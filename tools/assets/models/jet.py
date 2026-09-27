"""Jet: enemy twin-engine, twin-tail strike jet (original design).
Dark gunmetal with a charcoal spine and anti-glare panel, a lighter
radome, red fin tips and nose band, the emblem on the fins and a red nose
number. ~48 studs long, ~32 studs span.

Asset origin = centre of mass. Root = airframe; Bombs = the four
under-wing bombs (hidden on release); attachments Exhaust (between the
nozzles, looking aft), BombBay (belly, looking down), NavLightL /
NavLightR (wing tips), Cockpit (canopy centre).

HS-4 hard-surface pass: shoulder-mounted swept (cropped-delta) wings with
slight anhedral, flap-actuator fairings and pylons with ejector racks;
raked intakes faired into the fuselage, with splitter plates; bubble
canopy with baked frames, IRST ball, gun port; canted twin fins with
rudders, fin-cap fairings and root fillets, all-moving tailplanes;
nozzles with petals and flame holders, drag-chute stinger; ventral fins,
wing-tip missiles on rails, pitot, blade antennas. Baked from a
high-poly copy (rounded edges, panel lines, rivets, hinge lines)
with convex-edge chips, oil streaks, soot round the nozzles and the gun
port, a light dust film, and chipped markings; small hardware and the
wing-tip missiles are trim parts on the shared TrimEnemy sheet (JetKit).
Root and Bombs keep their pre-HS-4 bounding boxes exactly (= hit boxes):
`HIT` below, enforced by the build.
"""
import math

from rmh import aero, geo, hardsurface as hs, images, trim
from rmh.asset import Asset, rb_box

# RECLAIM-HS (QA-B item 5): the uploaded maps are capped at 512² (rmh/game_maps.py);
# the bake, .blend, previews and exported full-size PNGs stay 1024². At its nearest
# play range (250 studs, gunsight zoom) the 512² maps still give >= 1.4 texels per screen
# pixel, so the GPU was already sampling mip >= 1 of the 1024² maps: no visible change.
GAME_PX = 512

# Contract hit boxes: Roblox (centre, size) of the pre-HS-4 parts.
HIT = {
    "Root": ((0.0, 3.2951, -0.9), (32.38, 9.1901, 48.2)),
    "Bombs": ((0.0, -1.075, 3.3), (21.9, 1.35, 3.8)),
}
PAINT = "#3e4247"
DARK = "#2a2c30"
RED = "#b01c18"
DUST = "#a4876a"

FUSE = [
    (25.0, 0.1, 0.1, 0.3, 2.0),
    (23.5, 1.1, 1.1, 0.25, 2.0),
    (20.0, 2.3, 2.3, 0.35, 2.2),
    (16.0, 3.0, 2.9, 0.5, 2.6),
    (11.0, 3.6, 3.2, 0.6, 3.0),
    (6.0, 5.4, 3.3, 0.4, 3.4),
    (-2.0, 6.2, 3.2, 0.3, 3.6),
    (-12.0, 5.6, 2.9, 0.3, 3.6),
    (-18.0, 4.6, 2.6, 0.3, 3.2),
    (-21.0, 4.2, 2.4, 0.3, 3.0),
]
# Shoulder-mounted wing on top of the intakes, slight anhedral; the tip
# sits at the NavLight attachments' height (z = 0.84).
DIHEDRAL = -1.5
TIP_Z = 0.84
# Wing planform (right side): root LE/TE at x = 2.4, tip LE/TE at x = 16.
WING_ROOT = (2.4, 4.0, -12.0)
WING_TIP = (16.0, -6.8, -10.2)
NOZZLES = [(s * 1.15, -20.8, 0.3) for s in (-1, 1)]
PYLONS = (6.5, 10.5)
GUN = (1.86, 10.2, 1.3)

up_light = lambda f: 0.25 if f.normal.z > 0.6 else 1.0  # noqa: E731  seen from below
hidden_down = lambda f: 0.15 if f.normal.z < -0.5 else 1.0  # noqa: E731


