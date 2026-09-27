"""WreckMaps (HS-5): burnt-wreck colour maps for every enemy vehicle.

    tools/assets/build.sh WreckMaps                  # all vehicles + TrimEnemy
    BUILD_ARGS="--only Tank,Buggy" tools/assets/build.sh WreckMaps

No geometry and no bake: each vehicle's baked maps are turned into a
charred, rusted, paint-blistered colour map in image space and saved at
256² (512² for the Siege Crawler) next to them as
`<Name>_<group>_wreck.png` (the wreck look is dark and blotchy, so a small
colour map is enough; the vehicle's own full-size normal and roughness
maps keep the bolts, welds and panel lines). `wreck.json` records the hash of the colour map each one was
derived from: `publish.py upload` uploads a wreck map only while that
still matches, so a rebuilt vehicle never ships a wreck map painted for
its old UV layout. The rbxmx then carries, under each textured part, a
Folder `Wreck` holding the burnt SurfaceAppearance, which
`EnemyTypes/Common/Kit.char` swaps in on death.

Recipe (per texel, linear colour):
  - char: soot black to burnt brown, mottled (large + mid value noise);
  - blistered paint: patches where the original paint survives, darkened
    and desaturated, with pale ash speckles (blisters) at their edges;
  - rust: on bare-metal chips (metalness map), convex edges (curvature
    from the normal map) and in blotches, dark to orange;
  - ash: where the paint was dusty, a grey-brown ash film;
  - grime: the original cavity darkening is kept and deepened;
  - red markings burn to a dark oxide red and flake.
"""
import hashlib
import json
import math
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
VEHICLES = ["Tank", "Buggy", "Helicopter", "Jet", "SiegeCrawler", "TrimEnemy"]
# Wreck colour map size. Measured in Studio (HS-5): a 512² wreck map in view
# costs ~0.67 MB of GraphicsTexture, so the wave vehicles and the shared trim
# get 256² (their full-size normal/roughness maps carry the detail); the
# boss, seen alone in wave 10 and inspected up close as a wreck, keeps 512².
OUT_PX = {"SiegeCrawler": 512}
DEFAULT_PX = 256


def _load(path):
    img = bpy.data.images.load(str(path), check_existing=False)
    img.colorspace_settings.name = "Non-Color"  # raw bytes: we do the sRGB maths ourselves
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)


