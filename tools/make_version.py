"""PyInstaller için Windows sürüm bilgisi dosyası üretir (build\version_info.txt)."""
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
text = (root / "app" / "config.py").read_text("utf-8")
ver = re.search(r'APP_VERSION = "([\d.]+)"', text).group(1)
parts = (ver.split(".") + ["0", "0", "0"])[:4]
tup = ", ".join(parts)
out = root / "build"
out.mkdir(exist_ok=True)
(out / "version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers=({tup}), prodvers=({tup}), mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Bünyamin KAYA'),
      StringStruct('FileDescription', 'UUP Studio'),
      StringStruct('FileVersion', '{ver}'),
      StringStruct('InternalName', 'UUP Studio'),
      StringStruct('LegalCopyright', 'Bünyamin KAYA - bunyaminkaya.com'),
      StringStruct('OriginalFilename', 'UUP Studio.exe'),
      StringStruct('ProductName', 'UUP Studio'),
      StringStruct('ProductVersion', '{ver}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")
(out / "version.txt").write_text(ver, encoding="utf-8")
print(ver)
