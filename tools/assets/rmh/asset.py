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
        self.flags = flags
        self.bm = bmesh.new()
        self.mats = []
        self.instances = []

    def add(self, bm, mat, at=(0, 0, 0), rot=(0, 0, 0), scale=None, mirror_x=False):
        """Merge a primitive bmesh (consumed) into this part."""
        geo.transform(bm, at, rot, scale)
        pieces = [bm]
        if mirror_x:
            pieces.append(geo.mirror_x(bm))
        if mat not in self.mats:
            self.mats.append(mat)
        idx = self.mats.index(mat)
        for piece in pieces:
            for f in piece.faces:
                f.material_index = idx
            tmp = bpy.data.meshes.new("_tmp")
            piece.to_mesh(tmp)
            piece.free()
            self.bm.from_mesh(tmp)
            bpy.data.meshes.remove(tmp)
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

    def texture_group(self, name, size, sheet=False, metal=True):
        """Extra atlas. `sheet=True`: holds templates only (see module doc).
        `metal=False`: skip the metalness map (non-metal groups)."""
        self.tex_size[name] = size
        if sheet or not metal:
            self.group_opts[name] = {"sheet": sheet, "metal": metal}

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

    def decal(self, image, center, normal, size, up=(0, 0, 1), color=None):
        """Project `image` onto surfaces within a box of `size` (w, h, depth)
        centred at `center`, facing along `normal` (Blender coords)."""
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
        self.decals.append({"empty": empty, "image": img, "axis": tuple(n), "color": color})

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
            objs.append(obj)
        self.objects = objs
        return objs

    def finish(self, **kw):
        from . import pipeline

        return pipeline.finish(self, **kw)
