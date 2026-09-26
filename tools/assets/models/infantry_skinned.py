"""InfantrySkinned: the enemy soldier as ONE skinned mesh per variant on a
shared skeleton (face-lift CHAR-1). Variants: Rifleman, Grenadier, Radio.
All three share one 1024 texture set; the GLB also carries a decimated
LOD per variant.

Blender asset space (studs, +Z up, +Y forward, +X = the soldier's right),
same origin/scale as the rigid `Infantry` asset: feet on z=0, hip centre
(Hips bone, Roblox `Root`) at z=3.45, ~6.5 studs to the helmet top.

Bind pose: A-pose (arms 20 deg out, elbows bent 20 deg), the carbine held
by its pistol grip in the right hand, pointing along the forearm. Every
bone points up (identity rest rotation in Roblox, see rmh/skin.py), so a
pose is a table of `Bone.Transform` angles; `POSES` (Patrol, Aim) are
solved here with FK + two-bone IK and written to the manifest for CHAR-2.

Bone names avoid every part/joint name of the rigid rig (Head, Neck,
Rifle, RifleMuzzle, ...) so both can live in one model while the old
parts stay as invisible hit volumes.
"""
import math

import bmesh
from mathutils import Matrix, Vector

from rmh import geo
from rmh.skin import Bone, Pose, SkinnedAsset, rot, sweep

VARIANTS = ("Rifleman", "Grenadier", "Radio")
HIP_Z = 3.45
ARM_OUT = math.radians(20)


# --- skeleton -------------------------------------------------------------

def arm_points(s):
    """Shoulder, elbow, wrist, hand end for side s (+1 right, -1 left)."""
    S = Vector((s * 0.72, -0.02, 5.25))
    E = S + 1.16 * Vector((s * math.sin(ARM_OUT), 0.0, -math.cos(ARM_OUT)))
    fdir = Vector((s * 0.33, 0.36, -0.87)).normalized()
    W = E + 0.96 * fdir
    return S, E, W, fdir


def hand_frame(s):
    """Rest hand axes: long axis a (wrist->knuckles), width axis w
    (thumb side, forward), palm normal pn (towards the fingers' curl)."""
    _, _, W, a = arm_points(s)
    w = (Vector((0, 1, 0)) - a * a.y).normalized()
    pn = (w.cross(a) if s > 0 else a.cross(w)).normalized()
    return W, a, w, pn


def grip_point(s=1):
    W, a, w, pn = hand_frame(s)
    return W + a * 0.3 + pn * 0.03


def rifle_rest():
    """Rifle rest frame: columns (right, forward, up) in world; origin = grip hold point."""
    _, a, w, _ = hand_frame(1)
    X = a.cross(w).normalized()
    return Matrix((X, a, w)).transposed(), grip_point(1)


RIFLE_MUZZLE = Vector((0.0, 1.93, 0.34))
RIFLE_SUPPORT = Vector((0.0, 0.86, 0.3))
RIFLE_BUTT = Vector((0.0, -0.84, 0.3))


def rifle_to_world(p):
    R, G = rifle_rest()
    return G + R @ Vector(p)


def skeleton():
    bones = [
        Bone("Hips", (0, 0, HIP_Z), start=(0, 0, 3.0), end=(0, 0, 3.9)),
        Bone("Spine", (0, 0, 3.95), end=(0, 0, 4.45), parent="Hips"),
        Bone("Chest", (0, 0, 4.55), end=(0, 0, 5.35), parent="Spine"),
        Bone("NeckBone", (0, 0.03, 5.5), end=(0, 0.05, 5.78), parent="Chest"),
        Bone("HeadBone", (0, 0.05, 5.78), end=(0, 0.06, 6.3), parent="NeckBone"),
    ]
    for s, side in ((1, "Right"), (-1, "Left")):
        S, E, W, fdir = arm_points(s)
        bones += [
            Bone(side + "UpperArm", S, end=E, parent="Chest"),
            Bone(side + "LowerArm", E, end=W, parent=side + "UpperArm"),
            Bone(side + "Hand", W, end=W + fdir * 0.5, parent=side + "LowerArm"),
        ]
    for s, side in ((1, "Right"), (-1, "Left")):
        H, K, A = Vector((s * 0.31, 0, 3.38)), Vector((s * 0.31, 0.04, 1.83)), Vector((s * 0.31, -0.02, 0.36))
        bones += [
            Bone(side + "UpperLeg", H, end=K, parent="Hips"),
            Bone(side + "LowerLeg", K, end=A, parent=side + "UpperLeg"),
            Bone(side + "Foot", A, end=Vector((s * 0.31, 0.6, 0.1)), parent=side + "LowerLeg"),
        ]
    _, G = rifle_rest()
    bones += [
        Bone("RifleBone", G, parent="RightHand"),
        Bone("MuzzleBone", rifle_to_world(RIFLE_MUZZLE), parent="RifleBone"),
        Bone("SupportBone", rifle_to_world(RIFLE_SUPPORT), parent="RifleBone"),
        Bone("LampBone", (0, 0.5, 6.19), parent="HeadBone"),
    ]
    return bones


# --- helpers ----------------------------------------------------------------

