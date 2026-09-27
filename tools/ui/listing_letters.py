"""The "RM" stencil for the listing icon (LOOK-7): the title logo's own
letterforms and worn-metal treatment (tools/ui/title_logo.py), amber like
RED MESA, drawn at icon size.

    tools/ui/py.sh tools/ui/listing_letters.py    # writes assets/listing/src/icon_rm.png

Deterministic (pure numpy on Blender's bundled Python).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from look_textures import write_png  # noqa: E402
from title_logo import TRACK, build, line_width  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "listing" / "src"
TITLE_CAP = 112  # RED MESA's cap height on the 1024x256 title logo
CAP = 220  # cap height of the icon lettering (px, drawn for a 1024 icon master)
PAD = 22  # room for the outline and drop shadow


def main() -> int:
    width = math.ceil(line_width("RM", TRACK) * CAP) + 2 * PAD
    height = CAP + 2 * PAD
    lines = [("RM", "amber", PAD, PAD + CAP, CAP, TRACK)]
    rgba = build(lines, (width, height), k=CAP / TITLE_CAP)
    OUT.mkdir(parents=True, exist_ok=True)
    write_png(OUT / "icon_rm.png", rgba)
    print("wrote", OUT / "icon_rm.png", f"{width}x{height}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
