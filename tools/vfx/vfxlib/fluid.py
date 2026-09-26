"""Mantaflow gas sims for fire/smoke flipbooks (inside headless Blender).

Kept small on purpose: resolution ~64-96 and 60-90 frames bake in a couple
of minutes on the M4 Pro. The domain's grids render directly in Cycles
through `fire_smoke_material` (attributes density / flame / temperature).
"""
import os
import shutil
import time

import bpy
from mathutils import Vector


def _link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def _cube(name, size):
    import bmesh
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    bm.to_mesh(mesh)
    bm.free()
    return _link(bpy.data.objects.new(name, mesh))


def _sphere(name, radius, subdiv=3):
    import bmesh
    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=radius)
    bm.to_mesh(mesh)
    bm.free()
    return _link(bpy.data.objects.new(name, mesh))


def gas_domain(cache_dir, size=4.0, location=(0, 0, 0), res=80, frames=72, **settings):
    """A gas domain cube with open borders. Extra kwargs set domain_settings."""
    dom = _cube("Domain", size)
    dom.location = location
    mod = dom.modifiers.new("Fluid", "FLUID")
    mod.fluid_type = "DOMAIN"
    ds = mod.domain_settings
    ds.domain_type = "GAS"
    ds.resolution_max = res
    ds.use_adaptive_domain = False
    if os.path.isdir(cache_dir):
        shutil.rmtree(cache_dir)
    ds.cache_directory = cache_dir
    ds.cache_type = "ALL"
    ds.cache_frame_start = 1
    ds.cache_frame_end = frames
    for side in ("front", "back", "left", "right", "top", "bottom"):
        setattr(ds, f"use_collision_border_{side}", False)
    for key, value in settings.items():
        setattr(ds, key, value)
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = frames
    return dom


def flow_sphere(radius, location, flow_type="BOTH", on_frames=(1, 4), **settings):
    """An inflow sphere that emits only during `on_frames` (inclusive)."""
    obj = _sphere("Flow", radius)
    obj.location = location
    mod = obj.modifiers.new("Fluid", "FLUID")
    mod.fluid_type = "FLOW"
    fs = mod.flow_settings
    fs.flow_type = flow_type
    fs.flow_behavior = "INFLOW"
    fs.flow_source = "MESH"
    for key, value in settings.items():
        setattr(fs, key, value)
    first, last = on_frames
    for frame, state in ((first, True), (last, True), (last + 1, False)):
        fs.use_inflow = state
        fs.keyframe_insert("use_inflow", frame=frame)
    obj.hide_render = True
    return obj


def flow_texture(flow, scale=0.6, name="FlowNoise"):
    """Breaks up a flow's emission with a clouds texture (no perfect spheres)."""
    tex = bpy.data.textures.get(name) or bpy.data.textures.new(name, "CLOUDS")
    tex.noise_scale = scale
    fs = flow.modifiers["Fluid"].flow_settings
    fs.use_texture = True
    fs.noise_texture = tex
    fs.texture_map_type = "AUTO"
    fs.texture_size = 1.0


def density_bounds(domain, frames, threshold=0.02, grid="density_grid"):
    """World-space (xmin, xmax, zmin, zmax) union of the sim over `frames`."""
    import numpy as np
    boxes = frame_boxes(domain, frames, threshold, grid)
    box = [min(b[0] for b in boxes.values()), max(b[1] for b in boxes.values()),
           min(b[2] for b in boxes.values()), max(b[3] for b in boxes.values())]
    print(f"[vfx] sim bounds x {box[0]:.2f}..{box[1]:.2f} z {box[2]:.2f}..{box[3]:.2f}")
    return box


