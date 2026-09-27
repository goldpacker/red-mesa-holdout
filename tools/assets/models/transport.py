"""Transport: the enemy's four-engine turboprop cargo aircraft (original
design, tactical-airlifter class: high wing, rear loading ramp). ~105
studs long, 142 span, 40 tall (1 stud ~ 0.28 m). Enemy gunmetal with red
markings (fin tip, wing tips, prop tips) and the emblem on the fin, under
the wings and on the forward fuselage.

Asset origin (model pivot) = **centre of mass** (the wing root quarter
chord, 1 stud above the fuselage axis). Nose along -Z (Roblox), up +Y.

Parts (all CanQuery/CanCollide false: a client-side visual):
- `Root` (PrimaryPart): fuselage, drooped radome, cockpit, main-gear
  sponsons, wing-box fairing, dorsal fin fillet, ventral strakes, the
  cargo hold interior (seen through the open ramp), refuelling probe,
  sensor ball, antennas; emblem on the forward fuselage.
- `Wings`: high wing (slight outboard anhedral, red tips), four nacelles
  with chin intakes and exhaust stacks; emblem under each wing.
- `Tail`: swept fin (red tip, emblem both sides) and tailplanes.
- `Windows`: cockpit glazing and cabin windows (Glass, no textures).
- `Ramp` (Model, WorldPivot on the hinge at the aft end of the cargo
  floor): part `RampDoor`, attachment `ReleasePoint` at the ramp lip on
  its top surface, looking aft. Open for the drop = rotate the model about
  its pivot's X axis by `meta.ramp_open_deg` (+21.8 deg: level with the
  floor).
- `CargoDoor` (Model, WorldPivot on the door's aft hinge): part
  `CargoDoorPanel`. Open = rotate about the pivot's X axis by
  `meta.cargo_door_open_deg` (+60 deg: tucked up into the tail).
- `Prop1`..`Prop4` (Models, WorldPivot on the hub; 1 = left outboard ..
  4 = right outboard, as seen from the cockpit): parts `Blades<k>`
  (spinner + 5 scimitar blades, red tips; its bounding-box centre is the
  hub) and `Disc<k>` (prop-blur disc, Transparency 1 in the file; fade it
  in while the blades spin, e.g. Transparency 0.6-0.75). Spin about the
  hub's Z axis (the thrust line).
- `NavLampL` (red), `NavLampR` (green), `NavLampTail` (white),
  `BeaconLamp` (red, belly), `BeaconLampTop` (red): Neon lamps.
  `FormationLights`: Neon strips (fuselage sides, fin, wing tops),
  Transparency 1 in the file; show them at dusk/night.
- `LOD` (Model): part `LODHull` (whole airframe in ~1.5k tris,
  Transparency 1 in the file). Far LOD = show `LODHull` and the `Disc`s,
  hide every other part.
Attachments on `Root` unless noted: `NavLightL`, `NavLightR`,
`NavLightTail`, `Beacon` (belly), `BeaconTop`, `Exhaust1`..`Exhaust4`
(on `Wings`, at each exhaust outlet, looking aft), `CargoFloor` (cargo
floor centre ahead of the ramp hinge, looking aft).

Textures: the shared `TrimEnemy` sheet only (plain, red, bolted, grille,
mesh, canvas, cable) + Glass: **no texture of its own**.
"""
import math

import bmesh
from mathutils import Matrix, Vector

from rmh import aero, geo, trim
from rmh.asset import Asset

TAU = math.pi * 2

# Fuselage stations: (y, width, top z, bottom z, squareness).
FUSE = [
    (45.0, 0.8, -2.9, -3.7, 2.0),
    (44.3, 4.4, -1.2, -5.0, 2.2),
    (42.8, 7.8, 0.6, -6.3, 2.3),
    (41.0, 10.2, 1.6, -7.3, 2.4),
    (40.0, 11.4, 2.3, -7.8, 2.5),
    (37.6, 13.0, 5.0, -8.5, 2.6),
    (35.0, 14.2, 6.25, -8.8, 2.65),
    (31.0, 15.0, 6.85, -8.95, 2.7),
    (25.0, 15.2, 7.0, -9.0, 2.8),
    (12.0, 15.2, 7.0, -9.0, 2.8),
    (-6.0, 15.2, 7.0, -9.0, 2.8),
    (-18.0, 15.2, 7.0, -9.0, 2.8),
    (-26.0, 15.2, 7.0, -9.0, 2.8),
    (-31.5, 14.9, 7.0, -7.1, 2.75),
    (-37.5, 13.9, 7.0, -4.4, 2.7),
    (-42.0, 12.4, 7.0, -2.2, 2.6),
    (-47.0, 10.0, 6.9, -0.1, 2.5),
    (-51.5, 7.4, 6.7, 1.9, 2.4),
    (-56.0, 4.7, 6.5, 3.6, 2.3),
    (-59.5, 2.4, 6.3, 4.8, 2.2),
    (-61.2, 0.5, 5.9, 5.4, 2.0),
]
FUSE_N = 24
RAMP_Y = (-26.0, -37.5)
DOOR_Y = (-37.5, -47.0)
FLOOR_Z = -8.2
HINGE = Vector((0.0, -26.0, -8.8))
DOOR_HINGE = Vector((0.0, -47.0, -0.1))
RAMP_OPEN_DEG = math.degrees(math.atan2(-4.4 - -9.0, 37.5 - 26.0))
DOOR_OPEN_DEG = 60.0

