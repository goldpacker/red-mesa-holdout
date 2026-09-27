# Asset pipeline (Blender → Roblox)

Owner: Assets agent (face-lift: Hard-surface workstream). Contracts: `docs/ASSET_CONTRACTS.md`. Status of each
asset (ids, notes): `docs/ASSET_STATUS.md`.

```
tools/assets/models/<name>.py  --build.sh-->  assets/blender/<Name>.blend
   (Python, rmh library)                      assets/exported/<Name>/{<Name>.glb, *_color|normal|rough|metal.png, manifest.json}
                                              assets/previews/<Name>*.png
        --publish.py upload-->  Open Cloud: GLB as Model, maps as Image  (ids -> assets/exported/<Name>/roblox_ids.json)
        --Studio harvest-->     MeshIds read back via InsertService:LoadAsset (Edit datamodel)
        --publish.py meshes-->  assets/roblox/<Name>.rbxmx  --Rojo-->  ReplicatedStorage.Assets.<Name>
```

## 1. Build (Blender 5.2, headless)

```sh
tools/assets/build.sh SupplyCrate            # one or more asset names
```

Each asset is a Python module `tools/assets/models/<snake_name>.py` exposing
`build(**kw)`. It describes the asset with the `rmh` library:

- `rmh/geo.py`: bmesh primitives (bevelled box, tapered box, cylinder,
  tube, lathe, prism, side_prism, sphere, torus, pipe_path) plus
  transform/mirror helpers. Units are studs. **Blender +Z = up, +Y = model
  forward** (becomes Roblox −Z), +X = right (Roblox +X).
- `rmh/asset.py`: `Asset(name, pivot)` → `a.part(name, path, tex, **flags)`
  returns a `Part`; `part.add(bm, material, at, rot, scale, mirror_x)`
  merges primitives into one MeshPart. `path` places the part in a
  sub-model (`"TurretGun/MachineGun"`). Flags: `query`, `collide`,
  `material` (Roblox material name), `shadow`, `neon=(r,g,b)` (Neon part,
  no textures), `transparency`, `smooth_angle`, `fidelity`.
  `a.pivot(path, pos)` sets a sub-model WorldPivot; `a.attach(name, part,
  pos, axis)` adds an Attachment; `a.marker(name, path, pos, size, axis)`
  adds an invisible non-colliding Part (e.g. `Muzzle`); `a.decal(image,
  center, normal, size, color)` projects a stencil (`rmh/images.py`: enemy
  emblem, stripes, arrow, stencil digits) onto every surface inside the
  projector box; `a.texture_group(name, px)` declares extra atlases.
- `rmh/materials.py`: procedural PBR materials with baked wear (edge chips,
  cavity grime, streaks, dust on upward faces and near the ground). Kinds:
  `paint`, `metal`, `fabric` (+ `gores`/`camo` patterns), `rubber`, `wood`,
  `concrete`, `rock`, `flat`. Palette presets in `PRESETS` (olive, tan,
  gunmetal, charcoal, enemy_red, steel, sandbag, ...). `a.material(name,
  base="olive", **overrides)` derives variants; `marks=[{lo, hi, color}]`
  paints object-space boxes (bands, stripes).
- `rmh/pipeline.py` (`a.finish(views=...)`): applies weighted normals,
  smart-UV-packs every texture group into one atlas (all parts of a group
  share one SurfaceAppearance set), bakes colour/roughness/metalness
  (emission trick) and a tangent-space normal map with Cycles (Metal GPU),
  saves the .blend, renders previews with the *baked* maps (what Roblox
  will show), exports the GLB and writes `manifest.json` (part centres and
  sizes in Roblox space, sub-model pivots, attachments, markers, texture
  files, triangle counts).

Build logs: `logs/assets/<Name>.log`. Typical build: 30–120 s (the
Emplacement, with cloth sims and nine atlases, ~4 min). Wrap every build in
`tools/blender-lock.sh acquire <you>` / `release <you>` (it bakes).

### Opt-in pipeline features (face-lift, HS-1)

None of these change an asset that doesn't ask for them.

- **Sheet texture groups** (`a.texture_group(name, px, sheet=True)`): the
  atlas holds a few *templates* (`t = a.template(name, group, low, mat,
  high=None, uv="smart"|"seams")`) instead of every part's surface; parts
  place rigid copies with `part.add_template(t, at, rot, scale)` (no
  mirroring) which share the template's UVs. When a template has a dense
  `high` mesh the group is baked selected-to-active (all templates joined,
  far from the asset so AO/bevel never see it; cage 0.06, ray 0.4).
  `uv="seams"` unwraps angle-based along the mesh's marked seams (the cloth
  sacks mark theirs). Used for the Emplacement's 14 sandbag templates (≈200
  bags at 84 px/stud from one 1024² atlas) and its casings/belt rounds.
- **`metal=False`** on a texture group skips the metalness map (and its
  upload); the rbxmx then has no `MetalnessMap` (= 0).
