"""UUP Studio - uygulama girişi."""
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _install_excepthook() -> None:
    from app.config import data_dir

    log = Path(data_dir()) / "error.log"

    def hook(exc_type, exc, tb) -> None:
        try:
            with open(log, "a", encoding="utf-8") as fh:
                fh.write("".join(traceback.format_exception(exc_type, exc, tb)) + "\n")
        except OSError:
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = hook


def main() -> int:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.api import UUPDumpAPI
    from app.config import APP_NAME, Settings
    from app.i18n import i18n
    from app.library import Library
    from app.ui.widgets import app_icon
    from app.ui.window import MainWindow

    _install_excepthook()
    # ISO dönüştürme yönetici izni ister: en başta bir kez UAC iste, ayar/seçim kaybı olmasın.
    if os.name == "nt" and "--no-elevate" not in sys.argv:
        from app.converter import is_admin, relaunch_as_admin

        if not is_admin() and relaunch_as_admin():
            return 0
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("UUPStudio.App")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(app_icon())

    settings = Settings.load()
    i18n.set_language(settings.language, emit=False)
    window = MainWindow(settings, UUPDumpAPI(), Library())
    window.apply_theme()
    window.show()
    QTimer.singleShot(0, window.browser.reload)
    QTimer.singleShot(400, window.first_run_notice)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
