"""Bul → indir → doğrula → ISO'ya dönüştür akışını yürüten arka plan işi."""
from __future__ import annotations

import re
import shutil
import threading
import time
import uuid as uuidlib
from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .api import APIError, UUPDumpAPI
from .config import data_dir
from .converter import (
    defender_exclusion,
    mount_dir_path,
    ConverterError,
    clean_job_dir,
    ensure_converter,
    is_admin,
    is_windows,
    prepare_job_dir,
    run_conversion,
)
from .downloader import Cancelled, DownloadError, Downloader, verify_files
from .i18n import t
from .library import sha256_file

CONVERT_PHASES = ("prep", "wim", "update", "save", "build")
STAGES = ("files_list", "download", "verify", *CONVERT_PHASES, "iso")


def safe_name(text: str) -> str:
    return re.sub(r"[^\w.\- ]+", "_", text, flags=re.UNICODE).strip(" ._") or "build"


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for i in range(2, 1000):
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
    return path


def work_dir_for(req: "JobRequest") -> Path:
    """ISO modunda bu işin geçici çalışma klasörü."""
    return Path(req.work_dir) / f"{req.uuid[:8]}_{req.lang}"


@dataclass
class JobRequest:
    uuid: str
    title: str
    build: str
    arch: str
    lang: str
    editions: list[str]
    mode: str  # "iso" | "download"
    options: dict = field(default_factory=dict)
    parallel: int = 4
    output_dir: str = ""
    work_dir: str = ""
    keep_files: bool = False
    defender: bool = False

    @property
    def stages(self) -> tuple[str, ...]:
        return STAGES if self.mode == "iso" else STAGES[:3]


def _fmt_dur(sec: float) -> str:
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s_ = divmod(rem, 60)
    return f"{h} sa {m} dk {s_} sn" if h else (f"{m} dk {s_} sn" if m else f"{s_} sn")


