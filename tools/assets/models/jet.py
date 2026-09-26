"""Jet: enemy twin-engine, twin-tail strike jet (original design).
Dark gunmetal with a charcoal spine, red fin tips, emblem on the fins and
a red nose number. ~50 studs long, ~32 studs span.

Asset origin = centre of mass. Root = whole airframe (single part plus a
bomb load part); attachments Exhaust (between the nozzles, looking aft),
BombBay (belly, looking down), NavLightL / NavLightR (wing tips),
Cockpit (canopy centre).
"""
import math

from rmh import geo, images
from rmh.asset import Asset


def materials(a):
    a.material("skin", base="gunmetal", color="#3a3e43", wear=0.25, dust=0.12, dust_up=0.1, grime=0.55, panels=(2.6, 3.2, 0), panel_width=0.1,
               marks=[{"lo": (-1.6, 21.2, -2), "hi": (1.6, 21.7, 2), "color": "#a3161a"}])
    a.material("skin_dark", base="charcoal", wear=0.2, dust=0.1, dust_up=0.1)
    a.material("fin", base="gunmetal", color="#3a3e43", wear=0.25, dust=0.1, dust_up=0.1,
               marks=[{"lo": (-9, -24, 7.0), "hi": (9, -15, 9), "color": "#a3161a"}])
    a.material("canopy", base="glass", color="#2a2416", rough=0.04, metal=0.6)
    a.material("nozzle", base="steel", color="#4b4640", rough=0.35, grime=0.9)
    a.material("ordnance", base="olive_dark", color="#43453a", wear=0.35, dust=0.15)


