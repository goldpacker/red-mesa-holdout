"""Infantry: enemy rifleman of the fictional force (charcoal/grey camo,
gunmetal helmet with a red band, red armband, emblem shoulder patch,
plate carrier, balaclava and goggles), split into limb meshes for
procedural Motor6D animation.

Height ~6.5 studs (1.82 m). Asset origin = hip centre (Root, invisible).
Limb MeshParts are padded so their origin sits exactly on their joint:
LeftLeg/RightLeg at the hips, LeftArm/RightArm at the shoulders (so the
Motor6D C1 can be identity). Head rotates about its own centre.
Rest pose: arms hanging, rifle carried forward in the right hand.
"""
import math

from mathutils import Vector

from rmh import geo, images
from rmh.asset import Asset

HIP_Z = 3.45
HIP_X = 0.32
SHOULDER_Z = 5.3
SHOULDER_X = 0.8
NECK_Z = 5.62
RIFLE_ROT = (-90, 0, 0)


def limb_segment(r0, r1, length, verts=10):
    """Tapered limb segment hanging down from z=0 to z=-length."""
    prof = [(r0 * 0.7, 0.0), (r0, -length * 0.08), (r0 * 1.02, -length * 0.4), (r1, -length * 0.92), (r1 * 0.8, -length)]
    return geo.lathe(prof, verts=verts)


def materials(a):
    a.material("uniform", kind="fabric", pattern="camo", color="#3d4045", color2="#26282b", color3="#5a5c5e", camo_scale=2.4,
               rough=0.9, weave=45.0, wrinkle=0.7, wrinkle_scale=5.0, dust=0.55, dust_height=1.5, grime=0.5,
               marks=[{"lo": (-1.3, -0.6, 4.62), "hi": (-0.45, 0.6, 4.86), "color": "#a3161a"}])
    a.material("vest", kind="fabric", color="#2c2d2f", rough=0.85, weave=60.0, wrinkle=0.35, dust=0.5, grime=0.5)
    a.material("webbing", kind="fabric", color="#1f2022", rough=0.8, weave=80.0, wrinkle=0.15, dust=0.4)
    a.material("boot", base="rubber", color="#1c1a18", dust=0.35, dust_height=0.5)
    a.material("glove", base="rubber", color="#222222", dust=0.3)
    a.material("helmet", base="gunmetal", wear=0.45, dust=0.5,
               marks=[{"lo": (-2, -2, 6.08), "hi": (2, 2, 6.2), "color": "#a3161a"}])
    a.material("balaclava", kind="fabric", color="#232426", rough=0.95, weave=90.0, wrinkle=0.2, dust=0.2)
    a.material("goggle", base="glass", color="#3a2a18", rough=0.05, metal=0.3)
    a.material("rifle_metal", base="steel_dark", rough=0.5, dust=0.3)
    a.material("rifle_poly", kind="flat", color="#1d1e1f", rough=0.7, dust=0.35, grime=0.3)


def legs(a):
    for side, name in ((-1, "LeftLeg"), (1, "RightLeg")):
        x = side * HIP_X
        p = a.part(name, joint=(x, 0, HIP_Z), material="Fabric", smooth_angle=75)
        p.add(limb_segment(0.34, 0.26, 1.65), "uniform", at=(x, 0, HIP_Z + 0.05))
        p.add(limb_segment(0.28, 0.21, 1.55), "uniform", at=(x, 0.02, HIP_Z - 1.55))
        p.add(geo.sphere(0.24, 8, 5, scale=(1.0, 1.1, 1.0)), "uniform", at=(x, -0.06, HIP_Z - 1.95))  # calf
        p.add(geo.box(0.3, 0.4, 0.55, bevel=0.1, segments=1), "uniform", at=(x + side * 0.28, 0.02, HIP_Z - 0.75))  # cargo pocket
        p.add(geo.sphere(0.3, 10, 6, scale=(0.9, 0.55, 1.0)), "vest", at=(x, 0.2, HIP_Z - 1.62))  # knee pad
        p.add(geo.box(0.46, 1.0, 0.36, bevel=0.12, segments=1), "boot", at=(x, 0.2, 0.2))
        p.add(geo.box(0.5, 1.08, 0.1, bevel=0.03, segments=1), "boot", at=(x, 0.21, 0.05))
        p.add(geo.cylinder(0.24, 0.45, verts=10, bevel=0.05, segments=1), "boot", at=(x, 0.0, 0.55))