def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def torso_weights(co):
    """Spine chain by height; pelvis bottom blends into the thighs."""
    z = co.z
    chain = [("Hips", 3.45), ("Spine", 4.1), ("Chest", 4.85), ("NeckBone", 5.55), ("HeadBone", 5.85)]
    w = {}
    if z <= chain[0][1]:
        w["Hips"] = 1.0
    elif z >= chain[-1][1]:
        w["HeadBone"] = 1.0
    else:
        for (n0, z0), (n1, z1) in zip(chain, chain[1:]):
            if z0 <= z <= z1:
                t = smooth(z0, z1, z)
                w[n0] = 1 - t
                w[n1] = t
                break
    leg = smooth(3.35, 3.0, z) * smooth(0.1, 0.34, abs(co.x)) * 0.55
    if leg > 0.03:
        side = "Right" if co.x > 0 else "Left"
        w = {k: v * (1 - leg) for k, v in w.items()}
        w[side + "UpperLeg"] = leg
    return {k: v for k, v in w.items() if v > 0.03}


def blend_weights(a_name, b_name, t):
    t = max(0.0, min(1.0, t))
    if t < 0.03:
        return {a_name: 1.0}
    if t > 0.97:
        return {b_name: 1.0}
    return {a_name: 1 - t, b_name: t}


def curve_y(bm, k, x0=0.0):
    """Bend a slab around the body: y -= k * (x - x0)^2 (front plates)."""
    for v in bm.verts:
        v.co.y -= k * (v.co.x - x0) ** 2
    return bm


def place(bm, M, origin):
    """Apply a 3x3 rotation M then translate by origin (rifle-local -> world)."""
    T = Matrix.Translation(origin) @ M.to_4x4()
    bmesh.ops.transform(bm, matrix=T, verts=bm.verts)
    return bm


# --- materials ----------------------------------------------------------------

def materials(s):
    folds = []
    for side in (1, -1):
        S, E, W, fdir = arm_points(side)
        folds += [
            {"centre": (side * 0.31, 0.02, 1.85), "axis": (0, 0, 1), "radius": 0.5, "wavelength": 0.13, "depth": 0.9},
            {"centre": (side * 0.24, 0.28, 3.12), "axis": (side * 0.6, 0.2, 1.0), "radius": 0.5, "wavelength": 0.15, "depth": 0.8},
            {"centre": (side * 0.31, -0.02, 0.62), "axis": (0, 0, 1), "radius": 0.3, "wavelength": 0.075, "depth": 1.0, "warp": 4.0},
            {"centre": tuple(E), "axis": tuple((W - S).normalized()), "radius": 0.42, "wavelength": 0.11, "depth": 0.9},
            {"centre": tuple(S + Vector((-side * 0.12, 0.0, -0.3))), "axis": (side * 1.0, 0.0, -0.8), "radius": 0.35, "wavelength": 0.12, "depth": 0.7},
            {"centre": tuple(W - fdir * 0.12), "axis": tuple(fdir), "radius": 0.24, "wavelength": 0.07, "depth": 0.8, "warp": 3.0},
        ]
    s.material("uniform", kind="garment", pattern="camo", color="#3a3d42", color2="#25272a", color3="#52555a", camo_scale=2.2,
               rough=0.9, weave=70.0, weave_depth=0.18, wrinkle=0.35, wrinkle_scale=4.5, folds=folds, fold_shade=0.25,
               dust=0.55, dust_height=1.4, grime=0.45, bump=0.55)
    s.material("vest", kind="garment", color="#2c2e30", rough=0.85, weave=80.0, wrinkle=0.25, dust=0.5, grime=0.5, bump=0.4)
    s.material("pouch", kind="garment", color="#35383b", rough=0.85, weave=80.0, wrinkle=0.3, dust=0.5, grime=0.5, bump=0.4)
    s.material("webbing", kind="garment", color="#1f2022", rough=0.8, weave=110.0, wrinkle=0.1, dust=0.4, bump=0.3)
    s.material("pack", kind="garment", color="#303235", rough=0.88, weave=60.0, wrinkle=0.6, wrinkle_scale=3.0, dust=0.55, grime=0.5, bump=0.45)
    s.material("balaclava", kind="garment", color="#1e1f21", rough=0.95, weave=120.0, wrinkle=0.2, dust=0.15, bump=0.3,
               marks=[{"lo": (-0.3, 0.2, 5.95), "hi": (0.3, 0.6, 6.05), "color": "#4a3628"}])
    s.material("glove", kind="garment", color="#232325", rough=0.75, weave=90.0, wrinkle=0.5, wrinkle_scale=9.0, dust=0.35, bump=0.4)
    s.material("boot", base="rubber", color="#1d1a17", rough=0.7, dust=0.28, dust_height=0.35, grime=0.3)
    s.material("sole", base="rubber", color="#121212", dust=0.3, dust_height=0.15)
    s.material("red_band", kind="garment", color="#a3161a", rough=0.8, weave=90.0, wrinkle=0.2, dust=0.25, bump=0.25)
    # Readability at range: helmet and shoulder pads a touch lighter and
    # glossier than the uniform so they catch rim light.
    s.material("helmet_cover", kind="garment", pattern="camo", color="#4a4d52", color2="#2f3134", color3="#5f6368", camo_scale=5.0,
               rough=0.82, weave=90.0, wrinkle=0.55, wrinkle_scale=7.0, dust=0.6, dust_up=1.0, grime=0.4, bump=0.45)
    s.material("helmet_shell", base="gunmetal", color="#474c52", rough=0.36, wear=0.5, dust=0.55,
               marks=[{"lo": (-1, -1, 6.02), "hi": (1, 1, 6.1), "color": "#a3161a"}])
    s.material("shoulder_pad", base="gunmetal", color="#4a4f55", rough=0.42, wear=0.35, dust=0.5)
    s.material("goggle_lens", base="glass", color="#8a5a22", rough=0.06, metal=0.55)
    s.material("scarf", kind="garment", color="#3a3934", rough=0.95, weave=70.0, wrinkle=0.9, wrinkle_scale=6.0, dust=0.45, grime=0.3, bump=0.6,
               folds=[{"centre": (0, 0.05, 5.55), "axis": (0, 0, 1), "radius": 0.4, "wavelength": 0.07, "depth": 1.0, "warp": 5.0}])
    s.material("goggle_frame", base="rubber", color="#1a1a1a", dust=0.3)
    s.material("rifle_metal", base="steel_dark", rough=0.45, dust=0.25)
    s.material("rifle_poly", kind="flat", color="#1c1d1e", rough=0.7, dust=0.3, grime=0.3)
    s.material("optic_lens", base="glass", color="#20303a", rough=0.05, metal=0.2)
    s.material("radio", base="charcoal", color="#2b2d30", rough=0.5, wear=0.45, dust=0.55, panels=(0.0, 0.0, 0.25))
    s.material("antenna", base="rubber", color="#121212", dust=0.2)
    s.material("grenade", base="olive_dark", color="#3b3f2c", rough=0.5, wear=0.3, dust=0.4)


