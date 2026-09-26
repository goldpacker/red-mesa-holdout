#!/usr/bin/env python3
"""Before/after sheets for the VFX-2 effect captures.

    tools/qa/py tools/vfx/qa/pairs.py [qa/beauty/vfx-2]

Pairs every image in <set>/before/ with the same name in <set>/after/,
writes <set>/pairs/<name>.jpg (labelled side by side) and <set>/contact.jpg
(all pairs, two per row, downscaled). Images only present in after/ are
listed on the contact sheet as "after only".
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

W = 595  # half of a 1190 capture


def label(img, text):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8 + 7 * len(text), 20), fill=(0, 0, 0))
    d.text((4, 4), text, fill=(255, 220, 120))
    return img


def fit(path, width):
    im = Image.open(path).convert("RGB")
    h = round(im.height * width / im.width)
    return im.resize((width, h), Image.LANCZOS)


def main(argv):
    root = Path(argv[0] if argv else "qa/beauty/vfx-2")
    before, after = root / "before", root / "after"
    out = root / "pairs"
    out.mkdir(exist_ok=True)
    names = sorted(p.name for p in after.glob("*.jpg"))
    tiles = []
    for name in names:
        a = fit(after / name, W)
        b = fit(before / name, W) if (before / name).exists() else None
        sheet = Image.new("RGB", (W * 2, a.height), (20, 20, 20))
        if b:
            sheet.paste(label(b, "before  " + name), (0, 0))
        else:
            label(sheet, "after only")
        sheet.paste(label(a, "after  " + name), (W, 0))
        sheet.save(out / name, quality=90)
        tiles.append(sheet)
        print(f"{name}: {'pair' if b else 'after only'}")
    if not tiles:
        return 1
    thumb_w = 800
    thumbs = [t.resize((thumb_w, round(t.height * thumb_w / t.width)), Image.LANCZOS) for t in tiles]
    cols = 2
    rows = (len(thumbs) + cols - 1) // cols
    th = max(t.height for t in thumbs)
    contact = Image.new("RGB", (thumb_w * cols, th * rows), (12, 12, 12))
    for i, t in enumerate(thumbs):
        contact.paste(t, ((i % cols) * thumb_w, (i // cols) * th))
    contact.save(root / "contact.jpg", quality=85)
    print(f"wrote {root / 'contact.jpg'} ({len(thumbs)} pairs)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
