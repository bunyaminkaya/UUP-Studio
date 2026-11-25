"""build.bat tarafından çağrılır: assets/icon.ico üretir (çok boyutlu, PNG sıkıştırmalı).

Windows görev çubuğu 16-48 px boyutlarını ister; yalnızca 256 px'lik bir ICO genel simge gösterir."""
import os
import struct
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
if sys.platform != "win32":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

app = QGuiApplication([])
from app.ui.widgets import ICON_SIZES, icon_pixmap  # noqa: E402

images = []
for size in ICON_SIZES:
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    icon_pixmap(size).save(buf, "PNG")
    buf.close()
    images.append((size, bytes(data)))

header = struct.pack("<HHH", 0, 1, len(images))
offset = 6 + 16 * len(images)
entries, blobs = b"", b""
for size, png in images:
    dim = 0 if size >= 256 else size
    entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(png), offset + len(blobs))
    blobs += png
out = root / "assets"
out.mkdir(exist_ok=True)
(out / "icon.ico").write_bytes(header + entries + blobs)
print("icon.ico ok", len(images), "boyut")
