"""Tank: enemy main battle tank (original design). Dark gunmetal with red
markings, the enemy emblem and turret numbers.

Asset origin = ground centre under the hull. ~25 studs hull (7 m), gun
overhang to ~34 studs. Root = hull; TrackL / TrackR = tracks with road
wheels, sprockets, idlers; sub-model Turret (WorldPivot = turret ring
centre) with parts TurretBody and Barrel; attachment Barrel.Muzzle.
"""
import math

import bmesh

from rmh import geo, images
from rmh.asset import Asset

HULL_W = 7.0
TRACK_X = 4.35
TRACK_W = 2.2
WHEEL_R = 1.2
DECK_Z = 5.0
RING = (0.0, 0.6, DECK_Z)
GUN_Z = 6.35
GUN_Y0 = 5.4
GUN_LEN = 12.2


def materials(a):
    a.material("hull", base="gunmetal", wear=0.45, dust=0.45, dust_up=0.3, dust_height=2.2, grime=0.6)
    a.material("hull_dark", base="charcoal", wear=0.4, dust=0.4, dust_up=0.3, dust_height=2.2)
    a.material("red", base="enemy_red", wear=0.55, dust=0.3, dust_up=0.3)
    a.material("track", base="steel_dark", rough=0.6, dust=0.55, dust_up=0.4, dust_height=1.5, grime=0.7)
    a.material("wheel_rubber", base="rubber", dust=0.5, dust_up=0.3, dust_height=2.0)
    a.material("lamp", base="lens")
    a.material("drum", base="olive_dark", color="#3a3a33", wear=0.6)


def turret_shell():
    pts = [(-3.9, -4.4), (3.9, -4.4), (4.45, -1.2), (4.25, 2.2), (1.7, 4.9), (-1.7, 4.9), (-4.25, 2.2), (-4.45, -1.2)]
    bm = geo.prism(pts, 2.3, bevel=0.0)
    for v in bm.verts:
        if v.co.z > 0:
            v.co.x *= 0.88
            v.co.y = v.co.y * 0.9 - 0.15
    geo._bevel(bm, 0.12, 1)
    return bm


def wheel(r, w, verts=14):
    prof = [(0.0, -w / 2), (r * 0.4, -w / 2), (r * 0.85, -w / 2 + 0.06), (r, -w / 2 + 0.14), (r, w / 2 - 0.14), (r * 0.85, w / 2 - 0.06), (r * 0.4, w / 2), (0.0, w / 2)]
    return geo.lathe(prof, verts=verts, close_top=False, close_bottom=False)


def track_side(a, side):
    name = "TrackL" if side < 0 else "TrackR"
    p = a.part(name, tex="gear", material="Metal", smooth_angle=50)
    x = side * TRACK_X
    # Track loop: stadium profile in (y, z), extruded along X.
    ys, ye, zb, zt = -11.2, 11.0, 0.0, 3.4
    r = (zt - zb) / 2
    loop = []
    for k in range(9):
        ang = math.pi / 2 + math.pi * k / 8
        loop.append((ys + r * 0.8 + r * 0.8 * math.cos(ang), zb + r + r * math.sin(ang)))
    for k in range(9):
        ang = -math.pi / 2 + math.pi * k / 8
        loop.append((ye - r * 0.8 + r * 0.8 * math.cos(ang), zb + r + r * math.sin(ang)))
    inner = [(y * 0.97, (z - r) * 0.8 + r) for y, z in loop]
    outer_bm = geo.side_prism(loop, TRACK_W, bevel=0.05, segments=1)
    p.add(outer_bm, "track", at=(x, 0, 0))
    del inner
    # Grousers along the ground run and the top run.
    for i in range(40):
        y = ys + 1.2 + i * (ye - ys - 2.4) / 39
        p.add(geo.box(TRACK_W + 0.08, 0.22, 0.14, bevel=0.0), "track", at=(x, y, 0.02))
    for i in range(30):
        y = ys + 2.0 + i * (ye - ys - 4.0) / 29
        p.add(geo.box(TRACK_W + 0.08, 0.22, 0.12, bevel=0.0), "track", at=(x, y, zt - 0.02))
    # Road wheels (paired), sprocket at the rear, idler at the front.
    for i in range(7):
        y = -8.6 + i * 2.85
        for off in (-0.55, 0.55):
            p.add(wheel(WHEEL_R, 0.5, verts=12), "wheel_rubber", at=(x + off, y, WHEEL_R + 0.18), rot=(0, 90, 0))
        p.add(geo.cylinder(0.3, 1.7, verts=8, bevel=0.03, segments=1), "hull_dark", at=(x, y, WHEEL_R + 0.18), rot=(0, 90, 0))
    for y, rr, teeth in ((-10.4, 1.25, 11), (10.2, 1.15, 0)):
        p.add(wheel(rr, 1.5, verts=16), "hull_dark", at=(x, y, 1.75), rot=(0, 90, 0))
        for t in range(teeth):
            ang = 2 * math.pi * t / teeth
            p.add(geo.box(1.6, 0.3, 0.35, bevel=0.0), "hull_dark", at=(x, y + (rr + 0.1) * math.cos(ang), 1.75 + (rr + 0.1) * math.sin(ang)), rot=(math.degrees(ang), 0, 0))
    for y in (-4.5, 0.5, 5.5):
        p.add(geo.cylinder(0.38, 1.0, verts=10, bevel=0.03, segments=1), "hull_dark", at=(x, y, zt - 0.35), rot=(0, 90, 0))


