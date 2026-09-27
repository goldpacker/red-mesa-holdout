"""SupplyCrate: plywood air-drop crate on a skid with cargo straps and a
fluorescent marker panel, hanging from an orange/white cargo parachute.

Asset origin = crate bottom centre (ground contact). Parachute sub-model
pivot = crate top centre (where the risers meet the crate)."""
import math

from rmh import geo, images
from rmh.asset import Asset

W, D, H = 4.4, 3.6, 2.9  # crate body (X, Y, Z) in studs (~1.2 x 1.0 x 0.8 m)
SKID = 0.55
TOP = SKID + H
GORES = 12
R, DOME = 7.5, 4.6
HEM_Z = TOP + 10.5
CONFLUENCE = TOP + 2.6


def crate(a):
    a.material("crate_paint", base="olive", under="#8a6a45", under_metal=0.0, under_rough=0.8, wear=0.55, dust=0.6)
    a.material("bracket", base="olive_dark", wear=0.7)
    a.material("strap", kind="fabric", color="#c7741e", rough=0.8, wrinkle=0.15, weave=60.0, dust=0.4, bevel=0.02)
    a.material("marker_panel", kind="fabric", color="#ec5a26", rough=0.85, wrinkle=0.5, dust=0.35)
    a.material("skid_wood", base="wood_crate", color="#6e5638", grain="X")

    root = a.part("Root", query=True, collide=True, material="Wood")
    zc = SKID + H / 2
    root.add(geo.box(W, D, H, bevel=0.05), "crate_paint", at=(0, 0, zc))
    # Edge battens (cleats) around each face.
    t, p = 0.28, 0.08
    for sx in (-1, 1):
        for sy in (-1, 1):
            root.add(geo.box(t, t, H + 0.02, bevel=0.04), "crate_paint", at=(sx * (W / 2 - t / 2 + p), sy * (D / 2 - t / 2 + p), zc))
    for z in (SKID + t / 2, TOP - t / 2, zc):
        for sy in (-1, 1):
            root.add(geo.box(W - 2 * t + 2 * p, t, t, bevel=0.04), "crate_paint", at=(0, sy * (D / 2 + p / 2), z))
        if z != zc:
            for sx in (-1, 1):
                root.add(geo.box(t, D - 2 * t + 2 * p, t, bevel=0.04), "crate_paint", at=(sx * (W / 2 + p / 2), 0, z))
    # Lid cleats.
    for x in (-W / 2 + t / 2, 0, W / 2 - t / 2):
        root.add(geo.box(t, D, 0.1, bevel=0.03), "crate_paint", at=(x, 0, TOP + 0.05))
    # Steel corner brackets.
    for sx in (-1, 1):
        for sy in (-1, 1):
            for z in (SKID + 0.35, TOP - 0.35):
                root.add(geo.box(0.62, 0.05, 0.62, bevel=0.015), "bracket", at=(sx * (W / 2 - 0.2), sy * (D / 2 + p + 0.03), z))
                root.add(geo.box(0.05, 0.62, 0.62, bevel=0.015), "bracket", at=(sx * (W / 2 + p + 0.03), sy * (D / 2 - 0.2), z))
                for bx in (-0.15, 0.15):
                    root.add(geo.cylinder(0.05, 0.05, verts=6, bevel=0.0), "bracket", at=(sx * (W / 2 - 0.2) + bx, sy * (D / 2 + p + 0.06), z + bx), rot=(90, 0, 0))
    # Skid: three runners and deck boards.
    for y in (-D / 2 + 0.35, 0, D / 2 - 0.35):
        root.add(geo.box(W + 0.1, 0.5, SKID - 0.12, bevel=0.03), "skid_wood", at=(0, y, (SKID - 0.12) / 2))
    for i in range(6):
        x = -W / 2 + 0.35 + i * (W - 0.7) / 5
        root.add(geo.box(0.55, D + 0.1, 0.12, bevel=0.02), "skid_wood", at=(x, 0, SKID - 0.06))
    # Marker panel folded on the lid.
    root.add(geo.box(2.6, 1.9, 0.05, bevel=0.02), "marker_panel", at=(0, 0, TOP + 0.13))
    # Two cargo straps wrapped around the crate.
    for x in (-1.25, 1.25):
        root.add(geo.box(0.34, D + 0.34, 0.05, bevel=0.01), "strap", at=(x, 0, TOP + 0.19))
        for sy in (-1, 1):
            root.add(geo.box(0.34, 0.05, H + 0.35, bevel=0.01), "strap", at=(x, sy * (D / 2 + 0.17), SKID + H / 2 + 0.03))
        root.add(geo.box(0.44, 0.14, 0.5, bevel=0.03), "bracket", at=(x, -(D / 2 + 0.22), SKID + 1.0))
    # Stencils: up-arrows on the long faces, lot number on the ends.
    stencil = "#ded6bf"
    for sy in (-1, 1):
        a.decal(images.get("arrow"), (-0.9, sy * (D / 2 + p), zc + 0.1), (0, sy, 0), (1.2, 1.4, 0.4), color=stencil)
    for sx in (-1, 1):
        a.decal(images.get("digits", text="0417"), (sx * (W / 2 + p), 0, zc + 0.35), (sx, 0, 0), (2.0, 0.55, 0.4), color=stencil)
    a.decal(images.get("stripes", count=6, angle=45), (0.0, -(D / 2 + p), zc - 0.55), (0, -1, 0), (1.3, 0.35, 0.4), color="#1d1d1b")
    a.attach("Top", "Root", (0, 0, TOP + 0.2))


