"""2D painting helpers for numpy-painted sheets (flashes, sparks, singles).

Painted frames are premultiplied linear RGBA at CELL * SUPER pixels, like
rendered EXRs, so they go through the same image.process_frame. Emissive
paint leaves alpha at 0; process_frame derives alpha from the emission.

Noise is periodic value noise on a small 3D lattice (quintic fade), so an
fBm sampled with z moving by one lattice period loops seamlessly.
"""
import numpy as np


def lattice(seed, n=16):
    return np.random.default_rng(seed).random((n, n, n), dtype=np.float32)


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def noise3(lat, x, y, z):
    """Smooth value noise in 0..1, periodic with the lattice size."""
    n = lat.shape[0]
    xi, yi, zi = np.floor(x), np.floor(y), np.floor(z)
    u, v, w = _fade(x - xi), _fade(y - yi), _fade(z - zi)
    x0, y0, z0 = xi.astype(np.int64) % n, yi.astype(np.int64) % n, zi.astype(np.int64) % n
    x1, y1, z1 = (x0 + 1) % n, (y0 + 1) % n, (z0 + 1) % n

    def lerp(a, b, t):
        return a + (b - a) * t

    c00 = lerp(lat[x0, y0, z0], lat[x1, y0, z0], u)
    c10 = lerp(lat[x0, y1, z0], lat[x1, y1, z0], u)
    c01 = lerp(lat[x0, y0, z1], lat[x1, y0, z1], u)
    c11 = lerp(lat[x0, y1, z1], lat[x1, y1, z1], u)
    return lerp(lerp(c00, c10, v), lerp(c01, c11, v), w)


def fbm(lat, x, y, z=0.0, octaves=5, gain=0.5):
    """Fractal sum normalised to roughly 0..1 (mean 0.5)."""
    total = np.zeros(np.broadcast(x, y).shape, dtype=np.float32)
    amp, norm, freq = 1.0, 0.0, 1.0
    z = np.broadcast_to(np.asarray(z, dtype=np.float32), total.shape)
    for _ in range(octaves):
        total += amp * noise3(lat, x * freq, y * freq, z * freq)
        norm += amp
        amp *= gain
        freq *= 2.0
    return total / norm


def contrast(v, lo, hi):
    """Smoothstep remap of v from [lo, hi] to [0, 1]."""
    t = np.clip((v - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def grid(size):
    """Pixel-centre coordinates in -1..1 (x right, y up) for a size x size frame."""
    c = (np.arange(size, dtype=np.float32) + 0.5) / size * 2.0 - 1.0
    x, y = np.meshgrid(c, -c)
    return x, y


def emissive(intensity, color):
    """Premultiplied RGBA from an intensity map and a linear RGB colour."""
    out = np.zeros(intensity.shape + (4,), dtype=np.float32)
    out[..., :3] = intensity[..., None] * np.asarray(color, dtype=np.float32)
    return out


def segment_glow(x, y, p0, p1, width):
    """Gaussian glow around the segment p0-p1 (coordinates in -1..1)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    seg2 = dx * dx + dy * dy
    if seg2 < 1e-12:
        d2 = (x - p0[0]) ** 2 + (y - p0[1]) ** 2
    else:
        t = np.clip(((x - p0[0]) * dx + (y - p0[1]) * dy) / seg2, 0.0, 1.0)
        d2 = (x - p0[0] - t * dx) ** 2 + (y - p0[1] - t * dy) ** 2
    return np.exp(-d2 / (width * width))


def jet(x, y, origin, direction, length, w0, w1):
    """A tapered flame cone from origin along direction (unit), fading to its tip."""
    dx, dy = direction
    rx, ry = x - origin[0], y - origin[1]
    u = (rx * dx + ry * dy) / length
    v = rx * -dy + ry * dx
    uc = np.clip(u, 0.0, 1.0)
    width = w0 + (w1 - w0) * uc
    soft_start = np.clip(u / 0.08 + 1.0, 0.0, 1.0)
    return np.exp(-(v / width) ** 2) * (1.0 - uc) ** 1.3 * soft_start
