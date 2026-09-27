"""The airdrop in the title key art (LOOK-4): transports, a stick of
paratroopers under canopies and a tank on its drop platform under a
cargo-chute cluster, built from the game's own HS-6 / CHAR / HS assets.

Imported by tools/ui/keyart_scene.py (Blender). Everything is laid out in
Roblox world coordinates the way the game builds a drop:

  - the stick: troopers leave the ramp `stick` s apart along the flight
    line, free-fall FREE_FALL s (carried CARRY studs forward, dropping
    FREE_FALL_DROP), then descend under canopy at DESCENT studs/s drifting
    downwind (src/shared/AirdropConfig.luau, client/AirdropStyle.luau);
  - a trooper hangs `HARNESS_UP` below the canopy's harness point in the
    Hang pose of client/AirdropTrooperBody (arms up on the risers);
  - a cargo load: DropPlatform (rigging + slings) with the vehicle on
    LoadAttach, the canopies on SlingApex tilted out by Cargo.TILT.

GLB meshes come in rotated 180 deg about the vertical relative to the
assets' Roblox model frame (the HS pipeline turns the MeshParts back); `R180`
undoes that so model-space positions from the manifests apply directly.
"""
import math
import os

import bpy
from mathutils import Matrix, Vector

P_RB = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))  # Blender = P_RB @ Roblox
R180 = Matrix.Rotation(math.pi, 4, "Z")

# AirdropConfig / AirdropStyle values the layout reproduces.
TRANSPORT_SPEED = 90.0
TROOPER = {"stick": 0.4, "free_fall": 1.1, "free_fall_drop": 26.0, "carry": 36.0, "descent": 17.0, "scale": 1.1, "harness_up": 5.25 * 1.1}
CARGO_TILT = {"Tank": math.radians(29), "Buggy": math.radians(19)}
CARGO_CHUTES = {"Tank": 4, "Buggy": 2}
SLING_APEX = 36.0
LOAD_ATTACH = 2.3
WIND = Vector((2.6, 0.0, 1.1)).normalized() * 1.6  # studs/s (AirdropStyle fallback breeze)

# The Hang pose (client/AirdropTrooperBody HANG): Roblox Euler degrees per bone.
HANG = {
    "Spine": (3, 0, 0), "Chest": (2, 0, 0), "NeckBone": (-4, 0, 0), "HeadBone": (6, 0, 0),
    "RightUpperArm": (8, 0, 122), "RightLowerArm": (0, 0, 75),
    "LeftUpperArm": (8, 0, -122), "LeftLowerArm": (0, 0, -75),
    "RightUpperLeg": (12, 0, -2), "RightLowerLeg": (-20, 0, 0), "RightFoot": (22, 0, 0),
    "LeftUpperLeg": (8, 0, 2), "LeftLowerLeg": (-16, 0, 0), "LeftFoot": (22, 0, 0),
}
TUCK = {
    "Spine": (12, 0, 0), "Chest": (8, 0, 0), "NeckBone": (10, 0, 0), "HeadBone": (8, 0, 0),
    "RightUpperArm": (24, 0, -4), "RightLowerArm": (45, 0, 0),
    "LeftUpperArm": (24, 0, 4), "LeftLowerArm": (45, 0, 0),
    "RightUpperLeg": (28, 0, -3), "RightLowerLeg": (-45, 0, 0), "RightFoot": (15, 0, 0),
    "LeftUpperLeg": (28, 0, 3), "LeftLowerLeg": (-45, 0, 0), "LeftFoot": (15, 0, 0),
}

TRANSPORT_SKIP = ("Lamp", "Lights", "LODHull")


def rb(v):
    return Vector((v[0], -v[2], v[1]))


def rb_rot(m3):
    """Roblox rotation matrix -> Blender rotation matrix."""
    return P_RB @ m3 @ P_RB.transposed()


def roblox_angles(rx, ry, rz):
    """CFrame.Angles(rx, ry, rz) (radians) as a Roblox 3x3 matrix."""
    return (Matrix.Rotation(rx, 3, "X") @ Matrix.Rotation(ry, 3, "Y") @ Matrix.Rotation(rz, 3, "Z"))


def cframe(pos, rot3=None):
    """Roblox CFrame (position, 3x3 rotation) -> Blender 4x4 world matrix."""
    rot = rb_rot(rot3 if rot3 is not None else Matrix.Identity(3))
    return Matrix.Translation(rb(pos)) @ rot.to_4x4()


def heading_rot(yaw_deg, pitch_deg=0.0, roll_deg=0.0):
    """Roblox orientation for a model whose nose is -Z: yaw about +Y (0 = nose
    toward -Z, + turns the nose toward -X), then pitch (nose up), then roll
    (right wing down for +)."""
    return (Matrix.Rotation(math.radians(yaw_deg), 3, "Y") @ Matrix.Rotation(math.radians(pitch_deg), 3, "X") @ Matrix.Rotation(math.radians(-roll_deg), 3, "Z"))