# --- body -------------------------------------------------------------------

TORSO = [  # z, r_side, r_front, y offset
    (3.0, 0.3, 0.26, 0.0),
    (3.18, 0.5, 0.4, -0.02),
    (3.45, 0.6, 0.43, -0.03),
    (3.72, 0.57, 0.39, -0.01),
    (3.95, 0.54, 0.37, 0.0),
    (4.25, 0.58, 0.4, 0.0),
    (4.6, 0.66, 0.44, 0.01),
    (4.95, 0.7, 0.44, 0.0),
    (5.2, 0.66, 0.39, -0.01),
    (5.38, 0.5, 0.32, -0.01),
    (5.5, 0.27, 0.27, 0.02),
    (5.7, 0.225, 0.235, 0.04),
    (5.86, 0.21, 0.22, 0.05),
]


def torso(s):
    path = [(0, 0, z) for z, *_ in TORSO]
    radii = [(rs, rf) for _, rs, rf, _ in TORSO]
    offs = [(0.0, y) for *_, y in TORSO]
    bm = sweep(path, radii, n=14, offsets=offs, caps=(True, False), seam=math.pi / 2)
    s.add(bm, "uniform", bones=None, weight_fn=torso_weights)


LEG = [  # z, r_side, r_front, front offset
    (3.58, 0.32, 0.35, 0.0),
    (3.25, 0.34, 0.37, 0.0),
    (2.75, 0.31, 0.33, 0.015),
    (2.12, 0.25, 0.27, 0.03),
    (1.92, 0.24, 0.26, 0.04),
    (1.74, 0.235, 0.26, 0.03),
    (1.5, 0.24, 0.28, -0.03),
    (1.2, 0.23, 0.26, -0.03),
    (0.8, 0.197, 0.205, -0.01),
    (0.58, 0.215, 0.225, 0.0),
    (0.46, 0.17, 0.18, 0.0),
]


def leg_path_point(s, z):
    H, K, A = Vector((s * 0.31, 0, 3.38)), Vector((s * 0.31, 0.04, 1.83)), Vector((s * 0.31, -0.02, 0.36))
    if z >= K.z:
        t = (z - K.z) / (H.z - K.z)
        return K.lerp(H, t)
    t = (z - A.z) / (K.z - A.z)
    return A.lerp(K, t)


def legs(s):
    cands = ["Hips", "RightUpperLeg", "RightLowerLeg", "RightFoot"]
    path = [leg_path_point(1, z) for z, *_ in LEG]
    radii = [(rs, rf) for _, rs, rf, _ in LEG]
    offs = [(0.0, f) for *_, f in LEG]
    s.add(sweep(path, radii, n=11, offsets=offs), "uniform", bones=cands, mirror_x=True, falloff=5.0)
    # Cargo pocket with flap on the outer thigh.
    pocket = geo.box(0.12, 0.34, 0.42, bevel=0.0)
    s.add(pocket, "uniform", bones=cands, at=(0.635, 0.04, 2.72), rot=(0, 3, 0), mirror_x=True)
    s.add(geo.box(0.13, 0.36, 0.08, bevel=0.0), "uniform", bones=cands, at=(0.645, 0.04, 2.95), rot=(0, 3, 0), mirror_x=True)
    # Knee pads (strapped to the shin top).
    pad = geo.sphere(0.2, 8, 6, scale=(1.05, 0.55, 1.2))
    bmesh.ops.delete(pad, geom=[v for v in pad.verts if v.co.y < -0.02], context="VERTS")
    s.add(pad, "vest", bones="RightLowerLeg", at=(0.31, 0.22, 1.84), mirror_x=True)
    strap = sweep([(0.31, 0.02, 1.72), (0.31, 0.02, 1.66)], [(0.25, 0.28), (0.25, 0.28)], n=10, caps=(False, False))
    s.add(strap, "webbing", bones="RightLowerLeg", mirror_x=True)


