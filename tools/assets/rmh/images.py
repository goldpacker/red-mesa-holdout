"""Procedurally drawn decal images (RGBA, numpy rasterised).

The enemy emblem is original: a red downward chevron over a broken circle
(ASSET_CONTRACTS.md). Images are white-on-transparent unless noted; the
decal colour is applied in the material.
"""
import math

import bpy
import numpy as np


def _grid(n):
    ys, xs = np.mgrid[0:n, 0:n].astype(np.float32)
    # -1..1, y up
    return (xs + 0.5) / n * 2 - 1, 1 - (ys + 0.5) / n * 2


def _aa(d, px):
    """Signed distance (negative inside) -> coverage."""
    return np.clip(0.5 - d / px, 0.0, 1.0)


def _seg_dist(x, y, ax, ay, bx, by):
    pax, pay = x - ax, y - ay
    bax, bay = bx - ax, by - ay
    h = np.clip((pax * bax + pay * bay) / (bax * bax + bay * bay), 0, 1)
    return np.hypot(pax - bax * h, pay - bay * h)


def emblem_alpha(n=256):
    x, y = _grid(n)
    px = 2.0 / n
    r = np.hypot(x, y)
    ang = np.degrees(np.arctan2(y, x)) % 360
    ring = np.abs(r - 0.78) - 0.09
    # Break the ring with four gaps (at 45, 135, 225, 315 degrees).
    gap = np.min(np.stack([np.abs(((ang - a + 180) % 360) - 180) for a in (45, 135, 225, 315)]), axis=0)
    ring = np.maximum(ring, (12 - gap) * 0.02)
    # Downward chevron: two thick strokes meeting at the bottom.
    chev = np.minimum(_seg_dist(x, y, -0.5, 0.42, 0.0, -0.38), _seg_dist(x, y, 0.5, 0.42, 0.0, -0.38)) - 0.13
    chev2 = np.minimum(_seg_dist(x, y, -0.3, 0.62, 0.0, 0.14), _seg_dist(x, y, 0.3, 0.62, 0.0, 0.14)) - 0.07
    d = np.minimum(np.minimum(ring, chev), chev2)
    return _aa(d, px)


def stripes_alpha(n=256, count=5, angle=45):
    x, y = _grid(n)
    a = math.radians(angle)
    t = (x * math.cos(a) + y * math.sin(a)) * count
    return ((np.floor(t) % 2) == 0).astype(np.float32)


def arrow_alpha(n=256):
    """Stencilled 'this way up' double arrow (supply crates)."""
    x, y = _grid(n)
    px = 2.0 / n
    shafts = []
    for cx in (-0.35, 0.35):
        shaft = np.maximum(np.abs(x - cx) - 0.09, np.maximum(-0.7 - y, y - 0.2))
        head = np.maximum(np.maximum(y - 0.75, -(y - 0.15)), np.abs(x - cx) - (0.75 - y) * 0.55)
        shafts.append(np.minimum(shaft, head))
    d = np.minimum(shafts[0], shafts[1])
    return _aa(d, px)


_SEGMENTS = {
    "0": "abcdef", "1": "bc", "2": "abged", "3": "abgcd", "4": "fgbc",
    "5": "afgcd", "6": "afgedc", "7": "abc", "8": "abcdefg", "9": "abcdfg",
}


def stencil_digits_alpha(text, n=256):
    """Military-style stencil digits (seven-segment with stencil gaps)."""
    x, y = _grid(n)
    px = 2.0 / n
    count = len(text)
    w = 1.7 / count
    d = np.full_like(x, 10.0)
    for i, ch in enumerate(text):
        cx = -0.85 + w * (i + 0.5)
        hw, hh, t = w * 0.32, 0.62, 0.07
        segs = {
            "a": ((cx - hw, hh), (cx + hw, hh)),
            "d": ((cx - hw, -hh), (cx + hw, -hh)),
            "g": ((cx - hw, 0), (cx + hw, 0)),
            "f": ((cx - hw, 0.06), (cx - hw, hh - 0.06)),
            "b": ((cx + hw, 0.06), (cx + hw, hh - 0.06)),
            "e": ((cx - hw, -hh + 0.06), (cx - hw, -0.06)),
            "c": ((cx + hw, -hh + 0.06), (cx + hw, -0.06)),
        }
        for s in _SEGMENTS.get(ch, ""):
            (ax, ay), (bx, by) = segs[s]
            d = np.minimum(d, _seg_dist(x, y, ax, ay, bx, by) - t)
    return _aa(d, px)


