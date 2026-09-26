"""Tileable texture helpers for the environment textures.

Runs on Blender's bundled Python (numpy + OpenImageIO), see tools/env/py.sh.
Every operation that looks at neighbours wraps around the image edges, so
a seamless input stays seamless. Images are float32 HxWxC arrays in [0, 1].
"""
import numpy as np
import OpenImageIO as oiio


# ---------------------------------------------------------------- image IO
def load(path: str) -> np.ndarray:
    buf = oiio.ImageBuf(path)
    px = buf.get_pixels(oiio.FLOAT)
    if px is None:
        raise RuntimeError(f"cannot read {path}: {buf.geterror()}")
    if px.ndim == 2:
        px = px[..., None]
    return np.ascontiguousarray(px, dtype=np.float32)


def save(path: str, img: np.ndarray, bits: int = 8) -> None:
    img = np.clip(img, 0.0, 1.0).astype(np.float32)
    if img.ndim == 2:
        img = img[..., None]
    h, w, c = img.shape
    spec = oiio.ImageSpec(w, h, c, oiio.UINT8 if bits == 8 else oiio.UINT16)
    buf = oiio.ImageBuf(spec)
    buf.set_pixels(oiio.ROI(0, w, 0, h, 0, 1, 0, c), img)
    if not buf.write(path):
        raise RuntimeError(f"cannot write {path}: {buf.geterror()}")


def gray(img: np.ndarray) -> np.ndarray:
    return img[..., 0] if img.ndim == 3 else img


# ---------------------------------------------------------------- colour
def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(c: np.ndarray) -> np.ndarray:
    c = np.clip(c, 0.0, None)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def hex_rgb(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)


def luminance(lin: np.ndarray) -> np.ndarray:
    return lin[..., 0] * 0.2126 + lin[..., 1] * 0.7152 + lin[..., 2] * 0.0722


def mean_srgb(img_srgb: np.ndarray) -> str:
    """Mean colour (averaged in linear light) as a hex string."""
    m = linear_to_srgb(srgb_to_linear(img_srgb[..., :3]).reshape(-1, 3).mean(0))
    return "#" + "".join(f"{int(round(v * 255)):02X}" for v in m)


def recolor(src_srgb: np.ndarray, target_hex: str, contrast: float = 1.0,
            chroma_keep: float = 0.3, flatten_sigma: float = 0.0) -> np.ndarray:
    """Re-tints a photo texture to a palette colour, keeping its detail.

    The result's mean (linear) equals the target; luminance detail is
    scaled by `contrast`; `chroma_keep` keeps that fraction of the source's
    own colour variation. `flatten_sigma` (px) removes large-scale
    brightness drift (photo lighting) before re-tinting.
    """
    lin = srgb_to_linear(src_srgb[..., :3])
    y = luminance(lin) + 1e-4
    if flatten_sigma > 0:
        y = y / blur(y, flatten_sigma) * y.mean()
    d = y / y.mean()
    d = np.power(d, contrast)
    d = d / d.mean()
    chroma = lin / y[..., None]
    chroma = chroma / chroma.reshape(-1, 3).mean(0)
    chroma = 1.0 + (chroma - 1.0) * chroma_keep
    target = srgb_to_linear(hex_rgb(target_hex))
    out = target[None, None, :] * d[..., None] * chroma
    out = out * (target / out.reshape(-1, 3).mean(0))[None, None, :]
    return linear_to_srgb(out)


def tint(srgb: np.ndarray, factor: np.ndarray) -> np.ndarray:
    """Multiplies linear colour by a per-pixel factor (HxW or HxWx3)."""
    lin = srgb_to_linear(srgb[..., :3])
    if factor.ndim == 2:
        factor = factor[..., None]
    return linear_to_srgb(lin * factor)


def mix(a: np.ndarray, b: np.ndarray, t) -> np.ndarray:
    t = np.asarray(t, dtype=np.float32)
    if t.ndim == 2 and a.ndim == 3:
        t = t[..., None]
    return a + (b - a) * t


# ---------------------------------------------------------------- resampling
def downsample(img: np.ndarray, size: int) -> np.ndarray:
    """Box downsample by an integer factor (tile-safe)."""
    h, w = img.shape[:2]
    f = h // size
    assert h == w and h % size == 0, (h, w, size)
    return img.reshape(size, f, size, f, -1).mean(axis=(1, 3))


