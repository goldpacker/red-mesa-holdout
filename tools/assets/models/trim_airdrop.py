"""TrimAirdrop: the airdrop's shared fabric sheet (HS-6). One 512² set
(colour / normal / roughness, no metalness) shared by the personnel
parachute, the cargo parachutes and the drop platform's rigging, so every
chute in the sky costs the same three textures.

Strips (see rmh/trim.py):
- `canopy`: parachute canopy fabric, one period = GORES_PER_PERIOD gores.
  U runs round the canopy (whole periods), V from the apex vent (v0) to
  the skirt hem (v1): vent tape, a red identification band, alternating
  olive gore panels that bulge between raised radial tapes, horizontal
  reinforcing tapes and the skirt band with line-attachment tabs.
- `webbing`: olive nylon webbing with selvedges and stitch rows (risers,
  lashing straps, slings, deployment bag).
- `cord`: braided suspension-line cord.
- `kraft`: honeycomb crush-pad sides (kraft paper facings between cell
  layers).

Build: tools/assets/build.sh TrimAirdrop (texture-only).
Palette: enemy olive canopy (art bible enemy family: dark, desaturated),
marking red #BA1C18 faded.
"""
import math

import bmesh

from rmh import geo, hardsurface as hs, trim

GORES_PER_PERIOD = 10
CANOPY_WORLD = 16.0  # studs from vent to hem that the strip represents
VENT_TAPE = 0.45  # y ranges along the strip (apex = 0)
RED_BAND = (0.45, 2.3)
HOOPS = (2.3, 7.4, 11.9)  # horizontal reinforcing tapes
SKIRT = 0.6

M_GORE_A, M_GORE_B, M_TAPE, M_RED = range(4)


def materials(s):
    fab = {"kind": "fabric", "dust": 0.0, "grime": 0.25, "wrinkle": 0.12, "wrinkle_scale": 5.0, "weave_amount": 0.15, "bump": 0.3}
    s.material("gore_a", **fab, color="#4a4c3a", rough=0.82, weave=70.0, var_scale=1.1)
    s.material("gore_b", **fab, color="#535641", rough=0.82, weave=70.0, var_scale=1.1)
    s.material("tape", **dict(fab, grime=0.4), color="#3b3d2f", rough=0.9, weave=110.0)
    s.material("gore_red", **fab, color="#8a1f19", rough=0.8, weave=70.0, var_scale=1.1)
    s.material("webbing", kind="fabric", color="#45472f", rough=0.88, weave=120.0, weave_amount=0.35, wrinkle=0.05,
               dust=0.0, grime=0.5, bump=0.4)
    s.material("cord", kind="fabric", color="#77755e", rough=0.85, weave=0.0, wrinkle=0.05, dust=0.0, grime=0.35, bump=0.4)
    s.material("kraft", kind="fabric", color="#9a7650", rough=0.95, weave=0.0, wrinkle=0.25, wrinkle_scale=2.0,
               dust=0.0, grime=0.9, bump=0.3)


# --- helpers ------------------------------------------------------------------------

def _grid(x0, x1, y0, y1, nx, ny, fz, mat):
    bm = bmesh.new()
    rows = []
    for j in range(ny + 1):
        y = y0 + (y1 - y0) * j / ny
        rows.append([bm.verts.new((x0 + (x1 - x0) * i / nx, y, fz(x0 + (x1 - x0) * i / nx, y))) for i in range(nx + 1)])
    for j in range(ny):
        for i in range(nx):
            f = bm.faces.new((rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]))
            f.material_index = mat
    return bm


def _mat(bm, idx):
    for f in bm.faces:
        f.material_index = idx
    return bm


def _add(dst, bm, at=(0, 0, 0), rot=(0, 0, 0)):
    geo.transform(bm, at, rot)
    return hs._join(dst, bm)


# --- strip patterns (x along U over one period, y across, surface at z = 0) ---------