def wing_at(x):
    """(LE y, TE y, z centre) of the right wing at span station x."""
    t = (x - WING_ROOT[0]) / (WING_TIP[0] - WING_ROOT[0])
    le = WING_ROOT[1] + (WING_TIP[1] - WING_ROOT[1]) * t
    te = WING_ROOT[2] + (WING_TIP[2] - WING_ROOT[2]) * t
    return le, te, TIP_Z + (x - WING_TIP[0]) * math.tan(math.radians(DIHEDRAL))


def wing_thick(x):
    t = (x - WING_ROOT[0]) / (WING_TIP[0] - WING_ROOT[0])
    return 0.56 + (0.16 - 0.56) * t


def wing_surface(x, y, top=True):
    """z of the (lens-section) wing surface at span x, chordwise y."""
    le, te, z = wing_at(x)
    u = (y - (le + te) / 2) / ((le - te) / 2)
    half = wing_thick(x) / 2 * math.sqrt(max(0.0, 1.0 - u * u))
    return z + half if top else z - half


def materials(a):
    soot = [{"pos": (x, y + 0.2, z), "dir": (0, -1, 0), "radius": 1.45, "length": 1.1, "spread": 0.2, "strength": 0.75} for x, y, z in NOZZLES]
    soot += [{"pos": (x, y + 1.2, z), "dir": (0, -1, 0), "radius": 1.3, "length": 1.4, "spread": 0.4, "strength": 0.45} for x, y, z in NOZZLES]
    soot.append({"pos": GUN, "dir": (0.1, -1, 0.02), "radius": 0.28, "length": 3.2, "spread": 0.25, "strength": 0.85})
    marks = [
        {"lo": (-2, 21.7, -2), "hi": (2, 25.5, 2.5), "color": "#4b5055"},  # radome
        {"lo": (-1.6, 21.2, -2), "hi": (1.6, 21.7, 2), "color": RED},  # nose band
        {"lo": (-0.75, 16.6, 1.35), "hi": (0.75, 19.4, 3.0), "color": "#1e2023"},  # anti-glare panel
        {"lo": (-4, -6.0, -2), "hi": (-1.5, -1.5, 0.2), "color": "#464a4f"},  # replaced panels
        {"lo": (6.0, -9.5, -1), "hi": (9.5, -6.0, 2), "color": "#383c40"},
        {"lo": (1.8, 2.5, 1.2), "hi": (3.2, 6.5, 3), "color": "#454a4e"},
    ]
    paint = dict(kind="paint", color=PAINT, rough=0.45, wear=0.25, under="#8b8c89", under_rough=0.35,
                 chip_style="blotch", chip_scale=6.5, chip_bevel=0.06, ring=0.15, ring_color="#24201c",
                 edge_convex=True, polish=0.25, grime=0.5, grime_color="#1d1a17", streaks=0.5, dust=0.15, dust_up=0.05,
                 dust_height=0.8, dust_color=DUST, rough_breakup=0.35, fade=0.15, fade_color="#5d6166",
                 panels=(2.6, 3.2, 0), panel_width=0.06, bevel=0.05,
                 photo={"id": "green_metal_rust", "scale": 5.0, "color": 0.3, "sat": 0.08, "rough": 0.35, "height": 0.12})
    a.material("skin", **paint, marks=marks, soot=soot)
    a.material("skin_dark", **dict(paint, color=DARK, photo=None, fade=0.05), soot=soot)
    a.material("fin", **paint, marks=[{"lo": (-9, -24, 7.0), "hi": (9, -15, 9), "color": RED}], soot=soot)
    a.material("canopy", kind="flat", color="#2a2416", rough=0.04, dust=0.2, dust_up=0.4, grime=0.2,
               dust_cavity=0.45, dust_cavity_distance=0.25, dust_cavity_range=(0.1, 0.5), dust_color=DUST)
    a.material("seeker", kind="flat", color="#1e2a30", rough=0.1, grime=0.2)
    a.material("cavity", kind="flat", color="#0d0d0e", rough=0.85)
    a.material("nozzle", kind="metal", color="#4b4640", rough=0.38, metal=0.9, grime=0.9, dust=0.0, edge_convex=True, polish=0.4,
               soot=soot[:2])
    a.material("hot", kind="metal", color="#3a3431", rough=0.5, metal=0.8, grime=0.6, dust=0.0)
    a.material("ordnance", kind="paint", color="#43453a", rough=0.55, wear=0.3, under="#7d7e79", edge_convex=True, grime=0.4,
               dust=0.15, dust_height=0.5, dust_color=DUST, rough_breakup=0.2,
               marks=[{"lo": (-12, -1.8, -3), "hi": (12, -1.55, 0), "color": "#b8952a"}])


