"""Shared texture atlas for the ground dressing (ENV-3, FACELIFT_PLAN 1d).

    tools/env/py.sh tools/env/ground/dressing_textures.py

One 1024² colour (RGBA, alpha = coverage) + 512² normal set used by every
dressing mesh (dressing.py). Regions, in image pixels (x, y, w, h):

  cards (alpha cards, side view, base at the bottom edge):
    scrub_a   (  0,   0, 256, 256)  grey-green brittlebush / sage scrub
    scrub_b   (256,   0, 256, 256)  dead twiggy brush
    creosote  (512,   0, 256, 256)  creosote: upright fan of stems, dark olive leaves
    grass     (768,   0, 256, 256)  dry bunch grass
    shadow    (  0, 256, 256, 256)  soft contact shadow (ground card under a bush)
    saltbush  (256, 256, 512, 256)  low wide grey saltbush mound
    top       (768, 256, 256, 256)  canopy seen from above (bush tops)
  bark      (  0, 512, 1024,  64)  weathered dead wood, tiles along U (branches)
  tracks    (  0, 576, 1024, 128)  a pair of tyre marks, tiles along U (48 studs)
  rock      (  0, 704, 512, 320)  rust rock surface (pebbles, rock clusters)
  crater    (512, 704, 320, 320)  old, wind-filled shell crater (flat alpha disc)
  (832, 704, 192, 320) unused

Opaque meshes (rocks, pebbles, branches) sample only fully opaque regions,
so the same colour map also serves an opaque (AlphaMode Overlay)
SurfaceAppearance. Deterministic (fixed seeds).
"""
import json
import math
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
SS = 3  # supersampling for the painted cards

REGIONS = {
    "scrub_a": (0, 0, 256, 256),
    "scrub_b": (256, 0, 256, 256),
    "creosote": (512, 0, 256, 256),
    "grass": (768, 0, 256, 256),
    "shadow": (0, 256, 256, 256),
    "saltbush": (256, 256, 512, 256),
    "top": (768, 256, 256, 256),
    "bark": (0, 512, 1024, 64),
    "tracks": (0, 576, 1024, 128),
    "rock": (0, 704, 512, 320),
    "crater": (512, 704, 320, 320),
}
TRACK_STUDS = (48.0, 6.0)     # tracks band: along x across
CRATER_STUDS = 20.0            # crater region diameter
BARK_STUDS = (8.0, 1.0)        # bark band: along x around
ROCK_PX_PER_STUD = 1024 / 30.0  # the terrain Rock tile (30 studs per tile)


def lin(hex_):
    return T.srgb_to_linear(T.hex_rgb(hex_))


