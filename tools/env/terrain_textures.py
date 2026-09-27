"""Builds the terrain MaterialVariant texture sets (colour, normal, roughness).

    tools/env/py.sh tools/env/terrain_textures.py            # all materials
    tools/env/py.sh tools/env/terrain_textures.py Sand Road  # some

Inputs: Poly Haven CC0 maps in assets/source/cc0/<id>/ (fetch them with
`python3 tools/env/cc0.py fetch`). Outputs: seamless 1024² PNGs in
assets/textures/terrain/<Name>/ plus manifest.json; roughness ships at
ROUGH_N² (a box-downsample: the maps are near-constant, QA-B reclaim #13).
Each recipe re-tints the source to the art-bible palette and adds its own
procedural layer (pebbles, tyre ruts, sand drift, strata bands). Deterministic: fixed seeds.
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import texlib as T  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CC0 = os.path.join(ROOT, "assets", "source", "cc0")
OUT = os.path.join(ROOT, "assets", "textures", "terrain")
N = 1024
ROUGH_N = 256  # QA-B reclaim #13: roughness sd is 5-12/255, 256² loses nothing

# Palette (docs/FACELIFT_PLAN.md §2): rust-red cliffs #9E4A2E, ochre sand
# #C9824F, bleached washes #D9B98C. Values are albedo means.
PALETTE = {
    "sand": "#C9824F",         # ochre sand
    "sand_coarse": "#A9693F",  # gravel-lag patches: darker than the sand so the zones read (ENV-4)
    "road": "#9A6B48",         # packed road dirt
    "wash": "#D9B98C",         # bleached wash
    "rock": "#7A3D2B",         # between cliff shadow strata #6E3322 and rust-red
    "sandstone": "#9E4A2E",    # cliff rust-red
    "limestone": "#BA6A44",    # cliff light strata
    "slate": "#5A3226",        # cap rock
}


def src(asset_id: str, name: str) -> np.ndarray:
    path = os.path.join(CC0, asset_id, f"{name}.jpg")
    if not os.path.exists(path):
        raise SystemExit(f"missing {path}: run `python3 tools/env/cc0.py fetch {asset_id}`")
    img = T.load(path)
    if img.shape[0] == img.shape[1] and img.shape[0] % N == 0:
        return T.downsample(img, N)
    return T.resample(img, N)


def src_set(asset_id: str):
    col = src(asset_id, "diff")
    nor = T.decode_normal(src(asset_id, "nor_gl"))
    disp = T.gray(src(asset_id, "disp"))
    rough = T.gray(src(asset_id, "rough"))
    return col, nor, disp, rough


def remap(a: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return lo + (hi - lo) * T.normalize01(a)


def pebble_colors(height: np.ndarray, tone: np.ndarray, dark: str, light: str) -> np.ndarray:
    """Per-pebble colour between two tones, tops a little lighter."""
    a = T.srgb_to_linear(T.hex_rgb(dark))
    b = T.srgb_to_linear(T.hex_rgb(light))
    lin = a[None, None, :] + (b - a)[None, None, :] * (tone ** 1.5)[..., None]
    lin = lin * (0.75 + 0.35 * height)[..., None]
    return T.linear_to_srgb(lin)


def wind_ripples(seed: int, count: int, lee: float = 0.22) -> np.ndarray:
    """Aeolian ripple height field: crests along image x, `count` per tile.

    Asymmetric (gentle stoss, steep lee), crests wander and fork where a
    low-frequency warp shears them; amplitude fades in and out in patches.
    """
    yy = np.arange(N)[:, None] / N
    warp = 0.55 * T.fbm(N, seed, beta=3.0, min_period=200) + 0.1 * T.fbm(N, seed + 1, beta=2.2, min_period=40)
    phase = (count * yy + warp) % 1.0
    h = np.where(phase < 1 - lee, phase / (1 - lee), (1 - phase) / lee)
    h = T.blur(h.astype(np.float32), 1.2)
    amp = T.smoothstep(-1.0, 0.6, T.fbm(N, seed + 2, beta=2.6, min_period=96))
    return (h - h.mean()) * (0.35 + 0.65 * amp)


# ------------------------------------------------------------------ recipes
def sand():
    """Ochre basin sand: wind ripples (source relief) and sparse pebbles."""
    col, nor, disp, rough = src_set("aerial_beach_01")
    ripples = wind_ripples(11, 22)
    rip01 = T.normalize01(ripples)
    lowf = T.fbm(N, 12, beta=2.6, min_period=48)
    out = T.recolor(col, PALETTE["sand"], contrast=1.8, chroma_keep=0.15, flatten_sigma=40)
    # Wind-sorted grains: coarse pale grains on the crests, fine warm sand
    # in the troughs, so the ripples read in the albedo at range.
    out = T.tint(out, 0.84 + 0.3 * rip01)
    # Keep in-tile low frequencies weak: they are what makes tiling
    # visible at range. Large-scale variation comes from world patches.
    out = T.tint(out, 1.0 + 0.025 * lowf)
    grit = T.fbm(N, 13, beta=0.6, min_period=2, max_period=6)
    out = T.tint(out, 1.0 + 0.05 * grit)
    # Pebbles gather in troughs, in patches (lag).
    patch = T.smoothstep(0.1, 1.2, T.fbm(N, 14, beta=2.4, min_period=32))
    ph, pc, tone = T.scatter_stamps(N, 380, 15, 1.4, 3.4, mask=(0.08 + 0.92 * patch) * (1.1 - rip01))
    out = T.mix(out, pebble_colors(ph, tone, "#5A3022", "#A8704C"), pc * 0.85)
    # Normals: procedural ripples + fine source ripples + pebbles.
    n = T.height_to_normal(ripples * 9.0, 1.0)
    n = T.blend_normals(n, T.scale_normal(nor, 1.2))
    n = T.blend_normals(n, T.height_to_normal(ph * 2.2, 1.0))
    r = remap(rough, 0.86, 0.97) - 0.12 * pc
    return out, n, r


def sand_coarse():
    """Coarse gravel-lag sand for the large low-frequency patches."""
    col, nor, disp, rough = src_set("gravelly_sand")
    out = T.recolor(col, PALETTE["sand_coarse"], contrast=1.5, chroma_keep=0.25, flatten_sigma=96)
    out = T.tint(out, 1.0 + 0.03 * T.fbm(N, 21, beta=2.4, min_period=48))
    ph, pc, tone = T.scatter_stamps(N, 2600, 22, 1.8, 5.5, squash=0.6)
    out = T.mix(out, pebble_colors(ph, tone, "#5E3324", "#C99A70"), pc * 0.9)
    # Faint wind ripples so the patch edges blend into the rippled sand.
    yy = np.arange(N)[:, None] / N
    xx = np.arange(N)[None, :] / N
    warp = 0.02 * T.fbm(N, 24, beta=2.5, min_period=64)
    ripple = np.sin(2 * np.pi * (34 * yy + 3 * xx + warp * 34)) * 0.5 + 0.5
    ripple = ripple * T.smoothstep(-0.5, 0.8, T.fbm(N, 25, beta=2.5, min_period=96))
    n = T.scale_normal(nor, 1.3)
    n = T.blend_normals(n, T.height_to_normal(ripple * 1.2, 1.0))
    n = T.blend_normals(n, T.height_to_normal(ph * 2.6, 1.0))
    r = remap(rough, 0.84, 0.96) - 0.1 * pc
    return out, n, r


def road():
    """Packed dirt road: compacted tyre ruts along V, loose crown and berms."""
    col, nor, disp, rough = src_set("gravelly_sand")
    yy = np.arange(N)[:, None] / N
    xx = np.arange(N)[None, :] / N
    height = np.zeros((N, N), dtype=np.float32)
    rut_mask = np.zeros((N, N), dtype=np.float32)
    berm_mask = np.zeros((N, N), dtype=np.float32)
    tread_h = np.zeros((N, N), dtype=np.float32)
    rng = np.random.default_rng(31)
    # (centre, depth, width) per rut in tile units; two wheel pairs + an old track.
    ruts = [(0.12, 1.0, 0.020), (0.32, 1.0, 0.020), (0.60, 0.7, 0.024), (0.81, 0.7, 0.024), (0.47, 0.35, 0.03)]
    for c, depth, w in ruts:
        phase = rng.uniform(0, 2 * np.pi)
        centre = c + 0.008 * np.sin(2 * np.pi * yy + phase) + 0.002 * np.sin(2 * np.pi * 3 * yy + phase * 2)
        dx = (xx - centre + 0.5) % 1.0 - 0.5
        prof = np.exp(-(dx / w) ** 2)
        berm = np.exp(-((np.abs(dx) - 1.7 * w) / (0.7 * w)) ** 2)
        height += -depth * prof + 0.35 * depth * berm
        rut_mask = np.maximum(rut_mask, prof * depth)
        berm_mask = np.maximum(berm_mask, berm * depth)
        # Tyre tread: chevron bars every ~0.3 stud (tile = 32 studs).
        bars = np.sin(2 * np.pi * (96 * yy + np.abs(dx) * 2.4 / w))
        tread_h += depth * np.clip(bars, 0, 1) ** 0.5 * T.smoothstep(0.55, 0.25, np.abs(dx) / w) * (depth > 0.5)
    ground = T.fbm(N, 32, beta=2.2, min_period=3, max_period=256)
    height = height * 4.0 + ground * 0.35 + tread_h * 0.25
    out = T.recolor(col, PALETTE["road"], contrast=1.3, chroma_keep=0.2, flatten_sigma=96)
    out = T.tint(out, 1.0 + 0.04 * T.fbm(N, 33, beta=2.5, min_period=48))
    # Ruts compacted and darker; berms of loose pale dust.
    # Subtle in the albedo (the texture is world-projected, so ruts cross
    # the road where it bends; at range they must not read as hatching).
    out = T.tint(out, 1.0 - 0.12 * rut_mask + 0.08 * berm_mask)
    out = T.mix(out, np.broadcast_to(T.hex_rgb("#C49066"), out.shape), 0.15 * berm_mask)
    crown = T.smoothstep(0.35, 0.0, rut_mask)
    ph, pc, tone = T.scatter_stamps(N, 900, 34, 1.5, 4.0, mask=0.15 + 0.85 * crown)
    out = T.mix(out, pebble_colors(ph, tone, "#5A3223", "#C29A74"), pc * 0.9)
    n = T.height_to_normal(height, 1.2)
    n = T.blend_normals(n, T.scale_normal(nor, 1.0))
    n = T.blend_normals(n, T.height_to_normal(ph * 2.4, 1.0))
    r = remap(rough, 0.84, 0.95) - 0.14 * rut_mask + 0.03 * berm_mask - 0.1 * pc
    return out, n, r


def wash():
    """Bleached dry-wash bed: cracked mud plates with drifted sand."""
    col, nor, disp, rough = src_set("mud_cracked_dry_03")
    out = T.recolor(col, PALETTE["wash"], contrast=1.35, chroma_keep=0.3, flatten_sigma=128)
    cracks = T.smoothstep(0.35, 0.1, T.normalize01(disp))
    out = T.tint(out, 1.0 - 0.35 * cracks)
    out = T.tint(out, 1.0 + 0.06 * T.fbm(N, 41, beta=2.5, min_period=48))
    # Wind-blown sand drifts over parts of the crust (low frequency).
    drift = T.smoothstep(0.6, 1.8, T.fbm(N, 42, beta=1.8, min_period=16, max_period=320))
    sand_col = T.recolor(src("aerial_beach_01", "diff"), "#CD9A66", contrast=1.4, chroma_keep=0.1)
    out = T.mix(out, sand_col, drift * 0.85)
    n = T.scale_normal(nor, 1.5)
    flat = np.zeros_like(n)
    flat[..., 2] = 1
    n = T.mix(n, flat, drift * 0.7)
    n = n / np.linalg.norm(n, axis=-1, keepdims=True)
    r = remap(rough, 0.86, 0.97) + 0.03 * cracks
    return out, n, r


def rock():
    """Fractured rust-brown rock (terraces, boulders, scree)."""
    col, nor, disp, rough = src_set("rock_face_03")
    out = T.recolor(col, PALETTE["rock"], contrast=1.35, chroma_keep=0.4, flatten_sigma=48)
    cav = T.normalize01(T.highpass(disp, 12))
    out = T.tint(out, 0.8 + 0.4 * cav)
    # Flatten the source's large relief so the tile doesn't repeat visibly.
    nor = T.blend_normals(nor, T.height_to_normal(-T.blur(disp, 40) * 60.0, 1.0))
    n = T.scale_normal(nor, 1.25)
    r = remap(rough, 0.72, 0.95)
    return out, n, r


def strata_bands(seed: int, strength: float) -> np.ndarray:
    """Horizontal banding (along image rows), tileable in both directions."""
    rng = np.random.default_rng(seed)
    yy = np.arange(N)[:, None] / N
    xx = np.arange(N)[None, :] / N
    band = np.zeros((N, 1), dtype=np.float32)
    for k in (3, 5, 8, 13, 21, 34):
        band = band + np.sin(2 * np.pi * (k * yy + rng.random())) / np.sqrt(k)
    wobble = 0.004 * np.sin(2 * np.pi * (2 * xx + rng.random()))
    band2 = np.sin(2 * np.pi * (7 * (yy + wobble) + rng.random()))
    b = band / np.abs(band).max() * 0.7 + band2 * 0.3
    return 1.0 + strength * np.broadcast_to(b, (N, N))


def sandstone():
    """Rust-red layered sandstone with horizontal strata (cliffs, mesa)."""
    col, nor, disp, rough = src_set("cliff_side")
    # Stretch the source's blocky fractures into long horizontal layers so
    # the tile doesn't read as brickwork across a 2 km wall.
    col = T.mix(col, T.blur_aniso(col, 28, 0), 0.45)
    disp_h = T.blur_aniso(disp, 48, 1.5)
    out = T.recolor(col, PALETTE["sandstone"], contrast=1.1, chroma_keep=0.5, flatten_sigma=96)
    out = T.tint(out, strata_bands(61, 0.16))
    cav = T.normalize01(T.highpass(disp_h, 12))
    out = T.tint(out, 0.84 + 0.32 * cav)
    ledges = T.height_to_normal(disp_h * 40.0, 1.0)
    n = T.blend_normals(T.scale_normal(nor, 0.7), ledges)
    r = remap(rough, 0.74, 0.95)
    return out, n, r


def limestone():
    """Paler strata band (mid-cliff shelves, butte tops)."""
    col, nor, disp, rough = src_set("marble_cliff_04")
    col, nor, disp, rough = T.rot90(col), T.rot90(nor), T.rot90(disp[..., None])[..., 0], T.rot90(rough[..., None])[..., 0]
    # Rotating the image 90° counter-clockwise rotates the tangent frame too.
    nor = np.stack([-nor[..., 1], nor[..., 0], nor[..., 2]], axis=-1)
    col = T.mix(col, T.blur_aniso(col, 40, 0), 0.5)
    out = T.recolor(col, PALETTE["limestone"], contrast=1.1, chroma_keep=0.3, flatten_sigma=96)
    out = T.tint(out, strata_bands(71, 0.12))
    n = T.scale_normal(nor, 1.0)
    r = remap(rough, 0.72, 0.94)
    return out, n, r


def slate():
    """Dark cap rock along the rims."""
    col, nor, disp, rough = src_set("dark_rock_02")
    out = T.recolor(col, PALETTE["slate"], contrast=1.2, chroma_keep=0.3, flatten_sigma=96)
    out = T.tint(out, strata_bands(81, 0.06))
    n = T.scale_normal(nor, 1.2)
    r = remap(rough, 0.7, 0.92)
    return out, n, r


# name -> (recipe, base material, studs per tile, pattern, sources)
MATERIALS = {
    "Sand": (sand, "Sand", 48, "Organic", ["aerial_beach_01"]),
    "SandCoarse": (sand_coarse, "Mud", 40, "Organic", ["gravelly_sand"]),
    "Road": (road, "Ground", 32, "Regular", ["gravelly_sand"]),
    "Wash": (wash, "Salt", 24, "Organic", ["mud_cracked_dry_03", "aerial_beach_01"]),
    "Rock": (rock, "Rock", 30, "Organic", ["rock_face_03"]),
    "Sandstone": (sandstone, "Sandstone", 64, "Regular", ["cliff_side"]),
    "Limestone": (limestone, "Limestone", 64, "Regular", ["marble_cliff_04"]),
    "Slate": (slate, "Slate", 36, "Regular", ["dark_rock_02"]),
}


def build(name: str) -> dict:
    fn, base, spt, pattern, sources = MATERIALS[name]
    col, nor, rough = fn()
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    files = {"color": f"{name}_color.png", "normal": f"{name}_normal.png", "roughness": f"{name}_rough.png"}
    T.save(os.path.join(d, files["color"]), col)
    T.save(os.path.join(d, files["normal"]), T.encode_normal(nor))
    T.save(os.path.join(d, files["roughness"]), T.downsample(np.clip(rough, 0, 1)[..., None], ROUGH_N))
    info = {
        "name": name, "variant": f"RedMesa{name}", "base_material": base,
        "studs_per_tile": spt, "pattern": pattern, "size": N, "rough_size": ROUGH_N, "files": files,
        "mean_color": T.mean_srgb(col), "roughness_mean": round(float(np.mean(rough)), 3),
        "seam_ratio": {k: round(T.seam_ratio(v), 2) for k, v in (("color", col), ("normal", nor), ("roughness", rough))},
        "cc0_sources": sources,
    }
    with open(os.path.join(d, "manifest.json"), "w") as fh:
        json.dump(info, fh, indent=2)
    print(f"{name:10s} mean {info['mean_color']} rough {info['roughness_mean']} seams {info['seam_ratio']}")
    return info


def main(argv):
    names = argv or list(MATERIALS)
    for name in names:
        build(name)


if __name__ == "__main__":
    main(sys.argv[1:])
