"""Generates the Look workstream's post/lighting textures (LOOK-1).

    tools/ui/py.sh tools/ui/look_textures.py            # writes assets/ui/look/*.png

Outputs (RGBA PNG, white RGB unless noted, shape carried in alpha so the
Roblox Beam/ImageLabel colour tints them). Roblox maps a Beam texture's
horizontal axis ACROSS the beam and its vertical axis ALONG it (verified in
Studio), so beam textures are authored along/across and written transposed:
  searchlight_cone.png  Beam texture for the searchlight cones: along the
                        beam tileable dust streaks + motes, across it a soft
                        core with no hard edge.
  heat_haze.png         Thin wavy horizontal shimmer lines, tileable in U,
                        faded at the top and bottom of the band.
  vignette.png          Black radial vignette for the gunsight overlay.

Pure numpy + zlib (runs on Blender's bundled Python, which has numpy).
Deterministic: same seed, same bytes.
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "ui" / "look"


# ------------------------------------------------------------------ io
def write_png(path: Path, rgba: np.ndarray) -> None:
    """Writes an HxWx4 float array in [0, 1] as an 8-bit RGBA PNG."""
    data = (np.clip(rgba, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)
    h, w, _ = data.shape
    raw = b"".join(b"\x00" + data[y].tobytes() for y in range(h))

    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


def rgba(alpha: np.ndarray, rgb: tuple[float, float, float] = (1.0, 1.0, 1.0)) -> np.ndarray:
    h, w = alpha.shape
    out = np.empty((h, w, 4))
    out[..., 0], out[..., 1], out[..., 2] = rgb
    out[..., 3] = alpha
    return out


# ------------------------------------------------------------------ noise
def periodic_noise(h: int, w: int, seed: int, sigma_u: float, sigma_v: float) -> np.ndarray:
    """Anisotropic Gaussian-filtered white noise, periodic in both axes,
    normalised to zero mean and unit std. sigma in pixels (u = x, v = y)."""
    rng = np.random.default_rng(seed)
    white = rng.standard_normal((h, w))
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.fftfreq(w)[None, :]
    kernel = np.exp(-2.0 * (np.pi ** 2) * ((fx * sigma_u) ** 2 + (fy * sigma_v) ** 2))
    field = np.real(np.fft.ifft2(np.fft.fft2(white) * kernel))
    field -= field.mean()
    return field / (field.std() + 1e-9)


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def motes(h: int, w: int, seed: int, count: int, radius: tuple[float, float], v_sigma: float) -> np.ndarray:
    """Soft round specks, periodic in U, concentrated toward the band centre."""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w))
    ys, xs = np.mgrid[0:h, 0:w]
    for _ in range(count):
        cx = rng.uniform(0, w)
        cy = np.clip(rng.normal(h / 2, v_sigma), 2, h - 3)
        r = rng.uniform(*radius)
        dx = np.abs(xs - cx)
        dx = np.minimum(dx, w - dx)
        d2 = (dx ** 2 + (ys - cy) ** 2) / (r * r)
        out = np.maximum(out, np.exp(-d2) * rng.uniform(0.5, 1.0))
    return out


# ------------------------------------------------------------------ textures
def searchlight_cone() -> np.ndarray:
    h, w = 128, 512
    v = (np.arange(h) + 0.5) / h
    # Across the beam: bright soft core + broad shoulder, zero at the rim.
    core = np.exp(-(((v - 0.5) / 0.13) ** 2))
    shoulder = np.exp(-(((v - 0.5) / 0.30) ** 2))
    rim = smoothstep(0.0, 0.12, v) * smoothstep(1.0, 0.88, v)
    profile = (0.62 * core + 0.38 * shoulder) * rim
    # Along the beam: long dust streaks (stretched along U) and drifting motes.
    streaks = periodic_noise(h, w, 11, sigma_u=26.0, sigma_v=1.6)
    billows = periodic_noise(h, w, 12, sigma_u=60.0, sigma_v=10.0)
    dust = 0.62 + 0.22 * np.tanh(streaks * 0.9) + 0.16 * np.tanh(billows)
    specks = motes(h, w, 13, 90, (0.7, 1.6), v_sigma=h * 0.16)
    alpha = profile[:, None] * np.clip(dust, 0.0, 1.0) + 0.35 * specks * profile[:, None] ** 0.5
    return rgba(np.clip(alpha, 0.0, 1.0))


def heat_haze() -> np.ndarray:
    h, w = 128, 512
    ys, xs = np.mgrid[0:h, 0:w]
    u = xs / w
    v = (ys + 0.5) / h
    # Wavy horizontal lines: phase warped by periodic low-frequency noise so
    # the lines wobble like rising air; everything periodic in U.
    warp = periodic_noise(h, w, 31, sigma_u=18.0, sigma_v=6.0)
    phase = 2.0 * np.pi * (v * 6.0) + 1.1 * warp + 0.6 * np.sin(2.0 * np.pi * (u * 4.0 + v * 2.0))
    lines = 0.5 + 0.5 * np.sin(phase)
    lines = smoothstep(0.25, 1.0, lines) * 0.55
    breakup = 0.5 + 0.5 * np.tanh(periodic_noise(h, w, 32, sigma_u=30.0, sigma_v=6.0))
    envelope = smoothstep(0.0, 0.35, v) * smoothstep(1.0, 0.55, v)
    alpha = lines * breakup * envelope
    return rgba(np.clip(alpha, 0.0, 1.0))


def vignette() -> np.ndarray:
    n = 512
    ys, xs = np.mgrid[0:n, 0:n]
    x = (xs + 0.5) / n * 2.0 - 1.0
    y = (ys + 0.5) / n * 2.0 - 1.0
    r = np.sqrt(x * x + y * y) / np.sqrt(2.0)  # 0 centre .. 1 corner
    alpha = smoothstep(0.30, 0.95, r) ** 1.4
    out = rgba(np.clip(alpha, 0.0, 1.0))
    # Warm near-black that lifts slightly toward the centre (a flat-colour
    # upload failed to load in Studio; this also reads less "digital").
    tone = 0.02 + 0.06 * (1.0 - np.clip(r, 0.0, 1.0))
    out[..., 0], out[..., 1], out[..., 2] = tone * 1.1, tone, tone * 0.8
    return out


def beam(fn):
    """Authored as rows = across, columns = along; Roblox wants columns across."""
    return lambda: np.ascontiguousarray(np.transpose(fn(), (1, 0, 2)))


TEXTURES = {
    "searchlight_cone": beam(searchlight_cone),
    "heat_haze": beam(heat_haze),
    "vignette": vignette,
}


def main(argv: list[str]) -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    names = argv or list(TEXTURES)
    for name in names:
        img = TEXTURES[name]()
        path = OUT / f"{name}.png"
        write_png(path, img)
        a = img[..., 3]
        print(f"wrote {path.relative_to(ROOT)} {img.shape[1]}x{img.shape[0]} alpha mean {a.mean():.3f} max {a.max():.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
