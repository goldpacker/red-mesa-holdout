"""Before/after sheets for UI captures whose names aren't canonical beauty shots.

    tools/qa/py tools/ui/ui_compare.py <before-set> <after-set> [--crop x0,y0,x1,y1] [names...]

Pairs every image name present in both `qa/beauty/<before>/` and
`qa/beauty/<after>/` (or only the names given), writes one labelled
side-by-side per name into `qa/beauty/compare/<before>_vs_<after>/` and a
`contact.jpg` (one row per name, before | after). `--crop` also writes a
`<name>_crop.jpg` pair zoomed on a region (1190x1080 pixel coordinates),
for judging HUD detail at 1:1.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "qa"))
import qaimg  # noqa: E402


def pair(before: Image.Image, after: Image.Image, left: str, right: str) -> Image.Image:
    w, h = before.size
    out = Image.new("RGB", (w * 2 + 12, h), qaimg.BG)
    out.paste(qaimg.label(before.convert("RGB"), left), (0, 0))
    out.paste(qaimg.label(after.convert("RGB").resize((w, h)), right), (w + 12, 0))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("before")
    ap.add_argument("after")
    ap.add_argument("--crop", help="x0,y0,x1,y1 region for extra zoomed pairs")
    ap.add_argument("names", nargs="*")
    args = ap.parse_args()
    bdir, adir = qaimg.BEAUTY / args.before, qaimg.BEAUTY / args.after
    names = args.names or sorted(p.stem for p in adir.glob("*.jpg") if (bdir / p.name).exists() and p.stem != "contact")
    if not names:
        print("no common images")
        return 1
    out_dir = qaimg.BEAUTY / "compare" / f"{args.before}_vs_{args.after}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for name in names:
        b, a = Image.open(bdir / f"{name}.jpg"), Image.open(adir / f"{name}.jpg")
        qaimg.save_jpg(pair(b, a, f"{args.before}  {name}", f"{args.after}  {name}"), out_dir / f"{name}.jpg")
        if args.crop:
            box = tuple(int(v) for v in args.crop.split(","))
            scale = 2
            bc = b.crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale), Image.LANCZOS)
            ac = a.crop(box).resize(bc.size, Image.LANCZOS)
            qaimg.save_jpg(pair(bc, ac, args.before, args.after), out_dir / f"{name}_crop.jpg")
        rows.append([b, a])
        print(out_dir.relative_to(qaimg.REPO) / f"{name}.jpg")
    tile_w = 400
    tile_h = round(tile_w * qaimg.HEIGHT / qaimg.WIDTH)
    sheet = qaimg.grid(rows, tile_w, tile_h, row_labels=names, col_labels=[args.before, args.after],
                       title=f"{args.before} vs {args.after}")
    qaimg.save_jpg(sheet, out_dir / "contact.jpg")
    print(out_dir.relative_to(qaimg.REPO) / "contact.jpg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
