"""Siege Crawler weak points (HS-5): the main cannon, the two sponson
turrets, the core and its armour, and the torn-metal sockets left when a
weak point is blown off. Built into models/siege_crawler.py's Asset
(`turrets` atlas, high-poly bake; crew-scale kit on the TrimEnemy sheet).

Contract (docs/ASSET_CONTRACTS.md): MainCannon (WorldPivot at its ring)
with CannonTurret, CannonBarrel, CannonGlow and attachment Muzzle;
TurretLeft/TurretRight (WorldPivot at their rings) with TurretXBody and
attachment Muzzle; Core; CoreArmor. Their boxes are the pre-HS-5 ones
(HIT in siege_crawler.py). Kit parts ride in the weak point's sub-model,
so they are thrown off with it. Sockets are hidden (Transparency 1,
CanQuery false) parts named <WeakPoint>Socket at model level.
"""
import math
import random

from mathutils import Vector

from rmh import geo, hardsurface as hs, images
from rmh.asset import rb_box

MAIN_RING = (0.0, 12.0, 19.0)
SIDE_RING = (15.2, 20.0, 16.4)
CORE = (0.0, -21.0, 27.2)
GLOW_RED = (1.0, 0.33, 0.12)
RED = "#b01c18"
HAZARD = "#c9a227"
GUN_Z = 22.6
TOP_Z = 25.6
SIDE_GUN_Z = 19.0

# Main turret plan (x, y) at the bottom (z 19.8) and top (z 25.6), CCW.
MT_LO = [(-2.9, 22.45), (-7.9, 18.6), (-7.9, 6.5), (-6.3, 4.15), (6.3, 4.15), (7.9, 6.5), (7.9, 18.6), (2.9, 22.45)]
MT_HI = [(-2.4, 20.9), (-6.9, 17.6), (-7.0, 7.0), (-5.7, 5.0), (5.7, 5.0), (7.0, 7.0), (6.9, 17.6), (2.4, 20.9)]
# Side turret plan relative to its ring.
ST_LO = [(-3.1, -3.35), (3.1, -3.35), (3.1, 1.8), (1.9, 3.9), (-1.9, 3.9), (-3.1, 1.8)]
ST_HI = [(-2.55, -2.6), (2.55, -2.6), (2.55, 1.4), (1.5, 3.0), (-1.5, 3.0), (-2.55, 1.4)]


def materials(a, paint):
    band = [{"lo": (-9.0, 6.2, 23.6), "hi": (9.0, 18.2, 24.5), "color": RED}]
    msoot = [{"pos": (0, 52.3, GUN_Z), "dir": (0, -1, 0), "radius": 1.6, "length": 7.0, "spread": 0.05, "strength": 0.95}]
    ssoot = [{"pos": (s * SIDE_RING[0] + dx, 32.9, SIDE_GUN_Z), "dir": (0, -1, 0), "radius": 0.5, "length": 3.0, "spread": 0.05}
             for s in (-1, 1) for dx in (-0.8, 0.8)]
    turret = dict(paint, dust_height=0.0, dust_caked=0.0, dust_up=0.5)
    a.material("turret", **turret, marks=band)
    a.material("turret_dark", **dict(turret, color="#2b2d31", photo=None))
    a.material("barrel", **dict(turret, color="#34373b", wear=0.45), soot=msoot)
    a.material("side_turret", **turret, soot=ssoot,
               marks=[{"lo": (s * SIDE_RING[0] - 3.6, 16.0, 19.2), "hi": (s * SIDE_RING[0] + 3.6, 24.5, 19.75), "color": RED} for s in (-1, 1)])
    a.material("side_barrel", **dict(turret, color="#34373b", wear=0.45), soot=ssoot)
    a.material("red_box", **dict(turret, color="#9e1a16", photo=None, wear=0.6))
    a.material("armor", **dict(turret, dust_up=0.4))
    a.material("armor_red", **dict(turret, color="#9e1a16", photo=None, wear=0.6))
    # Torn, burnt steel for the sockets: charred paint, rusted and heat-tinted edges.
    a.material("torn", kind="paint", color="#1d1a18", rough=0.85, wear=0.9, under="#6a4a36", under_metal=0.4, under_rough=0.6,
               chip_style="blotch", chip_scale=4.5, ring=0.7, ring_color="#4a2a18", edge_convex=True, polish=0.5,
               polish_color="#7a6a5c", grime=0.9, grime_color="#0e0c0b", streaks=0.6, dust=0.15, rough_breakup=0.4)
    a.material("char", kind="flat", color="#0b0a09", rough=0.95, metal=0.0, dust=0.0, grime=0.0)
    a.material("torn_steel", kind="metal", color="#3b2f28", rough=0.55, metal=0.8, grime=0.8, grime_color="#1a120c",
               dust=0.0, edge_convex=True, polish=0.7, polish_color="#8a7a70", rough_breakup=0.4)


