"""SiegeCrawler: the enemy land fortress (boss). Twin-belt track units under
armoured sponsons, a hull with a dozer plow, a casemate superstructure
with a command tower and exhaust box, a central heavy cannon and two
twin-autocannon sponson turrets. Dark gunmetal with red markings, hazard
stripes and emblems.

Asset origin = ground centre. ~96 studs long with the gun.
Parts / models (docs/ASSET_CONTRACTS.md):
  Root (hull), TrackL, TrackR, Deck (superstructure, tower, exhaust box)
  TurretLeft / TurretRight  (Models, WorldPivot at their rings, attachment Muzzle)
  MainCannon (Model, WorldPivot at its ring; parts CannonTurret, CannonBarrel,
              CannonGlow (Neon sphere at the muzzle, starts transparent); attachment Muzzle)
  Core (Neon reactor, hidden under) CoreArmor (armoured dome that is blown off)
  Beacons (Neon red warning lights)

HS-5 hard-surface pass (tooling from HS-3): sloped glacis with reactive
bricks and vision blocks, a curved dozer blade with teeth and push arms,
bolted spaced-armour skirt modules, raised side-turret platforms, a
faceted casemate with louvred intakes, a command tower with vision slits,
cupola and mast, an armoured exhaust box with shielded stacks, and a
faceted main turret with spaced cheek plates. Hull, skirts, deck and
turrets are baked from high-poly copies (rounded edges, bolts, welds) with
chips, grime, dust, soot and chipped markings; the twin-belt tracks and
all crew-scale kit (rails, ladders, hatches' periscopes, jerrycans, tools,
grilles, searchlights) use the shared TrimEnemy sheet at its own density,
which is what makes the scale read. Every contract part keeps its old
bounding box (`HIT`, locked by the build). New non-hittable parts:
Skirts, HullKit, DeckKit, MainCannon/CannonKit, TurretLeft/TurretLeftKit,
TurretRight/TurretRightKit, and four hidden torn-metal sockets
(<WeakPoint>Socket) that SiegeCrawler.luau reveals when a weak point is
thrown off. Turrets, core and sockets: models/siege_crawler_turrets.py.
"""
import math

import bmesh
from mathutils import Vector

from rmh import geo, hardsurface as hs, images, trim
from rmh.asset import Asset, fix_inside_out, rb_box

from models import siege_crawler_turrets as turrets

# Contract hit boxes: Roblox (centre, size) of the pre-HS-5 parts.
HIT = {
    "Root": ((0.0, 10.3389, -0.6339), (43.5315, 18.3223, 91.198)),
    "TrackL": ((-15.5, 5.9875, 1.5), (9.6, 12.275, 78.9374)),
    "TrackR": ((15.5, 5.9875, 1.5), (9.6, 12.275, 78.9374)),
    "Deck": ((-0.05, 32.5, 2.9885), (21.9, 27.0, 66.2171)),
    "CannonTurret": ((0.0, 22.9, -13.356), (17.4364, 7.8, 18.6452)),
    "CannonBarrel": ((0.0, 22.6, -37.45), (4.5, 4.4, 29.9)),
    "TurretLeftBody": ((-15.2, 19.05, -24.7), (7.2, 4.1, 16.6)),
    "TurretRightBody": ((15.2, 19.05, -24.7), (7.2, 4.1, 16.6)),
    "Core": ((0.0, 27.2, 21.0), (6.4672, 6.8, 6.8)),
    "CoreArmor": ((0.0, 28.4, 21.0), (13.8, 7.2, 13.8)),
}
TRACK_X = 15.5
DECK_Z = 19.0
SPONSON_Z = 13.8
PLATFORM_Z = 16.4
ROOF_Z = 25.5
MAIN_RING = (0.0, 12.0, 19.0)
SIDE_RING = (15.2, 20.0, 16.4)
CORE = (0.0, -21.0, 27.2)
PAINT = "#3e4247"
DARK = "#2b2d31"
RED = "#b01c18"
HAZARD = "#c9a227"
DUST = "#a4876a"
CAKED = "#8e7556"
STACKS = [(5.9, -31.4), (8.4, -31.4)]
STACK_TOP = 34.6
TOWER = (-6.1, -31.4)
TOWER_TOP = 33.2
BELTS = (-2.55, 2.6)  # belt centres relative to TRACK_X (outer first for the left side)
BELT_W = 4.3


def materials(a):
    photo = {"id": "green_metal_rust", "scale": 7.0, "color": 0.5, "sat": 0.1, "rough": 0.45, "height": 0.25}
    paint = dict(kind="paint", color=PAINT, rough=0.5, wear=0.55, under="#8b8c89", under_metal=0.8, under_rough=0.35,
                 chip_style="blotch", chip_scale=3.6, chip_bevel=0.16, ring=0.3, ring_color="#24201c",
                 edge_convex=True, edge_convex_distance=0.45, polish=0.3, grime=0.65, streaks=0.5, dust=0.6,
                 dust_up=0.35, dust_height=7.5, dust_color=DUST, dust_caked=0.8, caked_height=5.2, caked_color=CAKED,
                 rough_breakup=0.3, photo=photo, fade=0.25, fade_color="#5d6166", bevel=0.12)
    soot = [{"pos": (x, y, STACK_TOP), "dir": (0.1, -0.2, 1.0), "radius": 1.0, "length": 3.0, "spread": 0.3} for x, y in STACKS]
    soot += [{"pos": (x, y, 27.0), "dir": (0.0, 0.0, -1.0), "radius": 1.6, "length": 2.2, "spread": 0.5, "strength": 0.6} for x, y in STACKS]
    soot += [{"pos": (10.6, -31.4, 26.8), "dir": (1.0, 0.0, -0.4), "radius": 1.2, "length": 4.0, "spread": 0.5, "strength": 0.7}]
    soot += [{"pos": (s * 6.0, -44.6, 13.0), "dir": (0.0, -0.4, -1.0), "radius": 1.2, "length": 4.0, "spread": 0.4, "strength": 0.7} for s in (-1, 1)]
    a.material("hull", **paint, soot=soot)
    a.material("hull_dark", **dict(paint, color=DARK, photo=None, fade=0.1), soot=soot)
    a.material("skirt", **dict(paint, dust=0.8, dust_height=9.0, caked_height=7.0))
    a.material("blade", **dict(paint, color="#35383c", wear=0.8, chip_scale=2.6, dust=0.8, dust_height=6.0, caked_height=4.5,
                                under="#6f6c68", ring=0.5, ring_color="#3a2618"))
    a.material("deck", **dict(paint, dust_up=0.5, dust_height=0.0, dust_caked=0.0), soot=soot)
    a.material("deck_dark", **dict(paint, color=DARK, photo=None, dust_up=0.5, dust_height=0.0, dust_caked=0.0), soot=soot)
    a.material("stack", kind="metal", color="#3a332e", rough=0.6, metal=0.7, dust=0.2, grime=0.9, edge_convex=True,
               polish=0.2, soot=soot, rough_breakup=0.4, streaks=0.7, grime_color="#2a1c14")
    a.material("rust", kind="metal", color="#4f3d31", rough=0.62, metal=0.6, grime=0.9, dust=0.4, dust_height=6.0,
               edge_convex=True, polish=0.5, rough_breakup=0.3)
    a.material("glass", kind="flat", color="#1c2226", rough=0.08, metal=0.2)
    a.material("steel", kind="metal", color="#3a3b3c", rough=0.45, metal=0.9, dust=0.3, grime=0.6, edge_convex=True, polish=0.6)
    turrets.materials(a, paint)