def hull(a):
    p = a.part("Root", tex="hull", material="Metal", smooth_angle=35)
    prof = [(-12.2, 1.5), (11.0, 1.5), (12.6, 3.0), (12.45, 3.45), (7.2, 4.85), (-11.7, 5.0), (-12.5, 4.4), (-12.5, 1.9)]
    p.add(geo.side_prism(prof, HULL_W, bevel=0.1, segments=1), "hull")
    # Fenders over the tracks and armoured side skirts in panels.
    for side in (-1, 1):
        p.add(geo.box(2.1, 24.2, 0.18, bevel=0.04, segments=1), "hull", at=(side * TRACK_X, 0.3, 4.3))
        for i in range(6):
            y = -10.1 + i * 3.95
            p.add(geo.tapered_box(0.3, 3.85, 2.3, top_scale=(1.0, 1.0), bevel=0.06, segments=1), "hull", at=(side * 5.55, y, 3.15))
            for bz in (2.3, 4.0):
                for by in (-1.5, 1.5):
                    p.add(geo.cylinder(0.08, 0.08, verts=6, bevel=0.0), "hull_dark", at=(side * 5.72, y + by, bz), rot=(0, 90, 0))
        # Stowage bins and a tow cable coil on the fenders.
        p.add(geo.box(1.7, 3.4, 0.9, bevel=0.08, segments=1), "hull_dark", at=(side * 4.35, -6.5, 4.85))
        p.add(geo.box(1.7, 2.6, 0.7, bevel=0.08, segments=1), "hull_dark", at=(side * 4.35, 7.6, 4.75))
        p.add(geo.torus(0.6, 0.08, verts=12, ring_verts=4), "track", at=(side * 4.35, -2.2, 4.48))
        # Headlight clusters with guards at the front corners.
        p.add(geo.box(0.6, 0.45, 0.45, bevel=0.06, segments=1), "hull_dark", at=(side * 2.8, 11.6, 3.75))
        p.add(geo.cylinder(0.17, 0.08, verts=10, bevel=0.0), "lamp", at=(side * 2.8, 11.85, 3.78), rot=(-90, 0, 0))
        p.add(geo.pipe_path([(side * 2.35, 11.4, 3.5), (side * 2.35, 12.05, 3.8), (side * 3.25, 12.05, 3.8), (side * 3.25, 11.4, 3.5)], 0.04, verts=5), "hull_dark")
        # Exhausts at the rear.
        p.add(geo.box(1.2, 0.35, 0.7, bevel=0.06, segments=1), "hull_dark", at=(side * 2.2, -12.55, 3.7))
        # Tow hooks.
        p.add(geo.torus(0.25, 0.07, verts=10, ring_verts=4), "hull_dark", at=(side * 2.0, 12.2, 2.3), rot=(0, 90, 0))
    # Engine deck grilles, driver hatch and periscopes.
    for i in range(7):
        p.add(geo.box(5.0, 0.18, 0.1, bevel=0.0), "hull_dark", at=(0, -10.8 + i * 0.55, 5.05))
    p.add(geo.box(5.4, 4.2, 0.08, bevel=0.02, segments=1), "hull_dark", at=(0, -9.1, 5.0))
    p.add(geo.cylinder(0.75, 0.25, verts=16, bevel=0.05, segments=1), "hull", at=(0, 8.4, 4.62), rot=(-15, 0, 0))
    for dx in (-0.55, 0.0, 0.55):
        p.add(geo.box(0.34, 0.2, 0.22, bevel=0.03, segments=1), "lamp", at=(dx, 9.3, 4.55), rot=(-15, 0, 0))
    # Fuel drums on the rear.
    for side in (-1, 1):
        p.add(geo.cylinder(0.75, 2.4, verts=14, bevel=0.06, segments=1), "drum", at=(side * 1.5, -13.3, 4.2), rot=(0, 90, 0))
    p.add(geo.box(5.5, 0.3, 0.3, bevel=0.04, segments=1), "hull_dark", at=(0, -12.8, 3.4))
    # Markings: emblem on the glacis and skirts, red recognition bands.
    for side in (-1, 1):
        a.decal(images.get("emblem"), (side * 5.7, -2.2, 3.2), (side, 0, 0), (1.6, 1.6, 0.6), color="#a8191a")


