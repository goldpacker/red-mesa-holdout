#!/usr/bin/env python3
"""Every flipbook sheet and single texture the VFX pipeline produces.

Pure data (no bpy/numpy) so shell tools can query it:
    python3 tools/vfx/sheets/registry.py names            # all outputs
    python3 tools/vfx/sheets/registry.py method <Name>    # render | paint | single

Keys used by tools/vfx/vfxlib/image.py when assembling a sheet:
  module        sheet module in tools/vfx/sheets/ (render/paint functions)
  method        "render": Blender scene per frame (holds a blender-lock slot)
                "paint":  numpy frames, no Blender render, no lock
                "single": one texture, numpy, no lock
  exposure      multiplier before tone mapping
  tone          "exp" (1 - e^-x, hot cores go white) or "clamp"
  alpha_gain    multiplier on rendered alpha (thicken thin wisps)
  grey          store luminance only (colour comes from the emitter's Color)
  border        px of alpha fade at every cell edge (final 128 px cells)
  preview_tint  sRGB hex the preview multiplies in (what the emitter would do)
  preview_add   LightEmission share the preview uses (0 normal, 1 additive)
  fade          (t0, t1): scale the frames to clear between t0 and t1 of the sheet
"""
import sys

SHEETS = {
    # --- volumetric renders (Blender Cycles) ---
    "Fireball": dict(module="fireball", method="render", exposure=1.0, alpha_gain=1.3,
                     fade=(0.72, 1.0), preview_add=0.25),
    "SmokeDark": dict(module="smoke", method="render", exposure=2.3, alpha_gain=1.0,
                      grey=True, preview_tint="#3A3530"),
    "DustPuff": dict(module="dust", method="render", exposure=2.6, alpha_gain=1.0,
                     grey=True, preview_tint="#D9B98C"),
    "SandKick": dict(module="dust", method="render", exposure=2.4, alpha_gain=1.0,
                     grey=True, preview_tint="#C9A27A"),
    "MissileTrail": dict(module="smoke", method="render", exposure=2.4, alpha_gain=1.0,
                         grey=True, preview_tint="#E6E2DA"),
    # --- painted (numpy) sheets ---
    "MuzzleFlashFront": dict(module="flash", method="paint", exposure=1.0, preview_add=0.5),
    "MuzzleFlashSide": dict(module="flash", method="paint", exposure=1.0, preview_add=0.5),
    "MuzzleFlashBurst": dict(module="flash", method="paint", exposure=1.0, preview_add=0.5),
    "RocketExhaust": dict(module="flash", method="paint", exposure=1.0, preview_add=0.5),
    "Sparks": dict(module="sparks", method="paint", exposure=1.0, preview_add=0.5),
    # VFX-2 additions (sheets/fire.py)
    "Flames": dict(module="fire", method="paint", exposure=1.0, preview_add=0.5),
    "RockChips": dict(module="fire", method="paint", exposure=1.0, tone="clamp", grey=True,
                      preview_tint="#8A5A44"),
    # --- single textures (numpy) ---
    "TracerBeam": dict(module="singles", method="single", preview_tint="#FFB347", preview_add=1.0),
    "ShockwaveRing": dict(module="singles", method="single", preview_tint="#FFE2B8", preview_add=0.5),
    "ScorchMark": dict(module="singles", method="single"),
}


def spec(name):
    if name not in SHEETS:
        raise KeyError(f"unknown sheet {name!r}; known: {', '.join(SHEETS)}")
    return dict(SHEETS[name], name=name)


def main(argv):
    if argv and argv[0] == "names":
        print(" ".join(SHEETS))
        return 0
    if len(argv) == 2 and argv[0] == "method":
        print(spec(argv[1])["method"])
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
