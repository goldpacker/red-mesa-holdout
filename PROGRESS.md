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
**Update 2 is complete** (2026-09-27): airdrop arrivals, a cinematic-realistic
environment, daylight only, and the wave and boss retune. All 17 milestones
of `docs/AIRDROP_ENVIRONMENT_PLAN.md` (plus the follow-ups AD-4, LOOK-6 and
LOOK-7) are built and reviewed. Summary and final QA are in `DONE.md`; the
ledger with every lead ruling is in `.superpowers/sdd/AIRDROP_ENVIRONMENT_PLAN/`.
The face-lift (phases 0–8) finished earlier and is summarised in `DONE.md`.

**Now:** release, on the user's instruction (2026-09-27), which overrides the
earlier "never publish / never push" rules:
- push to the new public GitHub repo `goldpacker/red-mesa-holdout` (both
  branches; default = `opus-5.5-run-01`);
- publish to Roblox as **Red Mesa Holdout**, private first, then public
  after the user's real-client playtest and the maturity questionnaire.
Listing art and text are in `assets/listing/`.

**Release status (2026-09-27, 10:33):**
- **GitHub:** https://github.com/goldpacker/red-mesa-holdout. Public, both
  branches, default `opus-5.5-run-01`.
- **Roblox:** published **private** as a new experience "Red Mesa Holdout"
  (Place 81446709679456, Universe 10768349365). Name, description and
  Computer-only devices are set from Studio. Team Create and Data Sharing
  are off.
- **Left for the user on Creator Hub** (Studio no longer edits these):
  - icon (`assets/listing/icon.png`);
  - thumbnails (`assets/listing/thumb_1..4_*.png`);
  - **server size 1** (single-player game);
  - the maturity questionnaire;
  - a real-client playtest;
  - then Public.

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
- Publish (GitHub, then Roblox private → public).
- Human playtest for aim feel, audio mix and difficulty.
