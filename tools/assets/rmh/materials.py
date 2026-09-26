"""Procedural PBR materials with wear, designed to be baked.

Every material ends in a Principled BSDF whose Base Color / Roughness /
Metallic / Normal inputs are what `bake.py` captures. Coordinates are
object space; parts are built at the asset origin so wear patterns are
continuous across parts.

Material specs are plain dicts, e.g.
    {"kind": "paint", "color": "#6b6f45", "wear": 0.5, "dust": 0.6}
Colours are sRGB hex or (r, g, b) 0..1 sRGB.
"""
import math
from pathlib import Path

import bpy
import numpy as np

DUST = "#b79b78"
GRIME = "#2b2520"
CC0_DIR = Path(__file__).resolve().parents[3] / "assets" / "source" / "cc0"
_PHOTO_CACHE = {}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(value):
    if isinstance(value, str):
        h = value.lstrip("#")
        value = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(srgb_to_linear(c) for c in value[:3]) + (1.0,)


def scale_rgb(value, k):
    r = rgb(value)
    return (r[0] * k, r[1] * k, r[2] * k, 1.0)


class G:
    """Tiny node-graph helper."""

    def __init__(self, mat):
        self.mat = mat
        self.nt = mat.node_tree
        self.nodes = self.nt.nodes
        self.links = self.nt.links
        self.x = -1600

    def node(self, kind, **props):
        n = self.nodes.new(kind)
        n.location = (self.x, 0)
        self.x += 40
        for k, v in props.items():
            setattr(n, k, v)
        return n

    def link(self, src, dst):
        self.links.new(src, dst)

    def _set(self, sock, v):
        if hasattr(v, "is_output"):
            self.link(v, sock)
        else:
            sock.default_value = v

    @staticmethod
    def sock(node, ident, out=False):
        coll = node.outputs if out else node.inputs
        for s in coll:
            if s.identifier == ident:
                return s
        for s in coll:
            if s.name == ident and s.enabled:
                return s
        raise KeyError(ident)

    # --- sources --------------------------------------------------------
    def coords(self, obj=None):
        n = self.node("ShaderNodeTexCoord")
        if obj is not None:
            n.object = obj
        return n.outputs["Object"]

    def geometry(self):
        return self.node("ShaderNodeNewGeometry")

    def mapping(self, vec, scale=(1, 1, 1), loc=(0, 0, 0)):
        n = self.node("ShaderNodeMapping")
        self.link(vec, n.inputs["Vector"])
        n.inputs["Scale"].default_value = scale
        n.inputs["Location"].default_value = loc
        return n.outputs["Vector"]

    def noise(self, vec, scale=4.0, detail=4.0, rough=0.55, distortion=0.0, color=False):
        n = self.node("ShaderNodeTexNoise")
        self.link(vec, n.inputs["Vector"])
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Distortion"].default_value = distortion
        return n.outputs["Color" if color else "Fac"]

    def voronoi(self, vec, scale=4.0, feature="F1", output="Distance"):
        n = self.node("ShaderNodeTexVoronoi")
        n.feature = feature
        self.link(vec, n.inputs["Vector"])
        n.inputs["Scale"].default_value = scale
        return n.outputs[output]

    def wave(self, vec, scale=4.0, distortion=2.0, detail=2.0, direction="Z", bands=True):
        n = self.node("ShaderNodeTexWave")
        n.wave_type = "BANDS" if bands else "RINGS"
        if bands:
            n.bands_direction = direction
        else:
            n.rings_direction = direction
        self.link(vec, n.inputs["Vector"])
        n.inputs["Scale"].default_value = scale
        n.inputs["Distortion"].default_value = distortion
        n.inputs["Detail"].default_value = detail
        return n.outputs["Fac"]

    # --- math -----------------------------------------------------------
    def math(self, op, a, b=0.0, clamp=False):
        n = self.node("ShaderNodeMath", operation=op, use_clamp=clamp)
        self._set(n.inputs[0], a)
        self._set(n.inputs[1], b)
        return n.outputs[0]

    def maprange(self, v, a, b, c=0.0, d=1.0, clamp=True, smooth=False):
        n = self.node("ShaderNodeMapRange", clamp=clamp)
        if smooth:
            n.interpolation_type = "SMOOTHSTEP"
        self._set(n.inputs["Value"], v)
        n.inputs["From Min"].default_value = a
        n.inputs["From Max"].default_value = b
        n.inputs["To Min"].default_value = c
        n.inputs["To Max"].default_value = d
        return n.outputs["Result"]

    def vmath(self, op, a, b=None):
        n = self.node("ShaderNodeVectorMath", operation=op)
        self._set(n.inputs[0], a)
        if b is not None:
            self._set(n.inputs[1], b)
        return n.outputs["Value"] if op in ("DOT_PRODUCT", "LENGTH", "DISTANCE") else n.outputs["Vector"]

    def sep(self, vec):
        n = self.node("ShaderNodeSeparateXYZ")
        self.link(vec, n.inputs[0])
        return n.outputs

    def mix(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="RGBA")
        self._set(self.sock(n, "Factor_Float"), fac)
        self._set(self.sock(n, "A_Color"), a)
        self._set(self.sock(n, "B_Color"), b)
        return self.sock(n, "Result_Color", out=True)

    def mixf(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="FLOAT")
        self._set(self.sock(n, "Factor_Float"), fac)
        self._set(self.sock(n, "A_Float"), a)
        self._set(self.sock(n, "B_Float"), b)
        return self.sock(n, "Result_Float", out=True)

    def multiply_color(self, fac, a, b):
        n = self.node("ShaderNodeMix", data_type="RGBA", blend_type="MULTIPLY")
        self._set(self.sock(n, "Factor_Float"), fac)
        self._set(self.sock(n, "A_Color"), a)
        self._set(self.sock(n, "B_Color"), b)
        return self.sock(n, "Result_Color", out=True)

    def ramp(self, fac, stops):
        n = self.node("ShaderNodeValToRGB")
        self.link(fac, n.inputs["Fac"])
        els = n.color_ramp.elements
        while len(els) > 2:
            els.remove(els[-1])
        for i, (pos, col) in enumerate(stops):
            e = els[i] if i < 2 else els.new(pos)
            e.position = pos
            e.color = rgb(col)
        return n.outputs["Color"]

    # --- masks ----------------------------------------------------------
    def edge_mask(self, radius=0.06):
        bev = self.node("ShaderNodeBevel", samples=8)
        bev.inputs["Radius"].default_value = radius
        geo = self.geometry()
        d = self.vmath("DOT_PRODUCT", bev.outputs["Normal"], geo.outputs["Normal"])
        return self.maprange(self.math("SUBTRACT", 1.0, d), 0.01, 0.12), bev.outputs["Normal"]

    def ao_cavity(self, distance=0.8):
        ao = self.node("ShaderNodeAmbientOcclusion", samples=12)
        ao.inputs["Distance"].default_value = distance
        return self.math("SUBTRACT", 1.0, ao.outputs["AO"])

    def box_mask(self, co, lo, hi, soft=0.02):
        """1 inside the axis-aligned box [lo, hi] (object space)."""
        xyz = self.sep(co)
        total = None
        for i in range(3):
            if lo[i] is None:
                continue
            a = self.maprange(xyz[i], lo[i] - soft, lo[i] + soft)
            b = self.maprange(xyz[i], hi[i] - soft, hi[i] + soft, 1.0, 0.0)
            m = self.math("MULTIPLY", a, b)
            total = m if total is None else self.math("MULTIPLY", total, m)
        return total

    def decal_mask(self, decal):
        """Alpha of a projected image decal (see Asset.decal)."""
        co = self.coords(decal["empty"])
        uv = self.mapping(co, loc=(0.5, 0.5, 0.0))
        img = self.node("ShaderNodeTexImage", extension="CLIP", interpolation="Cubic")
        img.image = decal["image"]
        self.link(uv, img.inputs["Vector"])
        xyz = self.sep(co)
        depth = self.maprange(self.math("ABSOLUTE", xyz[2]), 0.45, 0.5, 1.0, 0.0)
        geo = self.geometry()
        facing = self.maprange(self.vmath("DOT_PRODUCT", geo.outputs["Normal"], decal["axis"]), 0.25, 0.45)
        m = self.math("MULTIPLY", img.outputs["Alpha"], depth)
        return self.math("MULTIPLY", m, facing), img.outputs["Color"]


