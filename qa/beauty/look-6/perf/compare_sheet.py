"""LOOK-6 before/after sheets from qa/beauty/look-6/{before,after}.
    tools/qa/py qa/beauty/look-6/perf/compare_sheet.py
Writes qa/beauty/look-6/compare/<shot>.jpg (before | after, labelled) and
crops.jpg (3x nearest-neighbour crops of the top-left corner, the top-right
corner and a sky patch: film off | before | after)."""
from pathlib import Path
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[4] / "qa" / "beauty" / "look-6"
SHOTS = ["afternoon_2-turret", "sunset_2-turret", "sunset_glare-yaw62"]
OUT = ROOT / "compare"


def label(img: Image.Image, text: str) -> Image.Image:
    img = img.copy()
    d = ImageDraw.Draw(img)
    d.rectangle((0, img.height - 34, 12 + 9 * len(text), img.height), fill=(0, 0, 0))
    d.text((8, img.height - 28), text, fill=(255, 255, 255))
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for shot in SHOTS:
        a = Image.open(ROOT / "before" / f"{shot}.jpg").convert("RGB")
        b = Image.open(ROOT / "after" / f"{shot}.jpg").convert("RGB")
        sheet = Image.new("RGB", (a.width * 2 + 10, a.height), (30, 30, 30))
        sheet.paste(label(a, f"before (LOOK-5)  {shot}"), (0, 0))
        sheet.paste(label(b, f"after (LOOK-6)  {shot}"), (a.width + 10, 0))
        sheet.save(OUT / f"{shot}.jpg", quality=92)
    boxes = [("top-left corner", (0, 0, 160, 120)), ("top-right corner", (1030, 0, 1190, 120)), ("sky", (520, 160, 680, 280))]
    rows = []
    for shot in ("afternoon_2-turret", "sunset_2-turret"):
        imgs = [Image.open(ROOT / "before" / f"{shot}_filmoff.jpg").convert("RGB"),
                Image.open(ROOT / "before" / f"{shot}.jpg").convert("RGB"),
                Image.open(ROOT / "after" / f"{shot}.jpg").convert("RGB")]
        for name, box in boxes:
            row = [label(im.crop(box).resize((480, 360), Image.NEAREST), f"{shot} {name}: {tag}")
                   for im, tag in zip(imgs, ("film off", "before", "after"))]
            rows.append(row)
    sheet = Image.new("RGB", (3 * 490, len(rows) * 370), (30, 30, 30))
    for r, row in enumerate(rows):
        for c, im in enumerate(row):
            sheet.paste(im, (c * 490, r * 370))
    sheet.save(OUT / "crops.jpg", quality=92)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
