"""Emplacement turret gun assembly (HS-4): the yaw mount and the pitching
gun (shield, cradle, machine gun, rocket pod, missile rack), built for the
HS-3 high-poly bake (models/emplacement.py declares the `turret` and
`weapons` groups with high=...).

Contracts kept from HS-1/HS-2 (docs/ASSET_CONTRACTS.md):
- names/paths: TurretYaw/Mount, TurretGun/Cradle, TurretGun/MachineGun/
  {Gun, Belt, BeltRound, EjectCase}, TurretGun/RocketPod/Pod,
  TurretGun/MissileRack/{Rail, Missile1, Missile2}; markers Muzzle,
  RocketMuzzle, MissileMuzzle; pivots at the turret pivot.
- client/WeaponFxTurret swings RocketPod/MissileRack about the rear of
  their extents (models without a WorldPivot): Pod, Rail, Missile1/2 keep
  their HS-2 bounding boxes exactly (`HIT`, enforced by the build).
- client/EmplacementFx: barrel along +Y at z = 0.2 (jacket end y 3.66,
  muzzle 6.74), the belt path from the left ammo can into the feed tray,
  and the ejection port on the receiver's right side are unchanged.
- The shield stays inside its HS-1 envelope (top z <= 1.36) so the turret
  camera's view down the slope is unchanged.

Blender asset space: origin = turret pivot, +Y forward, +Z up.
"""
import math

from rmh import geo, hardsurface as hs
from rmh.asset import rb_box

BARREL_Z = 0.2
POD_X, POD_Z = 3.2, 0.3
RACK_X = -3.25
SY = 2.35  # shield plane (lower plate centre) along Y
RAKE = -10.0  # shield rake about X (top leans back toward the gunner)

# Roblox (centre, size) of the HS-2 parts whose extents drive the poses.
HIT = {
    "Pod": ((3.2, 0.4704, -0.42), (2.0, 2.3409, 3.56)),
    "Rail": ((-3.2975, -0.29, -0.35), (1.445, 1.18, 3.4)),
    "Missile1": ((-3.58, 0.445, -0.3505), (0.898, 0.55, 3.899)),
    "Missile2": ((-2.92, 0.445, -0.3505), (0.898, 0.55, 3.899)),
}


def along_y(bm, at):
    return geo.transform(bm, at, rot=(-90, 0, 0))


def plate(outline, thick=0.16, chamfer=0.035):
    """Armour plate: an (x, z) outline extruded `thick` along Y (centred),
    its front-face edges chamfered so the plate reads as cut steel."""
    bm = geo.prism(outline, thick, bevel=0.0)  # outline in XY, thickness along Z
    geo.transform(bm, rot=(90, 0, 0))  # XY outline -> XZ, thickness along Y
    if chamfer:
        hs.chamfer_edges(bm, lambda e: all(v.co.y < -thick * 0.49 for v in e.verts)
                         or all(v.co.y > thick * 0.49 for v in e.verts), chamfer)
    return bm


def _shield_frame(bm, at=(0, 0, 0), rot_z=0.0):
    """Place a piece built in shield space (origin at (0, SY, 0), plates in
    XZ) with the shield's rake."""
    return geo.transform(bm, at=(at[0], SY + at[1], at[2]), rot=(RAKE, 0, rot_z))


def materials(a):
    # HS-1 night-readable paint values, with chips and polish moved onto the
    # convex edges of the baked high poly (hard-surface language of HS-3).
    edges = {"edge_convex": True, "edge_convex_distance": 0.2, "polish": 0.25, "polish_color": "#8a8b84", "rough_breakup": 0.25}
    a.material("olive_t", base="olive_p", **edges)
    a.material("olive_dark_t", base="olive_dark_p", **edges)
    a.material("shield_t", base="shield", **edges)
    a.material("seat", kind="fabric", color="#3b3a2c", rough=0.8, wrinkle=0.3, dust=0.4)
    a.material("receiver", base="steel_dark", color="#3f3f3a", metal=0.55, rough=0.62, dust=0.4, grime=0.4, edge_convex=True, polish=0.35,
               photo={"id": "green_metal_rust", "scale": 2.4, "rough": 0.6, "height": 0.4})
    a.material("grip", base="rubber", color="#1c1a16")
    a.material("bore", kind="flat", color="#11100e", rough=0.8)
    a.material("cable", kind="rubber", color="#1d1c1a", rough=0.75, dust=0.35, dust_height=0.5)
    a.material("pod", base="olive_t", wear=0.5, marks=[{"lo": (1.5, 1.2, -2.0), "hi": (5.0, 1.45, 2.0), "color": "#c9a227"}],
               soot=[{"pos": (POD_X, -1.4, POD_Z), "dir": (0, -1, 0), "radius": 0.95, "length": 0.4, "spread": 0.2, "strength": 0.8},
                     {"pos": (POD_X, 2.2, POD_Z), "dir": (0, -1, 0), "radius": 0.9, "length": 0.35, "spread": 0.1, "strength": 0.45}])
    a.material("rocket_nose", base="olive_dark_t", color="#4d5236", marks=[{"lo": (1.5, 2.02, -2.0), "hi": (5.0, 2.09, 2.0), "color": "#c9a227"}])
    a.material("missile_body", kind="paint", color="#a39a7c", rough=0.5, wear=0.35, dust=0.45, grime=0.5, dust_color="#b3875f",
               chip_style="blotch", chip_scale=7.0, under="#7a7b78", edge_convex=True,
               marks=[{"lo": (-5, 1.35, -1), "hi": (-1, 1.5, 2), "color": "#c9a227"}, {"lo": (-5, -0.2, -1), "hi": (-1, -0.05, 2), "color": "#5a3a22"}])
    a.material("seeker", base="glass", color="#20282c", rough=0.05)
    # Soot on the MG muzzle brake and the barrel end.
    a.material("receiver_muzzle", base="receiver",
               soot=[{"pos": (0, 7.3, BARREL_Z), "dir": (0, -1, 0), "radius": 0.28, "length": 1.4, "spread": 0.1, "strength": 0.9}])


