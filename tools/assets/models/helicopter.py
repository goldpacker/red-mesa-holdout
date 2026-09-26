"""Helicopter: enemy tandem-seat attack helicopter (original design).
Dark gunmetal with red tail band, red nose number and the emblem.

Asset origin = centre of mass (under the mast). Rotor diameter 40 studs.
Root = fuselage, wings, pods, gear; MainRotor (4 blades, origin = hub,
spins about Y); TailRotor (origin = hub, spins about X); attachments
RocketMuzzleL / RocketMuzzleR (pod fronts), Searchlight (chin, looking
forward/down), GunMuzzle (chin cannon).
"""
import math

from rmh import geo, images
from rmh.asset import Asset

HUB = (0.0, 0.0, 4.9)
ROTOR_R = 20.0
TAIL_HUB = (0.95, -21.3, 4.7)
TAIL_R = 2.7
POD_X, POD_Y, POD_Z = 5.4, 0.2, -1.25


def materials(a):
    a.material("body", base="gunmetal", wear=0.35, dust=0.25, dust_up=0.15, grime=0.6, panels=(1.8, 2.4, 1.6), panel_width=0.08,
               marks=[{"lo": (-2, -15.2, -1), "hi": (2, -14.2, 4), "color": "#a3161a"},
                      {"lo": (-1, -23, 5.6), "hi": (1, -19, 7), "color": "#a3161a"}])
    a.material("body_dark", base="charcoal", wear=0.3, dust=0.2, dust_up=0.15)
    a.material("canopy", base="glass", color="#1b2328", rough=0.04, metal=0.4)
    a.material("blade", base="charcoal", color="#1f2124", wear=0.2, dust=0.1, dust_up=0.1)
    a.material("weapon", base="olive_dark", color="#3a3c34", wear=0.4, dust=0.3,
               marks=[{"lo": (-8, 1.2, -3), "hi": (8, 1.45, 0), "color": "#c9a227"}])
    a.material("tyre", base="rubber")
    a.material("lamp", base="lens")


