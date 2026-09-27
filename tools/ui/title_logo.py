"""Title logo: stencilled, worn metal "RED MESA / HOLDOUT" (LOOK-4).

    tools/ui/py.sh tools/ui/title_logo.py      # writes assets/ui/art/title_logo.png

Everything is procedural and original (GAME_SPEC §17): the letterforms are
a blocky military stencil drawn here from boxes, bars and 45° chamfers as
signed distance fields (every counter is broken by a stencil bridge), then
treated as bevelled steel letters:

  - a flat 45° bevel from the distance field, lit by a warm low key from
    the upper left (the title is a sunset scene) with a cool sky fill;
  - paint (worn amber on RED MESA, bone on HOLDOUT) chipped to bare
    brushed steel along the edges and in scattered spots, scratched, with
    dust gathered at the foot of every letter and grime in the bevels;
  - a dark outline and a soft drop shadow so it reads on any backdrop.

Rendered 3x supersampled and box-filtered to 1024x256 RGBA (straight
alpha). Pure numpy (Blender's bundled Python): deterministic.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from look_textures import periodic_noise, smoothstep, write_png  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "ui" / "art"

W, H = 1024, 256  # final texture
SS = 3  # supersampling
S_ = 0.21  # stroke (cap height = 1)
G_ = 0.055  # stencil bridge gap
C_ = 0.16  # corner chamfer
TRACK = 0.12  # letter spacing
SPACE = 0.34

AMBER_PAINT = np.array([0.93, 0.63, 0.16])
BONE_PAINT = np.array([0.86, 0.80, 0.66])
STEEL = np.array([0.50, 0.51, 0.50])
DUST = np.array([0.74, 0.60, 0.44])


# ------------------------------------------------------------------ SDF primitives (glyph units, y up)
def box(u, v, x0, y0, x1, y1):
    cx, cy, hx, hy = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    dx, dy = np.abs(u - cx) - hx, np.abs(v - cy) - hy
    outside = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))
    return outside + np.minimum(np.maximum(dx, dy), 0)


def chbox(u, v, x0, y0, x1, y1, tl=0.0, tr=0.0, bl=0.0, br=0.0):
    """Box with 45° chamfers of the given leg length per corner."""
    d = box(u, v, x0, y0, x1, y1)
    r2 = np.sqrt(2)
    for c, a in ((tl, (u - x0) + (y1 - v)), (tr, (x1 - u) + (y1 - v)), (bl, (u - x0) + (v - y0)), (br, (x1 - u) + (v - y0))):
        if c > 0:
            d = np.maximum(d, (c - a) / r2)
    return d


def seg(u, v, ax, ay, bx, by, hw):
    """Bar of half-width hw from A to B (square ends)."""
    dx, dy = bx - ax, by - ay
    length = np.hypot(dx, dy)
    tx, ty = dx / length, dy / length
    pu, pv = u - ax, v - ay
    along = pu * tx + pv * ty - length / 2
    across = -pu * ty + pv * tx
    return box(along, across, -length / 2, -hw, length / 2, hw)


def union(*ds):
    return np.minimum.reduce(ds)


def cut(d, *cuts):
    for c in cuts:
        d = np.maximum(d, -c)
    return d


def clip(d, u, v, w, tl=0.0, tr=0.0, bl=0.0, br=0.0):
    return np.maximum(d, chbox(u, v, 0, 0, w, 1, tl, tr, bl, br))


# ------------------------------------------------------------------ glyphs: name -> (width, sdf(u, v))
def g_H(u, v, w=0.78):
    s, g = S_, G_
    d = union(box(u, v, 0, 0, s, 1), box(u, v, w - s, 0, w, 1), box(u, v, s + g, 0.5 - s / 2, w - s - g, 0.5 + s / 2))
    return clip(d, u, v, w, C_, C_, C_, C_)


def g_E(u, v, w=0.66):
    s, g = S_, G_
    d = union(box(u, v, 0, 0, s, 1), box(u, v, s + g, 1 - s, w, 1), box(u, v, s + g, 0.5 - s / 2, w * 0.9, 0.5 + s / 2), box(u, v, s + g, 0, w, s))
    return clip(d, u, v, w, tl=C_, bl=C_)


def g_L(u, v, w=0.62):
    s, g = S_, G_
    d = union(box(u, v, 0, 0, s, 1), box(u, v, s + g, 0, w, s))
    return clip(d, u, v, w, tl=C_, bl=C_)


def g_T(u, v, w=0.72):
    s, g = S_, G_
    d = union(box(u, v, 0, 1 - s, w, 1), box(u, v, w / 2 - s / 2, 0, w / 2 + s / 2, 1 - s - g))
    return clip(d, u, v, w, tl=C_ * 0.6, tr=C_ * 0.6)


def g_O(u, v, w=0.78):
    s, g = S_, G_
    ring = cut(chbox(u, v, 0, 0, w, 1, C_ * 1.4, C_ * 1.4, C_ * 1.4, C_ * 1.4), chbox(u, v, s, s, w - s, 1 - s, C_ * 0.7, C_ * 0.7, C_ * 0.7, C_ * 0.7))
    return cut(ring, box(u, v, w / 2 - g / 2, -1, w / 2 + g / 2, 2))


def g_U(u, v, w=0.76):
    s, g = S_, G_
    ring = cut(chbox(u, v, 0, 0, w, 1, bl=C_ * 1.4, br=C_ * 1.4), chbox(u, v, s, s, w - s, 2, bl=C_ * 0.7, br=C_ * 0.7))
    return clip(cut(ring, box(u, v, w / 2 - g / 2, -1, w / 2 + g / 2, 2)), u, v, w, tl=C_ * 0.5, tr=C_ * 0.5)


def g_D(u, v, w=0.76):
    s, g = S_, G_
    bowl = cut(chbox(u, v, 0, 0, w, 1, tr=C_ * 1.8, br=C_ * 1.8), chbox(u, v, s, s, w - s, 1 - s, tr=C_ * 1.0, br=C_ * 1.0), box(u, v, -1, -1, s + g, 2))
    return clip(union(box(u, v, 0, 0, s, 1), bowl), u, v, w, tl=C_, bl=C_)


def g_R(u, v, w=0.76):
    s, g = S_, G_
    y0 = 0.42
    bowl = cut(chbox(u, v, 0, y0, w, 1, tr=C_ * 1.6, br=C_ * 0.7), chbox(u, v, s, y0 + s, w - s, 1 - s, tr=C_ * 0.8), box(u, v, -1, -1, s + g, 2))
    leg = seg(u, v, w * 0.46, y0 + s * 0.5, w - s * 0.62, -0.1, s * 0.54)
    leg = np.maximum(np.maximum(leg, -v), np.maximum(u - w, v - (y0 + s)))
    return clip(union(box(u, v, 0, 0, s, 1), bowl, leg), u, v, w, tl=C_, bl=C_)


def g_M(u, v, w=0.94):
    s, g = S_, G_
    left = seg(u, v, s * 0.5, 1.05, w / 2, 0.28, s * 0.5)
    right = seg(u, v, w - s * 0.5, 1.05, w / 2, 0.28, s * 0.5)
    vee = cut(np.maximum(union(left, right), v - 1), box(u, v, -1, -1, s + g, 2), box(u, v, w - s - g, -1, 2, 2), box(u, v, w / 2 - g / 2, -1, w / 2 + g / 2, 2))
    d = union(box(u, v, 0, 0, s, 1), box(u, v, w - s, 0, w, 1), vee)
    return clip(d, u, v, w, tl=C_, tr=C_)


def g_A(u, v, w=0.82):
    s, g = S_, G_
    top, bar = 0.38, 0.34
    outer = chbox(u, v, 0, 0, w, 1, tl=top, tr=top)
    inner = top - s * 0.41
    d = cut(
        outer,
        chbox(u, v, s, bar + s, w - s, 1 - s, tl=inner, tr=inner),
        box(u, v, s, -1, w - s, bar),
        box(u, v, s, bar - 0.01, s + g, bar + s + 0.01),
        box(u, v, w - s - g, bar - 0.01, w - s, bar + s + 0.01),
        box(u, v, w / 2 - g / 2, bar + s, w / 2 + g / 2, 2),
    )
    return d


def g_S(u, v, w=0.72):
    s = S_
    d = union(
        box(u, v, 0, 1 - s, w, 1),
        box(u, v, 0, 0.5 - s / 2, s, 1),
        chbox(u, v, 0, 0.5 - s / 2, w, 0.5 + s / 2, bl=C_ * 0.7, tr=C_ * 0.7),
        box(u, v, w - s, 0, w, 0.5 + s / 2),
        box(u, v, 0, 0, w, s),
    )
    return clip(d, u, v, w, tl=C_ * 1.2, br=C_ * 1.2)


GLYPHS = {"H": g_H, "E": g_E, "L": g_L, "T": g_T, "O": g_O, "U": g_U, "D": g_D, "R": g_R, "M": g_M, "A": g_A, "S": g_S}


def glyph_width(ch: str) -> float:
    if ch == " ":
        return SPACE
    return GLYPHS[ch].__defaults__[0]


def line_width(text: str, track: float) -> float:
    return sum(glyph_width(c) for c in text) + track * (len(text) - 1)


def draw_line(sdf: np.ndarray, line_id: np.ndarray, ident: int, text: str, x0: float, baseline: float, cap: float, track: float) -> None:
    """Rasterises `text` into the pixel SDF (px units), left edge x0, baseline y (px, y down)."""
    x = x0
    hgt, wid = sdf.shape
    for ch in text:
        gw = glyph_width(ch)
        if ch != " ":
            px0, px1 = int(max(0, x - 8)), int(min(wid, x + gw * cap + 8))
            py0, py1 = int(max(0, baseline - cap - 8)), int(min(hgt, baseline + 8))
            ys, xs = np.mgrid[py0:py1, px0:px1].astype(float) + 0.5
            u, v = (xs - x) / cap, (baseline - ys) / cap
            d = GLYPHS[ch](u, v) * cap
            region = sdf[py0:py1, px0:px1]
            take = d < region
            region[take] = d[take]
            line_id[py0:py1, px0:px1][take] = ident
        x += (gw + track) * cap


# ------------------------------------------------------------------ treatment
def blur(a: np.ndarray, r: int) -> np.ndarray:
    out = a.copy()
    for axis in (0, 1):
        k = np.cumsum(np.pad(out, [(r + 1, r) if i == axis else (0, 0) for i in range(2)], mode="edge"), axis=axis)
        hi = np.take(k, np.arange(2 * r + 1, k.shape[axis]), axis=axis)
        lo = np.take(k, np.arange(0, k.shape[axis] - 2 * r - 1), axis=axis)
        out = (hi - lo) / (2 * r + 1)
    return out


def scratches(h: int, w: int, seed: int, count: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w))
    for _ in range(count):
        cx, cy = rng.uniform(0, w), rng.uniform(0, h)
        ang = rng.normal(0, 0.35) + (np.pi / 2 if rng.random() < 0.15 else 0)
        length = rng.uniform(20, 110)
        dx, dy = np.cos(ang), np.sin(ang)
        x0, x1 = int(max(0, cx - length)), int(min(w, cx + length))
        y0, y1 = int(max(0, cy - length)), int(min(h, cy + length))
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(float)
        along = (xs - cx) * dx + (ys - cy) * dy
        across = -(xs - cx) * dy + (ys - cy) * dx
        wgt = np.clip(1.4 - np.abs(across), 0, 1) * (np.abs(along) < length / 2) * rng.uniform(0.4, 1.0)
        out[y0:y1, x0:x1] = np.maximum(out[y0:y1, x0:x1], wgt)
    return out


def sky(ry: np.ndarray) -> np.ndarray:
    """Sunset sky colour for a reflected ray's up component (-1..1)."""
    t = np.clip(ry, -1, 1)[..., None]
    horizon = np.array([1.0, 0.72, 0.46])
    zenith = np.array([0.36, 0.48, 0.72])
    ground = np.array([0.55, 0.33, 0.22])
    up = horizon + (zenith - horizon) * np.clip(t * 1.6, 0, 1)
    down = horizon + (ground - horizon) * np.clip(-t * 2.5, 0, 1)
    return np.where(t >= 0, up, down)


