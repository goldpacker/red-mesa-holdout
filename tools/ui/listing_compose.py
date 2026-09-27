"""Composes the Roblox listing art (LOOK-7) from the renders and captures in
assets/listing/src/ into assets/listing/: the 1920x1080 thumbnails, the
512x512 icon, the contact sheet and the list-size check sheet.

    tools/qa/py tools/ui/listing_compose.py

Sources (see assets/listing/README.md):
  - src/{hero,airdrop,icon}_render.png: Blender, tools/ui/listing_scene.py
  - src/icon_rm.png: the logo's stencil, tools/ui/listing_letters.py
  - src/{combat,boss}_studio.png: the real game in Studio (a 1899x1068
    viewport grabbed at the display's native 3798x2136 by
    tools/ui/listing_capture.py, area-downsampled to 1920x1080)
  - the logo: assets/ui/art/title_logo.png (tools/ui/title_logo.py)
Only the logo (and the icon's "RM") is laid over the images; there is no
other text. Pillow only (the QA venv).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "listing" / "src"
OUT = ROOT / "assets" / "listing"
LOGO = ROOT / "assets" / "ui" / "art" / "title_logo.png"
THUMB = (1920, 1080)
ICON = 512

# name, source, logo placement (left, top, width in thumbnail px) or None.
THUMBS = [
    ("thumb_1_hero", "hero_render.png", (56, 800, 800)),
    ("thumb_2_airdrop", "airdrop_render.png", (1500, 960, 380)),
    ("thumb_3_combat", "combat_studio.png", None),
    ("thumb_4_boss", "boss_studio.png", None),
]
# The icon: source render, and the "RM" stencil (left, top, width at 512) or None.
ICONS = [
    ("icon", "icon_render.png", (16, 264, 238)),
    ("icon_plain", "icon_render.png", None),
]


def resize(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Lanczos resize; RGBA through premultiplied alpha so edges stay clean."""
    if im.mode == "RGBA":
        return im.convert("RGBa").resize(size, Image.LANCZOS).convert("RGBA")
    return im.resize(size, Image.LANCZOS)


def fit(im: Image.Image, size: tuple[int, int]) -> Image.Image:
    """Centre-crops to the target aspect, then scales to size (downscale
    only: a smaller source is an error, never upscaled)."""
    w, h = im.size
    tw, th = size
    if w * th > h * tw:
        cw = round(h * tw / th)
        im = im.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h))
    elif w * th < h * tw:
        ch = round(w * th / tw)
        im = im.crop((0, (h - ch) // 2, w, (h - ch) // 2 + ch))
    if im.size[0] < tw:
        raise ValueError(f"source {im.size} smaller than {size}: re-render or re-capture, don't upscale")
    return im if im.size == size else resize(im, size)


def overlay(base: Image.Image, mark: Path, place: tuple[int, int, int]) -> Image.Image:
    left, top, width = place
    logo = Image.open(mark).convert("RGBA")
    logo = resize(logo, (width, round(logo.height * width / logo.width)))
    out = base.convert("RGBA")
    out.alpha_composite(logo, (left, top))
    return out.convert("RGB")


def compose_thumbs() -> list[tuple[str, Image.Image]]:
    done = []
    for name, src, logo in THUMBS:
        path = SRC / src
        if not path.exists():
            print(f"skip {name}: no {path.relative_to(ROOT)}")
            continue
        im = fit(Image.open(path).convert("RGB"), THUMB)
        if logo:
            im = overlay(im, LOGO, logo)
        im.save(OUT / f"{name}.png", optimize=True)
        done.append((name, im))
        print(f"wrote {name}.png {im.size[0]}x{im.size[1]}")
    return done


def compose_icons() -> list[tuple[str, Image.Image]]:
    done = []
    for name, src, rm in ICONS:
        path = SRC / src
        if not path.exists():
            print(f"skip {name}: no {path.relative_to(ROOT)}")
            continue
        im = fit(Image.open(path).convert("RGB"), (ICON, ICON))
        if rm:
            im = overlay(im, SRC / "icon_rm.png", rm)
        im.save(OUT / f"{name}.png", optimize=True)
        done.append((name, im))
        print(f"wrote {name}.png {im.size[0]}x{im.size[1]}")
    return done


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str) -> None:
    draw.text(xy, text, fill=(225, 225, 225))


def contact(thumbs: list[tuple[str, Image.Image]], icons: list[tuple[str, Image.Image]]) -> None:
    """Full size (thumbnails at 960 wide, icons at 512) and list size
    (thumbnails 400 wide, icons at 150 and 64), on the site's dark grey."""
    pad, bg = 24, (35, 37, 41)
    cols = 2
    tw, th = 960, 540
    rows = (len(thumbs) + cols - 1) // cols
    list_h = 225 + 150 + 3 * pad
    width = pad + cols * (tw + pad) + ICON + pad
    height = pad + rows * (th + pad + 18) + list_h + 40
    sheet = Image.new("RGB", (width, max(height, pad + len(icons) * (ICON + pad + 18) + list_h)), bg)
    draw = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(thumbs):
        x, y = pad + (i % cols) * (tw + pad), pad + (i // cols) * (th + pad + 18)
        label(draw, (x, y), f"{name}.png  1920x1080 (shown at 960)")
        sheet.paste(resize(im, (tw, th)), (x, y + 16))
    ix = pad + cols * (tw + pad)
    for j, (name, im) in enumerate(icons):
        y = pad + j * (ICON + pad + 18)
        label(draw, (ix, y), f"{name}.png  512x512")
        sheet.paste(im, (ix, y + 16))
    y0 = sheet.height - list_h
    label(draw, (pad, y0), "list size: thumbnails 400 wide, icons 150 and 64")
    x = pad
    for _name, im in thumbs:
        sheet.paste(resize(im, (400, 225)), (x, y0 + 20))
        x += 400 + pad // 2
    x = pad
    for _name, im in icons:
        sheet.paste(resize(im, (150, 150)), (x, y0 + 20 + 225 + pad))
        sheet.paste(resize(im, (64, 64)), (x + 150 + pad // 2, y0 + 20 + 225 + pad + 86))
        x += 150 + 64 + pad * 2
    sheet.save(OUT / "contact.jpg", quality=90)
    print(f"wrote contact.jpg {sheet.size[0]}x{sheet.size[1]}")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    thumbs = compose_thumbs()
    icons = compose_icons()
    contact(thumbs, icons)
    return 0


if __name__ == "__main__":
    sys.exit(main())
