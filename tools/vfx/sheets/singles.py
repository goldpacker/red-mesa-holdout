"""Single textures for VFX-2: tracer beam, shockwave ring, ground scorch.

Each returns straight-alpha RGBA with sRGB colour (0..1). Colour is defined
for every pixel (no black under transparent areas), and alpha reaches 0
before the image border.

TracerBeam     512x128 Beam texture: U (x) runs along the beam and tiles;
               V (y) across it: white-hot core, soft falloff. White, so the
               Beam's Color tints it (ours amber, enemy red).
ShockwaveRing  1024x1024 top-down ring: sharp outer front at 80% radius,
               soft trailing inner falloff, streaky breakup. White (tinted).
ScorchMark     512x512 top-down burn decal, colour baked (charred centre,
               brown burnt edge, radial splatter). Drawn at 1024 and box-
               downsampled (RECLAIM-HS, QA-B item 2: decals are uncompressed
               RGBA8, and a <= 20-stud scorch seen from >= 60 studs never
               needs more).
"""
import numpy as np

from vfxlib import image
from vfxlib import paint as P


def single(name):
    return {"TracerBeam": _tracer, "ShockwaveRing": _ring, "ScorchMark": _scorch}[name]()


def _rgba(rgb_srgb, alpha):
    out = np.empty(alpha.shape + (4,), dtype=np.float32)
    out[..., :3] = rgb_srgb
    out[..., 3] = np.clip(alpha, 0.0, 1.0)
    return out


def _tracer():
    w, h = 512, 128
    u = (np.arange(w, dtype=np.float32) + 0.5) / w
    v = (np.arange(h, dtype=np.float32) + 0.5) / h * 2.0 - 1.0
    uu, vv = np.meshgrid(u, v)
    lat = P.lattice(31, 16)
    shimmer = P.fbm(lat, uu * 16.0, np.zeros_like(uu) + 3.0, 0.0, octaves=3)  # period 16 = tiles in U
    core = np.exp(-(vv / 0.07) ** 2)
    halo = 0.5 * np.exp(-(vv / 0.3) ** 2) * (0.85 + 0.3 * (shimmer - 0.5))
    alpha = np.minimum(core + halo, 1.0) * np.clip((1.0 - np.abs(vv)) / 0.08, 0.0, 1.0)
    return _rgba(np.ones((h, w, 3), dtype=np.float32), alpha)


def _polar(size):
    x, y = P.grid(size)
    return x, y, np.hypot(x, y), np.arctan2(y, x)


def _ring():
    size = 1024
    x, y, r, th = _polar(size)
    lat = P.lattice(47, 16)
    radius = 0.8
    outer = 1.0 - P.contrast(r, radius - 0.005, radius + 0.045)
    inner = np.exp(-np.maximum(radius - r, 0.0) / 0.075)
    streaks = P.fbm(lat, np.cos(th) * 7.0 + 0.37, np.sin(th) * 7.0 + 0.61, r * 1.5, octaves=5)
    breakup = 0.45 + 0.9 * P.contrast(streaks, 0.3, 0.72)
    alpha = outer * inner * breakup * 0.95 + 0.035 * outer * (r < radius)
    alpha *= 1.0 - P.contrast(r, 0.9, 0.97)
    return _rgba(np.ones((size, size, 3), dtype=np.float32), alpha)


def _scorch():
    size = 1024
    x, y, r, th = _polar(size)
    lat = P.lattice(59, 16)
    edge = 0.62 * (0.8 + 0.4 * P.fbm(lat, np.cos(th) * 2.5 + 0.41, np.sin(th) * 2.5 + 0.29, 4.0, octaves=4))
    rr = r / edge
    body = 1.0 - P.contrast(rr, 0.55, 1.05)
    spokes = P.fbm(lat, np.cos(th) * 12.0 + 0.23, np.sin(th) * 12.0 + 0.57, r * 0.8 + 9.0, octaves=4)
    rays = P.contrast(spokes, 0.52, 0.78) * P.contrast(r, 0.3, 0.55) * (1.0 - P.contrast(r, 0.62, 0.93))
    mottle = P.fbm(lat, x * 7.0, y * 7.0, 2.0, octaves=6)
    patches = P.contrast(mottle, 0.35, 0.65)
    grain = P.fbm(lat, x * 40.0, y * 40.0, 7.0, octaves=2)
    body = body * (0.86 + 0.2 * patches)
    alpha = np.maximum(body, rays * 0.5) * (0.9 + 0.1 * grain) * (1.0 - P.contrast(r, 0.9, 0.97))

    char = image.hex_rgb("#141210")
    burnt = image.hex_rgb("#2B2119")
    edge_col = image.hex_rgb("#4A3525")
    heat = np.clip(1.0 - rr, 0.0, 1.0)[..., None]
    rgb = edge_col * (1 - heat) + burnt * heat
    rgb = rgb * (1 - heat ** 2) + char * heat ** 2
    rgb = rgb * (0.78 + 0.34 * patches[..., None]) * (0.9 + 0.2 * grain[..., None])
    return image.downsample(_rgba(np.clip(rgb, 0.0, 1.0), alpha), 2)  # 512² (RECLAIM-HS)
