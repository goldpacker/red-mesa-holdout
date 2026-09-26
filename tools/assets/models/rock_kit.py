"""Mesa / canyon rock kit: layered sandstone boulders, slab, hoodoo spire,
rubble and cliff pieces. Build all with `tools/assets/build.sh RockKit`.

Every piece is its own asset (Rock_* / Cliff_*), a single MeshPart `Root`
with the pivot at its base centre (ground contact); pieces sink ~0.4 studs
below the pivot so they sit into terrain. Cliff faces look along +Y in
Blender (Roblox -Z, i.e. the model's front); their backs are rough too.
Colours follow the terrain palette (Sandstone 160,66,40 / Rock 112,56,40).
"""
import math
import random

import bmesh
from mathutils import Vector, noise

from rmh import geo
from rmh.asset import Asset

PALETTE = ["#5e2b1c", "#8a3f26", "#a2502e", "#6e3422", "#b8683f", "#8e4630", "#c98a5a"]


def grid_box(sx, sy, sz, step):
    """Closed box made of per-face grids with ~`step` spacing."""
    nx, ny, nz = (max(2, int(round(s / step))) for s in (sx, sy, sz))
    bm = bmesh.new()
    faces = [
        ((0, 1, 2), 1, (nx, ny)), ((0, 1, 2), -1, (nx, ny)),
        ((0, 2, 1), 1, (nx, nz)), ((0, 2, 1), -1, (nx, nz)),
        ((1, 2, 0), 1, (ny, nz)), ((1, 2, 0), -1, (ny, nz)),
    ]
    half = (sx / 2, sy / 2, sz / 2)
    for (a, b, c), sign, (na, nb) in faces:
        verts = []
        for i in range(na + 1):
            row = []
            for j in range(nb + 1):
                co = [0.0, 0.0, 0.0]
                co[a] = -half[a] + 2 * half[a] * i / na
                co[b] = -half[b] + 2 * half[b] * j / nb
                co[c] = sign * half[c]
                row.append(bm.verts.new(co))
            verts.append(row)
        for i in range(na):
            for j in range(nb):
                q = (verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1])
                bm.faces.new(q if sign > 0 else tuple(reversed(q)))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def sculpt(bm, size, seed, roundness=0.5, ledge=1.2, ledge_amp=0.35, noise_amp=0.12, rill=0.25, taper=0.0, top_flat=0.0, front_only=False, big_amp=0.12):
    """Turn a grid box into weathered layered sandstone."""
    sx, sy, sz = size
    half = Vector((sx / 2, sy / 2, sz / 2))
    off = Vector((seed * 13.1, seed * 7.7, seed * 3.3))
    scale = max(sx, sy, sz)
    for v in bm.verts:
        u = Vector((v.co.x / half.x, v.co.y / half.y, v.co.z / half.z))  # -1..1 box coords
        # Round the box towards a superellipsoid.
        n = Vector((u.x * abs(u.x) ** 2, u.y * abs(u.y) ** 2, u.z * abs(u.z) ** 2))
        n = n.normalized() if n.length > 1e-6 else Vector((0, 0, 1))
        su = u.normalized() * max(abs(u.x), abs(u.y), abs(u.z))
        u = u.lerp(su * 1.0, roundness * (1 - max(0.0, u.z) * top_flat))
        co = Vector((u.x * half.x, u.y * half.y, u.z * half.z))
        # Taper towards the top (buttes, spires).
        t = (u.z + 1) / 2
        co.x *= 1 - taper * t
        co.y *= 1 - taper * t
        side = 1 - min(1.0, abs(n.z) * 1.2)
        horiz = Vector((n.x, n.y, 0))
        horiz = horiz.normalized() if horiz.length > 1e-6 else Vector((0, 0, 0))
        # Irregular sandstone layers: soft beds recess, hard beds form ledges.
        wz = co.z + noise.noise((co + off) * (0.5 / ledge)) * ledge * 0.9
        k = math.floor(wz / ledge)
        frac = wz / ledge - k
        hard = noise.noise(Vector((0.3, 0.7, k * 1.37)) + off)  # -1..1 per layer
        lip = math.tanh(4.0 * (0.5 - abs(frac - 0.5))) if hard > 0 else -0.4
        disp = horiz * side * (hard * 0.8 + lip * 0.45) * ledge_amp
        # Vertical rills / erosion gullies on the walls.
        r = noise.noise(Vector((co.x * 0.35, co.y * 0.35, co.z * 0.06)) + off)
        disp += horiz * side * (-abs(r)) * rill * scale * 0.08
        # Large-scale shape noise breaks the box silhouette.
        big = noise.fractal((co + off * 2.0) * (1.4 / scale), 0.8, 2.0, 3)
        disp += n * big * big_amp * scale
        # General fractal roughness along the normal.
        f = noise.fractal((co + off) * (2.2 / scale), 0.9, 2.0, 5)
        disp += n * f * noise_amp * scale * 0.15
        if front_only and n.y < -0.3:
            disp *= 0.4
        v.co = co + disp
    # Flatten the base and sink it slightly.
    zmin = -half.z
    for v in bm.verts:
        if v.co.z < zmin + 0.25 * sz * 0.1:
            v.co.z = zmin + (v.co.z - zmin) * 0.3
    bmesh.ops.smooth_vert(bm, verts=list(bm.verts), factor=0.25, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    lo = min(v.co.z for v in bm.verts)
    for v in bm.verts:
        v.co.z -= lo + 0.4
    return bm


PIECES = {
    # name: (size, step, seed, sculpt kwargs, tex, strata)
    "Rock_Boulder_A": ((7.0, 6.0, 5.0), 0.5, 1, dict(roundness=0.55, ledge=1.6, ledge_amp=0.25, noise_amp=0.14, big_amp=0.2), 512, 0.35),
    "Rock_Boulder_B": ((11.0, 7.0, 6.0), 0.55, 2, dict(roundness=0.5, ledge=1.8, ledge_amp=0.3, noise_amp=0.12, big_amp=0.2), 512, 0.3),
    "Rock_Boulder_C": ((4.0, 3.6, 3.2), 0.4, 3, dict(roundness=0.6, ledge=1.2, ledge_amp=0.15, noise_amp=0.16, big_amp=0.22), 512, 0.45),
    "Rock_Slab": ((15.0, 10.0, 3.2), 0.7, 4, dict(roundness=0.35, ledge=0.8, ledge_amp=0.35, noise_amp=0.1, top_flat=0.8), 512, 0.6),
    "Rock_Spire": ((6.0, 6.0, 17.0), 0.55, 5, dict(roundness=0.6, ledge=2.2, ledge_amp=0.7, noise_amp=0.08, taper=0.3, rill=0.35, big_amp=0.08), 512, 0.25),
    "Cliff_Wall_A": ((64.0, 16.0, 40.0), 1.5, 6, dict(roundness=0.3, ledge=4.5, ledge_amp=2.6, noise_amp=0.06, rill=0.6, top_flat=0.9, front_only=True, big_amp=0.1), 1024, 0.06),
    "Cliff_Wall_B": ((48.0, 18.0, 34.0), 1.4, 7, dict(roundness=0.35, ledge=3.8, ledge_amp=2.4, noise_amp=0.07, rill=0.7, top_flat=0.9, front_only=True, big_amp=0.12), 1024, 0.07),
    "Cliff_Corner": ((32.0, 32.0, 40.0), 1.4, 8, dict(roundness=0.55, ledge=4.2, ledge_amp=2.4, noise_amp=0.06, rill=0.6, top_flat=0.9, big_amp=0.12), 1024, 0.06),
    "Cliff_Butte": ((40.0, 30.0, 28.0), 1.3, 9, dict(roundness=0.45, ledge=3.4, ledge_amp=2.2, noise_amp=0.07, rill=0.55, taper=0.18, top_flat=1.0, big_amp=0.12), 1024, 0.075),
}


def rubble(a):
    rng = random.Random(10)
    p = a.part("Root", material="Sandstone", smooth_angle=60)
    for i in range(9):
        s = rng.uniform(0.8, 2.2)
        size = (s * rng.uniform(1.0, 1.6), s * rng.uniform(0.9, 1.3), s * rng.uniform(0.6, 1.0))
        bm = sculpt(grid_box(*size, 0.4), size, 20 + i, roundness=0.7, ledge=0.7, ledge_amp=0.12, noise_amp=0.25)
        r = rng.uniform(0, 4.5)
        th = rng.uniform(0, 2 * math.pi)
        p.add(bm, "rock", at=(r * math.cos(th), r * math.sin(th), 0.0), rot=(rng.uniform(-8, 8), rng.uniform(-8, 8), rng.uniform(0, 360)))


def build_piece(name, **kw):
    a = Asset(name, pivot=(0, 0, 0), tex_size=512)
    a.meta["kit"] = "rock"
    if name == "Rock_Rubble":
        a.material("rock", kind="rock", colors=PALETTE, strata=0.7, dust=0.6)
        rubble(a)
    else:
        size, step, seed, skw, tex, strata = PIECES[name]
        a.tex_size["main"] = tex
        a.material("rock", kind="rock", colors=PALETTE, strata=strata, crack_scale=0.35 if size[2] > 20 else 0.8, dust=0.55, dust_height=min(3.0, size[2] * 0.2))
        bm = sculpt(grid_box(*size, step), size, seed, **skw)
        p = a.part("Root", material="Sandstone", smooth_angle=65, collide=True)
        top = max(v.co.z for v in bm.verts)
        p.add(bm, "rock")
        if name == "Rock_Spire":  # hoodoo: harder, wider cap rock
            cap = (8.0, 7.0, 2.8)
            cbm = sculpt(grid_box(*cap, 0.5), cap, 55, roundness=0.5, ledge=1.0, ledge_amp=0.2, noise_amp=0.12, big_amp=0.15)
            p.add(cbm, "rock", at=(0.3, -0.2, top - 1.0), rot=(4, -3, 20))
    return a.finish(views=[("", (1.0, 1.5, 0.55))], **kw)


def build(**kw):
    names = list(PIECES) + ["Rock_Rubble"]
    only = kw.pop("only", None)
    out = []
    for n in names:
        if only and n not in only:
            continue
        out.append(build_piece(n, **kw))
    return out