# --- helpers ---------------------------------------------------------------------------

def yprism(section, y0, y1):
    """Extrude an (x, z) section from y0 to y1 (closed shell)."""
    bm = geo.prism(section, y1 - y0, bevel=0.0)
    for v in bm.verts:
        x, z, d = v.co.x, v.co.y, v.co.z
        v.co = Vector((x, (y0 + y1) / 2 + d, z))
    bmesh.ops.reverse_faces(bm, faces=bm.faces)  # the remap mirrors the shell
    bm.normal_update()
    return bm


def solid(bm):
    """Turn a closed shell outward now (geo.side_prism returns it inside-out),
    so texel functions see the real face normals."""
    bm.faces.index_update()
    fix_inside_out(bm)
    return bm


def mirror_pts(pts):
    return [(-x, y) for x, y in reversed(pts)]


def box_at(p, size, mat, at, rot=(0, 0, 0), bevel=0.0, **kw):
    p.add(geo.box(*size, bevel=bevel, segments=1), mat, at=at, rot=rot, **kw)


# --- hull ------------------------------------------------------------------------------

HULL_PROFILE = [(-43.6, 5.0), (36.5, 5.0), (44.6, 10.0), (45.3, 11.4), (33.0, DECK_Z), (-38.5, DECK_Z), (-44.2, 15.0), (-44.2, 7.0)]
SPONSON = [(-41.6, 12.3), (37.6, 12.3), (40.6, 10.9), (41.1, 11.3), (38.2, SPONSON_Z), (-41.6, SPONSON_Z)]
PLATFORM_LO = [(10.5, 3.0), (20.4, 3.0), (20.4, 28.0), (17.6, 31.6), (10.5, 31.6)]
PLATFORM_HI = [(10.5, 4.6), (19.0, 4.6), (19.0, 27.4), (17.0, 29.8), (10.5, 29.8)]


def hull(a):
    lo, hi = rb_box(*HIT["Root"])
    p = a.part("Root", tex="hull", material="Metal", smooth_angle=35, hitbox=(lo, hi))
    # Lower hull between the tracks: its flanks hide behind the tracks.
    body = solid(geo.side_prism(HULL_PROFILE, 21.0, bevel=0.0))
    # Cut the deck where the casemate and the turret collar cover it: those
    # faces are never seen and get almost no texture.
    for y in (-35.9, 1.6, 4.7, 19.3):
        bmesh.ops.bisect_plane(body, geom=list(body.verts) + list(body.edges) + list(body.faces), plane_co=(0, y, 0), plane_no=(0, 1, 0))

    def hidden(f):
        c = f.calc_center_median()
        if abs(f.normal.x) > 0.7 and c.z < 12.2:
            return 0.08
        if f.normal.z > 0.7 and c.z > DECK_Z - 0.1 and (-35.9 < c.y < 1.6 or 4.7 < c.y < 19.3):
            return 0.08
        return 1.0

    p.add(body, "hull", texel=hidden)
    for side in (-1, 1):
        # Sponson (track guard) with a chamfered outer edge and a sloped fender nose.
        sp = solid(geo.side_prism(SPONSON, 10.1, bevel=0.0))
        hs.chamfer_edges(sp, lambda e: all(abs(v.co.x) > 4.9 and v.co.z > SPONSON_Z - 0.05 for v in e.verts), 0.5)
        for y in (3.0, 31.6):
            bmesh.ops.bisect_plane(sp, geom=list(sp.verts) + list(sp.edges) + list(sp.faces), plane_co=(0, y, 0), plane_no=(0, 1, 0))

        def under(f):
            c = f.calc_center_median()
            if f.normal.z < -0.6 or (f.normal.z > 0.7 and 3.0 < c.y < 31.6):
                return 0.08  # belly, or covered by the turret platform
            return 0.6 if abs(f.normal.x) > 0.8 else 1.0

        p.add(sp, "hull", at=(side * 15.55, 0, 0), texel=under)
        # Upper hull sides lean in above the sponson (behind the turret platforms).
        wedge = [(10.5, SPONSON_Z), (12.3, SPONSON_Z), (10.5, DECK_Z)]
        p.add(yprism(wedge if side > 0 else [(-x, z) for x, z in reversed(wedge)], -38.5, 3.0), "hull", texel=0.75)
        # Raised side-turret platform with sloped outer and front faces.
        lo_pts = PLATFORM_LO if side > 0 else mirror_pts(PLATFORM_LO)
        hi_pts = PLATFORM_HI if side > 0 else mirror_pts(PLATFORM_HI)
        p.add(geo.tapered_prism(lo_pts, hi_pts, SPONSON_Z - 0.02, PLATFORM_Z), "hull")
        rx, ry, rz = side * SIDE_RING[0], SIDE_RING[1], SIDE_RING[2]
        p.add(geo.cylinder(4.1, 0.6, verts=28, bevel=0.0), "hull_dark", at=(rx, ry, rz + 0.3))
        p.detail(hs.bolt_row((rx - 3.3, ry - 2.6, rz + 0.62), (rx + 3.3, ry - 2.6, rz + 0.62), 1, (0, 0, 1), r=0.1, h=0.06), "hull_dark")
        for k in range(12):
            ang = 2 * math.pi * k / 12
            p.detail(hs.bolt((0.1), 0.07), "hull_dark", at=(rx + 3.8 * math.cos(ang), ry + 3.8 * math.sin(ang), rz + 0.6))
        # Weld seams along the platform joints and the sponson edge.
        p.detail(hs.weld([(side * 10.55, 3.1, SPONSON_Z + 0.05), (side * 10.55, 3.1, PLATFORM_Z - 0.05)], r=0.09), "hull")
        p.detail(hs.weld([(side * 12.2, -38.0, SPONSON_Z + 0.04), (side * 12.2, 2.8, SPONSON_Z + 0.04)], r=0.08), "hull")
        p.detail(hs.weld([(side * 10.52, -38.0, DECK_Z - 0.06), (side * 10.52, 2.8, DECK_Z - 0.06)], r=0.08), "hull")
        # Stowage bins on the sponson behind the platform, bolted lids.
        for y0, ln in ((-38.5, 7.0), (-29.8, 7.0), (-9.6, 8.5)):
            bx = side * 16.6
            box_at(p, (5.4, ln, 1.4), "hull_dark", (bx, y0 + ln / 2, SPONSON_Z + 0.7), texel=0.6)
            p.detail(hs.bolt_row((bx - side * 2.4, y0 + 0.4, SPONSON_Z + 1.42), (bx - side * 2.4, y0 + ln - 0.4, SPONSON_Z + 1.42), 6, (0, 0, 1), r=0.08, h=0.05), "hull_dark")
            p.detail(hs.weld([(bx + side * 2.7, y0, SPONSON_Z + 0.04), (bx + side * 2.7, y0 + ln, SPONSON_Z + 0.04)], r=0.07), "hull_dark")
            for hy in (y0 + 1.2, y0 + ln - 1.2):
                box_at(p, (0.25, 0.9, 0.35), "hull_dark", (bx + side * 2.8, hy, SPONSON_Z + 1.05))
        # Engine air intakes on the rear sponson (louvres in the kit).
        box_at(p, (5.6, 9.2, 0.35), "hull_dark", (side * 16.0, -18.2, SPONSON_Z + 0.17))
    glacis(p)
    rear(p)
    # Deck plate edges and the driver's hatch area in front of the turret.
    for side in (-1, 1):
        p.add(geo.cylinder(1.25, 0.35, verts=18, bevel=0.0), "hull_dark", at=(side * 4.2, 28.4, DECK_Z + 0.17))
        p.add(geo.box(2.2, 0.6, 0.35, bevel=0.0), "hull_dark", at=(side * 4.2, 29.9, DECK_Z + 0.2))
        p.detail(hs.bolt_row((side * 3.2, 27.0, DECK_Z + 0.36), (side * 5.2, 27.0, DECK_Z + 0.36), 4, (0, 0, 1), r=0.07, h=0.04), "hull_dark")
    p.detail(hs.weld([(-10.3, 32.9, DECK_Z - 0.02), (10.3, 32.9, DECK_Z - 0.02)], r=0.09), "hull")
    for side in (-1, 1):
        a.attach("Headlight", "Root", (side * 18.3, 40.0, 13.75), axis=(0, 1, -0.12))


