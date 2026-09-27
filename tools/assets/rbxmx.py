"""Generate a Roblox XML model (.rbxmx) from an asset manifest + ids.

Structure: top-level Model <Name>; sub-models from each part's `path`;
MeshParts carry MeshId/InitialSize and a SurfaceAppearance whose maps
come from the part's texture group. Markers become invisible Parts and
attachments become Attachments on their part. All parts are Anchored,
non-colliding unless flagged, CollisionFidelity Box (hit boxes per part).
"""
import math
from xml.sax.saxutils import escape

MATERIALS = {
    "Plastic": 256, "SmoothPlastic": 272, "Neon": 288, "Wood": 512, "Slate": 800,
    "Concrete": 816, "Rock": 896, "Sandstone": 912, "Metal": 1088, "DiamondPlate": 1056,
    "Fabric": 1312, "Sand": 1296, "Glass": 1568,
}
FIDELITY = {"Default": 0, "Hull": 1, "Box": 2, "PreciseConvexDecomposition": 3}


class Ref:
    def __init__(self):
        self.n = 0

    def __call__(self):
        self.n += 1
        return f"RBX{self.n:08X}"


def _num(v):
    return f"{v:.6g}" if isinstance(v, float) else str(v)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    length = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / length for c in v)


def look_rotation(look):
    """Rotation matrix rows for CFrame.lookAt(origin, origin + look)."""
    z = _norm(tuple(-c for c in look))
    up = (0.0, 1.0, 0.0) if abs(z[1]) < 0.99 else (0.0, 0.0, -1.0)
    x = _norm(_cross(up, z))
    y = _cross(z, x)
    return ((x[0], y[0], z[0]), (x[1], y[1], z[1]), (x[2], y[2], z[2]))


IDENTITY = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


def cframe_xml(tag, name, pos, rot=IDENTITY):
    fields = [("X", pos[0]), ("Y", pos[1]), ("Z", pos[2])]
    for i in range(3):
        for j in range(3):
            fields.append((f"R{i}{j}", rot[i][j]))
    inner = "".join(f"<{k}>{_num(float(v))}</{k}>" for k, v in fields)
    if tag == "OptionalCoordinateFrame":
        return f'<OptionalCoordinateFrame name="{name}"><CFrame>{inner}</CFrame></OptionalCoordinateFrame>'
    return f'<CoordinateFrame name="{name}">{inner}</CoordinateFrame>'


def vec3(name, v):
    return f'<Vector3 name="{name}"><X>{_num(float(v[0]))}</X><Y>{_num(float(v[1]))}</Y><Z>{_num(float(v[2]))}</Z></Vector3>'


def prop(kind, name, value):
    if kind == "bool":
        value = "true" if value else "false"
    elif kind == "Content":
        return f'<Content name="{name}"><url>{escape(value)}</url></Content>'
    elif kind == "string":
        value = escape(value)
    return f'<{kind} name="{name}">{value}</{kind}>'


def color3(rgb):
    r, g, b = (max(0, min(255, int(round(c * 255 if c <= 1 else c)))) for c in rgb[:3])
    return f'<Color3uint8 name="Color3uint8">{(0xFF << 24) | (r << 16) | (g << 8) | b}</Color3uint8>'


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


class Node:
    def __init__(self, cls, name, ref):
        self.cls = cls
        self.name = name
        self.ref = ref
        self.props = [prop("string", "Name", name)]
        self.children = []

    def xml(self, depth=1):
        pad = "  " * depth
        out = [f'{pad}<Item class="{self.cls}" referent="{self.ref}">', f"{pad}  <Properties>"]
        out += [f"{pad}    {p}" for p in self.props]
        out.append(f"{pad}  </Properties>")
        for c in self.children:
            out.append(c.xml(depth + 1))
        out.append(f"{pad}</Item>")
        return "\n".join(out)


