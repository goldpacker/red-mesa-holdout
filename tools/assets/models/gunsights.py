"""Gunsights: the first-person sight meshes drawn in front of the camera
while aiming (HS-2, client/GunsightModels.luau).

Asset space = eye space: origin at the camera, Blender +Y = view direction
(Roblox -Z / camera LookVector), +Z = camera up, +X = camera right. The
client pivots each sub-model to `camera.CFrame`, so everything here sits
where it is seen. Sizes are designed for the gunsight FieldOfView of 32
degrees: the vertical half-view is tan(16 deg) = 0.2867 per stud of depth,
the GUI reticle (client/WeaponHud) stays drawn on top.

Models:
  IronSight   (MG)      Ring (front cartwheel ring sight on its stalk,
                        4 studs ahead), Rear (rear sight leaf at the
                        bottom edge of the view).
  RocketScope (rockets) Housing: rear face of the rocket sight box with the
                        round eyepiece window. The window is exactly the
                        GUI scope lens (0.62 x screen height), so the GUI's
                        reticle marks sit inside it.
  AASeeker    (missile) hooded display bezel of the IR seeker unit: Top,
                        Bottom, Left + Plate ("IR SEEKER"), Right + Controls
                        (lamp bezel, tone knob, toggle) + Lamp (Neon,
                        coloured by lock state). The client slides the
                        left/right pieces to the viewport edges, so the
                        corners clear the centred HUD panels at any aspect.

Same material language as the emplacement (worn OD paint over bare steel,
parkerized steel, rubber, stencils), at sight scale.
"""
import math

import bmesh
from mathutils import Vector

from rmh import geo, images
from rmh.asset import Asset

T = math.tan(math.radians(16))  # vertical half-view per stud of depth at FOV 32
LENS = 0.31 * 2 * T  # GUI rocket-scope lens radius (0.62 x screen height), in tan units
DUST = "#b3875f"
STENCIL = "#c9b98a"

IRON_D = 4.0  # front ring sight depth
REAR_D = 0.7  # rear sight leaf depth
ROCKET_D = 1.1  # rocket sight rear face depth
AA_D = 0.7  # seeker bezel depth


def facing(bm, rot=(90, 0, 0), at=(0, 0, 0)):
    """Primitive built around +Z, turned so its axis runs along +Y (the view)."""
    return geo.transform(bm, at, rot)


def plate_with_hole(w, h, e, r, depth, n=64):
    """Rounded-rectangle slab (superellipse exponent `e`) in the XZ plane,
    `depth` thick along Y (front face at y = 0, back at y = depth), with a
    round hole of radius `r` at the centre. Rims are bevelled."""
    bm = bmesh.new()
    outer = geo._superellipse_ring(w, h, 0.0, e, n)
    loops = []
    for y in (0.0, depth):
        o = [bm.verts.new((x, y, z)) for x, z in outer]
        i = [bm.verts.new((r * math.cos(geo.TAU * k / n), y, r * math.sin(geo.TAU * k / n))) for k in range(n)]
        loops.append((o, i))
    (o0, i0), (o1, i1) = loops
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new((o0[k], o0[j], i0[j], i0[k]))  # front face (toward the eye)
        bm.faces.new((o1[k], i1[k], i1[j], o1[j]))  # back face
        bm.faces.new((o0[k], o1[k], o1[j], o0[j]))  # outer wall
        bm.faces.new((i0[k], i0[j], i1[j], i1[k]))  # hole wall
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

    def ring(v):
        return "in" if abs(math.hypot(v.co.x, v.co.z) - r) < 1e-5 else "out"

    rims = [ed for ed in bm.edges if abs(ed.verts[0].co.y - ed.verts[1].co.y) < 1e-7 and ring(ed.verts[0]) == ring(ed.verts[1])]
    geo._bevel(bm, min(0.01, depth * 0.3), 2, rims)
    return bm


def knurled(r, h, teeth=24, depth=0.006):
    """Knurled knob along +Z (alternating radius around the rim)."""
    bm = bmesh.new()
    n = teeth * 2
    top, bot = [], []
    for k in range(n):
        a = geo.TAU * k / n
        rr = r if k % 2 == 0 else r - depth
        bot.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), -h / 2)))
        top.append(bm.verts.new((rr * math.cos(a), rr * math.sin(a), h / 2)))
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new((bot[k], bot[j], top[j], top[k]))
    bm.faces.new(top)
    bm.faces.new(list(reversed(bot)))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


