"""Tank: enemy main battle tank (original design). Dark gunmetal with red
markings, the enemy emblem and turret numbers.

Asset origin = ground centre under the hull. Root = hull; TrackL / TrackR
= tracks with road wheels, sprocket, idler and return rollers; sub-model
Turret (WorldPivot = turret ring centre) with parts TurretBody and Barrel;
attachment Barrel.Muzzle.

HS-3 hard-surface pass: sloped glacis and sponsons, spaced-armour skirt
modules, wedge cheek armour on a faceted turret with a stowage basket,
cupola periscopes, smoke dischargers, roof MG, louvred engine deck,
armoured exhaust shrouds, tools, tow cable, jerrycans, spare track links,
hand rails and whip antennas. The hull, turret and barrel are baked from
high-poly copies (rounded edges, bolts, weld beads) with curvature chips,
AO grime, a dust gradient from the ground, soot at the exhausts and the
muzzle, and chipped red markings; tracks, wheels and stowage use the
shared TrimEnemy sheet (parts TrackL/R, HullKit, Turret/TurretKit).
Every contract part keeps its pre-HS-3 bounding box (= hit box, sizes
the client's VehicleFx reads): `HIT` below, enforced by the build.
"""
import math

import bmesh
from mathutils import Vector

from rmh import geo, hardsurface as hs, images, trim
from rmh.asset import Asset, rb_box

# Contract hit boxes: Roblox (centre, size) of the pre-HS-3 parts.
HIT = {
    "Root": ((0.0, 3.4, 0.7408), (11.52, 3.8, 26.6184)),
    "TrackL": ((-4.35, 1.695, 0.2693), (2.28, 3.49, 23.2385)),
    "TrackR": ((4.35, 1.695, 0.2693), (2.28, 3.49, 23.2385)),
    "TurretBody": ((0.0, 8.325, 0.9789), (8.8316, 6.75, 13.2422)),
    "Barrel": ((0.0, 6.35, -11.475), (1.1, 1.0724, 12.55)),
}
RING = (0.0, 0.6, 5.0)
GUN_Z = 6.35
MUZZLE_Y = 17.8
TRACK_X = 4.35
TRACK_W = 2.2
DECK = 4.9
ROOF = 8.05
PAINT = "#3e4247"
DARK = "#2b2d31"
RED = "#b01c18"
DUST = "#a4876a"

# Soot sources (exhaust outlets, smoke dischargers, muzzle).
EXHAUSTS = [(side * 4.3, -12.55, 4.35) for side in (-1, 1)]


def materials(a):
    photo = {"id": "green_metal_rust", "scale": 4.5, "color": 0.5, "sat": 0.1, "rough": 0.45, "height": 0.25}
    paint = dict(kind="paint", color=PAINT, rough=0.5, wear=0.55, under="#8b8c89", under_metal=0.8, under_rough=0.35,
                 chip_style="blotch", chip_scale=5.0, chip_bevel=0.12, ring=0.3, ring_color="#24201c",
                 edge_convex=True, polish=0.3, grime=0.6, streaks=0.45, dust=0.6, dust_up=0.35, dust_height=3.2,
                 dust_color=DUST, dust_caked=0.8, caked_height=2.7, caked_color="#8e7556", rough_breakup=0.3,
                 photo=photo, fade=0.25, fade_color="#5d6166", bevel=0.06)
    soot = [{"pos": p, "dir": (0.25 * math.copysign(1, p[0]), -0.35, 0.9), "radius": 0.55, "length": 2.8, "spread": 0.45}
            for p in EXHAUSTS]
    soot += [{"pos": (p[0], -12.9, 3.2), "dir": (0, 0, -1), "radius": 0.7, "length": 1.4, "spread": 0.3, "strength": 0.6}
             for p in EXHAUSTS]
    a.material("hull", **paint, soot=soot)
    a.material("hull_dark", **dict(paint, color=DARK, photo=None, fade=0.1), soot=soot)
    a.material("skirt", **dict(paint, dust=0.8, dust_height=5.2, caked_height=3.5))
    band = [{"lo": (-4.6, -6.35, 5.9), "hi": (4.6, -5.8, 7.5), "color": RED}]
    tsoot = [{"pos": (s * 3.45, 3.25, 7.45), "dir": (s * 0.3, 0.5, 0.8), "radius": 0.35, "length": 1.2, "strength": 0.55} for s in (-1, 1)]
    a.material("turret", **dict(paint, dust_height=0.0, dust_caked=0.0, dust_up=0.5), marks=band, soot=tsoot)
    a.material("turret_dark", **dict(paint, color=DARK, photo=None, dust_height=0.0, dust_caked=0.0, dust_up=0.5), soot=tsoot)
    msoot = [{"pos": (0, MUZZLE_Y - 0.05, GUN_Z), "dir": (0, -1, 0), "radius": 0.36, "length": 3.6, "spread": 0.04, "strength": 0.95}]
    a.material("barrel", **dict(paint, color="#34373b", dust_height=0.0, dust_caked=0.0, dust_up=0.4, wear=0.45), soot=msoot)
    a.material("steel", kind="metal", color="#3a3b3c", rough=0.45, metal=0.9, dust=0.3, grime=0.6, edge_convex=True, polish=0.6)


