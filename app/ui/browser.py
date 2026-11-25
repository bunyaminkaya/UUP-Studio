"""Build Gezgini: build'i bul, dil/edition seç, tek tuşla indir ve ISO yap."""
from __future__ import annotations

import json
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..api import Build, UUPDumpAPI
from ..config import Settings, data_dir
from ..i18n import t
from ..jobs import JobRequest
from .dialogs import ask
from .widgets import Seg, card, repolish, fmt_date, label, run_task, separator

DEFAULT_EDITIONS = ("professional",)  # her edition DISM süresini katlar; Home isteğe bağlı


def _needs_integration(title: str) -> bool:
    """Taban sürüm + kümülatif güncelleme paketi olan build'ler: güncelleme DISM ile her edition'a
    tek tek işlenir (saatler sürer). 'Windows 11, version ...' tam build'leri bunu gerektirmez."""
    low = title.lower()
    return low.startswith(("preview update", "cumulative update", "update for windows")) and "version" not in low


_UPDATE_ONLY = (".net framework", "critical oobe", "safe os", "servicing stack", "setup dynamic")


def _update_only(title: str) -> bool:
    low = title.lower()
    return any(k in low for k in _UPDATE_ONLY)


class BrowserPage(QWidget):
    startRequested = Signal(object)
    openAdvanced = Signal()
    _waitInfo = Signal(float)

    def __init__(self, api: UUPDumpAPI, settings: Settings) -> None:
        super().__init__()
        self.api, self.settings = api, settings
        self._tasks: set = set()
        self._waitInfo.connect(lambda sec: self.lbl_status.setText(t("browser.rate_wait", n=int(sec))))
        self._builds: list[Build] = []
        self._shown: list[Build] = []
        self._sel: Build | None = None
        self._token = 0
        self._lang_token = 0
        self._ed_token = 0
        self._build_ui()
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._search_remote)
        self.retranslate()

    # ------------------------------------------------------------------ arayüz
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 48, 28, 26)
        root.setSpacing(18)

        head = QHBoxLayout()
        col = QVBoxLayout()
        col.setSpacing(4)
        self.h1 = label("", "h1")
        self.sub = label("", "muted")
        col.addWidget(self.h1)
        col.addWidget(self.sub)
        head.addLayout(col, 1)
        self.btn_refresh = QPushButton()
        self.btn_refresh.clicked.connect(self.reload)
        head.addWidget(self.btn_refresh, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        filt = QHBoxLayout()
        filt.setSpacing(12)
        self.channel = Seg([("stable", ""), ("preview", ""), ("all", "")])
        self.arch = Seg([("amd64", "x64"), ("arm64", "arm64"), ("x86", "x86")])
        self.search = QLineEdit()
        self.search.setFixedWidth(260)
        self.search.setClearButtonEnabled(True)
        filt.addWidget(self.channel)
        filt.addWidget(self.arch)
        filt.addStretch(1)
        filt.addWidget(self.search)
        root.addLayout(filt)
        self.channel.changed.connect(lambda _v: self._fill())
        self.arch.changed.connect(lambda _v: self._fill())
        self.search.textChanged.connect(self._on_search)

        body = QHBoxLayout()
        body.setSpacing(20)
        root.addLayout(body, 1)

        # --- tablo kartı
        table_card = card()
        tl = QVBoxLayout(table_card)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(0)
        top = QHBoxLayout()
        top.setContentsMargins(18, 14, 18, 14)
        self.lbl_list = label("", "h2")
        self.lbl_status = label("", "faint")
        top.addWidget(self.lbl_list)
        top.addStretch(1)
        top.addWidget(self.lbl_status)
        tl.addLayout(top)
        tl.addWidget(separator())
        self.table = QTableWidget(0, 4)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(56)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        hh.setHighlightSections(False)
        hh.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 130)
        self.table.itemSelectionChanged.connect(self._on_select)
        tl.addWidget(self.table, 1)
        body.addWidget(table_card, 1)

        # --- yan panel
        aside = card()
        aside.setFixedWidth(330)
        # İçerik kaydırılabilir alanda: pencere küçülünce etiketler ezilip üst üste binmez.
        outer = QVBoxLayout(aside)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}")
        body_w = QWidget()
        body_w.setObjectName("asidebody")
        body_w.setStyleSheet("QWidget#asidebody{background:transparent;}")
        scroll.setWidget(body_w)
        outer.addWidget(scroll)
        al = QVBoxLayout(body_w)
        al.setContentsMargins(20, 20, 20, 20)
        al.setSpacing(12)
        self.cap_sel = label("", "caption")
        self.lbl_title = label("-", "title", wrap=True)
        self.lbl_build = label("", "accent")
        al.addWidget(self.cap_sel)
        al.addWidget(self.lbl_title)
        al.addWidget(self.lbl_build)
        al.addWidget(separator())
        self.kv = {}
        for key in ("channel", "arch", "added"):
            row = QHBoxLayout()
            k = label("", "muted")
            v = label("-")
            row.addWidget(k)
            row.addStretch(1)
            row.addWidget(v)
            al.addLayout(row)
            self.kv[key] = (k, v)
        al.addWidget(separator())
        self.cap_lang = label("", "small")
        self.combo_lang = QComboBox()
        self.combo_lang.currentIndexChanged.connect(self._on_lang)
        self.cap_ed = label("", "small")
        self.list_ed = QListWidget()
        self.list_ed.setFixedHeight(112)
        self.list_ed.itemChanged.connect(lambda _i: self._update_cta())
        al.addWidget(self.cap_lang)
        al.addWidget(self.combo_lang)
        al.addWidget(self.cap_ed)
        al.addWidget(self.list_ed)
        self.lbl_msg = label("", "small", wrap=True)
        al.addWidget(self.lbl_msg)
        self.btn_go = QPushButton()
        self.btn_go.setProperty("variant", "primary")
        self.btn_go.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_go.clicked.connect(self._start)
        self.btn_adv = QPushButton()
        self.btn_adv.clicked.connect(self.openAdvanced.emit)
        self.lbl_note = label("", "small", wrap=True)
        self.lbl_note.setMinimumHeight(62)
        al.addWidget(self.btn_go)
        al.addWidget(self.btn_adv)
        al.addWidget(self.lbl_note)
        al.addStretch(1)
        body.addWidget(aside)

    # ---------------------------------------------------------------- çeviri
    def retranslate(self) -> None:
        self.h1.setText(t("browser.title"))
        self.sub.setText(t("browser.subtitle"))
        self.btn_refresh.setText(t("browser.refresh"))
        self.channel.set_text("stable", t("browser.ch_stable"))
        self.channel.set_text("preview", t("browser.ch_preview"))
        self.channel.set_text("all", t("browser.ch_all"))
        self.search.setPlaceholderText(t("browser.search"))
        self.lbl_list.setText(t("browser.list_title"))
        self.table.setHorizontalHeaderLabels(
            [t("browser.col_build"), t("browser.col_version"), t("browser.col_arch"), t("browser.col_added")]
        )
        self.cap_sel.setText(t("browser.selected").upper())
        self.kv["channel"][0].setText(t("browser.kv_channel"))
        self.kv["arch"][0].setText(t("browser.kv_arch"))
        self.kv["added"][0].setText(t("browser.kv_added"))
        self.cap_lang.setText(t("browser.language"))
        self.cap_ed.setText(t("browser.editions"))
        self.btn_adv.setText(t("browser.advanced"))
        self.lbl_note.setText(t("browser.note"))
        self._update_status()
        self._select_labels()
        self.update_cta_text()

    def update_cta_text(self) -> None:
        key = "browser.cta_iso" if self.settings.output_mode == "iso" else "browser.cta_download"
        self.btn_go.setText(t(key))

    # ------------------------------------------------------------------ veri
    def reload(self) -> None:
        self._load(self.search.text().strip())

    def _on_search(self, _text: str) -> None:
        self._fill()
        self._debounce.start(600)

    def _search_remote(self) -> None:
        text = self.search.text().strip()
        if len(text) >= 3:
            self._load(text)

    def _load(self, query: str) -> None:
        self._token += 1
        token = self._token
        self.lbl_status.setText(t("browser.loading"))
        self.lbl_status.setProperty("role", "faint")
        self.btn_refresh.setEnabled(False)
        if not query and not self._builds:
            cached = self._read_cache()
            if cached:  # liste hemen görünsün; güncelleme arkada sürer
                self._builds = cached
                self._fill()
                self.lbl_status.setText(t("browser.refreshing"))

        def ok(builds: list[Build]) -> None:
            if token != self._token:
                return
            self._builds = builds
            if not query:
                self._write_cache(builds)
            self.btn_refresh.setEnabled(True)
            self._fill()

        def err(msg: str) -> None:
            if token != self._token:
                return
            self.btn_refresh.setEnabled(True)
            self.lbl_status.setText(t("browser.load_error", msg=msg))

        def work(q: str):
            self.api.on_wait = self._waitInfo.emit  # hız sınırı beklemesini göster
            try:
                return self.api.list_builds(q, True)
            finally:
                self.api.on_wait = None

        run_task(self._tasks, work, ok, err, query)

    @staticmethod
    def _cache_path():
        return data_dir() / "builds_cache.json"

    def _read_cache(self) -> list[Build]:
        try:
            raw = json.loads(self._cache_path().read_text(encoding="utf-8"))
            return [Build(**b) for b in raw.get("builds", [])]
        except Exception:
            return []

    def _write_cache(self, builds: list[Build]) -> None:
        try:
            data = {"saved": int(time.time()), "builds": [b.__dict__ for b in builds]}
            self._cache_path().write_text(json.dumps(data), encoding="utf-8")
        except Exception:
            pass

    def _fill(self) -> None:
        mode = self.channel.value()
        arch = self.arch.value()
        q = self.search.text().strip().lower()
        rows = []
        for b in self._builds:
            if b.arch != arch:
                continue
            if mode != "all" and _update_only(b.title):
                continue  # .NET/OOBE gibi paketlerden ISO çıkmaz
            if mode == "stable" and b.is_preview:
                continue
            if mode == "preview" and not b.is_preview:
                continue
            if q and q not in b.title.lower() and q not in b.build.lower():
                continue
            rows.append(b)
        self._shown = rows[:300]
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setPixelSize(13)
        keep = self._sel.uuid if self._sel else None
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._shown))
        for r, b in enumerate(self._shown):
            cells = [b.build, b.title, b.arch.replace("amd64", "x64"), fmt_date(b.created)]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c in (0, 2):
                    item.setFont(mono)
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, b)
                self.table.setItem(r, c, item)
            if keep and b.uuid == keep:
                self.table.selectRow(r)
        self.table.blockSignals(False)
        self._update_status()
        if self._shown and not any(b.uuid == keep for b in self._shown):
            self.table.selectRow(0)  # sinyal açık: dil/edition yüklenir

    def _update_status(self) -> None:
        if self._builds:
            self.lbl_status.setText(t("browser.count", n=len(self._shown)))
        elif not self.lbl_status.text():
            self.lbl_status.setText("")

    # -------------------------------------------------------------- seçim
    def _on_select(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        item = self.table.item(rows[0].row(), 0)
        build = item.data(Qt.ItemDataRole.UserRole) if item else None
        if build is None or (self._sel and build.uuid == self._sel.uuid):
            return
        self._sel = build
        self._select_labels()
        self._load_langs()

    def _select_labels(self) -> None:
        b = self._sel
        if not b:
            self.lbl_title.setText(t("browser.none_selected"))
            self.lbl_build.setText("")
            for _k, v in self.kv.values():
                v.setText("-")
            self._update_cta()
            return
        self.lbl_title.setText(b.title)
        self.lbl_build.setText(b.build)
        self.kv["channel"][1].setText(t("browser.ch_preview") if b.is_preview else t("browser.ch_stable"))
        self.kv["arch"][1].setText(b.arch.replace("amd64", "x64"))
        self.kv["added"][1].setText(fmt_date(b.created))
        self._update_cta()

    def _msg(self, text: str, role: str = "small") -> None:
        self.lbl_msg.setText(text)
        self.lbl_msg.setProperty("role", role)
        repolish(self.lbl_msg)
        self.lbl_note.setVisible(role != "danger")  # yer açmak için

    def _load_langs(self) -> None:
        assert self._sel
        self._lang_token += 1
        token, uuid = self._lang_token, self._sel.uuid
        self.combo_lang.blockSignals(True)
        self.combo_lang.clear()
        self.combo_lang.blockSignals(False)
        self.list_ed.clear()
        self.cap_ed.setVisible(True)
        self.list_ed.setVisible(True)
        self._msg(t("browser.loading"))
        self._update_cta()

        def ok(langs) -> None:
            if token != self._lang_token:
                return
            self.combo_lang.blockSignals(True)
            for lang in langs:
                self.combo_lang.addItem(f"{lang.name}  ({lang.code})", lang.code)
            codes = [lang.code for lang in langs]
            for wanted in (self.settings.last_lang, "tr-tr", "en-us"):
                if wanted in codes:
                    self.combo_lang.setCurrentIndex(codes.index(wanted))
                    break
            self.combo_lang.blockSignals(False)
            if not langs:
                # Dil paketi olmayan build'ler (.NET / kümülatif güncelleme) ISO üretemez.
                self.cap_ed.setVisible(False)
                self.list_ed.setVisible(False)  # boş liste yerine açıklama sığsın
                self._msg(t("browser.no_langs"), "danger")
                self._update_cta()
                return
            self._msg("")
            self._on_lang()

        def err(msg: str) -> None:
            if token == self._lang_token:
                self._msg(t("browser.load_error", msg=msg), "danger")

        run_task(self._tasks, self.api.list_langs, ok, err, uuid)

    def _on_lang(self) -> None:
        lang = self.combo_lang.currentData()
        if not self._sel or not lang:
            return
        self.settings.last_lang = lang
        self.settings.save()
        self._ed_token += 1
        token, uuid = self._ed_token, self._sel.uuid
        self.list_ed.clear()
        self._update_cta()

        def ok(editions) -> None:
            if token != self._ed_token:
                return
            self.list_ed.blockSignals(True)
            any_default = any(e.code.lower() in DEFAULT_EDITIONS for e in editions)
            for i, e in enumerate(editions):
                item = QListWidgetItem(e.name)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                checked = e.code.lower() in DEFAULT_EDITIONS if any_default else i == 0
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
                item.setData(Qt.ItemDataRole.UserRole, e.code)
                self.list_ed.addItem(item)
            self.list_ed.blockSignals(False)
            if not editions:
                self._msg(t("browser.no_editions"), "danger")
            elif self._sel and _needs_integration(self._sel.title):
                self._msg(t("browser.slow_build"), "ok")
            else:
                self._msg("")
            self._update_cta()

        def err(msg: str) -> None:
            if token == self._ed_token:
                self._msg(t("browser.load_error", msg=msg), "danger")

        run_task(self._tasks, self.api.list_editions, ok, err, uuid, lang)

    def _checked_editions(self) -> list[str]:
        out = []
        for i in range(self.list_ed.count()):
            item = self.list_ed.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                out.append(item.data(Qt.ItemDataRole.UserRole))
        return out

    def _update_cta(self) -> None:
        self.btn_go.setEnabled(bool(self._sel and self.combo_lang.currentData() and self._checked_editions()))

    def _start(self) -> None:
        editions = self._checked_editions()
        lang = self.combo_lang.currentData()
        if not (self._sel and lang and editions):
            self._msg(t("browser.pick_edition"), "danger")
            return
        s = self.settings
        if s.output_mode == "iso" and _needs_integration(self._sel.title):
            if not ask(
                self,
                t("browser.slow_confirm", n=len(editions)),
                t("browser.slow_go"),
                t("dlg.cancel"),
                title=t("browser.slow_title"),
                default_cancel=True,
            ):
                return
        self.startRequested.emit(
            JobRequest(
                uuid=self._sel.uuid,
                title=self._sel.title,
                build=self._sel.build,
                arch=self._sel.arch,
                lang=lang,
                editions=editions,
                mode=s.output_mode,
                options=s.converter_options(),
                parallel=s.parallel_files,
                output_dir=s.output_dir,
                work_dir=s.work_dir,
                keep_files=s.keep_uup_files,
                defender=s.defender_exclusion,
            )
        )
