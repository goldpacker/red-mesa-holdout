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
