"""Fireball: Mantaflow fire+smoke explosion, colour baked in.

Five fuel blobs (noise-textured, so the start is never a clean ball) burst
outward for a few frames, burn hot (white-yellow core, orange licks), cool to
dark red inside oily smoke that rolls and thins away. The camera is fitted to
the baked density bounds. The sheet runs ignition -> fade over the particle's
life (OneShot).
"""
import math
import os
import random

from vfxlib import fluid, scene

SIM_FRAMES = 76
FIRST = 5


def _sim_frame(t):
    return FIRST + round((SIM_FRAMES - FIRST) * t)


def _flows(rng):
    fluid.flow_sphere(0.26, (0.0, 0.0, 0.0), "BOTH", on_frames=(1, 4), fuel_amount=3.0,
                      temperature=3.0, density=1.0, surface_distance=0.2, volume_density=1.0,
                      use_initial_velocity=True, velocity_normal=4.0, velocity_random=2.5,
                      subframes=2)
    for k in range(5):
        a = k * 2.0 * math.pi / 5.0 + rng.uniform(-0.4, 0.4)
        loc = (math.cos(a) * 0.28, rng.uniform(-0.15, 0.15), math.sin(a) * 0.24 + 0.05)
        flow = fluid.flow_sphere(rng.uniform(0.14, 0.2), loc, "BOTH", on_frames=(1, rng.choice([2, 3, 4])),
                                 fuel_amount=2.5, temperature=2.5, density=1.0, surface_distance=0.15,
                                 volume_density=1.0, use_initial_velocity=True,
                                 velocity_normal=rng.uniform(4.0, 7.0), velocity_random=2.0, subframes=2)
        fluid.flow_texture(flow, scale=0.35)


def render(name, out_dir):
    sc = scene.setup(ortho=3.0, samples=64, ambient_strength=0.3, volume_bounces=2)
    scene.key_light(strength=3.0, rim=0.8)
    sc.render.fps = 24
    domain = fluid.gas_domain(
        os.path.join(out_dir, "sim"), size=3.6, location=(0, 0, 0.5), res=96, frames=SIM_FRAMES,
        alpha=0.0, beta=0.45, vorticity=0.35, burning_rate=0.35, flame_smoke=1.6,
        flame_vorticity=1.0, flame_ignition=1.25, flame_max_temp=2.0,
        use_dissolve_smoke=True, dissolve_speed=44, use_dissolve_smoke_log=True,
        timesteps_max=6, timesteps_min=1, use_noise=True, noise_scale=2, noise_strength=1.2,
    )
    _flows(random.Random(5))
    fluid.bake(domain)
    fluid.grid_stats(domain, [6, 12, 20, 30, 45])
    frames = [_sim_frame(i / 63.0) for i in range(64)]
    boxes = fluid.frame_boxes(domain, sorted(set(frames[::3] + [frames[-1]])), threshold=0.04)
    centres, size = fluid.tracking_camera(boxes, frames)
    sc.camera.data.ortho_scale = size
    mat = fluid.fire_smoke_material(
        smoke_density=30.0, smoke_albedo=0.1, flame_gain=20.0, flame_power=1.6,
        ramp=((0.0, (0.25, 0.02, 0.0)), (0.2, (0.9, 0.15, 0.01)), (0.45, (1.0, 0.35, 0.04)),
              (0.75, (1.0, 0.6, 0.15)), (1.0, (1.0, 0.85, 0.5))))
    domain.data.materials.append(mat)

    def setter(i, t):
        sc.frame_set(frames[i])
        sc.camera.location.x, sc.camera.location.z = centres[i]

    return scene.render_frames(out_dir, setter)