# --- airframe ------------------------------------------------------------------------

def airframe(a):
    lo, hi = rb_box(*HIT["Root"])
    p = a.part("Root", tex="body", material="Metal", smooth_angle=50, hitbox=(lo, hi))
    p.add(geo.loft(FUSE, n=20), "skin", texel=up_light)
    # Spine, anti-glare panel is a mark; dorsal airbrake outline (bake).
    p.add(geo.loft([(11.0, 1.2, 1.2, 1.8, 2.0), (6.0, 1.8, 1.3, 2.0, 2.4), (-12.0, 1.5, 1.0, 1.75, 2.4), (-17.0, 0.4, 0.3, 1.5, 2.0)], n=12),
          "skin_dark", texel=up_light)
    p.detail(geo.box(2.2, 3.0, 0.03, bevel=0.012, segments=1), "skin_dark", at=(0, -3.0, 2.64))
    for y in (-4.4, -1.6):
        p.detail(geo.cylinder(0.04, 2.0, verts=6, bevel=0.0), "skin_dark", at=(0, y, 2.66), rot=(0, 90, 0))
    canopy(a, p)
    intakes(p)
    wings(a, p)
    tails(a, p)
    nozzles(p)
    # Gun port on the right wing root with a blast panel (soot in the paint).
    gx, gy, gz = GUN
    p.add(geo.cylinder(0.2, 0.7, verts=10, bevel=0.0), "skin_dark", at=(gx, gy - 0.3, gz), rot=(-90, 0, 0))
    p.add(geo.cylinder(0.12, 0.05, verts=8, bevel=0.0), "cavity", at=(gx, gy + 0.06, gz), rot=(-90, 0, 0), texel=0.3)
    p.detail(geo.box(0.5, 1.6, 0.03, bevel=0.01, segments=1), "skin", at=(gx, gy - 1.2, gz + 0.12))
    a.attach("Exhaust", "Root", (0, -23.4, 0.3), axis=(0, -1, 0))
    a.attach("BombBay", "Root", (0, -2.0, -1.6), axis=(0, 0, -1))
    a.attach("Cockpit", "Root", (0, 14.2, 1.9), axis=(0, 1, 0))
    # Markings: nose number (chipped), fin emblems.
    for s in (-1, 1):
        a.decal(images.get("digits", text="31"), (s * 1.55, 18.4, 0.2), (s, 0, 0.1), (2.0, 1.0, 1.0), color=RED, wear=0.25, seed=5 + s)
        hs.stencil(a, "31", (s * 3.3, -20.3, 0.5), (s, 0, 0), 0.4, color="#9c9d97", wear=0.3, chip=0.3, seed=12 + s)


