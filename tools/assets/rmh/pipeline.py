"""Finish an Asset: UV atlas per texture group, bake PBR maps, render
previews, export a GLB and write the manifest consumed by make_rbxmx.py.

Outputs (NAME = asset name):
    assets/blender/NAME.blend
    assets/exported/NAME/NAME.glb
    assets/exported/NAME/NAME_<group>_{color,normal,rough,metal}.png
    assets/exported/NAME/manifest.json
    assets/previews/NAME.png, NAME_rear.png
"""
import json
import math
import os
import time
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[3]
CHANNELS = ("color", "rough", "metal", "normal")
_BSDF_INPUT = {"color": "Base Color", "rough": "Roughness", "metal": "Metallic"}


def rb(v):
    """Blender (x, y, z) -> Roblox (x, z, -y)."""
    return [round(v[0], 4), round(v[2], 4), round(-v[1], 4)]


def rb_size(v):
    return [round(v[0], 4), round(v[2], 4), round(v[1], 4)]


def log(msg):
    print(f"[rmh {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def _setup_cycles(samples):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        scene.cycles.device = "GPU"
    except Exception as err:  # CPU fallback is fine, just slower
        log(f"GPU unavailable ({err}); using CPU")
    scene.cycles.samples = samples


def _select(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def _unwrap(objs, margin):
    _select(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def _new_image(name, size, channel):
    img = bpy.data.images.new(name, size, size, alpha=False)
    if channel != "color":
        img.colorspace_settings.name = "Non-Color"
    if channel == "normal":
        img.generated_color = (0.5, 0.5, 1.0, 1.0)
    return img


def _group_materials(objs):
    seen = []
    for o in objs:
        for slot in o.material_slots:
            if slot.material and slot.material not in seen:
                seen.append(slot.material)
    return seen


def _bake_channel(objs, mats, img, channel):
    temp = []
    for mat in mats:
        nt = mat.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        for n in nt.nodes:
            n.select = False
        node.select = True
        nt.nodes.active = node
        temp.append((mat, node, None, None))
        if channel == "normal":
            continue
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output)
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        prev = out.inputs["Surface"].links[0].from_socket if out.inputs["Surface"].is_linked else None
        emit = nt.nodes.new("ShaderNodeEmission")
        src = bsdf.inputs[_BSDF_INPUT[channel]]
        if src.is_linked:
            nt.links.new(src.links[0].from_socket, emit.inputs["Color"])
        else:
            v = src.default_value
            emit.inputs["Color"].default_value = tuple(v) if channel == "color" else (v, v, v, 1.0)
        nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])
        temp[-1] = (mat, node, emit, (out, prev))
    _select(objs)
    bake = bpy.context.scene.render.bake
    bake.margin = 8
    bake.margin_type = "EXTEND"
    bake.use_clear = True
    bake.use_selected_to_active = False
    if channel == "normal":
        bake.normal_space = "TANGENT"
        bpy.ops.object.bake(type="NORMAL")
    else:
        bpy.ops.object.bake(type="EMIT")
    for mat, node, emit, restore in temp:
        nt = mat.node_tree
        nt.nodes.remove(node)
        if emit is not None:
            nt.nodes.remove(emit)
            out, prev = restore
            if prev is not None:
                nt.links.new(prev, out.inputs["Surface"])


