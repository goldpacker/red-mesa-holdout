"""Buggy: enemy desert raider (original design) - tubular space frame,
long-travel suspension, rear engine, light bar and a pintle machine gun.

Asset origin = ground centre. ~13 studs long. Root = chassis/body/cage;
WheelFL/FR/RL/RR centred on their axles (spin about X); sub-model Gun
(WorldPivot at the pintle, yaws) with part GunBody and attachment Muzzle;
attachment Headlight on Root (light bar, facing forward).
"""
import math

from rmh import geo, images
from rmh.asset import Asset

AXLE_Y = 4.3
TRACK_X = 3.35
TIRE_R = 1.35
TIRE_W = 1.15
FLOOR_Z = 1.55
CAGE_Z = 5.3
PINTLE = (0.0, -1.6, 5.35)


def materials(a):
    a.material("panel", base="charcoal", wear=0.55, dust=0.5, dust_up=0.35, dust_height=2.0,
               marks=[{"lo": (-3.0, 2.2, 2.55), "hi": (3.0, 3.6, 2.8), "color": "#a3161a"}])
    a.material("tube", base="gunmetal", color="#2e3134", wear=0.6, dust=0.45, dust_up=0.3)
    a.material("tire", base="rubber", color="#1e1d1b", dust=0.7, dust_up=0.5, dust_height=1.4)
    a.material("rim", base="steel_dark", dust=0.5)
    a.material("seat", kind="fabric", color="#2a2622", rough=0.85, wrinkle=0.3, dust=0.5)
    a.material("engine", base="steel", color="#4a4b4c", dust=0.4, grime=0.8)
    a.material("jerry_red", base="enemy_red", wear=0.6)
    a.material("lamp", base="lens")


def tube(p, pts, r=0.11, mat="tube"):
    p.add(geo.pipe_path(pts, r, verts=6), mat)


def wheel(a, name, x, y):
    p = a.part(name, tex="wheels", material="Rubber" if False else "Plastic", smooth_angle=45)
    side = 1 if x > 0 else -1
    w = TIRE_W
    prof = [(0.55, -w / 2), (1.05, -w / 2), (TIRE_R - 0.08, -w / 2 + 0.1), (TIRE_R, -w / 2 + 0.25), (TIRE_R, w / 2 - 0.25), (TIRE_R - 0.08, w / 2 - 0.1), (1.05, w / 2), (0.55, w / 2)]
    p.add(geo.lathe(prof, verts=18, close_top=False, close_bottom=False), "tire", at=(x, y, TIRE_R), rot=(0, 90, 0))
    for k in range(18):  # tread lugs, alternating
        ang = 2 * math.pi * (k + 0.5) / 18
        off = 0.22 if k % 2 else -0.22
        p.add(geo.box(0.55, 0.32, 0.12, bevel=0.03, segments=1), "tire",
              at=(x + off, y + (TIRE_R + 0.04) * math.cos(ang), TIRE_R + (TIRE_R + 0.04) * math.sin(ang)), rot=(math.degrees(ang) + 90, 0, 0))
    rim = [(0.0, -0.1), (0.3, -0.12), (0.6, -0.05), (0.62, 0.35)]
    p.add(geo.lathe(rim, verts=12, close_top=False), "rim", at=(x + side * 0.15, y, TIRE_R), rot=(0, side * 90, 0))
    for k in range(5):
        ang = 2 * math.pi * k / 5
        p.add(geo.cylinder(0.05, 0.1, verts=6, bevel=0.0), "rim", at=(x + side * 0.28, y + 0.28 * math.cos(ang), TIRE_R + 0.28 * math.sin(ang)), rot=(0, 90, 0))