class JobWorker(QThread):
    stage = Signal(str)
    progress = Signal(dict)
    log = Signal(str)
    succeeded = Signal(dict)
    failed = Signal(str)
    stopped = Signal(str)  # "pause" | "cancel"

    def __init__(self, req: JobRequest, api: UUPDumpAPI) -> None:
        super().__init__()
        self.req = req
        self.api = api
        self.cancel_event = threading.Event()
        self.stop_kind = "pause"
        self._job_dir: Path | None = None
        self._phase = CONVERT_PHASES[0]
        self._mark: tuple[str, float] | None = None
        self._marks: list[tuple[str, float]] = []

    def request_stop(self, kind: str) -> None:
        self.stop_kind = kind
        self.cancel_event.set()

    # ------------------------------------------------------------------ iş
    def run(self) -> None:
        try:
            self._run()
        except Cancelled:
            if self.stop_kind == "cancel" and self._job_dir is not None:
                shutil.rmtree(self._job_dir, ignore_errors=True)
            self.stopped.emit(self.stop_kind)
        except (APIError, DownloadError, ConverterError) as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # beklenmeyen hata
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            # İş bitince API'ye bağlı geri çağrıları bırak (silinmiş işçiye işaret etmesinler).
            self.api.on_wait = None
            self.api.cancel = None
            self._log_summary()

    def _enter(self, key: str) -> None:
        """Aşamayı başlatır; öncekinin süresini kapatır ve günlüğe saat damgalı satır yazar."""
        if self._mark and self._mark[0] == key:
            return  # aynı aşama tekrar bildirildi
        now = time.time()
        self._close_mark(now)
        self._mark = (key, now)
        self.log.emit(t("job.phase_start", time=time.strftime("%H:%M:%S", time.localtime(now)),
                        name=t(f"stage.{key}")))
        self.stage.emit(key)

    def _close_mark(self, now: float) -> None:
        if self._mark:
            self._marks.append((self._mark[0], now - self._mark[1]))
            self._mark = None

    def _log_summary(self) -> None:
        self._close_mark(time.time())
        if len(self._marks) < 2:
            return
        total = sum(d for _, d in self._marks)
        self.log.emit(t("job.phase_summary"))
        for key, d in self._marks:
            self.log.emit(f"  {t(f'stage.{key}'):<14} {_fmt_dur(d)}")
        self.log.emit(f"  {t('job.phase_total'):<14} {_fmt_dur(total)}")
        self._marks = []

    def _on_phase(self, key: str) -> None:
        self._phase = key
        self._enter(key)
        self.progress.emit({"stage": key, "indeterminate": True})

    def _run(self) -> None:
        req = self.req
        self._enter("files_list")
        self.log.emit(t("job.log_fetching"))
        self.api.cancel = self.cancel_event
        self.api.on_wait = lambda sec: self.log.emit(t("job.log_rate_wait", n=int(sec)))
        try:
            fileset = self.api.get_files(req.uuid, req.lang, req.editions)
        except APIError as exc:
            if self.cancel_event.is_set():
                raise Cancelled() from exc
            if "UNSUPPORTED_COMBINATION" in str(exc) or "UNSUPPORTED_LANG" in str(exc):
                raise APIError(t("job.err_combination")) from exc
            if exc.status == 429:
                raise APIError(t("job.err_rate")) from exc
            raise
        if fileset.skipped:
            self.log.emit(t("job.log_skipped", editions=", ".join(fileset.skipped).upper()))
        total = sum(f.size for f in fileset.files)
        self.log.emit(t("job.log_files", n=len(fileset.files)))

        name = safe_name(req.title)
        if req.mode == "iso":
            self._job_dir = work_dir_for(req)
            uup_dir = self._job_dir / "UUPs"
        else:
            self._job_dir = None
            uup_dir = Path(req.output_dir) / f"{name}_{req.lang}_UUP"
        self.progress.emit(
            {
                "stage": "files_list",
                "done": 0,
                "total": total,
                "speed": 0,
                "eta": 0,
                "active": 0,
                "percent": 0.0,
                "files": [
                    {"name": f.name, "size": f.size, "done": 0, "state": "queued"}
                    for f in fileset.files
                ],
            }
        )

        # --- indirme
        self._enter("download")
        downloader = Downloader(
            fileset.files, uup_dir, workers=req.parallel, cancel=self.cancel_event
        )
        downloader.run(on_progress=lambda snap: self.progress.emit({**snap, "stage": "download"}))

        # --- doğrulama
        self._enter("verify")
        self.log.emit(t("job.log_verifying"))

        def on_verify(index: int, count: int, fname: str) -> None:
            self.progress.emit(
                {"stage": "verify", "percent": (index - 1) / max(1, count) * 100, "name": fname}
            )

        verify_files(fileset.files, uup_dir, self.cancel_event, on_verify)

        if req.mode == "download":
            self.succeeded.emit({"mode": "download", "folder": str(uup_dir), "title": req.title})
            return

        # --- dönüştürme
        self._phase = CONVERT_PHASES[0]
        self._enter(self._phase)
        self.progress.emit({"stage": self._phase, "indeterminate": True})
        if is_windows() and not is_admin():
            raise ConverterError(t("job.err_admin"))
        converter_dir = ensure_converter(
            data_dir() / "converter", lambda m: self.log.emit(m), self.cancel_event
        )
        assert self._job_dir is not None
        self.log.emit(t("job.log_cleaning"))
        self._job_dir = clean_job_dir(self._job_dir, lambda m: self.log.emit(m))
        prepare_job_dir(self._job_dir, converter_dir, req.options)
        self.log.emit(t("job.log_converting"))
        excluded = (
            defender_exclusion(True, [str(self._job_dir), mount_dir_path()], lambda m: self.log.emit(m))
            if req.defender
            else []
        )
        try:
            produced = run_conversion(
                self._job_dir,
                lambda m: self.log.emit(m),
                self.cancel_event,
                lambda pct, text: self.progress.emit(
                    {"stage": self._phase, "percent": pct, "text": text}
                ),
                self._on_phase,
            )
        finally:
            if excluded:
                defender_exclusion(False, excluded, lambda m: self.log.emit(m))

        # --- ISO'yu taşı + özet
        self._enter("iso")
        out_dir = Path(req.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        final = unique_path(out_dir / produced.name)
        shutil.move(str(produced), str(final))
        digest = sha256_file(
            final,
            self.cancel_event,
            lambda pct: self.progress.emit({"stage": "iso", "percent": pct}),
        )
        if not req.keep_files:
            shutil.rmtree(self._job_dir, ignore_errors=True)
        self.succeeded.emit(
            {
                "mode": "iso",
                "id": uuidlib.uuid4().hex,
                "title": req.title,
                "file": str(final),
                "size": final.stat().st_size,
                "created": int(time.time()),
                "editions": req.editions,
                "lang": req.lang,
                "arch": req.arch,
                "build": req.build,
                "sha256": digest,
            }
        )
