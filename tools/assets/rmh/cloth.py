"""Cloth-simulated shapes (Blender cloth, headless) for soft props.

    high, low = cloth.sandbag(seed=3, neck=0.5)          # filled sack
    high, low = cloth.drape(grid, colliders, pinned)      # net over supports

Both return (high, low) bmeshes: `high` is the dense simulated surface
used as the bake source (selected-to-active, see Asset.template) and `low`
the game mesh, built from a sub-lattice of the same simulated vertices so
it lies exactly on the high surface. Units are studs, +Z up. The sims are
deterministic for the same arguments.
"""
import random

import bmesh
import bpy
from mathutils import Vector
from mathutils.kdtree import KDTree

FRAMES = 80


def _link(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _remove(obj):
    me = obj.data if obj.type == "MESH" else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


def _collider(name, bm, flip=False, thickness=0.005, friction=30.0):
    if flip:
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
    obj = _link(name, bm)
    obj.modifiers.new("col", "COLLISION")
    obj.collision.thickness_outer = thickness
    obj.collision.cloth_friction = friction
    return obj


def _plane(size, z):
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=size / 2)
    bmesh.ops.translate(bm, vec=(0, 0, z), verts=bm.verts)
    return bm


def _simulate(obj, settings, frames):
    cl = obj.modifiers.new("cloth", "CLOTH")
    s = cl.settings
    for k, v in settings.items():
        setattr(s, k, v)
    cl.collision_settings.use_self_collision = False
    cl.collision_settings.distance_min = 0.005
    cl.point_cache.frame_start = 1
    cl.point_cache.frame_end = frames
    scene = bpy.context.scene
    old = (scene.frame_start, scene.frame_end, scene.frame_current)
    scene.frame_start, scene.frame_end = 1, frames
    for f in range(1, frames + 1):
        scene.frame_set(f)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    pos = [obj.matrix_world @ v.co for v in ev.data.vertices]
    obj.modifiers.clear()
    scene.frame_start, scene.frame_end = old[0], old[1]
    scene.frame_set(old[2])
    return pos


def grid_box(L, W, H, nx, ny, nz):
    """Closed box made of quad grids; also returns each vertex's lattice key."""
    bm = bmesh.new()
    x0, y0, z0 = -L / 2, -W / 2, -H / 2

    def face(origin, u, v, nu, nv):
        rows = [[Vector(origin) + Vector(u) * (i / nu) + Vector(v) * (j / nv) for j in range(nv + 1)] for i in range(nu + 1)]
        verts = [[bm.verts.new(p) for p in row] for row in rows]
        for i in range(nu):
            for j in range(nv):
                bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]))

    face((x0, y0, z0), (L, 0, 0), (0, W, 0), nx, ny)
    face((x0, y0, -z0), (L, 0, 0), (0, W, 0), nx, ny)
    face((x0, y0, z0), (L, 0, 0), (0, 0, H), nx, nz)
    face((x0, -y0, z0), (L, 0, 0), (0, 0, H), nx, nz)
    face((x0, y0, z0), (0, W, 0), (0, 0, H), ny, nz)
    face((-x0, y0, z0), (0, W, 0), (0, 0, H), ny, nz)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _fit(bms, size):
    """Scale/translate bmeshes together so the first one's bbox has `size`,
    is centred in x/y and sits on z = 0."""
    ref = bms[0]
    lo = Vector([min(v.co[i] for v in ref.verts) for i in range(3)])
    hi = Vector([max(v.co[i] for v in ref.verts) for i in range(3)])
    ext = hi - lo
    sc = Vector([size[i] / max(ext[i], 1e-6) for i in range(3)])
    c = (lo + hi) / 2
    for bm in bms:
        for v in bm.verts:
            p = v.co - Vector((c.x, c.y, lo.z))
            v.co = Vector((p.x * sc.x, p.y * sc.y, p.z * sc.z))


