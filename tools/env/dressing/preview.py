#!/usr/bin/env python3
"""Flat-shaded previews of the ENV-4 meshes (no Blender): one contact sheet
per asset in assets/previews/dressing/<Asset>.png.

    .venv-env/bin/python tools/env/dressing/preview.py

Each triangle is painted (back to front) with the atlas colour at its UV
centroid, lit by a fixed sun; alpha pieces are drawn over a sand swatch.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import meshes as M  # noqa: E402

CELL = 256
SUN = np.array([-0.45, 0.8, -0.4])
SUN /= np.linalg.norm(SUN)


def render(mesh: M.Mesh, atlas_img: np.ndarray, alpha: bool) -> Image.Image:
    v, uv, f = mesh.arrays()
    img = Image.new("RGB", (CELL, CELL), (201, 130, 79) if alpha else (70, 72, 78))
    d = ImageDraw.Draw(img)
    yaw, pitch = math.radians(35), math.radians(28)
    cy, sy, cp, sp = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch)
    R = np.array([[cy, 0, -sy], [0, 1, 0], [sy, 0, cy]])
    P = np.array([[1, 0, 0], [0, cp, sp], [0, -sp, cp]])
    w = (v - (v.min(0) + v.max(0)) / 2) @ R.T @ P.T
    scale = 0.8 * CELL / max(np.ptp(w[:, 0]), np.ptp(w[:, 1]), 1e-3)
    xy = np.stack([CELL / 2 + w[:, 0] * scale, CELL / 2 - w[:, 1] * scale], 1)
    depth = w[f].mean(1)[:, 2]
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
    view = (np.array([0, 0, 1.0]) @ P) @ R  # camera forward in model space (depth grows along +z)
    H, W = atlas_img.shape[:2]
    for i in np.argsort(-depth):
        facing = np.dot(fn[i], -view)
        if facing < 0 and not alpha:
            continue  # back face
        c = uv[f[i]].mean(0)
        px = atlas_img[min(int(c[1] * H), H - 1), min(int(c[0] * W), W - 1)]
        a = px[3] / 255 if px.shape[0] == 4 else 1.0
        if alpha and a < 0.15:
            continue
        lit = 0.45 + 0.65 * max(np.dot(fn[i] if facing >= 0 else -fn[i], SUN), 0)
        col = tuple(int(min(255, px[k] * lit)) for k in range(3))
        d.polygon([tuple(xy[j]) for j in f[i]], fill=col)
    return img


def main():
    out = ROOT / "assets" / "previews" / "dressing"
    out.mkdir(parents=True, exist_ok=True)
    for name, (pieces, tex, atlas, _) in M.ASSETS.items():
        atlas_img = np.asarray(Image.open(M.TEX / f"{atlas}_color.png"))
        cells = []
        for pname, (make, alpha, *_rest) in pieces.items():
            im = render(make(), atlas_img, alpha == "Transparency")
            ImageDraw.Draw(im).text((4, 4), pname, fill=(255, 255, 255))
            cells.append(im)
        cols = 5
        rows = (len(cells) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * CELL, rows * CELL), (30, 30, 30))
        for k, im in enumerate(cells):
            sheet.paste(im, ((k % cols) * CELL, (k // cols) * CELL))
        sheet.save(out / f"{name}.png")
        print("wrote", out / f"{name}.png")


if __name__ == "__main__":
    main()
