"""Geometry primitives built with bmesh.

All functions return a *new* bmesh in local space. Units are studs.
Blender axes: +Z up, +Y = model forward (becomes Roblox -Z on export).
Combine them into parts with `Part.add(bm, mat, at=..., rot=...)`.
"""
import math

import bmesh
from mathutils import Matrix, Vector

TAU = math.pi * 2


def _bevel(bm, width, segments=2, edges=None, profile=0.5):
    if width <= 0:
        return bm
    geom = edges if edges is not None else list(bm.edges)
    if not geom:
        return bm
    bmesh.ops.bevel(
        bm,
        geom=geom,
        offset=width,
        offset_type="OFFSET",
        segments=segments,
        profile=profile,
        affect="EDGES",
        clamp_overlap=True,
    )
    return bm


def box(sx, sy, sz, bevel=0.06, segments=2):
    """Axis-aligned box centred on the origin."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz))
    return _bevel(bm, min(bevel, sx * 0.45, sy * 0.45, sz * 0.45), segments)


def tapered_box(sx, sy, sz, top_scale=(0.8, 0.8), top_shift=(0.0, 0.0), bevel=0.06, segments=2):
    """Box whose top face is scaled/shifted (sloped armour, housings)."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        x, y, z = v.co.x * sx, v.co.y * sy, v.co.z * sz
        if v.co.z > 0:
            x = x * top_scale[0] + top_shift[0]
            y = y * top_scale[1] + top_shift[1]
        v.co = Vector((x, y, z))
    return _bevel(bm, min(bevel, sx * 0.3, sy * 0.3, sz * 0.3), segments)


def cylinder(r, h, verts=16, r_top=None, bevel=0.04, segments=2, caps=True):
    """Cylinder/cone along +Z centred on the origin."""
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=caps,
        cap_tris=False,
        segments=verts,
        radius1=r,
        radius2=r if r_top is None else r_top,
        depth=h,
    )
    if bevel > 0 and caps:
        rim = [e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-6 and abs(abs(e.verts[0].co.z) - h / 2) < 1e-4]
        _bevel(bm, min(bevel, r * 0.4, h * 0.4), segments, rim)
    return bm


def tube(r_out, r_in, h, verts=16, bevel=0.02):
    """Hollow tube along +Z (barrels with a visible bore)."""
    bm = bmesh.new()
    top, bot = [], []
    for i in range(verts):
        a = TAU * i / verts
        c, s = math.cos(a), math.sin(a)
        top.append((bm.verts.new((c * r_out, s * r_out, h / 2)), bm.verts.new((c * r_in, s * r_in, h / 2))))
        bot.append((bm.verts.new((c * r_out, s * r_out, -h / 2)), bm.verts.new((c * r_in, s * r_in, -h / 2))))
    for i in range(verts):
        j = (i + 1) % verts
        bm.faces.new((bot[i][0], bot[j][0], top[j][0], top[i][0]))  # outer
        bm.faces.new((top[i][1], top[j][1], bot[j][1], bot[i][1]))  # inner
        bm.faces.new((top[i][0], top[j][0], top[j][1], top[i][1]))  # top rim
        bm.faces.new((bot[i][1], bot[j][1], bot[j][0], bot[i][0]))  # bottom rim
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def lathe(profile, verts=16, close_top=True, close_bottom=True, angle=TAU):
    """Revolve a list of (radius, z) points around +Z."""
    bm = bmesh.new()
    rings = []
    full = abs(angle - TAU) < 1e-6
    steps = verts if full else verts + 1
    for i in range(steps):
        a = angle * i / verts
        c, s = math.cos(a), math.sin(a)
        rings.append([bm.verts.new((c * r, s * r, z)) for r, z in profile])
    n = len(profile)
    seg = verts if full else verts
    for i in range(seg):
        a_ring = rings[i]
        b_ring = rings[(i + 1) % steps]
        for k in range(n - 1):
            quad = (a_ring[k], b_ring[k], b_ring[k + 1], a_ring[k + 1])
            if quad[0].co == quad[3].co or quad[1].co == quad[2].co:
                continue
            try:
                bm.faces.new(quad)
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    if full:
        if close_bottom and profile[0][0] > 1e-5:
            ring = [r[0] for r in rings]
            try:
                bm.faces.new(list(reversed(ring)))
            except ValueError:
                pass
        if close_top and profile[-1][0] > 1e-5:
            ring = [r[-1] for r in rings]
            try:
                bm.faces.new(ring)
            except ValueError:
                pass
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def prism(points, depth, bevel=0.05, segments=2):
    """Extrude a 2D polygon (x, y) along Z by `depth`, centred."""
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, -depth / 2)) for x, y in points]
    top = [bm.verts.new((x, y, depth / 2)) for x, y in points]
    n = len(points)
    bm.faces.new(list(reversed(bottom)))
    bm.faces.new(top)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _bevel(bm, bevel, segments)


