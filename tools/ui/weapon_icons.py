"""Weapon strip icons rendered from the real emplacement weapons (LOOK-4).

    tools/blender-lock.sh acquire look4
    /Applications/Blender.app/Contents/MacOS/Blender -b assets/blender/Emplacement.blend \
        -P tools/ui/weapon_icons.py -- [--compose-only]
    tools/blender-lock.sh release look4

Renders the HS-4 weapon meshes from assets/blender/Emplacement.blend (the
machine gun with its belt, the rocket pod, the missile rail with both
missiles) with their own materials, one orthographic three-quarter view
each, on a transparent film at 4x the icon size, into
assets/ui/art/src/icon_<Weapon>.png. Then composes the UI icons:

  - luminance only, levels stretched into a light range (0.42..1) so the
    HUD tints them with ImageColor3 (selected cream, idle grey, empty red);
  - a crisp dark outline and a soft drop shadow (black survives any tint)
    so they read on the olive plates and over bright sand;
  - box-filtered down to 192x64 cells (displayed at ~88x30, so 2x for
    large screens) in one 256x256 atlas: assets/ui/art/weapon_icons.png,
    cell rects in assets/ui/art/art.json ("icons").

--compose-only skips the renders and rebuilds the atlas from src/.
"""
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "assets", "ui", "art")
SRC = os.path.join(OUT, "src")
CELL = (192, 64)  # icon cell, px (w, h)
SS = 4  # supersampling of the renders
ATLAS = 256
FLOOR = 0.24  # darkest shade in the icon (black noses, bores), before the tint

# Weapon -> meshes, view (azimuth from the right side toward the muzzle,
# elevation, degrees), fraction of the cell the icon may fill.
ICONS = {
    "MG": {"objects": ["Gun"], "az": 14.0, "el": 12.0, "fill": 0.96},
    "Rocket": {"objects": ["Pod"], "az": 40.0, "el": 14.0, "fill": 0.92},
    "Missile": {"objects": ["Missile1", "Missile2"], "az": 12.0, "el": 24.0, "fill": 0.96},
}
ORDER = ["MG", "Rocket", "Missile"]


def arg(name):
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return name in argv


# ------------------------------------------------------------------ render
def setup_scene():
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except Exception as err:  # CPU is fine for three small renders
        print("GPU unavailable:", err)
    sc.cycles.samples = 96
    sc.cycles.use_denoising = True
    sc.cycles.seed = 7
    sc.render.film_transparent = True
    sc.render.resolution_x, sc.render.resolution_y = CELL[0] * SS, CELL[1] * SS
    sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "16"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0

    world = bpy.data.worlds.new("IconWorld")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.55, 0.58, 0.62, 1.0)
    bg.inputs["Strength"].default_value = 0.55
    sc.world = world
    for o in list(sc.objects):
        if o.type == "LIGHT" or o.type == "CAMERA":
            bpy.data.objects.remove(o)


def light(name, energy, direction, angle=6.0, color=(1, 1, 1)):
    data = bpy.data.lights.new(name, "SUN")
    data.energy = energy
    data.angle = math.radians(angle)
    data.color = color
    ob = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(ob)
    # Sun lights shine along their -Z: point -Z along `direction` (light travel).
    ob.rotation_euler = Vector(direction).normalized().to_track_quat("-Z", "Y").to_euler()
    return ob


def view_basis(az, el):
    """Camera looking at the weapon's right side (Blender +X), turned `az`
    toward the muzzle (+Y) and raised `el`. Returns (forward, up, right)."""
    a, e = math.radians(az), math.radians(el)
    to_cam = Vector((math.cos(a) * math.cos(e), math.sin(a) * math.cos(e), math.sin(e)))
    forward = -to_cam
    right = forward.cross(Vector((0, 0, 1))).normalized()
    up = right.cross(forward).normalized()
    return forward, up, right