def torso(a):
    p = a.part("Torso", material="Fabric", smooth_angle=70)
    body = [(0.45, HIP_Z - 0.25), (0.62, HIP_Z - 0.05), (0.6, HIP_Z + 0.5), (0.55, HIP_Z + 1.0), (0.66, HIP_Z + 1.55), (0.7, SHOULDER_Z - 0.1), (0.5, NECK_Z - 0.1), (0.2, NECK_Z + 0.05)]
    p.add(geo.lathe(body, verts=12), "uniform", scale=(1.15, 0.72, 1.0))
    for side in (-1, 1):  # deltoids
        p.add(geo.sphere(0.3, 10, 6), "uniform", at=(side * (SHOULDER_X - 0.08), 0, SHOULDER_Z - 0.05))
    p.add(geo.cylinder(0.2, 0.35, verts=10, bevel=0.0), "balaclava", at=(0, 0, NECK_Z))
    # Plate carrier with cummerbund, mag pouches, radio pouch and collar.
    p.add(geo.box(1.28, 0.3, 1.2, bevel=0.1, segments=1), "vest", at=(0, 0.42, 4.75))
    p.add(geo.box(1.28, 0.3, 1.25, bevel=0.1, segments=1), "vest", at=(0, -0.42, 4.8))
    p.add(geo.box(1.46, 1.0, 0.45, bevel=0.12, segments=1), "vest", at=(0, 0, 4.35))
    for i in range(3):
        p.add(geo.box(0.34, 0.26, 0.48, bevel=0.06, segments=1), "vest", at=(-0.38 + i * 0.38, 0.66, 4.45))
    p.add(geo.box(0.3, 0.22, 0.5, bevel=0.06, segments=1), "vest", at=(0.66, -0.35, 4.95))
    for side in (-1, 1):
        p.add(geo.box(0.22, 0.95, 0.08, bevel=0.03, segments=1), "webbing", at=(side * 0.45, 0, 5.42), rot=(0, side * 12, 0))
    # Belt with pouches, canteen and a small assault pack.
    p.add(geo.box(1.36, 0.92, 0.2, bevel=0.06, segments=1), "webbing", at=(0, 0, HIP_Z + 0.25))
    p.add(geo.box(0.3, 0.3, 0.38, bevel=0.06, segments=1), "vest", at=(-0.68, -0.18, HIP_Z + 0.12))
    p.add(geo.cylinder(0.17, 0.42, verts=10, bevel=0.05, segments=1), "vest", at=(0.66, -0.25, HIP_Z + 0.1))
    p.add(geo.box(1.0, 0.45, 1.05, bevel=0.14, segments=1), "vest", at=(0, -0.78, 4.75))
    p.add(geo.box(0.9, 0.2, 0.5, bevel=0.08, segments=1), "vest", at=(0, -1.02, 4.55))
    p.add(geo.cylinder(0.02, 1.2, verts=4, bevel=0.0), "rifle_metal", at=(0.35, -0.9, 5.7))
    a.decal(images.get("emblem"), (-0.95, 0.0, 5.02), (-1, 0, 0), (0.42, 0.42, 0.4), color="#b01c1c")


def head(a):
    p = a.part("Head", material="Fabric", smooth_angle=70)
    p.add(geo.sphere(0.36, 12, 8, scale=(0.92, 1.0, 1.12)), "balaclava", at=(0, 0.04, 6.0))
    # Helmet shell, rim and goggles strapped across the front.
    shell = geo.sphere(0.46, 14, 8, scale=(1.0, 1.08, 0.85))
    import bmesh

    bmesh.ops.delete(shell, geom=[v for v in shell.verts if v.co.z < -0.12], context="VERTS")
    p.add(shell, "helmet", at=(0, -0.02, 6.13))
    p.add(geo.torus(0.44, 0.035, verts=14, ring_verts=4), "helmet", at=(0, -0.02, 6.03), scale=(1.0, 1.08, 1.0))
    p.add(geo.box(0.62, 0.14, 0.2, bevel=0.06, segments=1), "webbing", at=(0, 0.38, 6.12))
    for side in (-1, 1):
        p.add(geo.sphere(0.1, 8, 5, scale=(1.1, 0.5, 0.9)), "goggle", at=(side * 0.14, 0.45, 6.12))
    p.add(geo.box(0.12, 0.12, 0.14, bevel=0.03, segments=1), "rifle_metal", at=(0, 0.46, 6.36))  # NVG mount


