"""Texture atlas for the road and wash edge strips (ENV-3, FACELIFT_PLAN 1c).

    tools/env/py.sh tools/env/ground/strip_textures.py

One 1024² colour (RGBA, alpha = coverage) + 512² normal set. U tiles along
the strip every PERIOD studs; V is split into bands across it:

  rows   0-255  road shoulder, right side (t = +9..+25 studs)
  rows 256-511  road shoulder, left side  (t = -9..-25 studs)
                 The inner part samples the terrain `RedMesaRoad` maps at
                 the same t the road core mesh shows them (same ruts), so
                 the alpha ramp over the core has no seam; then a loose-gravel
                 berm and sand with scattered pebbles fading onto the floor.
  rows 512-959  wash bank (both sides): q = -0.3..1.6, q = 0 at the bank
                 toe, q = 1 at the lip. Pebble bed fading in over the wash
                 bed, damp toe, sandy bank with rills, an eroded crust lip
                 with its undercut shadow, sand spilling onto the floor.
  rows 960-1023 unused (transparent).

UV conventions shared with strips.py (Blender UVs, v up = image up), for a
strip point with unit along-vector T_s, across-vector T_t (T_s x T_t = up):
  core (terrain Road maps): U = t / 32 + ROAD_U0, v = -s / 32
  band of side sigma (+1: t > 0, -1: t < 0): U = -sigma * s / PERIOD,
      v = band top - |t| or q (rows run outward).
Both are non-mirrored, so everything here is authored as height fields in
image space and turned into normals there; tile normals sampled from the
road maps are rotated into the band frame.

Everything is generated in a uniform 20 px/stud space and then resampled
along U, so pebbles stay round on the mesh. Deterministic (fixed seeds).
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import texlib as T  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
TERRAIN = os.path.join(ROOT, "assets", "textures", "terrain")
OUT = os.path.join(ROOT, "assets", "textures", "ground")
N = 1024
ALPHA_FLOOR = 2.5 / 255.0
PX = 20.0              # px per stud in the working space
PERIOD = 96.0          # studs along U per tile: 3 road tiles (32), 2 sand tiles (48), 4 wash tiles (24)
W = int(PERIOD * PX)   # 1920 working columns

ROAD_TILE = 32.0
ROAD_U0 = 0.465        # core: ruts at t = -11, -4.6, +4.4, +11
SHOULDER = (9.0, 25.0)             # |t| range of the shoulder bands
SHOULDER_ROWS = {1: (0, 256), -1: (256, 512)}
BANK_Q = (-0.3, 1.6)
BANK_NOMINAL = 11.0                # studs toe -> lip used for the working scale
BANK_ROWS = (512, 960)


def tile(name, kind):
    return T.load(os.path.join(TERRAIN, name, f"{name}_{kind}.png"))[..., :3]


def sample(img, rows_px, cols_px):
    """Bilinear wrap-around sample of a square tile at fractional pixel coords."""
    n = img.shape[0]
    r0 = np.floor(rows_px).astype(np.int64)
    c0 = np.floor(cols_px).astype(np.int64)
    fr = (rows_px - r0)[..., None]
    fc = (cols_px - c0)[..., None]
    r0 %= n
    c0 %= n
    r1 = (r0 + 1) % n
    c1 = (c0 + 1) % n
    return ((img[r0, c0] * (1 - fc) + img[r0, c1] * fc) * (1 - fr)
            + (img[r1, c0] * (1 - fc) + img[r1, c1] * fc) * fr).astype(np.float32)


def prefilter(img, src_px_per_stud):
    """Blur a tile before sampling it at PX px/stud (anti-alias)."""
    ratio = src_px_per_stud / PX
    if ratio <= 1.0:
        return img
    return np.stack([T.blur(img[..., c], 0.5 * ratio) for c in range(img.shape[2])], axis=-1)


def band_noise(rows, seed, beta=2.2, min_period=2.0, max_period=None):
    """fbm periodic along the columns, cropped to a band of `rows` rows."""
    return T.fbm(W, seed, beta=beta, min_period=min_period, max_period=max_period)[:rows]


def stamps(rows, count, seed, r_lo, r_hi, mask=None, squash=0.7):
    """Pebble stamps periodic along the columns (made on a W x W torus, cropped)."""
    m = None
    if mask is not None:
        m = np.zeros((W, W), dtype=np.float32)
        m[:rows] = mask
    h, c, tone = T.scatter_stamps(W, count, seed, r_lo, r_hi, mask=m, squash=squash)
    return h[:rows], c[:rows], tone[:rows]


def pebble_colors(height, tone, dark, light):
    a = T.srgb_to_linear(T.hex_rgb(dark))
    b = T.srgb_to_linear(T.hex_rgb(light))
    lin = a[None, None, :] + (b - a)[None, None, :] * (tone ** 1.5)[..., None]
    lin = lin * (0.72 + 0.38 * height)[..., None]
    return T.linear_to_srgb(lin)


def normals_from_height(h):
    """Tangent normals (x = +columns, y = image up) of a height field in studs."""
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5 * PX
    dy = (np.roll(h, 1, axis=0) - np.roll(h, -1, axis=0)) * 0.5 * PX
    dy[0] = dy[1]
    dy[-1] = dy[-2]
    n = np.stack([-dx, -dy, np.ones_like(h)], axis=-1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def to_atlas(img, rows_out):
    """Working space (rows, W, C) -> atlas band (rows_out, N, C)."""
    rows = img.shape[0]
    xs = (np.arange(N) + 0.5) * (W / N) - 0.5
    sq = np.pad(img, ((0, W - rows), (0, 0), (0, 0)), mode="edge")
    blurred = np.stack([T.blur_aniso(sq[..., c], 0.45 * W / N, 0.0)[:rows] for c in range(img.shape[2])], axis=-1)
    x0 = np.floor(xs).astype(np.int64)
    fx = (xs - x0)[None, :, None]
    x0 %= W
    along = blurred[:, x0] * (1 - fx) + blurred[:, (x0 + 1) % W] * fx
    ys = (np.arange(rows_out) + 0.5) * (rows / rows_out) - 0.5
    y0 = np.clip(np.floor(ys).astype(np.int64), 0, rows - 1)
    y1 = np.clip(y0 + 1, 0, rows - 1)
    fy = np.clip(ys - y0, 0, 1)[:, None, None]
    return (along[y0] * (1 - fy) + along[y1] * fy).astype(np.float32)


def colour_of(hex_, shape):
    return np.broadcast_to(T.hex_rgb(hex_), shape).astype(np.float32)


# ------------------------------------------------------------------ bands
def road_shoulder(sigma, road_c, road_n, sand_c, sand_n):
    """Shoulder band for side sigma: rows run outward from |t| = 9 to 25."""
    t0, t1 = SHOULDER
    rows = int((t1 - t0) * PX)
    a = t0 + (np.arange(rows)[:, None] + 0.5) / PX           # |t|
    col = (np.arange(W)[None, :] + 0.5)
    aa = np.broadcast_to(a, (rows, W))
    s = np.broadcast_to(-sigma * col / PX, (rows, W))        # U = -sigma * s / PERIOD
    t = sigma * aa
    # Road tile where the core shows it: U = t/32 + U0, v = -s/32 (row = s * 32 px).
    rr, rcol = s * (1024.0 / ROAD_TILE), (t / ROAD_TILE + ROAD_U0) * 1024.0
    rc = sample(road_c, rr, rcol)
    rn = T.decode_normal(sample(road_n, rr, rcol))
    # tile frame (x = T_t, y = -T_s) -> band frame (x = -sigma T_s, y = -sigma T_t)
    rn = np.stack([sigma * rn[..., 1], -sigma * rn[..., 0], rn[..., 2]], axis=-1)
    sp = 1024.0 / 48.0
    rows_px = np.broadcast_to(np.arange(rows)[:, None] * sp / PX + (517.0 if sigma > 0 else 131.0), (rows, W))
    cols_px = np.broadcast_to(col * sp / PX + 300.0, (rows, W))
    sc = sample(sand_c, rows_px, cols_px)
    sn = T.decode_normal(sample(sand_n, rows_px, cols_px))

    seed = 300 if sigma > 0 else 350
    wob = band_noise(rows, seed + 1, beta=2.6, min_period=20) * 0.9      # studs of edge wobble
    fine = band_noise(rows, seed + 2, beta=1.4, min_period=2, max_period=24)
    road_to_sand = T.smoothstep(15.5, 21.0, aa + wob)
    base = T.mix(rc, sc, road_to_sand)
    # Berm of loose, paler gravel pushed off the track.
    berm = np.exp(-((aa + 0.6 * wob - 16.0) / 1.6) ** 2)
    base = T.tint(base, 1.0 + 0.10 * berm)
    base = T.mix(base, colour_of("#B98A62", base.shape), 0.25 * berm)
    dens = np.clip(0.25 + 0.9 * berm + 0.35 * (1 - road_to_sand) - 0.5 * T.smoothstep(19, 25, aa), 0.02, 1.0)
    ph, pc, tone = stamps(rows, 1500, seed + 3, 1.6, 5.0, mask=dens)
    base = T.mix(base, pebble_colors(ph, tone, "#7A4B34", "#CFA886"), pc * 0.85)
    base = T.tint(base, 1.0 + 0.04 * fine)

    # Alpha: ramps in over the core (|t| 9..12.5), solid past the voxel paint
    # edge (<= ~19), then a ragged fade onto the terrain sand by |t| = 25.
    edge_in = T.smoothstep(9.2, 12.5, aa + 0.5 * wob)
    ragged = band_noise(rows, seed + 4, beta=1.8, min_period=3, max_period=64)
    edge_out = 1.0 - T.smoothstep(19.0, 24.5, aa + 1.4 * ragged + wob)
    alpha = np.clip(edge_in * edge_out, 0.0, 1.0)
    alpha = np.clip(np.maximum(alpha, pc * T.smoothstep(26.0, 21.0, aa) * (aa > 11.0)), 0, 1)

    n = T.mix(rn, sn, road_to_sand)
    n = n / np.linalg.norm(n, axis=-1, keepdims=True)
    n = T.blend_normals(n, normals_from_height(0.3 * berm + 0.05 * fine + 0.2 * ph))
    return base, alpha, n


def wash_bank(wash_c, wash_n, sand_c, sand_n):
    q0, q1 = BANK_Q
    rows = int((q1 - q0) * BANK_NOMINAL * PX)
    q = q0 + (np.arange(rows)[:, None] + 0.5) / (BANK_NOMINAL * PX)
    qq = np.broadcast_to(q, (rows, W))
    col = np.arange(W)[None, :] + 0.5
    wp = 1024.0 / 24.0
    rows_px = np.broadcast_to(np.arange(rows)[:, None] * wp / PX + 250.0, (rows, W))
    cols_px = np.broadcast_to(col * wp / PX + 111.0, (rows, W))
    wc = sample(wash_c, rows_px, cols_px)
    wn = T.decode_normal(sample(wash_n, rows_px, cols_px))
    sp = 1024.0 / 48.0
    rows_px = np.broadcast_to(np.arange(rows)[:, None] * sp / PX + 700.0, (rows, W))
    cols_px = np.broadcast_to(col * sp / PX + 40.0, (rows, W))
    sc = sample(sand_c, rows_px, cols_px)
    sn = T.decode_normal(sample(sand_n, rows_px, cols_px))
    # Softer ripples than the open floor: on the sloping bank faces the
    # floor's wind ripples read as contour lines close up.
    sc = T.mix(sc, np.broadcast_to(sc.reshape(-1, 3).mean(0), sc.shape), 0.45)
    sn = T.scale_normal(sn, 0.45)

    wob = band_noise(rows, 401, beta=2.8, min_period=24) * 0.05        # q units
    fine = band_noise(rows, 402, beta=1.4, min_period=2, max_period=24)
    lip_q = 1.0 + wob
    face = T.smoothstep(0.05, 0.45, qq)
    base = T.mix(wc, T.recolor(sc, "#C4905F", contrast=1.2, chroma_keep=0.5), face)
    spill = T.smoothstep(1.0, 1.12, qq - wob)
    base = T.mix(base, sc, spill)
    damp = T.smoothstep(0.35, 0.0, qq) * T.smoothstep(-0.32, -0.1, qq)
    base = T.tint(base, 1.0 - 0.22 * damp)
    # Rills: down-slope grooves from below the lip toward the toe.
    rng = np.random.default_rng(403)
    rill_h = np.zeros((rows, W), dtype=np.float32)
    for _ in range(40):
        c = rng.uniform(0, W)
        top = rng.uniform(0.65, 0.95)
        bot = rng.uniform(0.05, 0.35)
        width = rng.uniform(0.25, 0.7) * PX
        depth = rng.uniform(0.3, 1.0)
        meander = 0.6 * PX * np.sin(qq * rng.uniform(4, 9) + rng.uniform(0, 6.3))
        dx = (col - c - meander + W / 2) % W - W / 2
        along = T.smoothstep(bot, bot + 0.1, qq) * T.smoothstep(top, top - 0.1, qq)
        rill_h -= depth * np.exp(-(dx / width) ** 2) * along
    base = T.tint(base, 1.0 + 0.06 * rill_h)
    # Lip: crust ridge with the undercut shadow just below it.
    crust = np.exp(-((qq - lip_q + 0.03) / 0.045) ** 2)
    undercut = np.exp(-((qq - lip_q + 0.11) / 0.035) ** 2)
    broken = T.smoothstep(-0.4, 0.8, band_noise(rows, 404, beta=2.0, min_period=6, max_period=40))
    base = T.tint(base, 1.0 + 0.10 * crust * broken - 0.35 * undercut * (0.5 + 0.5 * broken))
    bed = T.smoothstep(-0.32, -0.12, qq) * T.smoothstep(0.3, 0.02, qq)
    dens = np.clip(1.0 * bed + 0.03 * (qq > 0.3) * (qq < 0.85) + 0.05 * spill * (qq < 1.3), 0.0, 1.0)
    ph, pc, tone = stamps(rows, 3200, 405, 1.8, 7.0, mask=dens)
    base = T.mix(base, pebble_colors(ph, tone, "#7A5038", "#D8C0A0"), pc * 0.9)
    base = T.tint(base, 1.0 + 0.04 * fine)

    ragged_in = band_noise(rows, 406, beta=1.8, min_period=3, max_period=48)
    ragged_out = band_noise(rows, 407, beta=1.8, min_period=3, max_period=64)
    edge_in = T.smoothstep(-0.28, -0.08, qq + 0.05 * ragged_in)
    edge_out = 1.0 - T.smoothstep(1.2, 1.56, qq + 0.08 * ragged_out + wob)
    alpha = np.clip(edge_in * edge_out, 0.0, 1.0)
    alpha = np.clip(np.maximum(alpha, pc * (qq < 0.2)), 0, 1)

    n = T.mix(wn, sn, np.maximum(face, spill))
    n = n / np.linalg.norm(n, axis=-1, keepdims=True)
    # rows run outward (q up) = image down, so the lip ridge in q is a ridge in -y
    h = 0.12 * rill_h + 0.35 * crust * broken - 0.25 * undercut + 0.05 * fine + 0.25 * ph
    n = T.blend_normals(n, normals_from_height(h))
    return base, alpha, n


def main():
    os.makedirs(OUT, exist_ok=True)
    road_c = prefilter(tile("Road", "color"), 1024 / ROAD_TILE)
    road_n = prefilter(tile("Road", "normal"), 1024 / ROAD_TILE)
    sand_c = prefilter(tile("Sand", "color"), 1024 / 48)
    sand_n = prefilter(tile("Sand", "normal"), 1024 / 48)
    wash_c = prefilter(tile("Wash", "color"), 1024 / 24)
    wash_n = prefilter(tile("Wash", "normal"), 1024 / 24)

    colour = np.zeros((N, N, 4), dtype=np.float32)
    colour[..., :3] = T.hex_rgb("#C9824F")
    normal = np.zeros((N, N, 3), dtype=np.float32)
    normal[..., 2] = 1.0
    bands = [
        ("shoulder+", SHOULDER_ROWS[1], road_shoulder(1, road_c, road_n, sand_c, sand_n)),
        ("shoulder-", SHOULDER_ROWS[-1], road_shoulder(-1, road_c, road_n, sand_c, sand_n)),
        ("bank", BANK_ROWS, wash_bank(wash_c, wash_n, sand_c, sand_n)),
    ]
    for name, (r0, r1), (c, a, n) in bands:
        colour[r0:r1] = to_atlas(np.concatenate([c, a[..., None]], axis=-1), r1 - r0)
        nn = to_atlas(n, r1 - r0)
        normal[r0:r1] = nn / np.linalg.norm(nn, axis=-1, keepdims=True)
        print(f"{name}: rows {r0}-{r1}, alpha mean {colour[r0:r1, :, 3].mean():.2f}")
    # Roblox replaces the colour of fully transparent texels with white on
    # upload, which then bleeds into the edges through filtering and mips
    # (measured: white fringes). Keep every texel at least 2/255 opaque.
    colour[..., 3] = np.maximum(colour[..., 3], ALPHA_FLOOR)
    T.save(os.path.join(OUT, "GroundStrips_color.png"), colour)
    T.save(os.path.join(OUT, "GroundStrips_normal.png"), T.encode_normal(T.downsample(normal, 512)))
    yy, xx = np.mgrid[0:N, 0:N]
    check = np.where(((yy // 32 + xx // 32) % 2)[..., None] == 0, 0.25, 0.4).astype(np.float32)
    prev = colour[..., :3] * colour[..., 3:] + check * (1 - colour[..., 3:])
    os.makedirs(os.path.join(ROOT, "assets", "previews", "ground"), exist_ok=True)
    T.save(os.path.join(ROOT, "assets", "previews", "ground", "GroundStrips_atlas.png"), prev)
    manifest = {
        "size": N, "period_studs": PERIOD, "road_tile": ROAD_TILE, "road_u0": ROAD_U0,
        "bands": {
            "shoulder+": {"rows": SHOULDER_ROWS[1], "abs_t": SHOULDER},
            "shoulder-": {"rows": SHOULDER_ROWS[-1], "abs_t": SHOULDER},
            "bank": {"rows": BANK_ROWS, "q": BANK_Q},
        },
        "mean_color": T.mean_srgb(colour[..., :3]),
    }
    with open(os.path.join(OUT, "strips.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
