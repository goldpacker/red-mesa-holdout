"""Generates the Look workstream's post/lighting textures (LOOK-1, LOOK-5).

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
  vignette.png          256² black radial vignette for the gunsight overlay
                        (and, much fainter, LOOK-5's full-screen film vignette).
  vignette_corner.png   128² film-vignette corner (LOOK-5), rotated per corner.
                        Unused since LOOK-6 (film_corner.png); kept for A/B.
  film_corner.png       256² film corner (LOOK-6): the corner vignette and the
                        film grain baked into one image, rotated per corner.
  film_grain.png        128² film grain tile, black/white grains with the
                        strength in alpha (LOOK-5, client/PostFxFilm).
  lens_flare.png        256x128 sun glare atlas: glow, ring, hex, disc, streak
                        (LOOK-5, client/PostFxFilm).

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
    # 256² since LOOK-5 (QA-B reclaim item 7): a smooth radial gradient
    # loses nothing, and GUI images are resident as uncompressed RGBA8.
    n = 256
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


def vignette_corner() -> np.ndarray:
    """One corner of the film vignette (LOOK-5): darkest in the top-left
    corner, falling to zero at the tile's far edges, so four rotated copies
    darken only the screen corners (a full-screen translucent layer costs
    ~0.5 ms of GPU in the busy scene; four corners cover about a third)."""
    n = 128
    ys, xs = np.mgrid[0:n, 0:n]
    d = np.sqrt(((xs + 0.5) / n) ** 2 + ((ys + 0.5) / n) ** 2)
    alpha = (1.0 - smoothstep(0.0, 1.0, d)) ** 1.6
    out = rgba(np.clip(alpha, 0.0, 1.0))
    out[..., 0], out[..., 1], out[..., 2] = 0.05, 0.045, 0.035
    return out


def film_grain() -> np.ndarray:
    """Full-screen film grain tile (LOOK-5): fine, slightly clumped grain,
    tileable. Dark grains are black and light grains white, with the grain's
    strength in alpha, so one overlay both darkens and lightens around the
    pixel's own value (no grey veil). Drawn 1:1 in screen pixels and jittered
    every frame by client/PostFxFilm."""
    n = 128
    grain = periodic_noise(n, n, 51, sigma_u=0.55, sigma_v=0.55)
    clumps = periodic_noise(n, n, 52, sigma_u=1.6, sigma_v=1.6)
    g = 0.8 * grain + 0.35 * clumps
    g /= g.std() + 1e-9
    out = np.empty((n, n, 4))
    light = (g > 0).astype(float)
    out[..., 0] = out[..., 1] = out[..., 2] = light
    out[..., 3] = np.clip(np.abs(g) / 2.6, 0.0, 1.0)
    return out


# LOOK-6 film corner: the corner piece is FILM_CORNER_SIZE x screen height
# (client/PostFxFilm CORNER_SIZE); the vignette keeps LOOK-5's profile in
# screen terms (it reached zero at 0.42 x height), so the smaller piece loses
# only its faint tail. Baked at the strongest preset/storm vignette and the
# presets' grain-to-vignette ratio; PostFxFilm scales the whole piece.
FILM_CORNER_SIZE = 0.34
FILM_CORNER_VIGNETTE = 0.3  # vignette opacity the texture holds (Sunset storm 0.22 x 1.3 = 0.286)
FILM_CORNER_GRAIN = 0.084   # grain opacity at that strength (grain/vignette ~0.28, Sunset storm 0.06 x 1.4)
FILM_CORNER_FULL = 0.75     # vignette the texture shows at ImageTransparency 0 (client/PostFxFilm)


def film_grain_field(n: int, seed: int) -> np.ndarray:
    """The film grain's signed field (LOOK-5 statistics): fine grain plus a
    little clumping, unit std, periodic."""
    grain = periodic_noise(n, n, seed, sigma_u=0.55, sigma_v=0.55)
    clumps = periodic_noise(n, n, seed + 1, sigma_u=1.6, sigma_v=1.6)
    g = 0.8 * grain + 0.35 * clumps
    return g / (g.std() + 1e-9)


def film_corner() -> np.ndarray:
    """One screen corner of the film layer (LOOK-6): the corner vignette and
    the film grain baked into ONE image, so the corner is a single layer.
    LOOK-5 drew a full-screen grain and four vignette corners on top of it
    (~1.6 screens of translucent fill); with this texture in the corners and
    the tiled grain only in the cross between them, every pixel is covered
    once. Darkest in the top-left texel, vignette zero at the tile's far
    edges; grain everywhere (same statistics as film_grain.png, 256 texels
    across the piece). Composited as grain over vignette, straight alpha:
    PostFxFilm's ImageTransparency scales both together (first-order exact at
    these opacities)."""
    n = 256
    ys, xs = np.mgrid[0:n, 0:n]
    d = np.sqrt(((xs + 0.5) / n) ** 2 + ((ys + 0.5) / n) ** 2)  # piece units
    d_look5 = d * (FILM_CORNER_SIZE / 0.42)                    # LOOK-5 piece units
    vig = (1.0 - smoothstep(0.0, 1.0, d_look5)) ** 1.6 * smoothstep(1.0, 0.88, d)
    av = FILM_CORNER_VIGNETTE * vig
    g = film_grain_field(n, 61)
    ag = FILM_CORNER_GRAIN * np.clip(np.abs(g) / 2.6, 0.0, 1.0)
    light = (g > 0).astype(float)
    dark = np.array([0.05, 0.045, 0.035])
    alpha = 1.0 - (1.0 - ag) * (1.0 - av)
    out = np.empty((n, n, 4))
    for ch in range(3):
        colour = light * ag + dark[ch] * av * (1.0 - ag)
        out[..., ch] = np.where(alpha > 1e-6, colour / np.maximum(alpha, 1e-6), light)
    # Scaled up for 8-bit headroom: at ImageTransparency 0 the piece is the
    # corner at vignette FILM_CORNER_FULL (linear in the vignette), so
    # PostFxFilm sets ImageTransparency = 1 - vignette / FILM_CORNER_FULL.
    out[..., 3] = alpha * (FILM_CORNER_FULL / FILM_CORNER_VIGNETTE)
    assert out[..., 3].max() <= 1.0, out[..., 3].max()
    return out


def lens_flare() -> np.ndarray:
    """Sun glare atlas (LOOK-5), white, tinted by ImageColor3 in
    client/PostFxFilm. Cells (x, y, w, h in pixels):
      glow  (0, 0, 128, 128)   soft sun bloom with a hot core
      ring  (128, 0, 64, 64)   thin soft ring ghost
      hex   (192, 0, 64, 64)   hexagonal aperture ghost, brighter rim
      disc  (128, 64, 64, 64)  soft round ghost
      streak (192, 64, 64, 64) short horizontal lens streak"""
    out = np.zeros((128, 256, 4))
    out[..., :3] = 1.0

    def cell(size: int) -> tuple[np.ndarray, np.ndarray]:
        ys, xs = np.mgrid[0:size, 0:size]
        x = (xs + 0.5) / size * 2.0 - 1.0
        y = (ys + 0.5) / size * 2.0 - 1.0
        return x, y

    x, y = cell(128)
    r = np.sqrt(x * x + y * y)
    glow = 0.55 * np.exp(-((r / 0.16) ** 2)) + 0.45 * np.exp(-((r / 0.48) ** 2))
    out[0:128, 0:128, 3] = glow * smoothstep(1.0, 0.8, r)

    x, y = cell(64)
    r = np.sqrt(x * x + y * y)
    ring = np.exp(-(((r - 0.72) / 0.08) ** 2)) * 0.8 + 0.12 * smoothstep(0.85, 0.2, r)
    out[0:64, 128:192, 3] = ring * smoothstep(1.0, 0.9, r)

    angle = np.arctan2(y, x)
    sector = np.pi / 3.0
    hex_r = r * np.cos((np.mod(angle, sector)) - sector / 2.0) / np.cos(sector / 2.0)
    hexa = 0.35 * smoothstep(0.82, 0.74, hex_r) + 0.45 * np.exp(-(((hex_r - 0.76) / 0.05) ** 2))
    out[0:64, 192:256, 3] = hexa * smoothstep(0.95, 0.85, hex_r)

    disc = smoothstep(0.9, 0.35, r) * 0.7
    out[64:128, 128:192, 3] = disc

    streak = np.exp(-((y / 0.06) ** 2)) * smoothstep(1.0, 0.0, np.abs(x)) ** 1.5
    out[64:128, 192:256, 3] = streak
    return out


def beam(fn):
    """Authored as rows = across, columns = along; Roblox wants columns across."""
    return lambda: np.ascontiguousarray(np.transpose(fn(), (1, 0, 2)))


TEXTURES = {
    "searchlight_cone": beam(searchlight_cone),
    "heat_haze": beam(heat_haze),
    "vignette": vignette,
    "film_grain": film_grain,
    "vignette_corner": vignette_corner,
    "film_corner": film_corner,
    "lens_flare": lens_flare,
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
