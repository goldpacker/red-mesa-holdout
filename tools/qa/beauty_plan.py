"""Prints the exact capture steps for a beauty-shot set (full or subset).
See tools/qa/BEAUTY.md.

    python3 tools/qa/beauty_plan.py p1-env                       # all 30
    python3 tools/qa/beauty_plan.py p1-env --shots 2,4 --tods afternoon,sunset

Order: shot by shot, every preset for each, so the frozen subjects are
spawned only once per stage. The plan ends with the save command.
"""
from __future__ import annotations

import argparse
import time

# Daylight only since 3397923 (spec §7.1): no dusk or night presets.
TODS = {"afternoon": "Afternoon", "lateafternoon": "LateAfternoon", "sunset": "Sunset"}
SHOTS = {1: "title", 2: "turret", 3: "gunsight", 4: "flank", 5: "night", 6: "boss"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("set")
    ap.add_argument("--shots", default="1,2,3,4,5,6", help="comma list of shot numbers or names")
    ap.add_argument("--tods", default=",".join(TODS), help=f"comma list from {list(TODS)}")
    args = ap.parse_args()

    by_name = {v: k for k, v in SHOTS.items()}
    shots = [int(s) if s.isdigit() else by_name[s] for s in args.shots.split(",")]
    tods = [t.strip().lower() for t in args.tods.split(",")]
    for t in tods:
        if t not in TODS:
            raise SystemExit(f"unknown tod {t!r}; use {list(TODS)}")

    since = int(time.time())
    names = []
    print(f"Beauty set {args.set}: {len(shots) * len(tods)} captures (studio lock held, play running, setup done).")
    print(f"SINCE={since}   # captures after this time are filed in order\n")
    step = 0
    for n in sorted(shots):
        for t in tods:
            step += 1
            name = f"{t}_{n}-{SHOTS[n]}"
            names.append(name)
            print(f"{step:2d}. execute_luau Server: return game.ServerStorage.RedMesaDebug:Invoke(\"beauty\", {{ shot = {n}, tod = \"{TODS[t]}\" }})")
            print(f"    screen_capture (capture_id \"{name}\")")
    print("\nThen:")
    print(f"tools/qa/py tools/qa/beauty_save.py --set {args.set} --since {since} \\\n    " + " ".join(names))
    print("and finish with: execute_luau Server: return game.ServerStorage.RedMesaDebug:Invoke(\"beautyEnd\")")


if __name__ == "__main__":
    main()
