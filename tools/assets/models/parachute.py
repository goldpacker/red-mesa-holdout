"""Parachute: the enemy's personnel static-line canopy (original design,
round military canopy class), in three states.

Asset origin (the model pivot) = the **riser confluence at the harness**:
the midpoint between the trooper's two shoulder connectors. Every state
shares it, so swapping states never moves the load. Model forward is -Z,
up +Y (Blender +Y / +Z here).

Sub-models (WorldPivot = the origin), one visible at a time:
- `Open`: `CanopyOpen` (inflated canopy, 20 gores bulging between radial
  tapes, scalloped skirt, apex vent) + `LinesOpen` (20 suspension lines
  into four risers, risers down to the shoulder connectors). Visible in
  the file.
- `Deploying`: `CanopyDeploying` (partly open "squid": narrow streaming
  crown, mouth starting to inflate) + `LinesDeploying` (lines, risers,
  deployment bag at the apex, static line up toward the aircraft).
  Transparency 1 in the file.
- `Collapsed`: `CanopyCollapsed` (cloth-simulated: blown over and
  deflated on the ground, lying toward +Z) + `LinesCollapsed` (slack
  lines on the ground back to the pivot). The pivot is **on the ground**
  (the riser ends where the trooper landed). Transparency 1 in the file.
- `Root`: invisible marker at the pivot (PrimaryPart) with attachments
  `LoadAttach` (where the trooper hangs: his shoulder midpoint, i.e. the
  Infantry rig's shoulder joints at y = 5.3 above his feet) and
  `NightLight` (on the left front riser, looking forward) + `NightLamp`
  (tiny Neon chemlight there, Transparency 1 in the file).
- `CanopyOpen` carries attachment `Apex` (top of the canopy: sway pivot).

All parts CanQuery/CanCollide false; the fabric maps into the shared
`TrimAirdrop` sheet (512², no metalness).

`models/parachute_cargo.py` builds the cargo canopy with the same code.
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector

from rmh import cloth, geo, trim
from rmh.asset import Asset

TAU = math.pi * 2


class Spec:
    """Canopy and rigging dimensions (studs, Blender axes, pivot at 0)."""

    def __init__(self, gores, radius, depth, line_len, riser_len, periods, harness, rings=7,
                 vent_deg=6.0, hem_deg=100.0, bulge=0.035, scallop=0.045, thickness=0.05,
                 line_r=0.035, riser_w=0.22, collapse_offset=10.0, seed=1):
        self.gores = gores
        self.radius = radius
        self.depth = depth  # dome half-height of the ellipse profile
        self.line_len = line_len
        self.riser_len = riser_len
        self.periods = periods  # canopy strip periods round the canopy (gores / 10)
        self.harness = harness  # True: four risers to two shoulder connectors
        self.rings = rings
        self.vent = math.radians(vent_deg)
        self.hem = math.radians(hem_deg)
        self.bulge = bulge
        self.scallop = scallop
        self.thickness = thickness
        self.line_r = line_r
        self.riser_w = riser_w
        self.collapse_offset = collapse_offset
        self.seed = seed

    # profile ------------------------------------------------------------------
    def profile(self, rings):
        """[(r, z, t)] from the vent (t = 0) to the hem (t = 1), z relative
        to the hem plane."""
        pts = []
        for j in range(rings + 1):
            phi = self.vent + (self.hem - self.vent) * j / rings
            pts.append((self.radius * math.sin(phi), self.depth * math.cos(phi)))
        z_hem = pts[-1][1]
        arc = [0.0]
        for a, b in zip(pts, pts[1:]):
            arc.append(arc[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        return [(r, z - z_hem, s / arc[-1]) for (r, z), s in zip(pts, arc)]

    def hem_height(self):
        """Height of the hem plane above the pivot."""
        hem_r = self.radius * math.sin(self.hem)
        drop = math.sqrt(max(1.0, self.line_len ** 2 - (hem_r - 0.5) ** 2))
        return self.riser_len + drop

    def apex_height(self):
        return self.hem_height() + self.profile(self.rings)[0][1]


def open_lattice(spec, sub=1):
    """Inflated canopy positions in canopy space (hem plane at z = 0):
    grid[j][i], j = vent..hem rows, i round the canopy (2 * sub columns
    per gore), plus (theta, t) per vertex."""
    rings = spec.rings * sub
    cols = spec.gores * 2 * sub
    prof = spec.profile(rings)
    grid, params = [], []
    for j, (r, z, t) in enumerate(prof):
        row, prow = [], []
        for i in range(cols):
            th = TAU * i / cols
            g = abs(math.sin(th * spec.gores / 2))  # 0 on the radial seams, 1 mid-gore
            rr = r * (1.0 + spec.bulge * g * math.sin(math.pi * min(1.0, t * 1.15)) ** 0.5)
            zz = z
            if j == rings:  # scalloped skirt: mid-gore lifts between the line tabs
                zz += spec.scallop * spec.radius * g
                rr -= 0.3 * spec.scallop * spec.radius * g
            row.append(Vector((rr * math.cos(th), rr * math.sin(th), zz)))
            prow.append((th, t))
        grid.append(row)
        params.append(prow)
    return grid, params


def lattice_bm(grid, params, T, spec):
    """bmesh of a lattice (closed round the canopy), UV-mapped into the
    `canopy` strip: U = gore angle (spec.periods periods round), V = arc
    from the vent."""
    bm = bmesh.new()
    bm.loops.layers.uv.new("UVMap")  # layers before geometry (see trim.Trim._faces)
    bm.faces.layers.int.new(trim.MAPPED)
    verts = [[bm.verts.new(p) for p in row] for row in grid]
    cols = len(grid[0])
    for j in range(len(grid) - 1):
        for i in range(cols):
            k = (i + 1) % cols
            bm.faces.new((verts[j][i], verts[j + 1][i], verts[j + 1][k], verts[j][k]))
    bm.normal_update()
    # Outward: a mid-canopy face's normal must point away from the axis.
    bm.faces.ensure_lookup_table()
    f = bm.faces[len(bm.faces) // 2]
    c = f.calc_center_median()
    if f.normal.dot(Vector((c.x, c.y, 0.0))) < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
    # T.custom maps by coordinate: key (u, t) on the inflated positions.
    by_co = {}
    for row, prow in zip(verts, params):
        for v, (th, t) in zip(row, prow):
            by_co[tuple(round(c, 5) for c in v.co)] = (th / TAU * spec.periods, t)
    T.custom(bm, "canopy", lambda co: by_co[tuple(round(c, 5) for c in co)], wrap=spec.periods)
    return bm, verts


def solidify(bm, thickness):
    """Double-sided fabric (Roblox culls back faces): inner shell + rims."""
    bmesh.ops.solidify(bm, geom=list(bm.faces), thickness=thickness)
    bm.normal_update()
    return bm


# --- canopy states --------------------------------------------------------------------

def canopy_open(spec, T):
    grid, params = open_lattice(spec)
    bm, verts = lattice_bm(grid, params, T, spec)
    geo.transform(bm, at=(0, 0, spec.hem_height()))
    hem = [v.co.copy() for v in verts[-1][::2]]  # seam points (line tabs)
    return solidify(bm, spec.thickness), hem


def deploy_shape(spec, t, th, rnd_phase):
    """Partly open canopy: narrow streaming crown, mouth inflating."""
    r = spec.radius * (0.04 + 0.34 * math.sin(math.pi / 2 * t) ** 2 * (1 - 0.35 * t ** 8))
    fold = 1.0 + 0.3 * (1.0 - t) * math.sin(th * spec.gores / 2) ** 2  # star-folded crown
    r *= fold
    length = spec.radius * 1.25
    z = (1.0 - t) * length
    sway = 0.09 * spec.radius * math.sin(TAU * (1.0 - t) * 0.9 + rnd_phase) * (1.0 - t)
    flutter = 0.03 * spec.radius * math.sin(th * 3 + t * 9 + rnd_phase)
    return Vector(((r + flutter) * math.cos(th) + sway, (r + flutter) * math.sin(th) + sway * 0.4, z))


def canopy_deploying(spec, T):
    grid, params = open_lattice(spec)
    bm, verts = lattice_bm(grid, params, T, spec)
    phase = 1.3
    for row, prow in zip(verts, params):
        for v, (th, t) in zip(row, prow):
            v.co = deploy_shape(spec, t, th, phase)
    # Lines stay the same length; the mouth is narrow, so the hem rises.
    hem_r = spec.radius * 0.26
    drop = math.sqrt(max(1.0, spec.line_len ** 2 - (hem_r - 0.5) ** 2))
    base = spec.riser_len + drop
    geo.transform(bm, at=(0, 0, base))
    hem = [v.co.copy() for v in verts[-1][::2]]
    apex = Vector((0, 0, base + spec.radius * 1.25))
    return solidify(bm, spec.thickness), hem, apex


def canopy_collapsed(spec, T, frames=110):
    """Deflated on the ground, streaming downwind toward -Y (Roblox +Z,
    behind the pivot): every gore is laid out along the wind at its full
    length (apex farthest), the cross-section narrowed to a flat tongue,
    then dropped with Blender cloth (self-collision, buckling) onto a
    ground plane so it folds naturally; the game lattice samples the
    simulated one."""
    sub = 2
    grid_hi, params_hi = open_lattice(spec, sub=sub)
    rows, cols = len(grid_hi), len(grid_hi[0])
    prof = spec.profile(spec.rings * 8)
    gore_len = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(prof, prof[1:]))
    rng = random.Random(spec.seed)
    lift = spec.radius * 0.24 + 0.3
    sheet = bmesh.new()
    sv = []
    for j in range(rows):
        srow = []
        for i in range(cols):
            g = grid_hi[j][i]
            th, t = params_hi[j][i]
            r = math.hypot(g.x, g.y)
            drift = 0.14 * gore_len * (1.0 - t) ** 2  # the crown blew off to one side
            p = Vector((r * math.cos(th) * 0.62 + drift, -spec.collapse_offset - (1.0 - t) * gore_len * 0.97,
                        lift + r * math.sin(th) * 0.22))
            p += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * 0.015 * spec.radius
            srow.append(sheet.verts.new(p))
        sv.append(srow)
    for j in range(rows - 1):
        for i in range(cols):
            k = (i + 1) % cols
            sheet.faces.new((sv[j][i], sv[j + 1][i], sv[j + 1][k], sv[j][k]))
    obj = cloth._link("_canopy_sim", sheet)
    ground = cloth._collider("_ground", cloth._plane(spec.radius * 12, 0.0), thickness=0.05, friction=60.0)
    cfg = {"quality": 10, "mass": 0.08, "air_damping": 1.0, "tension_stiffness": 15.0, "compression_stiffness": 0.5,
           "shear_stiffness": 2.0, "bending_stiffness": 0.005}
    pos = cloth._simulate(obj, cfg, frames, self_collision=0.02 * spec.radius ** 0.5)
    cloth._remove(ground)
    cloth._remove(obj)
    sheet.free()
    # Game lattice = every `sub`-th simulated vertex (same topology as Open).
    grid, params = open_lattice(spec)
    bm, verts = lattice_bm(grid, params, T, spec)
    for j, row in enumerate(verts):
        for i, v in enumerate(row):
            p = pos[(j * sub) * cols + i * sub]
            v.co = Vector((p.x, p.y, max(p.z, 0.04)))
    hem = [v.co.copy() for v in verts[-1][::2]]
    return solidify(bm, spec.thickness), hem


# --- lines and risers -----------------------------------------------------------------

def line(T, a, b, r, mids=()):
    pts = [Vector(a)] + [Vector(m) for m in mids] + [Vector(b)]
    bm = geo.pipe_path(pts, r, verts=3)
    axis = (pts[-1] - pts[0]).normalized()
    return T.cylindrical(bm, "cord", axis=tuple(axis), center=tuple(pts[0]), along=True)


def strap(T, a, b, width, thick=0.05):
    """Webbing strap from a to b (flat side faces +X before orienting)."""
    a, b = Vector(a), Vector(b)
    d = b - a
    bm = geo.box(width, d.length, thick, bevel=0.0)
    T.planar(bm, "webbing", u_axis=(0, 1, 0), v_axis=(1, 0, 0))
    return bm, tuple((a + b) / 2), frame_rot(d)


def frame_rot(d, side=(1, 0, 0)):
    """Euler (deg, XYZ) turning local +Y onto `d`, local +X as close to
    `side` as possible (strap width stays horizontal)."""
    y = Vector(d).normalized()
    x = Vector(side) - y * y.dot(Vector(side))
    if x.length < 1e-4:
        x = Vector((0, 1, 0)) - y * y.dot(Vector((0, 1, 0)))
    x.normalize()
    z = x.cross(y)
    m = Matrix((x, y, z)).transposed()
    return tuple(math.degrees(v) for v in m.to_euler("XYZ"))


def riser_tops(spec):
    """Personnel: four riser tops (front/rear x left/right); cargo: one
    confluence."""
    z = spec.riser_len
    if spec.harness:
        return {(sx, sy): Vector((sx * 0.42, sy * 0.3, z)) for sx in (-1, 1) for sy in (-1, 1)}
    return {(0, 0): Vector((0, 0, z))}


def quadrant(spec, p):
    if not spec.harness:
        return (0, 0)
    return (1 if p.x >= 0 else -1, 1 if p.y >= 0 else -1)


def rigging(part, spec, T, hem, tops, collapsed=False):
    """Suspension lines from the hem tabs to the riser tops, and the
    risers down to the connectors at the pivot."""
    rng = random.Random(spec.seed + 7)
    for p in hem:
        top = tops[quadrant(spec, p)]
        if collapsed:
            # Slack lines lying on the ground from the skirt back to the pivot.
            a = Vector((p.x, p.y, 0.05))
            b = Vector((top.x * 0.4, top.y * 0.4 - 0.6, 0.05))
            m1 = a.lerp(b, 0.35) + Vector((rng.uniform(-1, 1) * 1.2, 0, 0.02))
            m2 = a.lerp(b, 0.7) + Vector((rng.uniform(-1, 1) * 0.8, 0, 0.02))
            part.add(line(T, a, b, spec.line_r, (m1, m2)), "trim")
        else:
            part.add(line(T, p, top, spec.line_r), "trim")
    if collapsed:
        for (sx, sy) in tops:
            a = Vector((sx * 0.25, 0.0, 0.05))
            b = Vector((sx * 0.5, -0.9 - 0.2 * sy, 0.05))
            bm, at, rot = strap(T, a, b, spec.riser_w, 0.04)
            part.add(bm, "trim", at=at, rot=rot)
        return
    if spec.harness:
        for (sx, sy), top in tops.items():
            conn = Vector((sx * 0.5, 0.0, 0.0))
            bm, at, rot = strap(T, conn, top, spec.riser_w)
            part.add(bm, "trim", at=at, rot=rot)
            # Connector link at the shoulder.
        for sx in (-1, 1):
            link = geo.torus(0.12, 0.035, verts=8, ring_verts=4)
            T.fill(link, "cord")
            part.add(link, "trim", at=(sx * 0.5, 0.0, 0.02), rot=(0, 90, 0))
    else:
        top = tops[(0, 0)]
        bm, at, rot = strap(T, Vector((0, 0, 0.3)), top, spec.riser_w * 1.6, 0.1)
        part.add(bm, "trim", at=at, rot=rot)
        for z in (0.0, top.z):  # connector link and the confluence ring
            link = geo.torus(0.35 if z else 0.28, 0.08, verts=10, ring_verts=4)
            T.fill(link, "cord")
            part.add(link, "trim", at=(0, 0, z), rot=(0, 90, 0))


def deploy_extras(part, spec, T, apex):
    """Deployment bag above the apex and the static line up toward the
    aircraft (forward and up)."""
    bag = geo.box(spec.radius * 0.1, spec.radius * 0.06, spec.radius * 0.075, bevel=0.0)
    T.planar(bag, "webbing", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
    part.add(bag, "trim", at=(apex.x, apex.y, apex.z + spec.radius * 0.1))
    bag_top = Vector((apex.x, apex.y, apex.z + spec.radius * 0.14))
    part.add(line(T, apex, apex + Vector((0, 0, spec.radius * 0.07)), spec.line_r * 1.4), "trim")
    part.add(line(T, bag_top, bag_top + Vector((0, spec.radius * 0.35, spec.radius * 0.6)), spec.line_r * 1.6), "trim")


# --- asset ------------------------------------------------------------------------------

PERSONNEL = Spec(gores=20, radius=12.0, depth=8.6, line_len=24.0, riser_len=2.6, periods=2, harness=True,
                 rings=7, thickness=0.05, line_r=0.035, riser_w=0.22, collapse_offset=10.0, seed=3)


def build_chute(a, T, spec, night_at, lamp=True):
    """All three states + the Root marker and attachments."""
    for path in ("Open", "Deploying", "Collapsed"):
        a.pivot(path, (0, 0, 0))
    flags = dict(tex="airdrop", query=False, collide=False, material="Fabric")
    tops = riser_tops(spec)

    bm, hem = canopy_open(spec, T)
    a.part("CanopyOpen", path="Open", smooth_angle=70, **flags).add(bm, "trim")
    rigging(a.part("LinesOpen", path="Open", shadow=False, smooth_angle=30, **flags), spec, T, hem, tops)
    a.attach("Apex", "CanopyOpen", (0, 0, spec.apex_height()), axis=(0, 1, 0))

    bm, hem, apex = canopy_deploying(spec, T)
    a.part("CanopyDeploying", path="Deploying", smooth_angle=70, transparency=1, **flags).add(bm, "trim")
    lines = a.part("LinesDeploying", path="Deploying", shadow=False, smooth_angle=30, transparency=1, **flags)
    rigging(lines, spec, T, hem, tops)
    deploy_extras(lines, spec, T, apex)

    bm, hem = canopy_collapsed(spec, T)
    a.part("CanopyCollapsed", path="Collapsed", smooth_angle=60, transparency=1, **flags).add(bm, "trim")
    rigging(a.part("LinesCollapsed", path="Collapsed", shadow=False, smooth_angle=30, transparency=1, **flags),
            spec, T, hem, tops, collapsed=True)

    a.marker("Root", "", (0, 0, 0), size=(0.4, 0.4, 0.4))
    a.attach("LoadAttach", "Root", (0, 0, 0), axis=(0, 1, 0))
    a.attach("NightLight", "Root", night_at, axis=(0, 1, 0))
    if lamp:
        chem = geo.cylinder(0.07, 0.45, verts=6, bevel=0.0)
        a.part("NightLamp", neon=(1.0, 0.36, 0.24), transparency=1, query=False, collide=False, shadow=False).add(
            chem, "lamp", at=night_at)


def views(spec, name):
    """Previews: open (side, below), deploying, collapsed (three states)."""
    top = spec.apex_height()
    mid = top * 0.55
    open_parts = ["CanopyOpen", "LinesOpen"]
    dep = ["CanopyDeploying", "LinesDeploying"]
    col = ["CanopyCollapsed", "LinesCollapsed"]
    d = top * 1.55
    dep_top = spec.riser_len + spec.line_len + spec.radius * 2.0
    res = (1024, 1280)
    return [
        {"label": "", "pos": (d * 0.8, d * 0.7, mid + d * 0.1), "look": (0, 0, mid), "fov": 40, "res": res, "hide": dep + col},
        {"label": "_below", "pos": (spec.radius * 1.1, spec.radius * 0.8, 1.0), "look": (0, 0, top * 0.8), "fov": 55, "res": res, "hide": dep + col},
        {"label": "_deploying", "pos": (dep_top * 1.25, dep_top * 1.05, dep_top * 0.55), "look": (0, 0, dep_top * 0.5), "fov": 40,
         "res": res, "hide": open_parts + col, "show": dep},
        {"label": "_collapsed", "pos": (spec.radius * 1.9, spec.radius * 0.6, spec.radius * 1.4),
         "look": (0, -spec.collapse_offset - spec.radius * 0.7, 0), "fov": 45, "res": (1280, 900),
         "hide": open_parts + dep, "show": col},
        {"label": "_cam_turret", "pos": (top * 1.5, top * 8.5, 1.0), "look": (0, 0, mid), "fov": 12, "res": (1280, 900), "hide": dep + col},
    ]


def build(**kw):
    a = Asset("Parachute", pivot=(0, 0, 0), tex_size=512)
    a.preview_hide_transparent = True
    T = trim.use(a, "airdrop", "TrimAirdrop")
    a.material("lamp", kind="flat", color="#ff5c3d")
    # Night light on the left front riser, a hand's width above the shoulder.
    build_chute(a, T, PERSONNEL, night_at=(-0.46, 0.3, 1.3))
    return a.finish(views=views(PERSONNEL, "Parachute"), **kw)
