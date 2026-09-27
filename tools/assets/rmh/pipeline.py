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


def _unwrap(objs, margin, down=None, back=None):
    _select(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    weighted = down is not None or back is not None or any("rmh_texel" in o.data.attributes for o in objs)
    if weighted:
        bpy.ops.object.mode_set(mode="OBJECT")
        for o in objs:
            _weight_islands(o, down, back)
        _select(objs)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def uv_islands(me):
    """UV islands of a mesh as lists of polygon indices (read-only bmesh)."""
    import bmesh
    from bpy_extras import bmesh_utils

    bm = bmesh.new()
    bm.from_mesh(me)
    bm.faces.ensure_lookup_table()
    uv = bm.loops.layers.uv.active
    out = [[f.index for f in island] for island in bmesh_utils.bmesh_linked_uv_islands(bm, uv)]
    bm.free()
    return out


def _weight_islands(obj, down, back=None):
    """Opt-in texel weighting (HS-3): each face gets a weight — its
    `rmh_texel` value (Part.add(texel=...)), times `down` if it faces the
    ground, or `back` if it faces the model's rear. Within every UV island
    the faces of each weight are scaled about their own centre by it (which
    splits them off into their own island), before packing, so the freed
    space goes to the surfaces people see. UVs are edited in place (no
    bmesh round trip, so custom normals stay untouched)."""
    me = obj.data
    uvd = me.uv_layers.active.data
    attr = me.attributes.get("rmh_texel")

    def weight(pl):
        fw = attr.data[pl.index].value if attr is not None else 0.0
        w = fw if fw > 0 else 1.0
        if down is not None and pl.normal.z < -0.6:
            w *= down
        elif back is not None and pl.normal.y < -0.6:
            w *= back
        return round(w, 3)

    for island in uv_islands(me):
        groups = {}
        for i in island:
            pl = me.polygons[i]
            groups.setdefault(weight(pl), []).append(pl)
        for w, polys in groups.items():
            if abs(w - 1.0) < 1e-3:
                continue
            idx = [i for pl in polys for i in pl.loop_indices]
            cu = sum(uvd[i].uv.x for i in idx) / len(idx)
            cv = sum(uvd[i].uv.y for i in idx) / len(idx)
            for i in idx:
                uvd[i].uv = (cu + (uvd[i].uv.x - cu) * w, cv + (uvd[i].uv.y - cv) * w)


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


def _bake_channel(objs, mats, img, channel, sources=None, cage=0.06, ray=0.4):
    """Bake `channel` into `img` on `objs` (materials `mats`). With
    `sources` (high-poly objects) the bake is selected-to-active: the
    channel is read from the sources' materials and written to the single
    target object in `objs`."""
    temp = []
    src_mats = _group_materials(sources) if sources else mats
    for mat in mats:
        nt = mat.node_tree
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        for n in nt.nodes:
            n.select = False
        node.select = True
        nt.nodes.active = node
        temp.append((mat, node, None, None))
    for mat in src_mats:
        if channel == "normal":
            continue
        nt = mat.node_tree
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
        temp.append((mat, None, emit, (out, prev)))
    bake = bpy.context.scene.render.bake
    bake.margin = 8
    bake.margin_type = "EXTEND"
    bake.use_clear = True
    if sources:
        _select(list(sources) + list(objs))
        bpy.context.view_layer.objects.active = objs[0]
        bake.use_selected_to_active = True
        bake.cage_extrusion = cage
        bake.max_ray_distance = ray
    else:
        _select(objs)
        bake.use_selected_to_active = False
    if channel == "normal":
        bake.normal_space = "TANGENT"
        bpy.ops.object.bake(type="NORMAL")
    else:
        bpy.ops.object.bake(type="EMIT")
    bake.use_selected_to_active = False
    for mat, node, emit, restore in temp:
        nt = mat.node_tree
        if node is not None:
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
    if "metal" in imgs:
        nt.links.new(tex("metal").outputs["Color"], bsdf.inputs["Metallic"])
    else:
        bsdf.inputs["Metallic"].default_value = 0.0
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


TEMPLATE_ORIGIN = Vector((0.0, 4000.0, 0.0))  # far from the asset so AO/bevel never see it
TEMPLATE_SPACING = 8.0


def prepare_templates(asset):
    """Create and UV-unwrap each sheet group's template meshes (before
    build_objects realises the instances that share those UVs)."""
    groups = {}
    for t in asset.templates:
        groups.setdefault(t.group, []).append(t)
    for group, temps in groups.items():
        size = asset.tex_size.get(group, asset.tex_size["main"])
        lows = []
        for i, t in enumerate(temps):
            loc = TEMPLATE_ORIGIN + Vector((i * TEMPLATE_SPACING, 0.0, 0.0))
            me = bpy.data.meshes.new(f"TPL_{t.name}")
            t.low.to_mesh(me)
            low = bpy.data.objects.new(f"TPL_{t.name}", me)
            bpy.context.scene.collection.objects.link(low)
            low.location = loc
            me.materials.append(asset.material_obj(t.mat))
            lows.append(low)
            t.objects.append(low)
            if t.high is not None:
                hm = bpy.data.meshes.new(f"TPLH_{t.name}")
                t.high.to_mesh(hm)
                high = bpy.data.objects.new(f"TPLH_{t.name}", hm)
                bpy.context.scene.collection.objects.link(high)
                high.location = loc
                hm.materials.append(asset.material_obj(t.mat))
                hm.shade_smooth()
                t.objects.append(high)
        log(f"unwrap sheet {group} ({len(temps)} templates, {size}px)")
        _unwrap_templates(temps, lows, margin=6.0 / size)
        from .asset import finalize_normals

        for t, low in zip(temps, lows):
            finalize_normals(low, t.smooth_angle)
            t.mesh = low.data


def _unwrap_templates(temps, lows, margin):
    smart = [o for t, o in zip(temps, lows) if t.uv != "seams"]
    seams = [o for t, o in zip(temps, lows) if t.uv == "seams"]
    if smart:
        _select(smart)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=margin, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
        bpy.ops.object.mode_set(mode="OBJECT")
    if seams:
        _select(seams)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.unwrap(method="ANGLE_BASED", margin=margin)
        bpy.ops.object.mode_set(mode="OBJECT")
    _select(lows)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin=margin, rotate=True)
    bpy.ops.object.mode_set(mode="OBJECT")