def canopy(period, world):
    """Gore panels bulging between raised radial tapes; vent tape, red
    identification band, horizontal hoops and the skirt band."""
    gw = period / GORES_PER_PERIOD
    bm = bmesh.new()

    def bulge(x, y):
        f = (x / gw) % 1.0
        # Panels bulge between the radial tapes; a faint lengthwise ripple.
        return 0.05 * math.sin(math.pi * f) ** 0.8 + 0.006 * math.sin(2 * math.pi * y / 1.7 + 3.1 * math.floor(x / gw))

    bands = [(0.0, VENT_TAPE, None), (RED_BAND[0], RED_BAND[1], M_RED), (RED_BAND[1], world - SKIRT, None), (world - SKIRT, world, None)]
    for k in range(-1, GORES_PER_PERIOD + 1):
        x0, x1 = k * gw, (k + 1) * gw
        shade = M_GORE_A if k % 2 == 0 else M_GORE_B
        for y0, y1, mat in bands:
            ny = max(1, round((y1 - y0) / 0.5))
            _join(bm, _grid(x0, x1, y0, y1, 10, ny, bulge, shade if mat is None else mat))
        # Radial tape over the seam (full length).
        tape = geo.box(0.16, world + 0.02, 0.035, bevel=0.01, segments=1)
        _add(bm, _mat(tape, M_TAPE), (x0, world / 2, 0.012))
        # Line-attachment tab at the skirt, under the radial tape.
        tab = geo.box(0.22, 0.5, 0.05, bevel=0.012, segments=1)
        _add(bm, _mat(tab, M_TAPE), (x0, world - 0.2, 0.02))
    # Vent tape, hoops and skirt band run round the canopy (along U).
    for y0, y1 in ((0.0, VENT_TAPE), (world - SKIRT, world)):
        band = geo.box(period + 2 * gw, y1 - y0, 0.03, bevel=0.008, segments=1)
        _add(bm, _mat(band, M_TAPE), (period / 2, (y0 + y1) / 2, 0.022))
    for y in HOOPS:
        hoop = geo.box(period + 2 * gw, 0.12, 0.025, bevel=0.006, segments=1)
        _add(bm, _mat(hoop, M_TAPE), (period / 2, y, 0.035))
    return bm


def _join(dst, src):
    return hs._join(dst, src)


def webbing(period, world):
    """Flat webbing with rolled selvedges and two stitch rows."""
    bm = _grid(-0.3, period + 0.3, 0.0, world, int((period + 0.6) / 0.08), 6,
               lambda x, y: 0.012 * math.sin(2 * math.pi * x / 0.9 + 2.0 * y), 0)
    for y in (0.03, world - 0.03):
        edge = geo.box(period + 0.6, 0.06, 0.03, bevel=0.01, segments=1)
        _add(bm, edge, (period / 2, y, 0.012))
    n = int(period / 0.09)
    for k in range(-2, n + 2):
        for y in (0.11, world - 0.11):
            st = geo.box(0.05, 0.022, 0.012, bevel=0.0)
            _add(bm, st, ((k + 0.5) * period / n, y, 0.018))
    return bm


def cord(period, world, pitch=0.11):
    """Braided cord: crossing helical strands (height field)."""
    n = max(1, round(period / pitch))
    sp = period / n

    def fz(x, y):
        a = ((x + y * 0.8) / sp) % 1.0
        b = ((x - y * 0.8) / sp) % 1.0
        return 0.022 * max((1 - abs(a - 0.5) * 2) ** 0.7, (1 - abs(b - 0.5) * 2) ** 0.7) - 0.01

    return _grid(-0.2, period + 0.2, 0.0, world, int((period + 0.4) / 0.018), 14, fz, 0)


def kraft(period, world, layer=0.5, cell=0.12):
    """Honeycomb crush-pad side: paper facings every `layer` studs, cut
    cell walls between them (AO darkens the open cells)."""
    bm = _grid(-0.3, period + 0.3, 0.0, world, int((period + 0.6) / 0.25), 8,
               lambda x, y: -0.03 + 0.01 * math.sin(2 * math.pi * x / 3.1 + y), 0)
    layers = max(1, round(world / layer))
    for j in range(layers + 1):
        y = j * world / layers
        facing = geo.box(period + 0.6, 0.05, 0.05, bevel=0.01, segments=1)
        _add(bm, facing, (period / 2, y, 0.0))
    n = int(period / cell)
    for j in range(layers):
        yc = (j + 0.5) * world / layers
        for k in range(-2, n + 2):
            x = (k + 0.5) * period / n
            wall = geo.box(0.014, world / layers - 0.06, 0.05 if k % 2 else 0.035, bevel=0.0)
            _add(bm, wall, (x, yc, -0.01), rot=(0, 0, 8 if k % 2 else -8))
    return bm


def build(samples=24, preview=True, **kw):
    s = trim.TrimSheet("TrimAirdrop", size=512, gutter=6, metal=False)
    materials(s)
    s.strip("canopy", 224, CANOPY_WORLD, canopy, ["gore_a", "gore_b", "tape", "gore_red"], relief=(0.08, 0.04))
    s.strip("webbing", 32, 0.5, webbing, "webbing", relief=(0.04, 0.02))
    s.strip("cord", 16, 0.25, cord, "cord", relief=(0.03, 0.02))
    s.strip("kraft", 128, 2.0, kraft, "kraft", relief=(0.06, 0.06))
    return s.finish(samples=samples, preview=preview)