def arms(a):
    for side, name in ((-1, "LeftArm"), (1, "RightArm")):
        x = side * SHOULDER_X
        p = a.part(name, joint=(x, 0, SHOULDER_Z), material="Fabric", smooth_angle=75)
        tilt = (0, side * -5, 0)
        p.add(limb_segment(0.24, 0.2, 1.15, verts=9), "uniform", at=(x, 0, SHOULDER_Z + 0.1), rot=tilt)
        ex = x + side * 0.1
        p.add(limb_segment(0.2, 0.15, 1.0, verts=9), "uniform", at=(ex, 0.08, SHOULDER_Z - 1.0), rot=(8, side * -3, 0))
        p.add(geo.sphere(0.16, 8, 6, scale=(0.8, 1.1, 1.2)), "glove", at=(ex + side * 0.02, 0.2, SHOULDER_Z - 2.12))
        p.add(geo.cylinder(0.22, 0.12, verts=9, bevel=0.0), "webbing", at=(x + side * 0.08, 0.02, SHOULDER_Z - 0.95))  # elbow cuff


def rifle(a):
    """Original carbine held by the grip in the right hand, muzzle forward (+Y)."""
    gx, gy, gz = SHOULDER_X + 0.12, 0.2, SHOULDER_Z - 2.12  # hand position
    p = a.part("Rifle", material="Metal", smooth_angle=45)
    ox, oy, oz = gx, gy - 0.2, gz + 0.3  # receiver origin
    p.add(geo.box(0.16, 0.95, 0.24, bevel=0.03, segments=1), "rifle_metal", at=(ox, oy + 0.35, oz))
    p.add(geo.box(0.14, 0.7, 0.14, bevel=0.03, segments=1), "rifle_metal", at=(ox, oy + 0.3, oz + 0.18))  # rail
    p.add(geo.cylinder(0.11, 0.75, verts=8, bevel=0.02, segments=1), "rifle_poly", at=(ox, oy + 1.18, oz + 0.02), rot=(-90, 0, 0))  # handguard
    p.add(geo.cylinder(0.035, 0.8, verts=6, bevel=0.0), "rifle_metal", at=(ox, oy + 1.8, oz + 0.02), rot=(-90, 0, 0))  # barrel
    p.add(geo.cylinder(0.055, 0.18, verts=8, bevel=0.01, segments=1), "rifle_metal", at=(ox, oy + 2.2, oz + 0.02), rot=(-90, 0, 0))
    p.add(geo.prism([(0.0, 0.0), (0.2, 0.0), (0.28, -0.5), (0.1, -0.55)], 0.12, bevel=0.02), "rifle_poly", at=(ox, oy + 0.5, oz - 0.1), rot=(90, 0, 90))  # magazine
    p.add(geo.prism([(0.0, 0.0), (0.14, 0.0), (0.06, -0.34), (-0.07, -0.34)], 0.12, bevel=0.02), "rifle_poly", at=(ox, oy + 0.15, oz - 0.1), rot=(90, 0, 90))  # grip
    p.add(geo.prism([(0.0, 0.1), (0.0, -0.12), (-0.62, -0.2), (-0.66, 0.1)], 0.13, bevel=0.03), "rifle_poly", at=(ox, oy - 0.1, oz), rot=(90, 0, 90))  # stock
    p.add(geo.box(0.12, 0.22, 0.14, bevel=0.03, segments=1), "rifle_metal", at=(ox, oy + 0.35, oz + 0.3))  # optic
    p.add(geo.box(0.1, 0.02, 0.1, bevel=0.0), "goggle", at=(ox, oy + 0.46, oz + 0.3))
    # Carried along the arm (muzzle down at rest): when the shoulder swings
    # the arm forward to aim, the rifle points forward.
    p.rotate(RIFLE_ROT, (gx, gy, gz))
    muzzle = Vector((ox, oy + 2.32, oz + 0.02)) - Vector((gx, gy, gz))
    muzzle = geo.euler_matrix(RIFLE_ROT).to_3x3() @ muzzle + Vector((gx, gy, gz))
    a.attach("RifleMuzzle", "Rifle", tuple(muzzle), axis=(0, 0, -1))


def build(**kw):
    a = Asset("Infantry", pivot=(0, 0, HIP_Z), tex_size=1024)
    a.zmin = 0.0
    # RECLAIM-HS (QA-B item 14): since CHAR-2 these parts are invisible hit
    # volumes under the skinned soldier, so their maps are never drawn: they
    # are not uploaded and the rbxmx carries no SurfaceAppearance (publish.py
    # meta `untextured`); if the skinned templates ever fail, the rigid limbs
    # show in the uniform colour (Infantry.luau UNIFORM).
    a.meta["untextured"] = [0.22, 0.227, 0.251]
    materials(a)
    legs(a)
    torso(a)
    head(a)
    arms(a)
    rifle(a)
    a.marker("Root", "", (0, 0, HIP_Z), size=(2.0, 1.0, 2.0))
    views = [("", (1.0, 1.6, 0.35)), ("_rear", (-1.0, -1.4, 0.4)), ("_side", (1.0, 0.0, 0.15))]
    return a.finish(views=views, **kw)