def link_part(name, mesh, world, hide_shadow=False):
    ob = bpy.data.objects.new(name, mesh)
    ob.matrix_world = world
    if hide_shadow:
        ob.visible_shadow = False
    bpy.context.scene.collection.objects.link(ob)
    return ob


def model_matrix(pos, rot3):
    """World matrix for GLB part meshes of a model placed at (pos, rot3)."""
    return cframe(pos, rot3) @ R180


def hinge(pivot_rb, angle_rad):
    """Rotation about the model's X axis through a manifest pivot (Roblox
    model coordinates), expressed in the GLB mesh frame."""
    conv = R180.to_3x3() @ P_RB
    p = conv @ Vector(pivot_rb)
    axis = conv @ Vector((1, 0, 0))
    return Matrix.Translation(p) @ Matrix.Rotation(angle_rad, 4, axis) @ Matrix.Translation(-p)


# ------------------------------------------------------------------ transport
def place_transport(parts, spec, manifest):
    """parts: {name: (mesh, centre, size)} from keyart_scene.import_asset."""
    rot = heading_rot(spec["yaw"], spec.get("pitch", 0.0), spec.get("bank", 0.0))
    base = model_matrix(spec["pos"], rot)
    pivots = manifest["pivots"]
    ramp = hinge(pivots["Ramp"], math.radians(21.8 * spec.get("ramp", 1.0)))
    door = hinge(pivots["CargoDoor"], math.radians(60.0 * spec.get("ramp", 1.0)))
    n = 0
    for name, (mesh, _c, _s) in parts.items():
        if any(k in name for k in TRANSPORT_SKIP):
            continue
        local = Matrix.Identity(4)
        if name == "RampDoor":
            local = ramp
        elif name == "CargoDoorPanel":
            local = door
        link_part(f"{spec.get('tag', 'T')}_{name}", mesh, base @ local, hide_shadow=name.startswith("Disc"))
        n += 1
    return n


