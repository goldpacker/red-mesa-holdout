"""Buggy: enemy desert raider (original design) - tubular space frame,
long-travel suspension, rear engine, light bar and a pintle machine gun.

Asset origin = ground centre. ~13 studs long. Root = chassis/body/cage;
WheelFL/FR/RL/RR centred on their axles (spin about X); sub-model Gun
(WorldPivot at the pintle, yaws) with part GunBody and attachment Muzzle;
attachment Headlight on Root (light bar, facing forward).

HS-3 hard-surface pass: wedge armoured hood with louvres, angled fenders,
sloped rocker pods and bolted door plates on the roll cage (the cage stays
its silhouette), cage gussets, radiator and bull-bar skid plate, rear engine
with air filter, radiator and shielded exhausts, a rear rack with spare
wheel, red jerrycans and a tarp roll, sand ladders, shovel, ammo cans, and
a whip antenna with a red pennant. Body and gun are baked from high-poly
copies with chips, grime, a heavy dust gradient, wheel splash, exhaust
soot and chipped red markings; wheels and stowage use the shared
TrimEnemy sheet (WheelXX parts, BuggyKit). Contract parts keep their
pre-HS-3 bounding boxes (`HIT`, enforced by the build).
"""
import math

from rmh import geo, hardsurface as hs, images, trim
from rmh.asset import Asset, rb_box

# RECLAIM-HS (QA-B item 5): the uploaded maps are capped at 512² (rmh/game_maps.py);
# the bake, .blend, previews and exported full-size PNGs stay 1024². At its nearest
# play range (230 studs, gunsight zoom) the 512² maps still give >= 2.2 texels per screen
# pixel, so the GPU was already sampling mip >= 1 of the 1024² maps: no visible change.
GAME_PX = 512

HIT = {
    "Root": ((0.0, 3.375, -0.5657), (7.6, 4.95, 12.9472)),
    "WheelFL": ((-3.35, 1.35, -4.3), (1.15, 2.9, 2.9011)),
    "WheelFR": ((3.35, 1.35, -4.3), (1.15, 2.9, 2.9011)),
    "WheelRL": ((-3.35, 1.35, 4.3), (1.15, 2.9, 2.9011)),
    "WheelRR": ((3.35, 1.35, 4.3), (1.15, 2.9, 2.9011)),
    "GunBody": ((0.0, 5.9365, -0.0448), (1.5905, 1.5229, 5.4603)),
}
AXLE_Y = 4.3
TRACK_X = 3.35
TIRE_R = 1.35
FLOOR_Z = 1.55
CAGE_Z = 5.3
PINTLE = (0.0, -1.6, 5.35)
RED = "#b01c18"
CHAR = "#2a2c30"
EXHAUST_TIPS = [(side * 1.35, -5.75, FLOOR_Z + 2.45) for side in (-1, 1)]