# --- yaw mount -------------------------------------------------------------------------

def turret_yaw(a):
    y = a.part("Mount", path="TurretYaw", tex="turret", query=False, material="Metal")
    y.add(geo.cylinder(1.35, 0.45, verts=32, bevel=0.0), "olive_dark_t", at=(0, 0, -2.85))
    for i in range(12):
        ang = 2 * math.pi * i / 12
        y.detail(hs.bolt_row((1.2 * math.cos(ang), 1.2 * math.sin(ang), -2.62), (1.2 * math.cos(ang), 1.2 * math.sin(ang), -2.62), 1, (0, 0, 1),
                             r=0.075, h=0.06), "steel_dark_p")
    base = [(-1.35, -3.9), (1.35, -3.9), (1.6, -1.2), (1.6, 1.4), (-1.6, 1.4), (-1.6, -1.2)]
    bp = geo.prism(base, 0.18, bevel=0.0)
    hs.chamfer_edges(bp, lambda e: all(v.co.z > 0.08 for v in e.verts), 0.04)
    y.add(bp, "olive_t", at=(0, 0, -2.5))
    for sx in (-1, 1):
        # Yoke cheek plate (was an inside-out side prism) with a flanged
        # lightening recess, a stiffening lip and base gussets.
        prof = [(-1.3, -2.45), (1.3, -2.45), (0.75, 0.1), (0.35, 0.55), (-0.35, 0.55), (-0.85, 0.1)]
        cheek = geo.side_prism(prof, 0.18, bevel=0.0)
        y.add(cheek, "olive_t", at=(sx * 1.3, 0, 0))
        x_out = sx * 1.39
        y.add(geo.cylinder(0.34, 0.02, verts=16, bevel=0.0), "olive_dark_t", at=(x_out + sx * 0.005, 0.0, -1.35), rot=(0, 90, 0))
        y.detail(geo.torus(0.36, 0.035, verts=20, ring_verts=5), "olive_t", at=(x_out, 0.0, -1.35), rot=(0, 90, 0))
        y.detail(hs.bolt_row((x_out, -1.1, -2.25), (x_out, 1.1, -2.25), 6, (sx, 0, 0), r=0.055, h=0.04), "steel_dark_p")
        for gy in (-1.0, 1.0):
            g = geo.prism([(0.0, 0.0), (0.42, 0.0), (0.0, 0.6)], 0.08, bevel=0.0)
            geo.transform(g, rot=(90, 0, 0))
            y.add(g, "olive_t", at=(sx * 1.39, gy, -2.41), rot=(0, 0, 0 if sx > 0 else 180))
        # Trunnion bearing housing with its bolted cap and a grease nipple.
        y.add(geo.cylinder(0.48, 0.34, verts=20, bevel=0.0), "olive_dark_t", at=(sx * 1.47, 0, 0), rot=(0, 90, 0))
        y.add(geo.cylinder(0.3, 0.1, verts=16, bevel=0.0), "olive_dark_t", at=(sx * 1.68, 0, 0), rot=(0, 90, 0))
        for k in range(6):
            ang = 2 * math.pi * k / 6
            y.detail(hs.bolt_row((sx * 1.64, 0.4 * math.cos(ang), 0.4 * math.sin(ang)), (sx * 1.64, 0.4 * math.cos(ang), 0.4 * math.sin(ang)), 1,
                                 (sx, 0, 0), r=0.05, h=0.04), "steel_dark_p")
        y.add(geo.cylinder(0.035, 0.12, verts=6, bevel=0.0), "handle", at=(sx * 1.77, 0.15, 0.2), rot=(0, 90, 0))
        y.add(geo.box(0.1, 0.18, 2.2, bevel=0.0), "olive_dark_t", at=(sx * 1.43, -0.1, -1.3), rot=(12, 0, 0))
    # Gunner seat on a post behind the gun, with a footrest bar.
    y.add(geo.cylinder(0.14, 1.0, verts=10, bevel=0.0), "steel_dark_p", at=(0, -3.2, -1.95))
    y.add(geo.cylinder(0.24, 0.12, verts=12, bevel=0.0), "steel_dark_p", at=(0, -3.2, -1.5))
    y.add(geo.box(1.25, 1.0, 0.22, bevel=0.06), "olive_dark_t", at=(0, -3.1, -1.4))
    y.add(geo.box(1.1, 0.9, 0.16, bevel=0.07), "seat", at=(0, -3.1, -1.21))
    y.add(geo.box(1.1, 0.16, 1.05, bevel=0.07), "seat", at=(0, -3.62, -0.62), rot=(-12, 0, 0))
    y.add(geo.box(1.2, 0.1, 1.1, bevel=0.0), "olive_dark_t", at=(0, -3.72, -0.64), rot=(-12, 0, 0))
    for sx in (-0.45, 0.45):  # seat-back straps
        y.detail(geo.box(0.12, 0.04, 0.9, bevel=0.01, segments=1), "seat", at=(sx, -3.53, -0.6), rot=(-12, 0, 0))
    y.add(geo.pipe_path([(-0.8, -2.1, -2.35), (-0.8, -1.8, -2.05), (0.8, -1.8, -2.05), (0.8, -2.1, -2.35)], 0.06, verts=6), "handle")
    # Traverse handwheel housing on the right plate (bare steel from use).
    y.add(geo.box(0.35, 0.6, 0.6, bevel=0.0), "olive_dark_t", at=(1.6, -0.9, -1.5))
    y.detail(hs.bolt_row((1.78, -1.12, -1.28), (1.78, -0.68, -1.28), 2, (1, 0, 0), r=0.04, h=0.03), "steel_dark_p")
    y.add(geo.torus(0.35, 0.04, verts=16, ring_verts=6), "handle", at=(1.82, -0.9, -1.5), rot=(0, 90, 0))
    for k in range(3):  # handwheel spokes
        ang = math.radians(90 + 120 * k)
        y.add(geo.pipe_path([(1.82, -0.9, -1.5), (1.82, -0.9 + 0.33 * math.cos(ang), -1.5 + 0.33 * math.sin(ang))], 0.025, verts=5), "handle")
    y.add(geo.cylinder(0.04, 0.22, verts=6, bevel=0.0), "handle", at=(1.92, -0.62, -1.5), rot=(0, 90, 0))


