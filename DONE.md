# DONE — Red Mesa Holdout

Single-player Roblox arcade defense shooter built to `GAME_SPEC.md`: hold a
three-weapon gun emplacement on a red-rock mesa against 10 escalating waves
of infantry, buggies, tanks, helicopters and jets, ending with the Siege
Crawler boss.

## What was built

- **Flow:** title (controls card, panning camera, loading gate) → Start →
  10 waves with banners, intermission tally (score, clear + integrity
  bonus, 25% repair, resupply, next-wave preview, countdown) → victory
  (boss wreck, flare volley, stats, Play Again) or defeat (emplacement
  explodes and burns, camera pulls out, stats, Restart / Retry Wave from a
  wave-start checkpoint).
- **Turret:** mouse-locked aim over a 270° arc, third-person camera that
  orbits with pitch, hold-RMB gunsight per weapon; weapons switch with
  1/2/3 and the wheel with visible turret poses.
- **Weapons (server-authoritative):** machine gun with heat/overheat,
  tracers, sparks and ricochets on armour; rockets (8/wave, reload, splash,
  travel time); AA missiles (4/wave, ~1 s lock-on on aircraft only,
  homing); ammo restock at intermissions; supply crates add ammo/repair.
- **Enemies:** infantry (rifles, grenades at the mesa foot), buggies
  (wash runs, strafing), tanks (telegraphed shells, ~2 rockets), helicopters
  (rise from canyon walls, rocket salvos), jets (siren + warning, bombing
  runs), Siege Crawler (two turrets + charged main cannon as rocket weak
  points, exposed core, escorts, rocket crates, multi-stage death). All
  wreck/topple on death; wrecks persist until the intermission.
- **HUD:** integrity, weapon strip (ammo, heat, reload, lock state), wave /
  score / pulsing combo (×1–×4), radar with ground/air blips, off-screen
  threat arrows, jet warning, boss bar, cannon-charge warning, hit and kill
  markers, score popups, directional damage indicators, low-integrity
  vignette + alarm, first-encounter tips, crate notices.
- **World:** generated terraced mesa, eroded buttes and canyon walls,
  dunes, washes, road, terrain boulders + Blender rock kit, searchlight
  towers; time of day afternoon → sunset → dusk → night with tweened
  transitions, night flares and sweeping searchlights.
- **Art (grounded semi-realistic, spec §13):** Blender hero assets with
  PBR textures — Emplacement/turret, Infantry, Tank, Buggy, Helicopter,
  Jet, Siege Crawler, SupplyCrate, rock/cliff kit — uploaded privately via
  Open Cloud (ids in `docs/ASSET_STATUS.md`); primitive fallbacks remain in
  code.
- **Audio:** 36 original synthesized effects (`tools/audio/synth.py`) in one
  uploaded sound sheet (asset 70797639407728) played as regions; every
  sound fails silently.
- **Tooling:** Rojo project, `tools/check.sh`, Studio lock, QA bots
  (`tools/qa/`), Studio-only debug hooks.

Built by a lead plus Weapons, Enemies and Assets agents; contracts in
`docs/ARCHITECTURE.md` and `docs/ASSET_CONTRACTS.md`.

## Final playtest result (2026-09-26, Roblox Studio)

- **Fresh-start end-to-end run on the final code:** title → START (real
  button click) → waves 1–10 → Siege Crawler destroyed → victory in 15.7
  min, score 34,090; 211 infantry, 23 buggies, 10 tanks, 14 helicopters,
  12 jets, 1 Siege Crawler. No defeats, no game errors or warnings in the
  console. Driven by the QA bot (`tools/qa/autoplay_full.client.luau`,
  perfect-aim settings).
- **After victory:** PLAY AGAIN → wave 1, integrity 100, score 0, ammo
  restocked, wrecks cleared, afternoon lighting, session best kept.
  Forced defeat → RETRY WAVE restored the checkpoint; forced defeat →
  RESTART began a fresh run.
- **Difficulty sampling** with a handicapped "human-like" bot (aim error,
  reaction delay, bursts): waves 1–9 clear on the first attempt after
  tuning (waves 8–9 end around 40–50% integrity); the boss usually takes a
  retry or two. Balance changes are in the git history.