def canopy(a, p):
    cy, cz, rx, ry = 14.2, 1.75, 1.15, 4.2
    p.add(geo.sphere(1.0, 18, 9, scale=(rx, ry, rx)), "canopy", at=(0, cy, cz), texel=hidden_down, hp=0.0)

    def arch(y, k=11):
        """Frame arch round the canopy at station y (points on its surface)."""
        f = max(0.0, 1.0 - ((y - cy) / ry) ** 2)
        r = rx * math.sqrt(f)
        pts = []
        for i in range(k):
            ang = math.pi * (0.08 + 0.84 * i / (k - 1))
            pts.append((r * math.cos(ang), y, cz + r * math.sin(ang)))
        return pts

    for y in (16.9, 15.1, 11.6):
        p.detail(geo.pipe_path(arch(y), 0.06, verts=6), "skin_dark")
    for s in (-1, 1):  # sill rails
        sill = [(s * rx * math.sqrt(max(0.0, 1 - ((y - cy) / ry) ** 2)) * 0.99, y, cz + 0.1) for y in (17.8, 16.5, 14.2, 12.0, 10.6)]
        p.detail(geo.pipe_path(sill, 0.06, verts=6), "skin_dark")
    # Seat headrest and the IRST ball ahead of the windscreen.
    p.add(geo.box(0.6, 0.3, 0.7, bevel=0.0), "skin_dark", at=(0, 12.8, 2.1), hp=0.08)
    ball = geo.sphere(0.3, 12, 6)
    geo.transform(ball, at=(0.45, 18.9, 1.62))
    glass, housing = _split(ball, lambda f: f.normal.y > 0.35 and f.normal.z > -0.3)
    p.add(housing, "skin_dark")
    p.add(glass, "seeker", hp=0.0)


def _split(bm, pred):
    import bmesh

    a, b = bm.copy(), bm
    a.normal_update()
    b.normal_update()
    bmesh.ops.delete(a, geom=[f for f in a.faces if not pred(f)], context="FACES")
    bmesh.ops.delete(b, geom=[f for f in b.faces if pred(f)], context="FACES")
    return a, b


def intakes(p):
    """Raked rectangular intakes that fair back into the fuselage under the
    wing root, with a dark mouth, a lip and a splitter plate."""
    for s in (-1, 1):
        x = s * 2.78
        secs = [(10.4, 1.5, 1.9, 0.0, 5.0, x), (7.0, 1.5, 1.9, 0.0, 5.0, x), (2.0, 1.4, 1.85, 0.05, 4.5, x - s * 0.08),
                (-3.5, 1.0, 1.5, 0.2, 3.5, x - s * 0.45), (-6.5, 0.3, 0.8, 0.3, 2.5, x - s * 0.8)]
        duct = geo.loft(secs, n=16)
        for v in duct.verts:  # rake the mouth: its top edge leads by ~1 stud
            if v.co.y > 10.3:
                v.co.y += v.co.z * 0.53
        aero.outward(duct)
        mouth, body = _split(duct, lambda f: f.normal.y > 0.6)
        p.add(body, "skin", texel=up_light, hp=0.06)
        p.add(mouth, "cavity", texel=0.3, hp=0.0)
        # Lip round the mouth and rivets along the duct (bake).
        ring = [(x - 0.73, 10.9, 0.94), (x + 0.73, 10.9, 0.94), (x + 0.73, 9.9, -0.94), (x - 0.73, 9.9, -0.94), (x - 0.73, 10.9, 0.94)]
        p.detail(geo.pipe_path(ring, 0.06, verts=6), "skin_dark")
        p.detail(hs.rivet_row((x + s * 0.76, 9.0, 0.55), (x + s * 0.74, 3.0, 0.55), 14, (s, 0, 0), r=0.035), "skin")
        # Splitter plate standing off the fuselage.
        sp = geo.prism([(11.3, 0.95), (8.2, 0.95), (8.2, -0.95), (10.3, -0.95)], 0.07, bevel=0.0)
        geo.transform(sp, rot=(90, 0, 90))  # (y, z) profile, thickness along X
        p.add(sp, "skin_dark", at=(s * 1.92, 0, 0), hp=0.02)