def parachute(a):
    a.material("canopy", kind="fabric", pattern="gores", count=GORES, color="#d9661f", color2="#e2dccb", rough=0.75, wrinkle=0.35, weave=20.0, dust=0.15, grime=0.3, decals=False)
    a.material("line", kind="fabric", color="#cfc6ae", rough=0.8, wrinkle=0.0, dust=0.1, grime=0.2, decals=False)
    a.material("riser", kind="fabric", color="#5c5a3a", rough=0.85, wrinkle=0.1, dust=0.2, decals=False)

    # Canopy: thin inflated dome with an apex vent, bulging between gores.
    steps = 11
    outer = []
    for i in range(steps):
        phi = math.radians(6 + (104 - 6) * i / (steps - 1))
        outer.append((R * math.sin(phi), DOME * math.cos(phi)))
    inner = [(r - 0.07, z - 0.05) for r, z in reversed(outer)]
    bm = geo.lathe(outer + inner + [outer[0]], verts=GORES * 4, close_top=False, close_bottom=False)

    def bulge(co):
        theta = math.atan2(co.y, co.x)
        r = math.hypot(co.x, co.y)
        k = abs(math.sin(theta * GORES / 2)) * min(1.0, r / R)
        from mathutils import Vector

        if r < 1e-6:
            return Vector((0, 0, 0))
        return Vector((co.x / r * k * 0.45, co.y / r * k * 0.45, k * 0.25))

    geo.displace(bm, bulge)
    canopy = a.part("Canopy", path="Parachute", tex="chute", query=False, collide=False, material="Fabric", smooth_angle=70)
    canopy.add(bm, "canopy", at=(0, 0, HEM_Z - DOME * math.cos(math.radians(104))))

    lines = a.part("Lines", path="Parachute", tex="chute", query=False, collide=False, material="Fabric", shadow=False)
    hem_r = R * math.sin(math.radians(104))
    hem_z = HEM_Z + 0.05
    for k in range(GORES):
        th = 2 * math.pi * k / GORES
        lines.add(geo.pipe_path([(hem_r * math.cos(th), hem_r * math.sin(th), hem_z), (0, 0, CONFLUENCE)], 0.035, verts=4), "line")
    lines.add(geo.cylinder(0.14, 0.4, verts=8, bevel=0.03), "riser", at=(0, 0, CONFLUENCE))
    for sx in (-1, 1):
        for sy in (-1, 1):
            lines.add(geo.pipe_path([(0, 0, CONFLUENCE), (sx * (W / 2 - 0.25), sy * (D / 2 - 0.25), TOP + 0.12)], 0.06, verts=4), "riser")


def build(**kw):
    a = Asset("SupplyCrate", pivot=(0, 0, 0), tex_size=1024)
    # RECLAIM-HS (QA-B item 14): the chute fabric has no metal; its metalness
    # map was all zero, so it is not baked or uploaded (metalness 0 either way).
    a.texture_group("chute", 512, metal=False)
    a.pivot("Parachute", (0, 0, TOP))
    crate(a)
    parachute(a)
    return a.finish(views=[("", (1.0, 1.3, 0.62)), ("_rear", (-1.1, -1.2, 0.7)), ("_crate", (0.9, 1.4, 0.5), ["Root"])], **kw)