# --- hull ----------------------------------------------------------------------------

HULL_PROFILE = [(-11.6, 1.5), (10.8, 1.5), (12.45, 3.2), (12.5, 3.45), (11.2, 3.8), (-12.3, 3.8), (-12.55, 2.05)]
SPONSON = [(-12.35, 3.75), (10.4, 3.75), (12.48, 3.43), (6.6, 4.84), (-8.8, DECK + 0.01), (-12.3, 4.79)]


def hull(a):
    lo, hi = rb_box(*HIT["Root"])
    p = a.part("Root", tex="hull", material="Metal", smooth_angle=35, hitbox=(lo, hi))
    # Lower hull between the tracks: its flanks hide behind the tracks and
    # its top inside the sponsons, so they get little texture.
    hidden = lambda f: 0.12 if abs(f.normal.x) > 0.7 or f.normal.z > 0.7 else 1.0  # noqa: E731
    p.add(geo.side_prism(HULL_PROFILE, 6.5, bevel=0.0), "hull", texel=hidden)
    sp = geo.side_prism(SPONSON, 10.6, bevel=0.0)
    for v in sp.verts:  # sponson walls lean inward toward the deck
        if v.co.z > 4.3:
            v.co.x *= 0.965
    # Big chamfer along the sponsons' top outer edges (breaks the box edge).
    hs.chamfer_edges(sp, lambda e: all(abs(v.co.x) > 4.9 and v.co.z > 4.7 for v in e.verts)
                     and abs((e.verts[0].co - e.verts[1].co).normalized().y) > 0.8, 0.32)
    # Cut the deck round the turret footprint: the part under the turret is
    # rarely seen and gets less texture.
    for co, no in (((0, -5.9, 0), (0, 1, 0)), ((0, 3.9, 0), (0, 1, 0)), ((-3.5, 0, 0), (1, 0, 0)), ((3.5, 0, 0), (1, 0, 0))):
        bmesh.ops.bisect_plane(sp, geom=list(sp.verts) + list(sp.edges) + list(sp.faces), plane_co=co, plane_no=no)
    under_turret = lambda f: 0.3 if (f.normal.z > 0.7 and abs(f.calc_center_median().x) < 3.5  # noqa: E731
                                     and -5.9 < f.calc_center_median().y < 3.9) else 1.0
    p.add(sp, "hull", texel=under_turret)
    # Weld seams where the glacis meets the sponsons and the deck.
    for side in (-1, 1):
        p.detail(hs.weld([(side * 5.25, 11.2, 3.78), (side * 5.1, 6.6, 4.86)], r=0.05), "hull")
        p.detail(hs.weld([(side * 3.25, 12.4, 3.4), (side * 3.25, 10.9, 1.6)], r=0.045), "hull")
    p.detail(hs.weld([(-5.0, 6.62, 4.84), (5.0, 6.62, 4.84)], r=0.05), "hull")
    p.detail(hs.weld([(-3.2, 12.49, 3.46), (3.2, 12.49, 3.46)], r=0.05), "hull")
    # Splash board across the upper glacis.
    vane = geo.prism([(-3.0, 0.0), (0.0, 0.5), (3.0, 0.0), (3.0, 0.18), (0.0, 0.68), (-3.0, 0.18)], 0.35, bevel=0.03, segments=1)
    p.add(vane, "hull_dark", at=(0, 9.35, 4.35), rot=(0, 0, 0))
    # Driver's hatch with hinge, and his periscope bed (periscopes in the kit).
    p.add(geo.cylinder(0.72, 0.16, verts=16, bevel=0.04, segments=1), "hull_dark", at=(-1.5, 5.6, DECK + 0.02))
    p.add(geo.box(1.7, 0.5, 0.22, bevel=0.05, segments=1), "hull_dark", at=(-1.5, 6.55, 4.9), rot=(-13, 0, 0))
    p.detail(hs.bolt_row((-2.0, 5.6, DECK + 0.1), (-1.0, 5.6, DECK + 0.1), 4, (0, 0, 1), r=0.045, h=0.03), "hull_dark")
    # Engine deck: louvred grille frames (grilles in the kit), access doors.
    for side in (-1, 1):
        p.add(geo.box(2.35, 4.4, 0.16, bevel=0.04, segments=1), "hull_dark", at=(side * 1.75, -9.6, DECK + 0.05))
        p.detail(hs.bolt_row((side * 0.62, -11.7, DECK + 0.13), (side * 0.62, -7.5, DECK + 0.13), 7, (0, 0, 1), r=0.045, h=0.03), "hull_dark")
        p.detail(hs.bolt_row((side * 2.88, -11.7, DECK + 0.13), (side * 2.88, -7.5, DECK + 0.13), 7, (0, 0, 1), r=0.045, h=0.03), "hull_dark")
        # Access door on each sponson with hinges and a handle.
        p.add(geo.box(1.1, 2.6, 0.08, bevel=0.03, segments=1), "hull", at=(side * 4.45, -5.2, DECK - 0.02))
        for y in (-6.3, -4.1):
            p.detail(geo.cylinder(0.07, 0.3, verts=8, bevel=0.0), "hull_dark", at=(side * 3.95, y, DECK + 0.05), rot=(90, 0, 0))
    p.add(geo.box(0.9, 3.8, 0.1, bevel=0.03, segments=1), "hull_dark", at=(0, -9.6, DECK + 0.02))
    # Armoured exhaust shrouds on the rear corners (louvres in the kit).
    for x, y, z in EXHAUSTS:
        shroud = geo.tapered_box(1.5, 1.1, 0.85, top_scale=(0.9, 0.75), top_shift=(0, 0.1), bevel=0.06, segments=1)
        p.add(shroud, "hull_dark", at=(x, y + 0.45, z + 0.0))
        p.detail(hs.bolt_row((x - 0.6, y + 0.98, z - 0.3), (x + 0.6, y + 0.98, z - 0.3), 4, (0, 1, 0), r=0.04, h=0.03), "hull_dark")
    # Rear plate: tail lights, tow pintle, jerrycan shelf.
    for side in (-1, 1):
        p.add(geo.box(0.5, 0.2, 0.3, bevel=0.04, segments=1), "hull_dark", at=(side * 2.8, -12.62, 4.2))
        p.add(geo.torus(0.26, 0.07, verts=10, ring_verts=4), "hull_dark", at=(side * 2.1, -12.55, 2.35), rot=(0, 90, 0))
    p.add(geo.box(4.4, 0.9, 0.12, bevel=0.03, segments=1), "hull_dark", at=(0, -12.95, 2.55))
    for x in (-2.1, 2.1):
        p.add(geo.box(0.12, 0.7, 0.9, bevel=0.02, segments=1), "hull_dark", at=(x, -12.9, 2.95))
    # Front: tow hooks, headlight brackets, mud flaps.
    for side in (-1, 1):
        p.add(geo.torus(0.28, 0.08, verts=10, ring_verts=4), "hull_dark", at=(side * 2.0, 12.15, 2.35), rot=(0, 90, 0))
        p.add(geo.box(0.8, 0.5, 0.35, bevel=0.05, segments=1), "hull_dark", at=(side * 4.0, 10.45, 4.05))
        p.add(geo.box(1.9, 0.08, 0.75, bevel=0.02, segments=1), "hull_dark", at=(side * TRACK_X, 11.3, 3.35), rot=(12, 0, 0))
    # Fender stowage bins (low, so they stay inside the hull's hit box).
    for side in (-1, 1):
        for y, ln in ((-9.9, 2.4), (1.8, 2.0)):
            p.add(geo.box(1.0, ln, 0.34, bevel=0.05, segments=1), "hull_dark", at=(side * 4.75, y, DECK + 0.17))
            p.detail(hs.weld([(side * 4.25, y - ln / 2, DECK + 0.02), (side * 4.25, y + ln / 2, DECK + 0.02)], r=0.035), "hull_dark")
    skirts(a)
    # Markings: the emblem on the second skirt module, chipped.
    for side in (-1, 1):
        a.decal(images.get("emblem"), (side * 5.65, 3.4, 3.2), (side, 0, 0), (1.7, 1.7, 0.6), color=RED, wear=0.3, seed=3 + side)
    for side in (-1, 1):
        a.attach("Headlight", "Root", (side * 4.0, 11.05, 4.2), axis=(0, 1, -0.1))