def frame_boxes(domain, frames, threshold=0.02, grid="density_grid"):
    """{frame: (xmin, xmax, zmin, zmax)} world-space density bounds per frame."""
    import numpy as np
    lo = np.array([min(v[i] for v in domain.bound_box) for i in range(3)])
    hi = np.array([max(v[i] for v in domain.bound_box) for i in range(3)])
    lo = np.array(domain.matrix_world @ Vector(lo))
    hi = np.array(domain.matrix_world @ Vector(hi))
    boxes = {}
    scene = bpy.context.scene
    for f in frames:
        scene.frame_set(f)
        evaluated = domain.evaluated_get(bpy.context.evaluated_depsgraph_get())
        eds = evaluated.modifiers["Fluid"].domain_settings
        base = np.array(tuple(eds.domain_resolution))
        data = np.array(getattr(eds, grid)[:], dtype=np.float32)
        if data.size == 0 or base.prod() == 0:
            continue
        up = round((data.size / base.prod()) ** (1.0 / 3.0))  # noise upres grids are larger
        res = base * up
        vol = data.reshape(res[2], res[1], res[0])
        zs, _, xs = np.nonzero(vol > threshold)
        if xs.size == 0:
            continue
        cell = (hi - lo) / res
        boxes[f] = (lo[0] + xs.min() * cell[0], lo[0] + (xs.max() + 1) * cell[0],
                    lo[2] + zs.min() * cell[2], lo[2] + (zs.max() + 1) * cell[2])
    if not boxes:
        raise RuntimeError("sim bounds empty: the bake produced no density")
    return boxes


def tracking_camera(boxes, frames, margin=1.1, smooth=5):
    """Per-frame camera centres following each frame's density box (smoothed),
    and one ortho size that fits the largest frame. Returns (centres, size)."""
    import numpy as np
    known = sorted(boxes)
    cx = np.interp(frames, known, [(boxes[f][0] + boxes[f][1]) / 2.0 for f in known])
    cz = np.interp(frames, known, [(boxes[f][2] + boxes[f][3]) / 2.0 for f in known])
    kernel = np.ones(smooth) / smooth
    pad = smooth // 2
    cx = np.convolve(np.pad(cx, pad, mode="edge"), kernel, mode="valid")
    cz = np.convolve(np.pad(cz, pad, mode="edge"), kernel, mode="valid")
    size = 0.0
    for f, x, z in zip(frames, cx, cz):
        if f in boxes:
            b = boxes[f]
            size = max(size, 2 * max(abs(b[0] - x), abs(b[1] - x), abs(b[2] - z), abs(b[3] - z)))
    size *= margin
    print(f"[vfx] tracking camera ortho {size:.2f}, centre z {cz[0]:.2f}..{cz[-1]:.2f}")
    return list(zip(cx, cz)), size


def fit_camera(box, margin=1.08, min_size=1.0):
    """Centres the ortho camera on box and sizes it to the larger extent."""
    cam = bpy.context.scene.camera
    cx, cz = (box[0] + box[1]) / 2.0, (box[2] + box[3]) / 2.0
    size = max(box[1] - box[0], box[3] - box[2], min_size) * margin
    cam.location.x, cam.location.z = cx, cz
    cam.data.ortho_scale = size
    print(f"[vfx] camera centre ({cx:.2f}, {cz:.2f}) ortho {size:.2f}")


def grid_stats(domain, frames):
    """Logs max / mean-of-nonzero of density, flame and temperature grids."""
    import numpy as np
    scene = bpy.context.scene
    for f in frames:
        scene.frame_set(f)
        eds = domain.evaluated_get(bpy.context.evaluated_depsgraph_get()).modifiers["Fluid"].domain_settings
        parts = []
        for name in ("density_grid", "flame_grid", "temperature_grid"):
            g = np.array(getattr(eds, name)[:], dtype=np.float32)
            nz = g[g > 1e-3]
            parts.append(f"{name.split('_')[0]} max {g.max() if g.size else 0:.2f} mean {nz.mean() if nz.size else 0:.2f}")
        print(f"[vfx] frame {f}: " + ", ".join(parts))


