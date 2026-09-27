"""Builds the LOOK-3 step-vs-smooth sheet from the strobe captures.

    tools/qa/py tools/ui/motion_sheet.py

Reads qa/beauty/look-3/motion/strobe_<kind>_{raw,smooth}.jpg (one marker per
rendered frame at the drawn Root, blue = oldest, yellow = newest; see the
LOOK-3 report) and writes qa/beauty/look-3/motion/strobe_pairs.jpg: per
vehicle, the raw and smoothed frames side by side, each with a 2x crop of
the markers and the measured per-frame numbers underneath.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "qa" / "beauty" / "look-3" / "motion"

# kind -> (raw crop box, smooth crop box, raw caption, smooth caption)
ROWS = [
    ("buggy", (430, 380, 1190, 490), (520, 390, 1190, 650),
     "RAW: 15 of 29 frames frozen (steps 0.00 / 1.29 studs)", "SMOOTH: 0 frozen (steps 0.37-0.73, decelerating)"),
    ("tank", (480, 270, 790, 360), (410, 255, 725, 315),
     "RAW: 17 of 35 frozen, per-frame speed cv 0.98", "SMOOTH: 0 frozen, per-frame speed cv 0.12"),
    ("helicopter", (660, 320, 1060, 410), (300, 325, 1010, 440),
     "RAW: 18 of 35 frozen, per-frame speed cv 1.07", "SMOOTH: 0 frozen, per-frame speed cv 0.06"),
    ("jet", (600, 450, 1190, 510), (580, 450, 1190, 510),
     "RAW: 15 of 29 frozen, per-frame speed cv 1.04", "SMOOTH: 0 frozen, per-frame speed cv 0.13"),
]
COL_W = 600
FULL_H = 540
CROP_H = 150
TEXT_H = 34


def font(size: int) -> ImageFont.ImageFont:
    for path in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def panel(path: Path, box: tuple[int, int, int, int], caption: str, label: str) -> Image.Image:
    img = Image.open(path).convert("RGB")
    out = Image.new("RGB", (COL_W, FULL_H + CROP_H + TEXT_H), (18, 18, 16))
    full = img.resize((COL_W, round(img.height * COL_W / img.width)), Image.LANCZOS)
    out.paste(full.crop((0, 0, COL_W, FULL_H)), (0, 0))
    crop = img.crop(box)
    scale = min(COL_W / crop.width, CROP_H / crop.height)
    crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    out.paste(crop, ((COL_W - crop.width) // 2, FULL_H + (CROP_H - crop.height) // 2))
    draw = ImageDraw.Draw(out)
    f = font(18)
    draw.rectangle((0, 0, 12 + draw.textlength(label, font=f), 26), fill=(0, 0, 0))
    draw.text((6, 4), label, font=f, fill=(255, 210, 60))
    draw.text((8, FULL_H + CROP_H + 7), caption, font=font(16), fill=(235, 228, 205))
    return out


def main() -> int:
    rows = []
    for kind, raw_box, smooth_box, raw_cap, smooth_cap in ROWS:
        a = panel(DIR / f"strobe_{kind}_raw.jpg", raw_box, raw_cap, f"{kind} RAW")
        b = panel(DIR / f"strobe_{kind}_smooth.jpg", smooth_box, smooth_cap, f"{kind} SMOOTH")
        row = Image.new("RGB", (COL_W * 2 + 8, a.height), (60, 60, 56))
        row.paste(a, (0, 0))
        row.paste(b, (COL_W + 8, 0))
        rows.append(row)
    sheet = Image.new("RGB", (rows[0].width, sum(r.height for r in rows) + 8 * (len(rows) - 1)), (60, 60, 56))
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 8
    sheet.save(DIR / "strobe_pairs.jpg", quality=88)
    print("wrote", (DIR / "strobe_pairs.jpg").relative_to(ROOT), sheet.size)
    return 0


if __name__ == "__main__":
    sys.exit(main())
