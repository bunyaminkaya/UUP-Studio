"""Çerçevesiz ana pencere: tam boy kenar çubuğu, sağ üstte pencere düğmeleri."""
from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QEvent, QUrl, Qt
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizeGrip,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..api import UUPDumpAPI
from ..config import APP_NAME, APP_VERSION, Settings
from ..converter import is_admin, is_windows, relaunch_as_admin
from ..i18n import i18n, t
from ..joblog import JobLog
from ..jobs import JobRequest, JobWorker, work_dir_for
from ..library import Library
from .advanced import AdvancedPage
from .browser import BrowserPage
from .dialogs import ask, info
from .downloads import DownloadsPage
from .library_page import LibraryPage
from .settings_page import SettingsPage
from .widgets import app_icon, label, svg_icon, svg_pixmap

TITLEBAR_H = 40
PAGE_BROWSER, PAGE_DOWNLOADS, PAGE_LIBRARY, PAGE_SETTINGS, PAGE_ADVANCED = range(5)
NAV = (
    ("search", "nav.browser"),
    ("download", "nav.downloads"),
    ("disc", "nav.library"),
    ("settings", "nav.settings"),
)


class MainWindow(QWidget):
    def __init__(self, settings: Settings, api: UUPDumpAPI, library: Library) -> None:
        super().__init__()
        self.settings, self.api, self.library = settings, api, library
        self.worker: JobWorker | None = None
        self.last_req: JobRequest | None = None

        self.setObjectName("root")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.resize(1280, 800)
        self.setMinimumSize(1100, 700)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._build_sidebar())

        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)
        self.browser = BrowserPage(api, settings)
        self.downloads = DownloadsPage()
        self.library_page = LibraryPage(library)
        self.settings_page = SettingsPage(settings)
        self.advanced = AdvancedPage(settings)
        for page in (self.browser, self.downloads, self.library_page, self.settings_page, self.advanced):
            self.stack.addWidget(page)

        self._build_controls()
        self.grip = QSizeGrip(self)
        self.grip.setFixedSize(16, 16)

        # --- sinyaller
        self.browser.startRequested.connect(self.start_job)
        self.browser.openAdvanced.connect(lambda: self._goto(PAGE_ADVANCED, nav=0))
        self.advanced.back.connect(lambda: self._goto(PAGE_BROWSER))
        self.advanced.changed.connect(self.browser.update_cta_text)
        self.downloads.pauseRequested.connect(self._pause)
        self.downloads.resumeRequested.connect(self._resume)
        self.downloads.cancelRequested.connect(self._cancel)
        self.downloads.openBrowser.connect(lambda: self._goto(PAGE_BROWSER))
        self.downloads.openLibrary.connect(self._show_library)
        self.downloads.openFolder.connect(lambda p: QDesktopServices.openUrl(QUrl.fromLocalFile(p)))
        self.settings_page.languageChanged.connect(lambda lang: i18n.set_language(lang))
        self.settings_page.themeChanged.connect(lambda _name: self.apply_theme())
        i18n.changed.connect(self.retranslate)
        QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_scheme_changed)

        self.nav_buttons[0].setChecked(True)
        self.retranslate()

    # --------------------------------------------------------------- yapı
    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("sidebar")
        side.setFixedWidth(216)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(10, 0, 10, 16)
        lay.setSpacing(4)

        brand = QWidget()
        brand.setFixedHeight(TITLEBAR_H)
        bl = QHBoxLayout(brand)
        bl.setContentsMargins(6, 0, 0, 0)
        bl.setSpacing(10)
        self.brand_logo = label("")
        self.brand_logo.setFixedSize(20, 20)
        self.brand_logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = label(APP_NAME)
        name.setStyleSheet("font-weight: 600; font-size: 13px;")
        bl.addWidget(self.brand_logo)
        bl.addWidget(name)
        bl.addStretch(1)
        lay.addWidget(brand)
        lay.addSpacing(12)

        self.nav_group = QButtonGroup(self)
        self.nav_buttons: list[QPushButton] = []
        for i, (_icon, _key) in enumerate(NAV):
            b = QPushButton()
            b.setCheckable(True)
            b.setProperty("nav", True)
            b.setIconSize(b.iconSize().__class__(18, 18))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.nav_group.addButton(b, i)
            self.nav_buttons.append(b)
            lay.addWidget(b)
            b.toggled.connect(lambda _c, self=self: self._refresh_nav_icons())
        self.nav_group.idClicked.connect(self._on_nav)
        lay.addStretch(1)
        self.lbl_version = label(f"v{APP_VERSION}", "faint")
        self.lbl_version.setContentsMargins(12, 0, 0, 0)
        lay.addWidget(self.lbl_version)
        return side

    def _build_controls(self) -> None:
        self.controls = QWidget(self)
        cl = QHBoxLayout(self.controls)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.btn_min = self._ctl("min", self.showMinimized)
        self.btn_max = self._ctl("max", self._toggle_max)
        self.btn_close = self._ctl("close", self.close, close=True)
        for b in (self.btn_min, self.btn_max, self.btn_close):
            cl.addWidget(b)
        self.controls.setFixedSize(46 * 3, TITLEBAR_H)

    def _ctl(self, icon: str, slot, close: bool = False) -> QToolButton:
        b = QToolButton()
        b.setProperty("winctl", True)
        if close:
            b.setProperty("close", True)
        b.setFixedSize(46, TITLEBAR_H)
        b.setCursor(Qt.CursorShape.ArrowCursor)
        b.clicked.connect(slot)
        b.setProperty("icon_name", icon)
        return b

    # ----------------------------------------------------------- tema / dil
    def apply_theme(self) -> None:
        theme.apply(QApplication.instance(), self.settings.theme)
        self.refresh_theme()

    def _system_scheme_changed(self, *_args) -> None:
        if self.settings.theme == "system":
            self.apply_theme()

    def refresh_theme(self) -> None:
        pal = theme.pal()
        self.brand_logo.setStyleSheet(f"background: {pal['acc']}; border-radius: 5px;")
        self.brand_logo.setPixmap(svg_pixmap("logo", pal["onAcc"], 12, 3.0))
        self._refresh_nav_icons()
        self._refresh_controls()
        for page in (self.downloads, self.library_page, self.settings_page):
            page.refresh_theme()

    def _refresh_nav_icons(self) -> None:
        pal = theme.pal()
        for (icon, _key), b in zip(NAV, self.nav_buttons):
            b.setIcon(svg_icon(icon, pal["accTx"] if b.isChecked() else pal["nav"], 18))

    def _refresh_controls(self) -> None:
        pal = theme.pal()
        maximized = self.isMaximized()
        self.btn_min.setIcon(svg_icon("min", pal["mu"], 14))
        self.btn_max.setIcon(svg_icon("restore" if maximized else "max", pal["mu"], 14))
        self.btn_close.setIcon(svg_icon("close", pal["mu"], 14))
        self.btn_min.setToolTip(t("win.minimize"))
        self.btn_max.setToolTip(t("win.restore") if maximized else t("win.maximize"))
        self.btn_close.setToolTip(t("win.close"))

    def retranslate(self) -> None:
        for b, (_icon, key) in zip(self.nav_buttons, NAV):
            b.setText("  " + t(key))
        self.browser.retranslate()
        self.downloads.retranslate()
        self.library_page.retranslate()
        self.settings_page.retranslate()
        self.advanced.retranslate()
        self._refresh_controls()

    # --------------------------------------------------------- gezinme
    def _on_nav(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        if index == PAGE_LIBRARY:
            self.library_page.reload()

    def _goto(self, page: int, nav: int | None = None) -> None:
        self.stack.setCurrentIndex(page)
        target = nav if nav is not None else (page if page < len(self.nav_buttons) else 0)
        self.nav_buttons[target].setChecked(True)

    def _show_library(self) -> None:
        self.library_page.reload()
        self._goto(PAGE_LIBRARY)

    def first_run_notice(self) -> None:
        """İlk açılışta bir kez: kaynak, lisans ve Defender dışlaması hakkında kısa bilgi."""
        if self.settings.accepted_notice:
            return
        info(self, t("notice.first_run"), title=t("notice.title"))
        self.settings.accepted_notice = True
        self.settings.save()

    # ----------------------------------------------------------- işler
    def start_job(self, req: JobRequest) -> None:
        if self.worker is not None and self.worker.isRunning():
            info(self, t("job.busy"))
            self._goto(PAGE_DOWNLOADS)
            return
        if req.mode == "iso" and is_windows() and not is_admin():
            if ask(self, t("job.need_admin"), t("adv.admin_btn"), t("dlg.cancel")) and relaunch_as_admin():
                QApplication.quit()
            return
        self.last_req = req
        self.downloads.show_job(req)
        self._launch(req)
        self._goto(PAGE_DOWNLOADS)

    def _launch(self, req: JobRequest) -> None:
        worker = JobWorker(req, self.api)
        joblog = JobLog(req.title)
        self.downloads.set_log_file(joblog.path)
        worker.log.connect(joblog.append)
        worker.failed.connect(lambda m: joblog.append("ERROR: " + m))
        worker.stage.connect(self.downloads.set_stage)
        worker.progress.connect(self.downloads.set_progress)
        worker.log.connect(self.downloads.append_log)
        worker.succeeded.connect(self._on_success)
        worker.failed.connect(self.downloads.fail)
        worker.stopped.connect(self._on_stopped)
        worker.finished.connect(lambda w=worker: self._worker_finished(w))
        self.worker = worker
        worker.start()

    def _worker_finished(self, worker: JobWorker) -> None:
        if self.worker is worker:
            self.worker = None
        worker.deleteLater()

    def _on_success(self, result: dict) -> None:
        if result.get("mode") == "iso":
            entry = {k: v for k, v in result.items() if k != "mode"}
            self.library.add(entry)
            self.library_page.reload()
        self.downloads.finish(result)
        QApplication.alert(self, 3000)

    def _pause(self) -> None:
        if self.worker is not None:
            self.worker.request_stop("pause")

    def _resume(self) -> None:
        if self.last_req is None or (self.worker is not None and self.worker.isRunning()):
            return
        self.downloads.resume_view()
        self._launch(self.last_req)

    def _cancel(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop("cancel")
            return
        if self.last_req is not None and self.last_req.mode == "iso":
            shutil.rmtree(work_dir_for(self.last_req), ignore_errors=True)
        self.downloads.reset()

    def _on_stopped(self, kind: str) -> None:
        if kind == "pause":
            self.downloads.paused()
        else:
            self.downloads.reset()

    # -------------------------------------------------- pencere davranışı
    def _toggle_max(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.controls.move(self.width() - self.controls.width(), 0)
        self.controls.raise_()
        self.grip.move(self.width() - 16, self.height() - 16)
        self.grip.raise_()
        self.grip.setVisible(not self.isMaximized())

    def changeEvent(self, event) -> None:
        if event.type() == QEvent.Type.WindowStateChange:
            self._refresh_controls()
        super().changeEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < TITLEBAR_H:
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < TITLEBAR_H:
            self._toggle_max()
            return
        super().mouseDoubleClickEvent(event)

    def closeEvent(self, event) -> None:
        if self.worker is not None and self.worker.isRunning():
            if not ask(
                self, t("job.close_confirm"), t("job.close_yes"), t("dlg.cancel"), default_cancel=True
            ):
                event.ignore()
                return
            self.worker.request_stop("pause")
            self.worker.wait(8000)
        event.accept()
