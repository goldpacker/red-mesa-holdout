"""SiegeCrawler: the enemy land fortress (boss). Twin giant track units,
armoured hull with a ram plow, command tower, exhaust stacks, a central
heavy cannon and two twin-autocannon sponson turrets. Dark gunmetal /
charcoal with red markings, hazard stripes and large emblems.

Asset origin = ground centre. ~96 studs long with the gun.
Parts / models (docs/ASSET_CONTRACTS.md):
  Root (hull), TrackL, TrackR, Deck (superstructure, tower, stacks)
  TurretLeft / TurretRight  (Models, WorldPivot at their rings, attachment Muzzle)
  MainCannon (Model, WorldPivot at its ring; parts CannonTurret, CannonBarrel,
              CannonGlow (Neon sphere at the muzzle, starts transparent); attachment Muzzle)
  Core (Neon reactor, hidden under) CoreArmor (armoured dome that is blown off)
  Beacons (Neon red warning lights)
"""
import math

from rmh import geo, images
from rmh.asset import Asset

TRACK_X = 15.5
TRACK_W = 9.0
DECK_Z = 19.0
MAIN_RING = (0.0, 12.0, DECK_Z)
SIDE_RING = (15.2, 20.0, 16.4)
CORE = (0.0, -21.0, 27.2)
GLOW_RED = (1.0, 0.33, 0.12)


def materials(a):
    a.material("hull", base="gunmetal", wear=0.5, dust=0.35, dust_up=0.25, dust_height=6.0, grime=0.7, panels=(6.0, 5.0, 4.0), panel_width=0.12)
    a.material("hull_dark", base="charcoal", wear=0.45, dust=0.3, dust_up=0.2, dust_height=6.0, grime=0.7)
    a.material("red", base="enemy_red", wear=0.6, dust=0.3, dust_up=0.2)
    a.material("track", base="steel_dark", rough=0.6, dust=0.5, dust_up=0.4, dust_height=4.0, grime=0.8)
    a.material("wheel", base="charcoal", wear=0.5, dust=0.5, dust_height=8.0)
    a.material("glass", base="glass", color="#221a12", metal=0.5)
    a.material("rust", base="steel", color="#5a4a3e", rough=0.6, grime=0.9, dust=0.3)
    a.material("rail", base="steel_dark", dust=0.2)


def track_unit(a, side):
    p = a.part("TrackL" if side < 0 else "TrackR", tex="tracks", material="Metal", smooth_angle=45)
    x = side * TRACK_X
    ys, ye, zb, zt = -41.0, 38.0, 0.0, 12.0
    r = (zt - zb) / 2
    loop = []
    for k in range(11):
        ang = math.pi / 2 + math.pi * k / 10
        loop.append((ys + r + r * math.cos(ang), zb + r + r * math.sin(ang)))
    for k in range(11):
        ang = -math.pi / 2 + math.pi * k / 10
        loop.append((ye - r + r * math.cos(ang), zb + r + r * math.sin(ang)))
    p.add(geo.side_prism(loop, TRACK_W, bevel=0.2, segments=1), "track", at=(x, 0, 0))
    for i in range(46):
        y = ys + r * 0.6 + i * (ye - ys - r * 1.2) / 45
        p.add(geo.box(TRACK_W + 0.3, 0.8, 0.5, bevel=0.0), "track", at=(x, y, 0.1))
    for i in range(38):
        y = ys + r + i * (ye - ys - 2 * r) / 37
        p.add(geo.box(TRACK_W + 0.3, 0.8, 0.45, bevel=0.0), "track", at=(x, y, zt - 0.1))
    for i in range(8):
        y = -31.0 + i * 8.8
        p.add(geo.lathe([(0.0, -3.2), (2.2, -3.2), (3.4, -2.9), (3.6, -2.5), (3.6, 2.5), (3.4, 2.9), (2.2, 3.2), (0.0, 3.2)], verts=16), "wheel", at=(x, y, 3.8), rot=(0, 90, 0))
        p.add(geo.cylinder(1.0, TRACK_W + 0.6, verts=10, bevel=0.1, segments=1), "hull_dark", at=(x, y, 3.8), rot=(0, 90, 0))
    for y, teeth in ((ys + r, 14), (ye - r, 0)):
        p.add(geo.lathe([(0.0, -4.0), (4.6, -4.0), (5.0, -3.6), (5.0, 3.6), (4.6, 4.0), (0.0, 4.0)], verts=18), "hull_dark", at=(x, y, r), rot=(0, 90, 0))
        for t in range(teeth):
            ang = 2 * math.pi * t / teeth
            p.add(geo.box(TRACK_W - 1.0, 1.0, 1.2, bevel=0.0), "hull_dark", at=(x, y + 5.3 * math.cos(ang), r + 5.3 * math.sin(ang)), rot=(math.degrees(ang), 0, 0))


