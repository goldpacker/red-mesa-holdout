# VFX flipbook pipeline

Renders the particle flipbooks and single effect textures in `assets/vfx/`
(8x8 grids, 1024², clean straight alpha), uploads them as private Roblox
Images and lists them in `src/shared/Flipbooks.luau`. Owner: VFX workstream.

```
tools/vfx/sheets/<module>.py --render.sh--> tools/vfx/.cache/<Name>/f000..f063.exr   (Blender Cycles, blender-lock slot)
                             (or paint)       numpy frames, no Blender render, no lock
        --image.process_frame + assemble-->  assets/vfx/<Name>.png            (8x8 atlas or single)
                                             assets/vfx/previews/<Name>.png   (review contact sheet)
        --upload.py-->                       Open Cloud Image ids -> assets/vfx/roblox_ids.json
                                             -> generated IDS block in src/shared/Flipbooks.luau
```

## Commands

```sh
tools/vfx/render.sh all                    # every sheet and single (about 25 min)
tools/vfx/render.sh Fireball DustPuff      # named outputs
VFX_QUICK=9 tools/vfx/render.sh SmokeDark  # look-dev: renders every 9th frame only
NO_RENDER=1 tools/vfx/render.sh Fireball   # re-assemble cached frames (tone/alpha tweaks)

set -a; . ./.env.local; set +a             # Open Cloud credentials (never print)
python3 tools/vfx/upload.py                # upload changed PNGs, rewrite Luau ids
python3 tools/vfx/upload.py --ids-only     # rewrite the Luau id block only
```

`render.sh` takes a `tools/blender-lock.sh` slot (owner `vfx`, override with
`VFX_LOCK_OWNER`) only while a volumetric render runs and releases it right
after (also on error or Ctrl-C). Logs: `logs/vfx/<Name>.render.log` and
`logs/vfx/<Name>.log`. Everything is seeded, so a re-render reproduces the
same sheet (Mantaflow aside, which can differ slightly between runs).

## Outputs

| Name | How | Playback | Colour | Anchor |
|---|---|---|---|---|
| Fireball | Mantaflow fire+smoke sim (96³, noise upres 2) | OneShot | baked | centre |
| SmokeDark | procedural volume blobs | OneShot | greyscale, tint | centre |
| DustPuff | procedural volume blobs | OneShot | greyscale, tint | centre |
| SandKick | volume blobs + ballistic grain meshes | OneShot | greyscale, tint | ground at 88.5% down |
| MissileTrail | procedural volume blobs | OneShot | greyscale, tint | centre |
| MuzzleFlashFront | painted, 64 variants | random variant per particle | baked | centre |
| MuzzleFlashSide | painted, 64 variants | random variant per particle | baked | muzzle at 72.5% down |
| MuzzleFlashBurst | painted, 64 variants | random variant per particle | baked | centre |
| RocketExhaust | painted, seamless 64-frame loop | Loop | baked | nozzle at 85% down |
| Sparks | painted ballistic streaks | OneShot | baked | centre |
| TracerBeam | painted 512x128 Beam texture (U along beam, tiles) | - | white, tint | - |
| ShockwaveRing | painted 1024² top-down ring | - | white, tint | centre |
| ScorchMark | painted 1024² top-down decal | - | baked | centre |

Frames are row-major from the top-left cell (Roblox `Grid8x8` order).
Suggested emitter settings for each live in `src/shared/Flipbooks.luau`
(`Flipbooks.apply(emitter, name, scale)`).

## How a frame becomes a clean cell (`vfxlib/image.py`)

1. Frames are premultiplied scene-linear RGBA at 256² (2x supersampled).
2. Exposure, then a per-channel `1 - e^-x` tone map (hot cores go white,
   cooler fire stays orange-red).
3. Alpha is raised to at least the brightest channel, so emission is
   carried by alpha: fire covers the background (reads hot in daylight
   instead of washing out additively) and straight colour stays in 0..1.
4. Greyscale sheets store luminance only (the emitter's `Color` tints them).
5. 2x box downsample in premultiplied space (anti-aliasing).
6. Alpha fades to 0 over the outer 6 px of every 128 px cell: no frame ever
   shows a square edge ("black box") and mips never bleed between frames.
7. Unpremultiply, then push-pull fill: every pixel under 2/255 alpha takes
   the colour of the nearest visible region, so bilinear filtering and mip
   maps never pull black into edges (no dark fringes).
8. PNG: straight alpha, sRGB colour. `stats` in the assemble log checks the
   border alpha (must be 0) and unfilled black transparent pixels (must be 0).

Singles build straight RGBA directly with colour defined everywhere and
alpha reaching 0 before the image edge.

## Look-dev notes

- Volumetric sheets (`vfxlib/volume.py`): "blobs" are 2x2x2 cubes with a
  Principled Volume whose density is a domain-warped, fBm-billowed sphere.
  One material serves all blobs; each object passes density/time/heat in
  `Object.color`. Value nodes `Softness`, `Density`, `Interior` can be
  animated per frame (crisp billows early, soft wisps late).
- Lighting: warm key sun from the upper left front, cool rim, dim bluish
  ambient. Particles are billboards, so baked top light matches the sun
  being above in every time of day.
- Mantaflow (`vfxlib/fluid.py`): the bake happens inside the render job;
  the camera is fitted to the baked density bounds. Keep `res` <= 96 so the
  bake stays around 1-2 minutes.
- Painted sheets (`vfxlib/paint.py`): periodic 3D value-noise fBm on a
  16-cell lattice; offset polar coordinates off lattice planes (a
  coordinate sitting on a lattice plane shows as a crease).
- `preview_tint` / `preview_add` in `sheets/registry.py` only affect the
  review previews (what the emitter's Color / LightEmission would do).

## Adding a sheet

1. Add an entry to `sheets/registry.py` (module, method, exposure, grey...).
2. Write `render(name, out_dir)` (Blender scene; call
   `scene.render_frames(out_dir, setter)`) or `prepare(name, size)` +
   `paint(name, i, t, size, state)` (premultiplied numpy frame) or
   `single(name)` in the module.
3. `VFX_QUICK=9 tools/vfx/render.sh <Name>`, look at
   `assets/vfx/previews/<Name>.png`, iterate; then a full render.
4. `python3 tools/vfx/upload.py <Name>`, add its entry to `ENTRIES` in
   `src/shared/Flipbooks.luau`, test with a temporary emitter in Studio.
