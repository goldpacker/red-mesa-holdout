"""Road and wash centrelines for the ground strips (ENV-3, FACELIFT_PLAN 1c).

The lanes come straight from `src/shared/Config.luau` (parsed, not copied),
so the strips follow the same waypoints TerrainBuilder paints and carves.
Everything here is in Roblox coordinates on the XZ plane: a point is
(x, z); `y` is up.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "src" / "shared" / "Config.luau"

# Strip corridors: lane -> (extend before the first waypoint, extend after
# the last, half-width of the probed corridor, corner fillet radius).
# The road runs on past its spawn point and fades out; the washes run on
# until the carved trough closes (the first carving ball reaches ~19 studs
# past the first waypoint) and into the mesa talus at the other end.
CORRIDORS = {
    "Road": (90.0, 34.0, 36.0, 55.0),
    "WashLeft": (34.0, 34.0, 44.0, 26.0),
    "WashRight": (34.0, 34.0, 44.0, 26.0),
}


def lanes() -> dict[str, list[tuple[float, float]]]:
    text = CONFIG.read_text()
    start = text.index("Config.Lanes = {")
    body = text[start + len("Config.Lanes = {"):text.index("\n}\n", start)]
    out: dict[str, list[tuple[float, float]]] = {}
    for m in re.finditer(r"(\w+) = \{(.*?)\n\t\}", body, re.S):
        pts = [(float(a), float(b)) for a, b in re.findall(r"Vector2\.new\((-?[\d.]+),\s*(-?[\d.]+)\)", m.group(2))]
        if pts:
            out[m.group(1)] = pts
    return out


def extended(name: str) -> np.ndarray:
    """The lane polyline with its ends pushed out along the end segments."""
    pts = np.array(lanes()[name], dtype=np.float64)
    before, after = CORRIDORS[name][:2]
    d0 = pts[0] - pts[1]
    d1 = pts[-1] - pts[-2]
    head = pts[0] + d0 / np.linalg.norm(d0) * before
    tail = pts[-1] + d1 / np.linalg.norm(d1) * after
    return np.vstack([head, pts, tail])


def dist_to_polyline(p: np.ndarray, poly: np.ndarray) -> np.ndarray:
    """Distance from each point (N, 2) to a polyline (M, 2)."""
    best = np.full(len(p), np.inf)
    for a, b in zip(poly[:-1], poly[1:]):
        ab = b - a
        t = np.clip(((p - a) @ ab) / (ab @ ab), 0.0, 1.0)
        q = a + t[:, None] * ab
        best = np.minimum(best, np.linalg.norm(p - q, axis=1))
    return best


def filleted(poly: np.ndarray, radius: float, step: float = 2.0) -> np.ndarray:
    """Resample a polyline every ~`step` studs with each corner replaced by a
    circular arc of `radius` (shrunk where the segments are too short)."""
    pts = [poly[0]]
    n = len(poly)
    for i in range(1, n - 1):
        a, b, c = poly[i - 1], poly[i], poly[i + 1]
        u = (a - b) / np.linalg.norm(a - b)
        v = (c - b) / np.linalg.norm(c - b)
        ang = math.acos(float(np.clip(u @ v, -1.0, 1.0)))  # interior angle
        if ang > math.pi - 1e-3:
            pts.append(b)
            continue
        tan_len = radius / math.tan(ang / 2)
        lim = 0.45 * min(np.linalg.norm(a - b), np.linalg.norm(c - b))
        r = radius
        if tan_len > lim:
            tan_len = lim
            r = tan_len * math.tan(ang / 2)
        p0 = b + u * tan_len
        p1 = b + v * tan_len
        bis = (u + v) / np.linalg.norm(u + v)
        centre = b + bis * (r / math.sin(ang / 2))
        a0 = math.atan2(p0[1] - centre[1], p0[0] - centre[0])
        a1 = math.atan2(p1[1] - centre[1], p1[0] - centre[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        k = max(2, int(abs(da) * r / step))
        for j in range(k + 1):
            t = a0 + da * j / k
            pts.append(centre + r * np.array([math.cos(t), math.sin(t)]))
    pts.append(poly[-1])
    return resample(np.array(pts), step)


def resample(poly: np.ndarray, step: float) -> np.ndarray:
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    keep = np.concatenate([[True], seg > 1e-6])
    poly, s = poly[keep], s[keep]
    n = max(2, int(round(s[-1] / step)) + 1)
    si = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(si, s, poly[:, 0]), np.interp(si, s, poly[:, 1])], axis=1)


def frames(centre: np.ndarray):
    """Arc length, unit tangent and left normal (x, z) at every centreline point."""
    d = np.gradient(centre, axis=0)
    tan = d / np.linalg.norm(d, axis=1, keepdims=True)
    left = np.stack([-tan[:, 1], tan[:, 0]], axis=1)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(centre, axis=0), axis=1))])
    return s, tan, left


def centreline(name: str, step: float = 2.0) -> np.ndarray:
    return filleted(extended(name), CORRIDORS[name][3], step)
