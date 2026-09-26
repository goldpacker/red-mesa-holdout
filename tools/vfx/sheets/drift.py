"""Painted sheet added for VFX-3 motion dust.

DustDrift  OneShot soft dust cloud for trails behind wheels and tracks, rotor
           downwash and the jet's wake. Unlike DustPuff (a compact billow with
           a defined silhouette, right for impacts) it has no edge at all: a
           wide Gaussian body broken up by domain-warped fBm wisps, a little
           wider than tall and denser low down, that spreads and thins away.
           Many overlapping particles merge into one continuous haze instead
           of reading as a string of separate puffs. Greyscale, lit from above
           (the emitter's Color tints it to the ground); centred.
"""
import numpy as np

from vfxlib import paint as P


class _Drift:
    def __init__(self, size):
        self.x, self.y = P.grid(size)
        self.lat = P.lattice(211, 16)
        self.lat2 = P.lattice(223, 16)


def _drift(t, st):
    x, y = st.x, st.y
    grow = 1.0 - (1.0 - t) ** 2.0
    radius = 0.72 + 0.24 * grow
    cy = -0.04 + 0.05 * t
    # Gentle domain warp (off the lattice planes, which show as creases).
    wx = P.fbm(st.lat2, x * 1.7 + 3.13, y * 1.7 - t * 0.4 + 0.29, 1.37 + t * 0.6, octaves=4) - 0.5
    wy = P.fbm(st.lat2, x * 1.7 - 2.31, y * 1.7 + 1.71, 5.41 + t * 0.6, octaves=4) - 0.5
    u, v = x + wx * 0.22, y + wy * 0.22
    q2 = ((u * 0.95) ** 2 + ((v - cy) * 1.12) ** 2) / (radius * radius)
    # Compact soft bump: no silhouette, reaches zero inside the cell.
    body = np.clip(1.0 - q2, 0.0, 1.0) ** 1.25
    n = P.fbm(st.lat, u * 2.3 + 0.71, v * 2.3 - t * 0.6 + 0.43, 2.37 + t * 0.8, octaves=5)
    density = body * (0.75 + 0.9 * (n - 0.5)) * 1.45
    # Denser low down (dust hangs near the ground), thinner at the crown.
    density *= 0.85 + 0.3 * P.contrast(cy - v, -0.6, 0.6)
    density = np.clip(density, 0.0, 1.0)
    alpha = density * min(1.0, t / 0.05 + 0.3) * (1.0 - t) ** 1.1
    value = 0.68 + 0.22 * P.contrast(v - cy, -radius, radius) + 0.1 * (n - 0.5)
    out = np.zeros(x.shape + (4,), dtype=np.float32)
    out[..., :3] = (np.clip(value, 0.0, 1.0) * alpha)[..., None]
    out[..., 3] = np.clip(alpha, 0.0, 1.0)
    return out


def prepare(name, size):
    return _Drift(size)


def paint(name, i, t, size, st):
    return _drift(t, st)
