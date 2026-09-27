#!/usr/bin/env python3
"""Texture budget attribution (QA-B, docs/PERF_BUDGET.md §5).

    tools/qa/py tools/qa/texture_budget.py attrib-script > /tmp/attrib.luau
        Prints tools/qa/texture_attrib.client.luau with its GROUPS table
        filled in from the id maps (texture_map.py): one removal group per
        asset, map-kind groups for the calibration assets.
    tools/qa/py tools/qa/texture_budget.py report [<inventory.txt>] [--md out.md]
        Ranked per-asset table of full-resolution resident texture memory
        from the calibrated cost model (SA/MaterialVariant maps block-
        compressed, sky/decal/particle/beam/GUI images RGBA8, full mips),
        marking what an in-game inventory (texture_inventory.client.luau
        output) had live.
"""
from __future__ import annotations

import argparse
import re
import sys
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
# Calibrated resident cost at the top mip (QA-B additive calibration,
# qa/beauty/perf/qa-b/session2-perf-calib.txt): SurfaceAppearance and
# MaterialVariant maps are block-compressed — colour 4 bpp (8 with real
# alpha), normal 8 bpp, roughness+metalness packed into one 4 bpp map that
# also exists whenever a normal map does. Sky faces, Decals/Textures,
# particle, beam and GUI images are uncompressed RGBA8 (32 bpp). A full mip
# chain adds a third.
# Colour maps with real alpha: 32 bpp is the upper bound that fits ENV-3F's
# A/B (strips +3.0 MB, dressing +1.2 MB measured vs 3.6 / 1.4 modelled).
SA_BPP = {"color": 4, "color_alpha": 32, "normal": 8, "mr": 4}
RAW_BPP = 32
# Particle textures stream by on-screen size and stayed at or below mip 1
# even for 700-px particles (QA-B session 3): at most a quarter of the chain.
PARTICLE_SHARE = 0.25
# Flipbook images that are not particle textures (Flipbooks.luau notes).
VFX_NOT_PARTICLE = {"ScorchMark": "decal", "TracerBeam": "beam"}
# Terrain MaterialVariant textures don't show up in GraphicsTexture at all
# (QA-B session 3: a drawn override added 0.00 MB there).
NOT_IN_GRAPHICS_TEXTURE = {"terrain"}

# Where each asset is seen (camera distance from the turret, waves).
WHERE = {
    "sky": "always, full screen; one preset resident (two for ~1.5 s at a swap)",
    "vfx": "combat effects; resident once used, any wave; size on screen varies",
    "Emplacement": "always, 0-30 studs (the player's own turret pit); title/flank 400-700",
    "terrain": "always, 20-2000 studs",
    "Landscape_Mesa": "always, 10-200 studs below/around the turret",
    "SiegeCrawler": "wave 10 only, 400-1300 studs (night)",
    "Gunsights": "while aiming (right mouse), full screen; preloaded at start",
    "Tank": "waves 3, 5, 7, 9; 150-1200 studs",
    "Buggy": "waves 2, 5, 7, 9; 150-1200 studs",
    "Helicopter": "waves 4, 6, 8, 9; 150-900 studs",
    "Jet": "waves 6-9, fast passes 100-1000 studs",
    "TrimEnemy": "every vehicle (waves 2-10)",
    "InfantrySkinned": "every wave, 60-700 studs",
    "Cliff_": "wall bases, 500-1400 studs",
    "Rock_": "basin floor scatter, 100-1000 studs",
    "Landscape_": "far walls/buttes, 600-2000 studs",
    "GroundStrips": "road/wash edges, 50-1300 studs",
    "GroundDressing": "basin floor, 50-1000 studs (1,214 instances)",
    "SupplyCrate": "waves with crates (3-10), falling toward the mesa",
    "VfxDebris": "explosion debris, briefly",
    "kit": "HUD, always",
    "look": "night searchlight cones, heat haze (day), vignette",
    "motion": "tank/crawler treads",
    "Infantry": "unused since CHAR-2 (rigid parts' appearances destroyed)",
    "InfantrySpike": "unused (spike test)",
    "Transport": "Update 2 airdrop transports, 250-350 studs up, 300-1500 studs out (HS-6, not in game yet)",
    "Parachute": "Update 2 chutes (HS-6, not in game yet)",
    "ParachuteCargo": "Update 2 cargo chutes (HS-6, not in game yet)",
    "DropPlatform": "Update 2 vehicle drop platforms (HS-6, not in game yet)",
    "TrimAirdrop": "Update 2 shared airdrop trim sheet (HS-6, not in game yet)",
}


