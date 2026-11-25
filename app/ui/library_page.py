"""Kütüphane: otomatik oluşturulan ISO'ların listesi."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..i18n import t
from ..library import Library
from .dialogs import ask
from .widgets import card, fmt_date, fmt_size, label, repolish, separator, svg_pixmap


class IsoCard(QFrame):
    def __init__(self, entry: dict, on_click) -> None:
        super().__init__()
        self.entry = entry
        self._on_click = on_click
        self.setProperty("isocard", True)
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(16)
        self.icon = QFrame()
        self.icon.setFixedSize(44, 44)
        il = QVBoxLayout(self.icon)
        il.setContentsMargins(0, 0, 0, 0)
        self.icon_lbl = label("")
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.addWidget(self.icon_lbl)
        col = QVBoxLayout()
        col.setSpacing(4)
        self.title = label(entry.get("title", ""), None, wrap=True)
        self.title.setStyleSheet("font-weight: 600; font-size: 15px;")
        self.file = label(Path(entry.get("file", "")).name, "mono")
        meta = f"{', '.join(entry.get('editions', []))} · {fmt_date(entry.get('created', 0))} · {fmt_size(entry.get('size', 0))}"
        if not Library.exists(entry):
            meta += " · " + t("lib.missing")
        self.meta = label(meta, "small")
        col.addWidget(self.title)
        col.addWidget(self.file)
        col.addWidget(self.meta)
        lay.addWidget(self.icon, 0, Qt.AlignmentFlag.AlignTop)
        lay.addLayout(col, 1)
        self.refresh_theme()

    def refresh_theme(self) -> None:
        pal = theme.pal()
        self.icon.setStyleSheet(
            f"QFrame {{ background: {pal['bg']}; border: 1px solid {pal['bd']}; border-radius: 10px; }}"
        )
        self.icon_lbl.setPixmap(svg_pixmap("disc", pal["accTx"], 22))

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        repolish(self)

    def mousePressEvent(self, _event) -> None:
        self._on_click(self)


class LibraryPage(QWidget):
    def __init__(self, library: Library) -> None:
        super().__init__()
        self.library = library
        self._cards: list[IsoCard] = []
        self._sel: dict | None = None
        self._build_ui()
        self.retranslate()
        self.reload()

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

        body = QHBoxLayout()
        body.setSpacing(20)
        root.addLayout(body, 1)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.holder = QWidget()
        self.list_lay = QVBoxLayout(self.holder)
        self.list_lay.setContentsMargins(0, 0, 8, 0)
        self.list_lay.setSpacing(12)
        self.scroll.setWidget(self.holder)
        body.addWidget(self.scroll, 1)

        aside = card()
        aside.setFixedWidth(330)
        al = QVBoxLayout(aside)
        al.setContentsMargins(20, 20, 20, 20)
        al.setSpacing(12)
        self.cap = label("", "caption")
        self.lbl_title = label("-", "title", wrap=True)
        al.addWidget(self.cap)
        al.addWidget(self.lbl_title)
        al.addWidget(separator())
        self.kv = {}
        for key in ("editions", "size", "created", "sha"):
            row = QHBoxLayout()
            k = label("", "muted")
            v = label("-", wrap=True)
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            row.addWidget(k)
            row.addWidget(v, 1)
            al.addLayout(row)
            self.kv[key] = (k, v)
        al.addWidget(separator())
        self.btn_show = QPushButton()
        self.btn_show.setProperty("variant", "primary")
        self.btn_show.clicked.connect(self._show_in_folder)
        self.btn_copy = QPushButton()
        self.btn_copy.clicked.connect(self._copy_hash)
        self.btn_delete = QPushButton()
        self.btn_delete.setProperty("variant", "danger")
        self.btn_delete.clicked.connect(self._delete)
        for b in (self.btn_show, self.btn_copy, self.btn_delete):
            al.addWidget(b)
        al.addStretch(1)
        body.addWidget(aside, 0, Qt.AlignmentFlag.AlignTop)

    def retranslate(self) -> None:
        self.h1.setText(t("lib.title"))
        self.sub.setText(t("lib.subtitle"))
        self.cap.setText(t("lib.selected").upper())
        self.kv["editions"][0].setText(t("lib.kv_editions"))
        self.kv["size"][0].setText(t("lib.kv_size"))
        self.kv["created"][0].setText(t("lib.kv_created"))
        self.kv["sha"][0].setText("SHA-256")
        self.btn_show.setText(t("lib.show"))
        self.btn_copy.setText(t("lib.copy_hash"))
        self.btn_delete.setText(t("lib.delete"))
        self.reload()

    def refresh_theme(self) -> None:
        for c in self._cards:
            c.refresh_theme()

    # ----------------------------------------------------------------- liste
    def reload(self) -> None:
        keep = self._sel.get("id") if self._sel else None
        self.library.load()
        for c in self._cards:
            c.setParent(None)
            c.deleteLater()
        self._cards = []
        while self.list_lay.count():
            item = self.list_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not self.library.entries:
            empty = label(t("lib.empty"), "muted", wrap=True)
            self.list_lay.addWidget(empty)
            self.list_lay.addStretch(1)
            self._sel = None
            self._update_aside()
            return
        for entry in self.library.entries:
            c = IsoCard(entry, self._select)
            self._cards.append(c)
            self.list_lay.addWidget(c)
        self.list_lay.addStretch(1)
        target = next((c for c in self._cards if c.entry.get("id") == keep), self._cards[0])
        self._select(target)

    def _select(self, card_widget: IsoCard) -> None:
        for c in self._cards:
            c.set_selected(c is card_widget)
        self._sel = card_widget.entry
        self._update_aside()

    def _update_aside(self) -> None:
        e = self._sel
        has = e is not None
        for b in (self.btn_show, self.btn_copy, self.btn_delete):
            b.setEnabled(has)
        if not e:
            self.lbl_title.setText("-")
            for _k, v in self.kv.values():
                v.setText("-")
            return
        self.lbl_title.setText(e.get("title", ""))
        self.kv["editions"][1].setText(", ".join(e.get("editions", [])) or "-")
        self.kv["size"][1].setText(fmt_size(e.get("size", 0)))
        self.kv["created"][1].setText(fmt_date(e.get("created", 0)))
        self.kv["sha"][1].setText(t("lib.hash_ready") if e.get("sha256") else "-")

    # ---------------------------------------------------------------- işlemler
    def _show_in_folder(self) -> None:
        if not self._sel:
            return
        path = Path(self._sel["file"])
        if os.name == "nt" and path.exists():
            # Liste olarak verilirse Python "/select,yol" argümanını tırnaklar ve boşluk/Türkçe
            # karakter içeren yollarda Gezgin dosyayı seçemeyip Belgeler'i açar; tek dize şart.
            subprocess.Popen(f'explorer /select,"{os.path.normpath(str(path))}"')
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))

    def _copy_hash(self) -> None:
        if self._sel and self._sel.get("sha256"):
            QGuiApplication.clipboard().setText(self._sel["sha256"])

    def _delete(self) -> None:
        if not self._sel:
            return
        if ask(
            self,
            t("lib.delete_text", name=Path(self._sel["file"]).name),
            t("lib.delete"),
            t("dlg.cancel"),
            title=t("lib.delete_title"),
            danger=True,
            default_cancel=True,
        ):
            self.library.remove(self._sel["id"], delete_file=True)
            self._sel = None
            self.reload()
