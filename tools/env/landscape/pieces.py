"""Landscape piece definitions: which terrain ops each mesh wraps, the grid
it is built on, how it is sculpted and how it is split and textured.

Coordinates are Roblox world studs (+Y up). Each piece's box clips the
mesh: open edges must fall where no camera sees them (inside another piece,
behind a rim or under the floor).
"""
from __future__ import annotations

from dataclasses import dataclass

from ops import Op

BUTTES = {
    # name: (centre x, centre z, height, radius) from TerrainBuilder.buildButtes
    "Butte1": (-380.0, -1120.0, 90.0, 80.0),
    "Butte2": (260.0, -1150.0, 110.0, 120.0),
    "Butte3": (-60.0, -1180.0, 60.0, 70.0),
    "Butte4": (620.0, -1060.0, 90.0, 90.0),
}


@dataclass(frozen=True)
class Style:
    base: float  # constant outward offset of wall faces (studs, on top of margin)
    amp: float  # strata ledge amplitude
    gully: float  # gully depth
    gully_scale: float  # studs; spacing of the meandering gullies
    base_top: float  # offset on flat tops
    talus: float  # fillet radius at the foot (studs)
    talus_fan: float  # extra fillet radius under gullies
    rough: float  # small-scale roughness of wall faces (studs)


@dataclass(frozen=True)
class Piece:
    name: str
    groups: tuple[str, ...]
    lo: tuple[float, float, float]
    hi: tuple[float, float, float]
    h: float  # grid spacing (studs)
    closing: float  # fills notches narrower than ~2x this (studs)
    sigma: float  # smoothing of the envelope (studs)
    margin: float  # minimum clearance over the gameplay terrain (studs)
    style: Style
    tris: int  # low-poly triangle budget for the piece
    plan_close: float = 0.0  # per-bed closing of the plan outline (studs): merges bulges into ledges
    smear_axis: int | None = None  # straight walls: 0 = along x, 1 = along z (grid axes of a bed slice)
    smear: float = 0.0  # studs; bulges are stretched this far along the wall (per bed, scaled by hardness)
    ring_center: tuple | None = None  # (x, z): inside ring_radius the smear follows circles around it
    ring_radius: float = 0.0
    material: str = "Sandstone"
    keep_clear: bool = False  # mesa: stay under the turret's sight lines and out of the gun pit
    max_density: float = 10.0  # px/stud cap (the rear wall under the title camera sits behind the title UI)
    smooth_zone: tuple = ()  # ((a xyz), (b xyz), radius): no ledges near this segment (a camera inside the rock)

    def selects(self, op: Op) -> bool:
        return op.group in self.groups


WALL = Style(base=1.4, amp=3.2, gully=3.4, gully_scale=110.0, base_top=0.35, talus=7.0, talus_fan=12.0, rough=1.0)
BUTTE = Style(base=1.2, amp=2.6, gully=2.6, gully_scale=60.0, base_top=0.3, talus=6.0, talus_fan=9.0, rough=0.9)
MESA = Style(base=0.25, amp=1.1, gully=0.9, gully_scale=40.0, base_top=0.1, talus=3.5, talus_fan=3.5, rough=0.45)

# Turret line of sight (QaDebug losCheck): sight lines from the turret pivot
# to every lane end at feet height (+0.5 over the live ground: floor 2.0,
# wash ends -3.3) and along the lanes at hip height. The mesa mesh stays
# LOS_CLEARANCE under the lowest of them. Gun pit: the emplacement's
# concrete ring (r 14.3, y 58..66.4) hides everything inside PIT_RADIUS.
TURRET_PIVOT = (0.0, 72.0, 0.0)
LOS_CLEARANCE = 1.2  # the QA check sees a convex decomposition, ~1 stud proud of the mesh
PIT_RADIUS, PIT_FLOOR = 14.6, 57.5

# The title camera (AimController title pan) sits on the rear wall's face at
# x -115..-25, y 128, z 150 and looks down over the ridge and mesa.
TITLE_CAM = (-70.0, 128.0, 150.0)