- **Cloth sims** (`rmh/cloth.py`): `cloth.sandbag(seed, size, press,
  neck, load, …)` inflates a flat two-sheet sack with cloth pressure and
  slumps it on the ground (optionally squeezed by a plate), returns
  `(high, low)` where `low` samples the same simulated lattice (so it lies
  on the high surface) and has UV seams marked. `cloth.drape(sheet, nx, ny,
  colliders, pinned)` drops a `cloth.grid_sheet` over collider bmeshes with
  pinned tie points (the camo net). Deterministic for the same arguments.
- **CC0 photo layers** (`photo={"id", "scale", "color", "sat", "rough",
  "height"}` on paint/metal/fabric/concrete/flat materials): box-projects a
  Poly Haven map set from `assets/source/cc0/<id>/` (fetch with
  `python3 tools/assets/cc0.py fetch`) and multiplies only its variation
  into the palette colour; roughness/height add their deviation. Credit
  every id in `assets/source/CC0_CREDITS.md`.
- **Wear keys:** fabric `bleach`, `damp`/`damp_height`, `seam_dust`,
  `weave_amount`, `net={cell, gap}` (garnished camo net); paint
  `chip_style="blotch"` (+`chip_bevel`, `ring`, `ring_color`), `fade`,
  `patches`; any material `zmin` (its own ground height) and `dust_color`.
- **Stencils:** `images.get("text", text="7.62", wear=0.4, seed=1)` — our
  own stencil stroke font (digits, `. - /`, most capitals); the image is
  not square, so project it with a decal of the same aspect
  (`models/emplacement.py: stencil()` does this).
- **Camera previews:** a view may be a dict `{"label", "pos", "look",
  "fov" (vertical, like Roblox FieldOfView), "res", "hide"}` to render
  from an exact camera (e.g. the in-game turret camera).
- **Texel density:** the manifest records `texel_density` (px/stud) per
  texture group, and the build log prints it.

- The rock kit is one module building ten assets:
  `tools/assets/build.sh RockKit` (or `BUILD_ARGS="--only Rock_Spire,Cliff_Wall_A" tools/assets/build.sh RockKit`).
- Contact sheet of previews for review:
  `Blender -b --factory-startup -P tools/assets/montage.py -- out.png a.png b.png ...`
- Cycles on Metal very occasionally crashes compiling kernels
  (`/var/folders/.../T/<Name>.crash.txt`); just rerun the build.
- UV packing is not byte-deterministic, so any rebuild changes the GLB and
  needs a model re-upload + harvest, even for material-only changes.

### Hard-surface tooling (face-lift, HS-3)

All opt-in; assets that don't ask for it build exactly as before (checked:
SupplyCrate rebuilt with the HS-3 pipeline gives identical map statistics).
Used by `Tank` and `Buggy`; built for HS-4 (Helicopter, Jet, turret gun
assembly) and HS-5 (Siege Crawler, wrecks).

**1. Shared trim sheets** (`rmh/trim.py`, sheet `models/trim_enemy.py` →
texture-only asset `TrimEnemy`). One 1024² set that several vehicles map
into, so its four maps load once for every tank, buggy and (HS-4) aircraft
on screen.
- *Strips* are full-width bands that tile along U: `track` (cast shoes with
  double grousers, pins, end connectors), `grille` (louvres, frame, ribs),
  `mesh` (expanded metal), `bolted` (strap with hex bolts), `canvas`
  (folded khaki-grey canvas with webbing straps), `cable` (wire rope),
  `plain` (worn charcoal paint), `red` (marking red). Each is baked from a
  periodic high-poly pattern (`strip(name, px, world, build, mat, relief)`,
  `build(period, world)` returns the pattern for one period + overhang),
  and its material gets `periodic=<period>` so every procedural noise
  repeats exactly (`materials.G.coords` wraps X round a circle) — no seam
  wherever U wraps. Strip heights/densities are logged by the build and
  stored in `assets/exported/TrimEnemy/trim.json` (`v0`, `v1`, `period`,
  `world`, `density`).
- *Templates* are whole meshes with their own islands (`roadwheel`,
  `sprocket`, `tyre_half`, `rim`, `jerrycan_red`, `jerrycan_dark`,
  `ammo_can`, `shovel`, `pickaxe`, `crowbar`, `periscope`, `headlight`),
  each baked from a high poly (rounded edges + bolts/X-ribs/lightening holes
  that only exist in the high), shelf-packed at one density (~49 px/stud)
  into the band under the strips. `trim.json` stores their low meshes with
  UVs; a template can be rotated and scaled (even non-uniformly) freely.
- *Using it*: `T = trim.use(a, "trim", "TrimEnemy")` declares a shared
  texture group; parts in it (`tex="trim"`) are never unwrapped or baked.
  Map every piece before `Part.add` (the build refuses unmapped faces):
  `T.planar(bm, strip, u_axis, v_axis, band=(0,1))`, `T.fill(bm, strip)`
  (longest axis), `T.cylindrical(bm, strip, axis, along=False|True)`
  (wheels/drums: U round; cables/rolls/whips: `along=True`, U along, V
  ping-pongs round — no seam), `T.loop(bm, strip, profile)` (bands round a
  2D profile, e.g. a track loop from `geo.band_loop`; whole periods), and
  `T.template(name)`. `faces=lambda f: ...` restricts any mapping.
  Previews render trim parts with the sheet's baked maps.
