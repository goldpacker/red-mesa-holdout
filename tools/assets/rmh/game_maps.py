"""Game-resolution copies of an asset's own maps (opt-in, RECLAIM-HS).

An asset whose model file sets a module-level `GAME_PX` (and
`a.game_px = GAME_PX` in `build()`) still bakes at its full `tex_size`:
the .blend, the previews and `<Name>_<group>_<ch>.png` stay full size, so
key-art renders, wreck maps (models/wreck_maps.py) and later bakes read
full detail. What ships to Roblox is a copy of each larger map
downsampled to `game_px`, `<Name>_<group>_<ch>_<px>.png`, listed in the
manifest under `upload_textures` (`game_px` records the cap);
`publish.py upload` sends those in place of the full-size files. Maps
already at or below `game_px` (e.g. a `metal_px=512` metalness map) are
uploaded as they are. Shared trim groups are never touched.

Filter: a box average over integer factors, i.e. the next level of a
standard mip chain. Colour is averaged in linear light and re-encoded to
sRGB; normal, roughness and metalness maps are averaged as stored (normals
are not renormalised, as in a mip chain). Wherever the full map had at
least two texels per screen pixel, the GPU was already sampling that
level, so the copy looks the same there.

Runs inside Blender (numpy + bpy image IO, no bake):
    tools/assets/build.sh GameMaps                          # every model with GAME_PX
    BUILD_ARGS="--only Tank,Buggy" tools/assets/build.sh GameMaps
and at the end of every build of an opted-in asset (pipeline.finish).
"""
import json
from pathlib import Path

import bpy
import numpy as np

GRAY = ("rough", "metal")


def _load(path):
    """Raw stored values 0..1, (h, w, 4), row 0 = bottom (Blender order)."""
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.name = "Non-Color"  # raw bytes; sRGB maths done here
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)


def _save(arr, path, grayscale):
    """8-bit PNG of raw values 0..1 (RGB, or single-channel for gray maps)."""
    from . import pipeline

    h, w = arr.shape[:2]
    img = bpy.data.images.new(path.stem, w, h, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(arr[..., :3], 0.0, 1.0)
    img.pixels.foreach_set(rgba.ravel())
    pipeline._save_png(img, path, grayscale=grayscale)
    bpy.data.images.remove(img)


def _to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def _box(a, k):
    h, w = a.shape[:2]
    return a.reshape(h // k, k, w // k, k, *a.shape[2:]).mean(axis=(1, 3))


def downsample(arr, channel, k):
    """(h, w, 4) raw values -> (h/k, w/k, 3) raw values for `channel`."""
    rgb = arr[..., :3].astype(np.float64)
    if channel == "color":
        return _to_srgb(_box(_to_linear(rgb), k))
    return _box(rgb, k)


def export(folder, px, log=print):
    """Writes the game copies for one exported asset folder and records them
    in its manifest.json. Returns {group: {channel: file}}."""
    folder = Path(folder)
    man_path = folder / "manifest.json"
    manifest = json.loads(man_path.read_text())
    upload = {}
    for group, files in manifest.get("textures", {}).items():
        for ch, fname in files.items():
            src = folder / fname
            arr = _load(src)
            h, w = arr.shape[:2]
            if max(w, h) <= px:
                continue
            k = max(w, h) // px
            if w % k or h % k or max(w, h) != px * k:
                raise ValueError(f"{src.name}: {w}x{h} is not an integer multiple of {px}")
            out = folder / f"{src.stem}_{px}.png"
            _save(downsample(arr, ch, k), out, grayscale=ch in GRAY)
            upload.setdefault(group, {})[ch] = out.name
            log(f"game map {folder.name}/{group}/{ch}: {w}x{h} -> {w // k}x{h // k} {out.name}")
    manifest["game_px"] = px
    if upload:
        manifest["upload_textures"] = upload
    else:
        manifest.pop("upload_textures", None)
    with open(man_path, "w") as fh:
        json.dump(manifest, fh, indent=1)
    return upload
