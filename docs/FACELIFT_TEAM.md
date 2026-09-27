# Face-lift team contract

How the visual face-lift in `docs/FACELIFT_PLAN.md` is built by several
agents working at the same time on one branch. `docs/ARCHITECTURE.md` still
holds the code layout, gameplay contracts and testing notes; this file
overrides its **ownership** table for the duration of the face-lift.

## Decisions (user, 2026-09-26)

1. **CC0 inputs allowed.** Poly Haven CC0 textures and HDRIs may be used as
   raw input, substantially modified and baked into our own assets
   (GAME_SPEC §14.2). Download with `curl` from the Poly Haven API
   (`https://api.polyhaven.com/files/<id>`), at 1k–2k, into
   `assets/source/cc0/<id>/` (git-ignored, re-downloadable). Record every
   source in `assets/source/CC0_CREDITS.md` (id, URL, licence, what we did
   to it). Nothing from any other source; nothing paid.
2. **Hybrid landscape.** Meshes for the mesa, canyon walls, far wall and
   buttes; the basin floor stays terrain with custom MaterialVariants.
   Terrain remains the gameplay/collision/height surface underneath.
3. **Scope: all phases 0–9.**

## Visual only

Gameplay, balance, timings, damage, hit volumes, lanes, spawn points,
enemy paths, server authority and the event contracts in ARCHITECTURE.md
do not change. If a visual change needs a gameplay change, stop and report
it instead.

## Workstreams and ownership

Edit only files you own. For anything else: a minimal, additive change
(one `require(...).start()` line, one new function, one hook call), never a
restructure, and list it under "edits outside my ownership" in your report.

| Workstream | Phases | Owns |
|---|---|---|
| **Lead** (coordinator) | gates | `PROGRESS.md`, `GAME_SPEC.md`, `docs/ARCHITECTURE.md`, `docs/FACELIFT_*.md`, `DONE.md` |
| **QA-tools** | 0, 9 | `tools/qa/**`, `tools/studio-lock.sh`, `tools/blender-lock.sh`, `qa/beauty/**`, `docs/ART_BIBLE.md`, `docs/PERF_BUDGET.md`, `src/shared/BeautyShots.luau`, the Studio-only debug hooks (`RedMesaDebug`) |
| **Environment (ENV)** | 1 | `src/server/TerrainBuilder.luau`, `src/server/WorldBuilder.luau` (everything except lighting), new `src/server/{Landscape,GroundDressing}*.luau`, `src/shared/{SkyAssets,TerrainMaterials}.luau`, `tools/assets/models/{rock_kit,landscape_*,dressing_*,road_*,wash_*}.py`, `tools/env/**`, their assets under `assets/**`, `assets/source/**` |
| **Hard-surface (HS)** | 3, 4 | `tools/assets/{rmh/**,build.*,publish.py,rbxmx.py,opencloud.py,montage.py}` (core pipeline), `tools/assets/models/{emplacement,gunsights,tank,buggy,helicopter,jet,siege_crawler,supply_crate,trim_*,wreck_*}.py`, their assets, `src/server/Emplacement.luau`, `src/shared/AssetLibrary.luau`, `src/client/WeaponFxTurret.luau`, new `src/client/{EmplacementFx*,GunsightModels}.luau`, `src/client/VehicleLod.luau`, `src/server/EnemyTypes/**` except `Infantry.luau` (visual code only), `docs/ASSET_{STATUS,CONTRACTS,PIPELINE}.md` |
| **Character (CHAR)** | 5 | `tools/assets/models/infantry*.py`, Infantry assets, `src/server/EnemyTypes/Infantry.luau` (rig/visual parts only), `src/client/EnemyVisuals.luau`, new `src/client/InfantryRig*.luau` |
| **VFX** | 6 | `src/client/{Effects*,EnemyFireFx,WeaponFx,WeaponFxParticles,VehicleFx*}.luau`, new `src/shared/Flipbooks.luau`, `tools/vfx/**`, `assets/vfx/**` |
| **Look** (lighting, UI, motion) | 2, 7, 8 | `src/server/TimeOfDay.luau`, new `src/server/LightingRig.luau` (the lighting code moved out of WorldBuilder), `src/client/{NightFx,Hud,Screens,Ui,ThreatHud,WeaponHud,AimController}.luau`, new `src/client/{PostFx,UiKit,EnemyMotion}*.luau`, `assets/ui/**`, `tools/ui/**` |

