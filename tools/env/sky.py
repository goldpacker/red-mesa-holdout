"""Renders the Red Mesa skyboxes (6 faces per time-of-day preset) in Blender.

    tools/blender-lock.sh acquire env
    /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
        -P tools/env/sky.py -- [Preset ...] [--test] [--preview-only] [--views]
    tools/blender-lock.sh release env

A Cycles world shader (tools/env/sky.osl) layers Blender's physical Sky
Texture (sun disc off: Roblox draws the sun and moon) with haze, a cloud
deck, cirrus, and at night stars and a Milky Way band. Each preset is
rendered with six 90° cameras into
assets/textures/sky/<Preset>/<Preset>_<Face>.png (1024²) plus an
equirectangular preview in assets/previews/sky/<Preset>.png.

Sun/moon directions come from Roblox (Lighting:GetSunDirection() at the
preset's ClockTime and GeographicLatitude, measured in Studio), in Roblox
world space; Roblox (x, y, z) = Blender (x, -z, y).

--test renders an orientation test sky (labelled directions) used to
verify face orientation in Studio; --views renders a preset from the
STUDIO_VIEWS cameras (Roblox default 70° FOV) to compare with Studio
captures taken from the same directions (orientation and seams).
"""
import json
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(ROOT, "assets", "textures", "sky")
PREVIEW = os.path.join(ROOT, "assets", "previews", "sky")
FACE = 1024

# Roblox skybox face -> (camera forward, camera up) in Roblox world space.
# Measured in Studio with the --test sky (labelled directions): Roblox shows
# SkyboxLf when looking +X and SkyboxRt when looking -X; SkyboxUp's image
# top points to +X and SkyboxDn's to -X.
FACES = {
    "Ft": ((0, 0, -1), (0, 1, 0)),
    "Bk": ((0, 0, 1), (0, 1, 0)),
    "Lf": ((1, 0, 0), (0, 1, 0)),
    "Rt": ((-1, 0, 0), (0, 1, 0)),
    "Up": ((0, 1, 0), (1, 0, 0)),
    "Dn": ((0, -1, 0), (-1, 0, 0)),
}


def rb(v) -> Vector:
    """Roblox world vector -> Blender world vector."""
    return Vector((v[0], -v[2], v[1]))


def lin(hex_or_rgb, scale: float = 1.0):
    if isinstance(hex_or_rgb, str):
        h = hex_or_rgb.lstrip("#")
        c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        c = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    else:
        c = list(hex_or_rgb)
    return tuple(x * scale for x in c)


# Per preset: Roblox sun/moon directions, physical-sky settings and layers.
PRESETS = json.load(open(os.path.join(HERE, "sky_presets.json")))


def scene_setup(samples: int):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.shading_system = True  # OSL
    sc.cycles.samples = samples
    sc.cycles.use_denoising = False
    sc.cycles.filter_width = 1.2
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_depth = "8"
    sc.render.threads_mode = "AUTO"
    return sc


