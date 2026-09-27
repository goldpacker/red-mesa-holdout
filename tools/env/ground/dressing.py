#!/usr/bin/env python3
"""Ground dressing meshes (ENV-3, FACELIFT_PLAN 1d) -> assets/exported/GroundDressing/.

    .venv-env/bin/python tools/env/ground/dressing.py

A handful of small meshes, all mapped onto the one shared atlas made by
dressing_textures.py, that server/GroundDressing.luau instances across the
basin floor (a few MeshIds reused many times):

  Scrub_A, Scrub_B, Creosote, Saltbush, Grass   alpha cards (DoubleSided),
        crossed vertical cards cut to the foliage silhouette + a canopy
        card seen from above + a soft contact-shadow card on the ground.
        The cards are cut to the silhouette, so the bushes (not the grass)
        cast mound-shaped shadows (shadows ignore alpha).
  Branch_A, Branch_B     dead branches lying on the sand (opaque, bark band)
  Pebbles_A, Pebbles_B   scattered pebbles (opaque, rock region)
  Rocks_A, Rocks_B       small rock clusters for boulder feet (opaque)
  Tracks_A, Tracks_B     old tyre tracks, flat alpha ribbons (tracks band)
  Crater                 an old wind-filled crater, flat alpha disc

Each mesh is built around its ground point (0, 0, 0) in Roblox space; the
manifest's pivot_offset puts the MeshPart's pivot there, so Lua places a
piece with PivotTo(ground CFrame). Deterministic (fixed seeds).
"""
from __future__ import annotations

import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import glb  # noqa: E402

ROOT = HERE.parents[2]
NAME = "GroundDressing"
OUT = ROOT / "assets" / "exported" / NAME
TEX = ROOT / "assets" / "textures" / "ground"
ATLAS = json.loads((TEX / "dressing.json").read_text())
ALPHA = np.asarray(__import__("PIL.Image", fromlist=["Image"]).open(TEX / "GroundDressing_color.png"))[..., 3] / 255.0
REG = ATLAS["regions"]
S = ATLAS["size"]


class Mesh:
    def __init__(self):
        self.v: list = []
        self.uv: list = []
        self.f: list = []

    def quad(self, corners, uvs):
        """corners: 4 points (a, b, c, d) counter-clockwise seen from the front."""
        i = len(self.v)
        self.v += [list(c) for c in corners]
        self.uv += [list(u) for u in uvs]
        self.f += [[i, i + 1, i + 2], [i, i + 2, i + 3]]

    def add(self, v, uv, f):
        i = len(self.v)
        self.v += [list(x) for x in v]
        self.uv += [list(x) for x in uv]
        self.f += [[a + i, b + i, c + i] for a, b, c in f]

    def arrays(self):
        return np.array(self.v, float), np.array(self.uv, float), np.array(self.f, np.int64)


def region_uv(region, fx, fy, inset=1.5):
    """(fx, fy) in 0..1 of a region (fy = 0 at its top) -> glTF uv."""
    x, y, w, h = REG[region]
    return ((x + inset + fx * (w - 2 * inset)) / S, (y + inset + fy * (h - 2 * inset)) / S)


# ------------------------------------------------------------------ plants
def silhouette(region, cols=9, pad=0.04):
    """Top edge of a card's foliage (fy, 0 = region top) at `cols` columns,
    and the left/right extent, from the atlas alpha. Cards are cut to it so
    the mip-blurred alpha never shows the card's rectangle."""
    x, y, w, h = REG[region]
    a = ALPHA[y:y + h, x:x + w] > 0.08
    colsum = a.any(axis=0)
    xs = np.flatnonzero(colsum)
    lo, hi = xs[0] / w, (xs[-1] + 1) / w
    fx = np.linspace(max(lo - pad, 0), min(hi + pad, 1), cols)
    tops = []
    for f in fx:
        c0 = int(np.clip(f * w - w / (2 * cols), 0, w - 1))
        c1 = int(np.clip(f * w + w / (2 * cols), c0 + 1, w))
        rows = np.flatnonzero(a[:, c0:c1].any(axis=1))
        tops.append(max(rows[0] / h - pad, 0) if len(rows) else 0.92)
    return fx, np.array(tops)


