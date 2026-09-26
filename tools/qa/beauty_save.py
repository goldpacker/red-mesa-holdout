"""Saves Studio screen captures into a beauty-shot set and rebuilds its
contact sheet. See tools/qa/BEAUTY.md.

Every `screen_capture` MCP call leaves its image in the Claude session's
tool-results folder as `mcp-Roblox_Studio-blob-<epoch ms>-<id>.jpg`. This
tool takes those blobs in capture order and files them as
`qa/beauty/<set>/<tod>_<n>-<shot>.jpg` at the canonical resolution.

    # newest capture -> one name
    tools/qa/py tools/qa/beauty_save.py --set p1-env sunset_4-flank
    # every capture since a timestamp, in order -> the names given
    tools/qa/py tools/qa/beauty_save.py --set p1-env --since 1790436000 \
        sunset_2-turret sunset_4-flank night_5-night
    # only rebuild the contact sheet
    tools/qa/py tools/qa/beauty_save.py --set p1-env --sheet
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qaimg  # noqa: E402

BLOB_ROOT = Path(os.environ.get(
    "QA_BLOB_ROOT",
    Path.home() / ".claude" / "projects" / "-Users-xichaowang-projects-beach-head-opus"))
BLOB_RE = re.compile(r"mcp-Roblox_Studio-blob-(\d{13})-\w+\.(jpg|jpeg|png)$")


def find_blobs() -> list[tuple[int, Path]]:
    blobs = []
    for path in BLOB_ROOT.rglob("mcp-Roblox_Studio-blob-*"):
        m = BLOB_RE.search(path.name)
        if m:
            blobs.append((int(m.group(1)), path))
    blobs.sort()
    return blobs


def pick(names: list[str], since: float | None) -> list[tuple[int, Path]]:
    blobs = find_blobs()
    if since is not None:
        chosen = [b for b in blobs if b[0] > since * 1000]
        if len(chosen) != len(names):
            listing = "\n".join(f"  {time.strftime('%H:%M:%S', time.localtime(t / 1000))} {p}" for t, p in chosen)
            sys.exit(f"found {len(chosen)} captures since {since}, but {len(names)} names were given:\n{listing}")
        return chosen
    chosen = blobs[-len(names):]
    if len(chosen) < len(names):
        sys.exit(f"only {len(chosen)} captures found under {BLOB_ROOT}")
    age = time.time() - chosen[0][0] / 1000
    if age > 600:
        sys.exit(f"newest matching capture is {age:.0f}s old; capture again or pass --since")
    return chosen


def git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=qaimg.REPO, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "?"


def contact_sheet(set_dir: Path) -> Path | None:
    images = {p.stem: p for p in set_dir.glob("*.jpg") if qaimg.NAME_RE.match(p.stem)}
    if not images:
        return None
    tods = [t for t in qaimg.TODS if any(k.startswith(t + "_") for k in images)]
    shots = [n for n in qaimg.SHOTS if any(k.endswith(f"_{n}-{qaimg.SHOTS[n]}") for k in images)]
    tile_w, tile_h = 400, round(400 * qaimg.HEIGHT / qaimg.WIDTH)
    rows = []
    for tod in tods:
        row = []
        for n in shots:
            p = images.get(qaimg.shot_name(tod, n))
            row.append(Image.open(p) if p else None)
        rows.append(row)
    sheet = qaimg.grid(rows, tile_w, tile_h, row_labels=tods,
                       col_labels=[f"{n} {qaimg.SHOTS[n]}" for n in shots],
                       title=f"beauty set {set_dir.name}")
    out = set_dir / "contact.jpg"
    qaimg.save_jpg(sheet, out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, help="set id, e.g. p0-baseline or p1-env")
    ap.add_argument("--since", type=float, help="epoch seconds; take every capture after it, in order")
    ap.add_argument("--sheet", action="store_true", help="only rebuild the contact sheet")
    ap.add_argument("--any-name", action="store_true", help="allow names outside <tod>_<n>-<shot>")
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()

    set_dir = qaimg.BEAUTY / args.set
    if not args.sheet:
        if not args.names:
            sys.exit("give at least one name (e.g. sunset_4-flank)")
        for name in args.names:
            m = qaimg.NAME_RE.match(name)
            ok = m and m["tod"] in qaimg.TODS and qaimg.SHOTS.get(int(m["n"])) == m["shot"]
            if not ok and not args.any_name:
                sys.exit(f"bad name {name!r}: expected <tod>_<n>-<shot>, tod in {qaimg.TODS}, shots {qaimg.SHOTS}")
        manifest_path = set_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        head = git_head()
        for name, (stamp, blob) in zip(args.names, pick(args.names, args.since)):
            img, note = qaimg.fit(Image.open(blob), qaimg.WIDTH, qaimg.HEIGHT)
            out = set_dir / f"{name}.jpg"
            qaimg.save_jpg(img, out)
            manifest[name] = {
                "captured": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stamp / 1000)),
                "source_size": list(Image.open(blob).size),
                "normalised": note,
                "git_head": head,
            }
            flag = "" if note == "exact" else f"  [{note}]"
            print(f"{out.relative_to(qaimg.REPO)}{flag}")
        manifest_path.write_text(json.dumps(dict(sorted(manifest.items())), indent=1) + "\n")
    sheet = contact_sheet(set_dir)
    if sheet:
        print(f"contact sheet: {sheet.relative_to(qaimg.REPO)}")


if __name__ == "__main__":
    main()
