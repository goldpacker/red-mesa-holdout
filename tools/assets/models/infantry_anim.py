"""InfantryAnim: bone animation clips for the skinned infantry (CHAR-2).

Authored with the same FK + two-bone IK pose builder as the Patrol/Aim
poses (rmh.skin_pose.Pose), from a small set of rig controls per key
(hips offset/rotation, spine/chest/neck/head angles, ankle targets, hand
targets or FK arm angles). Every sampled frame re-runs the IK, so planted
feet stay planted between keys. No meshes are built: the skeleton comes
from models/infantry_skinned.py, previews pose the shipped GLB.

    Blender -b --factory-startup -P tools/assets/models/infantry_anim.py -- [--no-preview] [--only Walk,Throw]

Writes
    assets/exported/InfantrySkinned/anim.json      clips (Bone.Transform angles per frame)
    src/client/InfantryRigClips.luau               the same data for the client rig
    assets/previews/InfantryAnim_<Clip>.png        filmstrips (Workbench, textured)

Conventions (docs/ASSET_PIPELINE.md "Skinned meshes"): Blender asset space
(+Y forward, +Z up); a frame is {bone: [rx, ry, rz(, [x, y, z])]} for
`Bone.Transform = CFrame.new(x, y, z) * CFrame.Angles(rx, ry, rz)` in
degrees / studs at model scale 1 (the client multiplies the Hips offset
by the model's scale).
"""
import json
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import bpy
from mathutils import Matrix, Vector

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from rmh.skin_pose import Pose, pose_quaternion, rot  # noqa: E402
from models import infantry_skinned as inf  # noqa: E402

ROOT = HERE.parents[1]
OUT_DIR = ROOT / "assets" / "exported" / "InfantrySkinned"
LUAU = ROOT / "src" / "client" / "InfantryRigClips.luau"
FPS = 20

# Combat jog (the server moves infantry at 10.5 studs/s, x0.85-1.15, and
# renders them at 1.1x): one stride cycle covers WALK_CYCLE studs at scale 1.
WALK_FRAMES = 16
WALK_CYCLE = 7.2
STANCE = 0.36
FRONT = 1.0          # ankle y at touchdown
ANKLE_Z = 0.36
BALL = Vector((0.0, 0.42, -0.30))   # ball of the foot relative to the ankle (rest)

ANIMATED = [
    "Hips", "Spine", "Chest", "NeckBone", "HeadBone",
    "RightUpperArm", "RightLowerArm", "RightHand",
    "LeftUpperArm", "LeftLowerArm", "LeftHand",
    "RightUpperLeg", "RightLowerLeg", "RightFoot",
    "LeftUpperLeg", "LeftLowerLeg", "LeftFoot",
]
ASSET = SimpleNamespace(bones=inf.skeleton())
# Patrol / Aim re-solved with the fixed two-bone IK (docs/ASSET_PIPELINE.md
# "Skinned meshes", gotcha 7): the manifest's tables predate the fix and
# leave the support hand up to 0.6 studs off the handguard.
POSES = inf.poses(ASSET)