class Canvas:
    """Supersampled RGBA painter with tangent normals (linear colour)."""

    def __init__(self, w, h):
        self.w, self.h = w * SS, h * SS
        self.col = np.zeros((self.h, self.w, 3), dtype=np.float32)
        self.a = np.zeros((self.h, self.w), dtype=np.float32)
        self.n = np.zeros((self.h, self.w, 3), dtype=np.float32)
        self.n[..., 2] = 1.0

    def _over(self, ys, xs, cov, colour, normal):
        a0 = self.a[ys, xs]
        self.col[ys, xs] = self.col[ys, xs] * (1 - cov[..., None]) + colour * cov[..., None]
        self.n[ys, xs] = self.n[ys, xs] * (1 - cov[..., None]) + normal * cov[..., None]
        self.a[ys, xs] = a0 + (1 - a0) * cov

    def capsule(self, p0, p1, r0, r1, colour):
        """Tapered segment (card px, y down); colour linear rgb."""
        p0 = np.array(p0, dtype=np.float64) * SS
        p1 = np.array(p1, dtype=np.float64) * SS
        r0, r1 = r0 * SS, r1 * SS
        lo = np.floor(np.minimum(p0, p1) - max(r0, r1) - 2).astype(int)
        hi = np.ceil(np.maximum(p0, p1) + max(r0, r1) + 2).astype(int)
        x0, y0 = max(lo[0], 0), max(lo[1], 0)
        x1, y1 = min(hi[0], self.w - 1), min(hi[1], self.h - 1)
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1].astype(np.float64)
        d = p1 - p0
        L2 = max(d @ d, 1e-9)
        t = np.clip(((xx - p0[0]) * d[0] + (yy - p0[1]) * d[1]) / L2, 0, 1)
        qx, qy = p0[0] + t * d[0], p0[1] + t * d[1]
        dist = np.hypot(xx - qx, yy - qy)
        r = r0 + (r1 - r0) * t
        cov = np.clip(r + 0.7 - dist, 0, 1).astype(np.float32)
        if not cov.any():
            return
        # cylinder normal across the segment
        side = ((xx - qx) * (-d[1]) + (yy - qy) * d[0]) / math.sqrt(L2)
        k = np.clip(side / np.maximum(r, 0.5), -1, 1)
        nx = (-d[1] / math.sqrt(L2)) * k
        ny = (d[0] / math.sqrt(L2)) * k
        nrm = np.stack([nx, -ny, np.sqrt(np.clip(1 - k * k, 0.05, 1))], axis=-1).astype(np.float32)
        shade = (0.75 + 0.25 * np.sqrt(np.clip(1 - k * k, 0, 1)))[..., None]
        self._over(slice(y0, y1 + 1), slice(x0, x1 + 1), cov, (colour * shade).astype(np.float32), nrm)

    def blob(self, c, rx, ry, ang, colour, soft=0.8):
        cx, cy = c[0] * SS, c[1] * SS
        rx, ry = rx * SS, ry * SS
        rr = max(rx, ry) + 2
        x0, y0 = max(int(cx - rr), 0), max(int(cy - rr), 0)
        x1, y1 = min(int(cx + rr), self.w - 1), min(int(cy + rr), self.h - 1)
        if x1 <= x0 or y1 <= y0:
            return
        yy, xx = np.mgrid[y0:y1 + 1, x0:x1 + 1].astype(np.float64)
        u = (xx - cx) * math.cos(ang) + (yy - cy) * math.sin(ang)
        v = -(xx - cx) * math.sin(ang) + (yy - cy) * math.cos(ang)
        d2 = (u / rx) ** 2 + (v / ry) ** 2
        cov = np.clip((1 - d2) / (1 - soft) if soft < 1 else 1 - d2, 0, 1).astype(np.float32)
        if not cov.any():
            return
        dome = np.sqrt(np.clip(1 - d2, 0, 1))
        nrm = np.stack([u / rx * 0.8, -v / ry * 0.8, dome + 0.3], axis=-1)
        nrm = (nrm / np.linalg.norm(nrm, axis=-1, keepdims=True)).astype(np.float32)
        shade = (0.8 + 0.2 * dome)[..., None].astype(np.float32)
        self._over(slice(y0, y1 + 1), slice(x0, x1 + 1), cov, colour * shade, nrm)

    def result(self, w, h, volume=0.55):
        """Downsampled (h, w) srgb colour, alpha, tangent normal."""
        a = self.a.reshape(h, SS, w, SS).mean(axis=(1, 3))
        cw = (self.col * self.a[..., None]).reshape(h, SS, w, SS, 3).sum(axis=(1, 3))
        col = cw / np.maximum(self.a.reshape(h, SS, w, SS).sum(axis=(1, 3)), 1e-6)[..., None]
        n = self.n.reshape(h, SS, w, SS, 3).mean(axis=(1, 3))
        # Round the whole card like a volume, so a bush is lit as a mound.
        yy, xx = np.mgrid[0:h, 0:w]
        cx, cy = w / 2, h * 0.95
        vx = (xx - cx) / (w / 2)
        vy = (cy - yy) / h
        # Cards stand upright, so a normal straight out of the card is lit
        # only when the sun faces it; tilt it toward image-up (world up on
        # the card) so a bush takes the light like the ground around it.
        up = 1.1 if volume > 0 else 0.0
        vol = np.stack([vx * volume, (vy - 0.3) * volume + up, np.full_like(vx, 0.8, dtype=np.float64)], axis=-1)
        n = T.blend_normals(n / np.linalg.norm(n, axis=-1, keepdims=True), vol / np.linalg.norm(vol, axis=-1, keepdims=True))
        # Self-shadowing: the inside and bottom of a bush are darker than its
        # sunlit crown (reads as a volume, darker than the sand around it).
        if volume > 0:
            ao = 0.55 + 0.45 * np.clip(0.35 * np.abs(vx) + 1.1 * vy, 0, 1)
            col = col * ao[..., None]
        # dilate colour into transparent texels (no dark halos at mip levels)
        col = dilate(col.astype(np.float32), a > 0.02)
        return T.linear_to_srgb(col), a.astype(np.float32), n.astype(np.float32)


