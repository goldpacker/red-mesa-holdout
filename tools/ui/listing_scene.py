"""Roblox listing art (LOOK-7): the Blender thumbnails and the icon render,
from the LOOK-4 key-art scene (tools/ui/keyart_scene.py and its building
blocks: the real emplacement, landscape, captured terrain and placements,
ENV's Sunset sky, and the airdrop built from the game's own rules in
tools/ui/keyart_airdrop.py).

    tools/blender-lock.sh acquire look7
    B=/Applications/Blender.app/Contents/MacOS/Blender
    $B -b --factory-startup -P tools/ui/listing_scene.py -- --shot hero --sky   # sky plate for the shot
    $B -b --factory-startup -P tools/ui/listing_scene.py -- --shot hero         # final render
    tools/blender-lock.sh release look7

Shots (SHOTS below): `hero` (the key-art camera and drop, re-rendered at
16:9), `airdrop` (a two-ship formation mid-drop over the basin, laid out by
AirdropConfig's rules), `icon` (square, close on the same drop) and
`icon_gun` (an unused square alternative over the gun). Each final
is rendered at SS x its size and area-averaged down, so fine lines (risers,
far troopers) stay crisp, and written to assets/listing/src/<shot>_render.png
for tools/ui/listing_compose.py. Drafts: --draft [--res 0.5] [--samples 16]
write assets/listing/src/drafts/<shot>_draft.png (git-ignored). Camera
overrides for look-dev: --pos/--look x,y,z, --vfov, --yaw/--pitch (turret).
"""
import math
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np  # noqa: E402

import keyart_scene as ks  # noqa: E402
from keyart_world import ROOT, arg, log  # noqa: E402

OUT = os.path.join(ROOT, "assets", "listing", "src")
SS = 1.5  # supersampling of the finals (render SS x size, area-average down)
SAMPLES = 256

TRANSPORT_SPEED = 90.0  # AirdropConfig.Transport.SPEED
FORMATION = {"trail": 2.5, "offset": 70.0, "climb": 18.0}  # AirdropConfig.Transport FORMATION_*
STICK_SWING = [(6, -4), (-5, 7), (3, 5), (-7, -3), (5, 2), (-3, -6), (8, 1), (0, 0)]
STICK_JITTER = [(4, -9, 10), (-6, 5, -8), (3, -3, 14), (-2, 8, -4), (7, -6, 6), (-5, -5, -12), (2, 6, 5), (0, 0, 0)]


def formation_drop(lead, heading, t, t_wing, tank, wing_count=4, wing=True):
    """A two-ship formation mid-drop, by the game's rules: the lead
    (at `lead`, flying `heading`, level) has been dropping its stick of
    eight for `t` s; the wing (if `wing`) trails FORMATION.trail s behind,
    offset sideways (toward the outpost) and stepped up, `t_wing` s into its
    own stick; a tank rides its platform under the four-chute cluster at `tank`.
    Positions are Roblox studs; keyart_airdrop lays out each stick from its
    release point."""
    from mathutils import Vector

    d = Vector(heading).normalized()
    side = Vector((d.z, 0.0, -d.x))  # horizontal normal, toward +Z (the outpost) for a -X heading
    if side.z < 0:
        side = -side
    yaw = math.degrees(math.atan2(-d.x, -d.z))
    lead = Vector(lead)
    wing_pos = lead - d * (TRANSPORT_SPEED * FORMATION["trail"]) + side * FORMATION["offset"] + Vector((0, FORMATION["climb"], 0))

    def stick(pos, age, count, yaw0, tag, bank):
        release0 = pos - d * (TRANSPORT_SPEED * age + 34.0)
        return {
            "release0": tuple(release0), "dir": tuple(d), "count": count, "t": age, "yaw": yaw0,
            "swing": STICK_SWING, "jitter": STICK_JITTER,
            "transport": {"yaw": yaw, "bank": bank, "pitch": 1.0, "ramp": 1.0, "tag": tag},
        }

    return {
        "sticks": [stick(lead, t, 8, 15.0, "Lead", -4.0)] + ([stick(wing_pos, t_wing, wing_count, 50.0, "Wing", -3.0)] if wing else []),
        "transports": [],
        "cargo": [{"kind": "Tank", "pos": tuple(tank), "yaw": yaw - 40.0, "swing": (5, -4), "chute_yaw0": 12.0}],
        "ground_canopies": [],
    }


def vec_arg(name, default):
    v = arg(name)
    return tuple(float(c) for c in v.split(",")) if v else default


AIRBORNE = ("Lead_", "Wing_", "Trooper", "Cargo_")


def airborne_shadows_off(sc):
    """The drop casts no shadows: under the low sunset sun Cycles lays the
    canopies' shadows as dark blotches on the far canyon walls (~1,000
    studs from the camera), which read as dirt at thumbnail size."""
    import bpy

    n = 0
    for ob in bpy.data.objects:
        if ob.name.startswith(AIRBORNE):
            ob.visible_shadow = False
            n += 1
    log(f"airborne shadows off: {n} objects")