def resample(img: np.ndarray, size: int) -> np.ndarray:
    """Periodic Fourier resample of a tileable image to size x size."""
    h, w = img.shape[:2]
    out = np.empty((size, size, img.shape[2]), dtype=np.float32)
    for ch in range(img.shape[2]):
        f = np.fft.fftshift(np.fft.fft2(img[..., ch]))
        cy, cx = h // 2, w // 2
        r = size // 2
        g = np.zeros((size, size), dtype=np.complex128)
        ys, ye = max(cy - r, 0), min(cy + r, h)
        xs, xe = max(cx - r, 0), min(cx + r, w)
        g[r - (cy - ys):r + (ye - cy), r - (cx - xs):r + (xe - cx)] = f[ys:ye, xs:xe]
        out[..., ch] = np.real(np.fft.ifft2(np.fft.ifftshift(g))) * (size * size) / (h * w)
    return out


def rot90(img: np.ndarray, k: int = 1) -> np.ndarray:
    return np.ascontiguousarray(np.rot90(img, k, axes=(0, 1)))


# ---------------------------------------------------------------- periodic noise and filters
def _freq(n: int):
    fy = np.fft.fftfreq(n)[:, None]
    fx = np.fft.fftfreq(n)[None, :]
    return fy, fx


def blur(a: np.ndarray, sigma: float) -> np.ndarray:
    """Periodic Gaussian blur of an HxW array (sigma in px)."""
    n = a.shape[0]
    fy, fx = _freq(n)
    k = np.exp(-2 * (np.pi * sigma) ** 2 * (fx ** 2 + fy ** 2))
    return np.real(np.fft.ifft2(np.fft.fft2(a) * k)).astype(np.float32)


def blur_aniso(a: np.ndarray, sigma_x: float, sigma_y: float) -> np.ndarray:
    """Periodic anisotropic Gaussian blur (HxW or HxWxC), sigmas in px."""
    n = a.shape[0]
    fy, fx = _freq(n)
    k = np.exp(-2 * np.pi ** 2 * ((sigma_x * fx) ** 2 + (sigma_y * fy) ** 2))
    if a.ndim == 2:
        return np.real(np.fft.ifft2(np.fft.fft2(a) * k)).astype(np.float32)
    return np.stack([np.real(np.fft.ifft2(np.fft.fft2(a[..., c]) * k)) for c in range(a.shape[2])], axis=-1).astype(np.float32)


def fbm(n: int, seed: int, beta: float = 2.0, min_period: float = 2.0,
        max_period: float | None = None, aniso: tuple[float, float] = (1.0, 1.0)) -> np.ndarray:
    """Tileable fractal noise (spectral synthesis), zero mean, unit std.

    beta: spectral slope (2 = natural terrain-like). Periods are in px.
    aniso stretches features: (sx, sy) > 1 lengthens them along x / y.
    """
    rng = np.random.default_rng(seed)
    fy, fx = _freq(n)
    f = np.sqrt((fx * aniso[0]) ** 2 + (fy * aniso[1]) ** 2)
    f[0, 0] = 1.0
    amp = f ** (-beta / 2)
    amp[f > 1.0 / min_period] = 0
    if max_period:
        amp[f < 1.0 / max_period] = 0
    amp[0, 0] = 0
    phase = np.exp(2j * np.pi * rng.random((n, n)))
    out = np.real(np.fft.ifft2(amp * phase))
    return ((out - out.mean()) / (out.std() + 1e-9)).astype(np.float32)


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def normalize01(a: np.ndarray, lo_pct: float = 0.5, hi_pct: float = 99.5) -> np.ndarray:
    lo, hi = np.percentile(a, [lo_pct, hi_pct])
    return np.clip((a - lo) / (hi - lo + 1e-9), 0.0, 1.0)


def highpass(a: np.ndarray, sigma: float) -> np.ndarray:
    return a - blur(a, sigma)


# ---------------------------------------------------------------- normals
def decode_normal(rgb: np.ndarray) -> np.ndarray:
    n = rgb[..., :3] * 2.0 - 1.0
    return n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9)