def side_prism(profile_yz, width, bevel=0.06, segments=2):
    """Extrude a side profile given as (y, z) points along X (vehicle hulls)."""
    bm = prism(profile_yz, width, bevel=0, segments=segments)
    rot = Matrix.Rotation(math.pi / 2, 4, "Y")  # extrusion axis Z -> X
    # prism was built in (x=y_profile, y=z_profile, z=depth); remap to (depth, y, z)
    for v in bm.verts:
        py, pz, d = v.co.x, v.co.y, v.co.z
        v.co = Vector((d, py, pz))
    del rot
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return _bevel(bm, bevel, segments)


def sphere(r, segments=16, rings=10, scale=(1, 1, 1)):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segments, v_segments=rings, radius=r)
    for v in bm.verts:
        v.co = Vector((v.co.x * scale[0], v.co.y * scale[1], v.co.z * scale[2]))
    return bm


def icosphere(r, subdiv=2):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    return bm


def torus(r_major, r_minor, verts=16, ring_verts=8):
    profile = [(r_major + r_minor * math.cos(TAU * k / ring_verts), r_minor * math.sin(TAU * k / ring_verts)) for k in range(ring_verts + 1)]
    return lathe(profile, verts, close_top=False, close_bottom=False)


def pipe_path(points, r, verts=8):
    """Tube swept along a polyline (straps, cables, handles, rails)."""
    bm = bmesh.new()
    pts = [Vector(p) for p in points]
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            d = pts[1] - pts[0]
        elif i == len(pts) - 1:
            d = pts[-1] - pts[-2]
        else:
            d = (pts[i + 1] - pts[i - 1])
        d.normalize()
        up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        side = d.cross(up).normalized()
        up2 = side.cross(d).normalized()
        rings.append([bm.verts.new(p + (side * math.cos(TAU * k / verts) + up2 * math.sin(TAU * k / verts)) * r) for k in range(verts)])
    for i in range(len(rings) - 1):
        for k in range(verts):
            j = (k + 1) % verts
            bm.faces.new((rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def subdivide_smooth(bm, cuts=1, smooth=0.5, iterations=1):
    bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=cuts, use_grid_fill=True, smooth=smooth)
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm, verts=list(bm.verts), factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    return bm


def displace(bm, fn):
    """Move every vertex by fn(co) -> Vector offset."""
    for v in bm.verts:
        v.co = v.co + fn(v.co.copy())
    return bm


def transform(bm, at=(0, 0, 0), rot=(0, 0, 0), scale=None):
    m = Matrix.Translation(Vector(at)) @ euler_matrix(rot)
    if scale is not None:
        m = m @ Matrix.Diagonal(Vector((*scale, 1.0)))
    bmesh.ops.transform(bm, matrix=m, verts=bm.verts)
    return bm


def euler_matrix(rot):
    rx, ry, rz = (math.radians(a) for a in rot)
    return Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(ry, 4, "Y") @ Matrix.Rotation(rx, 4, "X")


def mirror_x(bm):
    """Return a mirrored copy across X (for symmetric pieces)."""
    out = bm.copy()
    bmesh.ops.scale(out, vec=(-1, 1, 1), verts=out.verts)
    bmesh.ops.reverse_faces(out, faces=out.faces)
    return out


def _superellipse_ring(w, h, zc, e, n, x0=0.0):
    pts = []
    for k in range(n):
        t = TAU * k / n
        c, s = math.cos(t), math.sin(t)
        x = w / 2 * math.copysign(abs(c) ** (2 / e), c)
        z = zc + h / 2 * math.copysign(abs(s) ** (2 / e), s)
        pts.append((x0 + x, z))
    return pts


def loft(sections, n=16, cap_start=True, cap_end=True):
    """Loft along +Y through superellipse cross-sections.

    sections: list of (y, width, height, z_centre, exponent[, x_centre]).
    exponent 2 = ellipse, higher = squarer. A width/height of ~0 makes a tip.
    """
    bm = bmesh.new()
    rings = []
    for sec in sections:
        y, w, h, zc, e = sec[:5]
        x0 = sec[5] if len(sec) > 5 else 0.0
        rings.append([bm.verts.new((x, y, z)) for x, z in _superellipse_ring(max(w, 1e-3), max(h, 1e-3), zc, e, n, x0)])
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(n):
            j = (k + 1) % n
            bm.faces.new((a[k], a[j], b[j], b[k]))
    if cap_start:
        bm.faces.new(list(reversed(rings[0])))
    if cap_end:
        bm.faces.new(rings[-1])
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def blade(length, root_chord, tip_chord, thickness, sweep=0.0):
    """Flat aerofoil blade/fin from the origin along +X (chord along Y)."""
    pts = [(0.0, -root_chord / 2), (length, -tip_chord / 2 + sweep), (length, tip_chord / 2 + sweep), (0.0, root_chord / 2)]
    return prism(pts, thickness, bevel=min(thickness * 0.4, 0.04), segments=1)
