"""Emplacement: reinforced-concrete gun pit on the mesa knob with a
sandbag parapet, props, and the three-weapon turret (heavy machine gun,
7-tube rocket pod, twin AA missile rail).

Asset origin = turret pivot (world Config.TURRET_PIVOT). Bunker top
surface at z = -6. Blender +Y = forward (Roblox -Z).

Models: Static, TurretYaw (yaws about the pivot), TurretGun (pitches about
the pivot) with sub-models MachineGun, RocketPod, MissileRack; markers
Muzzle (TurretGun), RocketMuzzle (RocketPod), MissileMuzzle (MissileRack);
missile meshes Missile1 / Missile2 (hidden by the client when unloaded).
"""
import math
import random

from mathutils import Vector

from rmh import geo, images
from rmh.asset import Asset

FLOOR = -6.0
BUNKER_R = 13.5
BAG_L, BAG_D, BAG_H = 2.2, 1.15, 0.6
GAP_DEG = 32  # half-angle of the rear opening in the parapet
BARREL_Z = 0.2
POD_X, POD_Z = 3.2, 0.3
RACK_X = -3.25

rng = random.Random(1307)


def along_y(bm, at):
    """Primitive built along +Z, laid along +Y (forward)."""
    return geo.transform(bm, at, rot=(-90, 0, 0))


def along_x(bm, at):
    return geo.transform(bm, at, rot=(0, 90, 0))


# --- small reusable shapes ---------------------------------------------------

