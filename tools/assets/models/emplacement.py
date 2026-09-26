"""Emplacement: reinforced-concrete gun pit on the mesa knob with a
sandbag parapet, props, and the three-weapon turret (heavy machine gun,
7-tube rocket pod, twin AA missile rail).

Asset origin = turret pivot (world Config.TURRET_PIVOT). Bunker top
surface at z = -6. Blender +Y = forward (Roblox -Z).

Models: Static, TurretYaw (yaws about the pivot), TurretGun (pitches about
the pivot) with sub-models MachineGun, RocketPod, MissileRack; markers
Muzzle (TurretGun), RocketMuzzle (RocketPod), MissileMuzzle (MissileRack);
missile meshes Missile1 / Missile2 (hidden by the client when unloaded).
Animatable extras (HS-2): Static/Antenna (part Whip, pivot at its base),
Static/CamoNet (part Net, pivot at the ridge), MachineGun part Belt.

Hero pass (HS-1): cloth-simulated sandbag variants shared through a sheet
texture group, burlap/concrete/painted-steel detail from CC0 photo
sources (tools/assets/cc0.py), stencils, a draped camo net, water cans,
a brass belt and scattered casings.
"""
import math
import random

import bmesh
from mathutils import Matrix, Vector

from rmh import cloth, geo, images
from rmh.asset import Asset

FLOOR = -6.0
BAG_L, BAG_D, BAG_H = 2.2, 1.15, 0.6
COURSE = BAG_H * 0.88
GAP_DEG = 32  # half-angle of the rear opening in the parapet
ROWS = [(11.55, 0.0), (12.75, 0.5)]  # (radius, stagger)
INNER_R = 11.0  # floor disc (Bunker) radius; the ring under the bags is BunkerWall
BARREL_Z = 0.2
POD_X, POD_Z = 3.2, 0.3
RACK_X = -3.25
NET_DEG = 126.0  # camo net centre (degrees clockwise from forward)
NET_POLES = (NET_DEG - 17, NET_DEG + 17)
POLE_R, POLE_TOP = 9.0, FLOOR + 3.35
AMMO_STACK = [(9.2, 128, 0), (9.2, 132, 0), (9.25, 130, 1), (10.1, 126, 0), (10.1, 131, 0), (10.1, 128.5, 1), (8.4, 137, 0)]
WATER_CANS = [(9.6, 114.5), (10.35, 117.5), (9.5, 121.0)]
RADIO = (6.5, 0.3, -12)  # x, y, rz
STENCIL = "#c9b98a"
DUST_OCHRE = "#b3875f"  # mesa sand (art bible ochre, dulled)
STENCIL_DARK = "#1f1d18"

rng = random.Random(1307)


def along_y(bm, at):
    """Primitive built along +Z, laid along +Y (forward)."""
    return geo.transform(bm, at, rot=(-90, 0, 0))


def polar(r, deg, z=0.0):
    th = math.radians(deg)
    return (r * math.sin(th), r * math.cos(th), z)


def stencil(a, text, center, normal, height, color=STENCIL, wear=0.35, up=(0, 0, 1), seed=1):
    """Stencilled text projected onto whatever surface sits at `center`."""
    img = images.get("text", text=text, wear=wear, seed=seed)
    aspect = img.size[0] / img.size[1]
    a.decal(img, center, normal, (height * aspect, height, 0.3), up=up, color=color)


# --- small shared meshes (sheet group "smalls") -----------------------------------

CASE_PROF = [(0.0, 0.0), (0.055, 0.0), (0.055, 0.25), (0.036, 0.3), (0.036, 0.36), (0.0, 0.36)]


def small_templates(a):
    """Casings, belted rounds and links share one tiny atlas."""
    a.material("round", kind="metal", color="#b8903e", rough=0.24, metal=1.0, dust=0.15, grime=0.35, bevel=0.01,
               marks=[{"lo": (-1, -1, 0.37), "hi": (1, 1, 1), "color": "#8e5a38", "soft": 0.004}])
    t = {}
    t["case"] = a.template("case", "smalls", geo.lathe(CASE_PROF, verts=5), "brass_p", smooth_angle=60)
    t["case_dull"] = a.template("case_dull", "smalls", geo.lathe(CASE_PROF, verts=5), "brass_dull", smooth_angle=60)
    rnd = geo.lathe([(0.0, 0.0), (0.058, 0.0), (0.058, 0.29), (0.04, 0.33), (0.04, 0.37), (0.036, 0.43), (0.015, 0.49), (0.0, 0.51)], verts=8)
    t["round"] = a.template("round", "smalls", rnd, "round", smooth_angle=60)
    t["link"] = a.template("link", "smalls", geo.box(0.07, 0.14, 0.07, bevel=0.0), "link", smooth_angle=30)
    return t


def belt_along(part, smalls, pts, n, up=(0, 0, 1)):
    """A linked belt of `n` rounds along a polyline; rounds lie across the
    belt (their axis perpendicular to the path, in the horizontal plane)."""
    path = [Vector(q) for q in pts]
    lengths = [(path[i + 1] - path[i]).length for i in range(len(path) - 1)]
    total = sum(lengths)
    for k in range(n):
        d = total * (k + 0.5) / n
        i = 0
        while i < len(lengths) - 1 and d > lengths[i]:
            d -= lengths[i]
            i += 1
        pos = path[i].lerp(path[i + 1], d / lengths[i])
        tang = (path[i + 1] - path[i]).normalized()
        across = tang.cross(Vector(up)).normalized()
        # Round axis = `across` (pointing forward, bullet first); belt tangent = local X.
        m = Matrix((tang, across, tang.cross(across))).transposed().to_4x4()
        eul = m.to_euler("XYZ")
        rot = tuple(math.degrees(v) for v in eul)
        part.add_template(smalls["round"], at=tuple(pos - across * 0.22), rot=_lay(rot))
        for off in (-0.08, 0.1):
            part.add_template(smalls["link"], at=tuple(pos + across * off - Vector((0, 0, 0.035))), rot=rot)


def _lay(rot):
    """Rotation that turns a +Z-built round onto local +Y, then applies `rot`."""
    m = geo.euler_matrix(rot) @ geo.euler_matrix((-90, 0, 0))
    return tuple(math.degrees(v) for v in m.to_euler("XYZ"))


# --- materials -----------------------------------------------------------------

