"""Texture atlases for the ENV-4 ground patches and conflict dressing.

    tools/env/py.sh tools/env/dressing/textures.py

Two small atlases (painted at twice the size and shrunk, like the ENV-3
dressing atlas), shared by every ENV-4 mesh (tools/env/dressing/meshes.py):

ConflictProps: opaque, 1024² painting -> 512² colour + 512² normal
(block-compressed: ~0.67 MB resident by QA-B's model). Regions (x, y, w, h
in painting pixels) and what one tile is in studs:
  concrete (  0,   0, 256, 256)  8 x 8    worn concrete: jersey barriers
  hesco    (256,   0, 256, 256)  4 x 4    geotextile behind a welded wire grid
  adobe    (512,   0, 256, 256)  8 x 8    mud plaster flaking off mudbrick courses
  brick    (768,   0, 256, 256)  8 x 8    bare mudbrick: broken wall tops, rubble
  wood     (  0, 256, 512,  64)  8 x 1    weathered grey timber, grain along U
  planks   (  0, 320, 512,  64)  8 x 1    olive crate planks, seams along U
  rubber   (  0, 384, 512,  64)  8 x 1    tyre tread, blocks across V
  char     (  0, 448, 512,  64)  8 x 1    burnt timber / soot
  drum     (512, 256, 256, 128)  7.2 x 3.6  faded olive drum (U around, V up)
  drum2    (512, 384, 256, 128)  7.2 x 3.6  rusted red-brown drum
  sheet    (768, 256, 256, 256)  6 x 6    rusted corrugated sheet (ribs along V)
  sand     (  0, 512, 512, 256)  24 x 12  ochre sand (hesco fill, drifts on props)
  steel    (512, 512, 256, 256)  4 x 4    weathered galvanised steel, pole hardware
  (768, 512, 256, 512), (0, 768, 768, 256): spare

GroundPatches: RGBA (alpha = coverage), 1024 x 512 painting -> 512 x 256
colour + 256 x 128 normal (~0.8 MB). Flat alpha meshes lying on the floor
and the concertina wire:
  gravel   (  0,   0, 256, 256)  20 studs   pebble lag patch
  scorch   (256,   0, 256, 256)  16 studs   burnt ground (hulks, fresh craters)
  stubble  (512,   0, 256, 256)  12 studs   flat mat of dry grass stubble
  stain    (768,   0, 256, 256)  14 studs   dark compacted soil / old oil
  trample  (  0, 256, 1024, 128) 48 x 6     trampled lane edge: scuffs, boot prints
  wire     (  0, 384, 1024, 128) 16 x 11.3  concertina loops (U along the coil,
                                            V once around it)
Deterministic (fixed seeds).
"""
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import texlib as T  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
CC0 = os.path.join(ROOT, "assets", "source", "cc0")
TERRAIN = os.path.join(ROOT, "assets", "textures", "terrain")
OUT = os.path.join(ROOT, "assets", "textures", "dressing")
PREVIEW = os.path.join(ROOT, "assets", "previews", "dressing")
ALPHA_FLOOR = 2.5 / 255.0

PROPS = {
    "concrete": ((0, 0, 256, 256), (8.0, 8.0)),
    "hesco": ((256, 0, 256, 256), (4.0, 4.0)),
    "adobe": ((512, 0, 256, 256), (8.0, 8.0)),
    "brick": ((768, 0, 256, 256), (8.0, 8.0)),
    "wood": ((0, 256, 512, 64), (8.0, 1.0)),
    "planks": ((0, 320, 512, 64), (8.0, 1.0)),
    "rubber": ((0, 384, 512, 64), (8.0, 1.0)),
    "char": ((0, 448, 512, 64), (8.0, 1.0)),
    "drum": ((512, 256, 256, 128), (7.2, 3.6)),
    "drum2": ((512, 384, 256, 128), (7.2, 3.6)),
    "sheet": ((768, 256, 256, 256), (6.0, 6.0)),
    "sand": ((0, 512, 512, 256), (24.0, 12.0)),
    "steel": ((512, 512, 256, 256), (4.0, 4.0)),
}
PATCHES = {
    "gravel": ((0, 0, 256, 256), (20.0, 20.0)),
    "scorch": ((256, 0, 256, 256), (16.0, 16.0)),
    "stubble": ((512, 0, 256, 256), (12.0, 12.0)),
    "stain": ((768, 0, 256, 256), (14.0, 14.0)),
    "trample": ((0, 256, 1024, 128), (48.0, 6.0)),
    "wire": ((0, 384, 1024, 128), (16.0, 11.3)),
}