def wings(a, p):
    for s in (-1, 1):
        secs = []
        for x in (WING_ROOT[0], 9.2, WING_TIP[0]):
            le, te, z = wing_at(x)
            secs.append((x, le - te, wing_thick(x), (le + te) / 2, z, 2.0))
        w = aero.span_loft(secs, n=10)
        if s < 0:
            w = geo.mirror_x(w)
        p.add(w, "skin", texel=up_light)
        # Flap and aileron hinge lines, top and bottom (bake).
        for x0, x1 in ((3.2, 9.0), (9.4, 15.0)):
            y0, y1 = wing_at(x0)[1] + 1.6, wing_at(x1)[1] + 1.3
            for top in (True, False):
                p.detail(geo.pipe_path([(s * x0, y0, wing_surface(x0, y0, top)), (s * x1, y1, wing_surface(x1, y1, top))], 0.03, verts=5), "skin")
        # Flap-actuator ("canoe") fairings under the wing.
        for x in (7.5, 11.8):
            yc = wing_at(x)[1] + 1.2
            c = aero.store(4.2, 0.24, nose=0.3, tail=0.45, verts=10)
            geo.transform(c, scale=(1.0, 1.0, 0.75))
            p.add(c, "skin", at=(s * x, yc, wing_surface(x, yc, False) - 0.1), hp=0.04)
        # Pylons with ejector racks and sway braces.
        for x in PYLONS:
            bottom = wing_surface(x, -3.4, False) + 0.05
            py = geo.tapered_box(0.2, 2.4, bottom + 0.8, top_scale=(1.0, 1.2), bevel=0.0)
            p.add(py, "skin_dark", at=(s * x, -3.4, (bottom - 0.8) / 2), hp=0.04)
            p.detail(hs.bolt_row((s * (x + 0.15), -4.3, -0.55), (s * (x + 0.15), -2.5, -0.55), 3, (s, 0, 0), r=0.04, h=0.03), "skin_dark")
        # Wing-tip launch rail (the missile on it is trim) and the nav light.
        rail = geo.box(0.24, 3.8, 0.26, bevel=0.0)
        p.add(rail, "skin_dark", at=(s * 15.98, -8.4, TIP_Z), hp=0.04)
        a.attach("NavLightL" if s < 0 else "NavLightR", "Root", (s * 16.1, -10.2, 0.84), axis=(s, 0, 0))


def tails(a, p):
    for s in (-1, 1):
        # All-moving tailplane with its pivot fairing.
        st = aero.span_loft([(2.2, 7.3, 0.32, -18.15, 0.0, 2.0), (8.8, 2.4, 0.12, -20.4, 0.0, 2.0)], n=10)
        if s < 0:
            st = geo.mirror_x(st)
        p.add(st, "skin", at=(0, 0, 0.2), texel=up_light)
        p.add(aero.store(3.2, 0.28, nose=0.4, tail=0.4, verts=10), "skin", at=(s * 2.55, -18.4, 0.2), hp=0.04)
        # Canted fin: aerofoil, rudder hinge, cap fairing, root fillet.
        fin = aero.span_loft([(0.0, 8.6, 0.42, -17.5, 0.0, 2.0), (3.45, 5.5, 0.28, -19.25, 0.0, 2.0), (6.9, 2.4, 0.16, -21.0, 0.0, 2.0)],
                             axis="z", n=10)
        fin_rot = (0, s * 18, 0)
        p.add(fin, "fin", at=(s * 2.3, 0, 1.3), rot=fin_rot)
        cap = geo.transform(aero.store(2.3, 0.1, nose=0.35, tail=0.3, verts=8), at=(0, -21.0, 6.78))
        p.add(cap, "fin", at=(s * 2.3, 0, 1.3), rot=fin_rot, hp=0.03)
        for sgn in (1, -1):
            hinge = geo.pipe_path([(sgn * 0.14, -19.9, 0.4), (sgn * 0.1, -21.35, 6.5)], 0.03, verts=5)
            p.detail(hinge, "fin", at=(s * 2.3, 0, 1.3), rot=fin_rot)
        fil = geo.prism([(-13.0, 0.0), (-14.6, 0.55), (-20.0, 0.55), (-21.2, 0.0)], 0.5, bevel=0.0)
        geo.transform(fil, rot=(90, 0, 90))
        p.add(fil, "skin", at=(s * 2.3, 0, 1.1), rot=fin_rot, hp=0.05)
        a.decal(images.get("emblem"), (s * 3.4, -18.4, 4.4), (s * 0.95, 0, 0.31), (2.2, 2.2, 0.8), color=RED, wear=0.3, seed=2 + s)
    # Drag-chute "stinger" on top between the nozzles.
    p.add(geo.loft([(-19.5, 0.9, 0.6, 1.2, 2.4), (-22.5, 0.6, 0.45, 1.15, 2.2), (-22.9, 0.1, 0.1, 1.15, 2.0)], n=10), "skin_dark")