def materials(a):
    paint_photo = {"id": "green_metal_rust", "scale": 3.6, "color": 0.85, "sat": 0.45, "rough": 0.5, "height": 0.35}
    worn = {"under": "#7a7b78", "under_metal": 0.9, "under_rough": 0.32, "chip_style": "blotch", "chip_scale": 5.0,
            "chip_bevel": 0.16, "fade": 0.45, "fade_color": "#6b6b45", "patches": 0.7, "patch_color": "#44462d",
            "dust_color": DUST_OCHRE, "grime": 0.75, "bevel": 0.07}
    a.material("olive_p", base="olive", color="#55563a", photo=paint_photo, wear=0.6, dust=0.6, **worn)
    a.material("olive_dark_p", base="olive_dark", color="#45472f", photo=paint_photo, wear=0.55, dust=0.55,
               **dict(worn, patch_color="#383a26", fade_color="#66674f"))
    a.material("shield", base="olive", color="#57583b", photo=paint_photo, wear=0.66, dust=0.62, **dict(worn, chip_scale=6.0))
    a.material("handle", kind="metal", color="#6a6862", rough=0.26, metal=1.0, dust=0.12, grime=0.45, bevel=0.02)
    a.material("steel_dark_p", base="steel_dark", photo={"id": "green_metal_rust", "scale": 2.0, "rough": 0.6, "height": 0.3})
    a.material("brass_p", kind="metal", color="#b8903e", rough=0.24, metal=1.0, dust=0.18, grime=0.35, bevel=0.01)
    a.material("brass_dull", kind="metal", color="#a07c3a", rough=0.38, metal=1.0, dust=0.5, grime=0.4, bevel=0.01, dust_up=1.0)
    a.material("copper", kind="metal", color="#9a6440", rough=0.3, metal=1.0, dust=0.15, grime=0.3, bevel=0.01)
    a.material("link", kind="metal", color="#2c2c2b", rough=0.45, metal=0.85, dust=0.2, grime=0.4)
    a.material("weld", kind="metal", color="#3d3a32", rough=0.6, metal=0.7, dust=0.4, grime=0.6, bevel=0.01, dust_color=DUST_OCHRE)
    a.material("rope", kind="fabric", color="#8c7a58", weave=60.0, wrinkle=0.2, rough=0.9, dust=0.3)
    a.material("wood_pole", base="wood_crate", color="#6d5638", grain="Z", wear=0.3)


def burlap(a, name, color, bleach):
    a.material(name, kind="fabric", color=color, rough=0.95, weave_amount=0.05, wrinkle=0.12, wrinkle_scale=6.0,
               photo={"id": "hessian_230", "scale": 2.4, "color": 1.0, "sat": 0.6, "rough": 0.35, "height": 2.2},
               bleach=bleach, bleach_color="#b8a784", damp=0.85, damp_height=0.2, damp_color="#46382a",
               seam_dust=1.0, seam_color="#c3a77d", seam_distance=0.22, weather_scale=2.2,
               dust=0.5, dust_up=0.55, dust_height=0.12, dust_color="#b89068", grime=0.45, zmin=0.0, decals=False, bump=0.45)


# --- bunker ----------------------------------------------------------------------

def bunker(a):
    photo = {"id": "concrete_floor_worn_001", "scale": 10.7, "color": 0.8, "sat": 0.25, "rough": 0.5, "height": 0.8}
    a.material("floor_concrete", base="concrete", color="#837d70", grime=0.9, dust=0.55, dust_height=1.2, photo=photo,
               dust_color=DUST_OCHRE,
               stain="#463a2c", joint=5.5,
               marks=[
                   {"lo": (-2.6, -9.5, -9), "hi": (2.4, -3.0, -5.5), "color": "#3f3930", "soft": 1.6},  # rocket backblast soot
                   {"lo": (3.2, -6.4, -9), "hi": (5.8, -3.6, -5.5), "color": "#4a3e30", "soft": 0.6},  # oil/damp under ammo
                   {"lo": (-1.4, 2.0, -9), "hi": (1.6, 5.5, -5.5), "color": "#a38d6a", "soft": 1.2},  # sand blown in
               ])
    a.material("wall_concrete", base="concrete", color="#888275", grime=0.9, dust=0.7, dust_height=3.0, dust_color=DUST_OCHRE,
               photo=dict(photo, scale=9.0, color=0.7))
    a.material("ladder_p", base="olive_dark", photo={"id": "green_metal_rust", "scale": 3.0, "color": 0.8, "sat": 0.5},
               wear=0.75, under="#6a6660", under_rough=0.4)
    a.material("sand_drift", kind="flat", color="#a9845e", rough=0.97, dust=0.0, grime=0.25, bump=0.35, var_scale=9.0,
               photo={"id": "concrete_floor_worn_001", "scale": 4.0, "height": 0.6, "rough": 0.3})

    b = a.part("Bunker", path="Static", tex="floor", collide=True, query=True, material="Concrete")
    rings = [(0.0, FLOOR), (2.4, FLOOR), (5.0, FLOOR), (8.0, FLOOR), (INNER_R, FLOOR)]
    b.add(geo.lathe(rings, verts=64, close_top=False, close_bottom=False), "floor_concrete")
    b.add(geo.cylinder(2.6, 0.3, verts=32, bevel=0.08), "floor_concrete", at=(0, 0, FLOOR + 0.15))
    # Floor drain grate at the rear and cast-in tie-down rings.
    b.add(geo.box(1.4, 0.7, 0.06, bevel=0.02), "ladder_p", at=(0, -9.8, FLOOR + 0.02))
    for i in range(6):
        b.add(geo.box(0.06, 0.62, 0.05, bevel=0.0), "ladder_p", at=(-0.55 + i * 0.22, -9.8, FLOOR + 0.05))
    for deg in (40, 140, 220, 320):
        x, y, _ = polar(9.5, deg)
        b.add(geo.torus(0.14, 0.03, verts=10, ring_verts=5), "ladder_p", at=(x, y, FLOOR + 0.03))

    w = a.part("BunkerWall", path="Static", tex="outer", collide=True, query=True, material="Concrete")
    prof = [(INNER_R, FLOOR), (12.8, FLOOR), (13.15, FLOOR - 0.05), (13.5, FLOOR - 0.3), (13.55, FLOOR - 0.75),
            (13.35, FLOOR - 0.85), (13.35, FLOOR - 3.6), (13.45, FLOOR - 3.7), (13.6, FLOOR - 7.0), (14.3, FLOOR - 8.0)]
    w.add(geo.lathe(prof, verts=64, close_top=False, close_bottom=False), "wall_concrete")
    for i in range(8):
        th = math.radians(22.5 + i * 45)
        w.add(geo.box(0.6, 0.5, 0.3, bevel=0.05), "ladder_p", at=(13.45 * math.sin(th), 13.45 * math.cos(th), FLOOR - 0.5), rot=(0, 0, -math.degrees(th)))
    # Rear access ladder down the bunker wall.
    for sx in (-1, 1):
        w.add(geo.box(0.12, 0.12, 8.0, bevel=0.02), "ladder_p", at=(sx * 0.7, -13.75, FLOOR - 3.6))
        w.add(geo.box(0.12, 0.6, 0.12, bevel=0.02), "ladder_p", at=(sx * 0.7, -13.45, FLOOR + 0.35))
    for i in range(10):
        w.add(geo.cylinder(0.05, 1.4, verts=6, bevel=0.0), "ladder_p", at=(0, -13.75, FLOOR - 7.2 + i * 0.75), rot=(0, 90, 0))

    d = a.part("Drifts", path="Static", tex="outer", query=False, material="Sand")
    for i in range(10):
        deg = 180 + GAP_DEG + 8 + i * (360 - 2 * GAP_DEG - 16) / 9
        x, y, _ = polar(10.6, deg)
        h = rng.uniform(0.14, 0.24)
        mound = geo.lathe([(0.0, h), (0.35, h * 0.9), (0.7, h * 0.62), (1.05, h * 0.3), (1.35, h * 0.1), (1.6, -0.04)], verts=16, close_bottom=False)
        d.add(mound, "sand_drift", scale=(rng.uniform(1.2, 1.9), rng.uniform(0.6, 0.85), 1.0),
              at=(x, y, FLOOR - 0.02), rot=(0, 0, -deg + rng.uniform(-8, 8)))

    p = a.part("Pedestal", path="Static", tex="turret", query=False, material="Metal")
    p.add(geo.cylinder(1.9, 0.25, verts=24, bevel=0.06), "olive_dark_p", at=(0, 0, FLOOR + 0.42))
    p.add(geo.cylinder(1.25, 2.6, verts=24, r_top=0.95, bevel=0.05), "olive_dark_p", at=(0, 0, FLOOR + 1.85))
    p.add(geo.cylinder(1.25, 0.18, verts=24, bevel=0.04), "olive_dark_p", at=(0, 0, FLOOR + 3.1))
    for i in range(10):
        ang = 2 * math.pi * i / 10
        p.add(geo.cylinder(0.09, 0.14, verts=6, bevel=0.02), "steel_dark_p", at=(1.62 * math.cos(ang), 1.62 * math.sin(ang), FLOOR + 0.58))
    for i in range(4):  # gusset ribs
        ang = math.pi / 4 + i * math.pi / 2
        p.add(geo.prism([(0, 0), (0.55, 0), (0, 1.3)], 0.12, bevel=0.02), "olive_dark_p",
              at=(1.05 * math.cos(ang), 1.05 * math.sin(ang), FLOOR + 0.55), rot=(90, 0, math.degrees(ang)))
    stencil(a, "3-41", (0, -1.12, FLOOR + 1.9), (0, -1, 0), 0.34, wear=0.45, seed=4)


