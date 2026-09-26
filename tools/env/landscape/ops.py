"""Terrain shape ops (captured from TerrainBuilder) and their signed distance.

`load()` reads assets/source/landscape/terrain_ops.txt (see capture.py).
`sdf(ops, xs, ys, zs)` evaluates the CSG of the ops on a regular grid in
Roblox world space (studs; +Y up), negative inside solid terrain. Solids
union (min), Air subtracts (max with the negated shape), in call order,
like Roblox's Fill* calls. Only a band of `band` studs around each shape
is exact; values further away are clamped, which is all the envelope needs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OPS_FILE = ROOT / "assets" / "source" / "landscape" / "terrain_ops.txt"


@dataclass(frozen=True)
class Op:
    phase: str
    group: str  # rear | flankL | flankR | far | Butte1..4 | mesa | washes | ...
    kind: str  # ball | block | cyl
    center: tuple[float, float, float]
    size: tuple[float, ...]  # ball: (r,), block: (sx, sy, sz), cyl: (h, r)
    material: str

    @property
    def air(self) -> bool:
        return self.material == "Air"

    def bounds(self, pad: float = 0.0) -> tuple[np.ndarray, np.ndarray]:
        c = np.array(self.center)
        if self.kind == "ball":
            h = np.full(3, self.size[0])
        elif self.kind == "block":
            h = np.array(self.size) / 2
        else:
            h = np.array([self.size[1], self.size[0] / 2, self.size[1]])
        return c - h - pad, c + h + pad


# Blocks/cylinders that start each landscape group in TerrainBuilder's call
# order (buildCliffs, buildButtes); the ops that follow belong to them.
ANCHORS = {
    ("block", (0.0, 60.0, 260.0)): "rear",
    ("block", (-900.0, 70.0, -400.0)): "flankL",
    ("block", (900.0, 70.0, -400.0)): "flankR",
    ("block", (0.0, 50.0, -1420.0)): "far",
    ("cyl", (-380.0, 31.5, -1120.0)): "Butte1",
    ("cyl", (260.0, 38.5, -1150.0)): "Butte2",
    ("cyl", (-60.0, 21.0, -1180.0)): "Butte3",
    ("cyl", (620.0, 31.5, -1060.0)): "Butte4",
}


def load(path: Path = OPS_FILE) -> list[Op]:
    ops = []
    group = ""
    last_phase = ""
    for line in path.read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        f = line.split()
        phase, kind = f[0], f[1]
        nums = [float(v) for v in f[2:-1]]
        center = tuple(nums[:3])
        if phase != last_phase:
            group, last_phase = phase, phase
        for (akind, acenter), name in ANCHORS.items():
            if kind == akind and all(abs(a - b) < 0.01 for a, b in zip(center, acenter)):
                group = name
        ops.append(Op(phase, group, kind, center, tuple(nums[3:]), f[-1]))
    return ops


# How much fatter Roblox's voxelised terrain is than the analytic shapes
# (studs, outward), measured in Studio with probe.py (probe rays against the
# live terrain; blocks p50 2.0 / p90 2.2-3.1, balls p50 1.2 / p90 1.9-3.0;
# cylinders from point probes on the mesa: sides +0.3, tops +1.2). Air balls
# carve correspondingly less.
INFLATE = {"ball": 1.6, "block": 2.1, "cyl_r": 0.5, "cyl_h": 1.3}


def _shape(op: Op, X: np.ndarray, Y: np.ndarray, Z: np.ndarray, inflate: bool = True) -> np.ndarray:
    cx, cy, cz = op.center
    grow = inflate * (1.0 if not op.air else -1.0)
    if op.kind == "ball":
        return np.sqrt((X - cx) ** 2 + (Y - cy) ** 2 + (Z - cz) ** 2) - (op.size[0] + grow * INFLATE["ball"])
    if op.kind == "block":
        hx, hy, hz = (s / 2 + grow * INFLATE["block"] for s in op.size)
        qx, qy, qz = np.abs(X - cx) - hx, np.abs(Y - cy) - hy, np.abs(Z - cz) - hz
        outside = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
        return outside + np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0)
    h, r = op.size
    dr = np.sqrt((X - cx) ** 2 + (Z - cz) ** 2) - (r + grow * INFLATE["cyl_r"])
    dy = np.abs(Y - cy) - (h / 2 + grow * INFLATE["cyl_h"])
    outside = np.sqrt(np.maximum(dr, 0) ** 2 + np.maximum(dy, 0) ** 2)
    return outside + np.minimum(np.maximum(dr, dy), 0)


def sdf(ops: list[Op], xs: np.ndarray, ys: np.ndarray, zs: np.ndarray, band: float = 24.0, inflate: bool = True) -> np.ndarray:
    """Signed distance of the ops' CSG on the grid xs x ys x zs (index order x, y, z),
    by default of the live (voxelised, see INFLATE) terrain."""
    d = np.full((len(xs), len(ys), len(zs)), band, dtype=np.float32)
    lo_grid = np.array([xs[0], ys[0], zs[0]])
    hi_grid = np.array([xs[-1], ys[-1], zs[-1]])
    for op in ops:
        lo, hi = op.bounds(band + 3.0)
        if np.any(hi < lo_grid) or np.any(lo > hi_grid):
            continue
        i0, i1 = np.searchsorted(xs, lo[0]), np.searchsorted(xs, hi[0], side="right")
        j0, j1 = np.searchsorted(ys, lo[1]), np.searchsorted(ys, hi[1], side="right")
        k0, k1 = np.searchsorted(zs, lo[2]), np.searchsorted(zs, hi[2], side="right")
        if i0 >= i1 or j0 >= j1 or k0 >= k1:
            continue
        X, Y, Z = np.meshgrid(xs[i0:i1], ys[j0:j1], zs[k0:k1], indexing="ij")
        s = np.clip(_shape(op, X, Y, Z, inflate), -band, band).astype(np.float32)
        view = d[i0:i1, j0:j1, k0:k1]
        if op.air:
            np.maximum(view, -s, out=view)
        else:
            np.minimum(view, s, out=view)
    return d