def cull_back_faces(part, eye=(0.0, 0.0, 0.0), slack=0.15):
    """Drop faces that face away from the eye: they are never seen, and
    removing them frees atlas space for the faces that are."""
    bm = part.bm
    bm.normal_update()
    e = Vector(eye)
    dead = [f for f in bm.faces if f.normal.dot((e - f.calc_center_median()).normalized()) < -slack]
    bmesh.ops.delete(bm, geom=dead, context="FACES")


def stencil(a, text, center, height, color=STENCIL, wear=0.35, seed=1, normal=(0, -1, 0)):
    img = images.get("text", text=text, wear=wear, seed=seed)
    aspect = img.size[0] / img.size[1]
    a.decal(img, center, normal, (height * aspect, height, 0.02), up=(0, 0, 1), color=color)


def materials(a):
    worn = {"under": "#85867f", "under_metal": 0.75, "under_rough": 0.38, "chip_style": "blotch", "chip_scale": 22.0,
            "chip_bevel": 0.05, "fade": 0.35, "fade_color": "#7c7c5a", "patches": 0.4, "patch_color": "#5c5f3f",
            "dust_color": DUST, "grime": 0.4, "bevel": 0.015}
    photo = {"id": "green_metal_rust", "scale": 12.0, "color": 0.8, "sat": 0.45, "rough": 0.5, "height": 0.25}
    a.material("sight_od", kind="paint", color="#686a48", rough=0.6, photo=photo, wear=0.5, dust=0.45, **worn)
    a.material("sight_od_dark", kind="paint", color="#5a5c3d", rough=0.62, photo=photo, wear=0.45, dust=0.4,
               **dict(worn, patch_color="#4f5236", fade_color="#737455"))
    a.material("sight_steel", kind="metal", color="#3f3f3a", metal=0.55, rough=0.6, dust=0.3, grime=0.45, bevel=0.006,
               photo={"id": "green_metal_rust", "scale": 10.0, "rough": 0.6, "height": 0.3})
    a.material("sight_bare", kind="metal", color="#6a6862", rough=0.3, metal=1.0, dust=0.1, grime=0.4, bevel=0.006)
    a.material("sight_rubber", base="rubber", color="#1d1b17")
    a.material("sight_glass", base="glass", color="#1c2428", rough=0.06)
    a.material("sight_brass", kind="metal", color="#a88a48", rough=0.35, metal=1.0, dust=0.2, grime=0.35, bevel=0.004)


# --- MG: front ring sight + rear leaf -----------------------------------------

def iron_sight(a):
    ring = a.part("Ring", path="IronSight", tex="sights", query=False, shadow=False, material="Metal", smooth_angle=60)
    d = IRON_D
    r_out, r_in = 0.24, 0.128
    ring.add(facing(geo.torus(r_out, 0.0085, verts=72, ring_verts=6)), "sight_steel", at=(0, d, 0))
    ring.add(facing(geo.torus(r_in, 0.0065, verts=56, ring_verts=6)), "sight_steel", at=(0, d, 0))
    for k in range(4):  # spokes between the rings only; the centre stays clear
        ang = math.radians(90 * k)
        c, s = math.cos(ang), math.sin(ang)
        ring.add(geo.pipe_path([(c * (r_in + 0.004), d, s * (r_in + 0.004)), (c * (r_out - 0.004), d, s * (r_out - 0.004))], 0.0055, verts=6), "sight_steel")
    # Short lead ticks on the outer ring at 3 and 9 o'clock.
    for sx in (-1, 1):
        ring.add(geo.pipe_path([(sx * (r_out + 0.004), d, 0), (sx * (r_out + 0.05), d, 0)], 0.006, verts=6), "sight_steel")
    # Stalk down to the barrel clamp (below the view) with a welded collar.
    ring.add(geo.pipe_path([(0, d, -r_out - 0.004), (0, d + 0.02, -0.5), (0, d + 0.06, -1.5)], 0.011, verts=8), "sight_od")
    ring.add(geo.cylinder(0.018, 0.06, verts=10, bevel=0.005), "sight_od_dark", at=(0, d + 0.01, -0.36))
    ring.add(geo.box(0.12, 0.1, 0.14, bevel=0.015), "sight_od_dark", at=(0, d + 0.06, -1.5))

    rear = a.part("Rear", path="IronSight", tex="sights", query=False, shadow=False, material="Metal")
    d = REAR_D
    top = -0.205 * d  # leaf top edge at 72 % of the half-view below the aim point
    # Leaf with a U notch (aligns under the ring sight), on a hinge block.
    leaf = [(-0.042, top - 0.13), (0.042, top - 0.13), (0.042, top), (0.01, top), (0.01, top - 0.016), (0.005, top - 0.021),
            (-0.005, top - 0.021), (-0.01, top - 0.016), (-0.01, top), (-0.042, top)]
    rear.add(geo.transform(geo.prism(leaf, 0.012, bevel=0.003, segments=1), rot=(90, 0, 0)), "sight_od", at=(0, d, 0))
    rear.add(geo.box(0.13, 0.05, 0.035, bevel=0.008), "sight_od_dark", at=(0, d + 0.02, top - 0.14))
    rear.add(facing(geo.cylinder(0.014, 0.12, verts=10, bevel=0.003), rot=(0, 90, 0)), "sight_bare", at=(0, d + 0.012, top - 0.125))
    for sx in (-1, 1):  # protective ears
        ear = [(sx * 0.042, top - 0.13), (sx * 0.062, top - 0.13), (sx * 0.062, top - 0.03), (sx * 0.052, top - 0.014), (sx * 0.042, top - 0.02)]
        if sx < 0:
            ear = list(reversed(ear))
        rear.add(geo.transform(geo.prism(ear, 0.018, bevel=0.004, segments=1), rot=(90, 0, 0)), "sight_od_dark", at=(0, d + 0.004, 0))
        rear.add(facing(geo.cylinder(0.005, 0.006, verts=6, bevel=0.0)), "sight_bare", at=(sx * 0.03, d - 0.008, top - 0.045))
    stencil(a, "600", (-0.022, d - 0.008, top - 0.03), 0.01, wear=0.3, seed=81)
    cull_back_faces(ring, slack=0.4)
    cull_back_faces(rear)


