"""UUP dump JSON API istemcisi (listid, listlangs, listeditions, get)."""
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from .config import API_BASE, APP_NAME, APP_VERSION


class APIError(Exception):
    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Build:
    uuid: str
    title: str
    build: str
    arch: str
    created: int

    @property
    def is_preview(self) -> bool:
        return "insider preview" in self.title.lower()


@dataclass(frozen=True)
class Lang:
    code: str
    name: str


@dataclass(frozen=True)
class Edition:
    code: str
    name: str


@dataclass(frozen=True)
class RemoteFile:
    name: str
    url: str
    size: int
    sha1: str = ""


@dataclass
class FileSet:
    title: str
    arch: str
    build: str
    files: list[RemoteFile] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)  # desteklenmediği için atlanan edition'lar


def _int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class UUPDumpAPI:
    def __init__(self, base: str = API_BASE, timeout: int = 40) -> None:
        self.base = base.rstrip("/")
        self.timeout = timeout
        self.cancel: threading.Event | None = None  # bekleme sırasında iptal için
        self.on_wait = None  # callable(saniye): hız sınırı beklemesini bildirir
        self._cache: dict[str, tuple[float, dict]] = {}  # aynı isteği tekrarlama
        self._combined_unsupported: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------ temel
    def _request(self, endpoint: str, **params) -> dict:
        """Önbellek + 429 (hız sınırı) için bekleyip yeniden deneme."""
        key = endpoint + "?" + urllib.parse.urlencode(sorted(params.items()))
        hit = self._cache.get(key)
        if hit and time.time() - hit[0] < 600:
            return hit[1]
        delays = (8, 20, 45)
        for attempt in range(len(delays) + 1):
            try:
                data = self._request_once(endpoint, **params)
                self._cache[key] = (time.time(), data)
                return data
            except APIError as exc:
                net = exc.status == 0 and "cancelled" not in str(exc)
                if (exc.status != 429 and not net) or attempt >= (1 if net else len(delays)):
                    raise
                self._wait(3 if net else delays[attempt])
        raise APIError("HTTP 429: USER_RATE_LIMITED", 429)  # ulaşılmaz

    def _wait(self, seconds: float) -> None:
        if self.on_wait:
            self.on_wait(seconds)
        end = time.time() + seconds
        while time.time() < end:
            if self.cancel is not None and self.cancel.is_set():
                raise APIError("cancelled")
            time.sleep(0.25)

    def _request_once(self, endpoint: str, **params) -> dict:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v not in (None, "")})
        url = f"{self.base}/{endpoint}" + (f"?{query}" if query else "")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as exc:
            message = f"HTTP {exc.code}"
            try:
                body = json.loads(exc.read().decode("utf-8"))
                detail = (body.get("response") or body).get("error")
                if detail:
                    message = f"{message}: {detail}"
            except Exception:
                pass
            raise APIError(message, exc.code) from exc
        except urllib.error.URLError as exc:
            raise APIError(str(exc.reason)) from exc
        except OSError as exc:
            raise APIError(str(exc)) from exc
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            raise APIError("invalid JSON") from exc
        resp = data.get("response", data) if isinstance(data, dict) else {}
        if isinstance(resp, dict) and resp.get("error"):
            raise APIError(str(resp["error"]))
        return resp

    # --------------------------------------------------------------- uç noktalar
    def list_builds(self, search: str = "", sort_by_date: bool = True) -> list[Build]:
        resp = self._request("listid.php", search=search, sortByDate=1 if sort_by_date else 0)
        items = resp.get("builds", [])
        if isinstance(items, dict):
            items = list(items.values())
        builds: list[Build] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            uuid = str(item.get("uuid") or item.get("id") or "")
            if not uuid:
                continue
            builds.append(
                Build(
                    uuid=uuid,
                    title=str(item.get("title", "")),
                    build=str(item.get("build", "")),
                    arch=str(item.get("arch", "")).lower(),
                    created=_int(item.get("created")),
                )
            )
        if sort_by_date:
            builds.sort(key=lambda b: b.created, reverse=True)
        return builds

    def list_langs(self, uuid: str) -> list[Lang]:
        resp = self._request("listlangs.php", id=uuid)
        codes = resp.get("langList", [])
        names = resp.get("langFancyNames", {}) or {}
        return [Lang(c, str(names.get(c, c))) for c in codes]

    def list_editions(self, uuid: str, lang: str) -> list[Edition]:
        resp = self._request("listeditions.php", lang=lang, id=uuid)
        codes = resp.get("editionList", [])
        names = resp.get("editionFancyNames", {}) or {}
        return [Edition(c, str(names.get(c, c))) for c in codes]

    def get_files(self, uuid: str, lang: str, editions: list[str]) -> FileSet:
        codes = [e.lower() for e in editions]
        skipped: list[str] = []
        combo_key = (uuid, lang)
        try:
            if len(codes) > 1 and combo_key in self._combined_unsupported:
                raise APIError("UNSUPPORTED_COMBINATION", 400)
            resp = self._request("get.php", id=uuid, lang=lang, edition=";".join(codes))
            responses = [resp]
        except APIError as exc:
            # Bazı sarmalayıcılar ";" ile birleşik listeyi bölmez; edition'ları tek tek dene.
            if len(codes) < 2 or "UNSUPPORTED_COMBINATION" not in str(exc):
                raise
            self._combined_unsupported.add(combo_key)
            responses = []
            for i, code in enumerate(codes):
                if i:
                    self._wait(2)  # art arda istek hız sınırına takılmasın
                try:
                    responses.append(self._request("get.php", id=uuid, lang=lang, edition=code))
                except APIError as single:
                    if "UNSUPPORTED" not in str(single):
                        raise
                    skipped.append(code)
            if not responses:
                raise
        resp = responses[0]
        merged: dict = {}
        for r in responses:
            files_part = r.get("files", {})
            if isinstance(files_part, dict):
                merged.update(files_part)
        raw_files = merged
        files: list[RemoteFile] = []
        if isinstance(raw_files, dict):
            for name, info in raw_files.items():
                if isinstance(info, dict) and info.get("url"):
                    files.append(
                        RemoteFile(
                            name=str(name),
                            url=str(info["url"]),
                            size=_int(info.get("size")),
                            sha1=str(info.get("sha1", "")).lower(),
                        )
                    )
        if not files:
            raise APIError("EMPTY_FILELIST")
        return FileSet(
            title=str(resp.get("updateName", "")),
            arch=str(resp.get("arch", "")),
            build=str(resp.get("build", "")),
            files=files,
            skipped=skipped,
        )
