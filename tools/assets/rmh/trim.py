"""Trim sheets (HS-3): one texture set shared by several assets.

A trim sheet is a texture-only asset (`models/trim_<name>.py`, built with
`tools/assets/build.sh Trim<Name>`). Its 1024² atlas holds

* **strips**: full-width bands that tile along U (track shoes, louvre
  grilles, mesh, bolted straps, canvas, wire rope, plain paint). Each is
  baked from a periodic high-poly pattern, and every procedural pattern in
  its material repeats with the same period (`materials` `periodic=`), so
  a surface can run U over any length without a seam;
* **templates**: whole meshes with their own UV islands (road wheels,
  sprockets, tyres, rims, jerrycans, ammo cans, tools, periscopes,
  headlights), packed at one texel density into the band below the strips.

Assets use it through a *shared* texture group: their parts carry UVs into
the sheet, nothing is baked, and the rbxmx points at the sheet's image ids
(`publish.py` resolves them from `assets/exported/<Trim>/roblox_ids.json`),
so every vehicle using the sheet shares the same four textures in memory.

Building a sheet (in a model file):
    s = trim.TrimSheet("TrimEnemy")
    s.material("steel", kind="metal", ...)
    s.strip("track", px=144, world=2.2, build=track_pattern, mat="steel", relief=(0.25, 0.1))
    s.template("jerrycan_red", hardsurface.jerrycan(), "red_can")
    return s.finish()

Using it (in an asset):
    T = trim.use(a, "trim", "TrimEnemy")
    p = a.part("TrackL", tex="trim")
    p.add(T.loop(bm, "track", profile), "trim")      # strip mappings return bm
    p.add(T.template("roadwheel"), "trim", at=..., rot=...)
Every face of a trim part must be mapped (build fails otherwise).
"""
import json
import math
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

from . import geo, hardsurface

ROOT = Path(__file__).resolve().parents[3]
MAPPED = "rmh_trim"
GROUP = "sheet"
CHANNELS = ("color", "rough", "metal", "normal")


def _uv_layer(bm):
    return bm.loops.layers.uv.get("UVMap") or bm.loops.layers.uv.new("UVMap")


def _flag(bm, faces):
    lay = bm.faces.layers.int.get(MAPPED) or bm.faces.layers.int.new(MAPPED)
    for f in faces:
        f[lay] = 1


def check_mapped(bm, name):
    """Every face of a trim part needs trim UVs (else it samples a corner)."""
    lay = bm.faces.layers.int.get(MAPPED)
    missing = sum(1 for f in bm.faces if lay is None or not f[lay])
    # The hit-box pad adds two tiny unmapped triangles; allow exactly those.
    if missing > 2:
        raise ValueError(f"part {name}: {missing} faces have no trim UVs (map every piece with the Trim helpers)")


# --- consumer side -------------------------------------------------------------