def _facet(lo, hi, z0, z1, i, z):
    """Point on plan edge i of a tapered prism at height z, and its outward normal (x, y)."""
    t = (z - z0) / (z1 - z0)
    n = len(lo)
    p0 = [lo[i][k] + (hi[i][k] - lo[i][k]) * t for k in range(2)]
    p1 = [lo[(i + 1) % n][k] + (hi[(i + 1) % n][k] - lo[(i + 1) % n][k]) * t for k in range(2)]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy)
    return ((p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2), (dy / ln, -dx / ln), ln, math.degrees(math.atan2(dy, dx))


# --- main cannon ---------------------------------------------------------------------------

def main_cannon(a, T, HIT):
    rx, ry, rz = MAIN_RING
    lo, hi = rb_box(*HIT["CannonTurret"])
    t = a.part("CannonTurret", path="MainCannon", tex="turrets", material="Metal", smooth_angle=35, hitbox=(lo, hi))
    t.add(geo.cylinder(7.3, 0.85, verts=32, bevel=0.0, caps=False), "turret_dark", at=(rx, ry, rz + 0.42))
    t.add(geo.tapered_prism(MT_LO, MT_HI, rz + 0.8, TOP_Z), "turret", texel=lambda f: 0.2 if f.normal.z < -0.6 else 1.0)
    for i in range(len(MT_LO)):
        (bx, by), (tx, ty) = MT_LO[i], MT_HI[i]
        t.detail(hs.weld([(bx, by, rz + 0.85), (tx, ty, TOP_Z - 0.05)], r=0.08), "turret")
    t.detail(hs.weld([(x, y, TOP_Z - 0.02) for x, y in MT_HI + MT_HI[:1]], r=0.08), "turret")
    # Spaced armour plates bolted off the two front cheek facets.
    for i in (0, 6):
        (x0, y0), (x1, y1) = MT_LO[i], MT_LO[i + 1]
        (u0, v0), (u1, v1) = MT_HI[i], MT_HI[i + 1]
        quad = [(x0, y0, rz + 1.1), (x1, y1, rz + 1.1), (u1, v1, TOP_Z - 0.4), (u0, v0, TOP_Z - 0.4)]
        t.add(hs.plate_on_quad(quad, offset=0.3, thickness=0.28, inset=0.14), "turret")
        (mx, my), (nx, ny), ln, _ = _facet(MT_LO, MT_HI, rz + 0.8, TOP_Z, i, 22.6)
        for zz in (20.9, 24.3):
            (qx, qy), _, ln2, _ = _facet(MT_LO, MT_HI, rz + 0.8, TOP_Z, i, zz)
            d = Vector((x1 - x0, y1 - y0, 0)).normalized() * (ln2 * 0.36)
            c = Vector((qx + nx * 0.62, qy + ny * 0.62, zz))
            t.detail(hs.bolt_row(c - d, c + d, 4, (nx, ny, 0.0), r=0.12, h=0.07), "turret")
    # Mantlet round the gun root.
    t.add(geo.tapered_box(5.4, 1.6, 4.0, top_scale=(0.86, 0.7), top_shift=(0, -0.15), bevel=0.0), "turret_dark",
          at=(0, 21.8, GUN_Z), rot=(0, 0, 0))
    t.detail(hs.bolt_row((-2.2, 22.62, 24.1), (2.2, 22.62, 24.1), 6, (0, 1, 0), r=0.1, h=0.05), "turret_dark")
    t.detail(hs.bolt_row((-2.2, 22.62, 21.1), (2.2, 22.62, 21.1), 6, (0, 1, 0), r=0.1, h=0.05), "turret_dark")
    # Side stowage bins, bolted.
    for s in (-1, 1):
        t.add(geo.tapered_box(0.75, 6.0, 2.2, top_scale=(0.7, 1.0), top_shift=(-s * 0.1, 0), bevel=0.0), "turret_dark",
              at=(s * 8.25, 9.4, 21.2))
        t.detail(hs.bolt_row((s * 8.64, 6.9, 22.0), (s * 8.64, 11.9, 22.0), 4, (s, 0, 0), r=0.08, h=0.05), "turret_dark")
    # Commander's cupola, loader's hatch, gunner's sight, roof vent.
    t.add(geo.cylinder(1.55, 0.8, verts=20, bevel=0.0), "turret", at=(-3.6, 9.0, TOP_Z + 0.4))
    t.add(geo.cylinder(1.25, 0.25, verts=20, bevel=0.0), "turret_dark", at=(-3.6, 8.8, TOP_Z + 0.9), rot=(-8, 0, 0))
    t.add(geo.cylinder(1.2, 0.3, verts=20, bevel=0.0), "turret_dark", at=(3.8, 8.2, TOP_Z + 0.15))
    t.add(geo.tapered_box(1.9, 2.3, 1.05, top_scale=(0.85, 0.75), top_shift=(0, -0.15), bevel=0.0), "turret_dark", at=(3.9, 15.9, TOP_Z + 0.52))
    t.add(geo.box(1.5, 0.12, 0.55, bevel=0.0), "glass", at=(3.9, 17.07, TOP_Z + 0.6))
    t.add(geo.cylinder(0.6, 0.45, verts=12, bevel=0.0), "turret_dark", at=(0.2, 6.6, TOP_Z + 0.22))
    for s in (-1, 1):
        t.detail(geo.torus(0.3, 0.08, verts=10, ring_verts=4), "turret_dark", at=(s * 5.0, 5.7, TOP_Z + 0.15), rot=(90, 0, 0))
    # Smoke dischargers: two banks of four on the rear cheeks.
    for s in (-1, 1):
        t.add(geo.box(1.4, 0.8, 0.55, bevel=0.0), "turret_dark", at=(s * 6.6, 17.2, TOP_Z - 0.25), rot=(0, 0, s * -36))
        for k in range(4):
            tube = geo.cylinder(0.2, 0.95, verts=10, bevel=0.0)
            t.add(tube, "turret_dark", at=(s * (6.05 + k * 0.33), 17.55 - k * 0.24, TOP_Z + 0.2), rot=(-52, 0, s * -36))
    # Markings: turret number both sides, emblem on the mantlet cover.
    for s in (-1, 1):
        hs.stencil(a, "01", (s * 7.6, 12.8, 22.7), (s, 0, 0.1), 2.1, color=RED, wear=0.25, chip=0.35, seed=21 + s)

    lo, hi = rb_box(*HIT["CannonBarrel"])
    b = a.part("CannonBarrel", path="MainCannon", tex="turrets", material="Metal", smooth_angle=40, hitbox=(lo, hi))

    def along(bm, y, mat="barrel"):
        return b.add(bm, mat, at=(0, y, GUN_Z), rot=(-90, 0, 0))

    along(geo.cylinder(1.65, 2.2, verts=24, bevel=0.0), 23.6)
    along(geo.cylinder(1.28, 24.0, verts=20, r_top=1.05, bevel=0.0), 24.7 + 12.0)
    along(geo.lathe([(1.18, -2.2), (1.72, -1.4), (1.72, 1.4), (1.15, 2.2)], verts=24), 34.0)
    for y in (27.5, 30.6, 38.6, 42.2, 45.6):
        along(geo.cylinder(1.3 - (y - 27.5) * 0.009, 0.4, verts=20, bevel=0.0), y)
        b.detail(hs.bolt_row((0.0, y, GUN_Z + 1.3 - (y - 27.5) * 0.009), (0.0, y, GUN_Z + 1.3 - (y - 27.5) * 0.009), 1, (0, 0, 1), r=0.1, h=0.06), "barrel")
    # Muzzle brake: a slotted block with side baffles (ports baked).
    b.add(geo.box(3.4, 2.9, 2.5, bevel=0.0), "barrel", at=(0, 50.95, GUN_Z))
    for yy in (50.0, 51.3):
        for s in (-1, 1):
            b.detail(geo.box(0.1, 0.8, 1.7, bevel=0.0), "turret_dark", at=(s * 1.72, yy, GUN_Z))
    b.add(geo.tube(1.12, 0.8, 0.3, verts=20, bevel=0.0), "barrel", at=(0, 52.25, GUN_Z), rot=(-90, 0, 0))
    g = a.part("CannonGlow", path="MainCannon", neon=GLOW_RED, transparency=1, query=False, shadow=False, material="Neon",
               hidden_preview=True)
    g.add(geo.icosphere(1.0, 2), "barrel", at=(0, 52.8, GUN_Z))
    a.attach("Muzzle", "CannonBarrel", (0, 52.5, GUN_Z), axis=(0, 1, 0))

    k = a.part("CannonKit", path="MainCannon", tex="trim", material="Metal", query=False, smooth_angle=50)
    for i in range(6):
        ang = math.radians(90 + i * 60)
        k.add(T.template("periscope"), "trim", at=(-3.6 + 1.4 * math.cos(ang), 9.0 + 1.4 * math.sin(ang), TOP_Z + 0.8),
              rot=(0, 0, math.degrees(ang) - 90), scale=(1.1, 1.1, 1.1))
    k.add(T.template("periscope"), "trim", at=(3.8, 9.5, TOP_Z + 0.3), scale=(1.3, 1.3, 1.3))
    for s in (-1, 1):
        w = hs.whip_antenna(height=5.5, base_r=0.15)
        T.cylindrical(w, "cable", axis=(0, 0, 1), along=True)
        k.add(w, "trim", at=(s * 4.6, 5.9, TOP_Z))
        r = hs.rail([(s * 7.25, 6.4, 24.6), (s * 7.25, 12.6, 24.6)], r=0.07, feet=True, foot_h=0.5)
        T.fill(r, "plain")
        k.add(r, "trim")
    for x in (1.0, 2.0):
        k.add(T.template("ammo_can"), "trim", at=(x, 5.9, TOP_Z), rot=(0, 0, 90), scale=(1.1, 1.1, 1.1))
    roll = hs.tarp_roll(length=4.0, r=0.45, straps=3)
    T.cylindrical(roll, "canvas", axis=(1, 0, 0), faces=lambda f: abs(f.normal.x) < 0.7, along=True)
    T.fill(roll, "canvas", faces=lambda f: abs(f.normal.x) >= 0.7)
    k.add(roll, "trim", at=(-1.0, 5.3, TOP_Z))
    # Canvas mantlet cover round the gun root.
    boot = geo.lathe([(1.7, -0.5), (1.95, -0.1), (1.85, 0.25), (1.6, 0.55)], verts=16, close_top=False, close_bottom=False)
    T.cylindrical(boot, "canvas", axis=(0, 0, 1), along=True)
    k.add(boot, "trim", at=(0, 23.0, GUN_Z), rot=(-90, 0, 0))


# --- side turrets --------------------------------------------------------------------------

def side_turret(a, T, HIT, side):
    name = "TurretLeft" if side < 0 else "TurretRight"
    cx, cy = side * SIDE_RING[0], SIDE_RING[1]
    z0 = SIDE_RING[2] + 0.6
    lo, hi = rb_box(*HIT[name + "Body"])
    t = a.part(name + "Body", path=name, tex="turrets", material="Metal", smooth_angle=40, hitbox=(lo, hi))
    t.add(geo.cylinder(3.45, 0.55, verts=24, bevel=0.0, caps=False), "turret_dark", at=(cx, cy, z0 + 0.27))
    lo_pts = [(cx + x, cy + y) for x, y in ST_LO]
    hi_pts = [(cx + x, cy + y) for x, y in ST_HI]
    t.add(geo.tapered_prism(lo_pts, hi_pts, z0 + 0.5, 20.4), "side_turret", texel=lambda f: 0.2 if f.normal.z < -0.6 else 1.0)
    for (bx, by), (hx, hy) in zip(lo_pts, hi_pts):
        t.detail(hs.weld([(bx, by, z0 + 0.55), (hx, hy, 20.35)], r=0.06), "side_turret")
    # Mantlet, twin autocannons with perforated jackets and flash hiders.
    t.add(geo.tapered_box(3.3, 1.2, 2.0, top_scale=(0.85, 0.7), bevel=0.0), "turret_dark", at=(cx, cy + 4.3, SIDE_GUN_Z - 1.0))
    for dx in (-0.8, 0.8):
        x = cx + dx
        t.add(geo.cylinder(0.36, 8.4, verts=12, r_top=0.32, bevel=0.0), "side_barrel", at=(x, cy + 4.6 + 4.2, SIDE_GUN_Z), rot=(-90, 0, 0))
        t.add(geo.cylinder(0.52, 3.2, verts=14, bevel=0.0), "side_barrel", at=(x, cy + 6.5, SIDE_GUN_Z), rot=(-90, 0, 0))
        for k in range(5):
            t.detail(geo.torus(0.53, 0.05, verts=12, ring_verts=4), "turret_dark", at=(x, cy + 5.2 + k * 0.62, SIDE_GUN_Z), rot=(90, 0, 0))
        t.add(geo.tube(0.48, 0.3, 0.9, verts=12, bevel=0.0), "side_barrel", at=(x, 32.5, SIDE_GUN_Z), rot=(-90, 0, 0))
    # Red ammo drum on the inboard flank (the old model's identity mark) and a periscope hood.
    t.add(geo.box(0.42, 2.6, 1.3, bevel=0.0), "red_box", at=(cx - side * 3.33, cy - 0.7, 18.95))
    t.detail(hs.bolt_row((cx - side * 3.55, cy - 1.7, 19.35), (cx - side * 3.55, cy + 0.3, 19.35), 3, (-side, 0, 0), r=0.07, h=0.04), "red_box")
    t.add(geo.tapered_box(1.1, 0.9, 0.55, top_scale=(0.8, 0.7), bevel=0.0), "turret_dark", at=(cx + side * 1.2, cy + 0.6, 20.65))
    t.add(geo.cylinder(0.75, 0.3, verts=14, bevel=0.0), "turret_dark", at=(cx - side * 0.9, cy - 1.2, 20.55))
    a.attach("Muzzle", name + "Body", (cx, 33.2, SIDE_GUN_Z), axis=(0, 1, 0))
    k = a.part(name + "Kit", path=name, tex="trim", material="Metal", query=False, smooth_angle=50)
    k.add(T.template("periscope"), "trim", at=(cx + side * 1.2, cy + 1.05, 20.9), scale=(1.1, 1.1, 1.1))
    w = hs.whip_antenna(height=4.0, base_r=0.12)
    T.cylindrical(w, "cable", axis=(0, 0, 1), along=True)
    k.add(w, "trim", at=(cx - side * 2.2, cy - 2.2, 20.4))


# --- core ----------------------------------------------------------------------------------

def core(a, HIT):
    cx, cy, cz = CORE
    lo, hi = rb_box(*HIT["Core"])
    c = a.part("Core", neon=GLOW_RED, material="Neon", query=True, hitbox=(lo, hi))
    c.add(geo.icosphere(3.4, 2), "hull", at=(cx, cy, cz))
    lo, hi = rb_box(*HIT["CoreArmor"])
    arm = a.part("CoreArmor", tex="turrets", material="Metal", query=True, smooth_angle=35, hitbox=(lo, hi))
    base = 24.95
    dome = geo.lathe([(6.2, 0.0), (6.2, 0.9), (5.75, 2.9), (4.4, 5.0), (2.4, 6.35), (0.0, 6.75)], verts=32)
    arm.add(dome, "armor", at=(cx, cy, base))
    for k in range(8):
        ang = 2 * math.pi * k / 8 + math.pi / 8
        fin = [(0.0, 0.0), (0.95, 0.0), (0.95, 2.4), (0.0, 4.2)]
        piece = geo.prism(fin, 0.55, bevel=0.0)
        # prism: (x=radial, y=up) extruded along z (tangential) -> radial fin standing on the dome base
        for v in piece.verts:
            r_, up, tg = v.co.x, v.co.y, v.co.z
            v.co = Vector((r_, tg, up))
        arm.add(piece, "armor", at=(cx + 5.8 * math.cos(ang), cy + 5.8 * math.sin(ang), base + 0.02), rot=(0, 0, math.degrees(ang)))
        arm.detail(hs.bolt_row((cx + 5.4 * math.cos(ang - 0.2), cy + 5.4 * math.sin(ang - 0.2), base + 1.3),
                               (cx + 5.4 * math.cos(ang + 0.2), cy + 5.4 * math.sin(ang + 0.2), base + 1.3), 2,
                               (math.cos(ang), math.sin(ang), 0.2), r=0.1, h=0.06), "armor")
    for k in range(4):
        ang = 2 * math.pi * k / 4
        arm.detail(hs.weld([(cx + 6.15 * math.cos(ang), cy + 6.15 * math.sin(ang), base + 0.9),
                            (cx + 4.4 * math.cos(ang), cy + 4.4 * math.sin(ang), base + 5.0),
                            (cx + 0.3 * math.cos(ang), cy + 0.3 * math.sin(ang), base + 6.74)], r=0.07), "armor")
        arm.add(geo.torus(0.35, 0.09, verts=10, ring_verts=4), "armor", at=(cx + 3.0 * math.cos(ang + 0.78), cy + 3.0 * math.sin(ang + 0.78),
                                                                            base + 6.0), rot=(90, 0, math.degrees(ang + 0.78)))
    arm.add(geo.cylinder(1.5, 0.45, verts=16, bevel=0.0), "armor_red", at=(cx, cy, base + 6.7))
    # Vents on the dome's front shoulder.
    for dx in (-1.6, 1.6):
        arm.add(geo.box(1.2, 0.4, 0.9, bevel=0.0), "armor", at=(cx + dx, cy + 4.9, base + 3.6), rot=(-35, 0, 0))
    a.decal(images.get("stripes", count=10, angle=45), (cx, cy + 5.9, base + 1.6), (0, 1, 0.2), (9.0, 1.6, 3.0), color=HAZARD, wear=0.35, seed=17)


# --- torn-metal sockets --------------------------------------------------------------------

def _shard(width, height, thick, rng):
    """A torn plate: jagged top edge, standing on z = 0, width along X, thickness along Y."""
    pts = [(-width / 2, 0.0), (width / 2, 0.0)]
    n = 4
    for i in range(n, -1, -1):
        x = -width / 2 + width * i / n
        h = height * (0.35 + 0.65 * rng.random())
        pts.append((x, h))
    bm = geo.prism(pts, thick, bevel=0.0)
    for v in bm.verts:  # (x, z_profile, depth) -> (x, depth, z)
        x, z, d = v.co.x, v.co.y, v.co.z
        v.co = Vector((x, d, z))
    return bm


def torn_socket(a, name, center, r_in, r_out, height, n, seed, base_h=0.45):
    """Hidden part: the torn ring left when a weak point is blown off."""
    rng = random.Random(seed)
    p = a.part(name, tex="turrets", material="Metal", query=False, transparency=1, smooth_angle=30)
    seen = 0.3  # only after the weak point is gone, from 330+ studs
    cx, cy, cz = center
    p.add(geo.tube(r_out, r_in, base_h, verts=28, bevel=0.0), "torn_steel", at=(cx, cy, cz + base_h / 2), texel=seen)
    p.add(geo.cylinder(r_in + 0.05, 0.12, verts=28, bevel=0.0), "char", at=(cx, cy, cz + base_h * 0.4), texel=0.05)
    for k in range(n):
        ang = 2 * math.pi * (k + rng.uniform(-0.25, 0.25)) / n
        w = 2 * math.pi * (r_in + r_out) / 2 / n * rng.uniform(0.6, 1.05)
        h = height * rng.uniform(0.45, 1.0)
        sh = _shard(w, h, rng.uniform(0.14, 0.26), rng)
        tilt = rng.uniform(15, 60)  # bent outward by the blast
        r = rng.uniform(r_in + 0.1, r_out - 0.1)
        p.add(sh, "torn", at=(cx + r * math.cos(ang), cy + r * math.sin(ang), cz + base_h * 0.8),
              rot=(tilt, rng.uniform(-10, 10), math.degrees(ang) - 90), texel=seen)
    # Cut pipe stubs and cable ends inside the ring.
    for k in range(5):
        ang = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.2, r_in * 0.7)
        rr = rng.uniform(0.12, 0.3) * (r_in / 3.0) ** 0.5
        hh = rng.uniform(0.6, 1.6) * height * 0.6
        p.add(geo.cylinder(rr, hh, verts=8, bevel=0.0), "torn_steel",
              at=(cx + r * math.cos(ang), cy + r * math.sin(ang), cz + hh / 2), rot=(rng.uniform(-25, 25), rng.uniform(-25, 25), 0),
              texel=seen)
    for k in range(4):
        ang = rng.uniform(0, 2 * math.pi)
        r = rng.uniform(0.3, r_in * 0.8)
        x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
        top = cz + height * rng.uniform(0.5, 0.9)
        pts = [(x, y, cz + 0.1), (x + rng.uniform(-0.3, 0.3), y + rng.uniform(-0.3, 0.3), (cz + top) / 2),
               (x + rng.uniform(-0.8, 0.8), y + rng.uniform(-0.8, 0.8), top)]
        p.add(geo.pipe_path(pts, 0.07 * (r_in / 3.0) ** 0.5, verts=6), "char", texel=0.1)
    return p


def sockets(a):
    for side, name in ((-1, "TurretLeftSocket"), (1, "TurretRightSocket")):
        torn_socket(a, name, (side * SIDE_RING[0], SIDE_RING[1], SIDE_RING[2] + 0.05), 3.0, 4.05, 2.4, 9, seed=31 + side)
    torn_socket(a, "MainCannonSocket", (MAIN_RING[0], MAIN_RING[1], MAIN_RING[2] - 0.05), 6.1, 7.45, 3.4, 14, seed=41)
    torn_socket(a, "CoreArmorSocket", (CORE[0], CORE[1], 24.9), 5.5, 6.4, 2.6, 12, seed=51, base_h=0.6)