def nozzles(p):
    for x, y, z in NOZZLES:
        outer = geo.lathe([(1.1, 0.0), (1.2, -0.7), (1.12, -1.5), (1.02, -2.35), (0.94, -2.4), (0.98, -1.5), (0.82, -0.6)],
                          verts=14, close_top=False, close_bottom=False)
        p.add(outer, "nozzle", at=(x, y, z), rot=(-90, 0, 0), hp=0.03)
        for k in range(14):  # petal seams (bake)
            ang = 2 * math.pi * (k + 0.5) / 14
            c, sn = math.cos(ang), math.sin(ang)
            seam = geo.pipe_path([(x + 1.2 * c, y - 0.8, z + 1.2 * sn), (x + 1.03 * c, y - 2.3, z + 1.03 * sn)], 0.025, verts=4)
            p.detail(seam, "nozzle")
        p.add(geo.cylinder(0.82, 0.05, verts=14, bevel=0.0), "cavity", at=(x, y - 0.55, z), rot=(-90, 0, 0), texel=0.3)
        p.add(geo.torus(0.5, 0.06, verts=14, ring_verts=4), "hot", at=(x, y - 0.5, z), rot=(90, 0, 0), texel=0.3)
        p.add(geo.cylinder(0.16, 0.25, verts=8, bevel=0.0), "hot", at=(x, y - 0.5, z), rot=(-90, 0, 0), texel=0.3)


def bombs(a):
    lo, hi = rb_box(*HIT["Bombs"])
    b = a.part("Bombs", tex="body", material="Metal", smooth_angle=45, hitbox=(lo, hi))
    for s in (-1, 1):
        for x in PYLONS:
            body = aero.store(3.5, 0.43, nose=0.38, tail=0.3, verts=12, fins=4, fin_span=0.2, fin_chord=0.8, fin_thick=0.04)
            b.add(body, "ordnance", at=(s * x, -3.3, -1.3), texel=0.6)
            b.add(geo.cylinder(0.07, 0.12, verts=6, bevel=0.0), "hot", at=(s * x, -1.5, -1.3), rot=(-90, 0, 0), texel=0.3)
            b.detail(geo.torus(0.44, 0.025, verts=16, ring_verts=4), "ordnance", at=(s * x, -2.0, -1.3), rot=(90, 0, 0))
            for dy in (-0.55, 0.55):  # suspension lugs
                b.add(geo.box(0.1, 0.18, 0.12, bevel=0.0), "hot", at=(s * x, -3.3 + dy, -0.82), texel=0.3)


# --- small hardware (trim, not hittable) ----------------------------------------------

