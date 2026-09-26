"""Skinned-mesh assets (Character workstream): one deforming mesh per
variant on a shared skeleton, posed in Roblox with `Bone.Transform`.

    s = SkinnedAsset("InfantrySkinned", bones=[Bone("Hips", (0, 0, 3.45), end=(0, 0, 3.95)), ...],
                     variants=("Rifleman", "Grenadier"))
    s.material("uniform", kind="garment", color="#3d4045", folds=[...])
    s.add(bm, "uniform", bones=["Hips", "LeftUpperLeg"])        # smooth weights
    s.add(bm, "helmet", bones="Head", only=("Rifleman",))        # rigid, one variant
    s.finish(views=[...], poses={...})

Coordinates are Blender asset space in studs (+Z up, +Y forward), like
rmh.asset. Pipeline facts this module relies on (verified in Studio, see
docs/ASSET_PIPELINE.md "Skinned meshes"):

- Every bone points straight up (+Z) with roll 0, so every glTF joint has
  an identity rotation; a bone's `head` is its pivot. `end` is only used
  to compute skin weights (distance to the head->end segment).
- The GLB is exported WITHOUT the 180-degree pre-rotation used for rigid
  assets. The Roblox importer turns the asset 180 degrees about up (the
  root bone gets that rotation); tools/assets/skin_publish.py turns the
  harvested model back, so in the .rbxmx the model faces -Z and every
  bone's rest rotation is identity in model space. Then
  `Bone.Transform = CFrame.Angles(rx, ry, rz)` means the same thing as a
  Motor6D.Transform on a rig whose C0/C1 have no rotation.
- All variants share one texture atlas: every piece lives in a "layer"
  keyed by the variants that use it; layers are unwrapped and baked
  together (non-shared layers moved apart so they don't shadow each
  other), then each variant's mesh is the join of its layers.
"""
import json
import math
import time
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Quaternion, Vector

from . import images, materials, pipeline
from .skin_bake import _bake_channel, _baked_material, _save_png  # noqa: F401  (also registers the "garment" kind)
from .skin_pose import _BONE_BASIS, Pose, euler_roblox, pose_quaternion, rot  # noqa: F401  (re-exported)

ROOT = pipeline.ROOT
log = pipeline.log
LAYER_SPACING = 30.0  # studs between bake layers (AO/cavity distance is < 1)


class Bone:
    """`head` = pivot. Skin weights use the segment `start`->`end`
    (start defaults to head). Bones without weights (markers such as a
    muzzle) are fine: they still export and import as Bone instances."""

    def __init__(self, name, head, end=None, parent=None, start=None):
        self.name = name
        self.head = Vector(head)
        self.end = Vector(end) if end is not None else Vector(head)
        self.start = Vector(start) if start is not None else Vector(head)
        self.parent = parent


def _swap_side(name):
    if name.startswith("Left"):
        return "Right" + name[4:]
    if name.startswith("Right"):
        return "Left" + name[5:]
    return name


def _seg_dist(p, a, b):
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-9 else max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (a + ab * t - p).length


# --- geometry helpers -------------------------------------------------------

def _ellipse_perimeter(a, b):
    return math.pi * (3 * (a + b) - math.sqrt(max((3 * a + b) * (a + 3 * b), 0.0)))