# --- sandbags --------------------------------------------------------------------

SHAPES = {
    # name: cloth.sandbag kwargs, final size
    "top0": ({"seed": 11, "press": 4.0, "jitter": 0.022}, (BAG_L, BAG_D, BAG_H)),
    "top1": ({"seed": 12, "press": 4.4, "neck": 0.5, "jitter": 0.025}, (BAG_L * 1.02, BAG_D, BAG_H * 1.02)),
    "mid0": ({"seed": 13, "press": 5.0, "load": 0.55, "jitter": 0.022}, (BAG_L * 1.03, BAG_D * 1.04, BAG_H * 0.95)),
    "mid1": ({"seed": 14, "press": 4.5, "load": 0.52, "neck": 0.45, "tension": 8.0, "jitter": 0.025}, (BAG_L * 1.04, BAG_D * 1.03, BAG_H * 0.94)),
}
# Art bible: burlap #A8916B, sun-bleached tops #CDB88F; kept a notch darker
# so close muzzle flashes and searchlights don't blow them out at night.
TINTS = {"a": ("#9a8560", 0.8), "b": ("#8c8367", 0.95), "c": ("#a48b61", 0.65), "d": ("#76634a", 0.45)}


def sandbag_templates(a):
    shapes = {}
    for key, (kw, size) in SHAPES.items():
        shapes[key] = cloth.sandbag(size=size, **kw)
    temps = {}
    for tint, (color, bleach) in TINTS.items():
        burlap(a, f"burlap_{tint}", color, bleach)
        for key, (high, low) in shapes.items():
            if tint == "d" and key.startswith("top"):
                continue  # dark, damp bags only on the bottom courses
            temps[(key, tint)] = a.template(f"bag_{key}_{tint}", "bags", low.copy(), f"burlap_{tint}", high=high.copy(), uv="seams")
    return temps, shapes


def sandbags(a):
    temps, shapes = sandbag_templates(a)
    parts = {name: a.part(name, path="Static", tex="bags", query=True, collide=False, material="Fabric", smooth_angle=80)
             for name in ("SandbagsLeft", "SandbagsFront", "SandbagsRight")}
    placed = []
    span = 360 - 2 * GAP_DEG
    for course in range(4):
        for row, (r, stagger) in enumerate(ROWS):
            if row == 0 and course == 3:
                continue  # inner row one course lower: stepped parapet
            top = (row == 1 and course == 3) or (row == 0 and course == 2)
            circ = 2 * math.pi * r * span / 360
            n = int(circ / (BAG_L * 0.97))
            for i in range(n):
                t = (i + 0.5 + ((course + row) % 2) * 0.5 * (1 if i < n - 1 else 0)) / n
                deg = 180 + GAP_DEG + t * span  # sweep from rear-left round the front
                x, y, _ = polar(r + rng.uniform(-0.05, 0.05), deg)
                z = FLOOR + course * COURSE - 0.02 + rng.uniform(-0.02, 0.02)
                shape = rng.choice(["top0", "top1"] if top else ["mid0", "mid1"])
                tint = rng.choice(["a", "a", "b", "c", "d"] if course == 0 else ["a", "a", "b", "c"])
                flip = 180 if rng.random() < 0.5 else 0
                rot = (rng.uniform(-2.5, 2.5), rng.uniform(-3, 3), -deg + flip + rng.uniform(-5, 5))
                scale = (rng.uniform(0.95, 1.04), rng.uniform(0.96, 1.04), rng.uniform(0.95, 1.03))
                key = "SandbagsLeft" if deg < 300 else ("SandbagsFront" if deg < 420 else "SandbagsRight")
                parts[key].add_template(temps[(shape, tint)], at=(x, y, z), rot=rot, scale=scale)
                placed.append((SHAPES[shape][1], (x, y, z), rot, scale, deg))
    return placed


# --- props -----------------------------------------------------------------------

def ammo_can(p, a, at, rz, mat="olive_p", label=True, seed=0):
    x, y, z = at
    p.add(geo.box(1.15, 0.55, 0.72, bevel=0.05), mat, at=(x, y, z + 0.36), rot=(0, 0, rz))
    p.add(geo.box(1.2, 0.6, 0.1, bevel=0.03), mat, at=(x, y, z + 0.75), rot=(0, 0, rz))
    c, s = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    p.add(geo.pipe_path([(x - 0.22 * c, y - 0.22 * s, z + 0.8), (x - 0.18 * c, y - 0.18 * s, z + 0.9), (x + 0.18 * c, y + 0.18 * s, z + 0.9), (x + 0.22 * c, y + 0.22 * s, z + 0.8)], 0.025, verts=5), "handle")
    p.add(geo.box(0.1, 0.08, 0.2, bevel=0.02), "steel_dark_p", at=(x + 0.58 * c, y + 0.58 * s, z + 0.62), rot=(0, 0, rz))
    if label:
        n = (-s, c, 0)
        stencil(a, "7.62", (x + n[0] * 0.3, y + n[1] * 0.3, z + 0.46), n, 0.2, wear=0.4, seed=seed)
        stencil(a, "LINKED", (x + n[0] * 0.3, y + n[1] * 0.3, z + 0.22), n, 0.11, wear=0.5, seed=seed + 1)


def water_can(p, a, at, rz, seed=0):
    x, y, z = at
    p.add(geo.box(0.95, 0.46, 1.2, bevel=0.1), "water", at=(x, y, z + 0.6), rot=(0, 0, rz))
    c, s = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    for k in (-0.28, 0.0, 0.28):
        p.add(geo.box(0.08, 0.1, 0.18, bevel=0.03), "water", at=(x + k * c, y + k * s, z + 1.25), rot=(0, 0, rz))
    p.add(geo.box(0.66, 0.1, 0.07, bevel=0.03), "water", at=(x, y, z + 1.35), rot=(0, 0, rz))
    p.add(geo.cylinder(0.11, 0.14, verts=10, bevel=0.03), "water_cap", at=(x + 0.36 * c, y + 0.36 * s, z + 1.26))
    n = (-s, c, 0)
    stencil(a, "WATER", (x + n[0] * 0.25, y + n[1] * 0.25, z + 0.62), n, 0.17, color=STENCIL_DARK, wear=0.35, seed=seed)


