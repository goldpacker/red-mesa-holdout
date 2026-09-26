"""VfxDebris: small meshes thrown by explosions and dropped by jets (VFX-2).

Owner: VFX workstream (client effects clone these; see src/client/Effects).
Every piece is its own MeshPart laid out along X so the preview shows them
all; the client clones single parts and positions them itself.

  Shard1..4  charred, bent steel plate fragments (vehicle kills)
  Chunk1..2  red sandstone chunks (rock/cliff hits, cliff-side blasts)
  Clod1..2   packed sand/dirt clods (ground blasts on the basin floor)
  Bomb       finned enemy aerial bomb, charcoal with a red band (jet raids)
  Rocket     the emplacement's unguided rocket in flight (olive, tan warhead)

Sizes are nominal (~1 stud pieces, bomb 3.6 long); the client scales them.
"""
import math
import random

from mathutils import Vector, noise

from rmh import geo
from rmh.asset import Asset

ROCK = ["#5e2b1c", "#8a3f26", "#a2502e", "#6e3422", "#b8683f"]
SAND = ["#7a5230", "#9a6b48", "#b27a4c", "#8a5e3a", "#c9824f"]


def _shard(seed):
    rng = random.Random(seed)
    n = rng.randint(6, 8)
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n + rng.uniform(-0.25, 0.25)
        r = rng.uniform(0.35, 0.72)
        pts.append((math.cos(a) * r * 1.25, math.sin(a) * r * 0.9))
    bm = geo.prism(pts, rng.uniform(0.08, 0.14), bevel=0.02, segments=1)
    bend = rng.uniform(0.25, 0.55)
    twist = rng.uniform(-0.35, 0.35)
    off = Vector((seed * 3.1, seed * 1.7, 0.0))

    def warp(co):
        z = bend * co.x * co.x - 0.2 + twist * co.x * co.y
        j = noise.noise((co + off) * 3.0) * 0.05
        return Vector((j, j * 0.5, z + j))

    return geo.displace(bm, warp)


def _chunk(seed, flat):
    bm = geo.icosphere(0.5, subdiv=2)
    off = Vector((seed * 5.3, seed * 2.9, seed * 1.1))
    rng = random.Random(seed)
    sx, sy = rng.uniform(0.85, 1.25), rng.uniform(0.75, 1.1)

    def warp(co):
        d = co.normalized()
        big = noise.noise((co + off) * 1.6) * 0.18
        facet = noise.noise((co + off) * 4.0) * 0.06
        k = big + facet
        scaled = Vector((co.x * sx, co.y * sy, co.z * flat))
        return scaled - co + d * k

    return geo.displace(bm, warp)


def _bomb(a, part, x):
    a.material("bomb_body", base="charcoal", wear=0.45, dust=0.35)
    a.material("bomb_band", base="enemy_red", wear=0.5)
    body = [(0.0, 1.8), (0.14, 1.74), (0.3, 1.55), (0.41, 1.25), (0.45, 0.9), (0.45, -0.55),
            (0.36, -1.05), (0.2, -1.4), (0.2, -1.5), (0.0, -1.5)]
    bm = geo.lathe([(r, z) for r, z in reversed(body)], verts=16)
    part.add(bm, "bomb_body", at=(x, 0, 1.0), rot=(-90, 0, 0))  # lathe axis Z -> +Y (nose forward)
    band = geo.cylinder(0.465, 0.12, verts=16, bevel=0.01)
    part.add(band, "bomb_band", at=(x, 0.95, 1.0), rot=(90, 0, 0))
    for k in range(4):
        fin = geo.box(0.04, 0.55, 0.42, bevel=0.01)
        ang = 45 + 90 * k
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        part.add(fin, "bomb_body", at=(x + c * 0.4, -1.25, 1.0 + s * 0.4), rot=(0, ang, 0))
    ring = geo.tube(0.62, 0.57, 0.28, verts=16)
    part.add(ring, "bomb_body", at=(x, -1.3, 1.0), rot=(90, 0, 0))


def _rocket(a, part, x):
    """70 mm-class unguided rocket fired from the emplacement pod."""
    a.material("rocket_body", base="olive_dark", wear=0.3, dust=0.25)
    a.material("rocket_head", base="tan", wear=0.35, dust=0.3)
    body = [(0.0, 1.3), (0.06, 1.24), (0.13, 1.05), (0.17, 0.8), (0.17, 0.72)]
    tube = [(0.165, 0.72), (0.165, -1.2), (0.12, -1.3), (0.0, -1.3)]
    bm = geo.lathe([(r, z) for r, z in reversed(body)], verts=12)
    part.add(bm, "rocket_head", at=(x, 0, 1.0), rot=(-90, 0, 0))
    bm = geo.lathe([(r, z) for r, z in reversed(tube)], verts=12)
    part.add(bm, "rocket_body", at=(x, 0, 1.0), rot=(-90, 0, 0))
    for k in range(4):
        fin = geo.box(0.03, 0.3, 0.2, bevel=0.005)
        ang = 45 + 90 * k
        c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        part.add(fin, "rocket_body", at=(x + c * 0.24, -1.1, 1.0 + s * 0.24), rot=(0, ang, 0))


def build(**kw):
    a = Asset("VfxDebris", pivot=(0, 0, 0), tex_size=512)
    a.material("charred", kind="paint", color="#2b2623", under="#6a5a4c", under_metal=0.6,
               rough=0.75, wear=0.75, dust=0.25, grime=0.9)
    a.material("rock_chunk", kind="rock", colors=ROCK, strata=0.9, dust=0.4)
    a.material("clod", kind="rock", colors=SAND, strata=0.3, dust=0.7, crack_scale=1.2)
    x = -9.0
    for i in range(4):
        p = a.part(f"Shard{i + 1}", query=False, collide=False, material="CorrodedMetal", shadow=False)
        p.add(_shard(11 + i * 7), "charred", at=(x, 0, 1.0), rot=(0, 0, i * 40))
        x += 2.0
    for i in range(2):
        p = a.part(f"Chunk{i + 1}", query=False, collide=False, material="Sandstone", shadow=False)
        p.add(_chunk(31 + i * 5, 0.8), "rock_chunk", at=(x, 0, 1.0))
        x += 2.0
    for i in range(2):
        p = a.part(f"Clod{i + 1}", query=False, collide=False, material="Sand", shadow=False)
        p.add(_chunk(51 + i * 5, 0.65), "clod", at=(x, 0, 1.0))
        x += 2.0
    bomb = a.part("Bomb", query=False, collide=False, material="Metal", shadow=False)
    _bomb(a, bomb, x + 2.0)
    rocket = a.part("Rocket", query=False, collide=False, material="Metal", shadow=False)
    _rocket(a, rocket, x + 5.0)
    return a.finish(views=[("", (0.0, 1.6, 0.9))], **kw)