def lin(hex_):
    return T.srgb_to_linear(T.hex_rgb(hex_))


def cc0(asset_id: str, name: str, n: int) -> np.ndarray:
    img = T.load(os.path.join(CC0, asset_id, f"{name}.jpg"))
    if img.shape[0] == img.shape[1] and img.shape[0] % n == 0:
        return T.downsample(img, n)
    return T.resample(img, n)


def flat_normal(h, w):
    n = np.zeros((h, w, 3), np.float32)
    n[..., 2] = 1.0
    return n


def normals(hgt, px_per_stud):
    """Tangent normal from a height map in studs (periodic)."""
    dx = (np.roll(hgt, -1, axis=1) - np.roll(hgt, 1, axis=1)) * 0.5 * px_per_stud
    dy = (np.roll(hgt, 1, axis=0) - np.roll(hgt, -1, axis=0)) * 0.5 * px_per_stud
    n = np.stack([-dx, -dy, np.ones_like(hgt)], axis=-1)
    return (n / np.linalg.norm(n, axis=-1, keepdims=True)).astype(np.float32)


def square_noise(w, h, seed, **kw):
    """Periodic fbm for a w x h region (w, h powers of two, periodic in both)."""
    n = max(w, h)
    a = T.fbm(n, seed, **kw)
    if w == h:
        return a
    # tile the square noise across the long side, keeping periodicity along it
    if w > h:
        return a[:h, :w] if n == w else np.tile(a, (1, w // n))[:h, :w]
    return a[:h, :w]


def grain(w, h, seed, lo=2, hi=24):
    return square_noise(w, h, seed, beta=1.4, min_period=lo, max_period=hi)


# ------------------------------------------------------------------ props
def concrete(w, h, spt):
    col = T.recolor(cc0("concrete_floor_worn_001", "diff", w), "#948A7A", contrast=1.25, chroma_keep=0.25, flatten_sigma=w / 6)
    nor = T.scale_normal(T.decode_normal(cc0("concrete_floor_worn_001", "nor_gl", w)), 0.8)
    # rain/dust streaks running down, and a few dark stains
    streak = T.smoothstep(0.8, 2.2, T.blur_aniso(T.fbm(w, 111, beta=1.8, min_period=3), 0.6, 9.0))
    stain = T.smoothstep(0.9, 1.8, T.fbm(w, 112, beta=2.6, min_period=30))
    col = T.tint(col, 1.0 - 0.18 * streak - 0.22 * stain + 0.05 * grain(w, h, 113))
    return col, nor


def hesco(w, h, spt):
    ppx = w / spt[0]
    fab = T.recolor(cc0("hessian_230", "diff", w), "#9C8B6E", contrast=1.35, chroma_keep=0.3, flatten_sigma=w / 5)
    fab_n = T.scale_normal(T.decode_normal(cc0("hessian_230", "nor_gl", w)), 0.6)
    yy, xx = np.mgrid[0:h, 0:w] / ppx
    cell = 0.5  # welded mesh spacing in studs
    fx = (xx / cell) % 1.0
    fy = (yy / cell) % 1.0
    # fabric pillows between the wires, wires on top
    pillow = np.sin(np.pi * fx) * np.sin(np.pi * fy)
    dwx = np.minimum(fx, 1 - fx) * cell
    dwy = np.minimum(fy, 1 - fy) * cell
    wire_w = 0.028
    wire = np.maximum(T.smoothstep(wire_w * 1.6, wire_w * 0.6, dwx), T.smoothstep(wire_w * 1.6, wire_w * 0.6, dwy))
    # bay joint: a heavier coil pin at the tile's vertical edge
    edge = np.minimum(xx % spt[0], spt[0] - xx % spt[0])
    pin = T.smoothstep(0.09, 0.04, edge)
    hgt = 0.05 * pillow + 0.035 * wire + 0.05 * pin
    dust = T.smoothstep(-0.2, 1.4, T.fbm(w, 121, beta=2.2, min_period=20))
    col = T.tint(fab, (0.78 + 0.28 * pillow) * (1 + 0.12 * dust))
    steel = lin("#6A6862")
    steel_c = T.linear_to_srgb(steel[None, None, :] * (0.8 + 0.3 * T.normalize01(grain(w, h, 122)))[..., None])
    m = np.maximum(wire, pin)[..., None]
    col = col * (1 - m) + steel_c * m
    return col, T.blend_normals(fab_n, normals(hgt.astype(np.float32), ppx))


def adobe(w, h, spt):
    ppx = w / spt[0]
    base = T.recolor(cc0("gravelly_sand", "diff", w), "#B48A64", contrast=0.8, chroma_keep=0.2, flatten_sigma=w / 6)
    yy, xx = np.mgrid[0:h, 0:w] / ppx
    course = 0.5  # mudbrick course height (studs)
    row = np.floor(yy / course)
    blen = 1.6
    off = (row % 2) * blen * 0.5
    bx = ((xx + off) % blen) / blen
    by = (yy % course) / course
    mortar = np.maximum(T.smoothstep(0.06, 0.02, np.minimum(bx, 1 - bx) * blen), T.smoothstep(0.07, 0.02, np.minimum(by, 1 - by) * course))
    brick_h = 0.03 * (1 - mortar) - 0.02 * mortar
    # plaster: covers most of the wall, flaked off in patches
    flake = T.fbm(w, 131, beta=2.4, min_period=6)
    plaster = T.smoothstep(-0.55, -0.25, flake)
    hgt = plaster * 0.06 + (1 - plaster) * brick_h + 0.01 * grain(w, h, 132)
    brick = lin("#9A6B48") * (0.85 + 0.25 * T.normalize01(T.fbm(w, 133, beta=1.2, min_period=8, max_period=40)))[..., None]
    brick = brick * (1 - 0.35 * mortar)[..., None]
    plast = T.srgb_to_linear(base) * (1 + 0.1 * grain(w, h, 134))[..., None]
    # cracks in the plaster
    crack = T.smoothstep(2.0, 2.6, np.abs(T.fbm(w, 135, beta=2.1, min_period=3)))
    plast = plast * (1 - 0.45 * crack)[..., None]
    col = plast * plaster[..., None] + brick * (1 - plaster)[..., None]
    edge = T.smoothstep(0.0, 0.12, np.abs(flake + 0.4))  # darker lip where plaster breaks
    col = col * (0.82 + 0.18 * edge)[..., None]
    return T.linear_to_srgb(col), normals(hgt.astype(np.float32), ppx)


def brick(w, h, spt):
    ppx = w / spt[0]
    yy, xx = np.mgrid[0:h, 0:w] / ppx
    course = 0.5
    row = np.floor(yy / course)
    blen = 1.6
    off = (row % 2) * blen * 0.5 + (row * 0.37 % 1) * 0.3
    bx = ((xx + off) % blen) / blen
    by = (yy % course) / course
    mortar = np.maximum(T.smoothstep(0.07, 0.02, np.minimum(bx, 1 - bx) * blen), T.smoothstep(0.08, 0.02, np.minimum(by, 1 - by) * course))
    erode = T.smoothstep(0.0, 1.5, T.fbm(w, 141, beta=2.0, min_period=4))
    hgt = 0.05 * (1 - mortar) * (1 - 0.6 * erode) + 0.015 * grain(w, h, 142)
    tone = T.normalize01(T.fbm(w, 143, beta=0.6, min_period=24, max_period=60))
    col = lin("#94643F") * (0.78 + 0.35 * tone)[..., None] * (1 - 0.4 * mortar)[..., None]
    col = col * (1 + 0.12 * grain(w, h, 144))[..., None]
    return T.linear_to_srgb(col), normals(hgt.astype(np.float32), ppx)


def timber(w, h, spt, seed, base="#8A8174", crack_k=0.5):
    ppx = w / spt[0]
    g = T.fbm(w, seed, beta=2.0, min_period=2, aniso=(14.0, 1.0))[:h]
    cracks = T.smoothstep(1.7, 2.5, np.abs(T.fbm(w, seed + 1, beta=2.2, min_period=3, aniso=(22.0, 1.0))[:h]))
    knots = T.smoothstep(2.2, 2.8, T.fbm(w, seed + 2, beta=2.8, min_period=10)[:h])
    shade = 1.0 + 0.16 * g - crack_k * cracks - 0.25 * knots
    col = lin(base)[None, None, :] * shade[..., None]
    hgt = 0.015 * g - 0.04 * cracks
    return col, hgt, ppx


def wood(w, h, spt):
    col, hgt, ppx = timber(w, h, spt, 151)
    return T.linear_to_srgb(col), normals(hgt.astype(np.float32), ppx)


def planks(w, h, spt):
    col, hgt, ppx = timber(w, h, spt, 161, base="#626446", crack_k=0.3)
    yy = np.arange(h)[:, None] / h
    seam = T.smoothstep(0.03, 0.0, np.minimum(np.abs(yy - 0.5), np.minimum(yy, 1 - yy)))
    paint_wear = T.smoothstep(0.6, 1.6, T.fbm(w, 162, beta=2.0, min_period=4)[:h])
    bare = lin("#8A7F6E")[None, None, :] * np.ones_like(col)
    col = col * (1 - paint_wear[..., None]) + bare * paint_wear[..., None]
    col = col * (1 - 0.5 * seam)[..., None]
    # a faded stencil band (unreadable blocks, not text)
    xx = np.arange(w)[None, :] / w
    stencil = ((np.floor(xx * 64) % 3 != 0) & (np.abs(yy - 0.28) < 0.06) & (xx % 0.5 < 0.22)).astype(np.float32)
    col = col * (1 - 0.35 * stencil[..., None]) + lin("#C9C2A8") * 0.35 * stencil[..., None]
    hgt = hgt - 0.03 * seam
    return T.linear_to_srgb(col), normals(hgt.astype(np.float32), ppx)


def rubber(w, h, spt):
    ppx = w / spt[0]
    yy, xx = np.mgrid[0:h, 0:w]
    u = xx / ppx
    v = yy / h
    lug = ((u * 2.2 + np.where(v < 0.5, 0.0, 0.5)) % 1.0 < 0.55) & (np.abs(v - 0.5) > 0.06) & (np.abs(v - 0.5) < 0.42)
    hgt = 0.04 * lug.astype(np.float32)
    col = lin("#2E2B28") * (0.9 + 0.15 * lug + 0.08 * grain(w, h, 171))[..., None]
    dust = T.smoothstep(0.3, 1.5, T.fbm(w, 172, beta=2.0, min_period=8)[:h])
    col = col * (1 - 0.22 * dust[..., None]) + lin("#9C6A48") * 0.22 * dust[..., None]
    return T.linear_to_srgb(col), normals(hgt.astype(np.float32), ppx)


def char(w, h, spt):
    col, hgt, ppx = timber(w, h, spt, 181, base="#2A2420", crack_k=0.6)
    ember = T.smoothstep(1.6, 2.4, T.fbm(w, 182, beta=2.0, min_period=3, aniso=(6.0, 1.0))[:h])
    ash = T.smoothstep(0.4, 1.6, T.fbm(w, 183, beta=2.2, min_period=6)[:h])
    col = col * (1 - 0.5 * ash[..., None]) + lin("#6E6660") * 0.5 * ash[..., None]
    col = col + lin("#3A2012") * 0.3 * ember[..., None]
    return T.linear_to_srgb(col), normals((hgt * 1.5).astype(np.float32), ppx)


def drum(w, h, spt, paint="#5B6344", seed=191, rust_k=0.45):
    ppx = w / spt[0]
    src = T.recolor(cc0("green_metal_rust", "diff", w), paint, contrast=1.2, chroma_keep=0.35, flatten_sigma=w / 6)[:h]
    yy = np.arange(h)[:, None] / h
    rib = np.exp(-((yy - 0.33) / 0.025) ** 2) + np.exp(-((yy - 0.67) / 0.025) ** 2)
    rim = T.smoothstep(0.05, 0.0, np.minimum(yy, 1 - yy))
    rust = T.smoothstep(0.2, 1.4, T.fbm(w, seed, beta=2.3, min_period=5)[:h]) * (0.5 + 0.5 * rim + 0.3 * rib)
    rustc = lin("#6B3A22") * (0.7 + 0.5 * T.normalize01(grain(w, h, seed + 1)))[..., None]
    col = T.srgb_to_linear(src) * (1 - rust_k * rust[..., None]) + rustc * rust_k * rust[..., None]
    dust = T.smoothstep(0.55, 1.0, yy) * 0.35 + 0.15 * T.smoothstep(0.3, 1.6, T.fbm(w, seed + 2, beta=2.0, min_period=10)[:h])
    col = col * (1 - dust[..., None]) + lin("#B98356") * dust[..., None]
    hgt = 0.05 * rib + 0.02 * rim - 0.01 * rust
    return T.linear_to_srgb(col), normals(hgt.astype(np.float32), ppx)


def drum2(w, h, spt):
    return drum(w, h, spt, paint="#7A3E2C", seed=201, rust_k=0.6)


def sheet(w, h, spt):
    ppx = w / spt[0]
    yy, xx = np.mgrid[0:h, 0:w] / ppx
    period = 0.375
    corr = 0.06 * np.sin(2 * np.pi * xx / period)
    rust = T.smoothstep(-0.4, 1.1, T.fbm(w, 211, beta=2.1, min_period=4))
    zinc = lin("#8B8A84") * (0.8 + 0.3 * T.normalize01(grain(w, h, 212)))[..., None]
    rustc = lin("#7A4526") * (0.7 + 0.6 * T.normalize01(T.fbm(w, 213, beta=1.6, min_period=3)))[..., None]
    col = zinc * (1 - rust[..., None]) + rustc * rust[..., None]
    streak = T.smoothstep(0.6, 2.0, T.blur_aniso(T.fbm(w, 214, beta=1.6, min_period=3), 0.5, 10.0))
    col = col * (1 - 0.25 * streak[..., None])
    col = col * (0.85 + 0.15 * np.cos(2 * np.pi * xx / period))[..., None]
    return T.linear_to_srgb(col), normals(corr.astype(np.float32), ppx)


def sand(w, h, spt):
    # a crop of the terrain's own sand tile (48 studs per 1024 px), so props
    # sit in drifts of the same sand
    tile = T.load(os.path.join(TERRAIN, "Sand", "Sand_color.png"))[..., :3]
    tn = T.decode_normal(T.load(os.path.join(TERRAIN, "Sand", "Sand_normal.png"))[..., :3])
    return tile[:h, :w].astype(np.float32), T.scale_normal(tn[:h, :w], 0.7).astype(np.float32)


def steel(w, h, spt):
    col = T.recolor(cc0("green_metal_rust", "diff", w), "#7C7D78", contrast=1.1, chroma_keep=0.1, flatten_sigma=w / 6)
    rust = T.smoothstep(0.8, 1.8, T.fbm(w, 221, beta=2.3, min_period=5))
    col = T.srgb_to_linear(col) * (1 - 0.5 * rust[..., None]) + lin("#6B3A22") * 0.5 * rust[..., None]
    nor = T.scale_normal(T.decode_normal(cc0("green_metal_rust", "nor_gl", w)), 0.5)
    return T.linear_to_srgb(col), nor


# ------------------------------------------------------------------ patches
def blob_alpha(w, h, seed, radius=0.42, rough=0.09, soft=0.06):
    yy, xx = np.mgrid[0:h, 0:w]
    ang = np.arctan2(yy - h / 2 + 0.5, xx - w / 2 + 0.5)
    r = np.hypot(yy - h / 2 + 0.5, xx - w / 2 + 0.5) / (w / 2)
    rng = np.random.default_rng(seed)
    wob = sum(rng.uniform(0.3, 1.0) * rough / k * np.sin(k * ang + rng.uniform(0, 6.28)) for k in (2, 3, 5, 7, 11))
    edge = T.fbm(w, seed, beta=1.8, min_period=3)[:h, :w] * rough * 0.5
    return T.smoothstep(radius + soft, radius - soft, r + wob + edge), r


def gravel(w, h, spt):
    ppx = w / spt[0]
    a, r = blob_alpha(w, h, 301, radius=0.74, rough=0.14, soft=0.1)
    base = T.recolor(cc0("gravelly_sand", "diff", w), "#A76B44", contrast=1.2, chroma_keep=0.3, flatten_sigma=w / 6)
    ph, pc, pt = T.scatter_stamps(w, 900, 302, 1.2, 4.0, mask=(0.25 + 0.75 * a).astype(np.float32))
    dark, light = lin("#5C3A2A"), lin("#C49A76")
    pcol = dark[None, None, :] + (light - dark)[None, None, :] * (pt ** 1.3)[..., None]
    pcol = pcol * (0.75 + 0.35 * ph)[..., None]
    col = T.srgb_to_linear(base) * (1 - pc[..., None]) + pcol * pc[..., None]
    alpha = np.clip(np.maximum(a * 0.9, pc * T.smoothstep(0.98, 0.7, r)), 0, 1)
    return T.linear_to_srgb(col), alpha.astype(np.float32), normals((ph * 0.12).astype(np.float32), ppx)


def scorch(w, h, spt):
    ppx = w / spt[0]
    a, r = blob_alpha(w, h, 311, radius=0.7, rough=0.12, soft=0.2)
    yy, xx = np.mgrid[0:h, 0:w]
    ang = np.arctan2(yy - h / 2, xx - w / 2)
    rays = 0.5 + 0.5 * np.sin(ang * 9 + 2 * np.sin(ang * 4))
    soot = lin("#231C18") * (0.8 + 0.4 * T.normalize01(grain(w, h, 312)))[..., None]
    ash = T.smoothstep(0.5, 1.8, T.fbm(w, 313, beta=2.0, min_period=4))
    col = soot * (1 - 0.5 * ash[..., None]) + lin("#5F5650") * 0.5 * ash[..., None]
    alpha = a * (0.5 + 0.45 * T.smoothstep(0.8, 0.15, r)) * (0.7 + 0.3 * rays)
    return T.linear_to_srgb(col), np.clip(alpha, 0, 1).astype(np.float32), flat_normal(h, w)


def stubble(w, h, spt):
    ppx = w / spt[0]
    a_blob, r = blob_alpha(w, h, 321, radius=0.7, rough=0.3, soft=0.2)
    a_blob = a_blob * T.smoothstep(-0.6, 0.4, T.fbm(w, 324, beta=2.0, min_period=6)[:h, :w])
    rng = np.random.default_rng(322)
    cov = np.zeros((h * 2, w * 2), np.float32)
    colacc = np.zeros((h * 2, w * 2, 3), np.float32)
    straws = [lin(c) for c in ("#A88B5E", "#B89B6A", "#96784E", "#7E6A48", "#C0A474")]
    for _ in range(7000):
        cx, cy = rng.uniform(0, w * 2), rng.uniform(0, h * 2)
        if a_blob[int(cy / 2) % h, int(cx / 2) % w] < rng.random() * 0.9:
            continue
        ang = rng.uniform(0, math.pi)
        ln = rng.uniform(3, 9)
        c = straws[rng.integers(len(straws))] * rng.uniform(0.7, 1.1)
        for t in np.linspace(-ln / 2, ln / 2, int(ln * 1.5) + 2):
            x = int(cx + math.cos(ang) * t) % (w * 2)
            y = int(cy + math.sin(ang) * t) % (h * 2)
            cov[y, x] = 1.0
            colacc[y, x] = c
    cov_s = cov.reshape(h, 2, w, 2).mean(axis=(1, 3))
    col = colacc.reshape(h, 2, w, 2, 3).sum(axis=(1, 3)) / np.maximum(cov.reshape(h, 2, w, 2).sum(axis=(1, 3)), 1e-6)[..., None]
    col = np.where(cov_s[..., None] > 0, col, lin("#B08E62"))
    base_a = a_blob * 0.12 * (0.6 + 0.4 * T.normalize01(grain(w, h, 323)))
    alpha = np.clip(np.maximum(base_a, cov_s * 0.95), 0, 1)
    col = col * (1 - 0.25 * (1 - cov_s))[..., None]
    col = dilate(T.linear_to_srgb(col).astype(np.float32), alpha > 0.02)
    return col, alpha.astype(np.float32), normals((cov_s * 0.03).astype(np.float32), ppx)


def stain(w, h, spt):
    a, r = blob_alpha(w, h, 331, radius=0.66, rough=0.32, soft=0.25)
    tone = T.normalize01(T.fbm(w, 332, beta=2.2, min_period=8))
    col = lin("#8A5A3C") * (0.8 + 0.3 * tone)[..., None]
    alpha = a * np.clip(0.1 + 0.45 * tone, 0, 1) * T.smoothstep(-0.8, 0.6, T.fbm(w, 333, beta=1.8, min_period=5))
    return T.linear_to_srgb(col), np.clip(alpha, 0, 1).astype(np.float32), flat_normal(h, w)


def trample(w, h, spt):
    ppx = w / spt[0]
    yy = (np.arange(h)[:, None] + 0.5) / h * spt[1] - spt[1] / 2
    band = T.smoothstep(3.0, 1.6, np.abs(yy + 0.3 * square_noise(w, h, 341, beta=3.0, min_period=100)))
    band = np.broadcast_to(band, (h, w))
    rng = np.random.default_rng(342)
    prints = np.zeros((h, w), np.float32)
    yy2, xx2 = np.mgrid[0:h, 0:w]
    for _ in range(420):
        cx, cy = rng.uniform(0, w), rng.uniform(h * 0.2, h * 0.8)
        ang = rng.uniform(-0.35, 0.35) + (0 if rng.random() < 0.5 else math.pi)
        rx, ry = 0.55 * ppx, 0.22 * ppx
        dxp = (xx2 - cx + w / 2) % w - w / 2
        u = dxp * math.cos(ang) + (yy2 - cy) * math.sin(ang)
        v = -dxp * math.sin(ang) + (yy2 - cy) * math.cos(ang)
        d2 = (u / rx) ** 2 + (v / ry) ** 2
        prints = np.maximum(prints, T.smoothstep(1.0, 0.6, d2) * rng.uniform(0.5, 1.0))
    scuff = T.smoothstep(-0.2, 1.2, square_noise(w, h, 343, beta=2.0, min_period=6))
    col = lin("#A8714A") * (0.85 + 0.2 * T.normalize01(square_noise(w, h, 344, beta=1.5, min_period=3, max_period=30)))[..., None]
    col = col * (1 - 0.3 * prints)[..., None]
    alpha = band * np.clip(0.08 + 0.22 * scuff + 0.35 * prints, 0, 1) * T.smoothstep(-0.9, 0.3, square_noise(w, h, 345, beta=2.4, min_period=40))
    hgt = -0.03 * prints + 0.01 * scuff
    return T.linear_to_srgb(col), alpha.astype(np.float32), normals(hgt.astype(np.float32), ppx)


def wire(w, h, spt):
    """Concertina: loops seen around the coil. U along the coil (16 studs),
    V once around it; each loop is a slanted sinusoid across V."""
    ppu = w / spt[0]
    yy, xx = np.mgrid[0:h, 0:w]
    v = yy / h  # 0..1 around
    u = xx / ppu  # studs along
    pitch = 0.9  # studs between loops of one helix (open, like a deployed coil)
    cov = np.zeros((h, w), np.float32)
    for k in range(2):  # two interleaved helices, half a pitch apart
        phase = (u - 0.45 * np.sin(2 * np.pi * v) - k * pitch / 2) / pitch
        d = np.abs(phase - np.round(phase)) * pitch * ppu  # px from the nearest loop
        cov = np.maximum(cov, T.smoothstep(1.6, 0.5, d))
    rng = np.random.default_rng(351)
    barbs = np.zeros((h, w), np.float32)
    for _ in range(500):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        r = 1.6
        dx = (xx - cx + w / 2) % w - w / 2
        dy = (yy - cy + h / 2) % h - h / 2
        barbs = np.maximum(barbs, T.smoothstep(r, r * 0.4, np.hypot(dx * 0.6, dy * 1.4)) * cov)
    alpha = np.clip(cov * 0.8 + barbs * 0.4, 0, 1)
    # dark galvanised wire, lighter where the loop faces up (the sun)
    col = lin("#3E3D3A") * (0.75 + 0.45 * (0.5 + 0.5 * np.cos(2 * np.pi * v)))[..., None]
    col = dilate(T.linear_to_srgb(col).astype(np.float32), alpha > 0.02)
    return col, alpha.astype(np.float32), flat_normal(h, w)


# ------------------------------------------------------------------ assembly
def dilate(img, valid, steps=10):
    img = img.copy()
    filled = valid.copy()
    for _ in range(steps):
        if filled.all():
            break
        acc = np.zeros_like(img)
        cnt = np.zeros(filled.shape, dtype=np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(np.roll(filled, dy, 0), dx, 1)
            acc += np.where(sh[..., None], np.roll(np.roll(img, dy, 0), dx, 1), 0)
            cnt += sh
        grow = (~filled) & (cnt > 0)
        img[grow] = acc[grow] / cnt[grow][:, None]
        filled |= grow
    if not filled.all() and filled.any():
        img[~filled] = img[filled].mean(axis=0)
    return img


def shrink(img, alpha=None):
    h, w = img.shape[:2]
    blk = img.reshape(h // 2, 2, w // 2, 2, -1)
    if alpha is None:
        return T.linear_to_srgb(T.srgb_to_linear(blk).mean(axis=(1, 3)))
    a = alpha.reshape(h // 2, 2, w // 2, 2)
    asum = a.sum(axis=(1, 3))
    lin_ = T.srgb_to_linear(blk)
    wc = (lin_ * a[..., None]).sum(axis=(1, 3))
    plain = lin_.mean(axis=(1, 3))
    col = np.where(asum[..., None] > 1e-4, wc / np.maximum(asum, 1e-9)[..., None], plain)
    return T.linear_to_srgb(col), asum / 4


def shrink_normal(n, factor):
    h, w = n.shape[:2]
    m = n.reshape(h // factor, factor, w // factor, factor, 3).mean(axis=(1, 3))
    return m / np.linalg.norm(m, axis=-1, keepdims=True)


def build_props():
    size = (1024, 1024)
    colour = np.zeros(size + (3,), np.float32)
    colour[...] = T.hex_rgb("#9A7A5A")
    normal = np.zeros(size + (3,), np.float32)
    normal[..., 2] = 1
    for name, ((x, y, w, h), spt) in PROPS.items():
        c, n = globals()[name](w, h, spt)
        colour[y:y + h, x:x + w] = c[..., :3]
        normal[y:y + h, x:x + w] = n
        print(f"props {name:9s} ({x},{y},{w},{h}) mean {T.mean_srgb(c)}")
    col = shrink(colour)
    T.save(os.path.join(OUT, "ConflictProps_color.png"), col)
    T.save(os.path.join(OUT, "ConflictProps_normal.png"), T.encode_normal(shrink_normal(normal, 2)))
    T.save(os.path.join(PREVIEW, "ConflictProps_atlas.png"), col)
    return {k: [v // 2 for v in r[0]] for k, r in PROPS.items()}, {k: list(r[1]) for k, r in PROPS.items()}, col.shape[1], col.shape[0]


def build_patches():
    size = (512, 1024)
    colour = np.zeros(size + (3,), np.float32)
    colour[...] = T.hex_rgb("#A8714A")
    alpha = np.zeros(size, np.float32)
    normal = np.zeros(size + (3,), np.float32)
    normal[..., 2] = 1
    for name, ((x, y, w, h), spt) in PATCHES.items():
        c, a, n = globals()[name](w, h, spt)
        c = dilate(c.astype(np.float32), a > 0.02)
        colour[y:y + h, x:x + w] = c[..., :3]
        alpha[y:y + h, x:x + w] = a
        normal[y:y + h, x:x + w] = n
        print(f"patch {name:9s} ({x},{y},{w},{h}) alpha mean {a.mean():.2f}")
    col, a = shrink(colour, alpha)
    a = np.maximum(a, ALPHA_FLOOR)
    rgba = np.concatenate([col, a[..., None]], axis=-1).astype(np.float32)
    T.save(os.path.join(OUT, "GroundPatches_color.png"), rgba)
    T.save(os.path.join(OUT, "GroundPatches_normal.png"), T.encode_normal(shrink_normal(normal, 4)))
    hh, ww = a.shape
    yy, xx = np.mgrid[0:hh, 0:ww]
    check = np.where(((yy // 16 + xx // 16) % 2)[..., None] == 0, 0.25, 0.4).astype(np.float32)
    T.save(os.path.join(PREVIEW, "GroundPatches_atlas.png"), col * a[..., None] + check * (1 - a[..., None]))
    return {k: [v // 2 for v in r[0]] for k, r in PATCHES.items()}, {k: list(r[1]) for k, r in PATCHES.items()}, ww, hh


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PREVIEW, exist_ok=True)
    pr, ps, pw, ph = build_props()
    gr, gs, gw, gh = build_patches()
    with open(os.path.join(OUT, "atlases.json"), "w") as fh:
        json.dump({"ConflictProps": {"size": [pw, ph], "regions": pr, "studs": ps},
                   "GroundPatches": {"size": [gw, gh], "regions": gr, "studs": gs}}, fh, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