def kit(a, T):
    k = a.part("JetKit", tex="trim", material="Metal", query=False, smooth_angle=45)
    for s in (-1, 1):
        # Wing-tip AA missile under the rail.
        _, _, tip_z = wing_at(WING_TIP[0])
        k.add(aam(T), "trim", at=(s * 15.98, -8.2, tip_z - 0.28))
        # Ventral fins under the tail booms.
        vf = geo.prism([(-12.2, 0.0), (-13.5, -1.2), (-15.4, -1.2), (-15.2, 0.0)], 0.07, bevel=0.0)
        geo.transform(vf, rot=(90, 0, 90))
        T.planar(vf, "plain", u_axis=(0, 1, 0), v_axis=(0, 0, 1))
        k.add(vf, "trim", at=(s * 2.1, 0, -0.95), rot=(0, s * 15, 0))
        # Angle-of-attack vane and air-data probe on the nose sides.
        v = geo.prism([(0.0, 0.0), (0.35, 0.0), (0.3, 0.18), (0.05, 0.18)], 0.03, bevel=0.0)
        if s < 0:
            v = geo.mirror_x(v)
        T.fill(v, "plain")
        k.add(v, "trim", at=(s * 0.98, 21.3, 0.5))
    # Pitot boom on the nose tip.
    pit = geo.cylinder(0.05, 2.0, verts=6, r_top=0.025, bevel=0.0)
    T.fill(pit, "cable")
    k.add(pit, "trim", at=(0, 25.8, 0.3), rot=(-90, 0, 0))
    # Blade antennas on the spine and the belly.
    for pos, up in (((0, 3.5, 2.55), True), ((0, -8.0, 2.35), True), ((0, 4.5, -1.28), False), ((0, -9.0, -1.1), False)):
        ant = geo.prism([(0.0, 0.0), (0.6, 0.0), (0.25, 0.5), (0.05, 0.5)], 0.05, bevel=0.0)
        T.fill(ant, "plain")
        k.add(ant, "trim", at=pos, rot=(90 if up else -90, 0, 90))


def aam(T, length=3.0, r=0.14):
    """Short-range air-to-air missile: charcoal body, red warhead band,
    canard and tail fins, dark seeker dome (trim sheet)."""
    body = aero.store(length, r, nose=0.1, tail=0.06, verts=8, fins=4, fin_span=0.2, fin_chord=0.45, blunt=0.55)
    for k in range(4):  # canards
        ang = 45 + 90 * k
        c = geo.prism([(r * 0.7, 0.0), (r + 0.14, -0.12), (r + 0.14, -0.3), (r * 0.7, -0.34)], 0.025, bevel=0.0)
        geo.transform(c, at=(0, length * 0.36, 0), rot=(0, ang, 0))
        hs._join(body, c)
    fins = lambda f: abs(f.normal.x) > 0.3 and abs(f.normal.z) > 0.3 and abs(f.normal.y) < 0.2  # noqa: E731
    band = lambda f: not fins(f) and length * 0.2 < f.calc_center_median().y < length * 0.3  # noqa: E731
    nose = lambda f: not fins(f) and f.calc_center_median().y >= length * 0.43  # noqa: E731
    rest = lambda f: not (fins(f) or band(f) or nose(f))  # noqa: E731
    T.cylindrical(body, "plain", axis=(0, 1, 0), along=True, faces=rest)
    T.cylindrical(body, "red", axis=(0, 1, 0), along=True, faces=band)
    T.fill(body, "cable", faces=nose)
    T.fill(body, "plain", faces=fins)
    return body


def build(**kw):
    a = Asset("Jet", pivot=(0, 0, 0), tex_size=1024)
    a.game_px = GAME_PX
    a.fix_inside_out = True
    a.texture_group("body", 1024, metal=False, high={"hp": 0.05, "cage": 0.12, "ray": 0.3})
    T = trim.use(a, "trim", "TrimEnemy")
    a.zmin = -2.0
    a.meta["no_ground"] = True  # air target: previews against the sky
    materials(a)
    airframe(a)
    bombs(a)
    kit(a, T)
    views = [("", (1.1, 1.2, 0.6)), ("_rear", (-1.0, -1.3, 0.5)), ("_top", (0.2, -0.3, 1.0)), ("_below", (0.5, 0.9, -0.55)),
             {"label": "_cam_player", "pos": (-55, 70, -45), "look": (0, 0, 0), "fov": 40, "res": (1280, 800)},
             {"label": "_close_nose", "pos": (10, 30, -2.5), "look": (0, 13, 0.5), "fov": 40, "res": (1280, 800)},
             {"label": "_close_tail", "pos": (-11, -36, -4), "look": (0, -17, 1.5), "fov": 40, "res": (1280, 800)},
             {"label": "_close_belly", "pos": (8, 12, -14), "look": (0, -2, -0.5), "fov": 40, "res": (1280, 800)}]
    return a.finish(views=views, **kw)