def skirts(a):
    """Spaced-armour skirt modules hung off the sponsons (gap 0.2). Their
    own part (inside Root's hit box, so not hittable itself) baked into the
    turret's atlas, which has room: the hull atlas alone would fall under
    30 px/stud."""
    p = a.part("Skirts", tex="turret", material="Metal", query=False, smooth_angle=35)
    y0, length, gap = -11.45, 3.7, 0.12
    for side in (-1, 1):
        for i in range(6):
            ya = y0 + i * (length + gap)
            yb = ya + length
            thick = 0.34 if i >= 4 else 0.22
            if i == 5:  # front module: lower front corner cut away
                prof = [(ya, 2.05), (yb - 1.1, 2.05), (yb, 3.1), (yb, 4.35), (ya, 4.35)]
            else:
                prof = [(ya, 2.05), (yb, 2.05), (yb, 4.35), (ya, 4.35)]
            panel = geo.side_prism(prof, thick, bevel=0.0)
            x = side * (5.5 + (0.06 if i >= 4 else 0.0))
            inner = lambda f, sd=side: 0.15 if f.normal.x * sd < -0.5 else 1.0  # noqa: E731
            p.add(panel, "skirt", at=(x, 0, 0), texel=inner)
            p.add(geo.box(0.3, 0.3, 0.3, bevel=0.03, segments=1), "hull_dark", at=(side * 5.3, (ya + yb) / 2, 4.2))
            xo = x + side * (thick / 2)
            n = 4 if i < 5 else 3
            p.detail(hs.bolt_row((xo, ya + 0.3, 4.12), (xo, yb - 0.3, 4.12), n, (side, 0, 0), r=0.07, h=0.05), "skirt")
            p.detail(hs.bolt_row((xo, ya + 0.3, 2.3), (xo, (yb - 1.2 if i == 5 else yb - 0.3), 2.3), n, (side, 0, 0), r=0.06, h=0.04), "skirt")
            if i >= 4:  # appliqué plates on the front modules
                plate = geo.box(0.08, length * 0.7, 1.1, bevel=0.02, segments=1)
                p.detail(plate, "skirt", at=(xo + side * 0.04, (ya + yb) / 2 - 0.2, 3.4))


