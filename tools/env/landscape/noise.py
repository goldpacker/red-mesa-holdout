"""Small vectorised noise library (numpy) for the landscape shapes and textures.

Deterministic lattice value noise with quintic interpolation, fbm and
ridged variants, plus a hash for per-index random numbers (strata beds).
All inputs are float arrays in studs divided by the caller's scale.
"""
from __future__ import annotations

import numpy as np

_M = np.uint32(0x9E3779B1)


def hash_u32(*ints: np.ndarray, seed: int = 0) -> np.ndarray:
    """Well-mixed uint32 hash of integer lattice coordinates."""
    h = np.full(np.shape(ints[0]), np.uint32((seed * 0x85EBCA6B + 0x27D4EB2F) & 0xFFFFFFFF), dtype=np.uint32)
    with np.errstate(over="ignore"):
        for i in ints:
            h ^= np.asarray(i).astype(np.int64).astype(np.uint32) * _M
            h = (h << np.uint32(13)) | (h >> np.uint32(19))
            h *= np.uint32(0x85EBCA6B)
            h ^= h >> np.uint32(16)
            h *= np.uint32(0xC2B2AE35)
            h ^= h >> np.uint32(13)
    return h


def rand01(*ints: np.ndarray, seed: int = 0) -> np.ndarray:
    return hash_u32(*ints, seed=seed).astype(np.float64) / 4294967295.0


def _fade(t: np.ndarray) -> np.ndarray:
    return t * t * t * (t * (t * 6 - 15) + 10)


def value2(x: np.ndarray, y: np.ndarray, seed: int = 0) -> np.ndarray:
    """2D value noise in [-1, 1]."""
    xi, yi = np.floor(x), np.floor(y)
    fx, fy = _fade(x - xi), _fade(y - yi)
    xi, yi = xi.astype(np.int64), yi.astype(np.int64)
    a = rand01(xi, yi, seed=seed)
    b = rand01(xi + 1, yi, seed=seed)
    c = rand01(xi, yi + 1, seed=seed)
    d = rand01(xi + 1, yi + 1, seed=seed)
    v = (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy
    return v * 2 - 1


def value3(x: np.ndarray, y: np.ndarray, z: np.ndarray, seed: int = 0) -> np.ndarray:
    """3D value noise in [-1, 1]."""
    xi, yi, zi = np.floor(x), np.floor(y), np.floor(z)
    fx, fy, fz = _fade(x - xi), _fade(y - yi), _fade(z - zi)
    xi, yi, zi = xi.astype(np.int64), yi.astype(np.int64), zi.astype(np.int64)
    out = 0.0
    for dx in (0, 1):
        wx = fx if dx else 1 - fx
        for dy in (0, 1):
            wy = fy if dy else 1 - fy
            for dz in (0, 1):
                wz = fz if dz else 1 - fz
                out = out + rand01(xi + dx, yi + dy, zi + dz, seed=seed) * wx * wy * wz
    return out * 2 - 1


def fbm2(x, y, octaves=4, lacunarity=2.0, gain=0.5, seed=0):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total = total + value2(x, y, seed=seed + o * 101) * amp
        norm += amp
        x, y = x * lacunarity, y * lacunarity
        amp *= gain
    return total / norm


def fbm3(x, y, z, octaves=4, lacunarity=2.0, gain=0.5, seed=0):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total = total + value3(x, y, z, seed=seed + o * 101) * amp
        norm += amp
        x, y, z = x * lacunarity, y * lacunarity, z * lacunarity
        amp *= gain
    return total / norm


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)
