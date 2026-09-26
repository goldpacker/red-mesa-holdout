"""TrimEnemy: the enemy force's shared trim sheet (HS-3). One 1024² set
used by the Tank and the Buggy (and the Helicopter/Jet in HS-4): tileable
strips for tracks, louvre grilles, mesh, bolted straps, canvas, wire rope
and plain worn paint, plus template meshes for road wheels, sprockets,
tyres, rims, jerrycans, ammo cans, tools, periscopes and headlights.

Build: tools/assets/build.sh TrimEnemy (texture-only; see rmh/trim.py).
Palette (art bible §2): gunmetal #3E4247, charcoal #2A2C30, near-black
#1A1B1E for rubber/grilles, marking red #BA1C18.
"""
import math

import bmesh
from mathutils import Vector

from rmh import geo, hardsurface as hs, trim

DUST = "#a88d6c"
CHAR = "#2c2e32"


def materials(s):
    worn = {"edge_convex": True, "rough_breakup": 0.25, "dust_color": DUST, "dust_up": 0.0, "dust_height": 0.001, "zmin": -5.0}
    s.material("trk_steel", kind="metal", color="#2b2b2a", rough=0.62, metal=0.8, polish=0.9, polish_radius=0.03,
               dust=0.0, grime=0.7, dust_cavity=0.55, dust_cavity_distance=0.25, dust_cavity_range=(0.2, 0.6), **{k: v for k, v in worn.items() if k != "zmin"})
    s.material("grille", kind="paint", color="#25272a", rough=0.6, wear=0.35, under="#6f706e", grime=0.9, dust=0.0,
               dust_cavity=0.35, dust_cavity_range=(0.25, 0.7), streaks=0.3, **worn)
    s.material("mesh", kind="metal", color="#2f3033", rough=0.55, metal=0.7, grime=0.8, dust=0.0, dust_cavity=0.25, dust_cavity_range=(0.25, 0.7), polish=0.5, **worn)
    s.material("strap", kind="paint", color=CHAR, rough=0.55, wear=0.45, under="#77797a", grime=0.7, dust=0.0,
               dust_cavity=0.35, chip_scale=11.0, **worn)
    s.material("canvas", kind="fabric", color="#3f3b31", rough=0.92, weave=34.0, weave_amount=0.35, wrinkle=0.4,
               dust=0.0, grime=0.6, dust_cavity=0.25, dust_color="#8d785c", zmin=-5.0,
               marks=[])
    s.material("cable", kind="metal", color="#3b3b39", rough=0.5, metal=0.85, grime=0.85, dust=0.0, dust_cavity=0.2, polish=0.6, **worn)
    s.material("plain", kind="paint", color=CHAR, rough=0.55, wear=0.4, under="#76787a", grime=0.5, dust=0.0,
               dust_cavity=0.3, chip_scale=8.0, **worn)
    s.material("red", kind="paint", color="#a41b17", rough=0.55, wear=0.45, under="#6e6c68", grime=0.4, dust=0.0,
               dust_cavity=0.2, chip_scale=9.0, **worn)
    # Template materials (object space of each template, not periodic).
    tw = {"edge_convex": True, "rough_breakup": 0.2, "dust_color": DUST}
    s.material("t_rubber", kind="rubber", color="#1c1b1a", rough=0.88, dust=0.35, dust_up=0.0, dust_height=0.001,
               dust_cavity=0.45, dust_cavity_distance=0.2, dust_cavity_range=(0.2, 0.6), grime=0.3, zmin=-5.0)
    s.material("t_wheel", kind="paint", color=CHAR, rough=0.5, wear=0.5, under="#7a7b7b", grime=0.7, dust=0.45,
               dust_up=0.0, dust_height=0.001, dust_cavity=0.4, dust_cavity_range=(0.15, 0.55), zmin=-5.0, chip_scale=10.0, **tw)
    s.material("t_red", kind="paint", color="#a41b17", rough=0.5, wear=0.55, under="#6e6c68", chip_style="blotch",
               chip_scale=6.0, chip_bevel=0.05, fade=0.25, fade_color="#b8574a", grime=0.6, dust=0.55, dust_up=0.6,
               dust_height=0.25, **tw)
    s.material("t_dark", kind="paint", color="#2e3034", rough=0.52, wear=0.5, under="#7a7b7b", chip_style="blotch",
               chip_scale=6.0, chip_bevel=0.05, grime=0.6, dust=0.55, dust_up=0.6, dust_height=0.25, **tw)
    s.material("t_ammo", kind="paint", color="#34372f", rough=0.55, wear=0.5, under="#7a7b7b", grime=0.6, dust=0.5,
               dust_up=0.6, dust_height=0.2, marks=[{"lo": (-1, -0.2, 0.3), "hi": (1, 0.2, 0.42), "color": "#a41b17"}], **tw)
    s.material("t_wood", kind="wood", color="#6a5237", rough=0.8, wear=0.2, grain="Y", dust=0.45, grime=0.6)
    s.material("t_steel", kind="metal", color="#4a4b4c", rough=0.45, metal=0.9, grime=0.6, dust=0.3, polish=0.7, **tw)
    s.material("t_glass", kind="flat", color="#1c2834", rough=0.08, metal=0.2, dust=0.35, dust_up=0.9, grime=0.2)
    s.material("t_lens", kind="flat", color="#d9d2b8", rough=0.12, metal=0.0, dust=0.3, grime=0.3)