def sandbag():
    bm = geo.box(1, 1, 1, bevel=0)
    import bmesh

    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=2, use_grid_fill=True)
    for v in bm.verts:
        nx, ny, nz = v.co.x * 2, v.co.y * 2, v.co.z * 2
        end = 1 - 0.28 * nx ** 6
        y = v.co.y * (1 - 0.22 * nz ** 2) * end
        z = v.co.z * (1 - 0.3 * nx ** 4) * (1 - 0.12 * ny ** 2)
        if nz > 0:
            z += 0.09 * (1 - nx ** 2) * (1 - ny ** 2)
        x = v.co.x * (1 - 0.05 * nz ** 2)
        v.co = Vector((x * BAG_L, y * BAG_D, z * BAG_H * 1.1))
    bmesh.ops.smooth_vert(bm, verts=list(bm.verts), factor=0.35, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    return bm


def cartridge(p, at, rot, scale=1.0):
    p.add(geo.cylinder(0.06 * scale, 0.42 * scale, verts=6, bevel=0.0), "brass", at=at, rot=rot)


# --- static -------------------------------------------------------------------

def bunker(a):
    a.material("bunker_concrete", base="concrete", color="#8e7c60", grime=0.9, dust=0.8, dust_height=3.0)
    a.material("pedestal", base="olive_dark", wear=0.6)
    a.material("ladder", base="steel_dark", dust=0.5)
    b = a.part("Bunker", path="Static", tex="static", collide=True, query=True, material="Concrete")
    prof = [(0.0, FLOOR), (12.8, FLOOR), (13.15, FLOOR - 0.05), (13.5, FLOOR - 0.3), (13.55, FLOOR - 0.75),
            (13.35, FLOOR - 0.85), (13.35, FLOOR - 3.6), (13.45, FLOOR - 3.7), (13.6, FLOOR - 7.0), (14.3, FLOOR - 8.0)]
    b.add(geo.lathe(prof, verts=64, close_top=False, close_bottom=False), "bunker_concrete")
    # Raised plinth around the turret pedestal.
    b.add(geo.cylinder(2.6, 0.3, verts=32, bevel=0.08), "bunker_concrete", at=(0, 0, FLOOR + 0.15))
    # Drain scuppers and tie-down rings around the lip.
    for i in range(8):
        th = math.radians(22.5 + i * 45)
        b.add(geo.box(0.6, 0.5, 0.3, bevel=0.05), "ladder", at=(13.45 * math.sin(th), 13.45 * math.cos(th), FLOOR - 0.5), rot=(0, 0, -math.degrees(th)))
    # Rear access ladder down the bunker wall.
    for sx in (-1, 1):
        b.add(geo.box(0.12, 0.12, 8.0, bevel=0.02), "ladder", at=(sx * 0.7, -13.75, FLOOR - 3.6))
        b.add(geo.box(0.12, 0.6, 0.12, bevel=0.02), "ladder", at=(sx * 0.7, -13.45, FLOOR + 0.35))
    for i in range(10):
        b.add(geo.cylinder(0.05, 1.4, verts=6, bevel=0.0), "ladder", at=(0, -13.75, FLOOR - 7.2 + i * 0.75), rot=(0, 90, 0))

    p = a.part("Pedestal", path="Static", tex="static", query=False, material="Metal")
    p.add(geo.cylinder(1.9, 0.25, verts=24, bevel=0.06), "pedestal", at=(0, 0, FLOOR + 0.42))
    p.add(geo.cylinder(1.25, 2.6, verts=24, r_top=0.95, bevel=0.05), "pedestal", at=(0, 0, FLOOR + 1.85))
    p.add(geo.cylinder(1.25, 0.18, verts=24, bevel=0.04), "pedestal", at=(0, 0, FLOOR + 3.1))
    for i in range(10):
        ang = 2 * math.pi * i / 10
        p.add(geo.cylinder(0.09, 0.14, verts=6, bevel=0.02), "ladder", at=(1.62 * math.cos(ang), 1.62 * math.sin(ang), FLOOR + 0.58))
    for i in range(4):  # gusset ribs
        ang = math.pi / 4 + i * math.pi / 2
        p.add(geo.prism([(0, 0), (0.55, 0), (0, 1.3)], 0.12, bevel=0.02), "pedestal",
              at=(1.05 * math.cos(ang), 1.05 * math.sin(ang), FLOOR + 0.55), rot=(90, 0, math.degrees(ang)))


def sandbags(a):
    # Kept mid-value (not pale) so close muzzle-flash light doesn't blow them out.
    a.material("bag_a", base="sandbag", color="#978158")
    a.material("bag_b", base="sandbag", color="#85704d")
    a.material("bag_c", base="sandbag", color="#a18c65", wrinkle=1.0)
    sections = {"SandbagsLeft": [], "SandbagsFront": [], "SandbagsRight": []}
    rows = [(11.55, 0.0), (12.75, 0.5)]
    for course in range(4):
        for row, (r, stagger) in enumerate(rows):
            circ = 2 * math.pi * r * (360 - 2 * GAP_DEG) / 360
            n = int(circ / (BAG_L * 0.97))
            span = 360 - 2 * GAP_DEG
            for i in range(n):
                t = (i + 0.5 + ((course + row) % 2) * 0.5 * (1 if i < n - 1 else 0)) / n
                deg = 180 + GAP_DEG + t * span  # sweep from rear-left round the front
                th = math.radians(deg)
                x, y = r * math.sin(th), r * math.cos(th)
                zc = FLOOR + BAG_H * 0.5 + course * BAG_H * 0.88 + rng.uniform(-0.03, 0.03)
                if row == 0 and course == 3:
                    continue  # inner row one course lower: stepped parapet
                rot = (rng.uniform(-3, 3), rng.uniform(-4, 4), -deg + rng.uniform(-4, 4))
                mat = rng.choice(["bag_a", "bag_a", "bag_b", "bag_c"])
                sx = rng.uniform(0.93, 1.05)
                bm = sandbag()
                geo.transform(bm, scale=(sx, rng.uniform(0.95, 1.05), rng.uniform(0.9, 1.05)))
                key = "SandbagsLeft" if deg < 300 else ("SandbagsFront" if deg < 420 else "SandbagsRight")
                sections[key].append((bm, mat, (x, y, zc), rot))
        # Rear opening end caps: bags laid radially.
    for name, bags in sections.items():
        part = a.part(name, path="Static", tex="bags", query=True, collide=False, material="Fabric", smooth_angle=80)
        for bm, mat, at, rot in bags:
            part.add(bm, mat, at=at, rot=rot)


def props(a):
    a.material("can_olive", base="olive", wear=0.7)
    a.material("crate_wood", base="olive_dark", under="#7a6040", under_metal=0.0, under_rough=0.8, wear=0.6)
    a.material("jerry", base="tan", color="#8a7a50", wear=0.6)
    a.material("rope", kind="fabric", color="#8c7a58", weave=60.0, wrinkle=0.2, rough=0.9, dust=0.3)
    a.material("sand_drift", kind="flat", color="#b58a60", rough=0.95, dust=0.4, bump=0.5)
    a.material("radio", base="olive_dark", wear=0.5)
    p = a.part("Props", path="Static", tex="props", query=False, material="Metal")
    # Ammo cans, two stacks near the gunner.
    for i, (x, y, z, rz) in enumerate([(4.2, -4.2, 0, 8), (4.2, -5.0, 0, 2), (4.25, -4.6, 1, 5), (5.4, -4.4, 0, -6), (5.4, -5.2, 0, 3)]):
        zc = FLOOR + 0.42 + z * 0.8
        p.add(geo.box(1.15, 0.6, 0.8, bevel=0.05), "can_olive", at=(x, y, zc), rot=(0, 0, rz))
        p.add(geo.box(1.2, 0.66, 0.1, bevel=0.03), "can_olive", at=(x, y, zc + 0.36), rot=(0, 0, rz))
        p.add(geo.box(0.5, 0.08, 0.06, bevel=0.02), "ladder", at=(x, y, zc + 0.46), rot=(0, 0, rz))
    # Rocket reload crates (wood, rope handles).
    for k, (x, y, z, rz) in enumerate([(-5.3, -5.6, 0, 20), (-5.1, -5.5, 1, 14), (-7.2, -3.4, 0, 70)]):
        zc = FLOOR + 0.55 + z * 1.1
        p.add(geo.box(3.6, 1.3, 1.1, bevel=0.06), "crate_wood", at=(x, y, zc), rot=(0, 0, rz))
        for sx in (-1, 1):
            p.add(geo.box(0.22, 1.36, 1.16, bevel=0.03), "crate_wood", at=(x + sx * 1.5 * math.cos(math.radians(rz)), y + sx * 1.5 * math.sin(math.radians(rz)), zc), rot=(0, 0, rz))
        a.decal(images.get("stripes", count=4, angle=0), (x, y, zc + 0.55), (0, 0, 1), (1.2, 0.4, 0.3), color="#c9a227")
    # Spare missile canisters on a low rack.
    for i, x in enumerate((-8.2, -8.9)):
        p.add(geo.cylinder(0.32, 4.0, verts=16, bevel=0.04), "can_olive", at=(x, 1.0, FLOOR + 0.6 + i * 0.05), rot=(-90, 0, 0))
        for yy in (-0.6, 2.6):
            p.add(geo.cylinder(0.36, 0.15, verts=16, bevel=0.03), "can_olive", at=(x, yy, FLOOR + 0.6 + i * 0.05), rot=(-90, 0, 0))
    for yy in (-0.3, 2.3):
        p.add(geo.box(1.8, 0.3, 0.28, bevel=0.03), "crate_wood", at=(-8.55, yy, FLOOR + 0.14))
    # Jerrycans against the parapet.
    for x, y, rz in [(7.6, 5.4, 38), (8.2, 4.6, 45), (7.0, 6.2, 30)]:
        p.add(geo.box(0.95, 0.55, 1.35, bevel=0.08), "jerry", at=(x, y, FLOOR + 0.68), rot=(0, 0, rz))
        p.add(geo.box(0.5, 0.12, 0.14, bevel=0.03), "jerry", at=(x, y, FLOOR + 1.42), rot=(0, 0, rz))
        p.add(geo.cylinder(0.1, 0.18, verts=8, bevel=0.02), "jerry", at=(x + 0.3, y + 0.1, FLOOR + 1.42), rot=(0, 0, rz))
    # Field radio on a crate with a whip antenna.
    p.add(geo.box(1.3, 0.9, 0.9, bevel=0.05), "crate_wood", at=(6.4, -1.2, FLOOR + 0.45), rot=(0, 0, -15))
    p.add(geo.box(0.9, 0.55, 0.7, bevel=0.05), "radio", at=(6.4, -1.2, FLOOR + 1.25), rot=(0, 0, -15))
    p.add(geo.cylinder(0.025, 3.2, verts=5, bevel=0.0), "ladder", at=(6.7, -1.3, FLOOR + 3.2), rot=(4, 3, 0))
    # Sand drifts along the inside of the parapet and in the corners.
    for i in range(9):
        th = math.radians(180 + GAP_DEG + 10 + i * (360 - 2 * GAP_DEG - 20) / 8)
        r = 10.7
        p.add(geo.sphere(1.0, 12, 6, scale=(rng.uniform(1.6, 2.6), 0.9, 0.22)), "sand_drift", at=(r * math.sin(th), r * math.cos(th), FLOOR), rot=(0, 0, -math.degrees(th)))

    c = a.part("Casings", path="Static", tex="props", query=False, shadow=False, material="Metal")
    for i in range(46):
        r = rng.uniform(1.8, 4.6)
        th = rng.uniform(-math.pi * 0.9, math.pi * 0.9)
        cartridge(c, (r * math.sin(th), r * math.cos(th) - 0.8, FLOOR + 0.07), (90, 0, rng.uniform(0, 360)), 0.9)

    s = a.part("Searchlight", path="Static", tex="props", query=False, material="Metal")
    sx, sy = -8.6, -6.2
    for i in range(3):
        ang = math.radians(90 + i * 120)
        s.add(geo.pipe_path([(sx, sy, FLOOR + 2.6), (sx + 1.1 * math.cos(ang), sy + 1.1 * math.sin(ang), FLOOR)], 0.06, verts=6), "ladder")
    s.add(geo.cylinder(0.12, 0.8, verts=8), "ladder", at=(sx, sy, FLOOR + 2.95))
    s.add(geo.box(1.5, 0.15, 0.9, bevel=0.03), "radio", at=(sx, sy, FLOOR + 3.45))
    s.add(geo.cylinder(0.7, 1.3, verts=24, r_top=0.78, bevel=0.06), "radio", at=(sx, sy + 0.1, FLOOR + 3.7), rot=(-90, 0, 0))
    s.add(geo.cylinder(0.82, 0.12, verts=24, bevel=0.03), "radio", at=(sx, sy + 0.8, FLOOR + 3.7), rot=(-90, 0, 0))
    s.add(geo.cylinder(0.72, 0.05, verts=24, bevel=0.0), "lens", at=(sx, sy + 0.85, FLOOR + 3.7), rot=(-90, 0, 0))
    a.attach("SearchlightBeam", "Searchlight", (sx, sy + 0.9, FLOOR + 3.7), axis=(0, 1, 0))


# --- turret -------------------------------------------------------------------

def turret_yaw(a):
    a.material("mount", base="olive", wear=0.55)
    a.material("mount_dark", base="olive_dark", wear=0.6)
    a.material("seat", kind="fabric", color="#3b3a2c", rough=0.8, wrinkle=0.3, dust=0.4)
    y = a.part("Mount", path="TurretYaw", tex="turret", query=False, material="Metal")
    y.add(geo.cylinder(1.35, 0.45, verts=32, bevel=0.06), "mount_dark", at=(0, 0, -2.85))
    for i in range(12):
        ang = 2 * math.pi * i / 12
        y.add(geo.cylinder(0.07, 0.1, verts=6, bevel=0.0), "steel", at=(1.2 * math.cos(ang), 1.2 * math.sin(ang), -2.58))
    plate = [(-1.35, -3.9), (1.35, -3.9), (1.6, -1.2), (1.6, 1.4), (-1.6, 1.4), (-1.6, -1.2)]
    y.add(geo.prism(plate, 0.18, bevel=0.05), "mount", at=(0, 0, -2.5))
    for sx in (-1, 1):
        prof = [(-1.3, -2.45), (1.3, -2.45), (0.75, 0.1), (0.35, 0.55), (-0.35, 0.55), (-0.85, 0.1)]
        y.add(geo.side_prism(prof, 0.18, bevel=0.05), "mount", at=(sx * 1.3, 0, 0))
        y.add(geo.cylinder(0.48, 0.34, verts=20, bevel=0.05), "mount_dark", at=(sx * 1.47, 0, 0), rot=(0, 90, 0))
        y.add(geo.cylinder(0.2, 0.1, verts=12, bevel=0.02), "steel", at=(sx * 1.68, 0, 0), rot=(0, 90, 0))
        # Stiffening rib on each yoke plate.
        y.add(geo.box(0.1, 0.18, 2.2, bevel=0.03), "mount_dark", at=(sx * 1.43, -0.1, -1.3), rot=(12, 0, 0))
    # Gunner seat on a post behind the gun, with a footrest bar.
    y.add(geo.cylinder(0.14, 1.0, verts=10), "steel_dark", at=(0, -3.2, -1.95))
    y.add(geo.box(1.25, 1.0, 0.22, bevel=0.08), "mount_dark", at=(0, -3.1, -1.4))
    y.add(geo.box(1.1, 0.9, 0.16, bevel=0.07), "seat", at=(0, -3.1, -1.21))
    y.add(geo.box(1.1, 0.16, 1.05, bevel=0.07), "seat", at=(0, -3.62, -0.62), rot=(-12, 0, 0))
    y.add(geo.box(1.2, 0.1, 1.1, bevel=0.04), "mount_dark", at=(0, -3.72, -0.64), rot=(-12, 0, 0))
    y.add(geo.pipe_path([(-0.8, -2.1, -2.35), (-0.8, -1.8, -2.05), (0.8, -1.8, -2.05), (0.8, -2.1, -2.35)], 0.06, verts=6), "steel_dark")
    # Traverse handwheel housing on the right plate.
    y.add(geo.box(0.35, 0.6, 0.6, bevel=0.05), "mount_dark", at=(1.6, -0.9, -1.5))
    y.add(geo.torus(0.35, 0.04, verts=16, ring_verts=6), "steel_dark", at=(1.82, -0.9, -1.5), rot=(0, 90, 0))


def turret_gun(a):
    a.material("shield", base="olive", wear=0.6, dust=0.55)
    a.material("receiver", base="steel_dark", rough=0.55, dust=0.35)
    a.material("grip", base="rubber", color="#1c1a16")
    a.material("belt", base="steel_dark")
    a.material("pod", base="olive", wear=0.5, marks=[{"lo": (1.5, 1.2, -2.0), "hi": (5.0, 1.45, 2.0), "color": "#c9a227"}])
    a.material("rocket_nose", base="olive_dark", color="#4d5236", marks=[{"lo": (1.5, 2.02, -2.0), "hi": (5.0, 2.09, 2.0), "color": "#c9a227"}])
    a.material("missile_body", kind="paint", color="#c9bb93", rough=0.45, wear=0.25, dust=0.35, grime=0.35,
               marks=[{"lo": (-5, 1.35, -1), "hi": (-1, 1.5, 2), "color": "#c9a227"}, {"lo": (-5, -0.2, -1), "hi": (-1, -0.05, 2), "color": "#5a3a22"}])
    a.material("seeker", base="glass", color="#20282c", rough=0.05)

    g = a.part("Cradle", path="TurretGun", tex="turret", query=False, material="Metal")
    g.add(geo.cylinder(0.24, 4.8, verts=16, bevel=0.03), "mount_dark", rot=(0, 90, 0))
    g.add(geo.box(1.05, 3.2, 0.32, bevel=0.06), "mount", at=(0, 0.5, -0.42))
    # Gun shield: armour plates around a barrel slot, raked back 10 degrees.
    rake = (-10, 0, 0)
    sy = 2.35
    g.add(geo.box(4.4, 0.14, 1.45, bevel=0.05), "shield", at=(0, sy, -0.95), rot=rake)
    for sx in (-1, 1):
        g.add(geo.tapered_box(1.65, 0.14, 1.6, top_scale=(0.72, 1.0), top_shift=(sx * 0.22, 0.0), bevel=0.05), "shield", at=(sx * 1.37, sy - 0.12, 0.55), rot=rake)
        g.add(geo.box(0.9, 0.06, 0.08, bevel=0.02), "mount_dark", at=(sx * 1.3, sy - 0.2, 0.75), rot=rake)
        g.add(geo.box(0.7, 0.14, 2.6, bevel=0.05), "shield", at=(sx * 2.45, sy - 0.35, -0.2), rot=(-10, 0, sx * -28))
        g.add(geo.box(0.14, 0.5, 0.14, bevel=0.03), "mount_dark", at=(sx * 0.9, sy - 0.4, -0.35))
    g.add(geo.box(1.1, 0.14, 0.5, bevel=0.04), "shield", at=(0, sy - 0.2, 1.1), rot=rake)
    for sx in (-1.9, -1.0, 1.0, 1.9):
        for zz in (-1.5, 1.2):
            g.add(geo.cylinder(0.06, 0.08, verts=6, bevel=0.0), "steel", at=(sx, sy + 0.08 + (0.03 if zz > 0 else -0.25) * 0.5 - 0.02 * zz, zz), rot=(-100, 0, 0))
    # Side arms carrying the rocket pod and missile rail.
    for sx in (-1, 1):
        g.add(geo.box(0.95, 1.3, 0.7, bevel=0.06), "mount_dark", at=(sx * 2.1, 0.15, 0.05))

    mg = a.part("Gun", path="TurretGun/MachineGun", tex="turret", query=False, material="Metal")
    mg.add(geo.box(0.78, 2.9, 0.8, bevel=0.05), "receiver", at=(0, 0.25, BARREL_Z))
    mg.add(geo.box(0.84, 1.5, 0.14, bevel=0.04), "receiver", at=(0, 0.75, BARREL_Z + 0.46))
    mg.add(geo.box(0.9, 0.18, 0.95, bevel=0.04), "receiver", at=(0, -1.3, BARREL_Z))
    mg.add(geo.box(0.95, 0.55, 0.95, bevel=0.05), "receiver", at=(0, 1.8, BARREL_Z))
    for sx in (-1, 1):  # side plates rivets + spade grips
        for i in range(5):
            mg.add(geo.cylinder(0.04, 0.05, verts=6, bevel=0.0), "steel", at=(sx * 0.4, -0.8 + i * 0.5, BARREL_Z - 0.2), rot=(0, 90, 0))
        mg.add(geo.pipe_path([(sx * 0.3, -1.38, BARREL_Z - 0.3), (sx * 0.32, -1.62, BARREL_Z - 0.2), (sx * 0.32, -1.72, BARREL_Z + 0.35)], 0.05, verts=6), "steel_dark")
        mg.add(geo.cylinder(0.085, 0.5, verts=10, bevel=0.03), "grip", at=(sx * 0.32, -1.7, BARREL_Z + 0.12), rot=(-8, 0, 0))
    mg.add(geo.box(0.32, 0.12, 0.2, bevel=0.03), "steel_dark", at=(0, -1.55, BARREL_Z + 0.2))
    mg.add(geo.box(0.12, 0.35, 0.12, bevel=0.03), "steel_dark", at=(0.47, 0.5, BARREL_Z + 0.05))
    mg.add(geo.cylinder(0.07, 0.25, verts=8), "steel_dark", at=(0.6, 0.5, BARREL_Z + 0.05), rot=(0, 90, 0))
    # Reflex sight on the top cover.
    mg.add(geo.box(0.34, 0.5, 0.3, bevel=0.05), "mount_dark", at=(0, -0.55, BARREL_Z + 0.68))
    mg.add(geo.box(0.3, 0.05, 0.26, bevel=0.02), "seeker", at=(0, -0.3, BARREL_Z + 0.7))
    # Barrel: perforated jacket, barrel, carry handle and muzzle brake.
    mg.add(along_y(geo.tube(0.26, 0.2, 1.6, verts=16), (0, 2.85, BARREL_Z)), "receiver")
    for yy in (2.15, 2.6, 3.05, 3.5):
        mg.add(along_y(geo.cylinder(0.29, 0.08, verts=16, bevel=0.01), (0, yy, BARREL_Z)), "receiver")
    mg.add(along_y(geo.cylinder(0.13, 3.6, verts=12, bevel=0.0), (0, 5.0, BARREL_Z)), "receiver")
    mg.add(geo.pipe_path([(0, 3.9, BARREL_Z + 0.1), (0, 4.0, BARREL_Z + 0.42), (0, 4.5, BARREL_Z + 0.42), (0, 4.6, BARREL_Z + 0.1)], 0.045, verts=6), "receiver")
    mg.add(along_y(geo.tube(0.2, 0.09, 0.55, verts=12), (0, 7.02, BARREL_Z)), "receiver")
    for sx in (-1, 1):
        mg.add(geo.box(0.06, 0.3, 0.16, bevel=0.01), "receiver", at=(sx * 0.2, 7.02, BARREL_Z))
    # Ammo can on the left with a belt of rounds into the feed tray.
    mg.add(geo.box(0.55, 1.15, 0.8, bevel=0.05), "can_olive", at=(-0.85, 0.55, BARREL_Z - 0.2))
    mg.add(geo.box(0.6, 1.2, 0.08, bevel=0.02), "can_olive", at=(-0.85, 0.55, BARREL_Z + 0.22))
    for i in range(8):
        t = i / 7
        x = -0.85 + t * 0.55
        z = BARREL_Z + 0.3 + math.sin(t * math.pi) * 0.22
        cartridge(mg, (x, 0.75, z), (-90, 0, 0))
        mg.add(geo.box(0.07, 0.22, 0.14, bevel=0.0), "belt", at=(x, 0.62, z - 0.02))

    pod = a.part("Pod", path="TurretGun/RocketPod", tex="turret", query=False, material="Metal")
    pod.add(along_y(geo.cylinder(0.95, 3.2, verts=24, bevel=0.08), (POD_X, 0.4, POD_Z)), "pod")
    for yy in (-1.15, 1.95):
        pod.add(along_y(geo.cylinder(1.0, 0.18, verts=24, bevel=0.04), (POD_X, yy, POD_Z)), "mount_dark")
    tubes = [(0.0, 0.0)] + [(0.58 * math.cos(math.pi / 6 + k * math.pi / 3), 0.58 * math.sin(math.pi / 6 + k * math.pi / 3)) for k in range(6)]
    for tx, tz in tubes:
        pod.add(along_y(geo.tube(0.26, 0.21, 0.2, verts=12), (POD_X + tx, 2.1, POD_Z + tz)), "mount_dark")
        pod.add(along_y(geo.lathe([(0.2, 0.0), (0.2, 0.12), (0.14, 0.3), (0.05, 0.42), (0.0, 0.45)], verts=10), (POD_X + tx, 1.72, POD_Z + tz)), "rocket_nose")
        pod.add(along_y(geo.tube(0.24, 0.12, 0.12, verts=10), (POD_X + tx, -1.3, POD_Z + tz)), "steel_dark")
    pod.add(geo.box(0.5, 1.0, 0.35, bevel=0.05), "mount_dark", at=(POD_X, 0.3, POD_Z + 1.0))
    pod.add(geo.pipe_path([(POD_X - 0.4, -0.3, POD_Z + 1.0), (POD_X - 0.4, 0.0, POD_Z + 1.3), (POD_X + 0.4, 0.0, POD_Z + 1.3), (POD_X + 0.4, -0.3, POD_Z + 1.0)], 0.05, verts=6), "steel_dark")

    rack = a.part("Rail", path="TurretGun/MissileRack", tex="turret", query=False, material="Metal")
    rack.add(geo.box(1.35, 3.4, 0.28, bevel=0.05), "mount_dark", at=(RACK_X, 0.35, 0.02))
    for sx in (-0.33, 0.33):
        rack.add(geo.box(0.16, 3.2, 0.16, bevel=0.03), "steel_dark", at=(RACK_X + sx, 0.35, 0.22))
    rack.add(geo.box(0.9, 0.9, 0.55, bevel=0.06), "mount_dark", at=(RACK_X, -0.9, -0.36))
    rack.add(geo.cylinder(0.16, 0.9, verts=12, bevel=0.03), "can_olive", at=(RACK_X - 0.32, -0.95, -0.72), rot=(0, 90, 0))
    for i, sx in enumerate((-0.33, 0.33)):
        m = a.part(f"Missile{i + 1}", path="TurretGun/MissileRack", tex="turret", query=False, material="Metal")
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
    for g in ("static", "bags", "props", "turret"):
        a.texture_group(g, 1024)
    for path in ("TurretYaw", "TurretGun", "TurretGun/MachineGun"):
        a.pivot(path, (0, 0, 0))
    bunker(a)
    sandbags(a)
    props(a)
    turret_yaw(a)
    turret_gun(a)
    turret = ["Mount", "Cradle", "Gun", "Pod", "Rail", "Missile1", "Missile2"]
    views = [
        ("", (1.0, 1.25, 0.75)),
        ("_player", (0.0, -1.6, 0.95), turret),
        ("_turret", (1.0, 1.1, 0.45), turret),
        ("_rear", (-1.0, -1.1, 0.8)),
    ]
    return a.finish(views=views, **kw)
