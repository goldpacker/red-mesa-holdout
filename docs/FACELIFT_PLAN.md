# Red Mesa Holdout — Face-lift Plan

Goal: move the game from "a Roblox game" to "a good-looking small shooter
that happens to run on Roblox", in line with GAME_SPEC §13 (grounded
semi-realistic, PBR, real proportions). This is a visual pass only;
gameplay, balance and code contracts stay as they are.

---

## 1. Diagnosis — why it still reads as Roblox

Judged against the current captures in `qa/screenshots/` (`final-*.jpg`,
`run2-*.jpg`, `terrain-v2-*.jpg`) and the model previews in
`assets/previews/`.

| # | What the player sees | Share of the frame | Root cause |
|---|---|---|---|
| 1 | Smooth, blobby terrain with stair-stepped edges on the road and washes; stock Roblox sand/sandstone textures | ~60–70% | Roblox voxel terrain (4-stud resolution), default materials, cliffs built from `FillBall` blobs |
| 2 | Flat, even light; flat blue gradient sky; little depth | ~25% (sky) + everything | Default skybox, no clouds, generic grading, no height fog layering |
| 3 | The gun and sandbags in the bottom third look clean and toy-like | ~15%, always on screen | Emplacement textures lack wear and variation; no micro-motion (belt, casings, heat) |
| 4 | Vehicles and the boss read as clean boxes in dark grey | small but the focus | Models are bevelled primitives with plain gunmetal; weak edge wear, no decals or roughness breakup |
| 5 | Soldiers read as blocky limb stacks | small, but everywhere | Rigid limb meshes on Motor6Ds; no deformation, cloth or silhouette detail |
| 6 | Explosions and smoke look generic | spikes during combat | Roblox built-in particle textures; ball-shaped fireballs from the early effects code |
| 7 | HUD is clean but flat | constant | Solid-colour panels, no texture, icons or motion design |
| 8 | Vehicles move in steps; nothing kicks up dust | motion | Server-driven anchored CFrames with no client smoothing; no wheel/rotor dust |

Items 1–3 are ~90% of the pixels. Fix those first.

---

## 2. Target look (art bible, one page)

- **Reference feel:** a sun-baked Southwest canyon. Layered red sandstone
  with horizontal strata and talus fans, pale dry washes, crusted sand with
  wind ripples, sparse grey-green scrub, heat haze. The military hardware is
  dusty, chipped and hand-maintained, not factory clean.