def boots(s):
    x = 0.31
    upper = geo.loft([
        (-0.3, 0.3, 0.3, 0.26, 2.4),
        (-0.2, 0.39, 0.46, 0.3, 2.6),
        (0.05, 0.42, 0.38, 0.24, 2.6),
        (0.3, 0.42, 0.25, 0.17, 2.8),
        (0.52, 0.38, 0.18, 0.13, 2.8),
        (0.64, 0.24, 0.1, 0.1, 2.2),
    ], n=10)
    cands = ["RightLowerLeg", "RightFoot"]
    s.add(upper, "boot", bones="RightFoot", at=(x, 0.02, 0.0), mirror_x=True)
    shaft = sweep([(x, -0.06, 0.3), (x, -0.05, 0.55), (x, -0.04, 0.72)], [(0.2, 0.22), (0.2, 0.215), (0.205, 0.215)], n=10, caps=(False, True))
    s.add(shaft, "boot", bones=cands, mirror_x=True, falloff=6.0)
    sole = geo.loft([
        (-0.31, 0.3, 0.09, 0.045, 3.0),
        (-0.2, 0.4, 0.09, 0.045, 4.0),
        (0.3, 0.44, 0.08, 0.04, 4.0),
        (0.55, 0.4, 0.08, 0.045, 3.5),
        (0.67, 0.26, 0.07, 0.05, 2.5),
    ], n=8)
    s.add(sole, "sole", bones="RightFoot", at=(x, 0.02, 0.0), mirror_x=True)


def arms(s):
    S, E, W, fdir = arm_points(1)
    up = (E - S).normalized()
    # Starts in a small dome just above the shoulder pivot so the top stays
    # inside the deltoid whatever the arm does.
    pts = [S - up * 0.1, S - up * 0.03, S + up * 0.1, S + up * 0.4, S + up * 0.8, E - up * 0.12, E, E + fdir * 0.12, E + fdir * 0.45, W - fdir * 0.1, W + fdir * 0.02]
    radii = [(0.12, 0.13), (0.21, 0.22), (0.245, 0.26), (0.23, 0.245), (0.205, 0.215), (0.185, 0.195), (0.185, 0.195), (0.19, 0.2), (0.17, 0.18), (0.14, 0.135), (0.12, 0.115)]
    cands = ["Chest", "RightUpperArm", "RightLowerArm", "RightHand"]
    s.add(sweep(pts, radii, n=10, ref=(0, 1, 0), seam=math.pi / 2), "uniform", bones=cands, mirror_x=True, falloff=5.0)
    # Armband (left upper arm, red) and emblem patch (right upper arm).
    Sl, El, _, _ = arm_points(-1)
    ul = (El - Sl).normalized()
    band = sweep([Sl + ul * 0.3, Sl + ul * 0.52], [(0.245, 0.26), (0.225, 0.24)], n=10, ref=(0, 1, 0), caps=(False, False))
    s.add(band, "red_band", bones="LeftUpperArm")
    n = Vector((math.cos(ARM_OUT), 0, math.sin(ARM_OUT)))
    s.decal("emblem", tuple(S + up * 0.42 + n * 0.23), tuple(n), (0.34, 0.34, 0.3), up=tuple(-up), color="#b01c1c")


def hands(s):
    W, a, w, pn = hand_frame(1)
    # Proper rotation: local x = long axis, y = width (thumb side), z = back of the hand (-pn).
    M = Matrix((a, w, a.cross(w))).transposed()

    def put(bm, local):
        return place(bm, M, W + M @ Vector(local))

    fist = geo.box(0.36, 0.3, 0.24, bevel=0.08, segments=1)
    s.add(put(fist, (0.24, 0.0, 0.0)), "glove", bones="RightHand", mirror_x=True)
    knuckles = geo.box(0.12, 0.28, 0.2, bevel=0.0)
    s.add(put(knuckles, (0.42, 0.0, 0.07)), "glove", bones="RightHand", mirror_x=True)
    thumb = geo.cylinder(0.055, 0.2, verts=6, bevel=0.0)
    bmesh.ops.rotate(thumb, cent=(0, 0, 0), matrix=Matrix.Rotation(math.radians(90), 3, "Y"), verts=thumb.verts)
    s.add(put(thumb, (0.22, 0.16, -0.05)), "glove", bones="RightHand", mirror_x=True)
    cuff = sweep([W - a * 0.1, W + a * 0.1], [(0.155, 0.15), (0.15, 0.145)], n=8, ref=tuple(w), caps=(False, False))
    s.add(cuff, "glove", bones=["RightLowerArm", "RightHand"], mirror_x=True, falloff=6.0)


def head(s):
    s.add(geo.sphere(0.345, 12, 8, scale=(0.92, 1.0, 1.1)), "balaclava", bones="HeadBone", at=(0, 0.06, 5.97))
    gaiter = sweep([(0, 0.0, 5.38), (0, 0.02, 5.48), (0, 0.04, 5.6), (0, 0.06, 5.72)], [(0.34, 0.33), (0.33, 0.33), (0.29, 0.3), (0.25, 0.27)], n=12, caps=(False, False))
    s.add(gaiter, "scarf", bones=["Chest", "NeckBone", "HeadBone"], falloff=3.0)
    s.add(geo.sphere(0.075, 6, 4, scale=(0.8, 1.0, 1.3)), "balaclava", bones="HeadBone", at=(0, 0.38, 5.92))  # nose
    # Goggles over the eyes with a strap.
    for x in (-0.13, 0.13):
        s.add(geo.sphere(0.1, 6, 4, scale=(1.15, 0.45, 0.8)), "goggle_lens", bones="HeadBone", at=(x, 0.36, 6.02))
    s.add(geo.box(0.46, 0.1, 0.18, bevel=0.04, segments=1), "goggle_frame", bones="HeadBone", at=(0, 0.32, 6.02))
    strap = sweep([(0, 0.02, 6.0), (0, 0.02, 6.06)], [(0.33, 0.345), (0.33, 0.345)], n=12, caps=(False, False))
    s.add(strap, "goggle_frame", bones="HeadBone", at=(0, 0.02, 0))


