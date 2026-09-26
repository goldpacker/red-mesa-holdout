"""Shared image helpers for the QA tools (Pillow; run via tools/qa/py)."""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[2]
BEAUTY = REPO / "qa" / "beauty"

# Canonical beauty-shot resolution (the Studio viewport the baseline was
# captured at). Every saved capture is normalised to this size.
WIDTH, HEIGHT = 1190, 1080
JPEG_QUALITY = 90

TODS = ["afternoon", "lateafternoon", "sunset", "dusk", "night"]
SHOTS = {1: "title", 2: "turret", 3: "gunsight", 4: "flank", 5: "night", 6: "boss"}
NAME_RE = re.compile(r"^(?P<tod>[a-z]+)_(?P<n>\d)-(?P<shot>[a-z]+)$")

BG = (18, 18, 20)
FG = (235, 230, 220)


def shot_name(tod: str, n: int) -> str:
    return f"{tod}_{n}-{SHOTS[n]}"


def all_names() -> list[str]:
    return [shot_name(t, n) for t in TODS for n in SHOTS]


def font(size: int) -> ImageFont.ImageFont:
    for path in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                 "/System/Library/Fonts/Helvetica.ttc",
                 "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def label(img: Image.Image, text: str, size: int = 22) -> Image.Image:
    """Returns a copy with `text` on a dark strip in the top-left corner."""
    out = img.copy()
    draw = ImageDraw.Draw(out)
    f = font(size)
    box = draw.textbbox((0, 0), text, font=f)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.rectangle((0, 0, w + 16, h + 14), fill=BG)
    draw.text((8, 5), text, font=f, fill=FG)
    return out


def fit(img: Image.Image, width: int, height: int) -> tuple[Image.Image, str]:
    """Normalises a capture to width x height. Same aspect: resize.
    Different aspect: centre-crop to the aspect first (reported)."""
    img = img.convert("RGB")
    if img.size == (width, height):
        return img, "exact"
    src_aspect = img.width / img.height
    dst_aspect = width / height
    note = "resized"
    if abs(src_aspect - dst_aspect) / dst_aspect > 0.02:
        if src_aspect > dst_aspect:
            w = round(img.height * dst_aspect)
            x = (img.width - w) // 2
            img = img.crop((x, 0, x + w, img.height))
        else:
            h = round(img.width / dst_aspect)
            y = (img.height - h) // 2
            img = img.crop((0, y, img.width, y + h))
        note = f"cropped from {src_aspect:.3f} aspect"
    return img.resize((width, height), Image.LANCZOS), note


def thumb(img: Image.Image, width: int) -> Image.Image:
    h = round(img.height * width / img.width)
    return img.convert("RGB").resize((width, h), Image.LANCZOS)


def grid(tiles: list[list[Image.Image | None]], tile_w: int, tile_h: int,
         row_labels: list[str] | None = None, col_labels: list[str] | None = None,
         title: str | None = None, gap: int = 6) -> Image.Image:
    """Lays out rows of equally sized tiles with optional row/column labels."""
    rows, cols = len(tiles), max(len(r) for r in tiles)
    left = 170 if row_labels else 0
    top = (44 if title else 0) + (34 if col_labels else 0)
    sheet = Image.new("RGB", (left + cols * (tile_w + gap) + gap, top + rows * (tile_h + gap) + gap), BG)
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((gap + 4, 8), title, font=font(26), fill=FG)
    if col_labels:
        for c, text in enumerate(col_labels):
            draw.text((left + gap + c * (tile_w + gap) + 4, top - 30), text, font=font(20), fill=FG)
    for r, row in enumerate(tiles):
        y = top + gap + r * (tile_h + gap)
        if row_labels:
            draw.text((10, y + tile_h // 2 - 12), row_labels[r], font=font(20), fill=FG)
        for c, tile in enumerate(row):
            x = left + gap + c * (tile_w + gap)
            if tile is None:
                draw.rectangle((x, y, x + tile_w, y + tile_h), outline=(80, 80, 80))
                draw.text((x + 10, y + 10), "missing", font=font(18), fill=(160, 90, 90))
            else:
                sheet.paste(tile.resize((tile_w, tile_h), Image.LANCZOS), (x, y))
    return sheet


def save_jpg(img: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=JPEG_QUALITY, optimize=True)