# --- strip patterns (x along U over one period, y across, surface at z = 0) -------

def _grid(nx, ny, sx, sy, fz):
    bm = bmesh.new()
    rows = []
    for j in range(ny + 1):
        y = sy * j / ny
        rows.append([bm.verts.new((sx[0] + (sx[1] - sx[0]) * i / nx, y, fz((sx[0] + (sx[1] - sx[0]) * i / nx), y))) for i in range(nx + 1)])
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
    return bm


def _add(dst, bm, at=(0, 0, 0), rot=(0, 0, 0)):
    geo.transform(bm, at, rot)
    return hs._join(dst, bm)


def track(period, world, shoes=24):
    pitch = period / shoes
    bm = geo.box(period + 4 * pitch, world, 0.02, bevel=0.0)
    geo.transform(bm, (period / 2, world / 2, -0.17))
    for k in range(-2, shoes + 2):
        x = (k + 0.5) * pitch
        plate = geo.box(pitch * 0.84, world * 0.9, 0.11, bevel=0.025, segments=2)
        _add(bm, plate, (x, world / 2, -0.055))
        for dx in (-pitch * 0.22, pitch * 0.22):
            gr = geo.tapered_box(pitch * 0.14, world * 0.84, 0.1, top_scale=(0.7, 0.98), bevel=0.012, segments=2)
            _add(bm, gr, (x + dx, world / 2, 0.05))
        # Centre guide horn gap and a bolted pad in the middle.
        pad = geo.box(pitch * 0.3, world * 0.12, 0.03, bevel=0.008, segments=1)
        _add(bm, pad, (x, world / 2, 0.015))
        for side in (0, 1):
            y = world * (0.035 if side == 0 else 0.965)
            conn = geo.box(pitch * 0.46, world * 0.07, 0.15, bevel=0.015, segments=2)
            _add(bm, conn, (x + pitch * 0.5, y, -0.04))
            pin = geo.cylinder(0.045, world * 0.07 + 0.03, verts=8, bevel=0.0)
            _add(bm, pin, (x + pitch * 0.5, y, 0.035), rot=(90, 0, 0))
            b = hs.bolt(0.03, 0.025, washer=False)
            _add(bm, b, (x + pitch * 0.5, y, 0.035 + 0.02))
    return bm


