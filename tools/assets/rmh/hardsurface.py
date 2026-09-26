"""Hard-surface kit (HS-3): high-poly detail for bakes and the stowage /
hardware pieces vehicles share.

High-poly detail (for texture groups declared with `high=...`, see
`Part.add(hp=...)` / `Part.detail(...)`):
    round_edges(bm, width)       rounded bevel on every hard edge (bake source)
    bolt(r, h) / bolt_row(...)   hex bolt heads with washers, rows of them
    rivet_row(...)               dome rivets
    weld(points, r)              rippled weld bead along a polyline
    grille_slats(...)            louvre slats inside a frame opening

Pieces (plain bmesh builders, low-poly game meshes, origin at their base):
    jerrycan, ammo_can, shovel, pickaxe, crowbar, periscope, tarp_roll,
    whip_antenna, rail(points), track_link, road_wheel, sprocket, tyre, rim

Helpers: stencil(a, text, ...) projects stencilled text with the right
aspect; `along_y(bm)` lays a +Z-built primitive along +Y.
Coordinates: Blender asset space, studs, +Z up, +Y forward.
"""
import math

import bmesh
from mathutils import Vector

from . import geo, images

TAU = math.pi * 2


# --- high-poly helpers ---------------------------------------------------------

def round_edges(bm, width, angle=28.0, segments=3):
    """Bevel every edge sharper than `angle` degrees into a rounded fillet
    (the high-poly copy of a hard-surface piece)."""
    limit = math.radians(angle)
    edges = [e for e in bm.edges if e.is_manifold and (e.calc_face_angle(0.0) or 0.0) > limit]
    if not edges:
        return bm
    shortest = min(e.calc_length() for e in edges)
    w = min(width, shortest * 0.45)
    if w <= 1e-4:
        return bm
    bmesh.ops.bevel(bm, geom=edges, offset=w, offset_type="OFFSET", segments=segments, profile=0.5,
                    affect="EDGES", clamp_overlap=True)
    return bm


def chamfer_edges(bm, pred, width, segments=1):
    """Bevel the edges for which `pred(edge)` is true (low-poly silhouette
    chamfers, e.g. the long top edges of a sponson)."""
    edges = [e for e in bm.edges if e.is_manifold and pred(e)]
    if edges:
        bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type="OFFSET", segments=segments, profile=0.5,
                        affect="EDGES", clamp_overlap=True)
    return bm


