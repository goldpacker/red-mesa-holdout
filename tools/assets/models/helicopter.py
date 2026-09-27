"""Helicopter: enemy tandem-seat attack helicopter (original design).
Dark gunmetal with a red tail band and fin tip, red nose number and the
emblem on the boom.

Asset origin = centre of mass (under the mast). Rotor diameter 40 studs.
Root = airframe (fuselage, sponsons, canopies, engines, stub wings with
rocket pods and missile racks, chin gun, sensor turret, tail); MainRotor
(4 blades, origin = hub, spins about Y); TailRotor (origin = hub, spins
about X); attachments RocketMuzzleL / RocketMuzzleR (pod fronts),
Searchlight (chin, looking forward/down), GunMuzzle (chin cannon),
NavLightL / NavLightR (wing-tip pods, looking outboard).

HS-4 hard-surface pass: flat-paned stepped canopies with baked frames,
armoured cheek sponsons, engine nacelles with mesh dust screens and
IR-suppressed exhausts (soot down the boom), cooling grilles, faceted
sensor turret, chin cannon with ammo chute, pylons with 19-tube rocket
pods and four finned missiles a side, wing-tip countermeasure pods, wire
cutters, antennas, pitots, trailing-arm gear, a tail with driveshaft
cover, stabilator and tail-rotor gearbox. The airframe is baked from a
high-poly copy (rounded edges, rivets, access panels) with convex-edge
chips, AO grime, oil streaks, rotor-wash dust low on the fuselage, soot
at the exhausts, gun and pod ends, and chipped red markings; rotors,
gear and small hardware are trim parts on the shared TrimEnemy sheet
(parts MainRotor, TailRotor, HeliKit). Root keeps its pre-HS-4 bounding
box exactly (= hit box and the size Dress/VehicleFx read): `HIT` below,
enforced by the build.
"""
import math

from rmh import aero, geo, hardsurface as hs, images, trim
from rmh.asset import Asset, rb_box

# RECLAIM-HS (QA-B item 5): the uploaded maps are capped at 512² (rmh/game_maps.py);
# the bake, .blend, previews and exported full-size PNGs stay 1024². At its nearest
# play range (300 studs, gunsight zoom) the 512² maps still give >= 2.1 texels per screen
# pixel, so the GPU was already sampling mip >= 1 of the 1024² maps: no visible change.
GAME_PX = 512

# Contract hit box: Roblox (centre, size) of the pre-HS-4 Root.
HIT = {"Root": ((0.0, 1.5977, 4.1462), (12.1778, 10.5955, 37.4925))}
HUB = (0.0, 0.0, 4.9)
ROTOR_R = 20.0
TAIL_HUB = (0.95, -21.3, 4.7)
TAIL_R = 2.7
POD_X, POD_Y, POD_Z = 5.4, 0.2, -1.25
RACK_X = 3.3
PAINT = "#3e4247"
DARK = "#2b2d31"
RED = "#b01c18"
DUST = "#a4876a"

# Fuselage stations (y, width, height, z centre, squareness).
FUSE = [
    (13.95, 1.2, 1.4, -0.5, 2.6),
    (13.4, 1.7, 2.2, -0.45, 2.8),
    (12.2, 2.2, 2.9, -0.3, 3.2),
    (9.5, 2.5, 3.4, -0.1, 3.6),
    (6.0, 2.8, 3.9, 0.2, 3.8),
    (2.0, 3.3, 4.2, 0.35, 4.0),
    (-2.5, 3.3, 4.0, 0.5, 4.0),
    (-5.0, 2.5, 3.0, 0.95, 3.4),
    (-7.5, 1.5, 1.8, 1.4, 2.6),
    (-17.5, 1.0, 1.25, 1.75, 2.4),
    (-21.8, 0.9, 1.1, 1.95, 2.4),
]
NACELLE_X = 1.55
# IR-suppressed exhaust ducts: centre and rotation per side; the outlet is
# the duct's aft face (local y = -0.86).
DUCT_LEN = 1.7


def duct_frame(s):
    return (s * (NACELLE_X + 0.35), -4.55, 2.75), (18, 0, s * 28)


def _outlet(s):
    from mathutils import Vector

    at, rot = duct_frame(s)
    return tuple(Vector(at) + geo.euler_matrix(rot).to_3x3() @ Vector((0, -DUCT_LEN / 2 - 0.01, 0)))


EXHAUSTS = [_outlet(s) for s in (-1, 1)]

up_light = lambda f: 0.4 if f.normal.z > 0.6 else 1.0  # noqa: E731  tops are seldom seen from the mesa
hidden_down = lambda f: 0.12 if f.normal.z < -0.5 else 1.0  # noqa: E731
belly = lambda f: 0.35 if f.normal.z < -0.5 else 1.0  # noqa: E731