def dilate(img, valid, steps=12):
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


# ------------------------------------------------------------------ plants
def grow(cv, rng, base, ang, length, width, depth, style, tips):
    """Recursive branching stem; collects tip positions for leaves."""
    x0, y0 = base
    bend = rng.normal(0, style["bend"])
    x1 = x0 + math.sin(ang) * length
    y1 = y0 - math.cos(ang) * length
    xm = (x0 + x1) / 2 + math.cos(ang) * bend * length
    ym = (y0 + y1) / 2 + math.sin(ang) * bend * length
    wood = lin(style["wood"][rng.integers(len(style["wood"]))]) * rng.uniform(0.8, 1.1)
    w1 = width * style["taper"]
    cv.capsule((x0, y0), (xm, ym), width, (width + w1) / 2, wood)
    cv.capsule((xm, ym), (x1, y1), (width + w1) / 2, w1, wood)
    tips.append(((xm, ym), depth + 0.5))
    tips.append(((x1, y1), depth + 1))
    if depth >= style["depth"]:
        return
    for _ in range(rng.integers(style["fork"][0], style["fork"][1] + 1)):
        t = rng.uniform(0.45, 1.0)
        bx = x0 + (x1 - x0) * t
        by = y0 + (y1 - y0) * t
        a2 = ang + rng.normal(0, style["spread"])
        grow(cv, rng, (bx, by), a2, length * rng.uniform(0.45, 0.7), w1 * 0.9, depth + 1, style, tips)


def plant(w, h, seed, style):
    rng = np.random.default_rng(seed)
    cv = Canvas(w, h)
    tips = []
    base_y = h - 3
    for i in range(style["stems"]):
        bx = w / 2 + rng.normal(0, style["base_spread"] * w)
        ang = rng.normal(0, style["fan"]) + (i / max(style["stems"] - 1, 1) - 0.5) * style["fan"] * 1.6
        length = h * rng.uniform(*style["length"])
        grow(cv, rng, (bx, base_y), ang, length, style["width"] * rng.uniform(0.8, 1.2), 0, style, tips)
    leaves = style["leaves"]
    for (tx, ty), depth in tips:
        if depth < leaves["min_depth"]:
            continue
        for _ in range(rng.poisson(leaves["per_tip"])):
            cx = tx + rng.normal(0, leaves["spread"])
            cy = ty + rng.normal(0, leaves["spread"])
            if not (2 < cx < w - 2 and 2 < cy < h - 2):
                continue
            mound = style.get("mound")
            if mound and ((cx - w / 2) / (mound[0] * w / 2)) ** 2 + ((h - cy) / (mound[1] * h)) ** 2 > 1:
                continue
            c = lin(leaves["colours"][rng.integers(len(leaves["colours"]))]) * rng.uniform(0.75, 1.15)
            r = rng.uniform(*leaves["size"])
            cv.blob((cx, cy), r, r * rng.uniform(0.45, 0.8), rng.uniform(0, math.pi), c.astype(np.float32))
    return cv.result(w, h, volume=style.get("volume", 0.55))


