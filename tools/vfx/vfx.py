"""Flipbook pipeline entry point (runs inside headless Blender).

    Blender -b --factory-startup -P tools/vfx/vfx.py -- render   <Name>
    Blender -b --factory-startup -P tools/vfx/vfx.py -- assemble <Name>

`render` builds the sheet's scene and writes 64 premultiplied EXR frames to
tools/vfx/.cache/<Name>/ (hold a blender-lock slot; render.sh does that).
`assemble` turns cached (or painted) frames into assets/vfx/<Name>.png and
assets/vfx/previews/<Name>.png, and prints alpha stats. Use render.sh.
"""
import importlib
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

from sheets import registry  # noqa: E402

CACHE = os.path.join(HERE, ".cache")
OUT = os.path.join(ROOT, "assets", "vfx")
FRAMES = 64
CELL = 128
SUPER = 2


def _module(spec):
    return importlib.import_module(f"sheets.{spec['module']}")


def cmd_render(name):
    spec = registry.spec(name)
    if spec["method"] != "render":
        print(f"[vfx] {name} is {spec['method']}; nothing to render")
        return
    out_dir = os.path.join(CACHE, name)
    for f in os.listdir(out_dir) if os.path.isdir(out_dir) else []:
        if f.endswith(".exr"):
            os.remove(os.path.join(out_dir, f))
    secs = _module(spec).render(name, out_dir)
    print(f"[vfx] {name}: rendered {FRAMES} frames in {secs:.1f}s")


def _frames(spec):
    """Yields premultiplied linear RGBA frames at CELL * SUPER."""
    from vfxlib import image
    mod = _module(spec)
    size = CELL * SUPER
    if spec["method"] == "render":
        folder = os.path.join(CACHE, spec["name"])
        last = None
        for i in range(FRAMES):
            path = os.path.join(folder, f"f{i:03d}.exr")
            if os.path.exists(path):
                last = path
            yield image.load_rgba(last)  # gaps only in VFX_QUICK look-dev renders
    else:
        state = mod.prepare(spec["name"], size) if hasattr(mod, "prepare") else None
        for i in range(FRAMES):
            yield mod.paint(spec["name"], i, i / (FRAMES - 1), size, state)


def cmd_assemble(name):
    from vfxlib import image
    spec = registry.spec(name)
    start = time.time()
    tint = image.hex_rgb(spec["preview_tint"]) if spec.get("preview_tint") else None
    if spec["method"] == "single":
        rgba = _module(spec).single(name)
        path = os.path.join(OUT, f"{name}.png")
        image.save_png(path, rgba)
        _single_preview(image, rgba, name, tint, spec)
        print(f"[vfx] {name}: wrote {path} {rgba.shape[1]}x{rgba.shape[0]}")
        return
    fade = spec.get("fade")  # (t_start, t_end): sheet fades to clear over its tail
    cells = []
    for i, frame in enumerate(_frames(spec)):
        if fade:
            t = i / (FRAMES - 1)
            k = min(max((t - fade[0]) / (fade[1] - fade[0]), 0.0), 1.0)
            frame = frame * (1.0 - k * k * (3.0 - 2.0 * k))  # premultiplied: scale all channels
        cells.append(image.process_frame(frame, spec, CELL))
    atlas = image.assemble(cells)
    path = os.path.join(OUT, f"{name}.png")
    image.save_png(path, atlas)
    image.preview(atlas, cells, os.path.join(OUT, "previews", f"{name}.png"),
                  tint=tint, additive=spec.get("preview_add", 0.0))
    st = image.stats(cells)
    os.makedirs(os.path.join(CACHE, name), exist_ok=True)
    with open(os.path.join(CACHE, name, "stats.json"), "w") as fh:
        json.dump(st, fh, indent=1)
    print(f"[vfx] {name}: wrote {path} in {time.time() - start:.1f}s stats={json.dumps(st)}")


def _single_preview(image, rgba, name, tint, spec):
    import numpy as np
    h, w = rgba.shape[:2]
    panels = [image.over(rgba, image.checker(h, w)),
              image.over(rgba, image.sky(h, w), tint, spec.get("preview_add", 0.0)),
              image.over(rgba, image.solid(h, w, "#B9774A"), tint, spec.get("preview_add", 0.0))]
    img = np.concatenate(panels, axis=0 if w >= 2 * h else 1)
    out = np.concatenate([img, np.ones(img.shape[:2] + (1,), dtype=np.float32)], axis=2)
    image.save_png(os.path.join(OUT, "previews", f"{name}.png"), out)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(argv) != 2 or argv[0] not in ("render", "assemble"):
        print(__doc__)
        sys.exit(2)
    try:
        {"render": cmd_render, "assemble": cmd_assemble}[argv[0]](argv[1])
    except Exception as exc:  # report and fail the Blender process
        import traceback
        traceback.print_exc()
        print(f"[vfx] ERROR {argv[0]} {argv[1]}: {exc}")
        sys.exit(1)


main()
