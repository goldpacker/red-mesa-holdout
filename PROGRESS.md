# Progress

Team setup (2026-09-26): lead (integration, world, waves, HUD, audio) plus
three agents — Weapons (done), Enemies (in progress), Assets (in progress).
Contracts: `docs/ARCHITECTURE.md`, `docs/ASSET_CONTRACTS.md`.

## Completed
- **Milestone 1 — first playable** (`1cfb819`): title, turret camera and
  gunsight, machine gun with overheat, infantry, integrity/damage feedback,
  scoring and combos, HUD with radar, intermission, defeat (Restart / Retry
  Wave), victory (Play Again), QA debug hooks and autoplay helper.
- **Art direction** changed to grounded semi-realistic (GAME_SPEC §13/§14).
- **Architecture for parallel work:** auto-registered enemy types,
  weapon-aware damage/splash API, extended enemy context, AssetLibrary with
  primitive fallbacks, per-owner config/HUD/FX modules, Studio lock,
  `tools/check.sh` syntax checker.
- **Weapons (agent, `55cbb9b`):** weapon switching (1/2/3, wheel) with
  turret poses, rockets (8/wave, reload 1.5 s, splash), AA missiles
  (4/wave, 1 s lock-on, homing, no lock = no fire), server-authoritative
  ammo, per-weapon crosshairs and gunsights, lock box, reload bars.
- **Waves:** all 10 waves per the spec table in `Config.Waves`, with time of
  day and crate drop times; per-wave max duration (boss wave 12 min).
- **Time of day:** afternoon → late afternoon → sunset → dusk → night,
  tweened during intermissions; night readability via ambient fill,
  sweeping searchlights and illumination flares.
- **Supply crates:** parachute drops (rockets / missiles / repair),
  collected by shooting them with any weapon; pickup notification.
- **Threat HUD:** off-screen arrows for enemies in attack range (air blue,
  ground red), jet warning banner + siren, boss bar (weak points + core),
  main-cannon charge warning, first-encounter tips, low-integrity alarm.
- **Audio:** 36 original synthesized effects in one uploaded sound sheet
  (asset 70797639407728, in moderation review at upload time), played as
  playback regions; positional one-shots and loops.
- **Terrain v2:** eroded mesa/buttes/canyon walls, dunes, smooth washes,
  organic boulders; turret line of sight to every lane end verified.
- **Title loading gate:** START enabled once the battlefield replicated.
- **Enemies (agent):** buggy, tank, helicopter, jet, Siege Crawler,
  human-scale infantry, destruction and night-readability FX.
- **Assets (agent):** Blender→Open Cloud→Rojo pipeline; SupplyCrate,
  Emplacement, Infantry, Tank, Buggy, Helicopter, Jet, SiegeCrawler, rock kit.
- **Balance:** waves 3/8/9 and the boss tuned from bot runs.
- **Final end-to-end playthrough succeeded** (see DONE.md).

## Current work
**Update 2 — airdrop arrivals + cinematic environment** (started 2026-09-26
evening, user feedback; spec §6.1/§13, plan `docs/AIRDROP_ENVIRONMENT_PLAN.md`,
contract `docs/FACELIFT_TEAM.md` "Update 2", ledger
`.superpowers/sdd/AIRDROP_ENVIRONMENT_PLAN/`). First wave running: AD-1
airdrop core, HS-6 transport/parachute art, ENV-3F ground edges + dressing,
LOOK-3B motion sweep, QA-B budget measurement. The paused face-lift items
below are resumed inside this plan.

**Visual face-lift** (`docs/FACELIFT_PLAN.md`), built 2026-09-26 by a lead
plus QA-tools, Environment (ENV), Hard-surface (HS), Character (CHAR), VFX
and Look agents under `docs/FACELIFT_TEAM.md`. User decisions: CC0 inputs
allowed (spec §14.2 amended), hybrid landscape, full scope. **Paused by the
user at 18:50**; all agents stopped, locks released, playtest stopped.
Every milestone below was reviewed (diff + before/after images) unless
marked otherwise. Briefs, reports and reviews:
`.superpowers/sdd/FACELIFT_PLAN/` (git-ignored).

### Done (reviewed)
- **Phase 0 – QA tooling:** six beauty cameras × five times of day,
  capture/compare/grayscale tools (`tools/qa/BEAUTY.md`), LOS and ground
  checks, perf probe, baseline `qa/beauty/p0-baseline/`,
  `docs/ART_BIBLE.md`, `docs/PERF_BUDGET.md`.
- **Phase 1 – environment (ENV-1, ENV-2):** custom PBR MaterialVariants for
  every terrain material (CC0-based, credited), macro variation, painted
  skyboxes per preset with clouds; mesa, rear/flank/far walls and four
  buttes rebuilt as strata meshes over the unchanged gameplay terrain
  (LOS and lane ground heights identical to baseline).