Frozen gameplay files (additive hooks only, and say so):
`src/server/{GameController,WaveDirector,Scoring,Crates,Weapons,Projectiles,Enemies,Types,init.server}.luau`,
`src/shared/{Config,Aim,WeaponConfig,EnemyConfig}.luau`,
`src/client/{GameState,WeaponController,LockOn,Sfx,SfxSheet,init.client}.luau`,
`default.project.json` (additive entries only).

### Shared pipeline code (`tools/assets/`)
HS owns the core. Other workstreams add **new** modules (`rmh/skin.py`,
`rmh/landscape.py`, …) or **opt-in** parameters with defaults that keep
current behaviour, so every existing asset still builds the same way.
Never change a default another asset relies on.

### Cross-workstream contracts
- **Sky:** ENV publishes `src/shared/SkyAssets.luau` → per time-of-day
  preset the six skybox faces, sun/moon settings and `Clouds` values.
  Look's `TimeOfDay`/`LightingRig` consume it through `pcall(require, …)`
  and fall back to the current sky when an entry is missing.
- **Surfaces for impacts:** every landscape/dressing mesh ENV places sets
  `Material` to what it looks like (`Rock`, `Sandstone`, `Sand`, `Ground`)
  so VFX can pick sand spurts, rock chips or sparks from a raycast result.
  Enemy and emplacement metal parts keep `Metal`/`DiamondPlate`-class
  materials or sit under a model with an `EnemyId` attribute.
- **Flipbooks:** VFX publishes `src/shared/Flipbooks.luau` (name → texture
  id, grid, fps). Other workstreams (HS backblast dust, CHAR dust) may use
  it read-only.
- **Enemy motion (Phase 8):** Look's `EnemyMotion` owns client-side root
  smoothing and body bob/roll/lean/bank. VFX and HS keep animating child
  parts (rotors, wheels, turrets) relative to the model, never the root.
- **Hit volumes:** server-side parts used for hits (infantry `Head`,
  enemy hull/weak-point parts, crates) keep their names, sizes and
  positions. Visual meshes may change freely around them.

## Shared resources

- **Studio (one instance).** `tools/studio-lock.sh acquire <you>` before
  any playtest, `screen_capture`, Edit-datamodel harvest or other Studio
  write; release right after. Waiters are served first-come first-served;
  if an acquire call is cut off by a tool timeout, run it again (your place
  is kept). Do offline work while you wait rather than holding the lock
  through long thinking or builds. Keep sessions short, never leave a playtest
  running. Before a playtest: `caffeinate -u -t 2`, and bring Studio to the
  front with computer-use `open_application("RobloxStudio")`. For visual QA
  set `settings().Rendering.QualityLevel = Enum.QualityLevel.Level15` in the
  Client datamodel and wait ~40 s for terrain. Studio id: `list_roblox_studios`.
- **Blender.** Headless only: `/Applications/Blender.app/Contents/MacOS/Blender -b ...`
  (or `tools/assets/build.sh`). Do **not** drive the running Blender GUI or
  the Blender MCP tools; that instance is the user's. Wrap every Cycles
  bake, render or fluid sim in `tools/blender-lock.sh acquire <you>` /
  `release <you>` (a few slots are shared; hold one only while a heavy job
  runs).
- **Rojo** (`rojo serve --port 34872`) live-syncs `src/` and
  `assets/roblox/` into Studio for everyone. Keep the tree working at all
  times: run `tools/check.sh` before saving risky edits and before every
  commit. If someone else's file breaks your playtest, don't fix it; note
  it in your report and carry on with what you can test.
  Rojo has dropped sync twice during the face-lift (7.7 can crash when a
  file is removed and re-added quickly). Before trusting a playtest,
  confirm your latest edit is in Studio (e.g. `script_read` a changed
  line). If it isn't: `pgrep -fl "rojo serve"`; restart with
  `rojo serve --port 34872 > logs/rojo-serve.log 2>&1 &` if needed, and
  reconnect the Studio plugin (Plugins → Rojo → Connect).
- **Open Cloud uploads** (`docs/ASSET_PIPELINE.md`): private uploads only,
  batched, skip unchanged files. Never print the key. Harvest mesh ids in the
  Edit datamodel under the Studio lock.

## Quality gates for every milestone

1. `tools/check.sh` passes.
2. A playtest of the areas you touched shows no new console errors or
   warnings from your files.
3. Gameplay safety (visual only, see above). ENV additionally re-runs the
   turret line-of-sight check to every lane end (QA-tools provides the
   command) and confirms enemies still spawn, snap to the ground and reach
   the mesa foot.