def helmet_shell(scale=1.0):
    shell = geo.sphere(0.44 * scale, 14, 9, scale=(1.0, 1.1, 0.86))
    bmesh.ops.delete(shell, geom=[v for v in shell.verts if v.co.z < -0.13 * scale], context="VERTS")
    # High cut over the ears.
    for v in shell.verts:
        if v.co.z < 0.0 and abs(v.co.x) > 0.3 and -0.15 < v.co.y < 0.2:
            v.co.z = max(v.co.z, 0.0 + (abs(v.co.x) - 0.3) * -0.4)
    return shell


def helmets(s):
    c = (0, 0.03, 6.07)
    # Covered helmet (Rifleman, Radio) with a red elastic band.
    s.add(helmet_shell(1.03), "helmet_cover", bones="HeadBone", at=c, only=("Rifleman", "Radio"))
    s.add(sweep([(0, 0.03, 6.11), (0, 0.03, 6.19)], [(0.455, 0.5), (0.44, 0.485)], n=14, caps=(False, False)), "red_band", bones="HeadBone", only=("Rifleman", "Radio"))
    # Bare painted helmet (Grenadier), red stripe baked via the shell marks.
    s.add(helmet_shell(1.0), "helmet_shell", bones="HeadBone", at=c, only=("Grenadier",))
    s.add(geo.torus(0.44, 0.03, verts=12, ring_verts=3), "helmet_shell", bones="HeadBone", at=(0, 0.03, 5.96), scale=(1.0, 1.1, 1.0), only=("Grenadier",))
    for only in (("Rifleman", "Radio"), ("Grenadier",)):
        mat = "helmet_cover" if len(only) == 2 else "helmet_shell"
        s.add(geo.box(0.16, 0.1, 0.13, bevel=0.03, segments=1), "rifle_metal", bones="HeadBone", at=(0, 0.5, 6.17), only=only)  # NVG shroud
        for x in (-0.4, 0.4):  # side rails
            s.add(geo.box(0.05, 0.36, 0.06, bevel=0.015, segments=1), mat, bones="HeadBone", at=(x, 0.05, 5.99), rot=(0, x * 20, 0), only=only)
    # Headset (Radio): ear cups and boom mic.
    for x in (-1, 1):
        s.add(geo.cylinder(0.11, 0.1, verts=8, bevel=0.02, segments=1), "radio", bones="HeadBone", at=(x * 0.34, 0.06, 5.94), rot=(0, 90, 0), only=("Radio",))
    s.add(geo.pipe_path([(-0.36, 0.12, 5.87), (-0.31, 0.3, 5.79), (-0.12, 0.43, 5.81)], 0.018, verts=5), "antenna", bones="HeadBone", only=("Radio",))


def plate_carrier(s):
    front = curve_y(geo.box(0.94, 0.15, 1.0, bevel=0.05, segments=1), 0.2)
    s.add(front, "vest", bones="Chest", at=(0, 0.5, 4.8))
    back = curve_y(geo.box(0.94, 0.15, 1.06, bevel=0.05, segments=1), -0.2)
    s.add(back, "vest", bones="Chest", at=(0, -0.5, 4.84))
    band = sweep([(0, 0, 4.1), (0, 0, 4.33), (0, 0, 4.56)], [(0.635, 0.45), (0.66, 0.47), (0.7, 0.5)], n=16, caps=(False, False))
    s.add(band, "vest", bones=["Spine", "Chest"], falloff=3.0)
    for side in (1, -1):  # shoulder straps
        strap = sweep([(side * 0.3, 0.46, 5.28), (side * 0.34, 0.25, 5.44), (side * 0.36, 0.0, 5.5), (side * 0.34, -0.25, 5.45), (side * 0.3, -0.46, 5.32)],
                      [(0.12, 0.03)] * 5, n=6, ref=(1, 0, 0))
        s.add(strap, "webbing", bones="Chest")
    # Deltoids (cap the sleeve tubes) and low shoulder pads on top: both
    # 70% upper arm / 30% chest so they move together.
    S, E, _, _ = arm_points(1)

    def shoulder_w(co):
        return {("Right" if co.x > 0 else "Left") + "UpperArm": 0.3, "Chest": 0.7}

    def deltoid_w(co):
        return {("Right" if co.x > 0 else "Left") + "UpperArm": 0.45, "Chest": 0.55}

    deltoid = geo.sphere(0.28, 10, 7, scale=(1.0, 1.1, 1.05))
    s.add(deltoid, "uniform", bones=None, at=tuple(S + Vector((0.0, 0.0, 0.0))), mirror_x=True, weight_fn=deltoid_w)
    pad = geo.sphere(0.27, 8, 6, scale=(1.0, 1.2, 0.5))
    bmesh.ops.delete(pad, geom=[v for v in pad.verts if v.co.z < -0.01], context="VERTS")
    s.add(pad, "shoulder_pad", bones=None, at=tuple(S + Vector((0.0, 0.0, 0.16))), rot=(0, math.degrees(ARM_OUT) * 0.8, 0), mirror_x=True, weight_fn=shoulder_w)


