#!/usr/bin/env python3
"""Enemy readability probe on a capture (VFX-4, same measure as LOOK-5).

    tools/qa/py tools/vfx/qa/readability.py <capture.jpg> <boxes.json> [--out annotated.jpg] [--label TEXT]

<boxes.json> is the output of tools/vfx/qa/enemyboxes.client.luau for the
same frame (viewport pixel boxes). For each enemy on screen, in grayscale
(Rec. 709 luma): `dark` = the 10th-percentile luminance inside its box,
`bg` = the median of a ring around the box (the box grown by half its size,
at least 6 px, minus the box). Ratio = (bg + 5) / (dark + 5); the art-bible
rule is >= 3:1 at engagement range. Prints one line per enemy and the
min / mean, and writes an annotated grayscale copy.
"""
import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw


def luma(img):
    r, g, b = img.convert("RGB").split()
    return Image.merge("RGB", (r, g, b)).convert("L", (0.2126, 0.7152, 0.0722, 0))


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    k = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[k]


def probe(gray, box):
    w, h = gray.size
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    x0, y0 = max(0, x0), max(0, y0)
    x1, y1 = min(w - 1, x1), min(h - 1, y1)
    if x1 - x0 < 2 or y1 - y0 < 2:
        return None
    px = gray.load()
    inside = [px[x, y] for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]
    gx = max(6, (x1 - x0) // 2)
    gy = max(6, (y1 - y0) // 2)
    rx0, ry0 = max(0, x0 - gx), max(0, y0 - gy)
    rx1, ry1 = min(w - 1, x1 + gx), min(h - 1, y1 + gy)
    ring = [px[x, y] for x in range(rx0, rx1 + 1) for y in range(ry0, ry1 + 1)
            if not (x0 <= x <= x1 and y0 <= y <= y1)]
    dark = pct(inside, 0.10)
    bg = pct(ring, 0.5)
    if dark is None or bg is None:
        return None
    return dark, bg, (bg + 5) / (dark + 5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("boxes")
    ap.add_argument("--out")
    ap.add_argument("--label", default="")
    ap.add_argument("--kinds", default="", help="comma list of kinds to include (default all)")
    ap.add_argument("--max-dist", type=float, default=0, help="only enemies within this camera distance")
    a = ap.parse_args()
    img = Image.open(a.image)
    data = json.loads(Path(a.boxes).read_text())
    vw, vh = data["viewport"]
    sx, sy = img.size[0] / vw, img.size[1] / vh
    gray = luma(img)
    kinds = set(k for k in a.kinds.split(",") if k)
    rows = []
    for e in data["enemies"]:
        if not e.get("front"):
            continue
        if kinds and e["kind"] not in kinds:
            continue
        if a.max_dist and e["dist"] > a.max_dist:
            continue
        x0, y0, x1, y1 = e["box"]
        box = (x0 * sx, y0 * sy, x1 * sx, y1 * sy)
        if box[2] < 0 or box[3] < 0 or box[0] > img.size[0] or box[1] > img.size[1]:
            continue
        r = probe(gray, box)
        if r:
            rows.append((e["kind"], e["dist"], box, r))
    out = gray.convert("RGB")
    d = ImageDraw.Draw(out)
    for kind, dist, box, (dark, bg, ratio) in rows:
        col = (80, 220, 80) if ratio >= 3 else (240, 60, 60)
        d.rectangle(box, outline=col)
        d.text((box[0], box[3] + 2), f"{kind[:4]} {dist} {ratio:.2f}", fill=col)
    head = a.label or Path(a.image).stem
    if rows:
        ratios = [r[3][2] for r in rows]
        summary = f"{head}: {len(rows)} enemies, min {min(ratios):.2f}, mean {sum(ratios) / len(ratios):.2f} (storm {data.get('storm', 0)}, {data.get('preset')}, fov {data.get('fov', 0):.0f})"
    else:
        summary = f"{head}: no enemies on screen"
    d.text((8, 8), summary, fill=(255, 255, 0))
    for kind, dist, box, (dark, bg, ratio) in sorted(rows, key=lambda r: r[3][2]):
        print(f"  {kind:<12} {dist:>5} studs  dark {dark:>3}  bg {bg:>3}  ratio {ratio:5.2f}")
    print(summary)
    if a.out:
        out.save(a.out, quality=90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