def materials(a):
    photo = {"id": "green_metal_rust", "scale": 3.5, "color": 0.35, "sat": 0.05, "rough": 0.45, "height": 0.25}
    splash = [{"center": (x, y, TIRE_R), "radius": 1.45, "strength": 0.55} for y in (AXLE_Y, -AXLE_Y) for x in (-TRACK_X, TRACK_X)]
    soot = [{"pos": p, "dir": (0, -0.3, 1.0), "radius": 0.28, "length": 1.4, "spread": 0.4} for p in EXHAUST_TIPS]
    base = dict(kind="paint", color=CHAR, rough=0.52, wear=0.6, under="#86878a", under_metal=0.8, under_rough=0.35,
                chip_style="blotch", chip_scale=5.5, chip_bevel=0.08, ring=0.3, ring_color="#221e1a", edge_convex=True,
                polish=0.3, grime=0.6, streaks=0.4, dust=0.6, dust_up=0.28, dust_height=2.4, dust_color="#a88a6a",
                dust_caked=0.75, caked_height=2.0, caked_color="#8f7556", rough_breakup=0.3, photo=photo, fade=0.12,
                fade_color="#4a4d52", splash=splash, soot=soot, bevel=0.05)
    stripe = [{"lo": (-3.0, 2.2, 2.35), "hi": (3.0, 3.6, 2.6), "color": RED}]
    a.material("panel", **base, marks=stripe)
    a.material("tube", **dict(base, color="#2e3134", wear=0.7, chip_scale=8.0, photo=None, dust_up=0.4))
    a.material("seat", kind="fabric", color="#2a2622", rough=0.85, wrinkle=0.35, dust=0.6, dust_up=0.8, dust_color="#a88a6a")
    a.material("engine", kind="metal", color="#46474a", rough=0.5, metal=0.8, dust=0.45, grime=0.9, edge_convex=True,
               polish=0.4, soot=soot, rough_breakup=0.3)
    a.material("spring", **dict(base, color="#a81c18", photo=None, wear=0.5, dust_caked=0.5))
    a.material("steel", kind="metal", color="#3a3b3d", rough=0.45, metal=0.9, dust=0.35, grime=0.6, edge_convex=True, polish=0.6)
    a.material("gun", kind="paint", color="#26282b", rough=0.45, wear=0.5, under="#7c7d7f", under_metal=0.9, grime=0.7,
               dust=0.35, dust_up=0.6, dust_height=0.0, edge_convex=True, polish=0.45, chip_scale=9.0, rough_breakup=0.25,
               soot=[{"pos": (PINTLE[0], PINTLE[1] + 4.4, PINTLE[2] + 0.75), "dir": (0, -1, 0), "radius": 0.2, "length": 1.6, "spread": 0.05}])
    a.material("rubber_flap", kind="rubber", color="#1d1c1a", dust=0.7, dust_height=2.0)


def tube(p, pts, r=0.11, mat="tube"):
    p.add(geo.pipe_path(pts, r, verts=6), mat, texel=0.6)


def gusset(p, at, rot, size=0.35):
    tri = geo.prism([(0, 0), (size, 0), (0, size)], 0.05, bevel=0.0)
    p.add(tri, "tube", at=at, rot=rot)


def wheel(a, T, name, x, y):
    lo, hi = rb_box(*HIT[name])
    p = a.part(name, tex="trim", material="Plastic", smooth_angle=45, hitbox=(lo, hi))
    out = 1 if x > 0 else -1
    s = 1.055  # lug tips at radius 1.445 (the contract wheel size), width 1.15
    p.add(T.template("tyre_half"), "trim", at=(x, y, TIRE_R), rot=(0, 90 * out, 0), scale=(s, s, 1.0))
    p.add(T.template("tyre_half"), "trim", at=(x, y, TIRE_R), rot=(0, -90 * out, 0), scale=(s, s, 1.0))
    p.add(T.template("rim"), "trim", at=(x - out * 0.1, y, TIRE_R), rot=(0, 90 * out, 0), scale=(s, s, 1.0))