# Every camera the game uses (Roblox studs; vertical FOV in degrees; the
# viewport is ~1080 px tall): position (a segment for the title pan), the
# point it looks at (None: the turret, which can face anywhere ahead of it),
# and FOV. Texture density is sized for the nearest camera that can see a
# point.
CAMERAS = (
    (((-115.0, 128.0, 150.0), (-25.0, 128.0, 150.0)), (90.0, 0.0, -420.0), 60.0),
    (((0.0, 80.0, 13.0), (0.0, 80.0, 13.0)), None, 70.0),
    (((0.0, 80.0, 13.0), (0.0, 80.0, 13.0)), None, 32.0),
    (((430.0, 70.0, -700.0), (430.0, 70.0, -700.0)), (-20.0, 25.0, -190.0), 45.0),
    (((95.0, 30.0, -560.0), (95.0, 30.0, -560.0)), (-50.0, 70.0, -40.0), 45.0),
    (((60.0, 127.0, -140.0), (60.0, 127.0, -140.0)), (0.0, 72.0, 0.0), 60.0),
    (((-60.0, 152.0, -60.0), (60.0, 152.0, -60.0)), (0.0, 10.0, -360.0), 60.0),
)
VIEW_PX = 1080.0
ASPECT = 1190.0 / 1080.0
DENSITY_SLACK = 0.75  # accept this much texture magnification at the nearest camera
DENSITY_RANGE = (1.5, 10.0)


def needed_density(points):
    """px/stud each point needs so its texture is ~1:1 at the nearest camera."""
    import numpy as np

    p = np.asarray(points, dtype=np.float64)
    best = np.zeros(len(p))
    for (a, b), look, fov in CAMERAS:
        a, b = np.array(a), np.array(b)
        ab = b - a
        t = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-9), 0.0, 1.0) if ab @ ab > 0 else np.zeros(len(p))
        rel = p - (a + t[:, None] * ab)
        d = np.linalg.norm(rel, axis=1)
        if look is None:
            seen = rel[:, 2] < 0.0  # the turret looks anywhere ahead of the mesa
        else:
            fwd = np.array(look) - (a + b) / 2.0
            fwd /= np.linalg.norm(fwd)
            half = np.arctan(np.tan(np.radians(fov) / 2.0) * np.hypot(1.0, ASPECT)) + np.radians(6.0)
            seen = (rel @ fwd) > d * np.cos(half)
        need = VIEW_PX / (2.0 * np.maximum(d, 1.0) * np.tan(np.radians(fov) / 2.0))
        best = np.maximum(best, np.where(seen, need, 0.0))
    return np.clip(best * DENSITY_SLACK, *DENSITY_RANGE)

PIECES: dict[str, Piece] = {
    "Mesa": Piece(
        "Mesa", ("mesa",), (-100.0, -8.0, -100.0), (100.0, 64.0, 200.0), 0.9, 4.5, 0.7, 0.8, MESA,
        tris=60000, keep_clear=True, plan_close=4.0, smear=7.0, smear_axis=1, ring_center=(0.0, 0.0), ring_radius=82.0,
    ),
    "RearWall": Piece(
        "RearWall", ("rear",), (-830.0, -8.0, 116.0), (830.0, 158.0, 292.0), 1.5, 5.0, 1.5, 1.2, WALL,
        tris=30000, plan_close=9.0, smear_axis=0, smear=12.0, max_density=4.0,
        # The title pan runs inside a terrain bulge on this face: keep the rock
        # there one smooth convex mass so no ledge face passes near the lens.
        smooth_zone=((-122.0, 128.0, 150.0), (-18.0, 128.0, 150.0), 24.0),
    ),
    "FlankLeft": Piece(
        "FlankLeft", ("flankL",), (-845.0, -8.0, -1262.0), (-690.0, 168.0, 420.0), 1.5, 5.0, 1.5, 1.2, WALL,
        tris=24000, plan_close=8.0, smear_axis=1, smear=12.0,
    ),
    "FlankRight": Piece(
        "FlankRight", ("flankR",), (690.0, -8.0, -1262.0), (845.0, 168.0, 420.0), 1.5, 5.0, 1.5, 1.2, WALL,
        tris=32000, plan_close=8.0, smear_axis=1, smear=12.0,
    ),
    "FarWall": Piece(
        "FarWall", ("far",), (-1000.0, -8.0, -1462.0), (1000.0, 148.0, -1282.0), 2.0, 6.0, 2.0, 1.4, WALL,
        tris=18000, plan_close=9.0, smear_axis=0, smear=14.0,
    ),
}

for _name, (_x, _z, _height, _r) in BUTTES.items():
    _pad = _r + 40.0
    PIECES[_name] = Piece(
        _name, (_name,), (_x - _pad, -8.0, _z - _pad), (_x + _pad, _height + 10.0, _z + _pad), 1.25, 4.0, 1.2, 1.2, BUTTE,
        tris=int(2000 + _r * 50), plan_close=6.0, smear=10.0, ring_center=(_x, _z), ring_radius=_r + 60.0,
    )