- *Publishing*: `publish.py upload TrimEnemy` uploads its maps only (no
  model, no harvest); an asset's `manifest.shared_textures` names its
  shared groups and `publish.py rbxmx` points them at the sheet's image ids.
  Rebuilding a sheet changes template UVs only if template meshes change;
  after a sheet rebuild, rebuild + re-upload every asset that uses it.
  UVs outside 0..1 wrap in Roblox (verified on the tank tracks).
- A second palette (e.g. an outpost OD sheet for the turret gun assembly)
  is another `models/trim_<name>.py` with the same builders and new
  materials.

**2. High-poly → game-mesh bake** (`a.texture_group(name, px, high={"hp":
0.05, "cage": 0.1, "ray": 0.3})`). Every piece added to a part of that
group is also copied into the part's high-poly source with its hard edges
rounded (`hp` = bevel width, per piece `Part.add(..., hp=0.02)`, 0 = as
is), and `Part.detail(bm, mat, ...)` adds geometry that exists only in the
high (bolt rows `hardsurface.bolt_row`, weld beads `hardsurface.weld`,
rivets, appliqué plates, perforation rings). The group is baked
selected-to-active (all channels) with the game meshes hidden from rays, so
AO grime and curvature wear are computed on the high surface. Keep the low
pieces unbevelled (the normal map carries the round edges) and keep
details within `cage` of the surface.