# --- shield and cradle -----------------------------------------------------------------

LOWER = [(-1.95, -1.675), (1.95, -1.675), (2.2, -1.43), (2.2, -0.23), (0.62, -0.23), (0.5, -0.34), (-0.5, -0.34), (-0.62, -0.23),
         (-2.2, -0.23), (-2.2, -1.43)]
UPPER_R = [(0.55, -0.3), (2.2, -0.3), (2.2, 0.35), (1.95, 1.18), (1.72, 1.33), (0.88, 1.33), (0.55, 0.95)]
WING = [(-0.35, -1.45), (0.35, -1.45), (0.35, 1.05), (0.12, 1.28), (-0.35, 1.28)]
CAP = [(-0.95, 0.78), (0.95, 0.78), (0.95, 1.1), (0.75, 1.3), (-0.75, 1.3), (-0.95, 1.1)]


def shield(a, g):
    lower = _shield_frame(plate(LOWER))
    g.add(lower, "shield_t")
    for sx in (-1, 1):
        up = plate([(sx * x, z) for x, z in UPPER_R])
        g.add(_shield_frame(up, at=(0, -0.02, 0)), "shield_t")
        # Wing plate on a hinge, swept back 28 degrees.
        w = plate(WING, thick=0.15)
        g.add(w, "shield_t", at=(sx * 2.45, SY - 0.35, -0.2), rot=(RAKE, 0, sx * -28))
        hx = sx * 2.2
        for kz in (-1.2, -0.3, 0.6):  # hinge knuckles on the gunner's side
            k = geo.cylinder(0.075, 0.24, verts=8, bevel=0.0)
            g.add(_shield_frame(k, at=(hx, -0.14, kz)), "olive_dark_t")
        g.add(_shield_frame(geo.cylinder(0.03, 2.1, verts=6, bevel=0.0), at=(hx, -0.14, -0.3)), "steel_dark_p")
        # Grab handle welded to each wing plate (worn to bare steel).
        g.add(geo.pipe_path([(sx * 2.35, SY - 0.55, 0.45), (sx * 2.35, SY - 0.75, 0.4), (sx * 2.35, SY - 0.75, -0.4), (sx * 2.35, SY - 0.55, -0.45)],
                            0.045, verts=6), "handle")
        # Vertical stiffeners and a horizontal angle on the gunner's side.
        for x in (sx * 1.1, sx * 1.95):
            st = geo.box(0.08, 0.2, 1.3, bevel=0.0)
            g.add(_shield_frame(st, at=(x, -0.17, 0.35)), "shield_t")
        # Bolt rows along the plate edges (bake) and weld beads on the joints.
        g.detail(_shield_frame(hs.bolt_row((sx * 0.72, -0.1, 1.2), (sx * 2.05, -0.1, 1.2), 5, (0, -1, 0), r=0.05, h=0.04)), "steel_dark_p")
        g.detail(_shield_frame(hs.bolt_row((sx * 2.08, -0.1, -0.2), (sx * 2.08, -0.1, 0.3), 2, (0, -1, 0), r=0.05, h=0.04)), "steel_dark_p")
        g.detail(_shield_frame(hs.weld([(sx * 0.62, -0.09, -0.26), (sx * 2.18, -0.09, -0.26)], r=0.035)), "weld")
        g.detail(_shield_frame(hs.weld([(sx * 0.56, -0.1, -0.26), (sx * 0.56, -0.1, 0.9)], r=0.03)), "weld")
        # Shield arms from the cradle with gussets.
        arm = geo.box(0.14, 0.62, 0.16, bevel=0.0)
        g.add(arm, "olive_dark_t", at=(sx * 0.9, SY - 0.42, -0.35))
        gus = geo.prism([(0.0, 0.0), (0.45, 0.0), (0.0, 0.4)], 0.06, bevel=0.0)
        geo.transform(gus, rot=(90, 0, 90))
        g.add(gus, "olive_dark_t", at=(sx * 0.9, SY - 0.73, -0.27))
    # Bolted cap plate over the barrel slot.
    cap = plate(CAP, thick=0.12)
    g.add(_shield_frame(cap, at=(0, 0.1, 0)), "shield_t")
    g.detail(_shield_frame(hs.bolt_row((-0.42, 0.04, 0.92), (0.42, 0.04, 0.92), 3, (0, -1, 0), r=0.05, h=0.04)), "steel_dark_p")
    # Lower plate: horizontal angle stiffener and edge bolts (gunner's side).
    g.add(_shield_frame(geo.box(4.2, 0.2, 0.08, bevel=0.0), at=(0, -0.17, -0.95)), "shield_t")
    g.detail(_shield_frame(hs.bolt_row((-2.0, -0.1, -0.5), (2.0, -0.1, -0.5), 9, (0, -1, 0), r=0.05, h=0.04)), "steel_dark_p")
    g.detail(_shield_frame(hs.bolt_row((-2.0, -0.1, -1.5), (2.0, -0.1, -1.5), 9, (0, -1, 0), r=0.05, h=0.04)), "steel_dark_p")
    # Armoured vision block on the left upper plate: hood, glass, a hinged
    # cover plate hooked open on the gunner's side.
    vx = -1.52
    hood = geo.tapered_box(0.5, 0.3, 0.26, top_scale=(0.9, 0.7), bevel=0.0)
    g.add(_shield_frame(hood, at=(vx, 0.2, 0.62)), "olive_dark_t")
    g.add(_shield_frame(geo.box(0.36, 0.04, 0.09, bevel=0.0), at=(vx, 0.36, 0.62)), "seeker")
    g.add(_shield_frame(geo.box(0.44, 0.04, 0.3, bevel=0.0), at=(vx, -0.2, 0.86)), "olive_dark_t")
    g.add(_shield_frame(geo.transform(geo.cylinder(0.03, 0.46, verts=6, bevel=0.0), rot=(0, 90, 0)), at=(vx, -0.15, 0.72)), "steel_dark_p")
    # Unit marking on the gunner's side of the shield.
    from models.emplacement import stencil

    stencil(a, "C-3-41", (-1.35, SY - 0.25, -0.95), (0, -0.985, 0.17), 0.3, wear=0.4, seed=70)
    stencil(a, "7.62", (1.35, SY - 0.25, -0.95), (0, -0.985, 0.17), 0.3, wear=0.45, seed=71)


