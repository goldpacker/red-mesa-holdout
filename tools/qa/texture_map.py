#!/usr/bin/env python3
"""Map every uploaded texture id to its local source file (QA-B).

Reads every `assets/**/roblox_ids.json` (the publish scripts' id maps),
finds the local image each id was uploaded from by content hash (the maps
store sha256[:16] of the uploaded file), falls back to the naming
convention when the local file changed since the upload, and reads the
resolution and alpha of that file.

    tools/qa/py tools/qa/texture_map.py                 # summary table
    tools/qa/py tools/qa/texture_map.py --json out.json # full map as JSON

Used by `texture_budget.py` to attribute texture memory per asset
(docs/PERF_BUDGET.md §5).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets"
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".tga", ".bmp"}
SKIP_DIRS = ("assets/ui/art/cache", "assets/source", "assets/blender")

# Workstream that owns each asset folder (docs/FACELIFT_TEAM.md).
OWNERS = [
    ("Landscape_", "ENV"), ("Cliff_", "ENV"), ("Rock_", "ENV"),
    ("GroundDressing", "ENV"), ("GroundStrips", "ENV"),
    ("textures/sky", "ENV"), ("textures/terrain", "ENV"), ("textures/ground", "ENV"),
    ("Emplacement", "HS"), ("Gunsights", "HS"), ("Tank", "HS"), ("Buggy", "HS"),
    ("Helicopter", "HS"), ("Jet", "HS"), ("SiegeCrawler", "HS"), ("TrimEnemy", "HS"),
    ("SupplyCrate", "HS"),
    ("InfantrySkinned", "CHAR"), ("InfantrySpike", "CHAR"), ("Infantry", "CHAR"),
    ("VfxDebris", "VFX"), ("assets/vfx", "VFX"),
    ("ui/kit", "Look"), ("ui/look", "Look"), ("ui/motion", "Look"),
]


def sha16(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def owner_for(rel: str) -> str:
    for prefix, owner in OWNERS:
        if prefix in rel:
            return owner
    return "?"


def hash_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in ASSETS.rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if path.suffix.lower() not in IMAGE_EXT or any(rel.startswith(s) for s in SKIP_DIRS):
            continue
        if "/previews/" in rel or rel.startswith("assets/previews"):
            continue
        index.setdefault(sha16(path), []).append(path)
    return index


def image_info(path: Path) -> dict:
    with Image.open(path) as im:
        w, h = im.size
        mode = im.mode
        alpha = False
        if "A" in im.getbands():
            lo, _hi = im.getchannel("A").getextrema()
            alpha = lo < 255
        gray = mode in ("L", "LA", "I;16", "I")
    return {"w": w, "h": h, "mode": mode, "alpha": alpha, "gray": gray}


def entries_of(map_path: Path) -> list[tuple[str, str, str | None]]:
    """(key, id, uploaded hash) for every texture id in one roblox_ids.json."""
    data = json.loads(map_path.read_text())
    hashes = data.get("hashes", {})
    out = []
    for group, maps in (data.get("textures") or {}).items():
        for kind, rid in maps.items():
            out.append((f"{group}/{kind}", rid, hashes.get(f"{group}/{kind}")))
    for group, rid in (data.get("wreck") or {}).items():
        out.append((f"wreck/{group}", rid, hashes.get(f"wreck/{group}")))
    for section in ("ids", "images"):
        for key, rid in (data.get(section) or {}).items():
            out.append((key, rid, hashes.get(key)))
    return out


def convention_path(map_path: Path, key: str) -> Path | None:
    folder = map_path.parent
    asset = folder.name
    parts = key.split("/")
    candidates: list[Path] = []
    if parts[0] == "wreck" and len(parts) == 2:
        candidates.append(folder / f"{asset}_{parts[1]}_wreck.png")
    elif len(parts) == 2:
        group, kind = parts
        candidates += [folder / f"{asset}_{group}_{kind}.png", folder / group / f"{group}_{kind}.png"]
        if kind == "roughness":
            candidates.append(folder / group / f"{group}_rough.png")
    else:
        candidates += [folder / f"{key}.png", folder / f"{key}.jpg"]
    for c in candidates:
        if c.exists():
            return c
    return None


def build_map() -> dict[str, dict]:
    index = hash_index()
    result: dict[str, dict] = {}
    for map_path in sorted(ASSETS.rglob("roblox_ids.json")):
        rel_map = map_path.relative_to(ROOT).as_posix()
        if any(rel_map.startswith(s) for s in SKIP_DIRS):
            continue
        asset = map_path.parent.name
        for key, rid, uploaded in entries_of(map_path):
            num = rid.replace("rbxassetid://", "")
            local = None
            changed = False
            if uploaded and uploaded in index:
                same_dir = [p for p in index[uploaded] if p.parent == map_path.parent or map_path.parent in p.parents]
                local = (same_dir or index[uploaded])[0]
            else:
                local = convention_path(map_path, key)
                changed = True
            rec = result.setdefault(num, {"id": num, "keys": [], "owner": owner_for(rel_map), "asset": asset})
            rec["keys"].append(key)
            if local is not None and "file" not in rec:
                rec["file"] = local.relative_to(ROOT).as_posix()
                rec["changed_since_upload"] = changed
                rec.update(image_info(local))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", help="write the full map to this file")
    args = ap.parse_args()
    table = build_map()
    if args.json:
        Path(args.json).write_text(json.dumps(table, indent=1, sort_keys=True))
    missing = [r for r in table.values() if "file" not in r]
    changed = [r for r in table.values() if r.get("changed_since_upload")]
    px = sum(r.get("w", 0) * r.get("h", 0) for r in table.values())
    print(f"{len(table)} texture ids, {px / 1e6:.1f} Mpx; {len(missing)} without a local file, "
          f"{len(changed)} whose local file changed since upload")
    for r in missing:
        print(f"  no local file: {r['asset']} {r['keys']} {r['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
