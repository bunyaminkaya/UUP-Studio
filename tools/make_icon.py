"""build.bat tarafından çağrılır: assets/icon.ico üretir (PySide6 ile)."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from PySide6.QtGui import QGuiApplication  # noqa: E402

import os; os.environ.setdefault("QT_QPA_PLATFORM", "offscreen") if sys.platform != "win32" else None
app = QGuiApplication([])
from app.ui.widgets import app_icon  # noqa: E402

out = root / "assets"
out.mkdir(exist_ok=True)
pix = app_icon().pixmap(256, 256)
ok = pix.save(str(out / "icon.ico"), "ICO")
print("icon.ico", "ok" if ok else "FAILED")
