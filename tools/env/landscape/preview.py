"""Quick look at landscape geometry from the beauty-shot cameras (Blender).

  Blender -b --factory-startup -P tools/env/landscape/preview.py -- \
      [--pieces Mesa,RearWall] [--high] [--baked] [--shots title,flank] [--out DIR] [--res 0.5]

Loads assets/source/landscape/build/<Piece>.npz (from shape.py), shades
it with a flat strata ramp (or, with --baked, the baked textures from
assets/exported/Landscape_<Piece>/), adds a sand floor and a sun, and
renders the beauty cameras (tools/qa/BEAUTY.md) into
assets/previews/landscape/ (default). Roblox (x, y, z) = Blender (x, -z, y).
"""
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)

import strata  # noqa: E402

BUILD = os.path.join(ROOT, "assets", "source", "landscape", "build")
EXPORTED = os.path.join(ROOT, "assets", "exported")

# Roblox cameras: (position, look-at, vertical FOV)
SHOTS = {
    "title": ((-70, 128, 150), (90, 0, -420), 60),
    "turret": ((0, 80, 22), (0, 80 - math.tan(math.radians(7.5)) * 100, -78), 70),
    "flank": ((430, 70, -700), (-20, 25, -190), 45),
    "night": ((95, 30, -560), (-50, 70, -40), 45),
    "mesa": ((150, 70, -160), (0, 30, 0), 50),
    "ridge": ((-40, 110, 120), (10, 40, 30), 60),
    "top": ((0, 4000, -550.01), (0, 0, -550), 29),
    "corner": ((500, 60, -100), (800, 60, 150), 60),
    "rim": ((60, 110, -260), (-70, 125, 140), 30),
    "butte": ((100, 40, -900), (260, 50, -1150), 40),
}
ALL = ["Mesa", "RearWall", "FlankLeft", "FlankRight", "FarWall", "Butte1", "Butte2", "Butte3", "Butte4"]


def rb(v):
    return Vector((v[0], -v[2], v[1]))


def arg(name, default=None):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
            return argv[i + 1]
        return True
    return default


def srgb(hexs):
    h = hexs.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]


def strata_colors(v):
    """Per-vertex flat preview colour from the bed model (Roblox coords)."""
    k, f = strata.bed_at(v[:, 0], v[:, 1], v[:, 2])
    hard = strata.HARD[k]
    light, mid, dark = np.array(srgb("#BA6A44")), np.array(srgb("#9E4A2E")), np.array(srgb("#6E3322"))
    c = np.where(hard[:, None] > 0.6, light * 0.6 + mid * 0.4, mid * 0.7 + dark * 0.3)
    return c


def add_mesh(name, v, f, colors=None):
    me = bpy.data.meshes.new(name)
    bv = np.stack([v[:, 0], -v[:, 2], v[:, 1]], axis=1).astype(np.float32)
    me.vertices.add(len(bv))
    me.vertices.foreach_set("co", bv.ravel())
    me.loops.add(len(f) * 3)
    me.loops.foreach_set("vertex_index", f.astype(np.int32).ravel())
    me.polygons.add(len(f))
    me.polygons.foreach_set("loop_start", np.arange(0, len(f) * 3, 3, dtype=np.int32))
    me.update()
    me.validate()
    if colors is not None:
        attr = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
        rgba = np.concatenate([colors, np.ones((len(colors), 1))], axis=1).astype(np.float32)
        attr.data.foreach_set("color", rgba.ravel())
    me.shade_flat()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def cull_backfaces(mat):
    """Roblox culls back faces; show the same (a camera inside the rock sees out)."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    nt.links.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


def vcol_material():
    mat = bpy.data.materials.new("Strata")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    attr = nt.nodes.new("ShaderNodeVertexColor")
    attr.layer_name = "Col"
    nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    return mat


def main():
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = int(arg("--samples", 24))
    sc.cycles.use_denoising = True
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except Exception:
        pass
    res = float(arg("--res", 0.5))
    sc.render.resolution_x, sc.render.resolution_y = int(1190 * res), int(1080 * res)
    sc.view_settings.view_transform = "AgX" if "AgX" in [i.identifier for i in sc.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    world = bpy.data.worlds.new("W")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.45, 0.6, 0.85, 1)
    bg.inputs["Strength"].default_value = 0.6
    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 4.0
    sun_data.angle = math.radians(1.0)
    sun = bpy.data.objects.new("Sun", sun_data)
    sc.collection.objects.link(sun)
    sun_dir = rb(tuple(float(c) for c in arg("--sun", "0.55,0.62,0.56").split(",")))  # toward the sun, Roblox coords
    sun.rotation_euler = sun_dir.to_track_quat("Z", "Y").to_euler()

    pieces = arg("--pieces", ",".join(ALL)).split(",")
    use_high = bool(arg("--high", False))
    baked = bool(arg("--baked", False))
    mat = vcol_material()
    cull_backfaces(mat)
    for name in pieces:
        blend = os.path.join(ROOT, "assets", "blender", f"Landscape_{name}.blend")
        if baked and os.path.exists(blend):
            with bpy.data.libraries.load(blend) as (src, dst):
                dst.objects = [n for n in src.objects if n.startswith(f"{name}_C")]
            for ob in dst.objects:
                sc.collection.objects.link(ob)
                for slot in ob.material_slots:
                    if slot.material and not slot.material.get("culled"):
                        cull_backfaces(slot.material)
                        slot.material["culled"] = True
            continue
        path = os.path.join(BUILD, f"{name}.npz")
        if not os.path.exists(path):
            print(f"skip {name}: no {path}")
            continue
        d = np.load(path)
        v = d["high_v"] if use_high else d["low_v"]
        f = d["high_f"] if use_high else d["low_f"]
        ob = add_mesh(name, v, f, strata_colors(v))
        ob.data.materials.append(mat)
    floor = add_mesh("Floor", np.array([[-1100, 0, -1600], [1100, 0, -1600], [1100, 0, 500], [-1100, 0, 500]], float),
                     np.array([[0, 2, 1], [0, 3, 2]]))
    fm = bpy.data.materials.new("Sand")
    fm.use_nodes = True
    next(n for n in fm.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = srgb("#C9824F") + [1]
    floor.data.materials.append(fm)

    out = arg("--out", os.path.join(ROOT, "assets", "previews", "landscape"))
    os.makedirs(out, exist_ok=True)
    tag = arg("--tag", "")
    for shot in arg("--shots", "title,turret,flank,night").split(","):
        pos, look, fov = SHOTS[shot]
        cam_data = bpy.data.cameras.new(shot)
        cam_data.sensor_fit = "VERTICAL"
        cam_data.angle = math.radians(fov)
        cam_data.clip_start = 0.5
        cam_data.clip_end = 5000
        cam = bpy.data.objects.new(shot, cam_data)
        sc.collection.objects.link(cam)
        cam.location = rb(pos)
        cam.rotation_euler = (rb(look) - rb(pos)).to_track_quat("-Z", "Y").to_euler()
        sc.camera = cam
        sc.render.filepath = os.path.join(out, f"{shot}{tag}.png")
        bpy.ops.render.render(write_still=True)
        print(f"rendered {sc.render.filepath} ({time.time() - t0:.0f}s)")


main()