STYLES = {
    "scrub_a": dict(stems=12, fan=0.95, base_spread=0.05, length=(0.3, 0.5), width=2.0, taper=0.55, depth=3,
                    fork=(2, 3), spread=0.5, bend=0.14, wood=["#6A5A48", "#7C6C58", "#5A4B3C"], mound=(0.95, 0.9),
                    leaves=dict(min_depth=1.0, per_tip=3.4, spread=7.0, size=(2.8, 5.4),
                                colours=["#6F7152", "#7E7F5F", "#626649", "#8E8D6D", "#7A6E4E", "#696B4F"])),
    "scrub_b": dict(stems=11, fan=0.62, base_spread=0.04, length=(0.4, 0.65), width=1.8, taper=0.5, depth=3,
                    fork=(2, 3), spread=0.55, bend=0.18, wood=["#7E6E5C", "#8E7E6A", "#6B5A3E", "#9A8A74"],
                    leaves=dict(min_depth=2.5, per_tip=0.35, spread=4.0, size=(1.8, 3.2),
                                colours=["#6B5A3E", "#8C7A5A", "#7A6848"])),
    "creosote": dict(stems=13, fan=0.32, base_spread=0.05, length=(0.55, 0.85), width=2.0, taper=0.6, depth=2,
                     fork=(2, 3), spread=0.3, bend=0.08, wood=["#4E4638", "#5E5444"],
                     leaves=dict(min_depth=0.8, per_tip=3.0, spread=7.0, size=(2.0, 3.8),
                                 colours=["#5C653B", "#687146", "#737A4B", "#555E39", "#7E8358"])),
    "grass": dict(stems=46, fan=0.38, base_spread=0.07, length=(0.35, 0.8), width=1.1, taper=0.25, depth=0,
                  fork=(0, 0), spread=0.0, bend=0.22, wood=["#B89B6A", "#C8AE7E", "#A68A5C", "#9A8866"],
                  leaves=dict(min_depth=99, per_tip=0, spread=0, size=(1, 1), colours=["#000000"]), volume=0.3),
    "saltbush": dict(stems=22, fan=1.1, base_spread=0.14, length=(0.35, 0.6), width=2.0, taper=0.55, depth=3,
                     fork=(2, 3), spread=0.5, bend=0.14, wood=["#6F6554", "#5E5546"], mound=(0.97, 0.92),
                     leaves=dict(min_depth=1.0, per_tip=4.2, spread=7.5, size=(2.6, 4.8),
                                 colours=["#7E8170", "#8C8F7C", "#737765", "#989A86"])),
}


def canopy_top(w, h, seed):
    """Bush seen from above: leaf clusters in a ragged disc."""
    rng = np.random.default_rng(seed)
    cv = Canvas(w, h)
    for _ in range(420):
        r = w * 0.42 * math.sqrt(rng.random())
        a = rng.uniform(0, 2 * math.pi)
        c = lin(["#6F7152", "#7E7F5F", "#626649", "#8A896A", "#66603F"][rng.integers(5)]) * rng.uniform(0.65, 1.05)
        s = rng.uniform(4, 9)
        cv.blob((w / 2 + r * math.cos(a), h / 2 + r * math.sin(a)), s, s * 0.6, rng.uniform(0, math.pi), c.astype(np.float32))
    col, a, n = cv.result(w, h, volume=0.0)
    return col, a, n


def contact_shadow(w, h):
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w / 2 + 0.5) / (w / 2), (yy - h / 2 + 0.5) / (h / 2))
    a = (0.62 * np.exp(-(r / 0.55) ** 2) * T.smoothstep(1.0, 0.8, r)).astype(np.float32)
    col = np.broadcast_to(T.hex_rgb("#3A2A1E"), (h, w, 3)).astype(np.float32)
    n = np.zeros((h, w, 3), dtype=np.float32)
    n[..., 2] = 1
    return col, a, n


# ------------------------------------------------------------------ surfaces
def periodic_noise(w, h, seed, **kw):
    """fbm periodic in x over a band w wide (made square, cropped)."""
    return T.fbm(w, seed, **kw)[:h]


def bark(w, h):
    grain = T.fbm(w, 601, beta=2.0, min_period=2, aniso=(12.0, 1.0))[:h]
    cracks = T.smoothstep(1.6, 2.4, np.abs(T.fbm(w, 602, beta=2.2, min_period=3, aniso=(20.0, 1.0))[:h]))
    base = lin("#8A7C6A")
    shade = 1.0 + 0.18 * grain - 0.45 * cracks
    around = np.sin(np.linspace(0, math.pi, h))[:, None]  # darker toward the seam edges
    colr = base[None, None, :] * (shade * (0.8 + 0.2 * around))[..., None]
    warm = T.smoothstep(0.5, 1.5, periodic_noise(w, h, 603, beta=2.5, min_period=40))
    colr = colr * (1 + 0.15 * warm[..., None] * np.array([1.0, 0.8, 0.55]))
    hgt = 0.02 * grain - 0.05 * cracks
    n = normals(hgt, px_per_stud=w / BARK_STUDS[0])
    return T.linear_to_srgb(colr).astype(np.float32), np.ones((h, w), np.float32), n