def grille(period, world, pitch=0.3):
    n = max(1, round(period / pitch))
    pitch = period / n
    bm = geo.box(period + 2, world, 0.02, bevel=0.0)
    geo.transform(bm, (period / 2, world / 2, -0.26))
    for k in range(-2, n + 2):
        slat = geo.box(0.045, world - 0.16, 0.2, bevel=0.01, segments=1)
        _add(bm, slat, ((k + 0.5) * pitch, world / 2, -0.09), rot=(0, 42, 0))
    for y in (0.045, world - 0.045):
        bar = geo.box(period + 2, 0.09, 0.08, bevel=0.015, segments=2)
        _add(bm, bar, (period / 2, y, -0.02))
    spacing = period / max(1, round(period / 2.4))
    for k in range(-1, round(period / spacing) + 1):
        rib = geo.box(0.07, world, 0.1, bevel=0.015, segments=2)
        _add(bm, rib, (k * spacing, world / 2, -0.04))
        for y in (0.045, world - 0.045):
            _add(bm, hs.bolt(0.035, 0.03, washer=False), (k * spacing, y, 0.02))
    return bm


def mesh(period, world, cell=0.24):
    n = max(1, round(period / cell))
    dx = period / n
    m = max(1, round(world / (cell * 0.55)))
    dy = world / m
    bm = geo.box(period + 2, world, 0.02, bevel=0.0)
    geo.transform(bm, (period / 2, world / 2, -0.12))
    for i in range(-1, n + 1):
        for j in range(m):
            x0, y0 = i * dx, j * dy
            for (ax, ay), (bx, by) in (((x0, y0), (x0 + dx / 2, y0 + dy)), ((x0 + dx / 2, y0 + dy), (x0 + dx, y0))):
                d = Vector((bx - ax, by - ay))
                strand = geo.box(d.length + 0.03, 0.035, 0.03, bevel=0.0)
                _add(bm, strand, ((ax + bx) / 2, (ay + by) / 2, -0.015), rot=(35, 0, math.degrees(math.atan2(d.y, d.x))))
    for y in (0.035, world - 0.035):
        bar = geo.box(period + 2, 0.07, 0.05, bevel=0.012, segments=2)
        _add(bm, bar, (period / 2, y, -0.01))
    return bm


def bolted(period, world, bolts=20):
    step = period / bolts
    bm = geo.box(period + 2, world, 0.02, bevel=0.0)
    geo.transform(bm, (period / 2, world / 2, -0.07))
    strap = geo.box(period + 2, world * 0.78, 0.05, bevel=0.012, segments=2)
    _add(bm, strap, (period / 2, world / 2, -0.025))
    for k in range(-1, bolts + 1):
        _add(bm, hs.bolt(0.055, 0.05), ((k + 0.5) * step, world / 2, 0.0))
    return bm


def canvas(period, world):
    waves = [(3, 0.045, 0.0, 0.7), (7, 0.02, 1.3, 1.9), (13, 0.01, 2.1, 3.3)]

    def fz(x, y):
        z = 0.0
        for k, amp, ph, fy in waves:
            z += amp * math.sin(2 * math.pi * k * x / period + ph + fy * y)
        return z

    nx = int(period / 0.06)
    bm = _grid(nx, int(world / 0.06), (-0.2, period + 0.2), world, fz)
    for k in range(-1, 5):
        x = (k + 0.5) * period / 4
        web = geo.box(0.2, world + 0.1, 0.03, bevel=0.008, segments=1)
        _add(bm, web, (x, world / 2, fz(x, world / 2) + 0.03))
        buckle = geo.box(0.26, 0.2, 0.04, bevel=0.01, segments=1)
        _add(bm, buckle, (x, world * 0.3, fz(x, world * 0.3) + 0.05))
    return bm


