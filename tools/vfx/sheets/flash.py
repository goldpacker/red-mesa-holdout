"""Painted emissive sheets: three muzzle flashes and a looping rocket exhaust.

MuzzleFlashFront  64 variants of a star flash seen down the barrel (4-6 prongs).
MuzzleFlashSide   64 variants of a flash seen from the side, pointing up the
                  texture; the muzzle sits 22.5% of the frame below centre.
MuzzleFlashBurst  64 variants of a round launch/cannon blast (many licks).
RocketExhaust     64-frame seamless loop of a flame plume; nozzle 35% below
                  centre, flame tail towards the top.
Colour is baked (hot white-yellow core, orange edges); alpha comes from
emission in image.process_frame.
"""
import math

import numpy as np

from vfxlib import paint as P

FLAME = (1.0, 0.4, 0.1)
BLAST = (1.0, 0.36, 0.08)


class State:
    def __init__(self, size):
        self.x, self.y = P.grid(size)
        self.r = np.hypot(self.x, self.y)
        self.th = np.arctan2(self.y, self.x)
        self.lat = P.lattice(7, 16)


def prepare(name, size):
    return State(size)


def paint(name, i, t, size, st):
    fn = {"MuzzleFlashFront": _front, "MuzzleFlashSide": _side,
          "MuzzleFlashBurst": _burst, "RocketExhaust": _exhaust}[name]
    return fn(i, st)


def _wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _prongs(st, rng, count, rot, length, width, weight, jitter=0.12):
    out = np.zeros_like(st.r)
    for j in range(count):
        ang = rot + j * 2.0 * math.pi / count + rng.normal(0.0, jitter)
        L = rng.uniform(*length)
        w0 = rng.uniform(*width)
        d = _wrap(st.th - ang)
        s = np.clip(st.r / L, 0.0, 1.0)
        w = w0 * (1.0 - 0.8 * s) + 0.015
        out += np.exp(-(d / w) ** 2) * (1.0 - s) ** 1.2 * rng.uniform(0.65, 1.0) * weight
    return out


def _polar_streaks(st, seed, spokes, radial):
    """fBm on a cylinder: varies around the circle and slowly along the radius."""
    return P.fbm(st.lat, np.cos(st.th) * spokes + seed + 0.31, np.sin(st.th) * spokes + 0.43, st.r * radial + seed,
                 octaves=4)


def _front(i, st):
    rng = np.random.default_rng(1000 + i)
    count = int(rng.choice([4, 5, 6], p=[0.45, 0.35, 0.2]))
    rot = rng.uniform(0.0, 2.0 * math.pi)
    petals = _prongs(st, rng, count, rot, (0.62, 0.95), (0.13, 0.22), 1.0)
    petals += _prongs(st, rng, count, rot + math.pi / count, (0.28, 0.48), (0.16, 0.26), 0.6)
    cloud = P.fbm(st.lat, st.x * 4.0 + i * 0.7, st.y * 4.0, i * 1.37)
    streak = _polar_streaks(st, i * 0.53, 3.5, 2.0)
    core = 2.4 * np.exp(-(st.r / 0.1) ** 2) + 0.4 * np.exp(-(st.r / 0.26) ** 2)
    body = petals * (0.3 + 1.0 * cloud) * (0.45 + 0.9 * streak)
    return P.emissive((core + body) * rng.uniform(2.4, 3.0), FLAME)