def chassis(a):
    lo, hi = rb_box(*HIT["Root"])
    p = a.part("Root", tex="body", material="Metal", smooth_angle=40, hitbox=(lo, hi))
    hidden_down = lambda f: 0.2 if f.normal.z < -0.6 else 1.0  # noqa: E731
    # Floor pan and bash plate.
    p.add(geo.box(4.0, 9.4, 0.22, bevel=0.0), "panel", at=(0, 0.3, FLOOR_Z - 0.05), texel=hidden_down)
    p.add(geo.tapered_box(3.2, 2.2, 0.35, top_scale=(1.1, 1.25), bevel=0.04, segments=1), "tube", at=(0, 5.45, FLOOR_Z - 0.06), rot=(-12, 0, 0))
    # Wedge armoured hood: side faces lean in (sloped armour).
    nose = [(2.3, FLOOR_Z - 0.05), (6.3, FLOOR_Z + 0.4), (6.45, FLOOR_Z + 1.0), (4.7, FLOOR_Z + 1.65), (2.3, FLOOR_Z + 1.9)]
    hood = geo.side_prism(nose, 3.4, bevel=0.0)
    for v in hood.verts:
        if v.co.z > FLOOR_Z + 1.0:
            v.co.x *= 0.84
    p.add(hood, "panel")
    p.detail(hs.weld([(-1.43, 4.7, FLOOR_Z + 1.65), (-1.43, 2.3, FLOOR_Z + 1.9)], r=0.035), "panel")
    p.detail(hs.weld([(1.43, 4.7, FLOOR_Z + 1.65), (1.43, 2.3, FLOOR_Z + 1.9)], r=0.035), "panel")
    for side in (-1, 1):
        p.detail(hs.bolt_row((side * 1.5, 6.1, FLOOR_Z + 1.15), (side * 1.5, 4.9, FLOOR_Z + 1.6), 3, (side * 0.3, 0.5, 0.8), r=0.05, h=0.035), "panel")
    # Angled fenders over the front wheels.
    fender = [(2.9, 2.95), (5.2, 3.1), (5.95, 2.62), (5.85, 2.5), (5.1, 2.96), (2.9, 2.83)]
    for side in (-1, 1):
        p.add(geo.side_prism(fender, 1.2, bevel=0.0), "panel", at=(side * 3.2, 0, 0))
        p.detail(hs.bolt_row((side * 2.65, 3.1, 3.05), (side * 2.65, 5.0, 3.18), 4, (0, 0, 1), r=0.045, h=0.03), "panel")
    # Sloped rocker pods and bolted door plates on the cage.
    for side in (-1, 1):
        pod = geo.tapered_box(0.9, 6.4, 1.1, top_scale=(0.62, 0.95), top_shift=(-side * 0.14, 0), bevel=0.0)
        p.add(pod, "panel", at=(side * 2.3, -0.2, FLOOR_Z + 0.6))
        p.detail(hs.bolt_row((side * 2.76, -3.0, FLOOR_Z + 0.45), (side * 2.76, 2.6, FLOOR_Z + 0.45), 7, (side, 0, 0.1), r=0.05, h=0.035), "panel")
        quad = [(side * 2.12, 2.9, FLOOR_Z + 1.15), (side * 2.12, -1.9, FLOOR_Z + 1.15), (side * 1.96, -1.7, FLOOR_Z + 2.15), (side * 1.96, 2.55, FLOOR_Z + 2.15)]
        p.add(hs.plate_on_quad(quad, offset=0.02, thickness=0.08, inset=0.0), "panel")
        p.detail(hs.bolt_row((side * 2.18, 2.6, FLOOR_Z + 2.0), (side * 2.18, -1.5, FLOOR_Z + 2.0), 5, (side, 0, 0.15), r=0.045, h=0.03), "panel")
        # Rear mud flaps.
        p.add(geo.box(1.3, 0.08, 0.9, bevel=0.0), "rubber_flap", at=(side * (TRACK_X - 0.2), -AXLE_Y - 1.52, 1.36))
        tube(p, [(side * 1.5, -AXLE_Y - 1.1, FLOOR_Z + 0.9), (side * (TRACK_X - 0.2), -AXLE_Y - 1.52, 1.85)], 0.06)
    # Bull bar.
    tube(p, [(-2.6, 6.4, 1.8), (-2.6, 6.88, 2.7), (2.6, 6.88, 2.7), (2.6, 6.4, 1.8)], 0.14)
    tube(p, [(-1.6, 6.88, 2.7), (-1.6, 6.5, 3.45), (1.6, 6.5, 3.45), (1.6, 6.88, 2.7)], 0.1)
    # Roll cage: A-pillars, roof hoop, rear hoop, diagonals, side bars, gussets.
    for side in (-1, 1):
        x = side * 2.05
        tube(p, [(x * 1.05, 3.2, FLOOR_Z + 0.2), (x * 0.95, 1.4, CAGE_Z), (x * 0.95, -1.9, CAGE_Z), (x * 1.05, -2.6, FLOOR_Z + 0.2)])
        tube(p, [(x * 1.1, 3.0, FLOOR_Z + 1.2), (x * 1.1, -2.4, FLOOR_Z + 1.2)])
        tube(p, [(x * 0.95, -1.9, CAGE_Z), (x * 0.6, -4.6, FLOOR_Z + 1.3)])
        gusset(p, (x * 0.95, 1.4, CAGE_Z - 0.02), (90, 0, 180))
        gusset(p, (x * 0.95, -1.9, CAGE_Z - 0.02), (90, 0, 0))
        # Suspension: A-arms and red coilovers to each wheel.
        for y in (AXLE_Y, -AXLE_Y):
            wx = side * (TRACK_X - 0.6)
            tube(p, [(side * 1.6, y - 0.7, FLOOR_Z - 0.1), (wx, y, TIRE_R), (side * 1.6, y + 0.7, FLOOR_Z - 0.1)], 0.08)
            p.add(geo.cylinder(0.16, 1.9, verts=8, bevel=0.0), "spring", at=(side * (TRACK_X - 1.35), y - 0.35, TIRE_R + 0.75), rot=(0, side * -40, 0))
            p.add(geo.cylinder(0.07, 2.3, verts=6, bevel=0.0), "steel", at=(side * (TRACK_X - 1.35), y - 0.35, TIRE_R + 0.75), rot=(0, side * -40, 0))
            p.add(geo.cylinder(0.09, 0.9, verts=6, bevel=0.0), "steel", at=(wx, y, TIRE_R), rot=(0, 90, 0))
    tube(p, [(-1.95, 1.4, CAGE_Z), (1.95, 1.4, CAGE_Z)])
    tube(p, [(-1.95, -1.9, CAGE_Z), (1.95, -1.9, CAGE_Z)])
    tube(p, [(-1.95, 1.4, CAGE_Z), (1.95, -1.9, CAGE_Z)], 0.09)
    # Light bar housing on the roof hoop (lamps in the kit).
    p.add(geo.tapered_box(3.0, 0.4, 0.42, top_scale=(0.96, 0.7), bevel=0.0), "tube", at=(0, 1.55, CAGE_Z + 0.33))
    # Headlight housings in the nose.
    for side in (-1, 1):
        p.add(geo.box(0.62, 0.35, 0.55, bevel=0.0), "panel", at=(side * 1.2, 5.95, FLOOR_Z + 1.15))
    # Cockpit: seats, dash, steering wheel.
    for side in (-1, 1):
        p.add(geo.box(1.2, 1.1, 0.35, bevel=0.1, segments=1), "seat", at=(side * 0.85, -0.4, FLOOR_Z + 0.6))
        p.add(geo.box(1.2, 0.3, 1.5, bevel=0.1, segments=1), "seat", at=(side * 0.85, -1.0, FLOOR_Z + 1.4), rot=(-12, 0, 0))
    p.add(geo.tapered_box(3.4, 0.6, 0.6, top_scale=(1.0, 0.6), bevel=0.0), "panel", at=(0, 2.15, FLOOR_Z + 1.5))
    p.add(geo.torus(0.4, 0.05, verts=12, ring_verts=4), "tube", at=(-0.85, 1.45, FLOOR_Z + 1.95), rot=(60, 0, 0))
    # Rear engine: block, cylinder heads, air filter, exhausts.
    p.add(geo.box(2.8, 2.3, 1.2, bevel=0.0), "engine", at=(0, -3.9, FLOOR_Z + 0.75))
    for side in (-1, 1):
        p.add(geo.tapered_box(0.9, 2.0, 0.5, top_scale=(0.8, 0.95), bevel=0.0), "engine", at=(side * 0.75, -3.9, FLOOR_Z + 1.6), rot=(0, side * 20, 0))
        p.detail(hs.bolt_row((side * 0.75, -4.7, FLOOR_Z + 1.86), (side * 0.75, -3.1, FLOOR_Z + 1.86), 4, (side * 0.34, 0, 0.94), r=0.04, h=0.03), "engine")
        tube(p, [(side * 1.0, -4.6, FLOOR_Z + 1.0), (side * 1.3, -5.3, FLOOR_Z + 1.3), (side * 1.35, -5.75, FLOOR_Z + 2.45)], 0.13, "engine")
    p.add(geo.cylinder(0.42, 0.7, verts=12, bevel=0.0), "engine", at=(0, -2.75, FLOOR_Z + 1.7), rot=(0, 90, 0))
    # Rear rack for the spare wheel and cans.
    for side in (-1, 1):
        tube(p, [(side * 1.6, -2.6, FLOOR_Z + 0.9), (side * 1.9, -5.3, FLOOR_Z + 1.0), (side * 1.9, -5.3, FLOOR_Z + 1.6)], 0.08)
    tube(p, [(-1.9, -5.3, FLOOR_Z + 1.0), (1.9, -5.3, FLOOR_Z + 1.0)], 0.08)
    tube(p, [(-0.9, -4.9, FLOOR_Z + 1.0), (-0.9, -4.9, FLOOR_Z + 3.4), (0.9, -4.9, FLOOR_Z + 3.4), (0.9, -4.9, FLOOR_Z + 1.0)], 0.07)
    for side in (-1, 1):  # jerrycan holders
        p.add(geo.box(0.72, 1.65, 0.08, bevel=0.0), "tube", at=(side * 2.45, -3.5, FLOOR_Z + 0.72))
        tube(p, [(side * 2.85, -2.75, FLOOR_Z + 0.75), (side * 2.85, -2.75, FLOOR_Z + 1.6), (side * 2.85, -4.25, FLOOR_Z + 1.6), (side * 2.85, -4.25, FLOOR_Z + 0.75)], 0.04)
    # Gun pedestal behind the seats.
    p.add(geo.cylinder(0.22, CAGE_Z - FLOOR_Z - 0.2, verts=10, bevel=0.0), "tube", at=(0, PINTLE[1], (FLOOR_Z + CAGE_Z) / 2))
    # Markings.
    a.decal(images.get("emblem"), (0, 4.6, FLOOR_Z + 1.72), (0, 0.15, 1), (1.3, 1.3, 0.6), color=RED, wear=0.35, seed=21)
    for side in (-1, 1):
        a.decal(images.get("emblem"), (side * 2.66, -0.5, FLOOR_Z + 0.6), (side, 0, 0.3), (0.9, 0.9, 0.4), color=RED, wear=0.35, seed=22 + side)
        hs.stencil(a, "43", (side * 1.62, 5.2, FLOOR_Z + 1.2), (side, 0.3, 0.35), 0.42, color="#b8b3a4", wear=0.3, chip=0.3, seed=25 + side)
    a.attach("Headlight", "Root", (0, 1.8, CAGE_Z + 0.35), axis=(0, 1, -0.12))


