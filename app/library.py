"""Oluşturulan ISO'ların kütüphanesi (JSON)."""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Callable

from .config import data_dir
from .downloader import Cancelled


def sha256_file(
    path: Path,
    cancel: threading.Event | None = None,
    on_percent: Callable[[float], None] | None = None,
) -> str:
    digest = hashlib.sha256()
    total = max(1, Path(path).stat().st_size)
    done = 0
    last = -1
    with open(path, "rb") as fh:
        while True:
            if cancel is not None and cancel.is_set():
                raise Cancelled()
            block = fh.read(1 << 20)
            if not block:
                break
            digest.update(block)
            done += len(block)
            if on_percent:
                pct = int(done * 100 / total)
                if pct != last:
                    last = pct
                    on_percent(float(pct))
    return digest.hexdigest()


class Library:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else data_dir() / "library.json"
        self.entries: list[dict] = []
        self.load()

    def load(self) -> None:
        try:
            self.entries = json.loads(self.path.read_text("utf-8"))
        except (OSError, ValueError):
            self.entries = []
        self.entries.sort(key=lambda e: e.get("created", 0), reverse=True)

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self.entries, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def add(self, entry: dict) -> None:
        self.entries = [e for e in self.entries if e.get("file") != entry.get("file")]
        self.entries.insert(0, entry)
        self.save()

    def remove(self, entry_id: str, delete_file: bool = False) -> None:
        for entry in list(self.entries):
            if entry.get("id") == entry_id:
                if delete_file:
                    try:
                        Path(entry["file"]).unlink(missing_ok=True)
                    except OSError:
                        pass
                self.entries.remove(entry)
        self.save()

    @staticmethod
    def exists(entry: dict) -> bool:
        return Path(entry.get("file", "")).is_file()
