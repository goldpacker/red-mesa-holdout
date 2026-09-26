"""Contact sheet of preview PNGs (run inside Blender for its image IO).

    Blender -b --factory-startup -P tools/assets/montage.py -- out.png a.png b.png ...
"""
import sys

import bpy
import numpy as np

args = sys.argv[sys.argv.index("--") + 1:]
out, files = args[0], args[1:]
cols = 3 if len(files) > 4 else 2
tile_w, tile_h = 512, 384
rows = (len(files) + cols - 1) // cols
sheet = np.zeros((rows * tile_h, cols * tile_w, 4), dtype=np.float32)
sheet[..., 3] = 1
for i, f in enumerate(files):
    img = bpy.data.images.load(f)
    img.scale(tile_w, tile_h)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(tile_h, tile_w, 4)
    r, c = rows - 1 - i // cols, i % cols
    sheet[r * tile_h:(r + 1) * tile_h, c * tile_w:(c + 1) * tile_w] = px
res = bpy.data.images.new("sheet", cols * tile_w, rows * tile_h)
res.pixels.foreach_set(sheet.ravel())
res.filepath_raw = out
res.file_format = "PNG"
res.save()