def buggy_kit(a, T):
    k = a.part("BuggyKit", tex="trim", material="Metal", query=False, smooth_angle=50)
    # Headlights with mesh guards; light bar lamps.
    for side in (-1, 1):
        k.add(T.template("headlight"), "trim", at=(side * 1.2, 6.08, FLOOR_Z + 1.15), scale=(0.75, 0.75, 0.75))
        g = geo.box(0.62, 0.05, 0.55, bevel=0.0)
        T.planar(g, "mesh", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
        k.add(g, "trim", at=(side * 1.2, 6.42, FLOOR_Z + 1.15))
    for i in range(4):
        k.add(T.template("headlight"), "trim", at=(-1.1 + i * 0.73, 1.72, CAGE_Z + 0.35), scale=(0.5, 0.5, 0.5))
    # Hood louvres, radiator mesh in the nose.
    lv = geo.box(1.5, 1.3, 0.04, bevel=0.0)
    T.planar(lv, "grille", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
    k.add(lv, "trim", at=(0, 3.5, FLOOR_Z + 1.83), rot=(-6, 0, 0))
    rad = geo.box(2.2, 0.05, 0.5, bevel=0.0)
    T.planar(rad, "mesh", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
    k.add(rad, "trim", at=(0, 6.43, FLOOR_Z + 0.7), rot=(-20, 0, 0))
    # Engine radiator and exhaust heat shields.
    er = geo.box(2.2, 1.4, 0.05, bevel=0.0)
    T.planar(er, "grille", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
    k.add(er, "trim", at=(0, -4.1, FLOOR_Z + 1.93))
    for side in (-1, 1):
        sh = geo.cylinder(0.2, 1.0, verts=8, bevel=0.0, caps=False)
        T.cylindrical(sh, "mesh", axis=(0, 0, 1), along=True)
        k.add(sh, "trim", at=(side * 1.35, -5.72, FLOOR_Z + 1.85))
    # Spare wheel on the rack, red jerrycans, tarp roll, ammo cans.
    # Both halves: a single open half is see-through from behind (back faces are culled).
    k.add(T.template("tyre_half"), "trim", at=(0, -5.05, FLOOR_Z + 2.45), rot=(90, 0, 0))
    k.add(T.template("tyre_half"), "trim", at=(0, -5.05, FLOOR_Z + 2.45), rot=(-90, 0, 0))
    k.add(T.template("rim"), "trim", at=(0, -5.2, FLOOR_Z + 2.45), rot=(90, 0, 0))
    for side in (-1, 1):
        k.add(T.template("jerrycan_red"), "trim", at=(side * 2.45, -3.5, FLOOR_Z + 0.76), scale=(0.9, 0.9, 0.9))
    roll = hs.tarp_roll(length=3.4, r=0.3, straps=3)
    T.cylindrical(roll, "canvas", axis=(1, 0, 0), faces=lambda f: abs(f.normal.x) < 0.7, along=True)
    T.fill(roll, "canvas", faces=lambda f: abs(f.normal.x) >= 0.7)
    k.add(roll, "trim", at=(0, -3.1, FLOOR_Z + 2.05))
    for dx in (-0.55, 0.55):
        k.add(T.template("ammo_can"), "trim", at=(dx, -2.15, FLOOR_Z + 0.2), scale=(0.9, 0.9, 0.9))
    # Sand ladders on the cage sides and a shovel.
    for side in (-1, 1):
        ld = geo.box(0.06, 3.6, 0.55, bevel=0.0)
        T.planar(ld, "grille", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
        k.add(ld, "trim", at=(side * 2.42, -0.6, FLOOR_Z + 1.95), rot=(side * -8, 0, 0))
        for y in (-1.8, 0.6):
            st = geo.box(0.1, 0.12, 0.75, bevel=0.0)
            T.fill(st, "bolted")
            k.add(st, "trim", at=(side * 2.47, y, FLOOR_Z + 1.95))
    k.add(T.template("shovel"), "trim", at=(-2.35, 1.2, FLOOR_Z + 1.2), rot=(0, -80, 0), scale=(0.85, 0.85, 0.85))
    # Whip antenna with a red pennant.
    w = hs.whip_antenna(height=5.5, base_r=0.09)
    T.cylindrical(w, "cable", axis=(0, 0, 1), along=True)
    k.add(w, "trim", at=(1.75, -5.0, FLOOR_Z + 1.9))
    flag = geo.prism([(0, 0), (0.0, 0.5), (1.1, 0.25)], 0.02, bevel=0.0)
    T.planar(flag, "red", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
    k.add(flag, "trim", at=(1.77, -5.0, FLOOR_Z + 1.9 + 5.4), rot=(90, 0, 200))
    # Wire-mesh sunroof over the rear of the cage.
    roof = geo.box(3.6, 2.6, 0.04, bevel=0.0)
    T.planar(roof, "mesh", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
    k.add(roof, "trim", at=(0, -0.25, CAGE_Z + 0.08))


def gun(a):
    lo, hi = rb_box(*HIT["GunBody"])
    g = a.part("GunBody", path="Gun", tex="body", material="Metal", smooth_angle=40, hitbox=(lo, hi))
    px, py, pz = PINTLE
    g.add(geo.cylinder(0.3, 0.3, verts=10, bevel=0.0), "gun", at=(px, py, pz - 0.02))
    g.add(geo.box(0.2, 0.5, 0.7, bevel=0.0), "gun", at=(px, py, pz + 0.43))
    gz = pz + 0.75
    g.add(geo.box(0.5, 2.0, 0.52, bevel=0.0), "gun", at=(px, py + 0.3, gz))
    g.add(geo.box(0.44, 1.2, 0.1, bevel=0.0), "gun", at=(px, py + 0.2, gz + 0.3))
    g.detail(hs.bolt_row((px + 0.25, py - 0.4, gz + 0.1), (px + 0.25, py + 1.0, gz + 0.1), 4, (1, 0, 0), r=0.03, h=0.02), "gun")
    # Perforated barrel jacket, barrel, flash hider.
    g.add(geo.cylinder(0.19, 1.3, verts=10, bevel=0.0), "gun", at=(px, py + 1.95, gz), rot=(-90, 0, 0))
    for k in range(6):
        for j in range(3):
            ang = math.radians(90 + j * 60 + (30 if k % 2 else 0))
            ring = geo.torus(0.045, 0.012, verts=8, ring_verts=3)
            hs._place(ring, (px + 0.19 * math.cos(ang), py + 1.45 + k * 0.2, gz + 0.19 * math.sin(ang)), (math.cos(ang), 0, math.sin(ang)))
            g.detail(ring, "gun")
    g.add(geo.cylinder(0.09, 2.1, verts=8, bevel=0.0), "gun", at=(px, py + 3.2, gz), rot=(-90, 0, 0))
    g.add(geo.cylinder(0.14, 0.32, verts=8, bevel=0.0), "gun", at=(px, py + 4.2, gz), rot=(-90, 0, 0))
    # Ammo can on the left, feed chute, spade grips, rear sight.
    g.add(geo.box(0.42, 0.75, 0.52, bevel=0.0), "gun", at=(px - 0.5, py + 0.4, gz - 0.1))
    g.add(geo.box(0.2, 0.3, 0.2, bevel=0.0), "gun", at=(px - 0.28, py + 0.45, gz + 0.1))
    for side in (-1, 1):
        g.add(geo.pipe_path([(px + side * 0.2, py - 0.7, gz - 0.2), (px + side * 0.25, py - 1.05, gz + 0.15)], 0.05, verts=5), "gun")
    g.add(geo.box(0.06, 0.1, 0.22, bevel=0.0), "gun", at=(px, py - 0.4, gz + 0.4))
    # Small angled gun shield, bolted.
    g.add(geo.tapered_box(1.55, 0.1, 0.96, top_scale=(0.8, 1.0), bevel=0.0), "gun", at=(px, py + 1.3, gz + 0.1), rot=(-8, 0, 0))
    g.detail(hs.bolt_row((px - 0.6, py + 1.36, gz - 0.3), (px + 0.6, py + 1.36, gz - 0.3), 4, (0, 1, 0), r=0.04, h=0.03), "gun")
    a.attach("Muzzle", "GunBody", (px, py + 4.45, gz), axis=(0, 1, 0))


def build(**kw):
    a = Asset("Buggy", pivot=(0, 0, 0), tex_size=1024)
    a.game_px = GAME_PX
    a.fix_inside_out = True
    a.texture_group("body", 1024, high={"hp": 0.04, "cage": 0.1, "ray": 0.25}, down=0.3, metal_px=512)
    T = trim.use(a, "trim", "TrimEnemy")
    a.pivot("Gun", PINTLE)
    materials(a)
    chassis(a)
    buggy_kit(a, T)
    for name, x, y in (("WheelFL", -TRACK_X, AXLE_Y), ("WheelFR", TRACK_X, AXLE_Y), ("WheelRL", -TRACK_X, -AXLE_Y), ("WheelRR", TRACK_X, -AXLE_Y)):
        wheel(a, T, name, x, y)
    gun(a)
    views = [("", (1.1, 1.3, 0.6)), ("_rear", (-1.2, -1.1, 0.7)), ("_side", (1.0, 0.05, 0.12)),
             {"label": "_cam_player", "pos": (-20, 34, 16), "look": (0, 0, 2.5), "fov": 40, "res": (1280, 800)}]
    return a.finish(views=views, **kw)
