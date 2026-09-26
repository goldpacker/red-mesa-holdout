"""Cycles scene setup and frame rendering for flipbooks (inside headless Blender).

Convention: Blender +Z is screen up, the orthographic camera looks along +Y,
so the frame's X is Blender X and its Y is Blender Z. Frames are written as
premultiplied scene-linear RGBA EXRs; tools/vfx/vfxlib/image.py does the
tone mapping and alpha work afterwards.
"""
import math
import os
import time

import bpy
from mathutils import Vector

GRID = 8
FRAMES = GRID * GRID      # 64 frames per 8x8 sheet
CELL = 128                # 1024 / 8 pixels per frame in the final sheet
SUPER = 2                 # frames render at CELL * SUPER, then box-downsample


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def use_gpu(scene) -> str:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    try:
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for dev in prefs.devices:
            dev.use = dev.type != "CPU"
        scene.cycles.device = "GPU"
        return "GPU"
    except (TypeError, AttributeError):
        scene.cycles.device = "CPU"
        return "CPU"


def _world(scene, color, strength):
    world = bpy.data.worlds.new("VfxWorld")
    scene.world = world
    try:
        world.use_nodes = True
    except AttributeError:
        pass
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*color, 1.0)
    bg.inputs["Strength"].default_value = strength


def setup(ortho=2.4, samples=64, res=CELL * SUPER, ambient=(0.62, 0.66, 0.74),
          ambient_strength=0.35, volume_bounces=1, biased=True, step_rate=1.0):
    """Fresh scene: Cycles GPU, transparent film, ortho camera, ambient world."""
    scene = reset()
    scene.render.engine = "CYCLES"
    device = use_gpu(scene)
    cy = scene.cycles
    cy.samples = samples
    cy.use_adaptive_sampling = False
    cy.use_denoising = False
    cy.volume_bounces = volume_bounces
    cy.volume_biased = biased
    cy.volume_step_rate = step_rate
    cy.volume_max_steps = 512
    cy.max_bounces = 4
    r = scene.render
    r.resolution_x = r.resolution_y = res
    r.resolution_percentage = 100
    r.film_transparent = True
    r.image_settings.file_format = "OPEN_EXR"
    r.image_settings.color_mode = "RGBA"
    r.image_settings.color_depth = "16"
    scene.view_settings.view_transform = "Standard"

    cam_data = bpy.data.cameras.new("VfxCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho
    cam_data.clip_start = 0.1
    cam_data.clip_end = 100.0
    cam = bpy.data.objects.new("VfxCam", cam_data)
    cam.location = (0.0, -30.0, 0.0)
    cam.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    scene.collection.objects.link(cam)
    scene.camera = cam
    _world(scene, ambient, ambient_strength)
    print(f"[vfx] scene ready: device={device} res={res} samples={samples} ortho={ortho}")
    return scene


def sun(direction, strength, color=(1.0, 1.0, 1.0), angle_deg=4.0, name="Sun"):
    """A sun light travelling along `direction` (x right, y into screen, z up)."""
    data = bpy.data.lights.new(name, "SUN")
    data.energy = strength
    data.color = color
    data.angle = math.radians(angle_deg)
    obj = bpy.data.objects.new(name, data)
    obj.rotation_euler = Vector(direction).normalized().to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(obj)
    return obj


def key_light(strength=4.0, rim=1.2):
    """Default particle lighting: warm key from upper left front, cool rim."""
    sun((0.45, 0.55, -0.7), strength, (1.0, 0.97, 0.92), name="Key")
    if rim > 0:
        sun((-0.3, -0.6, -0.4), rim, (0.85, 0.9, 1.0), name="Rim")


def render_frames(out_dir, setter, count=FRAMES):
    """Calls setter(i, t) for each frame (t in 0..1) and renders it to EXR.
    VFX_QUICK=<n> renders only every n-th frame (look-dev; the assembler
    reuses the previous rendered frame for the gaps)."""
    os.makedirs(out_dir, exist_ok=True)
    scene = bpy.context.scene
    step = max(1, int(os.environ.get("VFX_QUICK", "1")))
    start = time.time()
    for i in range(count):
        if i % step and i != count - 1:
            continue
        t = i / (count - 1) if count > 1 else 0.0
        setter(i, t)
        scene.render.filepath = os.path.join(out_dir, f"f{i:03d}.exr")
        bpy.ops.render.render(write_still=True)
        if i % 8 == 7 or i == count - 1:
            print(f"[vfx] rendered {i + 1}/{count} ({time.time() - start:.1f}s)")
    return time.time() - start