def hull(a):
    p = a.part("Root", tex="hull", material="Metal", smooth_angle=35)
    prof = [(-44.0, 5.0), (38.0, 5.0), (45.0, 10.5), (43.5, 15.0), (32.0, DECK_Z), (-38.0, DECK_Z), (-45.0, 15.0)]
    p.add(geo.side_prism(prof, 21.0, bevel=0.35, segments=1), "hull")
    # Sponsons over the tracks and segmented side skirts.
    for side in (-1, 1):
        p.add(geo.box(10.5, 80.0, 1.2, bevel=0.2, segments=1), "hull", at=(side * TRACK_X, -1.5, 13.0))
        p.add(geo.tapered_box(9.5, 30.0, 3.4, top_scale=(0.85, 0.9), bevel=0.25, segments=1), "hull", at=(side * TRACK_X, 12.0, 15.2))
        for i in range(9):
            y = -38.0 + i * 8.9
            p.add(geo.box(0.9, 8.6, 7.8, bevel=0.2, segments=1), "hull", at=(side * (TRACK_X + TRACK_W / 2 + 0.7), y, 8.4))
            for bz in (5.2, 11.6):
                for by in (-3.4, 0.0, 3.4):
                    p.add(geo.cylinder(0.22, 0.2, verts=6, bevel=0.0), "hull_dark", at=(side * (TRACK_X + TRACK_W / 2 + 1.2), y + by, bz), rot=(0, 90, 0))
        a.decal(images.get("emblem"), (side * (TRACK_X + TRACK_W / 2 + 1.15), -8.0, 8.6), (side, 0, 0), (7.5, 7.5, 1.4), color="#b01c1c")
    # Ram plow on the nose with push arms.
    plow = [(-22.0, 0.0), (22.0, 0.0), (20.0, 1.6), (-20.0, 1.6)]
    p.add(geo.prism(plow, 8.0, bevel=0.3, segments=1), "hull_dark", at=(0, 42.8, 5.2), rot=(-35, 0, 0))
    for side in (-1, 1):
        p.add(geo.box(1.8, 7.0, 1.8, bevel=0.2, segments=1), "rust", at=(side * 8.0, 39.6, 6.2), rot=(12, 0, 0))
        p.add(geo.cylinder(1.0, 2.4, verts=10, bevel=0.1, segments=1), "hull_dark", at=(side * 8.0, 36.8, 6.9), rot=(0, 90, 0))
    a.decal(images.get("stripes", count=8, angle=45), (0, 44.6, 6.0), (0, 0.6, 0.8), (36.0, 6.0, 3.0), color="#c9a227")
    # Add-on armour blocks on the glacis and along the upper hull sides.
    for row in range(2):
        for i in range(8):
            x = -8.75 + i * 2.5
            y = 36.5 + row * 2.9
            z = 17.4 - row * 2.6
            p.add(geo.box(2.2, 2.4, 0.9, bevel=0.12, segments=1), "hull_dark", at=(x, y, z), rot=(-42, 0, 0))
    for side in (-1, 1):
        for i in range(10):
            p.add(geo.box(0.8, 5.6, 2.8, bevel=0.12, segments=1), "hull_dark", at=(side * 10.8, -34.0 + i * 6.8, 16.6))
    # Engine grilles and hatches on the rear deck.
    for i in range(10):
        p.add(geo.box(12.0, 0.4, 0.3, bevel=0.0), "hull_dark", at=(0, -43.0 + i * 1.0 + 0.0, DECK_Z - 0.1 + 0.25))
    for x, y in ((-5.0, 26.0), (5.0, 26.0)):
        p.add(geo.cylinder(1.6, 0.5, verts=14, bevel=0.1, segments=1), "hull", at=(x, y, DECK_Z + 0.25))
    # Front lights and a big emblem on the glacis.
    for side in (-1, 1):
        p.add(geo.cylinder(0.9, 0.8, verts=12, bevel=0.1, segments=1), "hull_dark", at=(side * 7.0, 44.4, 12.2), rot=(-60, 0, 0))