def plate_on_quad(corners, offset=0.2, thickness=0.12, inset=0.08):
    """Spaced-armour plate standing off a planar quad face (4 corners, CCW
    seen from outside): shrunk by `inset` (fraction), pushed `offset` out
    along the face normal, `thickness` thick. Returns bmesh."""
    c = [Vector(p) for p in corners]
    centre = sum(c, Vector()) / 4
    n = (c[1] - c[0]).cross(c[3] - c[0]).normalized()
    if n.dot(centre) < 0 and centre.length > 0:
        n = -n
    outer = [centre + (p - centre) * (1 - inset) + n * (offset + thickness) for p in c]
    inner = [centre + (p - centre) * (1 - inset) + n * offset for p in c]
    bm = bmesh.new()
    vo = [bm.verts.new(p) for p in outer]
    vi = [bm.verts.new(p) for p in inner]
    bm.faces.new(vo)
    bm.faces.new(list(reversed(vi)))
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((vi[i], vi[j], vo[j], vo[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def _frame(normal, up_hint=(0.0, 0.0, 1.0)):
    n = Vector(normal).normalized()
    u = Vector(up_hint)
    if abs(n.dot(u.normalized())) > 0.95:
        u = Vector((0.0, 1.0, 0.0)) if abs(n.y) < 0.95 else Vector((1.0, 0.0, 0.0))
    x = u.cross(n).normalized()
    y = n.cross(x).normalized()
    return x, y, n


def _place(bm, pos, normal, spin=0.0):
    """Orient a +Z-built piece so +Z follows `normal`, then move to `pos`."""
    x, y, n = _frame(normal)
    c, s = math.cos(spin), math.sin(spin)
    xr, yr = x * c + y * s, -x * s + y * c
    for v in bm.verts:
        co = v.co.copy()
        v.co = Vector(pos) + xr * co.x + yr * co.y + n * co.z
    return bm


def bolt(r=0.07, h=0.05, washer=True):
    """Hex bolt head (+ washer) standing on z = 0 along +Z."""
    bm = geo.cylinder(r, h, verts=6, bevel=min(0.012, r * 0.2), segments=1)
    geo.transform(bm, (0, 0, h / 2))
    if washer:
        w = geo.cylinder(r * 1.45, h * 0.3, verts=10, bevel=0.0)
        geo.transform(w, (0, 0, h * 0.15))
        _join(bm, w)
    return bm


def rivet(r=0.045):
    """Dome rivet head on z = 0."""
    bm = geo.sphere(r, segments=8, rings=4, scale=(1, 1, 0.55))
    for v in list(bm.verts):
        if v.co.z < -1e-5:
            v.co.z = 0.0
    return bm


def _join(dst, src):
    import bpy

    me = bpy.data.meshes.new("_hsj")
    src.to_mesh(me)
    src.free()
    dst.from_mesh(me)
    bpy.data.meshes.remove(me)
    return dst


def bolt_row(p0, p1, n, normal, r=0.07, h=0.05, head=bolt, **kw):
    """`n` bolt heads evenly from p0 to p1, standing on a surface facing `normal`."""
    out = bmesh.new()
    a, b = Vector(p0), Vector(p1)
    for i in range(n):
        t = 0.5 if n == 1 else i / (n - 1)
        piece = head(r, h, **kw) if head is bolt else head(r)
        _place(piece, a.lerp(b, t), normal, spin=0.4 * i)
        _join(out, piece)
    return out


def rivet_row(p0, p1, n, normal, r=0.045):
    return bolt_row(p0, p1, n, normal, r=r, head=rivet)


def weld(points, r=0.05, ripple=0.3, pitch=None, verts=6):
    """Weld bead: a tube along `points` whose radius ripples like laid
    beads (pitch ~ 1.3 r)."""
    pts = [Vector(p) for p in points]
    pitch = pitch or r * 1.3
    dense = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int((b - a).length / (pitch / 3)))
        dense += [a.lerp(b, (k + 1) / n) for k in range(n)]
    bm = bmesh.new()
    rings = []
    s = 0.0
    for i, p in enumerate(dense):
        if i:
            s += (p - dense[i - 1]).length
        d = (dense[min(i + 1, len(dense) - 1)] - dense[max(i - 1, 0)]).normalized()
        up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        side = d.cross(up).normalized()
        up2 = side.cross(d).normalized()
        rr = r * (1.0 - ripple * 0.5 + ripple * abs(math.sin(math.pi * s / pitch)))
        rings.append([bm.verts.new(p + (side * math.cos(TAU * k / verts) + up2 * math.sin(TAU * k / verts)) * rr) for k in range(verts)])
    for a, b in zip(rings, rings[1:]):
        for k in range(verts):
            j = (k + 1) % verts
            bm.faces.new((a[k], a[j], b[j], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def grille_slats(width, height, pitch=0.3, depth=0.14, angle=40.0, thick=0.035):
    """Louvre slats across an opening `width` (X) x `height` (Y), lying in
    the XY plane with their tops at z = 0 (drop into a recess)."""
    bm = bmesh.new()
    n = max(2, int(height / pitch))
    for i in range(n):
        y = -height / 2 + (i + 0.5) * height / n
        slat = geo.box(width, depth / math.cos(math.radians(angle)), thick, bevel=0.0)
        geo.transform(slat, (0, y, -depth / 2), rot=(angle, 0, 0))
        _join(bm, slat)
    return bm


# --- pieces --------------------------------------------------------------------

def along_y(bm, at=(0, 0, 0)):
    """Primitive built along +Z, laid along +Y (forward)."""
    return geo.transform(bm, at, rot=(-90, 0, 0))


def jerrycan(w=0.62, l=1.7, h=1.25, detail=True):
    """NATO-style jerrycan standing on z = 0, long side along Y: body with
    the recessed X panels, three carry handles and the spout on top."""
    bm = geo.box(w, l, h * 0.9, bevel=0.08, segments=2)
    geo.transform(bm, (0, 0, h * 0.45))
    if detail:
        for side in (-1, 1):
            # Raised X-rib panels on both flanks.
            for rot in (38, -38):
                rib = geo.box(0.04, l * 0.95, 0.07, bevel=0.0)
                geo.transform(rib, (side * (w / 2 + 0.01), 0, h * 0.45), rot=(rot, 0, 0))
                _join(bm, rib)
        rim = geo.box(w + 0.03, l + 0.03, 0.05, bevel=0.015, segments=1)
        geo.transform(rim, (0, 0, h * 0.9))
        _join(bm, rim)
    for k, y in enumerate((-l * 0.28, 0.0, l * 0.28)):
        hd = geo.pipe_path([(0, y - 0.13, h * 0.9), (0, y - 0.1, h * 1.02), (0, y + 0.1, h * 1.02), (0, y + 0.13, h * 0.9)], 0.03, verts=5)
        _join(bm, hd)
    spout = geo.cylinder(0.1, 0.14, verts=8, bevel=0.02, segments=1)
    geo.transform(spout, (0, l * 0.42, h * 0.95), rot=(-35, 0, 0))
    _join(bm, spout)
    return bm


def ammo_can(w=0.5, l=1.0, h=0.62):
    """Steel ammunition can on z = 0 with a lid rim, latch and handle."""
    bm = geo.box(w, l, h * 0.86, bevel=0.03, segments=1)
    geo.transform(bm, (0, 0, h * 0.43))
    lid = geo.box(w + 0.04, l + 0.04, h * 0.16, bevel=0.025, segments=1)
    geo.transform(lid, (0, 0, h * 0.9))
    _join(bm, lid)
    latch = geo.box(0.16, 0.08, 0.2, bevel=0.01, segments=1)
    geo.transform(latch, (0, l / 2 + 0.03, h * 0.8))
    _join(bm, latch)
    handle = geo.pipe_path([(0, -0.2, h), (0, -0.18, h + 0.07), (0, 0.18, h + 0.07), (0, 0.2, h)], 0.025, verts=4)
    _join(bm, handle)
    return bm


def shovel(length=3.2):
    """Entrenching shovel lying along +Y on z = 0: handle, D-grip, blade."""
    bm = geo.cylinder(0.07, length * 0.72, verts=6, bevel=0.0)
    along_y(bm, (0, -length * 0.1, 0.08))
    grip = geo.torus(0.14, 0.035, verts=8, ring_verts=4)
    geo.transform(grip, (0, -length * 0.5, 0.08), rot=(0, 90, 0))
    _join(bm, grip)
    blade = geo.tapered_box(0.62, 0.8, 0.05, top_scale=(1.0, 1.0), bevel=0.02, segments=1)
    geo.transform(blade, (0, length * 0.36, 0.06))
    tip = geo.prism([(-0.31, 0.0), (0.31, 0.0), (0.0, 0.28)], 0.05, bevel=0.0)
    geo.transform(tip, (0, length * 0.36 + 0.4, 0.06))
    _join(bm, blade)
    _join(bm, tip)
    return bm


def pickaxe(length=2.8):
    """Pick lying along +Y on z = 0: helve and a double-ended head."""
    bm = geo.cylinder(0.075, length, verts=6, bevel=0.0)
    along_y(bm, (0, 0, 0.09))
    head = geo.tapered_box(1.9, 0.14, 0.14, top_scale=(0.8, 1.0), bevel=0.02, segments=1)
    geo.transform(head, (0, length * 0.44, 0.1))
    _join(bm, head)
    for side in (-1, 1):
        tip = geo.cylinder(0.07, 0.35, verts=5, r_top=0.01, bevel=0.0)
        geo.transform(tip, (side * 1.1, length * 0.44, 0.1), rot=(0, side * 90, 0))
        _join(bm, tip)
    return bm


def crowbar(length=3.4):
    """Pry bar lying along +Y on z = 0, hooked end."""
    pts = [(0, -length / 2, 0.06), (0, length / 2 - 0.3, 0.06), (0, length / 2 - 0.05, 0.14), (0, length / 2 - 0.12, 0.3)]
    return geo.pipe_path(pts, 0.06, verts=6)


def periscope(w=0.42, d=0.3, h=0.26):
    """Vision block head on z = 0 (glass face toward +Y)."""
    bm = geo.tapered_box(w, d, h, top_scale=(0.94, 0.8), top_shift=(0, -0.03), bevel=0.03, segments=1)
    geo.transform(bm, (0, 0, h / 2))
    hood = geo.box(w + 0.06, 0.12, 0.05, bevel=0.01, segments=1)
    geo.transform(hood, (0, d / 2 - 0.02, h + 0.01))
    _join(bm, hood)
    return bm


def tarp_roll(length=3.0, r=0.32, straps=3):
    """Rolled tarpaulin along +X on z = 0 (sagging slightly) with straps."""
    bm = geo.cylinder(r, length, verts=10, bevel=0.1, segments=2)
    geo.transform(bm, (0, 0, r), rot=(0, 90, 0))
    for v in bm.verts:
        v.co.z -= 0.04 * (1 - (2 * v.co.x / length) ** 2) if abs(v.co.x) < length / 2 else 0.0
        v.co.y *= 1.0 + 0.06 * math.sin(v.co.x * 3.1)
    for i in range(straps):
        x = -length / 2 + (i + 0.5) * length / straps
        strap = geo.torus(r + 0.015, 0.025, verts=10, ring_verts=3)
        geo.transform(strap, (x, 0, r), rot=(0, 90, 0))
        _join(bm, strap)
    return bm


def whip_antenna(height=5.0, base_r=0.12):
    """Whip antenna on z = 0: spring base, mount, thin tapered whip."""
    bm = geo.cylinder(base_r, 0.3, verts=8, bevel=0.02, segments=1)
    geo.transform(bm, (0, 0, 0.15))
    spring = geo.cylinder(base_r * 0.6, 0.35, verts=6, bevel=0.0)
    geo.transform(spring, (0, 0, 0.45))
    _join(bm, spring)
    whip = geo.cylinder(0.03, height, verts=4, r_top=0.012, bevel=0.0)
    geo.transform(whip, (0, 0, 0.6 + height / 2))
    _join(bm, whip)
    return bm


def rail(points, r=0.045, feet=True, foot_h=0.25):
    """Hand rail along `points` (a polyline at rail height) with a
    stand-off foot at each end."""
    bm = geo.pipe_path(points, r, verts=6)
    if feet:
        for p in (points[0], points[-1]):
            f = geo.cylinder(r * 0.9, foot_h, verts=5, bevel=0.0)
            geo.transform(f, (p[0], p[1], p[2] - foot_h / 2))
            _join(bm, f)
    return bm


def track_link(width=2.2, pitch=0.65, thick=0.14):
    """One spare track shoe (+ grousers) lying flat on z = 0, width along X."""
    bm = geo.box(width, pitch * 0.9, thick, bevel=0.02, segments=1)
    geo.transform(bm, (0, 0, thick / 2))
    for dy in (-pitch * 0.22, pitch * 0.22):
        g = geo.box(width * 0.94, 0.08, 0.08, bevel=0.01, segments=1)
        geo.transform(g, (0, dy, thick + 0.04))
        _join(bm, g)
    for x in (-width / 2 - 0.04, width / 2 + 0.04):
        c = geo.cylinder(0.08, 0.12, verts=6, bevel=0.0)
        geo.transform(c, (x, 0, thick / 2), rot=(0, 90, 0))
        _join(bm, c)
    return bm


def road_wheel(r=1.2, w=0.5, verts=14, hub=True):
    """Tank road wheel about +Z (axle), outer face toward +Z, open at the
    back: rubber tyre band, dished steel disc, hub."""
    tyre = r * 0.84
    prof = [(tyre * 0.98, -w / 2), (r, -w / 2 + 0.05), (r, w / 2 - 0.05), (tyre, w / 2), (tyre * 0.96, w / 2 - 0.02),
            (r * 0.62, w / 2 - 0.1), (r * 0.36, w / 2 - 0.02), (r * 0.3, w / 2 + 0.06), (0.0, w / 2 + 0.08)]
    bm = geo.lathe(prof, verts=verts, close_top=False, close_bottom=False)
    if hub:
        for k in range(6):
            a = TAU * k / 6
            b = geo.cylinder(0.05, 0.06, verts=6, bevel=0.0)
            geo.transform(b, (math.cos(a) * r * 0.2, math.sin(a) * r * 0.2, w / 2 + 0.1))
            _join(bm, b)
    return bm


def sprocket(r=1.25, w=0.9, teeth=12, verts=24):
    """Drive sprocket about +Z: toothed ring and a dished hub."""
    prof = [(r * 0.8, -w / 2), (r * 0.8, w / 2), (r * 0.55, w / 2 + 0.02), (r * 0.3, w / 2 + 0.1), (0.0, w / 2 + 0.12)]
    bm = geo.lathe(prof, verts=verts, close_top=False, close_bottom=False)
    for t in range(teeth):
        a = TAU * t / teeth
        # Tooth built along +Z (radial), tangential along X, axial along Y.
        tooth = geo.tapered_box(0.3, 0.26, 0.28, top_scale=(0.55, 1.0), bevel=0.0)
        geo.transform(tooth, (0, 0, 0.14))
        _place(tooth, (math.cos(a) * r * 0.8, math.sin(a) * r * 0.8, 0.0), (math.cos(a), math.sin(a), 0.0))
        for v in tooth.verts:
            v.co.z = max(-w / 2 + 0.05, min(w / 2 - 0.05, v.co.z))
        _join(bm, tooth)
    return bm


def tyre(r=1.35, w=1.15, r_in=0.62, lugs=18, verts=20, lug_h=0.1):
    """Off-road tyre about +Z (axle): rounded carcass with sidewalls to the
    rim radius and chunky alternating lugs."""
    rc = r - lug_h
    prof = [(r_in, -w / 2), (rc - 0.28, -w / 2), (rc - 0.1, -w / 2 + 0.07), (rc, -w / 2 + 0.22),
            (rc, w / 2 - 0.22), (rc - 0.1, w / 2 - 0.07), (rc - 0.28, w / 2), (r_in, w / 2)]
    bm = geo.lathe(prof, verts=verts, close_top=False, close_bottom=False)
    for k in range(lugs):
        a = TAU * (k + 0.5) / lugs
        for row, off in enumerate((-w * 0.22, w * 0.22)):
            shift = 0.5 * (TAU / lugs) * (row - 0.5) * 0.6
            lug = geo.tapered_box(0.34, w * 0.4, lug_h + 0.04, top_scale=(0.85, 0.9), bevel=0.0)
            geo.transform(lug, (0, 0, (lug_h + 0.04) / 2))
            aa = a + shift
            _place(lug, (math.cos(aa) * (rc - 0.02), math.sin(aa) * (rc - 0.02), off + (0.08 if k % 2 else -0.08)),
                   (math.cos(aa), math.sin(aa), 0.0))
            _join(bm, lug)
    return bm


def rim(r=0.62, w=0.9, bolts=8, verts=16):
    """Beadlock wheel rim about +Z, outer face toward +Z: dished face,
    beadlock ring with bolts, hub cap."""
    prof = [(r, -w / 2), (r, w / 2 - 0.05), (r * 0.95, w / 2), (r * 0.7, w / 2 - 0.12), (r * 0.35, w / 2 - 0.08),
            (r * 0.3, w / 2 + 0.02), (0.0, w / 2 + 0.05)]
    bm = geo.lathe(prof, verts=verts, close_top=False, close_bottom=False)
    ring = geo.torus(r * 0.93, 0.04, verts=verts, ring_verts=4)
    geo.transform(ring, (0, 0, w / 2 + 0.01))
    _join(bm, ring)
    for k in range(bolts):
        a = TAU * k / bolts
        b = geo.cylinder(0.035, 0.05, verts=6, bevel=0.0)
        geo.transform(b, (math.cos(a) * r * 0.93, math.sin(a) * r * 0.93, w / 2 + 0.05))
        _join(bm, b)
    return bm


def headlight(r=0.3, depth=0.28):
    """Round headlight bucket facing +Y on its back plane (y = 0)."""
    prof = [(0.0, 0.0), (r * 0.8, 0.0), (r, depth * 0.6), (r * 1.04, depth), (r * 0.9, depth + 0.01), (0.0, depth + 0.03)]
    bm = geo.lathe(prof, verts=12, close_top=False, close_bottom=False)
    return geo.transform(bm, rot=(-90, 0, 0))


# --- markings ------------------------------------------------------------------

def stencil(a, text, center, normal, height, color="#b31c19", wear=0.35, up=(0, 0, 1), seed=1, chip=0.0, depth=0.3):
    """Stencilled text (our stroke font) projected onto whatever surface
    sits at `center`; `chip` (0..1) flakes the marking's paint."""
    img = images.get("text", text=text, wear=wear, seed=seed)
    aspect = img.size[0] / img.size[1]
    a.decal(img, center, normal, (height * aspect, height, depth), up=up, color=color, wear=chip, seed=seed)
