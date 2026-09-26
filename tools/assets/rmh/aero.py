"""Aircraft pieces (HS-4): lofted wings, fins, rotor blades, stores.

All builders return a new bmesh in local space (Blender asset space
conventions: +Y forward, +Z up, studs) and are plain low-poly game
meshes; high-poly detail comes from `Part.add(hp=...)` / `Part.detail`.

    span_loft(sections, axis="x")   wing / stabiliser / fin / blade between
                                     aerofoil-like sections along a span axis
    store(length, r, ...)            bomb / missile / drop tank body (lathe
                                     along +Y) with optional cruciform fins
    tube_cluster(r, n_rings, ...)    rocket-pod tube mouths (for detail())
"""
import math

import bmesh
from mathutils import Vector

from . import geo

TAU = math.pi * 2


def _ring(chord, thick, e, n):
    """Superellipse ring (chord along the first axis, thickness along the
    second), `e` = 2 is a lens/ellipse, higher is squarer."""
    pts = []
    for k in range(n):
        t = TAU * k / n
        c, s = math.cos(t), math.sin(t)
        pts.append((chord / 2 * math.copysign(abs(c) ** (2 / e), c), thick / 2 * math.copysign(abs(s) ** (2 / e), s)))
    return pts


def span_loft(sections, axis="x", n=10, cap_root=True, cap_tip=True):
    """Solid through aerofoil-like sections along a span axis.

    axis "x" (wings, stabilisers, blades): sections are
        (x, chord, thickness, y_centre, z_centre[, e])
    chord runs along Y, thickness along Z.
    axis "z" (vertical fins): sections are
        (z, chord, thickness, y_centre, x_centre[, e])
    chord along Y, thickness along X.
    Returns a closed, outward-facing shell."""
    bm = bmesh.new()
    rings = []
    for sec in sections:
        s, chord, thick, yc, oc = sec[:5]
        e = sec[5] if len(sec) > 5 else 2.2
        ring = []
        for u, w in _ring(max(chord, 1e-3), max(thick, 1e-3), e, n):
            if axis == "x":
                ring.append(bm.verts.new((s, yc + u, oc + w)))
            else:
                ring.append(bm.verts.new((oc + w, yc + u, s)))
        rings.append(ring)
    for a, b in zip(rings, rings[1:]):
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((a[k], a[j], b[j], b[k]))
    if cap_root:
        bm.faces.new(list(reversed(rings[0])))
    if cap_tip:
        bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    outward(bm)
    return bm


def outward(bm):
    """Make a closed shell face outward (signed volume > 0)."""
    bm.normal_update()
    vol = sum(f.calc_center_median().dot(f.normal) * f.calc_area() for f in bm.faces)
    if vol < 0:
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        bm.normal_update()
    return bm


def store(length, r, nose=0.35, tail=0.25, verts=12, fins=0, fin_span=None, fin_chord=None, fin_thick=0.03, blunt=0.0):
    """Streamlined store along +Y centred on the origin: bomb, missile,
    drop tank. `nose`/`tail` = fraction of the length that tapers,
    `blunt` = nose radius fraction (0 = pointed; missiles ~0.35 for a
    seeker dome). `fins` > 0 adds cruciform (X) tail fins."""
    h = length / 2
    ln, lt = length * nose, length * tail
    prof = [(0.0, -h), (r * 0.55, -h + 0.02), (r * 0.86, -h + lt * 0.45), (r, -h + lt), (r, h - ln)]
    for k in range(1, 5):
        t = k / 5
        prof.append((r * max(blunt, math.cos(t * math.pi / 2) ** 0.8), h - ln + ln * t))
    prof.append((r * blunt * 0.6 if blunt else 0.0, h))
    if blunt:
        prof.append((0.0, h + r * blunt * 0.25))
    bm = geo.lathe(prof, verts=verts)
    geo.transform(bm, rot=(-90, 0, 0))
    if fins:
        span = fin_span or r * 1.2  # exposed span beyond the body
        chord = fin_chord or length * 0.18
        tip = r * 0.7 + span
        for k in range(fins):
            ang = 45 + k * 360 / fins
            f = geo.prism([(r * 0.7, 0.0), (tip, -chord * 0.35), (tip, -chord * 0.9), (r * 0.7, -chord)], fin_thick, bevel=0.0)
            # prism: (x, y) plan, thickness along z -> fin in the XY plane
            geo.transform(f, at=(0, -h + chord + 0.02, 0), rot=(0, ang, 0))
            _join(bm, f)
    return bm


def _join(dst, src):
    import bpy

    me = bpy.data.meshes.new("_aj")
    src.to_mesh(me)
    src.free()
    dst.from_mesh(me)
    bpy.data.meshes.remove(me)
    return dst


def tube_cluster(r_tube, rings=2, pitch=None, depth=0.08, verts=8):
    """Rocket-pod front: tube mouths (short open rims + dark bores) on a
    hexagonal pattern in the XZ plane, facing +Y at y = 0. rings=2 -> 19
    tubes. For Part.detail (bake only)."""
    pitch = pitch or r_tube * 2.25
    centres = [(0.0, 0.0)]
    for ring in range(1, rings + 1):
        for side in range(6):
            a0 = math.radians(60 * side)
            a1 = math.radians(60 * (side + 1))
            p0 = Vector((math.cos(a0), math.sin(a0))) * ring * pitch
            p1 = Vector((math.cos(a1), math.sin(a1))) * ring * pitch
            for k in range(ring):
                p = p0.lerp(p1, k / ring)
                centres.append((p.x, p.y))
    bm = bmesh.new()
    for cx, cz in centres:
        t = geo.tube(r_tube, r_tube * 0.78, depth, verts=verts, bevel=0.0)
        geo.transform(t, at=(cx, depth / 2, cz), rot=(-90, 0, 0))
        _join(bm, t)
    return bm, centres
