"""GameMaps (RECLAIM-HS): re-export the game-resolution copies of the maps
of every model that declares `GAME_PX`, without rebuilding it.

    tools/assets/build.sh GameMaps
    BUILD_ARGS="--only Tank,SiegeCrawler" tools/assets/build.sh GameMaps

Reads each model module's `GAME_PX` (the same value its `build()` puts on
`Asset.game_px`), downsamples the exported full-size maps and records
`game_px` / `upload_textures` in its manifest (rmh/game_maps.py). Then
`publish.py upload <Name>` sends the copies and `publish.py rbxmx <Name>`
points the SurfaceAppearances (and the burnt `Wreck` looks' normal and
roughness) at them. No geometry, UVs or mesh ids change, so no harvest.
"""
import importlib
from pathlib import Path

from rmh import game_maps
from rmh.pipeline import log

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def _asset_name(module):
    return "".join(w.capitalize() for w in module.split("_"))


def _module_name(asset):
    import re

    return re.sub(r"(?<!^)(?=[A-Z])", "_", asset).lower()


def _declared():
    """{asset: GAME_PX} for every model module that declares it."""
    out = {}
    for path in sorted(HERE.glob("*.py")):
        if path.stem in ("__init__", "game_maps"):
            continue
        text = path.read_text()
        if "GAME_PX" not in text:
            continue
        mod = importlib.import_module(f"models.{path.stem}")
        px = getattr(mod, "GAME_PX", None)
        if px:
            out[_asset_name(path.stem)] = px
    return out


def build(only=None, **kw):
    if only:
        declared = {}
        for name in only:
            mod = importlib.import_module(f"models.{_module_name(name)}")
            px = getattr(mod, "GAME_PX", None)
            if not px:
                raise SystemExit(f"{name}: its model file declares no GAME_PX")
            declared[name] = px
    else:
        declared = _declared()
    for name, px in declared.items():
        folder = ROOT / "assets" / "exported" / name
        up = game_maps.export(folder, px, log)
        log(f"GameMaps {name}: {sum(len(v) for v in up.values())} maps capped at {px}px")
