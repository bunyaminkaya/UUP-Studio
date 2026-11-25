"""Gelişmiş ayarlar (isteğe bağlı): çıktı türü ve dönüştürme seçenekleri."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import Settings
from ..converter import is_admin, is_windows, relaunch_as_admin
from ..i18n import t
from .widgets import OptionCard, card, label

OPTIONS = (
    ("add_updates", "adv.opt_updates"),
    ("cleanup", "adv.opt_cleanup"),
    ("reset_base", "adv.opt_resetbase"),
    ("netfx3", "adv.opt_netfx3"),
    ("wim2esd", "adv.opt_esd"),
    ("skip_apps", "adv.opt_skipapps"),
    ("defender_exclusion", "adv.opt_defender"),
)


class AdvancedPage(QWidget):
    back = Signal()
    changed = Signal()

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self._build_ui()
        self.retranslate()

    def _build_ui(self) -> None:
        s = self.settings
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
        self.btn_back = QPushButton()
        self.btn_back.clicked.connect(self.back.emit)
        head.addWidget(self.btn_back, 0, Qt.AlignmentFlag.AlignBottom)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(20)
        root.addLayout(body, 1)

        # --- çıktı
        out = card()
        ol = QVBoxLayout(out)
        ol.setContentsMargins(20, 20, 20, 20)
        ol.setSpacing(12)
        self.lbl_out = label("", "h2")
        ol.addWidget(self.lbl_out)
        self._group = QButtonGroup(self)
        self.card_download = OptionCard("download", "", "", self._group)
        self.card_iso = OptionCard("iso", "", "", self._group)
        ol.addWidget(self.card_iso)
        ol.addWidget(self.card_download)
        (self.card_iso if s.output_mode == "iso" else self.card_download).set_checked(True)
        self.card_iso.chosen.connect(self._on_mode)
        self.card_download.chosen.connect(self._on_mode)
        ol.addStretch(1)
        body.addWidget(out, 1)

        # --- seçenekler
        opts = card()
        pl = QVBoxLayout(opts)
        pl.setContentsMargins(20, 20, 20, 20)
        pl.setSpacing(10)
        self.lbl_opts = label("", "h2")
        pl.addWidget(self.lbl_opts)
        self.checks: dict[str, QCheckBox] = {}
        for attr, _key in OPTIONS:
            box = QCheckBox()
            box.setChecked(bool(getattr(s, attr)))
            box.toggled.connect(lambda v, a=attr: self._set(a, v))
            self.checks[attr] = box
            pl.addWidget(box)
        self.chk_keep = QCheckBox()
        self.chk_keep.setChecked(s.keep_uup_files)
        self.chk_keep.toggled.connect(lambda v: self._set("keep_uup_files", v))
        pl.addSpacing(6)
        pl.addWidget(self.chk_keep)
        row = QHBoxLayout()
        self.lbl_parallel = label("", None)
        self.spin = QSpinBox()
        self.spin.setRange(1, 8)
        self.spin.setValue(s.parallel_files)
        self.spin.setFixedWidth(70)
        self.spin.valueChanged.connect(lambda v: self._set("parallel_files", v))
        row.addWidget(self.lbl_parallel)
        row.addStretch(1)
        row.addWidget(self.spin)
        pl.addLayout(row)
        pl.addStretch(1)

        self.warn = QFrame()
        self.warn.setProperty("warn", True)
        wl = QVBoxLayout(self.warn)
        wl.setContentsMargins(14, 12, 14, 12)
        wl.setSpacing(8)
        self.lbl_warn = label("", None, wrap=True)
        self.btn_admin = QPushButton()
        self.btn_admin.clicked.connect(self._admin)
        wl.addWidget(self.lbl_warn)
        wl.addWidget(self.btn_admin, 0, Qt.AlignmentFlag.AlignLeft)
        self.warn.setVisible(is_windows() and not is_admin())
        pl.addWidget(self.warn)
        body.addWidget(opts, 1)

    def retranslate(self) -> None:
        self.h1.setText(t("adv.title"))
        self.sub.setText(t("adv.subtitle"))
        self.btn_back.setText(t("adv.back"))
        self.lbl_out.setText(t("adv.output"))
        self.card_iso.set_texts(t("adv.out_iso"), t("adv.out_iso_sub"))
        self.card_download.set_texts(t("adv.out_download"), t("adv.out_download_sub"))
        self.lbl_opts.setText(t("adv.options"))
        for attr, key in OPTIONS:
            self.checks[attr].setText(t(key))
        self.chk_keep.setText(t("adv.keep_files"))
        self.lbl_parallel.setText(t("adv.parallel"))
        self.lbl_warn.setText(t("adv.admin_warn"))
        self.btn_admin.setText(t("adv.admin_btn"))

    def _set(self, attr: str, value) -> None:
        setattr(self.settings, attr, value)
        self.settings.save()
        self.changed.emit()

    def _on_mode(self, value: str) -> None:
        self._set("output_mode", value)

    def _admin(self) -> None:
        if relaunch_as_admin():
            from PySide6.QtWidgets import QApplication

            QApplication.quit()
