"""SmokeDark and MissileTrail: greyscale volumetric sheets tinted by the emitter.

SmokeDark     dense, crisp-edged billowing smoke that roils and slowly grows,
              then thins out at the end of life. Strong top light and a dark
              underside so it keeps its form when tinted near-black (oily
              smoke from burning wrecks and explosion columns).
MissileTrail  one trail puff: starts small and dense, blooms into a wispy,
              turbulent cloud and dissolves. Emitted densely along a path.
"""
import math
import random

from mathutils import Vector

from vfxlib import scene, volume

ORTHO = 2.6


def render(name, out_dir):
    return {"SmokeDark": _smoke_dark, "MissileTrail": _missile_trail}[name](out_dir)


def _smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def _cluster(rng, count, dist, radius, depth=0.5):
    out = []
    for _ in range(count):
        theta = rng.uniform(0.0, 2.0 * math.pi)
        d = Vector((math.cos(theta), rng.uniform(-depth, depth), math.sin(theta))).normalized()
        out.append(dict(d=d, dist=rng.uniform(*dist), r0=rng.uniform(*radius),
                        spin=rng.uniform(-0.6, 0.6), rise=rng.uniform(0.0, 0.12)))
    return out


def _smoke_dark(out_dir):
    scene.setup(ortho=ORTHO, samples=96, ambient_strength=0.22, volume_bounces=1)
    scene.key_light(strength=4.2, rim=0.6)
    mat = volume.blob_material("Smoke", density=16.0, softness=0.12, distort=0.45,
                               billow_scale=2.5, billow_amp=1.1, billow_detail=7.0,
                               anisotropy=0.15, interior=0.15, interior_scale=3.5)
    rng = random.Random(31)
    core = [dict(d=Vector((0, 0, 0)), dist=0.0, r0=0.62, spin=0.0, rise=0.05)]
    specs = core + _cluster(rng, 16, (0.34, 0.5), (0.28, 0.4))
    blobs = [volume.add_blob(mat, f"Smoke{k}") for k in range(len(specs))]

    def setter(i, t):
        grow = 1.0 - (1.0 - t) ** 1.6
        volume.set_param(mat, "Softness", 0.12 + 0.45 * _smoothstep(0.45, 1.0, t))
        volume.set_param(mat, "Interior", 0.15 + 0.55 * _smoothstep(0.5, 1.0, t))
        dens = 1.0 - _smoothstep(0.55, 1.0, t)
        for obj, sp in zip(blobs, specs):
            ang = sp["spin"] * t
            d = Vector((sp["d"].x * math.cos(ang) - sp["d"].z * math.sin(ang), sp["d"].y,
                        sp["d"].x * math.sin(ang) + sp["d"].z * math.cos(ang)))
            loc = d * sp["dist"] * (0.72 + 0.4 * grow) + Vector((0, 0, sp["rise"] * t))
            volume.set_blob(obj, loc, sp["r0"] * (0.78 + 0.42 * grow), density=dens, time=0.6 * t)

    return scene.render_frames(out_dir, setter)


def _missile_trail(out_dir):
    scene.setup(ortho=ORTHO, samples=48, ambient_strength=0.4, volume_bounces=1)
    scene.key_light(strength=3.2, rim=1.0)
    mat = volume.blob_material("Trail", density=9.0, softness=0.25, distort=0.6,
                               billow_scale=3.0, billow_amp=1.0, billow_detail=6.0,
                               anisotropy=0.3, interior=0.3, interior_scale=4.5)
    rng = random.Random(47)
    specs = [dict(d=Vector((0, 0, 0)), dist=0.0, r0=0.55, spin=0.0, rise=0.0)]
    specs += _cluster(rng, 9, (0.3, 0.5), (0.3, 0.44), depth=0.7)
    blobs = [volume.add_blob(mat, f"Trail{k}") for k in range(len(specs))]

    def setter(i, t):
        grow = 1.0 - (1.0 - t) ** 3.0
        volume.set_param(mat, "Softness", 0.2 + 0.7 * t)
        volume.set_param(mat, "Interior", 0.25 + 0.6 * t)
        dens = (1.0 - t) ** 1.2
        for obj, sp in zip(blobs, specs):
            loc = sp["d"] * sp["dist"] * (0.25 + 0.85 * grow)
            volume.set_blob(obj, loc, sp["r0"] * (0.35 + 0.8 * grow), density=dens, time=0.7 * t)

    return scene.render_frames(out_dir, setter)
