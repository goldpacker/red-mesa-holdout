"""Generates the HUD kit textures (LOOK-2, FACELIFT_PLAN Phase 7).

    tools/ui/py.sh tools/ui/ui_kit_textures.py      # writes assets/ui/kit/*.png + atlas.json

One 512x512 atlas plus three small tiles, all procedural (numpy only, no
external inputs), deterministic (same seed, same bytes):

  kit_atlas.png   512x512 RGBA atlas. Cells (pixel rects in atlas.json):
                    radar_face    phosphor radar screen in a worn OD bezel
                    radar_sweep   white sweep line + fading tail (tinted)
                    radar_dead    hatched 90 deg rear dead-zone sector (tinted)
                    panel         9-slice worn olive metal frame + dark fill
                    button        9-slice raised olive plate
                    brackets      9-slice corner brackets (white, tinted)
                    trough        9-slice inset bar trough
                    fill          bar fill gradient (white, tinted)
                    blip          radar blip glow (white, tinted)
                    chevron       off-screen threat chevron (white, tinted)
                    wedge         damage-direction arc (white, tinted)
  kit_grain.png   128x128 tile: scanlines, grain, grime, scratches (overlay)
  kit_hazard.png  64x64 tile: worn diagonal hazard stripes (white/dark, tinted)
  kit_strip.png   64x8 tile: stencilled paint stripe with stencil bridges

9-slice cells are authored at display size (SliceScale 1): edges are uniform
along their length so stretching never smears detail; wear sits in the
corners and in the tiled grain overlay. White cells carry their shape in
alpha and a dark outline in RGB so ImageColor3 tints them.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True  # keep tools/ui free of __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
from look_textures import periodic_noise, smoothstep, write_png  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "ui" / "kit"

# ART_BIBLE §2 palette (0..1)
OD = np.array([79, 82, 52]) / 255.0  # olive drab
OD_WORN = np.array([107, 107, 69]) / 255.0
STEEL = np.array([122, 123, 120]) / 255.0
FILL = np.array([24, 27, 17]) / 255.0  # panel fill (HUD panel #10120C, a touch lighter/olive)
AMBER = np.array([255, 178, 36]) / 255.0


# ------------------------------------------------------------------ helpers
def canvas(h: int, w: int) -> np.ndarray:
    return np.zeros((h, w, 4))


def over(dst: np.ndarray, rgb, alpha: np.ndarray) -> None:
    """Composites colour `rgb` (3-vector or HxWx3) with coverage `alpha` over dst (straight alpha)."""
    rgb = np.broadcast_to(np.asarray(rgb, dtype=float), dst.shape[:2] + (3,))
    a_src = np.clip(alpha, 0.0, 1.0)
    a_dst = dst[..., 3]
    a_out = a_src + a_dst * (1.0 - a_src)
    safe = np.where(a_out > 1e-6, a_out, 1.0)
    dst[..., :3] = (rgb * a_src[..., None] + dst[..., :3] * (a_dst * (1.0 - a_src))[..., None]) / safe[..., None]
    dst[..., 3] = a_out


def grid(h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    y, x = np.mgrid[0:h, 0:w]
    return y + 0.5, x + 0.5


def edge_frame(h: int, w: int) -> tuple[np.ndarray, np.ndarray]:
    """Distance (px) to the nearest edge and which edge: 0 top, 1 left, 2 bottom, 3 right."""
    y, x = grid(h, w)
    stack = np.stack([y, x, h - y, w - x])
    return stack.min(axis=0), stack.argmin(axis=0)


def band(d: np.ndarray, a: float, b: float, aa: float = 0.5) -> np.ndarray:
    """Coverage of the band a <= d < b with a soft half-pixel edge."""
    return smoothstep(a - aa, a + aa, d) * (1.0 - smoothstep(b - aa, b + aa, d))


def disc(y, x, cy, cx, r, aa=0.75):
    dist = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    return 1.0 - smoothstep(r - aa, r + aa, dist)


def seg_dist(y, x, y0, x0, y1, x1):
    """Distance from each pixel to the segment (x0,y0)-(x1,y1)."""
    px, py = x - x0, y - y0
    dx, dy = x1 - x0, y1 - y0
    t = np.clip((px * dx + py * dy) / (dx * dx + dy * dy), 0.0, 1.0)
    return np.sqrt((px - t * dx) ** 2 + (py - t * dy) ** 2)


def rivet(img, y, x, cy, cx, r=1.7):
    over(img, STEEL * 0.45, disc(y, x, cy, cx, r + 0.6))
    over(img, STEEL, disc(y, x, cy, cx, r))
    over(img, np.array([0.85, 0.85, 0.8]), disc(y, x, cy - 0.6, cx - 0.6, r * 0.45) * 0.8)


# ------------------------------------------------------------------ 9-slices
def panel(w: int = 64, h: int = 64, frame: int = 6, seed: int = 41) -> np.ndarray:
    """Worn olive-metal frame (outline, bevelled band, groove) around a dark
    translucent fill. Corners: rivets and paint chipped to bare steel."""
    img = canvas(h, w)
    d, side = edge_frame(h, w)
    y, x = grid(h, w)
    lit = np.select([side == 0, side == 1, side == 2, side == 3], [0.17, 0.08, -0.13, -0.07])
    # fill with a soft shadow under the top frame edge
    shade = np.where(side == 0, 1.0 - smoothstep(frame + 2, frame + 9, d), 0.0)
    fill_rgb = FILL[None, None, :] * (1.0 - 0.35 * shade[..., None])
    over(img, fill_rgb, band(d, frame + 2, 1e9) * (0.80 + 0.1 * shade))
    # frame band: bevel strongest at the outer edge
    t = np.clip((d - 1) / frame, 0, 1)
    band_rgb = OD[None, None, :] + (lit * (1.25 - 1.1 * t))[..., None] * 0.9
    band_rgb = np.where((t > 0.8)[..., None], band_rgb * 0.82, band_rgb)  # slope into the groove
    over(img, np.clip(band_rgb, 0, 1), band(d, 1, 1 + frame))
    # groove + lit lower lip
    over(img, np.array([0.05, 0.055, 0.035]), band(d, 1 + frame, 2 + frame) * 0.95)
    lip = np.where((side == 2) | (side == 3), 0.26, 0.11)
    over(img, np.stack([lip, lip * 1.05, lip * 0.7], -1), band(d, 2 + frame, 3 + frame) * 0.8)
    # outline
    over(img, np.array([0.03, 0.035, 0.02]), band(d, -1, 1) * 0.92)
    # corner wear: paint chipped to bare steel, heavier toward the outer corner
    rng = np.random.default_rng(seed)
    corner = 12
    in_corner = ((x < corner) | (x > w - corner)) & ((y < corner) | (y > h - corner))
    cx = np.where(x < w / 2, x, w - x)
    cy = np.where(y < h / 2, y, h - y)
    reach = 1.0 - np.clip(np.sqrt(cx**2 + cy**2) / (corner * 1.1), 0, 1)
    chip = rng.random((h, w)) * 0.55 + reach * 0.75
    chips = in_corner & (chip > 0.95) & (d >= 1) & (d < 1 + frame)
    over(img, STEEL * 0.95, chips.astype(float))
    for cy0 in (1 + frame / 2, h - 1 - frame / 2):
        for cx0 in (1 + frame / 2, w - 1 - frame / 2):
            rivet(img, y, x, cy0, cx0)
    return img


def button(w: int = 96, h: int = 40) -> np.ndarray:
    """Raised olive plate: outline, strong 3 px bevel, vertical-gradient face."""
    img = canvas(h, w)
    d, side = edge_frame(h, w)
    y, x = grid(h, w)
    v = y / h
    face = (np.array([0.30, 0.33, 0.20])[None, None, :] * (1 - v[..., None])
            + np.array([0.19, 0.21, 0.12])[None, None, :] * v[..., None])
    over(img, face, band(d, 1, 1e9) * 0.97)
    lit = np.select([side == 0, side == 1, side == 2, side == 3], [0.24, 0.12, -0.16, -0.10])
    t = np.clip((d - 1) / 3, 0, 1)
    over(img, np.clip(OD[None, None, :] + (lit * (1.2 - 0.8 * t))[..., None], 0, 1), band(d, 1, 4))
    over(img, np.array([0.03, 0.035, 0.02]), band(d, -1, 1) * 0.95)
    for cy0 in (7.5, h - 7.5):
        for cx0 in (7.5, w - 7.5):
            rivet(img, y, x, cy0, cx0, 1.6)
    return img


def brackets(n: int = 32, arm: float = 10.0, thick: float = 2.0) -> np.ndarray:
    """White L-brackets in the four corners with a dark outline; middle clear."""
    img = canvas(n, n)
    y, x = grid(n, n)
    cx = np.where(x < n / 2, x, n - x)
    cy = np.where(y < n / 2, y, n - y)
    lshape = ((cy < 1 + thick) & (cx < 1 + arm)) | ((cx < 1 + thick) & (cy < 1 + arm))
    lshape &= (cx >= 1) & (cy >= 1)
    outline = ((cy < 2 + thick) & (cx < 2 + arm)) | ((cx < 2 + thick) & (cy < 2 + arm))
    over(img, np.zeros(3), outline.astype(float) * 0.6)
    over(img, np.ones(3), lshape.astype(float))
    return img


def trough(w: int = 24, h: int = 14) -> np.ndarray:
    img = canvas(h, w)
    d, side = edge_frame(h, w)
    over(img, np.array([0.055, 0.06, 0.04]), band(d, 1, 1e9) * 0.9)
    over(img, np.zeros(3), (band(d, 1, 3) * (side == 0)) * 0.55)
    over(img, np.array([0.30, 0.31, 0.21]), (band(d, 1, 2) * (side == 2)) * 0.75)
    over(img, np.array([0.02, 0.02, 0.015]), band(d, -1, 1) * 0.95)
    return img


def fill(w: int = 8, h: int = 16) -> np.ndarray:
    y, _ = grid(h, w)
    v = (y - 0.5) / (h - 1)
    lum = 0.96 - 0.30 * v
    lum = np.where(y < 1, 1.0, lum)
    lum = np.where(y > h - 1, 0.58, lum)
    lum = np.where((y > 1) & (y < 3), lum + 0.03, lum)
    img = canvas(h, w)
    img[..., :3] = np.clip(lum, 0, 1)[..., None]
    img[..., 3] = 1.0
    return img


def blip(n: int = 24) -> np.ndarray:
    y, x = grid(n, n)
    r = np.sqrt((y - n / 2) ** 2 + (x - n / 2) ** 2)
    alpha = np.clip(np.exp(-((r / 5.2) ** 2)) * 0.75 + (1 - smoothstep(2.2, 3.4, r)), 0, 1)
    img = canvas(n, n)
    img[..., :3] = 1.0
    img[..., 3] = alpha
    return img


def chevron(n: int = 32) -> np.ndarray:
    """Upward chevron: white stroke with a dark outline."""
    y, x = grid(n, n)
    dist = np.minimum(seg_dist(y, x, 25, 5.5, 8, 16), seg_dist(y, x, 8, 16, 25, 26.5))
    img = canvas(n, n)
    over(img, np.zeros(3), (1 - smoothstep(4.0, 5.2, dist)) * 0.75)
    over(img, np.ones(3), 1 - smoothstep(2.4, 3.3, dist))
    return img


def wedge(w: int = 128, h: int = 40, radius: float = 150.0) -> np.ndarray:
    """Damage-direction arc: convex side up (outward), a notch pointing out."""
    y, x = grid(h, w)
    cy, cx = 12 + radius, w / 2
    r = np.sqrt((y - cy) ** 2 + (x - cx) ** 2)
    s = radius * np.arctan2(x - cx, cy - y)  # arc length from the middle
    span = w / 2 - 6
    prof = np.clip(1 - (s / span) ** 2, 0, 1)
    thick = 1.2 + 4.2 * prof
    dist = np.abs(r - radius)
    core = (1 - smoothstep(thick - 0.8, thick + 0.8, dist)) * smoothstep(0, 0.12, prof)
    glow = np.exp(-((dist / (thick + 5)) ** 2)) * 0.45 * prof
    # notch: small triangle on the outer side of the arc at the middle
    ty = cy - radius - thick  # top of the arc band at the middle
    tri = (y < ty + 0.5) & (y > ty - 7) & (np.abs(x - cx) < (y - (ty - 7)) * 0.9)
    alpha = np.clip(np.maximum(core, glow) + tri.astype(float) * 0.95, 0, 1)
    img = canvas(h, w)
    img[..., :3] = 1.0
    img[..., 3] = alpha
    return img


# ------------------------------------------------------------------ radar
def polar(n: int):
    y, x = grid(n, n)
    dy, dx = y - n / 2, x - n / 2
    r = np.sqrt(dx * dx + dy * dy) / (n / 2)  # 0 centre .. 1 rim
    phi = np.degrees(np.arctan2(dx, -dy))  # 0 = up, clockwise positive
    return r, phi, y, x


SCREEN = 0.925  # radius of the phosphor screen inside the bezel (fraction of the cell)


def radar_face(n: int = 256, seed: int = 61) -> np.ndarray:
    r, phi, y, x = polar(n)
    px = n / 2  # pixels per unit radius
    img = canvas(n, n)
    # phosphor screen
    base = np.array([0.045, 0.085, 0.04])[None, None, :] * (1.25 - 0.55 * r[..., None])
    noise = periodic_noise(n, n, seed, 1.2, 1.2) * 0.012
    over(img, np.clip(base + noise[..., None], 0, 1), (1 - smoothstep(SCREEN - 1 / px, SCREEN + 1 / px, r)) * 0.9)
    inside = 1 - smoothstep(SCREEN - 1.5 / px, SCREEN, r)
    # fine grid
    gx = np.abs(((x - n / 2) / 16.0 + 0.5) % 1.0 - 0.5) * 16
    gy = np.abs(((y - n / 2) / 16.0 + 0.5) % 1.0 - 0.5) * 16
    gline = np.maximum(1 - smoothstep(0.2, 0.9, gx), 1 - smoothstep(0.2, 0.9, gy))
    over(img, np.array([0.16, 0.25, 0.12]), gline * inside * 0.35)
    # range rings at 1/3 and 2/3 of the screen radius, plus the cross
    green = np.array([0.34, 0.46, 0.22])
    for k in (1 / 3, 2 / 3):
        ring = 1 - smoothstep(0.35, 1.1, np.abs(r - SCREEN * k) * px)
        over(img, green, ring * 0.75)
    cross = np.minimum(np.abs(x - n / 2), np.abs(y - n / 2))
    over(img, green, (1 - smoothstep(0.3, 1.0, cross)) * inside * 0.35)
    # bearing ticks every 10 deg (30 deg long) at the screen edge
    ang = (phi + 360.0) % 10.0
    near = np.minimum(ang, 10.0 - ang)  # degrees to the nearest tick
    long_tick = (np.abs(((phi + 360.0) % 30.0) - 15.0) > 13.9)
    tick_len = np.where(long_tick, 9.0, 4.5) / px
    arc_px = np.radians(near) * r * px
    tick = (1 - smoothstep(0.35, 1.0, arc_px)) * band(r * px, (SCREEN - tick_len) * px, SCREEN * px)
    over(img, np.array([0.52, 0.62, 0.32]), tick * 0.9)
    # forward marker (aim is always up): small amber caret at the top edge
    caret = (np.abs(x - n / 2) < (y - (n / 2 - SCREEN * px) - 1) * 0.6) & (y < n / 2 - SCREEN * px + 9)
    over(img, AMBER, caret.astype(float) * 0.95)
    # bezel: worn OD ring, lit from the top-left, with an outline
    lit = np.cos(np.radians(phi + 45.0))  # +1 toward the top-left
    bez_rgb = OD[None, None, :] + (0.10 * lit)[..., None]
    chip = periodic_noise(n, n, seed + 1, 1.5, 1.5)
    bez_rgb = np.where((chip > 1.9)[..., None], STEEL[None, None, :], bez_rgb)
    over(img, np.clip(bez_rgb, 0, 1), band(r * px, SCREEN * px, n / 2 - 1.0))
    over(img, np.array([0.03, 0.035, 0.02]), band(r * px, SCREEN * px - 0.5, SCREEN * px + 1.0) * 0.9)
    over(img, np.array([0.03, 0.035, 0.02]), band(r * px, n / 2 - 1.5, n / 2 + 0.2) * 0.9)
    # bolts on the bezel at 45/135/225/315 deg
    rb = (SCREEN + 1) / 2 * px
    for a in (45, 135, 225, 315):
        cx0 = n / 2 + np.sin(np.radians(a)) * rb
        cy0 = n / 2 - np.cos(np.radians(a)) * rb
        rivet(img, y, x, cy0, cx0, 2.0)
    # glass sheen, top-left
    sheen = np.exp(-(((x - n * 0.36) / (n * 0.22)) ** 2 + ((y - n * 0.30) / (n * 0.12)) ** 2))
    over(img, np.ones(3), sheen * inside * 0.07)
    return img


def radar_sweep(n: int = 256, trail: float = 75.0) -> np.ndarray:
    """Leading line straight up; tail counter-clockwise behind it (rotates clockwise)."""
    r, phi, y, x = polar(n)
    px = n / 2
    inside = 1 - smoothstep(SCREEN - 2.5 / px, SCREEN - 0.5 / px, r)
    behind = np.clip(-phi / trail, 0, 1)  # 0 at the line .. 1 at the end of the tail
    tail = np.where((phi <= 0) & (phi >= -trail), (1 - behind) ** 2.4 * 0.42, 0.0)
    line_d = np.abs(x - n / 2)
    line = (1 - smoothstep(0.4, 1.4, line_d)) * (y < n / 2)
    alpha = np.clip(np.maximum(tail, line * 0.95), 0, 1) * inside * smoothstep(0.02, 0.12, r)
    img = canvas(n, n)
    img[..., :3] = 1.0
    img[..., 3] = alpha
    return img


def radar_dead(n: int = 256) -> np.ndarray:
    """Rear 90 deg sector (centred straight down), diagonally hatched."""
    r, phi, y, x = polar(n)
    px = n / 2
    rear = np.abs(np.abs(phi) - 180.0)  # 0 straight down
    edge_arc = (45.0 - rear)  # degrees inside the sector
    inside = (1 - smoothstep(SCREEN - 2 / px, SCREEN - 0.5 / px, r)) * smoothstep(-0.8, 0.8, np.radians(edge_arc) * r * px)
    hatch = np.abs(((x + y) / 7.0) % 1.0 - 0.5) * 7.0
    lines = 1 - smoothstep(0.6, 1.4, hatch)
    border = (1 - smoothstep(0.4, 1.3, np.abs(np.radians(edge_arc)) * r * px)) * (r < SCREEN) * (r > 0.05)
    alpha = np.clip(inside * (0.14 + 0.36 * lines) + border * 0.9, 0, 1)
    img = canvas(n, n)
    img[..., :3] = 1.0
    img[..., 3] = alpha
    return img


# ------------------------------------------------------------------ tiles
def grain(n: int = 128, seed: int = 71) -> np.ndarray:
    """Overlay: scanlines, fine grain, grime blotches and a few scratches."""
    img = canvas(n, n)
    y, x = grid(n, n)
    rng = np.random.default_rng(seed)
    grime = periodic_noise(n, n, seed, 9.0, 9.0)
    over(img, np.array([0.02, 0.02, 0.01]), np.clip(grime - 0.4, 0, 2) * 0.09)
    over(img, np.zeros(3), ((np.floor(y) % 3) == 0).astype(float) * 0.085)
    fine = rng.standard_normal((n, n))
    over(img, np.ones(3), np.clip(fine - 1.2, 0, 2) * 0.045)
    over(img, np.zeros(3), np.clip(-fine - 1.2, 0, 2) * 0.06)
    for _ in range(9):  # scratches, wrapped so the tile stays seamless
        y0, x0 = rng.uniform(0, n, 2)
        ang = rng.uniform(-0.5, 0.5) + (np.pi / 2 if rng.random() < 0.3 else 0)
        length = rng.uniform(8, 30)
        y1, x1 = y0 + np.sin(ang) * length, x0 + np.cos(ang) * length
        for oy in (-n, 0, n):
            for ox in (-n, 0, n):
                dist = seg_dist(y, x, y0 + oy, x0 + ox, y1 + oy, x1 + ox)
                over(img, np.array([0.85, 0.85, 0.78]), (1 - smoothstep(0.2, 0.9, dist)) * rng.uniform(0.05, 0.11))
    return img


def hazard(n: int = 64, period: int = 32, seed: int = 81) -> np.ndarray:
    y, x = grid(n, n)
    v = ((x + y) % period) / period
    edge = np.minimum(np.abs(v - 0.5), np.minimum(v, 1 - v)) * period  # px to a stripe edge
    light = (v < 0.5).astype(float)
    aa = smoothstep(0.0, 0.9, edge)
    lum = np.where(light > 0.5, 0.5 + 0.5 * aa, 0.5 - 0.5 * aa)
    wear = periodic_noise(n, n, seed, 2.0, 2.0)
    lum = np.where((wear > 1.5) & (lum > 0.5), lum * 0.55, lum)  # paint worn off the light stripes
    img = canvas(n, n)
    img[..., 0] = img[..., 1] = img[..., 2] = np.clip(0.07 + 0.93 * lum, 0, 1)
    img[..., 3] = 1.0
    return img


def strip(w: int = 64, h: int = 8, seed: int = 91) -> np.ndarray:
    """Stencilled paint stripe (white, tinted): 4 px bar with stencil bridges every 16 px."""
    y, x = grid(h, w)
    bar = band(y, 2, 6)
    bridge = 1 - band((x % 16), 13, 15)
    wear = periodic_noise(h, w, seed, 0.8, 0.8)
    alpha = bar * bridge * np.where(wear > 1.6, 0.35, 0.92)
    img = canvas(h, w)
    img[..., :3] = 1.0
    img[..., 3] = alpha
    return img


# ------------------------------------------------------------------ atlas
# name -> (x, y, image fn, 9-slice centre (l, t, r, b) in cell pixels or None)
CELLS = {
    "radar_face": (0, 0, radar_face, None),
    "radar_sweep": (256, 0, radar_sweep, None),
    "radar_dead": (0, 256, radar_dead, None),
    "panel": (260, 260, panel, (12, 12, 52, 52)),
    "button": (332, 260, button, (12, 12, 84, 28)),
    "brackets": (436, 260, brackets, (12, 12, 20, 20)),
    "trough": (476, 260, trough, (5, 5, 19, 9)),
    "fill": (476, 280, fill, (0, 3, 8, 13)),
    "blip": (440, 300, blip, None),
    "chevron": (476, 300, chevron, None),
    "wedge": (260, 336, wedge, None),
}
ATLAS = 512
TILES = {"kit_grain": grain, "kit_hazard": hazard, "kit_strip": strip}


def build_atlas() -> tuple[np.ndarray, dict]:
    atlas = canvas(ATLAS, ATLAS)
    rects = {}
    for name, (x0, y0, fn, center) in CELLS.items():
        cell = fn()
        h, w = cell.shape[:2]
        if x0 + w > ATLAS or y0 + h > ATLAS:
            raise ValueError(f"{name} does not fit at {x0},{y0}")
        if atlas[y0:y0 + h, x0:x0 + w, 3].max() > 0:
            raise ValueError(f"{name} overlaps another cell")
        atlas[y0:y0 + h, x0:x0 + w] = cell
        rects[name] = {"offset": [x0, y0], "size": [w, h]}
        if center:
            rects[name]["slice"] = list(center)
    return atlas, rects


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    atlas, rects = build_atlas()
    write_png(OUT / "kit_atlas.png", atlas)
    (OUT / "atlas.json").write_text(json.dumps({"size": [ATLAS, ATLAS], "cells": rects}, indent=1, sort_keys=True) + "\n")
    print(f"wrote assets/ui/kit/kit_atlas.png {ATLAS}x{ATLAS}, {len(rects)} cells")
    for name, fn in TILES.items():
        img = fn()
        write_png(OUT / f"{name}.png", img)
        print(f"wrote assets/ui/kit/{name}.png {img.shape[1]}x{img.shape[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