def props(a, smalls):
    a.material("crate_wood", base="olive_dark", photo={"id": "green_metal_rust", "scale": 3.0, "color": 0.6, "sat": 0.4},
               under="#7a6040", under_metal=0.0, under_rough=0.8, wear=0.6, chip_style="blotch", chip_scale=5.0,
               ring=0.3, fade=0.35, fade_color="#6c6d52", dust_color=DUST_OCHRE)
    a.material("jerry", base="tan", color="#8a7a50", wear=0.6, photo={"id": "green_metal_rust", "scale": 3.0, "color": 0.7, "sat": 0.2, "rough": 0.4},
               under="#6d6a66", under_metal=0.85, under_rough=0.35, chip_style="blotch", chip_scale=6.0, dust_color=DUST_OCHRE)
    a.material("water", kind="paint", color="#7c7453", rough=0.7, wear=0.0, dust=0.6, grime=0.55, bump=0.1)
    a.material("water_cap", kind="paint", color="#2d2b26", rough=0.6, wear=0.0, dust=0.4)
    a.material("radio", base="olive_dark_p", wear=0.55)
    a.material("canvas", kind="fabric", color="#5d5a3c", rough=0.92, wrinkle=0.35, dust=0.55, grime=0.5)
    p = a.part("Props", path="Static", tex="props", query=False, material="Metal")
    st = a.part("Stores", path="Static", tex="stores", query=False, material="Metal")
    # Ammo point under the camo net (rear right): stacked 7.62 cans.
    for k, (r, deg, lvl) in enumerate(AMMO_STACK):
        x, y, _z = polar(r, deg)
        ammo_can(st, a, (x, y, FLOOR + lvl * 0.84), -deg + 90 + rng.uniform(-6, 6), seed=10 + k, label=lvl == 1 or k in (0, 6))
    for k, (r, deg) in enumerate(WATER_CANS):
        x, y, _z = polar(r, deg)
        water_can(st, a, (x, y, FLOOR), -deg + 90 + rng.uniform(-8, 8), seed=30 + k)
    # An open can with a loose belt spilling out (belt: Casings part).
    x, y, _z = polar(8.3, 144)
    ammo_can(st, a, (x, y, FLOOR), -144 + 90, seed=40, label=True)
    loose_can = (x, y)

    # Rocket reload crates (wood, rope handles).
    for k, (x, y, z, rz) in enumerate([(-5.3, -5.6, 0, 20), (-5.1, -5.5, 1, 14), (-7.2, -3.4, 0, 70)]):
        zc = FLOOR + 0.55 + z * 1.1
        p.add(geo.box(3.6, 1.3, 1.1, bevel=0.06), "crate_wood", at=(x, y, zc), rot=(0, 0, rz))
        c, s = math.cos(math.radians(rz)), math.sin(math.radians(rz))
        for sx in (-1, 1):
            p.add(geo.box(0.22, 1.36, 1.16, bevel=0.03), "crate_wood", at=(x + sx * 1.5 * c, y + sx * 1.5 * s, zc), rot=(0, 0, rz))
            p.add(geo.torus(0.14, 0.03, verts=8, ring_verts=4), "rope", at=(x + sx * 1.66 * c, y + sx * 1.66 * s, zc + 0.1), rot=(0, 90, rz))
        a.decal(images.get("stripes", count=4, angle=0), (x, y, zc + 0.55), (0, 0, 1), (1.2, 0.4, 0.3), color="#c9a227")
        n = (-s, c, 0)
        stencil(a, "RKT 70", (x - n[0] * 0.66, y - n[1] * 0.66, zc + 0.05), (-n[0], -n[1], 0), 0.26, wear=0.4, seed=50 + k)
    # Spare missile canisters on a low rack.
    for i, x in enumerate((-8.2, -8.9)):
        p.add(geo.cylinder(0.32, 4.0, verts=16, bevel=0.04), "olive_p", at=(x, 1.0, FLOOR + 0.6 + i * 0.05), rot=(-90, 0, 0))
        for yy in (-0.6, 2.6):
            p.add(geo.cylinder(0.36, 0.15, verts=16, bevel=0.03), "olive_dark_p", at=(x, yy, FLOOR + 0.6 + i * 0.05), rot=(-90, 0, 0))
    for yy in (-0.3, 2.3):
        p.add(geo.box(1.8, 0.3, 0.28, bevel=0.03), "crate_wood", at=(-8.55, yy, FLOOR + 0.14))
    a.decal(images.get("stripes", count=2, angle=90), (-8.55, 1.6, FLOOR + 0.95), (0, 0, 1), (1.6, 0.3, 0.3), color="#c9a227")
    stencil(a, "AA MSL", (-7.85, 1.0, FLOOR + 0.62), (1, 0, 0), 0.2, up=(0, 0, 1), wear=0.35, seed=60)
    # Jerrycans against the parapet.
    for k, (x, y, rz) in enumerate([(7.6, 5.4, 38), (8.2, 4.6, 45), (7.0, 6.2, 30)]):
        p.add(geo.box(0.95, 0.55, 1.35, bevel=0.08), "jerry", at=(x, y, FLOOR + 0.68), rot=(0, 0, rz))
        p.add(geo.box(0.5, 0.12, 0.14, bevel=0.03), "handle", at=(x, y, FLOOR + 1.42), rot=(0, 0, rz))
        p.add(geo.cylinder(0.1, 0.18, verts=8, bevel=0.02), "jerry", at=(x + 0.3, y + 0.1, FLOOR + 1.42), rot=(0, 0, rz))
        # Embossed X panels on the sides.
        c, s = math.cos(math.radians(rz)), math.sin(math.radians(rz))
        for side in (-1, 1):
            for d in (1, -1):
                p.add(geo.box(0.9, 0.03, 0.05, bevel=0.01), "jerry", at=(x - side * 0.285 * s, y + side * 0.285 * c, FLOOR + 0.68), rot=(0, d * 50, rz))
    # Field radio on a crate; its whip antenna is Static/Antenna.
    rx, ry, rz = RADIO
    c, s_ = math.cos(math.radians(rz)), math.sin(math.radians(rz))

    def rloc(u, v, z):  # radio-local (u along its width, v toward its back)
        return (rx + u * c - v * s_, ry + u * s_ + v * c, FLOOR + z)

    p.add(geo.box(1.3, 0.9, 0.9, bevel=0.05), "crate_wood", at=rloc(0, 0, 0.45), rot=(0, 0, rz))
    p.add(geo.box(0.9, 0.55, 0.7, bevel=0.05), "radio", at=rloc(0, 0, 1.25), rot=(0, 0, rz))
    p.add(geo.box(0.6, 0.06, 0.4, bevel=0.02), "steel_dark_p", at=rloc(-0.05, -0.29, 1.28), rot=(0, 0, rz))
    for k in range(3):
        p.add(geo.cylinder(0.05, 0.08, verts=8, bevel=0.01), "handle", at=rloc(-0.2 + k * 0.16, -0.33, 1.42), rot=(90, 0, rz))
    p.add(geo.pipe_path([rloc(-0.4, -0.3, 1.1), rloc(-0.6, -0.45, 0.6), rloc(-0.55, -0.6, 0.1), rloc(-1.0, -0.9, 0.05)], 0.03, verts=5), "link")
    p.add(geo.box(0.5, 0.3, 0.2, bevel=0.04), "link", at=rloc(-1.05, -0.95, 0.1), rot=(0, 0, rz + 45))  # handset
    # Camo net supports: two pickets.
    for deg in NET_POLES:
        x, y, _z = polar(POLE_R, deg)
        st.add(geo.cylinder(0.07, POLE_TOP - FLOOR, verts=8, bevel=0.0), "wood_pole", at=(x, y, (POLE_TOP + FLOOR) / 2))
    a.pivot("Static/CamoNet", polar(POLE_R, NET_DEG, POLE_TOP))

    cs = a.part("Casings", path="Static", tex="smalls", query=False, shadow=False, material="Metal")
    for i in range(110):
        r = abs(rng.gauss(0.0, 1.0)) * 1.6 + 2.0
        th = rng.gauss(0.55, 0.9)  # thrown to the right of the gun, drifting forward and back
        x, y = r * math.sin(th), r * math.cos(th) - 0.6
        if math.hypot(x, y) > 10.0:
            continue
        t = smalls["case"] if rng.random() < 0.55 else smalls["case_dull"]
        cs.add_template(t, at=(x, y, FLOOR + 0.055), rot=_lay((0, rng.uniform(-8, 8), rng.uniform(0, 360))))
    lx, ly = loose_can
    belt_along(cs, smalls, [(lx + 0.05, ly + 0.05, FLOOR + 0.82), (lx + 0.25, ly + 0.3, FLOOR + 0.6), (lx + 0.45, ly + 0.65, FLOOR + 0.1),
                            (lx + 0.6, ly + 1.2, FLOOR + 0.05), (lx + 0.4, ly + 1.8, FLOOR + 0.05)], 11)

    s = a.part("Searchlight", path="Static", tex="props", query=False, material="Metal")
    sx, sy = -8.6, -6.2
    for i in range(3):
        ang = math.radians(90 + i * 120)
        s.add(geo.pipe_path([(sx, sy, FLOOR + 2.6), (sx + 1.1 * math.cos(ang), sy + 1.1 * math.sin(ang), FLOOR)], 0.06, verts=6), "steel_dark_p")
    s.add(geo.cylinder(0.12, 0.8, verts=8), "steel_dark_p", at=(sx, sy, FLOOR + 2.95))
    s.add(geo.box(1.5, 0.15, 0.9, bevel=0.03), "radio", at=(sx, sy, FLOOR + 3.45))
    s.add(geo.cylinder(0.7, 1.3, verts=24, r_top=0.78, bevel=0.06), "radio", at=(sx, sy + 0.1, FLOOR + 3.7), rot=(-90, 0, 0))
    s.add(geo.cylinder(0.82, 0.12, verts=24, bevel=0.03), "radio", at=(sx, sy + 0.8, FLOOR + 3.7), rot=(-90, 0, 0))
    s.add(geo.cylinder(0.72, 0.05, verts=24, bevel=0.0), "lens", at=(sx, sy + 0.85, FLOOR + 3.7), rot=(-90, 0, 0))
    a.attach("SearchlightBeam", "Searchlight", (sx, sy + 0.9, FLOOR + 3.7), axis=(0, 1, 0))

    # Radio whip antenna: own model so HS-2 can sway it about its base.
    base = Vector(rloc(0.25, 0.1, 1.6))
    a.pivot("Static/Antenna", tuple(base))
    ant = a.part("Whip", path="Static/Antenna", tex="props", query=False, shadow=False, material="Metal")
    ant.add(geo.cylinder(0.05, 0.22, verts=8, bevel=0.01), "steel_dark_p", at=tuple(base + Vector((0, 0, 0.11))))
    ant.add(geo.cylinder(0.035, 0.18, verts=6, bevel=0.0), "handle", at=tuple(base + Vector((0, 0, 0.3))))
    tip = base + Vector((0.12, 0.05, 3.3))
    ant.add(geo.pipe_path([tuple(base + Vector((0, 0, 0.3))), tuple(base.lerp(tip, 0.5) + Vector((0.02, 0, 0))), tuple(tip)], 0.02, verts=5), "link")
    ant.add(geo.box(0.02, 0.18, 0.1, bevel=0.0), "tape", at=tuple(tip + Vector((0, -0.1, -0.12))))
    a.material("tape", kind="fabric", color="#9a8a5c", rough=0.9, wrinkle=0.2, dust=0.3)