def chassis(a):
    p = a.part("Root", tex="body", material="Metal", smooth_angle=40)
    # Floor pan, skid plate and belly.
    p.add(geo.box(4.2, 9.6, 0.25, bevel=0.06, segments=1), "panel", at=(0, 0, FLOOR_Z))
    p.add(geo.tapered_box(3.2, 2.2, 0.4, top_scale=(1.1, 1.3), bevel=0.06, segments=1), "tube", at=(0, 5.3, FLOOR_Z - 0.1), rot=(-12, 0, 0))
    # Nose: sloped hood panel, side pods and the front bull bar.
    nose = [(3.2, FLOOR_Z), (6.2, FLOOR_Z + 0.5), (6.3, FLOOR_Z + 1.2), (4.6, FLOOR_Z + 1.55), (2.2, FLOOR_Z + 1.75), (2.2, FLOOR_Z)]
    p.add(geo.side_prism(nose, 3.6, bevel=0.08, segments=1), "panel")
    for side in (-1, 1):
        p.add(geo.tapered_box(0.9, 7.0, 1.1, top_scale=(0.7, 0.95), top_shift=(-side * 0.1, 0), bevel=0.1, segments=1), "panel", at=(side * 2.3, -0.2, FLOOR_Z + 0.6))
        # Rear mud flaps hung from the engine frame.
        p.add(geo.box(1.3, 0.08, 0.9, bevel=0.02, segments=1), "tire", at=(side * (TRACK_X - 0.2), -AXLE_Y - 1.55, 1.35))
        tube(p, [(side * 1.5, -AXLE_Y - 1.1, FLOOR_Z + 0.9), (side * (TRACK_X - 0.2), -AXLE_Y - 1.55, 1.85)], 0.06)
    tube(p, [(-2.6, 6.4, 1.8), (-2.6, 6.9, 2.7), (2.6, 6.9, 2.7), (2.6, 6.4, 1.8)], 0.14)
    tube(p, [(-1.6, 6.9, 2.7), (-1.6, 6.5, 3.4), (1.6, 6.5, 3.4), (1.6, 6.9, 2.7)], 0.1)
    # Roll cage: A-pillars, roof hoop, rear hoop, diagonals, side bars.
    for side in (-1, 1):
        x = side * 2.05
        tube(p, [(x * 1.05, 3.2, FLOOR_Z + 0.2), (x * 0.95, 1.4, CAGE_Z), (x * 0.95, -1.9, CAGE_Z), (x * 1.05, -2.6, FLOOR_Z + 0.2)])
        tube(p, [(x * 1.1, 3.0, FLOOR_Z + 1.2), (x * 1.1, -2.4, FLOOR_Z + 1.2)])
        tube(p, [(x * 0.95, -1.9, CAGE_Z), (x * 0.6, -4.6, FLOOR_Z + 1.3)])
        # Suspension: A-arms and coilover shocks to each wheel.
        for y in (AXLE_Y, -AXLE_Y):
            wx = side * (TRACK_X - 0.6)
            tube(p, [(side * 1.6, y - 0.7, FLOOR_Z - 0.1), (wx, y, TIRE_R), (side * 1.6, y + 0.7, FLOOR_Z - 0.1)], 0.08)
            p.add(geo.cylinder(0.15, 1.9, verts=8, bevel=0.03, segments=1), "jerry_red", at=(side * (TRACK_X - 1.35), y - 0.35, TIRE_R + 0.75), rot=(0, side * -40, 0))
            p.add(geo.cylinder(0.07, 2.3, verts=6, bevel=0.0), "rim", at=(side * (TRACK_X - 1.35), y - 0.35, TIRE_R + 0.75), rot=(0, side * -40, 0))
            p.add(geo.cylinder(0.08, 0.9, verts=6, bevel=0.0), "rim", at=(wx, y, TIRE_R), rot=(0, 90, 0))
    tube(p, [(-1.95, 1.4, CAGE_Z), (1.95, 1.4, CAGE_Z)])
    tube(p, [(-1.95, -1.9, CAGE_Z), (1.95, -1.9, CAGE_Z)])
    tube(p, [(-1.95, 1.4, CAGE_Z), (1.95, -1.9, CAGE_Z)], 0.09)
    # Light bar with four lamps on the roof hoop.
    p.add(geo.box(3.0, 0.35, 0.4, bevel=0.06, segments=1), "tube", at=(0, 1.55, CAGE_Z + 0.35))
    for k in range(4):
        p.add(geo.cylinder(0.15, 0.08, verts=10, bevel=0.0), "lamp", at=(-1.1 + k * 0.73, 1.75, CAGE_Z + 0.35), rot=(-90, 0, 0))
    for side in (-1, 1):  # headlights in the nose
        p.add(geo.cylinder(0.24, 0.3, verts=12, bevel=0.04, segments=1), "tube", at=(side * 1.25, 6.05, FLOOR_Z + 1.15), rot=(-90, 0, 0))
        p.add(geo.cylinder(0.2, 0.05, verts=12, bevel=0.0), "lamp", at=(side * 1.25, 6.22, FLOOR_Z + 1.15), rot=(-90, 0, 0))
    # Cockpit: two bucket seats, dash, steering wheel.
    for side in (-1, 1):
        p.add(geo.box(1.2, 1.1, 0.35, bevel=0.1, segments=1), "seat", at=(side * 0.85, -0.4, FLOOR_Z + 0.6))
        p.add(geo.box(1.2, 0.3, 1.5, bevel=0.1, segments=1), "seat", at=(side * 0.85, -1.0, FLOOR_Z + 1.4), rot=(-12, 0, 0))
    p.add(geo.box(3.6, 0.6, 0.6, bevel=0.08, segments=1), "panel", at=(0, 2.1, FLOOR_Z + 1.5))
    p.add(geo.torus(0.4, 0.05, verts=12, ring_verts=4), "tube", at=(-0.85, 1.45, FLOOR_Z + 1.95), rot=(60, 0, 0))
    # Rear engine bay with exhausts, spare wheel and jerrycans.
    p.add(geo.box(3.2, 2.6, 1.6, bevel=0.1, segments=1), "engine", at=(0, -3.9, FLOOR_Z + 0.9))
    for i in range(4):
        p.add(geo.box(3.3, 0.12, 0.1, bevel=0.0), "tube", at=(0, -3.0 - i * 0.55, FLOOR_Z + 1.75))
    for side in (-1, 1):
        tube(p, [(side * 1.0, -4.6, FLOOR_Z + 1.0), (side * 1.3, -5.3, FLOOR_Z + 1.3), (side * 1.3, -5.6, FLOOR_Z + 2.6)], 0.13, "engine")
        p.add(geo.box(0.9, 0.55, 1.2, bevel=0.07, segments=1), "jerry_red", at=(side * 2.3, -3.5, FLOOR_Z + 1.4))
    p.add(geo.lathe([(0.5, -0.45), (1.1, -0.45), (1.2, -0.3), (1.2, 0.3), (1.1, 0.45), (0.5, 0.45)], verts=14, close_top=False, close_bottom=False), "tire", at=(0, -5.3, FLOOR_Z + 2.3), rot=(90, 0, 0))
    # Gun pedestal behind the seats.
    p.add(geo.cylinder(0.22, CAGE_Z - FLOOR_Z - 0.2, verts=10, bevel=0.03, segments=1), "tube", at=(0, PINTLE[1], (FLOOR_Z + CAGE_Z) / 2))
    a.decal(images.get("emblem"), (0, 4.6, FLOOR_Z + 1.62), (0, 0.15, 1), (1.3, 1.3, 0.6), color="#a8191a")
    for side in (-1, 1):
        a.decal(images.get("emblem"), (side * 2.78, -0.5, FLOOR_Z + 0.6), (side, 0, 0), (0.9, 0.9, 0.4), color="#a8191a")
    a.attach("Headlight", "Root", (0, 1.8, CAGE_Z + 0.35), axis=(0, 1, -0.12))