def _side(i, st):
    rng = np.random.default_rng(2000 + i)
    y0 = -0.45
    length = rng.uniform(1.0, 1.32)
    s = (st.y - y0) / length
    sc = np.clip(s, 0.0, 1.0)
    wmax = rng.uniform(0.11, 0.17)
    width = 0.03 + wmax * np.sin(math.pi * np.clip(sc * 0.85 + 0.08, 0.0, 1.0)) ** 1.2
    lean = rng.normal(0.0, 0.03) * sc
    main = np.exp(-((st.x - lean) / width) ** 2) * (1.0 - sc) ** 0.8 * (s > -0.02)
    tongues = P.fbm(st.lat, st.x * 9.0 + i * 0.31, st.y * 1.8 - i * 0.9, i * 0.77)
    main *= 0.12 + 1.3 * P.contrast(tongues, 0.33, 0.68)
    jets = np.zeros_like(st.x)
    for side in (-1.0, 1.0):
        ang = math.radians(rng.uniform(58.0, 75.0))
        jet_len = rng.uniform(0.2, 0.34)
        direction = (side * math.sin(ang), math.cos(ang))
        jets += P.jet(st.x, st.y, (0.0, y0 + 0.04), direction, jet_len, 0.03, 0.09) * rng.uniform(0.5, 0.9)
    jets *= 0.45 + 1.1 * P.contrast(P.fbm(st.lat, st.x * 8.0, st.y * 8.0 + i, i * 0.5, octaves=4), 0.3, 0.7)
    core = 2.0 * np.exp(-((st.x / 0.06) ** 2 + ((st.y - y0 - 0.16) / 0.24) ** 2))
    back = 0.4 * np.exp(-((st.x / 0.1) ** 2 + ((st.y - y0 + 0.01) / 0.05) ** 2))
    return P.emissive((core + back + main * 1.3 + jets * 1.9) * rng.uniform(2.4, 3.0), FLAME)


def _burst(i, st):
    rng = np.random.default_rng(3000 + i)
    rot = rng.uniform(0.0, 2.0 * math.pi)
    licks = _prongs(st, rng, int(rng.integers(9, 14)), rot, (0.5, 0.92), (0.1, 0.2), 0.75, jitter=0.2)
    radius = 0.5 + 0.08 * (_polar_streaks(st, i * 0.29, 2.0, 0.0) - 0.5) * 4.0
    ball = np.clip(1.0 - st.r / np.maximum(radius, 0.1), 0.0, 1.0) ** 0.8
    cloud = P.fbm(st.lat, st.x * 3.5 + i * 0.41, st.y * 3.5, i * 1.13)
    body = (ball * 1.1 + licks) * (0.25 + 1.1 * cloud)
    core = 2.0 * np.exp(-(st.r / 0.18) ** 2)
    return P.emissive((core + body) * rng.uniform(2.3, 2.9), BLAST)


def _exhaust(i, st):
    tl = i / 64.0                                  # loop phase: frame 64 == frame 0
    y0 = -0.7
    length = 1.42 * (1.0 + 0.06 * math.sin(2.0 * math.pi * tl * 6.0))
    s = (st.y - y0) / length
    sc = np.clip(s, 0.0, 1.0)
    width = 0.1 + 0.36 * sc ** 0.5 * (1.0 - sc ** 2.5)
    turb = P.fbm(st.lat, st.x * 4.5, st.y * 2.4 - 32.0 * tl, 16.0 * tl)
    wobble = (P.fbm(st.lat, 3.0 + 0.0 * st.x, st.y * 1.2 - 16.0 * tl, 16.0 * tl + 5.0, octaves=3) - 0.5) * 0.12 * sc
    plume = np.exp(-((st.x - wobble) / width) ** 2) * (1.0 - sc) ** 1.1 * (s > -0.03)
    plume *= 0.2 + 1.2 * P.contrast(turb, 0.25, 0.75)
    diamonds = 0.8 + 0.2 * np.cos(2.0 * math.pi * sc / 0.13) ** 2
    core = np.exp(-(st.x / (0.045 + 0.07 * sc)) ** 2) * np.exp(-sc / 0.3) * diamonds * (s > -0.02)
    nozzle = np.exp(-((st.x / 0.1) ** 2 + ((st.y - y0) / 0.06) ** 2))
    return P.emissive(plume * 1.5 + core * 5.0 + nozzle * 1.5, FLAME)
