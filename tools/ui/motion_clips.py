#!/usr/bin/env python3
"""Turns a screen recording of a Studio playtest into LOOK-3 motion evidence.

    python3 tools/ui/motion_clips.py <recording.mov> <out_prefix> \
        [--crop x,y,w,h] [--fps 60] [--frames 12] [--start 0.5] [--scale 1]

Writes, next to <out_prefix>:
  <prefix>.mp4          the (cropped) clip, H.264, max --width px wide
  <prefix>.gif          the same, looping, 20 fps, max 360 px wide
  <prefix>_strip.jpg    --frames consecutive frames side by side (a frame
                        sequence: equal spacing = smooth, repeats/jumps = steps)

Recordings come from macOS `screencapture -v -V <s> -R x,y,w,h <file>.mov`
while Studio is in front. Needs ffmpeg on PATH. Deterministic for a given
recording.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def run(args: list[str]) -> None:
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("recording")
    ap.add_argument("prefix")
    ap.add_argument("--crop", default=None, help="x,y,w,h in recording pixels")
    ap.add_argument("--fps", type=int, default=60)
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--start", type=float, default=0.5, help="seconds into the clip for the strip")
    ap.add_argument("--scale", type=float, default=1.0, help="scale of the strip frames")
    ap.add_argument("--width", type=int, default=896, help="max width of the mp4")
    ap.add_argument("--vf", default="", help="extra ffmpeg filters after the crop (e.g. eq=gamma=1.5)")
    a = ap.parse_args(argv)

    src = Path(a.recording)
    prefix = Path(a.prefix)
    prefix.parent.mkdir(parents=True, exist_ok=True)
    vf = []
    if a.crop:
        x, y, w, h = (int(v) for v in a.crop.split(","))
        vf.append(f"crop={w}:{h}:{x}:{y}")
    if a.vf:
        vf.append(a.vf)
    base = ",".join(vf) if vf else "null"

    run(["ffmpeg", "-y", "-i", str(src), "-vf", f"{base},fps={a.fps},scale='min({a.width},iw)':-2:flags=lanczos",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "24", "-an", str(prefix.with_suffix(".mp4"))])
    run(["ffmpeg", "-y", "-i", str(prefix.with_suffix(".mp4")), "-vf",
         "fps=20,scale='min(360,iw)':-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer",
         str(prefix.with_suffix(".gif"))])
    with tempfile.TemporaryDirectory() as tmp:
        pattern = str(Path(tmp) / "f%03d.png")
        run(["ffmpeg", "-y", "-ss", f"{a.start}", "-i", str(prefix.with_suffix(".mp4")), "-frames:v", str(a.frames),
             "-vf", f"scale=iw*{a.scale}:-1", pattern])
        frames = sorted(Path(tmp).glob("f*.png"))
        if not frames:
            print("no frames extracted")
            return 1
        inputs: list[str] = []
        for f in frames:
            inputs += ["-i", str(f)]
        pads = "".join(f"[{i}:v]pad=iw+4:ih:0:0:white[p{i}];" for i in range(len(frames)))
        stack = "".join(f"[p{i}]" for i in range(len(frames))) + f"hstack=inputs={len(frames)}"
        run(["ffmpeg", "-y", *inputs, "-filter_complex", pads + stack, "-q:v", "3",
             str(prefix.parent / (prefix.name + "_strip.jpg"))])
    print("wrote", prefix.with_suffix(".mp4"), prefix.with_suffix(".gif"), prefix.parent / (prefix.name + "_strip.jpg"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