def fuselage(a):
    p = a.part("Root", tex="body", material="Metal", smooth_angle=55)
    secs = [
        (14.6, 0.3, 0.4, -0.7, 2.0),
        (13.8, 1.4, 1.7, -0.55, 2.6),
        (12.4, 2.1, 2.7, -0.35, 3.0),
        (9.5, 2.5, 3.4, -0.1, 3.4),
        (6.0, 2.8, 3.9, 0.2, 3.6),
        (2.0, 3.3, 4.2, 0.35, 3.8),
        (-2.5, 3.3, 4.0, 0.5, 3.8),
        (-5.0, 2.5, 3.0, 0.95, 3.2),
        (-7.5, 1.5, 1.8, 1.4, 2.6),
        (-17.5, 1.0, 1.25, 1.75, 2.4),
        (-21.8, 0.9, 1.1, 1.95, 2.4),
    ]
    p.add(geo.loft(secs, n=18), "body")
    # Stepped tandem canopy.
    p.add(geo.sphere(1.0, 14, 8, scale=(1.1, 2.4, 0.95)), "canopy", at=(0, 10.1, 1.15))
    p.add(geo.sphere(1.0, 14, 8, scale=(1.25, 2.7, 1.05)), "canopy", at=(0, 5.6, 1.9))
    for y, z, w in ((11.8, 1.1, 2.0), (8.4, 1.5, 2.3), (7.9, 2.1, 2.5), (3.2, 2.0, 2.6)):
        p.add(geo.box(w, 0.12, 0.12, bevel=0.03, segments=1), "body_dark", at=(0, y, z + 0.5))
    # Engine nacelles with intakes and angled exhausts, mast fairing.
    for side in (-1, 1):
        x = side * 1.55
        p.add(geo.loft([(3.4, 0.9, 0.9, 2.75, 2.0, x), (2.8, 1.5, 1.5, 2.75, 2.4, x), (-2.8, 1.5, 1.5, 2.8, 2.4, x), (-4.4, 0.9, 1.0, 2.9, 2.2, x)], n=12), "body")
        p.add(geo.tube(0.62, 0.4, 0.3, verts=12), "body_dark", at=(x, 3.4, 2.75), rot=(-90, 0, 0))
        p.add(geo.cylinder(0.5, 1.2, verts=10, bevel=0.03, segments=1), "body_dark", at=(x + side * 0.4, -4.6, 3.0), rot=(-90, 0, side * -30))
    p.add(geo.loft([(2.4, 0.4, 0.6, 3.1, 2.0), (1.2, 2.2, 1.4, 3.4, 2.6), (-1.6, 2.2, 1.4, 3.4, 2.6), (-3.2, 0.4, 0.5, 3.1, 2.0)], n=12), "body")
    p.add(geo.cylinder(0.35, 1.0, verts=10, bevel=0.0), "body_dark", at=(0, 0, 4.3))
    # Stub wings with a rocket pod and a missile rack each.
    for side in (-1, 1):
        w = geo.blade(4.6, 2.6, 1.8, 0.35)
        if side < 0:
            w = geo.mirror_x(w)
        p.add(w, "body", at=(side * 1.5, 0.2, -0.3), rot=(0, side * -6, 0))
        p.add(geo.box(0.3, 1.2, 0.7, bevel=0.05, segments=1), "body_dark", at=(side * POD_X, POD_Y, -0.75))
        p.add(geo.cylinder(0.6, 3.2, verts=14, bevel=0.08, segments=1), "weapon", at=(side * POD_X, POD_Y, POD_Z), rot=(-90, 0, 0))
        for k in range(7):
            ang = 2 * math.pi * k / 6
            r = 0.0 if k == 6 else 0.36
            p.add(geo.cylinder(0.13, 0.05, verts=8, bevel=0.0), "body_dark", at=(side * POD_X + r * math.cos(ang), POD_Y + 1.62, POD_Z + r * math.sin(ang)), rot=(-90, 0, 0))
        p.add(geo.box(0.3, 1.1, 0.6, bevel=0.05, segments=1), "body_dark", at=(side * 3.3, 0.1, -0.7))
        for dx in (-0.3, 0.3):
            for dz in (-1.05, -1.6):
                p.add(geo.cylinder(0.14, 2.2, verts=8, bevel=0.03, segments=1), "weapon", at=(side * 3.3 + dx, 0.3, dz), rot=(-90, 0, 0))
                p.add(geo.cylinder(0.14, 0.3, verts=8, r_top=0.02, bevel=0.0), "canopy", at=(side * 3.3 + dx, 1.55, dz), rot=(-90, 0, 0))
        a.attach("RocketMuzzleL" if side < 0 else "RocketMuzzleR", "Root", (side * POD_X, POD_Y + 1.75, POD_Z), axis=(0, 1, 0))
    # Chin gun turret and nose sensor.
    p.add(geo.sphere(0.65, 12, 7), "body_dark", at=(0, 11.6, -1.95))
    p.add(geo.cylinder(0.1, 2.4, verts=8, bevel=0.0), "body_dark", at=(0, 12.9, -2.05), rot=(-90, 0, 0))
    p.add(geo.sphere(0.55, 12, 7), "canopy", at=(0, 13.9, -0.25))
    a.attach("GunMuzzle", "Root", (0, 14.15, -2.05), axis=(0, 1, 0))
    # Searchlight under the chin.
    p.add(geo.cylinder(0.32, 0.5, verts=10, bevel=0.04, segments=1), "body_dark", at=(1.0, 9.6, -2.2), rot=(-70, 0, 0))
    p.add(geo.cylinder(0.26, 0.05, verts=10, bevel=0.0), "lamp", at=(1.0, 9.85, -2.3), rot=(-70, 0, 0))
    a.attach("Searchlight", "Root", (1.0, 9.9, -2.32), axis=(0, 1, -0.45))
    # Landing gear: main wheels, struts, tail wheel.
    for side in (-1, 1):
        p.add(geo.pipe_path([(side * 1.6, 4.0, -1.6), (side * 2.3, 4.0, -2.9)], 0.12, verts=6), "body_dark")
        p.add(geo.cylinder(0.55, 0.35, verts=12, bevel=0.06, segments=1), "tyre", at=(side * 2.35, 4.0, -3.15), rot=(0, 90, 0))
    p.add(geo.pipe_path([(0, -17.5, 1.3), (0, -17.8, 0.2)], 0.08, verts=6), "body_dark")
    p.add(geo.cylinder(0.3, 0.2, verts=10, bevel=0.03, segments=1), "tyre", at=(0, -17.8, 0.0), rot=(0, 90, 0))
    # Tail: fin, stabiliser, tail rotor gearbox.
    fin = geo.prism([(-20.2, 2.0), (-22.2, 2.2), (-22.9, 6.8), (-21.8, 6.9)], 0.3, bevel=0.05, segments=1)
    p.add(fin, "body", rot=(90, 0, 90), at=(0, 0, 0))
    for side in (-1, 1):
        s = geo.blade(3.0, 1.5, 1.0, 0.2, sweep=-0.3)
        if side < 0:
            s = geo.mirror_x(s)
        p.add(s, "body", at=(side * 0.45, -17.8, 1.8))
    p.add(geo.cylinder(0.35, 0.6, verts=10, bevel=0.03, segments=1), "body_dark", at=(0.45, TAIL_HUB[1], TAIL_HUB[2]), rot=(0, 90, 0))
    # Markings: emblem on the boom, nose number.
    for side in (-1, 1):
        a.decal(images.get("emblem"), (side * 0.62, -11.0, 1.55), (side, 0, 0), (1.4, 1.4, 0.5), color="#b01c1c")
        a.decal(images.get("digits", text="07"), (side * 1.4, 10.8, -0.5), (side, 0, 0), (1.3, 0.75, 0.9), color="#b01c1c")


