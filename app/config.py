"""Uygulama sabitleri, yollar ve kalıcı ayarlar."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_NAME = "UUP Studio"
APP_ID = "UUPStudio"
APP_VERSION = "0.3.1"
DEVELOPER = "Bünyamin KAYA"
WEBSITE = "https://bunyaminkaya.com"

# UUP dump JSON API
API_BASE = "https://api.uupdump.net"

# Resmi UUP dump indirme paketinin kullandığı dönüştürücü listesi (aria2 giriş biçimi).
# Uygulama bu listeyi her seferinde okur; erişilemezse aşağıdaki son bilinen değerlere döner.
CONVERTER_LIST_URL = (
    "https://git.uupdump.net/uup-dump/misc/raw/branch/master/autodl_files/converter_windows"
)
# uupdump.net/misc henüz güncellenmemişse aynı dosyalar bu depodan da alınır.
MIRROR_BASE = "https://git.uupdump.net/uup-dump/misc/raw/branch/master/"
FALLBACK_SEVENZR_URL = "https://uupdump.net/misc/7zr.exe"
FALLBACK_SEVENZR_SHA256 = "72c98287b2e8f85ea7bb87834b6ce1ce7ce7f41a8c97a81b307d4d4bf900922b"
FALLBACK_CONVERTER_URL = "https://uupdump.net/misc/uup-converter-wimlib-v126.7z"
FALLBACK_CONVERTER_SHA256 = "1448f7e33353fa63d558333c4b6ddb8b41b992a7911f19d3b72ba3246cf349bc"


def resource_path(*parts: str) -> Path:
    """Kaynak dosya yolu (PyInstaller ile paketlenmişken de çalışır)."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base.joinpath(*parts)


def data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = root / APP_ID
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass
class Settings:
    language: str = "tr"          # "tr" | "en"
    theme: str = "dark"           # "dark" | "light" | "system"
    output_mode: str = "iso"      # "iso" | "download"
    output_dir: str = ""
    work_dir: str = ""
    add_updates: bool = True
    cleanup: bool = False         # bileşen temizliği çok uzun sürer; isteğe bağlı
    reset_base: bool = False
    netfx3: bool = False
    wim2esd: bool = False
    skip_apps: bool = False
    defender_exclusion: bool = True  # dönüştürme sırasında geçici Defender dışlaması (hızlandırır)
    keep_uup_files: bool = False
    accepted_notice: bool = False  # ilk açılış bilgilendirmesi gösterildi mi
    parallel_files: int = 4
    last_lang: str = "tr-tr"
    version: int = 3              # ayar şeması (v2: Cleanup varsayılanı kapalı)

    def __post_init__(self) -> None:
        if not self.output_dir:
            self.output_dir = str(Path.home() / "Downloads" / "UUP Studio")
        if not self.work_dir:
            self.work_dir = str(data_dir() / "work")

    @staticmethod
    def _file() -> Path:
        return data_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        try:
            raw = json.loads(cls._file().read_text("utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        if int(raw.get("version", 1)) < 2:
            raw["cleanup"] = False  # eski varsayılan (açık) çok yavaştı
            raw["version"] = 2
        if int(raw.get("version", 2)) < 3:
            raw["defender_exclusion"] = True  # yeni varsayılan: kayıtlı eski 'kapalı' değeri ezilir
            raw["version"] = 3
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self) -> None:
        try:
            self._file().write_text(
                json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def converter_options(self) -> dict:
        return {
            "AddUpdates": self.add_updates,
            "Cleanup": self.cleanup,
            "ResetBase": self.reset_base,
            "NetFx3": self.netfx3,
            "wim2esd": self.wim2esd,
            "SkipApps": self.skip_apps,
        }
