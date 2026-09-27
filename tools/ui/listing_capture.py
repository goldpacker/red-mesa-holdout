"""Studio captures for the Roblox listing art (LOOK-7) at native resolution.

The Studio MCP's screen_capture returns ~1190 px wide images; a listing
thumbnail is 1920x1080. This grabs the viewport straight off the (Retina)
screen with macOS `screencapture`, so a 16:9 band of a large enough viewport
downsizes to 1920x1080 instead of being upscaled.

    tools/qa/py tools/ui/listing_capture.py viewport           # find the viewport (marker below)
    tools/qa/py tools/ui/listing_capture.py burst combat -n 30 # frames -> assets/listing/src/frames/combat/
    tools/qa/py tools/ui/listing_capture.py pick combat 17 --top 0.18   # 16:9 band -> src/combat_studio.png

`viewport` needs a full-viewport magenta marker on screen (Client datamodel):
    local g = Instance.new("ScreenGui"); g.Name = "ListingMarker"
    g.IgnoreGuiInset = true; g.DisplayOrder = 1e6
    local f = Instance.new("Frame", g); f.Size = UDim2.fromScale(1, 1)
    f.BackgroundColor3 = Color3.fromRGB(255, 0, 255); f.BorderSizePixel = 0
    g.Parent = game.Players.LocalPlayer.PlayerGui
(then destroy it). The rect (screen points) is kept in
src/frames/viewport.json. Studio must be visible (not covered) while
capturing. `--top` is where the band starts, as a fraction of the height
left over by the 16:9 band (0 = top, 0.5 = centred, 1 = bottom).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "assets" / "listing" / "src"
FRAMES = SRC / "frames"
RECT = FRAMES / "viewport.json"


def grab(path: Path, rect: tuple[int, int, int, int] | None = None) -> None:
    cmd = ["screencapture", "-x", "-t", "png"]
    if rect:
        cmd.append("-R{},{},{},{}".format(*rect))
    subprocess.run(cmd + [str(path)], check=True)


def screen_points_width() -> int:
    """The main display's width in points ("UI Looks like")."""
    info = subprocess.run(["system_profiler", "SPDisplaysDataType"], capture_output=True, text=True, check=True).stdout
    for line in info.splitlines():
        if "UI Looks like:" in line:
            return int(line.split(":")[1].split("x")[0])
    raise SystemExit("no display size from system_profiler")


def find_viewport() -> dict:
    FRAMES.mkdir(parents=True, exist_ok=True)
    (FRAMES / ".gitignore").write_text("*\n")
    shot = FRAMES / "screen.png"
    grab(shot)
    im = Image.open(shot).convert("RGB")
    r, g, b = im.split()
    # Magenta: red and blue high, green low.
    mask = Image.eval(r, lambda v: 255 if v > 235 else 0)
    mask = Image.composite(mask, Image.new("L", im.size), Image.eval(g, lambda v: 255 if v < 25 else 0))
    mask = Image.composite(mask, Image.new("L", im.size), Image.eval(b, lambda v: 255 if v > 235 else 0))
    box = mask.getbbox()
    if not box:
        raise SystemExit("no magenta marker on screen: show the ListingMarker ScreenGui and bring Studio forward")
    # Screen points (the capture is at the display's backing scale).
    scale = im.size[0] / screen_points_width()
    x0, y0, x1, y1 = box
    rect = {"x": round(x0 / scale), "y": round(y0 / scale), "w": round((x1 - x0) / scale), "h": round((y1 - y0) / scale), "scale": scale, "pixels": [x1 - x0, y1 - y0]}
    RECT.write_text(json.dumps(rect, indent=1) + "\n")
    print("viewport", rect)
    return rect


def burst(name: str, n: int, every: float) -> None:
    rect = json.loads(RECT.read_text())
    out = FRAMES / name
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    for i in range(n):
        grab(out / f"{i:03d}.png", (rect["x"], rect["y"], rect["w"], rect["h"]))
        wait = t0 + (i + 1) * every - time.time()
        if wait > 0:
            time.sleep(wait)
    size = Image.open(out / "000.png").size
    print(f"{n} frames of {name} at {size[0]}x{size[1]} in {time.time() - t0:.1f}s -> {out.relative_to(ROOT)}")


def pick(name: str, index: int, top: float, tag: str) -> None:
    im = Image.open(FRAMES / name / f"{index:03d}.png").convert("RGB")
    w, h = im.size
    bh = round(w * 9 / 16)
    if bh > h:
        raise SystemExit(f"viewport {w}x{h} is taller-than-16:9 only; crop width instead")
    y = round((h - bh) * top)
    band = im.crop((0, y, w, y + bh))
    if band.size[0] < 1920:
        raise SystemExit(f"band {band.size} is under 1920 wide: enlarge the viewport")
    dst = SRC / f"{tag or name}_studio.png"
    band.save(dst)
    print(f"wrote {dst.relative_to(ROOT)} {band.size[0]}x{band.size[1]} (frame {index}, rows {y}..{y + bh})")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("viewport")
    b = sub.add_parser("burst")
    b.add_argument("name")
    b.add_argument("-n", type=int, default=24)
    b.add_argument("--every", type=float, default=0.25)
    p = sub.add_parser("pick")
    p.add_argument("name")
    p.add_argument("index", type=int)
    p.add_argument("--top", type=float, default=0.5)
    p.add_argument("--tag", default="")
    a = ap.parse_args()
    if a.cmd == "viewport":
        find_viewport()
    elif a.cmd == "burst":
        burst(a.name, a.n, a.every)
    else:
        pick(a.name, a.index, a.top, a.tag)
    return 0


if __name__ == "__main__":
    sys.exit(main())