def materials(a):
    photo = {"id": "green_metal_rust", "scale": 5.0, "color": 0.35, "sat": 0.08, "rough": 0.35, "height": 0.15}
    soot = [{"pos": p, "dir": (math.copysign(0.55, p[0]), -0.55, -0.6), "radius": 0.5, "length": 3.2, "spread": 0.5, "strength": 0.9}
            for p in EXHAUSTS]
    soot += [{"pos": (math.copysign(1.2, p[0]), -8.0, 2.0), "dir": (0, -1, 0.05), "radius": 0.45, "length": 6.0, "spread": 0.35, "strength": 0.45}
             for p in EXHAUSTS]
    soot.append({"pos": (0, 14.15, -2.05), "dir": (0, -1, 0.05), "radius": 0.28, "length": 2.2, "spread": 0.1, "strength": 0.85})
    for s in (-1, 1):  # rocket motors blow back out of the pod ends
        soot.append({"pos": (s * POD_X, POD_Y - 1.7, POD_Z), "dir": (0, -1, 0.1), "radius": 0.6, "length": 1.6, "spread": 0.25, "strength": 0.7})
        soot.append({"pos": (s * POD_X, POD_Y + 1.8, POD_Z), "dir": (0, -1, 0), "radius": 0.55, "length": 0.5, "spread": 0.1, "strength": 0.5})
    panels = [  # re-sprayed / replaced panels in slightly different greys
        {"lo": (-2, 5.2, -2.5), "hi": (2, 7.4, -0.4), "color": "#464a4f"},
        {"lo": (-3, -3.6, 1.8), "hi": (3, -1.2, 4.0), "color": "#373b3f"},
        {"lo": (0.2, -13.0, 0.8), "hi": (2, -9.6, 3), "color": "#474b50"},
        {"lo": (-6.2, -2.0, -1.2), "hi": (-3.8, 2.0, 0.6), "color": "#393d41"},
    ]
    marks = panels + [
        {"lo": (-2, -15.2, -1), "hi": (2, -14.2, 4), "color": RED},  # tail band
        {"lo": (-1, -23.5, 6.05), "hi": (1, -19, 7.2), "color": RED},  # fin tip
    ]
    paint = dict(kind="paint", color=PAINT, rough=0.48, wear=0.35, under="#8b8c89", under_metal=0.0, under_rough=0.35,
                 chip_style="blotch", chip_scale=6.0, chip_bevel=0.08, ring=0.2, ring_color="#24201c",
                 edge_convex=True, polish=0.2, grime=0.55, grime_color="#1d1a17", streaks=0.55, dust=0.35, dust_up=0.08,
                 dust_height=2.9, dust_color=DUST, rough_breakup=0.35, photo=photo, fade=0.2, fade_color="#5d6166",
                 panels=(1.8, 2.4, 1.6), panel_width=0.05, bevel=0.05)
    a.material("body", **paint, marks=marks, soot=soot)
    a.material("body_dark", **dict(paint, color=DARK, photo=None, fade=0.1), soot=soot)
    a.material("canopy", kind="flat", color="#141b20", rough=0.06, metal=0.0, dust=0.3, dust_up=0.5, grime=0.25,
               dust_cavity=0.5, dust_cavity_distance=0.25, dust_cavity_range=(0.1, 0.5), dust_color=DUST)
    a.material("cavity", kind="flat", color="#0e0f10", rough=0.8, grime=0.0)
    a.material("steel", kind="metal", color="#46484a", rough=0.42, metal=0.9, dust=0.2, grime=0.7, edge_convex=True, polish=0.5)
    a.material("weapon", kind="paint", color="#3d4035", rough=0.55, wear=0.4, under="#7d7e79", chip_style="blotch", chip_scale=7.0,
               edge_convex=True, grime=0.5, dust=0.3, dust_up=0.1, dust_height=2.9, dust_color=DUST, rough_breakup=0.25,
               marks=[{"lo": (-8, 1.05, -3), "hi": (8, 1.3, 0), "color": "#b8952a"},
                      {"lo": (-8, -1.25, -3), "hi": (8, -1.05, 0), "color": "#b8952a"}], soot=soot)
    a.material("seeker", kind="flat", color="#1e2a30", rough=0.1, metal=0.0, grime=0.2)


# --- airframe ------------------------------------------------------------------------

