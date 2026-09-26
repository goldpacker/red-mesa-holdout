#!/usr/bin/env python3
"""Build the landscape meshes' geometry (high-poly + game-resolution chunks).

For each piece (pieces.py):
  1. signed distance of the gameplay terrain it wraps (ops.py, captured from
     TerrainBuilder), with the washes carved out;
  2. envelope: close notches narrower than `closing`, smooth by `sigma`, and
     never cut inside the terrain (min with the raw distance);
  3. sculpt outward only (so the terrain always stays inside): horizontal
     strata ledges and recesses (strata.py), meandering gullies, a flat-top
     offset, then a talus fillet onto the basin floor, fanning out under the
     gullies;
  4. marching cubes -> high-poly; faces under the floor are dropped;
  5. quadric decimation -> low-poly, split into chunks (<= CHUNK_TRIS and
     sized for the texel density).

  .venv-env/bin/python tools/env/landscape/shape.py [Piece ...] [--ops FILE]
Writes assets/source/landscape/build/<Piece>.npz (git-ignored; regenerable)
and prints stats. Needs .venv-env: python3 -m venv .venv-env &&
.venv-env/bin/pip install numpy scipy scikit-image fast-simplification pillow

Whole pipeline (ENV-2; inputs committed under assets/source/landscape/):
  1. capture.py   Studio snippet -> terrain_ops.txt (TerrainBuilder's shapes)
     probe.py     Studio snippets -> probes/*.txt (live terrain hits from the
                  game cameras) and mesa_heightfield.txt (live mesa tops)
  2. shape.py     geometry (this file)
  3. Blender -b --factory-startup -P tools/env/landscape/probe.py -- los|check
                  offline turret line of sight / terrain coverage checks
  4. Blender -b --factory-startup -P tools/env/landscape/bake.py -- <Pieces>
                  UVs, Cycles bakes, colour (texture.py), GLB + manifest
                  (assets/exported/Landscape_<Piece>/, assets/blender/)
  5. publish.py   upload, Studio harvest, assets/roblox/Landscape_*.rbxmx
  6. preview.py   Blender renders from the beauty cameras (optional)
In game: src/server/Landscape.luau.

Checklist after ANY change to the mesa (shape, strata, LOS constants):
  - Blender ... probe.py -- los must print ALL PASS, and in a Studio playtest
    RedMesaDebug losCheck must be ALL PASS: the mesa's runtime precise
    collision sits ~1 stud proud of the render mesh, so the LOS margin is a
    design rule (pieces.LOS_CLEARANCE, TOP_EXTRA_CLEARANCE), not physics.
  - groundCheck digests must stay Road 18060, ScrubLeft/Right 16400,
    WashLeft -34191, WashRight -34501.
After a TerrainBuilder change: re-capture terrain_ops.txt and the probes.
Clearance: the mesh is never inside the live terrain; the minimum clearance
is 0.35 studs (MIN_CLEAR), typical ~1, median camera-ray gap ~6.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage
from skimage import measure

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import fast_simplification  # noqa: E402

import ops as opsmod  # noqa: E402
import strata  # noqa: E402
from noise import fbm2, smoothstep, value3  # noqa: E402
from pieces import CLOSE_RANGE, PIECES, TURRET_PIVOT, LOS_CLEARANCE, Piece, close_view, needed_density  # noqa: E402,F401

OUT = opsmod.ROOT / "assets" / "source" / "landscape" / "build"
CHUNK_TRIS = 15000
TEX = 1024
PACK_EFFICIENCY = 0.58  # share of the 1024^2 atlas the packed islands really cover (measured ~0.6 on the mesa)
FLOOR_DROP = 2.5  # the talus fillet blends into a plane this far under the floor
MIN_CLEAR = 0.35  # the mesh surface never comes closer than this to the terrain
TOP_EXTRA_CLEARANCE = 0.8  # studs, extra LOS clearance on the mesa's top 15 studs of radius
MESA_TOP_CAP = 63.3  # under the emplacement's floor (66.1) and inside its wall (y 58..66.4); live terrain top 62.0


def log(msg: str) -> None:
    print(f"[shape {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def floor_height(wash_ops: list[opsmod.Op], X: np.ndarray, Z: np.ndarray) -> np.ndarray:
    """Top of the live basin floor terrain (the y 0 block top, +2 from
    voxelisation) with the wash troughs carved out."""
    F = np.full_like(X, opsmod.INFLATE["block"], dtype=np.float64)
    for op in wash_ops:
        if op.kind != "ball" or not op.air:
            continue
        cx, cy, cz = op.center
        r = op.size[0] - opsmod.INFLATE["ball"]
        d2 = (X - cx) ** 2 + (Z - cz) ** 2
        inside = d2 < r * r
        if inside.any():
            bottom = cy - np.sqrt(np.maximum(r * r - d2, 0.0))
            F = np.where(inside, np.minimum(F, bottom), F)
    return F


def smin(a: np.ndarray, b: np.ndarray, k: np.ndarray) -> np.ndarray:
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b + (a - b) * h - k * h * (1.0 - h)


def detail(piece: Piece, x, y, z, nx, ny, nz):
    """Outward offset (studs, >= 0) at surface points with envelope normal n."""
    st = piece.style
    steep = smoothstep(0.35, 0.75, 1.0 - np.abs(ny))
    k, f = strata.bed_at(x, y, z)
    lateral = 0.8 + 0.55 * value3(x / 48.0, k * 1.73, z / 48.0, seed=5)
    lateral = np.clip(lateral, 0.15, 1.35)
    ledge = st.amp * strata.ledge_profile(k, f) * lateral
    g = np.abs(fbm2(x / st.gully_scale, z / st.gully_scale, octaves=3, seed=21))
    gully = 1.0 - smoothstep(0.0, 0.16, g)
    gully = gully * (0.45 + 0.55 * smoothstep(-5.0, 45.0, y))
    rough = 0.5 + 0.5 * value3(x / 6.5, y / 2.6, z / 6.5, seed=61)
    # Gullies are smooth water-cut channels: the ledges fade out inside them.
    wall = st.base + ledge * (1.0 - 0.8 * gully) - st.gully * gully + st.rough * rough
    top = st.base_top + 0.35 * np.maximum(0.0, fbm2(x / 9.0, z / 9.0, octaves=2, seed=33))
    return np.maximum(0.12, top + (wall - top) * steep)


def fan_mask(piece: Piece, x, z):
    g = np.abs(fbm2(x / piece.style.gully_scale, z / piece.style.gully_scale, octaves=3, seed=21))
    return 1.0 - smoothstep(0.0, 0.3, g)


def is_scree(op: opsmod.Op) -> bool:
    """TerrainBuilder's scree(): Rock/Sandstone balls sunk 0.45 r into the floor."""
    return op.kind == "ball" and not op.air and abs(op.center[1] + 0.45 * op.size[0]) < 2e-3


