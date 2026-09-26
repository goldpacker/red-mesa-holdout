"""Sparks: a burst of hot metal sparks (OneShot), colour baked in.

Sparks leave the centre with drag and gravity, drawn as motion-blurred
streaks that cool from white-yellow to orange-red and die at different ages.
A short glow marks the impact in the first frames. Emitters usually spawn it
at the hit point facing the camera.
"""
import math

import numpy as np

from vfxlib import paint as P

HOT = (1.0, 0.46, 0.12)
COUNT = 64
DRAG = 2.6
GRAVITY = 2.4
BLUR = 0.065


class State:
    def __init__(self, size):
        self.x, self.y = P.grid(size)
        self.r = np.hypot(self.x, self.y)
        rng = np.random.default_rng(404)
        ang = math.pi / 2.0 + rng.normal(0.0, 1.05, COUNT)
        speed = rng.uniform(0.8, 2.3, COUNT) * np.where(rng.random(COUNT) < 0.2, 0.55, 1.0)
        self.v = np.stack([np.cos(ang) * speed, np.sin(ang) * speed], axis=1)
        self.life = rng.uniform(0.3, 1.0, COUNT)
        self.delay = rng.uniform(0.0, 0.05, COUNT)
        self.heat = rng.uniform(0.7, 1.2, COUNT)
        self.width = rng.uniform(0.01, 0.016, COUNT)
        self.size = size


def prepare(name, size):
    return State(size)


def _pos(v, tau):
    e = math.exp(-DRAG * tau)
    x = v[0] * (1.0 - e) / DRAG
    y = v[1] * (1.0 - e) / DRAG - GRAVITY / DRAG * (tau - (1.0 - e) / DRAG)
    return x, y


def paint(name, i, t, size, st):
    glow = np.zeros_like(st.x)
    for k in range(COUNT):
        tau = t - st.delay[k]
        if tau <= 0.0 or tau >= st.life[k]:
            continue
        age = tau / st.life[k]
        head = _pos(st.v[k], tau)
        tail = _pos(st.v[k], max(tau - BLUR, 0.0))
        fade = (1.0 - age) ** 0.9 * min(1.0, 1.2 - math.hypot(*head))
        if fade <= 0.0:
            continue
        glow += P.segment_glow(st.x, st.y, tail, head, st.width[k]) * fade * st.heat[k] * 4.0
    flash = max(0.0, 1.0 - t / 0.09)
    glow += 3.0 * flash * np.exp(-(st.r / 0.12) ** 2) + 0.6 * flash * np.exp(-(st.r / 0.3) ** 2)
    return P.emissive(glow, HOT)
