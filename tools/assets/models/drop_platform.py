"""DropPlatform: the enemy's heavy-drop platform (original design): an
aluminium pallet with side rails, tie-down rings, nose and tail bumpers
and corner suspension clevises, rigged for the Tank (or the Buggy) with
honeycomb crush pads and lashing straps, and four suspension slings up to
the clevis the cargo parachutes clip onto.

Asset origin (model pivot) = **base centre** (bottom of the platform).
Forward -Z (Roblox), up +Y. Sized for the Tank's footprint (tracks
11.0 x 23.2, hull 11.5 x 26.6 studs); usable for the Buggy.

Parts:
- `Root` (PrimaryPart; deck, rails, bumpers, clevises, D-rings; the shared
  TrimEnemy sheet).
- `TankRig/TankRigging`: crush pads under the tracks and belly, lashing
  straps up to the hull (TrimAirdrop: kraft + webbing).
- `BuggyRig/BuggyRigging`: pads under the wheels and frame, wheel
  lashings. Destroy the rig you don't use.
- `Slings`: four sling legs from the corner clevises to the apex clevis.
- `NightLamp`: tiny Neon strobe at `NightLight` (Transparency 1).
Attachments on `Root`:
- `LoadAttach`: top of the crush pads at the centre, looking forward: the
  vehicle's pivot (ground contact centre) goes here.
- `Riser1`..`Riser4`: the corner suspension clevises (1 front-left,
  2 front-right, 3 rear-left, 4 rear-right), each looking up its sling.
- `SlingApex`: where the four slings meet, 36 studs above the base: clip
  every cargo chute's `LoadAttach` here.
- `NightLight`: strobe on the front-right rail, looking up.
All parts CanQuery/CanCollide false.
"""
from mathutils import Vector

from models.parachute import frame_rot
from rmh import aero, geo, trim
from rmh.asset import Asset

L, W = 28.6, 12.2  # deck length (Blender Y) and width (X)
DECK = 0.55  # deck top above the base
RAIL_H, RAIL_W = 0.95, 0.4
PAD_TOP = 2.3  # top of the crush pads = LoadAttach height
APEX = 36.0
CORNERS = {1: (-1, 1), 2: (1, 1), 3: (-1, -1), 4: (1, -1)}  # (x sign, y sign); +Y = forward


def corner(k):
    sx, sy = CORNERS[k]
    return Vector((sx * (W / 2 - 0.2), sy * (L / 2 - 0.55), RAIL_H + 0.35))


