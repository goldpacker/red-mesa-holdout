"""Blender preview renders of the terrain texture sets.

    tools/blender-lock.sh acquire env
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        -P tools/env/preview_terrain.py -- [Name ...]
    tools/blender-lock.sh release env

For each material: a grazing "turret" view over a wide floor (or a cliff
wall for the rock materials) under a low warm sun, and a close view, at the
material's studs-per-tile (1 Blender unit = 1 stud). Writes
assets/previews/terrain/<Name>.png and a contact sheet terrain_sheet.png.
"""
import json
import math
import os
import sys

import bpy
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEX = os.path.join(ROOT, "assets", "textures", "terrain")
OUT = os.path.join(ROOT, "assets", "previews", "terrain")
WALLS = {"Rock", "Sandstone", "Limestone", "Slate"}
W, H = 960, 540


def reset():
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
    except Exception as e:  # CPU fallback
        print("GPU unavailable:", e)
    sc.cycles.samples = 48
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = W, H
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.62, 0.75, 1)
    bg.inputs["Strength"].default_value = 0.6
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 4.5
    sun.data.color = (1.0, 0.9, 0.78)
    sun.data.angle = math.radians(1.0)
    sun.rotation_euler = (math.radians(62), 0, math.radians(35))
    sc.collection.objects.link(sun)
    return sc


def material(name: str, info: dict, tiles_u: float, tiles_v: float) -> bpy.types.Material:
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uv = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (tiles_u, tiles_v, 1)
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])

    def img(key: str, non_color: bool):
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = bpy.data.images.load(os.path.join(TEX, name, info["files"][key]))
        if non_color:
            node.image.colorspace_settings.name = "Non-Color"
        nt.links.new(mp.outputs["Vector"], node.inputs["Vector"])
        return node

    nt.links.new(img("color", False).outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(img("roughness", True).outputs["Color"], bsdf.inputs["Roughness"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(img("normal", True).outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return m


def plane(sc, size_u: float, size_v: float, mat, loc, rot):
    bpy.ops.mesh.primitive_plane_add(size=1, location=loc, rotation=rot)
    ob = bpy.context.active_object
    ob.scale = (size_u, size_v, 1)
    ob.data.materials.append(mat)
    return ob


def camera(sc, loc, target, lens=35):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.lens = lens
    cam.data.clip_end = 5000
    cam.location = loc
    d = np.array(target) - np.array(loc)
    cam.rotation_euler = (math.atan2(math.hypot(d[0], d[1]), -d[2]), 0, math.atan2(d[1], d[0]) - math.pi / 2)
    sc.collection.objects.link(cam)
    sc.camera = cam


def render(path: str):
    bpy.context.scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def preview(name: str) -> list[str]:
    info = json.load(open(os.path.join(TEX, name, "manifest.json")))
    spt = info["studs_per_tile"]
    os.makedirs(OUT, exist_ok=True)
    shots = []
    for view in ("far", "near"):
        sc = reset()
        if name in WALLS:
            size_u, size_v = 600.0, 160.0
            mat = material(name, info, size_u / spt, size_v / spt)
            plane(sc, size_u, size_v, mat, (0, 0, size_v / 2), (math.radians(90), 0, 0))
            floor = material("Sand", json.load(open(os.path.join(TEX, "Sand", "manifest.json"))), 1200 / 48, 1200 / 48)
            plane(sc, 1200, 1200, floor, (0, -600, 0), (0, 0, 0))
            if view == "far":
                camera(sc, (-60, -420, 70), (0, 0, 60), 35)
            else:
                camera(sc, (-10, -45, 30), (0, 0, 26), 35)
        else:
            size = 1600.0
            mat = material(name, info, size / spt, size / spt)
            plane(sc, size, size, mat, (0, 0, 0), (0, 0, 0))
            if view == "far":
                camera(sc, (0, 0, 60), (0, 300, 0), 35)
            else:
                camera(sc, (0, 0, 14), (0, 22, 0), 35)
        path = os.path.join(OUT, f"{name}_{view}.png")
        render(path)
        shots.append(path)
    return shots


def sheet(files: list[str], out: str, cols: int = 2):
    rows = (len(files) + cols - 1) // cols
    tw, th = W // 2, H // 2
    arr = np.zeros((rows * th, cols * tw, 4), dtype=np.float32)
    arr[..., 3] = 1
    for i, f in enumerate(files):
        img = bpy.data.images.load(f)
        img.scale(tw, th)
        px = np.array(img.pixels[:], dtype=np.float32).reshape(th, tw, 4)
        r, c = rows - 1 - i // cols, i % cols
        arr[r * th:(r + 1) * th, c * tw:(c + 1) * tw] = px
    res = bpy.data.images.new("sheet", cols * tw, rows * th)
    res.pixels.foreach_set(arr.ravel())
    res.filepath_raw = out
    res.file_format = "PNG"
    res.save()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    names = argv or sorted(d for d in os.listdir(TEX) if os.path.exists(os.path.join(TEX, d, "manifest.json")))
    files = []
    for name in names:
        files += preview(name)
    if not argv:
        sheet(files, os.path.join(OUT, "terrain_sheet.png"))


main()
