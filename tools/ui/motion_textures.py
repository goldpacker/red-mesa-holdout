"""Generates the Look workstream's motion textures (LOOK-3).

    tools/qa/py tools/ui/motion_textures.py         # writes assets/ui/motion/*.png (needs Pillow)

Tread strips that client/EnemyMotionTracks projects onto the tank and Siege
Crawler track meshes as Roblox `Texture`s and scrolls with the distance
driven (the track meshes themselves are static trim-sheet parts). Both are
cut from the `track` strip of HS's TrimEnemy trim sheet
(assets/exported/TrimEnemy/TrimEnemy_sheet_color.png, strip rows from
trim.json), so the moving links are the same links the mesh shows:
  TreadRoll.png  front/back faces: the strip turned upright (U across the
                 track, V along the tread; one tile = one strip period,
                 PERIOD studs), the tread rolling over the idler/sprocket.
  TreadSide.png  side faces: U along the hull (one tile = PERIOD studs), V
                 over the whole face height. Only the bottom band (the ground
                 run under the road wheels) carries the links (squeezed); the
                 rest is transparent so wheels and skirts show through (the
                 top run moves the other way and is under the skirts).
Deterministic: same trim sheet, same bytes.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
TRIM = ROOT / "assets" / "exported" / "TrimEnemy"
OUT = ROOT / "assets" / "ui" / "motion"

SIDE_W, SIDE_H = 512, 256
BAND_BOTTOM = 0.16  # share of the face height: the ground run of links
BAND_TOP = 0.0  # the top run moves the other way; it sits under the skirts, so leave it bare


def track_strip() -> tuple[Image.Image, float]:
    meta = json.loads((TRIM / "trim.json").read_text())
    strip = meta["strips"]["track"]
    sheet = Image.open(TRIM / meta["files"]["color"]).convert("RGB")
    size = sheet.width
    top = round((1 - strip["v1"]) * size)
    bottom = round((1 - strip["v0"]) * size)
    return sheet.crop((0, top, size, bottom)), float(strip["period"])


def roll(strip: Image.Image) -> Image.Image:
    upright = strip.rotate(90, expand=True)  # links now stack along V
    w = 128
    h = 1024
    return upright.resize((w, h), Image.LANCZOS).convert("RGBA")


def side(strip: Image.Image) -> Image.Image:
    out = Image.new("RGBA", (SIDE_W, SIDE_H), (0, 0, 0, 0))
    low = round(SIDE_H * BAND_BOTTOM)
    high = round(SIDE_H * BAND_TOP)
    band_low = strip.resize((SIDE_W, low), Image.LANCZOS).convert("RGBA")
    out.paste(band_low, (0, SIDE_H - low))
    if high > 0:
        out.paste(strip.resize((SIDE_W, high), Image.LANCZOS).convert("RGBA"), (0, 0))
    # Soft inner edges (2 px) so the band doesn't cut a hard line over the wheels.
    px = out.load()
    for x in range(SIDE_W):
        for k, a in ((0, 90), (1, 180)):
            r, g, b, _ = px[x, SIDE_H - low + k]
            px[x, SIDE_H - low + k] = (r, g, b, a)
            if high > 2:
                r, g, b, _ = px[x, high - 1 - k]
                px[x, high - 1 - k] = (r, g, b, a)
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    strip, period = track_strip()
    roll(strip).save(OUT / "TreadRoll.png", optimize=True)
    side(strip).save(OUT / "TreadSide.png", optimize=True)
    (OUT / "motion.json").write_text(json.dumps({"period": period, "band_bottom": BAND_BOTTOM, "band_top": BAND_TOP}, indent=1) + "\n")
    print(f"wrote TreadRoll.png, TreadSide.png (strip period {period:.3f} studs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
