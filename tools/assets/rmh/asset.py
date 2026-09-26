"""Asset / Part builder: the in-Blender description of a Roblox asset.

    a = Asset("SupplyCrate", pivot=(0, 0, 0))
    p = a.part("Root")
    p.add(geo.box(4, 4, 4), "wood_crate", at=(0, 0, 2))
    a.attach("Top", "Root", (0, 0, 4))
    a.finish()           # -> bake, preview, export (see pipeline.py)

Coordinates are Blender asset space in studs: +Z up, +Y forward.
Each Part becomes one MeshPart. `path` places it in a sub-model
("TurretGun/MachineGun"); models get a WorldPivot from `a.pivot()`.

Sheet texture groups (opt-in, `a.texture_group(name, px, sheet=True)`):
the group's atlas holds a few *templates* instead of every part's surface.
Parts add rigid copies of a template (`part.add_template(t, at, rot)`),
which share its UVs, so hundreds of sandbags cost the texture space of a
dozen. A template may carry a dense `high` mesh that is baked onto its
game mesh (selected-to-active).
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import geo, images, materials


def _pad_to_joint(bm, joint, e=0.004):
    """Add two tiny triangles so the mesh bounding box is centred on `joint`.
    Roblox places a MeshPart's origin at its bbox centre; this makes limb
    origins sit at their joints (hip/shoulder) as the contract requires."""
    xs = [v.co for v in bm.verts]
    lo = Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs)))
    hi = Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs)))
    lo2 = Vector([min(lo[i], 2 * joint[i] - hi[i]) for i in range(3)])
    hi2 = Vector([max(hi[i], 2 * joint[i] - lo[i]) for i in range(3)])
    for corner, sign in ((lo2, 1), (hi2, -1)):
        a = bm.verts.new(corner)
        b = bm.verts.new(corner + Vector((sign * e, 0, 0)))
        c = bm.verts.new(corner + Vector((0, sign * e, 0)))
        bm.faces.new((a, b, c))


def _pad_to_box(bm, lo, hi, name, tol=0.02, e=0.004):
    """Opt-in hit-box lock (HS-3): the game mesh's bounding box (= its
    Roblox Size and CFrame, i.e. its Box hit volume) is exactly [lo, hi].
    Geometry outside the box is an error (move it to a CanQuery=false part);
    two tiny triangles at the corners make a smaller mesh fill the box."""
    lo, hi = Vector(lo), Vector(hi)
    xs = [v.co for v in bm.verts]
    glo = Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs)))
    ghi = Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs)))
    over = [f"{'xyz'[i]} {glo[i]:.3f}..{ghi[i]:.3f} vs {lo[i]:.3f}..{hi[i]:.3f}" for i in range(3) if glo[i] < lo[i] - tol or ghi[i] > hi[i] + tol]
    if over:
        raise ValueError(f"part {name} exceeds its locked hit box: " + "; ".join(over))
    for corner, sign in ((lo, 1), (hi, -1)):
        a = bm.verts.new(corner)
        b = bm.verts.new(corner + Vector((sign * e, 0, 0)))
        c = bm.verts.new(corner + Vector((0, sign * e, 0)))
        bm.faces.new((a, b, c))
    for v in bm.verts:
        v.co = Vector((min(max(v.co.x, lo.x), hi.x), min(max(v.co.y, lo.y), hi.y), min(max(v.co.z, lo.z), hi.z)))


def fix_inside_out(bm):
    """Closed shells whose faces point inward (negative signed volume) are
    turned the right way out. Roblox culls back faces, so such a shell
    shows its inside in game even though Cycles previews look fine.
    Returns how many shells were flipped."""
    bm.normal_update()
    seen = set()
    flipped = 0
    for start in bm.faces:
        if start.index in seen:
            continue
        comp, stack = [], [start]
        seen.add(start.index)
        while stack:
            f = stack.pop()
            comp.append(f)
            for e in f.edges:
                for g in e.link_faces:
                    if g.index not in seen:
                        seen.add(g.index)
                        stack.append(g)
        if not all(e.is_manifold for f in comp for e in f.edges):
            continue
        vol = sum(f.calc_center_median().dot(f.normal) * f.calc_area() for f in comp)
        if vol < -1e-6:
            bmesh.ops.reverse_faces(bm, faces=comp)
            flipped += 1
    return flipped


def rb_box(center, size):
    """Roblox (centre, size) of a part (manifest values) -> Blender (lo, hi)."""
    c = Vector((center[0], -center[2], center[1]))
    s = Vector((size[0], size[2], size[1]))
    return tuple(c - s / 2), tuple(c + s / 2)


def finalize_normals(obj, smooth_angle):
    """Smooth shading, sharp edges above `smooth_angle`, weighted normals
    applied to the mesh (what Roblox receives)."""
    me = obj.data
    me.shade_smooth()
    me.set_sharp_from_angle(angle=math.radians(smooth_angle))
    wn = obj.modifiers.new("wn", "WEIGHTED_NORMAL")
    wn.keep_sharp = True
    wn.weight = 60
    dg = bpy.context.evaluated_depsgraph_get()
    baked = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    obj.modifiers.clear()
    old = obj.data
    name = old.name
    obj.data = baked
    bpy.data.meshes.remove(old)
    baked.name = name
    return obj


class Template:
    """A reusable mesh with its own UV island in a sheet texture group."""

    def __init__(self, name, group, low, mat, high=None, smooth_angle=80, uv="smart"):
        self.name = name
        self.group = group
        self.low = low
        self.high = high
        self.mat = mat
        self.smooth_angle = smooth_angle
        self.uv = uv  # "smart" (smart project) or "seams" (angle-based unwrap along marked seams)
        self.mesh = None  # UV-unwrapped game mesh, set by pipeline.prepare_templates
        self.objects = []  # bake objects, removed after baking

    def triangles(self):
        return sum(len(f.verts) - 2 for f in self.low.faces)


class Part:
    def __init__(self, asset, name, path="", tex="main", **flags):
        self.asset = asset
        self.name = name
        self.path = path
        self.tex = tex
        self.hitbox = flags.pop("hitbox", None)
        # Opt-in (HS-4): parts whose faces were oriented on purpose (e.g.
        # face_up sand mounds with a capped underside) skip fix_inside_out.
        self.keep_normals = flags.pop("keep_normals", False)
        self.flags = flags
        self.bm = bmesh.new()
        self.mats = []
        self.instances = []
        # Opt-in high-poly bake (HS-3): groups declared with high=True keep a
        # second mesh per part (every piece re-bevelled round + detail-only
        # geometry) that is baked onto the game mesh.
        self.high = asset.group_opts.get(tex, {}).get("high")
        self.hbm = bmesh.new() if self.high else None

    @staticmethod
    def _merge(dst, piece):
        tmp = bpy.data.meshes.new("_tmp")
        piece.to_mesh(tmp)
        piece.free()
        dst.from_mesh(tmp)
        bpy.data.meshes.remove(tmp)

    def add(self, bm, mat, at=(0, 0, 0), rot=(0, 0, 0), scale=None, mirror_x=False, hp=None, texel=None):
        """Merge a primitive bmesh (consumed) into this part.
        Opt-in (HS-3): `hp` = bevel width of this piece in the high-poly
        bake source (high groups; default the group's `hp`, 0 = none);
        `texel` = relative texel density of this piece in its atlas
        (e.g. 0.3 for faces nobody looks at), or a function of each face
        (asset space) returning it."""
        geo.transform(bm, at, rot, scale)
        if texel is not None:
            lay = bm.faces.layers.float.get("rmh_texel") or bm.faces.layers.float.new("rmh_texel")
            bm.normal_update()
            for f in bm.faces:
                f[lay] = texel(f) if callable(texel) else texel
        pieces = [bm]
        if mirror_x:
            pieces.append(geo.mirror_x(bm))
        if mat not in self.mats:
            self.mats.append(mat)
        idx = self.mats.index(mat)
        for piece in pieces:
            for f in piece.faces:
                f.material_index = idx
            if self.hbm is not None:
                width = self.high.get("hp", 0.05) if hp is None else hp
                hi = piece.copy()
                if width > 0:
                    from . import hardsurface

                    hardsurface.round_edges(hi, width)
                self._merge(self.hbm, hi)
            self._merge(self.bm, piece)
        return self

    def detail(self, bm, mat, at=(0, 0, 0), rot=(0, 0, 0), scale=None, mirror_x=False):
        """Opt-in (HS-3): geometry that exists only in the high-poly bake
        source (bolts, weld beads, rivets, slats): it ends up in the normal,
        colour and roughness maps, not in the game mesh."""
        if self.hbm is None:
            raise ValueError(f"part {self.name}: detail() needs a texture group declared with high=...")
        geo.transform(bm, at, rot, scale)
        pieces = [bm] + ([geo.mirror_x(bm)] if mirror_x else [])
        if mat not in self.mats:
            self.mats.append(mat)
        idx = self.mats.index(mat)
        for piece in pieces:
            for f in piece.faces:
                f.material_index = idx
            self._merge(self.hbm, piece)
        return self

    def add_template(self, template, at=(0, 0, 0), rot=(0, 0, 0), scale=None):
        """Place a rigid copy of `template` (shares its UVs; see Asset.template)."""
        if template.group != self.tex:
            raise ValueError(f"template {template.name} is in group {template.group}, part {self.name} in {self.tex}")
        m = Matrix.Translation(Vector(at)) @ geo.euler_matrix(rot)
        if scale is not None:
            m = m @ Matrix.Diagonal(Vector((*scale, 1.0)))
        if m.determinant() <= 0:
            raise ValueError("template instances cannot be mirrored")
        if template.mat not in self.mats:
            self.mats.append(template.mat)
        self.instances.append((template, m))
        return self

    def rotate(self, rot, center):
        """Rotate everything added so far about `center` (degrees XYZ)."""
        m = geo.euler_matrix(rot)
        bmesh.ops.rotate(self.bm, cent=Vector(center), matrix=m.to_3x3(), verts=self.bm.verts)
        return self

    def triangles(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces) + sum(t.triangles() for t, _ in self.instances)

    def realise_instances(self):
        for t, m in self.instances:
            tmp = bmesh.new()
            tmp.from_mesh(t.mesh)
            bmesh.ops.transform(tmp, matrix=m, verts=tmp.verts)
            idx = self.mats.index(t.mat)
            for f in tmp.faces:
                f.material_index = idx
            me = bpy.data.meshes.new("_inst")
            tmp.to_mesh(me)
            tmp.free()
            self.bm.from_mesh(me)
            bpy.data.meshes.remove(me)
        self.instances = []


class Asset:
    def __init__(self, name, pivot=(0, 0, 0), tex_size=1024):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.name = name
        self.pivot_pos = Vector(pivot)
        self.tex_size = {"main": tex_size}
        self.parts = []
        self.attachments = []
        self.markers = []
        self.pivots = {"": Vector(pivot)}
        self.specs = dict(materials.PRESETS)
        self.decals = []
        self.primary = "Root"
        self.zmin = 0.0
        self.meta = {}
        self.group_opts = {}
        self.templates = []
        self._mats = {}
        # Opt-in (HS-3): turn inside-out closed shells outward at build time
        # (geo.side_prism returns them inside-out; Roblox culls back faces).
        self.fix_inside_out = False

    # --- description ----------------------------------------------------
    def part(self, name, path="", tex="main", **flags):
        p = Part(self, name, path, tex, **flags)
        self.parts.append(p)
        return p

    def material(self, name, **spec):
        base = dict(self.specs.get(spec.pop("base", ""), {}))
        base.update(spec)
        self.specs[name] = base
        return name

    def texture_group(self, name, size, sheet=False, metal=True, high=None, down=None, back=None):
        """Extra atlas. `sheet=True`: holds templates only (see module doc).
        `metal=False`: skip the metalness map (non-metal groups).
        Opt-in (HS-3): `high={"hp": 0.05, "cage": 0.1, "ray": 0.3}` bakes the
        group from a high-poly copy (see Part.add/detail); `down=0.3` gives
        downward-facing UV islands (hull bellies) that much texel density;
        `back=0.5` the same for islands facing the model's rear (-Y: enemy
        vehicles drive at the player). Declare groups before adding parts."""
        self.tex_size[name] = size
        if sheet or not metal or high or down or back:
            self.group_opts[name] = {"sheet": sheet, "metal": metal}
            if high:
                self.group_opts[name]["high"] = dict(high) if isinstance(high, dict) else {}
            if down:
                self.group_opts[name]["down"] = down
            if back:
                self.group_opts[name]["back"] = back

    def shared_group(self, name, source, size, images):
        """Opt-in (HS-3, rmh.trim): a texture group whose maps belong to
        another asset (a trim sheet). Nothing is unwrapped or baked; parts
        carry their own UVs; the rbxmx points at the source's image ids."""
        self.tex_size[name] = size
        self.group_opts[name] = {"shared": source, "images": images, "metal": True}

    def template(self, name, group, low, mat, high=None, smooth_angle=80, uv="smart"):
        """Declare a template mesh (bmesh, template-local space; its base
        should sit near z = 0) in sheet group `group` with material `mat`.
        `high` (optional bmesh, same space) is baked onto `low`."""
        if not self.group_opts.get(group, {}).get("sheet"):
            raise ValueError(f"group {group} is not a sheet group")
        t = Template(name, group, low, mat, high, smooth_angle, uv)
        self.templates.append(t)
        return t

    def material_obj(self, name):
        if name not in self._mats:
            spec = self.specs[name]
            self._mats[name] = materials.build(name, spec, self.decals if spec.get("decals", True) else (), self.zmin)
        return self._mats[name]

    def attach(self, name, part, pos, axis=None):
        """Attachment on `part` at world pos; `axis` = look direction (Blender)."""
        self.attachments.append({"name": name, "part": part, "pos": Vector(pos), "axis": axis})

    def marker(self, name, path, pos, size=(0.4, 0.4, 0.4), axis=None):
        """Invisible, non-colliding Part (e.g. the MG `Muzzle`)."""
        self.markers.append({"name": name, "path": path, "pos": Vector(pos), "size": size, "axis": axis})

    def pivot(self, path, pos):
        self.pivots[path] = Vector(pos)

    def decal(self, image, center, normal, size, up=(0, 0, 1), color=None, wear=0.0, seed=1):
        """Project `image` onto surfaces within a box of `size` (w, h, depth)
        centred at `center`, facing along `normal` (Blender coords).
        `wear` (opt-in, 0..1): the marking's paint chips and thins."""
        n = Vector(normal).normalized()
        u = Vector(up)
        if abs(n.dot(u.normalized())) > 0.95:
            u = Vector((0, 1, 0)) if abs(n.y) < 0.95 else Vector((1, 0, 0))
        x = u.cross(n).normalized()
        y = n.cross(x).normalized()
        m = Matrix((x, y, n)).transposed().to_4x4()
        empty = bpy.data.objects.new(f"Decal{len(self.decals)}", None)
        empty.matrix_world = Matrix.Translation(Vector(center)) @ m @ Matrix.Diagonal(Vector((size[0], size[1], size[2], 1)))
        bpy.context.scene.collection.objects.link(empty)
        img = image if isinstance(image, bpy.types.Image) else images.get(image)
        self.decals.append({"empty": empty, "image": img, "axis": tuple(n), "color": color, "wear": wear, "seed": seed})

    # --- realisation ----------------------------------------------------
    def build_objects(self):
        mat_for = self.material_obj
        objs = []
        for p in self.parts:
            me = bpy.data.meshes.new(p.name)
            bmesh.ops.remove_doubles(p.bm, verts=p.bm.verts, dist=1e-4)
            if p.instances:
                if p.bm.faces and self.group_opts.get(p.tex, {}).get("sheet"):
                    raise ValueError(f"part {p.name} mixes primitives and templates in sheet group {p.tex}")
                p.realise_instances()
            if p.flags.get("joint") is not None:
                _pad_to_joint(p.bm, Vector(p.flags["joint"]))
            if self.fix_inside_out and not p.keep_normals:
                p.bm.faces.index_update()
                n_flipped = fix_inside_out(p.bm)
                if n_flipped:
                    print(f"[rmh] {p.name}: turned {n_flipped} inside-out shell(s) the right way out", flush=True)
            if p.hitbox is not None:
                _pad_to_box(p.bm, p.hitbox[0], p.hitbox[1], p.name)
            if self.group_opts.get(p.tex, {}).get("shared"):
                from . import trim

                trim.check_mapped(p.bm, p.name)
            p.bm.to_mesh(me)
            p.bm.free()
            obj = bpy.data.objects.new(p.name, me)
            bpy.context.scene.collection.objects.link(obj)
            for m in p.mats:
                me.materials.append(mat_for(m))
            finalize_normals(obj, p.flags.get("smooth_angle", 42))
            obj["rmh_path"] = p.path
            obj["rmh_tex"] = p.tex
            for k, v in p.flags.items():
                obj["rmh_" + k] = v
            if p.hitbox is not None:
                obj["rmh_hitbox"] = True
            if p.hbm is not None:
                obj["rmh_high"] = self._high_object(p).name
            objs.append(obj)
        self.objects = objs
        return objs

    def _high_object(self, p):
        """The part's high-poly bake source (hidden until its group bakes)."""
        me = bpy.data.meshes.new(f"HP_{p.name}")
        if self.fix_inside_out and not p.keep_normals:
            p.hbm.faces.index_update()
            fix_inside_out(p.hbm)
        p.hbm.to_mesh(me)
        p.hbm.free()
        obj = bpy.data.objects.new(f"HP_{p.name}", me)
        bpy.context.scene.collection.objects.link(obj)
        for m in p.mats:
            me.materials.append(self.material_obj(m))
        me.shade_smooth()
        me.set_sharp_from_angle(angle=math.radians(p.high.get("smooth", 38)))
        obj.hide_render = True
        return obj

    def finish(self, **kw):
        from . import pipeline

        return pipeline.finish(self, **kw)