# --- Rockets: sight box rear face with the eyepiece window --------------------------

def rocket_scope(a):
    h = a.part("Housing", path="RocketScope", tex="rocket", query=False, shadow=False, material="Metal", smooth_angle=50)
    d = ROCKET_D
    r = LENS * d  # window radius = GUI lens circle
    W, H = 0.66, 0.56
    h.add(plate_with_hole(W, H, 7.0, r + 0.004, 0.05, n=96), "sight_od", at=(0, d, 0))
    # Raised steel bezel ring around the window.
    h.add(facing(geo.tube(r + 0.034, r + 0.004, 0.03, verts=96)), "sight_steel", at=(0, d - 0.012, 0))
    h.add(facing(geo.torus(r + 0.036, 0.004, verts=96, ring_verts=6)), "sight_bare", at=(0, d - 0.026, 0))
    # Sun hood over the top of the window (140-degree arc, protrudes toward the eye).
    hood = geo.lathe([(r + 0.04, 0.0), (r + 0.042, 0.065), (r + 0.052, 0.065), (r + 0.05, 0.0)], verts=36, close_top=False,
                     close_bottom=False, angle=math.radians(120))
    geo.transform(hood, rot=(0, 0, 30))
    h.add(facing(hood), "sight_od_dark", at=(0, d - 0.002, 0))
    # Mount bracket under the box (runs out of the bottom of the view).
    h.add(geo.box(0.16, 0.2, 0.2, bevel=0.012), "sight_od_dark", at=(0, d + 0.08, -H / 2 - 0.07))
    h.add(geo.box(0.22, 0.04, 0.03, bevel=0.006), "sight_steel", at=(0, d - 0.01, -H / 2 + 0.005))
    # Bolts at the corners, a data plate, the range drum, the reticle-lamp
    # rheostat and the lens cap hanging on its strap.
    for sx in (-1, 1):
        for sz in (-1, 1):
            h.add(facing(geo.cylinder(0.013, 0.012, verts=6, bevel=0.002)), "sight_bare", at=(sx * 0.29, d - 0.006, sz * 0.222))
    h.add(geo.box(0.1, 0.006, 0.04, bevel=0.002), "sight_brass", at=(-0.21, d - 0.003, -0.215))
    for sx in (-1, 1):
        h.add(facing(geo.cylinder(0.004, 0.004, verts=6, bevel=0.0)), "sight_bare", at=(-0.21 + sx * 0.04, d - 0.007, -0.215))
    h.add(facing(knurled(0.05, 0.05, teeth=28, depth=0.004)), "sight_bare", at=(0.235, d - 0.03, -0.17))
    h.add(facing(geo.cylinder(0.056, 0.012, verts=32, bevel=0.003)), "sight_od_dark", at=(0.235, d - 0.006, -0.17))
    h.add(facing(geo.box(0.012, 0.05, 0.03, bevel=0.003)), "sight_od_dark", at=(0.235, d - 0.062, -0.17))
    h.add(facing(knurled(0.022, 0.035, teeth=16, depth=0.003)), "sight_rubber", at=(0.285, d - 0.02, 0.06))
    h.add(geo.pipe_path([(-r - 0.03, d - 0.02, 0.06), (-r - 0.06, d - 0.05, 0.0), (-r - 0.07, d - 0.07, -0.08)], 0.006, verts=5), "sight_rubber")
    h.add(geo.cylinder(0.075, 0.025, verts=32, bevel=0.008), "sight_rubber", at=(-r - 0.06, d - 0.09, -0.15), rot=(70, 0, -25))
    stencil(a, "RKT SIGHT", (-0.2, d - 0.006, 0.242), 0.02, wear=0.4, seed=83)
    stencil(a, "M27", (0.19, d - 0.006, 0.248), 0.018, wear=0.35, seed=84)
    for k, lab in enumerate(("2", "4", "6")):  # range marks round the drum, clear of the bezel
        ang = math.radians(90 - k * 55)
        stencil(a, lab, (0.235 + 0.077 * math.cos(ang), d - 0.006, -0.17 + 0.077 * math.sin(ang)), 0.015, wear=0.2, seed=86 + k)
    cull_back_faces(h)