INV_LINE = re.compile(r"^(\S+)\|(\d+)\|(\d+)\|([^|]*)\|(.*)$")


def read_inventory(path: Path) -> dict[str, dict]:
    inv = {}
    for line in path.read_text().splitlines():
        m = INV_LINE.match(line.strip())
        if m:
            rid, n, live, props, roots = m.groups()
            inv[rid] = {"n": int(n), "live": int(live), "props": props, "roots": roots}
    return inv


def where(asset: str) -> str:
    for key, text in WHERE.items():
        if asset == key or (key.endswith("_") and asset.startswith(key)):
            return text
    return ""


def mb(w: int, h: int, bpp: float) -> float:
    """Resident MB of one w x h map with a full mip chain at bpp bits/pixel."""
    return w * h * bpp / 8 * 4 / 3 / 2**20


def cost_rows(table: dict[str, dict]) -> list[dict]:
    """One row per SurfaceAppearance/MaterialVariant combination or raw image."""
    import json

    def dims(rid: str) -> tuple[int, int, bool]:
        r = table.get(rid.replace("rbxassetid://", ""), {})
        return r.get("w", 0), r.get("h", 0), r.get("alpha", False)

    rows = []
    for map_path in sorted((ROOT / "assets").rglob("roblox_ids.json")):
        rel = map_path.relative_to(ROOT).as_posix()
        if rel.startswith("assets/ui/art/cache"):
            continue
        asset = map_path.parent.name
        data = json.loads(map_path.read_text())
        def sa_row(group: str, maps: dict[str, str]):
            total, ids, parts = 0.0, [], []
            area_mr = 0
            for kind, rid in maps.items():
                w, h, alpha = dims(rid)
                ids.append(rid.replace("rbxassetid://", ""))
                parts.append(f"{kind} {w}")
                if kind == "color":
                    total += mb(w, h, SA_BPP["color_alpha" if alpha else "color"])
                elif kind == "normal":
                    total += mb(w, h, SA_BPP["normal"])
                    area_mr = max(area_mr, w * h)
                else:  # rough / roughness / metal
                    area_mr = max(area_mr, w * h)
            if area_mr:
                total += area_mr * SA_BPP["mr"] / 8 * 4 / 3 / 2**20
            rows.append({"asset": asset, "group": group, "type": "SA", "ids": ids, "mb": total, "maps": parts,
                         "in_gt": asset not in NOT_IN_GRAPHICS_TEXTURE})
        for group, maps in (data.get("textures") or {}).items():
            sa_row(group, maps)
        for group, rid in (data.get("wreck") or {}).items():
            sa_row("wreck/" + group, {"color": rid})
        if asset == "terrain":
            mats: dict[str, dict[str, str]] = {}
            for key, rid in data["ids"].items():
                mat, kind = key.split("/")
                mats.setdefault(mat, {})[{"roughness": "rough"}.get(kind, kind)] = rid
            for mat, maps in mats.items():
                sa_row(mat, maps)
            continue
        for section in ("ids", "images"):
            for key, rid in (data.get(section) or {}).items():
                w, h, _ = dims(rid)
                group = key.split("/")[0] if asset == "sky" else key
                cost = mb(w, h, RAW_BPP)
                kind = "raw"
                if asset == "vfx" and key not in VFX_NOT_PARTICLE:
                    cost *= PARTICLE_SHARE
                    kind = "particle"
                rows.append({"asset": asset, "group": group, "type": kind, "in_gt": True,
                             "ids": [rid.replace("rbxassetid://", "")], "mb": cost, "maps": [f"{w}x{h}"]})
    return rows


