"""Grayscale thumbnails and a readability contact sheet (FACELIFT_PLAN §5:
every enemy type must stay identifiable at its engagement range).

    tools/qa/py tools/qa/grayscale.py qa/beauty/p1-env/*_2-turret.jpg --out qa/beauty/p1-env/gray
    tools/qa/py tools/qa/grayscale.py --set p1-env              # a whole set
    tools/qa/py tools/qa/grayscale.py --set p1-env --width 480  # smaller = harsher test

Writes <out>/<name>_gray.jpg for each image and <out>/readability.jpg: for
each image the colour thumbnail and its grayscale version side by side, at
the same small size, so value contrast (not hue) has to carry each enemy.
Also prints each image's luminance spread (p5..p95) as a rough number.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qaimg  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="*", type=Path)
    ap.add_argument("--set", help="use every <tod>_<n>-<shot>.jpg in qa/beauty/<set>")
    ap.add_argument("--out", type=Path, help="output folder (default: <set>/gray or next to the first image)")
    ap.add_argument("--width", type=int, default=640, help="thumbnail width in px")
    args = ap.parse_args()

    images = list(args.images)
    if args.set:
        set_dir = qaimg.BEAUTY / args.set
        images += sorted(p for p in set_dir.glob("*.jpg") if qaimg.NAME_RE.match(p.stem))
    if not images:
        sys.exit("no images given")
    out = args.out or ((qaimg.BEAUTY / args.set / "gray") if args.set else images[0].parent / "gray")
    out = out if out.is_absolute() else qaimg.REPO / out

    rows = []
    for path in images:
        color = qaimg.thumb(Image.open(path), args.width)
        gray = ImageOps.grayscale(color)
        hist = gray.histogram()
        total, acc, p5, p95 = sum(hist), 0, None, None
        for value, count in enumerate(hist):
            acc += count
            if p5 is None and acc >= total * 0.05:
                p5 = value
            if p95 is None and acc >= total * 0.95:
                p95 = value
        qaimg.save_jpg(gray, out / f"{path.stem}_gray.jpg")
        print(f"{path.stem:28s} luminance p5..p95 = {p5}..{p95} (spread {p95 - p5})")
        rows.append([qaimg.label(color, path.stem, 16), qaimg.label(gray.convert("RGB"), "gray", 16)])
    tile_h = rows[0][0].height
    sheet = qaimg.grid(rows, args.width, tile_h, title="readability: colour | grayscale")
    qaimg.save_jpg(sheet, out / "readability.jpg")
    print(f"-> {out.relative_to(qaimg.REPO) if out.is_relative_to(qaimg.REPO) else out}/readability.jpg")


if __name__ == "__main__":
    main()
