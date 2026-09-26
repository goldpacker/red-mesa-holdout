"""Painted sheets added for VFX-2: a looping fire and a rock-chip burst.

Flames     64-frame seamless loop of a licking fire (burning wrecks, the
           emplacement at defeat, crashing aircraft). Base line 39% of the
           frame below centre (anchor 0.89 down), tongues rise and break off
           towards the top. Colour baked: white-yellow core at the base,
           orange body, dark red tips (via the exp tone map of one hue).
RockChips  OneShot burst for bullet hits on rock: dark motion-blurred chips
           thrown up and out under gravity, and a dust cloud that swells and
           thins. Greyscale (emitter Color tints it to the rock); centred.
"""
import math

import numpy as np

from vfxlib import paint as P

FLAME_HOT = np.array((1.0, 0.5, 0.14), dtype=np.float32)
FLAME_COOL = np.array((1.0, 0.2, 0.04), dtype=np.float32)
BASE_Y = -0.8
HEIGHT = 1.72


class _Flames:
    def __init__(self, size):
        self.x, self.y = P.grid(size)
        self.lat = P.lattice(71, 16)
        self.lat2 = P.lattice(73, 16)


def _flames(i, st):
    tl = i / 64.0  # loop phase: frame 64 == frame 0
    x, y = st.x, st.y
    s = (y - BASE_Y) / HEIGHT
    sc = np.clip(s, 0.0, 1.0)
    # Slow sway of the column and a wavy warp that bends the tongues.
    sway = (P.fbm(st.lat2, 2.0 + 0.0 * x, y * 0.9 - 16.0 * tl, 16.0 * tl + 3.0, octaves=3) - 0.5) * 0.4 * sc
    warp = (P.fbm(st.lat2, x * 2.2 + 5.0, y * 1.6 - 16.0 * tl, 16.0 * tl + 9.0, octaves=3) - 0.5) * 0.34 * sc
    xs = x - sway - warp
    width = 0.07 + 0.4 * (1.0 - sc) ** 0.8 * np.clip(0.45 + sc * 6.0, 0.0, 1.0)
    shape = np.exp(-(xs / width) ** 2)
    # Rising turbulence (y and z both move one lattice period per loop);
    # finer across than along, so it breaks into vertical tongues.
    n = P.fbm(st.lat, xs * 4.6 + 0.37, y * 2.1 - 16.0 * tl, 16.0 * tl, octaves=5)
    heat = shape * (1.0 - sc) ** 0.9
    field = n * 1.3 + heat * 0.85 - 0.66 - 0.5 * sc
    fire = P.contrast(field, 0.0, 0.2) * shape**0.3
    fire *= P.contrast(s, -0.04, 0.12) * (s < 1.02)
    inner = P.fbm(st.lat2, xs * 6.0 + 1.7, y * 3.0 - 32.0 * tl, 16.0 * tl + 5.0, octaves=4)
    intensity = fire * (0.22 + 1.9 * heat**2.2) * (0.55 + 0.8 * inner)
    # Hue cools from yellow-orange in the hot core to red at the tips.
    k = np.clip(heat * 1.3, 0.0, 1.0)[..., None] ** 1.5
    colour = FLAME_COOL * (1.0 - k) + FLAME_HOT * k
    out = np.zeros(x.shape + (4,), dtype=np.float32)
    out[..., :3] = intensity[..., None] * colour
    return out


# ---------------------------------------------------------------- rock chips

CHIPS = 40
DRAG = 3.2
GRAVITY = 5.0


class _Chips:
    def __init__(self, size):
        self.x, self.y = P.grid(size)
        self.r = np.hypot(self.x, self.y)
        self.lat = P.lattice(83, 16)
        rng = np.random.default_rng(907)
        ang = math.pi / 2.0 + rng.normal(0.0, 0.9, CHIPS)          # mostly upwards
        speed = rng.uniform(2.2, 5.0, CHIPS) * np.where(rng.random(CHIPS) < 0.3, 0.5, 1.0)
        self.v = np.stack([np.cos(ang) * speed, np.sin(ang) * speed], axis=1)
        self.size = rng.uniform(0.008, 0.018, CHIPS) * np.where(rng.random(CHIPS) < 0.2, 1.8, 1.0)
        self.value = rng.uniform(0.16, 0.34, CHIPS)
        self.life = rng.uniform(0.35, 0.8, CHIPS)


def _pos(v, tau):
    e = math.exp(-DRAG * tau)
    x = v[0] * (1.0 - e) / DRAG
    y = v[1] * (1.0 - e) / DRAG - GRAVITY / DRAG * (tau - (1.0 - e) / DRAG) - 0.12
    return x, y


def _chips(i, t, st):
    rgb = np.zeros_like(st.x)
    alpha = np.zeros_like(st.x)
    # Dust cloud: swells from the hit, drifts up a little and thins away.
    grow = 1.0 - (1.0 - min(t / 0.4, 1.0)) ** 2.4
    radius = 0.12 + 0.55 * grow
    cy = -0.12 + 0.1 * t
    d = np.hypot(st.x, (st.y - cy) * 1.15) / radius
    billow = P.fbm(st.lat, st.x * 3.4 + 1.3, st.y * 3.4 - t * 1.5, 2.0 + t * 1.2, octaves=5)
    cloud = P.contrast(1.0 - d + (billow - 0.5) * 1.1, 0.0, 0.45)
    dust_a = cloud * 0.85 * (1.0 - t) ** 1.6 * min(1.0, t / 0.03 + 0.3)
    dust_v = 0.62 + 0.3 * P.contrast(st.y - cy, -0.3, 0.4) + 0.15 * (billow - 0.5)
    rgb += dust_v * dust_a
    alpha += dust_a
    # Chips: dark, slightly motion-blurred, lit from above.
    for k in range(CHIPS):
        if t >= st.life[k]:
            continue
        head = _pos(st.v[k], t)
        tail = _pos(st.v[k], max(t - 0.05, 0.0))
        fade = min(1.0, (st.life[k] - t) / 0.12)
        if abs(head[0]) > 0.92 or abs(head[1]) > 0.92:
            continue
        m = P.segment_glow(st.x, st.y, tail, head, st.size[k])
        m = np.clip(m * 2.2, 0.0, 1.0) * fade
        lit = st.value[k] * (1.0 + 0.6 * np.clip((st.y - head[1]) / st.size[k], -1.0, 1.0))
        rgb = rgb * (1.0 - m) + lit * m
        alpha = alpha * (1.0 - m) + m
    out = np.zeros(st.x.shape + (4,), dtype=np.float32)
    out[..., :3] = np.clip(rgb, 0.0, 1.0)[..., None]
    out[..., 3] = np.clip(alpha, 0.0, 1.0)
    return out


def prepare(name, size):
    return _Flames(size) if name == "Flames" else _Chips(size)


def paint(name, i, t, size, st):
    if name == "Flames":
        return _flames(i, st)
    return _chips(i, t, st)