def sweep(path, radii, n=10, ref=(1, 0, 0), offsets=None, shape=None, caps=(True, True), seam=-math.pi / 2):
    """Tube through `path` points with elliptical rings, with its own UVs
    (one island, seam at angle `seam`, u = around in studs, v = along).

    radii[i] = (r_side, r_front): r_side along `ref` (made perpendicular to
    the path), r_front along the third axis f = side x direction (front
    for limbs going down, back for a torso going up).
    offsets[i] = (side, f) shifts ring i off the path (calf bulge).
    shape(theta) -> radius multiplier (theta 0 = +side, pi/2 = +f).
    """
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    flag = bm.faces.layers.int.new("rmh_uv")
    pts = [Vector(p) for p in path]
    refv = Vector(ref)
    rings, perims, along = [], [], [0.0]
    for i, c in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        s = (refv - d * refv.dot(d)).normalized()
        f = s.cross(d).normalized()  # for d = -Z, s = +X: f = +Y (front)
        rs, rf = radii[i]
        if offsets:
            c = c + s * offsets[i][0] + f * offsets[i][1]
        ring = []
        for k in range(n):
            th = seam + math.tau * k / n
            m = shape(th) if shape else 1.0
            ring.append(bm.verts.new(c + (s * math.cos(th) * rs + f * math.sin(th) * rf) * m))
        rings.append(ring)
        perims.append(_ellipse_perimeter(rs, rf))
        if i:
            along.append(along[-1] + (pts[i] - pts[i - 1]).length)
    for i in range(len(rings) - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(n):
            j = (k + 1) % n
            face = bm.faces.new((a[k], b[k], b[j], a[j]))
            u0, u1 = k / n, (k + 1) / n
            coords = ((u0 * perims[i], along[i]), (u0 * perims[i + 1], along[i + 1]), (u1 * perims[i + 1], along[i + 1]), (u1 * perims[i], along[i]))
            for loop, co in zip(face.loops, coords):
                loop[uv].uv = co
            face[flag] = 1
    if caps[0]:
        bm.faces.new(list(reversed(rings[0])))
    if caps[-1]:
        bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return bm


# --- the asset ----------------------------------------------------------------

class SkinnedAsset:
    def __init__(self, name, bones, variants, tex_size=1024, pivot=(0, 0, 0)):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        self.name = name
        self.bones = list(bones)
        self.bone_index = {b.name: i for i, b in enumerate(self.bones)}
        self.variants = tuple(variants)
        self.tex_size = tex_size
        self.pivot = Vector(pivot)
        self.specs = dict(materials.PRESETS)
        self.decals = []
        self.layers = {}  # key (tuple of variants) -> {"bm", "mats", "deform", "weights"}
        self.zmin = 0.0
        self.meta = {}

    # --- description ----------------------------------------------------
    def material(self, name, **spec):
        base = dict(self.specs.get(spec.pop("base", ""), {}))
        base.update(spec)
        self.specs[name] = base
        return name

    def decal(self, image, center, normal, size, up=(0, 0, 1), color=None):
        """Same as rmh.asset.Asset.decal (projected stencil, bind pose)."""
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

    def _layer(self, only):
        key = tuple(v for v in self.variants if only is None or v in only)
        if not key:
            raise ValueError(f"no variant in {only}")
        if key not in self.layers:
            bm = bmesh.new()
            self.layers[key] = {"bm": bm, "mats": [], "deform": bm.verts.layers.deform.verify(),
                                "uv": bm.loops.layers.uv.verify(), "flag": bm.faces.layers.int.new("rmh_uv")}
        return self.layers[key]

    def weights(self, co, bones, falloff=4.0, max_influences=3):
        """Skin weights for a point: inverse-distance to each candidate
        bone's head->end segment, top `max_influences`, normalised."""
        if isinstance(bones, str):
            return {bones: 1.0}
        ws = []
        for name in bones:
            b = self.bones[self.bone_index[name]]
            d = max(_seg_dist(co, b.start, b.end), 0.02)
            ws.append((name, 1.0 / d ** falloff))
        ws.sort(key=lambda x: -x[1])
        ws = ws[:max_influences]
        total = sum(w for _, w in ws)
        out = {n: w / total for n, w in ws}
        return {n: w for n, w in out.items() if w > 0.04} or {ws[0][0]: 1.0}

    def add(self, bm, mat, bones, at=(0, 0, 0), rot=(0, 0, 0), scale=None, mirror_x=False, only=None, falloff=4.0, weight_fn=None):
        """Merge a primitive (consumed) into the layer for `only` variants.
        `bones`: a bone name (rigid) or a list of candidate bones (smooth).
        The mirrored copy swaps Left/Right bone names. `weight_fn(co)` ->
        {bone: w} overrides the automatic weights."""
        from . import geo

        geo.transform(bm, at, rot, scale)
        pieces = [(bm, bones)]
        if mirror_x:
            if bones is None:
                mb = None
            elif isinstance(bones, str):
                mb = _swap_side(bones)
            else:
                mb = [_swap_side(b) for b in bones]
            pieces.append((geo.mirror_x(bm), mb))
        layer = self._layer(only)
        if mat not in layer["mats"]:
            layer["mats"].append(mat)
        idx = layer["mats"].index(mat)
        dst = layer["bm"]
        deform = layer["deform"]
        dst_uv, dst_flag = layer["uv"], layer["flag"]
        for piece, bset in pieces:
            src_uv = piece.loops.layers.uv.active
            src_flag = piece.faces.layers.int.get("rmh_uv")
            vmap = {}
            for v in piece.verts:
                nv = dst.verts.new(v.co)
                ws = weight_fn(v.co) if weight_fn else self.weights(v.co, bset, falloff)
                for name, w in ws.items():
                    nv[deform][self.bone_index[name]] = w
                vmap[v] = nv
            for f in piece.faces:
                try:
                    nf = dst.faces.new([vmap[v] for v in f.verts])
                except ValueError:
                    continue
                nf.material_index = idx
                if src_uv is not None and src_flag is not None and f[src_flag]:
                    for ls, ld in zip(f.loops, nf.loops):
                        ld[dst_uv].uv = ls[src_uv].uv
                    nf[dst_flag] = 1
            piece.free()
        return self

    def triangles(self, variant):
        return sum(sum(len(f.verts) - 2 for f in L["bm"].faces) for key, L in self.layers.items() if variant in key)

    # --- realisation ----------------------------------------------------
    def _layer_objects(self, smooth_angle=48):
        mats = {}

        def mat_for(name):
            if name not in mats:
                spec = self.specs[name]
                mats[name] = materials.build(name, spec, self.decals if spec.get("decals", True) else (), self.zmin)
            return mats[name]

        objs = []
        for i, (key, L) in enumerate(self.layers.items()):
            name = "Layer_" + ("All" if len(key) == len(self.variants) else "_".join(key))
            me = bpy.data.meshes.new(name)
            L["bm"].to_mesh(me)
            L["bm"].free()
            obj = bpy.data.objects.new(name, me)
            bpy.context.scene.collection.objects.link(obj)
            for b in self.bones:
                obj.vertex_groups.new(name=b.name)
            for m in L["mats"]:
                me.materials.append(mat_for(m))
            me.shade_smooth()
            me.set_sharp_from_angle(angle=math.radians(smooth_angle))
            wn = obj.modifiers.new("wn", "WEIGHTED_NORMAL")
            wn.keep_sharp = True
            wn.weight = 60
            dg = bpy.context.evaluated_depsgraph_get()
            baked = bpy.data.meshes.new_from_object(obj.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            obj.modifiers.clear()
            old = obj.data
            obj.data = baked
            bpy.data.meshes.remove(old)
            baked.name = name
            obj["variants"] = list(key)
            obj["layer_index"] = i
            objs.append(obj)
        return objs

    def _bake(self, objs, out_dir, samples):
        """Shared atlas for all layers: smart-UV + pack, then bake colour /
        roughness / metalness (emission trick) and a tangent normal map."""
        pipeline._setup_cycles(samples)
        size = self.tex_size
        log(f"unwrap {len(objs)} layers ({size}px)")
        # Swept tubes (limbs, torso, straps) bring their own one-island UVs
        # (face attribute rmh_uv = 1); everything else is smart-projected.
        # Then all islands get the same texel density and are packed.
        for o in objs:
            attr = o.data.attributes.get("rmh_uv")
            for poly in o.data.polygons:
                poly.select = not (attr is not None and attr.data[poly.index].value)
        pipeline._select(objs)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_mode(type="FACE")
        bpy.ops.uv.smart_project(angle_limit=math.radians(52), island_margin=6.0 / size, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT")
        bpy.ops.uv.average_islands_scale()
        bpy.ops.uv.pack_islands(margin=6.0 / size, rotate=True)
        bpy.ops.object.mode_set(mode="OBJECT")
        mats = []
        for o in objs:
            for slot in o.material_slots:
                if slot.material and slot.material not in mats:
                    mats.append(slot.material)
        imgs, files = {}, {}
        for ch in ("color", "rough", "metal", "normal"):
            t0 = time.time()
            img = bpy.data.images.new(f"{self.name}_main_{ch}", size, size, alpha=False)
            if ch != "color":
                img.colorspace_settings.name = "Non-Color"
            if ch == "normal":
                img.generated_color = (0.5, 0.5, 1.0, 1.0)
            _bake_channel(objs, mats, img, ch)
            path = out_dir / f"{self.name}_main_{ch}.png"
            _save_png(img, path, grayscale=ch in ("rough", "metal"))
            imgs[ch] = img
            files[ch] = path.name
            log(f"  baked {ch} in {time.time() - t0:.1f}s")
        return {"files": files, "images": imgs}

    def _armature(self):
        data = bpy.data.armatures.new("Skeleton")
        arm = bpy.data.objects.new("Skeleton", data)
        bpy.context.scene.collection.objects.link(arm)
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        eb = {}
        for b in self.bones:
            e = data.edit_bones.new(b.name)
            e.head = b.head
            e.tail = b.head + Vector((0, 0, 0.3))  # straight up: identity joint rotation in glTF
            e.roll = 0.0
            e.use_deform = True
            if b.parent:
                e.parent = eb[b.parent]
                e.use_connect = False
            eb[b.name] = e
        bpy.ops.object.mode_set(mode="OBJECT")
        return arm

    def _variant_meshes(self, layer_objs, arm):
        out = {}
        for v in self.variants:
            parts = [o for o in layer_objs if v in o["variants"]]
            copies = []
            for o in parts:
                c = o.copy()
                c.data = o.data.copy()
                bpy.context.scene.collection.objects.link(c)
                copies.append(c)
            pipeline._select(copies)
            bpy.ops.object.join()
            obj = bpy.context.view_layer.objects.active
            obj.name = v
            obj.data.name = v
            obj.parent = arm
            mod = obj.modifiers.new("Armature", "ARMATURE")
            mod.object = arm
            out[v] = obj
        return out

    def _keep_marker_bones(self, obj):
        """The Roblox importer drops bones that no vertex is weighted to.
        For each such bone (muzzle, support-hand and lamp markers), give the
        nearest vertex that is rigidly on its parent a 5 % share: the
        marker has no Transform of its own, so the vertex doesn't move."""
        index = {vg.name: vg.index for vg in obj.vertex_groups}
        used = {g.group for v in obj.data.vertices for g in v.groups if g.weight > 1e-4}
        for b in self.bones:
            if index[b.name] in used or b.parent is None:
                continue
            pi = index[b.parent]
            best = None
            for v in obj.data.vertices:
                ws = {g.group: g.weight for g in v.groups if g.weight > 1e-4}
                if ws.get(pi, 0.0) > 0.999 and len(ws) == 1:
                    d = (v.co - b.head).length
                    if best is None or d < best[0]:
                        best = (d, v.index)
            if best is None:
                log(f"  WARNING: marker bone {b.name} has no rigid vertex on {b.parent} in {obj.name}")
                continue
            obj.vertex_groups[b.parent].add([best[1]], 0.95, "REPLACE")
            obj.vertex_groups[b.name].add([best[1]], 0.05, "REPLACE")

    def _lod(self, obj, ratio):
        c = obj.copy()
        c.data = obj.data.copy()
        c.name = obj.name + "LOD"
        c.data.name = c.name
        bpy.context.scene.collection.objects.link(c)
        c.modifiers.clear()
        dec = c.modifiers.new("dec", "DECIMATE")
        dec.ratio = ratio
        dec.use_collapse_triangulate = True
        dg = bpy.context.evaluated_depsgraph_get()
        m = bpy.data.meshes.new_from_object(c.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        old = c.data
        c.data = m
        bpy.data.meshes.remove(old)
        m.name = c.name  # after removing the copy, so glTF mesh (= MeshPart) names have no ".001"
        m.validate(clean_customdata=False)
        c.modifiers.clear()
        mod = c.modifiers.new("Armature", "ARMATURE")
        mod.object = obj.modifiers["Armature"].object
        return c

    def apply_pose(self, arm, pose):
        for pb in arm.pose.bones:
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = Quaternion()
            pb.location = (0, 0, 0)
        for name, r in (pose or {}).items():
            pb = arm.pose.bones[name]
            pb.rotation_quaternion = pose_quaternion(*r[:3])
            if len(r) > 3:
                # optional translation in Roblox axes (x, y, z) -> bone local
                t = Vector((r[3][0], -r[3][2], r[3][1]))
                pb.location = _BONE_BASIS.transposed() @ t
        bpy.context.view_layer.update()

    def _tri_count(self, obj):
        return sum(len(p.vertices) - 2 for p in obj.data.polygons)

    def finish(self, samples=24, preview_samples=96, views=None, poses=None, lod_ratio=None, preview=True, extra_previews=None):
        t0 = time.time()
        out_dir = ROOT / "assets" / "exported" / self.name
        out_dir.mkdir(parents=True, exist_ok=True)
        (ROOT / "assets" / "blender").mkdir(parents=True, exist_ok=True)
        (ROOT / "assets" / "previews").mkdir(parents=True, exist_ok=True)
        layer_objs = self._layer_objects()
        # Bake: shared atlas; move non-shared layers apart so AO/cavity only
        # sees their own geometry (object-space texture coords don't move).
        for o in layer_objs:
            if len(o["variants"]) != len(self.variants):
                o.location.x = LAYER_SPACING * (o["layer_index"] + 1)
        textures = {"main": self._bake(layer_objs, out_dir, samples)}
        for o in layer_objs:
            o.location = (0, 0, 0)
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=str(ROOT / "assets" / "blender" / f"{self.name}.blend"), compress=True, relative_remap=True)
        mat = _baked_material("Baked_main", textures["main"]["images"])
        for o in layer_objs:
            for slot in o.material_slots:
                slot.material = mat
        arm = self._armature()
        meshes = self._variant_meshes(layer_objs, arm)
        for o in layer_objs:
            bpy.data.objects.remove(o)
        lods = {}
        if lod_ratio:
            for v, obj in meshes.items():
                lods[v] = self._lod(obj, lod_ratio)
        for o in list(meshes.values()) + list(lods.values()):
            self._keep_marker_bones(o)
        previews = []
        if preview:
            previews = self.render_previews(arm, meshes, views or [], poses or {}, preview_samples, extra_previews or [])
        self.apply_pose(arm, None)
        export = list(meshes.values()) + list(lods.values())
        glb = self.export_glb(arm, export, out_dir)
        manifest = self.write_manifest(out_dir, meshes, lods, textures, previews, poses or {})
        log(f"{self.name}: {json.dumps({k: v['tris'] for k, v in manifest['meshes'].items()})} tris, {time.time() - t0:.0f}s -> {glb.name}")
        return manifest

    # --- previews ---------------------------------------------------------
    def _preview_scene(self, center, radius):
        scene = bpy.context.scene
        world = bpy.data.worlds.new("PreviewWorld")
        world.use_nodes = True
        bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
        bg.inputs["Color"].default_value = (0.42, 0.5, 0.62, 1.0)
        bg.inputs["Strength"].default_value = 0.8
        scene.world = world
        sun_data = bpy.data.lights.new("Sun", "SUN")
        sun_data.energy = 4.5
        sun_data.angle = math.radians(3)
        sun_data.color = (1.0, 0.93, 0.82)
        sun = bpy.data.objects.new("Sun", sun_data)
        sun.rotation_euler = (math.radians(48), 0, math.radians(35))
        scene.collection.objects.link(sun)
        bpy.ops.mesh.primitive_plane_add(size=400, location=(center.x, center.y, -0.02))
        ground = bpy.context.active_object
        gm = bpy.data.materials.new("Ground")
        gm.use_nodes = True
        gb = next(n for n in gm.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
        gb.inputs["Base Color"].default_value = materials.rgb("#b0663e")  # ochre/rust basin sand
        gb.inputs["Roughness"].default_value = 1.0
        ground.data.materials.append(gm)
        cam_data = bpy.data.cameras.new("Cam")
        cam_data.lens = 50
        cam_data.clip_end = 5000
        cam = bpy.data.objects.new("Cam", cam_data)
        scene.collection.objects.link(cam)
        scene.camera = cam
        return sun, ground, cam

    def render_previews(self, arm, meshes, views, poses, samples, extra):
        """views: (label, direction, variants|None, pose_name, [lens], [res]).
        Variants are laid out side by side along X (spacing 3.2)."""
        scene = bpy.context.scene
        pipeline._setup_cycles(samples)
        scene.cycles.use_denoising = True
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGB"
        scene.render.image_settings.compression = 100
        sun, ground, cam = self._preview_scene(Vector((0, 0, 3)), 4)
        outputs = []
        for view in list(views) + list(extra):
            label, direction, vset, pose_name = view[:4]
            opts = view[4] if len(view) > 4 else {}
            vset = vset or self.variants
            self.apply_pose(arm, poses.get(pose_name))
            # Lay the chosen variants out along X; hide the rest.
            spacing = opts.get("spacing", 3.4)
            axis = 1 if opts.get("axis") == "y" else 0
            for o in bpy.data.objects:
                if o.type == "MESH" and o.parent is arm:
                    o.hide_render = True
            copies = []
            for i, v in enumerate(vset):
                offset = (i - (len(vset) - 1) / 2) * spacing
                if i == 0:
                    arm.location[axis] = offset
                    meshes[v].hide_render = False
                    continue
                # extra variants: temporary copies with their own posed armature
                a2 = arm.copy()
                a2.data = arm.data
                a2.location[axis] = offset
                bpy.context.scene.collection.objects.link(a2)
                m2 = meshes[v].copy()
                m2.parent = a2
                m2.modifiers["Armature"].object = a2
                m2.hide_render = False
                bpy.context.scene.collection.objects.link(m2)
                copies += [a2, m2]
            bpy.context.view_layer.update()
            objs = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_render and o.name != "Plane"]
            dg = bpy.context.evaluated_depsgraph_get()
            lo = Vector((1e9, 1e9, 1e9))
            hi = Vector((-1e9, -1e9, -1e9))
            for o in objs:
                ev = o.evaluated_get(dg)
                for v in ev.to_mesh().vertices:
                    co = ev.matrix_world @ v.co
                    lo = Vector(map(min, lo, co))
                    hi = Vector(map(max, hi, co))
                ev.to_mesh_clear()
            center = (lo + hi) / 2
            radius = (hi - lo).length / 2
            cam.data.lens = opts.get("lens", 50)
            fov = 2 * math.atan(18 / cam.data.lens)
            d = Vector(direction).normalized()
            dist = opts.get("distance") or radius / math.sin(fov / 2) * 1.02
            cam.location = center + d * dist
            cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
            res = opts.get("res", (1024, 1024))
            scene.render.resolution_x, scene.render.resolution_y = res
            path = ROOT / "assets" / "previews" / f"{self.name}{label}.png"
            scene.render.filepath = str(path)
            scene.render.image_settings.color_mode = "BW" if opts.get("bw") else "RGB"
            bpy.ops.render.render(write_still=True)
            scene.render.image_settings.color_mode = "RGB"
            outputs.append(str(path.relative_to(ROOT)))
            log(f"preview {path.name}")
            for o in copies:
                bpy.data.objects.remove(o)
            arm.location = (0, 0, 0)
        for o in (sun, ground, cam):
            bpy.data.objects.remove(o)
        for o in bpy.data.objects:
            if o.type == "MESH" and o.parent is arm:
                o.hide_render = False
        return outputs

    # --- export -----------------------------------------------------------
    def export_glb(self, arm, meshes, out_dir):
        bpy.ops.object.select_all(action="DESELECT")
        arm.select_set(True)
        for o in meshes:
            o.select_set(True)
        bpy.context.view_layer.objects.active = arm
        path = out_dir / f"{self.name}.glb"
        bpy.ops.export_scene.gltf(
            filepath=str(path),
            export_format="GLB",
            use_selection=True,
            export_apply=False,
            export_materials="NONE",
            export_texcoords=True,
            export_normals=True,
            export_yup=True,
            export_skins=True,
            export_animations=False,
            export_rest_position_armature=True,
        )
        return path

    def write_manifest(self, out_dir, meshes, lods, textures, previews, poses):
        def entry(obj, variant, lod):
            lo, hi = pipeline._bounds([obj])
            return {
                "variant": variant,
                "lod": lod,
                "tris": self._tri_count(obj),
                "center": pipeline.rb((lo + hi) / 2),
                "size": pipeline.rb_size(hi - lo),
            }

        mesh_entries = {v: entry(o, v, False) for v, o in meshes.items()}
        mesh_entries.update({o.name: entry(o, v, True) for v, o in lods.items()})
        manifest = {
            "name": self.name,
            "skinned": True,
            "variants": list(self.variants),
            "bones": [{"name": b.name, "parent": b.parent, "head": pipeline.rb(b.head)} for b in self.bones],
            "meshes": mesh_entries,
            "textures": {g: t["files"] for g, t in textures.items()},
            "previews": previews,
            "poses": {k: {b: list(r) for b, r in p.items()} for k, p in poses.items()},
            "pivot": pipeline.rb(self.pivot),
            "meta": self.meta,
        }
        with open(out_dir / "manifest.json", "w") as fh:
            json.dump(manifest, fh, indent=1)
        return manifest