def platform(a, T):
    p = a.part("Root", tex="trim", query=False, collide=False, material="Metal", smooth_angle=40)
    # Deck: four transverse panels with bolted joints.
    for k in range(4):
        y = -L / 2 + L / 8 + k * L / 4
        panel = geo.box(W - 2 * RAIL_W, L / 4 - 0.12, DECK, bevel=0.0)
        T.planar(panel, "plain", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=lambda f: abs(f.normal.z) > 0.5)
        T.planar(panel, "plain", u_axis=(1, 0, 0), v_axis=(0, 0, 1), faces=lambda f: abs(f.normal.y) > 0.5)
        T.planar(panel, "plain", u_axis=(0, 1, 0), v_axis=(0, 0, 1), faces=lambda f: abs(f.normal.x) > 0.5)
        p.add(panel, "trim", at=(0, y, DECK / 2))
    for k in range(5):
        y = -L / 2 + k * L / 4
        joint = geo.box(W - 2 * RAIL_W, 0.32, 0.08, bevel=0.0)
        T.planar(joint, "bolted", u_axis=(1, 0, 0), v_axis=(0, 1, 0))
        p.add(joint, "trim", at=(0, y, DECK + 0.03))
    # Underside channels (seen from below while it descends).
    for k in range(7):
        y = -L / 2 + 1.2 + k * (L - 2.4) / 6
        ch = geo.box(W - 0.6, 0.45, 0.28, bevel=0.0)
        T.planar(ch, "bolted", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=lambda f: abs(f.normal.z) > 0.5)
        T.planar(ch, "plain", u_axis=(1, 0, 0), v_axis=(0, 0, 1), faces=lambda f: abs(f.normal.z) <= 0.5)
        p.add(ch, "trim", at=(0, y, -0.12))
    # Side rails with tie-down D-rings.
    for sx in (-1, 1):
        rail = geo.box(RAIL_W, L, RAIL_H, bevel=0.0)
        T.planar(rail, "bolted", u_axis=(0, 1, 0), v_axis=(0, 0, 1), faces=lambda f: abs(f.normal.x) > 0.5)
        T.planar(rail, "plain", u_axis=(0, 1, 0), v_axis=(1, 0, 0), faces=lambda f: abs(f.normal.x) <= 0.5)
        p.add(rail, "trim", at=(sx * (W / 2 - RAIL_W / 2), 0, RAIL_H / 2))
        for k in range(10):
            y = -L / 2 + 1.6 + k * (L - 3.2) / 9
            ring = geo.torus(0.2, 0.05, verts=8, ring_verts=4)
            T.fill(ring, "cable")
            p.add(ring, "trim", at=(sx * (W / 2 + 0.02), y, RAIL_H - 0.15), rot=(0, 90, 0))
    # Nose and tail bumpers: sloped plates with red hazard faces.
    for sy in (-1, 1):
        prof = [(0.0, 0.0), (0.0, RAIL_H), (0.7, RAIL_H * 0.55), (0.7, 0.0)]
        b = geo.side_prism([(sy * y, z) for y, z in prof], W, bevel=0.0)
        aero.outward(b)
        T.planar(b, "red", u_axis=(1, 0, 0), v_axis=(0, 0, 1), faces=lambda f: sy * f.normal.y > 0.3)
        T.planar(b, "plain", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=lambda f: sy * f.normal.y <= 0.3)
        p.add(b, "trim", at=(0, sy * L / 2, 0))
    # Corner suspension clevises (plates with a shackle) and the strobe mount.
    for k in CORNERS:
        c = corner(k)
        sx, sy = CORNERS[k]
        plate = geo.box(0.12, 0.8, 0.9, bevel=0.0)
        T.fill(plate, "plain")
        p.add(plate, "trim", at=(c.x, c.y, RAIL_H + 0.3))
        shackle = geo.torus(0.22, 0.06, verts=8, ring_verts=4)
        T.fill(shackle, "cable")
        p.add(shackle, "trim", at=(c.x, c.y, c.z + 0.1), rot=(0, 90, 0))
        a.attach(f"Riser{k}", "Root", tuple(c), axis=tuple((Vector((0, 0, APEX)) - c).normalized()))
    strobe = geo.box(0.35, 0.35, 0.3, bevel=0.0)
    T.fill(strobe, "plain")
    night = (W / 2 - 0.2, L / 2 - 2.2, RAIL_H + 0.3)
    p.add(strobe, "trim", at=(night[0], night[1], RAIL_H + 0.15))
    a.attach("NightLight", "Root", night, axis=(0, 0, 1))
    a.attach("LoadAttach", "Root", (0, 0, PAD_TOP), axis=(0, 1, 0))
    a.attach("SlingApex", "Root", (0, 0, APEX), axis=(0, 1, 0))  # identity-oriented: PivotTo a chute straight onto it
    lamp = geo.cylinder(0.12, 0.14, verts=8, bevel=0.0)
    a.part("NightLamp", neon=(1.0, 0.36, 0.24), transparency=1, query=False, collide=False, shadow=False).add(
        lamp, "lamp", at=(night[0], night[1], night[2] + 0.02))


def pad(T, sx, sy, sz):
    """Honeycomb crush-pad stack (kraft sides, top and bottom)."""
    bm = geo.box(sx, sy, sz, bevel=0.0)
    T.planar(bm, "kraft", u_axis=(0, 1, 0), v_axis=(0, 0, 1), faces=lambda f: abs(f.normal.x) > 0.5)
    T.planar(bm, "kraft", u_axis=(1, 0, 0), v_axis=(0, 0, 1), faces=lambda f: abs(f.normal.y) > 0.5)
    T.planar(bm, "kraft", u_axis=(1, 0, 0), v_axis=(0, 1, 0), faces=lambda f: abs(f.normal.z) > 0.5, band=(0.05, 0.2))
    return bm


def strap(part, T, a, b, width=0.3, thick=0.05, binder=True):
    a, b = Vector(a), Vector(b)
    d = b - a
    bm = geo.box(width, d.length, thick, bevel=0.0)
    T.planar(bm, "webbing", u_axis=(0, 1, 0), v_axis=(1, 0, 0))
    part.add(bm, "trim", at=tuple((a + b) / 2), rot=frame_rot(d))
    if binder:
        box = geo.box(width * 1.4, 0.6, 0.18, bevel=0.0)
        T.fill(box, "cord")
        part.add(box, "trim", at=tuple(a.lerp(b, 0.35)), rot=frame_rot(d))