def cradle(a):
    g = a.part("Cradle", path="TurretGun", tex="turret", query=False, material="Metal")
    g.add(geo.cylinder(0.24, 4.8, verts=16, bevel=0.0), "olive_dark_t", rot=(0, 90, 0))
    # U-channel cradle under the machine gun with a recoil buffer.
    g.add(geo.box(1.05, 3.2, 0.12, bevel=0.0), "olive_t", at=(0, 0.5, -0.52), hp=0.03)
    for sx in (-1, 1):
        cheek = geo.side_prism([(-1.1, -0.58), (2.1, -0.58), (2.1, -0.3), (1.6, -0.22), (-0.8, -0.22), (-1.1, -0.34)], 0.1, bevel=0.0)
        g.add(cheek, "olive_t", at=(sx * 0.48, 0, 0))
        for yy in (-0.3, 0.6, 1.5):  # lightening recesses (bake)
            g.detail(geo.torus(0.1, 0.02, verts=12, ring_verts=4), "olive_dark_t", at=(sx * 0.535, yy, -0.4), rot=(0, 90, 0))
    g.add(along_y(geo.cylinder(0.13, 1.2, verts=10, bevel=0.0), (0, 1.3, -0.72)), "olive_dark_t")
    # Weapon mounting arms (right: rocket pod, left: missile rack) with
    # bearing housings on the trunnion and bolted mounting shoes.
    for sx in (-1, 1):
        g.add(geo.cylinder(0.36, 0.5, verts=16, bevel=0.0), "olive_dark_t", at=(sx * 1.85, 0, 0), rot=(0, 90, 0))
        arm = geo.tapered_box(0.8, 1.25, 0.55, top_scale=(0.85, 0.8), bevel=0.0)
        g.add(arm, "olive_dark_t", at=(sx * 2.15, 0.2, -0.05), hp=0.06)
        g.add(geo.box(0.5, 0.9, 0.12, bevel=0.0), "olive_t", at=(sx * 2.15, 0.3, 0.28), hp=0.03)
        g.detail(hs.bolt_row((sx * 2.0, -0.05, 0.35), (sx * 2.0, 0.65, 0.35), 3, (0, 0, 1), r=0.05, h=0.04), "steel_dark_p")
        g.detail(hs.bolt_row((sx * 2.3, -0.05, 0.35), (sx * 2.3, 0.65, 0.35), 3, (0, 0, 1), r=0.05, h=0.04), "steel_dark_p")
        for k in range(6):
            ang = 2 * math.pi * k / 6
            g.detail(hs.bolt_row((sx * 2.11, 0.24 * math.cos(ang), 0.24 * math.sin(ang)), (sx * 2.11, 0.24 * math.cos(ang), 0.24 * math.sin(ang)),
                                 1, (sx, 0, 0), r=0.045, h=0.035), "steel_dark_p")
    # Elevation gear sector under the right trunnion (teeth in the bake):
    # a 70-degree annulus from below the trunnion to behind it.
    def sector(bm):
        geo.transform(bm, rot=(0, 90, 0))  # sector plane XY -> YZ (starts at -Z)
        return geo.transform(bm, rot=(0, 0, 180))  # sweep toward -Y (behind)

    arc = sector(geo.lathe([(0.9, -0.05), (1.22, -0.05), (1.22, 0.05), (0.9, 0.05)], verts=14, angle=math.radians(70)))
    g.add(arc, "olive_dark_t", at=(1.08, 0, 0), rot=(20, 0, 0))
    for k in range(18):
        tooth = geo.box(0.07, 0.07, 0.1, bevel=0.0)
        geo.transform(tooth, at=(1.26, 0, 0), rot=(0, 0, 0))
        geo.transform(tooth, rot=(0, 0, 70 * (k + 0.5) / 18))
        g.detail(sector(tooth), "steel_dark_p", at=(1.08, 0, 0), rot=(20, 0, 0))
    # Fire-control cables along the cradle to the mounting arms.
    for sx in (-1, 1):
        g.add(geo.pipe_path([(sx * 0.62, -0.6, -0.5), (sx * 1.2, -0.4, -0.45), (sx * 1.75, -0.2, -0.3), (sx * 1.95, 0.05, 0.2)], 0.04, verts=6),
              "cable", hp=0.0)
    shield(a, g)