def turret(a):
    t = a.part("TurretBody", path="Turret", tex="turret", material="Metal", smooth_angle=35)
    t.add(geo.cylinder(3.4, 0.5, verts=24, bevel=0.05, segments=1), "hull_dark", at=(RING[0], RING[1], DECK_Z + 0.2))
    t.add(turret_shell(), "hull", at=(0, 0.4, DECK_Z + 1.55))
    # Mantlet.
    t.add(geo.tapered_box(2.8, 1.3, 2.0, top_scale=(0.9, 0.8), bevel=0.12, segments=1), "hull", at=(0, 5.0, GUN_Z))
    # Rear bustle with stowage basket.
    t.add(geo.box(6.2, 2.0, 1.6, bevel=0.1, segments=1), "hull_banded", at=(0, -4.7, DECK_Z + 1.5))
    for x in (-3.2, 3.2):
        t.add(geo.box(0.1, 2.6, 0.9, bevel=0.0), "track", at=(x, -6.3, DECK_Z + 2.0))
    for yy in (-7.55, -5.0):
        t.add(geo.box(6.5, 0.1, 0.9, bevel=0.0), "track", at=(0, yy, DECK_Z + 2.0))
    for i in range(4):
        t.add(geo.box(6.4, 0.06, 0.06, bevel=0.0), "track", at=(0, -7.55, DECK_Z + 1.65 + i * 0.25))
    t.add(geo.box(2.2, 1.6, 0.8, bevel=0.2, segments=1), "drum", at=(-1.5, -6.2, DECK_Z + 1.9))
    t.add(geo.cylinder(0.5, 1.8, verts=10, bevel=0.1, segments=1), "drum", at=(1.5, -6.3, DECK_Z + 1.9), rot=(0, 90, 0))
    # Commander cupola with hatch and a roof MG; gunner sight box.
    cx, cy = -1.8, -1.0
    top = DECK_Z + 2.7
    t.add(geo.cylinder(1.0, 0.6, verts=16, bevel=0.06, segments=1), "hull", at=(cx, cy, top + 0.25))
    for k in range(6):
        ang = 2 * math.pi * k / 6
        t.add(geo.box(0.25, 0.1, 0.18, bevel=0.02, segments=1), "lamp", at=(cx + 0.98 * math.cos(ang), cy + 0.98 * math.sin(ang), top + 0.3), rot=(0, 0, math.degrees(ang) + 90))
    t.add(geo.cylinder(0.85, 0.12, verts=16, bevel=0.03, segments=1), "hull_dark", at=(cx, cy - 0.2, top + 0.62), rot=(-10, 0, 0))
    t.add(geo.box(0.3, 1.8, 0.28, bevel=0.03, segments=1), "track", at=(cx + 0.9, cy + 0.9, top + 0.75))
    t.add(geo.cylinder(0.06, 1.3, verts=6, bevel=0.0), "track", at=(cx + 0.9, cy + 2.2, top + 0.78), rot=(-90, 0, 0))
    t.add(geo.box(0.9, 1.2, 0.85, bevel=0.08, segments=1), "hull", at=(2.1, 2.2, top + 0.25))
    t.add(geo.box(0.7, 0.08, 0.5, bevel=0.02, segments=1), "lamp", at=(2.1, 2.82, top + 0.3))
    # Smoke grenade launchers on the turret cheeks.
    for side in (-1, 1):
        for k in range(4):
            t.add(geo.cylinder(0.14, 0.55, verts=8, bevel=0.0), "hull_dark", at=(side * (3.3 + k * 0.05), 2.7 - k * 0.32, DECK_Z + 2.55), rot=(-60, 0, side * -30))
    # Antennas (thin) at the rear corners.
    for side in (-1, 1):
        t.add(geo.cylinder(0.03, 4.0, verts=4, bevel=0.0), "track", at=(side * 2.8, -3.8, top + 2.0))
        t.add(geo.cylinder(0.12, 0.3, verts=8, bevel=0.0), "hull_dark", at=(side * 2.8, -3.8, top + 0.1))
    # Red markings: turret number both sides, red band round the bustle.
    for side in (-1, 1):
        a.decal(images.get("digits", text="217"), (side * 4.3, 0.6, DECK_Z + 1.6), (side, 0.1, 0), (2.4, 0.8, 0.8), color="#b11d1b")
    a.material("hull_banded", base="gunmetal", marks=[{"lo": (-3.5, -5.8, DECK_Z + 1.0), "hi": (3.5, -5.55, DECK_Z + 2.4), "color": "#9e1a16"}])

    b = a.part("Barrel", path="Turret", tex="turret", material="Metal", smooth_angle=40)
    y0 = GUN_Y0
    b.add(geo.cylinder(0.5, 1.2, verts=16, bevel=0.06, segments=1), "hull_dark", at=(0, y0 + 0.4, GUN_Z), rot=(-90, 0, 0))
    b.add(geo.cylinder(0.33, GUN_LEN, verts=14, r_top=0.28, bevel=0.0), "hull", at=(0, y0 + GUN_LEN / 2, GUN_Z), rot=(-90, 0, 0))
    for k, (yy, rr, ll) in enumerate([(y0 + 2.5, 0.4, 1.6), (y0 + 5.2, 0.55, 1.6), (y0 + 8.0, 0.38, 1.4)]):
        b.add(geo.lathe([(0.28, -ll / 2), (rr, -ll / 2 + 0.2), (rr, ll / 2 - 0.2), (0.28, ll / 2)], verts=14), "hull", at=(0, yy, GUN_Z), rot=(-90, 0, 0))
    b.add(geo.tube(0.34, 0.2, 0.5, verts=14), "hull_dark", at=(0, y0 + GUN_LEN - 0.1, GUN_Z), rot=(-90, 0, 0))
    b.add(geo.box(0.35, 0.3, 0.25, bevel=0.03, segments=1), "hull_dark", at=(0, y0 + GUN_LEN - 0.9, GUN_Z + 0.36))
    a.attach("Muzzle", "Barrel", (0, y0 + GUN_LEN + 0.2, GUN_Z), axis=(0, 1, 0))


def build(**kw):
    a = Asset("Tank", pivot=(0, 0, 0), tex_size=1024)
    a.texture_group("hull", 1024)
    a.texture_group("gear", 1024)
    a.texture_group("turret", 1024)
    a.pivot("Turret", RING)
    materials(a)
    hull(a)
    track_side(a, -1)
    track_side(a, 1)
    turret(a)
    views = [("", (1.1, 1.3, 0.6)), ("_rear", (-1.2, -1.1, 0.7)), ("_side", (1.0, 0.05, 0.12))]
    return a.finish(views=views, **kw)
