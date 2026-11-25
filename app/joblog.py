"""Her iş için günlüğü diske yazar; kullanıcı sorun bildirirken bu dosyayı gönderebilir."""
from __future__ import annotations

import os
import platform
import time
from pathlib import Path

from .config import APP_NAME, APP_VERSION, log_dir

KEEP = 20  # saklanan en fazla günlük dosyası


class JobLog:
    def __init__(self, title: str) -> None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        self.path: Path = log_dir() / f"{stamp}.log"
        self._prune()
        self.append(f"{APP_NAME} {APP_VERSION} | {platform.platform()} | {title}")

    def append(self, text: str) -> None:
        try:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(text.rstrip("\n") + "\n")
        except OSError:
            pass

    @staticmethod
    def _prune() -> None:
        try:
            files = sorted(log_dir().glob("*.log"), key=os.path.getmtime, reverse=True)
            for old in files[KEEP - 1:]:
                old.unlink(missing_ok=True)
        except OSError:
            pass
