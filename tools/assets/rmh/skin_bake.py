"""Texture side of skinned assets (rmh/skin.py): the `garment` material
kind (fabric with baked compression folds) and a self-contained copy of
the rigid pipeline's emission bake, so HS changes to rmh/pipeline.py
can't break skinned builds."""
import math

import bpy
from mathutils import Vector

from . import materials, pipeline


# --- garment material: fabric + folds around joints ---------------------------

def _garment(g, spec, decals, zmin):
    """Fabric (materials._fabric) plus compression folds baked into the
    height/normal: each fold = (centre, axis, radius, wavelength, depth);
    rings perpendicular to `axis`, distorted by noise, fading with
    distance from `centre` (object space, bind pose)."""
    co = g.coords()
    base = spec["color"]
    if spec.get("pattern") == "camo":
        n1 = g.noise(co, scale=spec.get("camo_scale", 1.6), detail=3.0, distortion=0.6)
        n2 = g.noise(g.mapping(co, loc=(3.1, 1.7, 0.4)), scale=spec.get("camo_scale", 1.6) * 1.3, detail=3.0)
        c = g.mix(g.maprange(n1, 0.52, 0.56), materials.rgb(base), materials.rgb(spec["color2"]))
        color = g.mix(g.maprange(n2, 0.6, 0.64), c, materials.rgb(spec.get("color3", base)))
    else:
        var = g.noise(co, scale=spec.get("var_scale", 2.0), detail=5.0)
        color = g.mix(g.maprange(var, 0.3, 0.7), materials.scale_rgb(base, 0.82), materials.scale_rgb(base, 1.1))
    color = materials._apply_marks(g, spec, co, color, decals)
    ws = spec.get("weave", 60.0)
    weave = g.math(
        "MULTIPLY",
        g.wave(g.mapping(co, scale=(ws, ws, ws)), scale=1.0, distortion=0.4, detail=0.0, direction="X"),
        g.wave(g.mapping(co, scale=(ws, ws, ws)), scale=1.0, distortion=0.4, detail=0.0, direction="Y"),
    )
    wrinkle = g.noise(co, scale=spec.get("wrinkle_scale", 4.0), detail=3.0, distortion=0.5)
    height = g.math("ADD", g.math("MULTIPLY", weave, spec.get("weave_depth", 0.2)), g.math("MULTIPLY", wrinkle, spec.get("wrinkle", 0.4)))
    warp = g.noise(co, scale=spec.get("fold_warp_scale", 3.5), detail=2.0)
    folds_total = None
    for f in spec.get("folds", []):
        centre, axis = Vector(f["centre"]), Vector(f["axis"]).normalized()
        rel = g.vmath("SUBTRACT", co, tuple(centre))
        t = g.vmath("DOT_PRODUCT", rel, tuple(axis))
        dist = g.vmath("LENGTH", rel)
        fade = g.maprange(dist, f["radius"] * 0.35, f["radius"], 1.0, 0.0, smooth=True)
        phase = g.math("ADD", g.math("MULTIPLY", t, math.tau / f.get("wavelength", 0.16)), g.math("MULTIPLY", warp, f.get("warp", 7.0)))
        wave = g.math("SINE", phase)
        # Sharpen crests into folds: |sin|^0.6 shaped ridges.
        ridge = g.math("POWER", g.math("ABSOLUTE", wave), 0.6)
        fold = g.math("MULTIPLY", g.math("MULTIPLY", ridge, fade), f.get("depth", 1.0))
        folds_total = fold if folds_total is None else g.math("MAXIMUM", folds_total, fold)
    if folds_total is not None:
        height = g.math("ADD", height, folds_total)
        # Fold valleys collect dust/grime slightly: darken troughs a touch.
        color = g.mix(g.math("MULTIPLY", g.math("SUBTRACT", 1.0, folds_total, clamp=True), spec.get("fold_shade", 0.0)), color, materials.scale_rgb(base, 0.6))
    edge, bevn = g.edge_mask(spec.get("bevel", 0.06))
    spec2 = dict(spec)
    spec2["wear"] = 0.0
    color, rough, metal, height = materials._wear_layers(g, spec2, co, color, spec.get("rough", 0.9), 0.0, height, edge, zmin)
    materials._finish(g, color, rough, 0.0, height, bevn, bump=spec.get("bump", 0.35), bump_distance=spec.get("bump_distance", 0.05))


materials.KINDS.setdefault("garment", _garment)


# --- baking (self-contained copy of the rigid pipeline's emission bake) ------

_BSDF_INPUT = {"color": "Base Color", "rough": "Roughness", "metal": "Metallic"}


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
        entry = [mat, node, None, None]
        if channel != "normal":
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
            entry[2:] = [emit, (out, prev)]
        temp.append(entry)
    pipeline._select(objs)
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