# --- tracks --------------------------------------------------------------------------

def track_profile():
    pts = [(-8.9, 0.02), (8.9, 0.02)]
    ic, ir = (10.0, 1.95), 1.31
    for k in range(9):
        t = math.radians(-70 + k * 20)
        pts.append((ic[0] + ir * math.cos(t), ic[1] + ir * math.sin(t)))
    for y, z in ((7.5, 3.33), (5.0, 3.41), (2.5, 3.34), (0.0, 3.41), (-2.5, 3.34), (-5.0, 3.41), (-7.5, 3.33)):
        pts.append((y, z))
    sc, sr = (-10.25, 1.95), 1.38
    for k in range(9):
        t = math.radians(90 + k * 20)
        pts.append((sc[0] + sr * math.cos(t), sc[1] + sr * math.sin(t)))
    return pts


def track_side(a, T, side):
    name = "TrackL" if side < 0 else "TrackR"
    lo, hi = rb_box(*HIT[name])
    p = a.part(name, tex="trim", material="Metal", smooth_angle=50, hitbox=(lo, hi))
    x = side * TRACK_X
    prof = track_profile()
    band = geo.band_loop(prof, 0.16, TRACK_W)
    T.loop(band, "track", prof, width_axis=0)
    p.add(band, "trim", at=(x, 0, 0))
    face = (0, 90 * side, 0)  # template axle +Z -> outward X
    for i in range(7):
        y = -7.8 + i * 2.6
        p.add(T.template("roadwheel"), "trim", at=(x, y, 1.36), rot=face)
    p.add(T.template("sprocket"), "trim", at=(x, -10.25, 1.95), rot=face)
    p.add(T.template("roadwheel"), "trim", at=(x, 10.0, 1.95), rot=face, scale=(0.94, 0.94, 0.94))
    for y in (-5.0, 0.0, 5.0):
        p.add(T.template("roadwheel"), "trim", at=(x, y, 2.92), rot=face, scale=(0.28, 0.28, 0.5))


# --- stowage on the hull (trim, not hittable) ----------------------------------------