def encode_normal(n: np.ndarray) -> np.ndarray:
    n = n / (np.linalg.norm(n, axis=-1, keepdims=True) + 1e-9)
    return n * 0.5 + 0.5


def height_to_normal(h: np.ndarray, strength: float) -> np.ndarray:
    """OpenGL (+Y up = image up) tangent normal from a periodic height map.

    strength: height units per pixel of slope (scale of h relative to texel).
    """
    dx = (np.roll(h, -1, axis=1) - np.roll(h, 1, axis=1)) * 0.5 * strength
    # Image rows grow downward; +Y (green) must point to image up.
    dy = (np.roll(h, 1, axis=0) - np.roll(h, -1, axis=0)) * 0.5 * strength
    n = np.stack([-dx, -dy, np.ones_like(h)], axis=-1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def scale_normal(n: np.ndarray, k: float) -> np.ndarray:
    out = n.copy()
    out[..., :2] *= k
    return out / np.linalg.norm(out, axis=-1, keepdims=True)


def blend_normals(base: np.ndarray, detail: np.ndarray) -> np.ndarray:
    """Whiteout blend of two unit tangent normals."""
    out = np.stack([base[..., 0] + detail[..., 0], base[..., 1] + detail[..., 1],
                    base[..., 2] * detail[..., 2]], axis=-1)
    return out / np.linalg.norm(out, axis=-1, keepdims=True)


# ---------------------------------------------------------------- stamps
def scatter_stamps(n: int, count: int, seed: int, r_lo: float, r_hi: float,
                   mask: np.ndarray | None = None, squash: float = 0.7) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Periodic scatter of rounded pebbles.

    Returns (height, coverage, tone): height is a max of domes (peak 1),
    coverage the pebble mask in [0, 1] used for colour and roughness, tone
    a per-pebble random value in [0, 1] (pick the pebble's colour with it).
    `mask` (HxW in [0, 1]) sets placement probability.
    """
    rng = np.random.default_rng(seed)
    height = np.zeros((n, n), dtype=np.float32)
    cover = np.zeros((n, n), dtype=np.float32)
    tone = np.zeros((n, n), dtype=np.float32)
    placed = 0
    tries = 0
    while placed < count and tries < count * 20:
        tries += 1
        cy, cx = rng.random(2) * n
        if mask is not None and rng.random() > mask[int(cy) % n, int(cx) % n]:
            continue
        r = rng.uniform(r_lo, r_hi)
        ang = rng.uniform(0, np.pi)
        ry = r * rng.uniform(squash, 1.0)
        size = int(np.ceil(r)) + 2
        ys = np.arange(int(cy) - size, int(cy) + size + 1)
        xs = np.arange(int(cx) - size, int(cx) + size + 1)
        yy, xx = np.meshgrid(ys - cy, xs - cx, indexing="ij")
        u = xx * np.cos(ang) + yy * np.sin(ang)
        v = -xx * np.sin(ang) + yy * np.cos(ang)
        d2 = (u / r) ** 2 + (v / ry) ** 2
        dome = np.sqrt(np.clip(1 - d2, 0, 1))
        iy = (ys % n)[:, None]
        ix = (xs % n)[None, :]
        dome = dome * rng.uniform(0.7, 1.0)
        c = smoothstep(1.0, 0.75, d2)
        on_top = dome > height[iy, ix]
        tone[iy, ix] = np.where(on_top, rng.random(), tone[iy, ix])
        height[iy, ix] = np.maximum(height[iy, ix], dome)
        cover[iy, ix] = np.maximum(cover[iy, ix], c)
        placed += 1
    return height, cover, tone


# ---------------------------------------------------------------- checks
def seam_ratio(img: np.ndarray) -> float:
    """Wrap-edge difference relative to typical neighbour difference.

    ~1 means the wrap seam is as smooth as the interior (tileable).
    """
    a = img.reshape(img.shape[0], img.shape[1], -1).astype(np.float64)
    interior = np.abs(np.diff(a, axis=1)).mean() + np.abs(np.diff(a, axis=0)).mean()
    edge = np.abs(a[:, 0] - a[:, -1]).mean() + np.abs(a[0, :] - a[-1, :]).mean()
    return float(edge / (interior + 1e-12))
