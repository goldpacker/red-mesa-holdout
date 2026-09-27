"""Minimal GLB writer for the ground meshes (ENV-3).

Writes one node + mesh per part (positions, normals, UVs, uint32 indices,
no materials), the way the shared pipeline exports them, so
`tools/assets/publish.py` uploads and harvests them unchanged:

- positions are given in Roblox space; Roblox's glTF importer turns an
  asset 180 degrees about up, so they are written pre-turned (-x, y, -z)
  (docs/ASSET_PIPELINE.md "Axis handling");
- UVs are in glTF convention: (0, 0) is the image's top-left corner, v runs
  down the image, so v = image row / height.

`check_uv_orientation` verifies that every triangle's UV mapping is not
mirrored (tangent x bitangent points along the face normal, bitangent =
image up), so tangent-space normal maps light the right way.
"""
from __future__ import annotations

import json
import struct

import numpy as np


def vertex_normals(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n = np.zeros_like(v)
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    ln[ln == 0] = 1
    return n / ln


def face_normals(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    return fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)


def check_uv_orientation(v: np.ndarray, uv: np.ndarray, f: np.ndarray) -> float:
    """Fraction of triangles whose UV mapping is mirrored (should be 0)."""
    p0, p1, p2 = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    t0, t1, t2 = uv[f[:, 0]], uv[f[:, 1]], uv[f[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = t1 - t0, t2 - t0
    det = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    ok = np.abs(det) > 1e-12
    r = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)[:, None]
    tangent = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) * r        # dP/du
    dpdv = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) * r           # dP/dv (v down the image)
    bitangent = -dpdv                                         # image up
    s = np.einsum("ij,ij->i", np.cross(tangent, bitangent), face_normals(v, f))
    return float(np.mean(s[ok] < 0)) if ok.any() else 0.0


def write(path: str, parts: list[dict]) -> None:
    """parts: [{name, v (N,3) roblox, f (M,3), uv (N,2), n (N,3) optional}]"""
    buf = bytearray()
    accessors, views, meshes, nodes = [], [], [], []

    def add(data: np.ndarray, target: int, comp: int, typ: str, minmax: bool = False) -> int:
        while len(buf) % 4:
            buf.append(0)
        raw = data.tobytes()
        views.append({"buffer": 0, "byteOffset": len(buf), "byteLength": len(raw), "target": target})
        buf.extend(raw)
        acc = {"bufferView": len(views) - 1, "componentType": comp, "count": int(data.shape[0]), "type": typ}
        if minmax:
            acc["min"] = [float(x) for x in data.min(axis=0)]
            acc["max"] = [float(x) for x in data.max(axis=0)]
        accessors.append(acc)
        return len(accessors) - 1

    for p in parts:
        v = np.asarray(p["v"], dtype=np.float64)
        f = np.asarray(p["f"], dtype=np.int64)
        n = p.get("n")
        n = vertex_normals(v, f) if n is None else np.asarray(n, dtype=np.float64)
        turn = np.array([-1.0, 1.0, -1.0])
        pos = (v * turn).astype(np.float32)
        nor = (n * turn).astype(np.float32)
        uv = np.asarray(p["uv"], dtype=np.float32)
        ia = add(pos, 34962, 5126, "VEC3", True)
        na = add(nor, 34962, 5126, "VEC3")
        ta = add(uv, 34962, 5126, "VEC2")
        xa = add(f.astype(np.uint32).ravel(), 34963, 5125, "SCALAR")
        meshes.append({"name": p["name"], "primitives": [{"attributes": {"POSITION": ia, "NORMAL": na, "TEXCOORD_0": ta},
                                                          "indices": xa, "mode": 4}]})
        nodes.append({"name": p["name"], "mesh": len(meshes) - 1})
    while len(buf) % 4:
        buf.append(0)
    gltf = {
        "asset": {"version": "2.0", "generator": "red-mesa tools/env/ground/glb.py"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(buf)}],
    }
    js = json.dumps(gltf, separators=(",", ":")).encode()
    while len(js) % 4:
        js += b" "
    total = 12 + 8 + len(js) + 8 + len(buf)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A))
        fh.write(js)
        fh.write(struct.pack("<II", len(buf), 0x004E4942))
        fh.write(bytes(buf))
