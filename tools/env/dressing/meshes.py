#!/usr/bin/env python3
"""ENV-4 meshes: ground patches and conflict dressing -> assets/exported/.

    .venv-env/bin/python tools/env/dressing/meshes.py

Two assets, each one GLB of small meshes on one shared atlas
(tools/env/dressing/textures.py), instanced across the basin by
src/server/ConflictDressing.luau and src/server/GroundDressing.luau:

GroundPatches (alpha, AlphaMode Transparency, GroundPatches atlas):
  Patch_Gravel, Patch_Scorch, Patch_Stubble, Patch_Stain   flat discs on the floor
  Trample                                                   72-stud lane-edge ribbon
  Wire_Coil                                                 16-stud concertina coil (double-sided)

ConflictDressing (opaque, ConflictProps atlas):
  Hesco_3        three MIL1-size bays (4.2 x 5.4 x 4.2 each) in a row, sand-filled
  Jersey         concrete jersey barrier, 12 long x 3.2 tall
  Drum, Drum_Red fuel drums (3.5 tall), Drums  a group of five
  Tyre           truck tyre lying flat (4.4 across), Tyres  a stack of three
  Crate          wooden crate (4.8 x 3.2 x 3.2), Crates  a stack of three
  Picket         steel wire picket (4.6 tall)
  Pole           wooden power pole, 30 tall, crossarm with three insulators
                 (wire points in the manifest's "markers")
  Pole_Snapped   the same pole broken at ~11 studs; Pole_Top  its fallen top
  Adobe_Wall     24 x 9 x 1.6 mudbrick wall, eroded top
  Adobe_Gap      the same with a collapsed middle; Adobe_Door  with a doorway
  Roof           collapsed roof: charred beams and a sagging corrugated sheet
  Rubble         mudbrick rubble heap (~12 across)
  Sheet          a bent corrugated sheet lying on the ground

Scale: soldiers are 7.2 studs (1.8 m), so 4 studs = 1 m. Every mesh is built
around its ground point (0, 0, 0), Roblox space (y up, the front faces -z);
the manifest's pivot_offset puts the MeshPart pivot there. Deterministic.
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "ground"))
import glb  # noqa: E402

ROOT = HERE.parents[2]
TEX = ROOT / "assets" / "textures" / "dressing"
ATLASES = json.loads((TEX / "atlases.json").read_text())


class Atlas:
    def __init__(self, name):
        a = ATLASES[name]
        self.w, self.h = a["size"]
        self.reg = a["regions"]
        self.studs = a["studs"]

    def uv(self, region, fu, fv, inset=1.0):
        """fu, fv in 0..1 of a region; fv = 0 at the region's TOP."""
        x, y, w, h = self.reg[region]
        return ((x + inset + fu * (w - 2 * inset)) / self.w, (y + inset + fv * (h - 2 * inset)) / self.h)


PROPS = Atlas("ConflictProps")
PATCH = Atlas("GroundPatches")
UP = np.array([0.0, 1.0, 0.0])


class Mesh:
    def __init__(self, atlas: Atlas):
        self.atlas = atlas
        self.v, self.uv, self.f = [], [], []

    def tri(self, pts, uvs, out=None):
        """pts counter-clockwise seen from the front; with `out` (a vector
        pointing out of the front) the order is fixed up if needed."""
        pts = [np.asarray(p, float) for p in pts]
        if out is not None and np.dot(np.cross(pts[1] - pts[0], pts[2] - pts[0]), out) < 0:
            pts, uvs = [pts[0], pts[2], pts[1]], [uvs[0], uvs[2], uvs[1]]
        i = len(self.v)
        self.v += [list(map(float, p)) for p in pts]
        self.uv += [list(map(float, u)) for u in uvs]
        self.f.append([i, i + 1, i + 2])

    def quad(self, pts, uvs, out=None):
        """pts counter-clockwise seen from the front (outside); see tri()."""
        pts = [np.asarray(p, float) for p in pts]
        if out is not None and np.dot(np.cross(pts[1] - pts[0], pts[2] - pts[0]) + np.cross(pts[2] - pts[0], pts[3] - pts[0]), out) < 0:
            pts, uvs = pts[::-1], uvs[::-1]
        i = len(self.v)
        self.v += [list(map(float, p)) for p in pts]
        self.uv += [list(map(float, u)) for u in uvs]
        self.f += [[i, i + 1, i + 2], [i, i + 2, i + 3]]

    def add(self, verts, uvs, faces):
        """Shared-vertex patch (smooth shading); faces index into verts."""
        i = len(self.v)
        self.v += [list(map(float, p)) for p in verts]
        self.uv += [list(map(float, u)) for u in uvs]
        self.f += [[a + i, b + i, c + i] for a, b, c in faces]

    def merge(self, other: "Mesh", at=(0, 0, 0), yaw=0.0, tilt=(0.0, 0.0)):
        c, s = math.cos(yaw), math.sin(yaw)
        rot = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
        ax, az = tilt
        rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
        rz = np.array([[math.cos(az), -math.sin(az), 0], [math.sin(az), math.cos(az), 0], [0, 0, 1]])
        m = rot @ rx @ rz
        i = len(self.v)
        for p in other.v:
            self.v.append(list(m @ np.array(p) + np.array(at, float)))
        self.uv += other.uv
        self.f += [[a + i, b + i, c_ + i] for a, b, c_ in other.f]

    def arrays(self):
        return np.array(self.v, float), np.array(self.uv, float), np.array(self.f, np.int64)