def bake(domain):
    start = time.time()
    with bpy.context.temp_override(object=domain, active_object=domain,
                                   selected_objects=[domain], selected_editable_objects=[domain]):
        bpy.ops.fluid.bake_all()
    secs = time.time() - start
    print(f"[vfx] fluid bake {secs:.1f}s")
    return secs


def _node(nt, kind, loc):
    node = nt.nodes.new(kind)
    node.location = loc
    return node


def fire_smoke_material(smoke_density=10.0, smoke_albedo=0.12, flame_gain=12.0, flame_power=1.4,
                        soot_clear=1.4,
                        ramp=((0.0, (0.35, 0.03, 0.0)), (0.3, (1.0, 0.22, 0.02)),
                              (0.6, (1.0, 0.5, 0.1)), (1.0, (1.0, 0.8, 0.45)))):
    """Principled Volume driven by the domain's density and flame grids."""
    mat = bpy.data.materials.new("FireSmoke")
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = _node(nt, "ShaderNodeOutputMaterial", (900, 0))
    vol = _node(nt, "ShaderNodeVolumePrincipled", (600, 0))
    dens_attr = _node(nt, "ShaderNodeAttribute", (-400, 200))
    dens_attr.attribute_name = "density"
    flame_attr = _node(nt, "ShaderNodeAttribute", (-400, -200))
    flame_attr.attribute_name = "flame"
    dmul = _node(nt, "ShaderNodeMath", (0, 200))
    dmul.operation = "MULTIPLY"
    dmul.inputs[1].default_value = smoke_density
    nt.links.new(dens_attr.outputs["Fac"], dmul.inputs[0])
    # Burning gas is hot and clear, soot sits outside it: density *= (1 - k*flame)^2.
    clear = _node(nt, "ShaderNodeMath", (0, 400))
    clear.operation = "MULTIPLY_ADD"
    clear.use_clamp = True
    clear.inputs[1].default_value = -soot_clear
    clear.inputs[2].default_value = 1.0
    nt.links.new(flame_attr.outputs["Fac"], clear.inputs[0])
    sq = _node(nt, "ShaderNodeMath", (200, 400))
    sq.operation = "MULTIPLY"
    nt.links.new(clear.outputs[0], sq.inputs[0])
    nt.links.new(clear.outputs[0], sq.inputs[1])
    soot = _node(nt, "ShaderNodeMath", (400, 300))
    soot.operation = "MULTIPLY"
    nt.links.new(dmul.outputs[0], soot.inputs[0])
    nt.links.new(sq.outputs[0], soot.inputs[1])
    nt.links.new(soot.outputs[0], vol.inputs["Density"])
    vol.inputs["Color"].default_value = (smoke_albedo, smoke_albedo, smoke_albedo, 1.0)

    cramp = _node(nt, "ShaderNodeValToRGB", (0, -200))
    elems = cramp.color_ramp.elements
    while len(elems) > 1:
        elems.remove(elems[-1])
    elems[0].position, elems[0].color = ramp[0][0], (*ramp[0][1], 1.0)
    for pos, col in ramp[1:]:
        e = elems.new(pos)
        e.color = (*col, 1.0)
    nt.links.new(flame_attr.outputs["Fac"], cramp.inputs["Fac"])
    nt.links.new(cramp.outputs["Color"], vol.inputs["Emission Color"])
    powr = _node(nt, "ShaderNodeMath", (0, -450))
    powr.operation = "POWER"
    powr.inputs[1].default_value = flame_power
    nt.links.new(flame_attr.outputs["Fac"], powr.inputs[0])
    gain = _node(nt, "ShaderNodeMath", (200, -450))
    gain.operation = "MULTIPLY"
    gain.name = "FlameGain"
    gain.inputs[1].default_value = flame_gain
    nt.links.new(powr.outputs[0], gain.inputs[0])
    nt.links.new(gain.outputs[0], vol.inputs["Emission Strength"])
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return mat