def build() -> np.ndarray:
    hh, ww = H * SS, W * SS
    sdf = np.full((hh, ww), 1e4)
    line_id = np.zeros((hh, ww), dtype=np.int8)
    left = 14 * SS
    cap1, cap2 = 112 * SS, 98 * SS
    top1 = 14 * SS
    base1 = top1 + cap1
    base2 = base1 + 14 * SS + cap2
    width1 = line_width("RED MESA", TRACK) * cap1
    track2 = (width1 / cap2 - line_width("HOLDOUT", 0)) / 6
    draw_line(sdf, line_id, 1, "RED MESA", left, base1, cap1, TRACK)
    draw_line(sdf, line_id, 2, "HOLDOUT", left, base2, cap2, track2)

    mask = np.clip(0.5 - sdf, 0, 1)
    bevel = 3.2 * SS
    height = np.clip(-sdf / bevel, 0, 1)
    gy, gx = np.gradient(height * bevel * 0.9)
    n = np.stack([-gx, -gy, np.ones_like(gx)], axis=-1)  # image axes: x right, y down, z out
    n /= np.linalg.norm(n, axis=-1, keepdims=True)

    # Paint, chips and bare steel.
    paint = np.where((line_id == 1)[..., None], AMBER_PAINT, BONE_PAINT)
    brushed = periodic_noise(hh, ww, 11, 60, 0.8) * 0.05 + periodic_noise(hh, ww, 12, 4, 4) * 0.03
    steel = STEEL[None, None, :] * (1 + brushed[..., None])
    edge = 1 - height  # 1 on the bevel, 0 on the face
    chips_n = periodic_noise(hh, ww, 21, 5, 5) * 0.55 + periodic_noise(hh, ww, 22, 18, 18) * 0.45
    wear = chips_n * 0.8 + edge * 1.7
    chip = smoothstep(1.28, 1.4, wear) + smoothstep(2.3, 2.42, chips_n)
    # A dark lip of lifted paint around every chip.
    lip = np.clip(smoothstep(1.1, 1.28, wear) - chip + smoothstep(2.12, 2.3, chips_n) * 0.6, 0, 1)
    chip = np.clip(chip + scratches(hh, ww, 31, 110) * (height > 0.3), 0, 1)
    grain = periodic_noise(hh, ww, 32, 1.2, 1.2) * 0.035
    streaks = np.clip(periodic_noise(hh, ww, 33, 2.5, 45), 0, None) * 0.07  # grime run-down
    paint_c = paint * (1 + grain - streaks)[..., None] * (1 - 0.35 * lip)[..., None]
    albedo = paint_c * (1 - chip[..., None]) + steel * chip[..., None]
    # Paint mottling and sun bleaching.
    mottle = periodic_noise(hh, ww, 41, 30, 30)
    ys = np.arange(hh, dtype=float)[:, None]
    in_line = np.where(line_id == 1, (ys - (base1 - cap1)) / cap1, (ys - (base2 - cap2)) / cap2)
    bleach = np.clip(1.08 - 0.22 * in_line, 0.8, 1.1)  # sun-bleached tops
    albedo *= ((1 + 0.08 * mottle) * np.where(chip > 0.5, 1.0, bleach))[..., None]
    # Dust at the foot of each letter (dust gathers low) and grime in the bevels.
    foot1 = smoothstep(base1 - cap1 * 0.45, base1, ys) * (line_id == 1)
    foot2 = smoothstep(base2 - cap2 * 0.45, base2, ys) * (line_id == 2)
    dust = np.clip((foot1 + foot2) * (0.35 + 0.35 * periodic_noise(hh, ww, 51, 12, 6)), 0, 0.6)
    albedo = albedo * (1 - dust[..., None]) + DUST * dust[..., None]
    grime = np.clip(edge * 0.22 + 0.10 * periodic_noise(hh, ww, 61, 40, 40), 0, 0.4)
    albedo *= (1 - grime)[..., None]

    # Light: warm low key from the upper left, cool sky fill from above,
    # metal reflects the sunset sky.
    key = np.array([-0.55, -0.55, 0.63])
    key /= np.linalg.norm(key)
    ndl = np.clip(n @ key, 0, 1)
    fill = np.clip(n @ np.array([0.2, -0.7, 0.68]), 0, 1)
    diffuse = albedo * (0.30 + 0.95 * ndl[..., None] * np.array([1.0, 0.9, 0.78]) + 0.22 * fill[..., None] * np.array([0.7, 0.8, 1.0]))
    refl_up = -2 * n[..., 2] * n[..., 1]  # reflected view ray's up component (view along -z, up = -y)
    metal = chip[..., None]
    spec = sky(refl_up * 1.0 + 0.05) * (0.22 * metal + 0.05 * (1 - metal))
    half = key + np.array([0, 0, 1.0])
    half /= np.linalg.norm(half)
    glint = np.clip(n @ half, 0, 1) ** 60 * (0.9 * metal[..., 0] + 0.15)
    color = diffuse + spec + glint[..., None] * np.array([1.0, 0.86, 0.66])
    color = np.clip(color, 0, 1)

    # Outline and drop shadow (black), then downsample.
    outline = np.clip(0.5 - (sdf - 2.0 * SS), 0, 1)
    shadow = np.roll(np.roll(blur(mask, 5 * SS), 4 * SS, 0), 3 * SS, 1) * 0.65
    back = np.maximum(outline * 0.92, shadow)
    alpha = mask + back * (1 - mask)
    rgb = color * (mask / np.maximum(alpha, 1e-6))[..., None]
    prem = np.concatenate([rgb * alpha[..., None], alpha[..., None]], axis=-1)
    small = prem.reshape(H, SS, W, SS, 4).mean(axis=(1, 3))
    out = small.copy()
    out[..., :3] = small[..., :3] / np.maximum(small[..., 3:4], 1e-6)
    return out


def preview(logo: np.ndarray) -> None:
    """The logo over a sunset-sky band and a sand band (review only)."""
    y = np.linspace(0, 1, H)[:, None, None]
    sky_band = np.array([0.33, 0.45, 0.65]) * (1 - y) + np.array([0.95, 0.72, 0.52]) * y
    sand_band = np.broadcast_to(np.array([0.79, 0.51, 0.31]), (H, 1, 3))
    sheet = np.ones((H * 2, W, 4))
    for i, band in enumerate((sky_band, sand_band)):
        a = logo[..., 3:4]
        sheet[i * H:(i + 1) * H, :, :3] = band * (1 - a) + logo[..., :3] * a
    path = ROOT / "assets" / "previews" / "ui" / "title_logo.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    write_png(path, sheet)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    logo = build()
    write_png(OUT / "title_logo.png", logo)
    preview(logo)
    print("wrote", OUT / "title_logo.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
