"""Title key art: the emplacement at sunset over the basin, with an airdrop
in progress (LOOK-4, Update 2).

Built in Blender from the real game assets:
  - the emplacement (assets/blender/Emplacement.blend, HS-4 source with its
    own full-resolution materials) at the turret pivot, turret posed;
  - the landscape meshes with their baked maps (assets/blender/Landscape_*.blend);
  - the live terrain surface captured from Studio (tools/ui/keyart_capture.py:
    assets/ui/art/src/keyart_terrain.npz), shaded with ENV's terrain
    MaterialVariant textures (assets/textures/terrain/<Name>/) at their
    studs-per-tile, blended per material like Roblox's voxel blend;
  - everything the game placed (ground strips, dressing, patches, ENV-4
    conflict dressing and hulks, rock and cliff kit; assets/ui/art/src/
    keyart_parts.json), instanced from their GLBs with their exported
    full-resolution PBR maps (trim sheets through `shared_textures`),
    resolved against the capture's commit (art.json `capture_rev`);
  - the airdrop (tools/ui/keyart_airdrop.py, layout in AIRDROP below): the
    HS-6 Transport with its ramp open, a stick of eight troopers (CHAR's
    skinned soldier in the Hang pose) under Parachute canopies, and a Tank
    on its DropPlatform under a four-chute ParachuteCargo cluster;
  - ENV's Sunset sky (tools/env/sky.osl + tools/env/sky_presets.json),
    rendered for the camera as a full-resolution plate (CPU, OSL) and as an
    equirect for the lighting, a sun lamp along the preset's sun, a low
    dust volume at the wall feet (LOOK-5's dust layer) and depth haze.

    tools/blender-lock.sh acquire look4
    B=/Applications/Blender.app/Contents/MacOS/Blender
    $B -b --factory-startup -P tools/ui/keyart_scene.py -- --sky --samples 64   # sky plate + env
    $B -b --factory-startup -P tools/ui/keyart_scene.py -- --texture            # final + texture
    tools/blender-lock.sh release look4

Defaults are the shipped render (camera "drop", sun 9, env 0.4, haze 0.18,
exposure 0.2, saturation 1.1, dust 0.006 up to 80 studs, AgX, 256 samples,
2048x1152). Drafts: --draft --res 0.4 --samples 12; overrides: --pos/--look
x,y,z (camera), --yaw/--pitch (turret), --view-look AgX_-_Punchy, --rev
<commit>|none, --no-airdrop, --save (writes assets/blender/TitleKeyArt.blend).

Writes assets/previews/ui/keyart_<cam>[_draft].png (the 16:9 render) and,
with --texture, assets/ui/art/title_keyart.png: the render squeezed
anamorphically into 1024x1024 (the title stretches it back to 16:9, so it
keeps 1024 px of vertical detail inside the 1024² texture cap) plus
assets/ui/art/art.json "keyart" (display aspect, focus). Roblox (x, y, z) =
Blender (x, -z, y); 1 Blender unit = 1 stud.
"""
import json
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
ART = os.path.join(ROOT, "assets", "ui", "art")
SRC = os.path.join(ART, "src")
CACHE = os.path.join(ART, "cache")
EXPORTED = os.path.join(ROOT, "assets", "exported")
PREVIEWS = os.path.join(ROOT, "assets", "previews", "ui")
TERRAIN_TEX = os.path.join(ROOT, "assets", "textures", "terrain")
PRESET = "Sunset"
TURRET_PIVOT = (0.0, 72.0, 0.0)
RES = (2048, 1152)  # 16:9 render; squeezed to 1024x1024 for the texture
OUT_SIZE = 1024

# Cameras (Roblox coordinates): eye, look-at, vertical FOV, turret yaw/pitch
# (degrees; yaw + turns toward +X, the right flank), focus: the horizontal
# screen point (0..1) the title keeps visible on narrow screens.
CAMERAS = {
    "hero": {"pos": (-16.0, 75.5, 15.0), "look": (14.0, 63.0, -48.0), "vfov": 40.0, "yaw": 16.0, "pitch": 4.0, "focus": 0.66},
    "wide": {"pos": (-26.0, 80.0, 24.0), "look": (20.0, 55.0, -120.0), "vfov": 42.0, "yaw": 12.0, "pitch": 3.0, "focus": 0.66},
    "low": {"pos": (-12.0, 70.2, 11.0), "look": (10.0, 69.0, -40.0), "vfov": 40.0, "yaw": 18.0, "pitch": 6.0, "focus": 0.66},
    # Update 2: over the gun at a drop in progress (transport, stick, tank).
    "drop": {"pos": (-10.0, 76.0, 24.0), "look": (15.0, 110.0, -700.0), "vfov": 42.0, "yaw": -22.0, "pitch": 16.0, "focus": 0.62},
}

