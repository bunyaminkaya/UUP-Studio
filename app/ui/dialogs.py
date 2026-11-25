"""Uygulamanın görünümüne uyan çerçevesiz diyaloglar (QMessageBox yerine)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..config import APP_NAME
from ..i18n import t
from .widgets import app_icon, repolish, svg_icon, svg_pixmap


class ThemedDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        text: str,
        buttons: list[tuple[str, str]],
        *,
        title: str = APP_NAME,
        icon: str = "info",
        default: int = 0,
    ) -> None:
        """buttons: [(metin, varyant)], varyant: "primary" | "dangerfill" | "" (ikincil)."""
        super().__init__(parent)
        self.setObjectName("themed")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.setWindowTitle(title)
        self.result_index = -1
        pal = theme.pal()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 14, 18, 22)  # gölge için pay
        card = QFrame()
        card.setObjectName("dlgcard")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 120))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        root = QVBoxLayout(card)
        root.setContentsMargins(20, 12, 12, 18)
        root.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(8)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(18, 18))
        head.addWidget(logo)
        ttl = QLabel(title)
        ttl.setStyleSheet("font-weight: 600; font-size: 13px;")
        head.addWidget(ttl, 1)
        close = QToolButton()
        close.setProperty("winctl", True)
        close.setIcon(svg_icon("close", pal["mu"], 14))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setFixedSize(34, 30)
        close.clicked.connect(self.reject)
        head.addWidget(close)
        root.addLayout(head)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 8, 0)
        body.setSpacing(16)
        ico = QLabel()
        ico.setPixmap(svg_pixmap(icon, pal["accTx"] if icon != "warn" else pal["danger"], 30, 1.8))
        ico.setAlignment(Qt.AlignmentFlag.AlignTop)
        body.addWidget(ico, 0, Qt.AlignmentFlag.AlignTop)
        msg = QLabel(text)
        msg.setWordWrap(True)
        msg.setMinimumWidth(340)
        msg.setMaximumWidth(440)
        msg.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        body.addWidget(msg, 1)
        root.addLayout(body)

        row = QHBoxLayout()
        row.setContentsMargins(0, 4, 8, 0)
        row.setSpacing(10)
        row.addStretch(1)
        self._buttons: list[QPushButton] = []
        for index, (caption, variant) in enumerate(buttons):
            btn = QPushButton(caption)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(38)
            if variant:
                btn.setProperty("variant", variant)
                repolish(btn)
            btn.clicked.connect(lambda _=False, i=index: self._finish(i))
            row.addWidget(btn)
            self._buttons.append(btn)
        root.addLayout(row)
        if self._buttons:
            self._buttons[min(default, len(self._buttons) - 1)].setDefault(True)
            self._buttons[min(default, len(self._buttons) - 1)].setFocus()
        self.adjustSize()

    def _finish(self, index: int) -> None:
        self.result_index = index
        self.accept()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            for i, btn in enumerate(self._buttons):
                if btn.isDefault():
                    self._finish(i)
                    return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 56:
            handle = self.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                return
        super().mousePressEvent(event)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        parent = self.parentWidget()
        if parent is not None:
            center = parent.mapToGlobal(parent.rect().center())
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)


def ask(
    parent: QWidget | None,
    text: str,
    ok_text: str,
    cancel_text: str | None = None,
    *,
    title: str = APP_NAME,
    icon: str = "question",
    danger: bool = False,
    default_cancel: bool = False,
) -> bool:
    """Onay diyaloğu; ok_text'e basılırsa True döndürür."""
    cancel_text = cancel_text or t("dlg.cancel")
    dlg = ThemedDialog(
        parent,
        text,
        [(ok_text, "dangerfill" if danger else "primary"), (cancel_text, "")],
        title=title,
        icon="warn" if danger else icon,
        default=1 if default_cancel else 0,
    )
    dlg.exec()
    return dlg.result_index == 0


def info(parent: QWidget | None, text: str, *, title: str = APP_NAME, icon: str = "info") -> None:
    ThemedDialog(parent, text, [(t("dlg.ok"), "primary")], title=title, icon=icon).exec()