def fuselage(a):
    lo, hi = rb_box(*HIT["Root"])
    p = a.part("Root", tex="body", material="Metal", smooth_angle=50, hitbox=(lo, hi))
    p.add(geo.loft(FUSE, n=20), "body", texel=up_light)
    # Armoured cheek sponsons (avionics bays) along the lower sides.
    prof = [(-3.4, -1.25), (5.4, -1.25), (7.3, -0.55), (7.3, 0.05), (6.4, 0.6), (-2.6, 0.6), (-3.6, 0.05)]
    for s in (-1, 1):
        sp = geo.side_prism(prof, 1.2, bevel=0.0)
        hs.chamfer_edges(sp, lambda e: all(abs(v.co.x) > 0.55 for v in e.verts)
                         and abs((e.verts[0].co - e.verts[1].co).normalized().y) > 0.8, 0.18)
        p.add(sp, "body", at=(s * 1.8, 0, 0), texel=belly)
        # Access panels and fasteners (bake only).
        for y0, y1 in ((-2.4, 0.6), (1.2, 4.6)):
            p.detail(geo.box(0.03, y1 - y0 - 0.3, 1.1, bevel=0.012, segments=1), "body", at=(s * 2.41, (y0 + y1) / 2, -0.28))
            p.detail(hs.rivet_row((s * 2.43, y0, 0.32), (s * 2.43, y1, 0.32), 9, (s, 0, 0), r=0.035), "body")
            p.detail(hs.rivet_row((s * 2.43, y0, -0.9), (s * 2.43, y1, -0.9), 9, (s, 0, 0), r=0.035), "body")
    # Faceted, stepped tandem canopies (gunner front, pilot raised behind).
    front_lo = [(-1.15, 8.2), (1.15, 8.2), (1.2, 10.4), (0.82, 12.3), (-0.82, 12.3), (-1.2, 10.4)]
    front_hi = [(-0.72, 8.35), (0.72, 8.35), (0.76, 10.0), (0.46, 10.95), (-0.46, 10.95), (-0.76, 10.0)]
    rear_lo = [(-1.3, 3.4), (1.3, 3.4), (1.36, 6.6), (1.0, 8.5), (-1.0, 8.5), (-1.36, 6.6)]
    rear_hi = [(-0.8, 3.7), (0.8, 3.7), (0.86, 6.4), (0.6, 7.45), (-0.6, 7.45), (-0.86, 6.4)]
    for lo_, hi_, z0, z1, bar in ((front_lo, front_hi, 0.75, 2.25, 9.3), (rear_lo, rear_hi, 1.35, 3.0, 5.0)):
        p.add(geo.tapered_prism(lo_, hi_, z0, z1), "canopy", texel=hidden_down, hp=0.03)
        canopy_frames(p, lo_, hi_, z0, z1, bar)
    # Nose sensor turret: a drum with flush sensor windows facing forward,
    # domed top and bottom, and a sight "ear" each side.
    nz = -0.5
    drum = geo.cylinder(0.62, 0.95, verts=16, bevel=0.0)
    geo.transform(drum, at=(0, 13.95, nz))
    windows, shell = split_faces(drum, lambda f: f.normal.y > 0.75)
    p.add(shell, "body_dark")
    p.add(windows, "seeker", hp=0.0)
    p.add(geo.sphere(0.62, 16, 6, scale=(1, 1, 0.42)), "body_dark", at=(0, 13.95, nz - 0.47))
    p.add(geo.sphere(0.56, 16, 6, scale=(1, 1, 0.3)), "body_dark", at=(0, 13.95, nz + 0.47))
    for s in (-1, 1):
        ear = geo.cylinder(0.26, 0.5, verts=10, bevel=0.0)
        geo.transform(ear, at=(s * 0.78, 13.85, nz), rot=(-90, 0, 0))
        lens, housing = split_faces(ear, lambda f: f.normal.y > 0.9)
        p.add(housing, "body_dark")
        p.add(lens, "seeker", hp=0.0)
    p.detail(geo.box(0.02, 0.9, 0.04, bevel=0.0), "body_dark", at=(0.0, 14.45, nz + 0.22))
    # Chin gun turret: ball, cradle, barrel with recoil sleeve and muzzle brake.
    gz = -2.05
    p.add(geo.sphere(0.66, 14, 8), "body_dark", at=(0, 11.55, -1.9))
    p.add(geo.box(0.62, 1.4, 0.5, bevel=0.0), "body_dark", at=(0, 12.25, gz), hp=0.06)
    p.add(geo.cylinder(0.16, 0.9, verts=10, bevel=0.0), "steel", at=(0, 13.1, gz), rot=(-90, 0, 0))
    p.add(geo.cylinder(0.09, 2.2, verts=8, bevel=0.0), "steel", at=(0, 13.0, gz), rot=(-90, 0, 0))
    p.add(geo.cylinder(0.13, 0.3, verts=8, bevel=0.0), "steel", at=(0, 13.98, gz), rot=(-90, 0, 0))
    a.attach("GunMuzzle", "Root", (0, 14.15, gz), axis=(0, 1, 0))
    engines(a, p)
    wings(a, p)
    tail(a, p)
    # Markings: emblem on the boom, nose number, chipped.
    for s in (-1, 1):
        a.decal(images.get("emblem"), (s * 0.62, -11.0, 1.6), (s, 0, 0), (1.4, 1.4, 0.5), color=RED, wear=0.3, seed=4 + s)
        a.decal(images.get("digits", text="07"), (s * 1.45, 10.3, -0.55), (s, 0, 0), (1.3, 0.75, 0.9), color=RED, wear=0.25, seed=7 + s)
        hs.stencil(a, "07", (s * 0.52, -19.4, 2.0), (s, 0, 0), 0.45, color="#9c9d97", wear=0.3, chip=0.3, seed=9 + s)