# --- machine gun -------------------------------------------------------------------------

def machine_gun(a, smalls, belt_along, lay):
    mg = a.part("Gun", path="TurretGun/MachineGun", tex="weapons", query=False, material="Metal")
    z = BARREL_Z
    mg.add(geo.box(0.78, 2.9, 0.8, bevel=0.0), "receiver", at=(0, 0.25, z))
    # Top cover with a front hinge pin and rear latch; side plate panels.
    mg.add(geo.box(0.84, 1.5, 0.14, bevel=0.0), "receiver", at=(0, 0.75, z + 0.46))
    mg.add(geo.cylinder(0.05, 0.9, verts=8, bevel=0.0), "receiver", at=(0, 1.5, z + 0.46), rot=(0, 90, 0))
    mg.add(geo.box(0.3, 0.12, 0.08, bevel=0.0), "handle", at=(0, 0.02, z + 0.55))
    for sx in (-1, 1):
        mg.detail(geo.box(0.03, 1.9, 0.5, bevel=0.012, segments=1), "receiver", at=(sx * 0.4, 0.1, z - 0.05))
        mg.detail(hs.rivet_row((sx * 0.41, -0.85, z - 0.25), (sx * 0.41, 1.15, z - 0.25), 7, (sx, 0, 0), r=0.04), "receiver")
        mg.detail(hs.rivet_row((sx * 0.41, -0.85, z + 0.25), (sx * 0.41, 1.15, z + 0.25), 7, (sx, 0, 0), r=0.04), "receiver")
    # Ejection port with its dust cover hinged open (right side).
    mg.add(geo.box(0.02, 0.5, 0.2, bevel=0.0), "bore", at=(0.395, 0.35, z + 0.05))
    mg.add(geo.box(0.03, 0.5, 0.18, bevel=0.0), "receiver", at=(0.42, 0.35, z - 0.14), rot=(0, 55, 0))
    # Rear plate, spade grips, butterfly trigger, buffer tube.
    mg.add(geo.box(0.9, 0.18, 0.95, bevel=0.0), "receiver", at=(0, -1.3, z))
    mg.add(along_y(geo.cylinder(0.14, 0.3, verts=10, bevel=0.0), (0, -1.5, z + 0.05)), "receiver")
    for sx in (-1, 1):
        mg.add(geo.pipe_path([(sx * 0.3, -1.38, z - 0.3), (sx * 0.32, -1.62, z - 0.2), (sx * 0.32, -1.72, z + 0.35)], 0.05, verts=6), "handle")
        mg.add(geo.cylinder(0.085, 0.5, verts=10, bevel=0.0), "grip", at=(sx * 0.32, -1.7, z + 0.12), rot=(-8, 0, 0))
    mg.add(geo.box(0.32, 0.12, 0.2, bevel=0.0), "handle", at=(0, -1.55, z + 0.2))
    # Charging handle on the right.
    mg.add(geo.box(0.12, 0.35, 0.12, bevel=0.0), "handle", at=(0.47, 0.5, z + 0.05))
    mg.add(geo.cylinder(0.07, 0.25, verts=8, bevel=0.0), "handle", at=(0.6, 0.5, z + 0.05), rot=(0, 90, 0))
    # Front trunnion block.
    fb = geo.tapered_box(0.95, 0.55, 0.95, top_scale=(0.85, 0.85), bevel=0.0)
    mg.add(fb, "receiver", at=(0, 1.8, z - 0.02))
    mg.detail(hs.bolt_row((-0.43, 1.65, z + 0.25), (-0.43, 1.95, z + 0.25), 2, (-1, 0, 0), r=0.045, h=0.035), "receiver")
    mg.detail(hs.bolt_row((0.43, 1.65, z + 0.25), (0.43, 1.95, z + 0.25), 2, (1, 0, 0), r=0.045, h=0.035), "receiver")
    # Reflex sight on a dovetail bracket with a hood and a brightness knob.
    mg.add(geo.box(0.22, 0.6, 0.08, bevel=0.0), "receiver", at=(0, -0.55, z + 0.57))
    mg.add(geo.box(0.34, 0.5, 0.3, bevel=0.0), "olive_dark_t", at=(0, -0.55, z + 0.76), hp=0.04)
    mg.add(geo.tapered_box(0.38, 0.2, 0.34, top_scale=(1.0, 1.4), top_shift=(0, 0.04), bevel=0.0), "olive_dark_t", at=(0, -0.24, z + 0.78))
    mg.add(geo.box(0.3, 0.05, 0.26, bevel=0.0), "seeker", at=(0, -0.31, z + 0.78))
    mg.add(geo.cylinder(0.06, 0.08, verts=8, bevel=0.0), "handle", at=(0.21, -0.65, z + 0.8), rot=(0, 90, 0))
    # Barrel: perforated jacket, barrel, carry handle and muzzle brake.
    mg.add(along_y(geo.tube(0.26, 0.2, 1.6, verts=16), (0, 2.85, z)), "receiver")
    for yy in (2.15, 2.6, 3.05, 3.5):
        mg.add(along_y(geo.cylinder(0.29, 0.08, verts=16, bevel=0.0), (0, yy, z)), "receiver")
    for yy in (2.37, 2.82, 3.27):  # cooling holes between the rings (bake)
        for k in range(8):
            ang = 2 * math.pi * (k + 0.5 * (int(yy * 10) % 2)) / 8
            hole = geo.cylinder(0.055, 0.02, verts=8, bevel=0.0)
            mg.detail(hole, "bore", at=(0.262 * math.cos(ang), yy, z + 0.262 * math.sin(ang)), rot=(0, 90 - math.degrees(ang), 0))
    mg.add(along_y(geo.cylinder(0.13, 3.6, verts=12, bevel=0.0), (0, 5.0, z)), "receiver")
    mg.add(geo.pipe_path([(0, 3.9, z + 0.1), (0, 4.0, z + 0.42), (0, 4.5, z + 0.42), (0, 4.6, z + 0.1)], 0.045, verts=6), "handle")
    mg.add(along_y(geo.tube(0.2, 0.09, 0.55, verts=12), (0, 7.02, z)), "receiver_muzzle")
    for sx in (-1, 1):
        mg.add(geo.box(0.06, 0.3, 0.16, bevel=0.0), "receiver_muzzle", at=(sx * 0.2, 7.02, z))
    # Ammo can on its bracket feeding the belt into the tray.
    mg.add(geo.box(0.55, 1.15, 0.8, bevel=0.0), "olive_t", at=(-0.85, 0.55, z - 0.2), hp=0.04)
    mg.add(geo.box(0.6, 1.2, 0.08, bevel=0.0), "olive_t", at=(-0.85, 0.55, z + 0.22))
    mg.add(geo.pipe_path([(-1.05, 0.3, z + 0.26), (-1.0, 0.3, z + 0.34), (-0.7, 0.3, z + 0.34), (-0.65, 0.3, z + 0.26)], 0.03, verts=5), "handle")
    mg.add(geo.box(0.08, 0.2, 0.3, bevel=0.0), "olive_dark_t", at=(-1.14, 0.55, z + 0.05))
    for yy in (0.1, 1.0):  # can ribs (bake) and the bracket under it
        mg.detail(geo.box(0.58, 0.06, 0.8, bevel=0.01, segments=1), "olive_t", at=(-0.85, yy, z - 0.2))
    mg.add(geo.box(0.7, 1.3, 0.06, bevel=0.0), "olive_dark_t", at=(-0.8, 0.55, z - 0.63))
    mg.add(geo.box(0.06, 0.9, 0.5, bevel=0.0), "olive_dark_t", at=(-0.46, 0.55, z - 0.45))
    # Feed tray with guide walls and the feed-cover pawl housing.
    mg.add(geo.box(0.22, 0.9, 0.06, bevel=0.0), "olive_dark_t", at=(-0.5, 0.75, z + 0.3))
    for yy in (0.33, 1.17):
        mg.add(geo.box(0.24, 0.04, 0.12, bevel=0.0), "olive_dark_t", at=(-0.5, yy, z + 0.36))
    from models.emplacement import stencil

    stencil(a, "7.62", (-1.13, 0.55, z - 0.15), (-1, 0, 0), 0.2, up=(0, 0, 1), wear=0.35, seed=72)

    belt = a.part("Belt", path="TurretGun/MachineGun", tex="smalls", query=False, material="Metal")
    belt_along(belt, smalls, [(-1.0, 0.75, z + 0.2), (-0.95, 0.75, z + 0.44), (-0.8, 0.75, z + 0.56),
                              (-0.6, 0.75, z + 0.56), (-0.42, 0.75, z + 0.42)], 7, up=(0, 0, -1))
    # HS-2 motion templates (hidden; client/EmplacementFx clones them).
    fed = a.part("BeltRound", path="TurretGun/MachineGun", tex="smalls", query=False, shadow=False, material="Metal", transparency=1)
    fed.add_template(smalls["round"], at=(0, -0.22, 0), rot=lay((0, 0, 0)))
    for off in (-0.08, 0.1):
        fed.add_template(smalls["link"], at=(0, off, -0.035))
    case = a.part("EjectCase", path="TurretGun/MachineGun", tex="smalls", query=False, shadow=False, material="Metal", transparency=1)
    case.add_template(smalls["case"])