def mag_pouches(s, xs, only):
    for x in xs:
        s.add(geo.box(0.2, 0.14, 0.32, bevel=0.04, segments=1), "pouch", bones="Chest", at=(x, 0.63, 4.52), only=only)
        s.add(geo.box(0.21, 0.16, 0.07, bevel=0.0), "pouch", bones="Chest", at=(x, 0.64, 4.7), only=only)
        s.add(geo.box(0.05, 0.02, 0.1, bevel=0.0), "webbing", bones="Chest", at=(x, 0.72, 4.62), only=only)  # pull tab


def front_gear(s):
    mag_pouches(s, (-0.25, 0.0, 0.25), ("Rifleman",))
    s.add(geo.box(0.5, 0.08, 0.26, bevel=0.03, segments=1), "pouch", bones="Chest", at=(0, 0.6, 5.0), only=("Rifleman",))  # admin pouch
    # Grenadier: six 40 mm rounds in open-top pouches and frag pouches.
    for i in range(6):
        x = -0.36 + i * 0.144
        s.add(geo.box(0.13, 0.13, 0.22, bevel=0.0), "pouch", bones="Chest", at=(x, 0.62, 4.52), only=("Grenadier",))
        s.add(geo.cylinder(0.055, 0.12, verts=6, bevel=0.0), "grenade", bones="Chest", at=(x, 0.62, 4.68), only=("Grenadier",))
    for side in (1, -1):
        s.add(geo.cylinder(0.1, 0.24, verts=8, bevel=0.0), "pouch", bones=["Spine", "Chest"], at=(side * 0.68, 0.24, 4.34), only=("Grenadier",))
    # Radio operator: two mag pouches, handset on the left strap, cable.
    mag_pouches(s, (-0.13, 0.13), ("Radio",))
    s.add(geo.box(0.11, 0.09, 0.3, bevel=0.03, segments=1), "radio", bones="Chest", at=(-0.3, 0.5, 5.18), rot=(10, 0, 0), only=("Radio",))
    s.add(geo.pipe_path([(-0.3, 0.46, 5.02), (-0.46, 0.35, 4.85), (-0.62, 0.0, 4.9), (-0.5, -0.5, 5.0)], 0.018, verts=5), "antenna", bones="Chest", only=("Radio",))


def back_gear(s):
    # Rifleman: assault pack with lid and side pockets.
    pack = geo.box(0.8, 0.38, 0.92, bevel=0.12, segments=2)
    s.add(pack, "pack", bones="Chest", at=(0, -0.77, 4.72), only=("Rifleman",))
    s.add(geo.box(0.78, 0.4, 0.16, bevel=0.07, segments=1), "pack", bones="Chest", at=(0, -0.76, 5.2), only=("Rifleman",))
    for side in (1, -1):
        s.add(geo.box(0.12, 0.3, 0.5, bevel=0.05, segments=1), "pack", bones="Chest", at=(side * 0.44, -0.76, 4.55), only=("Rifleman",))
        s.add(geo.box(0.05, 0.42, 0.04, bevel=0.0), "webbing", bones="Chest", at=(side * 0.2, -0.78, 4.9), rot=(0, 0, 0), only=("Rifleman",))
    # Grenadier: hydration carrier and a grenade bag.
    s.add(geo.box(0.62, 0.14, 0.8, bevel=0.06, segments=1), "pack", bones="Chest", at=(0, -0.63, 4.8), only=("Grenadier",))
    s.add(geo.box(0.36, 0.22, 0.3, bevel=0.06, segments=1), "pouch", bones=["Hips", "Spine"], at=(-0.32, -0.55, 3.75), only=("Grenadier",))
    # Radio: manpack radio with frame, knobs and a tall whip antenna.
    s.add(geo.box(0.7, 0.3, 0.84, bevel=0.05, segments=1), "radio", bones="Chest", at=(0, -0.73, 4.68), only=("Radio",))
    s.add(geo.box(0.74, 0.08, 0.9, bevel=0.03, segments=1), "rifle_metal", bones="Chest", at=(0, -0.58, 4.68), only=("Radio",))
    for x in (-0.18, 0.0, 0.18):
        s.add(geo.cylinder(0.04, 0.07, verts=6, bevel=0.0), "rifle_metal", bones="Chest", at=(x, -0.76, 5.13), only=("Radio",))
    s.add(geo.cylinder(0.05, 0.16, verts=6, bevel=0.0), "rifle_metal", bones="Chest", at=(0.26, -0.8, 5.16), only=("Radio",))
    s.add(geo.pipe_path([(0.26, -0.8, 5.2), (0.29, -0.86, 6.4), (0.33, -0.95, 7.6)], 0.016, verts=5), "antenna", bones="Chest", only=("Radio",))


def belt(s):
    band = sweep([(0, 0, 3.5), (0, 0, 3.61), (0, 0, 3.72)], [(0.625, 0.46), (0.62, 0.455), (0.61, 0.44)], n=16, caps=(False, False))
    s.add(band, "webbing", bones="Hips")
    s.add(geo.box(0.16, 0.06, 0.12, bevel=0.02, segments=1), "rifle_metal", bones="Hips", at=(0, 0.47, 3.61))  # buckle
    s.add(geo.box(0.34, 0.2, 0.3, bevel=0.06, segments=1), "pouch", bones="Hips", at=(0.2, -0.5, 3.5))  # IFAK
    s.add(geo.cylinder(0.14, 0.34, verts=10, bevel=0.04, segments=1), "pouch", bones="Hips", at=(0.6, -0.26, 3.48))  # canteen
    for side in (1, -1):
        s.add(geo.box(0.16, 0.14, 0.24, bevel=0.04, segments=1), "pouch", bones="Hips", at=(side * 0.52, 0.28, 3.55), rot=(0, 0, side * -30))
    # Two-point sling around the neck and under the right arm.
    path = [(-0.26, 0.52, 5.3), (-0.33, 0.12, 5.5), (-0.1, -0.32, 5.5), (0.34, -0.5, 5.1), (0.64, -0.22, 4.55), (0.66, 0.22, 4.3)]
    s.add(sweep(path, [(0.07, 0.016)] * len(path), n=6, ref=(0, 0, 1)), "webbing", bones="Chest")