def _join_copies(objs, name):
    copies = []
    for o in objs:
        c = o.copy()
        c.data = o.data.copy()
        bpy.context.scene.collection.objects.link(c)
        copies.append(c)
    _select(copies)
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    return joined


def _bake_sheet(asset, group, size, out_dir, channels):
    temps = [t for t in asset.templates if t.group == group]
    lows = [t.objects[0] for t in temps]
    highs = [t.objects[1] if len(t.objects) > 1 else t.objects[0] for t in temps]
    target = _join_copies(lows, f"BAKE_{group}")
    source = _join_copies(highs, f"BAKESRC_{group}")
    target.data.materials.clear()
    tm = bpy.data.materials.new(f"BakeTarget_{group}")
    tm.use_nodes = True
    target.data.materials.append(tm)
    imgs, files = {}, {}
    for ch in channels:
        t0 = time.time()
        img = _new_image(f"{asset.name}_{group}_{ch}", size, ch)
        _bake_channel([target], [tm], img, ch, sources=[source])
        path = out_dir / f"{asset.name}_{group}_{ch}.png"
        _save_png(img, path, grayscale=ch in ("rough", "metal"))
        imgs[ch] = img
        files[ch] = path.name
        log(f"  baked {ch} in {time.time() - t0:.1f}s (selected-to-active)")
    density = texel_density(lows, size)
    for o in [target, source] + [o for t in temps for o in t.objects]:
        bpy.data.objects.remove(o, do_unlink=True)
    for t in temps:
        t.objects = []
    return imgs, files, density