UNUSED = {"Infantry", "InfantrySpike"}
NOT_IN_GAME_YET = {"TrimAirdrop", "Transport", "Parachute", "ParachuteCargo", "DropPlatform"}


def summarize(rows: list[dict], inv: dict[str, dict]) -> dict[str, dict]:
    per_asset: dict[str, dict] = {}
    for r in rows:
        live = any(inv.get(i, {}).get("live", 0) > 0 for i in r["ids"])
        key = r["asset"] if r["asset"] != "sky" else f"sky {r['group']}"
        a = per_asset.setdefault(key, {"asset": r["asset"], "mb": 0.0, "live_mb": 0.0, "n": 0, "maps": [],
                                       "in_gt": r["in_gt"], "types": set()})
        a["mb"] += r["mb"]
        a["n"] += len(r["ids"])
        a["types"].add(r["type"])
        if live:
            a["live_mb"] += r["mb"]
        a["maps"].extend(r["maps"])
    return per_asset


def report(inv_path: Path | None, md: Path | None) -> None:
    table = build_map()
    inv = read_inventory(inv_path) if inv_path and inv_path.exists() else {}
    per_asset = summarize(cost_rows(table), inv)
    owners = {rec["asset"]: rec["owner"] for rec in table.values()}
    lines = ["| # | Asset | Owner | Maps | MB at full res (model) | Drawn in the all-loaded scene | Where it's seen |",
             "|---|---|---|---|---|---|---|"]
    run_total, live_total, by_owner = 0.0, 0.0, {}
    ranked = sorted(per_asset.items(), key=lambda kv: -kv[1]["mb"])
    for i, (key, a) in enumerate(ranked, 1):
        res: dict[str, int] = {}
        for m in a["maps"]:
            res[m] = res.get(m, 0) + 1
        maps = ", ".join(f"{n}x {m}" for m, n in sorted(res.items(), key=lambda kv: -kv[1]))
        note = ""
        if not a["in_gt"]:
            note = " (not in GraphicsTexture)"
        elif a["asset"] in UNUSED:
            note = " (never drawn)"
        elif a["asset"] in NOT_IN_GAME_YET:
            note = " (not in game yet)"
        elif "particle" in a["types"]:
            note = " (particles: ≤ mip 1)"
        # one sky preset counts (all cost the same; Night until the game went
        # daylight-only, 3397923, now Sunset, the last preset)
        counts = a["asset"] not in UNUSED | NOT_IN_GAME_YET and a["in_gt"] and (
            a["asset"] != "sky" or key == "sky Sunset")
        if counts:
            run_total += a["mb"]
            owner = owners.get(a["asset"], "?")
            by_owner[owner] = by_owner.get(owner, 0.0) + a["mb"]
        if a["in_gt"]:
            live_total += a["live_mb"]
        lines.append(f"| {i} | {key}{note} | {owners.get(a['asset'], '?')} | {a['n']} ({maps}) | {a['mb']:.1f} | "
                     f"{a['live_mb']:.1f} | {where(a['asset'])} |")
    owners_text = ", ".join(f"{o} {v:.1f}" for o, v in sorted(by_owner.items(), key=lambda kv: -kv[1]))
    lines.append("")
    lines.append(f"Game-owned GraphicsTexture, every asset drawn once, one sky preset: **{run_total:.1f} MB** "
                 f"({owners_text}); +32 MB for ~1.5 s at each sky swap.")
    if inv:
        lines.append(f"Of that, drawn in the inventoried scene: {live_total:.1f} MB.")
    text = "\n".join(lines)
    print(text)
    if md:
        md.write_text(text + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("attrib-script")
    rp = sub.add_parser("report")
    rp.add_argument("inventory", type=Path, nargs="?", help="texture_inventory output (marks what was live)")
    rp.add_argument("--md", type=Path)
    args = ap.parse_args()
    if args.cmd == "attrib-script":
        print(attrib_script())
    else:
        report(args.inventory, args.md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
