#!/usr/bin/env python3
"""Re-runs every LOOK-5 fix-1 readability probe from the files in this folder.
   python3 run_probes.py  (needs numpy + Pillow)  -> probe_results.txt"""
import pathlib, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
RUNS = [
    ("afternoon_ground_before-d030.jpg", "ground_mask.jpg", "rects_r_ground.txt", "afternoon-before-d030"),
    ("afternoon_ground_candidate-d0285.jpg", "ground_mask.jpg", "rects_r_ground.txt", "afternoon-candidate-d0285"),
    ("afternoon_ground_after-d027.jpg", "ground_mask.jpg", "rects_r_ground2.txt", "afternoon-after-d027"),
    ("afternoon_heli_before-d030.jpg", "afternoon_heli_mask.jpg", "rects_r_heli2.txt", "afternoon-heli-before-d030"),
    ("afternoon_heli_after-d027.jpg", "afternoon_heli_mask.jpg", "rects_r_heli2.txt", "afternoon-heli-after-d027"),
    ("afternoon_boss_before-d030.jpg", "boss_mask.jpg", "rects_r_boss.txt", "afternoon-boss-before-d030"),
    ("afternoon_boss_after-d027.jpg", "boss_mask.jpg", "rects_r_boss.txt", "afternoon-boss-after-d027"),
    ("lateafternoon_ground_pre-look5-emulated.jpg", "ground_mask.jpg", "rects_r_ground2.txt", "late-pre-LOOK-5-emulated"),
    ("lateafternoon_ground_before-d028.jpg", "ground_mask.jpg", "rects_r_ground2.txt", "late-before-d028"),
    ("lateafternoon_ground_after-d024.jpg", "ground_mask.jpg", "rects_r_ground3.txt", "late-after-d024"),
    ("lateafternoon_heli_before-d028.jpg", "lateafternoon_heli_before_mask.jpg", "rects_r_heli_late.txt", "late-heli-before-d028"),
    ("lateafternoon_heli_after-d024.jpg", "lateafternoon_heli_after_mask.jpg", "rects_r_heli_late2.txt", "late-heli-after-d024"),
    ("lateafternoon_boss_after-d024.jpg", "boss_mask.jpg", "rects_r_boss2.txt", "late-boss-after-d024"),
    ("sunset_ground.jpg", "ground_mask.jpg", "rects_r_ground2.txt", "sunset-unchanged"),
    ("sunset_heli.jpg", "sunset_heli_mask.jpg", "rects_r_heli_sunset.txt", "sunset-heli-unchanged"),
    ("sunset_boss.jpg", "boss_mask.jpg", "rects_r_boss2.txt", "sunset-boss-unchanged"),
]
out = ["# LOOK-5 fix 1: masked telephoto readability probe (maskprobe.py); camera at the turret-shot",
       "# position, zoomed onto the group; med:1 = body median, q1:1 = body darkest quartile (LOOK-1's",
       "# probe), both sRGB luma (bg+5)/(x+5); WCAG = relative-luminance ratio of the medians (palette.py)"]
for img, mask, rects, label in RUNS:
    r = subprocess.run([sys.executable, str(HERE / "maskprobe.py"), str(HERE / img), str(HERE / mask), str(HERE / rects), "--label", label],
                       capture_output=True, text=True)
    out += ["", (r.stdout + r.stderr).strip()]
(HERE / "probe_results.txt").write_text("\n".join(out) + "\n")
print("\n".join(out))