**3. Texture passes** (`materials.py`, any hard-surface kind):
`edge_convex=True` (chips/polish only on convex edges; creases keep paint),
`polish` (sharpest edges rubbed to bright steel), `dust_cavity` (+
`dust_cavity_range`, `_distance`: dust packed into gaps whatever way they
face), `dust_caked` + `caked_height`/`caked_color` (opaque noisy band from
the ground up), `splash=[{center, radius, strength}]` (dirt sprayed round
wheels), `soot=[{pos, dir, radius, length, spread, strength}]` (plumes at
exhausts, muzzles, dischargers), `rough_breakup` (smudges, wipes, fine
scratches), `streaks`, `grime_color`; decals take `wear`/`seed`
(`a.decal(..., wear=0.35)`: the marking's own paint chips and thins).
`hardsurface.stencil(a, text, centre, normal, height, chip=...)` projects
stencil text with the right aspect.

**4. Texture where it's seen.** `Part.add(..., texel=0.15)` or
`texel=lambda face: ...` gives faces a relative texel density;
`texture_group(..., down=0.3, back=0.6)` does it for faces pointing at
the ground / the model's rear (enemies drive at the player). The weighting
splits faces into their own islands before packing; the manifest's
`texel_density` then reports the density of the full-weight (visible)
surfaces.

**5. Contract hit boxes.** `a.part(name, ..., hitbox=rb_box(centre,
size))` (Roblox centre/size from the old manifest) pads the mesh with two
tiny corner triangles so its bounding box — its Roblox `Size`/`CFrame`,
i.e. its Box hit volume and what client code reads from it — stays exactly
the same; geometry outside the box fails the build (move it to a
`query=False` part). The tank and buggy lock every contract part.

**6. Inside-out shells.** `geo.side_prism` has always returned
inside-out shells (stale normals before `recalc_face_normals`); Roblox
culls back faces, so such pieces render wrong or vanish (the old buggy's
hood was invisible in game: `qa/beauty/hs-3-pre/afternoon_buggy-front.jpg`).
`side_prism` is left as is so other assets rebuild identically; set
`a.fix_inside_out = True` and every closed shell (low and high) is turned
outward at build time (the log says how many). Turn it on for every asset
you rebuild.

**Kit** (`rmh/hardsurface.py`): `round_edges`, `chamfer_edges`,
`plate_on_quad` (spaced-armour plate off a face), `bolt`, `rivet`,
`bolt_row`, `rivet_row`, `weld`, `grille_slats`, and pieces (`jerrycan`,
`ammo_can`, `shovel`, `pickaxe`, `crowbar`, `periscope`, `tarp_roll`,
`whip_antenna`, `rail`, `track_link`, `road_wheel`, `sprocket`, `tyre`,
`rim`, `headlight`); `geo.tapered_prism` (faceted turrets, wedges) and
`geo.band_loop` (tracks, straps).

**Recipe for a vehicle** (see `models/tank.py`): lock the contract parts'
hit boxes; hull/turret parts in `high` groups (1024², `down`/`back`
weights) with unbevelled low pieces, `detail()` bolts/welds, and a paint
spec with `edge_convex`, `polish`, `dust_caked`, `soot`, `rough_breakup`,
a `photo` layer and chipped decals; wheels, tracks and stowage as trim
parts (`query=False` kit parts for anything outside a hit box); check the
build log for texel density ≥ 30 and triangle counts; look at the
previews (add a `{"label": "_cam_player", ...}` view from the player's
side).

### Aircraft and turret additions (HS-4)

- **`rmh/aero.py`** (new): `span_loft(sections, axis="x"|"z")` lofts
  wings, stabilisers, fins and rotor blades through lens/superellipse
  sections (chord, thickness, centre per station — sweep, taper and
  dihedral come from the section list); `store(length, r, fins=4, blunt=)`
  builds bombs, missiles, drop tanks and pods along +Y; `tube_cluster`
  makes rocket-pod tube mouths for `detail()`; `outward(bm)` turns a
  closed shell outward (use it on a `side_prism` before splitting it).
- **Aircraft on the trim sheet:** rotor blades map to `plain` with the tip
  faces on `red` (`T.planar(..., faces=...)`), hubs to `bolted`/`plain`,
  missiles to `plain` + a `red` band + `cable` seeker (`T.cylindrical(...,
  along=True)`), gear to the `tyre_half`/`rim` templates scaled down. Only
  the airframe keeps its own 1024² atlas (`metal=False`: painted skins).
- **Texel weights for air targets:** they are seen from below, so upward
  faces get `texel=0.25–0.4` instead of `down=`.
- **`keep_normals=True`** (per part, opt-in): skips `fix_inside_out` for
  parts whose faces were oriented on purpose (the emplacement's `face_up`
  sand drifts have a capped underside, so the shell test would flip them).
- **Bake gotcha:** `detail()` geometry must sit on or above the low
  surface. Plates placed a few hundredths *below* it (inside the cage)
  baked as black slots on the jet's belly.
- **Rebuilding one group of a big asset** (Emplacement): every group
  re-bakes with sub-2/255 noise; copy the untouched groups' PNGs back from
  HEAD so `upload` skips them (hash) and their ids stay.

### Siege Crawler, wrecks and LOD (HS-5)

- **Siege Crawler** (`models/siege_crawler.py` + `models/siege_crawler_turrets.py`):
  four high-poly-baked 1024² atlases (`hull`, `armour` = skirts and plow,
  `deck`, `turrets` = weak points, core armour and sockets) and the shared
  `TrimEnemy` sheet for the twin-belt tracks (the `track` strip at ~2×,
  five periods round the loop) and all crew-scale kit. Crew-scale pieces
  (jerrycans, periscopes, rails at 3 studs, ladder rungs every 1.1 studs,
  tools) keep their real size: that is what makes the 90-stud hull read
  huge. `solid(bm)` turns a `side_prism` outward *before* `Part.add`, so a
  `texel=` function never depends on how the shell came out.
- **`texture_group(..., metal_px=512)`** (opt-in): the metalness map is
  saved at that size (a chip mask needs few pixels; 512² is a quarter of the
  memory). Used by the crawler, Tank and Buggy.
- **`a.preview_hide_transparent = True`** (opt-in): previews leave out
  parts that are invisible in the file (Transparency ≥ 0.99, or
  `hidden_preview=True`) unless a camera view lists them in `"show"`.
- **Wreck maps** (`tools/assets/build.sh WreckMaps`, `models/wreck_maps.py`,
  Blender's numpy, no bake): each vehicle's baked colour/metal/normal maps
  become a 256² (crawler 512²) burnt colour map `<Name>_<group>_wreck.png` (char, blistered
  paint remnants with ash rims, rust on chips/convex edges/blotches, dust
  turned to ash, markings burnt to oxide) plus `wreck.json` (the hash of the
  colour map it came from). `publish.py upload <Name>` uploads it only while
  that hash still matches the group's colour map, so **after rebuilding a
  vehicle (or the TrimEnemy sheet) re-run `build.sh WreckMaps`** - a stale
  wreck map is dropped with a warning and `Kit.char` falls back to tinting
  the live SurfaceAppearance. The rbxmx puts a Folder `Wreck` with the burnt
  SurfaceAppearance (wreck colour + the part's own normal/roughness) under
  every textured part; `Kit.char` swaps it in on death.
- **Runtime facts (Studio, 2026-09-26):** `SurfaceAppearance.Color` (tint)
  is writable by game scripts; the map `*Content` properties are read-only;
  imported MeshParts have `RenderFidelity = Automatic` (engine LOD) and it
  can't be changed from game scripts.
- **Vehicle LOD** (`src/client/VehicleLod.luau`): engine mesh LOD (Automatic)
  plus client culling of every `*Kit` part (CanQuery false) beyond 400
  zoom-corrected studs. New kit parts should keep the `Kit` suffix.

### Airdrop assets (HS-6)

`Transport`, `Parachute`, `ParachuteCargo`, `DropPlatform` and the
texture-only `TrimAirdrop` sheet (`models/{transport,parachute,
parachute_cargo,drop_platform,trim_airdrop}.py`; contracts in
`docs/ASSET_CONTRACTS.md`). New opt-in tooling, default behaviour unchanged
(every other asset builds as before):

- **`TrimSheet(name, size, gutter, metal=False)`**: a sheet with no
  metalness map (fabric). Consumers' rbxmx then leave `MetalnessMap` empty.
- **Multi-material strips**: `s.strip(name, px, world, build, mat=[...])`
  takes a list indexed by the pattern faces' `material_index` (gore shades,
  tapes, a marking band in one strip). A single name works as before.
- **`T.custom(bm, strip, fn, band, faces, wrap=None)`**: your own
  parameterisation, `fn(co) -> (u in periods, t in 0..1)`; `wrap` = periods
  round a closed loop (faces straddling it are shifted, no seam). The
  canopies map U = gore angle and V = arc from the vent on the inflated
  shape, then deform (deploy streamer, cloth collapse) keeping those UVs.
- **Part flag `flat=(r, g, b)`** (sRGB 0..1): no textures at all — a Roblox
  `material` + Color (the transport's `Windows` are `material="Glass"`).
  The pipeline skips it in unwrap/bake; previews use a matching stand-in.
- **`cloth._simulate(..., self_collision=d)`**: cloth self-collision
  distance (the collapsed canopies fold onto themselves); off by default.
- **Geometric markings on trim assets**: `transport.emblem(size)` builds the
  enemy emblem (broken ring + two chevrons, the proportions of
  `images.emblem_alpha`) as a flat single-sided mesh mapped to the `red`
  strip, laid a hair off the skin (`orient`). Red tips/bands come from face
  predicates on `T.planar` (wing, fin and prop tips). No decal bake needed,
  so an asset can stay on a shared sheet with zero own textures.
- **Cut glazing**: `transport.cockpit_glazing` insets the fuselage loft's
  facets in the glazed band (`bmesh.ops.inset_individual`; the rim stays skin
  as the frame), recesses the pane and moves it to the Glass part. Create
  any face layer *before* collecting face references (adding a layer
  invalidates them), and after an inset re-tag: the new rim faces copy the
  original face's layer values.
- **Canopy builder** (`models/parachute.py`: `Spec`, `open_lattice`,
  `canopy_open/deploying/collapsed`, `rigging`): one lattice (2 columns per
  gore, rings vent→hem) with gore bulges and a scalloped skirt; double-sided
  with `bmesh.ops.solidify`. The collapse lays every gore out downwind at
  full length with a narrowed cross-section, then drops a 2× lattice with
  Blender cloth (low compression stiffness so it buckles, self-collision)
  and samples it back onto the game lattice. A dome shell dropped as is
  stays a rigid bowl; pre-flatten it.

Rebuild and publish:
```sh
tools/blender-lock.sh acquire hs; tools/assets/build.sh TrimAirdrop Transport Parachute ParachuteCargo DropPlatform; tools/blender-lock.sh release hs
set -a; . ./.env.local; set +a; python3 tools/assets/publish.py upload TrimAirdrop Transport Parachute ParachuteCargo DropPlatform
python3 tools/assets/publish.py harvest Transport Parachute ParachuteCargo DropPlatform   # run in Studio (Edit), save the JSON
python3 tools/assets/publish.py meshes <harvest.json>
```
Rebuilding `TrimAirdrop` changes nothing in the assets' UVs as long as the
strip order/heights stay (they map into `trim.json` at build time: rebuild
them after changing it).

### Game-resolution maps and never-drawn maps (RECLAIM-HS)

Texture reclaim from QA-B's list (`docs/PERF_BUDGET.md` §5.5). All opt-in;
every other asset builds and publishes as before.

- **`GAME_PX` / `Asset.game_px`** (`rmh/game_maps.py`): a cap on the maps
  *uploaded* to Roblox. A model file declares a module-level `GAME_PX = 512`
  and sets `a.game_px = GAME_PX` in `build()`. The bake, the `.blend`, the
  previews and `<Name>_<group>_<ch>.png` stay at the full `tex_size`, so
  key art, wreck maps and later bakes keep full detail. The build then
  writes `<Name>_<group>_<ch>_512.png` for every larger map and records
  `game_px` and `upload_textures` in the manifest; `publish.py upload`
  sends those copies in place of the full maps (maps already ≤ the cap,
  e.g. `metal_px=512` metalness, go as they are). The copies are a box
  average, i.e. the next level of a standard mip chain: colour in linear
  light, normal/roughness/metalness as stored. The Wreck looks keep their
  own colour map (made from the full-size colour map, so `wreck.json` stays
  fresh) and pick up the 512² normal/roughness in `publish.py rbxmx`.
  Used by Tank, Buggy, Helicopter, Jet and SiegeCrawler (not by the shared
  `TrimEnemy` sheet). Why it is invisible in play: at each vehicle's
  nearest gunsight range the 512² maps still give ≥ 1.1 texels per screen
  pixel (crawler 1.1 at 330 studs, jet 1.2 at ~220, heli 2.1, buggy 2.2,
  tank 3.6), so the GPU was already sampling mip ≥ 1 of the 1024² maps.
- **Re-export without a rebuild:** `tools/assets/build.sh GameMaps`
  (`models/game_maps.py`, a few seconds, no bake, no lock) or
  `BUILD_ARGS="--only Tank" tools/assets/build.sh GameMaps`. It reads each
  model's `GAME_PX`, writes the copies and the manifest keys. Then
  `publish.py upload <Name>` + `publish.py rbxmx <Name>`; geometry and mesh
  ids don't change, so no harvest. **To opt out**, delete `GAME_PX` (and the
  `a.game_px` line), remove `game_px`/`upload_textures` from the manifest
  (or rebuild) and upload again: the full maps go back up.
- **Meta `untextured`** (`publish.py`, `rbxmx.py`): an asset whose maps are
  never drawn (the rigid `Infantry` parts are invisible hit volumes under
  the skinned soldier since CHAR-2; the `InfantrySpike` test bar is never
  shipped). `a.meta["untextured"] = [r, g, b]` (0..1) or `True`:
  `publish.py upload` uploads no maps and drops their ids; the rbxmx
  carries no SurfaceAppearance and gives the parts that flat colour (the
  rigid infantry fall back to the uniform charcoal if the skinned templates
  ever fail). The maps are still baked locally for previews.
- **Dead maps removed:** the SupplyCrate `chute` group is declared
  `metal=False` (its metalness map was all zero; metalness 0 either way),
  and the stale pre-HS-3 `Tank_gear_*` and `Buggy_wheels_*` PNGs (no
  manifest group, never uploaded) were deleted from `assets/exported/`.

```sh
tools/assets/build.sh GameMaps
set -a; . ./.env.local; set +a
python3 tools/assets/publish.py upload Tank Buggy Helicopter Jet SiegeCrawler
python3 tools/assets/publish.py rbxmx Tank Buggy Helicopter Jet SiegeCrawler
```

### Axis handling (verified in Studio)
Roblox's glTF importer turns an asset 180° about up. `export_glb` rotates
mesh data 180° about Z just for the export, so a model built facing +Y in
Blender faces −Z in Roblox, and `manifest` uses Roblox = (x, z, −y).
MeshParts are re-centred on their bounding box by the importer; the rbxmx
places each part at its bbox centre with identity rotation. The importer
keeps 1 Blender unit = 1 stud for GLB (FBX came in at 100×, so GLB is used).

## 2. Upload (Open Cloud)

```sh
set -a; . ./.env.local; set +a      # ROBLOX_OPEN_CLOUD_KEY, ROBLOX_CREATOR_USER_ID (never print)
python3 tools/assets/publish.py upload SupplyCrate Emplacement
```

`tools/assets/opencloud.py` posts multipart `request` + `fileContent` to
`https://apis.roblox.com/assets/v1/assets` and polls
`/assets/v1/operations/{id}`. The GLB goes up as assetType `Model`, maps as
assetType `Image` (the returned id is directly usable in SurfaceAppearance;
`Decal` ids are not). Uploads are private to the creator account and are
skipped when the file hash is unchanged (`roblox_ids.json` → `hashes`).

## 3. Harvest mesh ids (Studio)

The API key cannot download asset contents, so mesh ids are read in Studio:

```sh
python3 tools/assets/publish.py harvest SupplyCrate Emplacement   # prints tools/assets/.harvest/multi.luau
```

Run the printed snippet with MCP `execute_luau` in the **Edit** datamodel
(no playtest needed; `InsertService:LoadAsset` works there for the
creator's own assets). It returns `{Name: {Part: {id, size}}}`. Save that
JSON to a file and:

```sh
python3 tools/assets/publish.py meshes /path/to/harvest.json
```

This checks every imported mesh size against the manifest (catches axis
or scale errors), stores the ids and writes `assets/roblox/<Name>.rbxmx`.
`upload` also forgets cached map ids for texture groups/channels that the
current manifest no longer has.
`python3 tools/assets/publish.py rbxmx <Name>` regenerates from cached ids.

## 4. In game

Rojo syncs `assets/roblox/*.rbxmx` to `ReplicatedStorage.Assets`.
`AssetLibrary.clone(name)` returns a fresh copy (or nil). Generated models:
all parts Anchored, CanTouch false, CanCollide per flag (default false),
CanQuery per flag (default true), CollisionFidelity Box, SurfaceAppearance
with Color/Normal/Roughness/Metalness maps. The top model's pivot is the
asset origin (`PrimaryPart` = `Root` with a PivotOffset when present, else
`WorldPivot`). Verify in Studio (lock + `caffeinate -u -t 2`): clone into
Workspace, `screen_capture`, check pivots and orientation.

## Adding an asset

1. Create `tools/assets/models/<snake_name>.py` with `build(**kw)`
   (copy `supply_crate.py` as a template); follow the contract names.
2. `tools/assets/build.sh <Name>`; review `assets/previews/<Name>*.png`
   against GAME_SPEC §13 and iterate.
3. `publish.py upload <Name>` → harvest in Studio → `publish.py meshes`.
4. Check in Studio, append to `docs/ASSET_STATUS.md`, commit
   (`assets/`, `tools/assets/`).

## Skinned meshes (Character workstream, verified in Studio 2026-09-26)

One deforming mesh per variant on a shared skeleton, posed from code with
`Bone.Transform` (GAME_SPEC §14.1 item 8). Library `tools/assets/rmh/skin.py`
(`SkinnedAsset`, `Bone`, `Pose`, `sweep`), publisher
`tools/assets/skin_publish.py`. Assets: `InfantrySpike`
(`models/infantry_spike.py`, the 3-bone test bar, also the regression test)
and `InfantrySkinned` (`models/infantry_skinned.py`, the soldier).

```
models/<name>.py (SkinnedAsset)  --build.sh-->  assets/blender/<Name>.blend (bake stage)
                                                assets/exported/<Name>/{<Name>.glb, <Name>_main_{color,normal,rough,metal}.png, manifest.json}
                                                assets/previews/<Name>_*.png (posed with the manifest poses)
  --skin_publish.py upload-->    Open Cloud: GLB as Model, maps as Image (publish.upload; ids in roblox_ids.json)
  --skin_publish.py harvest-->   Studio snippet (Edit datamodel) -> JSON {parts, bones, root}
  --skin_publish.py meshes <Name> <json>-->  checks + assets/roblox/<prefix>_<Variant>.rbxmx
  --in game, once per template--> Body:ApplyMesh(AssetService:CreateMeshPartAsync(...))   (see gotcha 1)
```

### What the pipeline does (exact settings that work)
- **Skeleton:** every bone points straight up (+Z) with roll 0, so every
  glTF joint has an identity rotation; a bone's `head` is its pivot. The
  bone's `start`/`end` segment is only used for skin weights.
- **Weights:** set per piece in `SkinnedAsset.add` — a bone name (rigid),
  a list of candidate bones (inverse distance to their segments, power
  4–6, top 3, normalised) or a `weight_fn(co)`. Mirrored copies swap
  Left/Right bone names.
- **Export:** `export_scene.gltf(export_format="GLB", use_selection=True`
  (armature + meshes)`, export_apply=False, export_skins=True,
  export_animations=False, export_rest_position_armature=True,
  export_yup=True, export_materials="NONE")`. **No** 180° pre-rotation
  (rigid assets have one). FBX was not needed.
- **Upload:** GLB as assetType `Model` through `opencloud.upload`, like
  rigid assets.
- **What the importer builds** (`InsertService:LoadAsset` in Edit): a
  Model with one MeshPart per glTF *mesh* (named after the mesh data, so
  avoid `.001` suffixes; `HasSkinnedMesh = true`; plus a `<Mesh>Motor6D`),
  the Bone hierarchy with the Blender bone names — under a `RootPart`
  Part at the glTF origin when there are several meshes, under the
  MeshPart itself when there is one — an `AnimationController` and an
  `InitialPoses` folder. The asset is turned 180° about up: the root bone
  carries that rotation, child bones are identity relative to it.
  **Bones that no vertex is weighted to are dropped**; `skin.py` keeps
  marker bones (muzzle, support hand, lamp) alive by giving one vertex
  rigidly on the parent a 5 % share.
- **rbxmx** (`skin_publish.py`), per variant: Model `<prefix>_<Variant>`
  (PrimaryPart `Root`, WorldPivot = asset pivot) containing `Root` (Part,
  invisible, 2×2×1, CanQuery false, at the pivot, identity rotation; holds
  the Bone tree), `Body` (the skinned MeshPart + SurfaceAppearance,
  CanQuery false, Material Fabric) and optionally `BodyLOD` (Transparency
  1). Everything is turned back 180° about up, so the model faces −Z and
  every bone's rest rotation is identity in model space. `meshes` checks
  imported sizes against the manifest and that every turned bone lands on
  its manifest head with identity rotation.
- **UVs:** tubes from `sweep()` (limbs, torso, straps) carry their own
  one-island UVs; the other faces are smart-projected; then all islands
  get the same texel density (`average_islands_scale`) and are packed into
  one atlas shared by every variant. Non-shared layers are moved 30 studs
  apart during the bake so AO/cavity don't see other variants' gear.
- **Materials:** `rmh.materials` kinds, plus `garment` (registered by
  `skin.py`): fabric with compression folds around joints baked into the
  normal map (`folds=[{centre, axis, radius, wavelength, depth}]`).

### Gotchas (all reproduced in Studio)
1. **A MeshPart made from an rbxmx is not skinned.** Rojo (or any plugin
   setting `MeshId`) creates it with `HasSkinnedMesh = false`, and it does
   not deform; the property is NotAccessible (can't be written). Fix, once
   per template before cloning (server or client):
   ```lua
   local mp = AssetService:CreateMeshPartAsync(Content.fromUri(body.MeshId), { CollisionFidelity = Enum.CollisionFidelity.Box })
   body:ApplyMesh(mp); mp:Destroy()   -- body.HasSkinnedMesh is now true
   ```
   Done on the server on the ReplicatedStorage template, clones replicate
   to clients already skinned. 6 meshes took 1.8 s in a playtest.
2. **Joint the mesh straight to its bone holder.** The skinned MeshPart
   only follows bones under itself or under a part it is jointed to
   *directly* (Weld/WeldConstraint/Motor6D between the bone holder and
   `Body`). Being in the same assembly is not enough: CHAR-2 first welded
   `Body` and the bone holder each to a third part (the rigid soldier's
   `Root`) and the mesh stayed in its bind pose while the bones moved
   (`qa/beauty/char-2/extra/weld_to_hub_no_deform.jpg` vs
   `weld_to_bone_holder_deforms.jpg`). Chain it: hub → `SkinRoot` →
   `Body`/`BodyLOD`. Two separately anchored parts: no deformation either.
3. `Bone.Transform` is local (not replicated) and renders in Edit too.
   `Bone.WorldCFrame` ignores Transform; posed positions come from
   `Bone.TransformedWorldCFrame`.
4. **`PrimaryPart` can be nil** on a template right after Rojo's first live
   sync, although the rbxmx carries the ref. Set
   `model.PrimaryPart = model.Root` in code before `PivotTo`/`ScaleTo`.
5. **`Model:ScaleTo` works with skinned meshes** (verified in a playtest,
   `qa/beauty/char-2/extra/scaleto_test_client_clones.jpg`): it scales the
   MeshPart and every `Bone.CFrame` (e.g. `LeftUpperLeg` −0.31 → −0.341 at
   1.1×), and the scaled mesh still deforms. It does **not** scale what you
   write into `Bone.Transform`: multiply any Transform translation (the
   Hips offset) by the model scale yourself.
6. **`ApplyMesh` on the server template is enough**: clones made on the
   server afterwards replicate with `HasSkinnedMesh = true` and deform on
   every client (CHAR-2 in-game soldiers). Keep a rigid fallback if
   `CreateMeshPartAsync` fails.
7. **Two-bone IK with a rotated parent** (`rmh.skin_pose.Pose.ik`): fixed
   in CHAR-2. It used to set the upper bone's world rotation to `Du`
   instead of `Du @ Dp`, so hands/feet missed their targets whenever the
   parent (chest/hips) was rotated: with the Patrol/Aim chest angles the
   right hand (and muzzle) sat 0.10/0.17 studs off and the support hand
   0.33/0.60 studs off the handguard; for a falling body, whole studs. The
   manifest's Patrol/Aim tables predate the fix; `infantry_anim.py`
   re-solves them, and the client uses its tables (a rebuild of
   `InfantrySkinned` would refresh the manifest's copy).

### Posing convention
`bone.Transform = CFrame.new(x, y, z) * CFrame.Angles(rx, ry, rz)` means
the same as a Motor6D.Transform on a rig with unrotated C0/C1 (model
faces −Z): +X swings a hanging limb forward, +Y turns left, +Z swings a
hanging limb towards +X. `rmh.skin.Pose` builds poses in Blender with FK
and analytic two-bone IK and writes them to `manifest.json` → `poses` as
`{bone: [rx, ry, rz(, [x, y, z])]}` degrees/studs; previews are rendered
from the same tables, so a pose that looks right in the preview looks the
same in Roblox (checked side by side: `qa/beauty/char-1/`).

### Animation clips (CHAR-2)
`tools/assets/models/infantry_anim.py` authors the infantry's clips with
the same FK + IK pose builder, from a handful of rig controls per key
(hips offset/rotation, spine/chest/neck/head angles, ankle targets with
knee poles in the hips' frame, hand targets or FK arm angles). Every
sampled frame (20 fps) re-runs the IK, so planted feet stay planted; the
script prints the worst IK miss (0.000 studs now). The jog cycle is 16
frames over `WALK_CYCLE` = 7.2 studs of travel, played by distance moved,
not time. Output: `assets/exported/InfantrySkinned/anim.json`, the
generated client module `src/client/InfantryRigClips.luau` (don't edit;
re-run the script) and filmstrip previews
`assets/previews/InfantryAnim_*.png` (Workbench render of the shipped GLB,
a few seconds, no bake). Runtime: `src/client/InfantryRigPose.luau`
(compile/sample) and `InfantryRig.luau` (state machine, blends, layers).
```sh
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/assets/models/infantry_anim.py -- [--no-preview] [--only Walk,Throw,DeathBack,DeathFront,Poses]
```

### Commands
```sh
tools/blender-lock.sh acquire <you>; tools/assets/build.sh InfantrySkinned; tools/blender-lock.sh release <you>
set -a; . ./.env.local; set +a
python3 tools/assets/skin_publish.py upload InfantrySkinned
python3 tools/assets/skin_publish.py harvest InfantrySkinned     # run the printed snippet in Studio (Edit), save its JSON
python3 tools/assets/skin_publish.py meshes InfantrySkinned harvest.json
```
The spike (`InfantrySpike`) runs the same commands; its rbxmx
(`InfantrySpike_Bar`) is a test object — delete it from `assets/roblox/`
after checking, it is not shipped.
