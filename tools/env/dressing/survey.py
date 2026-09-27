#!/usr/bin/env python3
"""Top-down layout board for the ENV-4 ground zoning and conflict dressing.

    .venv-env/bin/python tools/env/dressing/survey.py <survey.json> [out.png]

survey.json comes from tools/env/dressing/survey.server.luau (Studio playtest,
Server datamodel, posted to tools/env/ground/sink.py). The board shows the
terrain (hillshade tinted by material), the lanes, the airdrop band
(300-800 studs), every simulated landing point with its straight walk/drive
to the lane, the boulders and rock kit, and the beauty cameras. When the
survey ran on a build with Battlefield.ConflictDressing it also draws the
placed pieces and flags any near a landing, a walk line or a lane.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[3]
PX = 0.5  # pixels per stud
MAT = {
    "Sand": (201, 130, 79), "Mud": (184, 116, 70), "Ground": (154, 107, 72), "Salt": (217, 185, 140),
    "Rock": (122, 61, 43), "Sandstone": (158, 74, 46), "Limestone": (186, 106, 68), "Slate": (90, 50, 38),
}
LANES = {
    "Road": [(-40, -900), (60, -720), (-30, -540), (40, -360), (0, -190), (0, -92)],
    "ScrubLeft": [(-260, -860), (-200, -620), (-150, -400), (-90, -200), (-50, -85)],
    "ScrubRight": [(260, -860), (210, -620), (150, -400), (90, -200), (50, -85)],
    "WashLeft": [(-620, -760), (-500, -520), (-380, -300), (-240, -150), (-90, -40)],
    "WashRight": [(620, -760), (500, -520), (380, -300), (240, -150), (90, -40)],
}
KIND_COL = {"Infantry": (40, 40, 200), "Buggy": (0, 150, 150), "Tank": (160, 0, 160)}
# Beauty cameras (src/shared/BeautyShots.luau): position, look-at, FOV (vertical).
CAMERAS = {
    "1 title": ((-62, 122, 122), (90, 0, -420), 60),
    "2 turret": ((0, 76, 13), None, 70),
    "4 flank": ((430, 70, -700), (-20, 25, -190), 45),
    "5 night": ((95, 30, -560), (-50, 70, -40), 45),
}


def load(path: str) -> dict:
    s = json.loads(Path(path).read_text())
    if isinstance(s, str):
        s = json.loads(s)
    return s


def grid(s: dict):
    step = s["step"]
    xs = np.arange(s["x0"], s["x1"] + 1, step)
    zs = np.arange(s["z0"], s["z1"] + 1, step)
    h = np.full((len(zs), len(xs)), np.nan)
    mat = np.empty((len(zs), len(xs)), dtype=object)
    for i, row in enumerate(s["rows"]):
        for j, cell in enumerate(row.split(";")):
            if cell:
                y, m, _ = cell.split(",")
                h[i, j] = float(y)
                mat[i, j] = m
    return xs, zs, h, mat


class Board:
    def __init__(self, s: dict):
        self.s = s
        self.x0, self.z0 = s["x0"], s["z0"]
        self.w = int((s["x1"] - s["x0"]) * PX) + 1
        self.hgt = int((s["z1"] - s["z0"]) * PX) + 1
        xs, zs, h, mat = grid(s)
        rgb = np.zeros((len(zs), len(xs), 3))
        for m, c in MAT.items():
            rgb[mat == m] = c
        # hillshade (light from the upper left of the board)
        gz, gx = np.gradient(np.nan_to_num(h, nan=0.0), s["step"])
        shade = np.clip(1.0 + (-gx * 0.6 + gz * 0.6), 0.55, 1.35)
        rgb = np.clip(rgb * shade[..., None], 0, 255).astype(np.uint8)
        img = Image.fromarray(rgb[::-1], "RGB")  # z up the board = far wall at top
        self.img = img.resize((self.w, self.hgt), Image.NEAREST)
        self.d = ImageDraw.Draw(self.img, "RGBA")
        try:
            self.font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 11)
        except OSError:
            self.font = ImageFont.load_default()

    def p(self, x: float, z: float):
        return ((x - self.x0) * PX, self.hgt - 1 - (z - self.z0) * PX)

    def circle(self, x, z, r, outline=None, fill=None, width=1):
        cx, cy = self.p(x, z)
        rr = r * PX
        self.d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=outline, fill=fill, width=width)

    def text(self, x, z, t, fill=(0, 0, 0, 255)):
        self.d.text(self.p(x, z), t, fill=fill, font=self.font)

    def base(self):
        s, d = self.s, self.d
        for x in range(-800, 801, 100):
            d.line([self.p(x, s["z0"]), self.p(x, s["z1"])], fill=(0, 0, 0, 40))
            self.text(x + 3, s["z1"] - 20, str(x), (0, 0, 0, 160))
        for z in range(-1400, 201, 100):
            d.line([self.p(s["x0"], z), self.p(s["x1"], z)], fill=(0, 0, 0, 40))
            self.text(s["x0"] + 4, z + 14, str(z), (0, 0, 0, 160))
        for r in (300, 800):
            self.circle(0, 0, r, outline=(255, 255, 255, 170), width=2)
        for name, pts in LANES.items():
            d.line([self.p(*q) for q in pts], fill=(255, 255, 0, 200), width=2)
            self.text(pts[0][0] + 6, pts[0][1] - 6, name, (60, 60, 0, 255))
        for b in s["boulders"]:
            self.circle(b[0], b[1], b[2] * 2.5, outline=(80, 30, 20, 200))
        for r in s["rocks"]:
            self.circle(r[0], r[1], r[2], outline=(40, 10, 10, 230), width=2)

    def drops(self):
        for x, z, kind, lane, gx, gz in self.s["drops"]:
            self.d.line([self.p(x, z), self.p(gx, gz)], fill=(0, 0, 90, 22))
        for x, z, kind, lane, gx, gz in self.s["drops"]:
            c = KIND_COL.get(kind, (0, 0, 0))
            self.circle(x, z, 3, fill=c + (230,))

    def cameras(self):
        for name, (pos, look, fov) in CAMERAS.items():
            x, _, z = pos
            if look is None:
                look = (0, 0, -1000)
            dx, dz = look[0] - x, look[2] - z
            a = math.atan2(dz, dx)
            hf = math.radians(fov) * 1.1 / 2  # 1177x1068 viewport: horizontal ~ 1.1 x vertical
            for s in (-1, 1):
                ex, ez = x + math.cos(a + s * hf) * 900, z + math.sin(a + s * hf) * 900
                self.d.line([self.p(x, z), self.p(ex, ez)], fill=(255, 255, 255, 150), width=1)
            self.circle(x, z, 6, fill=(255, 255, 255, 255))
            self.text(x + 8, z + 8, name, (255, 255, 255, 255))

    def layout(self, pieces: list[dict], drops: list) -> list[str]:
        problems = []
        pts = np.array([[d[0], d[1]] for d in drops])
        segs = np.array([[d[0], d[1], d[4], d[5]] for d in drops])
        for piece in pieces:
            x, z, r = piece["x"], piece["z"], piece.get("r", 6)
            self.circle(x, z, r, outline=(255, 0, 0, 255), width=2)
            self.text(x + r + 2, z, piece["name"], (120, 0, 0, 255))
            if len(pts):
                dl = np.hypot(pts[:, 0] - x, pts[:, 1] - z).min()
                a, b = segs[:, :2], segs[:, 2:]
                ab = b - a
                t = np.clip(((np.array([x, z]) - a) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-9), 0, 1)
                dw = np.hypot(*(a + ab * t[:, None] - np.array([x, z])).T).min()
                if dl < r + 12 or dw < r + 4:
                    problems.append(f"{piece['name']} at ({x},{z}) r {r}: nearest landing {dl:.0f}, walk line {dw:.0f}")
            dlane = min(seg_dist((x, z), p, q) for pts_ in LANES.values() for p, q in zip(pts_, pts_[1:]))
            if dlane < r + piece.get("lane_clear", 24):
                problems.append(f"{piece['name']} at ({x},{z}) r {r}: lane {dlane:.0f}")
        return problems


def seg_dist(p, a, b):
    ax, az = a
    bx, bz = b
    px, pz = p
    abx, abz = bx - ax, bz - az
    t = max(0.0, min(1.0, ((px - ax) * abx + (pz - az) * abz) / max(abx * abx + abz * abz, 1e-9)))
    return math.hypot(px - (ax + abx * t), pz - (az + abz * t))


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    s = load(argv[0])
    out = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else str(Path(argv[0]).with_suffix(".png"))
    b = Board(s)
    b.base()
    b.drops()
    b.cameras()
    if s.get("pieces"):
        pieces = [{"x": p[0], "z": p[1], "r": p[2], "name": p[4].split("/")[-1], "h": p[3],
                   "lane_clear": 16 if p[3] < 1 else 24} for p in s["pieces"]]
        for problem in b.layout(pieces, s["drops"]):
            print("CLASH", problem)
    b.img.save(out)
    kinds = {}
    for d in s["drops"]:
        kinds[d[2]] = kinds.get(d[2], 0) + 1
    print(f"wrote {out} ({b.w}x{b.hgt}); drops {kinds}; boulders {len(s['boulders'])}; rocks {len(s['rocks'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