def face_grid(m: Mesh, region, origin, right, up, ulen, vlen, u0=0.0, v0=0.0, bulge=None, nu=None, nv=None):
    """A planar face (origin = bottom-left seen from the front, `right` and
    `up` unit vectors, normal = right x up) mapped onto a tiling `region`,
    split at tile boundaries so the texture tiles across it. `bulge(fu, fv)`
    pushes vertices along the normal (studs). u0/v0 offset the texture."""
    su, sv = m.atlas.studs[region]
    right, up = np.asarray(right, float), np.asarray(up, float)
    normal = np.cross(right, up)
    us = sorted(set([0.0, ulen] + [k * su - u0 for k in range(int((u0) // su) + 1, int((u0 + ulen) // su) + 1) if 0 < k * su - u0 < ulen]))
    vs = sorted(set([0.0, vlen] + [k * sv - v0 for k in range(int((v0) // sv) + 1, int((v0 + vlen) // sv) + 1) if 0 < k * sv - v0 < vlen]))
    if nu:
        us = sorted(set(us + list(np.linspace(0, ulen, nu + 1))))
    if nv:
        vs = sorted(set(vs + list(np.linspace(0, vlen, nv + 1))))

    def P(a, b):
        p = np.asarray(origin, float) + right * a + up * b
        if bulge:
            p = p + normal * bulge(a / ulen, b / vlen)
        return p

    for i in range(len(us) - 1):
        for j in range(len(vs) - 1):
            a0, a1, b0, b1 = us[i], us[i + 1], vs[j], vs[j + 1]
            tu = math.floor((a0 + u0 + 1e-6) / su)
            tv = math.floor((b0 + v0 + 1e-6) / sv)

            def UV(a, b):
                fu = (a + u0) / su - tu
                fv = (b + v0) / sv - tv
                return m.atlas.uv(region, fu, 1.0 - fv)
            m.quad([P(a0, b0), P(a1, b0), P(a1, b1), P(a0, b1)], [UV(a0, b0), UV(a1, b0), UV(a1, b1), UV(a0, b1)])


def box(m: Mesh, centre, size, region, top=None, bottom=False, yaw=0.0, bulge=0.0):
    """Axis box (yaw about y) with each face tiled; `top` region override."""
    cx, cy, cz = centre
    sx, sy, sz = size
    c, s = math.cos(yaw), math.sin(yaw)
    X = np.array([c, 0, -s])
    Z = np.array([s, 0, c])
    o = np.array([cx, cy - sy / 2, cz])
    faces = [  # (origin = bottom-left seen from outside, right, up, ulen, vlen); normal = right x up
        (o + X * sx / 2 - Z * sz / 2, -X, UP, sx, sy),       # front (-z)
        (o - X * sx / 2 + Z * sz / 2, X, UP, sx, sy),        # back (+z)
        (o + X * sx / 2 + Z * sz / 2, -Z, UP, sz, sy),       # +x side
        (o - X * sx / 2 - Z * sz / 2, Z, UP, sz, sy),        # -x side
    ]
    for org, r, u, ul, vl in faces:
        bl = (lambda fu, fv: bulge * math.sin(math.pi * fu) * math.sin(math.pi * fv)) if bulge else None
        face_grid(m, region, org, r, u, ul, vl, bulge=bl, nu=2 if bulge else None, nv=2 if bulge else None)
    # top: seen from above, right = +x, "up" = -z (far side)
    face_grid(m, top or region, o + UP * sy - X * sx / 2 + Z * sz / 2, X, -Z, sx, sz)
    if bottom:
        face_grid(m, region, o - X * sx / 2 - Z * sz / 2, X, Z, sx, sz)


def cylinder(m: Mesh, base, radius, height, sides, region, top_region=None, r_top=None, cap=True, u_scale=1.0, jitter=None, axis_v="up"):
    """Vertical cylinder; U around (circumference in studs x u_scale), V up."""
    su, sv = m.atlas.studs[region]
    r_top = radius if r_top is None else r_top
    base = np.asarray(base, float)
    circ = 2 * math.pi * radius * u_scale
    for k in range(sides):
        a0, a1 = 2 * math.pi * k / sides, 2 * math.pi * (k + 1) / sides
        d0 = np.array([math.cos(a0), 0, math.sin(a0)])
        d1 = np.array([math.cos(a1), 0, math.sin(a1)])
        p00, p10 = base + d0 * radius, base + d1 * radius
        p01, p11 = base + d0 * r_top + UP * height, base + d1 * r_top + UP * height
        # outward CCW seen from outside: (p10, p00, p01, p11) since angle grows toward +z
        u0 = circ * k / sides
        u1 = circ * (k + 1) / sides
        nvseg = max(1, int(math.ceil(height / sv - 1e-6)))
        for j in range(nvseg):
            b0 = height * j / nvseg
            b1 = height * (j + 1) / nvseg
            f0, f1 = b0 / height, b1 / height
            q00, q10 = p00 + (p01 - p00) * f0, p10 + (p11 - p10) * f0
            q01, q11 = p00 + (p01 - p00) * f1, p10 + (p11 - p10) * f1
            tv = math.floor(b0 / sv + 1e-6)
            fv0, fv1 = b0 / sv - tv, b1 / sv - tv
            tu = math.floor(u0 / su + 1e-6)
            fu0, fu1 = u0 / su - tu, u1 / su - tu
            uv = m.atlas.uv
            out = (q00 + q10) / 2 - base
            out[1] = 0
            m.quad([q10, q00, q01, q11], [uv(region, fu0, 1 - fv0), uv(region, fu1, 1 - fv0), uv(region, fu1, 1 - fv1), uv(region, fu0, 1 - fv1)], out=out)
    if cap:
        tr = top_region or region
        top = base + UP * height
        for k in range(sides):
            a0, a1 = 2 * math.pi * k / sides, 2 * math.pi * (k + 1) / sides
            p0 = top + np.array([math.cos(a0), 0, math.sin(a0)]) * r_top
            p1 = top + np.array([math.cos(a1), 0, math.sin(a1)]) * r_top
            uv = lambda p: m.atlas.uv(tr, 0.5 + (p[0] - top[0]) / (2.2 * max(r_top, 0.01)), 0.5 + (p[2] - top[2]) / (2.2 * max(r_top, 0.01)))
            m.tri([top, p1, p0], [uv(top), uv(p1), uv(p0)], out=UP)


def bent_cylinder_between(m: Mesh, p0, p1, radius, sides, region, r1=None, u0=0.0):
    """A tube from p0 to p1 (any direction), U along it from u0 (studs,
    within one tile), V once around; r1 tapers it."""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    axis = p1 - p0
    length = float(np.linalg.norm(axis))
    a = axis / length
    ref = np.array([0.0, 1.0, 0.0]) if abs(a[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    b1 = np.cross(a, ref)
    b1 /= np.linalg.norm(b1)
    b2 = np.cross(a, b1)
    su, sv = m.atlas.studs[region]
    for k in range(sides):
        t0, t1 = 2 * math.pi * k / sides, 2 * math.pi * (k + 1) / sides
        d0 = math.cos(t0) * b1 + math.sin(t0) * b2
        d1 = math.cos(t1) * b1 + math.sin(t1) * b2
        rb = radius if r1 is None else r1
        q0, q1 = p0 + d0 * radius, p0 + d1 * radius
        q3, q2 = p1 + d0 * rb, p1 + d1 * rb
        fa = (u0 % su) / su
        fu = min(fa + length / su, 1.0)
        uv = m.atlas.uv
        m.quad([q0, q3, q2, q1], [uv(region, fa, k / sides), uv(region, fu, k / sides), uv(region, fu, (k + 1) / sides), uv(region, fa, (k + 1) / sides)], out=d0 + d1)


# ------------------------------------------------------------------ patches
def disc(region, diameter, rings=1, segs=12, y=0.07, seed=0):
    m = Mesh(PATCH)
    rng = np.random.default_rng(seed)
    r = diameter / 2
    verts = [(0.0, y, 0.0)]
    uvs = [PATCH.uv(region, 0.5, 0.5)]
    for i in range(1, rings + 1):
        rr = r * i / rings
        for j in range(segs):
            a = 2 * math.pi * j / segs
            jit = 1.0 + (rng.uniform(-0.04, 0.04) if i == rings else 0.0)
            verts.append((rr * jit * math.cos(a), y, rr * jit * math.sin(a)))
            uvs.append(PATCH.uv(region, 0.5 + 0.5 * (rr / r) * math.cos(a) * 0.985, 0.5 + 0.5 * (rr / r) * math.sin(a) * 0.985))
    faces = [[0, 1 + (j + 1) % segs, 1 + j] for j in range(segs)]
    for i in range(1, rings):
        b0, b1 = 1 + (i - 1) * segs, 1 + i * segs
        for j in range(segs):
            j1 = (j + 1) % segs
            faces += [[b0 + j, b1 + j1, b1 + j], [b0 + j, b0 + j1, b1 + j1]]
    v = np.array(verts)
    if np.cross(v[faces[0][1]] - v[faces[0][0]], v[faces[0][2]] - v[faces[0][0]])[1] < 0:
        faces = [[a, c, b] for a, b, c in faces]
    m.v = [list(p) for p in verts]
    m.uv = [list(u) for u in uvs]
    m.f = faces
    return m


def ribbon(region, length, width, step=4.0, curve=0.0, y=0.08, seed=0):
    """Flat ribbon along x (a lane-edge trample band), gently wandering."""
    m = Mesh(PATCH)
    rng = np.random.default_rng(seed)
    su = PATCH.studs[region][0]
    n = int(length / step)
    heading = 0.0
    p = np.array([-length / 2, 0.0])
    pts, heads = [], []
    for i in range(n + 1):
        pts.append(p.copy())
        heads.append(heading)
        heading += curve * step * (1 + 0.5 * math.sin(i * 0.7 + rng.uniform(0, 1)))
        p = p + step * np.array([math.cos(heading), math.sin(heading)])
    pts = np.array(pts)
    pts -= pts.mean(axis=0)
    verts, uvs = [], []
    for i, (q, hd) in enumerate(zip(pts, heads)):
        side = np.array([-math.sin(hd), math.cos(hd)])
        for j, sgn in enumerate((-1, 1)):
            e = q + side * sgn * width / 2
            verts.append((e[0], y, e[1]))
            x, yy, w, h = PATCH.reg[region]
            uvs.append((i * step / su, (yy + 1 + j * (h - 2)) / PATCH.h))
    faces = []
    for i in range(n):
        a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2
        faces += [[a, b, c], [a, c, d]]
    v = np.array(verts)
    if np.cross(v[faces[0][1]] - v[faces[0][0]], v[faces[0][2]] - v[faces[0][0]])[1] < 0:
        faces = [[a, c, b] for a, b, c in faces]
    m.v, m.uv, m.f = [list(p) for p in verts], [list(u) for u in uvs], faces
    return m


def wire_coil(length=16.0, radius=1.8, sides=8, segs=8, seed=0):
    """Concertina coil lying along x: a slightly flattened, sagging cylinder
    of alpha loops (double-sided), base on the ground."""
    m = Mesh(PATCH)
    rng = np.random.default_rng(seed)
    x0, y0, w, h = PATCH.reg["wire"]
    rows = []
    for i in range(segs + 1):
        t = i / segs
        x = -length / 2 + length * t
        sag = 0.25 * math.sin(math.pi * t) + rng.uniform(-0.08, 0.08)
        wob = 0.3 * math.sin(2 * math.pi * t * 1.3 + 0.5)
        ring = []
        for k in range(sides + 1):
            a = 2 * math.pi * k / sides
            ry = radius * 0.86
            ring.append((x, radius * 0.86 + math.sin(a) * ry - sag, wob + math.cos(a) * radius))
        rows.append(ring)
    for i in range(segs):
        for k in range(sides):
            p00, p01 = rows[i][k], rows[i][k + 1]
            p10, p11 = rows[i + 1][k], rows[i + 1][k + 1]
            u0, u1 = (x0 + 1 + (w - 2) * i / segs) / PATCH.w, (x0 + 1 + (w - 2) * (i + 1) / segs) / PATCH.w
            v0, v1 = (y0 + 1 + (h - 2) * k / sides) / PATCH.h, (y0 + 1 + (h - 2) * (k + 1) / sides) / PATCH.h
            m.quad([p00, p10, p11, p01], [(u0, v0), (u1, v0), (u1, v1), (u0, v1)])
    return m


# ------------------------------------------------------------------ props
def hesco3():
    m = Mesh(PROPS)
    bw, bh, bd = 4.2, 5.4, 4.2
    for i in range(3):
        x = (i - 1) * bw
        # sides bulge a little between the wire frames
        box(m, (x, bh / 2 - 0.2, 0), (bw, bh, bd), "hesco", top="sand", bulge=0.14)
    # sand mounds proud of each bay's top (settled fill)
    for i in range(3):
        x = (i - 1) * bw
        top = Mesh(PROPS)
        cyl_mound(top, (x, bh - 0.2, 0), bw * 0.46, 0.35, 8, "sand")
        m.merge(top)
    # sand banked against the wall (fill spilled from the bays + wind drift)
    half = 1.5 * bw
    for side in (-1, 1):
        drift_strip(m, (-half - 0.3, 0, side * bd / 2), (half + 0.3, 0, side * bd / 2), (0, 0, side), 0.3, 1.25, 2.8, 40 + side)
    for end in (-1, 1):
        drift_strip(m, (end * half, 0, -bd / 2 - 0.2), (end * half, 0, bd / 2 + 0.2), (end, 0, 0), 0.3, 0.7, 1.6, 44 + end, step=1.0)
    return m


def cyl_mound(m, centre, radius, height, sides, region):
    c = np.asarray(centre, float)
    apex = c + UP * height
    uv = lambda p: m.atlas.uv(region, 0.5 + (p[0] - c[0]) / 8.0, 0.5 + (p[2] - c[2]) / 8.0)
    for k in range(sides):
        a0, a1 = 2 * math.pi * k / sides + math.pi / sides, 2 * math.pi * (k + 1) / sides + math.pi / sides
        p0 = c + np.array([math.cos(a0), 0, math.sin(a0)]) * radius
        p1 = c + np.array([math.cos(a1), 0, math.sin(a1)]) * radius
        m.tri([apex, p1, p0], [uv(apex), uv(p1), uv(p0)], out=UP)


DRIFT_SINK = -0.14  # a drift's outer edge runs under the terrain, so no seam line shows


def _drift_grid(m, rows, uvf, closed=False):
    """rows: list of vertex rows (each inner -> outer); shared vertices so the
    drift shades smooth; faces wound to face up."""
    n, k = len(rows), len(rows[0])
    verts = [p for row in rows for p in row]
    uvs = [uvf(p) for p in verts]
    faces = []
    for i in range(n if closed else n - 1):
        i1 = (i + 1) % n
        for j in range(k - 1):
            a, b, c, d = i * k + j, i1 * k + j, i1 * k + j + 1, i * k + j + 1
            faces += [[a, b, c], [a, c, d]]
    v = np.array(verts)
    up_count = sum(1 for f in faces if np.cross(v[f[1]] - v[f[0]], v[f[2]] - v[f[0]])[1] > 0)
    if up_count < len(faces) / 2:
        faces = [[a, c, b] for a, b, c in faces]
    m.add(verts, uvs, faces)


def drift_strip(m, a, b, out, face_in, h_face, width, seed, step=1.4):
    """Wind-blown sand piled against a straight face from a to b (ground
    points, y ignored), spreading along `out` (unit, horizontal). It starts
    `face_in` inside the face at h_face (hidden by the prop) and slopes out
    `width` studs to DRIFT_SINK below the ground; height and reach swell and
    thin smoothly along the face and taper at the corners. Mapped on the
    props atlas' sand region (a crop of the terrain sand) by position.
    ENV-4 fix 1."""
    rng = np.random.default_rng(seed)
    a, b, out = np.asarray(a, float), np.asarray(b, float), np.asarray(out, float)
    a[1] = b[1] = 0.0
    length = float(np.linalg.norm(b - a))
    along = (b - a) / length
    n = max(2, int(math.ceil(length / step)))
    k1, k2 = rng.uniform(0, 6.28), rng.uniform(0, 6.28)
    rows = []
    for i in range(n + 1):
        t = i / n
        taper = min(1.0, 3 * t, 3 * (1 - t)) ** 0.6
        swell = 0.5 + 0.3 * math.sin(k1 + 6.5 * t) + 0.2 * math.sin(k2 + 15 * t)
        hf = h_face * (0.45 + 0.55 * swell) * (0.35 + 0.65 * taper)
        wd = width * (0.65 + 0.35 * swell) * (0.45 + 0.55 * taper)
        base = a + along * (length * t)
        rows.append([base - out * face_in + np.array([0, hf, 0]),
                     base + out * (0.3 * wd) + np.array([0, hf * 0.62, 0]),
                     base + out * (0.62 * wd) + np.array([0, hf * 0.22, 0]),
                     base + out * wd + np.array([0, DRIFT_SINK, 0])])
    su, sv = PROPS.studs["sand"]
    _drift_grid(m, rows, lambda p: PROPS.uv("sand", (p[0] + 12.0) / su, (p[2] + 6.0) / sv, inset=2))


def drift_ring(m, centre, r_in, r_out, h_in, seed, segs=12):
    """Sand drifted round a round prop's base (tyres): from r_in at h_in
    (inside the prop) out to r_out below the ground. ENV-4 fix 1."""
    rng = np.random.default_rng(seed)
    c = np.array([centre[0], 0.0, centre[2]], float)
    k1 = rng.uniform(0, 6.28)
    rows = []
    for k in range(segs):
        ang = 2 * math.pi * k / segs
        d = np.array([math.cos(ang), 0, math.sin(ang)])
        swell = 0.5 + 0.5 * math.sin(k1 + 2 * ang)
        ro = r_out * (0.85 + 0.3 * swell)
        h = h_in * (0.6 + 0.4 * swell)
        rows.append([c + d * r_in + np.array([0, h, 0]),
                     c + d * (r_in + 0.35 * (ro - r_in)) + np.array([0, h * 0.6, 0]),
                     c + d * (r_in + 0.7 * (ro - r_in)) + np.array([0, h * 0.2, 0]),
                     c + d * ro + np.array([0, DRIFT_SINK, 0])])
    su, sv = PROPS.studs["sand"]
    _drift_grid(m, rows, lambda p: PROPS.uv("sand", 0.5 + (p[0] - c[0]) / su, 0.5 + (p[2] - c[2]) / sv, inset=2), closed=True)


def jersey(length=12.0, seed=0):
    """Profile (half-width, height) from the base up, extruded along x."""
    m = Mesh(PROPS)
    prof = [(1.2, 0.0), (1.2, 0.3), (0.9, 1.05), (0.3, 3.2)]
    rng = np.random.default_rng(seed)
    L = length
    # sides: each profile segment is a tiled face along x
    for side in (-1, 1):
        for (w0, h0), (w1, h1) in zip(prof, prof[1:]):
            p0 = np.array([-L / 2, h0, side * w0])
            p1 = np.array([-L / 2, h1, side * w1])
            up = p1 - p0
            ln = float(np.linalg.norm(up))
            up /= ln
            right = np.array([1.0, 0, 0]) * side
            origin = p0 + np.array([L if side < 0 else 0.0, 0, 0])
            face_grid(m, "concrete", origin, right, up, L, ln, v0=h0)
    # top strip: mapped to the region's dusty-top band (textures.py concrete())
    face_grid(m, "concrete", np.array([-L / 2, 3.2, 0.3]), np.array([1.0, 0, 0]), np.array([0, 0, -1.0]), L, 0.6, v0=3.3)
    # end caps (planar polygons, chipped a little)
    for end in (-1, 1):
        x = end * L / 2
        pts = [(x, h, -w) for w, h in prof] + [(x, h, w) for w, h in reversed(prof)]
        pts = [np.array(p) + np.array([rng.uniform(-0.05, 0.05), 0, 0]) for p in pts]
        cen = np.mean(pts, axis=0)
        for a, b in zip(pts, pts[1:] + pts[:1]):
            tri = [cen, a, b]
            uv = lambda p, e=end: PROPS.uv("concrete", 0.5 - e * p[2] / 8.0, 1 - p[1] / 8.0)
            m.tri(tri, [uv(p) for p in tri], out=np.array([end, 0.0, 0.0]))
    # sand drifted against both faces and the ends (ENV-4 fix 1: grounding)
    for side in (-1, 1):
        drift_strip(m, (-L / 2 - 0.4, 0, side * 1.2), (L / 2 + 0.4, 0, side * 1.2), (0, 0, side), 0.3, 0.85, 2.2, seed + 3 + side)
    for end in (-1, 1):
        drift_strip(m, (end * L / 2, 0, -1.3), (end * L / 2, 0, 1.3), (end, 0, 0), 0.25, 0.4, 1.2, seed + 7 + end, step=0.9)
    return m


def drum(region="drum"):
    m = Mesh(PROPS)
    cylinder(m, (0, 0, 0), 1.15, 3.5, 12, region, top_region="steel")
    return m


def drums():
    m = Mesh(PROPS)
    spots = [((0, 0, 0), "drum", 0.0, None), ((2.4, 0, 0.4), "drum2", 0.4, None), ((1.1, 0, 2.1), "drum", 1.1, None),
             ((-1.8, 0, 1.7), "drum", 0.0, None), ((3.6, 0, 3.0), "drum2", 0.0, "lying")]
    for pos, reg, yaw, pose in spots:
        d = drum(reg)
        if pose == "lying":
            m.merge(d, at=(pos[0], 1.15, pos[2]), yaw=yaw + 0.6, tilt=(0.0, math.pi / 2))
        else:
            m.merge(d, at=pos, yaw=yaw)
    return m


def tyre(r_out=2.2, r_in=1.15, width=1.3, segs=10):
    """Tyre lying flat: tread band (outer), sidewalls (top/bottom), rim hole."""
    m = Mesh(PROPS)
    su = PROPS.studs["rubber"][0]
    circ = 2 * math.pi * r_out
    prof = [(r_in, 0.12), (r_out - 0.25, 0.0), (r_out, 0.3), (r_out, width - 0.3), (r_out - 0.25, width), (r_in, width - 0.12), (r_in, 0.12)]
    vfrac = [0.0, 0.18, 0.3, 0.7, 0.82, 1.0, 0.0]
    for k in range(segs):
        a0, a1 = 2 * math.pi * k / segs, 2 * math.pi * (k + 1) / segs
        for j in range(len(prof) - 1):
            (r0, y0), (r1, y1) = prof[j], prof[j + 1]
            q00 = np.array([math.cos(a0) * r0, y0, math.sin(a0) * r0])
            q10 = np.array([math.cos(a1) * r0, y0, math.sin(a1) * r0])
            q01 = np.array([math.cos(a0) * r1, y1, math.sin(a0) * r1])
            q11 = np.array([math.cos(a1) * r1, y1, math.sin(a1) * r1])
            fu0 = (circ * k / segs / su) % 1.0
            fu1 = fu0 + circ / segs / su
            uv = PROPS.uv
            pts = [q00, q10, q11, q01]
            uvs = [uv("rubber", fu0, vfrac[j]), uv("rubber", fu1, vfrac[j]), uv("rubber", fu1, vfrac[j + 1]), uv("rubber", fu0, vfrac[j + 1])]
            mid = (q00 + q11) / 2
            radial = np.array([mid[0], 0, mid[2]])
            outward = {0: np.array([0, -1.0, 0]) + 0.2 * radial, 4: np.array([0, 1.0, 0]) + 0.2 * radial, 5: -radial}.get(j, radial)
            m.quad(pts, uvs, out=outward)
    return m


def tyre_grounded(seed=0):
    m = tyre()
    drift_ring(m, (0, 0, 0), 2.05, 3.1, 0.45, 60 + seed)
    return m


def tyres():
    m = Mesh(PROPS)
    for i, (dx, dz) in enumerate(((0, 0), (0.25, -0.2), (-0.2, 0.15))):
        m.merge(tyre(), at=(dx, i * 1.28, dz), yaw=i * 0.7, tilt=(0.03 * i, -0.02 * i))
    m.merge(tyre(), at=(4.4, 0.0, 1.2), yaw=0.3)
    # sand round the stack's bottom tyre and the loose one (ENV-4 fix 1)
    drift_ring(m, (0, 0, 0), 2.05, 3.3, 0.5, 61)
    drift_ring(m, (4.4, 0, 1.2), 2.05, 3.0, 0.4, 62)
    return m


def crate(size=(4.8, 3.2, 3.2)):
    m = Mesh(PROPS)
    box(m, (0, size[1] / 2, 0), size, "planks")
    return m


def crates():
    m = Mesh(PROPS)
    m.merge(crate(), at=(0, 0, 0), yaw=0.05)
    m.merge(crate(), at=(0.3, 3.2, 0.1), yaw=-0.12)
    m.merge(crate((3.2, 2.4, 3.2)), at=(4.3, 0, 0.6), yaw=0.4)
    return m


def picket():
    m = Mesh(PROPS)
    bent_cylinder_between(m, (0, -0.4, 0), (0.05, 4.6, 0.02), 0.12, 5, "steel")
    return m


POLE_H = 30.0
ARM_Y = POLE_H - 1.6
WIRE_X = (-3.4, -1.1, 3.4)


def pole(height=POLE_H, snapped=None):
    m = Mesh(PROPS)
    top = snapped or height
    su = PROPS.studs["wood"][0]
    r_base, r_tip = 0.62, 0.40
    ys = list(np.arange(-0.5, top, su)) + [top]
    for y0, y1 in zip(ys, ys[1:]):
        r0 = r_base + (r_tip - r_base) * max(y0, 0) / height
        r1 = r_base + (r_tip - r_base) * y1 / height
        bent_cylinder_between(m, (0, y0, 0), (0, y1, 0), r0, 8, "wood", r1=r1)
    rt = r_base + (r_tip - r_base) * top / height
    cylinder(m, (0, top - 0.001, 0), rt, 0.001, 8, "char" if snapped else "wood", cap=True)
    markers = []
    if not snapped:
        box(m, (0, ARM_Y, 0), (8.2, 0.5, 0.45), "wood")
        # braces from the pole to the arm
        for sx in (-1, 1):
            bent_cylinder_between(m, (0, ARM_Y - 2.4, 0.3), (sx * 2.2, ARM_Y - 0.2, 0.3), 0.07, 4, "steel")
        for x in WIRE_X:
            cylinder(m, (x, ARM_Y + 0.25, 0), 0.16, 0.7, 6, "steel", r_top=0.12)
            markers.append({"name": f"Wire{len(markers) + 1}", "pos": [x, ARM_Y + 0.9, 0.0]})
    return m, markers


SPAN = 74.0  # power-line span the Wire_Span mesh is built for (stretched per span)
WIRE_SAG = 1.9


def wire_span(length=SPAN, sag=WIRE_SAG, segs=10):
    """The three wires of one power-line span as one mesh: thin sagging
    tubes along x from -L/2 to L/2 at the crossarm's wire offsets, the
    ends at y 0 (the insulator tops). A span runs along the line and the
    pole's crossarm (its local x) lies across it, so span z = -(pole x).
    One MeshPart per span, instanced."""
    m = Mesh(PROPS)
    for z in (-x for x in WIRE_X):
        pts = []
        for i in range(segs + 1):
            t = i / segs
            pts.append((-length / 2 + length * t, -sag * 4 * t * (1 - t), z))
        for a, b in zip(pts, pts[1:]):
            bent_cylinder_between(m, a, b, 0.07, 3, "rubber")
    return m


def pole_top():
    """The fallen upper part of a snapped pole, lying along x."""
    m, _ = pole()
    sub = Mesh(PROPS)
    # keep the part above the break, turn it over on the ground
    brk = 11.0
    v = np.array(m.v)
    keep = [f for f in m.f if min(v[f][:, 1]) >= brk - 0.6]
    idx = sorted({i for f in keep for i in f})
    remap = {old: new for new, old in enumerate(idx)}
    pts = v[idx] - np.array([0, brk, 0])
    # lay it down along +x, crossarm resting on the ground on one end
    c, s = math.cos(-math.pi / 2 + 0.06), math.sin(-math.pi / 2 + 0.06)
    rot = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
    pts = pts @ rot.T
    roll = np.array([[1, 0, 0], [0, 0.0, -1.0], [0, 1.0, 0.0]])  # arm flat on the ground
    pts = pts @ roll.T
    pts[:, 1] -= pts[:, 1].min() + 0.25
    sub.v = [list(p) for p in pts]
    sub.uv = [m.uv[i] for i in idx]
    sub.f = [[remap[a], remap[b], remap[c_]] for a, b, c_ in keep]
    return sub


def wall_profile(length, height, seed, gap=None, tile=8.0):
    """Column x positions (including every texture-tile boundary, so no
    column straddles one) and the eroded top height at each."""
    rng = np.random.default_rng(seed)
    xs = set(np.round(np.linspace(-length / 2, length / 2, int(length / 1.5) + 1), 4))
    xs |= {round(-length / 2 + k * tile, 4) for k in range(int(length / tile) + 1)}
    xs = np.array(sorted(xs))
    top = height - 0.35 * np.abs(np.sin(xs * 0.9 + rng.uniform(0, 3))) - rng.uniform(0, 0.45, len(xs))
    if gap:
        c, w, low = gap
        top = np.minimum(top, low + (height - low) * np.clip((np.abs(xs - c) - w / 2) / 3.0, 0, 1) + rng.uniform(0, 0.6, len(xs)))
    return xs, top


WALL_V = 10.0  # studs of wall height per adobe tile (8-stud tile stretched a little)


def adobe_wall(length=24.0, height=9.0, thick=1.6, seed=0, gap=None, door=None):
    """Mudbrick wall along x, faces toward -z and +z, eroded top (bare brick)."""
    m = Mesh(PROPS)
    su = PROPS.studs["adobe"][0]
    xs, top = wall_profile(length, height, seed, gap, su)
    if door:
        c, w, hgt = door
        xs_d = set(xs) | {c - w / 2, c + w / 2}
        xs_new = np.array(sorted(xs_d))
        top = np.interp(xs_new, xs, top)
        xs = xs_new
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        t0, t1 = top[i], top[i + 1]
        lo = door[2] if door and x0 >= door[0] - door[1] / 2 - 1e-6 and x1 <= door[0] + door[1] / 2 + 1e-6 else 0.0
        base = math.floor((x0 + length / 2) / su + 1e-6)
        fu0 = (x0 + length / 2) / su - base
        fu1 = (x1 + length / 2) / su - base
        uv = lambda fu, y: PROPS.uv("adobe", fu, 1 - min(y / WALL_V, 1.0))
        for side in (-1, 1):
            z = side * thick / 2
            pts = [np.array([x0, lo, z]), np.array([x1, lo, z]), np.array([x1, t1, z]), np.array([x0, t0, z])]
            uvs = [uv(fu0, lo), uv(fu1, lo), uv(fu1, t1), uv(fu0, t0)]
            if side < 0:  # seen from -z, +x runs to the left: mirror U so the texture reads
                uvs = [uv(1 - fu0, lo), uv(1 - fu1, lo), uv(1 - fu1, t1), uv(1 - fu0, t0)]
            m.quad(pts, uvs, out=np.array([0, 0, side]))
        # eroded top: bare brick
        pts = [np.array([x0, t0, -thick / 2]), np.array([x1, t1, -thick / 2]), np.array([x1, t1, thick / 2]), np.array([x0, t0, thick / 2])]
        tuv = lambda p: PROPS.uv("brick", fu0 + (p[0] - x0) / su, 0.5 + p[2] / su)
        m.quad(pts, [tuv(p) for p in pts], out=UP)
    # ends
    for end, i in ((-1, 0), (1, len(xs) - 1)):
        x = xs[i]
        pts = [np.array([x, 0, -thick / 2]), np.array([x, 0, thick / 2]), np.array([x, top[i], thick / 2]), np.array([x, top[i], -thick / 2])]
        euv = lambda p, e=end: PROPS.uv("brick", 0.5 - e * p[2] / su, 1 - min(p[1] / WALL_V, 1.0))
        m.quad(pts, [euv(p) for p in pts], out=np.array([end, 0, 0]))
    if door:
        c, w, hgt = door
        for x, o in ((c - w / 2, 1), (c + w / 2, -1)):
            pts = [np.array([x, 0, -thick / 2]), np.array([x, 0, thick / 2]), np.array([x, hgt, thick / 2]), np.array([x, hgt, -thick / 2])]
            juv = lambda p, e=o: PROPS.uv("brick", 0.5 - e * p[2] / su, 1 - p[1] / WALL_V)
            m.quad(pts, [juv(p) for p in pts], out=np.array([o, 0, 0]))
        pts = [np.array([c - w / 2, hgt, -thick / 2]), np.array([c + w / 2, hgt, -thick / 2]), np.array([c + w / 2, hgt, thick / 2]), np.array([c - w / 2, hgt, thick / 2])]
        m.quad(pts, [PROPS.uv("wood", (p[0] - c + w / 2) / 8, 0.5 + p[2] / 2) for p in pts], out=-UP)
    if gap:
        m.merge(rubble(seed + 7, 5.5, 1.8), at=(gap[0], 0, 2.2))
    return m


def rubble(seed=0, radius=6.0, height=2.4):
    m = Mesh(PROPS)
    rng = np.random.default_rng(seed)
    # a lumpy mound (brick) plus a few block chunks
    rings, segs = 3, 10
    verts = [(0.0, height, 0.0)]
    for i in range(1, rings + 1):
        rr = radius * i / rings
        for j in range(segs):
            a = 2 * math.pi * j / segs + rng.uniform(-0.1, 0.1)
            hh = height * (1 - (i / rings) ** 1.6) * rng.uniform(0.8, 1.2) - (0.15 if i == rings else 0)
            verts.append((rr * rng.uniform(0.85, 1.1) * math.cos(a), hh, rr * rng.uniform(0.85, 1.1) * math.sin(a)))
    v = np.array(verts)
    uvs = [PROPS.uv("brick", 0.5 + p[0] / 16, 0.5 + p[2] / 16) for p in v]
    faces = [[0, 1 + (j + 1) % segs, 1 + j] for j in range(segs)]
    for i in range(1, rings):
        b0, b1 = 1 + (i - 1) * segs, 1 + i * segs
        for j in range(segs):
            j1 = (j + 1) % segs
            faces += [[b0 + j, b1 + j1, b1 + j], [b0 + j, b0 + j1, b1 + j1]]
    if np.cross(v[faces[0][1]] - v[faces[0][0]], v[faces[0][2]] - v[faces[0][0]])[1] < 0:
        faces = [[a, c, b] for a, b, c in faces]
    m.v, m.uv, m.f = [list(p) for p in v], [list(u) for u in uvs], faces
    for _ in range(5):
        s = (rng.uniform(1.0, 1.8), rng.uniform(0.35, 0.5), rng.uniform(0.7, 1.0))
        a = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.3, 0.9) * radius
        chunk = Mesh(PROPS)
        box(chunk, (0, s[1] / 2, 0), s, "brick")
        m.merge(chunk, at=(r * math.cos(a), max(0.0, height * (1 - (r / radius) ** 1.6)) - 0.2, r * math.sin(a)), yaw=rng.uniform(0, 3), tilt=(rng.uniform(-0.3, 0.3), rng.uniform(-0.3, 0.3)))
    return m


def sheet_piece(w=6.0, d=3.0, bend=0.6, segs=4):
    m = Mesh(PROPS)
    for i in range(segs):
        x0, x1 = -w / 2 + w * i / segs, -w / 2 + w * (i + 1) / segs
        y0 = bend * math.sin(math.pi * i / segs) + 0.05
        y1 = bend * math.sin(math.pi * (i + 1) / segs) + 0.05
        for side in (1, -1):
            off = np.array([0, 0.0 if side > 0 else -0.02, 0])
            pts = [np.array([x0, y0, -d / 2]) + off, np.array([x0, y0, d / 2]) + off, np.array([x1, y1, d / 2]) + off, np.array([x1, y1, -d / 2]) + off]
            uv = lambda p, sd=side: PROPS.uv("sheet", min((p[0] + w / 2) / 6.0, 1.0), 0.5 + sd * p[2] / 6.0)
            m.quad(pts, [uv(p) for p in pts], out=np.array([0, side, 0]))
    return m


def roof():
    """A collapsed roof: two charred beams resting from a wall top down to
    the floor, a third snapped, and a corrugated sheet sagging on them."""
    m = Mesh(PROPS)
    for z in (-4.0, 0.0, 4.0):
        hi = 8.2 if z != 0.0 else 5.0
        bent_cylinder_between(m, (-7.0, hi, z), (6.5, 0.4, z + 0.8), 0.32, 6, "char")
    # sheets lying on the beams (two panels, slightly bent)
    for dz in (-2.4, 2.4):
        sh = sheet_piece(15.0, 4.6, -0.5, 5)
        slope = math.atan2(8.2 - 0.6, 13.5)
        m.merge(sh, at=(-0.3, 4.4, dz), yaw=0.0, tilt=(0.0, -slope))
    return m


# ------------------------------------------------------------------ build
# name: (builder, atlas, alpha mode, material, cast shadow, double sided)
PATCH_PIECES = {
    "Patch_Gravel": (lambda: disc("gravel", 20.0, seed=1), "Transparency", "Ground", False, False),
    "Patch_Scorch": (lambda: disc("scorch", 16.0, seed=2), "Transparency", "Ground", False, False),
    "Patch_Stubble": (lambda: disc("stubble", 12.0, seed=3), "Transparency", "Grass", False, False),
    "Patch_Stain": (lambda: disc("stain", 14.0, seed=4), "Transparency", "Ground", False, False),
    "Trample": (lambda: ribbon("trample", 72.0, 6.0, curve=0.0012, seed=5), "Transparency", "Ground", False, False),
    "Wire_Coil": (lambda: wire_coil(seed=6), "Transparency", "Metal", False, True),
}
PROP_PIECES = {
    "Hesco_3": (hesco3, "Overlay", "Fabric", True, False),
    "Jersey": (lambda: jersey(seed=11), "Overlay", "Concrete", True, False),
    "Drum": (lambda: drum("drum"), "Overlay", "Metal", True, False),
    "Drum_Red": (lambda: drum("drum2"), "Overlay", "Metal", True, False),
    "Drums": (drums, "Overlay", "Metal", True, False),
    "Tyre": (tyre_grounded, "Overlay", "Rubber", True, False),
    "Tyres": (tyres, "Overlay", "Rubber", True, False),
    "Crate": (crate, "Overlay", "WoodPlanks", True, False),
    "Crates": (crates, "Overlay", "WoodPlanks", True, False),
    "Picket": (picket, "Overlay", "Metal", False, False),
    "Pole": (lambda: pole()[0], "Overlay", "Wood", True, False),
    "Pole_Snapped": (lambda: pole(snapped=11.0)[0], "Overlay", "Wood", True, False),
    "Pole_Top": (pole_top, "Overlay", "Wood", True, False),
    "Adobe_Wall": (lambda: adobe_wall(seed=21), "Overlay", "Brick", True, False),
    "Adobe_Gap": (lambda: adobe_wall(seed=22, gap=(1.0, 8.0, 2.2)), "Overlay", "Brick", True, False),
    "Adobe_Door": (lambda: adobe_wall(seed=23, door=(-4.0, 4.0, 7.0)), "Overlay", "Brick", True, False),
    "Roof": (roof, "Overlay", "CorrodedMetal", True, True),
    "Rubble": (lambda: rubble(31), "Overlay", "Brick", True, False),
    "Sheet": (sheet_piece, "Overlay", "CorrodedMetal", False, True),
    "Wire_Span": (wire_span, "Overlay", "Metal", False, False),
}
ASSETS = {
    "GroundPatches": (PATCH_PIECES, "patches", "GroundPatches", 16.0),
    "ConflictDressing": (PROP_PIECES, "props", "ConflictProps", 64.0),
}


def build(name):
    pieces, tex, atlas, density = ASSETS[name]
    out = ROOT / "assets" / "exported" / name
    out.mkdir(parents=True, exist_ok=True)
    parts, gparts = [], []
    for pname, (make, alpha, material, shadow, double) in pieces.items():
        v, uv, f = make().arrays()
        mirrored = glb.check_uv_orientation(v, uv, f)
        if mirrored > 0.02:
            print(f"note {pname}: {mirrored:.0%} of triangles have mirrored UVs")
        lo, hi = v.min(axis=0), v.max(axis=0)
        centre = (lo + hi) / 2
        gparts.append({"name": pname, "v": v, "f": f, "uv": uv})
        parts.append({
            "name": pname, "path": "", "center": [round(float(x), 4) for x in centre],
            "size": [round(float(x), 4) for x in hi - lo], "tex": tex, "tris": int(len(f)),
            "query": False, "collide": False, "shadow": shadow, "material": material, "alpha": alpha,
            "double_sided": double, "pivot_offset": [round(float(-x), 4) for x in centre],
        })
        print(f"{name:16s} {pname:14s} {len(f):5d} tris  size {np.round(hi - lo, 2)}")
    glb.write(str(out / f"{name}.glb"), gparts)
    textures = {tex: {"color": f"{name}_{tex}_color.png", "normal": f"{name}_{tex}_normal.png"}}
    shutil.copyfile(TEX / f"{atlas}_color.png", out / textures[tex]["color"])
    shutil.copyfile(TEX / f"{atlas}_normal.png", out / textures[tex]["normal"])
    markers = []
    if name == "ConflictDressing":
        _, pm = pole()
        markers = [dict(m, part="Pole") for m in pm]
    manifest = {
        "name": name, "primary": None, "pivots": {"": [0.0, 0.0, 0.0]}, "parts": parts,
        "attachments": [], "markers": markers, "textures": textures, "texel_density": {tex: density},
        "previews": [], "triangles": sum(p["tris"] for p in parts),
        "meta": {"kit": name, "no_primary": True},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"wrote {out.relative_to(ROOT)}: {len(parts)} meshes, {manifest['triangles']} tris")


if __name__ == "__main__":
    for n in (sys.argv[1:] or list(ASSETS)):
        build(n)
