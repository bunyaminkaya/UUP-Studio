"""Ortak arayüz bileşenleri ve yardımcı işlevler."""
from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from .. import theme
from ..i18n import i18n, t

SVG = {
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "download": '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
    "disc": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2"/>',
    "settings": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    "min": '<path d="M5 12h14"/>',
    "max": '<rect x="6" y="6" width="12" height="12"/>',
    "restore": '<rect x="5" y="8" width="11" height="11"/><path d="M8 8V5h11v11h-3"/>',
    "close": '<path d="M6 6l12 12M18 6L6 18"/>',
    "check": '<path d="M5 12l5 5 9-10"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "question": '<circle cx="12" cy="12" r="9"/><path d="M9.6 9.4a2.5 2.5 0 1 1 3.6 2.2c-.8.4-1.2 1-1.2 1.8M12 17h.01"/>',
    "warn": '<path d="M12 4l9 16H3z"/><path d="M12 10v4M12 17h.01"/>',
    "logo": '<path d="M12 4v12M6 11l6 6 6-6M5 21h14"/>',
}


def svg_pixmap(name: str, color: str, size: int, stroke: float = 2.0) -> QPixmap:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" '
        f'stroke-linejoin="round">{SVG[name]}</svg>'
    )
    dpr = 2
    pm = QPixmap(size * dpr, size * dpr)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    QSvgRenderer(svg.encode("utf-8")).render(painter)
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def svg_icon(name: str, color: str, size: int = 18, stroke: float = 2.0) -> QIcon:
    return QIcon(svg_pixmap(name, color, size, stroke))


def app_icon() -> QIcon:
    size = 256
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#3CC7B0"))
    p.drawRoundedRect(QRectF(16, 16, size - 32, size - 32), 56, 56)
    p.end()
    glyph = svg_pixmap("logo", "#06211D", 140, 2.6)
    painter = QPainter(pm)
    painter.drawPixmap(58, 58, glyph.scaled(140, 140, Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation))
    painter.end()
    return QIcon(pm)