def smooth(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    if isinstance(a, (tuple, list)):
        return tuple(x + (y - x) * t for x, y in zip(a, b))
    return a + (b - a) * t


# --- rig controls -> Pose ----------------------------------------------------

def table_rot(pose_name, bone):
    r = POSES[pose_name].get(bone)
    return rot(*r[:3]) if r else Matrix.Identity(3)


def ankle_on_ball(ball_ground, pitch):
    """Ankle position when the foot pivots toe-down (`pitch` < 0) about its
    ball resting at `ball_ground`."""
    R = rot(pitch, 0, 0)
    return Vector(ball_ground) - R @ BALL


def leg(p, side, ankle, foot=(0, 0, 0), pole=None):
    """IK a leg: ankle target (world), foot world angles, knee pole in the
    hips' frame (default: forward), so knees bend the right way lying down."""
    s = "Left" if side < 0 else "Right"
    pole = p.world_rot("Hips") @ Vector(pole or (side * 0.12, 1.0, 0.0))
    p.ik(s + "UpperLeg", s + "LowerLeg", s + "Foot", Vector(ankle), rot(*foot), pole)


def chest_frame(p):
    return p.world_rot("Chest"), p.world_head("Chest"), p.bones["Chest"].head


def rifle_one_hand(p, grip_rest, yaw, pitch, roll, pole=(0.9, -0.6, -0.3)):
    """Right hand carries the carbine alone: grip point and rifle direction
    are given in the chest's rest frame, so the gun moves with the torso."""
    R0, G0 = inf.rifle_rest()
    Rc, _, _ = chest_frame(p)
    target = Matrix.Rotation(math.radians(yaw), 3, "Z") @ Matrix.Rotation(math.radians(pitch), 3, "X") @ Matrix.Rotation(math.radians(roll), 3, "Y")
    D = Rc @ target @ R0.transposed()
    grip = p.world_point("Chest", grip_rest)
    H0 = p.bones["RightHand"].head
    wrist = grip + D @ (H0 - G0)
    p.ik("RightUpperArm", "RightLowerArm", "RightHand", wrist, D, pole)


def hand_to(p, side, target, pole, wrist=(0, 0, 0)):
    """IK a wrist to a model-space point (feet are planted, so the model
    frame is the ground frame); `pole` is the elbow direction (model space);
    the hand then continues the forearm with a `wrist` bend (Roblox angles)."""
    s = "Left" if side < 0 else "Right"
    p.ik(s + "UpperArm", s + "LowerArm", s + "Hand", Vector(target), Matrix.Identity(3), Vector(pole))
    p.local[s + "Hand"] = rot(*wrist)


def build(c):
    """c: controls dict -> Pose."""
    p = Pose(ASSET)
    p.offset = Vector(c.get("hips.off", (0, 0, 0)))
    p.set("Hips", rot(*c.get("hips", (0, 0, 0))))
    base = c.get("base")
    for b in ("Spine", "Chest", "NeckBone", "HeadBone"):
        R = rot(*c.get(b, (0, 0, 0)))
        if base:
            R = R @ table_rot(base, b)
        p.set(b, R)
    leg(p, -1, c["lfoot"], c.get("lfoot.rot", (0, 0, 0)), c.get("lknee"))
    leg(p, 1, c["rfoot"], c.get("rfoot.rot", (0, 0, 0)), c.get("rknee"))
    arms = c.get("arms", "Patrol")
    if arms in ("Patrol", "Aim"):
        for b in ("RightUpperArm", "RightLowerArm", "RightHand", "LeftUpperArm", "LeftLowerArm", "LeftHand"):
            p.set(b, table_rot(arms, b))
    elif arms == "throw":
        rifle_one_hand(p, *c["rifle"])
        hand_to(p, -1, *c["lhand"])
    elif arms == "fk":
        for b, r in c["fk"].items():
            p.set(b, rot(*r))
    return p


def frame_of(p):
    """Pose -> {bone: [rx, ry, rz(, [x, y, z])]} for the animated bones."""
    out = {}
    angles = p.angles()
    for b in ANIMATED:
        r = angles.get(b, [0.0, 0.0, 0.0])
        if b == "Hips" and len(r) < 4:
            r = list(r[:3]) + [[0.0, 0.0, 0.0]]
        out[b] = r
    return out


def blend(a, b, t):
    """Blend two control values (numbers, nested tuples, dicts; strings snap)."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * t
    if isinstance(a, (tuple, list, Vector)) and isinstance(b, (tuple, list, Vector)):
        return tuple(blend(x, y, t) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return {k: blend(a[k], b[k], t) if k in b else a[k] for k in a}
    return b if t >= 0.5 else a


EASE = {
    "smooth": lambda a: a * a * (3 - 2 * a),
    "in": lambda a: a * a,
    "out": lambda a: 1 - (1 - a) ** 2,
    "linear": lambda a: a,
}


def keyed(keys, t):
    """Eased interpolation between control keys [(time, controls, ease)];
    a key's ease shapes the segment that ends at it."""
    if t <= keys[0][0]:
        return dict(keys[0][1])
    for (t0, c0, _), (t1, c1, ease) in zip(keys, keys[1:]):
        if t <= t1:
            a = EASE[ease or "smooth"]((t - t0) / (t1 - t0))
            out = dict(c1)
            for k, v in c0.items():
                if k in c1:
                    out[k] = blend(v, c1[k], a)
            return out
    return dict(keys[-1][1])


# --- clips ----------------------------------------------------------------------

STAND = {"lfoot": (-0.31, -0.02, ANKLE_Z), "rfoot": (0.31, -0.02, ANKLE_Z)}


def static_clip(name):
    """Patrol / Aim as solved by models/infantry_skinned.poses()."""
    table = POSES[name]
    frame = {b: table.get(b, [0.0, 0.0, 0.0]) for b in ANIMATED}
    if len(frame["Hips"]) < 4:
        frame["Hips"] = list(frame["Hips"][:3]) + [[0.0, 0.0, 0.0]]
    return {"loop": True, "frames": [frame]}


def foot_track(u):
    """Ankle target, foot angles for one foot at foot phase u (0 = touchdown)."""
    S = WALK_CYCLE * STANCE
    toe_off = ankle_on_ball((0, FRONT - S + BALL.y, ANKLE_Z + BALL.z), -38)
    if u < STANCE:
        a = u / STANCE
        y = FRONT - a * S
        heel = 7 * (1 - smooth(0, 0.18, a))
        pitch = heel - 38 * smooth(0.55, 1.0, a)
        if pitch < 0:
            ankle = ankle_on_ball((0, y + BALL.y, ANKLE_Z + BALL.z), pitch)
        else:
            ankle = Vector((0, y, ANKLE_Z))
        return ankle, pitch
    b = (u - STANCE) / (1 - STANCE)
    e = 0.5 - 0.5 * math.cos(math.pi * b)
    y = lerp(toe_off.y, FRONT, e) - 0.55 * math.sin(math.pi * b) * (1 - b) ** 1.5
    z = lerp(toe_off.z, ANKLE_Z, b) + 0.95 * math.sin(math.pi * b ** 0.7) * (1 - 0.25 * b)
    pitch = -38 - 18 * math.sin(math.pi * min(1, b * 1.6)) * (b < 0.62) + 45 * smooth(0.25, 0.92, b)
    return Vector((0, y, z)), pitch


def walk_controls(phase):
    feet = {}
    for side, off in ((-1, 0.0), (1, 0.5)):
        u = (phase + off) % 1.0
        ankle, pitch = foot_track(u)
        ankle.x = side * 0.23
        feet[side] = (ankle, pitch, u < STANCE)
    bob = math.cos(4 * math.pi * (phase - STANCE / 2))
    stance_w = (1 if feet[-1][2] else 0) - (1 if feet[1][2] else 0)
    yaw = -7.0 * (feet[-1][0].y - feet[1][0].y) / (WALK_CYCLE * STANCE)
    roll = -2.5 * stance_w
    c = {
        "base": "Patrol",
        "hips.off": (0.05 * stance_w * -1, 0.05, -0.31 - 0.07 * bob),
        "hips": (-5.0, yaw, roll),
        "Spine": (1.5 * bob, -0.75 * yaw, -0.8 * roll),
        "Chest": (1.0 * bob, -0.35 * yaw, 0.0),
        "NeckBone": (-0.8 * bob, 0.5 * yaw, 0.0),
        "HeadBone": (2.0, 0.3 * yaw, 0.0),
        "arms": "Patrol",
        "lfoot": tuple(feet[-1][0]), "lfoot.rot": (feet[-1][1], 0, 0),
        "rfoot": tuple(feet[1][0]), "rfoot.rot": (feet[1][1], 0, 0),
    }
    return c


def walk_clip():
    frames = [frame_of(build(walk_controls(i / WALK_FRAMES))) for i in range(WALK_FRAMES)]
    return {"loop": True, "cycle": WALK_CYCLE, "frames": frames}


# Left-handed overhand throw (the right hand keeps the carbine low). The
# right side faces the target: right foot forward, left foot back; the
# torso winds up to the left (+yaw) and whips right through the release.
THROW_FEET = {"lfoot": (-0.45, -0.72, ANKLE_Z), "rfoot": (0.32, 0.7, ANKLE_Z), "lfoot.rot": (0, 55, 0), "rfoot.rot": (0, 12, 0)}
RIFLE_LOW = ((0.62, 0.42, 3.75), 12, -52, -18)


def throw_keys():
    ready = dict(THROW_FEET, **{
        "hips.off": (0.0, -0.05, -0.34), "hips": (-4, 24, 0),
        "Spine": (-5, 6, 0), "Chest": (-3, 4, 0), "NeckBone": (2, -14, 0), "HeadBone": (-4, -16, 0),
        "arms": "throw", "rifle": RIFLE_LOW,
        "lhand": ((-0.05, 0.72, 4.95), (-0.8, -0.5, -0.6), (10, 0, 0)),
    })
    cock = dict(ready, **{
        "hips.off": (-0.05, -0.28, -0.3), "hips": (4, 40, 2),
        "Spine": (5, 12, 0), "Chest": (6, 10, 0), "NeckBone": (-2, -28, 0), "HeadBone": (-6, -26, 0),
        "lhand": ((-0.6, -1.25, 5.9), (-1.0, 0.0, 0.15), (-40, 0, 0)),
    })
    release = dict(ready, **{
        "hips.off": (0.05, 0.22, -0.38), "hips": (-8, -14, -2),
        "Spine": (-10, -14, 0), "Chest": (-6, -10, 0), "NeckBone": (-2, 16, 0), "HeadBone": (6, 14, 0),
        "lhand": ((-0.42, 1.25, 6.25), (-1.0, 0.2, 0.0), (30, 0, 0)),
    })
    follow = dict(ready, **{
        "hips.off": (0.1, 0.42, -0.55), "hips": (-18, -28, -3),
        "Spine": (-14, -12, 0), "Chest": (-8, -6, 0), "NeckBone": (4, 18, 0), "HeadBone": (10, 16, 0),
        "lhand": ((0.35, 1.05, 3.2), (-1.0, 0.3, 0.3), (20, 0, 0)),
        "lfoot": (-0.45, -0.66, ANKLE_Z + 0.18), "lfoot.rot": (-30, 55, 0),
    })
    return [
        (0.0, ready, None),
        (0.14, cock, "out"),
        (0.26, release, "in"),
        (0.44, follow, "out"),
        (0.62, follow, "linear"),
        (1.05, ready, "smooth"),
    ], ready


def throw_clips():
    keys, ready = throw_keys()
    dur = keys[-1][0]
    n = int(round(dur * FPS)) + 1
    frames = [frame_of(build(keyed(keys, i / FPS))) for i in range(n)]
    return {"loop": False, "duration": dur, "frames": frames}, {"loop": True, "frames": [frame_of(build(ready))]}


# Death falls: backward (the server's fallDir +1) and forward (-1).
ARM_SLACK = {"RightUpperArm": (15, 0, 10), "RightLowerArm": (35, 0, 0), "RightHand": (0, 0, 0),
             "LeftUpperArm": (20, 0, -10), "LeftLowerArm": (45, 0, 0), "LeftHand": (0, 0, 0)}


def death_back_keys():
    hit = dict(STAND, **{
        "hips.off": (0, -0.12, -0.12), "hips": (10, 0, 0),
        "Spine": (12, 0, 0), "Chest": (10, 0, 4), "NeckBone": (10, 0, 0), "HeadBone": (16, 0, 0),
        "arms": "fk", "fk": {"RightUpperArm": (-12, 0, 30), "RightLowerArm": (40, 0, 0), "RightHand": (-20, 0, 0),
                             "LeftUpperArm": (-16, 0, -34), "LeftLowerArm": (35, 0, 0), "LeftHand": (0, 0, 0)},
    })
    buckle = dict(hit, **{
        "hips.off": (0.05, -0.45, -1.05), "hips": (28, 4, -5),
        "Spine": (10, 0, 0), "Chest": (6, 0, 4), "NeckBone": (12, 0, 0), "HeadBone": (18, 8, 0),
        "lfoot": (-0.34, 0.3, ANKLE_Z), "rfoot": (0.38, 0.12, ANKLE_Z),
        "fk": {"RightUpperArm": (-20, 0, 48), "RightLowerArm": (30, 0, 0), "RightHand": (-20, 0, 0),
               "LeftUpperArm": (-14, 0, -54), "LeftLowerArm": (25, 0, 0), "LeftHand": (0, 0, 0)},
    })
    fall = dict(buckle, **{
        "hips.off": (0.05, -1.45, -2.35), "hips": (62, 6, -8),
        "Spine": (8, 0, 0), "Chest": (4, 0, 4), "NeckBone": (10, 0, 0), "HeadBone": (14, 14, 0),
        "lfoot": (-0.36, 0.9, 0.62), "rfoot": (0.42, 0.75, 0.48), "lfoot.rot": (25, 0, 0), "rfoot.rot": (15, 0, 0),
        "fk": {"RightUpperArm": (-10, 0, 66), "RightLowerArm": (25, 0, 0), "RightHand": (-20, 0, 0),
               "LeftUpperArm": (0, 0, -70), "LeftLowerArm": (20, 0, 0), "LeftHand": (0, 0, 0)},
    })
    impact = dict(fall, **{
        "hips.off": (0.05, -1.9, -3.08), "hips": (87, 6, -6),
        "Spine": (4, 0, 0), "Chest": (2, 0, 2), "NeckBone": (-4, 10, 0), "HeadBone": (-6, 22, 0),
        "lfoot": (-0.55, 1.08, 0.3), "rfoot": (0.5, 0.55, 0.5), "lfoot.rot": (40, 0, -10), "rfoot.rot": (15, 0, 0),
        "fk": {"RightUpperArm": (40, 0, 78), "RightLowerArm": (20, 0, 0), "RightHand": (-10, 0, 0),
               "LeftUpperArm": (60, 0, -72), "LeftLowerArm": (35, 0, 0), "LeftHand": (0, 0, 0)},
    })
    settle = dict(impact, **{
        "hips.off": (0.05, -1.95, -3.12), "hips": (89, 6, -6),
        "NeckBone": (-4, 14, 0), "HeadBone": (-8, 30, 0),
        "fk": {"RightUpperArm": (30, 0, 82), "RightLowerArm": (25, 0, 0), "RightHand": (-10, 0, 0),
               "LeftUpperArm": (50, 0, -76), "LeftLowerArm": (40, 0, 0), "LeftHand": (0, 0, 0)},
    })
    return [(0.0, hit, None), (0.28, buckle, "smooth"), (0.6, fall, "in"), (0.8, impact, "in"),
            (0.95, dict(impact, **{"hips.off": (0.05, -1.92, -2.98)}), "out"), (1.15, settle, "smooth"), (1.3, settle, "linear")]


def death_front_keys():
    hit = dict(STAND, **{
        "hips.off": (0, 0.05, -0.2), "hips": (-12, 0, 0),
        "Spine": (-16, 0, 0), "Chest": (-10, 0, 0), "NeckBone": (-14, 0, 0), "HeadBone": (-18, 0, 0),
        "arms": "fk", "fk": dict(ARM_SLACK),
    })
    kneel = dict(hit, **{
        "hips.off": (0, 0.05, -1.62), "hips": (-12, -4, 3),
        "Spine": (-18, 0, 0), "Chest": (-10, 0, 0), "NeckBone": (-14, 0, 0), "HeadBone": (-16, -6, 0),
        "lfoot": (-0.34, -1.38, 0.3), "rfoot": (0.34, -1.3, 0.3), "lfoot.rot": (-70, 0, 0), "rfoot.rot": (-65, 0, 0),
        "fk": {"RightUpperArm": (8, 0, 12), "RightLowerArm": (30, 0, 0), "RightHand": (0, 0, 0),
               "LeftUpperArm": (10, 0, -12), "LeftLowerArm": (35, 0, 0), "LeftHand": (0, 0, 0)},
    })
    tip = dict(kneel, **{
        "hips.off": (0, 0.55, -2.25), "hips": (-52, -4, 6),
        "Spine": (-8, 0, 0), "Chest": (-4, 0, 0), "NeckBone": (4, 0, 0), "HeadBone": (6, -10, 0),
        "lfoot": (-0.34, -1.5, 0.26), "rfoot": (0.36, -1.45, 0.3),
        "fk": {"RightUpperArm": (70, 0, 18), "RightLowerArm": (25, 0, 0), "RightHand": (0, 0, 0),
               "LeftUpperArm": (75, 0, -22), "LeftLowerArm": (20, 0, 0), "LeftHand": (0, 0, 0)},
    })
    down = dict(tip, **{
        "hips.off": (0.05, 1.05, -3.05), "hips": (-86, -6, 8),
        "Spine": (-2, 0, 0), "Chest": (-2, 0, 0), "NeckBone": (14, 20, 0), "HeadBone": (12, 42, 0),
        "lfoot": (-0.42, -1.95, 0.28), "rfoot": (0.45, -1.75, 0.34), "lfoot.rot": (-80, 0, 0), "rfoot.rot": (-75, 0, 0),
        "fk": {"RightUpperArm": (20, 0, 30), "RightLowerArm": (30, 0, 0), "RightHand": (0, 0, 0),
               "LeftUpperArm": (150, 0, -25), "LeftLowerArm": (25, 0, 0), "LeftHand": (0, 0, 0)},
    })
    settle = dict(down, **{"hips.off": (0.05, 1.08, -3.1), "hips": (-88, -6, 8), "HeadBone": (12, 48, 0)})
    return [(0.0, hit, None), (0.34, kneel, "in"), (0.62, tip, "smooth"), (0.86, down, "in"),
            (0.98, dict(down, **{"hips.off": (0.05, 1.05, -2.95)}), "out"), (1.15, settle, "smooth"), (1.35, settle, "linear")]


def keyed_clip(keys):
    dur = keys[-1][0]
    n = int(round(dur * FPS)) + 1
    return {"loop": False, "duration": dur, "frames": [frame_of(build(keyed(keys, i / FPS))) for i in range(n)]}


def clips():
    out = {"Patrol": static_clip("Patrol"), "Aim": static_clip("Aim"), "Walk": walk_clip()}
    out["Throw"], out["ThrowReady"] = throw_clips()
    out["DeathBack"] = keyed_clip(death_back_keys())
    out["DeathFront"] = keyed_clip(death_front_keys())
    return out


# --- output ---------------------------------------------------------------------

def fmt(v, nd):
    s = f"{v:.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def write_luau(data):
    lines = [
        "--!strict",
        "-- GENERATED by tools/assets/models/infantry_anim.py (CHAR-2); do not edit.",
        "-- Bone.Transform keyframes for the skinned infantry. Per clip: frames,",
        "-- loop, duration (s, one-shot clips) or cycle (studs per stride, Walk).",
        "-- tracks[bone] = flat { rx, ry, rz, ... } in degrees per frame; Hips",
        "-- carries { rx, ry, rz, x, y, z } with the offset in studs at scale 1.",
        "",
        "return {",
        f"\tfps = {FPS},",
        "\tbones = { " + ", ".join(f'"{b}"' for b in ANIMATED) + " },",
        "\tclips = {",
    ]
    for name, clip in data.items():
        lines.append(f"\t\t{name} = {{")
        lines.append(f"\t\t\tframes = {len(clip['frames'])},")
        lines.append(f"\t\t\tloop = {'true' if clip['loop'] else 'false'},")
        if "duration" in clip:
            lines.append(f"\t\t\tduration = {fmt(clip['duration'], 3)},")
        if "cycle" in clip:
            lines.append(f"\t\t\tcycle = {fmt(clip['cycle'], 3)},")
        lines.append("\t\t\ttracks = {")
        for b in ANIMATED:
            vals = []
            for fr in clip["frames"]:
                r = fr[b]
                vals += [fmt(x, 1) for x in r[:3]]
                if b == "Hips":
                    vals += [fmt(x, 3) for x in r[3]]
            lines.append(f"\t\t\t\t{b} = {{ {', '.join(vals)} }},")
        lines.append("\t\t\t},")
        lines.append("\t\t},")
    lines += ["\t},", "}", ""]
    LUAU.write_text("\n".join(lines))


# --- previews ---------------------------------------------------------------------

def preview_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(OUT_DIR / "InfantrySkinned.glb"))
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    img = bpy.data.images.load(str(OUT_DIR / "InfantrySkinned_main_color.png"))
    mat = bpy.data.materials.new("Preview")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs[0], bsdf.inputs[0])
    for o in bpy.data.objects:
        if o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(mat)
            o.hide_render = True
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_shadows = True
    sh.show_cavity = True
    sh.shadow_intensity = 0.6
    bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 0, 0))
    ground = bpy.context.active_object
    gm = bpy.data.materials.new("Ground")
    gm.use_nodes = True
    gb = next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    gb.inputs[0].default_value = (0.55, 0.33, 0.2, 1)
    ground.data.materials.append(gm)
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    return arm, bpy.data.objects["Rifleman"], cam