# --- rocket pod --------------------------------------------------------------------------

def rocket_pod(a):
    from models.emplacement import stencil

    lo, hi = rb_box(*HIT["Pod"])
    pod = a.part("Pod", path="TurretGun/RocketPod", tex="weapons", query=False, material="Metal", hitbox=(lo, hi))
    x0, z0 = POD_X, POD_Z
    pod.add(along_y(geo.cylinder(0.95, 3.2, verts=24, bevel=0.0), (x0, 0.4, z0)), "pod")
    for yy in (-1.15, 1.95):
        pod.add(along_y(geo.cylinder(1.0, 0.18, verts=24, bevel=0.0), (x0, yy, z0)), "olive_dark_t")
    for yy in (-0.2, 1.0):  # clamp bands with their bolt lugs
        pod.add(along_y(geo.cylinder(0.975, 0.12, verts=24, bevel=0.0), (x0, yy, z0)), "olive_dark_t")
        lug = geo.box(0.2, 0.14, 0.16, bevel=0.0)
        pod.add(lug, "olive_dark_t", at=(x0 - 0.7, yy, z0 + 0.7), rot=(0, -45, 0))
        pod.detail(geo.cylinder(0.035, 0.3, verts=6, bevel=0.0), "steel_dark_p", at=(x0 - 0.72, yy, z0 + 0.72), rot=(0, -45, 0))
    tubes = [(0.0, 0.0)] + [(0.58 * math.cos(math.pi / 6 + k * math.pi / 3), 0.58 * math.sin(math.pi / 6 + k * math.pi / 3)) for k in range(6)]
    for tx, tz in tubes:
        pod.add(along_y(geo.tube(0.26, 0.21, 0.2, verts=12), (x0 + tx, 2.1, z0 + tz)), "olive_dark_t")
        pod.add(along_y(geo.lathe([(0.2, 0.0), (0.2, 0.12), (0.14, 0.3), (0.05, 0.42), (0.0, 0.45)], verts=10), (x0 + tx, 1.72, z0 + tz)), "rocket_nose")
        # Rear: nozzle ring with a dark bore and the rocket's nozzle inside.
        pod.add(along_y(geo.tube(0.24, 0.13, 0.12, verts=10), (x0 + tx, -1.3, z0 + tz)), "steel_dark_p")
        pod.add(along_y(geo.cylinder(0.13, 0.02, verts=10, bevel=0.0), (x0 + tx, -1.25, z0 + tz)), "bore")
        pod.add(along_y(geo.lathe([(0.06, 0.0), (0.1, 0.12)], verts=8, close_top=False, close_bottom=False), (x0 + tx, -1.36, z0 + tz)),
                "steel_dark_p")
    # Rear bulkhead bolts (bake), umbilical connector and cable, top shoe,
    # suspension lugs and the carry handle.
    for k in range(10):
        ang = 2 * math.pi * k / 10
        pod.detail(hs.bolt_row((x0 + 0.88 * math.cos(ang), -1.25, z0 + 0.88 * math.sin(ang)),
                               (x0 + 0.88 * math.cos(ang), -1.25, z0 + 0.88 * math.sin(ang)), 1, (0, -1, 0), r=0.045, h=0.035), "steel_dark_p")
    pod.add(geo.cylinder(0.12, 0.2, verts=10, bevel=0.0), "steel_dark_p", at=(x0 - 0.62, -1.22, z0 + 0.62), rot=(-90, 0, 0))
    pod.add(geo.pipe_path([(x0 - 0.62, -1.25, z0 + 0.66), (x0 - 0.7, -1.22, z0 + 0.95), (x0 - 0.55, -0.6, z0 + 1.05), (x0 - 0.3, 0.0, z0 + 1.0)],
                          0.045, verts=6), "cable", hp=0.0)
    pod.add(geo.box(0.5, 1.0, 0.35, bevel=0.0), "olive_dark_t", at=(x0, 0.3, z0 + 1.0), hp=0.04)
    pod.detail(hs.bolt_row((x0 - 0.2, -0.1, z0 + 1.18), (x0 - 0.2, 0.7, z0 + 1.18), 3, (0, 0, 1), r=0.04, h=0.03), "steel_dark_p")
    pod.detail(hs.bolt_row((x0 + 0.2, -0.1, z0 + 1.18), (x0 + 0.2, 0.7, z0 + 1.18), 3, (0, 0, 1), r=0.04, h=0.03), "steel_dark_p")
    for yy in (-0.45, 1.05):
        pod.add(geo.box(0.16, 0.2, 0.2, bevel=0.0), "olive_dark_t", at=(x0, yy, z0 + 1.02))
        pod.add(geo.torus(0.09, 0.025, verts=8, ring_verts=4), "steel_dark_p", at=(x0, yy, z0 + 1.15), rot=(0, 90, 0))
    pod.add(geo.pipe_path([(x0 - 0.4, -0.3, z0 + 1.0), (x0 - 0.4, 0.0, z0 + 1.3), (x0 + 0.4, 0.0, z0 + 1.3), (x0 + 0.4, -0.3, z0 + 1.0)],
                          0.05, verts=6), "handle")
    stencil(a, "RKT 70", (x0 - 0.96, 0.2, z0), (-1, 0, 0), 0.24, up=(0, 0, 1), wear=0.35, seed=73)
    a.marker("RocketMuzzle", "TurretGun/RocketPod", (x0, 2.3, z0), size=(0.3, 0.3, 0.3), axis=(0, 1, 0))