# --- camo net --------------------------------------------------------------------

def camo_net(a, placed):
    a.material("camo_net", kind="fabric", pattern="camo", color="#4d5332", color2="#86724d", color3="#2e3023",
               camo_scale=0.45, rough=0.95, weave=9.0, weave_amount=0.2, wrinkle=0.5, wrinkle_scale=2.0,
               net={"cell": 0.2, "gap": 0.06, "gap_color": "#191812"},
               dust=0.4, dust_up=0.5, grime=0.3, decals=False, bump=0.8)
    W, D = 8.4, 8.0  # along the parapet (tangent) x across (radial)
    nx, ny = 42, 40
    r_mid = 10.5
    sheet = cloth.grid_sheet(W, D, nx, ny)

    def height(r):
        if r < 7.0:
            return FLOOR + 0.3
        if r < POLE_R:
            return FLOOR + 0.3 + (POLE_TOP + 0.1 - FLOOR - 0.3) * (r - 7.0) / (POLE_R - 7.0)
        if r < 12.9:
            return POLE_TOP + 0.1 + (FLOOR + 2.5 - POLE_TOP - 0.1) * (r - POLE_R) / (12.9 - POLE_R)
        return FLOOR + 2.5 - (r - 12.9) * 1.2

    th = math.radians(NET_DEG)
    radial_dir = Vector((math.sin(th), math.cos(th), 0))
    tangent = Vector((math.cos(th), -math.sin(th), 0))
    centre = Vector(polar(r_mid, NET_DEG))
    for v in sheet.verts:
        p2 = centre + tangent * v.co.x + radial_dir * v.co.y
        v.co = Vector((p2.x, p2.y, height(p2.xy.length) + 0.12))
    pins = [Vector(polar(POLE_R, deg, POLE_TOP + 0.22)) for deg in NET_POLES]
    stakes = [(centre + tangent * (k * W / 2 * 0.9) + radial_dir * (-D / 2)).xy for k in (-1, 0, 1)]

    def pinned(co):
        co = Vector(co)
        return any((co - pp).length < 0.3 for pp in pins) or any((co.xy - st).length < 0.25 for st in stakes)

    colliders = [cloth._plane(80, FLOOR)]
    # Bags near the net as collision (their game meshes), the parapet's end
    # and the stores underneath.
    near = [pl for pl in placed if abs(((pl[4] % 360) - NET_DEG + 180) % 360 - 180) < 40]
    bag_col = bmesh.new()
    for size, at, rot, scale, _deg in near:
        box = geo.box(size[0] * scale[0], size[1] * scale[1], size[2] * scale[2] * 0.95, bevel=0.15, segments=2)
        geo.transform(box, at=(at[0], at[1], at[2] + size[2] * 0.5), rot=rot)
        me = bmesh_to_mesh(box)
        bag_col.from_mesh(me)
    colliders.append(bag_col)
    stores = bmesh.new()
    boxes = [(r, deg, 0.84 * (lvl + 1) + 0.05) for r, deg, lvl in AMMO_STACK] + [(r, deg, 1.45) for r, deg in WATER_CANS]
    for r, deg, h in boxes:
        x, y, _z = polar(r, deg)
        box = geo.box(1.25, 0.7, h, bevel=0.1)
        geo.transform(box, at=(x, y, FLOOR + h / 2), rot=(0, 0, -deg + 90))
        stores.from_mesh(bmesh_to_mesh(box))
    colliders.append(stores)
    wall = geo.lathe([(12.8, FLOOR), (13.5, FLOOR - 0.3), (13.6, FLOOR - 7.0)], verts=64, close_top=False, close_bottom=False)
    colliders.append(wall)
    high, low = cloth.drape(sheet, nx, ny, colliders, pinned, step=2, frames=110)
    net = a.part("Net", path="Static/CamoNet", tex="net", query=False, material="Fabric", smooth_angle=70)
    net.add(low, "camo_net")
    return high