def normals(h, px_per_stud):
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5 * px_per_stud
    dy = (np.roll(h, 1, axis=0) - np.roll(h, -1, axis=0)) * 0.5 * px_per_stud
    n = np.stack([-dx, -dy, np.ones_like(h)], axis=-1)
    return (n / np.linalg.norm(n, axis=-1, keepdims=True)).astype(np.float32)


def tracks(w, h):
    """Two tyre marks along x, partly filled by wind-blown sand."""
    ppx = w / TRACK_STUDS[0]
    ppy = h / TRACK_STUDS[1]
    y = (np.arange(h)[:, None] + 0.5) / ppy - TRACK_STUDS[1] / 2      # studs across, 0 = centre
    x = (np.arange(w)[None, :] + 0.5) / ppx                          # studs along
    yy = np.broadcast_to(y, (h, w))
    xx = np.broadcast_to(x, (h, w))
    wander = 0.15 * periodic_noise(w, h, 701, beta=3.0, min_period=200)
    hgt = np.zeros((h, w), np.float32)
    mark = np.zeros((h, w), np.float32)
    for c in (-1.9, 1.9):
        d = np.abs(yy - c - wander)
        prof = T.smoothstep(0.75, 0.55, d)
        berm = np.exp(-((d - 0.85) / 0.18) ** 2)
        tread = 0.5 + 0.5 * np.sign(np.sin(2 * math.pi * (xx / 0.55 + np.abs(yy - c) * 0.9)))
        hgt += -0.06 * prof + 0.03 * berm - 0.02 * prof * tread
        mark = np.maximum(mark, prof * (0.75 + 0.25 * tread))
        mark = np.maximum(mark, 0.45 * berm)
    fill = T.smoothstep(-0.3, 1.2, periodic_noise(w, h, 702, beta=2.2, min_period=30))
    alpha = np.clip(mark * (1 - 0.8 * fill), 0, 1).astype(np.float32)
    sand = lin("#C9824F")
    colr = sand[None, None, :] * (0.78 + 0.1 * periodic_noise(w, h, 703, beta=1.5, min_period=3, max_period=20)[..., None])
    colr = colr * (1 + 0.25 * np.clip(hgt, 0, None)[..., None] / 0.03)
    return T.linear_to_srgb(colr).astype(np.float32), alpha, normals(hgt, ppx)


def crater(w, h):
    ppx = w / CRATER_STUDS
    yy, xx = np.mgrid[0:h, 0:w]
    rng = np.random.default_rng(801)
    ang = np.arctan2(yy - h / 2 + 0.5, xx - w / 2 + 0.5)
    rad = np.hypot(yy - h / 2 + 0.5, xx - w / 2 + 0.5) / (w / 2)       # 0..1 at the region edge
    wob = 0.04 * np.sin(3 * ang + 1.3) + 0.03 * np.sin(7 * ang + 0.4) + 0.02 * np.sin(13 * ang + 2.2)
    r = rad + wob
    rim_r = 0.55
    hgt = (-0.35 * T.smoothstep(rim_r, 0.0, r) ** 1.5 + 0.22 * np.exp(-((r - rim_r) / 0.1) ** 2)
           + 0.08 * np.exp(-((r - rim_r - 0.18) / 0.15) ** 2))
    rays = 0.5 + 0.5 * np.sin(ang * 11 + 2 * np.sin(ang * 3))
    ejecta = T.smoothstep(0.95, rim_r, r) * T.smoothstep(rim_r - 0.05, rim_r + 0.05, r) * rays
    sand = lin("#C9824F")
    scorch = lin("#6E5040")
    lite = lin("#D69A68")
    t_sc = (T.smoothstep(rim_r + 0.05, 0.1, r) * 0.55)[..., None]
    colr = sand * (1 - t_sc) + scorch * t_sc
    colr = colr * (1 - 0.35 * ejecta[..., None]) + lite * 0.35 * ejecta[..., None]
    # wind-blown sand drift across one side of the bowl
    drift = T.smoothstep(0.2, 0.8, (np.cos(ang - 0.8) * 0.5 + 0.5) * T.smoothstep(0.7, 0.2, r))
    colr = colr * (1 - 0.6 * drift[..., None]) + sand * 0.6 * drift[..., None]
    grain = T.fbm(w, 802, beta=1.4, min_period=2, max_period=24)[:h, :w]
    colr = colr * (1 + 0.06 * grain[..., None])
    # scattered dark debris
    dh, dc, dt = T.scatter_stamps(w, 160, 803, 1.0, 2.6, mask=(T.smoothstep(0.9, 0.3, rad) * 0.9 + 0.05).astype(np.float32))
    colr = colr * (1 - dc[..., None] * 0.55) + lin("#4A3A30") * dc[..., None] * 0.55
    hgt = hgt + 0.04 * dh
    alpha = np.clip(T.smoothstep(0.98, 0.72, r + 0.05 * grain), 0, 1).astype(np.float32)
    return T.linear_to_srgb(colr).astype(np.float32), alpha, normals(hgt.astype(np.float32), ppx)


