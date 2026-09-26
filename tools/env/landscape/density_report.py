"""Texel density actually baked on a piece, split by the title camera's close
range (Blender, reads assets/blender/Landscape_<Piece>.blend).

  Blender -b assets/blender/Landscape_Mesa.blend -P tools/env/landscape/density_report.py -- Mesa
"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pieces as P  # noqa: E402

name = sys.argv[sys.argv.index("--") + 1]
ctex = P.TEXTURE_SIZES.get(name, P.TEXTURE_SIZES_DEFAULT)[0]
rows = []
all_close, all_d, all_a = [], [], []
for ob in sorted((o for o in bpy.data.objects if o.name.startswith(f"{name}_C")), key=lambda o: o.name):
    me = ob.data
    uv = me.uv_layers.active.data
    cents, dens, areas = [], [], []
    for poly in me.polygons:
        pts = [uv[i].uv for i in poly.loop_indices]
        ua = 0.0
        for i in range(1, len(pts) - 1):
            a, b, c = pts[0], pts[i], pts[i + 1]
            ua += abs((b.x - a.x) * (c.y - a.y) - (c.x - a.x) * (b.y - a.y)) / 2
        area = poly.area
        if area < 1e-6:
            continue
        co = poly.center
        cents.append((co.x, co.z, -co.y))  # Blender -> Roblox
        dens.append(np.sqrt(ua * ctex * ctex / area))
        areas.append(area)
    cents, dens, areas = np.array(cents), np.array(dens), np.array(areas)
    close = P.close_view(cents, P.CLOSE_RANGE)
    all_close.append(close)
    all_d.append(dens)
    all_a.append(areas)
    def wmean(m):
        return float((dens[m] * areas[m]).sum() / areas[m].sum()) if m.any() else float("nan")
    rows.append(f"{ob.name}: close area {areas[close].sum():7.0f} density {wmean(close):5.1f} (min {dens[close].min() if close.any() else float('nan'):4.1f}) | other {wmean(~close):5.1f}")
close, dens, areas = np.concatenate(all_close), np.concatenate(all_d), np.concatenate(all_a)
print("\n".join(rows))
p10 = np.percentile(dens[close], 10) if close.any() else float("nan")
print(f"{name}: title-close surfaces {areas[close].sum():.0f} stud^2, area-weighted density {(dens[close]*areas[close]).sum()/areas[close].sum():.1f} px/stud, 10th pct {p10:.1f}, share >= 8: {areas[close & (dens >= 8)].sum()/areas[close].sum():.0%}")
