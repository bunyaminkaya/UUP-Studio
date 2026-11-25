"""Çok iş parçacıklı, devam edebilen indirici ve SHA-1 doğrulaması."""
from __future__ import annotations

import hashlib
import os
import socket
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .api import RemoteFile
from .config import APP_NAME, APP_VERSION

CHUNK = 1 << 20
USER_AGENT = f"{APP_NAME}/{APP_VERSION}"


class DownloadError(Exception):
    pass


class Cancelled(Exception):
    pass


@dataclass
class FileState:
    name: str
    size: int
    done: int = 0
    state: str = "queued"  # queued | downloading | done | error


class Downloader:
    def __init__(
        self,
        files: list[RemoteFile],
        dest: Path,
        workers: int = 4,
        cancel: threading.Event | None = None,
    ) -> None:
        self.files = files
        self.dest = Path(dest)
        self.workers = max(1, workers)
        self.cancel = cancel or threading.Event()
        self.states = {f.name: FileState(f.name, f.size) for f in files}
        self._stop = threading.Event()
        self._errors: list[str] = []
        self._lock = threading.Lock()
        self._samples: deque[tuple[float, int]] = deque(maxlen=40)

    # ------------------------------------------------------------- ilerleme
    def snapshot(self) -> dict:
        done = sum(s.done for s in self.states.values())
        total = sum(s.size for s in self.states.values())
        now = time.monotonic()
        self._samples.append((now, done))
        speed = 0.0
        while len(self._samples) > 2 and now - self._samples[0][0] > 6:
            self._samples.popleft()
        if len(self._samples) >= 2:
            t0, b0 = self._samples[0]
            if now > t0:
                speed = max(0.0, (done - b0) / (now - t0))
        eta = (total - done) / speed if speed > 1 and total > done else 0.0
        active = sum(1 for s in self.states.values() if s.state == "downloading")
        return {
            "done": done,
            "total": total,
            "speed": speed,
            "eta": eta,
            "active": active,
            "percent": (done / total * 100.0) if total else 0.0,
            "files": [
                {"name": s.name, "size": s.size, "done": s.done, "state": s.state}
                for s in self.states.values()
            ],
        }

    # ------------------------------------------------------------- çalıştırma
    def run(self, on_progress: Callable[[dict], None] | None = None, interval: float = 0.3) -> None:
        self.dest.mkdir(parents=True, exist_ok=True)
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            pending = {pool.submit(self._download_one, f) for f in self.files}
            while pending:
                finished, pending = wait(pending, timeout=interval, return_when=FIRST_COMPLETED)
                for fut in finished:
                    exc = fut.exception()
                    if exc is not None and not isinstance(exc, Cancelled):
                        with self._lock:
                            self._errors.append(str(exc))
                        self._stop.set()
                if self.cancel.is_set():
                    self._stop.set()
                if on_progress:
                    on_progress(self.snapshot())
        if self.cancel.is_set():
            raise Cancelled()
        if self._errors:
            raise DownloadError(self._errors[0])
        if on_progress:
            on_progress(self.snapshot())

    # ------------------------------------------------------------- tek dosya
    def _check_stop(self) -> None:
        if self.cancel.is_set() or self._stop.is_set():
            raise Cancelled()

    def _download_one(self, f: RemoteFile) -> None:
        state = self.states[f.name]
        path = self.dest / f.name
        part = path.with_name(path.name + ".part")
        if path.exists() and (f.size <= 0 or path.stat().st_size == f.size):
            state.size = state.size or path.stat().st_size
            state.done = state.size
            state.state = "done"
            return
        last_error = "unknown error"
        for attempt in range(1, 4):
            self._check_stop()
            try:
                state.state = "downloading"
                self._fetch(f, state, path, part)
                state.state = "done"
                return
            except Cancelled:
                state.state = "queued"
                raise
            except urllib.error.HTTPError as exc:
                if exc.code == 416 and part.exists():
                    if f.size and part.stat().st_size == f.size:
                        os.replace(part, path)
                        state.done = f.size
                        state.state = "done"
                        return
                    part.unlink(missing_ok=True)
                    last_error = "HTTP 416"
                elif exc.code in (401, 403, 404, 410):
                    state.state = "error"
                    raise DownloadError(f"{f.name}: HTTP {exc.code} (link expired?)") from exc
                else:
                    last_error = f"HTTP {exc.code}"
            except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as exc:
                last_error = str(exc)
            time.sleep(1.5 * attempt)
        state.state = "error"
        raise DownloadError(f"{f.name}: {last_error}")

    def _fetch(self, f: RemoteFile, state: FileState, path: Path, part: Path) -> None:
        resume = part.stat().st_size if part.exists() else 0
        if f.size and resume > f.size:
            part.unlink(missing_ok=True)
            resume = 0
        headers = {"User-Agent": USER_AGENT}
        if resume:
            headers["Range"] = f"bytes={resume}-"
        req = urllib.request.Request(f.url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as resp:
            append = bool(resume) and getattr(resp, "status", 200) == 206
            state.done = resume if append else 0
            if not state.size:
                length = resp.headers.get("Content-Length")
                if length and length.isdigit():
                    state.size = int(length) + (resume if append else 0)
            with open(part, "ab" if append else "wb") as out:
                while True:
                    self._check_stop()
                    chunk = resp.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    state.done += len(chunk)
        if f.size and part.stat().st_size != f.size:
            raise OSError(f"size mismatch ({part.stat().st_size}/{f.size})")
        os.replace(part, path)
        state.done = state.size = path.stat().st_size


def sha1_file(path: Path, cancel: threading.Event | None = None) -> str:
    digest = hashlib.sha1()
    with open(path, "rb") as fh:
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            block = fh.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def verify_files(
    files: list[RemoteFile],
    dest: Path,
    cancel: threading.Event | None = None,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> None:
    """Her dosyanın SHA-1 değerini API'nin verdiği değerle karşılaştırır."""
    todo = [f for f in files if f.sha1]
    for index, f in enumerate(todo, 1):
        if on_progress:
            on_progress(index, len(todo), f.name)
        path = Path(dest) / f.name
        if sha1_file(path, cancel) != f.sha1:
            path.unlink(missing_ok=True)  # bozuk dosya: yeniden indirilsin
            raise DownloadError(f"{f.name}: SHA-1 mismatch")
