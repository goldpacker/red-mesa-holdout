"""Procedural volume "blobs" for smoke, dust and trail sheets (inside Blender).

A blob is a 2x2x2 cube carrying a Principled Volume whose density is a
noise-distorted sphere with billowed edges. One material serves every blob;
each object passes its own values through `Object.color`:

    R = density multiplier     G = evolution time (0..1, drives 4D noise W)
    B = heat (emission, 0..1)  A = unused

Sheets animate blobs from Python per frame (location, radius, colour).
"""
import bmesh
import bpy


def _node(nt, kind, loc=(0, 0), **props):
    node = nt.nodes.new(kind)
    node.location = loc
    for key, value in props.items():
        setattr(node, key, value)
    return node


def _math(nt, op, a, b=None, loc=(0, 0), clamp=False):
    node = _node(nt, "ShaderNodeMath", loc, operation=op, use_clamp=clamp)
    for idx, val in ((0, a), (1, b)):
        if val is None:
            continue
        if isinstance(val, (int, float)):
            node.inputs[idx].default_value = val
        else:
            nt.links.new(val, node.inputs[idx])
    return node.outputs[0]


def _value(nt, name, value, loc=(0, 0)):
    node = _node(nt, "ShaderNodeValue", loc)
    node.name = name
    node.label = name
    node.outputs[0].default_value = value
    return node.outputs[0]


def set_param(mat, name, value):
    """Sets a named Value node ("Softness", "Density") for the next frame."""
    mat.node_tree.nodes[name].outputs[0].default_value = value


def _noise(nt, vector, w, scale, detail, roughness, distortion=0.0, loc=(0, 0)):
    node = _node(nt, "ShaderNodeTexNoise", loc, noise_dimensions="4D", noise_type="FBM")
    nt.links.new(vector, node.inputs["Vector"])
    nt.links.new(w, node.inputs["W"])
    node.inputs["Scale"].default_value = scale
    node.inputs["Detail"].default_value = detail
    node.inputs["Roughness"].default_value = roughness
    node.inputs["Distortion"].default_value = distortion
    return node


