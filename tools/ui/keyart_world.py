"""Scene building blocks for the LOOK-4 title key art (tools/ui/keyart_scene.py):
paths and CLI helpers, materials (full-resolution PBR maps, trim sheets via
`shared_textures`, flat parts), the captured terrain with ENV's
MaterialVariant textures, the landscape meshes, the posed emplacement and
every part the game placed (resolved against the capture's commit).
Roblox (x, y, z) = Blender (x, -z, y); 1 Blender unit = 1 stud.
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