WING_Z = 7.8
# Wing stations: (x, chord, thickness, leading edge y).
WING = [(0.0, 17.0, 2.7, 4.3), (19.0, 15.3, 2.3, 3.55), (37.0, 13.6, 1.9, 2.84), (68.0, 8.6, 1.05, 1.62), (71.0, 8.2, 1.0, 1.5)]
ANHEDRAL_FROM, ANHEDRAL = 37.0, 3.0
ENGINES = [(-37.0, 1), (-19.0, 2), (19.0, 3), (37.0, 4)]  # (x, number)
PROP_R = 7.2
BLADES = 5


def wing_z(x):
    return WING_Z - max(0.0, abs(x) - ANHEDRAL_FROM) * math.tan(math.radians(ANHEDRAL))


def wing_le(x):
    x = abs(x)
    for (x0, _, _, l0), (x1, _, _, l1) in zip(WING, WING[1:]):
        if x0 <= x <= x1:
            return l0 + (l1 - l0) * (x - x0) / (x1 - x0)
    return WING[-1][3]


def wing_chord(x):
    x = abs(x)
    for (x0, c0, _, _), (x1, c1, _, _) in zip(WING, WING[1:]):
        if x0 <= x <= x1:
            return c0 + (c1 - c0) * (x - x0) / (x1 - x0)
    return WING[-1][1]


def hub(x):
    """Propeller hub position for an engine at span x."""
    return Vector((x, wing_le(x) + 10.5, wing_z(x) - 1.3))


# --- helpers --------------------------------------------------------------------------

def sections(stations):
    """FUSE-style stations -> geo.loft sections (y, w, h, zc, e)."""
    return [(y, w, top - bot, (top + bot) / 2, e) for y, w, top, bot, e in stations]


def section_at(y, stations=FUSE):
    """(w, top, bot, e) interpolated at y."""
    pts = sorted(stations, key=lambda s: s[0])
    for a, b in zip(pts, pts[1:]):
        if a[0] <= y <= b[0]:
            t = (y - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * t for i in range(1, 5))
    s = pts[0] if y < pts[0][0] else pts[-1]
    return s[1:]


def surf(y, ang, out=0.0):
    """Point on the fuselage surface at station y, section angle `ang`
    (degrees, 0 = +X, 90 = top), pushed `out` studs along the normal."""
    w, top, bot, e = section_at(y)
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    x = w / 2 * math.copysign(abs(c) ** (2 / e), c)
    z = (top + bot) / 2 + (top - bot) / 2 * math.copysign(abs(s) ** (2 / e), s)
    n = Vector((x / (w / 2) ** 2, 0.0, (z - (top + bot) / 2) / ((top - bot) / 2) ** 2)).normalized()
    return Vector((x, y, z)) + n * out


def split(bm, pred):
    """(faces where pred, the rest) of a primitive; consumes bm."""
    a, b = bm.copy(), bm
    a.normal_update()
    b.normal_update()
    bmesh.ops.delete(a, geom=[f for f in a.faces if not pred(f)], context="FACES")
    bmesh.ops.delete(b, geom=[f for f in b.faces if pred(f)], context="FACES")
    return a, b


def box_map(T, bm, strip, faces=None, along=1):
    """Box-projection into a strip: each face by its dominant normal axis
    (U runs along `along`, the long axis of the piece)."""
    keep = faces or (lambda f: True)
    for axis in range(3):
        u = [0, 0, 0]
        u[along if along != axis else (along + 1) % 3] = 1
        v = [0, 0, 0]
        v[next(i for i in range(3) if i != axis and u[i] == 0)] = 1
        pick = lambda f, axis=axis: keep(f) and max(range(3), key=lambda i: abs(f.normal[i])) == axis  # noqa: E731
        T.planar(bm, strip, u_axis=tuple(u), v_axis=tuple(v), faces=pick)
    return bm


def orient(bm, at, normal, up):
    """Turn a piece built in its XY plane (normal +Z, up +Y) onto a surface."""
    n = Vector(normal).normalized()
    u = Vector(up)
    u = (u - n * u.dot(n)).normalized()
    r = u.cross(n)
    m = Matrix((r, u, n)).transposed().to_4x4()
    m.translation = Vector(at)
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    return bm