def main_rotor(a):
    r = a.part("MainRotor", tex="rotor", query=False, joint=HUB, material="Metal", smooth_angle=30)
    hx, hy, hz = HUB
    r.add(geo.cylinder(0.85, 0.7, verts=14, bevel=0.08, segments=1), "body_dark", at=(hx, hy, hz))
    r.add(geo.cylinder(0.4, 0.5, verts=10, r_top=0.15, bevel=0.03, segments=1), "body_dark", at=(hx, hy, hz + 0.55))
    r.add(geo.cylinder(0.4, 0.5, verts=10, r_top=0.15, bevel=0.03, segments=1), "body_dark", at=(hx, hy, hz - 0.55), rot=(180, 0, 0))
    for k in range(4):
        ang = 45 + 90 * k
        r.add(geo.blade(ROTOR_R - 0.7, 1.05, 0.8, 0.12), "blade", at=(hx, hy, hz), rot=(4, 0, ang))
        r.add(geo.box(1.4, 0.5, 0.3, bevel=0.06, segments=1), "body_dark", at=(hx + 1.2 * math.cos(math.radians(ang)), hy + 1.2 * math.sin(math.radians(ang)), hz), rot=(0, 0, ang))


def tail_rotor(a):
    t = a.part("TailRotor", tex="rotor", query=False, joint=TAIL_HUB, material="Metal", smooth_angle=30)
    x, y, z = TAIL_HUB
    t.add(geo.cylinder(0.3, 0.4, verts=10, bevel=0.04, segments=1), "body_dark", at=(x + 0.15, y, z), rot=(0, 90, 0))
    for k in range(4):
        ang = 90 * k + 45
        b = geo.transform(geo.blade(TAIL_R, 0.5, 0.35, 0.07), rot=(0, -90, 0))  # length along +Z, thin along X
        t.add(b, "blade", at=(x + 0.3, y, z), rot=(ang, 0, 0))


def build(**kw):
    a = Asset("Helicopter", pivot=(0, 0, 0), tex_size=1024)
    a.texture_group("body", 1024)
    a.texture_group("rotor", 512)
    a.zmin = -3.7
    a.meta["no_ground"] = False
    materials(a)
    fuselage(a)
    main_rotor(a)
    tail_rotor(a)
    views = [("", (1.1, 1.3, 0.55)), ("_rear", (-1.2, -1.1, 0.7)), ("_side", (1.0, 0.05, 0.05))]
    return a.finish(views=views, **kw)