def card(m, region, yaw, width, height, sink=0.15, lean=0.0):
    """Vertical alpha card on the origin, rotated by yaw (radians), cut to
    the foliage silhouette (a strip of quads from the base to its top edge)."""
    dx, dz = math.cos(yaw), math.sin(yaw)
    side = np.array([dx, 0.0, dz])
    normal = np.array([-dz, 0.0, dx])
    fx, tops = silhouette(region)
    verts, uvs = [], []
    for f, t in zip(fx, tops):
        base = side * (f - 0.5) * width + np.array([0, -sink, 0])
        top = base + np.array([0, (1 - t) * height, 0]) + normal * lean * (1 - t) * height
        verts += [base, top]
        uvs += [region_uv(region, f, 1.0), region_uv(region, f, t)]
    faces = []
    for i in range(len(fx) - 1):
        a, b, c, d = 2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1
        faces += [[a, b, c], [a, c, d]]
    v = np.array(verts)
    fn = np.cross(v[faces[0][1]] - v[faces[0][0]], v[faces[0][2]] - v[faces[0][0]])
    if np.dot(fn, normal) < 0:
        faces = [[p, r, q] for p, q, r in faces]
    m.add(verts, uvs, faces)


def disc_card(m, region, size, y, rot=0.0, sides=10):
    """Horizontal polygon card facing up (canopy seen from above)."""
    verts = [(0.0, y, 0.0)]
    uvs = [region_uv(region, 0.5, 0.5)]
    for k in range(sides):
        a = rot + 2 * math.pi * k / sides
        verts.append((math.cos(a) * size / 2, y, math.sin(a) * size / 2))
        uvs.append(region_uv(region, 0.5 + 0.5 * math.cos(a - rot), 0.5 + 0.5 * math.sin(a - rot)))
    faces = [[0, 1 + k, 1 + (k + 1) % sides] for k in range(sides)]
    v = np.array(verts)
    if np.cross(v[faces[0][1]] - v[0], v[faces[0][2]] - v[0])[1] < 0:
        faces = [[a, c, b] for a, b, c in faces]
    m.add(verts, uvs, faces)


def flat_card(m, region, size, y, rot=0.0):
    """Horizontal card facing up, centred on the origin."""
    h = size / 2
    pts = []
    for fx, fz in ((-1, 1), (1, 1), (1, -1), (-1, -1)):
        x, z = fx * h, fz * h
        pts.append((x * math.cos(rot) - z * math.sin(rot), y, x * math.sin(rot) + z * math.cos(rot)))
    uvs = [region_uv(region, 0, 1), region_uv(region, 1, 1), region_uv(region, 1, 0), region_uv(region, 0, 0)]
    a, b, c, d = (np.array(p) for p in pts)
    if np.cross(b - a, d - a)[1] < 0:
        pts = [pts[1], pts[0], pts[3], pts[2]]
        uvs = [uvs[1], uvs[0], uvs[3], uvs[2]]
    m.quad(pts, uvs)


def bush(region, n_cards, width, height, top=None, shadow=None, seed=0, lean=0.12):
    rng = np.random.default_rng(seed)
    m = Mesh()
    for i in range(n_cards):
        yaw = math.pi * i / n_cards + rng.uniform(-0.15, 0.15)
        card(m, region, yaw, width * rng.uniform(0.9, 1.1), height * rng.uniform(0.9, 1.08),
             lean=lean * rng.choice([-1, 1]))
    if top:
        disc_card(m, "top", top[0], top[1], rng.uniform(0, math.pi))
    if shadow:
        disc_card(m, "shadow", shadow, 0.06, rng.uniform(0, math.pi), sides=8)
    return m


