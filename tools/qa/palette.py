"""Renders the art-bible palette swatches to docs/art/palette.png.
The palette here is the source of truth for the hex table in
docs/ART_BIBLE.md; keep them in sync.

    tools/qa/py tools/qa/palette.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qaimg  # noqa: E402

PALETTE: list[tuple[str, list[tuple[str, str]]]] = [
    ("Environment", [
        ("cliff rust-red", "#9E4A2E"),
        ("cliff shadow strata", "#6E3322"),
        ("cliff light strata", "#BA6A44"),
        ("cap rock", "#5A3226"),
        ("ochre sand", "#C9824F"),
        ("packed road dirt", "#9A6B48"),
        ("bleached wash", "#D9B98C"),
        ("sage scrub", "#7D7F5A"),
        ("dead scrub", "#6B5A3E"),
    ]),
    ("Outpost (player)", [
        ("sun-bleached sand", "#CDB88F"),
        ("burlap sandbag", "#A8916B"),
        ("olive drab", "#4F5234"),
        ("worn OD paint", "#6B6B45"),
        ("bare steel", "#7A7B78"),
        ("concrete", "#8C877C"),
        ("brass", "#B08A3E"),
    ]),
    ("Enemy force", [
        ("gunmetal", "#3E4247"),
        ("charcoal", "#2A2C30"),
        ("near-black", "#1A1B1E"),
        ("marking red", "#BA1C18"),
        ("canopy glass", "#1C2834"),
    ]),
    ("Light and FX", [
        ("lamp warm", "#FFE2AA"),
        ("fire orange", "#FF8C3A"),
        ("our tracer amber", "#FFB224"),
        ("enemy tracer red", "#FF4A3A"),
        ("night ambient", "#68729E"),
        ("moonlight", "#A0B4E6"),
    ]),
    ("HUD", [
        ("amber", "#FFB224"),
        ("amber dim", "#AA741C"),
        ("olive", "#7A8446"),
        ("olive dark", "#3A4022"),
        ("panel", "#10120C"),
        ("text", "#F0E4C4"),
        ("alert red", "#E63426"),
        ("ok green", "#7ED250"),
    ]),
]

GROUNDS = ["#C9824F", "#9E4A2E", "#D9B98C", "#9A6B48"]
ENEMIES = ["#3E4247", "#2A2C30", "#BA1C18"]


def rgb(hex_: str) -> tuple[int, int, int]:
    return tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]


def luminance(hex_: str) -> float:
    def lin(c: int) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb(hex_))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main() -> None:
    sw, sh, gap, left = 150, 90, 12, 220
    cols = max(len(c) for _, c in PALETTE)
    rows = len(PALETTE) + 1
    width = left + cols * (sw + gap) + gap
    height = 70 + rows * (sh + 70)
    img = Image.new("RGB", (width, height), qaimg.BG)
    d = ImageDraw.Draw(img)
    d.text((gap, 18), "Red Mesa Holdout - art bible palette", font=qaimg.font(30), fill=qaimg.FG)
    small, tiny = qaimg.font(15), qaimg.font(13)
    y = 70
    for group, colors in PALETTE:
        d.text((gap, y + sh // 2 - 10), group, font=qaimg.font(20), fill=qaimg.FG)
        for i, (name, hex_) in enumerate(colors):
            x = left + i * (sw + gap)
            d.rectangle((x, y, x + sw, y + sh), fill=rgb(hex_))
            d.text((x, y + sh + 6), hex_, font=small, fill=qaimg.FG)
            d.text((x, y + sh + 26), name, font=tiny, fill=(170, 165, 155))
        y += sh + 70
    # Readability row: enemy colours on the main ground colours with their
    # luminance contrast ratio (the art-bible rule wants >= 3:1 for hulls).
    d.text((gap, y + sh // 2 - 20), "Readability\nenemy on ground", font=qaimg.font(18), fill=qaimg.FG)
    i = 0
    for g in GROUNDS:
        for e in ENEMIES[:2]:
            if i >= cols:
                break
            x = left + i * (sw + gap)
            d.rectangle((x, y, x + sw, y + sh), fill=rgb(g))
            d.rectangle((x + sw // 3, y + sh // 4, x + 2 * sw // 3, y + 3 * sh // 4), fill=rgb(e))
            d.text((x, y + sh + 6), f"{contrast(g, e):.1f}:1", font=small, fill=qaimg.FG)
            d.text((x, y + sh + 26), f"{e} on {g}", font=tiny, fill=(170, 165, 155))
            i += 1
    out = qaimg.REPO / "docs" / "art" / "palette.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"-> {out.relative_to(qaimg.REPO)}")
    for g in GROUNDS:
        print(g, " ".join(f"{e}:{contrast(g, e):.2f}" for e in ENEMIES))


if __name__ == "__main__":
    main()