def bmesh_to_mesh(bm):
    import bpy

    me = bpy.data.meshes.new("_col")
    bm.to_mesh(me)
    bm.free()
    return me


# --- turret -------------------------------------------------------------------

def turret_yaw(a):
    a.material("seat", kind="fabric", color="#3b3a2c", rough=0.8, wrinkle=0.3, dust=0.4)
    y = a.part("Mount", path="TurretYaw", tex="turret", query=False, material="Metal")
    y.add(geo.cylinder(1.35, 0.45, verts=32, bevel=0.06), "olive_dark_p", at=(0, 0, -2.85))
    for i in range(12):
        ang = 2 * math.pi * i / 12
        y.add(geo.cylinder(0.07, 0.1, verts=6, bevel=0.0), "steel_dark_p", at=(1.2 * math.cos(ang), 1.2 * math.sin(ang), -2.58))
    plate = [(-1.35, -3.9), (1.35, -3.9), (1.6, -1.2), (1.6, 1.4), (-1.6, 1.4), (-1.6, -1.2)]
    y.add(geo.prism(plate, 0.18, bevel=0.05), "olive_p", at=(0, 0, -2.5))
    for sx in (-1, 1):
        prof = [(-1.3, -2.45), (1.3, -2.45), (0.75, 0.1), (0.35, 0.55), (-0.35, 0.55), (-0.85, 0.1)]
        y.add(geo.side_prism(prof, 0.18, bevel=0.05), "olive_p", at=(sx * 1.3, 0, 0))
        y.add(geo.cylinder(0.48, 0.34, verts=20, bevel=0.05), "olive_dark_p", at=(sx * 1.47, 0, 0), rot=(0, 90, 0))
        y.add(geo.cylinder(0.2, 0.1, verts=12, bevel=0.02), "handle", at=(sx * 1.68, 0, 0), rot=(0, 90, 0))
        y.add(geo.box(0.1, 0.18, 2.2, bevel=0.03), "olive_dark_p", at=(sx * 1.43, -0.1, -1.3), rot=(12, 0, 0))
    # Gunner seat on a post behind the gun, with a footrest bar.
    y.add(geo.cylinder(0.14, 1.0, verts=10), "steel_dark_p", at=(0, -3.2, -1.95))
    y.add(geo.box(1.25, 1.0, 0.22, bevel=0.08), "olive_dark_p", at=(0, -3.1, -1.4))
    y.add(geo.box(1.1, 0.9, 0.16, bevel=0.07), "seat", at=(0, -3.1, -1.21))
    y.add(geo.box(1.1, 0.16, 1.05, bevel=0.07), "seat", at=(0, -3.62, -0.62), rot=(-12, 0, 0))
    y.add(geo.box(1.2, 0.1, 1.1, bevel=0.04), "olive_dark_p", at=(0, -3.72, -0.64), rot=(-12, 0, 0))
    y.add(geo.pipe_path([(-0.8, -2.1, -2.35), (-0.8, -1.8, -2.05), (0.8, -1.8, -2.05), (0.8, -2.1, -2.35)], 0.06, verts=6), "handle")
    # Traverse handwheel housing on the right plate (bare steel from use).
    y.add(geo.box(0.35, 0.6, 0.6, bevel=0.05), "olive_dark_p", at=(1.6, -0.9, -1.5))
    y.add(geo.torus(0.35, 0.04, verts=16, ring_verts=6), "handle", at=(1.82, -0.9, -1.5), rot=(0, 90, 0))
    y.add(geo.cylinder(0.04, 0.22, verts=6), "handle", at=(1.92, -0.62, -1.5), rot=(0, 90, 0))