def _save(arr, path):
    h, w = arr.shape[:2]
    img = bpy.data.images.new(path.stem, w, h, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(arr, 0.0, 1.0)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def to_linear(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def _resize(a, n):
    """Area-average (down, integer factors) or bilinear (up) resize of an
    (h, h[, c]) array to n x n."""
    h = a.shape[0]
    if h == n:
        return a
    if h > n and h % n == 0:
        k = h // n
        return a.reshape(n, k, n, k, *a.shape[2:]).mean(axis=(1, 3))
    xs = np.linspace(0, h - 1, n)
    i0 = np.floor(xs).astype(int)
    i1 = np.minimum(i0 + 1, h - 1)
    t = (xs - i0).astype(np.float32)
    extra = (1,) * (a.ndim - 2)
    tr = t.reshape(n, 1, *extra)
    rows = a[i0] * (1 - tr) + a[i1] * tr
    tc = t.reshape(1, n, *extra)
    return rows[:, i0] * (1 - tc) + rows[:, i1] * tc


def _noise(n, cells, rng, octaves=1):
    """Smooth value noise in 0..1 (bilinear-upsampled random grids, summed octaves)."""
    total = np.zeros((n, n), dtype=np.float32)
    amp, norm = 1.0, 0.0
    for o in range(octaves):
        c = cells * (2 ** o)
        grid = rng.random((c + 1, c + 1)).astype(np.float32)
        total += amp * _resize(grid, n)
        norm += amp
        amp *= 0.5
    return total / norm


def _blur(a, r):
    """Box blur of radius r (separable, edge-clamped)."""
    if r < 1:
        return a
    out = a
    for axis in (0, 1):
        pad = [(0, 0)] * a.ndim
        pad[axis] = (r + 1, r)
        p = np.pad(out, pad, mode="edge")
        c = np.cumsum(p, axis=axis)
        hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
        lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
        out = (hi - lo) / (2 * r + 1)
    return out


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    t = np.asarray(t, dtype=np.float32)
    if t.ndim == 2:
        t = t[..., None]
    return a + (b - a) * t


def burn(color, metal, normal, seed):
    """Wreck colour (linear RGB, n x n) from a vehicle's maps (linear colour,
    metalness 0..1 or None, tangent normal 0..1), all already at n x n."""
    n = color.shape[0]
    rng = np.random.default_rng(seed)
    lum = color @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    local = _blur(lum, max(2, n // 64))
    cav = np.clip((local - lum) / np.maximum(local, 1e-3), 0.0, 1.0)
    warm = np.clip((color[..., 0] - color[..., 2]) / np.maximum(color[..., 0], 1e-3), 0.0, 1.0)
    dust = smoothstep(0.1, 0.25, lum) * smoothstep(0.2, 0.45, warm)
    red = smoothstep(1.8, 3.0, color[..., 0] / np.maximum(color[..., 1] + color[..., 2], 1e-3) * 2.0) * smoothstep(0.02, 0.06, color[..., 0])
    if metal is not None:
        chip = smoothstep(0.3, 0.7, metal)
    else:
        sat = (color.max(axis=-1) - color.min(axis=-1)) / np.maximum(color.max(axis=-1), 1e-3)
        chip = smoothstep(0.14, 0.24, lum) * (1 - smoothstep(0.12, 0.3, sat)) * (1 - dust)
    nx, ny = normal[..., 0] * 2 - 1, normal[..., 1] * 2 - 1
    curv = np.gradient(nx, axis=1) + np.gradient(ny, axis=0)
    convex = smoothstep(0.02, 0.12, _blur(curv, 1) * (n / 512.0))

    big = _noise(n, 12, rng, 3)
    mid = _noise(n, 24, rng, 3)
    fine = _noise(n, 96, rng, 2)
    speck = _noise(n, 220, rng, 1)
    mid2 = _noise(n, 18, rng, 2)

    soot = np.array([0.011, 0.0095, 0.0085], np.float32)
    brown = np.array([0.034, 0.022, 0.015], np.float32)
    rust_dark = np.array([0.062, 0.026, 0.011], np.float32)
    rust_orange = np.array([0.19, 0.072, 0.024], np.float32)
    ash = np.array([0.15, 0.14, 0.13], np.float32)
    oxide = np.array([0.075, 0.016, 0.01], np.float32)

    out = lerp(soot, brown, smoothstep(0.3, 0.75, mid * 0.6 + big * 0.4))
    # Blistered paint: surviving patches, darkened and greyed, bubbled rims.
    keep = smoothstep(0.58, 0.68, big * 0.65 + mid * 0.35) * (1 - dust * 0.7)
    gray = (color.mean(axis=-1, keepdims=True) * 0.55 + color * 0.45) * 0.3
    paint = np.where(red[..., None] > 0.5, oxide * (0.7 + 0.6 * fine[..., None]), gray * (0.75 + 0.5 * fine[..., None]))
    out = lerp(out, paint, keep * 0.9)
    rim = smoothstep(0.5, 0.57, big * 0.65 + mid * 0.35) * (1 - smoothstep(0.6, 0.66, big * 0.65 + mid * 0.35))
    blister = np.clip(rim * 0.8 + keep * smoothstep(0.78, 0.86, speck), 0, 1)
    out = lerp(out, ash * 0.7, blister * 0.22)
    # Red markings flake to oxide even outside the kept paint.
    out = lerp(out, oxide * (0.6 + 0.6 * fine[..., None]), red * smoothstep(0.35, 0.55, fine) * 0.8)
    # Rust on chips, convex edges and in blotches.
    rust = np.clip(chip * 0.95 + convex * 0.75 + smoothstep(0.62, 0.78, mid2) * 0.55, 0.0, 1.0)
    rust *= 0.55 + 0.45 * smoothstep(0.25, 0.7, fine)
    rust_col = lerp(rust_dark, rust_orange, smoothstep(0.35, 0.8, fine * 0.7 + speck * 0.3))
    out = lerp(out, rust_col, rust * 0.7)
    # Burnt dust turns to a grey-brown ash film.
    out = lerp(out, ash * (0.55 + 0.35 * fine[..., None]), dust * 0.75 * (0.6 + 0.4 * mid))
    # Grime deepened in cavities.
    out = out * (1 - np.clip(cav * 0.9, 0, 0.75))[..., None]
    return out.astype(np.float32)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def process(name):
    folder = ROOT / "assets" / "exported" / name
    manifest = json.loads((folder / "manifest.json").read_text())
    textures = manifest.get("textures") or {}
    record = {}
    for i, (group, files) in enumerate(sorted(textures.items())):
        if "color" not in files or "normal" not in files:
            continue
        cpath = folder / files["color"]
        color = to_linear(_load(cpath)[..., :3])
        n = OUT_PX.get(name, DEFAULT_PX)
        size = color.shape[0]
        work = min(size, 1024)
        color_w = _resize(color, work)
        normal = _resize(_load(folder / files["normal"])[..., :3], work)
        metal = _resize(_load(folder / files["metal"])[..., 0], work) if files.get("metal") else None
        seed = int(hashlib.sha256(f"{name}/{group}".encode()).hexdigest()[:8], 16)
        wreck = burn(color_w, metal, normal, seed)
        wreck = _resize(wreck, n)
        out = folder / f"{name}_{group}_wreck.png"
        _save(to_srgb(wreck), out)
        record[group] = {"file": out.name, "source": _sha(cpath), "px": n}
        print(f"[wreck] {name}/{group}: {out.name} ({n}px) from {files['color']} "
              f"mean {float(wreck.mean()):.4f} vs {float(color_w.mean()):.4f}", flush=True)
    (folder / "wreck.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    return record


def build(only=None, **kw):
    for name in only or VEHICLES:
        process(name)