# The airdrop in the "drop" key art (Roblox coordinates; tools/ui/keyart_airdrop.py).
AIRDROP = {
    "sticks": [
        {
            "release0": (400.0, 290.0, -560.0), "dir": (-1.0, 0.0, -0.3), "count": 8, "t": 4.2, "yaw": 20.0,
            "swing": [(6, -4), (-5, 7), (3, 5), (-7, -3), (5, 2), (-3, -6), (8, 1), (0, 0)],
            "jitter": [(4, -9, 10), (-6, 5, -8), (3, -3, 14), (-2, 8, -4), (7, -6, 6), (-5, -5, -12), (2, 6, 5), (0, 0, 0)],
            "transport": {"yaw": 73.3, "bank": -5.0, "pitch": 1.0, "ramp": 1.0, "tag": "Lead"},
        },
    ],
    "transports": [],
    "cargo": [{"kind": "Tank", "pos": (72.0, 80.0, -390.0), "yaw": 30.0, "swing": (4, -3), "chute_yaw0": 20.0}],
    "ground_canopies": [],
}

# Terrain material index (keyart_capture.MATERIALS) -> ENV texture set.
TERRAIN_SETS = ["Sand", "SandCoarse", "Road", "Wash", "Rock", "Sandstone", "Limestone", "Slate"]
LANDSCAPE = ["Mesa", "RearWall", "FlankLeft", "FlankRight", "FarWall", "Butte1", "Butte2", "Butte3", "Butte4"]
# Assets placed from the capture (MeshId -> GLB part), with their alpha mode.
PLACED = {"GroundDressing": True, "GroundStrips": True}
TURRET_YAW_PARTS = {"Mount"}
TURRET_GUN_PARTS = {"Cradle", "Gun", "Belt", "Pod", "Rail", "Missile1", "Missile2"}
EMPLACEMENT_SKIP = {"BeltRound", "EjectCase"}


def arg(name, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            return argv[i + 1]
        return True
    return default


def log(msg):
    print(f"[keyart {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rb(v):
    return Vector((v[0], -v[2], v[1]))


P_RB = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))  # Blender = P_RB @ Roblox


def cam_spec():
    spec = dict(CAMERAS[arg("--cam", "drop")])
    for key in ("pos", "look"):
        if arg(f"--{key}"):
            spec[key] = tuple(float(v) for v in arg(f"--{key}").split(","))
    for key in ("yaw", "pitch", "vfov"):
        if arg(f"--{key}"):
            spec[key] = float(arg(f"--{key}"))
    return spec


def res():
    scale = float(arg("--res", 1.0))
    return int(RES[0] * scale), int(RES[1] * scale)


def place_camera(sc, spec):
    cam = bpy.data.objects.new("KeyCam", bpy.data.cameras.new("KeyCam"))
    cam.data.sensor_fit = "VERTICAL"
    cam.data.angle = math.radians(spec["vfov"])
    cam.data.clip_start = 0.3
    cam.data.clip_end = 6000
    pos, look = rb(spec["pos"]), rb(spec["look"])
    f = (look - pos).normalized()
    r = f.cross(Vector((0, 0, 1))).normalized()
    u = r.cross(f).normalized()
    cam.matrix_world = Matrix.Translation(pos) @ Matrix((r, u, -f)).transposed().to_4x4()
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def gpu(sc):
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except Exception as err:
        log(f"GPU unavailable ({err}); CPU")


def env_sky_module():
    """tools/env/sky.py's helpers without running its main()."""
    path = os.path.join(ROOT, "tools", "env", "sky.py")
    src = open(path).read()
    src = src[: src.rindex("\nmain()")]
    ns = {"__file__": path, "__name__": "env_sky"}
    exec(compile(src, path, "exec"), ns)
    return ns


# ------------------------------------------------------------------ sky pass (CPU, OSL)
def render_sky():
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, ".gitignore"), "w") as f:
        f.write("*\n")
    sky = env_sky_module()
    p = sky["PRESETS"][PRESET]
    sc = sky["scene_setup"](int(arg("--samples", 48)))
    sky["build_world"](sc, p)
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "OPEN_EXR"
    sc.render.image_settings.color_depth = "16"
    sc.render.film_transparent = False
    sky["pano_camera"](sc)
    sky["render_to"](sc, os.path.join(CACHE, "sky_env.exr"), 2048, 1024)
    if arg("--cam") == "none":
        return
    spec = cam_spec()
    place_camera(sc, spec)
    w, h = res()
    sky["render_to"](sc, plate_path(spec, w), w, h)
    log(f"sky plate {os.path.basename(plate_path(spec, w))} {w}x{h}")


def plate_path(spec, w):
    import hashlib

    key = hashlib.sha1(json.dumps([spec["pos"], spec["look"], spec["vfov"]]).encode()).hexdigest()[:8]
    return os.path.join(CACHE, f"sky_plate_{key}_{w}.exr")


