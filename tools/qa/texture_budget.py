#!/usr/bin/env python3
"""Texture budget attribution (QA-B, docs/PERF_BUDGET.md §5).

    tools/qa/py tools/qa/texture_budget.py attrib-script > /tmp/attrib.luau
        Prints tools/qa/texture_attrib.client.luau with its GROUPS table
        filled in from the id maps (texture_map.py): one removal group per
        asset, map-kind groups for the calibration assets.
    tools/qa/py tools/qa/texture_budget.py report <inventory.txt> <attrib.txt> [--md out.md]
        Joins the in-game inventory (texture_inventory.client.luau output)
        and the removal log with the id map: per-texture resolution,
        estimated MB (calibrated), measured MB per group, ranked table.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from texture_map import ROOT, build_map  # noqa: E402

TEMPLATE = ROOT / "tools/qa/texture_attrib.client.luau"

# Removal order. Each entry: (group name, predicate over a map record).
# Calibration first: the Emplacement and the terrain MaterialVariants are
# removed one map kind at a time, which gives bytes per pixel per kind.
def _kind(rec: dict) -> str:
    key = rec["keys"][0]
    if key.startswith("wreck/"):
        return "wreck"
    tail = key.split("/")[-1]
    return {"roughness": "rough", "metalness": "metal"}.get(tail, tail)


LANDSCAPE_WALLS = ("Landscape_FarWall", "Landscape_FlankLeft", "Landscape_FlankRight", "Landscape_RearWall")
VEHICLES = ("Tank", "Buggy", "Helicopter", "Jet", "TrimEnemy")

GROUPS: list[tuple[str, callable]] = [
    ("HS Emplacement normal", lambda r: r["asset"] == "Emplacement" and _kind(r) == "normal"),
    ("HS Emplacement rough", lambda r: r["asset"] == "Emplacement" and _kind(r) == "rough"),
    ("HS Emplacement metal", lambda r: r["asset"] == "Emplacement" and _kind(r) == "metal"),
    ("HS Emplacement color", lambda r: r["asset"] == "Emplacement" and _kind(r) == "color"),
    ("ENV terrain MV normal", lambda r: r["asset"] == "terrain" and _kind(r) == "normal"),
    ("ENV terrain MV rough", lambda r: r["asset"] == "terrain" and _kind(r) == "rough"),
    ("ENV terrain MV color", lambda r: r["asset"] == "terrain" and _kind(r) == "color"),
    ("ENV sky (active preset)", lambda r: r["asset"] == "sky"),
    ("ENV Landscape_Mesa", lambda r: r["asset"] == "Landscape_Mesa"),
    ("ENV landscape walls", lambda r: r["asset"] in LANDSCAPE_WALLS),
    ("ENV landscape buttes", lambda r: r["asset"].startswith("Landscape_Butte")),
    ("ENV cliff kit", lambda r: r["asset"].startswith("Cliff_")),
    ("ENV rock kit", lambda r: r["asset"].startswith("Rock_")),
    ("ENV GroundStrips", lambda r: r["asset"] == "GroundStrips"),
    ("ENV GroundDressing", lambda r: r["asset"] == "GroundDressing"),
    ("HS Gunsights", lambda r: r["asset"] == "Gunsights"),
    ("HS SiegeCrawler", lambda r: r["asset"] == "SiegeCrawler" and _kind(r) != "wreck"),
    ("HS SiegeCrawler wreck", lambda r: r["asset"] == "SiegeCrawler" and _kind(r) == "wreck"),
    ("HS Tank", lambda r: r["asset"] == "Tank" and _kind(r) != "wreck"),
    ("HS Buggy", lambda r: r["asset"] == "Buggy" and _kind(r) != "wreck"),
    ("HS Helicopter", lambda r: r["asset"] == "Helicopter" and _kind(r) != "wreck"),
    ("HS Jet", lambda r: r["asset"] == "Jet" and _kind(r) != "wreck"),
    ("HS TrimEnemy sheet", lambda r: r["asset"] == "TrimEnemy" and _kind(r) != "wreck"),
    ("HS vehicle wrecks", lambda r: r["asset"] in VEHICLES and _kind(r) == "wreck"),
    ("HS SupplyCrate", lambda r: r["asset"] == "SupplyCrate"),
    ("CHAR InfantrySkinned", lambda r: r["asset"] == "InfantrySkinned"),
    ("CHAR Infantry rigid + spike", lambda r: r["asset"] in ("Infantry", "InfantrySpike")),
    ("VFX flipbooks", lambda r: r["asset"] == "vfx"),
    ("VFX debris", lambda r: r["asset"] == "VfxDebris"),
    ("Look UI kit", lambda r: r["asset"] == "kit"),
    ("Look post/searchlight", lambda r: r["asset"] == "look"),
    ("Look tread motion", lambda r: r["asset"] == "motion"),
]
# The removal script re-points references at this HUD tile; never strip it.
KEEP_ID = "93922214770132"


def grouped(table: dict[str, dict]) -> list[tuple[str, list[dict]]]:
    out = []
    used: set[str] = set()
    for name, pred in GROUPS:
        recs = [r for r in table.values() if r["id"] not in used and r["id"] != KEEP_ID and pred(r)]
        used.update(r["id"] for r in recs)
        out.append((name, recs))
    rest = [r for r in table.values() if r["id"] not in used and r["id"] != KEEP_ID]
    if rest:
        out.append(("other mapped", rest))
    return out


def attrib_script() -> str:
    table = build_map()
    rows = []
    for name, recs in grouped(table):
        ids = ", ".join(f'"{r["id"]}"' for r in sorted(recs, key=lambda r: r["id"]))
        rows.append(f'\t{{ name = "{name}", ids = {{ {ids} }} }},')
    body = "{\n" + "\n".join(rows) + "\n}"
    text = TEMPLATE.read_text()
    return text.replace("{} --@@GROUPS@@", body)


# ------------------------------------------------------------------ report

INV_LINE = re.compile(r"^(\S+)\|(\d+)\|(\d+)\|([^|]*)\|(.*)$")
ATTRIB_LINE = re.compile(r"^(\d+)\s+(.+?)\s+refs\s+(\d+).*?tex\s+([\d.]+)\s+->\s+([\d.]+)\s+\(-\s*([-\d.]+)\)\s+particles\s+-\s*([-\d.]+)")


def read_inventory(path: Path) -> dict[str, dict]:
    inv = {}
    for line in path.read_text().splitlines():
        m = INV_LINE.match(line.strip())
        if m:
            rid, n, live, props, roots = m.groups()
            inv[rid] = {"n": int(n), "live": int(live), "props": props, "roots": roots}
    return inv


def read_attrib(path: Path) -> dict[str, dict]:
    out = {}
    for line in path.read_text().splitlines():
        m = ATTRIB_LINE.match(line.strip())
        if m:
            _i, name, refs, _b, _a, tex, particles = m.groups()
            out[name.strip()] = {"refs": int(refs), "tex": float(tex), "particles": float(particles)}
    return out


def mb(w: int, h: int, bpp: float) -> float:
    """Resident MB of one w×h map with a full mip chain at bpp bits/pixel."""
    return w * h * bpp / 8 * 4 / 3 / 2**20


def report(inv_path: Path, attrib_path: Path, bpp: dict[str, float], md: Path | None) -> None:
    table = build_map()
    inv = read_inventory(inv_path)
    attrib = read_attrib(attrib_path) if attrib_path.exists() else {}
    lines = ["| # | Group | Maps referenced (live) | Mpx | Estimated MB | Measured MB (GraphicsTexture) |",
             "|---|---|---|---|---|---|"]
    total_est = total_meas = 0.0
    for i, (name, recs) in enumerate(grouped(table), 1):
        referenced = [r for r in recs if r["id"] in inv and inv[r["id"]]["n"] > 0 and "WS" in inv[r["id"]]["roots"] + "MS.Lighting.PG"]
        live = [r for r in recs if r["id"] in inv and inv[r["id"]]["live"] > 0]
        px = sum(r["w"] * r["h"] for r in live)
        est = sum(mb(r["w"], r["h"], bpp.get(_kind(r), bpp["color"])) for r in live)
        meas = attrib.get(name, {}).get("tex")
        total_est += est
        total_meas += meas or 0
        lines.append(f"| {i} | {name} | {len(referenced)} ({len(live)}) | {px / 1e6:.2f} | {est:.1f} | "
                     f"{'' if meas is None else f'{meas:.1f}'} |")
    lines.append(f"| | **Total** | | | **{total_est:.1f}** | **{total_meas:.1f}** |")
    unmapped = [(rid, rec) for rid, rec in inv.items() if rid not in table]
    lines.append("")
    lines.append(f"Referenced ids with no local source ({len(unmapped)}):")
    for rid, rec in sorted(unmapped):
        lines.append(f"- `{rid}` refs {rec['n']} (live {rec['live']}) {rec['props']} {rec['roots'][:120]}")
    text = "\n".join(lines)
    print(text)
    if md:
        md.write_text(text + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("attrib-script")
    rp = sub.add_parser("report")
    rp.add_argument("inventory", type=Path)
    rp.add_argument("attrib", type=Path)
    rp.add_argument("--md", type=Path)
    rp.add_argument("--bpp", default="color=8,normal=8,rough=8,metal=8,wreck=8",
                    help="bits per pixel per map kind (calibrated from the removal log)")
    args = ap.parse_args()
    if args.cmd == "attrib-script":
        print(attrib_script())
    else:
        bpp = {k: float(v) for k, v in (kv.split("=") for kv in args.bpp.split(","))}
        report(args.inventory, args.attrib, bpp, args.md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