def apply_frame(arm, frame):
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.location = (0, 0, 0)
    basis_t = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0))).transposed()
    for name, r in frame.items():
        pb = arm.pose.bones[name]
        pb.rotation_quaternion = pose_quaternion(*r[:3])
        if len(r) > 3:
            pb.location = basis_t @ Vector((r[3][0], -r[3][2], r[3][1]))


def filmstrip(objs, name, frames, step, view, res=(1800, 560), lens=50):
    """One posed copy per frame, laid out along `step`; camera along `view`."""
    arm, mesh, cam = objs
    scene = bpy.context.scene
    step = Vector(step)
    copies = []
    n = len(frames)
    for i, fr in enumerate(frames):
        a2 = arm.copy()
        a2.data = arm.data
        a2.location = step * (i - (n - 1) / 2)
        scene.collection.objects.link(a2)
        m2 = mesh.copy()
        m2.parent = a2
        m2.modifiers[0].object = a2
        m2.hide_render = False
        scene.collection.objects.link(m2)
        apply_frame(a2, fr)
        copies += [a2, m2]
    bpy.context.view_layer.update()
    cam.data.lens = lens
    d = Vector(view).normalized()
    fov = 2 * math.atan(18 / lens)
    aspect = res[0] / res[1]
    half_w = (n * step.length + 1.5) / 2
    dist = max(half_w / math.tan(fov / 2), 4.2 * aspect / math.tan(fov / 2)) * 1.02
    cam.location = Vector((0, 0, 2.4)) + d * dist
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x, scene.render.resolution_y = res
    path = ROOT / "assets" / "previews" / f"InfantryAnim_{name}.png"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    for o in copies:
        bpy.data.objects.remove(o)
    print(f"[anim] preview {path.name}")


