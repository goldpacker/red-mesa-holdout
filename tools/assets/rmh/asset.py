"""Asset / Part builder: the in-Blender description of a Roblox asset.

    a = Asset("SupplyCrate", pivot=(0, 0, 0))
    p = a.part("Root")
    p.add(geo.box(4, 4, 4), "wood_crate", at=(0, 0, 2))
    a.attach("Top", "Root", (0, 0, 4))
    a.finish()           # -> bake, preview, export (see pipeline.py)

Coordinates are Blender asset space in studs: +Z up, +Y forward.
Each Part becomes one MeshPart. `path` places it in a sub-model
("TurretGun/MachineGun"); models get a WorldPivot from `a.pivot()`.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import geo, images, materials


class Part:
    def __init__(self, asset, name, path="", tex="main", **flags):
        self.asset = asset
        self.name = name
        self.path = path
        self.tex = tex
        self.flags = flags
        self.bm = bmesh.new()
        self.mats = []

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

    def triangles(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)


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

    def texture_group(self, name, size):
        self.tex_size[name] = size

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
        mats = {}

        def mat_for(name):
            if name not in mats:
                spec = self.specs[name]
                mats[name] = materials.build(name, spec, self.decals if spec.get("decals", True) else (), self.zmin)
            return mats[name]

        objs = []
        for p in self.parts:
            me = bpy.data.meshes.new(p.name)
            bmesh.ops.remove_doubles(p.bm, verts=p.bm.verts, dist=1e-4)
            p.bm.to_mesh(me)
            p.bm.free()
            obj = bpy.data.objects.new(p.name, me)
            bpy.context.scene.collection.objects.link(obj)
            for m in p.mats:
                me.materials.append(mat_for(m))
            me.shade_smooth()
            me.set_sharp_from_angle(angle=math.radians(p.flags.get("smooth_angle", 42)))
            wn = obj.modifiers.new("wn", "WEIGHTED_NORMAL")
            wn.keep_sharp = True
            wn.weight = 60
            dg = bpy.context.evaluated_depsgraph_get()
            baked = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            obj.modifiers.clear()
            old = obj.data
            obj.data = baked
            bpy.data.meshes.remove(old)
            baked.name = p.name
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
