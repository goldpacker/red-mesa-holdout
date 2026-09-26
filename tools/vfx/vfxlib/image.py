"""Frame post-processing, 8x8 atlas assembly and previews (numpy; bpy for IO).

Frames arrive as premultiplied scene-linear RGBA (EXR renders or painted
numpy frames) at CELL * SUPER pixels. `process_frame`:

1. scales by exposure and tone maps (per-channel 1 - exp(-x), so hot cores
   saturate towards white the way fire does);
2. raises alpha to cover emission (alpha >= max channel), so fire occludes
   the background instead of relying on additive blending that washes out
   in daylight, and straight colour always fits in 0..1;
3. optionally converts to greyscale for sheets the emitter tints;
4. box-downsamples in premultiplied space (anti-aliasing);
5. fades alpha to 0 over the outer pixels of the cell, so no frame ever
   shows a hard square edge ("black box") or bleeds into its neighbour;
6. unpremultiplies and fills every (near-)transparent pixel's colour from
   its surroundings (push-pull), so bilinear filtering and mipmaps never
   pull black into the edges (no dark fringes).

PNGs are written as straight alpha with sRGB-encoded colour.
"""
import os

import bpy
import numpy as np

GRID = 8
FILL_ALPHA = 2.0 / 255.0


# --- IO -------------------------------------------------------------------

def load_rgba(path):
    """Loads an image as float RGBA, row 0 = top. EXRs come back premultiplied."""
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    buf = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(buf)
    bpy.data.images.remove(img)
    return buf.reshape(h, w, 4)[::-1].copy()