def previews(data, only):
    objs = preview_scene()
    want = lambda n: not only or n in only  # noqa: E731
    if want("Walk"):
        w = data["Walk"]["frames"]
        filmstrip(objs, "Walk_side", w[::2], (0, 2.8, 0), (1, 0, 0.06))
        filmstrip(objs, "Walk", w[::2], (-3.2, 0, 0), (0.35, 1, 0.12))
    if want("Poses"):
        poses = [data[k]["frames"][0] for k in ("Patrol", "Aim", "ThrowReady")] + [data["Walk"]["frames"][4]]
        filmstrip(objs, "Poses", poses, (-3.6, 0, 0), (0.4, 1, 0.1), res=(1400, 600))
    if want("Throw"):
        fr = data["Throw"]["frames"]
        pick = [fr[i] for i in (0, 2, 3, 4, 5, 6, 8, 10, 13, len(fr) - 1)]
        filmstrip(objs, "Throw", pick, (-3.2, 0, 0), (0.15, 1, 0.12))
        filmstrip(objs, "Throw_left", pick, (0, -3.4, 0), (-1, 0.15, 0.08))
    for key in ("DeathBack", "DeathFront"):
        if want(key):
            fr = data[key]["frames"]
            pick = [fr[i] for i in (0, 3, 6, 9, 12, 16, 20, len(fr) - 1)]
            filmstrip(objs, key, pick, (0, 6.5, 0), (1, 0.0, 0.3), res=(2000, 480), lens=55)


