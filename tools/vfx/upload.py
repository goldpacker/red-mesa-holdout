#!/usr/bin/env python3
"""Upload VFX textures as private Roblox Images and refresh Flipbooks.luau ids.

    set -a; . ./.env.local; set +a
    python3 tools/vfx/upload.py            # every output in sheets/registry.py
    python3 tools/vfx/upload.py Fireball   # just these
    python3 tools/vfx/upload.py --ids-only # rewrite the Luau id block only

Uses tools/assets/opencloud.py (credentials from the environment, never
printed). Files whose hash is unchanged are skipped. Ids and hashes live in
assets/vfx/roblox_ids.json; the block between the GENERATED IDS markers in
src/shared/Flipbooks.luau is regenerated from it.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "tools" / "assets"))
sys.path.insert(0, str(HERE))

import opencloud  # noqa: E402
from sheets import registry  # noqa: E402

IDS = ROOT / "assets" / "vfx" / "roblox_ids.json"
LUAU = ROOT / "src" / "shared" / "Flipbooks.luau"
BEGIN, END = "-- BEGIN GENERATED IDS (tools/vfx/upload.py)", "-- END GENERATED IDS"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def load_ids() -> dict:
    if IDS.exists():
        return json.loads(IDS.read_text())
    return {"images": {}, "hashes": {}}


def save_ids(ids: dict) -> None:
    IDS.write_text(json.dumps(ids, indent=1, sort_keys=True) + "\n")


def upload(names: list[str], ids: dict) -> None:
    for name in names:
        path = ROOT / "assets" / "vfx" / f"{name}.png"
        if not path.exists():
            print(f"missing {path.relative_to(ROOT)}; run tools/vfx/render.sh {name}")
            continue
        h = sha(path)
        if ids["hashes"].get(name) == h and ids["images"].get(name):
            print(f"unchanged {name}: {ids['images'][name]}")
            continue
        res = opencloud.upload(str(path), "Image", f"RMH_VFX_{name}", "Red Mesa Holdout VFX texture")
        ids["images"][name] = f"rbxassetid://{res['assetId']}"
        ids["hashes"][name] = h
        save_ids(ids)
        print(f"uploaded {name}: {ids['images'][name]}")


def write_luau(ids: dict) -> None:
    text = LUAU.read_text()
    if BEGIN not in text or END not in text:
        raise SystemExit(f"{LUAU.relative_to(ROOT)} lacks the generated-ids markers")
    lines = [BEGIN, "local IDS: { [string]: string } = {"]
    for name in registry.SHEETS:
        if name in ids["images"]:
            lines.append(f'\t{name} = "{ids["images"][name]}",')
    lines.append("}")
    head, rest = text.split(BEGIN, 1)
    _, tail = rest.split(END, 1)
    LUAU.write_text(head + "\n".join(lines) + "\n" + END + tail)
    print(f"wrote ids into {LUAU.relative_to(ROOT)}")


def main(argv: list[str]) -> int:
    ids = load_ids()
    if argv[:1] != ["--ids-only"]:
        names = argv or list(registry.SHEETS)
        for n in names:
            registry.spec(n)
        upload(names, ids)
    write_luau(ids)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except opencloud.OpenCloudError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