def save_png(path, rgba):
    """Saves straight RGBA (values already encoded, 0..1) as an 8-bit PNG."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    h, w = rgba.shape[:2]
    img = bpy.data.images.new("vfx_out", w, h, alpha=True)
    data = np.clip(rgba[::-1], 0.0, 1.0).astype(np.float32)
    img.pixels.foreach_set(np.ascontiguousarray(data).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


# --- colour ---------------------------------------------------------------

def srgb_encode(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def srgb_decode(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, np.power((x + 0.055) / 1.055, 2.4))


def hex_rgb(hex_str):
    h = hex_str.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], dtype=np.float32)


def luminance(rgb):
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def tone(c, curve):
    if curve == "clamp":
        return np.clip(c, 0.0, 1.0)
    return 1.0 - np.exp(-np.maximum(c, 0.0))


# --- frame processing -----------------------------------------------------

def downsample(img, factor):
    if factor == 1:
        return img
    h, w = img.shape[:2]
    shape = (h // factor, factor, w // factor, factor) + img.shape[2:]
    return img.reshape(shape).mean(axis=(1, 3))


def border_mask(size, width):
    """1 inside, smooth fall to 0 over `width` px at every cell edge."""
    idx = np.arange(size, dtype=np.float32) + 0.5
    d = np.minimum(idx, size - idx)
    t = np.clip((d - 1.0) / max(width - 1.0, 1e-6), 0.0, 1.0)
    edge = t * t * (3.0 - 2.0 * t)
    return np.outer(edge, edge)


def push_pull(rgb, alpha, thresh=FILL_ALPHA):
    """Straight colour defined everywhere: pixels under `thresh` alpha take the
    alpha-weighted average colour of the nearest visible region."""
    w = (alpha >= thresh).astype(np.float32)
    levels = [(rgb * w[..., None], w)]
    p, q = levels[0]
    while p.shape[0] > 1 and p.shape[0] % 2 == 0:
        h2, w2 = p.shape[0] // 2, p.shape[1] // 2
        p = p.reshape(h2, 2, w2, 2, 3).sum(axis=(1, 3))
        q = q.reshape(h2, 2, w2, 2).sum(axis=(1, 3))
        levels.append((p, q))
    p, q = levels[-1]
    colour = np.where(q[..., None] > 0, p / np.maximum(q, 1e-8)[..., None], 0.5)
    for p, q in reversed(levels[:-1]):
        up = np.repeat(np.repeat(colour, 2, axis=0), 2, axis=1)
        colour = np.where(q[..., None] > 0, p / np.maximum(q, 1e-8)[..., None], up)
    return np.where(w[..., None] > 0, rgb, colour)


def process_frame(premult, spec, cell=128):
    """premult: (H, W, 4) linear premultiplied -> (cell, cell, 4) straight sRGB."""
    exposure = spec.get("exposure", 1.0)
    rgb = tone(premult[..., :3] * exposure, spec.get("tone", "exp"))
    a = np.clip(premult[..., 3] * spec.get("alpha_gain", 1.0), 0.0, 1.0)
    if spec.get("alpha_gamma", 1.0) != 1.0:
        a = np.power(a, spec["alpha_gamma"])
    a = np.maximum(a, rgb.max(axis=2) * spec.get("emission_alpha", 1.0))
    a = np.clip(a, 0.0, 1.0)
    rgb = np.minimum(rgb, a[..., None])
    if spec.get("grey", False):
        rgb = np.repeat(luminance(rgb)[..., None], 3, axis=2)
    factor = premult.shape[0] // cell
    rgb, a = downsample(rgb, factor), downsample(a, factor)
    mask = border_mask(cell, spec.get("border", 6))
    rgb, a = rgb * mask[..., None], a * mask
    a = np.where(a < 0.5 / 255.0, 0.0, a)
    straight = np.where(a[..., None] > 0, rgb / np.maximum(a, 1e-8)[..., None], 0.0)
    straight = push_pull(np.clip(straight, 0.0, 1.0), a)
    out = np.empty((cell, cell, 4), dtype=np.float32)
    out[..., :3] = srgb_encode(straight)
    out[..., 3] = a
    return out


def assemble(cells):
    """64 (cell, cell, 4) frames -> 8x8 atlas, row-major from the top left."""
    cell = cells[0].shape[0]
    atlas = np.zeros((cell * GRID, cell * GRID, 4), dtype=np.float32)
    for i, frame in enumerate(cells):
        r, c = divmod(i, GRID)
        atlas[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = frame
    return atlas


def stats(cells):
    """Numbers for the report: coverage, border alpha, unfilled black pixels."""
    cov = [float(c[..., 3].mean()) for c in cells]
    border = max(float(max(c[0, :, 3].max(), c[-1, :, 3].max(), c[:, 0, 3].max(), c[:, -1, 3].max()))
                 for c in cells)
    clear = np.concatenate([c[..., 3].ravel() == 0 for c in cells])
    black = np.concatenate([(c[..., :3].max(axis=2) < 1e-3).ravel() for c in cells])
    unfilled = int(np.logical_and(clear, black).sum())
    return {
        "coverage_first": round(cov[0], 3),
        "coverage_peak": round(max(cov), 3),
        "coverage_last": round(cov[-1], 3),
        "border_alpha_max": round(border, 4),
        "clear_black_px": unfilled,
    }


# --- previews -------------------------------------------------------------

def checker(h, w, size=16, lo=0.28, hi=0.42):
    yy, xx = np.mgrid[0:h, 0:w]
    val = np.where(((yy // size) + (xx // size)) % 2 == 0, lo, hi).astype(np.float32)
    return np.repeat(val[..., None], 3, axis=2)


def solid(h, w, hex_str):
    return np.broadcast_to(hex_rgb(hex_str), (h, w, 3)).astype(np.float32).copy()


def sky(h, w):
    top, bottom = hex_rgb("#6F97C4"), hex_rgb("#C9D6E2")
    t = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None, None]
    return np.broadcast_to(top * (1 - t) + bottom * t, (h, w, 3)).astype(np.float32).copy()


def over(rgba, bg, tint=None, additive=0.0):
    """Composites straight sRGB rgba over bg in linear light (like the engine).
    `additive` mimics LightEmission: that share of the colour is added instead."""
    col = srgb_decode(rgba[..., :3])
    if tint is not None:
        col = col * srgb_decode(np.asarray(tint, dtype=np.float32))
    a = rgba[..., 3:4]
    base = srgb_decode(bg)
    out = base * (1 - a * (1 - additive)) + col * a
    return srgb_encode(out)


def upscale(img, k):
    return np.repeat(np.repeat(img, k, axis=0), k, axis=1)


def preview(atlas, cells, path, tint=None, additive=0.0):
    """Atlas over checker | atlas over sand, then 8 frames at 2x over sky and sand."""
    size = atlas.shape[0]
    top = np.concatenate([
        over(atlas, checker(size, size)),
        over(atlas, solid(size, size, "#C9824F"), tint, additive),
    ], axis=1)
    picks = [round(i * (len(cells) - 1) / 7) for i in range(8)]
    big = [upscale(cells[i], 2) for i in picks]
    cell = big[0].shape[0]
    row_sky = np.concatenate([over(b, sky(cell, cell), tint, additive) for b in big], axis=1)
    row_sand = np.concatenate([over(b, solid(cell, cell, "#B9774A"), tint, additive) for b in big], axis=1)
    rows = [top, row_sky, row_sand]
    width = max(r.shape[1] for r in rows)
    rows = [np.pad(r, ((0, 0), (0, width - r.shape[1]), (0, 0)), constant_values=0.1) for r in rows]
    img = np.concatenate(rows, axis=0)
    rgba = np.concatenate([img, np.ones(img.shape[:2] + (1,), dtype=np.float32)], axis=2)
    save_png(path, rgba)