def turret_gun(a, smalls):
    a.material("receiver", base="steel_dark", rough=0.5, dust=0.35, photo={"id": "green_metal_rust", "scale": 2.4, "rough": 0.6, "height": 0.4})
    a.material("grip", base="rubber", color="#1c1a16")
    a.material("pod", base="olive_p", wear=0.5, marks=[{"lo": (1.5, 1.2, -2.0), "hi": (5.0, 1.45, 2.0), "color": "#c9a227"}])
    a.material("rocket_nose", base="olive_dark_p", color="#4d5236", marks=[{"lo": (1.5, 2.02, -2.0), "hi": (5.0, 2.09, 2.0), "color": "#c9a227"}])
    a.material("missile_body", kind="paint", color="#b3a887", rough=0.5, wear=0.35, dust=0.45, grime=0.5, dust_color=DUST_OCHRE,
               chip_style="blotch", chip_scale=7.0, under="#7a7b78",
               marks=[{"lo": (-5, 1.35, -1), "hi": (-1, 1.5, 2), "color": "#c9a227"}, {"lo": (-5, -0.2, -1), "hi": (-1, -0.05, 2), "color": "#5a3a22"}])
    a.material("seeker", base="glass", color="#20282c", rough=0.05)

    g = a.part("Cradle", path="TurretGun", tex="turret", query=False, material="Metal")
    g.add(geo.cylinder(0.24, 4.8, verts=16, bevel=0.03), "olive_dark_p", rot=(0, 90, 0))
    g.add(geo.box(1.05, 3.2, 0.32, bevel=0.06), "olive_p", at=(0, 0.5, -0.42))
    # Gun shield: armour plates around a barrel slot, raked back 10 degrees.
    rake = (-10, 0, 0)
    sy = 2.35
    g.add(geo.box(4.4, 0.14, 1.45, bevel=0.05), "shield", at=(0, sy, -0.95), rot=rake)
    for sx in (-1, 1):
        g.add(geo.tapered_box(1.65, 0.14, 1.6, top_scale=(0.72, 1.0), top_shift=(sx * 0.22, 0.0), bevel=0.05), "shield", at=(sx * 1.37, sy - 0.12, 0.55), rot=rake)
        g.add(geo.box(0.9, 0.06, 0.08, bevel=0.02), "olive_dark_p", at=(sx * 1.3, sy - 0.2, 0.75), rot=rake)
        g.add(geo.box(0.7, 0.14, 2.6, bevel=0.05), "shield", at=(sx * 2.45, sy - 0.35, -0.2), rot=(-10, 0, sx * -28))
        g.add(geo.box(0.14, 0.5, 0.14, bevel=0.03), "olive_dark_p", at=(sx * 0.9, sy - 0.4, -0.35))
        # Grab handle welded to each wing plate (worn to bare steel).
        g.add(geo.pipe_path([(sx * 2.35, sy - 0.55, 0.45), (sx * 2.35, sy - 0.75, 0.4), (sx * 2.35, sy - 0.75, -0.4), (sx * 2.35, sy - 0.55, -0.45)], 0.045, verts=6), "handle")
    g.add(geo.box(1.1, 0.14, 0.5, bevel=0.04), "shield", at=(0, sy - 0.2, 1.1), rot=rake)
    # Weld beads along the plate joints and bolt rows on the gunner's side
    # (built in the lower plate's frame, then raked with it).
    for pts in ([(-2.15, -0.2, 0.76), (-0.6, -0.2, 0.76)], [(0.6, -0.2, 0.76), (2.15, -0.2, 0.76)]):
        g.add(geo.pipe_path(pts, 0.04, verts=5), "weld", at=(0, sy, -0.95), rot=rake)
    for k in range(9):
        bolt = geo.transform(geo.cylinder(0.045, 0.05, verts=6, bevel=0.0), at=(-2.0 + k * 0.5, -0.085, 0.45), rot=(90, 0, 0))
        g.add(bolt, "steel_dark_p", at=(0, sy, -0.95), rot=rake)
    for sx in (-1, 1):
        for k in range(3):
            bolt = geo.transform(geo.cylinder(0.045, 0.05, verts=6, bevel=0.0), at=(sx * 2.05, -0.085, -0.45 + k * 0.35), rot=(90, 0, 0))
            g.add(bolt, "steel_dark_p", at=(0, sy, -0.95), rot=rake)
    for sx in (-1.9, -1.0, 1.0, 1.9):
        for zz in (-1.5, 1.2):
            g.add(geo.cylinder(0.06, 0.08, verts=6, bevel=0.0), "steel_dark_p", at=(sx, sy + 0.08 + (0.03 if zz > 0 else -0.25) * 0.5 - 0.02 * zz, zz), rot=(-100, 0, 0))
    for sx in (-1, 1):
        g.add(geo.box(0.95, 1.3, 0.7, bevel=0.06), "olive_dark_p", at=(sx * 2.1, 0.15, 0.05))
    # Unit marking on the gunner's side of the shield.
    stencil(a, "C-3-41", (-1.35, sy - 0.25, -0.95), (0, -0.985, 0.17), 0.3, wear=0.4, seed=70)
    stencil(a, "7.62", (1.35, sy - 0.25, -0.95), (0, -0.985, 0.17), 0.3, wear=0.45, seed=71)

    mg = a.part("Gun", path="TurretGun/MachineGun", tex="weapons", query=False, material="Metal")
    mg.add(geo.box(0.78, 2.9, 0.8, bevel=0.05), "receiver", at=(0, 0.25, BARREL_Z))
    mg.add(geo.box(0.84, 1.5, 0.14, bevel=0.04), "receiver", at=(0, 0.75, BARREL_Z + 0.46))
    mg.add(geo.box(0.9, 0.18, 0.95, bevel=0.04), "receiver", at=(0, -1.3, BARREL_Z))
    mg.add(geo.box(0.95, 0.55, 0.95, bevel=0.05), "receiver", at=(0, 1.8, BARREL_Z))
    for sx in (-1, 1):  # side plates rivets + spade grips
        for i in range(5):
            mg.add(geo.cylinder(0.04, 0.05, verts=6, bevel=0.0), "handle", at=(sx * 0.4, -0.8 + i * 0.5, BARREL_Z - 0.2), rot=(0, 90, 0))
        mg.add(geo.pipe_path([(sx * 0.3, -1.38, BARREL_Z - 0.3), (sx * 0.32, -1.62, BARREL_Z - 0.2), (sx * 0.32, -1.72, BARREL_Z + 0.35)], 0.05, verts=6), "handle")
        mg.add(geo.cylinder(0.085, 0.5, verts=10, bevel=0.03), "grip", at=(sx * 0.32, -1.7, BARREL_Z + 0.12), rot=(-8, 0, 0))
    mg.add(geo.box(0.32, 0.12, 0.2, bevel=0.03), "handle", at=(0, -1.55, BARREL_Z + 0.2))
    mg.add(geo.box(0.12, 0.35, 0.12, bevel=0.03), "handle", at=(0.47, 0.5, BARREL_Z + 0.05))
    mg.add(geo.cylinder(0.07, 0.25, verts=8), "handle", at=(0.6, 0.5, BARREL_Z + 0.05), rot=(0, 90, 0))
    # Reflex sight on the top cover.
    mg.add(geo.box(0.34, 0.5, 0.3, bevel=0.05), "olive_dark_p", at=(0, -0.55, BARREL_Z + 0.68))
    mg.add(geo.box(0.3, 0.05, 0.26, bevel=0.02), "seeker", at=(0, -0.3, BARREL_Z + 0.7))
    # Barrel: perforated jacket, barrel, carry handle and muzzle brake.
    mg.add(along_y(geo.tube(0.26, 0.2, 1.6, verts=16), (0, 2.85, BARREL_Z)), "receiver")
    for yy in (2.15, 2.6, 3.05, 3.5):
        mg.add(along_y(geo.cylinder(0.29, 0.08, verts=16, bevel=0.01), (0, yy, BARREL_Z)), "receiver")
    mg.add(along_y(geo.cylinder(0.13, 3.6, verts=12, bevel=0.0), (0, 5.0, BARREL_Z)), "receiver")
    mg.add(geo.pipe_path([(0, 3.9, BARREL_Z + 0.1), (0, 4.0, BARREL_Z + 0.42), (0, 4.5, BARREL_Z + 0.42), (0, 4.6, BARREL_Z + 0.1)], 0.045, verts=6), "handle")
    mg.add(along_y(geo.tube(0.2, 0.09, 0.55, verts=12), (0, 7.02, BARREL_Z)), "receiver")
    for sx in (-1, 1):
        mg.add(geo.box(0.06, 0.3, 0.16, bevel=0.01), "receiver", at=(sx * 0.2, 7.02, BARREL_Z))
    # Ammo can on the left feeding the belt into the tray.
    mg.add(geo.box(0.55, 1.15, 0.8, bevel=0.05), "olive_p", at=(-0.85, 0.55, BARREL_Z - 0.2))
    mg.add(geo.box(0.6, 1.2, 0.08, bevel=0.02), "olive_p", at=(-0.85, 0.55, BARREL_Z + 0.22))
    mg.add(geo.box(0.22, 0.9, 0.06, bevel=0.02), "olive_dark_p", at=(-0.5, 0.75, BARREL_Z + 0.3))  # feed tray
    stencil(a, "7.62", (-1.13, 0.55, BARREL_Z - 0.15), (-1, 0, 0), 0.2, up=(0, 0, 1), wear=0.35, seed=72)

    belt = a.part("Belt", path="TurretGun/MachineGun", tex="smalls", query=False, material="Metal")
    belt_along(belt, smalls, [(-1.0, 0.75, BARREL_Z + 0.2), (-0.95, 0.75, BARREL_Z + 0.44), (-0.8, 0.75, BARREL_Z + 0.56),
                              (-0.6, 0.75, BARREL_Z + 0.56), (-0.42, 0.75, BARREL_Z + 0.42)], 7, up=(0, 0, -1))

    pod = a.part("Pod", path="TurretGun/RocketPod", tex="weapons", query=False, material="Metal")
    pod.add(along_y(geo.cylinder(0.95, 3.2, verts=24, bevel=0.08), (POD_X, 0.4, POD_Z)), "pod")
    for yy in (-1.15, 1.95):
        pod.add(along_y(geo.cylinder(1.0, 0.18, verts=24, bevel=0.04), (POD_X, yy, POD_Z)), "olive_dark_p")
    tubes = [(0.0, 0.0)] + [(0.58 * math.cos(math.pi / 6 + k * math.pi / 3), 0.58 * math.sin(math.pi / 6 + k * math.pi / 3)) for k in range(6)]
    for tx, tz in tubes:
        pod.add(along_y(geo.tube(0.26, 0.21, 0.2, verts=12), (POD_X + tx, 2.1, POD_Z + tz)), "olive_dark_p")
        pod.add(along_y(geo.lathe([(0.2, 0.0), (0.2, 0.12), (0.14, 0.3), (0.05, 0.42), (0.0, 0.45)], verts=10), (POD_X + tx, 1.72, POD_Z + tz)), "rocket_nose")
        pod.add(along_y(geo.tube(0.24, 0.12, 0.12, verts=10), (POD_X + tx, -1.3, POD_Z + tz)), "steel_dark_p")
    pod.add(geo.box(0.5, 1.0, 0.35, bevel=0.05), "olive_dark_p", at=(POD_X, 0.3, POD_Z + 1.0))
    pod.add(geo.pipe_path([(POD_X - 0.4, -0.3, POD_Z + 1.0), (POD_X - 0.4, 0.0, POD_Z + 1.3), (POD_X + 0.4, 0.0, POD_Z + 1.3), (POD_X + 0.4, -0.3, POD_Z + 1.0)], 0.05, verts=6), "handle")
    stencil(a, "RKT 70", (POD_X - 0.96, 0.2, POD_Z), (-1, 0, 0), 0.24, up=(0, 0, 1), wear=0.35, seed=73)

    rack = a.part("Rail", path="TurretGun/MissileRack", tex="weapons", query=False, material="Metal")
    rack.add(geo.box(1.35, 3.4, 0.28, bevel=0.05), "olive_dark_p", at=(RACK_X, 0.35, 0.02))
    for sx in (-0.33, 0.33):
        rack.add(geo.box(0.16, 3.2, 0.16, bevel=0.03), "steel_dark_p", at=(RACK_X + sx, 0.35, 0.22))
    rack.add(geo.box(0.9, 0.9, 0.55, bevel=0.06), "olive_dark_p", at=(RACK_X, -0.9, -0.36))
    rack.add(geo.cylinder(0.16, 0.9, verts=12, bevel=0.03), "olive_p", at=(RACK_X - 0.32, -0.95, -0.72), rot=(0, 90, 0))
    for i, sx in enumerate((-0.33, 0.33)):
        m = a.part(f"Missile{i + 1}", path="TurretGun/MissileRack", tex="weapons", query=False, material="Metal")
        mx, mz = RACK_X + sx, 0.52
        body = [(0.0, -1.55), (0.12, -1.55), (0.14, -1.45), (0.2, -1.4), (0.2, 1.75), (0.18, 1.95), (0.12, 2.2), (0.0, 2.28)]
        m.add(along_y(geo.lathe(body[:5], verts=16, close_top=True), (mx, 0.0, mz)), "missile_body")
        m.add(along_y(geo.lathe([(0.2, 1.75), (0.18, 1.95), (0.12, 2.2), (0.0, 2.3)], verts=16, close_bottom=False), (mx, 0.0, mz)), "seeker")
        for k in range(4):
            ang = 45 + k * 90
            fin = geo.prism([(0.18, -0.2), (0.62, -0.02), (0.62, 0.25), (0.18, 0.35)], 0.03, bevel=0.0)
            m.add(fin, "missile_body", at=(mx, -1.15, mz), rot=(-90, 0, ang))
            canard = geo.prism([(0.18, -0.05), (0.38, 0.05), (0.38, 0.15), (0.18, 0.2)], 0.025, bevel=0.0)
            m.add(canard, "missile_body", at=(mx, 1.55, mz), rot=(-90, 0, ang))
    a.marker("Muzzle", "TurretGun", (0, 7.4, BARREL_Z), size=(0.3, 0.3, 0.3), axis=(0, 1, 0))
    a.marker("RocketMuzzle", "TurretGun/RocketPod", (POD_X, 2.3, POD_Z), size=(0.3, 0.3, 0.3), axis=(0, 1, 0))
    a.marker("MissileMuzzle", "TurretGun/MissileRack", (RACK_X - 0.33, 2.45, 0.52), size=(0.3, 0.3, 0.3), axis=(0, 1, 0))


