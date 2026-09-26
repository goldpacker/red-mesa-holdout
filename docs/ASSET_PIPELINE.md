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