def rifle(s):
    """Original carbine in rifle-local space (origin = grip hold point,
    +Y muzzle, +Z up), placed in the right hand's rest frame."""
    R, G = rifle_rest()

    def add(bm, mat, at=(0, 0, 0), rot_=(0, 0, 0), only=None):
        geo.transform(bm, at, rot_)
        s.add(place(bm, R, G), mat, bones="RifleBone", only=only)

    add(geo.prism([(0.06, 0.16), (-0.08, 0.16), (-0.16, -0.2), (-0.04, -0.21)], 0.11, bevel=0.025, segments=1), "rifle_poly", rot_=(90, 0, 90))  # grip
    add(geo.box(0.13, 0.62, 0.14, bevel=0.02, segments=1), "rifle_metal", at=(0, 0.19, 0.23))  # lower receiver
    add(geo.prism([(0.3, 0.16), (0.46, 0.16), (0.58, -0.34), (0.42, -0.37)], 0.1, bevel=0.02, segments=1), "rifle_poly", rot_=(90, 0, 90))  # magazine
    add(geo.box(0.14, 0.75, 0.13, bevel=0.02, segments=1), "rifle_metal", at=(0, 0.235, 0.36))  # upper receiver
    add(geo.box(0.08, 0.95, 0.035, bevel=0.0), "rifle_metal", at=(0, 0.5, 0.44))  # top rail
    add(geo.box(0.1, 0.24, 0.12, bevel=0.03, segments=1), "rifle_metal", at=(0, 0.18, 0.53))  # prism optic body
    add(geo.cylinder(0.055, 0.08, verts=8, bevel=0.0), "rifle_metal", at=(0, 0.33, 0.53), rot_=(-90, 0, 0))
    add(geo.cylinder(0.045, 0.01, verts=8, bevel=0.0, caps=True), "optic_lens", at=(0, 0.375, 0.53), rot_=(-90, 0, 0))
    add(geo.cylinder(0.088, 0.8, verts=8, bevel=0.02, segments=1), "rifle_poly", at=(0, 0.95, 0.34), rot_=(-90, 0, 0))  # handguard
    for y in (0.7, 1.2):
        add(geo.box(0.2, 0.06, 0.2, bevel=0.0), "rifle_poly", at=(0, y, 0.34))  # rail sections
    add(geo.cylinder(0.028, 0.45, verts=6, bevel=0.0), "rifle_metal", at=(0, 1.57, 0.34), rot_=(-90, 0, 0))  # barrel
    add(geo.box(0.07, 0.07, 0.14, bevel=0.0), "rifle_metal", at=(0, 1.42, 0.4))  # gas block / front sight
    add(geo.cylinder(0.042, 0.16, verts=8, bevel=0.01, segments=1), "rifle_metal", at=(0, 1.84, 0.34), rot_=(-90, 0, 0))  # muzzle brake
    add(geo.cylinder(0.05, 0.58, verts=6, bevel=0.0), "rifle_metal", at=(0, -0.42, 0.34), rot_=(-90, 0, 0))  # buffer tube
    add(geo.prism([(-0.4, 0.42), (-0.82, 0.43), (-0.84, 0.13), (-0.68, 0.16), (-0.42, 0.3)], 0.12, bevel=0.025, segments=1), "rifle_poly", rot_=(90, 0, 90))  # stock
    add(geo.box(0.14, 0.03, 0.32, bevel=0.0), "sole", at=(0, -0.845, 0.28))  # butt pad
    add(geo.box(0.03, 0.26, 0.03, bevel=0.0), "rifle_metal", at=(0, 0.1, 0.09))  # trigger guard
    add(geo.box(0.16, 0.06, 0.04, bevel=0.0), "rifle_metal", at=(0, -0.12, 0.42))  # charging handle
    # Sling hanging under the rifle between the swivels.
    sling = sweep([(-0.1, 1.18, 0.3), (-0.11, 0.8, 0.2), (-0.11, 0.2, 0.18), (-0.1, -0.4, 0.24), (-0.08, -0.78, 0.26)], [(0.012, 0.035)] * 5, n=4, ref=(1, 0, 0))
    add(sling, "webbing")
    # Grenadier: under-barrel 40 mm launcher.
    add(geo.cylinder(0.072, 0.58, verts=10, bevel=0.02, segments=1), "rifle_metal", at=(0, 1.25, 0.16), rot_=(-90, 0, 0), only=("Grenadier",))
    add(geo.box(0.12, 0.22, 0.1, bevel=0.02, segments=1), "rifle_metal", at=(0, 0.98, 0.2), only=("Grenadier",))


# --- poses --------------------------------------------------------------------

