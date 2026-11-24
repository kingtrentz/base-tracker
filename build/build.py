"""Inject build/data.json into build/template.html and write index.html at the repo root.

Full refresh of game data:
  git clone --depth 1 https://github.com/ClashKingInc/ClashKingAssets /tmp/ck
  python build/gen_data.py /tmp/ck/assets/static_data
  python build/build.py
Page code changes go in build/template.html (never edit index.html by hand; it is overwritten here).
"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8"))
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
assert tpl.count("__DATA__") == 1, "template.html must contain __DATA__ exactly once"
out = tpl.replace("__DATA__", json.dumps(data, separators=(",", ":"), ensure_ascii=False))
open(os.path.join(HERE, "..", "index.html"), "w", encoding="utf-8").write(out)
print(f"index.html written ({len(out) // 1024} KB, Town Hall 1 to {data.get('top')}, {len(data['items'])} items)")