def check_reach(data_builders):
    """Largest gap between an IK target and where the foot/hand ended up."""
    worst = 0.0
    for name, controls in data_builders:
        p = build(controls)
        for side, key in ((-1, "lfoot"), (1, "rfoot")):
            s = "Left" if side < 0 else "Right"
            gap = (p.world_head(s + "Foot") - Vector(controls[key])).length
            if gap > 0.02:
                print(f"[anim] WARN {name}: {s}Foot misses its target by {gap:.2f}")
            worst = max(worst, gap)
    return worst


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    only = set(argv[argv.index("--only") + 1].split(",")) if "--only" in argv else set()
    data = clips()
    samples = [(f"Walk{i}", walk_controls(i / WALK_FRAMES)) for i in range(WALK_FRAMES)]
    keys, _ = throw_keys()
    samples += [(f"Throw{t:.2f}", keyed(keys, t)) for t in (k[0] for k in keys)]
    samples += [(f"DeathBack{k[0]:.2f}", k[1]) for k in death_back_keys()]
    samples += [(f"DeathFront{k[0]:.2f}", k[1]) for k in death_front_keys()]
    print(f"[anim] worst IK reach gap {check_reach(samples):.3f} studs")
    (OUT_DIR / "anim.json").write_text(json.dumps({"fps": FPS, "bones": ANIMATED, "clips": data}, indent=0))
    write_luau(data)
    print(f"[anim] clips: {', '.join(f'{k}({len(v['frames'])})' for k, v in data.items())} -> {LUAU.relative_to(ROOT)}")
    if "--no-preview" not in argv:
        previews(data, only)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        sys.exit(1)