- **Palette (keep spec §13):** outpost sand/tan/olive drab; enemy charcoal
  gunmetal with red markings and the chevron emblem; environment rust-red
  cliffs (#9E4A2E), ochre sand (#C9824F), bleached washes (#D9B98C). Enemies
  must keep strong value contrast against the ground.
- **Surface rules:**
  - No `SmoothPlastic` on anything larger than a bolt.
  - Every visible surface has a custom PBR texture: `SurfaceAppearance` on meshes, `MaterialVariant` on terrain and parts.
  - Wear placement: dust gathers low, edges chip and polish, roughness varies across every surface.
- **Texel density:** heroes (emplacement, boss) ≥ 40 px/stud, vehicles
  ≥ 30 px/stud, landscape ≥ 8 px/stud at close range with a detail layer.
- **Light keys:** each time-of-day preset has one reference beauty shot
  and a written intent (e.g. "sunset: long raking shadows, warm key, cool
  bounce, rim light on silhouettes").

---

## 3. Roblox constraints this plan designs around

- **No custom shaders.** The look must come from meshes, PBR textures, MaterialVariants, lighting, post effects, Beams and particle flipbooks.
- **Texture resolution** is capped around 1024², so large objects need tiling textures, trim sheets or several material slots.
- **MeshPart triangle cap** is about 20k per mesh, so large pieces get split into chunks.
- **Terrain** is voxel-based (4 studs). Only `MaterialVariant`s can change its surface look; its shapes can't be finer than the voxels.
- **Decals** only project onto part faces. Markings on meshes must be baked into the texture.
- **Particles** support flipbook grids up to 8×8. `Beam` works for tracers, trails and light shafts.
- **Skinned meshes** with `Bone` objects are supported, and bones can be posed from code (`Bone.Transform`) with no animation upload needed.
- **Spec §17:** nothing paid, all assets original, all uploads private. See the decision on CC0 source textures in §7.

---

## 4. The plan

Phases are ordered by visual impact per unit of effort. Each phase ends
with before/after beauty shots (§5). Sizes: S ≈ a few hours, M ≈ a day,
L ≈ several days of agent time.

### Phase 0 — Baseline and tooling (S)
- Add six fixed **beauty-shot cameras** plus a capture script that takes all six
  at every time of day into `qa/beauty/<phase>/`:
  1. title
  2. turret view, day
  3. gunsight on the road
  4. sunset, flank view
  5. night
  6. boss approach
- Write the art bible above into `docs/ART_BIBLE.md` with the palette swatches
  and material list.
- Set a performance budget:
  - 60 fps on a mid-range PC at graphics level 8
  - under ~1M triangles on screen
  - under ~250 MB of texture memory
  
  Record the baseline numbers from the Studio stats panel.

### Phase 1 — Environment rebuild (L, biggest win)
**1a. Landscape meshes replace voxel hero terrain.**
- In Blender, sculpt the mesa, the flank canyon walls, the far wall and
  the four buttes as **real meshes**:
  - build from a heightfield or boolean blockout
  - add strata with layered displacement (horizontal bands)
  - add erosion, gullies and talus fans
  - decimate to game resolution and bake the high-poly normals onto the low-poly mesh
  - split into 10–20k-triangle chunks
- Texture them with a strata material:
  - world-space tiling rock
  - a height-banded colour ramp
  - baked ambient-occlusion and curvature masks, for dark crevices and bleached edges
- **Gameplay safety:**
  - keep the current terrain as the invisible-in-practice collision and height source, with the mesh surface 0.5–1 stud above it
  - or switch the ground raycasts to include the landscape meshes
  - re-run the line-of-sight check to every lane end (`TerrainBuilder` notes) and keep the terrace radii that protect the turret's view down the slope
- Place the unused **cliff kit** (`Cliff_Wall_A/B`, `Cliff_Corner`,
  `Cliff_Butte`) as dressing where the big meshes meet the floor.

**1b. Basin floor stays terrain, with custom MaterialVariants.**
- Author PBR sets (colour, normal, roughness), 1024², seamless:
  - `Sand`: wind ripples and pebbles
  - `Ground` (road): packed dirt with tyre ruts
  - `Salt` (washes): cracked dry mud
  - `Rock`
  - `Sandstone`
- Apply them through `MaterialService` with sensible `StudsPerTile`.
- Add a second, lower-frequency variation so the tiling doesn't repeat
  visibly across 1 km.

**1c. Hide voxel edges.**
- Road: a spline-built mesh strip in Blender with a soft alpha edge
  (feathered ruts, gravel shoulders) lying on the terrain; the voxel
  material edge sits under it.
- Washes: mesh bank strips (eroded lips, pebble beds) along both edges.

**1d. Ground dressing (instanced meshes, a few MeshIds reused).**
- Dry scrub (3–4 variants, alpha-card leaves), creosote clumps, dead
  branches, scattered pebbles, small rock clusters around boulders, tyre
  tracks and old craters as flat alpha meshes.
- Density falls off with distance from the turret, and lanes stay clear.

**1e. Sky.**
- Custom 6-face skybox per time of day (afternoon, sunset, dusk, night),
  rendered in Blender from a procedural sky: sun disc off, clouds,
  horizon haze, stars and a milky band at night.
- Roblox `Clouds` for drifting cover in the afternoon, sparse at sunset.

**Done when:**
- no voxel stair-step is visible from any beauty camera
- every cliff shows strata
- the floor shows ripples and variation
- the sky is no longer a flat gradient

### Phase 2 — Lighting and post (M)
- Re-key each time-of-day preset against the art bible:
  - sun angle for long raking shadows
  - `ShadowSoftness`
  - `EnvironmentDiffuse/SpecularScale` so the PBR metals read
  - a cooler ambient against a warm key
- Atmosphere layering: denser low haze in the basin, clearer upper air,
  horizon colour matched to each skybox.
- Colour grading per preset (`ColorCorrection`), with contrast and warm/cool
  split tuned against the beauty shots. Bloom thresholds per preset so
  only fire, flares and muzzle flashes bloom.
- Aim view: a subtle `DepthOfField` that keeps the far target sharp and
  softens the near sandbags. A vignette only in the gunsight.
- Heat haze: a subtle refractive-looking band using a scrolling-normal
  `Beam` or particle sheet over the hot basin, daytime only.
- Night: warm fire light versus cool moonlight; searchlight beams with a
  dusty cone texture instead of a flat beam.

**Done when** a still frame of each preset looks deliberate next to its
written intent.

### Phase 3 — The always-on-screen foreground: emplacement and turret (M)
The bottom third of every frame is the gun pit, so it deserves hero
treatment.
- **Re-texture pass:**
  - sandbag burlap weave with dust packed into the seams, sun-bleached tops and damp dark bottoms
  - chipped olive paint over bare steel on the gun edges and handles
  - brass ammunition belt
  - stencils ("7.62", unit number) baked into the textures
  - concrete with stains and cracks
- **Geometry:**
  - softer, lumpier sandbags (cloth-sim shapes baked into 3–4 variants and rotated)
  - a camo net draped over the rear
  - scattered brass casings
  - water cans
  - radio antenna with a sway
- **Motion (client):**
  - animated ammo belt feed
  - ejected casings (small mesh particles)
  - barrel heat glow tied to MG heat
  - rocket pod backblast dust
  - the camo net rippling in the wind
- **First-person gunsight polish:** proper sight meshes (iron sight, rocket
  scope housing, AA seeker unit) in front of the camera instead of pure
  GUI circles, with the UI overlay only for reticle marks.

### Phase 4 — Hard-surface upgrade for vehicles and the boss (L)
Apply a proper hard-surface workflow to the tank, buggy, helicopter, jet and
Siege Crawler.
- **Shape:**
  - break the box silhouettes with sloped and angled armour, spaced-armour panels, stowage (tarps, jerrycans, spare track links), tools, grilles, antennas, hand rails, periscopes and exhaust shrouds
  - model a high-poly version (bevels, weld seams, bolts) and bake it onto the game mesh
- **Texture:**
  - trim sheets for panels, rivets and grilles
  - curvature-driven edge wear
  - AO-driven grime
  - dust gradient up from the ground
  - roughness breakup
  - soot around exhausts and gun muzzles
  - red markings and the emblem as baked decals with chipping
- **Silhouette readability:** keep per-type identity (the tank's big turret,
  the buggy's roll cage, the helicopter's rotor and stub wings, the jet's
  delta, the crawler's scale) and check it in grayscale thumbnails at
  game distances.
- **Damage states:** a burnt `Wreck_*` texture swap (charred, rusted,
  paint blistered) instead of just darkening the colour; boss weak points
  get a torn-metal socket mesh when thrown off.

### Phase 5 — Infantry rebuild (M–L)
- Replace the limb-stack soldier with **one skinned mesh**. Build a proper
  body base (anatomical proportions), then add gear: plate carrier,
  pouches, helmet with cover, gloves, boots, sling, and a detailed original
  carbine. Bake cloth folds into the normal map.
- Rig with a simple skeleton (hips, spine, neck, head, arms, legs, rifle
  bone) and drive the bones from code with `Bone.Transform`, keeping the
  current state machine (walk, aim, throw, die). Add a smooth walk cycle,
  aim sway, a proper throw arc and a two-variant death fall.
- Add 2–3 texture and gear variants (radio operator, grenadier,
  rifleman) so groups don't look cloned.
- Readability at 500+ studs: slightly brighter rim/specular on the helmet
  and shoulders, and the red armband kept.

### Phase 6 — VFX (M)
- Render **custom flipbooks** in Blender (Mantaflow smoke/fire sims, 8×8
  grids, 1024²):
  - fireball
  - dark oily smoke
  - light dust puff
  - sand kick
  - muzzle flash (3 variants)
  - rocket exhaust
  - missile trail
  - sparks
- Explosions become layered:
  - flash
  - fireball flipbook
  - shockwave ring (a Beam or disc mesh)
  - debris chunks (small meshes on physics or tweened arcs)
  - lingering smoke column
  - ground scorch decal mesh
- **Impacts** by surface: sand spurt on terrain, rock chips on cliffs, sparks
  on metal.
- **Tracers:** textured `Beam`s with a hot core and soft falloff; enemy tracers
  red, ours amber.
- **Motion dust:** wheel dust on buggies, track dust on tanks, rotor
  downwash rings under low helicopters, the jet's wake over the basin
  floor.
- Keep the existing live-effect cap and add distance-based level of detail for
  particle rates.

### Phase 7 — UI and title (S–M)
- Textured 9-slice panels (worn olive metal with stencilled edges and a
  subtle scanline/noise overlay), and consistent corner brackets.
- Weapon icons rendered from the actual Blender models; animated heat
  and reload bars; a radar sweep line with fading blips.
- A title key-art render from Blender (the emplacement at sunset with the
  basin behind it) as the title backdrop, with a logo treatment
  (stencilled, worn metal).
- Motion design: banner slide-ins, the tally counting up, damage indicator
  easing. Keep everything glanceable (spec §12).

### Phase 8 — Motion polish (S–M)
- **Client-side interpolation** for enemy root CFrames (buffer about 100 ms
  and lerp) to remove stepping. Server authority is unchanged.
- Vehicle suspension bob and body roll on turns; tank track texture
  scrolling; helicopter body lean with velocity; jet banking.
- Camera: a slight weapon sway at idle, kick scaled by weapon, and a
  gentle look-lag on the turret model (already partial).

### Phase 9 — Performance and final QA (S)
- Profile the busiest waves (8–10, at night): triangles, draw calls,
  texture memory, particle counts. Add LODs (a simpler mesh beyond ~400
  studs for vehicles and dressing), `RenderFidelity` settings, and
  streaming-friendly dressing.
- Run the full QA loop again: full playthrough plus beauty-shot comparisons at every
  time of day.

---

## 5. How we'll know it worked

- **Beauty-shot comparison:** for each phase, six before/after pairs per time of day,
  side by side in `qa/beauty/`. Every phase must visibly improve its target
  shots with no regressions elsewhere.
- **"Roblox-tell" checklist.** None of these may be visible from any beauty camera:
  - voxel stair-steps
  - stock terrain textures
  - `SmoothPlastic`
  - the default sky
  - built-in particle textures
  - clean untextured boxes
  - robotic stepped motion
- **Readability check:** grayscale thumbnails of combat frames. Each enemy
  type must still be identifiable at its engagement range.
- **Performance:** holds the Phase 0 budget in waves 8–10.
- **Gameplay unchanged:** the full run still passes, and the line-of-sight check to every lane end
  still passes.

---

## 6. Team and ownership (same model as the main build)

| Workstream | Phases | Notes |
|---|---|---|
| Environment agent | 1, 2 (sky assets) | Blender landscape, MaterialVariants, dressing, skyboxes; owns `TerrainBuilder`/`WorldBuilder` changes jointly with the lead |
| Hard-surface agent | 3, 4 | Emplacement, vehicles, boss, wrecks; extends `tools/assets` (trim sheets, high-to-low bake) |
| Character agent | 5 | Skinned infantry and the bone-driven animation in `EnemyVisuals` |
| VFX agent | 6 | Flipbooks, `Effects`/`WeaponFx`/`VehicleFx` upgrades |
| Lead | 0, 2, 7, 8, 9 | Lighting and post, UI, interpolation, QA, integration |

Blender is a single instance, so the Blender-heavy agents take turns (a
Blender lock like the Studio lock). Studio sessions stay behind
`tools/studio-lock.sh`.

---

## 7. Decisions needed from you

1. **CC0 source textures.** May we use Poly Haven (CC0) textures and HDRIs as
   *raw material*, heavily modified and baked into our own assets? The
   spec currently says all assets must be original. Allowing CC0 inputs
   saves a lot of time and raises quality. Otherwise everything stays
   procedural or hand-authored in Blender.
2. **Landscape meshes versus terrain.** The recommendation is meshes for the cliffs, mesa and
   buttes, and terrain with MaterialVariants for the floor. Going all-mesh
   looks best but costs more memory and work on raycasts and collision.
3. **Scope.** Do all phases, or stop after Phases 0–3 (environment,
   lighting, foreground), which cover about 90% of the frame, and judge from
   there.

---

## 8. Risks

- **Texture memory and draw calls** grow with every new material. Mitigate with shared
  trim sheets, reused dressing MeshIds and LODs, and measure after each phase.
- **Mesh landscape and gameplay.** Enemies snap to terrain height, and the turret's
  line of sight depends on the mesa shape. Keep terrain as the gameplay
  surface under the meshes, and re-run the line-of-sight checks.
- **Upload pipeline.** Each rebuilt mesh needs a re-upload and a harvest of the new
  asset ids (see `docs/ASSET_PIPELINE.md`). Batch the uploads, and keep
  the Open Cloud key valid; rotate it as noted in `DONE.md`.
- **Readability.** More detail can make threats harder to spot. The grayscale
  thumbnail check (§5) gates every phase.