def closing(T: np.ndarray, rho: float, h: float) -> np.ndarray:
    """Morphological closing of the solid {T < 0} by radius rho, as a
    signed distance (fills notches and gaps narrower than ~2 rho)."""
    if rho <= 0:
        return T
    A = T < rho
    # The EDT measures to the nearest outside *sample*; the boundary lies
    # about half a voxel closer.
    e = ndimage.distance_transform_edt(A, sampling=h).astype(np.float32) - 0.5 * h
    return np.minimum(np.where(A, rho - e, T), T).astype(np.float32)


def smear(solid: np.ndarray, XX: np.ndarray, ZZ: np.ndarray, w: float, piece: Piece) -> np.ndarray:
    """Stretch a bed's solid plan mask `w` studs along the wall: around the
    piece's ring centre (mesa terraces, buttes) the smear follows the circle,
    elsewhere it runs along `smear_axis` (straight walls, the mesa's ridge)."""
    h = piece.h
    out = solid.copy()
    ring = np.zeros_like(solid)
    if piece.ring_center is not None:
        cx, cz = piece.ring_center
        dx, dz = XX - cx, ZZ - cz
        r = np.sqrt(dx * dx + dz * dz)
        ring = r < piece.ring_radius
        amax = np.minimum(w / np.maximum(r, 1.0), 0.6)
        ring_solid = solid & ring
        for t in np.linspace(-1.0, 1.0, 13):
            a = amax * t
            ca, sa = np.cos(a), np.sin(a)
            sx = cx + dx * ca - dz * sa
            sz = cz + dx * sa + dz * ca
            i = np.clip(np.rint((sx - XX[0, 0]) / h).astype(int), 0, solid.shape[0] - 1)
            j = np.clip(np.rint((sz - ZZ[0, 0]) / h).astype(int), 0, solid.shape[1] - 1)
            out |= ring_solid[i, j] & ring
    if piece.smear_axis is not None:
        straight = solid & ~ring
        out |= ndimage.maximum_filter1d(straight.astype(np.uint8), size=int(2 * w / h) | 1, axis=piece.smear_axis) > 0
    return out


