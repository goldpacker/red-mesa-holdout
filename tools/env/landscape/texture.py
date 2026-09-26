"""Colour and roughness of the landscape strata material (numpy).

Inputs are per-texel maps baked from the high-poly surface (bake.py):
world position, world normal, ambient occlusion, pointiness and a bevel
edge mask. The colour is built in linear light from:
  - the strata beds (strata.py): each bed gets its own tone from the art
    bible's cliff family (#9E4A2E mid, #BA6A44 light, #6E3322 shadow), with
    a few pale and dark marker beds;
  - world-space tiling rock (triplanar CC0 photo luminance, high-passed so
    only the grain and fractures remain; offset per bed so block rows never
    line up across beds);
  - desert-varnish streaks down steep faces, dark crevices from AO and
    concave pointiness, bleached convex edges;
  - wind-blown sand on ledge tops and at the foot, rubble on the talus.
"""
from __future__ import annotations

import os

import numpy as np

import strata
from noise import fbm2, fbm3, rand01, smoothstep

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
CC0 = os.path.join(ROOT, "assets", "source", "cc0")


def srgb_to_lin(c):
    c = np.asarray(c, dtype=np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def lin_to_srgb(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def hexc(h):
    h = h.lstrip("#")
    return srgb_to_lin([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


MID = hexc("#9E4A2E")
LIGHT = hexc("#BA6A44")
SHADOW = hexc("#6E3322")
CAP = hexc("#5A3226")
PALE = hexc("#C98A5E")
SAND = hexc("#C9824F")
DUST = hexc("#B8704A")  # reddish wind-blown sand (the basin floor is ochre #C9824F)
BLEACH = hexc("#D9B98C")
VARNISH = hexc("#3B2419")
RUBBLE = hexc("#8A5238")


class Photo:
    """A CC0 map as a tileable luminance field (high-passed, mean 1)."""

    def __init__(self, asset_id: str, stem: str, size: int = 1024):
        import OpenImageIO as oiio

        buf = oiio.ImageBuf(os.path.join(CC0, asset_id, f"{stem}.jpg"))
        spec = buf.spec()
        buf = oiio.ImageBufAlgo.resize(buf, roi=oiio.ROI(0, size, 0, size, 0, 1, 0, spec.nchannels))
        px = buf.get_pixels(oiio.FLOAT)
        lum = px[:, :, :3].mean(axis=2) if px.shape[2] >= 3 else px[:, :, 0]
        lum = srgb_to_lin(lum) if stem == "diff" else lum
        # High-pass: divide by a wide periodic blur so only grain/fractures stay.
        f = np.fft.rfft2(lum)
        ky = np.fft.fftfreq(size)[:, None]
        kx = np.fft.rfftfreq(size)[None, :]
        blur = np.fft.irfft2(f * np.exp(-(kx * kx + ky * ky) * (size / 10.0) ** 2 * 2), s=lum.shape)
        self.map = (lum / np.maximum(blur, 1e-3)).astype(np.float32)
        self.map /= self.map.mean()
        self.size = size

    def sample(self, u, v):
        """Bilinear, wrapping; u, v in tiles."""
        s = self.size
        x = (u % 1.0) * s - 0.5
        y = (1.0 - (v % 1.0)) * s - 0.5
        x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
        fx, fy = x - x0, y - y0
        x0 %= s
        y0 %= s
        x1, y1 = (x0 + 1) % s, (y0 + 1) % s
        m = self.map
        return (m[y0, x0] * (1 - fx) + m[y0, x1] * fx) * (1 - fy) + (m[y1, x0] * (1 - fx) + m[y1, x1] * fx) * fy


_PHOTOS: dict = {}


def photo(asset_id, stem):
    key = (asset_id, stem)
    if key not in _PHOTOS:
        _PHOTOS[key] = Photo(asset_id, stem)
    return _PHOTOS[key]


def triplanar(ph: Photo, P, N, scale, k=None, sharp=4.0, top: Photo | None = None, top_scale=None):
    """World-space triplanar sample; beds (k) shift the side projections
    horizontally so photo block rows never line up across bed boundaries.
    `top` optionally replaces the photo on up/down-facing surfaces."""
    w = np.abs(N) ** sharp
    w /= w.sum(axis=1, keepdims=True) + 1e-9
    x, y, z = P[:, 0] / scale, P[:, 1] / scale, P[:, 2] / scale
    off = rand01(k, seed=77) * 7.3 if k is not None else 0.0
    sx = ph.sample(z + off, y)  # faces looking along x
    sz = ph.sample(x + off, y)  # faces looking along z
    if top is not None:
        ts = top_scale or scale
        sy = top.sample(P[:, 0] / ts, P[:, 2] / ts)
    else:
        sy = ph.sample(x, z)
    return sx * w[:, 0] + sy * w[:, 1] + sz * w[:, 2]


def bed_colour(k, f, P):
    """Base colour of each strata bed (linear RGB)."""
    r1 = rand01(k, seed=301)[:, None]
    r2 = rand01(k, seed=302)[:, None]
    hard = strata.HARD[k][:, None]
    hard_c = MID + (LIGHT - MID) * (0.25 + 0.6 * r1)
    soft_c = SHADOW + (MID - SHADOW) * (0.25 + 0.65 * r1)
    c = soft_c + (hard_c - soft_c) * smoothstep(0.35, 0.7, hard)
    pale = (r2 > 0.9)
    c = np.where(pale, c + (PALE - c) * 0.65, c)
    dark = (r2 < 0.07)
    c = np.where(dark, c + (CAP - c) * 0.7, c)
    # Bed bottoms slightly darker (fine-grained parting), tops a touch lighter.
    grad = 0.92 + 0.12 * smoothstep(0.0, 0.35, f)[:, None]
    return c * grad


def composite(P, N, ao, point, edge, floor_y=0.0, joint=None, cell=None):
    """Returns (colour sRGB 0..1, roughness 0..1) for texels (arrays of n).
    `joint` (1 in a rock joint) and `cell` (random per joint-bounded slab)
    come from the bake's fracture network."""
    N = N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-9)
    k, f = strata.bed_at(P[:, 0], P[:, 1], P[:, 2])
    col = bed_colour(k, f, P)
    # Large, soft colour drift so long walls don't read as one flat tone.
    drift = fbm3(P[:, 0] / 140.0, P[:, 1] / 90.0, P[:, 2] / 140.0, octaves=3, seed=90)
    col = col * (1.0 + 0.16 * drift)[:, None]
    warm = fbm2(P[:, 0] / 260.0, P[:, 2] / 260.0, octaves=2, seed=91)
    col = col * np.stack([1 + 0.05 * warm, 1 - 0.01 * warm, 1 - 0.06 * warm], axis=1)
    # Rock detail: layered sandstone grain + fracture photo.
    slick = photo("rock_face_03", "diff")
    d1 = triplanar(photo("cliff_side", "diff"), P, N, 26.0, k, top=slick, top_scale=34.0)
    d2 = triplanar(slick, P, N, 15.0, k, top=slick, top_scale=6.0)
    d3 = triplanar(photo("cliff_side", "diff"), P, N, 7.5, k, top=photo("gravelly_sand", "diff"), top_scale=9.0)
    detail = 0.45 * d1 + 0.3 * d2 + 0.25 * d3
    steep = 1.0 - smoothstep(0.35, 0.75, np.abs(N[:, 1]))
    gain = 0.75 + 0.35 * (1.0 - steep)  # flat tops need more grain to read
    col = col * np.clip(1.0 + gain * (detail - 1.0), 0.45, 1.7)[:, None]
    if cell is not None:
        # Joint-bounded slabs: each weathers to its own tone, most on the tops.
        col = col * (1.0 + (0.1 + 0.12 * (1.0 - steep)) * (cell - 0.5) * 2.0)[:, None]
    # Desert varnish: dark vertical streaks down steep faces.
    sv = fbm3(P[:, 0] / 3.2, P[:, 1] / 38.0, P[:, 2] / 3.2, octaves=3, seed=95)
    region = smoothstep(-0.1, 0.45, fbm3(P[:, 0] / 60.0, P[:, 1] / 50.0, P[:, 2] / 60.0, octaves=2, seed=96))
    varnish = smoothstep(0.12, 0.45, sv) * region * steep
    col = col + (VARNISH - col) * (0.55 * varnish)[:, None]
    # Crevices dark, convex edges bleached.
    point = 0.5 + (point - np.median(point))  # Cycles pointiness: flat is ~the median
    cav = smoothstep(0.47, 0.35, point)
    convex = smoothstep(0.53, 0.66, point) * smoothstep(0.02, 0.2, edge)
    occl = 0.5 + 0.5 * np.clip(ao, 0, 1) ** 1.2
    col = col * (occl * (1.0 - 0.35 * cav))[:, None]
    col = col + (BLEACH - col) * (0.18 * convex * (0.5 + 0.5 * np.clip(ao, 0, 1)))[:, None]
    if joint is not None:
        # Joints: dark open cracks; on steep faces only in hard beds.
        hardness = smoothstep(0.35, 0.7, strata.HARD[k])
        flat = smoothstep(0.75, 0.95, N[:, 1])
        jw = np.clip(joint, 0.0, 1.0) * (flat + steep * 0.6 * hardness)
        col = col * (1.0 - 0.4 * jw)[:, None]
    # Wind-blown sand on ledge tops and at the foot; rubble on the talus.
    grain = triplanar(photo("gravelly_sand", "diff"), P, N, 6.0)
    up = smoothstep(0.55, 0.92, N[:, 1])
    patch = 0.6 + 0.4 * smoothstep(-0.3, 0.4, fbm2(P[:, 0] / 11.0, P[:, 2] / 11.0, octaves=3, seed=97))
    height = P[:, 1] - floor_y
    foot = smoothstep(2.5, 0.0, height)
    talus = smoothstep(14.0, 3.0, height) * smoothstep(0.25, 0.6, N[:, 1])
    rubble_c = RUBBLE * np.clip(1.0 + 0.9 * (triplanar(photo("rock_face_03", "diff"), P, N, 4.0) - 1.0), 0.5, 1.5)[:, None]
    col = col + (rubble_c - col) * (0.75 * talus)[:, None]
    sand_c = (SAND * 0.35 + DUST * 0.65) * np.clip(1.0 + 0.8 * (grain - 1.0), 0.6, 1.4)[:, None]
    foot_c = SAND * np.clip(1.0 + 0.8 * (grain - 1.0), 0.6, 1.4)[:, None]
    sand_c = sand_c + (foot_c - sand_c) * foot[:, None]
    dusty = np.clip(up * patch * 0.5 * (1.0 - 0.6 * talus) + foot * 0.85, 0.0, 0.95)
    col = col + (sand_c * (0.55 + 0.45 * np.clip(ao, 0, 1))[:, None] - col) * dusty[:, None]
    # Roughness: dry rock ~0.9, varnish a little glossier, sand fully rough.
    rough = 0.88 + 0.06 * (detail - 1.0) - 0.18 * varnish + 0.08 * dusty
    return lin_to_srgb(col), np.clip(rough, 0.55, 1.0)
