"""Ayarlar: Görünüm ve dil / Klasörler / Hakkında."""
from __future__ import annotations

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..config import APP_VERSION, DEVELOPER, WEBSITE, Settings, log_dir
from ..i18n import t
from .widgets import OptionCard, ThemePreview, card, label, separator, svg_pixmap


class SettingsPage(QWidget):
    languageChanged = Signal(str)
    themeChanged = Signal(str)

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
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

        body = QHBoxLayout()
        body.setSpacing(20)
        root.addLayout(body, 1)

        tabs = QVBoxLayout()
        tabs.setSpacing(4)
        self.tab_group = QButtonGroup(self)
        self.tab_btns: list[QPushButton] = []
        for i in range(3):
            b = QPushButton()
            b.setCheckable(True)
            b.setProperty("nav", True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.tab_group.addButton(b, i)
            self.tab_btns.append(b)
            tabs.addWidget(b)
        tabs.addStretch(1)
        self.tab_btns[0].setChecked(True)
        tab_holder = QWidget()
        tab_holder.setFixedWidth(210)
        tab_holder.setLayout(tabs)
        tabs.setContentsMargins(0, 0, 0, 0)
        body.addWidget(tab_holder)

        self.panes = QStackedWidget()
        body.addWidget(self.panes, 1)
        self.panes.addWidget(self._appearance_pane())
        self.panes.addWidget(self._folders_pane())
        self.panes.addWidget(self._about_pane())
        self.tab_group.idClicked.connect(self.panes.setCurrentIndex)

    def show_tab(self, index: int) -> None:
        self.tab_btns[index].setChecked(True)
        self.panes.setCurrentIndex(index)

    def _pane(self) -> tuple[QWidget, QVBoxLayout]:
        frame = card()
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(28)
        lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        return frame, lay

    def _appearance_pane(self) -> QWidget:
        frame, lay = self._pane()
        s = self.settings

        lang_box = QVBoxLayout()
        lang_box.setSpacing(12)
        self.lbl_lang = label("", "h2")
        self.lbl_lang_sub = label("", "muted", wrap=True)
        lang_box.addWidget(self.lbl_lang)
        lang_box.addWidget(self.lbl_lang_sub)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.lang_group = QButtonGroup(self)
        self.lang_cards = {
            "tr": OptionCard("tr", "Türkçe", "Turkish", self.lang_group),
            "en": OptionCard("en", "English", "İngilizce", self.lang_group),
        }
        for c in self.lang_cards.values():
            row.addWidget(c, 1)
            c.chosen.connect(self._on_lang)
        self.lang_cards.get(s.language, self.lang_cards["tr"]).set_checked(True)
        lang_box.addLayout(row)
        lay.addLayout(lang_box)

        theme_box = QVBoxLayout()
        theme_box.setSpacing(12)
        self.lbl_theme = label("", "h2")
        self.lbl_theme_sub = label("", "muted", wrap=True)
        theme_box.addWidget(self.lbl_theme)
        theme_box.addWidget(self.lbl_theme_sub)
        trow = QHBoxLayout()
        trow.setSpacing(12)
        self.theme_group = QButtonGroup(self)
        self.theme_cards = {}
        for mode in ("system", "light", "dark"):
            c = OptionCard(mode, "", "", self.theme_group, ThemePreview(mode))
            c.chosen.connect(self._on_theme)
            self.theme_cards[mode] = c
            trow.addWidget(c, 1)
        self.theme_cards.get(s.theme, self.theme_cards["dark"]).set_checked(True)
        theme_box.addLayout(trow)
        lay.addLayout(theme_box)

        self.lbl_instant = label("", "faint")
        lay.addWidget(self.lbl_instant)
        lay.addStretch(1)
        return frame

    def _folders_pane(self) -> QWidget:
        frame, lay = self._pane()
        lay.setSpacing(18)
        self.lbl_folders = label("", "h2")
        lay.addWidget(self.lbl_folders)
        self.folder_rows = {}
        for attr in ("output_dir", "work_dir"):
            box = QVBoxLayout()
            box.setSpacing(6)
            cap = label("", "small")
            hint = label("", "faint", wrap=True)
            row = QHBoxLayout()
            edit = QLineEdit(getattr(self.settings, attr))
            edit.setReadOnly(True)
            btn = QPushButton()
            btn.clicked.connect(lambda _=False, a=attr: self._browse(a))
            row.addWidget(edit, 1)
            row.addWidget(btn)
            box.addWidget(cap)
            box.addLayout(row)
            box.addWidget(hint)
            lay.addLayout(box)
            self.folder_rows[attr] = (cap, hint, edit, btn)
        lay.addStretch(1)
        return frame

    def _about_pane(self) -> QWidget:
        frame, lay = self._pane()
        lay.setSpacing(20)
        top = QHBoxLayout()
        top.setSpacing(18)
        self.logo = label("")
        self.logo.setFixedSize(64, 64)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name = QVBoxLayout()
        name.setSpacing(4)
        title = label("UUP Studio", None)
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.lbl_version = label("", "muted")
        name.addWidget(title)
        name.addWidget(self.lbl_version)
        top.addWidget(self.logo)
        top.addLayout(name, 1)
        lay.addLayout(top)
        self.lbl_about = label("", None, wrap=True)
        self.lbl_about.setMaximumWidth(620)
        lay.addWidget(self.lbl_about)

        self.about_rows = {}
        table = QVBoxLayout()
        table.setSpacing(0)
        table_w = QWidget()
        table_w.setMaximumWidth(620)
        table_w.setLayout(table)
        table.setContentsMargins(0, 0, 0, 0)
        table.addWidget(separator())
        for key in ("developer", "website", "source", "languages", "themes"):
            row = QHBoxLayout()
            row.setContentsMargins(0, 12, 0, 12)
            k = label("", "muted")
            v = label("")
            v.setAlignment(Qt.AlignmentFlag.AlignRight)
            v.setOpenExternalLinks(True)
            row.addWidget(k)
            row.addStretch(1)
            row.addWidget(v)
            wrapper = QWidget()
            wrapper.setLayout(row)
            table.addWidget(wrapper)
            table.addWidget(separator())
            self.about_rows[key] = (k, v)
        lay.addWidget(table_w)
        self.lbl_disclaimer = label("", "small", wrap=True)
        self.lbl_disclaimer.setMaximumWidth(620)
        lay.addWidget(self.lbl_disclaimer)
        self.lbl_credits = label("", "small", wrap=True)
        self.lbl_credits.setMaximumWidth(620)
        lay.addWidget(self.lbl_credits)
        self.lbl_defender = label("", "small", wrap=True)
        self.lbl_defender.setMaximumWidth(620)
        lay.addWidget(self.lbl_defender)
        self.btn_logs = QPushButton()
        self.btn_logs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(log_dir()))))
        lay.addWidget(self.btn_logs, 0, Qt.AlignmentFlag.AlignLeft)
        self.btn_site = QPushButton()
        self.btn_site.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(WEBSITE)))
        lay.addWidget(self.btn_site, 0, Qt.AlignmentFlag.AlignLeft)
        lay.addStretch(1)
        return frame

    # ---------------------------------------------------------------- çeviri
    def retranslate(self) -> None:
        self.h1.setText(t("settings.title"))
        self.sub.setText(t("settings.subtitle"))
        for b, key in zip(self.tab_btns, ("settings.tab_look", "settings.tab_folders", "settings.tab_about")):
            b.setText(t(key))
        self.lbl_lang.setText(t("settings.language"))
        self.lbl_lang_sub.setText(t("settings.language_sub"))
        self.lbl_theme.setText(t("settings.theme"))
        self.lbl_theme_sub.setText(t("settings.theme_sub"))
        self.theme_cards["system"].set_texts(t("settings.theme_system"), t("settings.theme_system_sub"))
        self.theme_cards["light"].set_texts(t("settings.theme_light"), t("settings.theme_light_sub"))
        self.theme_cards["dark"].set_texts(t("settings.theme_dark"), t("settings.theme_dark_sub"))
        self.lbl_instant.setText(t("settings.instant"))
        self.lbl_folders.setText(t("settings.tab_folders"))
        hints = {"output_dir": "settings.out_dir_hint", "work_dir": "settings.work_dir_hint"}
        caps = {"output_dir": "settings.out_dir", "work_dir": "settings.work_dir"}
        for attr, (cap, hint, _edit, btn) in self.folder_rows.items():
            cap.setText(t(caps[attr]))
            hint.setText(t(hints[attr]))
            btn.setText(t("settings.browse"))
        self.lbl_version.setText(t("about.version", v=APP_VERSION))
        self.lbl_about.setText(t("about.description"))
        labels = {
            "developer": "about.developer",
            "website": "about.website",
            "source": "about.source",
            "languages": "about.languages",
            "themes": "about.themes",
        }
        for key, (k, _v) in self.about_rows.items():
            k.setText(t(labels[key]))
        self.lbl_disclaimer.setText(t("about.disclaimer"))
        self.btn_site.setText(t("about.open_site"))
        self.lbl_credits.setText(t("about.credits"))
        self.lbl_defender.setText(t("about.defender"))
        self.btn_logs.setText(t("about.open_logs"))
        self.refresh_theme()

    def refresh_theme(self) -> None:
        pal = theme.pal()
        self.logo.setStyleSheet(f"background: {pal['acc']}; border-radius: 16px;")
        self.logo.setPixmap(svg_pixmap("logo", pal["onAcc"], 34, 2.6))
        link = f'<a href="{WEBSITE}" style="color:{pal["accTx"]};text-decoration:none">bunyaminkaya.com</a>'
        values = {
            "developer": DEVELOPER,
            "website": link,
            "source": t("about.source_value"),
            "languages": "Türkçe, English",
            "themes": t("about.themes_value"),
        }
        for key, (_k, v) in self.about_rows.items():
            v.setText(values[key])
        for card_ in list(self.theme_cards.values()):
            card_.findChild(ThemePreview).update()

    # ---------------------------------------------------------------- olaylar
    def _on_lang(self, value: str) -> None:
        self.settings.language = value
        self.settings.save()
        self.languageChanged.emit(value)

    def _on_theme(self, value: str) -> None:
        self.settings.theme = value
        self.settings.save()
        self.themeChanged.emit(value)

    def _browse(self, attr: str) -> None:
        current = getattr(self.settings, attr)
        folder = QFileDialog.getExistingDirectory(
            self, t("settings.choose_folder"), current, QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontUseNativeDialog
        )
        if folder:
            setattr(self.settings, attr, folder)
            self.settings.save()
            self.folder_rows[attr][2].setText(folder)