def _photo_image(pid, stem):
    """A CC0 source map (tools/assets/cc0.py) plus its mean value (linear)."""
    path = CC0_DIR / pid / f"{stem}.jpg"
    key = str(path)
    if key in _PHOTO_CACHE:
        return _PHOTO_CACHE[key]
    if not path.exists():
        raise FileNotFoundError(f"{path} missing: run `python3 tools/assets/cc0.py fetch {pid}`")
    img = bpy.data.images.load(key, check_existing=True)
    if stem != "diff":
        img.colorspace_settings.name = "Non-Color"
    px = np.empty(len(img.pixels), dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(-1, 4)[::7, :3]
    if stem == "diff":
        px = np.where(px <= 0.04045, px / 12.92, ((px + 0.055) / 1.055) ** 2.4)
    mean = tuple(float(m) for m in px.mean(axis=0))
    _PHOTO_CACHE[key] = (img, mean)
    return img, mean


def _photo_tex(g, co, photo, stem):
    img, mean = _photo_image(photo["id"], stem)
    s = 1.0 / photo.get("scale", 1.0)
    vec = g.mapping(co, scale=(s, s, s), loc=tuple(photo.get("offset", (0.0, 0.0, 0.0))))
    n = g.node("ShaderNodeTexImage", projection="BOX", interpolation="Linear")
    n.projection_blend = photo.get("blend", 0.3)
    n.image = img
    g.link(vec, n.inputs["Vector"])
    return n, mean


def _photo_layers(g, spec, co, color, rough, height):
    """Opt-in CC0 detail (`photo={id, scale, color, sat, rough, height}`):
    the photo is box-projected in object space and only its *variation*
    (ratio to its mean colour) is multiplied into our palette colour, so
    the result keeps the art-bible colours; roughness and height get the
    photo's deviation from its mean."""
    photo = spec.get("photo")
    if not photo:
        return color, rough, height
    if photo.get("color", 0.0) > 0:
        n, mean = _photo_tex(g, co, photo, "diff")
        detail = g.vmath("DIVIDE", n.outputs["Color"], tuple(max(m, 1e-3) for m in mean))
        lum = g.vmath("DOT_PRODUCT", detail, (0.2126, 0.7152, 0.0722))
        detail = g.mix(photo.get("sat", 0.3), lum, detail)
        color = g.mix(photo["color"], color, g.multiply_color(1.0, color, detail))
    if photo.get("rough", 0.0) > 0:
        n, mean = _photo_tex(g, co, photo, "rough")
        dev = g.math("SUBTRACT", n.outputs["Color"], mean[0])
        rough = g.math("ADD", rough, g.math("MULTIPLY", dev, photo["rough"]), clamp=True)
    if photo.get("height", 0.0) > 0:
        n, mean = _photo_tex(g, co, photo, "disp")
        dev = g.math("SUBTRACT", n.outputs["Color"], mean[0])
        height = g.math("ADD", height, g.math("MULTIPLY", dev, photo["height"]))
    return color, rough, height


def _cloth_weathering(g, spec, co, color, rough, height, zmin):
    """Opt-in sandbag weathering: sun-bleached tops (`bleach`), damp dark
    bottoms (`damp`, `damp_height` above zmin) and dust packed into the
    seams and creases (`seam_dust`)."""
    geo = g.geometry()
    nz = g.sep(geo.outputs["Normal"])[2]
    z = g.sep(co)[2]
    breakup = g.noise(co, scale=spec.get("weather_scale", 3.0), detail=5.0, rough=0.6)
    if spec.get("bleach", 0) > 0:
        up = g.maprange(nz, 0.25, 0.95)
        m = g.math("MULTIPLY", up, g.maprange(breakup, 0.25, 0.7, 0.55, 1.0))
        color = g.mix(g.math("MULTIPLY", m, spec["bleach"]), color, rgb(spec.get("bleach_color", "#b3a383")))
        rough = g.mixf(g.math("MULTIPLY", m, spec["bleach"]), rough, 0.97)
    if spec.get("damp", 0) > 0:
        low = g.maprange(z, zmin, zmin + spec.get("damp_height", 0.2), 1.0, 0.0, smooth=True)
        low = g.math("MULTIPLY", low, g.maprange(breakup, 0.2, 0.6, 0.6, 1.0))
        down = g.maprange(nz, 0.3, -0.6)
        m = g.math("MULTIPLY", g.math("MAXIMUM", low, g.math("MULTIPLY", down, 0.6)), spec["damp"])
        color = g.mix(m, color, rgb(spec.get("damp_color", "#4a3b27")))
        rough = g.mixf(m, rough, spec.get("damp_rough", 0.72))
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", m, 0.1))
    if spec.get("seam_dust", 0) > 0:
        ao = g.node("ShaderNodeAmbientOcclusion", samples=16)
        ao.inputs["Distance"].default_value = spec.get("seam_distance", 0.12)
        cav = g.maprange(g.math("SUBTRACT", 1.0, ao.outputs["AO"]), 0.08, 0.45)
        fine = g.noise(co, scale=spec.get("seam_noise", 22.0), detail=4.0, rough=0.7)
        m = g.math("MULTIPLY", cav, g.maprange(fine, 0.3, 0.65, 0.5, 1.0))
        m = g.math("MULTIPLY", m, spec["seam_dust"])
        color = g.mix(m, color, rgb(spec.get("seam_color", "#c2a67c")))
        rough = g.mixf(m, rough, 0.98)
        height = g.math("ADD", height, g.math("MULTIPLY", m, 0.15))
    return color, rough, height


def _wear_layers(g, spec, co, color, rough, metal, height, edge, zmin):
    """Chips, grime, streaks and dust shared by hard-surface kinds."""
    wear = spec.get("wear", 0.4)
    dust = spec.get("dust", 0.5)
    grime = spec.get("grime", 0.5)
    # Paint chips along edges plus a few scattered scratches.
    if wear > 0 and spec.get("chip_style") == "blotch":
        # Opt-in: irregular chip blotches concentrated on edges, scattered
        # nicks on faces, and a dark rust/primer ring around each chip.
        cs = spec.get("chip_scale", 9.0)
        if spec.get("chip_bevel"):
            edge, _ = g.edge_mask(spec["chip_bevel"])
        n1 = g.maprange(g.noise(co, scale=cs, detail=8.0, rough=0.72), 0.32, 0.68)
        n2 = g.maprange(g.noise(co, scale=cs * 3.7, detail=6.0, rough=0.6), 0.32, 0.68)
        src = g.math("ADD", g.math("MULTIPLY", edge, 0.5), g.math("MULTIPLY", n1, 0.55))
        src = g.math("ADD", src, g.math("MULTIPLY", n2, 0.2))
        t = 1.25 - wear * 0.5
        ring = g.maprange(src, t - 0.12, t - 0.02)
        chip = g.maprange(src, t, t + 0.03)
        nick = g.maprange(g.noise(co, scale=cs * 2.2, detail=10.0, rough=0.8), 0.76 - wear * 0.03, 0.78 - wear * 0.03)
        chip = g.math("MAXIMUM", chip, nick)
        color = g.mix(g.math("MULTIPLY", ring, spec.get("ring", 0.55)), color, rgb(spec.get("ring_color", "#3b3124")))
        rough = g.mixf(g.math("MULTIPLY", ring, 0.5), rough, 0.8)
        under = spec.get("under", "#6d6a66")
        color = g.mix(chip, color, rgb(under))
        rough = g.mixf(chip, rough, spec.get("under_rough", 0.38))
        metal = g.mixf(chip, metal, spec.get("under_metal", 0.85))
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", chip, 0.45))
    elif wear > 0:
        n = g.noise(co, scale=spec.get("chip_scale", 9.0), detail=8.0, rough=0.7)
        chip_src = g.math("ADD", g.math("MULTIPLY", edge, 0.75), g.math("MULTIPLY", n, 0.55))
        t = 1.08 - wear * 0.42
        chip = g.maprange(chip_src, t, t + 0.05)
        spots = g.maprange(g.noise(co, scale=3.2, detail=10.0, rough=0.75), 0.74 - wear * 0.05, 0.76 - wear * 0.05)
        chip = g.math("MAXIMUM", chip, g.math("MULTIPLY", spots, 0.9))
        under = spec.get("under", "#6d6a66")
        color = g.mix(chip, color, rgb(under))
        rough = g.mixf(chip, rough, spec.get("under_rough", 0.38))
        metal = g.mixf(chip, metal, spec.get("under_metal", 0.85))
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", chip, 0.35))
    # Cavity grime and vertical rain/oil streaks.
    if grime > 0:
        cav = g.maprange(g.ao_cavity(), 0.15, 0.7)
        streak_n = g.noise(g.mapping(co, scale=(6.0, 6.0, 0.35)), scale=3.0, detail=3.0)
        streak = g.maprange(streak_n, 0.5, 0.8, 0.0, 0.5)
        gm = g.math("MULTIPLY", g.math("MAXIMUM", cav, streak), grime)
        color = g.mix(g.math("MULTIPLY", gm, 0.75), color, rgb(GRIME))
        rough = g.math("ADD", rough, g.math("MULTIPLY", gm, 0.12), clamp=True)
    # Dust: on upward faces and near the ground.
    if dust > 0:
        geo = g.geometry()
        nz = g.sep(geo.outputs["Normal"])[2]
        up = g.maprange(nz, 0.35, 0.9)
        z = g.sep(co)[2]
        low = g.maprange(z, zmin, zmin + spec.get("dust_height", 2.5), 1.0, 0.0)
        dn = g.noise(co, scale=2.2, detail=6.0, rough=0.6)
        base = g.math("MAXIMUM", g.math("MULTIPLY", up, spec.get("dust_up", 0.8)), low)
        dm = g.maprange(g.math("MULTIPLY", base, g.math("ADD", dn, 0.2)), 0.25, 0.75, 0.0, dust)
        color = g.mix(dm, color, rgb(spec.get("dust_color", DUST)))
        rough = g.mixf(dm, rough, 0.93)
        metal = g.mixf(dm, metal, 0.0)
    return color, rough, metal, height


def _apply_marks(g, spec, co, color, decals):
    for mark in spec.get("marks", []):
        m = g.box_mask(co, mark["lo"], mark["hi"], mark.get("soft", 0.02))
        color = g.mix(m, color, rgb(mark["color"]))
    if spec.get("decals", True):
        for d in decals:
            m, img_col = g.decal_mask(d)
            if d.get("color") is not None:
                color = g.mix(m, color, rgb(d["color"]))
            else:
                color = g.mix(m, color, img_col)
    return color


def _finish(g, color, rough, metal, height, bevel_normal, bump=0.25, bump_distance=0.05):
    bsdf = next(n for n in g.nodes if n.type == "BSDF_PRINCIPLED")
    g.link(color, bsdf.inputs["Base Color"])
    g._set(bsdf.inputs["Roughness"], rough)
    g._set(bsdf.inputs["Metallic"], metal)
    bmp = g.node("ShaderNodeBump")
    bmp.inputs["Strength"].default_value = bump
    bmp.inputs["Distance"].default_value = bump_distance
    g._set(bmp.inputs["Height"], height)
    if bevel_normal is not None:
        g.link(bevel_normal, bmp.inputs["Normal"])
    g.link(bmp.outputs["Normal"], bsdf.inputs["Normal"])


def build(name, spec, decals=(), zmin=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    g = G(mat)
    kind = spec.get("kind", "paint")
    builder = KINDS[kind]
    builder(g, spec, list(decals), spec.get("zmin", zmin))
    mat["rmh_spec"] = repr(spec)
    return mat


# --- material kinds ---------------------------------------------------------

def _paint(g, spec, decals, zmin):
    co = g.coords()
    base = spec["color"]
    var = g.noise(co, scale=spec.get("var_scale", 1.4), detail=5.0)
    color = g.mix(g.maprange(var, 0.3, 0.7), scale_rgb(base, 0.86), scale_rgb(base, 1.08))
    color = _apply_marks(g, spec, co, color, decals)
    rough = g.maprange(g.noise(co, scale=6.0), 0.3, 0.7, spec.get("rough", 0.55) - 0.08, spec.get("rough", 0.55) + 0.08)
    metal = spec.get("metal", 0.0)
    edge, bevn = g.edge_mask(spec.get("bevel", 0.05))
    height = g.math("MULTIPLY", g.noise(co, scale=40.0, detail=2.0), 0.15)
    if spec.get("panels"):
        lines = _panel_lines(g, co, spec["panels"], spec.get("panel_width", 0.035))
        color = g.mix(g.math("MULTIPLY", lines, 0.55), color, scale_rgb(base, 0.45))
        height = g.math("SUBTRACT", height, g.math("MULTIPLY", lines, 0.6))
    color, rough, height = _photo_layers(g, spec, co, color, rough, height)
    if spec.get("fade"):
        # Opt-in: sun-faded, chalky paint on upward faces, blotchy.
        nz = g.sep(g.geometry().outputs["Normal"])[2]
        fm = g.math("MULTIPLY", g.maprange(nz, 0.1, 0.9), g.maprange(g.noise(co, scale=1.1, detail=5.0), 0.3, 0.7, 0.4, 1.0))
        fm = g.math("MULTIPLY", fm, spec["fade"])
        color = g.mix(fm, color, rgb(spec.get("fade_color", "#8a8a66")))
        rough = g.mixf(fm, rough, 0.8)
    if spec.get("patches"):
        # Opt-in: touch-up paint patches in a slightly different shade.
        pm = g.maprange(g.noise(g.mapping(co, loc=(7.3, 2.1, 5.5)), scale=0.9, detail=2.0), 0.62, 0.64)
        color = g.mix(g.math("MULTIPLY", pm, spec["patches"]), color, rgb(spec.get("patch_color", "#4c5130")))
        rough = g.mixf(g.math("MULTIPLY", pm, spec["patches"]), rough, 0.5)
    color, rough, metal, height = _wear_layers(g, spec, co, color, rough, metal, height, edge, zmin)
    _finish(g, color, rough, metal, height, bevn, bump=spec.get("bump", 0.18))


def _panel_lines(g, co, spacing, width):
    """Thin grooves every `spacing` studs along each axis (panel seams)."""
    xyz = g.sep(co)
    total = None
    for i, sp in enumerate(spacing):
        if not sp:
            continue
        # Offset per axis so seams do not all line up.
        v = g.math("ADD", g.math("DIVIDE", xyz[i], sp), 0.37 * (i + 1))
        f = g.math("PINGPONG", v, 0.5)
        line = g.maprange(f, 0.0, width / sp, 1.0, 0.0)
        total = line if total is None else g.math("MAXIMUM", total, line)
    return total


def _metal(g, spec, decals, zmin):
    co = g.coords()
    base = spec.get("color", "#3a3b3d")
    n = g.noise(co, scale=5.0, detail=6.0)
    color = g.mix(g.maprange(n, 0.3, 0.7), scale_rgb(base, 0.8), scale_rgb(base, 1.15))
    edge, bevn = g.edge_mask(spec.get("bevel", 0.03))
    color = g.mix(g.math("MULTIPLY", edge, 0.8), color, scale_rgb(base, 1.9))
    rough = g.maprange(g.noise(co, scale=12.0), 0.3, 0.7, spec.get("rough", 0.42) - 0.1, spec.get("rough", 0.42) + 0.1)
    rough = g.mixf(edge, rough, 0.25)
    metal = spec.get("metal", 0.9)
    height = g.math("MULTIPLY", g.noise(co, scale=60.0, detail=2.0), 0.1)
    spec2 = dict(spec)
    spec2.setdefault("wear", 0.0)
    color, rough, height = _photo_layers(g, spec, co, color, rough, height)
    color, rough, metal, height = _wear_layers(g, spec2, co, color, rough, metal, height, edge, zmin)
    _finish(g, color, rough, metal, height, bevn, bump=spec.get("bump", 0.12))


def _fabric(g, spec, decals, zmin):
    co = g.coords()
    base = spec["color"]
    pattern = spec.get("pattern")
    if pattern == "gores":
        xyz = g.sep(co)
        ang = g.node("ShaderNodeMath", operation="ARCTAN2")
        g.link(xyz[1], ang.inputs[0])
        g.link(xyz[0], ang.inputs[1])
        count = spec.get("count", 12)
        k = g.math("MULTIPLY", ang.outputs[0], count / (2 * math.pi))
        m = g.math("FLOORED_MODULO", g.math("FLOOR", k), 2.0)
        color = g.mix(m, rgb(base), rgb(spec["color2"]))
    elif pattern == "camo":
        n1 = g.noise(co, scale=spec.get("camo_scale", 1.6), detail=3.0, distortion=0.6)
        n2 = g.noise(g.mapping(co, loc=(3.1, 1.7, 0.4)), scale=spec.get("camo_scale", 1.6) * 1.3, detail=3.0)
        c = g.mix(g.maprange(n1, 0.52, 0.56), rgb(base), rgb(spec["color2"]))
        color = g.mix(g.maprange(n2, 0.6, 0.64), c, rgb(spec.get("color3", base)))
    else:
        var = g.noise(co, scale=spec.get("var_scale", 2.0), detail=5.0)
        color = g.mix(g.maprange(var, 0.3, 0.7), scale_rgb(base, 0.82), scale_rgb(base, 1.1))
    color = _apply_marks(g, spec, co, color, decals)
    net_h = None
    if spec.get("net"):
        # Garnished camo net: leaf clusters on a mesh with dark gaps.
        net = spec["net"]
        warp = g.vmath("MULTIPLY", g.vmath("SUBTRACT", g.noise(co, scale=2.5, color=True), (0.5, 0.5, 0.5)), (0.5, 0.5, 0.5))
        wco = g.vmath("ADD", co, warp)
        sc = 1.0 / net.get("cell", 0.3)
        edge_d = g.voronoi(wco, scale=sc, feature="DISTANCE_TO_EDGE", output="Distance")
        gap = g.maprange(edge_d, net.get("gap", 0.07), 0.0)
        holes = g.maprange(g.noise(co, scale=3.0, detail=3.0), 0.58, 0.64)
        gap = g.math("MAXIMUM", gap, g.math("MULTIPLY", holes, 0.8))
        tone = g.voronoi(wco, scale=sc, feature="F1", output="Color")
        tint = g.vmath("ADD", g.vmath("MULTIPLY", tone, (0.5, 0.5, 0.5)), (0.75, 0.75, 0.75))
        color = g.multiply_color(1.0, color, tint)
        color = g.mix(g.math("MULTIPLY", gap, 0.9), color, rgb(net.get("gap_color", "#1b1a15")))
        leaf = g.maprange(edge_d, 0.0, 0.18)
        net_h = g.math("MULTIPLY", g.math("SUBTRACT", leaf, g.math("MULTIPLY", gap, 0.6)), 0.9)
    ws = spec.get("weave", 28.0)
    weave = g.math(
        "MULTIPLY",
        g.wave(g.mapping(co, scale=(ws, ws, ws)), scale=1.0, distortion=0.4, detail=0.0, direction="X"),
        g.wave(g.mapping(co, scale=(ws, ws, ws)), scale=1.0, distortion=0.4, detail=0.0, direction="Y"),
    )
    wrinkle = g.noise(co, scale=spec.get("wrinkle_scale", 3.0), detail=3.0, distortion=0.5)
    height = g.math("ADD", g.math("MULTIPLY", weave, spec.get("weave_amount", 0.25)), g.math("MULTIPLY", wrinkle, spec.get("wrinkle", 0.6)))
    if net_h is not None:
        height = g.math("ADD", height, net_h)
    edge, bevn = g.edge_mask(spec.get("bevel", 0.08))
    rough = spec.get("rough", 0.9)
    color, rough, height = _photo_layers(g, spec, co, color, rough, height)
    if spec.get("bleach") or spec.get("damp") or spec.get("seam_dust"):
        color, rough, height = _cloth_weathering(g, spec, co, color, rough, height, zmin)
    spec2 = dict(spec)
    spec2["wear"] = 0.0
    color, rough, metal, height = _wear_layers(g, spec2, co, color, rough, 0.0, height, edge, zmin)
    _finish(g, color, rough, 0.0, height, bevn, bump=spec.get("bump", 0.35))


def _rubber(g, spec, decals, zmin):
    spec = dict({"color": "#1f1f1f", "rough": 0.85, "wear": 0.0, "dust": 0.8, "grime": 0.3, "dust_height": 1.6}, **spec)
    co = g.coords()
    n = g.noise(co, scale=8.0, detail=4.0)
    color = g.mix(g.maprange(n, 0.3, 0.7), scale_rgb(spec["color"], 0.8), scale_rgb(spec["color"], 1.2))
    edge, bevn = g.edge_mask(0.04)
    height = g.math("MULTIPLY", g.noise(co, scale=30.0), 0.2)
    color, rough, metal, height = _wear_layers(g, spec, co, color, spec["rough"], 0.0, height, edge, zmin)
    _finish(g, color, rough, metal, height, bevn, bump=0.3)


def _wood(g, spec, decals, zmin):
    co = g.coords()
    base = spec.get("color", "#8a6a45")
    grain_dir = spec.get("grain", "X")
    sc = {"X": (0.25, 3.0, 3.0), "Y": (3.0, 0.25, 3.0), "Z": (3.0, 3.0, 0.25)}[grain_dir]
    grain = g.noise(g.mapping(co, scale=sc), scale=6.0, detail=8.0, rough=0.6, distortion=1.5)
    color = g.mix(g.maprange(grain, 0.35, 0.65), scale_rgb(base, 0.7), scale_rgb(base, 1.15))
    color = _apply_marks(g, spec, co, color, decals)
    edge, bevn = g.edge_mask(0.04)
    height = g.math("MULTIPLY", grain, 0.4)
    color, rough, metal, height = _wear_layers(g, spec, co, color, spec.get("rough", 0.75), 0.0, height, edge, zmin)
    _finish(g, color, rough, metal, height, bevn, bump=0.3)


def _rock(g, spec, decals, zmin):
    co = g.coords()
    warp = g.noise(co, scale=spec.get("warp_scale", 0.25), detail=3.0, color=True)
    wco = g.vmath("ADD", co, g.vmath("SUBTRACT", warp, (0.5, 0.5, 0.5)))
    strata = g.wave(g.mapping(wco, scale=(0.0, 0.0, spec.get("strata", 0.5))), scale=1.0, distortion=4.0, detail=3.0, direction="Z")
    blotch = g.noise(co, scale=spec.get("blotch_scale", 0.35), detail=4.0, rough=0.6)
    fac = g.math("ADD", g.math("MULTIPLY", strata, 0.55), g.math("MULTIPLY", blotch, 0.45))
    colors = spec.get("colors", ["#7a3a24", "#a2502e", "#c07a4a", "#8c4a30", "#d19a6a"])
    stops = [(i / (len(colors) - 1), c) for i, c in enumerate(colors)]
    color = g.ramp(fac, stops)
    n = g.noise(co, scale=1.8, detail=8.0, rough=0.65)
    color = g.multiply_color(g.maprange(n, 0.3, 0.7, 0.0, 0.3), color, rgb("#6a5040"))
    cracks = g.voronoi(g.vmath("ADD", co, warp), scale=spec.get("crack_scale", 0.6), feature="DISTANCE_TO_EDGE")
    patch = g.maprange(g.noise(co, scale=0.3, detail=2.0), 0.5, 0.6)
    crack = g.math("MULTIPLY", g.maprange(cracks, 0.0, 0.025, 1.0, 0.0), patch)
    color = g.mix(g.math("MULTIPLY", crack, 0.45), color, rgb("#3a2016"))
    grain = g.noise(co, scale=9.0, detail=6.0)
    height = g.math("ADD", g.math("MULTIPLY", n, 0.8), g.math("MULTIPLY", grain, 0.3))
    height = g.math("SUBTRACT", height, g.math("MULTIPLY", crack, 0.6))
    height = g.math("ADD", height, g.math("MULTIPLY", strata, 0.35))
    edge, bevn = g.edge_mask(0.25)
    color = g.mix(g.math("MULTIPLY", edge, 0.3), color, rgb("#cf9468"))
    spec2 = dict({"wear": 0.0, "dust": 0.6, "grime": 0.6, "dust_height": 0.0}, **spec)
    color, rough, metal, height = _wear_layers(g, spec2, co, color, 0.9, 0.0, height, edge, zmin)
    _finish(g, color, rough, 0.0, height, bevn, bump=spec.get("bump", 0.55), bump_distance=0.2)


def _flat(g, spec, decals, zmin):
    """Uniform material with light variation (glass, lenses, skin)."""
    co = g.coords()
    n = g.noise(co, scale=spec.get("var_scale", 6.0), detail=3.0)
    color = g.mix(g.maprange(n, 0.3, 0.7), scale_rgb(spec["color"], 0.9), scale_rgb(spec["color"], 1.08))
    color = _apply_marks(g, spec, co, color, decals)
    edge, bevn = g.edge_mask(spec.get("bevel", 0.03))
    height = g.math("MULTIPLY", n, 0.1)
    rough = spec.get("rough", 0.5)
    metal = spec.get("metal", 0.0)
    color, rough, height = _photo_layers(g, spec, co, color, rough, height)
    if spec.get("dust", 0) > 0 or spec.get("grime", 0) > 0:
        spec2 = dict(spec)
        spec2["wear"] = 0.0
        color, rough, metal, height = _wear_layers(g, spec2, co, color, rough, metal, height, edge, zmin)
    _finish(g, color, rough, metal, height, bevn, bump=spec.get("bump", 0.1))


def _concrete(g, spec, decals, zmin):
    """Cast concrete: formwork board seams on walls, slab joints on floors,
    tie holes, water stains, hairline cracks."""
    co = g.coords()
    xyz = g.sep(co)
    base = spec.get("color", "#9e8b6c")
    var = g.noise(co, scale=0.8, detail=6.0, rough=0.6)
    color = g.mix(g.maprange(var, 0.3, 0.7), scale_rgb(base, 0.82), scale_rgb(base, 1.08))
    fine = g.noise(co, scale=14.0, detail=4.0)
    color = g.mix(g.maprange(fine, 0.35, 0.75, 0.0, 0.25), color, scale_rgb(base, 0.7))
    geo = g.geometry()
    nz = g.math("ABSOLUTE", g.sep(geo.outputs["Normal"])[2])
    wall = g.maprange(nz, 0.8, 0.5)
    board = spec.get("board", 0.85)
    seam = g.maprange(g.math("FRACT", g.math("DIVIDE", xyz[2], board)), 0.0, 0.03, 1.0, 0.0)
    seam = g.math("MULTIPLY", seam, wall)
    joint = spec.get("joint", 6.5)
    jx = g.maprange(g.math("PINGPONG", xyz[0], joint / 2), 0.0, 0.05, 1.0, 0.0)
    jy = g.maprange(g.math("PINGPONG", xyz[1], joint / 2), 0.0, 0.05, 1.0, 0.0)
    joints = g.math("MULTIPLY", g.math("MAXIMUM", jx, jy), g.math("SUBTRACT", 1.0, wall))
    cracks = g.voronoi(g.vmath("ADD", co, g.noise(co, scale=1.5, color=True)), scale=0.35, feature="DISTANCE_TO_EDGE")
    crack = g.math("MULTIPLY", g.maprange(cracks, 0.0, 0.015, 1.0, 0.0), g.maprange(g.noise(co, scale=0.7), 0.5, 0.6))
    grooves = g.math("MAXIMUM", g.math("MAXIMUM", seam, joints), crack)
    color = g.mix(g.math("MULTIPLY", grooves, 0.7), color, scale_rgb(base, 0.45))
    stain = g.noise(g.mapping(co, scale=(2.5, 2.5, 0.18)), scale=1.6, detail=5.0)
    stain = g.math("MULTIPLY", g.maprange(stain, 0.45, 0.75, 0.0, 0.55), wall)
    color = g.mix(stain, color, rgb(spec.get("stain", "#4a3f33")))
    color = _apply_marks(g, spec, co, color, decals)
    height = g.math("SUBTRACT", g.math("MULTIPLY", fine, 0.35), g.math("MULTIPLY", grooves, 0.8))
    edge, bevn = g.edge_mask(0.08)
    rough = g.maprange(var, 0.3, 0.7, 0.82, 0.95)
    color, rough, height = _photo_layers(g, spec, co, color, rough, height)
    spec2 = dict({"wear": 0.0, "dust": 0.7, "grime": 0.8}, **spec)
    spec2["wear"] = 0.0
    color, rough, metal, height = _wear_layers(g, spec2, co, color, rough, 0.0, height, edge, zmin)
    _finish(g, color, rough, 0.0, height, bevn, bump=spec.get("bump", 0.45), bump_distance=0.08)


KINDS = {
    "concrete": _concrete,
    "paint": _paint,
    "metal": _metal,
    "fabric": _fabric,
    "rubber": _rubber,
    "wood": _wood,
    "rock": _rock,
    "flat": _flat,
}

# Shared palette (GAME_SPEC §13): outpost sand/tan/olive; enemy gunmetal + red.
PRESETS = {
    "olive": {"kind": "paint", "color": "#5d6238", "rough": 0.6, "wear": 0.45, "dust": 0.55, "grime": 0.5},
    "olive_dark": {"kind": "paint", "color": "#454a2a", "rough": 0.62, "wear": 0.4, "dust": 0.5, "grime": 0.5},
    "tan": {"kind": "paint", "color": "#a58c62", "rough": 0.62, "wear": 0.4, "dust": 0.45, "grime": 0.5},
    "gunmetal": {"kind": "paint", "color": "#34373b", "rough": 0.5, "wear": 0.4, "dust": 0.6, "grime": 0.5, "under": "#8a8a88"},
    "charcoal": {"kind": "paint", "color": "#26282b", "rough": 0.55, "wear": 0.35, "dust": 0.55, "grime": 0.4, "under": "#7c7c7a"},
    "enemy_red": {"kind": "paint", "color": "#9e1a16", "rough": 0.5, "wear": 0.5, "dust": 0.4, "grime": 0.4},
    "steel": {"kind": "metal", "color": "#3b3c3e", "rough": 0.42, "metal": 0.9, "dust": 0.35, "grime": 0.5},
    "steel_dark": {"kind": "metal", "color": "#232426", "rough": 0.5, "metal": 0.85, "dust": 0.3, "grime": 0.5},
    "brass": {"kind": "metal", "color": "#9a7a3a", "rough": 0.35, "metal": 1.0, "dust": 0.2, "grime": 0.3},
    "rubber": {"kind": "rubber"},
    "sandbag": {"kind": "fabric", "color": "#b39a6e", "rough": 0.95, "dust": 0.55, "grime": 0.55, "wrinkle": 0.8, "weave": 30.0},
    "canvas_olive": {"kind": "fabric", "color": "#5a5c3a", "rough": 0.9, "dust": 0.5, "grime": 0.5},
    "concrete": {"kind": "concrete", "color": "#9e8b6c", "dust": 0.7, "grime": 0.8},
    "wood_crate": {"kind": "wood", "color": "#7a6040", "rough": 0.8, "wear": 0.3, "dust": 0.5, "grime": 0.5},
    "glass": {"kind": "flat", "color": "#1a2226", "rough": 0.08, "metal": 0.2},
    "lens": {"kind": "flat", "color": "#e8e2c8", "rough": 0.15, "metal": 0.0},
    "skin": {"kind": "flat", "color": "#9a7058", "rough": 0.6, "bump": 0.2},
    "rock": {"kind": "rock"},
}
