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
tools/vfx/render.sh all                    # every sheet and single (~15-35 min, shared GPU)
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
| Flames | painted, seamless 64-frame loop (`sheets/fire.py`, VFX-2) | Loop | baked | base at 89% down |
| RockChips | painted chips + dust cloud (`sheets/fire.py`, VFX-2) | OneShot | greyscale, tint | centre |
| TracerBeam | painted 512x128 Beam texture (U along beam, tiles) | - | white, tint | - |
| ShockwaveRing | painted 1024² top-down ring | - | white, tint | centre |
| ScorchMark | painted 1024² top-down decal | - | baked | centre |

Frames are row-major from the top-left cell (Roblox `Grid8x8` order).
Suggested emitter settings for each live in `src/shared/Flipbooks.luau`
(`Flipbooks.apply(emitter, name, scale)`).

Verified in Studio (captures in `qa/beauty/vfx-1/`): OneShot sheets play
over the particle lifetime in grid order, alpha is clean over sky and sand,
and with `Orientation = VelocityParallel` Roblox lays the texture's X axis
along the velocity, so the side flash and exhaust (drawn pointing up) need
`Rotation = -90`.

Render times on the shared M4 Pro GPU (64 frames at 256², other agents'
jobs running): Fireball bake 110-130 s + render 100 s; DustPuff 330 s;
SandKick 505 s; SmokeDark 545 s (96 samples); MissileTrail 190 s. Painted
sheets and singles take 2-5 s each; `VFX_QUICK=9` look-dev renders take
10-40 s (plus the Fireball bake).

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

## In game (VFX-2)

The effect code uses these textures only (no built-in particle textures):

| Module | What |
|---|---|
| `src/client/Effects.luau` | shared helpers (`emitter`, pooled `rig`s, `anchor`, `flash`, `pulse`, `exposure`, `lod`, `groundBelow`, `surfaceOf`), pooled Beam tracers, our MG muzzle flash, bullet impacts by surface, enemy muzzle flashes / rifle shots / grenades |
| `src/client/VehicleFxParticles.luau` | layered explosion, debris meshes, scorch decals, lasting fires, trails, enemy projectiles/bombs, glints |
| `src/client/WeaponFxParticles.luau` | rocket/missile exhaust + smoke, backblast, ricochets |
| `src/client/WeaponFx.luau`, `EnemyFireFx.luau`, `VehicleFx.luau` | drive the above from game events |

Debris meshes (`Shard1-4`, `Chunk1-2`, `Clod1-2`, `Bomb`, `Rocket`) come
from the `VfxDebris` asset: `tools/assets/models/vfx_debris.py`, built and
published with the standard asset pipeline (`docs/ASSET_PIPELINE.md`) into
`assets/roblox/VfxDebris.rbxmx` (ReplicatedStorage.Assets.VfxDebris).

Brightness: emissive sprites, beams and flash lights scale by
`Effects.exposure()` = `2^(-0.85 * Lighting.ExposureCompensation)` so the
dusk/night exposure boost doesn't blow them out against the bloom.

### Capture harness (`tools/vfx/qa/`)

`fxharness.client.luau` / `fxharness.server.luau`: paste each into MCP
`execute_luau` (Client / Server) once per Play session. They install
`ReplicatedStorage.FxHarness` (aim, fire, weapon, freeze/unfreeze, probe)
and `ServerStorage.FxHarnessServer` (enemy fire through the real
`EnemyFire` GameEvent: `shell`, `bombs`, `heliRockets`, `volley`). Stage
with `RedMesaDebug:Invoke("beauty", {shot = 2, tod = ...})`, trigger, then
`H.freeze()` (particle `TimeScale` 0 + `FxFreeze`) to hold a phase for
`screen_capture`. Captures: `qa/beauty/vfx-2/`.

## Motion dust and particle LOD (VFX-3)

| Module | What |
|---|---|
| `src/client/VehicleFxDust.luau` | motion dust: buggy wheel dust (plume + sand-spurt rooster tail), tank and Siege Crawler track dust (rate from speed), helicopter rotor downwash (radial billows + flat ring, by height above ground), jet wake over the basin floor (by height); tinted by the terrain under each source (sand, road, wash, rock) |
| `src/client/EffectsLod.luau` | distance LOD shared by every effect module: `factor` (continuous rate/size multipliers with a cutoff), `count` (one-shot bursts, was `Effects.lod`), `track` (keeps fires, smoke columns and trails on their LOD) |

- **Sources** are the contract names in `docs/ASSET_CONTRACTS.md`: Buggy
  `WheelRL`/`WheelRR`, Tank and SiegeCrawler `TrackL`/`TrackR` (rear bottom
  of the part), Helicopter `MainRotor` (hub), Jet `Exhaust`. The emitters
  sit on world attachments that follow those children each frame; the model
  root is never moved, so rebuilt meshes (HS) and client root smoothing
  (Look's `EnemyMotion`) are picked up unchanged. Tuning: `SPECS` at the
  top of `VehicleFxDust.luau` (rate, reference speed, height window, cutoff,
  size).
- **LOD:** distances are zoom-corrected (FOV 32 in the gunsight). Inside
  250 studs full detail; out to each effect's cutoff the rate falls to 20 %
  while particles grow up to 2x (~1/sqrt(rate), so a cloud keeps its
  coverage); beyond the cutoff nothing new is emitted. Motion dust also has
  a global cap (`MAX_RATE` particles/s).
- **Studio switches** (Workspace attributes): `FxLodOff = true` disables
  LOD (perf A/B), `FxDustOff = true` stops motion dust (before/after
  captures). Published in Studio: `FxOneShotLive` (live one-shot particle
  estimate), `FxDustRate`, `FxDustSources`.
- **Harness:** `H.follow(model, offset, fov, look)` chase camera for moving
  vehicles; `H.particles()` / `H.sample(seconds)` live particle estimate
  (continuous emitters' Rate x mean lifetime + the one-shot estimate).
  Captures: `qa/beauty/vfx-3/`.