GLACIS_SLOPE = math.degrees(math.atan2(DECK_Z - 11.4, 45.3 - 33.0))
GLACIS_N = Vector((0.0, math.sin(math.radians(GLACIS_SLOPE)), math.cos(math.radians(GLACIS_SLOPE))))


def on_glacis(x, y, off):
    """Point `off` studs out from the upper glacis surface at (x, y)."""
    z = 11.4 + (45.3 - y) * (DECK_Z - 11.4) / (45.3 - 33.0)
    return Vector((x, y, z)) + GLACIS_N * off


def glacis(p):
    # Reactive armour bricks in two rows on the upper glacis.
    tilt = (-GLACIS_SLOPE, 0, 0)
    for y in (42.3, 38.9):
        for i in range(6):
            x = -7.5 + i * 3.0
            p.add(geo.box(2.7, 2.9, 0.7, bevel=0.0), "hull_dark", at=tuple(on_glacis(x, y, 0.33)), rot=tilt)
            p.detail(hs.bolt_row(on_glacis(x - 0.9, y, 0.69), on_glacis(x + 0.9, y, 0.69), 2, GLACIS_N, r=0.09, h=0.05), "hull_dark")
    # Driver's vision block housings (periscopes in the kit).
    for side in (-1, 1):
        p.add(geo.tapered_box(3.0, 1.6, 1.1, top_scale=(0.85, 0.6), top_shift=(0, -0.2), bevel=0.0), "hull_dark",
              at=tuple(on_glacis(side * 4.6, 35.4, 0.5)), rot=tilt)
    # Nose plate: tow shackle mounts and a weld bead along the glacis joint.
    for side in (-1, 1):
        p.add(geo.box(1.4, 0.9, 1.4, bevel=0.0), "hull_dark", at=(side * 7.6, 44.8, 10.6))
        p.add(geo.torus(0.7, 0.2, verts=12, ring_verts=5), "steel", at=(side * 7.6, 45.2, 10.2), rot=(0, 90, 0))
    p.detail(hs.weld([(-10.4, 45.25, 11.35), (10.4, 45.25, 11.35)], r=0.1), "hull")
    p.detail(hs.weld([(-10.4, 44.55, 10.0), (10.4, 44.55, 10.0)], r=0.1), "hull")


def rear(p):
    # Rear plate: exhaust grille frames, tail lamps, tow pintle, jerrycan shelf.
    for side in (-1, 1):
        p.add(geo.box(7.0, 0.35, 2.8, bevel=0.0), "hull_dark", at=(side * 5.6, -44.3, 12.4))
        p.add(geo.box(0.9, 0.3, 0.5, bevel=0.0), "hull_dark", at=(side * 9.0, -44.3, 8.2))
    p.add(geo.box(3.2, 0.7, 1.2, bevel=0.0), "hull_dark", at=(0, -44.5, 6.6))
    p.add(geo.torus(0.6, 0.18, verts=12, ring_verts=5), "steel", at=(0, -44.75, 6.0), rot=(90, 0, 0))
    p.add(geo.box(14.0, 0.8, 0.3, bevel=0.0), "hull_dark", at=(0, -44.55, 9.4))