def bedded(E: np.ndarray, xs, ys, zs, piece: Piece) -> np.ndarray:
    """Square the envelope off bed by bed. Within each strata bed a column is
    solid wherever the terrain is solid anywhere in that bed; the bed's plan
    outline is then closed (bulges merge into continuous ledges) and, for
    straight walls, smeared along the wall so bosses become ledge runs. The
    result is a stack of slabs with vertical faces, never smaller than E."""
    h = piece.h
    XX, ZZ = np.meshgrid(xs, zs, indexing="ij")
    yw = ys[None, :, None] + strata.warp(XX, ZZ)[:, None, :]
    K = np.clip(np.searchsorted(strata.BOTTOMS, yw, side="right") - 1, 0, len(strata.BOTTOMS) - 1)
    out = E.copy()
    for k in np.unique(K):
        mask = K == k
        m = np.where(mask, E, np.inf).min(axis=1)
        solid = m < -0.6 * h  # only real terrain spreads (a flat top never rises)
        if not solid.any():
            continue
        if piece.smear > 0:
            # Per-bed smear length, so ledges of different beds end at different places.
            w = piece.smear * (0.5 + float(strata.HARD[k]))
            solid = smear(solid, XX, ZZ, w, piece)
        rho = piece.plan_close
        if rho > 0:
            dil = ndimage.distance_transform_edt(~solid, sampling=h) <= rho
            solid = solid | (ndimage.distance_transform_edt(dil, sampling=h) > rho)
        sd = np.where(solid, -ndimage.distance_transform_edt(solid, sampling=h) + 0.5 * h,
                      ndimage.distance_transform_edt(~solid, sampling=h) - 0.5 * h).astype(np.float32)
        out = np.where(mask, np.minimum(out, sd[:, None, :]), out)
    return out


TALUS_SLOPE = 0.7  # rise per stud of the scree apron's flanks (~35 degrees, the angle of repose)