# ------------------------------------------------------------------ branches
def tube(m, p0, p1, r0, r1, u0, sides=6):
    """Tapered tube p0 -> p1 mapped onto the bark band (U along, V around)."""
    p0, p1 = np.array(p0, float), np.array(p1, float)
    axis = p1 - p0
    length = float(np.linalg.norm(axis))
    a = axis / length
    ref = np.array([0.0, 1.0, 0.0]) if abs(a[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
    b1 = np.cross(a, ref)
    b1 /= np.linalg.norm(b1)
    b2 = np.cross(a, b1)
    bx, by, bw, bh = REG["bark"]
    along = ATLAS["bark_studs"][0]
    verts, uvs = [], []
    for end, (p, r) in enumerate(((p0, r0), (p1, r1))):
        for k in range(sides + 1):
            t = 2 * math.pi * k / sides
            verts.append(p + r * (math.cos(t) * b1 + math.sin(t) * b2))
            uvs.append(((u0 + end * length) / along, (by + 1 + (bh - 2) * k / sides) / S))
    faces = []
    for k in range(sides):
        a0, a1 = k, k + 1
        c0, c1 = sides + 1 + k, sides + 2 + k
        faces += [[a0, c0, c1], [a0, c1, a1]]
    # outward winding check (first face against the radial direction)
    v = np.array(verts)
    fn = np.cross(v[faces[0][1]] - v[faces[0][0]], v[faces[0][2]] - v[faces[0][0]])
    if np.dot(fn, v[faces[0][0]] - p0) < 0:
        faces = [[x, z, y] for x, y, z in faces]
    m.add(verts, uvs, faces)
    return u0 + length


def branch(seed):
    rng = np.random.default_rng(seed)
    m = Mesh()
    length = rng.uniform(4.5, 6.5)
    r = rng.uniform(0.18, 0.26)
    yaw = 0.0
    p = np.array([-length / 2, r * 0.7, 0.0])
    u = 0.0
    pts = [p]
    for i in range(4):  # gently kinked main limb lying on the ground
        yaw += rng.normal(0, 0.25)
        q = pts[-1] + np.array([math.cos(yaw), 0, math.sin(yaw)]) * (length / 4)
        q[1] = r * 0.7 * (1 - 0.35 * (i + 1) / 4)
        u = tube(m, pts[-1], q, r * (1 - 0.18 * i), r * (1 - 0.18 * (i + 1)), u)
        pts.append(q)
    for j in range(3):  # side twigs, some raised off the ground
        base = pts[rng.integers(1, 4)]
        dirn = np.array([rng.uniform(-0.6, 0.6), rng.uniform(0.2, 0.9), rng.choice([-1, 1]) * rng.uniform(0.5, 1.0)])
        dirn /= np.linalg.norm(dirn)
        tip = base + dirn * rng.uniform(1.2, 2.4)
        tube(m, base, tip, r * 0.45, r * 0.12, rng.uniform(0, 8), sides=5)
    return m


# ------------------------------------------------------------------ rocks
def ico(subdiv=1):
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2), (10, 7, 6),
         (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11), (6, 2, 10),
         (8, 6, 7), (9, 8, 1)]
    v = [np.array(p, float) / np.linalg.norm(p) for p in v]
    for _ in range(subdiv):
        cache = {}
        nf = []

        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                p = v[a] + v[b]
                v.append(p / np.linalg.norm(p))
                cache[key] = len(v) - 1
            return cache[key]
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [(a, ab, ca), (b, bc, ab), (c, ca, bc), (ab, bc, ca)]
        f = nf
    return np.array(v), np.array(f)


def octa():
    v = np.array([(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)], float)
    f = np.array([(0, 2, 4), (4, 2, 1), (1, 2, 5), (5, 2, 0), (4, 3, 0), (1, 3, 4), (5, 3, 1), (0, 3, 5)])
    return v, f


def stone(m, rng, centre, size, flat=0.6, subdiv=1, bury=0.35):
    """subdiv -1: an 8-face pebble; 0/1: icosphere levels."""
    v, f = octa() if subdiv < 0 else ico(subdiv)
    noise_dirs = rng.normal(size=(5, 3))
    bump = sum(rng.uniform(0.05, 0.16) * np.maximum(0, v @ (d / np.linalg.norm(d))) ** 3 for d in noise_dirs)
    v = v * (1 + bump[:, None] - 0.12 * rng.random((len(v), 1)))
    v = v * np.array([size * rng.uniform(0.8, 1.2), size * flat, size * rng.uniform(0.8, 1.2)])
    yaw = rng.uniform(0, 2 * math.pi)
    rot = np.array([[math.cos(yaw), 0, -math.sin(yaw)], [0, 1, 0], [math.sin(yaw), 0, math.cos(yaw)]])
    v = v @ rot.T
    v = v + np.array(centre) + np.array([0, size * flat * (1 - 2 * bury), 0])
    # flat-shaded faces, each box-projected onto the rock region
    rx, ry, rw, rh = REG["rock"]
    pps = ATLAS["rock_px_per_stud"]
    off = rng.uniform(0, 1, 2)
    verts, uvs, faces = [], [], []
    for a, b, c in f:
        p = v[[a, b, c]]
        n = np.cross(p[1] - p[0], p[2] - p[0])
        ax = int(np.argmax(np.abs(n)))
        uaxes = {0: (2, 1), 1: (0, 2), 2: (0, 1)}[ax]
        for q in p:
            pu = (q[uaxes[0]] * pps / rw + off[0]) % 1.0
            pv = (q[uaxes[1]] * pps / rh + off[1]) % 1.0
            verts.append(q)
            uvs.append(((rx + 2 + pu * (rw - 4)) / S, (ry + 2 + pv * (rh - 4)) / S))
        i = len(verts) - 3
        faces.append([i, i + 1, i + 2])
    # wrapped UVs inside a face would smear across the region: re-centre per face
    uv = np.array(uvs)
    for k in range(0, len(uv), 3):
        tri = uv[k:k + 3]
        for dim, (lo, span) in enumerate(((rx, rw), (ry, rh))):
            vals = tri[:, dim] * S
            if vals.max() - vals.min() > span / 2:
                vals = np.where(vals < lo + span / 2, vals + span - 4, vals)
                vals = np.minimum(vals, lo + span - 2)
                tri[:, dim] = vals / S
        uv[k:k + 3] = tri
    m.add(verts, [tuple(x) for x in uv], faces)