def split_faces(bm, pred):
    """Split a primitive into (faces where pred is true, the rest) so the
    two can take different materials. Consumes `bm`."""
    import bmesh

    a, b = bm.copy(), bm
    a.normal_update()
    b.normal_update()
    bmesh.ops.delete(a, geom=[f for f in a.faces if not pred(f)], context="FACES")
    bmesh.ops.delete(b, geom=[f for f in b.faces if pred(f)], context="FACES")
    return a, b


def canopy_frames(p, lo_, hi_, z0, z1, bar, sill=0.35):
    """Canopy frame bars along every pane edge above the sill (bake detail
    onto the glass): posts, roof edges, the sill and a door bar per side."""
    n = len(lo_)
    f = sill / (z1 - z0)

    def at(i, t):  # point on the edge from bottom vertex i to top vertex i
        return (lo_[i][0] + (hi_[i][0] - lo_[i][0]) * t, lo_[i][1] + (hi_[i][1] - lo_[i][1]) * t, z0 + (z1 - z0) * t)

    for i in range(n):
        j = (i + 1) % n
        p.detail(geo.pipe_path([at(i, f), at(i, 1.0)], 0.055, verts=6), "body")
        p.detail(geo.pipe_path([at(i, 1.0), at(j, 1.0)], 0.055, verts=6), "body")
        p.detail(geo.pipe_path([at(i, f), at(j, f)], 0.05, verts=6), "body")
    for s, (i, j) in ((1, (1, 2)), (-1, (0, 5))):  # side panes: vertices 1-2 (+X), 0-5 (-X)
        t = (bar - lo_[i][1]) / (lo_[j][1] - lo_[i][1])
        b0 = [lo_[i][k] + (lo_[j][k] - lo_[i][k]) * t for k in (0, 1)]
        b1 = [hi_[i][k] + (hi_[j][k] - hi_[i][k]) * t for k in (0, 1)]
        pb = (b0[0] + (b1[0] - b0[0]) * f, b0[1] + (b1[1] - b0[1]) * f, z0 + sill)
        p.detail(geo.pipe_path([pb, (b1[0], b1[1], z1)], 0.05, verts=6), "body")
        p.detail(hs.bolt_row((pb[0], pb[1] + 0.2, pb[2] + 0.2), (pb[0], pb[1] + 0.5, pb[2] + 0.2), 2, (s, 0, 0), r=0.04, h=0.03), "body")


def engines(a, p):
    for s in (-1, 1):
        x = s * NACELLE_X
        secs = [(3.75, 1.05, 1.05, 2.8, 2.0, x), (3.35, 1.45, 1.45, 2.8, 2.2, x), (1.0, 1.62, 1.62, 2.82, 2.7, x),
                (-2.9, 1.62, 1.6, 2.86, 2.7, x), (-4.3, 1.15, 1.22, 2.95, 2.4, x)]
        p.add(geo.loft(secs, n=16, cap_start=False), "body", texel=up_light)
        p.add(geo.torus(0.5, 0.07, verts=16, ring_verts=6), "body_dark", at=(x, 3.72, 2.8), rot=(90, 0, 0))
        p.add(geo.cylinder(0.5, 0.05, verts=12, bevel=0.0), "cavity", at=(x, 3.3, 2.8), rot=(-90, 0, 0), texel=0.2)
        # IR-suppressed exhaust: a duct turned outboard and down.
        at, rot = duct_frame(s)
        duct = geo.tapered_box(0.95, DUCT_LEN, 0.72, top_scale=(0.8, 0.85), bevel=0.0)
        p.add(duct, "body_dark", at=at, rot=rot, hp=0.06)
        hole = geo.transform(geo.box(0.66, 0.06, 0.46, bevel=0.0), at=(0, -DUCT_LEN / 2 + 0.02, 0))
        p.add(hole, "cavity", at=at, rot=rot, texel=0.3)
        # Access panels, fasteners and a hinge line on each nacelle (bake).
        p.detail(hs.rivet_row((x + s * 0.8, 2.9, 3.05), (x + s * 0.8, -2.6, 3.05), 14, (s, 0, 0.2), r=0.035), "body")
        p.detail(geo.box(0.03, 2.4, 0.8, bevel=0.012, segments=1), "body", at=(x + s * 0.8, 0.3, 2.72))
        for y in (-0.8, 1.4):
            p.detail(geo.cylinder(0.035, 0.28, verts=6, bevel=0.0), "body_dark", at=(x + s * 0.82, y, 3.2), rot=(-90, 0, 0))
    # Mast fairing ("doghouse") between the engines, mast and oil cooler hump.
    p.add(geo.loft([(2.6, 0.4, 0.6, 3.15, 2.0), (1.3, 2.2, 1.45, 3.45, 2.8), (-1.8, 2.2, 1.45, 3.45, 2.8),
                    (-3.6, 0.5, 0.55, 3.15, 2.0)], n=14), "body", texel=up_light)
    p.add(geo.cylinder(0.36, 0.9, verts=12, bevel=0.0), "steel", at=(0, 0, 4.35))
    p.add(geo.tapered_box(1.0, 1.4, 0.4, top_scale=(0.8, 0.7), bevel=0.0), "body_dark", at=(0, -2.6, 4.25))
    p.detail(hs.bolt_row((-0.9, 1.8, 4.2), (0.9, 1.8, 4.2), 5, (0, 0.2, 1), r=0.04, h=0.03), "body")