def gun(a):
    g = a.part("GunBody", path="Gun", tex="body", material="Metal", smooth_angle=40)
    px, py, pz = PINTLE
    g.add(geo.cylinder(0.3, 0.35, verts=10, bevel=0.04, segments=1), "tube", at=(px, py, pz))
    g.add(geo.box(0.2, 0.5, 0.7, bevel=0.03, segments=1), "tube", at=(px, py, pz + 0.45))
    gz = pz + 0.75
    g.add(geo.box(0.5, 2.0, 0.55, bevel=0.05, segments=1), "rim", at=(px, py + 0.3, gz))
    g.add(geo.tube(0.19, 0.14, 1.2, verts=10), "rim", at=(px, py + 1.9, gz), rot=(-90, 0, 0))
    g.add(geo.cylinder(0.09, 2.2, verts=8, bevel=0.0), "rim", at=(px, py + 3.0, gz), rot=(-90, 0, 0))
    g.add(geo.cylinder(0.14, 0.35, verts=8, bevel=0.02, segments=1), "rim", at=(px, py + 4.2, gz), rot=(-90, 0, 0))
    g.add(geo.box(0.45, 0.7, 0.5, bevel=0.04, segments=1), "tube", at=(px - 0.5, py + 0.4, gz - 0.1))
    for side in (-1, 1):
        g.add(geo.pipe_path([(px + side * 0.2, py - 0.7, gz - 0.2), (px + side * 0.25, py - 1.05, gz + 0.15)], 0.05, verts=5), "rim")
    # Small gun shield.
    g.add(geo.tapered_box(1.6, 0.1, 1.0, top_scale=(0.8, 1.0), bevel=0.04, segments=1), "panel", at=(px, py + 1.3, gz + 0.1), rot=(-8, 0, 0))
    a.attach("Muzzle", "GunBody", (px, py + 4.45, gz), axis=(0, 1, 0))


def build(**kw):
    a = Asset("Buggy", pivot=(0, 0, 0), tex_size=1024)
    a.texture_group("body", 1024)
    a.texture_group("wheels", 512)
    a.pivot("Gun", PINTLE)
    materials(a)
    chassis(a)
    for name, x, y in (("WheelFL", -TRACK_X, AXLE_Y), ("WheelFR", TRACK_X, AXLE_Y), ("WheelRL", -TRACK_X, -AXLE_Y), ("WheelRR", TRACK_X, -AXLE_Y)):
        wheel(a, name, x, y)
    gun(a)
    views = [("", (1.1, 1.3, 0.6)), ("_rear", (-1.2, -1.1, 0.7)), ("_side", (1.0, 0.05, 0.12))]
    return a.finish(views=views, **kw)