def pebbles(seed, count, radius):
    rng = np.random.default_rng(seed)
    m = Mesh()
    for _ in range(count):
        r = radius * math.sqrt(rng.random())
        a = rng.uniform(0, 2 * math.pi)
        stone(m, rng, (r * math.cos(a), 0, r * math.sin(a)), rng.uniform(0.14, 0.4), flat=0.55, subdiv=-1, bury=0.3)
    return m


def rocks(seed, count):
    rng = np.random.default_rng(seed)
    m = Mesh()
    for i in range(count):
        size = rng.uniform(0.9, 2.1) if i < 2 else rng.uniform(0.35, 0.9)
        r = rng.uniform(0.5, 3.8) if i >= 2 else rng.uniform(0, 1.5)
        a = rng.uniform(0, 2 * math.pi)
        stone(m, rng, (r * math.cos(a), 0, r * math.sin(a)), size, flat=0.62, subdiv=1 if i < 2 else 0, bury=0.35)
    return m


# ------------------------------------------------------------------ flat decals
def track(seed, length, curve, width=6.0, step=3.0, y=0.07):
    """Tyre-track ribbon along a gentle curve (curve = 1/radius, sign = side)."""
    rng = np.random.default_rng(seed)
    x, y0, w = REG["tracks"][1], REG["tracks"][1], REG["tracks"][3]
    along = ATLAS["tracks_studs"][0]
    n = int(length / step)
    m = Mesh()
    heading = 0.0
    p = np.array([-length / 2, 0.0])
    pts, heads = [], []
    for i in range(n + 1):
        pts.append(p.copy())
        heads.append(heading)
        k = curve * (1 + 0.6 * math.sin(i / n * math.pi * rng.uniform(1.5, 2.5)))
        heading += k * step
        p = p + step * np.array([math.cos(heading), math.sin(heading)])
    pts = np.array(pts)
    pts -= pts.mean(axis=0)
    verts, uvs = [], []
    for i, (q, hd) in enumerate(zip(pts, heads)):
        side = np.array([-math.sin(hd), math.cos(hd)])
        for j, sgn in enumerate((-1, 1)):
            e = q + side * sgn * width / 2
            verts.append((e[0], y, e[1]))
            uvs.append((i * step / along, (y0 + 1 + j * (w - 2)) / S))
    faces = []
    for i in range(n):
        a, b, c, d = 2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2
        faces += [[a, b, c], [a, c, d]]
    v = np.array(verts)
    if np.cross(v[faces[0][1]] - v[faces[0][0]], v[faces[0][2]] - v[faces[0][0]])[1] < 0:
        faces = [[a, c, b] for a, b, c in faces]
    m.add(verts, uvs, faces)
    return m


def crater(seed, radius=10.0, y=0.06, rings=5, segs=28):
    rng = np.random.default_rng(seed)
    rx, ry, rw, rh = REG["crater"]
    m = Mesh()
    verts = [(0.0, y, 0.0)]
    uvs = [((rx + rw / 2) / S, (ry + rh / 2) / S)]
    for i in range(1, rings + 1):
        rr = radius * i / rings
        for j in range(segs):
            a = 2 * math.pi * j / segs
            verts.append((rr * math.cos(a), y + (0.12 if i == 3 else 0.0), rr * math.sin(a)))
            fx = 0.5 + 0.5 * (rr / radius) * math.cos(a) * 0.985
            fy = 0.5 + 0.5 * (rr / radius) * math.sin(a) * 0.985
            uvs.append(((rx + fx * rw) / S, (ry + fy * rh) / S))
    faces = []
    for j in range(segs):
        faces.append([0, 1 + j, 1 + (j + 1) % segs])
    for i in range(1, rings):
        b0 = 1 + (i - 1) * segs
        b1 = 1 + i * segs
        for j in range(segs):
            j1 = (j + 1) % segs
            faces += [[b0 + j, b1 + j, b1 + j1], [b0 + j, b1 + j1, b0 + j1]]
    v = np.array(verts)
    if np.cross(v[faces[0][1]] - v[faces[0][0]], v[faces[0][2]] - v[faces[0][0]])[1] < 0:
        faces = [[a, c, b] for a, b, c in faces]
    m.add(verts, uvs, faces)
    return m


