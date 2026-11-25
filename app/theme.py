"""Açık/koyu tema paletleri ve Qt stil sayfası."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication

from .config import data_dir

DARK = dict(
    bg="#0F1216", panel="#14191F", hi="#1B222A", bd="#262E38", bd2="#333D49",
    tx="#E6E9ED", mu="#9BA6B3", mu2="#8793A1", nav="#C3CBD5",
    acc="#3CC7B0", accHover="#58D6C1", accTx="#3CC7B0", accBd="#3CC7B0", onAcc="#06211D",
    seg="#2A343F", segTx="#FFFFFF", segOff="#B3BDC9", danger="#F4A79D",
    warnBg="#2B2412", warnBd="#5C4A1A", warnTx="#F2C86B",
    input="#0F1216", winbd="#3A4552", dbg="#F4A79D", dtx="#2A0E0B", side="#14191F", rowbd="#1F262E", logbg="#0B0E11", closeHover="#C42B1C",
)
LIGHT = dict(
    bg="#F4F6F8", panel="#FFFFFF", hi="#E4F5F2", bd="#D5DBE2", bd2="#BFC8D2",
    tx="#151A20", mu="#566170", mu2="#5F6B7A", nav="#333D49",
    acc="#3CC7B0", accHover="#2FB59F", accTx="#0B7A6B", accBd="#0B8F7C", onAcc="#06211D",
    seg="#2A3441", segTx="#FFFFFF", segOff="#3E4854", danger="#B3261E",
    warnBg="#FFF4D6", warnBd="#E6C96B", warnTx="#7A5A00",
    input="#F4F6F8", winbd="#8B97A5", dbg="#B3261E", dtx="#FFFFFF", side="#F4F6F8", rowbd="#E6EAEE", logbg="#EEF1F4", closeHover="#C42B1C",
)

PAL: dict = dict(DARK)
NAME = "dark"

MONO = '"Cascadia Mono", "Consolas", "JetBrains Mono", monospace'

QSS = """
* { font-family: "Segoe UI", "Inter", "Noto Sans", sans-serif; font-size: 14px; color: @tx@; }
QWidget#root { background: @bg@; border: 1px solid @winbd@; }
QToolTip { background: @panel@; color: @tx@; border: 1px solid @bd@; padding: 4px 8px; }
QFrame#sidebar { background: @side@; border: 1px solid @winbd@; border-right: 1px solid @bd@; }
QFrame[card="true"] { background: @panel@; border: 1px solid @bd@; border-radius: 10px; }
QFrame[sep="true"] { background: @bd@; border: 0; max-height: 1px; min-height: 1px; }
QLabel { background: transparent; border: 0; }
QLabel[role="h1"] { font-size: 24px; font-weight: 700; }
QLabel[role="h2"] { font-size: 16px; font-weight: 600; }
QLabel[role="title"] { font-size: 18px; font-weight: 700; }
QLabel[role="muted"] { color: @mu@; }
QLabel[role="small"] { color: @mu@; font-size: 12px; }
QLabel[role="faint"] { color: @mu2@; font-size: 12px; }
QLabel[role="caption"] { color: @mu@; font-size: 12px; font-weight: 600; }
QLabel[role="mono"] { font-family: @mono@; font-size: 13px; }
QLabel[role="accent"] { color: @accTx@; font-family: @mono@; font-size: 13px; }
QLabel[role="danger"] { color: @danger@; }
QLabel[role="ok"] { color: @accTx@; }
QPushButton { min-height: 38px; padding: 0 16px; border: 1px solid @bd2@; border-radius: 8px; background: transparent; font-weight: 500; }
QPushButton:hover { background: @hi@; }
QPushButton:disabled { color: @mu2@; border-color: @bd@; }
QPushButton[variant="primary"] { background: @acc@; color: @onAcc@; border: 0; font-weight: 700; min-height: 44px; }
QPushButton[variant="primary"]:hover { background: @accHover@; }
QPushButton[variant="primary"]:disabled { background: @bd@; color: @mu2@; }
QPushButton[variant="danger"] { color: @danger@; }
QPushButton[nav="true"] { text-align: left; border: 0; border-radius: 8px; min-height: 44px; padding: 0 12px; color: @nav@; font-weight: 500; }
QPushButton[nav="true"]:checked { background: @hi@; color: @accTx@; font-weight: 600; }
QPushButton[nav="true"]:hover:!checked { background: @hi@; }
QFrame#seggroup { background: @panel@; border: 1px solid @bd@; border-radius: 10px; }
QPushButton[seg="true"] { border: 0; border-radius: 7px; min-height: 34px; padding: 0 14px; color: @segOff@; font-size: 13px; }
QPushButton[seg="true"]:checked { background: @seg@; color: @segTx@; font-weight: 600; }
QPushButton[seg="true"]:hover:!checked { background: @hi@; }
QToolButton[winctl="true"] { border: 0; background: transparent; }
QToolButton[winctl="true"]:hover { background: @hi@; }
QToolButton[winctl="true"][close="true"]:hover { background: @closeHover@; }
QLineEdit, QComboBox, QSpinBox { min-height: 38px; padding: 0 12px; border: 1px solid @bd@; border-radius: 8px; background: @input@; selection-background-color: @acc@; selection-color: @onAcc@; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: @accBd@; }
QLineEdit:disabled { color: @mu@; }
QComboBox::drop-down { border: 0; width: 28px; }
QComboBox::down-arrow { image: url("@arrow@"); width: 12px; height: 12px; }
QComboBox QAbstractItemView { background: @panel@; border: 1px solid @bd@; selection-background-color: @hi@; selection-color: @tx@; outline: 0; padding: 4px; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; border: 0; }
QCheckBox, QRadioButton { spacing: 12px; background: transparent; }
QCheckBox::indicator, QRadioButton::indicator { width: 18px; height: 18px; }
QCheckBox::indicator { border: 1px solid @bd2@; border-radius: 4px; background: @input@; }
QCheckBox::indicator:checked { background: @acc@; border: 1px solid @acc@; image: url("@check@"); }
QRadioButton::indicator { width: 16px; height: 16px; border: 1px solid @bd2@; border-radius: 9px; background: @input@; }
QRadioButton::indicator:checked { width: 8px; height: 8px; border: 5px solid @acc@; border-radius: 9px; background: @input@; }
QFrame[optcard="true"] { background: @bg@; border: 1px solid @bd@; border-radius: 10px; }
QFrame[optcard="true"][selected="true"] { background: @hi@; border: 1px solid @accBd@; }
QFrame[isocard="true"] { background: @panel@; border: 1px solid @bd@; border-radius: 10px; }
QFrame[isocard="true"][selected="true"] { background: @hi@; border: 1px solid @accBd@; }
QFrame[warn="true"] { background: @warnBg@; border: 1px solid @warnBd@; border-radius: 8px; }
QFrame[warn="true"] QLabel { color: @warnTx@; }
QProgressBar { background: @bd@; border: 0; border-radius: 5px; min-height: 10px; max-height: 10px; color: transparent; }
QProgressBar::chunk { background: @acc@; border-radius: 5px; }
QAbstractScrollArea, QAbstractScrollArea > QWidget { background: transparent; }
QTableWidget, QListWidget { background: @panel@; border: 0; outline: 0; selection-background-color: @hi@; selection-color: @tx@; }
QTableWidget::item { padding: 0 18px; border-bottom: 1px solid @rowbd@; }
QTableWidget::item:selected { background: @hi@; color: @tx@; }
QListWidget::item { padding: 6px 8px; border-radius: 6px; }
QListWidget::item:hover { background: @hi@; }
QListWidget::indicator { width: 18px; height: 18px; border: 1px solid @bd2@; border-radius: 4px; background: @input@; }
QListWidget::indicator:checked { background: @acc@; border: 1px solid @acc@; image: url("@check@"); }
QHeaderView::section { background: @panel@; color: @mu@; border: 0; border-bottom: 1px solid @bd@; padding: 0 18px; min-height: 38px; font-weight: 600; font-size: 12px; }
QHeaderView { background: @panel@; }
QScrollBar:vertical { width: 10px; background: transparent; margin: 2px; }
QScrollBar::handle:vertical { background: @bd2@; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 10px; background: transparent; margin: 2px; }
QScrollBar::handle:horizontal { background: @bd2@; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QPlainTextEdit#log { background: @logbg@; border: 0; font-family: @mono@; font-size: 12px; color: @nav@; padding: 10px 14px; }
QScrollArea { border: 0; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QMessageBox { background: @panel@; }
QDialog#themed { background: transparent; }
QFrame#dlgcard { background: @panel@; border: 1px solid @winbd@; border-radius: 12px; }
QPushButton[variant="dangerfill"] { background: @dbg@; color: @dtx@; border: 0; font-weight: 700; }
QPushButton[variant="dangerfill"]:hover { background: @dbg@; }
QFileDialog, QFileDialog QWidget { background: @panel@; color: @tx@; }
QFileDialog QTreeView, QFileDialog QListView { background: @input@; border: 1px solid @bd@; }
"""


def resolve(name: str) -> str:
    if name == "system":
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
            return "light" if scheme == Qt.ColorScheme.Light else "dark"
        except Exception:
            return "dark"
    return name if name in ("dark", "light") else "dark"


def pal() -> dict:
    return PAL


def _write_icons(p: dict) -> dict:
    folder = data_dir() / "icons"
    if not str(folder).isascii():  # Türkçe karakterli kullanıcı klasörü QSS url()'ini bozabilir
        import os
        import tempfile
        base = Path(os.environ.get("PUBLIC") or tempfile.gettempdir())
        folder = base / "UUPStudio_icons"
    folder.mkdir(parents=True, exist_ok=True)
    check = folder / f"check_{NAME}.svg"
    check.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{p["onAcc"]}" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M5 12l5 5 9-10"/></svg>',
        encoding="utf-8",
    )
    arrow = folder / f"arrow_{NAME}.svg"
    arrow.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{p["mu"]}" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M6 9l6 6 6-6"/></svg>',
        encoding="utf-8",
    )
    return {"check": check.as_posix(), "arrow": arrow.as_posix()}


def build_qss(p: dict, icons: dict) -> str:
    values = {**p, **icons, "mono": MONO}
    return re.sub(r"@(\w+)@", lambda m: str(values[m.group(1)]), QSS)


def apply(app, name: str) -> str:
    """Temayı uygular ve çözümlenen adı ("dark" | "light") döndürür."""
    global PAL, NAME
    NAME = resolve(name)
    PAL = dict(DARK if NAME == "dark" else LIGHT)
    _apply_palette(app, PAL)
    app.setStyleSheet(build_qss(PAL, _write_icons(PAL)))
    return NAME


def _apply_palette(app, pal: dict) -> None:
    """Windows'un yerel stili/paleti QSS'i ezmesin diye Fusion + açık palet."""
    from PySide6.QtGui import QColor, QPalette
    if app.style().objectName().lower() != "fusion":
        app.setStyle("Fusion")
    p = QPalette()
    bg, panel, tx, mu = QColor(pal["bg"]), QColor(pal["panel"]), QColor(pal["tx"]), QColor(pal["mu"])
    for role, col in (
        (QPalette.ColorRole.Window, bg), (QPalette.ColorRole.Base, panel),
        (QPalette.ColorRole.AlternateBase, bg), (QPalette.ColorRole.Button, panel),
        (QPalette.ColorRole.WindowText, tx), (QPalette.ColorRole.Text, tx),
        (QPalette.ColorRole.ButtonText, tx), (QPalette.ColorRole.ToolTipBase, panel),
        (QPalette.ColorRole.ToolTipText, tx), (QPalette.ColorRole.PlaceholderText, mu),
        (QPalette.ColorRole.Highlight, QColor(pal["acc"])),
        (QPalette.ColorRole.HighlightedText, QColor(pal["bg"])),
    ):
        p.setColor(role, col)
    app.setPalette(p)