# --- missile rack ------------------------------------------------------------------------

def missile_rack(a):
    lo, hi = rb_box(*HIT["Rail"])
    rack = a.part("Rail", path="TurretGun/MissileRack", tex="weapons", query=False, material="Metal", hitbox=(lo, hi))
    x0 = RACK_X
    # Launcher beam: a channel with flanges and lightening recesses.
    rack.add(geo.box(1.35, 3.4, 0.1, bevel=0.0), "olive_dark_t", at=(x0, 0.35, 0.11), hp=0.03)
    for sx in (-1, 1):
        rack.add(geo.box(0.1, 3.3, 0.28, bevel=0.0), "olive_dark_t", at=(x0 + sx * 0.62, 0.35, 0.0), hp=0.03)
        for yy in (-0.8, 0.1, 1.0, 1.7):
            rack.detail(geo.torus(0.09, 0.018, verts=12, ring_verts=4), "olive_dark_t", at=(x0 + sx * 0.675, yy, 0.0), rot=(0, 90, 0))
    rack.add(geo.box(1.2, 3.2, 0.06, bevel=0.0), "olive_dark_t", at=(x0, 0.35, -0.12))
    for sx in (-0.33, 0.33):  # launch rails with detents
        rack.add(geo.box(0.16, 3.2, 0.16, bevel=0.0), "steel_dark_p", at=(x0 + sx, 0.35, 0.22), hp=0.03)
        for yy in (-0.9, 0.35, 1.6):
            rack.detail(geo.box(0.2, 0.12, 0.05, bevel=0.01, segments=1), "steel_dark_p", at=(x0 + sx, yy, 0.31))
    # Launcher electronics with cooling fins, the coolant bottle with
    # straps and the umbilical cables to the rails.
    rack.add(geo.box(0.9, 0.9, 0.55, bevel=0.0), "olive_dark_t", at=(x0, -0.9, -0.36), hp=0.05)
    for k in range(5):
        rack.add(geo.box(0.14, 0.03, 0.4, bevel=0.0), "olive_dark_t", at=(x0 + 0.52, -0.9 - 0.3 + k * 0.15, -0.38))
    rack.detail(hs.bolt_row((x0 - 0.35, -1.36, -0.15), (x0 + 0.35, -1.36, -0.15), 3, (0, -1, 0), r=0.04, h=0.03), "steel_dark_p")
    rack.add(geo.cylinder(0.1, 0.12, verts=8, bevel=0.0), "steel_dark_p", at=(x0 - 0.2, -1.28, -0.45), rot=(-90, 0, 0))
    rack.add(geo.cylinder(0.16, 0.9, verts=12, bevel=0.0), "olive_t", at=(x0 - 0.32, -0.95, -0.72), rot=(0, 90, 0))
    for xx in (-0.55, -0.1):
        rack.detail(geo.torus(0.17, 0.02, verts=12, ring_verts=4), "steel_dark_p", at=(x0 + xx, -0.95, -0.72), rot=(0, 90, 0))
    for sx in (-0.33, 0.33):
        rack.add(geo.pipe_path([(x0 + sx * 0.6, -0.9, -0.08), (x0 + sx, -0.7, 0.08), (x0 + sx, -0.4, 0.14)], 0.035, verts=5), "cable", hp=0.0)
    for i, sx in enumerate((-0.33, 0.33)):
        name = f"Missile{i + 1}"
        lo, hi = rb_box(*HIT[name])
        m = a.part(name, path="TurretGun/MissileRack", tex="weapons", query=False, material="Metal", hitbox=(lo, hi))
        mx, mz = x0 + sx, 0.52
        body = [(0.0, -1.55), (0.12, -1.55), (0.14, -1.45), (0.2, -1.4), (0.2, 1.75), (0.18, 1.95), (0.12, 2.2), (0.0, 2.28)]
        m.add(along_y(geo.lathe(body[:5], verts=16, close_top=True), (mx, 0.0, mz)), "missile_body")
        m.add(along_y(geo.lathe([(0.2, 1.75), (0.18, 1.95), (0.12, 2.2), (0.0, 2.3)], verts=16, close_bottom=False), (mx, 0.0, mz)), "seeker")
        m.detail(geo.torus(0.2, 0.015, verts=16, ring_verts=4), "missile_body", at=(mx, 0.6, mz), rot=(90, 0, 0))
        m.detail(geo.box(0.06, 0.8, 0.03, bevel=0.01, segments=1), "missile_body", at=(mx, 0.3, mz + 0.2))
        for k in range(4):
            ang = 45 + k * 90
            fin = geo.prism([(0.18, -0.2), (0.62, -0.02), (0.62, 0.25), (0.18, 0.35)], 0.03, bevel=0.0)
            m.add(fin, "missile_body", at=(mx, -1.15, mz), rot=(-90, 0, ang))
            canard = geo.prism([(0.18, -0.05), (0.38, 0.05), (0.38, 0.15), (0.18, 0.2)], 0.025, bevel=0.0)
            m.add(canard, "missile_body", at=(mx, 1.55, mz), rot=(-90, 0, ang))
    a.marker("MissileMuzzle", "TurretGun/MissileRack", (x0 - 0.33, 2.45, 0.52), size=(0.3, 0.3, 0.3), axis=(0, 1, 0))


def build_turret(a, smalls, belt_along, lay):
    """Mount + gun assembly (call from models.emplacement.build)."""
    materials(a)
    turret_yaw(a)
    cradle(a)
    machine_gun(a, smalls, belt_along, lay)
    rocket_pod(a)
    missile_rack(a)
    a.marker("Muzzle", "TurretGun", (0, 7.4, BARREL_Z), size=(0.3, 0.3, 0.3), axis=(0, 1, 0))
