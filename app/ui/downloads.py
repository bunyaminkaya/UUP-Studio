"""İndirmeler: aşamalar, ilerleme, dosya listesi ve günlük."""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..i18n import t
from ..jobs import CONVERT_PHASES, JobRequest
from .dialogs import info
from .widgets import BarDelegate, StepBar, card, fmt_eta, fmt_size, fmt_speed, label, separator, repolish


class DownloadsPage(QWidget):
    pauseRequested = Signal()
    resumeRequested = Signal()
    cancelRequested = Signal()
    openLibrary = Signal()
    openBrowser = Signal()
    openFolder = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.req: JobRequest | None = None
        self.state = "idle"  # idle | running | paused | failed | done
        self.stage = "files_list"
        self.result: dict | None = None
        self._last_snap: dict | None = None
        self._conv_text = ""
        self._conv_last = 0.0  # son çıktı zamanı
        self._ticker = QTimer(self)
        self._ticker.setInterval(1000)
        self._ticker.timeout.connect(self._tick_convert)
        self._rows: list[str] = []
        self._build_ui()
        self.retranslate()

    # ------------------------------------------------------------------ arayüz
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 48, 28, 26)
        root.setSpacing(18)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.h1 = label("", "h1")
        self.sub = label("", "muted")
        col.addWidget(self.h1)
        col.addWidget(self.sub)
        root.addLayout(col)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        # --- boş durum
        empty = QWidget()
        el = QVBoxLayout(empty)
        el.setContentsMargins(0, 0, 0, 0)
        box = card()
        bl = QVBoxLayout(box)
        bl.setContentsMargins(32, 32, 32, 32)
        bl.setSpacing(12)
        bl.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.lbl_empty_title = label("", "h2")
        self.lbl_empty_text = label("", "muted", wrap=True)
        self.btn_to_browser = QPushButton()
        self.btn_to_browser.setProperty("variant", "primary")
        self.btn_to_browser.clicked.connect(self.openBrowser.emit)
        bl.addWidget(self.lbl_empty_title)
        bl.addWidget(self.lbl_empty_text)
        bl.addWidget(self.btn_to_browser, 0, Qt.AlignmentFlag.AlignLeft)
        el.addWidget(box)
        el.addStretch(1)
        self.stack.addWidget(empty)

        # --- etkin iş
        active = QWidget()
        al = QVBoxLayout(active)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(18)
        job = card()
        jl = QVBoxLayout(job)
        jl.setContentsMargins(20, 20, 20, 20)
        jl.setSpacing(20)
        top = QHBoxLayout()
        tcol = QVBoxLayout()
        tcol.setSpacing(4)
        self.lbl_job = label("", "title", wrap=True)
        self.lbl_job_sub = label("", "faint")
        tcol.addWidget(self.lbl_job)
        tcol.addWidget(self.lbl_job_sub)
        top.addLayout(tcol, 1)
        self.btn_pause = QPushButton()
        self.btn_pause.clicked.connect(self._on_pause)
        self.btn_cancel = QPushButton()
        self.btn_cancel.setProperty("variant", "danger")
        self.btn_cancel.clicked.connect(self.cancelRequested.emit)
        self.btn_open = QPushButton()
        self.btn_open.setProperty("variant", "primary")
        self.btn_open.clicked.connect(self._on_open)
        top.addWidget(self.btn_pause)
        top.addWidget(self.btn_cancel)
        top.addWidget(self.btn_open)
        jl.addLayout(top)
        self.steps = StepBar()
        jl.addWidget(self.steps)
        prow = QHBoxLayout()
        self.lbl_head = label("", None)
        self.lbl_head.setStyleSheet("font-weight: 600;")
        self.lbl_pct = label("", "mono")
        prow.addWidget(self.lbl_head, 1)
        prow.addWidget(self.lbl_pct)
        jl.addLayout(prow)
        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setTextVisible(False)
        jl.addWidget(self.bar)
        self.lbl_stats = label("", "muted")
        self.lbl_stats.setTextFormat(Qt.TextFormat.RichText)
        jl.addWidget(self.lbl_stats)
        al.addWidget(job)

        bottom = QHBoxLayout()
        bottom.setSpacing(20)
        files = card()
        fl = QVBoxLayout(files)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(0)
        self.lbl_files = label("", "h2")
        self.lbl_files.setContentsMargins(18, 14, 18, 14)
        fl.addWidget(self.lbl_files)
        fl.addWidget(separator())
        self.table = QTableWidget(0, 4)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)  # boyut/durum tek satırda kalsın
        self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(46)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c, w in ((1, 110), (2, 110), (3, 130)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.table.setColumnWidth(c, w)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItemDelegateForColumn(2, BarDelegate(self.table))
        fl.addWidget(self.table, 1)
        bottom.addWidget(files, 1)

        logc = card()
        logc.setFixedWidth(330)
        ll = QVBoxLayout(logc)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(0)
        self.lbl_log = label("", "h2")
        self.btn_save_log = QPushButton()
        self.btn_save_log.clicked.connect(self._save_log)
        lhead = QHBoxLayout()
        lhead.setContentsMargins(18, 10, 14, 10)
        lhead.addWidget(self.lbl_log, 1)
        lhead.addWidget(self.btn_save_log)
        ll.addLayout(lhead)
        ll.addWidget(separator())
        self.log = QPlainTextEdit()
        self.log.setObjectName("log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(3000)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        ll.addWidget(self.log, 1)
        bottom.addWidget(logc)
        al.addLayout(bottom, 1)
        self.stack.addWidget(active)

    # ---------------------------------------------------------------- çeviri
    def retranslate(self) -> None:
        self.h1.setText(t("dl.title"))
        self.sub.setText(t("dl.subtitle"))
        self.lbl_empty_title.setText(t("dl.empty_title"))
        self.lbl_empty_text.setText(t("dl.empty_text"))
        self.btn_to_browser.setText(t("dl.go_browser"))
        self.btn_cancel.setText(t("dl.cancel"))
        self.lbl_files.setText(t("dl.files"))
        self.lbl_log.setText(t("dl.log"))
        self.btn_save_log.setText(t("dl.save_log"))
        self.table.setHorizontalHeaderLabels(
            [t("dl.col_file"), t("dl.col_size"), t("dl.col_progress"), t("dl.col_state")]
        )
        if self.req:
            self._refresh_steps()
            self._refresh_texts()
            if self._last_snap:
                self._update_stats(self._last_snap)
                self._update_table(self._last_snap.get("files", []))

    def refresh_theme(self) -> None:
        self.steps.update()
        self.table.viewport().update()
        if self._last_snap:
            self._update_stats(self._last_snap)

    # ---------------------------------------------------------------- durum
    def _refresh_steps(self) -> None:
        if not self.req:
            return
        keys = self.req.stages
        labels = [t(f"stage.{k}") for k in keys]
        if self.state == "done":
            idx = len(keys)
        else:
            idx = keys.index(self.stage) if self.stage in keys else 0
        self.steps.set_steps(labels, idx)

    def _refresh_texts(self) -> None:
        req = self.req
        if not req:
            return
        self.lbl_job.setText(req.title)
        mode = t("dl.mode_iso") if req.mode == "iso" else t("dl.mode_download")
        self.lbl_job_sub.setText(f"{req.lang} · {', '.join(req.editions)} · {mode}")
        running = self.state == "running"
        done = self.state == "done"
        self.btn_pause.setVisible(not done)
        self.btn_cancel.setVisible(not done)
        self.btn_open.setVisible(done)
        if running:
            self.btn_pause.setText(t("dl.pause"))
        elif self.state == "failed":
            self.btn_pause.setText(t("dl.retry"))
        else:
            self.btn_pause.setText(t("dl.resume"))
        if done:
            self.btn_open.setText(t("dl.show_library") if (self.result or {}).get("mode") == "iso" else t("dl.open_folder"))
        role = "danger" if self.state == "failed" else None
        self.lbl_head.setProperty("role", role)
        repolish(self.lbl_head)
        if self.state == "paused":
            self.lbl_head.setText(t("status.paused"))
        elif self.state == "done":
            key = "status.done_iso" if (self.result or {}).get("mode") == "iso" else "status.done_download"
            self.lbl_head.setText(t(key))
        elif self.state == "failed":
            pass  # hata metni fail() içinde ayarlanır
        else:
            self.lbl_head.setText(t(f"status.{self.stage}"))

    def show_job(self, req: JobRequest) -> None:
        self.req = req
        self.state = "running"
        self.stage = "files_list"
        self.result = None
        self._last_snap = None
        self._rows = []
        self.table.setRowCount(0)
        self.log.clear()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.lbl_pct.setText("")
        self.lbl_stats.setText("")
        self._refresh_steps()
        self._refresh_texts()
        self.stack.setCurrentIndex(1)

    def resume_view(self) -> None:
        """Duraklatılmış/başarısız işi yeniden başlatırken görünümü sıfırlar."""
        self.state = "running"
        self._refresh_texts()

    def reset(self) -> None:
        self.req = None
        self.state = "idle"
        self.stack.setCurrentIndex(0)

    def set_stage(self, key: str) -> None:
        self.stage = key
        if key in CONVERT_PHASES:
            if not self._ticker.isActive():
                self._conv_t0 = time.time()
            self._conv_last = time.time()
            self._conv_text = ""
            self.bar.setRange(0, 0)
            self.lbl_pct.setText("")
            self.lbl_stats.setText(t(f"dl.phase_{key}"))
            self._ticker.start()
        else:
            self._ticker.stop()
        if key in ("download", "files_list"):
            self.bar.setRange(0, 1000)
        self._refresh_steps()
        self._refresh_texts()

    def _tick_convert(self) -> None:
        """Dönüştürme sürerken geçen süreyi ve sessiz kalma süresini canlı göster."""
        if self.stage not in CONVERT_PHASES or self.state != "running":
            return
        now = time.time()
        mins = int((now - getattr(self, "_conv_t0", now)) // 60)
        idle = int((now - self._conv_last) // 60)
        text = f"{self._conv_text or t('dl.phase_' + self.stage)}  ·  {t('unit.min', n=mins)}"
        if idle >= 2:
            text += "  ·  " + t("dl.idle_note", n=idle)
        self.lbl_stats.setText(text)

    def set_log_file(self, path: Path) -> None:
        self._log_file = path

    def _save_log(self) -> None:
        """Günlüğü kullanıcının seçtiği dosyaya kaydeder (hata bildirimi için)."""
        src = getattr(self, "_log_file", None)
        default = src.name.replace(".log", ".txt") if src else "uup-studio-log.txt"
        target, _ = QFileDialog.getSaveFileName(self, t("dl.save_log_title"), default, "Text (*.txt)")
        if not target:
            return
        try:
            if src is not None and src.exists():
                text = src.read_text("utf-8", errors="replace")
            else:
                text = self.log.toPlainText()
            Path(target).write_text(text, encoding="utf-8")
        except OSError as exc:
            info(self, str(exc), icon="warn")

    def append_log(self, text: str) -> None:
        self.log.appendPlainText(text)

    # --------------------------------------------------------------- ilerleme
    def set_progress(self, snap: dict) -> None:
        stage = snap.get("stage")
        if "files" in snap:
            self._last_snap = snap
            self._update_table(snap["files"])
        if stage in ("download", "files_list"):
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(snap.get("percent", 0) * 10))
            self.lbl_pct.setText(f"{snap.get('percent', 0):.1f}%".replace(".", ",") if _tr() else f"{snap.get('percent', 0):.1f}%")
            self._update_stats(snap)
        elif stage == "verify":
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(snap.get("percent", 0) * 10))
            self.lbl_pct.setText(f"{snap.get('percent', 0):.0f}%")
            self.lbl_stats.setText(snap.get("name", ""))
        elif stage in CONVERT_PHASES:
            if "percent" in snap:
                pc = float(snap["percent"])
                if pc >= 99.9:  # alt adım bitti, sıradaki sürüyor: gerçek yüzde yok
                    self.bar.setRange(0, 0)
                    self.lbl_pct.setText("")
                else:
                    self.bar.setRange(0, 1000)
                    self.bar.setValue(int(pc * 10))
                    self.lbl_pct.setText(f"{pc:.0f}%")
                self._conv_text = str(snap.get("text", ""))[:110]
                self._conv_last = time.time()
                self._tick_convert()
            else:
                self.bar.setRange(0, 0)
                self.lbl_pct.setText("")
                self.lbl_stats.setText(t(f"dl.phase_{stage}"))
        elif stage == "iso":
            self.bar.setRange(0, 1000)
            self.bar.setValue(int(snap.get("percent", 0) * 10))
            self.lbl_pct.setText(f"{snap.get('percent', 0):.0f}%")
            self.lbl_stats.setText(t("dl.hashing"))

    def _update_stats(self, snap: dict) -> None:
        tx = theme.pal()["tx"]

        def bold(v: str) -> str:
            return f'<b style="color:{tx};font-weight:600">{v}</b>'

        parts = [
            f"{t('dl.speed')} {bold(fmt_speed(snap.get('speed', 0)))}",
            f"{t('dl.remaining')} {bold(fmt_eta(snap.get('eta', 0)))}",
            f"{t('dl.downloaded')} {bold(fmt_size(snap.get('done', 0)) + ' / ' + fmt_size(snap.get('total', 0)))}",
            f"{t('dl.connections')} {bold(str(snap.get('active', 0)))}",
        ]
        self.lbl_stats.setText("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;".join(parts))

    def _update_table(self, files: list[dict]) -> None:
        names = [f["name"] for f in files]
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPixelSize(13)
        if names != self._rows:
            self._rows = names
            self.table.setRowCount(len(files))
            for r in range(len(files)):
                for c in range(4):
                    item = QTableWidgetItem()
                    if c == 0:
                        item.setFont(mono)
                    self.table.setItem(r, c, item)
        states = {
            "queued": t("file.queued"),
            "done": t("file.done"),
            "error": t("file.error"),
        }
        for r, f in enumerate(files):
            size = f["size"] or 0
            pct = 100.0 if f["state"] == "done" else (f["done"] / size * 100 if size else 0.0)
            if f["state"] == "downloading":
                state = f"{pct:.0f}%"
            else:
                state = states.get(f["state"], f["state"])
            self._set(r, 0, f["name"])
            self._set(r, 1, fmt_size(size) if size else "-")
            self.table.item(r, 2).setData(Qt.ItemDataRole.UserRole, pct)
            self._set(r, 3, state)
        self.table.viewport().update()

    def _set(self, row: int, col: int, text: str) -> None:
        item = self.table.item(row, col)
        if item is not None and item.text() != text:
            item.setText(text)

    # ------------------------------------------------------------ sonuçlar
    def finish(self, result: dict) -> None:
        self.state = "done"
        self.result = result
        self.bar.setRange(0, 1000)
        self.bar.setValue(1000)
        self.lbl_pct.setText("100%")
        self.lbl_stats.setText(result.get("file") or result.get("folder", ""))
        self._refresh_steps()
        self._refresh_texts()

    def fail(self, message: str) -> None:
        self.state = "failed"
        self.bar.setRange(0, 1000)
        self._refresh_texts()
        self.lbl_head.setText(t("status.failed", msg=message))
        self.lbl_head.setWordWrap(True)
        self.append_log("ERROR: " + message)

    def paused(self) -> None:
        self.state = "paused"
        self.bar.setRange(0, 1000)
        self._refresh_texts()

    # ------------------------------------------------------------ düğmeler
    def _on_pause(self) -> None:
        if self.state == "running":
            self.pauseRequested.emit()
        else:
            self.resumeRequested.emit()

    def _on_open(self) -> None:
        if not self.result:
            return
        if self.result.get("mode") == "iso":
            self.openLibrary.emit()
        else:
            self.openFolder.emit(self.result.get("folder", ""))


def _tr() -> bool:
    from ..i18n import i18n

    return i18n.lang == "tr"
