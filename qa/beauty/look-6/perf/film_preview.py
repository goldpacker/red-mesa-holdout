"""Offline preview of the film layer, LOOK-5 vs LOOK-6, composited in PIL
over a film-off capture (same maths as the GUI: straight-alpha 'over').
    tools/qa/py qa/beauty/look-6/perf/film_preview.py <filmoff.jpg> <out prefix> <vignette> <grain>
Writes <prefix>_old.png, <prefix>_new.png and a 3x crop sheet of the top-left
corner and the sky."""
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[4]
LOOK = ROOT / "assets" / "ui" / "look"


def scaled_alpha(img: Image.Image, k: float) -> Image.Image:
    r, g, b, a = img.split()
    a = a.point(lambda v: int(round(v * k)))
    return Image.merge("RGBA", (r, g, b, a))


def tiled(tile: Image.Image, size: tuple[int, int], tile_px: int) -> Image.Image:
    t = tile.resize((tile_px, tile_px), Image.BILINEAR) if tile_px != tile.width else tile
    out = Image.new("RGBA", size)
    for y in range(0, size[1], tile_px):
        for x in range(0, size[0], tile_px):
            out.paste(t, (x, y))
    return out


def corners(img: Image.Image, size: tuple[int, int], c: int, k: float, origin=(0, 0), box=None) -> Image.Image:
    """Four rotated corner pieces (rotation 0/90/180/270 clockwise, as the GUI)."""
    W, H = box or size
    ox, oy = origin
    piece = scaled_alpha(img.resize((c, c), Image.BILINEAR), k)
    out = Image.new("RGBA", size)
    # GUI Rotation is clockwise; PIL rotate is counter-clockwise.
    for (x, y), rot in (((0, 0), 0), ((W - c, 0), 90), ((W - c, H - c), 180), ((0, H - c), 270)):
        p = piece.rotate(-rot)
        out.alpha_composite(p, (ox + x, oy + y))
    return out


def old_layer(size, vig, grain):
    W, H = size
    out = Image.new("RGBA", size)
    out.alpha_composite(corners(Image.open(LOOK / "vignette_corner.png").convert("RGBA"), size, round(0.42 * H), vig))
    out.alpha_composite(scaled_alpha(tiled(Image.open(LOOK / "film_grain.png").convert("RGBA"), size, 128), grain))
    return out


def new_layer(size, vig, grain, corner_size=0.34, full=0.75, jitter=0):
    W, H = size
    Wc, Hc = W + 12, H + 12
    c = min(round(corner_size * Hc), Wc // 2)
    tile_px = round(128 * c / 256)
    box = Image.new("RGBA", (Wc, Hc))
    box.alpha_composite(corners(Image.open(LOOK / "film_corner.png").convert("RGBA"), (Wc, Hc), c, vig / full))
    band = scaled_alpha(tiled(Image.open(LOOK / "film_grain.png").convert("RGBA"), (Wc, Hc), tile_px), grain)
    for x, y, w, h in ((c, 0, Wc - 2 * c, Hc), (0, c, c, Hc - 2 * c), (Wc - c, c, c, Hc - 2 * c)):
        box.alpha_composite(band.crop((0, 0, w, h)), (x, y))
    return box.crop((jitter, jitter, jitter + W, jitter + H))


def main():
    src, prefix, vig, grain = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
    base = Image.open(src).convert("RGBA")
    size = base.size
    shots = {}
    for name, layer in (("old", old_layer(size, vig, grain)), ("new", new_layer(size, vig, grain))):
        img = base.copy()
        img.alpha_composite(layer)
        img.convert("RGB").save(f"{prefix}_{name}.png")
        shots[name] = img.convert("RGB")
    # 3x crops: top-left corner and a patch of sky, old | new
    crops = []
    for box in ((0, 0, 200, 150), (500, 180, 700, 330)):
        row = [shots[n].crop(box).resize((600, 450), Image.NEAREST) for n in ("old", "new")]
        crops.append(row)
    sheet = Image.new("RGB", (1210, 910), (40, 40, 40))
    for r, row in enumerate(crops):
        for c, im in enumerate(row):
            sheet.paste(im, (c * 610, r * 460))
    sheet.save(f"{prefix}_crops.png")
    print("wrote", prefix + "_{old,new,crops}.png")


if __name__ == "__main__":
    main()