def icon_prepare(sc):
    """The icon: the drop without shadows, and without the wing transport,
    whose nose would sit cut at the frame edge (its stick is out of frame)."""
    import bpy

    airborne_shadows_off(sc)
    for ob in bpy.data.objects:
        if ob.name.startswith("Wing_"):
            ob.hide_render = True


def basin_drop():
    """The drop in the airdrop thumbnail and the icon (one moment, two
    cameras): a two-ship formation over the basin and a tank cluster below."""
    return formation_drop(
        vec_arg("--lead", (-50.0, 262.0, -650.0)), vec_arg("--heading", (-1.0, 0.0, -0.3)), float(arg("--t", 4.6)),
        float(arg("--t-wing", 1.3)), vec_arg("--tank", (-15.0, 140.0, -530.0)),
    )


SHOTS = {
    # The key art itself (keyart_scene "drop"), at 16:9 thumbnail size.
    "hero": {"cam": ks.CAMERAS["drop"], "airdrop": ks.AIRDROP, "size": (1920, 1080)},
    # From a flank ledge up at the drop: the formation, the stick trailing
    # the lead, the tank cluster, the lit right flank and far wall below.
    "airdrop": {
        "cam": {"pos": (-230.0, 110.0, -330.0), "look": (90.0, 200.0, -640.0), "vfov": 38.0, "yaw": -30.0, "pitch": 18.0, "focus": 0.5},
        "airdrop": basin_drop,
        "prepare": airborne_shadows_off,
        "size": (1920, 1080),
    },
    # Square, close on the same drop: the tank under its four canopies.
    "icon": {
        "cam": {"pos": (-140.0, 112.0, -400.0), "look": (-12.0, 182.0, -560.0), "vfov": 50.0, "yaw": -30.0, "pitch": 18.0, "focus": 0.5},
        "airdrop": basin_drop,
        "prepare": icon_prepare,
        "size": (1024, 1024),
    },
    # Square: over the gun's shoulder, the turret tracking a drop (an
    # alternative icon background).
    "icon_gun": {
        "cam": {"pos": (-5.1, 75.2, 22.9), "look": (3.0, 119.0, -300.0), "vfov": 56.7, "yaw": -14.9, "pitch": 20.8, "focus": 0.5},
        "airdrop": lambda: formation_drop((60.0, 262.0, -440.0), (-1.0, 0.0, -0.3), 1.6, 0.0, (-80.0, 160.0, -300.0), wing=False),
        "prepare": airborne_shadows_off,
        "size": (1024, 1024),
    },
}


def shot_spec(name):
    shot = SHOTS[name]
    spec = dict(shot["cam"])
    for key in ("pos", "look"):
        if arg(f"--{key}"):
            spec[key] = tuple(float(v) for v in arg(f"--{key}").split(","))
    for key in ("yaw", "pitch", "vfov"):
        if arg(f"--{key}"):
            spec[key] = float(arg(f"--{key}"))
    return shot, spec


def area_down(src_path, dst_path, size):
    """Area-average a render down to `size` (w, h) and write it."""
    px = ks.load_png(src_path)
    rgb = px[..., :3]
    small = ks.resample_axis(ks.resample_axis(rgb, size[0], 1), size[1], 0)
    out = np.ones((size[1], size[0], 4))
    out[..., :3] = small
    ks.write_png(dst_path, out)


def main():
    name = arg("--shot", "hero")
    shot, spec = shot_spec(name)
    layout = shot["airdrop"]() if callable(shot["airdrop"]) else shot["airdrop"]
    draft = bool(arg("--draft"))
    scale = float(arg("--res", 0.5 if draft else SS))
    size = (int(round(shot["size"][0] * scale)), int(round(shot["size"][1] * scale)))
    if arg("--sky"):
        ks.render_sky(spec, size, env=not os.path.exists(os.path.join(ks.CACHE, "sky_env.exr")))
        return
    samples = int(arg("--samples", 16 if draft else SAMPLES))
    if draft:
        d = os.path.join(OUT, "drafts")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, ".gitignore"), "w") as f:
            f.write("*\n")
        ks.render_scene(spec, layout, size, os.path.join(d, f"{name}_draft{arg('--tag', '')}.png"), samples, shot.get("prepare"))
        return
    big = os.path.join(ks.CACHE, f"listing_{name}_{size[0]}.png")
    ks.render_scene(spec, layout, size, big, samples, prepare=shot.get("prepare"))
    os.makedirs(OUT, exist_ok=True)
    dst = os.path.join(OUT, f"{name}_render.png")
    area_down(big, dst, shot["size"])
    log(f"wrote {dst} {shot['size'][0]}x{shot['size'][1]} (from {size[0]}x{size[1]}, {math.prod(size) / math.prod(shot['size']):.2f}x px)")


main()