def repolish(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def card() -> QFrame:
    frame = QFrame()
    frame.setProperty("card", True)
    return frame


def separator() -> QFrame:
    line = QFrame()
    line.setProperty("sep", True)
    line.setFixedHeight(1)
    return line


def label(text: str = "", role: str | None = None, wrap: bool = False) -> QLabel:
    lab = QLabel(text)
    if role:
        lab.setProperty("role", role)
    lab.setWordWrap(wrap)
    return lab


# ------------------------------------------------------------------ biçimleme
def _dec(text: str) -> str:
    return text.replace(".", ",") if i18n.lang == "tr" else text


def fmt_size(n: float) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    value, i = float(n), 0
    while value >= 1024 and i < len(units) - 1:
        value /= 1024
        i += 1
    return _dec(f"{value:.0f} {units[i]}" if i == 0 else f"{value:.1f} {units[i]}")


def fmt_speed(bps: float) -> str:
    return fmt_size(bps) + t("unit.per_second")


def fmt_eta(seconds: float) -> str:
    if seconds <= 0:
        return "-"
    if seconds < 90:
        return "~" + t("unit.sec", n=int(seconds) or 1)
    if seconds < 5400:
        return "~" + t("unit.min", n=int(seconds / 60 + 0.5))
    return "~" + t("unit.hour", n=f"{seconds / 3600:.1f}")


def fmt_date(ts: int) -> str:
    if not ts:
        return "-"
    days = int((time.time() - ts) // 86400)
    if days <= 0:
        return t("date.today")
    if days < 14:
        return t("date.days_ago", n=days)
    if days < 60:
        return t("date.weeks_ago", n=days // 7)
    return time.strftime("%d.%m.%Y", time.localtime(ts))


# ------------------------------------------------------------- arka plan işi
class Task(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args) -> None:
        super().__init__()
        self._fn, self._args = fn, args

    def run(self) -> None:
        try:
            self.done.emit(self._fn(*self._args))
        except Exception as exc:
            self.failed.emit(str(exc))


def run_task(owner: set, fn, ok, err, *args) -> Task:
    task = Task(fn, *args)
    task.done.connect(ok)
    task.failed.connect(err)
    task.finished.connect(lambda t_=task: owner.discard(t_))
    owner.add(task)
    task.start()
    return task


# ----------------------------------------------------------------- bileşenler
class Seg(QFrame):
    """Segmentli (tek seçimli) düğme grubu."""

    changed = Signal(str)

    def __init__(self, items: list[tuple[str, str]]) -> None:
        super().__init__()
        self.setObjectName("seggroup")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._btns: dict[str, QPushButton] = {}
        for value, text in items:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setProperty("seg", True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            lay.addWidget(btn)
            self._group.addButton(btn)
            self._btns[value] = btn
            btn.clicked.connect(lambda _=False, v=value: self.changed.emit(v))
        next(iter(self._btns.values())).setChecked(True)

    def value(self) -> str:
        return next((v for v, b in self._btns.items() if b.isChecked()), "")

    def set_value(self, value: str) -> None:
        if value in self._btns:
            self._btns[value].setChecked(True)

    def set_text(self, value: str, text: str) -> None:
        self._btns[value].setText(text)


class ThemePreview(QWidget):
    """Tema kartlarındaki küçük pencere önizlemesi."""

    LIGHT = ("#F4F6F8", "#E1E6EB", "#9AA5B1")
    DARK = ("#0F1216", "#14191F", "#3A4452")

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode
        self.setFixedHeight(72)

    def _draw(self, p: QPainter, rect: QRectF, colors: tuple[str, str, str]) -> None:
        bg, side, line = colors
        p.fillRect(rect, QColor(bg))
        p.fillRect(QRectF(rect.x(), rect.y(), rect.width() * 0.28, rect.height()), QColor(side))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(line))
        x = rect.x() + rect.width() * 0.28 + 12
        w = rect.width() * 0.72 - 24
        p.drawRoundedRect(QRectF(x, rect.y() + 14, w * 0.7, 8), 4, 4)
        p.drawRoundedRect(QRectF(x, rect.y() + 30, w * 0.45, 8), 4, 4)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(rect, 6, 6)
        p.setClipPath(path)
        if self.mode == "system":
            half = rect.width() / 2
            p.save()
            p.setClipRect(QRectF(rect.x(), rect.y(), half, rect.height()), Qt.ClipOperation.IntersectClip)
            self._draw(p, rect, self.LIGHT)
            p.restore()
            p.save()
            p.setClipRect(QRectF(rect.x() + half, rect.y(), half, rect.height()), Qt.ClipOperation.IntersectClip)
            self._draw(p, rect, self.DARK)
            p.restore()
        else:
            self._draw(p, rect, self.LIGHT if self.mode == "light" else self.DARK)
        p.setClipping(False)
        p.setPen(QPen(QColor("#6B7683"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(rect, 6, 6)


class OptionCard(QFrame):
    """Radyo düğmeli seçim kartı (dil, tema, çıktı türü...)."""

    chosen = Signal(str)

    def __init__(self, value: str, title: str, sub: str, group: QButtonGroup,
                 preview: QWidget | None = None) -> None:
        super().__init__()
        self.value = value
        self.setProperty("optcard", True)
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(12)
        if preview is not None:
            lay.addWidget(preview)
        row = QHBoxLayout()
        row.setSpacing(12)
        self.radio = QRadioButton()
        group.addButton(self.radio)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        self.title = QLabel(title)
        self.title.setStyleSheet("font-weight: 600;")
        self.sub = label(sub, "small", wrap=True)
        texts.addWidget(self.title)
        texts.addWidget(self.sub)
        row.addWidget(self.radio, 0, Qt.AlignmentFlag.AlignTop)
        row.addLayout(texts, 1)
        lay.addLayout(row)
        self.radio.toggled.connect(self._toggled)

    def _toggled(self, checked: bool) -> None:
        self.setProperty("selected", checked)
        repolish(self)
        if checked:
            self.chosen.emit(self.value)

    def set_checked(self, checked: bool) -> None:
        self.radio.blockSignals(True)
        self.radio.setChecked(checked)
        self.radio.blockSignals(False)
        self.setProperty("selected", checked)
        repolish(self)

    def set_texts(self, title: str, sub: str) -> None:
        self.title.setText(title)
        self.sub.setText(sub)

    def mousePressEvent(self, _event) -> None:
        if not self.radio.isChecked():
            self.radio.setChecked(True)


class StepBar(QWidget):
    """Bul → İndir → Doğrula → Dönüştür → ISO adım göstergesi."""

    def __init__(self) -> None:
        super().__init__()
        self.labels: list[str] = []
        self.active = 0
        self.setFixedHeight(28)

    def set_steps(self, labels: list[str], active: int) -> None:
        self.labels, self.active = labels, active
        self.update()

    def paintEvent(self, _event) -> None:
        if not self.labels:
            return
        pal = theme.pal()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = QFont(self.font())
        font.setPixelSize(13)
        p.setFont(font)
        bold = QFont(font)
        bold.setWeight(QFont.Weight.DemiBold)
        n = len(self.labels)
        circle, gap = 24, 8
        widths = []
        for i, text in enumerate(self.labels):
            f = bold if i == self.active else font
            widths.append(QFontMetrics(f).horizontalAdvance(text))
        total = sum(circle + gap + w for w in widths)
        crowded = total + 12 * max(0, n - 1) > self.width()
        if crowded:  # sığmıyorsa yalnızca geçerli adımın etiketini göster
            widths = [w if i == self.active else 0 for i, w in enumerate(widths)]
            total = sum(circle + (gap if widths[i] else 0) + w for i, w in enumerate(widths))
        spacing = max(16.0, (self.width() - total) / max(1, n - 1)) if n > 1 else 0
        x = 0.0
        mid = self.height() / 2
        for i, text in enumerate(self.labels):
            done = i < self.active
            cur = i == self.active
            rect = QRectF(x, mid - circle / 2, circle, circle)
            p.setPen(Qt.PenStyle.NoPen)
            if cur:
                p.setBrush(QColor(pal["acc"]))
                p.drawEllipse(rect)
                p.setPen(QColor(pal["onAcc"]))
                p.setFont(bold)
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i + 1))
            elif done:
                p.setBrush(QColor(pal["seg"]))
                p.drawEllipse(rect)
                p.drawPixmap(int(rect.x() + 6), int(rect.y() + 6),
                             svg_pixmap("check", "#FFFFFF", 12, 3.2))
            else:
                p.setPen(QPen(QColor(pal["bd2"]), 1))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(rect.adjusted(0.5, 0.5, -0.5, -0.5))
                p.setPen(QColor(pal["mu"]))
                p.setFont(font)
                p.drawText(rect, Qt.AlignmentFlag.AlignCenter, str(i + 1))
            p.setFont(bold if cur else font)
            p.setPen(QColor(pal["tx"] if cur else pal["mu"]))
            if widths[i]:
                tr = QRectF(x + circle + gap, 0, widths[i] + 4, self.height())
                p.drawText(tr, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
            x += circle + (gap if widths[i] else 0) + widths[i]
            if i < n - 1:
                p.setPen(QPen(QColor(pal["bd2"]), 1))
                p.drawLine(int(x + 8), int(mid), int(x + spacing - 8), int(mid))
                x += spacing


class BarDelegate(QStyledItemDelegate):
    """Tablo hücresinde ilerleme çubuğu (Qt.UserRole = yüzde)."""

    def paint(self, painter: QPainter, option, index) -> None:
        pal = theme.pal()
        pct = float(index.data(Qt.ItemDataRole.UserRole) or 0)
        r = option.rect.adjusted(18, 0, -18, 0)
        h = 6
        y = r.center().y() - h / 2
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(pal["bd"]))
        painter.drawRoundedRect(QRectF(r.x(), y, r.width(), h), 3, 3)
        painter.setBrush(QColor(pal["acc"]))
        painter.drawRoundedRect(QRectF(r.x(), y, r.width() * max(0.0, min(100.0, pct)) / 100, h), 3, 3)
        painter.restore()