# --- skirts and plow (own atlas, not hittable: inside Root's box) ---------------------

def skirts(a):
    p = a.part("Skirts", tex="armour", material="Metal", query=False, smooth_angle=35)
    y0, length, gap = -40.4, 8.25, 0.3
    # Battle-worn: modules hang a little unevenly, one on the left is gone.
    drop = {(-1, 2): 0.35, (-1, 6): 0.25, (1, 1): 0.3, (1, 4): 0.4, (1, 7): 0.2}
    for side in (-1, 1):
        for i in range(9):
            if (side, i) == (-1, 5):
                continue
            ya = y0 + i * (length + gap)
            yb = ya + length
            front = i == 8
            thick = 0.55 if i >= 7 else 0.4
            zt, zb = 13.4, 4.6 - drop.get((side, i), 0.0)
            prof = [(ya, zb), (yb - 2.6, zb), (yb, 7.6), (yb, zt), (ya, zt)] if front else [(ya, zb), (yb, zb), (yb, zt), (ya, zt)]
            panel = solid(geo.side_prism(prof, thick, bevel=0.0))
            x = side * (20.65 + (0.08 if i >= 7 else 0.0))
            inner = lambda f, sd=side: 0.12 if f.normal.x * sd < -0.5 else 1.0  # noqa: E731
            p.add(panel, "skirt", at=(x, 0, 0), texel=inner)
            xo = x + side * thick / 2
            n = 6
            p.detail(hs.bolt_row((xo, ya + 0.5, zt - 0.5), (xo, yb - 0.5, zt - 0.5), n, (side, 0, 0), r=0.13, h=0.08), "skirt")
            p.detail(hs.bolt_row((xo, ya + 0.5, zb + 0.5), (xo, (yb - 3.0 if front else yb - 0.5), zb + 0.5), n - (2 if front else 0),
                                 (side, 0, 0), r=0.12, h=0.07), "skirt")
            # Hanger brackets to the sponson.
            for hy in (ya + 1.6, yb - 1.6):
                p.add(geo.box(0.6, 0.8, 0.8, bevel=0.0), "hull_dark", at=(side * 20.35, hy, 13.0))
            if i >= 7:  # applique plates on the front modules
                p.detail(geo.box(0.12, length * 0.62, 3.4, bevel=0.0), "skirt", at=(xo + side * 0.06, (ya + yb) / 2 - 0.4, 9.8))
            if i in (3, 4):  # a stiffening rib on the middle modules
                p.detail(hs.weld([(xo, ya + 0.3, 9.0), (xo, yb - 0.3, 9.0)], r=0.1), "skirt")
        # Emblem on the middle module, chipped; hazard stripe on the front one.
        a.decal(images.get("emblem"), (side * 21.0, -2.1, 9.0), (side, 0, 0), (6.0, 6.0, 1.6), color=RED, wear=0.3, seed=7 + side)
        hs.stencil(a, "01", (side * 21.0, 30.6, 10.8), (side, 0, 0), 2.4, color=RED, wear=0.3, chip=0.35, seed=9 + side)
    plow(a, p)


def plow(a, p):
    """Curved dozer blade across the nose with teeth, ribs and push arms."""
    n = 10
    front, back = [], []
    for k in range(n + 1):
        t = k / n
        z = 1.35 + 7.0 * t
        y = 46.05 - 1.1 * t - 0.95 * math.sin(math.pi * t) + (0.35 * max(0.0, t - 0.85) / 0.15)
        front.append((y, z))
        back.append((y - 0.75, z))
    prof = front + list(reversed(back))
    blade = solid(geo.side_prism(prof, 43.0, bevel=0.0))
    p.add(blade, "blade", texel=lambda f: 0.35 if f.normal.y < -0.5 else 1.0)
    # Ribs on the back of the blade and a top beam.
    for x in (-18.0, -9.0, 0.0, 9.0, 18.0):
        rib = [(45.2, 1.6), (45.2, 8.0), (43.4, 7.0), (42.9, 2.4)]
        p.add(geo.side_prism(rib, 0.6, bevel=0.0), "blade", at=(x, 0, 0))
    p.add(geo.box(43.0, 0.9, 0.7, bevel=0.0), "blade", at=(0, 44.95, 8.45))
    # Cutting edge with bolted teeth.
    p.add(geo.box(43.0, 0.5, 0.45, bevel=0.0), "rust", at=(0, 45.9, 1.45))
    for i in range(14):
        x = -19.5 + i * 3.0
        tooth = geo.tapered_box(1.1, 0.7, 1.2, top_scale=(0.6, 0.8), bevel=0.0)
        p.add(tooth, "rust", at=(x, 45.85, 1.18), rot=(180, 0, 0))
        p.detail(hs.bolt((0.1), 0.06), "rust", at=(x, 46.12, 1.7), rot=(-90, 0, 0))
    # Push arms and hydraulic rams back to the hull belly.
    for side in (-1, 1):
        arm = [(44.4, 2.6), (44.4, 4.2), (37.2, 5.6), (37.2, 4.2)]
        p.add(geo.side_prism(arm, 1.3, bevel=0.0), "blade", at=(side * 8.5, 0, 0))
        x = side * 13.0
        p.add(geo.pipe_path([(x, 44.0, 6.1), (x, 41.2, 6.25)], 0.4, verts=10), "steel")
        p.add(geo.pipe_path([(x, 41.6, 6.24), (x, 38.4, 6.4)], 0.62, verts=10), "rust")
    # Hazard stripes along the top of the blade, chipped.
    a.decal(images.get("stripes", count=10, angle=45), (0, 45.5, 7.4), (0, 1, 0.25), (40.0, 1.7, 3.0), color=HAZARD, wear=0.45, seed=13)


# --- tracks (trim) ---------------------------------------------------------------------

def belt_profile():
    pts = [(-34.4, 0.05), (31.7, 0.05)]
    ic, ir = (32.35, 6.2), 5.6
    for k in range(9):
        t = math.radians(-80 + k * 21.25)
        pts.append((ic[0] + ir * math.cos(t), ic[1] + ir * math.sin(t)))
    for y in (24.0, 14.0, 4.0, -6.0, -16.0, -26.0):
        pts.append((y, 11.55 if y % 20 == 4 else 11.75))
    sc, sr = (-35.0, 6.1), 5.9
    for k in range(9):
        t = math.radians(90 + k * 21.25)
        pts.append((sc[0] + sr * math.cos(t), sc[1] + sr * math.sin(t)))
    return pts