def deck(a):
    p = a.part("Deck", tex="deck", material="Metal", smooth_angle=35)
    # Raised superstructure behind the main turret.
    p.add(geo.tapered_box(20.0, 34.0, 5.5, top_scale=(0.9, 0.95), bevel=0.3, segments=1), "hull", at=(0, -17.0, DECK_Z + 2.75))
    # Command tower with a window band and a mast.
    p.add(geo.tapered_box(9.0, 8.0, 9.0, top_scale=(0.85, 0.85), bevel=0.3, segments=1), "hull", at=(-6.0, -30.0, DECK_Z + 10.0))
    p.add(geo.box(9.2, 7.0, 1.1, bevel=0.1, segments=1), "glass", at=(-6.0, -29.6, DECK_Z + 12.2))
    p.add(geo.box(10.0, 9.0, 0.6, bevel=0.1, segments=1), "hull_dark", at=(-6.0, -30.0, DECK_Z + 14.8))
    p.add(geo.cylinder(0.25, 12.0, verts=6, bevel=0.0), "rail", at=(-8.0, -32.0, DECK_Z + 21.0))
    p.add(geo.box(3.0, 0.2, 0.2, bevel=0.0), "rail", at=(-8.0, -32.0, DECK_Z + 24.0))
    # Exhaust stacks.
    for i, (x, y) in enumerate(((6.5, -33.0), (9.5, -33.0), (6.5, -29.5), (9.5, -29.5))):
        p.add(geo.tube(1.2, 0.85, 9.0, verts=12), "rust", at=(x, y, DECK_Z + 9.5))
        p.add(geo.cylinder(1.4, 0.5, verts=12, bevel=0.1, segments=1), "hull_dark", at=(x, y, DECK_Z + 6.0))
    # Core cradle ring on the rear deck (the Core sits inside).
    p.add(geo.lathe([(4.2, -1.0), (6.4, -1.0), (6.6, 0.0), (6.0, 1.4), (4.6, 1.4), (4.2, 0.6)], verts=24), "hull_dark", at=(CORE[0], CORE[1], DECK_Z + 6.4))
    # Catwalk railings along the deck edges and ladders.
    for side in (-1, 1):
        x = side * 10.2
        posts = [(x, y, DECK_Z) for y in range(-36, 31, 6)]
        for px, py, pz in posts:
            p.add(geo.cylinder(0.12, 2.2, verts=5, bevel=0.0), "rail", at=(px, py, pz + 1.1))
        p.add(geo.pipe_path([(x, -36.0, DECK_Z + 2.2), (x, 30.0, DECK_Z + 2.2)], 0.12, verts=5), "rail")
        p.add(geo.pipe_path([(x, -36.0, DECK_Z + 1.2), (x, 30.0, DECK_Z + 1.2)], 0.09, verts=5), "rail")
    # Spotlights and antenna masts on the tower roof.
    for side in (-1, 1):
        p.add(geo.cylinder(0.8, 1.2, verts=12, bevel=0.1, segments=1), "hull_dark", at=(-6.0 + side * 3.2, -26.4, DECK_Z + 15.5), rot=(-80, 0, 0))