def render_icon(key, spec, cam):
    sc = bpy.context.scene
    names = set(spec["objects"])
    for o in sc.objects:
        if o.type == "MESH":
            o.hide_render = o.name not in names
    objs = [bpy.data.objects[n] for n in spec["objects"]]
    pts = [o.matrix_world @ v.co for o in objs for v in o.data.vertices]
    forward, up, right = view_basis(spec["az"], spec["el"])
    xs = [p.dot(right) for p in pts]
    ys = [p.dot(up) for p in pts]
    zs = [p.dot(forward) for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    aspect = CELL[0] / CELL[1]
    scale = max(w, h * aspect) / spec["fill"]
    center = right * cx + up * cy + forward * ((min(zs) + max(zs)) / 2)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = scale
    cam.data.clip_start = 0.01
    cam.data.clip_end = 100
    cam.location = center - forward * 30
    cam.rotation_euler = Matrix((right, up, -forward)).transposed().to_euler()
    # Key from the upper front-left of the view, a cool fill, a warm rim from behind.
    for o in [o for o in sc.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o)
    light("Key", 4.2, -up * 1.0 - right * 0.55 + forward * 0.9, color=(1.0, 0.96, 0.9))
    light("Fill", 0.9, right * 0.8 + forward * 1.0 + up * 0.2, angle=20, color=(0.85, 0.9, 1.0))
    light("Rim", 3.2, forward * -1.0 - up * 0.6 + right * 0.3, angle=4)
    path = os.path.join(SRC, f"icon_{key}.png")
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print(f"rendered {path} (view {w:.2f} x {h:.2f} studs, ortho {scale:.2f})")


def render_all():
    os.makedirs(SRC, exist_ok=True)
    setup_scene()
    cam_data = bpy.data.cameras.new("IconCam")
    cam = bpy.data.objects.new("IconCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    for key in ORDER:
        render_icon(key, ICONS[key], cam)


# ------------------------------------------------------------------ compose
def load_rgba(path):
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = "Non-Color"  # raw stored values (already display-encoded)
    w, h = img.size
    px = np.array(img.pixels[:], dtype=np.float64).reshape(h, w, 4)[::-1]  # top row first
    bpy.data.images.remove(img)
    return px


def box_down(a, f):
    h, w = a.shape[:2]
    return a.reshape(h // f, f, w // f, f, *a.shape[2:]).mean(axis=(1, 3))


def dilate(a, r):
    """Max filter with a disc of radius r (px)."""
    out = a.copy()
    ri = int(math.ceil(r))
    for dy in range(-ri, ri + 1):
        for dx in range(-ri, ri + 1):
            if dx * dx + dy * dy <= r * r + 1e-6:
                out = np.maximum(out, np.roll(np.roll(a, dy, 0), dx, 1))
    return out


def blur(a, r):
    out = a.copy()
    for axis in (0, 1):
        acc = np.zeros_like(out)
        for d in range(-r, r + 1):
            acc += np.roll(out, d, axis)
        out = acc / (2 * r + 1)
    return out


def compose_icon(px):
    """4x RGBA render -> 192x64 straight-alpha RGBA icon (light grey, outlined)."""
    alpha = px[..., 3]
    rgb = px[..., :3]  # Blender writes PNGs with straight alpha
    lum = rgb @ np.array([0.2126, 0.7152, 0.0722])
    inside = alpha > 0.5
    lo, hi = np.percentile(lum[inside], [1, 99.5])
    shade = np.clip((lum - lo) / max(hi - lo, 1e-4), 0, 1) ** 0.8
    shade = FLOOR + (1 - FLOOR) * shade
    # Premultiplied downsample, then a light unsharp mask so edges and panel
    # lines survive the 2x display reduction.
    a_small = box_down(alpha, SS)
    s_small = box_down(shade * alpha, SS) / np.maximum(a_small, 1e-4)
    s_small = np.clip(s_small + 0.6 * (s_small - blur(s_small, 1)), 0, 1)
    # Outline (1.6 px) and a soft shadow down-right, both black.
    outline = np.clip(dilate(a_small, 1.6), 0, 1)
    shadow = np.roll(np.roll(blur(dilate(a_small, 1.0), 2), 2, 0), 1, 1) * 0.55
    back_a = np.maximum(outline * 0.9, shadow)
    out = np.zeros(a_small.shape + (4,))
    # icon over black backing (straight alpha)
    a_out = a_small + back_a * (1 - a_small)
    col = s_small * a_small / np.maximum(a_out, 1e-4)
    out[..., 0] = out[..., 1] = out[..., 2] = col
    out[..., 3] = a_out
    return out


def write_png(path, rgba):
    h, w, _ = rgba.shape
    img = bpy.data.images.new(os.path.basename(path), w, h, alpha=True)
    img.colorspace_settings.name = "Non-Color"
    img.pixels = np.clip(rgba[::-1], 0, 1).astype(np.float32).ravel()
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def compose():
    atlas = np.zeros((ATLAS, ATLAS, 4))
    cells = {}
    for i, key in enumerate(ORDER):
        icon = compose_icon(load_rgba(os.path.join(SRC, f"icon_{key}.png")))
        y = i * (CELL[1] + 4)
        atlas[y:y + CELL[1], 0:CELL[0]] = icon
        cells[key] = {"offset": [0, y], "size": list(CELL)}
    write_png(os.path.join(OUT, "weapon_icons.png"), atlas)
    meta_path = os.path.join(OUT, "art.json")
    meta = json.load(open(meta_path)) if os.path.exists(meta_path) else {}
    meta["icons"] = {"size": [ATLAS, ATLAS], "cells": cells}
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=1, sort_keys=True)
        f.write("\n")
    print("wrote", os.path.join(OUT, "weapon_icons.png"))


def preview():
    """Mock weapon strip: the icons on olive plates at display size (1x, from
    the 2x cells) in the three HUD tints, magnified 3x (nearest) for review,
    plus the cells at 2x on sand. -> assets/previews/ui/weapon_icons.png"""
    atlas = load_rgba(os.path.join(OUT, "weapon_icons.png"))
    tints = [(240 / 255, 228 / 255, 196 / 255), (120 / 255, 120 / 255, 110 / 255), (230 / 255, 52 / 255, 38 / 255)]
    plate = np.array([62, 66, 42]) / 255
    sand = np.array([201, 130, 79]) / 255
    row_h, col_w = 40, 104
    small = np.zeros((row_h * 3, col_w * 3, 3))
    small[:] = plate
    for r, tint in enumerate(tints):
        for c, key in enumerate(ORDER):
            x, y = 0, c * (CELL[1] + 4)
            icon = box_down(atlas[y:y + CELL[1], x:x + CELL[0]], 2)  # 96x32
            a = icon[..., 3:4]
            col = icon[..., :3] * np.array(tint)
            oy, ox = r * row_h + 4, c * col_w + 4
            region = small[oy:oy + 32, ox:ox + 96]
            small[oy:oy + 32, ox:ox + 96] = region * (1 - a) + col * a
    big = np.repeat(np.repeat(small, 3, 0), 3, 1)
    full = np.zeros((CELL[1] * 3 + 16, CELL[0] + 16, 3))
    full[:] = sand
    for c, key in enumerate(ORDER):
        y = c * (CELL[1] + 4)
        icon = atlas[y:y + CELL[1], 0:CELL[0]]
        a = icon[..., 3:4]
        oy = 8 + c * CELL[1]
        full[oy:oy + CELL[1], 8:8 + CELL[0]] = full[oy:oy + CELL[1], 8:8 + CELL[0]] * (1 - a) + icon[..., :3] * np.array(tints[0]) * a
    h = big.shape[0] + full.shape[0] + 8
    w = max(big.shape[1], full.shape[1])
    sheet = np.ones((h, w, 4))
    sheet[..., :3] = 0.1
    sheet[:big.shape[0], :big.shape[1], :3] = big
    sheet[big.shape[0] + 8:, :full.shape[1], :3] = full
    os.makedirs(os.path.join(ROOT, "assets", "previews", "ui"), exist_ok=True)
    write_png(os.path.join(ROOT, "assets", "previews", "ui", "weapon_icons.png"), sheet)


if arg("--preview"):
    preview()
else:
    if not arg("--compose-only"):
        render_all()
    compose()
    preview()
