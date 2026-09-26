"""InfantrySpike: the skinned-mesh pipeline spike (CHAR-1) and its
regression test. A 6-stud bar on three bones (Base -> Mid -> Tip) with a
nub on its front face (+Y, becomes Roblox -Z) and a cap block skinned only
to Tip, built with rmh/skin.py exactly like the soldier.

    tools/assets/build.sh InfantrySpike
    python3 tools/assets/skin_publish.py upload InfantrySpike
    python3 tools/assets/skin_publish.py harvest InfantrySpike   # run in Studio (Edit)
    python3 tools/assets/skin_publish.py meshes InfantrySpike harvest.json

Setting Mid/Tip `Bone.Transform` in a playtest must bend the bar smoothly
across z = 2 and z = 4 (see docs/ASSET_PIPELINE.md, "Skinned meshes").
"""
import bmesh

from rmh import geo
from rmh.skin import Bone, SkinnedAsset


def build(**kw):
    bones = [
        Bone("Base", (0, 0, 0), end=(0, 0, 2)),
        Bone("Mid", (0, 0, 2), end=(0, 0, 4), parent="Base"),
        Bone("Tip", (0, 0, 4), end=(0, 0, 6), parent="Mid"),
    ]
    s = SkinnedAsset("InfantrySpike", bones, ("Bar",), tex_size=256, pivot=(0, 0, 0))
    s.material("bar", base="gunmetal", color="#6a6e74", wear=0.4,
               marks=[{"lo": (-1, -1, 1.9), "hi": (1, 1, 2.1), "color": "#a3161a"}, {"lo": (-1, -1, 3.9), "hi": (1, 1, 4.1), "color": "#a3161a"}])
    bar = bmesh.new()
    bmesh.ops.create_cube(bar, size=1.0)
    for v in bar.verts:
        v.co.z += 0.5
    bmesh.ops.subdivide_edges(bar, edges=[e for e in bar.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 0.5], cuts=11, use_grid_fill=True)
    for v in bar.verts:
        v.co.z *= 6.0
    s.add(bar, "bar", bones=["Base", "Mid", "Tip"], falloff=6.0)
    s.add(geo.box(0.4, 0.4, 0.4, bevel=0.0), "bar", bones="Tip", at=(0, 0.65, 5.2))  # front nub
    s.add(geo.box(0.6, 0.6, 0.6, bevel=0.0), "bar", bones="Tip", at=(0.9, 0, 5.5))  # cap on Tip only
    s.meta = {"rbxmx_prefix": "InfantrySpike"}
    return s.finish(views=[("", (1.0, 1.3, 0.4), None, "Rest", {})], poses={}, preview=kw.get("preview", True), samples=kw.get("samples", 16))