def rifle_pose(p, grip, yaw=0.0, pitch=0.0, roll=0.0, right_pole=(0.8, -1.0, -0.4), left_pole=(-0.9, -0.2, -1.0)):
    """Put the carbine's grip at `grip` (world) pointing yaw/pitch/roll
    (degrees; yaw + = muzzle to the left), then IK both arms onto it."""
    R0, G0 = rifle_rest()
    target = Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X") @ Matrix.Rotation(math.radians(roll), 3, "Y")
    D = target @ R0.transposed()
    grip = Vector(grip)
    bones = p.bones
    H0 = bones["RightHand"].head
    wrist = grip + D @ (H0 - G0)
    p.ik("RightUpperArm", "RightLowerArm", "RightHand", wrist, D, right_pole)
    # Support hand: wraps the handguard from below-left, thumb to the muzzle.
    Xr, Yr, Zr = D @ R0.col[0], D @ R0.col[1], D @ R0.col[2]
    W0, a0, w0, _ = hand_frame(-1)
    a1 = (Zr * 0.75 + Xr * 0.66).normalized()
    Fr = Matrix((a0, w0, a0.cross(w0))).transposed()
    w1 = (Yr - a1 * a1.dot(Yr)).normalized()
    F1 = Matrix((a1, w1, a1.cross(w1))).transposed()
    DL = F1 @ Fr.transposed()
    support = grip + D @ (rifle_to_world(RIFLE_SUPPORT) - G0)
    palm = grip_point(-1)
    p.ik("LeftUpperArm", "LeftLowerArm", "LeftHand", support - DL @ (palm - W0), DL, left_pole)
    return D


def poses(s):
    out = {}
    # Patrol: low ready while walking; slight crouch, muzzle down-left.
    p = Pose(s)
    p.offset = Vector((0, 0, -0.08))
    p.set("Spine", rot(-5, 4, 0)).set("Chest", rot(-3, 4, 0)).set("NeckBone", rot(4, -5, 0)).set("HeadBone", rot(3, -3, 0))
    p.set("RightUpperLeg", rot(10, 0, 4)).set("RightLowerLeg", rot(-16, 0, 0)).set("RightFoot", rot(6, 0, -4))
    p.set("LeftUpperLeg", rot(-4, 0, -4)).set("LeftLowerLeg", rot(-10, 0, 0)).set("LeftFoot", rot(14, 0, 4))
    rifle_pose(p, (0.3, 0.62, 4.35), yaw=22, pitch=-28, roll=-10)
    out["Patrol"] = p.angles()
    # Aim: rifle shouldered, bladed stance, head down on the optic.
    p = Pose(s)
    p.offset = Vector((0, 0, -0.1))
    p.set("Spine", rot(-4, 14, 0)).set("Chest", rot(-4, 10, 0)).set("NeckBone", rot(-6, -12, 0)).set("HeadBone", rot(-10, -10, 4))
    p.set("LeftUpperLeg", rot(16, 0, -4)).set("LeftLowerLeg", rot(-14, 0, 0)).set("LeftFoot", rot(-2, 0, 0))
    p.set("RightUpperLeg", rot(-12, 0, 5)).set("RightLowerLeg", rot(-8, 0, 0)).set("RightFoot", rot(20, 0, 0))
    grip_z = 5.36 - 0.34
    rifle_pose(p, (0.2, 0.98, grip_z), yaw=0, pitch=0, roll=0, right_pole=(1.0, -0.4, -0.5), left_pole=(-0.6, 0.0, -1.0))
    out["Aim"] = p.angles()
    return out


def build(**kw):
    s = SkinnedAsset("InfantrySkinned", skeleton(), VARIANTS, tex_size=1024, pivot=(0, 0, HIP_Z))
    s.zmin = 0.0
    materials(s)
    torso(s)
    legs(s)
    boots(s)
    arms(s)
    hands(s)
    head(s)
    helmets(s)
    plate_carrier(s)
    front_gear(s)
    back_gear(s)
    belt(s)
    rifle(s)
    R0, _ = rifle_rest()
    s.meta = {
        "rbxmx_prefix": "Infantry_Skinned",
        "hip_height": HIP_Z,
        # Rifle axes at rest in Roblox model space (forward = towards the muzzle).
        "rifle_rest": {"forward": [round(v, 4) for v in (R0.col[1].x, R0.col[1].z, -R0.col[1].y)],
                       "up": [round(v, 4) for v in (R0.col[2].x, R0.col[2].z, -R0.col[2].y)]},
    }
    for v in VARIANTS:
        print(f"[rmh] {v}: {s.triangles(v)} tris (pre-triangulation estimate)")
    ps = poses(s)
    views = [
        ("_front", (0.18, 1.0, 0.12), None, "Patrol", {}),
        ("_side", (1.0, 0.08, 0.1), None, "Patrol", {"axis": "y"}),
        ("_rear", (-0.25, -1.0, 0.14), None, "Patrol", {}),
        ("_aim", (0.9, 1.0, 0.2), ("Rifleman",), "Aim", {}),
        ("_bind", (0.3, 1.0, 0.15), ("Rifleman",), "Rest", {}),
        ("_Rifleman", (0.7, 1.0, 0.25), ("Rifleman",), "Patrol", {}),
        ("_Grenadier", (0.7, 1.0, 0.25), ("Grenadier",), "Patrol", {}),
        ("_Radio", (-0.7, -1.0, 0.25), ("Radio",), "Patrol", {}),
        ("_thumb500", (0.1, 1.0, 0.15), None, "Patrol", {"lens": 220, "distance": 500, "res": (256, 144), "bw": True}),
    ]
    return s.finish(views=views, poses=ps, lod_ratio=kw.get("lod_ratio", 0.32), preview=kw.get("preview", True), samples=kw.get("samples", 24))