# ------------------------------------------------------------------ materials
def img(path, non_color=False):
    im = bpy.data.images.load(path, check_existing=True)
    if non_color:
        im.colorspace_settings.name = "Non-Color"
    return im


def pbr_material(name, color, normal=None, rough=None, metal=None, alpha=False, uv="UVMap"):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img(color)
    nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    if alpha:
        nt.links.new(t.outputs["Alpha"], bsdf.inputs["Alpha"])
    if normal:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = img(normal, True)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.uv_map = uv
        nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if rough:
        tr = nt.nodes.new("ShaderNodeTexImage")
        tr.image = img(rough, True)
        nt.links.new(tr.outputs["Color"], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.9
    if metal:
        tm = nt.nodes.new("ShaderNodeTexImage")
        tm.image = img(metal, True)
        nt.links.new(tm.outputs["Color"], bsdf.inputs["Metallic"])
    return mat


def capture_rev():
    """--rev, else the commit the battlefield capture was taken at (art.json
    `capture_rev`), so the captured mesh ids resolve to the meshes the game
    was running even after an asset is rebuilt; `--rev none` = working tree."""
    rev = arg("--rev")
    if rev is None:
        meta_path = os.path.join(ART, "art.json")
        rev = json.load(open(meta_path)).get("capture_rev") if os.path.exists(meta_path) else None
    return None if rev in (None, "none", True) else rev


def asset_dir(asset):
    """assets/exported/<asset>, or with --rev REV that commit's copy (so the
    meshes match the ids a capture was taken with while an asset is being
    rebuilt in the working tree)."""
    rev = capture_rev()
    if not rev:
        return os.path.join(EXPORTED, asset)
    import subprocess

    out = os.path.join(CACHE, f"rev_{rev}", asset)
    if not os.path.isdir(out):
        names = subprocess.run(["git", "-C", ROOT, "ls-tree", "--name-only", rev, f"assets/exported/{asset}/"], capture_output=True, text=True, check=True).stdout.split()
        if not names:  # not in that commit (a newer asset): the working tree's
            return os.path.join(EXPORTED, asset)
        os.makedirs(out)
        for n in names:
            data = subprocess.run(["git", "-C", ROOT, "show", f"{rev}:{n}"], capture_output=True, check=True).stdout
            with open(os.path.join(out, os.path.basename(n)), "wb") as f:
                f.write(data)
    return out


def asset_maps(asset, group):
    """The full-resolution maps of an asset's texture group; a group shared
    from a trim sheet (manifest `shared_textures`, e.g. HS-6's `airdrop` ->
    TrimAirdrop) resolves to that sheet's maps."""
    base = os.path.join(asset_dir(asset), f"{asset}_{group}_")
    man_path = os.path.join(asset_dir(asset), "manifest.json")
    shared = json.load(open(man_path)).get("shared_textures", {}) if os.path.exists(man_path) else {}
    if group in shared and not os.path.exists(base + "color.png"):
        sheet = shared[group]
        base = os.path.join(asset_dir(sheet), f"{sheet}_sheet_")
    pick = {k: base + f"{k}.png" for k in ("color", "normal", "rough", "metal")}
    return {k: v for k, v in pick.items() if os.path.exists(v)}


def flat_material(name, rgb, glass=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (*[c ** 2.2 for c in rgb], 1)
    b.inputs["Roughness"].default_value = 0.08 if glass else 0.6
    if glass:
        b.inputs["Specular IOR Level"].default_value = 0.9
    return mat


# ------------------------------------------------------------------ terrain
def terrain_textures():
    out = []
    for name in TERRAIN_SETS:
        d = os.path.join(TERRAIN_TEX, name)
        man = json.load(open(os.path.join(d, "manifest.json")))
        out.append((name, man["studs_per_tile"], os.path.join(d, man["files"]["color"]), os.path.join(d, man["files"]["normal"]), os.path.join(d, man["files"]["roughness"])))
    return out


def blur2(a, r=1):
    out = a.copy()
    for axis in (0, 1):
        acc = np.zeros_like(out)
        for d in range(-r, r + 1):
            acc += np.roll(out, d, axis)
        out = acc / (2 * r + 1)
    return out


def build_terrain(sc):
    path = os.path.join(SRC, "keyart_terrain.npz")
    if not os.path.exists(path):
        log("no terrain capture; flat sand stand-in")
        xs = np.arange(-1000, 1001, 8.0)
        zs = np.arange(-1520, 161, 8.0)
        height = np.zeros((len(zs), len(xs)), np.float32)
        mat = np.zeros_like(height, dtype=np.int8)
    else:
        d = np.load(path)
        xs, zs, height, mat = d["xs"].astype(float), d["zs"].astype(float), d["height"], d["mat"]
    nz, nx = height.shape
    hole = np.isnan(height)
    height = np.where(hole, -30.0, height)
    gx, gz = np.meshgrid(xs, zs)
    verts = np.stack([gx, -gz, height], axis=-1).reshape(-1, 3).astype(np.float32)
    idx = np.arange(nz * nx).reshape(nz, nx)
    a, b, c, d_ = idx[:-1, :-1], idx[:-1, 1:], idx[1:, 1:], idx[1:, :-1]
    quads = np.stack([a, d_, c, b], axis=-1).reshape(-1, 4)
    keep = ~(hole[:-1, :-1] | hole[:-1, 1:] | hole[1:, 1:] | hole[1:, :-1]).reshape(-1)
    quads = quads[keep]
    me = bpy.data.meshes.new("Terrain")
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.ravel())
    me.loops.add(len(quads) * 4)
    me.loops.foreach_set("vertex_index", quads.astype(np.int32).ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set("loop_start", np.arange(0, len(quads) * 4, 4, dtype=np.int32))
    me.update()
    # Material weights per vertex (softened across one cell like Roblox's blend).
    w = np.zeros((8, nz, nx), np.float32)
    for i in range(8):
        w[i] = blur2((mat == i).astype(np.float32), 1)
    wa = np.stack([w[0], w[1], w[2], w[3]], axis=-1).reshape(-1, 4)
    wb = np.stack([w[4], w[5], w[6], w[7]], axis=-1).reshape(-1, 4)
    for name, arr in (("wA", wa), ("wB", wb)):
        attr = me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
        attr.data.foreach_set("color", arr.astype(np.float32).ravel())
    uv = me.uv_layers.new(name="UVMap")
    loops_v = np.zeros(len(me.loops), dtype=np.int32)
    me.loops.foreach_get("vertex_index", loops_v)
    uvs = np.stack([verts[loops_v, 0], verts[loops_v, 1]], axis=-1).astype(np.float32)
    uv.data.foreach_set("uv", uvs.ravel())
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new("Terrain", me)
    sc.collection.objects.link(ob)
    ob.data.materials.append(terrain_material())
    log(f"terrain {nx}x{nz}, {len(quads)} quads")
    return ob


def terrain_material():
    mat = bpy.data.materials.new("TerrainBlend")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "UVMap"
    attrs = []
    for name in ("wA", "wB"):
        a = nt.nodes.new("ShaderNodeVertexColor")
        a.layer_name = name
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(a.outputs["Color"], sep.inputs["Color"])
        attrs += [sep.outputs[0], sep.outputs[1], sep.outputs[2]]
        amath = nt.nodes.new("ShaderNodeAttribute")
        amath.attribute_name = name
        attrs.append(amath.outputs["Alpha"])
    # Macro variation so the tiles don't read across the basin.
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 0.004
    noise.inputs["Detail"].default_value = 3
    nt.links.new(uvn.outputs["UV"], noise.inputs["Vector"])
    sums = {"col": None, "nrm": None, "rgh": None, "w": None}

    def acc(key, sock, is_vec):
        prev = sums[key]
        if prev is None:
            sums[key] = sock
            return
        n = nt.nodes.new("ShaderNodeVectorMath" if is_vec else "ShaderNodeMath")
        n.operation = "ADD"
        nt.links.new(prev, n.inputs[0])
        nt.links.new(sock, n.inputs[1])
        sums[key] = n.outputs[0]

    for i, (name, spt, col, nrm, rgh) in enumerate(terrain_textures()):
        mapn = nt.nodes.new("ShaderNodeMapping")
        mapn.inputs["Scale"].default_value = (1 / spt, 1 / spt, 1)
        nt.links.new(uvn.outputs["UV"], mapn.inputs["Vector"])
        maps = []
        for path, nc in ((col, False), (nrm, True), (rgh, True)):
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = img(path, nc)
            t.interpolation = "Cubic"
            nt.links.new(mapn.outputs["Vector"], t.inputs["Vector"])
            maps.append(t.outputs["Color"])
        wsock = attrs[i]
        for key, sock, is_vec in (("col", maps[0], True), ("nrm", maps[1], True)):
            m = nt.nodes.new("ShaderNodeVectorMath")
            m.operation = "SCALE"
            nt.links.new(sock, m.inputs[0])
            nt.links.new(wsock, m.inputs["Scale"])
            acc(key, m.outputs[0], True)
        mr = nt.nodes.new("ShaderNodeMath")
        mr.operation = "MULTIPLY"
        nt.links.new(maps[2], mr.inputs[0])
        nt.links.new(wsock, mr.inputs[1])
        acc("rgh", mr.outputs[0], False)
        acc("w", wsock, False)
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "DIVIDE"
    inv.inputs[0].default_value = 1.0
    wmax = nt.nodes.new("ShaderNodeMath")
    wmax.operation = "MAXIMUM"
    wmax.inputs[1].default_value = 1e-3
    nt.links.new(sums["w"], wmax.inputs[0])
    nt.links.new(wmax.outputs[0], inv.inputs[1])
    outs = {}
    for key in ("col", "nrm"):
        m = nt.nodes.new("ShaderNodeVectorMath")
        m.operation = "SCALE"
        nt.links.new(sums[key], m.inputs[0])
        nt.links.new(inv.outputs[0], m.inputs["Scale"])
        outs[key] = m.outputs[0]
    rr = nt.nodes.new("ShaderNodeMath")
    rr.operation = "MULTIPLY"
    nt.links.new(sums["rgh"], rr.inputs[0])
    nt.links.new(inv.outputs[0], rr.inputs[1])
    # colour * macro variation (0.9..1.1)
    var = nt.nodes.new("ShaderNodeMapRange")
    var.inputs["To Min"].default_value = 0.9
    var.inputs["To Max"].default_value = 1.1
    nt.links.new(noise.outputs["Fac"], var.inputs["Value"])
    cm = nt.nodes.new("ShaderNodeVectorMath")
    cm.operation = "SCALE"
    nt.links.new(outs["col"], cm.inputs[0])
    nt.links.new(var.outputs["Result"], cm.inputs["Scale"])
    nt.links.new(cm.outputs[0], bsdf.inputs["Base Color"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nt.links.new(outs["nrm"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(rr.outputs[0], bsdf.inputs["Roughness"])
    return mat


# ------------------------------------------------------------------ landscape, emplacement
def link_blend(path, pred):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = [n for n in src.objects if pred(n)]
    out = []
    for ob in dst.objects:
        if ob is None:
            continue
        bpy.context.scene.collection.objects.link(ob)
        out.append(ob)
    return out


def build_landscape():
    n = 0
    for name in LANDSCAPE:
        path = os.path.join(ROOT, "assets", "blender", f"Landscape_{name}.blend")
        n += len(link_blend(path, lambda s, name=name: s.startswith(f"{name}_C")))
    log(f"landscape chunks {n}")


def build_emplacement(spec):
    objs = link_blend(os.path.join(ROOT, "assets", "blender", "Emplacement.blend"), lambda s: not s.startswith("Decal") and s not in EMPLACEMENT_SKIP)
    pivot = Matrix.Translation(rb(TURRET_PIVOT))
    yaw = Matrix.Rotation(math.radians(-spec["yaw"]), 4, "Z")  # + yaw turns toward +X (right)
    pitch = Matrix.Rotation(math.radians(spec["pitch"]), 4, "X")
    for ob in objs:
        base = ob.matrix_world.copy()
        if ob.name in TURRET_GUN_PARTS:
            ob.matrix_world = pivot @ yaw @ pitch @ base
        elif ob.name in TURRET_YAW_PARTS:
            ob.matrix_world = pivot @ yaw @ base
        else:
            ob.matrix_world = pivot @ base
    log(f"emplacement {len(objs)} objects")


# ------------------------------------------------------------------ captured placements
def mesh_index():
    """MeshId -> (asset, part) over every exported asset."""
    out = {}
    rev = capture_rev()
    for asset in os.listdir(EXPORTED):
        if rev:
            import subprocess

            r = subprocess.run(["git", "-C", ROOT, "show", f"{rev}:assets/exported/{asset}/roblox_ids.json"], capture_output=True, text=True)
            ids = json.loads(r.stdout) if r.returncode == 0 else {}
        else:
            p = os.path.join(EXPORTED, asset, "roblox_ids.json")
            ids = json.load(open(p)) if os.path.exists(p) else {}
        for part, mid in ids.get("meshes", {}).items():
            out[mid] = (asset, part)
    return out


IMPORTED = {}


def import_asset(asset):
    """Imports an asset GLB once (hidden); returns {part: (mesh, bbox centre, bbox size)}."""
    if asset in IMPORTED:
        return IMPORTED[asset]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(asset_dir(asset), f"{asset}.glb"))
    new = [o for o in bpy.data.objects if o not in before]
    names = [o.name for o in new if o.type != "MESH"]
    manifest = json.load(open(os.path.join(asset_dir(asset), "manifest.json")))
    tex_of = {p["name"]: p.get("tex") for p in manifest.get("parts", [])}
    alpha_of = {p["name"]: bool(p.get("alpha")) for p in manifest.get("parts", [])}
    flat_of = {p["name"]: (p["flat"], p.get("material")) for p in manifest.get("parts", []) if p.get("flat")}
    mats = {}
    parts = {}
    for ob in new:
        if ob.type != "MESH":
            continue
        ob.data.transform(ob.matrix_world)
        ob.matrix_world = Matrix.Identity(4)
        name = ob.name.split(".")[0]
        group = tex_of.get(name) or tex_of.get(ob.data.name) or "main"
        key = (group, alpha_of.get(name, False))
        if name in flat_of:
            rgb, material = flat_of[name]
            key = ("flat_" + name, False)
            mats[key] = flat_material(f"{asset}_{name}", rgb, glass=material == "Glass")
        if key not in mats:
            maps = asset_maps(asset, group)
            if "color" in maps:
                mats[key] = pbr_material(f"{asset}_{group}", maps["color"], maps.get("normal"), maps.get("rough"), maps.get("metal"), alpha=key[1], uv=ob.data.uv_layers[0].name if ob.data.uv_layers else "UVMap")
            else:
                mats[key] = None
        ob.data.materials.clear()
        if mats[key]:
            ob.data.materials.append(mats[key])
        co = np.zeros(len(ob.data.vertices) * 3)
        ob.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        lo, hi = co.min(axis=0), co.max(axis=0)
        parts[name] = (ob.data, Vector((lo + hi) / 2), Vector(hi - lo))
        bpy.data.objects.remove(ob)
    for leftover in [bpy.data.objects.get(n) for n in names]:
        if leftover is not None:
            bpy.data.objects.remove(leftover)
    IMPORTED[asset] = parts
    return parts


BOX_MATS = {}


def add_box(p):
    """Plain Roblox Part (searchlight towers): a box in a matching material."""
    key = p["mat"]
    if key not in BOX_MATS:
        mat = bpy.data.materials.new(f"Part_{key}")
        mat.use_nodes = True
        b = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        b.inputs["Base Color"].default_value = (*[c ** 2.2 for c in p["col"]], 1)
        b.inputs["Metallic"].default_value = 0.6 if key in ("Metal", "DiamondPlate") else 0.0
        b.inputs["Roughness"].default_value = 0.1 if key == "Glass" else 0.55
        BOX_MATS[key] = mat
    me = bpy.data.meshes.new("PartBox")
    h = [v / 2 for v in p["s"]]
    vs = [(x * h[0], y * h[1], z * h[2]) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    vs = [tuple(P_RB @ Vector(v)) for v in vs]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    me.from_pydata(vs, [], faces)
    me.materials.append(BOX_MATS[key])
    cf = p["cf"]
    r_rb = Matrix(((cf[3], cf[4], cf[5]), (cf[6], cf[7], cf[8]), (cf[9], cf[10], cf[11])))
    ob = bpy.data.objects.new(p["n"].split(".")[-1], me)
    ob.matrix_world = Matrix.Translation(rb(cf[:3])) @ (P_RB @ r_rb @ P_RB.transposed()).to_4x4()
    bpy.context.scene.collection.objects.link(ob)


def build_placed():
    path = os.path.join(SRC, "keyart_parts.json")
    if not os.path.exists(path):
        log("no parts capture; skipping dressing/strips/rocks")
        return
    captured = json.load(open(path))
    index = mesh_index()
    loaded = {}
    placed, skipped = 0, {}
    for p in captured:
        if p["c"] == "Part":
            add_box(p)
            placed += 1
            continue
        hit = index.get(p.get("m", ""))
        if not hit:
            skipped[p["n"].split(".")[2] if p["n"].count(".") > 1 else p["n"]] = skipped.get(p["n"], 0) + 1
            continue
        asset, part = hit
        if asset.startswith("Landscape_") or asset == "Emplacement":
            continue
        if asset not in loaded:
            loaded[asset] = import_asset(asset)
        entry = loaded[asset].get(part)
        if entry is None:
            continue
        mesh, centre, size = entry
        cf = p["cf"]
        r_rb = Matrix(((cf[3], cf[4], cf[5]), (cf[6], cf[7], cf[8]), (cf[9], cf[10], cf[11])))
        rot = P_RB @ r_rb @ P_RB.transposed()
        sx, sy, sz = p["s"]  # Roblox part axes
        native = (size.x, size.z, size.y)  # Roblox X, Y, Z extents of the mesh
        scale = Matrix.Diagonal((
            sx / max(native[0], 1e-4),
            sz / max(native[2], 1e-4),
            sy / max(native[1], 1e-4),
            1.0,
        ))
        m = Matrix.Translation(rb(cf[:3])) @ rot.to_4x4() @ scale @ Matrix.Translation(-centre)
        ob = bpy.data.objects.new(part, mesh)
        ob.matrix_world = m
        bpy.context.scene.collection.objects.link(ob)
        placed += 1
    log(f"placed {placed} captured parts from {sorted(loaded)}; unmatched groups: {dict(list(skipped.items())[:12])}")


# ------------------------------------------------------------------ light, world, compositing
def build_world_and_sun(sc):
    sky = env_sky_module()
    p = sky["PRESETS"][PRESET]
    world = bpy.data.worlds.new("KeyWorld")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    env_path = os.path.join(CACHE, "sky_env.exr")
    if os.path.exists(env_path):
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.vector_type = "VECTOR"
        mp.inputs["Rotation"].default_value = (0, 0, math.radians(90))  # pano centre is Roblox -Z (Blender +Y)
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = img(env_path)
        nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = float(arg("--env", 0.4))
    else:
        log("no sky env yet (run --sky); flat stand-in")
        bg.inputs["Color"].default_value = (0.35, 0.4, 0.55, 1)
        bg.inputs["Strength"].default_value = 0.8
    sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", "SUN"))
    sun_dir = rb(p["sun"]).normalized()
    sun.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
    sun.data.energy = float(arg("--sun", 9.0))
    sun.data.angle = math.radians(1.2)
    sun.data.color = (1.0, 0.66, 0.42)
    sc.collection.objects.link(sun)
    sc.world.mist_settings.start = float(arg("--mist-start", 150))
    sc.world.mist_settings.depth = float(arg("--mist-depth", 2400))
    sc.world.mist_settings.falloff = "QUADRATIC"


def build_ground_dust(sc):
    """LOOK-5's low dust layer as a volume: a box over the basin floor whose
    density falls off with height (thickest at the wall feet), lit by the sun."""
    density = float(arg("--dust", 0.006))
    if density <= 0:
        return
    top = float(arg("--dust-top", 80.0))
    me = bpy.data.meshes.new("GroundDust")
    x0, x1, z0, z1 = -1000.0, 1000.0, -1560.0, -120.0
    vs = [(x, -z, y) for x in (x0, x1) for z in (z0, z1) for y in (-12.0, top)]
    me.from_pydata(vs, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
    mat = bpy.data.materials.new("GroundDust")
    mat.use_nodes = True
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    for n in [n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"]:
        nt.nodes.remove(n)
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Color"].default_value = (0.95, 0.62, 0.42, 1)
    vol.inputs["Anisotropy"].default_value = 0.45
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(geo.outputs["Position"], sep.inputs[0])
    rng = nt.nodes.new("ShaderNodeMapRange")  # height -> 1 at the floor .. 0 at the top
    rng.inputs["From Min"].default_value = 0.0
    rng.inputs["From Max"].default_value = top
    rng.inputs["To Min"].default_value = 1.0
    rng.inputs["To Max"].default_value = 0.0
    nt.links.new(sep.outputs["Z"], rng.inputs["Value"])
    sq = nt.nodes.new("ShaderNodeMath")
    sq.operation = "POWER"
    sq.inputs[1].default_value = 2.0
    nt.links.new(rng.outputs["Result"], sq.inputs[0])
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = density
    nt.links.new(sq.outputs[0], mul.inputs[0])
    nt.links.new(mul.outputs[0], vol.inputs["Density"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    me.materials.append(mat)
    ob = bpy.data.objects.new("GroundDust", me)
    sc.collection.objects.link(ob)
    log(f"ground dust volume, density {density}, top {top}")


def compositor(sc, plate_path):
    """Haze from the mist pass over the scene, then the scene over the sky plate."""
    sc.view_layers[0].use_pass_mist = True
    ng = bpy.data.node_groups.new("KeyComp", "CompositorNodeTree")
    sc.compositing_node_group = ng
    ng.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    rl = ng.nodes.new("CompositorNodeRLayers")
    out = ng.nodes.new("NodeGroupOutput")
    fac = ng.nodes.new("ShaderNodeMath")
    fac.operation = "MULTIPLY"
    ng.links.new(rl.outputs["Mist"], fac.inputs[0])
    fac.inputs[1].default_value = float(arg("--haze", 0.18))
    fac2 = ng.nodes.new("ShaderNodeMath")
    fac2.operation = "MULTIPLY"
    ng.links.new(fac.outputs[0], fac2.inputs[0])
    ng.links.new(rl.outputs["Alpha"], fac2.inputs[1])
    mix = ng.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    ng.links.new(fac2.outputs[0], mix.inputs[0])
    ng.links.new(rl.outputs["Image"], mix.inputs[6])
    haze = [float(c) for c in arg("--haze-col", "0.95,0.62,0.44").split(",")]
    mix.inputs[7].default_value = (*haze, 1.0)
    result = mix.outputs[2]
    if plate_path and os.path.exists(plate_path):
        plate = ng.nodes.new("CompositorNodeImage")
        plate.image = img(plate_path)
        over = ng.nodes.new("CompositorNodeAlphaOver")
        ng.links.new(plate.outputs["Image"], over.inputs[0] if over.inputs[0].type == "RGBA" else over.inputs[1])
        # inputs: (Fac?) Background, Foreground - resolve by name
        names = [i.name for i in over.inputs]
        bg_in = over.inputs[names.index("Background")] if "Background" in names else over.inputs[1]
        fg_in = over.inputs[names.index("Foreground")] if "Foreground" in names else over.inputs[2]
        ng.links.new(plate.outputs["Image"], bg_in)
        # restore the scene alpha on the hazed colour
        set_a = ng.nodes.new("CompositorNodeSetAlpha")
        ng.links.new(result, set_a.inputs[0])
        ng.links.new(rl.outputs["Alpha"], set_a.inputs[1])
        ng.links.new(set_a.outputs[0], fg_in)
        result = over.outputs[0]
    # Grade: a touch more saturation (the game's sunset is a strong warm
    # red-orange; the AgX transform mutes it).
    hs = ng.nodes.new("CompositorNodeHueSat")
    ng.links.new(result, hs.inputs["Image"])
    hs.inputs["Saturation"].default_value = float(arg("--sat", 1.1))
    result = hs.outputs[0]
    glare = ng.nodes.new("CompositorNodeGlare")
    try:
        glare.glare_type = "BLOOM"
    except Exception:
        pass
    ng.links.new(result, glare.inputs[0])
    ng.links.new(glare.outputs[0], out.inputs[0])


# ------------------------------------------------------------------ output
def load_png(path):
    im = bpy.data.images.load(path, check_existing=False)
    im.colorspace_settings.name = "Non-Color"
    w, h = im.size
    px = np.array(im.pixels[:], dtype=np.float64).reshape(h, w, 4)[::-1]
    bpy.data.images.remove(im)
    return px


def resample_axis(a, n, axis):
    """Area-average resample of axis to n samples."""
    m = a.shape[axis]
    edges = np.linspace(0, m, n + 1)
    c = np.cumsum(np.concatenate([np.zeros_like(np.take(a, [0], axis=axis)), a], axis=axis), axis=axis)

    def at(x):
        i = np.clip(np.floor(x).astype(int), 0, m - 1)
        f = x - i
        lo = np.take(c, i, axis=axis)
        hi = np.take(c, i + 1, axis=axis)
        shape = [1] * a.ndim
        shape[axis] = -1
        return lo + (hi - lo) * f.reshape(shape)

    return (at(edges[1:]) - at(edges[:-1])) / (m / n)


def write_png(path, rgba):
    h, w, _ = rgba.shape
    im = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    im.colorspace_settings.name = "Non-Color"
    im.pixels = np.clip(rgba[::-1], 0, 1).astype(np.float32).ravel()
    im.filepath_raw = path
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def finish_texture(render_path, spec):
    px = load_png(render_path)
    rgb = px[..., :3]
    squeezed = resample_axis(resample_axis(rgb, OUT_SIZE, 1), OUT_SIZE, 0)
    out = np.ones((OUT_SIZE, OUT_SIZE, 4))
    out[..., :3] = squeezed
    write_png(os.path.join(ART, "title_keyart.png"), out)
    meta_path = os.path.join(ART, "art.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    meta["keyart"] = {"size": [OUT_SIZE, OUT_SIZE], "aspect": round(RES[0] / RES[1], 4), "focus_x": spec["focus"], "camera": arg("--cam", "drop")}
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=1, sort_keys=True)
        f.write("\n")
    log("wrote title_keyart.png")


def main():
    if arg("--sky"):
        render_sky()
        return
    t0 = time.time()
    spec = cam_spec()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    gpu(sc)
    draft = bool(arg("--draft"))
    sc.cycles.samples = int(arg("--samples", 24 if draft else 256))
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.film_transparent = True
    w, h = res()
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.view_settings.view_transform = "AgX"
    want = str(arg("--view-look", "None")).replace("_", " ")  # e.g. AgX_-_Punchy
    try:  # a dynamic enum: RNA lists no items, so try the assignment
        sc.view_settings.look = want
    except TypeError:
        log(f"no look {want!r}; None")
        sc.view_settings.look = "None"
    sc.view_settings.exposure = float(arg("--exposure", 0.2))
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    place_camera(sc, spec)
    build_world_and_sun(sc)
    build_terrain(sc)
    build_landscape()
    build_emplacement(spec)
    build_placed()
    if arg("--cam", "drop") == "drop" and not arg("--no-airdrop"):
        sys.path.insert(0, HERE)
        import keyart_airdrop

        keyart_airdrop.build(AIRDROP, import_asset, pbr_material, EXPORTED, log)
    build_ground_dust(sc)
    plate = plate_path(spec, w)
    if not os.path.exists(plate):
        log(f"no sky plate {os.path.basename(plate)}; the env shows through")
        sc.render.film_transparent = False
        plate = None
    compositor(sc, plate)
    os.makedirs(PREVIEWS, exist_ok=True)
    tag = "_draft" if draft else ""
    path = os.path.join(PREVIEWS, f"keyart_{arg('--cam', 'drop')}{tag}{arg('--tag', '')}.png")
    sc.render.filepath = path
    if arg("--save"):
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "assets", "blender", "TitleKeyArt.blend"), relative_remap=True)
    bpy.ops.render.render(write_still=True)
    log(f"rendered {path} in {time.time() - t0:.0f}s")
    if not draft and arg("--texture"):
        finish_texture(path, spec)


main()