# ------------------------------------------------------------------ build
# name: (builder, alpha mode, material, cast shadow)
PIECES = {
    "Scrub_A": (lambda: bush("scrub_a", 5, 3.8, 3.0, top=(3.0, 1.7), shadow=4.6, seed=1), "Transparency", "Grass", True),
    "Scrub_B": (lambda: bush("scrub_b", 3, 3.4, 2.7, shadow=4.0, seed=2), "Transparency", "Wood", True),
    "Creosote": (lambda: bush("creosote", 5, 4.6, 5.2, top=(3.6, 3.2), shadow=5.6, seed=3, lean=0.08), "Transparency", "Grass", True),
    "Saltbush": (lambda: bush("saltbush", 3, 6.0, 3.0, top=(4.2, 1.5), shadow=6.6, seed=4), "Transparency", "Grass", True),
    "Grass": (lambda: bush("grass", 3, 2.6, 1.7, seed=5, lean=0.18), "Transparency", "Grass", False),
    "Branch_A": (lambda: branch(21), "Overlay", "Wood", True),
    "Branch_B": (lambda: branch(22), "Overlay", "Wood", True),
    "Pebbles_A": (lambda: pebbles(31, 16, 2.6), "Overlay", "Rock", False),
    "Pebbles_B": (lambda: pebbles(32, 22, 3.6), "Overlay", "Rock", False),
    "Rocks_A": (lambda: rocks(41, 6), "Overlay", "Rock", True),
    "Rocks_B": (lambda: rocks(42, 8), "Overlay", "Rock", True),
    "Tracks_A": (lambda: track(51, 66.0, 1 / 90.0), "Transparency", "Sand", False),
    "Tracks_B": (lambda: track(52, 84.0, -1 / 140.0), "Transparency", "Sand", False),
    "Crater": (lambda: crater(61), "Transparency", "Sand", False),
}


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    parts, gparts = [], []
    for name, (make, alpha, material, shadow) in PIECES.items():
        v, uv, f = make().arrays()
        mirrored = glb.check_uv_orientation(v, uv, f)
        if mirrored > 0.0 and alpha == "Overlay" and not name.startswith(("Pebbles", "Rocks")):
            print(f"WARNING {name}: {mirrored:.0%} of triangles have mirrored UVs")
        lo, hi = v.min(axis=0), v.max(axis=0)
        centre = (lo + hi) / 2
        gparts.append({"name": name, "v": v, "f": f, "uv": uv})
        parts.append({
            "name": name, "path": "", "center": [round(float(x), 4) for x in centre],
            "size": [round(float(x), 4) for x in hi - lo], "tex": "dressing", "tris": int(len(f)),
            "query": False, "collide": False, "shadow": shadow, "material": material, "alpha": alpha,
            "double_sided": alpha == "Transparency" and name not in ("Tracks_A", "Tracks_B", "Crater"),
            "pivot_offset": [round(float(-x), 4) for x in centre],
        })
        print(f"{name:10s} {len(f):5d} tris  size {np.round(hi - lo, 2)}  {alpha}")
    glb.write(str(OUT / f"{NAME}.glb"), gparts)
    textures = {"dressing": {"color": f"{NAME}_dressing_color.png", "normal": f"{NAME}_dressing_normal.png"}}
    shutil.copyfile(TEX / "GroundDressing_color.png", OUT / textures["dressing"]["color"])
    shutil.copyfile(TEX / "GroundDressing_normal.png", OUT / textures["dressing"]["normal"])
    manifest = {
        "name": NAME, "primary": None, "pivots": {"": [0.0, 0.0, 0.0]}, "parts": parts,
        "attachments": [], "markers": [], "textures": textures, "texel_density": {"dressing": 64.0},
        "previews": [], "triangles": sum(p["tris"] for p in parts),
        "meta": {"kit": "ground_dressing", "no_primary": True},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(parts)} meshes, {manifest['triangles']} tris")


if __name__ == "__main__":
    build()