def wings(a, p):
    for s in (-1, 1):
        wing = aero.span_loft([(1.2, 2.8, 0.52, 0.25, 0.0, 2.3), (4.0, 2.3, 0.42, 0.15, 0.0, 2.3), (6.02, 1.9, 0.32, 0.05, 0.0, 2.3)], n=12)
        if s < 0:
            wing = geo.mirror_x(wing)
        p.add(wing, "body", at=(0, 0, -0.1), rot=(0, s * 4, 0), texel=up_light)
        tip_z = -0.1 - 5.9 * math.sin(math.radians(4))
        # Spar rivets along the wing's upper and lower surface (bake).
        for dz in (0.2, -0.2):
            p.detail(hs.rivet_row((s * 1.9, 0.6, dz - 0.05), (s * 5.6, 0.45, dz - 0.05 - 0.26), 12, (0, 0, math.copysign(1, dz)), r=0.035), "body")
        # Wing-tip countermeasure pod.
        p.add(aero.store(2.1, 0.22, nose=0.3, tail=0.25, verts=10), "body_dark", at=(s * 5.84, 0.15, tip_z))
        for y in (-0.55, -0.2):
            p.detail(geo.box(0.06, 0.26, 0.26, bevel=0.01, segments=1), "body_dark", at=(s * 6.04, y, tip_z))
        a.attach("NavLightL" if s < 0 else "NavLightR", "Root", (s * 5.84, 1.2, tip_z), axis=(s, 0, 0))
        # Pylons.
        for px, top in ((RACK_X, -0.28), (POD_X, -0.42)):
            py = geo.tapered_box(0.3, 1.5, 0.42, top_scale=(1.0, 1.2), bevel=0.0)
            p.add(py, "body_dark", at=(s * px, 0.1, top - 0.21), hp=0.05)
        rocket_pod(a, p, s)
        missile_rack(p, s)


def rocket_pod(a, p, s):
    x, y, z = s * POD_X, POD_Y, POD_Z
    body = geo.lathe([(0.0, -1.75), (0.36, -1.72), (0.58, -1.5), (0.6, -1.2), (0.6, 1.3), (0.64, 1.42), (0.64, 1.62),
                      (0.5, 1.7), (0.0, 1.72)], verts=16)
    p.add(body, "weapon", at=(x, y, z), rot=(-90, 0, 0))
    tubes, _ = aero.tube_cluster(0.1, rings=2, depth=0.06)
    p.detail(tubes, "cavity", at=(x, y + 1.68, z))
    for ty in (-0.9, 0.9):  # suspension bands
        p.detail(geo.torus(0.62, 0.035, verts=20, ring_verts=4), "body_dark", at=(x, y + ty, z), rot=(90, 0, 0))
    a.attach("RocketMuzzleL" if s < 0 else "RocketMuzzleR", "Root", (x, y + 1.75, z), axis=(0, 1, 0))


def missile_rack(p, s):
    x = s * RACK_X
    p.add(geo.box(1.0, 1.9, 0.18, bevel=0.0), "body_dark", at=(x, 0.3, -0.62), hp=0.04)
    p.add(geo.box(0.14, 1.9, 0.72, bevel=0.0), "body_dark", at=(x, 0.3, -1.0), hp=0.04)


def missile(T, length=2.3, r=0.13):
    """ATGM on the trim sheet: body on `plain` with a `red` band behind the
    seeker, cruciform tail fins, a dark seeker dome."""
    body = aero.store(length, r, nose=0.12, tail=0.08, verts=8, fins=4, fin_span=0.13, fin_chord=0.35, blunt=0.5)
    fins = lambda f: abs(f.normal.x) > 0.3 and abs(f.normal.z) > 0.3 and f.calc_center_median().y < -length * 0.25  # noqa: E731
    band = lambda f: not fins(f) and length * 0.28 < f.calc_center_median().y < length * 0.4  # noqa: E731
    nose = lambda f: not fins(f) and f.calc_center_median().y >= length * 0.4  # noqa: E731
    rest = lambda f: not (fins(f) or band(f) or nose(f))  # noqa: E731
    T.cylindrical(body, "plain", axis=(0, 1, 0), along=True, faces=rest)
    T.cylindrical(body, "red", axis=(0, 1, 0), along=True, faces=band)
    T.fill(body, "cable", faces=nose)
    T.fill(body, "plain", faces=fins)
    return body