def airframe(a):
    p = a.part("Root", tex="body", material="Metal", smooth_angle=50)
    secs = [
        (25.0, 0.1, 0.1, 0.3, 2.0),
        (23.5, 1.1, 1.1, 0.25, 2.0),
        (20.0, 2.3, 2.3, 0.35, 2.2),
        (16.0, 3.0, 2.9, 0.5, 2.6),
        (11.0, 3.6, 3.2, 0.6, 3.0),
        (6.0, 5.4, 3.3, 0.4, 3.4),
        (-2.0, 6.2, 3.2, 0.3, 3.6),
        (-12.0, 5.6, 2.9, 0.3, 3.6),
        (-18.0, 4.6, 2.6, 0.3, 3.2),
        (-21.0, 4.2, 2.4, 0.3, 3.0),
    ]
    p.add(geo.loft(secs, n=20), "skin")
    # Canopy and spine.
    p.add(geo.sphere(1.0, 16, 8, scale=(1.15, 4.2, 1.15)), "canopy", at=(0, 14.2, 1.75))
    p.add(geo.loft([(11.0, 1.2, 1.2, 1.8, 2.0), (6.0, 1.8, 1.3, 2.0, 2.4), (-12.0, 1.5, 1.0, 1.75, 2.4), (-17.0, 0.4, 0.3, 1.5, 2.0)], n=12), "skin_dark")
    p.add(geo.box(2.1, 0.12, 0.2, bevel=0.03, segments=1), "skin_dark", at=(0, 16.0, 2.3), rot=(-25, 0, 0))
    # Intakes on the fuselage sides.
    for side in (-1, 1):
        x = side * 2.55
        p.add(geo.loft([(10.8, 1.3, 1.9, 0.0, 4.0, x), (8.5, 1.5, 2.0, 0.0, 4.0, x), (2.0, 1.2, 1.9, 0.1, 4.0, x * 0.85)], n=12, cap_start=False), "skin")
        p.add(geo.box(1.1, 0.08, 1.6, bevel=0.0), "skin_dark", at=(x, 10.7, 0.0))
    # Twin engine nozzles.
    for side in (-1, 1):
        x = side * 1.15
        p.add(geo.lathe([(1.1, 0.0), (1.2, -0.8), (1.05, -2.4), (0.8, -2.4), (0.9, -0.9), (0.6, -0.4)], verts=16, close_top=False, close_bottom=True), "nozzle", at=(x, -20.8, 0.3), rot=(-90, 0, 0))
    # Wings, horizontal tails and canted twin fins.
    for side in (-1, 1):
        wing = geo.prism([(2.4, 4.0), (16.0, -6.8), (16.0, -10.2), (2.4, -12.0)], 0.38, bevel=0.08, segments=1)
        tail = geo.prism([(2.2, -14.5), (8.8, -19.2), (8.8, -21.6), (2.2, -21.8)], 0.26, bevel=0.06, segments=1)
        if side < 0:
            wing, tail = geo.mirror_x(wing), geo.mirror_x(tail)
        p.add(wing, "skin", at=(0, 0, 0.0), rot=(0, side * -3, 0))
        p.add(tail, "skin", at=(0, 0, 0.2))
        fin = geo.prism([(-13.2, 0.0), (-19.8, 6.9), (-22.2, 6.9), (-21.8, 0.0)], 0.3, bevel=0.06, segments=1)
        geo.transform(fin, rot=(90, 0, 90))  # profile (y, z), thickness along X
        p.add(fin, "fin", at=(side * 2.3, 0, 1.3), rot=(0, side * 18, 0))
        a.decal(images.get("emblem"), (side * 3.4, -18.4, 4.4), (side * 0.95, 0, 0.31), (2.2, 2.2, 0.8), color="#b01c1c")
        # Pylons and bombs.
        for wx in (6.5, 10.5):
            p.add(geo.box(0.25, 2.2, 0.6, bevel=0.05, segments=1), "skin_dark", at=(side * wx, -3.5, -0.5))
        # Wing-tip rails.
        p.add(geo.cylinder(0.14, 3.4, verts=8, r_top=0.05, bevel=0.0), "skin_dark", at=(side * 16.05, -8.4, 0.84), rot=(-90, 0, 0))
        a.attach("NavLightL" if side < 0 else "NavLightR", "Root", (side * 16.1, -10.2, 0.84), axis=(side, 0, 0))
    # Nose number and a red band behind the radome (marks on 'skin').
    for side in (-1, 1):
        a.decal(images.get("digits", text="31"), (side * 1.55, 18.4, 0.2), (side, 0, 0.1), (2.0, 1.0, 1.0), color="#b01c1c")
    a.attach("Exhaust", "Root", (0, -23.4, 0.3), axis=(0, -1, 0))
    a.attach("BombBay", "Root", (0, -2.0, -1.6), axis=(0, 0, -1))
    a.attach("Cockpit", "Root", (0, 14.2, 1.9), axis=(0, 1, 0))

    bombs = a.part("Bombs", tex="body", material="Metal", smooth_angle=45)
    for side in (-1, 1):
        for wx in (6.5, 10.5):
            bm = geo.lathe([(0.0, -1.9), (0.32, -1.6), (0.45, -0.8), (0.45, 0.9), (0.3, 1.6), (0.0, 1.9)], verts=12)
            bombs.add(bm, "ordnance", at=(side * wx, -3.3, -1.3), rot=(-90, 0, 0))
            for k in range(4):
                fin = geo.prism([(0.0, 0.0), (0.55, -0.5), (0.55, -0.9), (0.0, -0.6)], 0.04, bevel=0.0)
                bombs.add(fin, "ordnance", at=(side * wx, -3.3 - 1.4, -1.3), rot=(-90, 0, 45 + 90 * k))


def build(**kw):
    a = Asset("Jet", pivot=(0, 0, 0), tex_size=1024)
    a.texture_group("body", 1024)
    a.zmin = -2.0
    materials(a)
    airframe(a)
    views = [("", (1.1, 1.2, 0.6)), ("_rear", (-1.0, -1.3, 0.5)), ("_top", (0.2, -0.3, 1.0))]
    return a.finish(views=views, **kw)