# Stencil stroke font: char -> (advance, polylines in a 1-high glyph box).
# Gaps between strokes are the stencil bridges.
_GLYPHS = {
    "0": (0.62, [[(0.24, 1), (0.1, 1), (0, 0.86), (0, 0.14), (0.1, 0), (0.24, 0)], [(0.38, 1), (0.52, 1), (0.62, 0.86), (0.62, 0.14), (0.52, 0), (0.38, 0)]]),
    "1": (0.4, [[(0.05, 0.8), (0.3, 1), (0.3, 0)]]),
    "2": (0.62, [[(0, 0.82), (0.14, 1), (0.48, 1), (0.62, 0.84), (0.62, 0.62), (0.02, 0.02), (0.62, 0.02)]]),
    "3": (0.62, [[(0, 0.86), (0.12, 1), (0.5, 1), (0.62, 0.86), (0.62, 0.64), (0.5, 0.53), (0.22, 0.53)], [(0.5, 0.47), (0.62, 0.36), (0.62, 0.14), (0.5, 0), (0.12, 0), (0, 0.14)]]),
    "4": (0.62, [[(0.46, 0), (0.46, 0.64)], [(0.46, 0.84), (0.46, 1), (0, 0.3), (0.62, 0.3)]]),
    "5": (0.62, [[(0.6, 1), (0.04, 1), (0, 0.55), (0.46, 0.58), (0.62, 0.42), (0.62, 0.14), (0.5, 0), (0.12, 0), (0, 0.12)]]),
    "6": (0.62, [[(0.55, 1), (0.2, 1), (0, 0.76), (0, 0.14), (0.12, 0), (0.5, 0), (0.62, 0.14), (0.62, 0.4), (0.5, 0.55), (0.14, 0.55)]]),
    "7": (0.62, [[(0, 1), (0.62, 1), (0.2, 0)]]),
    "8": (0.62, [[(0.14, 0.53), (0, 0.65), (0, 0.88), (0.12, 1), (0.5, 1), (0.62, 0.88), (0.62, 0.65), (0.48, 0.53)], [(0.14, 0.47), (0, 0.35), (0, 0.12), (0.12, 0), (0.5, 0), (0.62, 0.12), (0.62, 0.35), (0.48, 0.47)]]),
    "9": (0.62, [[(0.07, 0), (0.42, 0), (0.62, 0.24), (0.62, 0.86), (0.5, 1), (0.12, 1), (0, 0.86), (0, 0.6), (0.12, 0.45), (0.48, 0.45)]]),
    ".": (0.26, [[(0.1, 0.04), (0.1, 0.06)]]),
    "-": (0.5, [[(0.06, 0.48), (0.42, 0.48)]]),
    "/": (0.5, [[(0.02, 0), (0.46, 1)]]),
    " ": (0.36, []),
    "A": (0.66, [[(0, 0), (0.33, 1), (0.66, 0)], [(0.16, 0.36), (0.5, 0.36)]]),
    "B": (0.64, [[(0, 0), (0, 1)], [(0.12, 1), (0.46, 1), (0.6, 0.88), (0.6, 0.64), (0.46, 0.53), (0.12, 0.53)], [(0.12, 0.47), (0.48, 0.47), (0.64, 0.35), (0.64, 0.12), (0.48, 0), (0.12, 0)]]),
    "C": (0.62, [[(0.62, 0.84), (0.5, 1), (0.12, 1), (0, 0.86), (0, 0.14), (0.12, 0), (0.5, 0), (0.62, 0.16)]]),
    "D": (0.64, [[(0, 0), (0, 1)], [(0.12, 1), (0.42, 1), (0.64, 0.78), (0.64, 0.22), (0.42, 0), (0.12, 0)]]),
    "E": (0.58, [[(0, 0), (0, 1)], [(0.12, 1), (0.58, 1)], [(0.12, 0.5), (0.48, 0.5)], [(0.12, 0), (0.58, 0)]]),
    "F": (0.56, [[(0, 0), (0, 1)], [(0.12, 1), (0.56, 1)], [(0.12, 0.5), (0.46, 0.5)]]),
    "G": (0.64, [[(0.62, 0.84), (0.5, 1), (0.12, 1), (0, 0.86), (0, 0.14), (0.12, 0), (0.5, 0), (0.64, 0.14), (0.64, 0.44), (0.36, 0.44)]]),
    "H": (0.64, [[(0, 0), (0, 1)], [(0.64, 0), (0.64, 1)], [(0.12, 0.5), (0.52, 0.5)]]),
    "I": (0.2, [[(0.06, 0), (0.06, 1)]]),
    "K": (0.62, [[(0, 0), (0, 1)], [(0.62, 1), (0.14, 0.5), (0.62, 0)]]),
    "L": (0.54, [[(0, 1), (0, 0.12)], [(0.1, 0), (0.54, 0)]]),
    "M": (0.74, [[(0, 0), (0, 1), (0.37, 0.4), (0.74, 1), (0.74, 0)]]),
    "N": (0.64, [[(0, 0), (0, 1), (0.64, 0), (0.64, 1)]]),
    "O": (0.66, [[(0.26, 1), (0.12, 1), (0, 0.86), (0, 0.14), (0.12, 0), (0.26, 0)], [(0.4, 1), (0.54, 1), (0.66, 0.86), (0.66, 0.14), (0.54, 0), (0.4, 0)]]),
    "P": (0.6, [[(0, 0), (0, 1)], [(0.12, 1), (0.46, 1), (0.6, 0.86), (0.6, 0.62), (0.46, 0.48), (0.12, 0.48)]]),
    "R": (0.62, [[(0, 0), (0, 1)], [(0.12, 1), (0.46, 1), (0.6, 0.86), (0.6, 0.62), (0.46, 0.48), (0.12, 0.48)], [(0.34, 0.44), (0.62, 0)]]),
    "S": (0.62, [[(0.62, 0.84), (0.5, 1), (0.12, 1), (0, 0.86), (0, 0.66), (0.12, 0.53), (0.5, 0.47), (0.62, 0.34), (0.62, 0.14), (0.5, 0), (0.12, 0), (0, 0.16)]]),
    "T": (0.62, [[(0, 1), (0.62, 1)], [(0.31, 0.88), (0.31, 0)]]),
    "U": (0.62, [[(0, 1), (0, 0.14), (0.12, 0), (0.5, 0), (0.62, 0.14), (0.62, 1)]]),
    "W": (0.8, [[(0, 1), (0.18, 0), (0.4, 0.62), (0.62, 0), (0.8, 1)]]),
    "X": (0.62, [[(0, 1), (0.62, 0)], [(0, 0), (0.62, 1)]]),
}