def track_side(a, T, side):
    name = "TrackL" if side < 0 else "TrackR"
    lo, hi = rb_box(*HIT[name])
    p = a.part(name, tex="trim", material="Metal", smooth_angle=50, hitbox=(lo, hi))
    prof = belt_profile()
    face = (0, 90 * side, 0)  # template axle +Z -> outward X
    for k, off in enumerate(BELTS):
        x = side * (TRACK_X - off) if side < 0 else side * (TRACK_X + off)
        outer = k == 0
        band = geo.band_loop(prof, 0.42, BELT_W)
        T.loop(band, "track", prof, width_axis=0, periods=5)
        p.add(band, "trim", at=(x, 0, 0))
        wheel_s = (2.1, 2.1, 3.1)
        stations = (-27.0, -18.2, -9.4, -0.6, 8.2, 17.0, 25.0) if outer else (17.0, 25.0)
        for y in stations:
            p.add(T.template("roadwheel"), "trim", at=(x, y, 2.98), rot=face, scale=wheel_s)
        p.add(T.template("sprocket"), "trim", at=(x, -35.0, 6.1), rot=face, scale=(4.25, 4.25, 3.4))
        p.add(T.template("roadwheel"), "trim", at=(x, 32.35, 6.2), rot=face, scale=(4.2, 4.2, 3.2))


# --- hull kit (trim, not hittable) -----------------------------------------------------