def tail(a, p):
    # Driveshaft cover along the boom top with bearing hangers (bake).
    p.add(geo.loft([(-6.8, 0.1, 0.1, 2.3, 2.0), (-7.4, 0.45, 0.32, 2.45, 2.6), (-19.6, 0.45, 0.3, 2.52, 2.6),
                    (-20.2, 0.1, 0.1, 2.5, 2.0)], n=10), "body", texel=up_light)
    for y in range(-8, -20, -2):
        p.detail(geo.box(0.5, 0.12, 0.34, bevel=0.02, segments=1), "body_dark", at=(0, y, 2.5))
    # Boom stringer rivets (bake).
    for s in (-1, 1):
        p.detail(hs.rivet_row((s * 0.62, -8.0, 1.6), (s * 0.5, -17.0, 1.75), 24, (s, 0, 0), r=0.03), "body")
        p.detail(hs.rivet_row((s * 0.45, -8.0, 2.25), (s * 0.4, -17.0, 2.3), 24, (s, 0, 0.5), r=0.03), "body")
    # Swept vertical fin (aerofoil), tail-rotor gearbox fairing, tail bumper.
    fin = aero.span_loft([(1.6, 2.6, 0.44, -21.0, 0.0, 2.3), (4.2, 1.85, 0.3, -21.85, 0.0, 2.3), (6.85, 1.2, 0.2, -22.22, 0.0, 2.3)],
                         axis="z", n=10)
    p.add(fin, "body")
    p.add(geo.sphere(0.5, 12, 7, scale=(0.9, 1.2, 1.0)), "body", at=(0.3, TAIL_HUB[1], TAIL_HUB[2]))
    p.add(geo.cylinder(0.3, 0.5, verts=10, bevel=0.0), "body_dark", at=(0.55, TAIL_HUB[1], TAIL_HUB[2]), rot=(0, 90, 0))
    p.detail(hs.bolt_row((0.72, TAIL_HUB[1] - 0.25, TAIL_HUB[2] + 0.25), (0.72, TAIL_HUB[1] + 0.25, TAIL_HUB[2] - 0.25), 3, (1, 0, 0), r=0.04, h=0.03), "body_dark")
    p.add(geo.tapered_box(0.35, 1.2, 0.45, top_scale=(1.0, 1.3), bevel=0.0), "body_dark", at=(0, -21.2, 1.3), hp=0.05)
    # Stabilator on the boom end.
    for s in (-1, 1):
        st = aero.span_loft([(0.35, 1.5, 0.22, -17.9, 0.0, 2.3), (3.1, 1.0, 0.14, -18.35, 0.0, 2.3)], n=10)
        if s < 0:
            st = geo.mirror_x(st)
        p.add(st, "body", at=(0, 0, 1.85), texel=up_light)
        p.add(geo.box(0.12, 1.0, 0.6, bevel=0.0), "body_dark", at=(s * 3.42, -18.3, 1.85), hp=0.03)


# --- rotors (trim) -------------------------------------------------------------------

def _blade(T, r0, r1, chord, tip_chord, thick, red_len):
    """One rotor blade from radius r0 to r1 along +X: plain strip, red tip."""
    split = r1 - red_len
    bm = aero.span_loft([(r0, chord, thick, 0.0, 0.0, 2.6), (split, chord, thick, 0.0, 0.0, 2.6),
                         (r1 - red_len * 0.35, tip_chord, thick * 0.8, -0.08, 0.0, 2.6), (r1, tip_chord * 0.55, thick * 0.6, -0.22, 0.0, 2.6)], n=8)
    T.planar(bm, "plain", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=lambda f: f.calc_center_median().x < split)
    T.planar(bm, "red", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=lambda f: f.calc_center_median().x >= split)
    return bm


def main_rotor(a, T):
    r = a.part("MainRotor", tex="trim", query=False, joint=HUB, material="Metal", smooth_angle=35)
    hx, hy, hz = HUB
    hub = geo.cylinder(0.82, 0.55, verts=14, bevel=0.0)
    T.cylindrical(hub, "bolted", axis=(0, 0, 1))
    r.add(hub, "trim", at=HUB)
    cap = geo.sphere(0.55, 12, 5, scale=(1, 1, 0.6))
    T.fill(cap, "plain")
    r.add(cap, "trim", at=(hx, hy, hz + 0.3))
    swash = geo.cylinder(0.72, 0.16, verts=14, bevel=0.0)
    T.cylindrical(swash, "plain", axis=(0, 0, 1))
    r.add(swash, "trim", at=(hx, hy, hz - 0.6))
    for k in range(4):
        ang = 45 + 90 * k
        rad = math.radians(ang)
        c, s = math.cos(rad), math.sin(rad)
        grip = geo.tapered_box(1.3, 0.62, 0.36, top_scale=(1.0, 0.8), bevel=0.0)
        T.fill(grip, "bolted")
        r.add(grip, "trim", at=(hx + 1.25 * c, hy + 1.25 * s, hz), rot=(0, 0, ang))
        blade = _blade(T, 1.8, ROTOR_R, 0.95, 0.8, 0.13, 1.1)
        r.add(blade, "trim", at=HUB, rot=(3.0, -2.5, ang))
        link = geo.pipe_path([(0.75, 0.3, -0.55), (1.0, 0.32, -0.05)], 0.04, verts=5)
        T.fill(link, "cable")
        r.add(link, "trim", at=HUB, rot=(0, 0, ang))
        damper = geo.cylinder(0.08, 0.8, verts=6, bevel=0.0)
        T.cylindrical(damper, "cable", axis=(0, 0, 1), along=True)
        r.add(damper, "trim", at=(hx + 0.95 * c - 0.3 * s, hy + 0.95 * s + 0.3 * c, hz + 0.05), rot=(0, 90, ang))