def cable(period, world, strand=0.125, twist=1.6):
    n = max(1, round(period / strand))
    sp = period / n

    def fz(x, y):
        t = ((x + y * twist) / sp) % 1.0
        return 0.05 * (1.0 - abs(t - 0.5) * 2) ** 0.6 - 0.02

    return _grid(int(period / 0.02), 24, (-0.2, period + 0.2), world, fz)


def plain(period, world):
    def fz(x, y):
        return 0.004 * math.sin(2 * math.pi * 5 * x / period + 1.7 * y)

    return _grid(64, 4, (-0.2, period + 0.2), world, fz)


# --- templates -----------------------------------------------------------------

def _mat(bm, idx):
    for f in bm.faces:
        f.material_index = idx
    return bm


def road_wheel():
    """Dual road wheel about +Z (axle) with a groove between the two tyres;
    hub bolts and lightening holes only in the high poly."""
    r, w = 1.2, 1.0
    prof = [(1.02, -w / 2), (r, -w / 2 + 0.05), (r, -0.06), (r * 0.9, -0.02), (r * 0.9, 0.02), (r, 0.06), (r, w / 2 - 0.05), (1.02, w / 2)]
    low = _mat(geo.lathe(prof, verts=12, close_top=False, close_bottom=False), 0)
    disc = [(1.02, w / 2), (0.74, w / 2 - 0.1), (0.4, w / 2 - 0.02), (0.33, w / 2 + 0.06), (0.0, w / 2 + 0.08)]
    hs._join(low, _mat(geo.lathe(disc, verts=12, close_top=False, close_bottom=False), 1))
    high = hs.round_edges(low.copy(), 0.02)
    for k in range(6):
        a = 2 * math.pi * k / 6
        b = _mat(hs.bolt(0.05, 0.05), 1)
        hs._place(b, (math.cos(a) * 0.22, math.sin(a) * 0.22, w / 2 + 0.07), (0, 0, 1))
        hs._join(high, b)
    for k in range(5):
        a = 2 * math.pi * (k + 0.5) / 5
        rim = _mat(geo.torus(0.13, 0.025, verts=10, ring_verts=4), 1)
        geo.transform(rim, (math.cos(a) * 0.58, math.sin(a) * 0.58, w / 2 - 0.045))
        hs._join(high, rim)
    return low, high


def sprocket():
    return _mat(hs.sprocket(r=1.25, w=0.9, teeth=12, verts=24), 0)


def tyre_half():
    """Outer half of the buggy's off-road tyre about +Z (z >= 0): sidewall
    down to the rim and half the tread with its lugs. Two halves (one
    turned 180° about Y) make a tyre; both share this texture. The
    shoulder blocks exist only in the high poly."""
    r, w, r_in, lug_h, lugs = 1.35, 1.15, 0.64, 0.12, 14
    rc = r - lug_h
    prof = [(rc, 0.0), (rc, w / 2 - 0.22), (rc - 0.1, w / 2 - 0.07), (rc - 0.3, w / 2), (r_in + 0.1, w / 2 - 0.02), (r_in, w / 2 - 0.08)]
    low = geo.lathe(prof, verts=18, close_top=False, close_bottom=False)
    high = hs.round_edges(low.copy(), 0.02)
    for k in range(lugs):
        a = 2 * math.pi * (k + (0.25 if k % 2 else 0.0)) / lugs
        for dst in (low, high):
            lug = geo.tapered_box(0.44, 0.42, lug_h + 0.05, top_scale=(0.82, 0.9), bevel=0.0)
            geo.transform(lug, (0, 0, (lug_h + 0.05) / 2 - 0.03))
            bottom = [f for f in lug.faces if f.normal.z < -0.9]
            bmesh.ops.delete(lug, geom=bottom, context="FACES_ONLY")
            if dst is high:
                hs.round_edges(lug, 0.02)
            hs._place(lug, (math.cos(a) * rc, math.sin(a) * rc, w * 0.22 + (0.05 if k % 2 else -0.04)), (math.cos(a), math.sin(a), 0.0),
                      spin=math.pi / 2)
            hs._join(dst, lug)
        sh = geo.box(0.34, 0.18, 0.14, bevel=0.02, segments=2)
        geo.transform(sh, (0, 0, 0.04))
        hs._place(sh, (math.cos(a) * (rc - 0.12), math.sin(a) * (rc - 0.12), w / 2 - 0.06), (math.cos(a) * 0.4, math.sin(a) * 0.4, 1.0))
        hs._join(high, sh)
    return low, high