def main_cannon(a):
    t = a.part("CannonTurret", path="MainCannon", tex="turrets", material="Metal", smooth_angle=35)
    rx, ry, rz = MAIN_RING
    t.add(geo.cylinder(7.0, 1.2, verts=24, bevel=0.2, segments=1), "hull_dark", at=(rx, ry, rz + 0.6))
    pts = [(-7.5, -8.0), (7.5, -8.0), (8.5, -2.0), (7.0, 5.0), (3.2, 8.5), (-3.2, 8.5), (-7.0, 5.0), (-8.5, -2.0)]
    shell = geo.prism(pts, 5.0, bevel=0.0)
    for v in shell.verts:
        if v.co.z > 0:
            v.co.x *= 0.85
            v.co.y = v.co.y * 0.88 - 0.4
    geo._bevel(shell, 0.3, 1)
    t.add(shell, "hull", at=(rx, ry, rz + 3.7))
    t.add(geo.tapered_box(6.0, 3.0, 4.2, top_scale=(0.9, 0.8), bevel=0.3, segments=1), "hull_dark", at=(rx, ry + 9.2, rz + 3.6))
    t.add(geo.cylinder(1.6, 1.6, verts=12, bevel=0.15, segments=1), "hull", at=(rx - 3.6, ry - 3.0, rz + 7.0))
    for side in (-1, 1):
        t.add(geo.box(0.6, 12.0, 2.4, bevel=0.1, segments=1), "red", at=(rx + side * 7.6, ry - 1.0, rz + 3.8), rot=(0, 0, side * -8))
    b = a.part("CannonBarrel", path="MainCannon", tex="turrets", material="Metal", smooth_angle=40)
    gz = rz + 3.6
    y0 = ry + 10.5
    b.add(geo.cylinder(1.5, 28.0, verts=16, r_top=1.2, bevel=0.0), "hull", at=(rx, y0 + 14.0, gz), rot=(-90, 0, 0))
    for yy, rr in ((y0 + 5.0, 1.9), (y0 + 11.0, 2.2), (y0 + 17.0, 1.7)):
        b.add(geo.lathe([(1.3, -1.4), (rr, -0.9), (rr, 0.9), (1.3, 1.4)], verts=16), "hull_dark", at=(rx, yy, gz), rot=(-90, 0, 0))
    b.add(geo.tube(2.0, 1.0, 2.6, verts=16), "hull_dark", at=(rx, y0 + 28.6, gz), rot=(-90, 0, 0))
    for side in (-1, 1):
        b.add(geo.box(0.5, 1.6, 1.2, bevel=0.05, segments=1), "hull_dark", at=(rx + side * 2.0, y0 + 28.6, gz))
    g = a.part("CannonGlow", path="MainCannon", neon=GLOW_RED, transparency=1, query=False, shadow=False, material="Neon")
    g.add(geo.icosphere(1.0, 2), "hull", at=(rx, y0 + 30.3, gz))
    a.attach("Muzzle", "CannonBarrel", (rx, y0 + 30.0, gz), axis=(0, 1, 0))