def rock(w, h):
    col = T.load(os.path.join(TERRAIN, "Rock", "Rock_color.png"))[..., :3]
    nor = T.load(os.path.join(TERRAIN, "Rock", "Rock_normal.png"))[..., :3]
    y0, x0 = 180, 240
    c = col[y0:y0 + h, x0:x0 + w]
    n = T.decode_normal(nor[y0:y0 + h, x0:x0 + w])
    # a little lighter and dustier than the terrain rock (small stones catch sun and dust)
    c = T.tint(c, np.full(c.shape[:2], 1.12, np.float32))
    return c.astype(np.float32), np.ones((h, w), np.float32), n.astype(np.float32)


def main():
    os.makedirs(OUT, exist_ok=True)
    colour = np.zeros((N, N, 4), dtype=np.float32)
    colour[..., :3] = T.hex_rgb("#8A7C5A")
    normal = np.zeros((N, N, 3), dtype=np.float32)
    normal[..., 2] = 1.0
    makers = {
        "scrub_a": lambda w, h: plant(w, h, 11, STYLES["scrub_a"]),
        "scrub_b": lambda w, h: plant(w, h, 12, STYLES["scrub_b"]),
        "creosote": lambda w, h: plant(w, h, 13, STYLES["creosote"]),
        "grass": lambda w, h: plant(w, h, 14, STYLES["grass"]),
        "saltbush": lambda w, h: plant(w, h, 15, STYLES["saltbush"]),
        "top": lambda w, h: canopy_top(w, h, 16),
        "shadow": contact_shadow,
        "bark": bark,
        "tracks": tracks,
        "rock": rock,
        "crater": crater,
    }
    for name, (x, y, w, h) in REGIONS.items():
        c, a, n = makers[name](w, h)
        colour[y:y + h, x:x + w, :3] = c
        colour[y:y + h, x:x + w, 3] = a
        normal[y:y + h, x:x + w] = n
        print(f"{name:9s} ({x},{y},{w},{h}) alpha mean {a.mean():.2f}")
    # Roblox replaces the colour of fully transparent texels with white on
    # upload, which then bleeds into the edges through filtering and mips
    # (measured: white fringes). Keep every texel at least 2/255 opaque.
    colour[..., 3] = np.maximum(colour[..., 3], ALPHA_FLOOR)
    T.save(os.path.join(OUT, "GroundDressing_color.png"), colour)
    T.save(os.path.join(OUT, "GroundDressing_normal.png"), T.encode_normal(T.downsample(normal, 512)))
    yy, xx = np.mgrid[0:N, 0:N]
    check = np.where(((yy // 32 + xx // 32) % 2)[..., None] == 0, 0.25, 0.4).astype(np.float32)
    prev = colour[..., :3] * colour[..., 3:] + check * (1 - colour[..., 3:])
    os.makedirs(os.path.join(ROOT, "assets", "previews", "ground"), exist_ok=True)
    T.save(os.path.join(ROOT, "assets", "previews", "ground", "GroundDressing_atlas.png"), prev)
    with open(os.path.join(OUT, "dressing.json"), "w") as fh:
        json.dump({"size": N, "regions": REGIONS, "tracks_studs": TRACK_STUDS, "crater_studs": CRATER_STUDS,
                   "bark_studs": BARK_STUDS, "rock_px_per_stud": ROCK_PX_PER_STUD}, fh, indent=1)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
