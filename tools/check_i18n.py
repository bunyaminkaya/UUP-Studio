"""Kodda kullanılan t("...") anahtarlarının iki dilde de bulunduğunu doğrular."""
import json, re, sys
from pathlib import Path
root = Path(__file__).resolve().parent.parent
keys = set()
for f in (root / "app").rglob("*.py"):
    text = f.read_text("utf-8")
    keys |= set(re.findall(r'\bt\(\s*"([a-z_]+\.[a-z0-9_]+)"', text))
    keys |= set(re.findall(r'"((?:browser|dl|lib|adv|settings|about|job|nav|win|stage|status|file|date|unit)\.[a-z0-9_]+)"', text))
    for m in re.findall(r't\(f"([a-z_]+\.)\{', text):
        pass
tr = json.loads((root / "locales" / "tr.json").read_text("utf-8"))
en = json.loads((root / "locales" / "en.json").read_text("utf-8"))
keys.discard("settings.json")
missing = sorted(k for k in keys if k not in tr or k not in en)
unused = sorted(k for k in tr if k not in keys and not k.startswith(("stage.", "status.")))
print("used:", len(keys), "missing:", missing, "unused:", unused)
sys.exit(1 if missing else 0)
