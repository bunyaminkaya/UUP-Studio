"""Basit çok dilli metin desteği (locales/*.json)."""
from __future__ import annotations

import json

from PySide6.QtCore import QObject, Signal

from .config import resource_path

LANGUAGES = ("tr", "en")


class I18n(QObject):
    changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.lang = "tr"
        self._data: dict[str, str] = {}
        self._fallback: dict[str, str] = {}
        self.set_language("tr", emit=False)

    @staticmethod
    def _read(lang: str) -> dict[str, str]:
        path = resource_path("locales", f"{lang}.json")
        try:
            return json.loads(path.read_text("utf-8"))
        except (OSError, ValueError):
            return {}

    def set_language(self, lang: str, emit: bool = True) -> None:
        if lang not in LANGUAGES:
            lang = "tr"
        self.lang = lang
        self._fallback = self._read("tr")
        self._data = self._read(lang)
        if emit:
            self.changed.emit()

    def t(self, key: str, **kw) -> str:
        text = self._data.get(key) or self._fallback.get(key) or key
        return text.format(**kw) if kw else text


i18n = I18n()
t = i18n.t