def rig(a, T, name, pads, straps):
    part = a.part(name, path=name.replace("Rigging", "Rig"), tex="airdrop", query=False, collide=False, material="Fabric",
                  smooth_angle=30)
    a.pivot(name.replace("Rigging", "Rig"), (0, 0, 0))
    for (x, y, z0, z1, sx, sy) in pads:
        part.add(pad(T, sx, sy, z1 - z0), "trim", at=(x, y, (z0 + z1) / 2))
    for s in straps:
        strap(part, T, *s)


def tank_rig(a, T):
    pads = []
    for x in (-4.35, 4.35):
        for y in (-8.3, -2.77, 2.77, 8.3):
            pads.append((x, y, DECK, PAD_TOP, 2.3, 5.0))
    for y in (-5.5, 5.5):  # under the belly (hull bottom 1.5 above the track shoes)
        pads.append((0.0, y, DECK, PAD_TOP + 1.5, 5.2, 4.2))
    straps = []
    for sx in (-1, 1):
        for y0, dy in ((9.5, 2.2), (3.2, 1.8), (-3.2, -1.8), (-9.5, -2.2)):
            straps.append(((sx * (W / 2 + 0.05), y0, RAIL_H - 0.15), (sx * 5.55, y0 + dy, PAD_TOP + 3.2)))
        straps.append(((sx * 3.2, L / 2 - 0.4, DECK + 0.1), (sx * 3.0, 12.7, PAD_TOP + 2.6)))  # front tow eyes
        straps.append(((sx * 3.2, -L / 2 + 0.4, DECK + 0.1), (sx * 3.0, -14.1, PAD_TOP + 2.8)))  # rear tow hooks
    rig(a, T, "TankRigging", pads, straps)


def buggy_rig(a, T):
    pads = []
    for x in (-3.35, 3.35):
        for y in (-4.3, 4.3):
            pads.append((x, y, DECK, PAD_TOP, 1.6, 2.6))
    pads.append((0.0, 0.3, DECK, PAD_TOP + 0.9, 4.0, 5.0))  # under the frame (0.9 above the tyres' contact)
    straps = []
    for sx in (-1, 1):
        for y in (-4.3, 4.3):
            hub = (sx * 3.9, y, PAD_TOP + 1.35)
            straps.append(((sx * (W / 2 + 0.05), y + 1.6, RAIL_H - 0.15), hub, 0.26))
            straps.append(((sx * (W / 2 + 0.05), y - 1.6, RAIL_H - 0.15), hub, 0.26))
    rig(a, T, "BuggyRigging", pads, [(s[0], s[1], s[2]) for s in straps])


def slings(a, T):
    part = a.part("Slings", tex="airdrop", query=False, collide=False, material="Fabric", smooth_angle=30, shadow=False)
    apex = Vector((0, 0, APEX))
    for k in CORNERS:
        c = corner(k)
        strap(part, T, c + Vector((0, 0, 0.2)), apex - (apex - c).normalized() * 0.6, width=0.4, thick=0.08, binder=False)
    link = geo.torus(0.45, 0.12, verts=10, ring_verts=4)
    T.fill(link, "cord")
    part.add(link, "trim", at=(0, 0, APEX), rot=(0, 90, 0))


def build(**kw):
    a = Asset("DropPlatform", pivot=(0, 0, 0), tex_size=512)
    a.fix_inside_out = True
    a.preview_hide_transparent = True
    a.meta["no_ground"] = True  # seen from below while it descends
    a.meta["no_wreck"] = True  # never charred: no burnt Wreck folders from the trim sheet
    T = trim.use(a, "trim", "TrimEnemy")
    TA = trim.use(a, "airdrop", "TrimAirdrop")
    a.material("lamp", kind="flat", color="#ff5c3d")
    platform(a, T)
    tank_rig(a, TA)
    buggy_rig(a, TA)
    slings(a, TA)
    views = [
        {"label": "", "pos": (17, 21, 13), "look": (0, 0, 1.5), "fov": 45, "res": (1280, 900), "hide": ["BuggyRigging", "Slings"]},
        {"label": "_below", "pos": (13, 17, -11), "look": (0, 0, 0.5), "fov": 45, "res": (1280, 900), "hide": ["BuggyRigging", "Slings"]},
        {"label": "_buggy", "pos": (15, 18, 11), "look": (0, 0, 1.5), "fov": 45, "res": (1280, 900), "hide": ["TankRigging", "Slings"]},
        {"label": "_slings", "pos": (42, 50, 22), "look": (0, 0, 15), "fov": 45, "res": (1024, 1024), "hide": ["BuggyRigging"]},
    ]
    return a.finish(views=views, **kw)