# --- AA: IR seeker display bezel --------------------------------------------------

AA_SIDE_INNER = 0.195  # |x| of the side bars' inner edge (corner blocks); client/GunsightModels AA_SIDE_INNER


def aa_seeker(a):
    """Hooded display bezel. The HUD's panels are fixed-pixel and centred
    (score/wave panel 520 px, tips, boss bar), so everything readable sits in
    the two top corners on the `Left` / `Right` parts, which the client
    slides to the viewport edges: that keeps it beside the panels at any
    resolution and aspect (checked 1190x1080, 1280x720, 1366x768,
    1440x1080, 1920x1080). The centred `Top` / `Bottom` bars are plain."""
    d = AA_D
    top_edge = 0.24 * d  # lower edge of the top bar (84 % up the half-view, above the 13-degree lock-break cone)
    bot_edge = -0.25 * d  # upper edge of the bottom lip
    L = 1.3  # bars run past any sane aspect ratio

    top = a.part("Top", path="AASeeker", tex="sights", query=False, shadow=False, material="Metal")
    top.add(geo.box(L, 0.03, 0.09, bevel=0.008), "sight_od", at=(0, d + 0.015, top_edge + 0.045))
    top.add(geo.box(L, 0.2, 0.012, bevel=0.004), "sight_od_dark", at=(0, d - 0.08, top_edge + 0.092))  # visor
    top.add(geo.box(L, 0.012, 0.012, bevel=0.003), "sight_rubber", at=(0, d - 0.004, top_edge + 0.002))
    for x in (-0.36, -0.28, 0.28, 0.36):
        top.add(facing(geo.cylinder(0.007, 0.006, verts=6, bevel=0.0)), "sight_bare", at=(x, d - 0.002, top_edge + 0.03))

    bot = a.part("Bottom", path="AASeeker", tex="sights", query=False, shadow=False, material="Metal")
    bot.add(geo.box(L, 0.03, 0.09, bevel=0.008), "sight_od", at=(0, d + 0.015, bot_edge - 0.045))
    bot.add(geo.box(L, 0.012, 0.012, bevel=0.003), "sight_rubber", at=(0, d - 0.004, bot_edge - 0.002))
    for x in (-0.36, -0.2, 0.2, 0.36):
        bot.add(facing(geo.cylinder(0.007, 0.006, verts=6, bevel=0.0)), "sight_bare", at=(x, d - 0.002, bot_edge - 0.018))

    sides = {}
    for side, name in ((-1, "Left"), (1, "Right")):
        p = a.part(name, path="AASeeker", tex="sights", query=False, shadow=False, material="Metal")
        x = side * 0.2  # nominal; the client slides it to the viewport edge
        p.add(geo.box(0.05, 0.03, 0.6, bevel=0.008), "sight_od", at=(x + side * 0.025, d + 0.015, 0))
        p.add(geo.box(0.012, 0.012, 0.6, bevel=0.003), "sight_rubber", at=(x + side * 0.004, d - 0.004, 0))
        p.add(geo.box(0.012, 0.2, 0.6, bevel=0.004), "sight_od_dark", at=(x + side * 0.05, d - 0.08, 0))  # hood side
        for z in (-0.1, 0.0, 0.1):
            p.add(facing(geo.cylinder(0.007, 0.006, verts=6, bevel=0.0)), "sight_bare", at=(x + side * 0.022, d - 0.002, z))
        for zz in (top_edge + 0.02, bot_edge - 0.02):  # rubber corner blocks
            p.add(geo.box(0.06, 0.04, 0.06, bevel=0.014), "sight_rubber", at=(x + side * 0.025, d - 0.012, zz))
        sides[side] = p

    # The two corner pieces carry the only small lettering, so they get their
    # own 512 atlas ("labels", ~3000 px/stud): the text stays crisp at 1080p.
    # Top-left corner: riveted data plate with the unit name.
    left = a.part("Plate", path="AASeeker", tex="labels", query=False, shadow=False, material="Metal")
    th = 0.012
    tw = th * images.text_aspect("IR SEEKER")
    pw = tw + 0.022
    pz = top_edge + 0.014
    px = -AA_SIDE_INNER + pw / 2 + 0.002
    left.add(geo.box(pw, 0.012, 0.028, bevel=0.003), "sight_od_dark", at=(px, d - 0.008, pz))
    for sx in (-1, 1):
        left.add(facing(geo.cylinder(0.0028, 0.004, verts=6, bevel=0.0)), "sight_bare", at=(px + sx * (pw / 2 - 0.006), d - 0.015, pz))
    stencil(a, "IR SEEKER", (px, d - 0.016, pz), th, wear=0.2, seed=94)

    # Top-right corner: control box with the lock lamp (the Lamp part sits
    # in its bezel), tone knob and uncage toggle.
    right = a.part("Controls", path="AASeeker", tex="labels", query=False, shadow=False, material="Metal")
    cz = top_edge + 0.017
    lamp_x, knob_x, tog_x = AA_SIDE_INNER - 0.07, AA_SIDE_INNER - 0.04, AA_SIDE_INNER - 0.016
    right.add(geo.box(0.092, 0.02, 0.066, bevel=0.006), "sight_od_dark", at=(AA_SIDE_INNER - 0.046, d - 0.008, cz - 0.004))
    right.add(facing(geo.tube(0.016, 0.0105, 0.012, verts=24)), "sight_bare", at=(lamp_x, d - 0.022, cz))
    right.add(facing(geo.cylinder(0.0106, 0.004, verts=20, bevel=0.0)), "lamp_off", at=(lamp_x, d - 0.016, cz))
    right.add(facing(knurled(0.012, 0.016, teeth=14, depth=0.002)), "sight_rubber", at=(knob_x, d - 0.026, cz))
    right.add(facing(geo.cylinder(0.007, 0.01, verts=10, bevel=0.002)), "sight_bare", at=(tog_x, d - 0.022, cz))
    right.add(geo.pipe_path([(tog_x, d - 0.026, cz), (tog_x + 0.004, d - 0.05, cz + 0.012)], 0.0032, verts=6), "sight_bare")
    stencil(a, "LOCK", (lamp_x, d - 0.019, cz - 0.0215), 0.0075, wear=0.15, seed=91)
    stencil(a, "TONE", (knob_x, d - 0.019, cz - 0.0215), 0.0075, wear=0.15, seed=92)
    lamp = a.part("Lamp", path="AASeeker", neon=(0.49, 0.82, 0.31), query=False, shadow=False, transparency=0.2, material="Neon")
    lamp.add(facing(geo.cylinder(0.0098, 0.004, verts=20, bevel=0.0)), "lamp_off", at=(lamp_x, d - 0.02, cz))

    for p in (top, bot, sides[-1], sides[1], left, right):
        cull_back_faces(p)
    a.material("lamp_off", kind="flat", color="#2a1210", rough=0.2)


def build(**kw):
    a = Asset("Gunsights", pivot=(0, 0, 0), tex_size=1024)
    a.primary = None
    a.zmin = -100.0  # no ground-dust gradient: these hang in front of the eye
    a.meta["no_ground"] = True
    a.texture_group("sights", 1024)
    a.texture_group("rocket", 1024)
    a.texture_group("labels", 512)
    for path in ("IronSight", "RocketScope", "AASeeker"):
        a.pivot(path, (0, 0, 0))
    materials(a)
    iron_sight(a)
    rocket_scope(a)
    aa_seeker(a)
    iron = ["Ring", "Rear"]
    rocket = ["Housing"]
    aa = ["Top", "Bottom", "Left", "Right", "Plate", "Controls", "Lamp"]

    def eye(label, hide, res=(1190, 1080)):
        return {"label": label, "pos": (0, 0, 0), "look": (0, 10, 0), "fov": 32, "res": res, "hide": hide}

    views = [
        eye("_iron", rocket + aa),
        eye("_rocket", iron + aa),
        eye("_aa", iron + rocket),
        eye("_rocket_wide", iron + aa, (1920, 1080)),
        ("_all", (1.0, -0.6, 0.5)),
    ]
    return a.finish(views=views, **kw)
