#!/usr/bin/env python3
"""CC0 raw inputs for the environment textures (Poly Haven).

Downloads the source maps each terrain material starts from into
assets/source/cc0/<id>/ (git-ignored, re-downloadable). Every id used here
is credited in assets/source/CC0_CREDITS.md.

    python3 tools/env/cc0.py fetch            # all sources, 2k jpg
    python3 tools/env/cc0.py fetch cliff_side # one source
    python3 tools/env/cc0.py list

Runs on any Python 3 (stdlib only).
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CC0_DIR = os.path.join(ROOT, "assets", "source", "cc0")
API = "https://api.polyhaven.com"
RESOLUTION = "2k"
# Poly Haven map key -> local file stem. nor_gl: OpenGL (+Y) tangent normals,
# the convention Roblox uses.
MAPS = {"Diffuse": "diff", "nor_gl": "nor_gl", "Rough": "rough", "Displacement": "disp", "AO": "ao"}

# id -> what it is used for (kept in sync with CC0_CREDITS.md).
SOURCES = {
    "aerial_beach_01": "Sand: base colour and fine ripple normals; Wash: drift sand",
    "gravelly_sand": "SandCoarse patches; Road: dirt grain under the ruts",
    "mud_cracked_dry_03": "Wash (Salt): cracked dry mud",
    "rock_face_03": "Rock: fractured rock",
    "cliff_side": "Sandstone: layered strata",
    "marble_cliff_04": "Limestone: pale strata bands (rotated 90°)",
    "dark_rock_02": "Slate: dark cap rock",
}


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "RedMesaHoldout-env/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def fetch(asset_id: str, resolution: str = RESOLUTION) -> str:
    out_dir = os.path.join(CC0_DIR, asset_id)
    os.makedirs(out_dir, exist_ok=True)
    files = json.loads(_get(f"{API}/files/{asset_id}"))
    info = json.loads(_get(f"{API}/info/{asset_id}"))
    with open(os.path.join(out_dir, "info.json"), "w") as fh:
        json.dump({"id": asset_id, "name": info.get("name"), "authors": info.get("authors"),
                   "dimensions_mm": info.get("dimensions"), "license": "CC0",
                   "url": f"https://polyhaven.com/a/{asset_id}"}, fh, indent=2)
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
        for k, v in SOURCES.items():
            print(f"{k:24s} {v}")
        return 0
    if argv[0] == "fetch":
        for asset_id in argv[1:] or list(SOURCES):
            print(f"fetch {asset_id}")
            fetch(asset_id)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