def _smooth_noise(h, w, cell, seed):
    rng = np.random.default_rng(seed)
    gh, gw = h // cell + 2, w // cell + 2
    grid = rng.random((gh, gw)).astype(np.float32)
    ys = np.arange(h, dtype=np.float32) / cell
    xs = np.arange(w, dtype=np.float32) / cell
    y0, x0 = ys.astype(int), xs.astype(int)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = grid[y0][:, x0]
    b = grid[y0][:, x0 + 1]
    c = grid[y0 + 1][:, x0]
    d = grid[y0 + 1][:, x0 + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def text_alpha(text, height=96, stroke=0.085, pad=0.18, spacing=0.14, wear=0.0, seed=1):
    """Stencilled text (own stroke font above) as a (h, w) alpha array.
    The image aspect is (width / height); project it with a decal whose
    size has the same aspect (see `text_aspect`). `wear` 0..1 erodes the
    paint like an old spray stencil."""
    segs = []
    x = 0.0
    for ch in text.upper():
        adv, lines = _GLYPHS.get(ch, _GLYPHS[" "])
        for line in lines:
            for (ax, ay), (bx, by) in zip(line, line[1:]):
                segs.append((x + ax, ay, x + bx, by))
        x += adv + spacing
    width_units = max(x - spacing, 0.1)
    total_w = width_units + 2 * pad
    total_h = 1.0 + 2 * pad
    h = height
    w = max(8, int(round(h * total_w / total_h)))
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    ux = (xs + 0.5) / h * total_h - pad
    uy = (1 - (ys + 0.5) / h) * total_h - pad
    d = np.full((h, w), 10.0, dtype=np.float32)
    for ax, ay, bx, by in segs:
        if (ax, ay) == (bx, by):
            bx += 1e-4
        d = np.minimum(d, _seg_dist(ux, uy, ax, ay, bx, by))
    alpha = np.clip(0.5 - (d - stroke) / (total_h / h * 1.2), 0.0, 1.0)
    if wear > 0:
        n = 0.6 * _smooth_noise(h, w, max(2, h // 10), seed) + 0.4 * _smooth_noise(h, w, max(2, h // 40), seed + 1)
        alpha *= np.clip((n - wear * 0.55) / 0.12, 0.0, 1.0)
    return alpha


def text_aspect(text, **kw):
    a = text_alpha(text, height=16, **kw)
    return a.shape[1] / a.shape[0]


def to_image(name, alpha, color=(1, 1, 1)):
    h, w = alpha.shape
    img = bpy.data.images.new(name, w, h, alpha=True)
    rgba = np.zeros((h, w, 4), dtype=np.float32)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = color
    rgba[..., 3] = alpha
    img.pixels.foreach_set(np.flipud(rgba).ravel())
    img.pack()
    return img


def get(kind, **kw):
    key = kind + "_" + "_".join(f"{k}{v}" for k, v in sorted(kw.items()))
    if key in bpy.data.images:
        return bpy.data.images[key]
    fn = {
        "emblem": emblem_alpha,
        "stripes": stripes_alpha,
        "arrow": arrow_alpha,
        "digits": lambda **k: stencil_digits_alpha(k.pop("text"), **k),
        "text": lambda **k: text_alpha(k.pop("text"), **k),
    }[kind]
    return to_image(key, fn(**kw))