4. **Before/after beauty shots** of the cameras your change affects, taken
   with the QA-tools capture tool into `qa/beauty/<milestone-id>/`, and a
   side-by-side comparison against `qa/beauty/p0-baseline/`. Look at them
   yourself and iterate until the change is a clear improvement with no
   regression elsewhere.
5. The plan's **"Roblox-tell" checklist** (FACELIFT_PLAN §5) for what you
   touched: no voxel stair-steps, stock terrain textures, `SmoothPlastic`,
   default sky, built-in particle textures, clean untextured boxes or
   robotic stepped motion.
6. Readability: enemies still contrast with the ground (grayscale check
   for anything that changes enemies or the ground behind them).
7. Performance: measure against `docs/PERF_BUDGET.md` when you add
   geometry, textures or particles.

## Assets and the repo

- Textures ≤ 1024²; meshes ≤ ~20k triangles per MeshPart (split larger).
- Don't commit any file over 50 MB. High-poly sources must be regenerable
  from the build scripts; commit the game-resolution `.blend`, exports and
  previews as the existing pipeline does.
- Update `docs/ASSET_STATUS.md` (HS keeps the table; others add rows
  for their assets).

## Git

- Same branch (`opus-5.5-run-01`) for everyone. Commit only your own paths,
  and always name them so another agent's staged files never ride along:
  `git add <paths> && git commit -m "<type>(<ws>): <msg>" -- <paths>`
  where `<ws>` is `qa`, `env`, `hs`, `char`, `vfx` or `look`. End the message
  with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- If `.git/index.lock` exists, wait a few seconds and retry. Never
  `git add -A`, `git commit -a`, `git stash`, `git reset`, `git checkout --`
  on others' files, `--amend`, rebase, push or force-push.

## Reporting

Each milestone dispatch names a report file. Write the full report there:
what changed, evidence (commands, check output, playtest notes, beauty-shot
paths, perf numbers), edits outside your ownership, known issues, and what
the next milestone should know. Reply to the lead with a short status only.

---

## Update 2 — airdrop arrivals and cinematic environment (2026-09-26)

Plan: `docs/AIRDROP_ENVIRONMENT_PLAN.md`. Spec: `GAME_SPEC.md` §6.1, §7,
§8, §13–15. Everything above still applies, with these changes.

**Gameplay may change only in the Airdrop workstream**, and only as spec
§6.1/§8 describe (arrival by airdrop, wave retune). Every other workstream
stays visual only.

| Workstream | Adds to its ownership |
|---|---|
| **Airdrop (AD)** — new | new `src/server/Airdrop*.luau`, `src/client/Airdrop*.luau`, `src/shared/AirdropConfig.luau`; `src/server/WaveDirector.luau`; the spawn entry points (`opts.landAt`) in `src/server/Enemies.luau` and `src/server/EnemyTypes/{Infantry,Buggy,Tank}.luau` — additive, behaviour after landing unchanged; the wave table in `src/shared/Config.luau` (`Config.Waves` only); `tools/qa/autoplay*.luau` (bots); `tools/audio/**`, `src/client/SfxSheet.luau` and new sound names in `src/client/Sfx.luau`; the client "no effect" feedback hook in `src/client/WeaponController.luau` (additive) |
| **Hard-surface** | `tools/assets/models/{transport,parachute*,drop_platform}.py` and their assets |
| **Environment** | new `src/server/{Dressing,ConflictDressing}*.luau`, `tools/env/dressing/**`, their assets |
| **VFX** | new `src/client/{Weather,Wind,Birds,DustStorm}*.luau`, `src/shared/Wind.luau`, `tools/vfx/**` additions; a `weather` field per wave in `Config.Waves` (additive; coordinate with AD) |
| **Look** | storm lighting states and the film treatment in `LightingRig`/`TimeOfDay`/`PostFx*` |
| **QA-tools** | as before; plus the final before/after page inputs |

Contracts for Update 2:
- **Sortie event:** AD publishes `AirdropSortie` (server → client) with the
  path, timing and each load's `landPos`/`landT`; clients render transports
  and descents from it. Document the payload in `docs/ARCHITECTURE.md`'s
  event list (AD may append there).
- **Airborne visuals:** client-only, under `Workspace.AirdropFx`, tagged
  `Airborne = true`, `CanQuery` true only for the client's own "no effect"
  raycast. Server weapons never see them.
- **Wind:** VFX publishes `src/shared/Wind.luau` (direction, strength, gust
  at time t). Look, ENV (flutter) and AD (chute drift) read it; nothing
  else defines wind.
- **Storms:** a wave's `weather` field starts a storm. VFX owns particles
  and density; Look owns the lighting state; both keep the readability
  rule.
