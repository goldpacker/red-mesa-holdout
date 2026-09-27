"""QA-B texture reclaim for the environment's shipped maps (ENV-4 step 0).

    tools/env/py.sh tools/env/reclaim.py sky      # every preset's SkyboxDn -> DN_FACE²
    tools/env/py.sh tools/env/reclaim.py rocks    # Cliff_* maps -> CLIFF_SHIP², no metal maps on the rock kit

Shrinks maps in place (idempotent: a map already at its target size is left
alone) and drops the all-zero metalness maps from the manifests, so
`tools/env/publish_env.py upload sky` / `tools/assets/publish.py upload
<Name>` pick the new files up by hash and forget the metal ids. Why each cut
is invisible in play: .superpowers/sdd/AIRDROP_ENVIRONMENT_PLAN/reports/QA-B.md §6
(items 1, 3, 14).

  sky    The lower cube face is never on screen (every camera sits above the
         floor, pitch >= -45 deg). It still feeds Future lighting's ambient
         (EnvironmentDiffuseScale 0.4-0.55), so each preset keeps its own
         face, box-averaged (same mean colour; the 1024² faces vary by
         sd <= 3.6/255). tools/env/sky.py renders the face at DN_FACE.
  rocks  Cliff pieces are >= 290 studs from the gun: 1024² -> 512² (colour
         averaged in linear light, normals renormalised, roughness box).
         tools/assets/models/rock_kit.py bakes them at 1024² and calls
         shrink_asset() after the build, with metal=False on every piece.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import texlib as T  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
SKY = os.path.join(ROOT, "assets", "textures", "sky")
EXPORTED = os.path.join(ROOT, "assets", "exported")
DN_FACE = 64
CLIFF_SHIP = 512
CLIFFS = ("Cliff_Wall_A", "Cliff_Wall_B", "Cliff_Corner", "Cliff_Butte")
ROCKS = ("Rock_Boulder_A", "Rock_Boulder_B", "Rock_Boulder_C", "Rock_Slab", "Rock_Spire", "Rock_Rubble") + CLIFFS


def box(img: np.ndarray, size: int) -> np.ndarray:
    h, w = img.shape[:2]
    f = h // size
    assert h == w and h % size == 0, (h, w, size)
    return img.reshape(size, f, size, f, img.shape[2]).mean(axis=(1, 3))


def shrink_colour(path: str, size: int) -> bool:
    img = T.load(path)
    if img.shape[0] <= size:
        return False
    rgb = T.linear_to_srgb(box(T.srgb_to_linear(img[..., :3]), size))
    out = np.concatenate([rgb, box(img[..., 3:], size)], axis=-1) if img.shape[2] == 4 else rgb
    T.save(path, out.astype(np.float32))
    return True


def shrink_normal(path: str, size: int) -> bool:
    img = T.load(path)
    if img.shape[0] <= size:
        return False
    n = box(T.decode_normal(img[..., :3]), size)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-6)
    T.save(path, T.encode_normal(n).astype(np.float32))
    return True


def shrink_gray(path: str, size: int) -> bool:
    img = T.load(path)
    if img.shape[0] <= size:
        return False
    T.save(path, box(img[..., :1], size).astype(np.float32))
    return True


def drop_metal(name: str) -> bool:
    """Removes an asset's metalness maps (file + manifest entry)."""
    d = os.path.join(EXPORTED, name)
    man_path = os.path.join(d, "manifest.json")
    man = json.load(open(man_path))
    changed = False
    for group, files in man.get("textures", {}).items():
        fname = files.pop("metal", None)
        if fname:
            changed = True
            p = os.path.join(d, fname)
            if os.path.exists(p):
                os.remove(p)
    if changed:
        with open(man_path, "w") as fh:
            json.dump(man, fh, indent=1)
    return changed


def shrink_asset(name: str, size: int = CLIFF_SHIP) -> list[str]:
    """Shrinks every colour/normal/rough map of an exported asset to size²."""
    d = os.path.join(EXPORTED, name)
    man = json.load(open(os.path.join(d, "manifest.json")))
    done = []
    for group, files in man.get("textures", {}).items():
        for ch, fname in files.items():
            p = os.path.join(d, fname)
            fn = {"color": shrink_colour, "normal": shrink_normal, "rough": shrink_gray}.get(ch)
            if fn and fn(p, size):
                done.append(fname)
    return done


def sky() -> None:
    for preset in sorted(os.listdir(SKY)):
        p = os.path.join(SKY, preset, f"{preset}_Dn.png")
        if os.path.exists(p):
            before = T.load(p)
            changed = shrink_colour(p, DN_FACE)
            after = T.load(p)
            print(f"{preset:14s} Dn {before.shape[0]}² -> {after.shape[0]}²  mean {before[..., :3].mean(axis=(0, 1)).round(3)} -> "
                  f"{after[..., :3].mean(axis=(0, 1)).round(3)}{'' if changed else ' (already)'}")


def rocks() -> None:
    for name in ROCKS:
        metal = drop_metal(name)
        shrunk = shrink_asset(name) if name in CLIFFS else []
        print(f"{name:15s} metal {'dropped' if metal else '-'}; shrunk {', '.join(shrunk) or '-'}")


def main(argv: list[str]) -> int:
    cmds = {"sky": sky, "rocks": rocks}
    if not argv or any(a not in cmds for a in argv):
        print(__doc__)
        return 2
    for a in argv:
        cmds[a]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