def tail_rotor(a, T):
    t = a.part("TailRotor", tex="trim", query=False, joint=TAIL_HUB, material="Metal", smooth_angle=35)
    x, y, z = TAIL_HUB
    hub = geo.cylinder(0.26, 0.42, verts=10, bevel=0.0)
    T.cylindrical(hub, "bolted", axis=(0, 0, 1))
    t.add(hub, "trim", at=(x + 0.15, y, z), rot=(0, 90, 0))
    for k in range(4):
        ang = 90 * k + 45
        b = _blade(T, 0.25, TAIL_R, 0.45, 0.4, 0.07, 0.45)
        geo.transform(b, rot=(0, -90, 0))  # span +X -> +Z, thin along X
        t.add(b, "trim", at=(x + 0.3, y, z), rot=(ang, 0, 0))


# --- small hardware (trim, not hittable) ----------------------------------------------

def kit(a, T):
    k = a.part("HeliKit", tex="trim", material="Metal", query=False, smooth_angle=45)
    for s in (-1, 1):
        x = s * NACELLE_X
        # Mesh dust screen domed over each engine intake.
        dome = geo.lathe([(0.6, 0.0), (0.56, 0.13), (0.44, 0.24), (0.24, 0.31), (0.0, 0.33)], verts=14)
        geo.transform(dome, rot=(-90, 0, 0))
        T.planar(dome, "mesh", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
        k.add(dome, "trim", at=(x, 3.74, 2.8))
        # Exhaust outlet louvres; doghouse and nacelle cooling grilles.
        at, rot = duct_frame(s)
        g = geo.box(0.62, 0.05, 0.44, bevel=0.0)
        T.planar(g, "grille", u_axis=(1, 0, 0), v_axis=(0, 0, 1))
        geo.transform(g, at=(0, -DUCT_LEN / 2 - 0.02, 0))
        k.add(g, "trim", at=at, rot=rot)
        side = geo.box(0.04, 1.8, 0.45, bevel=0.0)
        T.planar(side, "grille", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
        k.add(side, "trim", at=(s * 0.96, -0.3, 3.95), rot=(0, -s * 35, 0))
        top = geo.box(0.7, 1.6, 0.04, bevel=0.0)
        T.planar(top, "grille", u_axis=(0, 1, 0), v_axis=(1, 0, 0))
        k.add(top, "trim", at=(x, -1.9, 3.64))
        # Pitot probes on the nose sides; radar-warning sensors.
        pit = geo.cylinder(0.035, 1.1, verts=5, r_top=0.02, bevel=0.0)
        T.fill(pit, "cable")
        k.add(pit, "trim", at=(s * 0.78, 13.3, 0.3), rot=(-90, 0, s * -8))
        for pos in ((s * 0.95, 12.6, 0.2), (s * 0.5, -22.3, 2.6)):
            rwr = geo.cylinder(0.14, 0.34, verts=8, bevel=0.0)
            T.fill(rwr, "plain")
            k.add(rwr, "trim", at=pos, rot=(-90, 0, s * 30))
        # Crew steps and hand holds on the sponsons.
        for y in (4.8, 8.0):
            st = hs.rail([(s * 2.4, y - 0.25, -0.6), (s * 2.62, y - 0.25, -0.6), (s * 2.62, y + 0.25, -0.6), (s * 2.4, y + 0.25, -0.6)],
                         r=0.04, feet=False)
            T.fill(st, "plain")
            k.add(st, "trim")
        # Flare dispensers on the boom sides.
        fl = geo.box(0.16, 1.2, 0.5, bevel=0.0)
        T.planar(fl, "bolted", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
        k.add(fl, "trim", at=(s * 0.66, -9.4, 1.35))
        # Main gear: trailing arm, oleo strut, wheel.
        axle = (s * 2.35, 4.0, -3.15)
        arm = geo.pipe_path([(s * 1.95, 5.5, -1.2), (s * 2.18, 4.0, -3.15)], 0.11, verts=6)
        T.fill(arm, "plain")
        k.add(arm, "trim")
        oleo = geo.pipe_path([(s * 2.0, 3.2, -1.2), (s * 2.15, 3.95, -2.9)], 0.09, verts=6)
        T.fill(oleo, "cable")
        k.add(oleo, "trim")
        face = (0, 90 * s, 0)
        k.add(T.template("tyre_half"), "trim", at=axle, rot=face, scale=(0.4, 0.4, 0.3))
        k.add(T.template("tyre_half"), "trim", at=axle, rot=(0, -90 * s, 0), scale=(0.4, 0.4, 0.3))
        k.add(T.template("rim"), "trim", at=(axle[0] + s * 0.02, axle[1], axle[2]), rot=face, scale=(0.42, 0.42, 0.25))
        # Missiles on launcher rails under the rack: charcoal bodies with a
        # red warhead band, finned tails, dark seeker domes.
        for dx in (-0.3, 0.3):
            for dz in (-0.93, -1.48):
                rail = geo.box(0.08, 1.8, 0.06, bevel=0.0)
                T.fill(rail, "plain")
                k.add(rail, "trim", at=(s * RACK_X + dx, 0.45, dz + 0.17))
                k.add(missile(T), "trim", at=(s * RACK_X + dx, 0.55, dz))
    # Wire strike protection: roof cutter and the deflector to the mast.
    cut = geo.prism([(0.0, 0.0), (0.9, 0.05), (0.2, 0.55), (0.0, 0.4)], 0.07, bevel=0.0)
    T.fill(cut, "plain")
    k.add(cut, "trim", at=(0, 7.3, 3.0), rot=(90, 0, 90))
    defl = geo.pipe_path([(0, 7.6, 3.2), (0, 3.9, 3.45), (0, 1.2, 4.0)], 0.035, verts=5)
    T.fill(defl, "cable")
    k.add(defl, "trim")
    # Blade antennas, whip on the boom, doppler fairing, ammo chute.
    for pos, h in (((0, -6.2, 2.6), 0.55), ((0, -12.5, 2.62), 0.45), ((0, 1.5, -1.8), -0.5)):
        ant = geo.prism([(0.0, 0.0), (0.45, 0.0), (0.2, abs(h)), (0.05, abs(h))], 0.05, bevel=0.0)
        T.fill(ant, "plain")
        k.add(ant, "trim", at=pos, rot=(90 if h > 0 else -90, 0, 90))
    w = hs.whip_antenna(height=2.6, base_r=0.07)
    T.cylindrical(w, "cable", axis=(0, 0, 1), along=True)
    k.add(w, "trim", at=(0.3, -15.8, 2.25), rot=(-20, 0, 0))
    chute = geo.pipe_path([(0.35, 11.2, -1.55), (0.62, 10.2, -1.35), (0.7, 9.0, -1.2)], 0.12, verts=6)
    T.fill(chute, "bolted")
    k.add(chute, "trim")
    # Searchlight housing and bracket under the chin (lamp from Dress).
    k.add(T.template("headlight"), "trim", at=(1.0, 9.62, -2.2), rot=(-24, 0, 0), scale=(1.35, 1.2, 1.35))
    br = geo.box(0.14, 0.5, 0.5, bevel=0.0)
    T.fill(br, "plain")
    k.add(br, "trim", at=(1.0, 9.4, -1.85))
    a.attach("Searchlight", "Root", (1.0, 9.9, -2.32), axis=(0, 1, -0.45))
    # Tail wheel with its strut.
    strut = geo.pipe_path([(0, -17.5, 1.3), (0, -17.8, 0.15)], 0.08, verts=6)
    T.fill(strut, "cable")
    k.add(strut, "trim")
    k.add(T.template("tyre_half"), "trim", at=(0, -17.8, 0.0), rot=(0, 90, 0), scale=(0.22, 0.22, 0.2))
    k.add(T.template("tyre_half"), "trim", at=(0, -17.8, 0.0), rot=(0, -90, 0), scale=(0.22, 0.22, 0.2))
    # Fin-top antenna.
    fa = geo.cylinder(0.05, 0.6, verts=5, r_top=0.02, bevel=0.0)
    T.fill(fa, "cable")
    k.add(fa, "trim", at=(0, -22.4, 7.15))


def build(**kw):
    a = Asset("Helicopter", pivot=(0, 0, 0), tex_size=1024)
    a.game_px = GAME_PX
    a.fix_inside_out = True
    a.texture_group("body", 1024, metal=False, high={"hp": 0.05, "cage": 0.12, "ray": 0.3})
    T = trim.use(a, "trim", "TrimEnemy")
    a.zmin = -3.7
    a.meta["no_ground"] = True  # air targets: previews against the sky
    materials(a)
    fuselage(a)
    main_rotor(a, T)
    tail_rotor(a, T)
    kit(a, T)
    views = [("", (1.1, 1.3, 0.55)), ("_rear", (-1.2, -1.1, 0.7)), ("_side", (1.0, 0.05, 0.05)),
             ("_below", (0.7, 1.0, -0.35)), ("_front", (0.25, 1.0, -0.12), ["Root", "HeliKit"]),
             {"label": "_cam_player", "pos": (-40, 60, -8), "look": (0, 0, 0.5), "fov": 40, "res": (1280, 800)},
             {"label": "_close_nose", "pos": (7.5, 24, 0.5), "look": (0, 9.5, 0.2), "fov": 38, "res": (1280, 800)},
             {"label": "_close_engine", "pos": (9, -9, 7), "look": (1.2, -1.5, 2.6), "fov": 38, "res": (1280, 800)}]
    return a.finish(views=views, **kw)