def texel_density(objs, size, skip_down=False, skip_back=False):
    """Average texture density in px/stud over the objects' UV'd surface.
    Faces given less texture on purpose (Part.add(texel=...) < 1) are left
    out, so the number is what the visible surfaces get."""
    a3 = auv = 0.0
    for o in objs:
        me = o.data
        if not me.uv_layers:
            continue
        uv = me.uv_layers.active.data
        weights = me.attributes.get("rmh_texel")
        sx, sy, sz = o.matrix_world.to_scale()
        for poly in me.polygons:
            if weights is not None and 0.0 < weights.data[poly.index].value < 0.999:
                continue
            if skip_down and poly.normal.z < -0.6:
                continue
            if skip_back and poly.normal.y < -0.6:
                continue
            a3 += poly.area * abs(sx * sy * sz) ** (2.0 / 3.0)
            pts = [uv[i].uv for i in poly.loop_indices]
            auv += abs(sum(pts[k].x * pts[(k + 1) % len(pts)].y - pts[(k + 1) % len(pts)].x * pts[k].y for k in range(len(pts)))) / 2
    return round(size * math.sqrt(auv / a3), 1) if a3 > 0 else None


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
        opts = asset.group_opts.get(group, {})
        channels = [ch for ch in CHANNELS if ch != "metal" or opts.get("metal", True)]
        if opts.get("shared"):
            # Trim sheet owned by another asset: UVs come from the parts,
            # the maps are the source's (loaded for previews only).
            log(f"shared group {group} -> {opts['shared']} ({len(objs)} parts)")
            textures[group] = {"files": {}, "images": opts["images"], "objects": objs,
                               "density": texel_density(objs, size), "shared": opts["shared"]}
            continue
        if opts.get("high"):
            log(f"bake group {group} from high poly ({len(objs)} parts, {size}px)")
            _unwrap(objs, margin=6.0 / size, down=opts.get("down"), back=opts.get("back"))
            imgs, files = _bake_high(asset, group, objs, size, out_dir, channels, opts["high"], opts.get("metal_px"))
            textures[group] = {"files": files, "images": imgs, "objects": objs, "density": texel_density(objs, size, opts.get("down") is not None, opts.get("back") is not None)}
            continue
        if opts.get("sheet"):
            log(f"bake sheet {group} ({len(objs)} parts, {size}px)")
            imgs, files, density = _bake_sheet(asset, group, size, out_dir, channels)
            textures[group] = {"files": files, "images": imgs, "objects": objs, "density": density}
            continue
        log(f"unwrap group {group} ({len(objs)} parts, {size}px)")
        _unwrap(objs, margin=6.0 / size, down=opts.get("down"), back=opts.get("back"))
        mats = _group_materials(objs)
        imgs = {}
        files = {}
        for ch in channels:
            t0 = time.time()
            img = _new_image(f"{asset.name}_{group}_{ch}", size, ch)
            _bake_channel(objs, mats, img, ch)
            _shrink_metal(img, ch, opts.get("metal_px"), size)
            path = out_dir / f"{asset.name}_{group}_{ch}.png"
            _save_png(img, path, grayscale=ch in ("rough", "metal"))
            imgs[ch] = img
            files[ch] = path.name
            log(f"  baked {ch} in {time.time() - t0:.1f}s")
        textures[group] = {"files": files, "images": imgs, "objects": objs, "density": texel_density(objs, size, opts.get("down") is not None, opts.get("back") is not None)}
    return textures


_RAY_VIS = ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter", "visible_shadow")


def _shrink_metal(img, channel, px, size):
    """Opt-in (HS-5, texture_group(metal_px=...)): store the metalness map
    at a lower resolution than the other channels."""
    if channel == "metal" and px and px < size:
        img.scale(px, px)