class Trim:
    """A trim sheet as seen by an asset (see `use`)."""

    def __init__(self, a, group, source):
        self.source = source
        self.group = group
        folder = ROOT / "assets" / "exported" / source
        data = json.loads((folder / "trim.json").read_text())
        self.size = data["size"]
        self.strips = data["strips"]
        self.templates = data["templates"]
        self.template_density = data.get("template_density")
        images = {}
        for ch, fname in data["files"].items():
            img = bpy.data.images.load(str(folder / fname), check_existing=True)
            if ch != "color":
                img.colorspace_settings.name = "Non-Color"
            images[ch] = img
        a.shared_group(group, source, self.size, images)
        if "trim" not in a.specs:
            a.material("trim", kind="flat", color="#777777", dust=0.0, grime=0.0)
        self.px = 1.0 / self.size

    # strip coordinates ----------------------------------------------------
    def _band(self, strip, band):
        s = self.strips[strip]
        v0, v1 = s["v0"] + self.px, s["v1"] - self.px
        return s, v0 + (v1 - v0) * band[0], v0 + (v1 - v0) * band[1]

    def _faces(self, bm, faces):
        # Create the layers first: adding a layer invalidates face references.
        _uv_layer(bm)
        if bm.faces.layers.int.get(MAPPED) is None:
            bm.faces.layers.int.new(MAPPED)
        bm.normal_update()
        return list(bm.faces) if faces is None else [f for f in bm.faces if faces(f)]

    def planar(self, bm, strip, u_axis=(1, 0, 0), v_axis=(0, 0, 1), band=(0.0, 1.0), u_offset=0.0, fit=True, faces=None, u_scale=1.0):
        """Map faces into `strip`: U = distance along `u_axis` / the strip's
        period (tiles), V = extent along `v_axis` fitted into the strip's
        height (`band` = sub-range 0..1 of it). Axes are in the piece's own
        space (call before Part.add transforms it). Returns bm."""
        s, v0, v1 = self._band(strip, band)
        ua, va = Vector(u_axis).normalized(), Vector(v_axis).normalized()
        sel = self._faces(bm, faces)
        uv = _uv_layer(bm)
        ts = [v.co.dot(va) for f in sel for v in f.verts]
        if not ts:
            return bm
        tmin, tmax = min(ts), max(ts)
        span = (tmax - tmin) if fit else s["world"]
        span = span if span > 1e-6 else 1.0
        for f in sel:
            for loop in f.loops:
                co = loop.vert.co
                t = (co.dot(va) - tmin) / span
                loop[uv].uv = (co.dot(ua) / s["period"] * u_scale + u_offset, v0 + (v1 - v0) * min(max(t, 0.0), 1.0))
        _flag(bm, sel)
        return bm

    def fill(self, bm, strip, band=(0.0, 1.0), faces=None):
        """Planar map along the piece's longest extent (small hardware,
        brackets, rails: anything where the exact pattern doesn't matter)."""
        vs = [v.co for v in bm.verts]
        ext = [max(c[i] for c in vs) - min(c[i] for c in vs) for i in range(3)]
        order = sorted(range(3), key=lambda i: -ext[i])
        axes = [Vector([1.0 if i == k else 0.0 for i in range(3)]) for k in order]
        return self.planar(bm, strip, axes[0], axes[1], band=band, faces=faces)

    def cylindrical(self, bm, strip, axis=(0, 0, 1), center=(0, 0, 0), band=(0.0, 1.0), periods=None, faces=None, along=False):
        """Wrap `strip` round an axis: U = angle (a whole number of periods
        round the circumference, so no seam), V = position along the axis
        fitted into the band (wheels, drums). `along=True` turns it round:
        U = distance along the axis (tiles), V = angle round the strip's
        height (cables, whips, rolled canvas)."""
        s, v0, v1 = self._band(strip, band)
        ax = Vector(axis).normalized()
        c = Vector(center)
        ref = Vector((1, 0, 0)) if abs(ax.x) < 0.9 else Vector((0, 1, 0))
        e1 = (ref - ax * ref.dot(ax)).normalized()
        e2 = ax.cross(e1)
        sel = self._faces(bm, faces)
        pts = [v.co - c for f in sel for v in f.verts]
        if not pts:
            return bm
        radius = max((p - ax * p.dot(ax)).length for p in pts)
        n = periods or max(1, round(2 * math.pi * radius / s["period"]))
        ts = [p.dot(ax) for p in pts]
        tmin, tmax = min(ts), max(ts)
        span = (tmax - tmin) or 1.0
        uv = _uv_layer(bm)
        for f in sel:
            us = []
            for loop in f.loops:
                p = loop.vert.co - c
                us.append(math.atan2(p.dot(e2), p.dot(e1)) / (2 * math.pi))
            if not along and max(us) - min(us) > 0.5:
                us = [u + 1.0 if u < 0 else u for u in us]
            for loop, u in zip(f.loops, us):
                d = (loop.vert.co - c).dot(ax)
                if along:
                    # V ping-pongs round the circumference: no seam (V can't wrap).
                    frac = u % 1.0
                    loop[uv].uv = (d / s["period"], v0 + (v1 - v0) * (1.0 - abs(2.0 * frac - 1.0)))
                else:
                    loop[uv].uv = (u * n, v0 + (v1 - v0) * (d - tmin) / span)
        _flag(bm, sel)
        return bm

    def loop(self, bm, strip, profile, width_axis=0, band=(0.0, 1.0), closed=True, faces=None, periods=None):
        """Map a band that runs round a 2D `profile` (list of (a, b) points
        in the plane of the two axes other than `width_axis`, e.g. a track
        loop built with geo.side_prism): U = arc length along the profile
        (a whole number of periods when closed), V = across (width axis)."""
        s, v0, v1 = self._band(strip, band)
        axes = [i for i in range(3) if i != width_axis]
        pts = [Vector(p) for p in profile] + ([Vector(profile[0])] if closed else [])
        cum = [0.0]
        for a, b in zip(pts, pts[1:]):
            cum.append(cum[-1] + (b - a).length)
        total = cum[-1]
        n = periods or max(1, round(total / s["period"]))
        scale = n / total if closed else 1.0 / s["period"]
        sel = self._faces(bm, faces)
        ws = [v.co[width_axis] for f in sel for v in f.verts]
        if not ws:
            return bm
        wmin, wmax = min(ws), max(ws)
        span = (wmax - wmin) or 1.0
        uv = _uv_layer(bm)

        def param(co):
            q = Vector((co[axes[0]], co[axes[1]]))
            best, arc = 1e9, 0.0
            for i, (a, b) in enumerate(zip(pts, pts[1:])):
                ab = b - a
                t = max(0.0, min(1.0, (q - a).dot(ab) / (ab.length_squared or 1.0)))
                d = (a + ab * t - q).length
                if d < best:
                    best, arc = d, cum[i] + ab.length * t
            return arc

        for f in sel:
            us = [param(loop.vert.co) * scale for loop in f.loops]
            if closed and max(us) - min(us) > n / 2:
                us = [u + n if u < n / 2 else u for u in us]
            for loop, u in zip(f.loops, us):
                t = (loop.vert.co[width_axis] - wmin) / span
                loop[uv].uv = (u, v0 + (v1 - v0) * t)
        _flag(bm, sel)
        return bm

    def template(self, name):
        """A fresh bmesh of template `name` with its sheet UVs (template-
        local space: origin at its base / axle, as built)."""
        t = self.templates[name]
        bm = bmesh.new()
        uv = _uv_layer(bm)
        bm.faces.layers.int.new(MAPPED)
        verts = [bm.verts.new(co) for co in t["verts"]]
        for idx, uvs in zip(t["faces"], t["uvs"]):
            try:
                f = bm.faces.new([verts[i] for i in idx])
            except ValueError:
                continue
            for loop, (u, v) in zip(f.loops, uvs):
                loop[uv].uv = (u, v)
        _flag(bm, bm.faces)
        return bm


