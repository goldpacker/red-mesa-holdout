#!/usr/bin/env python3
"""Upload the landscape pieces and write their .rbxmx (Rojo -> ReplicatedStorage.Assets).

Uses the shared pipeline (tools/assets/publish.py, read-only) on the assets
bake.py exports as assets/exported/Landscape_<Piece>/:

  set -a; . ./.env.local; set +a
  .venv-env/bin/python tools/env/landscape/publish.py upload [Piece ...]     # GLB + maps (skips unchanged)
  .venv-env/bin/python tools/env/landscape/publish.py harvest [Piece ...]    # prints the Studio snippet (Edit)
  .venv-env/bin/python tools/env/landscape/publish.py meshes <harvest.json>  # ids -> assets/roblox/Landscape_*.rbxmx
  .venv-env/bin/python tools/env/landscape/publish.py rbxmx [Piece ...]      # regenerate from cached ids

The rbxmx gets RenderFidelity Precise on every chunk: the pieces are large
and seen from far away, so Roblox's automatic mesh LOD would pop them.
"""
import json
import re
import sys
from pathlib import Path

import importlib.util

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(1, str(ROOT / "tools" / "assets"))

from pieces import PIECES  # noqa: E402

# tools/assets/publish.py (same module name as this file, so load it by path).
_spec = importlib.util.spec_from_file_location("assets_publish", ROOT / "tools" / "assets" / "publish.py")
pipeline = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pipeline)
rbxmx = pipeline.rbxmx

RENDER_PRECISE = '<token name="RenderFidelity">1</token>'


def names(args):
    return [f"Landscape_{a}" for a in (args or list(PIECES))]


def write_rbxmx(name: str) -> None:
    _, manifest, ids, _ = pipeline.load(name)
    xml = rbxmx.build(manifest, ids)
    xml = re.sub(r'(<token name="Material">\d+</token>)', r"\1" + RENDER_PRECISE, xml)
    target = ROOT / "assets" / "roblox" / f"{name}.rbxmx"
    target.write_text(xml)
    print(f"wrote {target.relative_to(ROOT)} ({len(manifest['parts'])} chunks)")


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "upload":
        for n in names(rest):
            pipeline.upload(n)
    elif cmd == "harvest":
        pipeline.harvest(names(rest))
    elif cmd == "meshes":
        text = Path(rest[0]).read_text()
        data = json.loads(text)
        if isinstance(data, str):
            data = json.loads(data)
        for name, meshes in data.items():
            pipeline.meshes(name, json.dumps(meshes))
            write_rbxmx(name)
    elif cmd == "rbxmx":
        for n in names(rest):
            write_rbxmx(n)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