def build(**kw):
    a = Asset("Emplacement", pivot=(0, 0, 0), tex_size=1024)
    a.primary = None
    a.zmin = FLOOR
    a.texture_group("floor", 1024, metal=False)
    a.texture_group("outer", 1024, metal=False)
    a.texture_group("bags", 1024, sheet=True, metal=False)
    a.texture_group("net", 512, metal=False)
    a.texture_group("smalls", 256, sheet=True)
    for g in ("props", "stores", "turret", "weapons"):
        a.texture_group(g, 1024)
    for path in ("TurretYaw", "TurretGun", "TurretGun/MachineGun"):
        a.pivot(path, (0, 0, 0))
    materials(a)
    smalls = small_templates(a)
    bunker(a)
    placed = sandbags(a)
    props(a, smalls)
    camo_net(a, placed)
    turret_yaw(a)
    turret_gun(a, smalls)
    turret = ["Mount", "Cradle", "Gun", "Belt", "Pod", "Rail", "Missile1", "Missile2"]
    views = [
        ("", (1.0, 1.25, 0.75)),
        ("_player", (0.0, -1.6, 0.95), turret),
        ("_turret", (1.0, 1.1, 0.45), turret),
        ("_rear", (-1.0, -1.1, 0.8)),
        # The in-game turret camera (13 back, 8 up, FieldOfView 70, pitch -4).
        {"label": "_cam_turret", "pos": (0, -13, 8), "look": (0, 87, 8 - 100 * math.tan(math.radians(4))), "fov": 70, "res": (1920, 1080)},
        # Same camera turned to the ammo point (yaw 110 right).
        {"label": "_cam_right", "pos": (-12.2, 4.45, 8), "look": (-12.2 + 94, 4.45 - 34.2, 1.0), "fov": 70},
        {"label": "_close_bags", "pos": (-2.5, -1.0, -1.0), "look": (-7.5, 7.0, -4.6), "fov": 40},
        {"label": "_close_gun", "pos": (-1.6, -4.2, 1.2), "look": (0.0, 1.5, 0.0), "fov": 40},
        {"label": "_close_net", "pos": (4.9, -2.7, 0.6), "look": (8.0, -6.9, -4.2), "fov": 55},
    ]
    return a.finish(views=views, **kw)
