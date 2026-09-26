"""Bake and export the landscape meshes (Blender 5.2, headless).

    tools/blender-lock.sh acquire env
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        -P tools/env/landscape/bake.py -- Mesa [RearWall ...] [--samples 32]
    tools/blender-lock.sh release env

For each piece (geometry from shape.py, assets/source/landscape/build/):
  1. one low-poly object per chunk, smooth-by-angle normals, UVs from smart
     projection with every island scaled to the texel density its nearest
     game camera needs (pieces.needed_density), packed into 1024^2;
  2. Cycles selected-to-active bakes from the high-poly (whose material adds
     world-space rock bump from CC0 height maps): tangent normal map, and
     position / normal / AO / pointiness / bevel-edge maps;
  3. texture.composite() turns those into the colour and roughness maps;
  4. exports assets/exported/Landscape_<Piece>/ (GLB, PNGs, manifest.json in
     the tools/assets pipeline format) and assets/blender/Landscape_<Piece>.blend.
"""
import json
import math
import os
import sys
import time

import bpy
import bmesh
import numpy as np
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)

import pieces as P  # noqa: E402
import texture  # noqa: E402

BUILD = os.path.join(ROOT, "assets", "source", "landscape", "build")
TEX = 1024
# Normal-map size per piece: the mesa is seen up close (title, defeat
# cameras); the walls and buttes only from 300+ studs.
NORMAL_TEX = {"Mesa": 1024}
NORMAL_TEX_DEFAULT = 512
SMOOTH_ANGLE = math.radians(55)
NEIGHBOURS = {  # pieces that shade (AO) each other
    "Mesa": ["RearWall"],
    "RearWall": ["Mesa", "FlankLeft", "FlankRight"],
    "FlankLeft": ["RearWall", "FarWall"],
    "FlankRight": ["RearWall", "FarWall"],
    "FarWall": ["FlankLeft", "FlankRight", "Butte3"],
}


