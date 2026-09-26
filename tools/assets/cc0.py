#!/usr/bin/env python3
"""CC0 raw inputs for the hard-surface assets (Poly Haven).

Same layout as tools/env/cc0.py: assets/source/cc0/<id>/{diff,nor_gl,rough,
disp,ao}.jpg + info.json (git-ignored, re-downloadable). Materials use them
through `photo=` layers (tools/assets/rmh/materials.py), which re-colour and
bake them into our own textures. Every id is credited in
assets/source/CC0_CREDITS.md.

    python3 tools/assets/cc0.py fetch             # all HS sources
    python3 tools/assets/cc0.py fetch hessian_230 # one source
    python3 tools/assets/cc0.py list

Stdlib only.
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CC0_DIR = os.path.join(ROOT, "assets", "source", "cc0")
API = "https://api.polyhaven.com"
MAPS = {"Diffuse": "diff", "nor_gl": "nor_gl", "Rough": "rough", "Displacement": "disp", "AO": "ao"}

# id -> (resolution, use). Keep in sync with assets/source/CC0_CREDITS.md.
SOURCES = {
    "hessian_230": ("1k", "Emplacement sandbags: burlap weave detail"),
    "green_metal_rust": ("2k", "Emplacement/turret: chipped paint and bare-steel breakup"),
    "concrete_floor_worn_001": ("2k", "Emplacement bunker: worn concrete detail, stains"),
}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "RedMesaHoldout-hs/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def fetch(asset_id: str, resolution: str = "1k") -> str:
    out_dir = os.path.join(CC0_DIR, asset_id)
    os.makedirs(out_dir, exist_ok=True)
    files = json.loads(_get(f"{API}/files/{asset_id}"))
    info = json.loads(_get(f"{API}/info/{asset_id}"))
    with open(os.path.join(out_dir, "info.json"), "w") as fh:
        json.dump({"id": asset_id, "name": info.get("name"), "authors": info.get("authors"),
                   "dimensions_mm": info.get("dimensions"), "license": "CC0",
                   "resolution": resolution, "url": f"https://polyhaven.com/a/{asset_id}"}, fh, indent=2)
    for key, stem in MAPS.items():
        entry = files.get(key, {}).get(resolution, {}).get("jpg")
        if not entry:
            continue
        path = os.path.join(out_dir, f"{stem}.jpg")
        if os.path.exists(path) and os.path.getsize(path) == entry.get("size"):
            continue
        with open(path, "wb") as fh:
            fh.write(_get(entry["url"]))
        print(f"  {asset_id}/{stem}.jpg")
    return out_dir


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "list":
        for k, (res, use) in SOURCES.items():
            print(f"{k:26s} {res:3s} {use}")
        return 0
    if argv[0] == "fetch":
        for asset_id in argv[1:] or list(SOURCES):
            print(f"fetch {asset_id}")
            fetch(asset_id, SOURCES.get(asset_id, ("1k", ""))[0])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