def blob_material(name="Blob", albedo=(1.0, 1.0, 1.0), density=10.0, softness=0.35,
                  distort=0.45, distort_scale=1.1, billow_scale=2.6, billow_amp=0.9,
                  billow_detail=6.0, roughness=0.55, anisotropy=0.2, time_scale=3.0,
                  emission_color=(1.0, 0.45, 0.12), emission_gain=0.0,
                  absorption=(0.0, 0.0, 0.0), interior=0.0, interior_scale=4.0):
    """Shared blob volume material. Returns the material."""
    mat = bpy.data.materials.new(name)
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = _node(nt, "ShaderNodeOutputMaterial", (1400, 0))
    texco = _node(nt, "ShaderNodeTexCoord", (-1200, 0))
    info = _node(nt, "ShaderNodeObjectInfo", (-1200, -300))
    sep = _node(nt, "ShaderNodeSeparateColor", (-1000, -300))
    nt.links.new(info.outputs["Color"], sep.inputs[0])
    p = texco.outputs["Object"]

    # W = time * time_scale + random * 17  (each blob evolves on its own)
    w = _math(nt, "MULTIPLY_ADD", sep.outputs[1], time_scale, (-800, -300))
    rnd = _math(nt, "MULTIPLY", info.outputs["Random"], 17.0, (-900, -450))
    nt.links.new(rnd, w.node.inputs[2])

    # Domain-warp the sphere with a low-frequency vector noise.
    warp = _noise(nt, p, w, distort_scale, 2.0, 0.5, loc=(-800, 150))
    centred = _node(nt, "ShaderNodeVectorMath", (-600, 150), operation="SUBTRACT")
    nt.links.new(warp.outputs["Color"], centred.inputs[0])
    centred.inputs[1].default_value = (0.5, 0.5, 0.5)
    scaled = _node(nt, "ShaderNodeVectorMath", (-450, 150), operation="SCALE")
    nt.links.new(centred.outputs[0], scaled.inputs[0])
    scaled.inputs["Scale"].default_value = distort
    q = _node(nt, "ShaderNodeVectorMath", (-300, 100), operation="ADD")
    nt.links.new(p, q.inputs[0])
    nt.links.new(scaled.outputs[0], q.inputs[1])
    length = _node(nt, "ShaderNodeVectorMath", (-150, 100), operation="LENGTH")
    nt.links.new(q.outputs[0], length.inputs[0])

    # Billowed edge: fBm on the warped coordinates.
    billow = _noise(nt, q.outputs[0], w, billow_scale, billow_detail, roughness, loc=(-150, -150))
    b_centred = _math(nt, "SUBTRACT", billow.outputs["Fac"], 0.5, (50, -150))
    b_amp = _math(nt, "MULTIPLY", b_centred, billow_amp, (200, -150))
    inside = _math(nt, "SUBTRACT", 1.0, length.outputs["Value"], (50, 100))
    field = _math(nt, "ADD", inside, b_amp, (350, 0))

    soft = _value(nt, "Softness", softness, (300, 200))
    dens_val = _value(nt, "Density", density, (650, 200))
    ramp = _node(nt, "ShaderNodeMapRange", (500, 0), interpolation_type="SMOOTHSTEP")
    nt.links.new(field, ramp.inputs["Value"])
    ramp.inputs["From Min"].default_value = 0.0
    nt.links.new(soft, ramp.inputs["From Max"])
    dens = _math(nt, "MULTIPLY", ramp.outputs["Result"], sep.outputs[0], (700, 0))
    dens = _math(nt, "MULTIPLY", dens, dens_val, (850, 0))

    # Interior breakup: thicker and thinner patches inside the silhouette.
    inner = _noise(nt, q.outputs[0], w, interior_scale, 4.0, 0.55, loc=(300, -450))
    patch = _node(nt, "ShaderNodeMapRange", (500, -450), interpolation_type="SMOOTHSTEP")
    nt.links.new(inner.outputs["Fac"], patch.inputs["Value"])
    patch.inputs["From Min"].default_value = 0.32
    patch.inputs["From Max"].default_value = 0.68
    amount = _value(nt, "Interior", interior, (500, -650))
    mix = _node(nt, "ShaderNodeMix", (700, -450), data_type="FLOAT")
    nt.links.new(amount, mix.inputs["Factor"])
    mix.inputs["A"].default_value = 1.0
    nt.links.new(patch.outputs["Result"], mix.inputs["B"])
    dens = _math(nt, "MULTIPLY", dens, mix.outputs["Result"], (950, -100))

    vol = _node(nt, "ShaderNodeVolumePrincipled", (1100, 0))
    vol.inputs["Color"].default_value = (*albedo, 1.0)
    vol.inputs["Absorption Color"].default_value = (*absorption, 1.0)
    vol.inputs["Anisotropy"].default_value = anisotropy
    nt.links.new(dens, vol.inputs["Density"])
    if emission_gain > 0:
        core = _node(nt, "ShaderNodeMapRange", (700, -300), interpolation_type="SMOOTHSTEP")
        nt.links.new(field, core.inputs["Value"])
        core.inputs["From Min"].default_value = 0.05
        core.inputs["From Max"].default_value = 0.7
        heat = _math(nt, "MULTIPLY", core.outputs["Result"], sep.outputs[2], (850, -300))
        heat = _math(nt, "MULTIPLY", heat, emission_gain, (950, -300))
        nt.links.new(heat, vol.inputs["Emission Strength"])
        vol.inputs["Emission Color"].default_value = (*emission_color, 1.0)
    nt.links.new(vol.outputs[0], out.inputs["Volume"])
    return mat


def _cube_mesh():
    mesh = bpy.data.meshes.get("BlobCube")
    if mesh:
        return mesh
    mesh = bpy.data.meshes.new("BlobCube")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bm.to_mesh(mesh)
    bm.free()
    return mesh


def add_blob(mat, name="Blob"):
    """A new blob object using `mat` (each object gets its own mesh slot link)."""
    mesh = _cube_mesh()
    if not mesh.materials:
        mesh.materials.append(mat)
    obj = bpy.data.objects.new(name, mesh)
    obj.material_slots[0].link = "OBJECT"
    obj.material_slots[0].material = mat
    bpy.context.scene.collection.objects.link(obj)
    return obj


def set_blob(obj, location, radius, density=1.0, time=0.0, heat=0.0):
    obj.location = location
    obj.scale = (radius, radius, radius)
    obj.color = (max(0.0, min(1.0, density)), max(0.0, min(1.0, time)),
                 max(0.0, min(1.0, heat)), 1.0)
    obj.hide_render = density <= 0.001 or radius <= 0.001