def emblem(size):
    """The enemy emblem as flat geometry (single-sided, normal +Z): a broken
    ring (four arcs) over a thick downward chevron and a thin one
    (rmh/images.emblem_alpha, same proportions)."""
    bm = bmesh.new()
    k = size / 2

    def quad(pts):
        vs = [bm.verts.new((p[0] * k, p[1] * k, 0.0)) for p in pts]
        bm.faces.new(vs)

    for a0 in (45, 135, 225, 315):
        lo, hi = math.radians(a0 + 12), math.radians(a0 + 90 - 12)
        seg = 6
        for i in range(seg):
            t0 = lo + (hi - lo) * i / seg
            t1 = lo + (hi - lo) * (i + 1) / seg
            quad([(0.69 * math.cos(t0), 0.69 * math.sin(t0)), (0.87 * math.cos(t0), 0.87 * math.sin(t0)),
                  (0.87 * math.cos(t1), 0.87 * math.sin(t1)), (0.69 * math.cos(t1), 0.69 * math.sin(t1))])

    def arm(a, b, w):
        d = Vector((b[0] - a[0], b[1] - a[1]))
        n = Vector((-d.y, d.x)).normalized() * w
        A, B = Vector(a), Vector(b)
        pts = [A + n, A - n, B - n, B + n]
        if (pts[1] - pts[0]).cross(pts[2] - pts[1]) < 0:
            pts.reverse()
        quad([(p.x, p.y) for p in pts])

    for (ax, ay), (bx, by), w in (((-0.5, 0.42), (0.0, -0.38), 0.13), ((0.5, 0.42), (0.0, -0.38), 0.13),
                                  ((-0.3, 0.62), (0.0, 0.14), 0.07), ((0.3, 0.62), (0.0, 0.14), 0.07)):
        arm((ax, ay), (bx, by), w)
    bm.normal_update()
    for f in bm.faces:
        if f.normal.z < 0:
            f.normal_flip()
    return bm