def hull_kit(a, T):
    k = a.part("HullKit", tex="trim", material="Metal", query=False, smooth_angle=50)
    # Engine deck louvres in their frames.
    for side in (-1, 1):
        g = geo.box(2.05, 4.1, 0.06, bevel=0.0)
        T.planar(g, "grille", u_axis=(0, 1, 0), v_axis=(1, 0, 0))
        k.add(g, "trim", at=(side * 1.75, -9.6, DECK + 0.1))
        # Exhaust louvres facing back.
        x, y, z = EXHAUSTS[0 if side < 0 else 1]
        gl = geo.box(1.2, 0.06, 0.55, bevel=0.0)
        T.planar(gl, "grille", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
        k.add(gl, "trim", at=(x, y - 0.12, z))
    # Headlights with mesh guards.
    for side in (-1, 1):
        k.add(T.template("headlight"), "trim", at=(side * 4.0, 10.72, 4.2), rot=(-6, 0, 0))
        for gx in (-0.42, 0.42):
            bar = geo.box(0.05, 0.75, 0.62, bevel=0.0)
            T.planar(bar, "mesh", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
            k.add(bar, "trim", at=(side * 4.0 + gx, 10.95, 4.2))
        top = geo.box(0.9, 0.75, 0.05, bevel=0.0)
        T.planar(top, "mesh", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
        k.add(top, "trim", at=(side * 4.0, 10.95, 4.52))
    # Driver's periscopes.
    for dx in (-0.5, 0.0, 0.5):
        k.add(T.template("periscope"), "trim", at=(-1.5 + dx, 6.38, 4.92), rot=(-13, 0, 0))
    # Spare track links on the upper glacis (two pairs).
    tilt = -math.degrees(math.atan2(4.82 - 3.45, 12.5 - 6.6))
    for x in (-2.05, 2.05):
        for j in range(2):
            y = 9.75 - j * 0.66
            z = 3.45 + (12.5 - y) / (12.5 - 6.6) * (4.82 - 3.45)
            link = hs.track_link(width=TRACK_W, pitch=0.62)
            T.planar(link, "track", u_axis=(0, 1, 0), v_axis=(1, 0, 0), fit=True)
            k.add(link, "trim", at=(x, y, z + 0.02), rot=(tilt, 0, 0))
        bar = geo.box(2.4, 0.1, 0.1, bevel=0.0)
        T.fill(bar, "plain")
        k.add(bar, "trim", at=(x, 10.3, 3.57 + 0.12), rot=(tilt, 0, 0))
    # Tools on the right fender in clamps; tow cable on the left fender.
    for piece, y in (("shovel", 4.0), ("pickaxe", -0.9)):
        k.add(T.template(piece), "trim", at=(4.75, y, DECK), rot=(0, 0, 0))
    k.add(T.template("crowbar"), "trim", at=(4.45, -2.2, DECK), rot=(0, 0, 0))
    for y in (-2.6, 0.2, 2.6, 5.2):
        clamp = geo.box(0.9, 0.12, 0.2, bevel=0.0)
        T.fill(clamp, "bolted")
        k.add(clamp, "trim", at=(4.62, y, DECK + 0.12))
    for dz, dx in ((0.1, 0.0), (0.1, 0.24)):
        c = geo.pipe_path([(-4.55 - dx, -7.6, DECK + dz), (-4.55 - dx, 5.8, DECK + dz)], 0.085, verts=6)
        T.cylindrical(c, "cable", axis=(0, 1, 0), center=(-4.55 - dx, 0, DECK + dz), along=True)
        k.add(c, "trim")
    for y in (-7.8, 6.0):
        eye = geo.torus(0.22, 0.07, verts=8, ring_verts=4)
        T.fill(eye, "cable")
        k.add(eye, "trim", at=(-4.67, y, DECK + 0.12))
    # Jerrycans on the rear shelf, spare links on the rear plate.
    for x in (-1.0, 1.0):
        k.add(T.template("jerrycan_dark"), "trim", at=(x, -13.25, 2.61), rot=(0, 0, 90))
    strap = geo.box(4.2, 0.06, 0.12, bevel=0.0)
    T.fill(strap, "bolted")
    k.add(strap, "trim", at=(0, -13.58, 3.3))


# --- turret --------------------------------------------------------------------------

TURRET_BOTTOM = [(-1.35, 4.9), (-3.95, 3.3), (-4.3, 1.4), (-4.25, -3.3), (-3.7, -6.8), (3.7, -6.8), (4.25, -3.3), (4.3, 1.4), (3.95, 3.3), (1.35, 4.9)]
TURRET_TOP = [(-1.15, 3.55), (-3.35, 2.3), (-3.85, 0.9), (-3.8, -3.2), (-3.35, -6.55), (3.35, -6.55), (3.8, -3.2), (3.85, 0.9), (3.35, 2.3), (1.15, 3.55)]
CUPOLA = (-1.95, -1.6)


def turret(a):
    lo, hi = rb_box(*HIT["TurretBody"])
    t = a.part("TurretBody", path="Turret", tex="turret", material="Metal", smooth_angle=35, hitbox=(lo, hi))
    t.add(geo.cylinder(3.3, 0.36, verts=24, bevel=0.0, caps=False), "turret_dark", at=(RING[0], RING[1], 5.13))
    shell = geo.tapered_prism(TURRET_BOTTOM, TURRET_TOP, 5.3, ROOF, bevel=0.0)
    t.add(shell, "turret")
    # Weld seams along the shell's facet joints.
    for i in (1, 2, 3):
        (bx, by), (tx, ty) = TURRET_BOTTOM[i], TURRET_TOP[i]
        for s in (-1, 1):
            t.detail(hs.weld([(s * bx, by, 5.32), (s * tx, ty, ROOF - 0.02)], r=0.045), "turret")
    for s in (-1, 1):
        t.detail(hs.weld([(s * 1.2, 4.1, ROOF - 0.01), (s * 3.45, 2.8, ROOF - 0.01), (s * 3.85, 1.2, ROOF - 0.01), (s * 3.8, -3.2, ROOF - 0.01)], r=0.045), "turret")
    # Spaced armour plates bolted off the cheek faces and the front sides.
    for s in (-1, 1):
        for i in (0,):  # front cheeks (the sides would leave the hit box)
            b0, b1 = TURRET_BOTTOM[i], TURRET_BOTTOM[i + 1]
            t0, t1 = TURRET_TOP[i], TURRET_TOP[i + 1]
            quad = [(s * b0[0], b0[1], 5.35), (s * b1[0], b1[1], 5.35), (s * t1[0], t1[1], ROOF - 0.05), (s * t0[0], t0[1], ROOF - 0.05)]
            t.add(hs.plate_on_quad(quad, offset=0.24, thickness=0.14, inset=0.07), "turret")
            mid_lo = [(Vector(quad[0]) + Vector(quad[1])) / 2, (Vector(quad[3]) + Vector(quad[2])) / 2]
            n = (Vector(quad[1]) - Vector(quad[0])).cross(Vector(quad[3]) - Vector(quad[0])).normalized()
            if n.dot(Vector((s, 1.0, 0.0))) < 0:
                n = -n
            for q in (Vector(quad[0]).lerp(Vector(quad[3]), 0.2), Vector(quad[0]).lerp(Vector(quad[3]), 0.8)):
                a_ = q.lerp(Vector(quad[1]).lerp(Vector(quad[2]), 0.2 if q.z < 6.5 else 0.8), 0.12) + n * 0.39
                b_ = q.lerp(Vector(quad[1]).lerp(Vector(quad[2]), 0.2 if q.z < 6.5 else 0.8), 0.88) + n * 0.39
                t.detail(hs.bolt_row(a_, b_, 4, n, r=0.07, h=0.05), "turret")
            del mid_lo
    # Mantlet around the gun.
    t.add(geo.tapered_box(2.5, 1.0, 1.7, top_scale=(0.85, 0.7), top_shift=(0, -0.1), bevel=0.08, segments=1), "turret_dark", at=(0, 5.08, GUN_Z))
    t.detail(hs.bolt_row((-1.0, 5.6, 5.7), (1.0, 5.6, 5.7), 5, (0, 1, 0), r=0.06, h=0.04), "turret_dark")
    # Side stowage bins.
    for s in (-1, 1):
        t.add(geo.tapered_box(0.5, 3.2, 1.15, top_scale=(0.75, 1.0), top_shift=(-s * 0.05, 0), bevel=0.05, segments=1), "turret_dark", at=(s * 4.1, -2.4, 6.5))
        t.detail(hs.bolt_row((s * 4.36, -3.8, 6.6), (s * 4.36, -1.0, 6.6), 3, (s, 0, 0), r=0.05, h=0.035), "turret_dark")
    # Commander's cupola with hatch; roof MG on a pintle.
    cx, cy = CUPOLA
    t.add(geo.cylinder(1.05, 0.5, verts=16, bevel=0.05, segments=1), "turret", at=(cx, cy, ROOF + 0.25))
    t.add(geo.cylinder(0.85, 0.14, verts=16, bevel=0.04, segments=1), "turret_dark", at=(cx, cy - 0.15, ROOF + 0.58), rot=(-8, 0, 0))
    t.add(geo.cylinder(0.08, 0.6, verts=8, bevel=0.0), "turret_dark", at=(cx + 0.75, cy + 0.6, ROOF + 0.8))
    mg = ROOF + 1.15
    t.add(geo.box(0.26, 1.2, 0.3, bevel=0.04, segments=1), "turret_dark", at=(cx + 0.75, cy + 0.9, mg))
    t.add(geo.cylinder(0.06, 1.6, verts=8, bevel=0.0), "turret_dark", at=(cx + 0.75, cy + 2.2, mg + 0.03), rot=(-90, 0, 0))
    t.add(geo.cylinder(0.1, 0.3, verts=8, bevel=0.02, segments=1), "turret_dark", at=(cx + 0.75, cy + 3.0, mg + 0.03), rot=(-90, 0, 0))
    # Gunner's sight "doghouse" (front right).
    t.add(geo.tapered_box(0.95, 1.25, 0.75, top_scale=(0.9, 0.8), top_shift=(0, -0.08), bevel=0.06, segments=1), "turret_dark", at=(2.15, 2.1, ROOF + 0.37))
    # Smoke grenade dischargers (two banks of four) on the cheeks.
    for s in (-1, 1):
        t.add(geo.box(0.9, 0.5, 0.35, bevel=0.04, segments=1), "turret_dark", at=(s * 3.45, 2.75, 7.25), rot=(0, 0, s * -30))
        for k in range(4):
            tube = geo.cylinder(0.12, 0.6, verts=8, bevel=0.0, caps=True)
            t.add(tube, "turret_dark", at=(s * (3.15 + k * 0.2), 3.0 - k * 0.12, 7.55), rot=(-55, 0, s * -30))
    # Antenna bases (whips in the kit).
    for s in (-1, 1):
        t.add(geo.cylinder(0.16, 0.3, verts=8, bevel=0.03, segments=1), "turret_dark", at=(s * 2.9, -5.6, ROOF + 0.15))
    # Rear bustle lifting eyes.
    for s in (-1, 1):
        t.add(geo.torus(0.18, 0.05, verts=8, ring_verts=4), "turret_dark", at=(s * 2.2, -6.2, ROOF + 0.15), rot=(90, 0, 0))
    # Markings: turret number both sides (chipped), red band on the bustle (material marks).
    for s in (-1, 1):
        hs.stencil(a, "217", (s * 4.12, 0.3, 6.6), (s, 0.05, 0.15), 0.85, color=RED, wear=0.25, chip=0.35, seed=11 + s)


def barrel(a):
    lo, hi = rb_box(*HIT["Barrel"])
    b = a.part("Barrel", path="Turret", tex="turret", material="Metal", smooth_angle=40, hitbox=(lo, hi))
    y0 = 5.2

    def along(bm, y):
        return b.add(bm, "barrel", at=(0, y, GUN_Z), rot=(-90, 0, 0))

    along(geo.cylinder(0.5, 0.7, verts=16, bevel=0.06, segments=1), y0 + 0.35)
    along(geo.cylinder(0.3, 11.7, verts=14, r_top=0.27, bevel=0.0), y0 + 0.7 + 5.85)
    for y in (y0 + 2.0, y0 + 3.9, y0 + 8.6, y0 + 10.4):
        along(geo.cylinder(0.345, 0.18, verts=14, bevel=0.03, segments=1), y)
    along(geo.lathe([(0.3, -0.95), (0.46, -0.65), (0.46, 0.65), (0.3, 0.95)], verts=16), y0 + 6.3)
    along(geo.lathe([(0.27, -0.25), (0.33, -0.1), (0.33, 0.25), (0.2, 0.26)], verts=14, close_top=False), MUZZLE_Y - 0.3)
    b.add(geo.box(0.22, 0.3, 0.16, bevel=0.03, segments=1), "barrel", at=(0, MUZZLE_Y - 0.55, GUN_Z + 0.4))
    for y in (y0 + 2.0, y0 + 3.9, y0 + 8.6, y0 + 10.4):
        b.detail(hs.bolt_row((0.0, y, GUN_Z + 0.36), (0.0, y, GUN_Z + 0.36), 1, (0, 0, 1), r=0.04, h=0.03), "barrel")
    a.attach("Muzzle", "Barrel", (0, MUZZLE_Y, GUN_Z), axis=(0, 1, 0))


def turret_kit(a, T):
    k = a.part("TurretKit", path="Turret", tex="trim", material="Metal", query=False, smooth_angle=50)
    # Stowage basket round the bustle: rails, mesh sides, contents.
    rails = [(-3.6, -6.7, ROOF - 0.35), (-3.6, -8.2, ROOF - 0.35), (3.6, -8.2, ROOF - 0.35), (3.6, -6.7, ROOF - 0.35)]
    for dz in (0.0, 0.55):
        r = hs.rail([(x, y, z + dz) for x, y, z in rails], r=0.05, feet=False)
        T.fill(r, "plain")
        k.add(r, "trim")
    for x in (-3.6, -1.2, 1.2, 3.6):
        post = geo.box(0.07, 0.07, 1.0, bevel=0.0)
        T.fill(post, "plain")
        k.add(post, "trim", at=(x, -8.2, ROOF - 0.55))
    side = geo.box(7.2, 0.04, 0.9, bevel=0.0)
    T.planar(side, "mesh", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
    k.add(side, "trim", at=(0, -8.2, ROOF - 0.5))
    for x in (-3.6, 3.6):
        s = geo.box(0.04, 1.45, 0.9, bevel=0.0)
        T.planar(s, "mesh", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
        k.add(s, "trim", at=(x, -7.45, ROOF - 0.5))
    floor = geo.box(7.2, 1.5, 0.05, bevel=0.0)
    T.planar(floor, "mesh", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
    k.add(floor, "trim", at=(0, -7.45, ROOF - 1.0))
    roll = hs.tarp_roll(length=3.4, r=0.36, straps=3)
    T.cylindrical(roll, "canvas", axis=(1, 0, 0), faces=lambda f: abs(f.normal.x) < 0.7, along=True)
    T.fill(roll, "canvas", faces=lambda f: abs(f.normal.x) >= 0.7)
    k.add(roll, "trim", at=(-1.6, -7.4, ROOF - 0.97))
    k.add(T.template("jerrycan_red"), "trim", at=(1.35, -7.45, ROOF - 0.97), rot=(0, 0, 90))
    k.add(T.template("jerrycan_dark"), "trim", at=(2.55, -7.45, ROOF - 0.97), rot=(0, 0, 90), scale=(0.95, 0.95, 0.95))
    k.add(T.template("ammo_can"), "trim", at=(-3.0, -7.3, ROOF - 0.35), rot=(0, 0, 90))
    bed = geo.box(3.2, 1.2, 0.5, bevel=0.15, segments=2)
    T.planar(bed, "canvas", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
    k.add(bed, "trim", at=(-1.3, -7.35, ROOF - 0.35 + 0.08))
    # Mantlet dust cover (canvas boot) round the gun root.
    boot = geo.lathe([(0.62, -0.3), (0.72, -0.05), (0.66, 0.15), (0.5, 0.35), (0.42, 0.5)], verts=12, close_top=False, close_bottom=False)
    T.cylindrical(boot, "canvas", axis=(0, 0, 1), along=True)
    k.add(boot, "trim", at=(0, 5.72, GUN_Z), rot=(-90, 0, 0))
    # Cupola periscopes and the sight window.
    cx, cy = CUPOLA
    for i in range(6):
        ang = math.radians(90 + i * 60)
        k.add(T.template("periscope"), "trim", at=(cx + 0.84 * math.cos(ang), cy + 0.84 * math.sin(ang), ROOF + 0.38),
              rot=(0, 0, math.degrees(ang) - 90), scale=(0.8, 0.8, 0.8))
    k.add(T.template("periscope"), "trim", at=(2.15, 2.72, ROOF + 0.18), scale=(1.8, 1.2, 1.5))
    k.add(T.template("ammo_can"), "trim", at=(cx + 1.12, cy + 0.9, ROOF + 0.98), rot=(0, 0, 90), scale=(0.7, 0.7, 0.7))
    # Whip antennas and hand rails.
    for s in (-1, 1):
        w = hs.whip_antenna(height=4.2, base_r=0.1)
        T.cylindrical(w, "cable", axis=(0, 0, 1), along=True)
        k.add(w, "trim", at=(s * 2.9, -5.6, ROOF + 0.3))
        r = hs.rail([(s * 4.0, -4.4, 7.5), (s * 4.08, -2.4, 7.55), (s * 4.08, 0.2, 7.52)], r=0.045)
        T.fill(r, "plain")
        k.add(r, "trim")


def build(**kw):
    a = Asset("Tank", pivot=(0, 0, 0), tex_size=1024)
    a.fix_inside_out = True
    a.texture_group("hull", 1024, high={"hp": 0.06, "cage": 0.12, "ray": 0.3}, down=0.3, back=0.6)
    a.texture_group("turret", 1024, high={"hp": 0.05, "cage": 0.12, "ray": 0.3}, down=0.3)
    T = trim.use(a, "trim", "TrimEnemy")
    a.pivot("Turret", RING)
    materials(a)
    hull(a)
    hull_kit(a, T)
    track_side(a, T, -1)
    track_side(a, T, 1)
    turret(a)
    barrel(a)
    turret_kit(a, T)
    views = [("", (1.1, 1.3, 0.6)), ("_rear", (-1.2, -1.1, 0.7)), ("_side", (1.0, 0.05, 0.12)),
             ("_close_front", (0.8, 1.2, 0.55), ["TurretBody", "Barrel"]),
             {"label": "_cam_player", "pos": (-38, 62, 30), "look": (0, 0, 4.5), "fov": 40, "res": (1280, 800)}]
    return a.finish(views=views, **kw)
