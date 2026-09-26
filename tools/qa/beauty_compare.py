"""Before/after comparison of two beauty-shot sets. See tools/qa/BEAUTY.md.

    tools/qa/py tools/qa/beauty_compare.py p0-baseline p1-env
    tools/qa/py tools/qa/beauty_compare.py p0-baseline p1-env --gray

Writes into qa/beauty/compare/<before>_vs_<after>/:
  <tod>_<n>-<shot>.jpg   before | after side by side, for every image in both
  contact.jpg            all pairs: rows = time of day, columns = shots
                         (each cell: before on top, after below)
With --gray the pairs and sheet are grayscale (readability check).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qaimg  # noqa: E402


def load(path: Path, gray: bool) -> Image.Image:
    img = Image.open(path).convert("RGB")
    return ImageOps.grayscale(img).convert("RGB") if gray else img


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--gray", action="store_true", help="grayscale pairs (readability)")
    ap.add_argument("--width", type=int, default=960, help="width of each half of a pair (px)")
    args = ap.parse_args()

    before_dir, after_dir = qaimg.BEAUTY / args.before, qaimg.BEAUTY / args.after
    for d in (before_dir, after_dir):
        if not d.is_dir():
            sys.exit(f"no such set: {d}")
    suffix = "_gray" if args.gray else ""
    out_dir = qaimg.BEAUTY / "compare" / f"{args.before}_vs_{args.after}{suffix}"
    names = sorted(p.stem for p in after_dir.glob("*.jpg")
                   if qaimg.NAME_RE.match(p.stem) and (before_dir / p.name).exists())
    if not names:
        sys.exit("the sets share no <tod>_<n>-<shot>.jpg images")

    pairs: dict[str, Image.Image] = {}
    for name in names:
        a = qaimg.thumb(load(before_dir / f"{name}.jpg", args.gray), args.width)
        b = qaimg.thumb(load(after_dir / f"{name}.jpg", args.gray), args.width)
        pair = Image.new("RGB", (a.width + b.width + 8, max(a.height, b.height)), qaimg.BG)
        pair.paste(qaimg.label(a, f"BEFORE {args.before}  {name}"), (0, 0))
        pair.paste(qaimg.label(b, f"AFTER {args.after}  {name}"), (a.width + 8, 0))
        qaimg.save_jpg(pair, out_dir / f"{name}.jpg")
        pairs[name] = pair

    # Contact sheet: before stacked over after in each cell.
    tods = [t for t in qaimg.TODS if any(n.startswith(t + "_") for n in names)]
    shots = [n for n in qaimg.SHOTS if any(x.endswith(f"_{n}-{qaimg.SHOTS[n]}") for x in names)]
    cell_w = 360
    half_h = round(cell_w * qaimg.HEIGHT / qaimg.WIDTH)
    rows = []
    for tod in tods:
        row = []
        for n in shots:
            name = qaimg.shot_name(tod, n)
            if name not in pairs:
                row.append(None)
                continue
            a = qaimg.thumb(load(before_dir / f"{name}.jpg", args.gray), cell_w)
            b = qaimg.thumb(load(after_dir / f"{name}.jpg", args.gray), cell_w)
            cell = Image.new("RGB", (cell_w, half_h * 2 + 4), qaimg.BG)
            cell.paste(a.resize((cell_w, half_h)), (0, 0))
            cell.paste(b.resize((cell_w, half_h)), (0, half_h + 4))
            row.append(cell)
        rows.append(row)
    sheet = qaimg.grid(rows, cell_w, half_h * 2 + 4, row_labels=tods,
                       col_labels=[f"{n} {qaimg.SHOTS[n]}" for n in shots],
                       title=f"{args.before} (top) vs {args.after} (bottom){' - grayscale' if args.gray else ''}")
    qaimg.save_jpg(sheet, out_dir / "contact.jpg")
    print(f"{len(names)} pairs -> {out_dir.relative_to(qaimg.REPO)}/ (contact.jpg)")


if __name__ == "__main__":
    main()