def add_emblem(part, T, at, normal, up, size):
    bm = emblem(size)
    T.planar(bm, "red", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
    orient(bm, at, normal, up)
    part.add(bm, "trim")


# --- airframe -----------------------------------------------------------------------------

def fuselage(a, T):
    p = a.part("Root", tex="trim", query=False, collide=False, material="Metal", smooth_angle=35)
    shell = geo.loft(sections(FUSE), n=FUSE_N)
    shell.normal_update()
    glass = cockpit_glazing(shell)
    w = a.part("Windows", flat=(0.11, 0.157, 0.204), material="Glass", query=False, collide=False, shadow=False, smooth_angle=10)
    w.add(glass, "glass")
    cabin_windows(w)

    def in_band(f, band):
        c = f.calc_center_median()
        return band[1] < c.y < band[0] and f.normal.z < -0.42

    ramp, shell = split(shell, lambda f: in_band(f, RAMP_Y))
    door, shell = split(shell, lambda f: in_band(f, DOOR_Y))
    opening_frame(p, T, shell)
    p.add(box_map(T, shell, "plain"), "trim")
    ramp_door(a, T, ramp)
    cargo_door(a, T, door)
    hold(p, T)
    # Main-gear sponsons with flare dispensers.
    for s in (-1, 1):
        sp = geo.loft([(8.5, 0.4, 1.2, -6.2, 2.0, s * 7.3), (5.5, 3.3, 6.2, -5.7, 2.6, s * 7.65),
                       (-12.5, 3.5, 6.4, -5.7, 2.6, s * 7.75), (-18.0, 0.6, 2.0, -5.0, 2.0, s * 7.4)], n=14)
        p.add(box_map(T, sp, "plain"), "trim")
        fl = geo.box(0.35, 2.4, 1.0, bevel=0.0)
        box_map(T, fl, "bolted")
        p.add(fl, "trim", at=(s * 9.45, -13.0, -5.6))
    # Wing-box fairing on the roof and the dorsal fin fillet.
    p.add(box_map(T, geo.loft([(10.0, 1.0, 0.5, 7.1, 2.0), (6.0, 8.2, 2.4, 7.55, 2.6), (-12.5, 8.2, 2.6, 7.6, 2.6),
                                  (-18.5, 1.4, 0.7, 7.2, 2.0)], n=14), "plain"), "trim")
    p.add(box_map(T, geo.loft([(-22.0, 0.2, 0.2, 7.0, 2.0), (-30.0, 1.2, 1.2, 7.4, 2.2), (-38.0, 1.5, 3.6, 8.4, 2.2),
                                  (-41.5, 1.5, 5.0, 9.2, 2.2)], n=8), "plain"), "trim")
    # Ventral strakes under the upswept tail.
    for s in (-1, 1):
        st = geo.prism([(-44.5, 0.0), (-53.0, 0.0), (-53.0, -0.9), (-46.5, -1.3)], 0.14, bevel=0.0)
        geo.transform(st, rot=(90, 0, 90))
        aero.outward(st)
        box_map(T, st, "plain")
        p.add(st, "trim", at=(s * 3.3, 0, 1.2), rot=(0, s * 30, 0))
    # Radome seam band, refuelling probe, sensor ball, antennas.
    probe = geo.pipe_path([(2.2, 30.0, 6.4), (2.3, 38.0, 5.6), (2.2, 47.5, 4.4)], 0.22, verts=8)
    T.cylindrical(probe, "cable", axis=(0, 1, 0), along=True)
    p.add(probe, "trim")
    p.add(box_map(T, geo.sphere(0.95, 12, 7), "plain"), "trim", at=(0.0, 36.5, -8.7))
    for pos, up in (((0, 14.0, 9.0), True), ((0, -2.0, 9.1), True), ((0, 20.0, -9.0), False), ((0, -20.0, -9.0), False)):
        ant = geo.prism([(0.0, 0.0), (0.9, 0.0), (0.4, 0.8), (0.1, 0.8)], 0.08, bevel=0.0)
        aero.outward(ant)
        T.fill(ant, "plain")
        p.add(ant, "trim", at=pos, rot=(90 if up else -90, 0, 90))
    dome = geo.sphere(1.3, 12, 5, scale=(1.0, 1.4, 0.5))
    box_map(T, dome, "plain")
    p.add(dome, "trim", at=(0, 1.0, 9.0))
    # Emblem each side of the forward fuselage.
    for s in (-1, 1):
        at = surf(25.0, 10 if s > 0 else 170, out=0.08)
        add_emblem(p, T, at, (s, 0, 0.1), (0, 0, 1), 5.2)
    doors_and_frames(a, p, T)
    # Lights and attachments on the airframe.
    a.attach("NavLightTail", "Root", (0, -61.5, 5.65), axis=(0, -1, 0))
    a.attach("Beacon", "Root", (0, -6.0, -9.35), axis=(0, 0, -1))
    a.attach("CargoFloor", "Root", (0, -14.0, FLOOR_Z), axis=(0, -1, 0))
    return p


def opening_frame(p, T, shell):
    """Bolted frame round the ramp/cargo-door opening (the hole's boundary
    edges aft of the cockpit), a little proud of the skin."""
    for e in shell.edges:
        if len(e.link_faces) != 1:
            continue
        a, b = (v.co.copy() for v in e.verts)
        if max(a.y, b.y) > -20.0:  # only the belly opening (not the nose cap seam)
            continue
        n = e.link_faces[0].normal
        bar = geo.pipe_path([a + n * 0.06, b + n * 0.06], 0.1, verts=4)
        T.fill(bar, "bolted")
        p.add(bar, "trim")


def doors_and_frames(a, p, T):
    """Riveted frame bands round the fuselage, the crew door (left, under
    the cockpit), a paratroop door each side ahead of the ramp hinge with
    a window, and emergency hatches on the roof: bolted outlines."""
    for y in (22.0, 13.5, -8.0, -17.0):
        band = geo.loft([(y + 0.14, 15.34, 16.14, -1.0, 2.8), (y - 0.14, 15.34, 16.14, -1.0, 2.8)], n=FUSE_N,
                        cap_start=False, cap_end=False)
        T.cylindrical(band, "bolted", axis=(0, 1, 0), center=(0, 0, -1.0))
        p.add(band, "trim")

    def outline(y0, y1, a0, a1):
        pts = [surf(y0, a0, 0.05), surf(y1, a0, 0.05), surf(y1, a1, 0.05), surf(y0, a1, 0.05), surf(y0, a0, 0.05)]
        for q0, q1 in zip(pts, pts[1:]):
            bar = geo.pipe_path([q0, q1], 0.09, verts=4)
            T.fill(bar, "bolted")
            p.add(bar, "trim")

    outline(27.2, 30.4, 184, 214)  # crew door, left
    for s in (-1, 1):
        a0, a1 = (-28, 2) if s > 0 else (178, 208)
        outline(-19.0, -23.0, a0, a1)  # paratroop doors
        a.attach("ParaDoorL" if s < 0 else "ParaDoorR", "Root", tuple(surf(-21.0, (a0 + a1) / 2, 0.1)), axis=(s, 0, 0))
    for y in (18.0, -10.5):  # roof escape hatches
        outline(y - 1.1, y + 1.1, 78, 102)


def ramp_door(a, T, ramp):
    """Ramp: the belly panel between the cargo floor and the door, with
    thickness; its top (inner) face is the loading surface."""
    a.pivot("Ramp", tuple(HINGE))
    part = a.part("RampDoor", path="Ramp", tex="trim", query=False, collide=False, material="Metal", smooth_angle=35)
    box_map(T, ramp, "plain")
    ramp.normal_update()
    bmesh.ops.solidify(ramp, geom=list(ramp.faces), thickness=0.45)
    ramp.normal_update()
    # Inner (upward-facing) faces: roller-track floor.
    T.planar(ramp, "bolted", u_axis=(0, 1, 0), v_axis=(1, 0, 0), faces=lambda f: f.normal.z > 0.5)
    part.add(ramp, "trim")
    lip = Vector((0.0, RAMP_Y[1] + 0.25, -4.4 + 0.6))
    a.attach("ReleasePoint", "RampDoor", tuple(lip), axis=(0, -1, 0))


def cargo_door(a, T, door):
    a.pivot("CargoDoor", tuple(DOOR_HINGE))
    part = a.part("CargoDoorPanel", path="CargoDoor", tex="trim", query=False, collide=False, material="Metal", smooth_angle=35)
    box_map(T, door, "plain")
    bmesh.ops.solidify(door, geom=list(door.faces), thickness=0.35)
    door.normal_update()
    T.planar(door, "canvas", u_axis=(0, 1, 0), v_axis=(1, 0, 0), faces=lambda f: f.normal.z > 0.5)
    part.add(door, "trim")


def hold(p, T):
    """Cargo hold seen through the open ramp: quilted walls and ceiling
    (canvas), roller floor, a bulkhead at the front of the visible bay."""
    stations = [s for s in FUSE if -47.0 <= s[0] <= -12.0]
    stations = [(-12.0, 15.2, 7.0, -9.0, 2.8)] + [s for s in stations if s[0] < -12.0]
    inner = [(y, w - 0.9, top - 0.45, max(bot + 0.45, FLOOR_Z), e) for y, w, top, bot, e in stations]
    shell = geo.loft(sections(inner), n=16, cap_start=False, cap_end=False)
    bmesh.ops.reverse_faces(shell, faces=list(shell.faces))  # faces the inside
    shell.normal_update()
    # No floor or lower sides: the floor box covers the cabin, and aft of
    # the hinge that is the ramp/door opening (same split as the skin).
    bmesh.ops.delete(shell, geom=[f for f in shell.faces if f.normal.z > 0.42], context="FACES")
    shell.normal_update()
    T.planar(shell, "canvas", u_axis=(0, 1, 0), v_axis=(1, 0, 0), faces=lambda f: abs(f.normal.z) >= 0.6)
    T.planar(shell, "canvas", u_axis=(0, 1, 0), v_axis=(0, 0, 1), faces=lambda f: abs(f.normal.z) < 0.6)
    p.add(shell, "trim")
    floor = geo.box(13.4, 14.4, 0.2, bevel=0.0)
    T.planar(floor, "bolted", u_axis=(0, 1, 0), v_axis=(1, 0, 0))
    p.add(floor, "trim", at=(0, -19.0, FLOOR_Z - 0.1))
    bulk = geo.box(14.2, 0.3, 15.2, bevel=0.0)
    box_map(T, bulk, "plain", along=0)
    p.add(bulk, "trim", at=(0, -11.9, -1.1))


def wings(a, T):
    p = a.part("Wings", tex="trim", query=False, collide=False, material="Metal", smooth_angle=35)
    for s in (-1, 1):
        secs = [(x, c, t, le - c / 2, wing_z(x), 2.2) for x, c, t, le in WING]
        w = aero.span_loft(secs, n=12)
        if s < 0:
            w = geo.mirror_x(w)
        tips = lambda f: abs(f.calc_center_median().x) > WING[-2][0]  # noqa: E731
        T.planar(w, "plain", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=lambda f: not tips(f))
        T.planar(w, "red", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=tips)
        p.add(w, "trim")
        # Flap track fairings under the trailing edge.
        for x in (12.0, 28.0, 46.0, 58.0):
            y = wing_le(x) - wing_chord(x) + 1.6
            f = aero.store(4.4, 0.32, nose=0.35, tail=0.5, verts=8)
            box_map(T, f, "plain")
            p.add(f, "trim", at=(s * x, y, wing_z(x) - 0.55))
        # Emblem under each wing, outboard of the engines.
        x = 54.0
        th = WING[2][2] + (WING[3][2] - WING[2][2]) * (x - WING[2][0]) / (WING[3][0] - WING[2][0])
        add_emblem(p, T, (s * x, wing_le(x) - wing_chord(x) * 0.5, wing_z(x) - th / 2 - 0.08), (0, 0, -1), (0, 1, 0), 6.4)
        nl = "NavLightL" if s < 0 else "NavLightR"
        a.attach(nl, "Wings", (s * 71.25, WING[-1][3] - 2.6, wing_z(71.0)), axis=(s, 0, 0))
    for x, k in ENGINES:
        nacelle(a, p, T, x, k)
    return p


def nacelle(a, p, T, x, k):
    h = hub(x)
    le = wing_le(x)
    zc = h.z
    secs = [(h.y - 0.9, 3.0, 3.2, zc, 2.2, x), (h.y - 2.6, 4.2, 4.9, zc - 0.15, 2.4, x), (le, 4.4, 5.6, zc + 0.1, 2.6, x),
            (le - 7.0, 4.0, 4.9, zc + 0.45, 2.6, x), (le - wing_chord(x) - 2.5, 1.2, 1.4, zc + 1.4, 2.2, x)]
    body = geo.loft(secs, n=16)
    p.add(box_map(T, body, "plain"), "trim")
    # Chin oil-cooler scoop with a louvred mouth.
    scoop = geo.loft([(h.y - 3.0, 1.9, 1.1, zc - 2.55, 2.6, x), (h.y - 6.0, 2.2, 1.4, zc - 2.7, 2.6, x),
                      (le - 1.5, 1.2, 0.6, zc - 2.4, 2.2, x)], n=10)
    mouth, rest = split(scoop, lambda f: f.normal.y > 0.8)
    T.planar(mouth, "grille", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
    p.add(mouth, "trim")
    p.add(box_map(T, rest, "plain"), "trim")
    # Exhaust stack on the outboard upper side, over the wing.
    side = 1 if x > 0 else -1
    e0 = Vector((x + side * 1.6, le - 1.0, zc + 1.9))
    e1 = Vector((x + side * 2.2, le - 4.6, zc + 2.35))
    ex = geo.pipe_path([e0, e1], 0.55, verts=10)
    T.cylindrical(ex, "cable", axis=tuple((e1 - e0).normalized()), center=tuple(e0), along=True)
    p.add(ex, "trim")
    a.attach(f"Exhaust{k}", "Wings", tuple(e1 + (e1 - e0).normalized() * 0.2), axis=tuple((e1 - e0).normalized()))
    propeller(a, T, h, k)


def blade(T):
    """One scimitar blade along +X from the hub (chord in the disc plane,
    thickness along the thrust axis before pitch), red tip."""
    tip = PROP_R - 0.7
    b = aero.span_loft([(0.9, 0.8, 0.34, 0.0, 0.0, 2.4), (2.6, 1.6, 0.24, 0.1, 0.0, 2.6), (4.6, 1.45, 0.16, -0.15, 0.0, 2.6),
                        (tip, 0.85, 0.11, -0.5, 0.0, 2.6), (PROP_R, 0.3, 0.06, -0.85, 0.0, 2.4)], n=6)
    T.planar(b, "plain", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=lambda f: f.calc_center_median().x < tip)
    T.planar(b, "red", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=lambda f: f.calc_center_median().x >= tip)
    return b


def propeller(a, T, h, k):
    path = f"Prop{k}"
    a.pivot(path, tuple(h))
    bp = a.part(f"Blades{k}", path=path, tex="trim", query=False, collide=False, joint=tuple(h), material="Metal", smooth_angle=40)
    spinner = geo.lathe([(0.0, 1.9), (0.55, 1.6), (0.95, 1.0), (1.2, 0.2), (1.25, -0.6), (1.25, -1.1)], verts=14)
    geo.transform(spinner, rot=(-90, 0, 0))  # axis +Z -> +Y (forward)
    T.cylindrical(spinner, "plain", axis=(0, 1, 0))
    bp.add(spinner, "trim", at=tuple(h))
    for i in range(BLADES):
        b = blade(T)
        # Chord into the disc plane (XZ), 28 deg of pitch, then round the hub.
        geo.transform(b, rot=(90 - 28, 0, 0))
        geo.transform(b, rot=(0, 360.0 * i / BLADES + 15 * k, 0))
        bp.add(b, "trim", at=tuple(h + Vector((0, -0.25, 0))))
    disc(a, T, h, k, path)


def disc(a, T, h, k, path):
    """Prop-blur disc: charcoal inner disc, red tip ring, both faces."""
    bm = bmesh.new()
    n = 28
    r_in, r_out = PROP_R - 0.75, PROP_R
    for side, y in ((1, 0.02), (-1, -0.02)):
        c = bm.verts.new((0, y, 0))
        inner = [bm.verts.new((r_in * math.cos(TAU * i / n), y, r_in * math.sin(TAU * i / n))) for i in range(n)]
        outer = [bm.verts.new((r_out * math.cos(TAU * i / n), y, r_out * math.sin(TAU * i / n))) for i in range(n)]
        for i in range(n):
            j = (i + 1) % n
            tri = [c, inner[i], inner[j]] if side < 0 else [c, inner[j], inner[i]]
            bm.faces.new(tri)
            q = [inner[i], outer[i], outer[j], inner[j]] if side < 0 else [inner[j], outer[j], outer[i], inner[i]]
            bm.faces.new(q)
    bm.normal_update()
    for f in bm.faces:  # each face looks away from the disc's mid-plane
        if f.normal.y * f.calc_center_median().y < 0:
            f.normal_flip()
    bm.normal_update()
    ring = lambda f: Vector((f.calc_center_median().x, f.calc_center_median().z)).length > r_in - 0.01  # noqa: E731
    T.planar(bm, "plain", u_axis=(1, 0, 0), v_axis=(0, 0, 1), faces=lambda f: not ring(f))
    T.planar(bm, "red", u_axis=(1, 0, 0), v_axis=(0, 0, 1), faces=ring)
    d = a.part(f"Disc{k}", path=path, tex="trim", query=False, collide=False, shadow=False, transparency=1,
               joint=tuple(h), material="Metal", smooth_angle=10)
    d.add(bm, "trim", at=tuple(h + Vector((0, -0.25, 0))))


def tail(a, T):
    p = a.part("Tail", tex="trim", query=False, collide=False, material="Metal", smooth_angle=35)
    fin = aero.span_loft([(5.2, 22.0, 1.7, -50.0, 0.0, 2.3), (18.0, 15.0, 1.15, -54.0, 0.0, 2.3), (28.5, 10.5, 0.75, -57.2, 0.0, 2.3),
                          (31.0, 9.4, 0.62, -57.9, 0.0, 2.3)], axis="z", n=12)
    tip = lambda f: f.calc_center_median().z > 28.5  # noqa: E731
    T.planar(fin, "plain", u_axis=(0, 1, 0), v_axis=(0, 0, 1), faces=lambda f: not tip(f))
    T.planar(fin, "red", u_axis=(0, 1, 0), v_axis=(0, 0, 1), faces=tip)
    p.add(fin, "trim")
    for s in (-1, 1):
        add_emblem(p, T, (s * 0.62, -53.5, 17.5), (s, 0, 0), (0, 0, 1), 7.5)
        st = aero.span_loft([(0.0, 13.0, 1.3, -53.2, 4.6, 2.3), (27.0, 6.0, 0.5, -56.8, 4.6 + 27.0 * math.tan(math.radians(6)), 2.3)], n=10)
        if s < 0:
            st = geo.mirror_x(st)
        T.planar(st, "plain", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
        p.add(st, "trim")
    return p


def face_angle(f):
    """Section angle (degrees, 0 = +X, 90 = top) of a fuselage face."""
    c = f.calc_center_median()
    w, top, bot, _ = section_at(c.y)
    return math.degrees(math.atan2((c.z - (top + bot) / 2) / ((top - bot) / 2), c.x / (w / 2))) % 360


COCKPIT = [((37.6, 40.0), (40, 140)),  # windscreen, on the step
           ((35.0, 37.6), (60, 120)),  # eyebrow windows
           ((35.0, 40.0), (22, 45)), ((35.0, 40.0), (135, 158))]  # side windows


def cockpit_glazing(shell):
    """Cut the cockpit panes out of the fuselage loft: each facet in the
    glazed band is inset (the rim stays skin, a frame), the pane recessed a
    little and removed from `shell`; returns the panes as a bmesh."""
    def pane(f):
        c = f.calc_center_median()
        ang = face_angle(f)
        return any(y0 < c.y < y1 and a0 < ang < a1 for (y0, y1), (a0, a1) in COCKPIT)

    tag = shell.faces.layers.int.new("rmh_pane")  # layer first: adding one invalidates face refs
    shell.normal_update()
    faces = [f for f in shell.faces if pane(f)]
    for f in faces:
        f[tag] = 1
    bmesh.ops.inset_individual(shell, faces=faces, thickness=0.16, depth=-0.04, use_even_offset=True)
    shell.normal_update()
    for f in shell.faces:  # the new rim faces copied the tag: they are frame (skin)
        f[tag] = 0
    for f in faces:
        f[tag] = 1
    glass = shell.copy()
    gt = glass.faces.layers.int.get("rmh_pane")
    bmesh.ops.delete(glass, geom=[f for f in glass.faces if not f[gt]], context="FACES")
    st = shell.faces.layers.int.get("rmh_pane")
    bmesh.ops.delete(shell, geom=[f for f in shell.faces if f[st]], context="FACES")
    shell.normal_update()
    glass.normal_update()
    return glass


def cabin_windows(w):
    """Cabin and paratroop-door windows: flat Glass panes just off the
    (flat) cabin sides."""

    def pane(y0, y1, a0, a1):
        corners = [surf(y, ang, out=0.07) for y, ang in ((y0, a0), (y1, a0), (y1, a1), (y0, a1))]
        bm = bmesh.new()
        f = bm.faces.new([bm.verts.new(c) for c in corners])
        bm.normal_update()
        centre = f.calc_center_median()
        _, top, bot, _ = section_at((y0 + y1) / 2)
        if f.normal.dot(centre - Vector((0, centre.y, (top + bot) / 2))) < 0:
            f.normal_flip()
        w.add(bm, "glass")

    for a0, a1 in ((-18, -8), (188, 198)):  # paratroop door windows
        pane(-20.4, -21.6, a0, a1)
    for y in (22.0, 12.0, -4.0, -12.5):  # cabin windows
        for a0, a1 in ((4, 10), (170, 176)):
            pane(y - 0.6, y + 0.6, a0, a1)


def lamps(a):
    for name, pos, col in (("NavLampL", (-71.3, WING[-1][3] - 2.6, wing_z(71.0)), (1.0, 0.12, 0.08)),
                           ("NavLampR", (71.3, WING[-1][3] - 2.6, wing_z(71.0)), (0.1, 1.0, 0.35)),
                           ("NavLampTail", (0.0, -61.35, 5.65), (1.0, 0.95, 0.85)),
                           ("BeaconLamp", (0.0, -6.0, -9.2), (1.0, 0.1, 0.06)),
                           ("BeaconLampTop", (0.0, -14.0, 9.05), (1.0, 0.1, 0.06))):
        lamp = geo.sphere(0.32, 8, 5)
        a.part(name, neon=col, query=False, collide=False, shadow=False).add(lamp, "lamp", at=pos)
    a.attach("BeaconTop", "Root", (0.0, -14.0, 9.4), axis=(0, 0, 1))
    # Formation ("slime") light strips: forward and aft fuselage sides, fin
    # sides, wing tips. One Neon part, hidden in the file: show it at dusk
    # and night so the transport's shape reads against a dark sky.
    fl = a.part("FormationLights", neon=(0.62, 1.0, 0.5), transparency=1, query=False, collide=False, shadow=False)
    for s in (-1, 1):
        ang = 8 if s > 0 else 172
        for y in (27.0, -33.0):
            c = surf(y, ang, out=0.05)
            fl.add(geo.box(0.06, 4.2, 0.36, bevel=0.0), "lamp", at=tuple(c))
        fl.add(geo.box(0.06, 4.6, 0.36, bevel=0.0), "lamp", at=(s * 0.8, -52.5, 11.0), rot=(-34, 0, 0))
        x = 69.0
        th = WING[3][2] + (WING[4][2] - WING[3][2]) * (x - WING[3][0]) / (WING[4][0] - WING[3][0])
        fl.add(geo.box(0.32, 3.6, 0.06, bevel=0.0), "lamp", at=(s * x, wing_le(x) - wing_chord(x) * 0.45, wing_z(x) + th / 2 + 0.04))


def lod(a, T):
    """Far LOD: fuselage, wings with nacelles, fin and tailplanes as one
    ~1.5k-triangle mesh."""
    a.pivot("LOD", (0, 0, 0))
    p = a.part("LODHull", path="LOD", tex="trim", query=False, collide=False, transparency=1, material="Metal", smooth_angle=35)
    stations = [FUSE[i] for i in (0, 2, 4, 6, 8, 11, 13, 15, 17, 19)]
    p.add(box_map(T, geo.loft(sections(stations), n=12), "plain"), "trim")
    for s in (-1, 1):
        secs = [(x, c, t, le - c / 2, wing_z(x), 2.2) for x, c, t, le in (WING[0], WING[2], WING[4])]
        w = aero.span_loft(secs, n=6)
        if s < 0:
            w = geo.mirror_x(w)
        T.planar(w, "plain", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
        p.add(w, "trim")
        st = aero.span_loft([(0.0, 13.0, 1.3, -53.2, 4.6, 2.3), (27.0, 6.0, 0.5, -56.8, 7.4, 2.3)], n=6)
        if s < 0:
            st = geo.mirror_x(st)
        T.planar(st, "plain", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
        p.add(st, "trim")
    for x, _ in ENGINES:
        h = hub(x)
        le = wing_le(x)
        body = geo.loft([(h.y - 0.9, 3.0, 3.2, h.z, 2.2, x), (le, 4.4, 5.6, h.z + 0.1, 2.6, x),
                         (le - wing_chord(x) - 2.5, 1.2, 1.4, h.z + 1.4, 2.2, x)], n=8)
        p.add(box_map(T, body, "plain"), "trim")
    fin = aero.span_loft([(5.2, 22.0, 1.7, -50.0, 0.0, 2.3), (31.0, 9.4, 0.62, -57.9, 0.0, 2.3)], axis="z", n=6)
    T.planar(fin, "plain", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
    p.add(fin, "trim")


def build(**kw):
    a = Asset("Transport", pivot=(0, 0, 0), tex_size=1024)
    a.fix_inside_out = True
    a.preview_hide_transparent = True
    a.meta["no_ground"] = True  # seen against the sky
    a.meta["no_wreck"] = True  # never charred: no burnt Wreck folders from the trim sheet
    a.meta["ramp_open_deg"] = round(RAMP_OPEN_DEG, 2)
    a.meta["cargo_door_open_deg"] = DOOR_OPEN_DEG
    T = trim.use(a, "trim", "TrimEnemy")
    a.material("glass", kind="flat", color="#1c2834")
    a.material("lamp", kind="flat", color="#ff3020")
    fuselage(a, T)
    wings(a, T)
    tail(a, T)
    lamps(a)
    lod(a, T)
    views = [("", (1.0, 1.1, 0.5)), ("_rear", (-0.9, -1.2, 0.35)), ("_side", (1.0, 0.0, 0.05)),
             ("_front", (0.15, 1.0, 0.05)),
             {"label": "_below", "pos": (18, 40, -230), "look": (0, -6, 4), "fov": 40, "res": (1280, 900)},
             {"label": "_cam_turret", "pos": (-120, 260, -290), "look": (0, 0, 0), "fov": 22, "res": (1280, 900)},
             {"label": "_ramp", "pos": (22, -95, -22), "look": (0, -34, -4), "fov": 40, "res": (1280, 900)},
             {"label": "_close_nose", "pos": (26, 70, 4), "look": (0, 36, 0), "fov": 40, "res": (1280, 900)},
             {"label": "_lod", "pos": (-120, 260, -290), "look": (0, 0, 0), "fov": 22, "res": (1280, 900),
              "show": ["LODHull"], "hide": ["Root", "Wings", "Tail", "Windows", "RampDoor", "CargoDoorPanel"]
              + [f"Blades{k}" for k in range(1, 5)]}]
    manifest = a.finish(views=views, **kw)
    if kw.get("preview", True):
        open_doors_preview(a)
    return manifest


def open_doors_preview(a):
    """Extra previews with the ramp and cargo door open (rotated about their
    hinges exactly as the contract says: +21.8 / +60 deg about X, which is
    the same angle in Blender and Roblox axes). Not part of the export."""
    import bpy

    from rmh import pipeline

    for name, hinge, deg in (("RampDoor", HINGE, RAMP_OPEN_DEG), ("CargoDoorPanel", DOOR_HINGE, DOOR_OPEN_DEG)):
        o = bpy.data.objects[name]
        m = Matrix.Translation(hinge) @ Matrix.Rotation(math.radians(deg), 4, "X") @ Matrix.Translation(-hinge)
        o.matrix_world = m @ o.matrix_world
    pipeline.render_previews(a, [
        {"label": "_ramp_open", "pos": (26, -100, -26), "look": (0, -33, -5), "fov": 40, "res": (1280, 900)},
        {"label": "_ramp_open_side", "pos": (70, -40, -14), "look": (0, -34, -4), "fov": 40, "res": (1280, 900)},
    ], samples=64)
