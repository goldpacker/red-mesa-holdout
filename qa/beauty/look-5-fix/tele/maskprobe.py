"""Masked readability probe (LOOK-5 fix).
usage: maskprobe.py normal.jpg mask.jpg rects.txt [--viewport WxH] [--label L] [--crops outdir]
Body = pixels painted solid magenta in the mask capture (eroded 1 px), inside the
enemy's projected box. Ground = median luma of a ring around that body (dilated
body, excluding every masked pixel), from the normal capture. Luma = Rec.709 on
sRGB 0..255. ratio = (ground + 5) / (body + 5), for the body median ("main body")
and the body's darkest quartile (LOOK-1's probe), and the lighter-than-ground
case the other way round."""
import sys
import numpy as np
from PIL import Image, ImageFilter

args = sys.argv[1:]
def opt(name, default=None):
    if name in args:
        i = args.index(name); v = args[i + 1]; del args[i:i + 2]; return v
    return default
vp = tuple(int(x) for x in opt("--viewport", "1177x1068").split("x"))
label = opt("--label", "")
crops = opt("--crops")
normal_p, mask_p, rect_p = args
A = np.asarray(Image.open(normal_p).convert("RGB")).astype(float)
M = np.asarray(Image.open(mask_p).convert("RGB")).astype(float)
H, W, _ = A.shape
sx, sy = W / vp[0], H / vp[1]
luma = A @ [0.2126, 0.7152, 0.0722]
c = A / 255.0
lin = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
Y = lin @ [0.2126, 0.7152, 0.0722]  # WCAG relative luminance (tools/qa/palette.py)
R, G, B = M[..., 0], M[..., 1], M[..., 2]
mag = (R > 140) & (B > 130) & (G < 125) & ((R + B) / 2 - G > 70)
mag_img = Image.fromarray((mag * 255).astype(np.uint8))
body_all = np.asarray(mag_img.filter(ImageFilter.MinFilter(5))) > 0
any_near = np.asarray(mag_img.filter(ImageFilter.MaxFilter(9))) > 0
print(f"# {label} {normal_p.split('/')[-1]}  (mask px {mag.sum()})")
print(f"{'subject':<18}{'dist':>6}{'px':>7}{'body med':>9}{'body q1':>8}{'ground':>8}{'med:1':>7}{'q1:1':>7}{'WCAG':>7}")
rows = []
for line in open(rect_p):
    p = line.split()
    if len(p) < 6 or p[0].startswith("#"):
        continue
    name = p[0]; x0, y0, x1, y1, dist = map(float, p[1:6])
    xi0, yi0 = max(int(x0 * sx) - 2, 0), max(int(y0 * sy) - 2, 0)
    xi1, yi1 = min(int(np.ceil(x1 * sx)) + 2, W), min(int(np.ceil(y1 * sy)) + 2, H)
    if xi1 - xi0 < 2 or yi1 - yi0 < 2:
        continue
    sel = np.zeros_like(body_all)
    sel[yi0:yi1, xi0:xi1] = body_all[yi0:yi1, xi0:xi1]
    n = int(sel.sum())
    if n < 12:
        print(f"{name:<18}{dist:6.0f}{n:7d}  (too few mask px)")
        continue
    vals = np.sort(luma[sel])
    med = float(np.median(vals)); q1 = float(vals[: max(1, len(vals) // 4)].mean())
    hgt = (yi1 - yi0)
    r = min(24, max(6, int(0.35 * hgt)))
    # work in a window around the box (MaxFilter on the full frame is slow)
    wx0, wy0 = max(xi0 - r - 2, 0), max(yi0 - r - 2, 0)
    wx1, wy1 = min(xi1 + r + 2, W), min(yi1 + r + 2, H)
    win = sel[wy0:wy1, wx0:wx1]
    grown = np.asarray(Image.fromarray((win * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(2 * (r // 2) + 1)))
    grown = np.asarray(Image.fromarray(grown).filter(ImageFilter.MaxFilter(2 * (r - r // 2) + 1))) > 0
    outer = np.zeros_like(sel)
    outer[wy0:wy1, wx0:wx1] = grown
    ring = outer & ~any_near
    if ring.sum() < 20:
        print(f"{name:<18}{dist:6.0f}{n:7d}  (no ring)")
        continue
    bg = float(np.median(luma[ring]))
    rm = (bg + 5) / (med + 5) if bg >= med else (med + 5) / (bg + 5)
    rq = (bg + 5) / (q1 + 5)
    yb, yg = float(np.median(Y[sel])), float(np.median(Y[ring]))
    rw = (max(yb, yg) + 0.05) / (min(yb, yg) + 0.05)
    rows.append((name, dist, rm, rq, rw))
    print(f"{name:<18}{dist:6.0f}{n:7d}{med:9.1f}{q1:8.1f}{bg:8.1f}{rm:7.2f}{rq:7.2f}{rw:7.2f}" + ("" if bg >= med else "  (lighter than ground)"))
    if crops:
        import os
        os.makedirs(crops, exist_ok=True)
        pad = int(hgt * 0.6) + 6
        box = (max(xi0 - pad, 0), max(yi0 - pad, 0), min(xi1 + pad, W), min(yi1 + pad, H))
        c = Image.open(normal_p).convert("L").crop(box)
        scale = max(1, int(160 / max(c.size)))
        c.resize((c.size[0] * scale, c.size[1] * scale), Image.NEAREST).save(f"{crops}/{label}_{name}.png")
if rows:
    print(f"min main-body {min(r[2] for r in rows):.2f}   min darkest-quartile {min(r[3] for r in rows):.2f}   min WCAG main-body {min(r[4] for r in rows):.2f}")
