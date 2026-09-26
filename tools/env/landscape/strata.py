"""Shared strata model: horizontal sandstone beds that run through every
landscape piece (the canyon's layers line up across the basin).

Used by the shape (each bed becomes a slab with its own outline, hard beds
stand out as ledges) and by the texture (colour ramp), so geometry and
colour agree. Bed boundaries are forced onto the mesa's terrace tops, and
the beds lie flat around the mesa, so squaring the mesa's beds off never
raises a terrace lip (the turret's line of sight depends on them).
"""
from __future__ import annotations

import numpy as np

from noise import fbm2, rand01, smoothstep

BED_SEED = 2604
Y0, Y1 = -40.0, 260.0
# TerrainBuilder.buildMesa terrace tops (8, 22, 38, 50, 60) and ridge tops
# (24, 56) as the live terrain has them (voxelisation: +1.3 on cylinder
# tops, +2.1 on blocks; see ops.INFLATE).
FIXED = (-4.0, 9.3, 23.3, 26.1, 39.3, 51.3, 58.1, 61.3)
FLAT_RADIUS = (110.0, 260.0)  # beds are unwarped inside the first radius, fully warped past the second


def _beds() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Bed bottoms, thicknesses and hardness (0 soft .. 1 hard)."""
    bottoms, thick, hard = [], [], []
    y, k = Y0, 0
    while y < Y1:
        t = 2.6 + 7.5 * float(rand01(np.array(k), seed=BED_SEED)) ** 1.4
        h = float(rand01(np.array(k), seed=BED_SEED + 1))
        if float(rand01(np.array(k), seed=BED_SEED + 2)) > 0.78:  # a thick, hard cliff former
            t *= 1.6
            h = 0.85 + 0.15 * h
        top = y + t
        cut = [b for b in FIXED if y + 1.2 < b < top]
        if cut:
            top = cut[0]
        elif any(0 < b - top < 1.8 for b in FIXED):  # don't leave a sliver below a fixed boundary
            top = min(b for b in FIXED if b > top)
        bottoms.append(y)
        thick.append(top - y)
        hard.append(h)
        y = top
        k += 1
    return np.array(bottoms), np.array(thick), np.array(hard)


BOTTOMS, THICK, HARD = _beds()


def warp(x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Vertical offset of the beds: gentle undulation plus a faint dip,
    faded out around the mesa."""
    w = 3.6 * fbm2(x / 300.0, z / 300.0, octaves=3, seed=11) + 0.0016 * x - 0.0011 * z
    r = np.sqrt(np.asarray(x) ** 2 + np.asarray(z) ** 2)
    return w * smoothstep(FLAT_RADIUS[0], FLAT_RADIUS[1], r)


def bed_at(x: np.ndarray, y: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Bed index and fraction (0 at the bed's bottom, 1 at its top)."""
    yw = y + warp(x, z)
    k = np.clip(np.searchsorted(BOTTOMS, yw, side="right") - 1, 0, len(BOTTOMS) - 1)
    f = np.clip((yw - BOTTOMS[k]) / THICK[k], 0.0, 1.0)
    return k, f


def ledge_profile(k: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Relative protrusion 0..1 of a bed at fraction f: hard beds stand out
    as vertical faces with a weathered shoulder and a sharp undercut base;
    soft beds form a bench that recedes upward to a recess."""
    h = HARD[k]
    hard = np.minimum(1.0, f / 0.05) * (1.0 - 0.55 * np.clip((f - 0.72) / 0.28, 0, 1) ** 1.5)
    soft = 0.42 * (1.0 - f) ** 1.6 + 0.08
    w = np.clip((h - 0.35) / 0.3, 0.0, 1.0)
    return (soft * (1 - w) + hard * w) * (0.35 + 0.65 * h)