def build(manifest, ids):
    ref = Ref()
    root = Node("Model", manifest["name"], ref())
    models = {"": root}
    pivots = manifest.get("pivots", {})

    def model_for(path):
        if path in models:
            return models[path]
        parent_path, _, leaf = path.rpartition("/")
        parent = model_for(parent_path)
        m = Node("Model", leaf, ref())
        parent.children.append(m)
        models[path] = m
        return m

    part_nodes = {}
    # Opt-in (RECLAIM-HS): meta `untextured` = [r, g, b] (0..1). The asset's
    # maps are never drawn (e.g. invisible hit volumes): no SurfaceAppearance,
    # parts keep their Material with this flat Color, so nothing can load them.
    untextured = manifest.get("meta", {}).get("untextured")
    tex_ids = {} if untextured else ids.get("textures", {})
    meshes = ids.get("meshes", {})
    for p in manifest["parts"]:
        node = Node("MeshPart", p["name"], ref())
        mesh = meshes.get(p["name"])
        if mesh is None:
            raise KeyError(f"no mesh id for part {p['name']}")
        node.props += [
            prop("Content", "MeshId", mesh["id"] if isinstance(mesh, dict) else mesh),
            vec3("InitialSize", p["size"]),
            vec3("size", p["size"]),
            cframe_xml("CoordinateFrame", "CFrame", p["center"]),
            prop("bool", "Anchored", True),
            prop("bool", "CanCollide", bool(p.get("collide", False))),
            prop("bool", "CanQuery", bool(p.get("query", True))),
            prop("bool", "CanTouch", False),
            prop("bool", "CastShadow", bool(p.get("shadow", True))),
            prop("token", "CollisionFidelity", FIDELITY[p.get("fidelity", "Box")]),
            prop("float", "Transparency", _num(float(p.get("transparency", 0)))),
        ]
        neon = p.get("neon")
        flat = p.get("flat")
        if neon is not None:
            node.props += [prop("token", "Material", MATERIALS["Neon"]), color3(neon)]
        elif flat is not None:
            # Opt-in (HS-6): no textures, a Roblox material + Color (glass).
            node.props += [prop("token", "Material", MATERIALS.get(p.get("material", "Glass"), 1568)), color3(flat)]
        else:
            base = untextured if isinstance(untextured, (list, tuple)) else (1, 1, 1)
            node.props += [prop("token", "Material", MATERIALS.get(p.get("material", "Metal"), 1088)), color3(base)]
            maps = tex_ids.get(p.get("tex") or "", {})
            if maps:
                sa = Node("SurfaceAppearance", "SurfaceAppearance", ref())
                for key, prop_name in (("color", "ColorMap"), ("normal", "NormalMap"), ("rough", "RoughnessMap"), ("metal", "MetalnessMap")):
                    if maps.get(key):
                        sa.props.append(prop("Content", prop_name, maps[key]))
                    else:
                        # Explicitly empty, so a live Rojo sync clears a map an
                        # earlier build had (absent properties are left as-is).
                        sa.props.append(f'<Content name="{prop_name}"><null></null></Content>')
                node.children.append(sa)
                wreck = ids.get("wreck", {}).get(p.get("tex") or "")
                if wreck:
                    # HS-5: the burnt look Kit.char swaps in on death (own
                    # normal/roughness maps, a 512² wreck colour map).
                    folder = Node("Folder", "Wreck", ref())
                    wsa = Node("SurfaceAppearance", "SurfaceAppearance", ref())
                    wsa.props.append(prop("Content", "ColorMap", wreck))
                    for key, prop_name in (("normal", "NormalMap"), ("rough", "RoughnessMap")):
                        if maps.get(key):
                            wsa.props.append(prop("Content", prop_name, maps[key]))
                    wsa.props.append('<Content name="MetalnessMap"><null></null></Content>')
                    folder.children.append(wsa)
                    node.children.append(folder)
        if p.get("pivot_offset") is not None:
            node.props.append(cframe_xml("CoordinateFrame", "PivotOffset", p["pivot_offset"]))
        model_for(p["path"]).children.append(node)
        part_nodes[p["name"]] = (node, p["center"])

    for m in manifest.get("markers", []):
        node = Node("Part", m["name"], ref())
        node.props += [
            vec3("size", m["size"]),
            cframe_xml("CoordinateFrame", "CFrame", m["pos"], look_rotation(m["axis"])),
            prop("bool", "Anchored", True),
            prop("bool", "CanCollide", False),
            prop("bool", "CanQuery", False),
            prop("bool", "CanTouch", False),
            prop("bool", "CastShadow", False),
            prop("float", "Transparency", 1),
            prop("token", "Material", MATERIALS["SmoothPlastic"]),
            color3((0.2, 0.2, 0.2)),
        ]
        model_for(m["path"]).children.append(node)
        part_nodes[m["name"]] = (node, m["pos"])

    for a in manifest.get("attachments", []):
        parent, center = part_nodes[a["part"]]
        node = Node("Attachment", a["name"], ref())
        node.props.append(cframe_xml("CoordinateFrame", "CFrame", _sub(a["pos"], center), look_rotation(a["axis"])))
        parent.children.append(node)

    for path, m in models.items():
        if path in pivots:
            m.props.append(cframe_xml("OptionalCoordinateFrame", "WorldPivotData", pivots[path]))
    primary = manifest.get("primary")
    if primary in part_nodes and not manifest.get("meta", {}).get("no_primary"):
        node, center = part_nodes[primary]
        root.props.append(f'<Ref name="PrimaryPart">{node.ref}</Ref>')
        if "" in pivots:
            node.props.append(cframe_xml("CoordinateFrame", "PivotOffset", _sub(pivots[""], center)))

    body = root.xml()
    return f'<roblox xmlns:xmime="http://www.w3.org/2005/05/xmlmime" version="4">\n{body}\n</roblox>\n'