- **Visual inspection** (screenshots in `qa/screenshots/`): title, HUD in
  combat, gunsight, intermission tally, jet warning + AA lock, rocket
  launch, boss bar, sunset, dusk, night, defeat, victory; terrain, rock kit
  and all enemy assets.

## Known remaining issues

- **Real mouse play is unverified.** All firing in tests used Studio debug
  attributes; aim feel and sensitivity should be checked by a human.
- **Audio untested by ear.** The sheet loads in Studio (80.8 s); it was
  still in Roblox moderation review at upload time.
- **Difficulty** was tuned against bots, not people; the boss fight is
  deliberately hard.
- Wash/road material edges show 4-stud voxel steps (Roblox terrain limit).
- Enemy vehicles move by anchored CFrame updates without client smoothing;
  fast jets may look slightly steppy on a real network connection.
- Particle effects use Roblox's built-in textures.
- The Open Cloud API key was pasted in chat; rotate it.

## Final Git commit

`de23177` — last code change (Siege Crawler balance). `DONE.md` and the
final screenshots are committed on top of it.

---

# Face-lift and Update 2 (2026-09-26 → 27)

## What was built
- **Visual face-lift** (`docs/FACELIFT_PLAN.md`, phases 0–8):
  - custom PBR terrain materials and painted skyboxes;
  - strata landscape meshes for the mesa, walls and buttes;
  - re-keyed lighting;
  - a hero pass on the emplacement and turret;
  - hard-surface rebuilds of every vehicle and the Siege Crawler, with burnt
    wrecks and LOD;
  - skinned, bone-animated infantry;
  - rendered flipbook effects;
  - a textured HUD kit;
  - client motion smoothing.
- **Update 2** (`docs/AIRDROP_ENVIRONMENT_PLAN.md`, user feedback):
  - Infantry, buggies and tanks **parachute in** from untouchable
    transports. They are invincible in the air, land 300–800 studs out and
    join their lanes. There is a HUD banner, radar marks and sounds.
  - Waves were retuned for the new arrivals, including the boss wave.
  - A lived-in battlefield: ground cover, tyre tracks, power poles, a
    weathered checkpoint.
  - Depth haze, sun shafts and a film treatment.
  - Wind, sand streamers, dust devils, wreck smoke, birds, and dust storms
    on waves 3 and 7.
  - New title key art and weapon icons.
  - **Daylight only** (user decision): afternoon, late afternoon, sunset.
  - Roblox listing art in `assets/listing/`.

## Final playtest result (QA-F, commit 33f37c4; boss retune AD-4 after)
- **Full fresh-start run:** victory in 16.4 min with 0 retries and a clean
  console. Play Again, Retry Wave and Restart work.
- **Airdrops:** 233 of 233 ground enemies arrived by drop, landing 367–800
  studs out, with no hand-off pops, none stuck and 0 drop-zone violations.
- **LOS and ground:** LOS to every lane end passes; ground heights are
  identical to the original build.
- **Readability:** every enemy is ≥ 3:1 at engagement range at all
  presets and storm peaks.
- **Performance:** busy wave 9 (Sunset) 5.74 ms GPU against a 6 ms working
  limit. The boss wave is ~6.0–6.3 ms, within measurement noise. Game-owned
  textures are 130 MB by the budget model.
- **Boss (AD-4, human-like bot):** 5 of 5 seeds won within ≤ 2 retries
  (0/0/0/1/0), with the lowest integrity between 7 and 49%.
- **Final beauty set:** `qa/beauty/final/` against `qa/beauty/p0-baseline/`.

## Known remaining issues
- Headshots don't register on infantry, and hitscan has no lag
  compensation. Both are pre-existing gameplay issues awaiting a user
  decision.
- Real mouse aim feel and the audio mix still need a human playtest; the
  first real-server play follows publishing.
- Cosmetic, logged in the Update 2 ledger:
  - the storm wall reads as a dust band;
  - streamers and dust devils are subtle from the gun;
  - a faint warm haze lingers ~4 s after a storm clears;
  - there is no scrub sway or wire flutter.
