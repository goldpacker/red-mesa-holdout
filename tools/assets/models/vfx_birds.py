"""VfxBirds: low-poly birds for the weather-and-life layer (VFX-4).

Owner: VFX workstream (client/Birds clones these; nothing else uses them).
Untextured `flat` parts (no maps, no bake): a Roblox material + a colour;
seen against the sky at 150+ studs they are silhouettes.

  Vulture     one mesh in the soaring pose: broad wings held in a shallow
              V, five splayed primaries at each tip, short fan tail, small
              bald head. Wingspan ~8 studs (a large vulture). Its origin is
              its bounding-box centre.
  Crow        body (head, beak, fan tail) of a small dark bird for the
              flocks that scatter from explosions; ~1.6 studs long.
  CrowWingL/R one wing each, flat, from the shoulder outward (span ~1.6).
              Padded so each mesh's origin (bbox centre) is the shoulder
              joint: the client flaps them by rotating about their origin.

Blender axes: +Y forward (Roblox -Z), +Z up, wings along X.
"""
import math

from rmh import geo
from rmh.asset import Asset

VULTURE = (0.17, 0.14, 0.12)  # dark brown-black
CROW = (0.1, 0.1, 0.11)
FLAGS = dict(query=False, collide=False, shadow=False, material="Fabric")


def _poly(points, thickness):
    return geo.prism(points, thickness, bevel=0, segments=1)


def _mirror(points):
    return [(-x, y) for x, y in reversed(points)]


def _vulture_wing(sign):
    """Right wing (sign 1) or left (-1) with its splayed primaries."""
    main = [(0.2, 0.40), (1.2, 0.58), (2.2, 0.55), (2.9, 0.40), (3.3, 0.22), (3.36, -0.52),
            (2.6, -0.84), (1.4, -0.98), (0.2, -0.80)]
    pieces = [main]
    for k in range(5):
        base_y = 0.14 - k * 0.165
        ang = math.radians(10 - k * 9)
        length = 0.78 - k * 0.07
        w0, w1 = 0.075, 0.025
        cx, cy = 3.26, base_y
        dx, dy = math.cos(ang), math.sin(ang)
        nx, ny = -dy, dx
        tip = (cx + dx * length, cy + dy * length)
        pieces.append([(cx - nx * w0, cy - ny * w0), (tip[0] - nx * w1, tip[1] - ny * w1),
                       (tip[0] + nx * w1, tip[1] + ny * w1), (cx + nx * w0, cy + ny * w0)])
    out = []
    for pts in pieces:
        if sign < 0:
            pts = _mirror(pts)
        out.append(pts)
    return out


def _vulture(a, x):
    p = a.part("Vulture", flat=VULTURE, **FLAGS)
    body = geo.loft([
        (-1.05, 0.02, 0.02, 0.0, 2),
        (-0.9, 0.34, 0.24, 0.0, 2),
        (-0.3, 0.66, 0.5, 0.0, 2.2),
        (0.35, 0.62, 0.5, 0.02, 2.2),
        (0.8, 0.34, 0.32, 0.06, 2),
        (1.08, 0.24, 0.24, 0.1, 2),
        (1.3, 0.12, 0.12, 0.08, 2),
        (1.42, 0.02, 0.02, 0.06, 2),
    ], n=8)
    p.add(body, "feather", at=(x, 0, 0))
    tail = _poly([(-0.24, -0.8), (0.24, -0.8), (0.52, -1.9), (0.0, -2.02), (-0.52, -1.9)], 0.06)
    p.add(tail, "feather", at=(x, 0, 0.02))
    dihedral = 7  # soaring V
    for sign in (1, -1):
        for pts in _vulture_wing(sign):
            p.add(_poly(pts, 0.07), "feather", at=(x, 0, 0.08), rot=(0, -dihedral * sign, 0))


def _crow_wing(sign):
    pts = [(0.0, 0.2), (0.7, 0.27), (1.25, 0.16), (1.6, -0.06), (1.42, -0.3), (0.8, -0.38), (0.0, -0.24)]
    return pts if sign > 0 else _mirror(pts)


def _crow(a, x):
    p = a.part("Crow", flat=CROW, **FLAGS)
    body = geo.loft([
        (-0.5, 0.04, 0.03, 0.0, 2),
        (-0.34, 0.3, 0.24, 0.0, 2),
        (0.08, 0.38, 0.33, 0.0, 2.2),
        (0.44, 0.26, 0.26, 0.04, 2),
        (0.6, 0.15, 0.15, 0.05, 2),
        (0.74, 0.03, 0.03, 0.04, 2),
    ], n=8)
    p.add(body, "feather", at=(x, 0, 0))
    tail = _poly([(-0.1, -0.42), (0.1, -0.42), (0.2, -0.9), (0.0, -0.95), (-0.2, -0.9)], 0.04)
    p.add(tail, "feather", at=(x, 0, 0.02))
    shoulder = 0.12
    for sign, name in ((1, "CrowWingR"), (-1, "CrowWingL")):
        joint = (x + sign * shoulder, 0.05, 0.08)
        w = a.part(name, flat=CROW, joint=joint, **FLAGS)
        w.add(_poly(_crow_wing(sign), 0.04), "feather", at=joint)


def build(**kw):
    a = Asset("VfxBirds", pivot=(0, 0, 0), tex_size=64)
    a.material("feather", kind="flat", color="#2b2420", rough=0.9)
    _vulture(a, 0.0)
    _crow(a, 7.0)
    return a.finish(views=[("", (0.2, -0.6, 1.0)), ("_side", (1.0, 0.4, 0.35))], **kw)