def hull_kit(a, T):
    k = a.part("HullKit", tex="trim", material="Metal", query=False, smooth_angle=50)
    for side in (-1, 1):
        # Headlight pair on each fender nose, in a mesh guard.
        for dx in (-1.1, 1.1):
            k.add(T.template("headlight"), "trim", at=(side * 17.2 + side * dx, 39.3, 13.75), rot=(-6, 0, 0), scale=(2.2, 2.2, 2.2))
        for gx in (-2.35, 0.0, 2.35):
            bar = geo.box(0.12, 1.4, 1.7, bevel=0.0)
            T.planar(bar, "mesh", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
            k.add(bar, "trim", at=(side * 17.2 + gx, 40.1, 13.75))
        top = geo.box(4.8, 1.4, 0.12, bevel=0.0)
        T.planar(top, "mesh", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
        k.add(top, "trim", at=(side * 17.2, 40.1, 14.65))
        brace = geo.box(4.8, 0.9, 0.9, bevel=0.0)
        T.fill(brace, "plain")
        k.add(brace, "trim", at=(side * 17.2, 39.0, 13.0))
        # Driver's periscopes on the vision block housings.
        for dx in (-0.8, 0.0, 0.8):
            k.add(T.template("periscope"), "trim", at=tuple(on_glacis(side * 4.6 + dx, 35.2, 1.02)), rot=(-GLACIS_SLOPE * 0.5, 0, 0),
                  scale=(1.4, 1.4, 1.4))
        # Engine air intake louvres on the rear sponson.
        g = geo.box(5.2, 8.8, 0.1, bevel=0.0)
        T.planar(g, "grille", u_axis=(0, 1, 0), v_axis=(1, 0, 0))
        k.add(g, "trim", at=(side * 16.0, -18.2, SPONSON_Z + 0.4))
        # Jerrycans in a rack behind the turret platform (crew scale).
        for i in range(4):
            k.add(T.template("jerrycan_red" if i % 3 == 0 else "jerrycan_dark"), "trim",
                  at=(side * (12.75 + i * 1.25), 1.95, SPONSON_Z), rot=(0, 0, 0))
        strap = geo.box(5.2, 0.08, 0.2, bevel=0.0)
        T.fill(strap, "bolted")
        k.add(strap, "trim", at=(side * 14.65, 1.05, SPONSON_Z + 0.95))
        # Tools in clamps on a bin lid, a tow cable along the walkway.
        lid = SPONSON_Z + 1.4
        k.add(T.template("shovel"), "trim", at=(side * 17.8, -26.3, lid), rot=(0, 0, 0))
        k.add(T.template("pickaxe"), "trim", at=(side * 16.0, -26.3, lid), rot=(0, 0, 90))
        k.add(T.template("crowbar"), "trim", at=(side * 18.8, -26.3, lid), rot=(0, 0, 0))
        for cy in (-27.6, -25.0):
            clamp = geo.box(3.6, 0.2, 0.3, bevel=0.0)
            T.fill(clamp, "bolted")
            k.add(clamp, "trim", at=(side * 17.5, cy, lid + 0.2))
        for dx in (0.0, 0.42):
            cx = side * (13.2 + dx)
            c = geo.pipe_path([(cx, -12.0, SPONSON_Z + 0.18), (cx, 0.6, SPONSON_Z + 0.18)], 0.16, verts=6)
            T.cylindrical(c, "cable", axis=(0, 1, 0), center=(cx, 0, SPONSON_Z + 0.18), along=True)
            k.add(c, "trim")
        # Ammo boxes on the platform's rear corner.
        for i in range(2):
            k.add(T.template("ammo_can"), "trim", at=(side * (17.6 + i * 0.7), 5.6, PLATFORM_Z), rot=(0, 0, 0), scale=(1.2, 1.2, 1.2))
        # Hand rail round the side-turret platform.
        r = hs.rail([(side * 18.6, 5.2, PLATFORM_Z + 2.4), (side * 18.6, 26.6, PLATFORM_Z + 2.4)], r=0.09, feet=True, foot_h=2.4)
        T.fill(r, "plain")
        k.add(r, "trim")
        # Mud flap behind the fender nose.
        flap = geo.box(9.0, 0.12, 2.0, bevel=0.0)
        T.planar(flap, "canvas", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
        k.add(flap, "trim", at=(side * 15.55, 38.2, 11.3))
    # Spare track links on the upper glacis between the brick rows.
    for x in (-5.0, 5.0):
        for j in range(2):
            y = 40.6 - j * 1.45
            link = hs.track_link(width=BELT_W, pitch=1.35, thick=0.3)
            T.planar(link, "track", u_axis=(0, 1, 0), v_axis=(1, 0, 0), fit=True)
            k.add(link, "trim", at=tuple(on_glacis(x, y, 0.02)), rot=(-GLACIS_SLOPE, 0, 0))
    # Rear: exhaust louvres in the grille frames, spare links, jerrycans.
    for side in (-1, 1):
        g = geo.box(6.4, 0.1, 2.3, bevel=0.0)
        T.planar(g, "grille", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
        k.add(g, "trim", at=(side * 5.6, -44.52, 12.4))
    for x in (-3.0, -1.6, 1.6, 3.0):
        k.add(T.template("jerrycan_dark"), "trim", at=(x, -44.6, 9.55), rot=(0, 0, 90))
    for x in (-8.2, 8.2):
        link = hs.track_link(width=BELT_W, pitch=1.35, thick=0.3)
        T.planar(link, "track", u_axis=(0, 1, 0), v_axis=(1, 0, 0), fit=True)
        k.add(link, "trim", at=(x, -44.55, 6.8), rot=(90, 0, 0))
    # Rear engine-deck louvres on the upper rear slope.
    rs = math.degrees(math.atan2(DECK_Z - 15.0, 44.2 - 38.5))
    g = geo.box(18.0, 5.2, 0.1, bevel=0.0)
    T.planar(g, "grille", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
    k.add(g, "trim", at=(0, -41.3, 17.1), rot=(rs, 0, 0))


# --- deck: superstructure, command tower, exhaust box --------------------------------

SUPER_LO = [(-10.4, -35.9), (10.4, -35.9), (10.4, -2.0), (8.0, 1.6), (-8.0, 1.6), (-10.4, -2.0)]
SUPER_HI = [(-8.8, -34.4), (8.8, -34.4), (8.8, -3.2), (6.8, -0.2), (-6.8, -0.2), (-8.8, -3.2)]
TOWER_LO = [(-10.2, -35.6), (-2.0, -35.6), (-2.0, -28.8), (-3.4, -27.4), (-8.8, -27.4), (-10.2, -28.8)]
TOWER_HI = [(-9.7, -35.1), (-2.5, -35.1), (-2.5, -29.1), (-3.7, -27.9), (-8.5, -27.9), (-9.7, -29.1)]


def deck(a):
    lo, hi = rb_box(*HIT["Deck"])
    p = a.part("Deck", tex="deck", material="Metal", smooth_angle=35, hitbox=(lo, hi))
    p.add(geo.tapered_prism(SUPER_LO, SUPER_HI, DECK_Z, ROOF_Z), "deck", texel=lambda f: 0.12 if f.normal.z < -0.6 else 1.0)
    # Weld seams along the casemate's facet joints.
    for (bx, by), (tx, ty) in zip(SUPER_LO, SUPER_HI):
        p.detail(hs.weld([(bx, by, DECK_Z + 0.05), (tx, ty, ROOF_Z - 0.05)], r=0.08), "deck")
    for side in (-1, 1):
        # Louvred intake frames on the casemate flanks (louvres in the kit).
        for y in (-24.0, -12.0):
            p.add(geo.box(0.3, 7.0, 3.4, bevel=0.0), "deck_dark", at=(side * 9.75, y, 22.2), rot=(0, side * -13.8, 0))
        # Crew hatches with hinges and handles on the roof.
        for hx, hy in ((side * 4.8, -8.4),):
            p.add(geo.cylinder(1.35, 0.35, verts=20, bevel=0.0), "deck_dark", at=(hx, hy, ROOF_Z + 0.17))
            p.add(geo.box(2.2, 0.6, 0.4, bevel=0.0), "deck_dark", at=(hx, hy - 1.5, ROOF_Z + 0.2))
            p.detail(geo.torus(0.35, 0.06, verts=10, ring_verts=4), "steel", at=(hx, hy + 0.7, ROOF_Z + 0.4), rot=(90, 0, 0))
        # Bolted applique plates along the casemate's lower flank.
        for y in (-31.0, -4.4):
            zc = 20.6
            xc = side * (10.4 - (zc - DECK_Z) * (1.6 / (ROOF_Z - DECK_Z)) + 0.2)
            p.add(geo.box(0.35, 4.6, 2.4, bevel=0.0), "deck_dark", at=(xc, y, zc), rot=(0, side * -13.8, 0))
            p.detail(hs.bolt_row((xc + side * 0.2, y - 1.9, zc + 0.85), (xc + side * 0.2, y + 1.9, zc + 0.85), 4, (side, 0, 0.24), r=0.1, h=0.06), "deck_dark")
            p.detail(hs.bolt_row((xc + side * 0.2, y - 1.9, zc - 0.85), (xc + side * 0.2, y + 1.9, zc - 0.85), 4, (side, 0, 0.24), r=0.1, h=0.06), "deck_dark")
        # Roof stowage boxes along the edges.
        box_at(p, (1.8, 7.5, 1.3), "deck_dark", (side * 6.9, -11.75, ROOF_Z + 0.65))
        p.detail(hs.bolt_row((side * 6.9, -15.2, ROOF_Z + 1.32), (side * 6.9, -8.3, ROOF_Z + 1.32), 5, (0, 0, 1), r=0.08, h=0.05), "deck_dark")
    p.detail(hs.weld([(-8.7, -2.9, ROOF_Z - 0.03), (8.7, -2.9, ROOF_Z - 0.03)], r=0.07), "deck")
    # Core cradle ring on the roof (the Core sits inside).
    cx, cy, _ = CORE
    p.add(geo.lathe([(6.3, -0.35), (7.5, -0.35), (7.6, 0.3), (7.0, 0.9), (6.3, 0.9)], verts=32), "deck_dark", at=(cx, cy, ROOF_Z))
    for k in range(16):
        ang = 2 * math.pi * k / 16
        p.detail(hs.bolt(0.11, 0.07), "deck_dark", at=(cx + 7.2 * math.cos(ang), cy + 7.2 * math.sin(ang), ROOF_Z + 0.52), rot=(0, 0, 0))
    # Coolant pipes from the cradle to the exhaust box.
    for dx in (-0.8, 0.8):
        p.add(geo.pipe_path([(cx + 5.5 + dx * 0.2, cy - 5.0 + dx, ROOF_Z + 0.4), (4.2, -29.0 + dx, ROOF_Z + 0.4),
                             (4.2, -30.2 + dx, ROOF_Z + 1.2)], 0.3, verts=8), "steel")
    tower(p)
    exhaust(p)


def tower(p):
    tx, ty = TOWER
    p.add(geo.tapered_prism(TOWER_LO, TOWER_HI, ROOF_Z - 0.02, TOWER_TOP), "deck")
    for (bx, by), (hx, hy) in zip(TOWER_LO, TOWER_HI):
        p.detail(hs.weld([(bx, by, ROOF_Z + 0.05), (hx, hy, TOWER_TOP - 0.05)], r=0.07), "deck")
    # Vision slit band with an armoured brow round the front facets.
    for (x0, y0), (x1, y1) in zip(TOWER_HI[2:5], TOWER_HI[3:6]):
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        ang = math.degrees(math.atan2(y1 - y0, x1 - x0))
        ln = math.hypot(x1 - x0, y1 - y0)
        nx, ny = math.sin(math.radians(ang)), -math.cos(math.radians(ang))
        p.add(geo.box(ln * 0.8, 0.2, 0.6, bevel=0.0), "glass", at=(mx + nx * 0.05, my + ny * 0.05, 30.9), rot=(0, 0, ang))
        p.add(geo.box(ln * 0.92, 0.7, 0.25, bevel=0.0), "deck_dark", at=(mx + nx * 0.3, my + ny * 0.3, 31.45), rot=(0, 0, ang))
    # Cupola and hatch on the roof.
    p.add(geo.cylinder(1.7, 0.9, verts=20, bevel=0.0), "deck", at=(tx + 1.0, ty + 0.4, TOWER_TOP + 0.45))
    p.add(geo.cylinder(1.35, 0.3, verts=20, bevel=0.0), "deck_dark", at=(tx + 1.0, ty + 0.2, TOWER_TOP + 1.05), rot=(-8, 0, 0))
    p.add(geo.cylinder(0.45, 1.0, verts=10, bevel=0.0), "deck_dark", at=(tx - 1.8, ty - 1.6, TOWER_TOP + 0.5))
    # Searchlight brackets (lamps in the kit).
    for dx in (-2.9, 2.2):
        p.add(geo.box(0.5, 0.8, 1.0, bevel=0.0), "deck_dark", at=(tx + dx, ty + 3.2, TOWER_TOP + 0.5))


def exhaust(p):
    # Armoured exhaust box on the right rear of the roof, louvres in the kit.
    box = geo.tapered_prism([(3.4, -35.6), (10.2, -35.6), (10.2, -26.8), (3.4, -26.8)],
                            [(3.9, -35.1), (9.6, -35.1), (9.6, -27.3), (3.9, -27.3)], ROOF_Z - 0.02, 28.2)
    p.add(box, "deck_dark")
    p.detail(hs.bolt_row((4.2, -27.2, 28.25), (9.3, -27.2, 28.25), 6, (0, 0, 1), r=0.08, h=0.05), "deck_dark")
    p.detail(hs.bolt_row((4.2, -35.0, 28.25), (9.3, -35.0, 28.25), 6, (0, 0, 1), r=0.08, h=0.05), "deck_dark")
    for x, y in STACKS:
        p.add(geo.tube(1.05, 0.75, STACK_TOP - 28.2, verts=16), "stack", at=(x, y, (28.2 + STACK_TOP) / 2))
        p.add(geo.cylinder(1.35, 0.6, verts=16, bevel=0.0), "stack", at=(x, y, 28.5))
        for z in (30.2, 32.6):
            p.add(geo.cylinder(1.12, 0.22, verts=16, bevel=0.0), "stack", at=(x, y, z))
        # Angled rain cap on each stack.
        p.add(geo.cylinder(1.15, 0.12, verts=16, bevel=0.0), "stack", at=(x, y - 0.4, STACK_TOP + 0.45), rot=(-35, 0, 0))


# --- deck kit (trim, not hittable) ------------------------------------------------------

def deck_kit(a, T):
    k = a.part("DeckKit", tex="trim", material="Metal", query=False, smooth_angle=50)
    tx, ty = TOWER
    for side in (-1, 1):
        # Intake louvres on the casemate flanks.
        for y in (-24.0, -12.0):
            g = geo.box(0.1, 6.4, 2.9, bevel=0.0)
            T.planar(g, "grille", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
            k.add(g, "trim", at=(side * 9.95, y, 22.2), rot=(0, side * -13.8, 0))
        # Catwalk rails along the roof edges.
        pts = [(side * 8.3, -25.6, ROOF_Z + 2.8), (side * 8.3, -3.0, ROOF_Z + 2.8)]
        r = hs.rail(pts, r=0.09, feet=True, foot_h=2.8)
        T.fill(r, "plain")
        k.add(r, "trim")
        r2 = geo.pipe_path([(side * 8.3, -25.6, ROOF_Z + 1.4), (side * 8.3, -3.0, ROOF_Z + 1.4)], 0.07, verts=6)
        T.fill(r2, "plain")
        k.add(r2, "trim")
        for y in (-18.0, -10.5):
            post = geo.cylinder(0.08, 2.8, verts=5, bevel=0.0)
            T.fill(post, "plain")
            k.add(post, "trim", at=(side * 8.3, y, ROOF_Z + 1.4))
        # Ladder from the sponson walkway up to the roof (crew scale: rungs every 1.1).
        ladder(k, T, side, -17.9)
        # Hatch periscopes.
        k.add(T.template("periscope"), "trim", at=(side * 4.8, -6.2, ROOF_Z + 0.35), scale=(1.4, 1.4, 1.4))
        # Jerrycans and ammo on the roof stowage.
        k.add(T.template("ammo_can"), "trim", at=(side * 6.9, -12.4, ROOF_Z + 1.3), rot=(0, 0, 90), scale=(1.2, 1.2, 1.2))
    # Tower cupola periscopes, searchlights, mast and whips.
    for i in range(7):
        ang = math.radians(90 + i * 51.4)
        k.add(T.template("periscope"), "trim", at=(tx + 1.0 + 1.55 * math.cos(ang), ty + 0.4 + 1.55 * math.sin(ang), TOWER_TOP + 0.85),
              rot=(0, 0, math.degrees(ang) - 90), scale=(1.2, 1.2, 1.2))
    for dx in (-2.9, 2.2):
        k.add(T.template("headlight"), "trim", at=(tx + dx, ty + 3.5, TOWER_TOP + 1.35), rot=(-4, 0, 0), scale=(2.6, 2.6, 2.6))
    mast = geo.cylinder(0.28, 12.2, verts=8, r_top=0.14, bevel=0.0)
    T.cylindrical(mast, "cable", axis=(0, 0, 1), along=True)
    k.add(mast, "trim", at=(tx - 1.8, ty - 1.6, TOWER_TOP + 1.0 + 6.1))
    for z, w in ((TOWER_TOP + 8.0, 3.4), (TOWER_TOP + 10.5, 2.2)):
        bar = geo.box(w, 0.14, 0.14, bevel=0.0)
        T.fill(bar, "plain")
        k.add(bar, "trim", at=(tx - 1.8, ty - 1.6, z))
    for dx, h in ((-3.4, 7.0), (0.6, 5.5)):
        w = hs.whip_antenna(height=h, base_r=0.16)
        T.cylindrical(w, "cable", axis=(0, 0, 1), along=True)
        k.add(w, "trim", at=(tx + dx, ty - 3.0, TOWER_TOP))
    # Exhaust box louvres and perforated heat shields on the stacks.
    for side_y in (-35.62, -26.78):
        g = geo.box(5.8, 0.1, 1.8, bevel=0.0)
        T.planar(g, "grille", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
        k.add(g, "trim", at=(6.8, side_y, 26.9))
    g = geo.box(0.1, 7.6, 1.8, bevel=0.0)
    T.planar(g, "grille", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
    k.add(g, "trim", at=(10.22, -31.2, 26.9))
    for x, y in STACKS:
        shield = geo.lathe([(1.3, 0.0), (1.3, 3.2)], verts=14, close_top=False, close_bottom=False, angle=math.pi)
        T.cylindrical(shield, "mesh", axis=(0, 0, 1), center=(0, 0, 0))
        k.add(shield, "trim", at=(x, y, 29.4), rot=(0, 0, 180))
    # Jerrycans and a tarp roll on the roof behind the core.
    for i in range(3):
        k.add(T.template("jerrycan_dark" if i else "jerrycan_red"), "trim", at=(-1.2 + i * 0.75, -33.4, ROOF_Z), rot=(0, 0, 90))
    roll = hs.tarp_roll(length=5.0, r=0.55, straps=3)
    T.cylindrical(roll, "canvas", axis=(1, 0, 0), faces=lambda f: abs(f.normal.x) < 0.7, along=True)
    T.fill(roll, "canvas", faces=lambda f: abs(f.normal.x) >= 0.7)
    k.add(roll, "trim", at=(0.6, -30.6, ROOF_Z))


def ladder(k, T, side, y):
    x0, x1 = side * 12.75, side * 9.35
    z0, z1 = SPONSON_Z, ROOF_Z + 0.4
    for dy in (-0.8, 0.8):
        s = geo.pipe_path([(x0, y + dy, z0), (x1, y + dy, z1)], 0.09, verts=6)
        T.fill(s, "plain")
        k.add(s, "trim")
    n = int((z1 - z0) / 1.1)
    for i in range(1, n + 1):
        t = i / (n + 1)
        rung = geo.cylinder(0.06, 1.6, verts=5, bevel=0.0)
        T.fill(rung, "plain")
        k.add(rung, "trim", at=(x0 + (x1 - x0) * t, y, z0 + (z1 - z0) * t), rot=(90, 0, 0))


def beacons(a):
    b = a.part("Beacons", neon=(1.0, 0.1, 0.08), material="Neon", query=False, shadow=False)
    tx, ty = TOWER
    for x, y, z in ((tx - 3.4, ty - 3.2, TOWER_TOP + 0.35), (tx + 3.2, ty - 3.2, TOWER_TOP + 0.35), (tx - 1.8, ty - 1.6, TOWER_TOP + 13.4),
                    (8.8, -34.2, ROOF_Z + 0.4), (-19.3, 5.2, PLATFORM_Z + 2.6), (19.3, 5.2, PLATFORM_Z + 2.6)):
        b.add(geo.sphere(0.45, 8, 5), "hull", at=(x, y, z))


def build(**kw):
    a = Asset("SiegeCrawler", pivot=(0, 0, 0), tex_size=1024)
    a.fix_inside_out = True
    a.preview_hide_transparent = True
    high = {"hp": 0.1, "cage": 0.22, "ray": 0.5}
    a.texture_group("hull", 1024, high=high, down=0.15, back=0.3, metal_px=512)
    a.texture_group("armour", 1024, high=high, down=0.15, back=0.3, metal_px=512)
    a.texture_group("deck", 1024, high=high, down=0.15, back=0.4, metal_px=512)
    a.texture_group("turrets", 1024, high=high, down=0.15, back=0.35, metal_px=512)
    T = trim.use(a, "trim", "TrimEnemy")
    a.pivot("MainCannon", MAIN_RING)
    a.pivot("TurretLeft", (-SIDE_RING[0], SIDE_RING[1], SIDE_RING[2]))
    a.pivot("TurretRight", SIDE_RING)
    materials(a)
    hull(a)
    skirts(a)
    hull_kit(a, T)
    track_side(a, T, -1)
    track_side(a, T, 1)
    deck(a)
    deck_kit(a, T)
    turrets.main_cannon(a, T, HIT)
    turrets.side_turret(a, T, HIT, -1)
    turrets.side_turret(a, T, HIT, 1)
    turrets.core(a, HIT)
    turrets.sockets(a)
    beacons(a)
    views = [("", (1.1, 1.3, 0.6)), ("_rear", (-1.2, -1.1, 0.7)), ("_side", (1.0, 0.05, 0.15)),
             ("_close_front", (0.7, 1.3, 0.55), ["CannonTurret", "CannonBarrel", "Deck"]),
             {"label": "_cam_player", "pos": (-60, 330, 62), "look": (0, 0, 14), "fov": 32, "res": (1280, 800)},
             {"label": "_cam_mid", "pos": (-55, 120, 42), "look": (0, 5, 15), "fov": 40, "res": (1280, 800)},
             {"label": "_sockets", "pos": (-40, 70, 70), "look": (0, 0, 18), "fov": 45, "res": (1280, 800),
              "hide": ["CannonTurret", "CannonBarrel", "CannonKit", "TurretLeftBody", "TurretLeftKit",
                       "TurretRightBody", "TurretRightKit", "CoreArmor"], "show": ["MainCannonSocket", "TurretLeftSocket",
                                                                                  "TurretRightSocket", "CoreArmorSocket"]}]
    return a.finish(views=views, **kw)
