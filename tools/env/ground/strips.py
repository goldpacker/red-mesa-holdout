#!/usr/bin/env python3
"""Road and wash edge strips (ENV-3, FACELIFT_PLAN 1c) -> assets/exported/GroundStrips/.

    .venv-env/bin/python tools/env/ground/strips.py

Mesh ribbons that lie on the live terrain (probe.py heightfield) along the
road and both washes, hiding the voxel-stepped paint edges:

  Road    core  t = -14..14   opaque, the terrain `RedMesaRoad` tile (at 512²)
                              with the ruts following the road (U across, V along)
          edge  |t| = 13.5..17.5 opaque gravel berm (strip atlas)
          edgeA |t| = 9..13.5 and 17.5..25, alpha ramps over the core and
                              onto the floor sand (strip atlas, Transparency)
  Wash    bank  q = 0.05..1.05 opaque bank: toe -> eroded lip (strip atlas)
          bankA q = -0.3..0.05 pebble bed fading in over the wash bed, and
                q = 1.05..1.6 sand spill fading out over the lip
          (q = 0 at the bank toe, q = 1 at the measured lip, per cross-section)

Beyond ~110-200 studs from the turret the wash pieces also clear the coarse
(LOD) terrain mesh, which fills the troughs in at a distance (see LOD_K).

Opaque and alpha pieces are separate MeshParts because transparent
SurfaceAppearances don't receive shadows (measured in Studio). Alpha pieces
sit a little above what they cover. Each chunk is built in its own frame,
yawed along the path, so its (Box) bounding volume hugs the strip.

The strips follow the lane waypoints in src/shared/Config.luau (paths.py).
The far end of the road and the closed ends of the wash troughs taper to a
point; the mesa end runs in under the landscape talus.
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
import paths  # noqa: E402
import probe  # noqa: E402

ROOT = HERE.parents[2]
NAME = "GroundStrips"
OUT = ROOT / "assets" / "exported" / NAME
TEX = ROOT / "assets" / "textures" / "ground"
ATLAS = json.loads((TEX / "strips.json").read_text())
PERIOD = ATLAS["period_studs"]
ROAD_TILE = ATLAS["road_tile"]
ROAD_U0 = ATLAS["road_u0"]
BANDS = ATLAS["bands"]
ATLAS_H = float(ATLAS.get("height", ATLAS["size"]))

STEP = 2.0            # studs between cross-sections
CHUNK = 150.0         # studs of path per chunk
ROW_TOL = 0.05        # studs: drop cross-sections a straight interpolation reproduces this well
WASH_ROW_TOL = 0.12   # banks follow bumpier terrain; settle() then lifts any dip
MAX_SKIP = 8          # ... up to 8 in a row (16 studs)
BASE = 0.12           # studs above the terrain
SLOPE_LIFT = 0.35     # extra lift per unit terrain slope (render vs physics on slopes)
ALPHA_LIFT = 0.08     # alpha pieces over what they cover
EDGE_LIFT = 0.08      # road edge (berm) over the core where they overlap

ROAD_CORE_T = [-14.0, -10.5, -7.0, -3.5, 0.0, 3.5, 7.0, 10.5, 14.0]
ROAD_EDGE_T = [13.5, 15.5, 17.5]
ROAD_EDGE_IN = [9.0, 11.25, 13.5]
ROAD_EDGE_OUT = [17.5, 19.5, 21.5, 23.5, 25.0]
ROAD_TAPER = 60.0      # studs over which the road's far end narrows to a point

BANK_Q = [0.05, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0, 1.05]
BANK_IN = [-0.3, -0.18, -0.06, 0.05]
BANK_OUT = [1.05, 1.2, 1.4, 1.6]
WASH_TOE = 6.5         # studs from the centre where the bank band's q = 0 (max)
FLOOR_Y = 2.0          # live basin floor height
LIP_Y = 1.6            # the lip is where the bank reaches this height (floor 2.0)
MIN_DEPTH = 1.2        # trough deeper than this at the centre -> full strip
# Terrain LOD (ENV-3F): beyond ~250-300 studs from the camera Roblox meshes
# the terrain from coarser voxels, which fills the concave wash troughs in
# (the bed and the bank toe rise, the lip sinks), so a strip lying 0.2 over
# the fine surface is poked through and the voxel paint edge shows (measured
# from the title camera: WashLeft/Right at 300-530 studs). Wash strips are
# lifted to clear a 16-stud box-filtered surface (the coarse mesh's shape)
# plus a margin, blended in with distance from the turret so the near banks
# (seen at full detail) still hug the ground. Flat floor and convex lips get
# no extra lift. Empirically a uniform +0.6 still let flecks through at
# 400-500 studs and +1.0 cleared them; this lift is >= that where it's needed.
LOD_K = 16.0           # studs: box filter / grid of the emulated coarse mesh
LOD_MARGIN = 0.3       # studs over it
LOD_NEAR, LOD_FAR = 110.0, 200.0   # plan distance from the turret: no lift -> full lift


class Field:
    def __init__(self, name):
        self.xs, self.zs, self.y, self.mat, self.land = probe.load(name)
        # fill holes (outside the corridor) with the floor height
        self.y = np.where(np.isfinite(self.y), self.y, 2.0)
        gz, gx = np.gradient(self.y, 2.0)
        self.slope = np.hypot(gx, gz)

    def _bil(self, a, px, pz):
        fx = (np.asarray(px) - self.xs[0]) / 2.0
        fz = (np.asarray(pz) - self.zs[0]) / 2.0
        ix = np.clip(np.floor(fx).astype(int), 0, len(self.xs) - 2)
        iz = np.clip(np.floor(fz).astype(int), 0, len(self.zs) - 2)
        tx = np.clip(fx - ix, 0, 1)
        tz = np.clip(fz - iz, 0, 1)
        return ((a[iz, ix] * (1 - tx) + a[iz, ix + 1] * tx) * (1 - tz)
                + (a[iz + 1, ix] * (1 - tx) + a[iz + 1, ix + 1] * tx) * tz)

    def height(self, px, pz):
        return self._bil(self.y, px, pz)

    def ground(self, px, pz):
        """Height a strip vertex sits at (before layer lifts): terrain + clearance."""
        return self.height(px, pz) + BASE + SLOPE_LIFT * self._bil(self.slope, px, pz)

    def land_over(self, px, pz):
        land = self._bil(np.where(np.isfinite(self.land), self.land, -1e3), px, pz)
        return land - self.height(px, pz)

    def lod(self, px, pz):
        """Height of the coarse (LOD) terrain mesh, emulated: the heightfield
        box-filtered over LOD_K studs, sampled on a LOD_K-aligned grid and
        interpolated bilinearly."""
        if not hasattr(self, "_lod"):
            k, n = LOD_K, int(LOD_K / 2.0)
            gx = np.arange(np.ceil(self.xs[0] / k) * k, self.xs[-1], k)
            gz = np.arange(np.ceil(self.zs[0] / k) * k, self.zs[-1], k)
            G = np.empty((len(gz), len(gx)))
            for j, z in enumerate(gz):
                iz = int(round((z - self.zs[0]) / 2.0))
                for i, x in enumerate(gx):
                    ix = int(round((x - self.xs[0]) / 2.0))
                    G[j, i] = self.y[max(0, iz - n // 2):iz + n // 2 + 1, max(0, ix - n // 2):ix + n // 2 + 1].mean()
            self._lod = (gx, gz, G)
        gx, gz, G = self._lod
        fx = np.clip((np.asarray(px) - gx[0]) / LOD_K, 0, len(gx) - 1.001)
        fz = np.clip((np.asarray(pz) - gz[0]) / LOD_K, 0, len(gz) - 1.001)
        ix, iz = np.floor(fx).astype(int), np.floor(fz).astype(int)
        tx, tz = fx - ix, fz - iz
        return ((G[iz, ix] * (1 - tx) + G[iz, ix + 1] * tx) * (1 - tz)
                + (G[iz + 1, ix] * (1 - tx) + G[iz + 1, ix + 1] * tx) * tz)

    def lod_lift(self, px, pz, y):
        """y raised to clear the coarse terrain mesh, blended in with distance
        from the turret (see LOD_K)."""
        d = np.hypot(px, pz)
        w = np.clip((d - LOD_NEAR) / (LOD_FAR - LOD_NEAR), 0, 1)
        w = w * w * (3 - 2 * w)
        return y + w * np.maximum(0.0, self.lod(px, pz) + LOD_MARGIN - y)


def smooth(a, k):
    if k <= 1:
        return a
    pad = np.pad(a, (k, k), mode="edge")
    ker = np.ones(2 * k + 1) / (2 * k + 1)
    return np.convolve(pad, ker, mode="valid")


def mesa_end(f, c, perp, half):
    """Last row to build: a couple of rows after the whole cross-section is
    under the mesa mesh (or the path's end)."""
    for i in range(len(c)):
        pts = [c[i] + t * perp[i] for t in (-half, 0.0, half)]
        over = [f.land_over(p[0], p[1]) for p in pts]
        if min(over) > 0.25:
            return min(i + 2, len(c) - 1)
    return len(c) - 1


def frame_basis(tan):
    """perp with T_s x T_t = up (Roblox: T_s = +X -> T_t = -Z)."""
    return np.stack([tan[:, 1], -tan[:, 0]], axis=1)


class Grid:
    """A ribbon piece: rows = cross-sections, cols = offsets; vertex arrays."""

    def __init__(self, P, UV):
        self.P = P      # (rows, cols, 3) world
        self.UV = UV    # (rows, cols, 2) glTF uv

    def settle(self, f, clear, rounds=4):
        """Raise vertices until every triangle clears the terrain by `clear`
        at a set of interior sample points (convex terrain between vertices)."""
        bcs = [(1 / 3, 1 / 3, 1 / 3), (0.5, 0.5, 0), (0.5, 0, 0.5), (0, 0.5, 0.5),
               (0.7, 0.15, 0.15), (0.15, 0.7, 0.15), (0.15, 0.15, 0.7)]
        rows, cols = self.P.shape[:2]
        for _ in range(rounds):
            v = self.P.reshape(-1, 3)
            _, _, fa = self.triangles(0, rows - 1)
            need = np.zeros(len(v))
            for bc in bcs:
                p = v[fa[:, 0]] * bc[0] + v[fa[:, 1]] * bc[1] + v[fa[:, 2]] * bc[2]
                deficit = f.height(p[:, 0], p[:, 2]) + clear - p[:, 1]
                for k in range(3):
                    np.maximum.at(need, fa[:, k], deficit)
            if need.max() <= 1e-3:
                break
            v[:, 1] += np.clip(need, 0, None) + np.where(need > 0, 0.01, 0)
            self.P = v.reshape(rows, cols, 3)
        return self

    def under_mesa(self, f):
        """Where the mesa landscape mesh covers the ground, keep the strip
        just under the mesh (it runs on underneath the talus)."""
        x, y, z = self.P[..., 0], self.P[..., 1], self.P[..., 2]
        over = f.land_over(x, z)
        # Under the mesh the strip stays at floor level and dives into the
        # rising mesa terrain instead of climbing it (hidden either way), so
        # its bounding box never rises into the turret's sight lines.
        self.P[..., 1] = np.where(over > 0.25, np.minimum(y, FLOOR_Y + 0.3), y)
        return self

    def triangles(self, r0, r1):
        rows, cols = self.P.shape[:2]
        v = self.P[r0:r1 + 1].reshape(-1, 3)
        uv = self.UV[r0:r1 + 1].reshape(-1, 2)
        f = []
        n = cols
        for i in range(r1 - r0):
            for j in range(cols - 1):
                a, b = i * n + j, i * n + j + 1
                c, d = (i + 1) * n + j + 1, (i + 1) * n + j
                f += [[a, b, c], [a, c, d]]
        f = np.array(f, np.int64)
        if len(f):
            fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
            flip = fn[:, 1] < 0
            f[flip] = f[flip][:, [0, 2, 1]]
        return v, uv, f


def piece(centre, perp, s, offsets, y_of, uv_of, width_scale=None):
    rows, cols = len(centre), len(offsets)
    k = np.ones(rows) if width_scale is None else width_scale
    t = np.asarray(offsets)[None, :] * k[:, None] if np.ndim(offsets) == 1 else offsets * k[:, None]
    xz = centre[:, None, :] + t[..., None] * perp[:, None, :]
    y = y_of(xz[..., 0], xz[..., 1])
    P = np.stack([xz[..., 0], y, xz[..., 1]], axis=-1)
    UV = uv_of(s, np.asarray(offsets) if np.ndim(offsets) == 1 else offsets)
    return Grid(P, UV)


def finish(g, f, clear):
    return g.settle(f, clear).under_mesa(f)


# ------------------------------------------------------------------ road
def road():
    f = Field("Road")
    c = paths.centreline("Road", STEP)
    s, tan, _ = paths.frames(c)
    perp = frame_basis(tan)
    end = mesa_end(f, c, perp, ROAD_EDGE_OUT[-1])
    c, s, tan, perp = c[:end + 1], s[:end + 1], tan[:end + 1], perp[:end + 1]
    k = np.clip(s / ROAD_TAPER, 0, 1)
    k = k * k * (3 - 2 * k)
    k[0] = 0.02

    def y_core(x, z):
        return f.ground(x, z)

    def y_edge(x, z):
        return f.ground(x, z) + EDGE_LIFT

    def y_alpha(x, z):
        return f.ground(x, z) + EDGE_LIFT + ALPHA_LIFT

    def uv_core(ss, tt):
        u = np.broadcast_to(np.asarray(tt)[None, :] / ROAD_TILE + ROAD_U0, (len(ss), len(tt)))
        v = np.broadcast_to(ss[:, None] / ROAD_TILE, (len(ss), len(tt)))
        return np.stack([u, v], axis=-1)

    def uv_band(sigma):
        r0, r1 = BANDS["shoulder+" if sigma > 0 else "shoulder-"]["rows"]
        a0, a1 = BANDS["shoulder+"]["abs_t"]

        def fn(ss, tt):
            a = np.abs(np.asarray(tt))
            u = np.broadcast_to(-sigma * ss[:, None] / PERIOD, (len(ss), len(tt)))
            row = r0 + 0.5 + (a - a0) / (a1 - a0) * (r1 - r0 - 1)
            v = np.broadcast_to(row[None, :] / ATLAS_H, (len(ss), len(tt)))
            return np.stack([u, v], axis=-1)
        return fn

    grids = {"core": [finish(piece(c, perp, s, ROAD_CORE_T, y_core, uv_core, k), f, 0.06)], "edge": [], "edgeA": []}
    for sigma in (1, -1):
        edge = np.array(ROAD_EDGE_T) * sigma
        grids["edge"].append(finish(piece(c, perp, s, edge, y_edge, uv_band(sigma), k), f, 0.1))
        for ring in (ROAD_EDGE_IN, ROAD_EDGE_OUT):
            grids["edgeA"].append(finish(piece(c, perp, s, np.array(ring) * sigma, y_alpha, uv_band(sigma), k), f, 0.14))
    return "Road", c, s, tan, grids, f


# ------------------------------------------------------------------ washes
def lip_profile(f, c, perp, sigma):
    """Distance from the centreline to the lip (h >= LIP_Y) on one side."""
    ts = np.arange(0.0, 40.0, 0.5)
    pts = c[:, None, :] + (sigma * ts)[None, :, None] * perp[:, None, :]
    h = f.height(pts[..., 0], pts[..., 1])
    lip = np.full(len(c), np.nan)
    for i in range(len(c)):
        above = np.flatnonzero(h[i] >= LIP_Y)
        if len(above):
            lip[i] = ts[above[0]]
    return lip


def wash(name):
    f = Field(name)
    c = paths.centreline(name, STEP)
    s, tan, _ = paths.frames(c)
    perp = frame_basis(tan)
    depth = 2.0 - f.height(c[:, 0], c[:, 1])
    deep = np.flatnonzero(depth > MIN_DEPTH)
    start = max(deep[0] - 12, 0)                    # taper into the closed far end
    # The mesa end runs at full width in under the landscape talus.
    end = mesa_end(f, c, perp, 34.0)
    c, s, tan, perp, depth = c[start:end + 1], s[start:end + 1], tan[start:end + 1], perp[start:end + 1], depth[start:end + 1]
    lips = {}
    for sigma in (1, -1):
        lip = lip_profile(f, c, perp, sigma)
        lip = np.where(np.isfinite(lip), lip, 0.0)
        # median then mean, so single notches don't kink the band
        med = np.array([np.median(lip[max(0, i - 3):i + 4]) for i in range(len(lip))])
        lips[sigma] = smooth(med, 5)
    # width scale: the strip closes where the trough ends
    k = np.clip((depth - 0.3) / (MIN_DEPTH - 0.3), 0, 1)
    k = smooth(k * k * (3 - 2 * k), 2)
    first_full = int(np.argmax(k > 0.999))
    k[first_full:] = 1.0      # taper only into the closed far end

    r0, r1 = BANDS["bank"]["rows"]
    q0, q1 = BANDS["bank"]["q"]

    grids = {"bank": [], "bankA": []}
    for sigma in (1, -1):
        lip = np.maximum(lips[sigma], 8.0)
        toe = np.minimum(WASH_TOE, 0.35 * lip)

        def make(qs, lift):
            qs = np.asarray(qs)
            t = (toe[:, None] + qs[None, :] * (lip - toe)[:, None]) * sigma
            t = np.where(np.abs(t) < 1.5, 1.5 * sigma, t)
            xz = c[:, None, :] + (t * k[:, None])[..., None] * perp[:, None, :]
            y = f.lod_lift(xz[..., 0], xz[..., 1], f.ground(xz[..., 0], xz[..., 1]) + lift)
            P = np.stack([xz[..., 0], y, xz[..., 1]], axis=-1)
            u = np.broadcast_to(-sigma * s[:, None] / PERIOD, t.shape)
            row = r0 + 0.5 + (qs - q0) / (q1 - q0) * (r1 - r0 - 1)
            v = np.broadcast_to(row[None, :] / ATLAS_H, t.shape)
            return finish(Grid(P, np.stack([u, v], axis=-1)), f, 0.06 + lift)

        grids["bank"].append(make(BANK_Q, 0.0))
        grids["bankA"].append(make(BANK_IN, ALPHA_LIFT))
        grids["bankA"].append(make(BANK_OUT, ALPHA_LIFT))
    short = {"WashLeft": "WashL", "WashRight": "WashR"}[name]
    return short, c, s, tan, grids, f


# ------------------------------------------------------------------ build
KINDS = {
    # kind: (texture group, alpha mode, material, part colour, terrain clearance)
    # Opaque pieces use Overlay (the alpha is exactly 1 where they sample, and
    # Overlay shares the colour map's base copy; AlphaMode.Opaque would cost
    # another copy of the map in texture memory - measured +0.67 MB).
    "core": ("road", "Overlay", "Ground", (1, 1, 1), 0.06),
    "edge": ("strips", "Overlay", "Ground", (0.65, 0.46, 0.31), 0.10),
    "edgeA": ("strips", "Transparency", "Ground", (1, 1, 1), 0.14),
    "bank": ("strips", "Overlay", "Sand", (0.75, 0.59, 0.45), 0.06),
    "bankA": ("strips", "Transparency", "Sand", (1, 1, 1), 0.14),
}


def keep_rows(grids, s, tol=ROW_TOL):
    """Cross-sections to keep: greedy, as long as every vertex of every
    piece between two kept rows lies within `tol` (height) and 3 * `tol`
    (plan) of the straight interpolation between them (flat straight road
    -> long quads)."""
    allP = np.concatenate([g.P for gl in grids.values() for g in gl], axis=1)
    n = len(s)
    keep = [0]
    i = 0
    while i < n - 1:
        j = min(i + MAX_SKIP, n - 1)
        while j > i + 1:
            t = (s[i + 1:j] - s[i]) / (s[j] - s[i])
            interp = allP[i][None] + (allP[j] - allP[i])[None] * t[:, None, None]
            d = allP[i + 1:j] - interp
            if np.abs(d[..., 1]).max() < tol and np.hypot(d[..., 0], d[..., 2]).max() < 3 * tol:
                break
            j -= 1
        keep.append(j)
        i = j
    return np.array(keep)


def chunk_frame(c, i0, i1):
    d = c[i1] - c[i0]
    d = d / max(np.linalg.norm(d), 1e-9)
    X = np.array([d[0], 0.0, d[1]])
    Y = np.array([0.0, 1.0, 0.0])
    Z = np.cross(X, Y)
    return np.stack([X, Y, Z], axis=1)  # columns = axes


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    parts, gparts = [], []
    stats = {}
    for name, c, s, tan, grids, field in [road(), wash("WashLeft"), wash("WashRight")]:
        rows = keep_rows(grids, s, ROW_TOL if name == "Road" else WASH_ROW_TOL)
        full = len(c)
        c, s = c[rows], s[rows]
        for kind, glist in grids.items():
            for g in glist:
                g.P, g.UV = g.P[rows], g.UV[rows]
                g.settle(field, KINDS[kind][4]).under_mesa(field)
        print(f"{name}: kept {len(rows)} of {full} cross-sections")
        n = len(c)
        nchunks = max(1, int(round(s[-1] - s[0]) / CHUNK))
        bounds = np.linspace(0, n - 1, nchunks + 1).round().astype(int)
        for ci in range(nchunks):
            i0, i1 = int(bounds[ci]), int(bounds[ci + 1])
            R = chunk_frame(c, i0, i1)
            for kind, glist in grids.items():
                vs, uvs, fs = [], [], []
                off = 0
                for g in glist:
                    v, uv, f = g.triangles(i0, i1)
                    if not len(f):
                        continue
                    # drop degenerate (fully tapered) triangles
                    area = np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
                    f = f[area > 1e-4]
                    vs.append(v)
                    uvs.append(uv)
                    fs.append(f + off)
                    off += len(v)
                if not fs or not sum(len(x) for x in fs):
                    continue
                v = np.concatenate(vs)
                uv = np.concatenate(uvs)
                f = np.concatenate(fs)
                # drop vertices no triangle uses (the importer does, and the
                # part's centre/size must match the imported mesh)
                used = np.unique(f)
                remap = -np.ones(len(v), dtype=np.int64)
                remap[used] = np.arange(len(used))
                v, uv, f = v[used], uv[used], remap[f]
                mirrored = glb.check_uv_orientation(v, uv, f)
                if mirrored > 0.01:
                    raise SystemExit(f"{name} {kind}: {mirrored:.0%} of triangles have mirrored UVs")
                origin = v.mean(axis=0)
                local = (v - origin) @ R          # world -> chunk frame
                lo, hi = local.min(axis=0), local.max(axis=0)
                lc = (lo + hi) / 2
                centre = origin + R @ lc
                pname = f"{name}_C{ci:02d}_{kind}"
                gparts.append({"name": pname, "v": local, "f": f, "uv": uv,
                               "n": glb.vertex_normals(local, f)})
                tex, alpha, material, colour, _ = KINDS[kind]
                parts.append({
                    "name": pname, "path": "", "center": [round(float(x), 4) for x in centre],
                    "size": [round(float(x), 4) for x in hi - lo],
                    "rotation": [[round(float(R[i][j]), 6) for j in range(3)] for i in range(3)],
                    "tex": tex, "tris": int(len(f)), "query": False, "collide": False, "shadow": False,
                    "material": material, "alpha": alpha, "color": list(colour),
                })
                stats[kind] = stats.get(kind, 0) + len(f)
        print(f"{name}: {nchunks} chunks, {s[-1] - s[0]:.0f} studs")
    glb.write(str(OUT / f"{NAME}.glb"), gparts)
    textures = {
        "strips": {"color": f"{NAME}_strips_color.png", "normal": f"{NAME}_strips_normal.png"},
        "road": {"color": f"{NAME}_road_color.png", "normal": f"{NAME}_road_normal.png"},
    }
    shutil.copyfile(TEX / "GroundStrips_color.png", OUT / textures["strips"]["color"])
    shutil.copyfile(TEX / "GroundStrips_normal.png", OUT / textures["strips"]["normal"])
    shutil.copyfile(TEX / "GroundRoad_color.png", OUT / textures["road"]["color"])
    shutil.copyfile(TEX / "GroundRoad_normal.png", OUT / textures["road"]["normal"])
    manifest = {
        "name": NAME, "primary": None, "pivots": {"": [0.0, 0.0, 0.0]}, "parts": parts,
        "attachments": [], "markers": [], "textures": textures,
        # the road core shows the terrain RedMesaRoad tile at 512² (strip_textures.py)
        "texel_density": {"strips": round(1024 / PERIOD, 1), "road": round(512 / ROAD_TILE, 1)},
        "previews": [], "triangles": sum(p["tris"] for p in parts),
        "meta": {"kit": "ground_strips", "no_primary": True},
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}: {len(parts)} parts, {manifest['triangles']} tris {stats}")


if __name__ == "__main__":
    build()