def log(msg):
    print(f"[land {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def argv():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default):
    a = argv()
    return type(default)(a[a.index(name) + 1]) if name in a else default


def to_blender(v):
    """Roblox (x, y, z) -> Blender (x, -z, y)."""
    return np.stack([v[:, 0], -v[:, 2], v[:, 1]], axis=1)


def to_roblox(v):
    return np.stack([v[:, 0], v[:, 2], -v[:, 1]], axis=1)


def make_mesh(name, v, f):
    me = bpy.data.meshes.new(name)
    bv = to_blender(v).astype(np.float32)
    me.vertices.add(len(bv))
    me.vertices.foreach_set("co", bv.ravel())
    me.loops.add(len(f) * 3)
    me.loops.foreach_set("vertex_index", f.astype(np.int32).ravel())
    me.polygons.add(len(f))
    me.polygons.foreach_set("loop_start", np.arange(0, len(f) * 3, 3, dtype=np.int32))
    me.update()
    me.validate()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def compact(v, f):
    used = np.unique(f)
    remap = -np.ones(len(v), dtype=np.int64)
    remap[used] = np.arange(len(used))
    return v[used], remap[f]


def setup():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
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
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.light_settings.distance = 14.0  # AO reach (studs)


def img_node(nt, path, colorspace="Non-Color"):
    n = nt.nodes.new("ShaderNodeTexImage")
    n.image = bpy.data.images.load(path, check_existing=True)
    n.image.colorspace_settings.name = colorspace
    n.projection = "BOX"
    n.projection_blend = 0.3
    return n


def high_material():
    """High-poly shading: world-space rock bump (box-projected CC0 height
    maps at two scales) that the normal bake carries into the game mesh."""
    mat = bpy.data.materials.new("HighRock")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    coord = nt.nodes.new("ShaderNodeTexCoord")
    layers = []
    for asset, scale, weight in (("cliff_side", 26.0, 0.5), ("rock_face_03", 15.0, 0.3), ("cliff_side", 7.5, 0.2)):
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (1 / scale, 1 / scale, 1 / scale)
        nt.links.new(coord.outputs["Object"], mp.inputs["Vector"])
        tex = img_node(nt, os.path.join(texture.CC0, asset, "disp.jpg"))
        nt.links.new(mp.outputs["Vector"], tex.inputs["Vector"])
        mul = nt.nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = weight * scale / 26.0  # relief scales with the tile size
        nt.links.new(tex.outputs["Color"], mul.inputs[0])
        layers.append(mul)
    add1 = nt.nodes.new("ShaderNodeMath")
    add1.operation = "ADD"
    nt.links.new(layers[0].outputs[0], add1.inputs[0])
    nt.links.new(layers[1].outputs[0], add1.inputs[1])
    add2 = nt.nodes.new("ShaderNodeMath")
    add2.operation = "ADD"
    nt.links.new(add1.outputs[0], add2.inputs[0])
    nt.links.new(layers[2].outputs[0], add2.inputs[1])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.85
    bump.inputs["Distance"].default_value = 1.6
    nt.links.new(add2.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    # Emission outputs used by the aux bakes (switched in per bake).
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    bev = nt.nodes.new("ShaderNodeBevel")
    bev.inputs["Radius"].default_value = 0.9
    bev.samples = 8
    dot = nt.nodes.new("ShaderNodeVectorMath")
    dot.operation = "DOT_PRODUCT"
    nt.links.new(bev.outputs["Normal"], dot.inputs[0])
    nt.links.new(geo.outputs["Normal"], dot.inputs[1])
    edge = nt.nodes.new("ShaderNodeMath")
    edge.operation = "SUBTRACT"
    edge.inputs[0].default_value = 1.0
    nt.links.new(dot.outputs["Value"], edge.inputs[1])
    curv = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(geo.outputs["Pointiness"], curv.inputs["X"])
    nt.links.new(edge.outputs[0], curv.inputs["Y"])
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.name = "AuxEmit"
    mat["sources"] = {}
    return mat, {"position": geo.outputs["Position"], "normal": geo.outputs["Normal"], "curv": curv.outputs["Vector"]}, emit, bsdf


def island_scale(ob, face_density):
    """Scale each UV island by the density its faces need (relative), so the
    later pack keeps near surfaces sharper than far ones."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.active
    bm.faces.ensure_lookup_table()
    parent = list(range(len(bm.faces)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for e in bm.edges:
        lf = e.link_faces
        if len(lf) != 2:
            continue
        f0, f1 = lf
        same = True
        for vert in e.verts:
            u0 = next(l[uv].uv for l in f0.loops if l.vert == vert)
            u1 = next(l[uv].uv for l in f1.loops if l.vert == vert)
            if (u0 - u1).length > 1e-5:
                same = False
                break
        if same:
            a, b = find(f0.index), find(f1.index)
            if a != b:
                parent[a] = b
    groups = {}
    for f in bm.faces:
        groups.setdefault(find(f.index), []).append(f)
    mean = float(np.mean(face_density))
    for faces in groups.values():
        d = float(np.mean([face_density[f.index] for f in faces])) / mean
        loops = [l for f in faces for l in f.loops]
        cu = sum((l[uv].uv for l in loops), start=loops[0][uv].uv * 0) / len(loops)
        for l in loops:
            l[uv].uv = cu + (l[uv].uv - cu) * d
    bm.to_mesh(me)
    bm.free()
    return len(groups)


def unwrap(ob, face_density):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.average_islands_scale()
    bpy.ops.object.mode_set(mode="OBJECT")
    n = island_scale(ob, face_density)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin=0.004, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    return n


def smooth_normals(ob):
    with bpy.context.temp_override(object=ob, selected_editable_objects=[ob], active_object=ob):
        try:
            bpy.ops.object.shade_smooth_by_angle(angle=SMOOTH_ANGLE)
        except Exception:
            bpy.ops.object.shade_smooth()


def bake(target, high, mat, kind, img, emit=None, bsdf=None, socket=None, samples=1):
    sc = bpy.context.scene
    sc.cycles.samples = samples
    tnt = target.active_material.node_tree
    node = tnt.nodes.new("ShaderNodeTexImage")
    node.image = img
    for n in tnt.nodes:
        n.select = False
    node.select = True
    tnt.nodes.active = node
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    if socket is not None:
        nt.links.new(socket, emit.inputs["Color"])
        nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
    bk = sc.render.bake
    bk.use_selected_to_active = True
    bk.cage_extrusion = 1.6
    bk.max_ray_distance = 4.0
    bk.margin = 6
    bk.margin_type = "EXTEND"
    bk.use_clear = True
    bpy.ops.object.select_all(action="DESELECT")
    high.select_set(True)
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    if kind == "NORMAL":
        bk.normal_space = "TANGENT"
    bpy.ops.object.bake(type=kind)
    if socket is not None:
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tnt.nodes.remove(node)


def pixels(img, channels):
    a = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)[:, :, :channels]


def save_png(path, rgb, mode="RGB"):
    import OpenImageIO as oiio

    h, w = rgb.shape[:2]
    ch = rgb.shape[2] if rgb.ndim == 3 else 1
    spec = oiio.ImageSpec(w, h, ch, oiio.UINT8)
    buf = oiio.ImageBuf(spec)
    data = np.clip(np.round(np.flipud(rgb.reshape(h, w, ch)) * 255), 0, 255).astype(np.uint8)
    buf.set_pixels(oiio.ROI(0, w, 0, h, 0, 1, 0, ch), data)
    buf.write(path)


def resize(a, size):
    import OpenImageIO as oiio

    h, w = a.shape[:2]
    ch = a.shape[2] if a.ndim == 3 else 1
    buf = oiio.ImageBuf(oiio.ImageSpec(w, h, ch, oiio.FLOAT))
    buf.set_pixels(oiio.ROI(0, w, 0, h, 0, 1, 0, ch), a.reshape(h, w, ch).astype(np.float32))
    out = oiio.ImageBufAlgo.resize(buf, roi=oiio.ROI(0, size, 0, size, 0, 1, 0, ch))
    return out.get_pixels(oiio.FLOAT).reshape(size, size, ch)


def build_piece(name, samples):
    t0 = time.time()
    setup()
    d = np.load(os.path.join(BUILD, f"{name}.npz"))
    meta = json.load(open(os.path.join(BUILD, f"{name}.json")))
    piece = P.PIECES[name]
    high = make_mesh(f"{name}_high", d["high_v"].astype(np.float64), d["high_f"])
    high.data.shade_smooth()
    mat, sockets, emit, bsdf = high_material()
    high.data.materials.append(mat)
    for other in NEIGHBOURS.get(name, []):
        path = os.path.join(BUILD, f"{other}.npz")
        if os.path.exists(path):
            o = np.load(path)
            make_mesh(f"occ_{other}", o["low_v"].astype(np.float64), o["low_f"])
    floor = make_mesh("occ_floor", np.array([[-1200, -0.3, -1700], [1200, -0.3, -1700], [1200, -0.3, 600], [-1200, -0.3, 600]], float),
                      np.array([[0, 2, 1], [0, 3, 2]]))
    floor.hide_select = False
    out_dir = os.path.join(ROOT, "assets", "exported", f"Landscape_{name}")
    os.makedirs(out_dir, exist_ok=True)
    aux_dir = os.path.join(BUILD, "aux")
    os.makedirs(aux_dir, exist_ok=True)
    lv, lf, chunk, fd = d["low_v"].astype(np.float64), d["low_f"], d["chunk"], d["face_density"]
    parts, textures, density = [], {}, {}
    chunks = []
    for c in range(int(chunk.max()) + 1):
        sel = chunk == c
        v, f = compact(lv, lf[sel])
        cname = f"{name}_C{c:02d}"
        ob = make_mesh(cname, v, f)
        smooth_normals(ob)
        tm = bpy.data.materials.new(f"Bake_{cname}")
        tm.use_nodes = True
        ob.data.materials.append(tm)
        islands = unwrap(ob, fd[sel])
        chunks.append((ob, cname, fd[sel]))
        log(f"{cname}: {int(sel.sum())} tris, {islands} islands")
    for ob, cname, dens in chunks:
        imgs = {}
        for key, kind, socket, spp, color in (
            ("normal", "NORMAL", None, 4, False),
            ("position", "EMIT", "position", 1, True),
            ("wnormal", "EMIT", "normal", 1, True),
            ("curv", "EMIT", "curv", 4, True),
            ("ao", "AO", None, samples, True),
        ):
            img = bpy.data.images.new(f"{cname}_{key}", TEX, TEX, alpha=True, float_buffer=color)
            img.colorspace_settings.name = "Non-Color"
            img.generated_color = (0, 0, 0, 0) if color else (0.5, 0.5, 1.0, 1.0)
            bake(ob, high, mat, kind, img, emit, bsdf, sockets.get(socket) if socket else None, spp)
            imgs[key] = img
        pos = pixels(imgs["position"], 4)
        valid = pos[:, :, 3] > 0.5
        Pw = to_roblox(pos[:, :, :3][valid].astype(np.float64))
        Nw = to_roblox(pixels(imgs["wnormal"], 3)[valid].astype(np.float64))
        ao = pixels(imgs["ao"], 1)[:, :, 0][valid].astype(np.float64)
        curv = pixels(imgs["curv"], 3)[valid].astype(np.float64)
        col, _rough = texture.composite(Pw, Nw, ao, curv[:, 0], curv[:, 1])
        colour = np.zeros((TEX, TEX, 3))
        colour[valid] = col
        # Fill the gutter between islands with the nearest island colour.
        colour = dilate(colour, valid)
        normal = pixels(imgs["normal"], 3)
        ntex = NORMAL_TEX.get(name, NORMAL_TEX_DEFAULT)
        if ntex != TEX:
            n = resize(normal, ntex) * 2.0 - 1.0
            n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-6)
            normal = n * 0.5 + 0.5
        grp = cname[len(name) + 1:].lower()
        # No roughness map: Roblox allocates a full-size internal texture for
        # it (measured ~2.4 MB per chunk) and dry rock is uniformly matte.
        files = {
            "color": f"Landscape_{name}_{grp}_color.png",
            "normal": f"Landscape_{name}_{grp}_normal.png",
        }
        stale = os.path.join(out_dir, f"Landscape_{name}_{grp}_rough.png")
        if os.path.exists(stale):
            os.remove(stale)
        save_png(os.path.join(out_dir, files["color"]), colour)
        save_png(os.path.join(out_dir, files["normal"]), normal)
        np.savez_compressed(os.path.join(aux_dir, f"{cname}.npz"), pos=pos.astype(np.float32), ao=pixels(imgs["ao"], 1).astype(np.float16),
                            curv=pixels(imgs["curv"], 2).astype(np.float16), wn=pixels(imgs["wnormal"], 3).astype(np.float16))
        textures[grp] = files
        area = sum(p.area for p in ob.data.polygons)
        uv_area = uv_coverage(ob)
        density[grp] = round(math.sqrt(uv_area * TEX * TEX / max(area, 1e-6)), 2)
        # Show the baked result on the chunk (for previews and the .blend).
        ob.data.materials.clear()
        ob.data.materials.append(baked_material(cname, imgs["normal"], out_dir, files))
        for img in imgs.values():
            if img.name.endswith(("_position", "_wnormal", "_curv", "_ao")):
                bpy.data.images.remove(img)
        log(f"{cname}: baked ({density[grp]} px/stud mean, {time.time() - t0:.0f}s)")
    # Export GLB (chunks only) and manifest.
    for o in list(bpy.data.objects):
        if o.name.startswith(("occ_", f"{name}_high")):
            bpy.data.objects.remove(o, do_unlink=True)
    objs = [ob for ob, _, _ in chunks]
    glb = os.path.join(out_dir, f"Landscape_{name}.glb")
    export_glb(objs, glb)
    for ob, cname, _ in chunks:
        bv = np.array([v.co[:] for v in ob.data.vertices])
        rv = to_roblox(bv)
        lo, hi = rv.min(axis=0), rv.max(axis=0)
        grp = cname[len(name) + 1:].lower()
        parts.append({
            "name": cname, "path": "", "center": [round(float(x), 4) for x in (lo + hi) / 2],
            "size": [round(float(x), 4) for x in hi - lo], "tex": grp,
            "tris": len(ob.data.polygons), "query": False, "collide": False, "shadow": True,
            "material": piece.material,
        })
    manifest = {
        "name": f"Landscape_{name}", "primary": None, "pivots": {"": [0.0, 0.0, 0.0]}, "parts": parts,
        "attachments": [], "markers": [], "textures": textures, "texel_density": density,
        "previews": [], "triangles": sum(p["tris"] for p in parts),
        "meta": {"kit": "landscape", "no_primary": True, "high_tris": meta["high_tris"]},
    }
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    os.makedirs(os.path.join(ROOT, "assets", "blender"), exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "assets", "blender", f"Landscape_{name}.blend"), compress=True, relative_remap=True)
    log(f"{name}: {len(parts)} chunks, {manifest['triangles']} tris, density {density}, {time.time() - t0:.0f}s")


def dilate(a, valid, steps=24):
    """Push island colours outward into the empty gutter (mip bleeding)."""
    a = a.copy()
    filled = valid.copy()
    for _ in range(steps):
        if filled.all():
            break
        acc = np.zeros_like(a)
        cnt = np.zeros(filled.shape)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh = np.roll(np.roll(filled, dy, 0), dx, 1)
            acc += np.where(sh[:, :, None], np.roll(np.roll(a, dy, 0), dx, 1), 0)
            cnt += sh
        grow = (~filled) & (cnt > 0)
        a[grow] = acc[grow] / cnt[grow][:, None]
        filled |= grow
    if not filled.all():
        a[~filled] = a[filled].mean(axis=0)
    return a


def uv_coverage(ob):
    me = ob.data
    uv = me.uv_layers.active.data
    total = 0.0
    for p in me.polygons:
        pts = [uv[i].uv for i in p.loop_indices]
        for i in range(1, len(pts) - 1):
            a, b, c = pts[0], pts[i], pts[i + 1]
            total += abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) / 2
    return total


def baked_material(cname, normal_img, out_dir, files):
    mat = bpy.data.materials.new(f"Baked_{cname}")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    col = nt.nodes.new("ShaderNodeTexImage")
    col.image = bpy.data.images.load(os.path.join(out_dir, files["color"]))
    nt.links.new(col.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.92
    nrm = nt.nodes.new("ShaderNodeTexImage")
    nrm.image = bpy.data.images.load(os.path.join(out_dir, files["normal"]))
    nrm.image.colorspace_settings.name = "Non-Color"
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nrm.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def export_glb(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    # Roblox's glTF importer turns assets 180 degrees about up; pre-rotate so
    # Blender +Y ends up as Roblox -Z (same as tools/assets/rmh/pipeline.py).
    turn = Matrix.Rotation(math.pi, 4, "Z")
    for o in objs:
        o.data.transform(turn)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=False,
                              export_materials="NONE", export_texcoords=True, export_normals=True, export_yup=True)
    for o in objs:
        o.data.transform(turn.inverted())


def main():
    names = [a for a in argv() if not a.startswith("--") and a in P.PIECES]
    samples = opt("--samples", 32)
    for name in names:
        build_piece(name, samples)


main()