def sandbag(seed=0, size=(2.2, 1.15, 0.6), press=4.0, neck=0.0, load=0.0, tension=15.0,
            jitter=0.02, grid=(40, 24), low=(8, 4), flat=(2.45, 1.6), frames=FRAMES, drop_bottom=True):
    """A sand-filled sack: a flat two-sheet sack inflated with cloth
    pressure and slumped by gravity on the ground (`load` > 0 squeezes it
    with a plate to that height first, like a lower course in a wall;
    `neck` gathers one end like a tied mouth). Scaled to `size`."""
    L, W = flat
    H = 0.08
    nx, ny = grid
    lx, ly = low
    rnd = random.Random(seed)
    high = grid_box(L, W, H, nx, ny, 1)
    high.verts.ensure_lookup_table()
    tree = KDTree(len(high.verts))
    for v in high.verts:
        tree.insert(v.co, v.index)
    tree.balance()

    def shape(co):
        u = co.x / L + 0.5
        p = co.copy()
        if neck > 0 and u > 0.8:
            k = (u - 0.8) / 0.2
            p.y *= 1 - neck * k
            p.z *= 1 - neck * 0.5 * k
        return p

    for v in high.verts:
        p = shape(v.co)
        p.x += rnd.uniform(-1, 1) * jitter
        p.y += rnd.uniform(-1, 1) * jitter
        p.z += rnd.uniform(-1, 1) * jitter * 0.3
        v.co = p
    obj = _link("_sack", high)
    obj.location = (0, 0, H / 2 + 0.3)
    colliders = [_collider("_ground", _plane(8, 0.0))]
    if load > 0:
        top = _collider("_load", _plane(4, 1.4), flip=True)
        top.keyframe_insert("location", frame=1)
        top.keyframe_insert("location", frame=30)
        top.location.z = load - 1.4
        top.keyframe_insert("location", frame=60)
        colliders.append(top)
    pos = _simulate(obj, {
        "quality": 10, "mass": 0.3, "air_damping": 1.0,
        "tension_stiffness": tension, "compression_stiffness": tension,
        "shear_stiffness": 5.0, "bending_stiffness": 0.05,
        "use_pressure": True, "uniform_pressure_force": press, "pressure_factor": 1.0,
    }, frames)
    for c in colliders:
        _remove(c)
    _remove(obj)
    for v in high.verts:
        v.co = pos[v.index]
    lowbm = grid_box(L, W, H, lx, ly, 1)
    lowbm.verts.ensure_lookup_table()
    _mark_seams(lowbm, L, H, L / lx)
    for v in lowbm.verts:
        v.co = pos[tree.find(v.co)[1]].copy()
    _fit([high, lowbm], size)
    if drop_bottom:
        # Faces resting flat on the ground are never seen.
        dead = [f for f in lowbm.faces if f.normal.z < -0.9 and max(v.co.z for v in f.verts) < 0.04 * size[2]]
        bmesh.ops.delete(lowbm, geom=dead, context="FACES")
    bmesh.ops.recalc_face_normals(high, faces=high.faces)
    return high, lowbm


def _mark_seams(bm, L, H, dx):
    """UV seams for a sack: around the top sheet, around the bottom sheet
    and one cut across the side band at the -X end (rest coordinates)."""
    def cls(f):
        zs = [v.co.z for v in f.verts]
        if all(z > H / 2 - 1e-4 for z in zs):
            return 1
        if all(z < -H / 2 + 1e-4 for z in zs):
            return -1
        return 0

    fcls = {f.index: cls(f) for f in bm.faces}
    for e in bm.edges:
        kinds = {fcls[f.index] for f in e.link_faces}
        if len(kinds) > 1 and 1 in kinds:
            e.seam = True
        a, b = e.verts
        if abs(a.co.y) < 1e-4 and abs(b.co.y) < 1e-4:
            end_band = abs(a.co.x + L / 2) < 1e-4 and abs(b.co.x + L / 2) < 1e-4
            end_bottom = a.co.z < -H / 2 + 1e-4 and b.co.z < -H / 2 + 1e-4 and max(a.co.x, b.co.x) < -L / 2 + dx + 1e-4
            if end_band or end_bottom:
                e.seam = True  # cut across the band and the bottom rim at the -X end
    bm.faces.ensure_lookup_table()


def grid_sheet(w, h, nx, ny):
    """Flat sheet in the XY plane centred on the origin (row-major verts)."""
    bm = bmesh.new()
    verts = [[bm.verts.new((-w / 2 + w * i / nx, -h / 2 + h * j / ny, 0.0)) for j in range(ny + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(ny):
            bm.faces.new((verts[i][j], verts[i + 1][j], verts[i + 1][j + 1], verts[i][j + 1]))
    return bm


def drape(sheet, nx, ny, colliders, pinned, step=3, frames=90, settings=None):
    """Drop a `grid_sheet` (already placed in asset space) onto collider
    bmeshes; vertices where `pinned(co)` is true stay fixed (tie-downs).
    Returns (high, low) where low keeps every `step`-th row/column."""
    obj = _link("_sheet", sheet)
    group = obj.vertex_groups.new(name="pin")
    pins = [v.index for v in obj.data.vertices if pinned(v.co)]
    if pins:
        group.add(pins, 1.0, "REPLACE")
    cols = [_collider(f"_col{i}", bm, thickness=0.03, friction=40.0) for i, bm in enumerate(colliders)]
    cfg = {
        "quality": 8, "mass": 0.15, "air_damping": 2.0,
        "tension_stiffness": 12.0, "compression_stiffness": 12.0,
        "shear_stiffness": 4.0, "bending_stiffness": 0.02,
        "vertex_group_mass": "pin",
    }
    cfg.update(settings or {})
    pos = _simulate(obj, cfg, frames)
    for c in cols:
        _remove(c)
    _remove(obj)
    high = sheet.copy()
    high.verts.ensure_lookup_table()
    for v in high.verts:
        v.co = pos[v.index]
    lo = bmesh.new()
    grid = {}
    rows = sorted(set(range(0, nx + 1, step)) | {nx})
    cols_ = sorted(set(range(0, ny + 1, step)) | {ny})
    for i in rows:
        for j in cols_:
            grid[(i, j)] = lo.verts.new(pos[i * (ny + 1) + j])
    ii = sorted({i for i, _ in grid})
    jj = sorted({j for _, j in grid})
    for a in range(len(ii) - 1):
        for b in range(len(jj) - 1):
            lo.faces.new((grid[(ii[a], jj[b])], grid[(ii[a + 1], jj[b])], grid[(ii[a + 1], jj[b + 1])], grid[(ii[a], jj[b + 1])]))
    return high, lo

