"""DustPuff and SandKick: greyscale volumetric sheets tinted by the emitter.

DustPuff  - a soft burst of dust that billows out and thins away (centred).
SandKick  - a spurt of sand thrown up from an impact point that sits near the
            bottom of the frame (ground line 38.5% of the frame below centre),
            clumps rising and falling back, grains and a base dust ring.
"""
import math
import random

import bpy
from mathutils import Vector

from vfxlib import scene, volume

ORTHO = 2.6
GROUND = -1.0          # SandKick ground line (frame spans -1.3 .. 1.3)


def render(name, out_dir):
    return {"DustPuff": _dust_puff, "SandKick": _sand_kick}[name](out_dir)


def _ease_out(t, power):
    return 1.0 - (1.0 - t) ** power


def _smoothstep(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def _flat_dir(rng, depth=0.45):
    """Random unit vector, squashed in depth so the spread reads on screen."""
    theta = rng.uniform(0.0, 2.0 * math.pi)
    y = rng.uniform(-depth, depth)
    return Vector((math.cos(theta), y, math.sin(theta))).normalized()


def _dust_puff(out_dir):
    scene.setup(ortho=ORTHO, samples=48)
    scene.key_light(strength=3.2, rim=0.8)
    mat = volume.blob_material("Dust", density=7.0, softness=0.3, distort=0.55,
                               billow_scale=1.7, billow_amp=1.15, billow_detail=6.0,
                               anisotropy=0.3, interior=0.5, interior_scale=3.2)
    rng = random.Random(11)
    specs = [dict(d=Vector((0, 0, 0)), dist=0.0, r0=0.8)]
    for k in range(12):
        d = _flat_dir(rng)
        specs.append(dict(d=d, dist=rng.uniform(0.42, 0.56), r0=rng.uniform(0.42, 0.56)))
    blobs = [volume.add_blob(mat, f"Dust{k}") for k in range(len(specs))]

    def setter(i, t):
        grow = _ease_out(t, 2.4)
        fade = (1.0 - t) ** 1.25 * (0.6 + 0.4 * _smoothstep(0.0, 0.05, t))
        volume.set_param(mat, "Softness", 0.22 + 0.5 * t)
        volume.set_param(mat, "Interior", 0.35 + 0.5 * t)
        for obj, sp in zip(blobs, specs):
            loc = sp["d"] * sp["dist"] * (0.2 + 0.8 * grow) + Vector((0, 0, 0.05 * t))
            radius = sp["r0"] * (0.5 + 0.62 * grow)
            volume.set_blob(obj, loc, radius, density=fade, time=0.45 * t)

    return scene.render_frames(out_dir, setter)


def _grain_material():
    mat = bpy.data.materials.new("Grain")
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    bsdf = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.75, 0.75, 0.75, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.9
    return mat


def _grain_mesh():
    import bmesh
    mesh = bpy.data.meshes.new("Grain")
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(_grain_material())
    return mesh


def _clamped_gauss(rng, sigma, limit):
    return max(-limit, min(limit, rng.gauss(0.0, sigma)))


def _ballistic(v0, t, gravity, drag):
    """Position after t with linear drag k: x = v0 (1 - e^-kt) / k, gravity on z."""
    k = drag
    e = math.exp(-k * t)
    x = v0.x * (1 - e) / k
    y = v0.y * (1 - e) / k
    z = v0.z * (1 - e) / k - gravity / k * (t - (1 - e) / k)
    return Vector((x, y, z))


def _sand_kick(out_dir):
    scene.setup(ortho=ORTHO, samples=48)
    scene.key_light(strength=3.2, rim=0.8)
    mat = volume.blob_material("Sand", density=8.0, softness=0.4, distort=0.7,
                               billow_scale=2.6, billow_amp=1.1, billow_detail=5.0,
                               anisotropy=0.25, interior=0.35, interior_scale=4.0)
    rng = random.Random(23)
    origin = Vector((0.0, 0.0, GROUND))
    clumps = []
    for _ in range(38):
        v0 = Vector((_clamped_gauss(rng, 0.35, 0.9), _clamped_gauss(rng, 0.2, 0.5),
                     rng.uniform(4.2, 9.2)))
        clumps.append(dict(v0=v0, r0=rng.uniform(0.06, 0.09), r1=rng.uniform(0.13, 0.24),
                           delay=rng.uniform(0.0, 0.1)))
    ring = [dict(d=Vector((math.cos(a), 0.3 * math.sin(a), 0.0)), dist=rng.uniform(0.28, 0.45),
                 r1=rng.uniform(0.28, 0.36))
            for a in [k * 2 * math.pi / 7 + rng.uniform(-0.3, 0.3) for k in range(7)]]
    clump_objs = [volume.add_blob(mat, f"Clump{k}") for k in range(len(clumps))]
    ring_objs = [volume.add_blob(mat, f"Ring{k}") for k in range(len(ring))]

    grain_mesh = _grain_mesh()
    grains = []
    for k in range(160):
        v0 = Vector((_clamped_gauss(rng, 0.6, 1.4), _clamped_gauss(rng, 0.3, 0.6),
                     rng.uniform(4.5, 9.0)))
        obj = bpy.data.objects.new(f"Grain{k}", grain_mesh)
        bpy.context.scene.collection.objects.link(obj)
        grains.append((obj, v0, rng.uniform(0.008, 0.016)))

    gravity, drag = 16.0, 1.2

    def setter(i, t):
        for obj, c in zip(clump_objs, clumps):
            tau = max(t - c["delay"], 0.0)
            pos = origin + _ballistic(c["v0"], tau, gravity, drag)
            pos.z = max(pos.z, GROUND + 0.08)
            radius = c["r0"] + (c["r1"] - c["r0"]) * _ease_out(min(tau / 0.8, 1.0), 1.6)
            dens = 1.0 - _smoothstep(0.35, 1.0, t)
            volume.set_blob(obj, pos, radius, density=dens, time=0.5 * t)
        for obj, rg in zip(ring_objs, ring):
            grow = _ease_out(t, 2.2)
            pos = origin + rg["d"] * rg["dist"] * (0.15 + 0.85 * grow) + Vector((0, 0, 0.1 + 0.12 * grow))
            dens = 0.45 * (1.0 - t) ** 1.2 * (0.4 + 0.6 * _smoothstep(0.0, 0.08, t))
            volume.set_blob(obj, pos, rg["r1"] * (0.35 + 0.65 * grow), density=dens, time=0.5 * t)
        for obj, v0, size in grains:
            pos = origin + _ballistic(v0, t * 0.95, gravity, 0.6)
            obj.location = pos
            obj.scale = (size, size, size)
            obj.hide_render = pos.z < GROUND or t > 0.9

    return scene.render_frames(out_dir, setter)