def use(a, group, source):
    """Declare texture group `group` of asset `a` as the trim sheet `source`."""
    return Trim(a, group, source)


# --- building a sheet ----------------------------------------------------------

class _Strip:
    def __init__(self, name, px, world, build, mat, relief):
        self.name, self.px, self.world, self.build, self.mat, self.relief = name, px, world, build, mat, relief


class _Tpl:
    def __init__(self, name, low, mat, high, hp, smooth):
        self.name, self.low, self.mat, self.high, self.hp, self.smooth = name, low, mat, high, hp, smooth


class TrimSheet:
    def __init__(self, name, size=1024, gutter=8):
        from .asset import Asset

        self.asset = Asset(name, tex_size=size)
        self.name = name
        self.size = size
        self.gutter = gutter
        self.strips = []
        self.templates = []

    def material(self, name, **spec):
        return self.asset.material(name, **spec)

    def strip(self, name, px, world, build, mat, relief=(0.2, 0.2)):
        """Add a strip `px` pixels tall representing `world` studs across.
        `build(period, world)` returns the high-poly pattern in strip space:
        X along U over [0, period) — repeat whole elements and overhang one
        past both ends so the bake tiles —, Y across over [0, world], the
        mean surface at z = 0 with relief up to relief[0] above and
        relief[1] below."""
        self.strips.append(_Strip(name, px, world, build, mat, relief))

    def template(self, name, low, mat, high=None, hp=0.03, smooth=60):
        """Add a template mesh (`low`, template-local) baked from `high`
        (default: `low` with rounded edges, `hp` wide). `mat` is a material
        name or a list indexed by the faces' material_index."""
        self.templates.append(_Tpl(name, low, mat, high, hp, smooth))

    # layout -----------------------------------------------------------------
    def _layout(self):
        g = self.gutter / self.size
        v = 1.0 - g
        out = {}
        for s in self.strips:
            h = s.px / self.size
            density = s.px / s.world
            out[s.name] = {"v0": round(v - h, 6), "v1": round(v, 6), "world": s.world,
                           "period": round(self.size / density, 6), "density": round(density, 2)}
            v -= h + g
        return out, v

    def finish(self, samples=24, preview=True):
        from . import pipeline
        from .asset import finalize_normals

        t0 = time.time()
        a = self.asset
        out_dir = ROOT / "assets" / "exported" / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        strips, band_top = self._layout()
        lows, highs = [], []
        # Strips: a flat low plane per strip (UVs = the strip rectangle) and
        # its periodic high pattern, each at its own slot.
        for i, s in enumerate(self.strips):
            st = strips[s.name]
            slot = Vector((0.0, 40.0 * i, 0.0))
            period = st["period"]
            mat = a.material(f"{s.mat}__p{i}", base=s.mat, periodic=period)
            me = bpy.data.meshes.new(f"TL_{s.name}")
            bm = bmesh.new()
            vs = [bm.verts.new(c) for c in ((0, 0, 0), (period, 0, 0), (period, s.world, 0), (0, s.world, 0))]
            f = bm.faces.new(vs)
            uv = _uv_layer(bm)
            for loop in f.loops:
                x, y = loop.vert.co.x, loop.vert.co.y
                loop[uv].uv = (x / period, st["v0"] + (st["v1"] - st["v0"]) * y / s.world)
            bm.to_mesh(me)
            bm.free()
            low = bpy.data.objects.new(f"TL_{s.name}", me)
            low.location = slot
            bpy.context.scene.collection.objects.link(low)
            lows.append(low)
            hbm = s.build(period, s.world)
            hme = bpy.data.meshes.new(f"TH_{s.name}")
            hbm.to_mesh(hme)
            hbm.free()
            hme.shade_smooth()
            hme.set_sharp_from_angle(angle=math.radians(38))
            high = bpy.data.objects.new(f"TH_{s.name}", hme)
            high.location = slot
            hme.materials.append(a.material_obj(mat))
            bpy.context.scene.collection.objects.link(high)
            highs.append(high)
        # Templates: low + high at their own slots, unwrapped and packed into
        # the band under the strips at one texel density.
        tpl_objs = []
        for j, t in enumerate(self.templates):
            slot = Vector((14.0 * (j % 8), -60.0 - 14.0 * (j // 8), 0.0))
            me = bpy.data.meshes.new(f"TT_{t.name}")
            t.low.to_mesh(me)
            low = bpy.data.objects.new(f"TT_{t.name}", me)
            low.location = slot
            bpy.context.scene.collection.objects.link(low)
            mats = t.mat if isinstance(t.mat, (list, tuple)) else [t.mat]
            for m in mats:
                me.materials.append(a.material_obj(m))
            finalize_normals(low, t.smooth)
            if t.high is not None:
                hbm = t.high
            else:
                hbm = t.low.copy()
                if t.hp > 0:
                    hardsurface.round_edges(hbm, t.hp)
            hme = bpy.data.meshes.new(f"TTH_{t.name}")
            hbm.to_mesh(hme)
            hme.shade_smooth()
            hme.set_sharp_from_angle(angle=math.radians(38))
            for m in mats:
                hme.materials.append(a.material_obj(m))
            high = bpy.data.objects.new(f"TTH_{t.name}", hme)
            high.location = slot
            bpy.context.scene.collection.objects.link(high)
            highs.append(high)
            tpl_objs.append(low)
        density = None
        if tpl_objs:
            pipeline._select(tpl_objs)
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.0, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
            bpy.ops.object.mode_set(mode="OBJECT")
            density = _shelf_pack(tpl_objs, (self.gutter / self.size, band_top), self.size, margin=6.0 / self.size)
            pipeline.log(f"templates packed at {density:.1f} px/stud")
        # Bake everything in one go: target = joined lows, sources = highs.
        pipeline._setup_cycles(samples)
        target = pipeline._join_copies(lows + tpl_objs, f"BAKE_{self.name}")
        target.data.materials.clear()
        tm = bpy.data.materials.new("TrimTarget")
        tm.use_nodes = True
        target.data.materials.append(tm)
        for o in lows + tpl_objs + [target]:
            for k in pipeline._RAY_VIS:
                setattr(o, k, False)
        up = max([s.relief[0] for s in self.strips] + [0.12]) + 0.05
        down = max([s.relief[1] for s in self.strips] + [0.12]) + 0.1
        files, imgs = {}, {}
        for ch in CHANNELS:
            t1 = time.time()
            img = pipeline._new_image(f"{self.name}_{GROUP}_{ch}", self.size, ch)
            pipeline._bake_channel([target], [tm], img, ch, sources=highs, cage=up, ray=up + down)
            path = out_dir / f"{self.name}_{GROUP}_{ch}.png"
            pipeline._save_png(img, path, grayscale=ch in ("rough", "metal"))
            files[ch] = path.name
            imgs[ch] = img
            pipeline.log(f"  baked {ch} in {time.time() - t1:.1f}s")
        bpy.data.objects.remove(target, do_unlink=True)
        data = {"name": self.name, "size": self.size, "group": GROUP, "files": files, "strips": strips,
                "template_density": round(density, 2) if density else None, "templates": {}}
        for t, o in zip(self.templates, tpl_objs):
            me = o.data
            uvl = me.uv_layers.active.data
            data["templates"][t.name] = {
                "verts": [[round(c, 5) for c in v.co] for v in me.vertices],
                "faces": [list(p.vertices) for p in me.polygons],
                "uvs": [[[round(uvl[i].uv.x, 6), round(uvl[i].uv.y, 6)] for i in p.loop_indices] for p in me.polygons],
                "smooth": t.smooth,
                "tris": sum(len(p.vertices) - 2 for p in me.polygons),
            }
        (out_dir / "trim.json").write_text(json.dumps(data, separators=(",", ":")) + "\n")
        previews = self._preview(lows, tpl_objs, highs, imgs) if preview else []
        manifest = {"name": self.name, "kind": "trim", "primary": None, "pivots": {}, "parts": [], "attachments": [],
                    "markers": [], "textures": {GROUP: files}, "texel_density": {s: v["density"] for s, v in strips.items()},
                    "template_density": data["template_density"], "previews": previews, "triangles": 0, "meta": {}}
        (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1))
        pipeline.log(f"{self.name}: {len(self.strips)} strips, {len(self.templates)} templates, {time.time() - t0:.0f}s")
        for name, st in strips.items():
            pipeline.log(f"  strip {name}: v {st['v0']:.3f}..{st['v1']:.3f}, period {st['period']:.2f} studs, {st['density']} px/stud")
        return manifest

    def _preview(self, lows, tpls, highs, imgs):
        """Sheet image + every strip and template rendered with the baked maps."""
        from . import pipeline

        for h in highs:
            bpy.data.objects.remove(h, do_unlink=True)
        mat = pipeline._baked_material("TrimBaked", imgs)
        for o in lows + tpls:
            o.data.materials.clear()
            o.data.materials.append(mat)
            for k in pipeline._RAY_VIS:
                setattr(o, k, True)
        # Lay the pieces out on a grid for the camera.
        x = 0.0
        for o in lows:
            o.location = (0.0, x, 0.0)
            x += o.dimensions.y + 0.8
        y0 = x + 1.0
        col = 0.0
        row = y0
        for o in tpls:
            o.location = (col, row, 0.0)
            col += o.dimensions.x + 1.2
            if col > 16:
                col, row = 0.0, row + 4.0
        self.asset.objects = lows + tpls
        views = [("", (0.15, -0.35, 1.0)), ("_templates", (0.6, 0.9, 0.8), [o.name for o in tpls])]
        return pipeline.render_previews(self.asset, views, samples=48)


def _shelf_pack(objs, band, size, margin):
    """Scale every UV island to one texel density and shelf-pack them into
    the full-width band V in [band[0], band[1]] (largest density that
    fits). Returns the density in px/stud."""
    from . import pipeline

    items = []
    for o in objs:
        me = o.data
        uvd = me.uv_layers.active.data
        for island in pipeline.uv_islands(me):
            polys = [me.polygons[i] for i in island]
            a3 = sum(pl.area for pl in polys)
            auv = 0.0
            for pl in polys:
                pts = [uvd[i].uv for i in pl.loop_indices]
                auv += abs(sum(pts[k].x * pts[(k + 1) % len(pts)].y - pts[(k + 1) % len(pts)].x * pts[k].y for k in range(len(pts)))) / 2
            s = math.sqrt(a3 / auv) if a3 > 1e-9 and auv > 1e-12 else 1.0  # UV units -> studs
            idx = [i for pl in polys for i in pl.loop_indices]
            us = [uvd[i].uv.x for i in idx]
            vs = [uvd[i].uv.y for i in idx]
            items.append({"uvd": uvd, "idx": idx, "s": s, "u0": min(us), "v0": min(vs),
                          "w": (max(us) - min(us)) * s, "h": (max(vs) - min(vs)) * s})
    width = 1.0
    height = band[1] - band[0]

    def place(k):
        order = sorted(items, key=lambda it: -min(it["w"], it["h"]))
        x = y = shelf = 0.0
        spots = []
        for it in order:
            rot = it["h"] > it["w"]
            w, h = (it["h"], it["w"]) if rot else (it["w"], it["h"])
            w, h = w * k + margin, h * k + margin
            if x + w > width:
                x, y, shelf = 0.0, y + shelf, 0.0
            if y + h > height or w > width:
                return None
            spots.append((it, x, y, rot))
            x += w
            shelf = max(shelf, h)
        return spots

    lo, hi = 1e-5, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if place(mid) is None:
            hi = mid
        else:
            lo = mid
    k = lo
    for it, x, y, rot in place(k):
        uvd = it["uvd"]
        for i in it["idx"]:
            u = (uvd[i].uv.x - it["u0"]) * it["s"] * k
            v = (uvd[i].uv.y - it["v0"]) * it["s"] * k
            if rot:
                u, v = v, it["w"] * k - u
            uvd[i].uv = (x + margin / 2 + u, band[0] + y + margin / 2 + v)
    return k * size