# ------------------------------------------------------------------ trooper
def posed_trooper_mesh(glb_path, variant, pose, color_mat):
    """Imports the skinned soldier, poses it, returns a static posed mesh (GLB frame)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb_path)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == "ARMATURE")
    body = next(o for o in new if o.type == "MESH" and o.name.split(".")[0] == variant)
    bpy.context.view_layer.update()
    # The rig's bone rest frames follow the model axes, so each pose Euler is
    # a rotation about the model's (Roblox) axes at the bone head, composed
    # parent first. Work in the armature's space (GLB frame = R180 @ rb).
    conv = R180.to_3x3() @ P_RB
    world = {}
    for bone in arm.data.bones:  # parents come before children
        e = pose.get(bone.name)
        r_rb = roblox_angles(*(math.radians(a) for a in e)) if e else Matrix.Identity(3)
        r = (conv @ r_rb @ conv.transposed()).to_4x4()
        head = bone.head_local
        local = Matrix.Translation(head) @ r @ Matrix.Translation(-head)
        parent = world.get(bone.parent.name) if bone.parent else Matrix.Identity(4)
        world[bone.name] = parent @ local
    for pb in arm.pose.bones:
        pb.matrix = world[pb.name] @ pb.bone.matrix_local
        bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(body.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    mesh.transform(body.matrix_world)
    mesh.materials.clear()
    mesh.materials.append(color_mat)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    return mesh


def stick_layout(spec):
    """Positions (Roblox) of each trooper's harness and whether its canopy is
    open, `spec['t']` seconds after the first trooper left the ramp."""
    d = Vector(spec["dir"]).normalized()
    p0 = Vector(spec["release0"])
    out = []
    for i in range(spec["count"]):
        age = spec["t"] - i * TROOPER["stick"]
        if age < 0:
            continue
        r = p0 + d * (TRANSPORT_SPEED * TROOPER["stick"] * i)
        ff = TROOPER["free_fall"]
        if age < ff:
            u = age / ff
            pos = r + d * (TROOPER["carry"] * u) - Vector((0, TROOPER["free_fall_drop"] * u * u, 0))
            state = "Deploying"
        else:
            pos = r + d * TROOPER["carry"] - Vector((0, TROOPER["free_fall_drop"] + TROOPER["descent"] * (age - ff), 0)) + WIND * (age - ff)
            state = "Open"
        jitter = spec.get("jitter")
        if jitter:  # real sticks spread: each trooper's own drift and sink rate
            pos = pos + Vector(jitter[i % len(jitter)])
        out.append((i, pos, state, age))
    transport = p0 + d * (TRANSPORT_SPEED * spec["t"] + spec.get("ramp_ahead", 34.0))
    return out, transport


def place_trooper(chute_parts, body_mesh, pos, state, yaw_deg, swing_deg, tag):
    rot = Matrix.Rotation(math.radians(yaw_deg), 3, "Y") @ Matrix.Rotation(math.radians(swing_deg[0]), 3, "X") @ Matrix.Rotation(math.radians(swing_deg[1]), 3, "Z")
    base = model_matrix(pos, rot)
    for name in (f"Canopy{state}", f"Lines{state}"):
        mesh = chute_parts[name][0]
        link_part(f"{tag}_{name}", mesh, base)
    s = TROOPER["scale"]
    body = base @ Matrix.Translation((0, 0, -TROOPER["harness_up"])) @ Matrix.Diagonal((s, s, s, 1))
    link_part(f"{tag}_Body", body_mesh, body)


# ------------------------------------------------------------------ cargo
def place_cargo(platform_parts, cargo_parts, vehicle_parts, spec):
    kind = spec["kind"]
    rot = Matrix.Rotation(math.radians(spec["yaw"]), 3, "Y") @ Matrix.Rotation(math.radians(spec.get("swing", (0, 0))[0]), 3, "X") @ Matrix.Rotation(math.radians(spec.get("swing", (0, 0))[1]), 3, "Z")
    base = model_matrix(spec["pos"], rot)
    for name in ("Root", "Slings", f"{kind}Rigging"):
        link_part(f"Cargo_{name}", platform_parts[name][0], base)
    load = base @ Matrix.Translation((0, 0, LOAD_ATTACH))
    for name, (mesh, _c, _s) in vehicle_parts.items():
        link_part(f"Cargo_{kind}_{name}", mesh, load)
    n = CARGO_CHUTES[kind]
    tilt = CARGO_TILT[kind]
    for k in range(n):
        yaw = spec.get("chute_yaw0", 45.0) + 360.0 * k / n
        # Around the apex: turn to this chute's azimuth, then lean it out.
        lean = Matrix.Rotation(math.radians(yaw), 4, "Z") @ Matrix.Rotation(tilt, 4, "X")
        m = base @ Matrix.Translation((0, 0, SLING_APEX)) @ lean
        for name in ("CanopyOpen", "LinesOpen"):
            link_part(f"Cargo_chute{k}_{name}", cargo_parts[name][0], m)


def ground_canopy(chute_parts, pos, yaw_deg, tag):
    base = model_matrix(pos, Matrix.Rotation(math.radians(yaw_deg), 3, "Y"))
    for name in ("CanopyCollapsed", "LinesCollapsed"):
        link_part(f"{tag}_{name}", chute_parts[name][0], base)


# ------------------------------------------------------------------ build
def build(spec, import_asset, pbr_material, exported, log):
    """spec: the key-art airdrop layout (see keyart_scene.AIRDROP)."""
    import json

    tp = import_asset("Transport")
    tman = json.load(open(os.path.join(exported, "Transport", "manifest.json")))
    n = 0
    for t in spec.get("transports", []):
        n += place_transport(tp, t, tman)
    chute = import_asset("Parachute")
    inf = os.path.join(exported, "InfantrySkinned")
    body_mat = pbr_material("Trooper", *(os.path.join(inf, f"InfantrySkinned_main_{k}.png") for k in ("color", "normal", "rough", "metal")))
    bodies = {"Hang": posed_trooper_mesh(os.path.join(inf, "InfantrySkinned.glb"), "Rifleman", HANG, body_mat)}
    bodies["Tuck"] = posed_trooper_mesh(os.path.join(inf, "InfantrySkinned.glb"), "Rifleman", TUCK, body_mat)
    troopers = 0
    for s in spec.get("sticks", []):
        layout, tpos = stick_layout(s)
        for i, pos, state, age in layout:
            sw = s.get("swing", [(0, 0)])[i % len(s.get("swing", [(0, 0)]))]
            place_trooper(chute, bodies["Hang" if state == "Open" else "Tuck"], pos, state, s.get("yaw", 0) + 37 * i, sw, f"Trooper{i}")
            troopers += 1
        if s.get("transport"):
            t = dict(s["transport"])
            t["pos"] = tuple(tpos + Vector(t.get("offset", (0, 0, 0))))
            n += place_transport(tp, t, tman)
        log(f"stick: {len(layout)} troopers, transport at {tuple(round(v) for v in tpos)}")
    for c in spec.get("cargo", []):
        place_cargo(import_asset("DropPlatform"), import_asset("ParachuteCargo"), import_asset(c["kind"]), c)
    for g in spec.get("ground_canopies", []):
        ground_canopy(chute, g["pos"], g["yaw"], "Landed")
    log(f"airdrop: {n} transport parts, {troopers} troopers, {len(spec.get('cargo', []))} cargo loads")