def side_turret(a, side):
    name = "TurretLeft" if side < 0 else "TurretRight"
    x, y, z = side * SIDE_RING[0], SIDE_RING[1], SIDE_RING[2] + 0.6
    t = a.part(name + "Body", path=name, tex="turrets", material="Metal", smooth_angle=40)
    t.add(geo.cylinder(3.6, 0.8, verts=20, bevel=0.15, segments=1), "hull_dark", at=(x, y, z + 0.4))
    t.add(geo.lathe([(3.4, 0.0), (3.4, 1.4), (2.8, 2.6), (1.6, 3.2), (0.0, 3.3)], verts=20), "hull", at=(x, y, z + 0.8))
    t.add(geo.box(3.2, 2.4, 2.2, bevel=0.2, segments=1), "hull_dark", at=(x, y + 3.0, z + 2.0))
    for dx in (-0.8, 0.8):
        t.add(geo.cylinder(0.45, 9.0, verts=10, bevel=0.0), "hull", at=(x + dx, y + 8.2, z + 2.0), rot=(-90, 0, 0))
        t.add(geo.tube(0.6, 0.3, 1.2, verts=10), "hull_dark", at=(x + dx, y + 12.4, z + 2.0), rot=(-90, 0, 0))
    t.add(geo.box(1.4, 2.2, 1.6, bevel=0.1, segments=1), "red", at=(x - side * 2.4, y - 1.0, z + 2.0))
    a.attach("Muzzle", name + "Body", (x, y + 13.2, z + 2.0), axis=(0, 1, 0))


def core(a):
    cx, cy, cz = CORE
    c = a.part("Core", neon=GLOW_RED, material="Neon", query=True)
    c.add(geo.icosphere(3.4, 2), "hull", at=(cx, cy, cz))
    arm = a.part("CoreArmor", tex="armor", material="Metal", query=True, smooth_angle=35)
    dome = geo.lathe([(6.2, -0.4), (6.2, 0.6), (5.6, 3.0), (4.0, 5.0), (1.8, 6.0), (0.0, 6.2)], verts=24)
    arm.add(dome, "hull", at=(cx, cy, cz - 2.0))
    for k in range(8):
        ang = 2 * math.pi * k / 8
        arm.add(geo.box(0.8, 2.6, 5.0, bevel=0.15, segments=1), "hull_dark", at=(cx + 5.6 * math.cos(ang), cy + 5.6 * math.sin(ang), cz + 0.4), rot=(0, 0, math.degrees(ang) + 90))
    arm.add(geo.cylinder(1.4, 0.8, verts=12, bevel=0.1, segments=1), "red", at=(cx, cy, cz + 4.4))
    a.decal(images.get("stripes", count=10, angle=45), (cx, cy + 5.8, cz), (0, 1, 0.2), (8.0, 2.5, 3.0), color="#c9a227")
    beacons = a.part("Beacons", neon=(1.0, 0.1, 0.08), material="Neon", query=False, shadow=False)
    for x, y, z in ((-6.0, -26.0, DECK_Z + 15.3), (-8.0, -32.0, DECK_Z + 27.2), (10.2, 30.0, DECK_Z + 2.6), (-10.2, 30.0, DECK_Z + 2.6), (10.2, -36.0, DECK_Z + 2.6), (-10.2, -36.0, DECK_Z + 2.6)):
        beacons.add(geo.sphere(0.45, 8, 5), "hull", at=(x, y, z))


def build(**kw):
    a = Asset("SiegeCrawler", pivot=(0, 0, 0), tex_size=1024)
    for g in ("hull", "tracks", "deck", "turrets", "armor"):
        a.texture_group(g, 1024 if g != "armor" else 512)
    a.pivot("MainCannon", MAIN_RING)
    a.pivot("TurretLeft", (-SIDE_RING[0], SIDE_RING[1], SIDE_RING[2]))
    a.pivot("TurretRight", SIDE_RING)
    materials(a)
    hull(a)
    track_unit(a, -1)
    track_unit(a, 1)
    deck(a)
    main_cannon(a)
    side_turret(a, -1)
    side_turret(a, 1)
    core(a)
    views = [("", (1.1, 1.3, 0.6)), ("_rear", (-1.2, -1.1, 0.7)), ("_side", (1.0, 0.05, 0.15))]
    return a.finish(views=views, **kw)