def _bake_high(asset, group, objs, size, out_dir, channels, opts, metal_px=None):
    """Selected-to-active bake of a group from its parts' high-poly copies
    (Part.add rounds every hard edge; Part.detail adds bolts, welds, slats).
    The game meshes are hidden from rays meanwhile, so AO grime and edge
    wear are computed on the high-poly surface only."""
    highs = [bpy.data.objects[o["rmh_high"]] for o in objs if o.get("rmh_high")]
    if not highs:
        raise ValueError(f"group {group} is declared high but has no high-poly parts")
    target = _join_copies(objs, f"BAKE_{group}")
    target.data.materials.clear()
    tm = bpy.data.materials.new(f"BakeTarget_{group}")
    tm.use_nodes = True
    target.data.materials.append(tm)
    hidden = objs + [target]
    saved = [(o, [getattr(o, k) for k in _RAY_VIS]) for o in hidden]
    for o in hidden:
        for k in _RAY_VIS:
            setattr(o, k, False)
    for h in highs:
        h.hide_render = False
    imgs, files = {}, {}
    try:
        for ch in channels:
            t0 = time.time()
            img = _new_image(f"{asset.name}_{group}_{ch}", size, ch)
            _bake_channel([target], [tm], img, ch, sources=highs, cage=opts.get("cage", 0.1), ray=opts.get("ray", 0.3))
            _shrink_metal(img, ch, metal_px, size)
            path = out_dir / f"{asset.name}_{group}_{ch}.png"
            _save_png(img, path, grayscale=ch in ("rough", "metal"))
            imgs[ch] = img
            files[ch] = path.name
            log(f"  baked {ch} in {time.time() - t0:.1f}s (high poly, {sum(len(h.data.polygons) for h in highs)} faces)")
    finally:
        for o, vals in saved:
            if o.name in bpy.data.objects:
                for k, v in zip(_RAY_VIS, vals):
                    setattr(o, k, v)
        bpy.data.objects.remove(target, do_unlink=True)
        for h in highs:
            bpy.data.objects.remove(h, do_unlink=True)
    return imgs, files


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
    if getattr(asset, "preview_hide_transparent", False):
        # Opt-in (HS-5): what Roblox shows - no parts that are invisible in the file.
        for o in objs:
            if o.get("rmh_hidden_preview") or (o.get("rmh_transparency") or 0) >= 0.99:
                o.hide_render = True
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
    base_res = (scene.render.resolution_x, scene.render.resolution_y)
    for view in views:
        if isinstance(view, dict):
            outputs.append(_render_camera_view(asset, scene, cam, view, base_res))
            continue
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


def _render_camera_view(asset, scene, cam, view, base_res):
    """Opt-in preview from an explicit camera (e.g. the in-game turret
    camera): {"label", "pos", "look" (Blender coords), "fov" (vertical
    degrees, Roblox FieldOfView), "res": (w, h), "hide": [part names]}."""
    data = cam.data
    old = (data.sensor_fit, data.lens)
    data.sensor_fit = "VERTICAL"
    data.angle_y = math.radians(view.get("fov", 70))
    data.clip_start = 0.05
    pos = Vector(view["pos"])
    cam.location = pos
    cam.rotation_euler = (Vector(view["look"]) - pos).to_track_quat("-Z", "Y").to_euler()
    scene.render.resolution_x, scene.render.resolution_y = view.get("res", (1280, 720))
    hidden = [o for o in asset.objects if o.name in view.get("hide", ()) and not o.hide_render]
    for o in hidden:
        o.hide_render = True
    shown = [o for o in asset.objects if o.name in view.get("show", ()) and o.hide_render]
    for o in shown:
        o.hide_render = False
    path = ROOT / "assets" / "previews" / f"{asset.name}{view['label']}.png"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    for o in shown:
        o.hide_render = True
    data.sensor_fit, data.lens = old
    scene.render.resolution_x, scene.render.resolution_y = base_res
    log(f"preview {path.name}")
    return str(path.relative_to(ROOT))


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
        for key in ("query", "collide", "neon", "material", "transparency", "shadow", "invisible", "pivot_offset", "fidelity", "hitbox"):
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
        "textures": {g: t["files"] for g, t in textures.items() if not t.get("shared")},
        "texel_density": {g: t.get("density") for g, t in textures.items()},
        "previews": previews,
        "triangles": sum(p["tris"] for p in parts),
        "meta": asset.meta,
    }
    shared = {g: t["shared"] for g, t in textures.items() if t.get("shared")}
    if shared:
        manifest["shared_textures"] = shared
    with open(out_dir / "manifest.json", "w") as fh:
        json.dump(manifest, fh, indent=1)
    return manifest


def finish(asset, samples=24, preview_samples=96, views=None, preview=True):
    t0 = time.time()
    out_dir = ROOT / "assets" / "exported" / asset.name
    out_dir.mkdir(parents=True, exist_ok=True)
    (ROOT / "assets" / "blender").mkdir(parents=True, exist_ok=True)
    (ROOT / "assets" / "previews").mkdir(parents=True, exist_ok=True)
    if asset.templates:
        prepare_templates(asset)
    asset.build_objects()
    textures = bake_groups(asset, out_dir, samples)
    for o in [o for o in bpy.data.objects if o.name.startswith("HP_")]:
        bpy.data.objects.remove(o, do_unlink=True)  # high-poly sources of skipped groups
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
    log(f"  texel density px/stud: {manifest['texel_density']}")
    for p in manifest["parts"]:
        log(f"  {p['path'] or '.'}/{p['name']}: {p['tris']} tris size={p['size']}")
    return manifest