def _baked_material(name, imgs):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")

    def tex(ch):
        n = nt.nodes.new("ShaderNodeTexImage")
        n.image = imgs[ch]
        return n

    nt.links.new(tex("color").outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex("rough").outputs["Color"], bsdf.inputs["Roughness"])
    nt.links.new(tex("metal").outputs["Color"], bsdf.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tex("normal").outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _neon_material(color):
    mat = bpy.data.materials.new("Neon")
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    c = tuple(color) + (1.0,)
    bsdf.inputs["Base Color"].default_value = c
    bsdf.inputs["Emission Color"].default_value = c
    bsdf.inputs["Emission Strength"].default_value = 4.0
    return mat


def _save_png(img, path, grayscale=False):
    settings = bpy.context.scene.render.image_settings
    settings.file_format = "PNG"
    settings.color_mode = "BW" if grayscale else "RGB"
    settings.color_depth = "8"
    settings.compression = 100
    if grayscale:
        img.save_render(str(path), scene=bpy.context.scene)
        img.filepath_raw = str(path)
    else:
        img.filepath_raw = str(path)
        img.file_format = "PNG"
        img.save()


def bake_groups(asset, out_dir, samples):
    groups = {}
    for o in asset.objects:
        if o.get("rmh_neon") is not None or o.get("rmh_invisible"):
            continue
        groups.setdefault(o["rmh_tex"], []).append(o)
    textures = {}
    _setup_cycles(samples)
    for group, objs in groups.items():
        size = asset.tex_size.get(group, asset.tex_size["main"])
        log(f"unwrap group {group} ({len(objs)} parts, {size}px)")
        _unwrap(objs, margin=6.0 / size)
        mats = _group_materials(objs)
        imgs = {}
        files = {}
        for ch in CHANNELS:
            t0 = time.time()
            img = _new_image(f"{asset.name}_{group}_{ch}", size, ch)
            _bake_channel(objs, mats, img, ch)
            path = out_dir / f"{asset.name}_{group}_{ch}.png"
            _save_png(img, path, grayscale=ch in ("rough", "metal"))
            imgs[ch] = img
            files[ch] = path.name
            log(f"  baked {ch} in {time.time() - t0:.1f}s")
        textures[group] = {"files": files, "images": imgs, "objects": objs}
    return textures


def _bounds(objs):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for o in objs:
        for v in o.data.vertices:
            co = o.matrix_world @ v.co
            lo = Vector(map(min, lo, co))
            hi = Vector(map(max, hi, co))
    return lo, hi


def render_previews(asset, views, samples=96):
    scene = bpy.context.scene
    _setup_cycles(samples)
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1024, 768
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.compression = 100
    objs = [o for o in asset.objects if not o.get("rmh_invisible")]
    lo, hi = _bounds(objs)
    center = (lo + hi) / 2
    radius = (hi - lo).length / 2

    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.42, 0.5, 0.62, 1.0)
    bg.inputs["Strength"].default_value = 0.8
    scene.world = world

    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 4.5
    sun_data.angle = math.radians(3)
    sun_data.color = (1.0, 0.93, 0.82)
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(48), 0, math.radians(35))
    scene.collection.objects.link(sun)

    bpy.ops.mesh.primitive_plane_add(size=radius * 12, location=(center.x, center.y, lo.z - 0.02))
    ground = bpy.context.active_object
    gm = bpy.data.materials.new("Ground")
    gm.use_nodes = True
    gb = next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    gb.inputs["Base Color"].default_value = (0.36, 0.2, 0.12, 1.0)
    gb.inputs["Roughness"].default_value = 1.0
    ground.data.materials.append(gm)
    if asset.meta.get("no_ground"):
        ground.hide_render = True

    cam_data = bpy.data.cameras.new("Cam")
    cam_data.lens = 50
    cam_data.clip_end = max(1000.0, radius * 40)
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    fov = 2 * math.atan(18 / cam_data.lens)
    outputs = []
    for view in views:
        label, direction = view[0], view[1]
        c, rad = center, radius
        if len(view) > 2 and view[2]:
            flo, fhi = _bounds([o for o in objs if o.name in view[2]])
            c, rad = (flo + fhi) / 2, (fhi - flo).length / 2
        d = Vector(direction).normalized()
        dist = rad / math.sin(fov / 2) * 1.05
        cam.location = c + d * dist
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        path = ROOT / "assets" / "previews" / f"{asset.name}{label}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        outputs.append(str(path.relative_to(ROOT)))
        log(f"preview {path.name}")
    for o in (sun, ground, cam):
        bpy.data.objects.remove(o)
    return outputs