def build_world(sc, p: dict):
    world = bpy.data.worlds.new("sky")
    sc.world = world
    world.use_nodes = True
    nt = world.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    osl = nt.nodes.new("ShaderNodeScript")
    osl.mode = "EXTERNAL"
    osl.filepath = os.path.join(HERE, "sky.osl")
    osl.update()
    nt.links.new(osl.outputs["Col"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0

    sun_b = rb(p["sun"]).normalized()
    moon_b = rb(p.get("moon", [0, 1, 0])).normalized()
    phys = p.get("physical")
    if phys:
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = phys.get("type", "MULTIPLE_SCATTERING")
        sky.sun_disc = False
        sky.sun_elevation = math.asin(max(-1.0, min(1.0, sun_b.z)))
        sky.sun_rotation = sun_rotation_for(sun_b)
        sky.altitude = phys.get("altitude", 800.0)
        sky.air_density = phys.get("air", 1.0)
        sky.aerosol_density = phys.get("aerosol", 1.0)
        sky.ozone_density = phys.get("ozone", 1.0)
        nt.links.new(sky.outputs["Color"], osl.inputs["Base"])

    def setv(name, value):
        sock = osl.inputs.get(name)
        if sock is None:
            raise KeyError(f"sky.osl has no input {name}")
        if isinstance(value, (list, tuple)) and len(value) == 3 and sock.type == "RGBA":
            value = (*value, 1.0)
        sock.default_value = value

    setv("SunDir", tuple(sun_b))
    setv("MoonDir", tuple(moon_b))
    for key, value in p.get("shader", {}).items():
        # Colours: "#rrggbb" (sRGB) or ["#rrggbb", radiance scale].
        if isinstance(value, str):
            value = lin(value)
        elif isinstance(value, list) and value and isinstance(value[0], str):
            value = lin(value[0], value[1])
        elif key == "MilkyNormal":
            value = tuple(rb(value).normalized())
        elif isinstance(value, list):
            value = tuple(value)
        setv(key, value)
    return world


def sun_rotation_for(sun_b: Vector) -> float:
    # Blender's Sky Texture puts the sun at azimuth `sun_rotation` measured
    # from +Y toward +X (checked by rendering: rotation 0 -> +Y, pi/2 -> +X).
    return math.atan2(sun_b.x, sun_b.y)


def face_camera(sc, forward_rb, up_rb, fov_deg: float = 90.0, fit: str = "HORIZONTAL"):
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    cam.data.type = "PERSP"
    cam.data.sensor_fit = fit
    cam.data.angle = math.radians(fov_deg)
    cam.data.clip_start = 0.01
    cam.data.clip_end = 1000
    f = rb(forward_rb).normalized()
    r = f.cross(rb(up_rb).normalized()).normalized()
    u = r.cross(f).normalized()
    m = Matrix((r, u, -f)).transposed().to_4x4()
    cam.matrix_world = m
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def pano_camera(sc):
    cam = bpy.data.objects.new("pano", bpy.data.cameras.new("pano"))
    cam.data.type = "PANO"
    cam.data.panorama_type = "EQUIRECTANGULAR"
    # Centre of the panorama = Roblox -Z (the basin), up = Roblox +Y.
    f = rb((0, 0, -1))
    u = rb((0, 1, 0))
    r = f.cross(u)
    cam.matrix_world = Matrix((r, u, -f)).transposed().to_4x4()
    sc.collection.objects.link(cam)
    sc.camera = cam
    return cam


def colour_management(sc, p: dict):
    cm = p.get("view", {})
    sc.view_settings.view_transform = cm.get("transform", "AgX")
    look = cm.get("look")
    if look:
        sc.view_settings.look = look
    sc.view_settings.exposure = cm.get("exposure", 0.0)
    sc.view_settings.gamma = cm.get("gamma", 1.0)


def render_to(sc, path: str, w: int, h: int):
    sc.render.resolution_x, sc.render.resolution_y = w, h
    sc.render.resolution_percentage = 100
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def add_test_labels(sc):
    """Emissive text in each Roblox direction and an 'UP' arrow above it."""
    mat = bpy.data.materials.new("label")
    mat.use_nodes = True
    nt = mat.node_tree
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1, 1, 0.2, 1)
    em.inputs["Strength"].default_value = 4
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    labels = {
        "-Z FRONT": ((0, 0, -1), (0, 1, 0)),
        "+Z BACK": ((0, 0, 1), (0, 1, 0)),
        "-X": ((-1, 0, 0), (0, 1, 0)),
        "+X": ((1, 0, 0), (0, 1, 0)),
        "UP -Z^": ((0, 1, 0), (0, 0, -1)),
        "DOWN -Z^": ((0, -1, 0), (0, 0, -1)),
    }
    for text, (d, up) in labels.items():
        curve = bpy.data.curves.new(text, "FONT")
        curve.body = text
        curve.align_x = "CENTER"
        curve.align_y = "CENTER"
        curve.size = 1.6
        ob = bpy.data.objects.new(text, curve)
        ob.data.materials.append(mat)
        f = rb(d).normalized()
        u = rb(up).normalized()
        # Text faces the origin: its +Z normal points back at the camera.
        normal = -f
        x = u.cross(normal).normalized()
        ob.matrix_world = Matrix.Translation(f * 10) @ Matrix((x, u, normal)).transposed().to_4x4()
        sc.collection.objects.link(ob)


# Studio comparison views: (yaw from -Z toward +X, pitch) in degrees, seen
# with Roblox's default camera (70° vertical FOV) at the capture size.
STUDIO_VIEWS = {
    "v1_front": (0, 10), "v2_back": (180, 10), "v3_left": (-90, 10), "v4_right": (90, 10),
    "v5_up": (0, 60), "v6_down": (0, -60), "v7_corner": (-45, 45), "v8_corner": (135, 30),
}
STUDIO_SIZE = (1190, 1080)


def view_dir(yaw: float, pitch: float):
    y, p = math.radians(yaw), math.radians(pitch)
    return (math.sin(y) * math.cos(p), math.sin(p), -math.cos(y) * math.cos(p))


def render_views(name: str, p: dict, samples: int):
    """Renders the Studio comparison views of a preset for orientation/seam checks."""
    sc = scene_setup(samples)
    build_world(sc, p)
    colour_management(sc, p)
    if p.get("test"):
        add_test_labels(sc)
    d = os.path.join(PREVIEW, "views", name)
    os.makedirs(d, exist_ok=True)
    for vname, (yaw, pitch) in STUDIO_VIEWS.items():
        face_camera(sc, view_dir(yaw, pitch), (0, 1, 0), 70.0, "VERTICAL")
        render_to(sc, os.path.join(d, f"{vname}.png"), *STUDIO_SIZE)


def render_preset(name: str, p: dict, preview_only: bool, samples: int):
    sc = scene_setup(samples)
    build_world(sc, p)
    colour_management(sc, p)
    if p.get("test"):
        add_test_labels(sc)
    os.makedirs(PREVIEW, exist_ok=True)
    pano_camera(sc)
    render_to(sc, os.path.join(PREVIEW, f"{name}.png"), 2048, 1024)
    if preview_only:
        return
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)
    for face, (fwd, up) in FACES.items():
        face_camera(sc, fwd, up)
        render_to(sc, os.path.join(d, f"{name}_{face}.png"), FACE, FACE)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    preview_only = "--preview-only" in argv
    names = [a for a in argv if not a.startswith("--")]
    if "--test" in argv:
        names = ["Test"]
    names = names or [k for k in PRESETS if not PRESETS[k].get("test")]
    samples = 32
    for name in names:
        print(f"[sky] rendering {name}")
        if "--views" in argv:
            render_views(name, PRESETS[name], PRESETS[name].get("samples", samples))
            continue
        render_preset(name, PRESETS[name], preview_only, PRESETS[name].get("samples", samples))


main()