def rim():
    low = hs.rim(r=0.64, w=0.9, bolts=0, verts=12)
    high = hs.round_edges(low.copy(), 0.015)
    for k in range(12):
        a = 2 * math.pi * k / 12
        b = hs.bolt(0.035, 0.04, washer=False)
        hs._place(b, (math.cos(a) * 0.6, math.sin(a) * 0.6, 0.47), (0, 0, 1))
        hs._join(high, b)
    return low, high


def jerrycan():
    """Low: plain can with handles and spout; high adds the X-rib panels."""
    return hs.jerrycan(detail=False), hs.round_edges(hs.jerrycan(detail=True), 0.03)


def ammo_can():
    return hs.ammo_can()


def shovel():
    bm = hs.shovel()
    return bm


def pickaxe():
    return hs.pickaxe()


def crowbar():
    return hs.crowbar()


def periscope():
    body = _mat(hs.periscope(), 0)
    glass = _mat(geo.box(0.34, 0.03, 0.14, bevel=0.0), 1)
    geo.transform(glass, (0, 0.145, 0.13), rot=(-12, 0, 0))
    hs._join(body, glass)
    return body


def headlight():
    body = _mat(hs.headlight(0.3, 0.28), 0)
    lens = _mat(geo.cylinder(0.26, 0.04, verts=12, bevel=0.0), 1)
    geo.transform(lens, (0, 0.29, 0), rot=(-90, 0, 0))
    hs._join(body, lens)
    return body


def build(samples=24, preview=True, **kw):
    s = trim.TrimSheet("TrimEnemy")
    materials(s)
    s.strip("track", 144, 2.2, track, "trk_steel", relief=(0.12, 0.2))
    s.strip("grille", 88, 1.2, grille, "grille", relief=(0.06, 0.28))
    s.strip("mesh", 56, 0.8, mesh, "mesh", relief=(0.03, 0.14))
    s.strip("bolted", 56, 0.5, bolted, "strap", relief=(0.08, 0.1))
    s.strip("canvas", 88, 1.4, canvas, "canvas", relief=(0.12, 0.08))
    s.strip("cable", 32, 0.5, cable, "cable", relief=(0.05, 0.04))
    s.strip("plain", 48, 1.0, plain, "plain", relief=(0.02, 0.02))
    s.strip("red", 24, 0.6, plain, "red", relief=(0.02, 0.02))
    rw_low, rw_high = road_wheel()
    s.template("roadwheel", rw_low, ["t_rubber", "t_wheel"], high=rw_high)
    s.template("sprocket", sprocket(), "t_wheel")
    ty_low, ty_high = tyre_half()
    s.template("tyre_half", ty_low, "t_rubber", high=ty_high)
    rim_low, rim_high = rim()
    s.template("rim", rim_low, "t_wheel", high=rim_high)
    for name, mat in (("jerrycan_red", "t_red"), ("jerrycan_dark", "t_dark")):
        low, high = jerrycan()
        s.template(name, low, mat, high=high)
    s.template("ammo_can", ammo_can(), "t_ammo")
    s.template("shovel", shovel(), "t_wood")
    s.template("pickaxe", pickaxe(), "t_wood")
    s.template("crowbar", crowbar(), "t_steel")
    s.template("periscope", periscope(), ["t_dark", "t_glass"])
    s.template("headlight", headlight(), ["t_dark", "t_lens"])
    return s.finish(samples=samples, preview=preview)