def apron(scree: list[opsmod.Op], xs, zs, piece: Piece) -> np.ndarray:
    """Height of a talus apron covering every scree ball by >= margin: each
    ball becomes a cone at the talus angle that clears its cap, the cones
    merge into one slope, with small rubble lumps on top."""
    h = piece.h
    XX, ZZ = np.meshgrid(xs, zs, indexing="ij")
    A = np.full(XX.shape, -50.0)
    need = np.full(XX.shape, -50.0)
    dd = np.linspace(0.0, 1.0, 21)
    for op in scree:
        cx, cy, cz = op.center
        r = op.size[0] + opsmod.INFLATE["ball"]
        cap = cy + np.sqrt(np.maximum(r * r - (dd * r) ** 2, 0.0)) + piece.margin
        apex = float(np.max(cap + TALUS_SLOPE * dd * r))
        d = np.sqrt((XX - cx) ** 2 + (ZZ - cz) ** 2)
        A = np.maximum(A, apex - TALUS_SLOPE * d)
        inside = d < r
        need = np.where(inside, np.maximum(need, cy + np.sqrt(np.maximum(r * r - d * d, 0)) + piece.margin), need)
    # Fill the valleys between neighbouring cones: one continuous skirt.
    fp = int(round(14.0 / h)) | 1
    yy, xx = np.mgrid[:fp, :fp] - fp // 2
    A = ndimage.grey_closing(A, footprint=(xx * xx + yy * yy) <= (fp // 2) ** 2)
    A = ndimage.gaussian_filter(A, 2.5 / h)
    A = A + 0.5 * np.abs(fbm2(XX / 4.0, ZZ / 4.0, octaves=2, seed=51))
    return np.maximum(A, need)


HEIGHTFIELD = opsmod.ROOT / "assets" / "source" / "landscape" / "mesa_heightfield.txt"


def live_heightfield(piece: Piece, xs, ys, zs):
    """The mesa's live top surface, measured in Studio (probe.py mesa): the
    smooth terrain fills the terraces' inner corners with wide chamfers the
    analytic shapes don't have. Returned as a (vertical) signed distance
    over raised ground (tops above 6.5, in front of the rear wall), or None."""
    if piece.name != "Mesa" or not HEIGHTFIELD.exists():
        return None
    lines = [ln for ln in HEIGHTFIELD.read_text().splitlines() if ln and not ln.startswith("#")]
    x0, z0, step, nx, nz = (float(v) for v in lines[0].split())
    H = np.array([float(v) for v in lines[1].split(",")]).reshape(int(nz), int(nx)).T  # [x, z]
    gx = np.clip((xs - x0) / step, 0, nx - 1.001)
    gz = np.clip((zs - z0) / step, 0, nz - 1.001)
    ix, iz = gx.astype(int), gz.astype(int)
    fx, fz = (gx - ix)[:, None], (gz - iz)[None, :]
    Hg = (H[ix][:, iz] * (1 - fx) * (1 - fz) + H[ix + 1][:, iz] * fx * (1 - fz)
          + H[ix][:, iz + 1] * (1 - fx) * fz + H[ix + 1][:, iz + 1] * fx * fz)
    raised = (Hg > 6.5) & (zs[None, :] < 140.0)
    Hg = np.where(raised, Hg, -100.0)
    return (ys[None, :, None] - Hg[:, None, :]).astype(np.float32)


def zone_weight(piece: Piece, xs, ys, zs):
    """0 inside the piece's smooth zone (a capsule), 1 outside, blended over 8 studs."""
    if not piece.smooth_zone:
        return None
    a, b, radius = piece.smooth_zone
    a, b = np.array(a), np.array(b)
    ab = b - a
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")
    P = np.stack([X - a[0], Y - a[1], Z - a[2]], axis=-1)
    t = np.clip((P @ ab) / (ab @ ab), 0.0, 1.0)
    d = np.linalg.norm(P - t[..., None] * ab, axis=-1)
    w = smoothstep(radius, radius + 8.0, d)
    # Only below the lens: rock above the camera is outside its view, and
    # there the rim keeps its bedded ledges like the rest of the wall.
    top = 0.5 * (a[1] + b[1]) + 9.0
    w = np.maximum(w, smoothstep(top, top + 4.0, Y))
    return w.astype(np.float32)


def build_field(piece: Piece, ops: list[opsmod.Op]):
    lo, hi, h = np.array(piece.lo), np.array(piece.hi), piece.h
    xs = np.arange(lo[0], hi[0] + h * 0.5, h)
    ys = np.arange(lo[1], hi[1] + h * 0.5, h)
    zs = np.arange(lo[2], hi[2] + h * 0.5, h)
    log(f"{piece.name}: grid {len(xs)}x{len(ys)}x{len(zs)} = {len(xs) * len(ys) * len(zs) / 1e6:.1f}M at {h} studs")
    sel = [op for op in ops if piece.selects(op)]
    washes = [op for op in ops if op.group == "washes"]
    body = [op for op in sel if not is_scree(op)]
    scree = [op for op in sel if is_scree(op)]
    band = 30.0
    T = opsmod.sdf(sel + washes, xs, ys, zs, band=band)
    Tb = opsmod.sdf(body + washes, xs, ys, zs, band=band)
    live = live_heightfield(piece, xs, ys, zs)
    if live is not None:
        T, Tb = np.minimum(T, live), np.minimum(Tb, live)
    log(f"  terrain sdf: {len(body)} body + {len(scree)} scree ops (+{len(washes)} wash carves)")
    # Body: close notches, square off bed by bed, soften the edges a little.
    Ec = closing(Tb, piece.closing, h)
    Eb = bedded(Ec, xs, ys, zs, piece)
    Eb = np.minimum(ndimage.gaussian_filter(Eb, piece.sigma / h), Tb).astype(np.float32)
    zone = zone_weight(piece, xs, ys, zs)
    if zone is not None:
        # Softened ledges (not the raw terrain ball) around the lens.
        smooth = np.minimum(ndimage.gaussian_filter(Eb, 3.5 / h), Tb)
        Eb = (smooth + (Eb - smooth) * zone).astype(np.float32)
        del smooth
    del Ec
    del Tb
    gx, gy, gz = np.gradient(Eb, h)
    gl = np.sqrt(gx * gx + gy * gy + gz * gz) + 1e-6
    maxd = piece.margin + piece.style.base + piece.style.amp + 2.0
    band_mask = (Eb > -3.0 * h) & (Eb < maxd + 3.0 * h)
    ii, jj, kk = np.nonzero(band_mask)
    D = detail(piece, xs[ii], ys[jj], zs[kk], gx[band_mask] / gl[band_mask], gy[band_mask] / gl[band_mask], gz[band_mask] / gl[band_mask])
    if zone is not None:
        D = piece.style.base + (D - piece.style.base) * zone[band_mask]
    S = Eb - piece.margin - piece.style.base
    S[band_mask] = Eb[band_mask] - piece.margin - D
    del gx, gy, gz, gl, D, Eb
    # Scree: one smooth rubble apron (a height field over the scree balls)
    # instead of separate domes.
    if scree:
        A = apron(scree, xs, zs, piece)
        S = smin(S, (ys[None, :, None] - A[:, None, :]).astype(np.float32), np.float32(2.0))
    # Talus fillet into a plane just under the floor.
    XX, ZZ = np.meshgrid(xs, zs, indexing="ij")
    F = floor_height(washes, XX, ZZ)
    k = piece.style.talus + piece.style.talus_fan * fan_mask(piece, XX, ZZ)
    k = k * (0.75 + 0.5 * np.clip(0.5 + 0.5 * fbm2(XX / 23.0, ZZ / 23.0, octaves=2, seed=41), 0, 1))
    plane = ys[None, :, None] - (F[:, None, :] - FLOOR_DROP)
    S = smin(S, plane.astype(np.float32), k[:, None, :].astype(np.float32)).astype(np.float32)
    if piece.keep_clear:
        S = keep_clear(S, xs, ys, zs)
    else:
        # Whatever the sculpting did, stay at least MIN_CLEAR outside the terrain.
        S = np.minimum(S, T - MIN_CLEAR).astype(np.float32)
    return xs, ys, zs, T, S, F


LOS_SECTOR = np.radians(5.0)  # a sight line also caps points this far off its azimuth


def los_cap(r: np.ndarray, azimuth: np.ndarray) -> np.ndarray:
    """Lowest turret sight line (to a lane end at feet height, or along a
    lane at hip height) over points at horizontal distance r from the pivot
    and within LOS_SECTOR of the line's azimuth, minus the clearance."""
    import sys as _sys

    _sys.path.insert(0, str(HERE))
    import probe

    px, py, pz = TURRET_PIVOT
    targets = []
    for pts in probe.lanes().values():
        ex, ez = pts[-1]
        g = -3.3 if abs(abs(ex) - 90) < 1 and abs(ez + 40) < 1 else 2.0
        targets.append((np.hypot(ex - px, ez - pz), g + 0.5, np.arctan2(ex - px, -(ez - pz))))
        for i in range(len(pts) - 1):
            a, b = np.array(pts[i]), np.array(pts[i + 1])
            n = max(1, int(np.linalg.norm(b - a) // 20))
            for k in range(n):
                q = a + (b - a) * k / n
                targets.append((np.hypot(q[0] - px, q[1] - pz), 2.0 + 3.0, np.arctan2(q[0] - px, -(q[1] - pz))))
    cap = np.full(np.shape(r), np.inf)
    for dist, height, az in targets:
        near = np.abs(np.angle(np.exp(1j * (azimuth - az)))) < LOS_SECTOR
        cap = np.where(near, np.minimum(cap, py - (py - height) * np.asarray(r) / dist), cap)
    return cap - LOS_CLEARANCE


def keep_clear(S, xs, ys, zs):
    """Mesa: never rise into the turret's sight lines. The top under the gun
    pit stays solid (the emplacement hides it): a hole there would give the
    QA line-of-sight check's convex collision pieces a concavity to bridge."""
    XX, ZZ = np.meshgrid(xs, zs, indexing="ij")
    r = np.hypot(XX - TURRET_PIVOT[0], ZZ - TURRET_PIVOT[2])
    cap = los_cap(r, np.arctan2(XX - TURRET_PIVOT[0], -(ZZ - TURRET_PIVOT[2])))
    # Near the top the rim is seen edge-on by the sight lines: extra margin.
    cap = cap - np.clip((30.0 - r) / 15.0, 0.0, 1.0) * TOP_EXTRA_CLEARANCE
    cap = np.minimum(cap, MESA_TOP_CAP)
    above = (ys[None, :, None] - cap[:, None, :]) * 0.8
    return np.maximum(S, above.astype(np.float32))


def mesh_from(S, xs, ys, zs, F, h):
    verts, faces, _, _ = measure.marching_cubes(S, 0.0, spacing=(h, h, h), gradient_direction="ascent", allow_degenerate=False)
    # skimage winds 'ascent' faces inward for a negative-inside field; Roblox
    # culls back faces, so turn them to face out (counter-clockwise from outside).
    faces = faces[:, ::-1]
    verts += np.array([xs[0], ys[0], zs[0]])
    # Drop faces fully under the floor (the fillet's plane).
    fx = np.clip(((verts[:, 0] - xs[0]) / h).astype(int), 0, len(xs) - 1)
    fz = np.clip(((verts[:, 2] - zs[0]) / h).astype(int), 0, len(zs) - 1)
    under = verts[:, 1] < F[fx, fz] - FLOOR_DROP + 0.45
    keep = ~under[faces].all(axis=1)
    faces = faces[keep]
    used = np.unique(faces)
    remap = -np.ones(len(verts), dtype=np.int64)
    remap[used] = np.arange(len(used))
    return verts[used].astype(np.float64), remap[faces]


def face_areas(v, f):
    return 0.5 * np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)


def density_at(piece: Piece, c: np.ndarray) -> np.ndarray:
    d = np.minimum(needed_density(c, slack=piece.density_slack, cap=piece.max_density), piece.max_density)
    if piece.close_density > 0:
        d = np.where(close_view(c, CLOSE_RANGE), np.maximum(d, piece.close_density), d)
    return d


def split(piece: Piece, v, f):
    """Split faces into chunks under the triangle and texture-area limits:
    n = enough chunks for both, then a recursive k-d split that divides the
    texels in proportion to the chunk counts on each side, so every chunk's
    atlas ends up about equally full. Returns a chunk id per face and the
    density each chunk's atlas can hold relative to the need."""
    cent = v[f].mean(axis=1)
    area = face_areas(v, f)
    dens = density_at(piece, cent)
    texels = area * dens * dens  # px^2 each face needs
    budget = TEX * TEX * PACK_EFFICIENCY
    n_total = max(int(np.ceil(texels.sum() / budget * 1.04)), piece.min_chunks, 1)
    ids = np.zeros(len(f), dtype=np.int32)
    todo = [(np.arange(len(f)), n_total)]
    done = []
    while todo:
        idx, n = todo.pop()
        if n <= 1:
            done.append(idx)
            continue
        c = cent[idx]
        axis = int(np.argmax(c.max(axis=0) - c.min(axis=0)))
        order = idx[np.argsort(c[:, axis])]
        n1 = n // 2
        w = np.cumsum(texels[order])
        cut = int(np.searchsorted(w, w[-1] * n1 / n))
        cut = min(max(cut, 1), len(order) - 1)
        todo += [(order[:cut], n1), (order[cut:], n - n1)]
    # Parts over the triangle cap (dense, low-texel regions) split by count.
    final = []
    for idx in done:
        k = int(np.ceil(len(idx) / CHUNK_TRIS))
        if k <= 1:
            final.append(idx)
            continue
        c = cent[idx]
        axis = int(np.argmax(c.max(axis=0) - c.min(axis=0)))
        final += list(np.array_split(idx[np.argsort(c[:, axis])], k))
    done = final
    done.sort(key=lambda a: tuple(np.round(cent[a].mean(axis=0) / 50.0)))
    for k, idx in enumerate(done):
        ids[idx] = k
    return ids, [float(np.sqrt(min(1.0, budget / max(texels[i].sum(), 1e-6)))) for i in done]


def build(piece: Piece, ops):
    t0 = time.time()
    xs, ys, zs, T, S, F = build_field(piece, ops)
    hv, hf = mesh_from(S, xs, ys, zs, F, piece.h)
    log(f"  high-poly {len(hf)} tris ({time.time() - t0:.0f}s)")
    # The raw terrain surface, kept to check that the mesh always encloses it.
    tv, tf = mesh_from(T, xs, ys, zs, np.full_like(F, -1e3), piece.h)
    del S, T
    target = min(piece.tris, len(hf))
    lv, lf = fast_simplification.simplify(hv, hf.astype(np.int32), target_count=target, agg=6.0, preserve_border=True)
    log(f"  low-poly {len(lf)} tris")
    chunk, dens = split(piece, lv, lf)
    n = int(chunk.max()) + 1
    log(f"  {n} chunks: tris {[int((chunk == i).sum()) for i in range(n)]}")
    log(f"  atlas fill vs need (1.0 = full density) {[round(d, 2) for d in dens]}")
    OUT.mkdir(parents=True, exist_ok=True)
    # The analytic terrain surface (for probe.py's coverage check), decimated.
    tlv, tlf = fast_simplification.simplify(tv, tf.astype(np.int32), target_count=min(len(tf), 150000), agg=5.0)
    np.savez_compressed(
        OUT / f"{piece.name}.npz",
        high_v=hv.astype(np.float32), high_f=hf.astype(np.int32),
        low_v=lv.astype(np.float32), low_f=lf.astype(np.int32), chunk=chunk,
        face_density=density_at(piece, lv[lf].mean(axis=1)).astype(np.float32),
        terrain_v=tlv.astype(np.float32), terrain_f=tlf.astype(np.int32),
    )
    meta = {"piece": piece.name, "chunks": n, "density": dens, "high_tris": int(len(hf)), "low_tris": int(len(lf)),
            "material": piece.material, "seconds": round(time.time() - t0, 1)}
    (OUT / f"{piece.name}.json").write_text(json.dumps(meta, indent=1))
    log(f"  wrote {OUT.relative_to(opsmod.ROOT)}/{piece.name}.npz ({time.time() - t0:.0f}s)")
    return meta


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("pieces", nargs="*")
    ap.add_argument("--ops", default=str(opsmod.OPS_FILE))
    a = ap.parse_args(argv)
    ops = opsmod.load(Path(a.ops))
    names = a.pieces or list(PIECES)
    for name in names:
        build(PIECES[name], ops)


if __name__ == "__main__":
    main(sys.argv[1:])