def export_glb(asset, out_dir):
    meshes = [o for o in asset.objects if not o.get("rmh_invisible")]
    _select(meshes)
    path = out_dir / f"{asset.name}.glb"
    # Roblox's glTF importer turns assets 180 degrees about up (glTF +Z is
    # the asset front). Pre-rotate so Blender +Y ends up as Roblox -Z and the
    # manifest mapping rb() = (x, z, -y) holds for geometry too.
    turn = Matrix.Rotation(math.pi, 4, "Z")
    for o in meshes:
        o.data.transform(turn)
    bpy.ops.export_scene.gltf(
        filepath=str(path),
        export_format="GLB",
        use_selection=True,
        export_apply=False,
        export_materials="NONE",
        export_texcoords=True,
        export_normals=True,
        export_yup=True,
    )
    for o in meshes:
        o.data.transform(turn.inverted())
    return path


def write_manifest(asset, out_dir, textures, previews):
    parts = []
    for o in asset.objects:
        lo, hi = _bounds([o])
        center = (lo + hi) / 2
        entry = {
            "name": o.name,
            "path": o["rmh_path"],
            "center": rb(center),
            "size": rb_size(hi - lo),
            "tex": None if (o.get("rmh_neon") is not None or o.get("rmh_invisible")) else o["rmh_tex"],
            "tris": sum(len(p.vertices) - 2 for p in o.data.polygons),
        }
        for key in ("query", "collide", "neon", "material", "transparency", "shadow", "invisible", "pivot_offset", "fidelity"):
            if o.get("rmh_" + key) is not None:
                v = o["rmh_" + key]
                entry[key] = list(v) if hasattr(v, "__len__") and not isinstance(v, str) else v
        if entry.get("pivot_offset") is not None:
            entry["pivot_offset"] = rb(Vector(entry["pivot_offset"]))
        parts.append(entry)

    def axis(a):
        return rb(Vector(a if a is not None else (0, 1, 0)).normalized())

    manifest = {
        "name": asset.name,
        "primary": asset.primary,
        "pivots": {k: rb(v) for k, v in asset.pivots.items()},
        "parts": parts,
        "attachments": [{"name": a["name"], "part": a["part"], "pos": rb(a["pos"]), "axis": axis(a["axis"])} for a in asset.attachments],
        "markers": [{"name": m["name"], "path": m["path"], "pos": rb(m["pos"]), "size": rb_size(Vector(m["size"])), "axis": axis(m["axis"])} for m in asset.markers],
        "textures": {g: t["files"] for g, t in textures.items()},
        "previews": previews,
        "triangles": sum(p["tris"] for p in parts),
        "meta": asset.meta,
    }
    with open(out_dir / "manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=1)
    return manifest


def finish(asset, samples=24, preview_samples=96, views=None, preview=True):
    t0 = time.time()
    out_dir = ROOT / "assets" / "exported" / asset.name
    out_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "assets" / "blender").mkdir(parents=True, exist_ok=True)
    (ROOT / "assets" / "previews").mkdir(parents=True, exist_ok=True)
    asset.build_objects()
    textures = bake_groups(asset, out_dir, samples)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "assets" / "blender" / f"{asset.name}.blend"), compress=True, relative_remap=True)
    for group, t in textures.items():
        mat = _baked_material(f"Baked_{group}", t["images"])
        for o in t["objects"]:
            for slot in o.material_slots:
                slot.material = mat
    for o in asset.objects:
        if o.get("rmh_neon") is not None:
            o.data.materials.clear()
            o.data.materials.append(_neon_material(o["rmh_neon"]))
        if o.get("rmh_invisible"):
            o.hide_render = True
    previews = []
    if preview:
        views = views or [("", (1.0, 1.3, 0.62)), ("_rear", (-1.1, -1.2, 0.7))]
        previews = render_previews(asset, views, preview_samples)
    export_glb(asset, out_dir)
    manifest = write_manifest(asset, out_dir, textures, previews)
    log(f"{asset.name}: {len(manifest['parts'])} parts, {manifest['triangles']} tris, {time.time() - t0:.0f}s")
    for p in manifest["parts"]:
        log(f"  {p['path'] or '.'}/{p['name']}: {p['tris']} tris size={p['size']}")
    return manifest