- **Phase 2 – lighting (LOOK-1):** `LightingRig`, re-keyed presets with
  written intents, day-for-night Night, dusk lit by its lamps, grading and
  bloom per preset, gunsight depth of field and vignette, heat haze,
  dusty searchlights, pit lamp.
- **Phase 3 – emplacement (HS-1, HS-2, HS-4):** worn burlap sandbags,
  chipped OD gun, brass belt, stencils, camo net; belt feed, ejected brass,
  barrel heat glow, net ripple, antenna sway; 3D gunsights; turret gun
  assembly rebuilt from high-poly bakes.
- **Phase 4 – vehicles (HS-3..5):** shared trim sheets and high→low bake
  tooling; tank, buggy, helicopter, jet and Siege Crawler rebuilt; torn
  weak-point sockets; burnt wreck textures; distance LOD.
- **Phase 5 – infantry (CHAR-1, CHAR-2):** one skinned soldier (3 gear
  variants, LOD) animated by bones: walk, aim sway, throw, two deaths.
- **Phase 6 – VFX (VFX-1..3):** Blender-rendered flipbooks, layered
  explosions, surface-aware impacts, textured Beam tracers, muzzle flashes,
  backblast, motion dust, particle LOD. No built-in particle textures left.
- **Phase 7 – UI (LOOK-2):** worn-metal 9-slice HUD kit, animated bars,
  radar sweep, banner/tally/damage motion; player list hidden.
- **Phase 8 – motion (LOOK-3):** client root smoothing, vehicle bob/roll,
  heli lean, jet bank, moving treads, camera kick/sway/look-lag (aim stays
  exact). One open item below.

### Stopped mid-flight (not reviewed)
- **ENV-3 road/wash edges + ground dressing:** first version committed
  (`2081f8a`); a further iteration (dressing/strip re-publish, shadow range
  in `GroundDressing.luau`) is **uncommitted** in the working tree.
- **LOOK-4 weapon icons + title key art:** just started; new scripts in
  `tools/ui/` are **untracked**, `tools/ui/publish_look.py` modified; no
  commits.
- **LOOK-3 fix round 2:** the 0.5 s `EnemyMotion` re-check sweep walks every
  tracked model's descendants (likely cause of 0.15 → 0.30 ms, one 3 ms
  frame); make it event-driven and measure. Not started.

### Still planned
- Finish and review ENV-3 and LOOK-4 (weapon icons, title key art, logo).
- **Phase 9 / QA-9:** authoritative perf pass (texture memory measured
  241–256 MB vs ~250 MB budget; wave-9 GPU 6.05 ms vs 6 ms limit), full
  10-wave playthrough, final beauty set vs baseline, "Roblox-tell"
  checklist, readability, and the carry-over checks listed in
  `.superpowers/sdd/FACELIFT_PLAN/briefs/QA-9.md` (restore the Studio
  viewport width first — it was narrowed to ~896 px).

### Lead rulings (details in the SDD ledger)
Parallel workstreams on one branch with file ownership; headless Blender
only; no in-game change before the baseline; backblast dust to VFX; turret
gun pass added to HS-4; perf headroom split confirmed; accepted trade-offs:
far-wall/butte texel density, aircraft 21–26 px/stud, Crawler 12–18 px/stud,
+2–5 MB burnt-wreck maps; headshot bug and lag compensation left for the
user (gameplay, not visual).

## Known bugs / gaps
- **No lag compensation on server hitscan** (found 2026-09-26 by the Look
  agent): at ~100 ms latency, MG shots at a moving buggy's centre hit
  ~25% of the time. Pre-existing and unchanged by the face-lift's client
  smoothing; a netcode/gameplay change that needs a user decision.
- **Headshots never register on infantry** (found 2026-09-26 by the
  Character agent; pre-existing since the Blender infantry landed): the
  padded leg hit boxes enclose the `Head` box, so the MG 2× headshot never
  applies. Left as-is during the visual-only face-lift because balance was
  tuned without headshots; needs a user decision.
- Real mouse play and audio not yet checked by a human (see DONE.md).
- Wash/road material edges show 4-stud voxel steps (Roblox terrain limit).
- The Mac display idles when unattended, pausing Studio rendering; a
  12 h `caffeinate -d` assertion is running and playtests run
  `caffeinate -u` first.

## Last successful playtest
- Face-lift: each milestone was playtested in its own area (live waves,
  boss wave 10, all screens), but **no full 10-wave run has been done on
  the face-lifted build yet** (planned in QA-9).
- 2026-09-26: fresh-start 10-wave run to victory (15.7 min, no errors),
  then Play Again, Retry Wave and Restart verified.

## Next planned task
- Resume the face-lift: ENV-3 review, LOOK-3 fix round 2, LOOK-4, then QA-9.
- Human playtest for aim feel, audio mix and difficulty.
