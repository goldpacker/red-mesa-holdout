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


def to_image(name, alpha, color=(1, 1, 1)):
    n = alpha.shape[0]
    img = bpy.data.images.new(name, n, n, alpha=True)
    rgba = np.zeros((n, n, 4), dtype=np.float32)
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
    }[kind]
    return to_image(key, fn(**kw))
