# GAME_SPEC.md — Red Mesa Holdout

## 1. Overview

**Red Mesa Holdout** is a single-player Roblox arcade defense shooter. The player mans a fixed, multi-weapon gun emplacement on top of a red-rock mesa and must survive **10 escalating waves** of combined-arms enemy forces — infantry, fast buggies, tanks, helicopters, and jets — culminating in a boss assault by a giant armored **Siege Crawler**.

It is an original reinterpretation of the *feeling* of classic early-2000s PC "fixed-position defense" arcade games (inspired by Beach Head 2000). It must not reuse or imitate any of that game's assets, names, maps, UI, sounds, or music.

**Scope:** a small, highly polished vertical slice. One battlefield, three weapons, five enemy types plus one boss, ten waves, roughly **15 minutes** for a complete successful run.

**Platform:** PC, keyboard + mouse. Single player.

---

## 2. Design Pillars

1. **Threat prioritization is the game.** At almost every moment the player should be asking "what kills me first?" — the close infantry, the tank about to fire, or the jet starting its bombing run.
2. **The right tool for the job.** Each weapon has a clear purpose. Switching weapons at the right moment is the core skill.
3. **Distance is a countdown.** Every enemy is harmless far away and dangerous once it reaches its attack range. The player can read urgency by looking at the battlefield.
4. **The front is wider than your view.** The player cannot see everything at once and must sweep the battlefield, supported by radar and off-screen warnings.
5. **Arcade spectacle.** Weapons feel powerful, destruction is satisfying, and the battlefield visibly fills with fire, smoke, and wrecks as a wave escalates.
6. **Readable chaos.** Late waves are intense, but the player can always tell what each threat is and where it is.

The target emotional rhythm of every wave:

> quiet battlefield → distant enemies appear → threats close in → combat escalates → chaos → barely survive → brief relief → next wave

---

## 3. Game Flow

1. **Title screen** — game title, a Start button, and a single compact controls card. The battlefield is visible behind it (e.g. slow camera pan over the mesa).
2. **Wave loop (×10)** — a short "WAVE N · <threat hint>" banner, the wave plays out, then a "WAVE CLEAR" intermission (~10–15 s) showing the wave score tally, repair, resupply, and a preview of the next wave.
3. **Victory** — after the Siege Crawler is destroyed and wave 10 ends: an unmistakable victory sequence (big boss explosion, celebratory banner, final stats). Offers **Play Again** (fresh run from wave 1).
4. **Defeat** — when Outpost Integrity reaches 0: the emplacement is destroyed, the camera pulls back over the burning mesa, "OUTPOST LOST" banner, wave reached and stats. Offers:
   - **Restart** — fresh run from wave 1.
   - **Retry Wave** — restart the wave the player died on, with integrity, ammunition, and score restored to what they were at the *start* of that wave (a checkpoint).

The player never needs to walk anywhere or perform any setup: pressing Start puts them directly in control of the emplacement. No developer intervention is ever required for normal play.

---

## 4. Camera, Controls, and Aiming

### Camera

A hybrid camera:

- **Default view — third-person:** positioned behind and above the turret. The player sees their gun, its recoil, and the emplacement taking hits, with a wide view of the battlefield for situational awareness.
- **Aim view — hold right mouse button:** snaps into a first-person gunsight with a weapon-specific sight overlay (e.g. machine-gun iron sight, rocket scope, anti-air lock reticle). Narrower field of view and reduced mouse sensitivity for precise long-range shots.

### Traverse

- The mouse directly controls turret aim with a locked cursor and a center-screen crosshair.
- Aim response must feel immediate. The visible gun model may lag very slightly behind the aim for a sense of weight, but the actual aim point must not.
- Horizontal traverse covers roughly **270°**. The rear of the position is protected by terrain (e.g. the back of the mesa/cliff) and traverse stops there. Enemies never attack from outside the traversable arc.
- Vertical aim ranges from slightly below the horizon (to hit ground targets at the foot of the mesa) up to steep angles (to engage aircraft).

### Controls

| Input | Action |
|---|---|
| Mouse | Aim |
| Left mouse | Fire |
| Right mouse (hold) | Aim view / gunsight |
| 1 / 2 / 3 | Select Machine Gun / Rockets / AA Missiles |
| Mouse wheel | Cycle weapons |

Reloading is automatic. Controls should be discoverable from the title screen controls card and contextual tips; no separate tutorial level.

Gamepad and mobile support are out of scope.

---

## 5. Weapons

Three weapons, all mounted on the same emplacement. The currently selected weapon should be visibly distinguishable on the turret model (e.g. the active weapon raises/rotates into position, or the gunsight changes), and switching should be quick (well under a second).

The rule players should learn within seconds: **machine gun for small targets, rockets for tanks, missiles for anything flying.** Interesting decisions come from the edges of that rule.

### 5.1 Machine Gun (slot 1)

- **Role:** general purpose — infantry and buggies; can slowly wear down a helicopter in an emergency. Nearly useless against tanks (visible sparks/ricochets, negligible damage) and the boss.
- **Resource:** unlimited ammunition but **overheats** under sustained fire. Heat builds while firing and dissipates when not firing. At maximum heat the gun locks briefly (~2 s) while it cools, with clear audiovisual feedback (steam, warning tone, heat bar flashing).
- **Feel:** high rate of fire, heavy punchy sound, muzzle flash, glowing tracers, visible impact puffs on terrain, sparks on metal, recoil/shake on the gun.
- **Ballistics:** effectively instant hit along the aim line with visible tracers. No bullet drop. What you aim at is what you hit.

### 5.2 Rockets (slot 2)

- **Role:** anti-armor. The intended counter to tanks and the Siege Crawler's weak points. Splash damage can clear a cluster of infantry (tempting, but wasteful). Can hit a buggy with a well-led shot, or a hovering helicopter.
- **Resource:** limited — approximately **8 rockets per wave**, fully restocked during each intermission. Short reload between shots (~1.5 s). Supply crates can add more mid-wave.
- **Feel:** visible projectile with a smoke trail and noticeable (but fast) travel time, so fast targets need to be led. Big explosion on impact with screen shake appropriate to proximity.

### 5.3 AA Missiles (slot 3)

- **Role:** anti-air. The intended counter to helicopters and jets. Cannot lock onto ground targets.
- **Lock-on:** the player keeps an aircraft near the crosshair for roughly one second to acquire a lock, with a rising tone and a lock box that tightens on the target. Once locked, firing launches a homing missile.
- **Resource:** limited — approximately **4 missiles per wave**, fully restocked during each intermission. Supply crates can add more.
- **Feel:** distinct launch sound, bright exhaust trail, satisfying mid-air explosion with falling wreckage.

Exact numbers are tuning values. The requirement is that rockets and missiles feel **valuable** — the player should sometimes have to decide whether a target deserves one — while never leaving a well-playing player unable to deal with the threats of a wave.

There is no special/emergency weapon.

---

## 6. Enemies

Five enemy types plus one boss. Each must have a **distinct silhouette, color-readable against the terrain, and a clear gameplay identity**. Each is harmless at long range and dangerous once it reaches its attack range, and its attacks should be telegraphed clearly enough that the player can react.

| Enemy | Identity | Threat | Intended counter |
|---|---|---|---|
| **Infantry** | Numerous, weak soldiers advancing across open scrub and rocks, often in groups. Die in one or two machine-gun hits. | Light chip damage with rifles from mid range. If they reach the base of the mesa, they throw grenades for substantially higher damage — ignoring them must be dangerous. | Machine gun |
| **Buggy** | Fast, light attack vehicle weaving up the dry riverbeds on the flanks. | Reaches its attack range quickly, then circles or strafes at mid range with a mounted gun, dealing steady damage. | Machine gun burst, or a well-led rocket |
| **Tank** | Slow, heavily armored, large. | Advances to a firing position and fires heavy shells every several seconds. Each shot is telegraphed (turret aims, muzzle flash) and deals heavy damage. | Rockets (about two to destroy). Machine gun should be ineffective. |
| **Helicopter** | Rises from behind the canyon walls on the flanks and hovers or repositions at mid range, often to the side of the player's current view. | Periodic rocket salvos. | One AA missile, or a long machine-gun burst |
| **Jet** | Very fast. Appears down the canyon for a bombing run with a short engagement window. | Announced by a siren and warning indicator. If not destroyed before reaching its release point, it drops bombs that deal heavy damage. | One AA missile with a quick lock |

Destroying any enemy should be satisfying: infantry fall and ragdoll or topple, vehicles explode into burning wrecks, aircraft break apart and crash with smoke trails. Wrecks and scorch marks remain on the battlefield for the rest of the wave and are cleared during the intermission.

Enemies must never get permanently stuck, spawn inside terrain, or remain alive out of reach in a way that prevents a wave from ending.

### 6.1 Arrival by airdrop

Ground forces don't appear out of nowhere at the far end of the basin. **Infantry, buggies and tanks are air-dropped** from enemy military transport aircraft that fly over the battlefield, which adds uncertainty about where the next threat will land.

- **Transports:** an original four-engine military cargo aircraft in the enemy palette flies across the basin at high altitude. It opens its rear ramp over the drop zone and releases its load in a stick: paratroopers jump one after another, and vehicles roll out on drop platforms under a cluster of cargo parachutes. Transports can't be targeted or damaged, and they never fly over the player's mesa.
- **Drop zone:** loads land scattered across the whole basin width, on open basin floor **300–800 studs from the outpost** (never on cliffs, buttes or the mesa slope). Where the next group lands varies from wave to wave and from run to run.
- **Invincible in the air:** paratroopers and dropping vehicles can't be damaged until they touch down. Shots at them show a clear "no effect" response (tracers pass through or spark off; no hit marker, no score), and they can't be locked by AA missiles.
- **Landing:** the canopy collapses and drapes on the ground, dust kicks up, and the soldier or vehicle joins the nearest approach lane and advances toward the mesa as before. Vehicles unhook from their platform and drive off.
- **Readability:** the player sees transports crossing the horizon and chutes blossoming before anything can attack. The HUD announces incoming drops and marks them on the radar.
- **Unchanged:** helicopters and jets fly in as before. The Siege Crawler grinds in from the far end of the road as the boss entrance; its infantry escorts arrive by air.

### 6.2 Boss — The Siege Crawler (wave 10)

A huge multi-turreted armored land fortress that grinds slowly up the central road. It should be the single largest and most impressive object in the game.

- **Weak points:** two side turrets and a heavy main cannon, each destroyed with rockets (machine gun ineffective). Each destroyed weak point visibly breaks off or bursts into flames.
- **Main cannon:** fires a devastating shot after a long, clearly visible charge-up (glow, sound build-up, warning indicator). This teaches the player to prioritize it.
- **Core:** once all three weak points are destroyed, the exposed core can be destroyed with rockets to kill the boss.
- **Escorts:** air-dropped infantry, helicopters, and jets continue to attack during the fight so all three weapons remain relevant.
- **Anti-softlock:** extra supply crates (weighted toward rockets) drop during the fight so the player cannot become permanently unable to damage the boss.
- **Death:** a multi-stage explosion sequence that is the biggest spectacle in the game, flowing directly into the victory state.

The boss should have a visible health/progress indicator (e.g. a boss bar showing remaining weak points and core).

---

## 7. Battlefield — The Red Mesa

One polished battlefield in a desert canyon basin.

- **Player position:** a sandbagged emplacement on top of a red-rock mesa, overlooking a wide basin below. Elevation makes distances easy to read.
- **Rear:** protected by the mesa/cliffs; no attacks come from behind.
- **Approach lanes** (layout is at the developer's discretion, but the battlefield should offer recognizably distinct routes):
  - A central dusty road winding toward the mesa — the main route for tanks and the Siege Crawler.
  - Dry riverbeds or washes on the left and right flanks — fast routes for buggies.
  - Open scrub and rock cover between lanes — infantry advance routes.
  - Canyon walls on the flanks — helicopters rise from behind them.
  - A long canyon axis — jets make their runs along or across it.
- Enemies must appear far enough away to be spotted, become identifiable, and approach, creating rising urgency. Ground forces arrive by airdrop (§6.1): transports cross the horizon, chutes open over the basin, and loads land 300–800 studs out before advancing along the lanes.
- The environment should support situational awareness: clear sightlines, strong color contrast between enemies and terrain, limited clutter.

### 7.1 Time of Day Progression

All ten waves are played in **bright afternoon** light (user decision, 2026-09-27, after playtest: late afternoon and sunset lost too much visual quality on the player's machine). Warmer late-afternoon and sunset presets may return once a performance solution keeps their fidelity; until then the escalation comes from the enemies, the airdrops and the storms, not the light.

Transitions happen during intermissions (or smoothly during them), never in a way that makes enemies hard to see.

---

## 8. Waves

Ten waves, each roughly **60–120 seconds**, with an intermission of roughly **10–15 seconds**. A complete successful run should take about **15 minutes**.

Each wave should open quietly with the first transports crossing the horizon and build to a peak. Difficulty increases mainly through **combinations of threats, attack directions, and overlapping timing** — not by inflating enemy health.

| Wave | Time of day | Content | Purpose |
|---|---|---|---|
| 1 | Afternoon | Infantry, center lane | Learn aiming, machine gun, overheat |
| 2 | Afternoon | Infantry + buggies on the flanks | Traversing the arc; fast targets |
| 3 | Afternoon | First tanks + infantry. First supply crate. | Rockets; basic prioritization |
| 4 | Afternoon | First helicopters + infantry | AA lock-on; off-screen warnings |
| 5 | Afternoon | Mixed ground assault on all lanes | Juggling three ground threats |
| 6 | Afternoon | First jets + helicopters + infantry | "Look up now" reactions |
| 7 | Afternoon | Armored push: tanks with buggy escorts, plus jets | Rocket scarcity |
| 8 | Afternoon | Air assault: helicopters on both flanks, jets, infantry rush | Missile scarcity; machine-gun fallback |
| 9 | Afternoon | Full combined arms from every direction | Everything at once |
| 10 | Afternoon | Siege Crawler boss + escorts | Climax |

Exact compositions, counts, drop timing, drop points, and routes are at the developer's discretion, guided by this table. Waves are retuned after the airdrop change so difficulty stays as intended.

A wave ends when all of its enemies have been destroyed (or, for the boss wave, when the Siege Crawler is destroyed and remaining escorts are cleared or dismissed). Wave completion must be reliable and never hang.

### 8.1 Intermission

During the intermission:

- "WAVE CLEAR" banner and wave score tally.
- Outpost Integrity repairs by roughly 25% (capped at maximum).
- Rockets and AA missiles fully restock; machine-gun heat resets.
- Wrecks and battlefield debris are cleared.
- A preview of the next wave (e.g. "WAVE 7 · ARMOR INCOMING").
- A checkpoint is saved for Retry Wave.

### 8.2 First-Encounter Tips

The first time each enemy type appears, show a short contextual tip, e.g.:

- Tank: "Bullets can't stop armor — press **2** for rockets."
- Helicopter: "Air threat — press **3**, hold on target to lock."
- Jet: "Incoming jet! Lock and fire before it drops its bombs."
- First airdrop: "Paratroopers can't be hit in the air — pick them off when they land."

Tips should be brief, non-blocking, and not repeat after the player has seen them in the current session.

---

## 9. Health and Damage

- A single health value: **Outpost Integrity**, 0–100%. The player and the emplacement are one unit; there is no separate character health.
- Integrity carries over between waves (with partial repair during intermissions), so poor defense has lasting consequences.
- **Damage feedback must be unmistakable:**
  - directional damage indicators showing where damage came from
  - camera shake and debris on heavy hits (tank shells, bombs, boss cannon)
  - a flash or hit sound on every hit
  - a red low-integrity vignette below ~30%
  - an alarm below ~15%
- **Defeat** occurs at 0% integrity (see Game Flow).

---

## 10. Supply Crates

Occasionally during waves (starting in wave 3), a supply crate drifts across the basin under a parachute. Shooting it with any weapon collects its contents, with a clear pickup notification. Contents are one of:

- extra rockets
- extra AA missiles
- a small integrity repair

Crates are a tempting "divert fire for loot" decision. They should be clearly visible and identifiable (bright color, parachute), drift slowly enough to be hittable, and disappear if not collected. Extra crates drop during the boss fight (see 6.1).

---

## 11. Scoring

Simple arcade scoring the player understands immediately.

- **Kill points by threat value** (relative order must be kept; exact values are tunable):
  - Infantry 10
  - Buggy 50
  - Helicopter 100
  - Tank 150
  - Jet 200
  - Boss weak point 1,000
  - Boss kill 5,000
- **Combo multiplier:** kills in quick succession (within ~3 s of each other) raise the multiplier ×2 → ×3 → ×4 (max). It resets to ×1 after a gap without a kill. Taking damage does not reset it.
- **Wave-clear bonus:** a flat bonus per completed wave plus a bonus scaled by remaining integrity.
- **End screen stats** (victory and defeat):
  - final score
  - wave reached
  - kills by enemy type
  - accuracy
  - best combo
  - best score this session

  Accuracy is displayed but does not affect score.
- Floating score popups on kills are encouraged.
- No persistent leaderboards or cross-session saves.

---

## 12. HUD and UI

The player should spend nearly all their attention on the battlefield. The HUD is minimal, glanceable, and styled like an **early-2000s arcade military interface** — stencil/blocky military typography, amber and olive accents on dark translucent panels, subtle bevel or scanline touches. It must not look like a generic Roblox simulator UI.

Required elements (placement is a suggestion):

- **Weapon strip (bottom center):**
  - the three weapon slots, with the selected weapon highlighted
  - ammo counts for rockets and missiles
  - a heat bar for the machine gun
  - reload progress
- **Integrity bar (bottom left).**
- **Wave number, score, and combo multiplier (top).** The combo visibly pulses when it increases.
- **Threat radar (bottom right):** covers the 270° arc and shows enemy blips color-coded by category (at minimum ground vs air) relative to the current aim direction.
- **Off-screen threat indicators:** arrows at the screen edge pointing toward dangerous off-screen threats (e.g. enemies in attack range). Jets get a distinct urgent warning with a siren.
- **Crosshair:** changes per weapon; hit markers confirm hits; a distinct kill confirmation.
- **Lock-on indicator** for AA missiles (acquiring vs locked states).
- **Boss health indicator** during wave 10.
- **Large center banners** for wave start, wave clear, victory, and defeat.
- **Screens:** title, intermission tally, victory, defeat (with Restart and Retry Wave).

---

## 13. Visual Style

**Grounded semi-realistic.** The game should look like a decent, modern Roblox military shooter — believable hardware, weathered desert terrain, and cinematic lighting — while keeping arcade readability. Target: the best-looking military games on Roblox, not AAA photorealism. It must **not** look like a bulky, blocky, default-Roblox game.

- **Models:** custom meshes with realistic proportions and believable detail (panel lines, bolts, hatches, tracks, tread, bevelled edges). No visible stacked-primitive construction on anything the player looks at. Silhouettes stay distinct per enemy type through real design differences (tank vs buggy vs helicopter), not through exaggerated scale.
- **Materials:** PBR surfaces (color, normal, roughness, metalness via `SurfaceAppearance`) with wear — dust, chipped paint, scorch, grime. Avoid flat `SmoothPlastic` on hero objects.
- **Terrain:** custom terrain material variants (`MaterialService`) for sand, packed dirt road, layered sandstone, and rock, so the desert reads as real ground with visible strata and texture. Mesa and canyon walls use modeled rock meshes where Roblox terrain looks too smooth.
- **Scale:** real-world proportions (soldiers are human-sized). Readability at distance comes from contrast, silhouette, lighting (e.g. glints, headlights, rotor blur), and HUD support (radar, indicators) — not from oversizing.
- **Palettes:**
  - The player's outpost uses sand, tan, and olive drab.
  - The fictional enemy force uses dark gunmetal/charcoal with red markings and an original emblem.
  - Enemies must contrast strongly against the orange-red terrain.
- **Lighting:** Roblox Future lighting with shadows, atmosphere, a proper sky, bloom, sun rays, and per-time-of-day color grading. Lighting is tuned per scene, not left at defaults.
- **Effects:** particle-based and grounded — layered fireballs, sparks, dust kicks, thick smoke columns, heat shimmer where cheap, bright tracers, muzzle flashes, debris, and decals for scorch marks. Punchy enough for arcade satisfaction without cartoon shapes. Screen shake used with restraint and scaled to proximity/intensity.
- **Environment — cinematic realism:** the models are good enough; further visual effort goes into the overall environment. Reference: the desert maps of modern military shooters (Battlefield, Call of Duty): crisp detail, strong contrast, a lived-in battlefield, and clean, readable combat spaces. Priorities, in order:
  1. **Atmosphere and light:** haze with real depth layered through the basin, sun shafts through dust, heat shimmer, a dramatic sky at every time of day, and a restrained film treatment (subtle grain and lens response).
  2. **Ground realism:** no bare, repeating sand anywhere the camera looks. Dense, varied ground cover (scrub, rocks, pebbles), tyre tracks, old craters, eroded wash banks and road edges, and signs of an ongoing conflict and past habitation (burnt-out vehicle hulks, barriers and wire, power poles, a ruined roadside compound), kept off the lanes.
  3. **Weather and life:** wind-blown sand streaming over the ground, dust devils, smoke drifting from old wrecks, birds, and occasional dust storms rolling through on some waves.
  Weather, haze and dressing never hide an enemy at its engagement range or cover the HUD, and the performance budget stays at 60 fps on a mid-range PC at graphics level 8 with about 250 MB of texture memory.
- **Consistency:** vehicles, weapons, environment, effects, and UI must look like they belong to the same game.

No assets, logos, emblems, or names from Beach Head 2000 or any other existing game may be used or imitated.

---

## 14. Assets

### 14.1 Hero assets (custom-built in Blender)

These carry the game's visual identity and should be modeled in Blender via Python/CLI, with sources saved to `assets/blender/`, exports to `assets/exported/`, and rendered previews to `assets/previews/`. Each ships with PBR textures and a reasonable triangle budget for Roblox:

1. **Player emplacement and turret:** a single mount carrying all three weapons (machine gun, rocket pod, AA missile rack), with sandbagged/fortified surroundings.
2. **Tank.**
3. **Buggy.**
4. **Helicopter** (with a rotor that can spin).
5. **Jet.**
6. **Siege Crawler**, with its weak points as separable parts so they can be destroyed individually.
7. **Mesa rock formation kit** — modular rock/cliff meshes for the mesa, canyon walls, and scattered boulders.
8. **Infantry soldier:** a human-proportioned soldier animated procedurally from code (march, aim, throw, die): either split into limb meshes (head, torso, arms, legs, rifle) on Motor6D joints, or one skinned mesh whose bones are posed with `Bone.Transform`. No animation upload pipeline required.
9. **Transport aircraft:** an original four-engine military cargo plane with a rear loading ramp that opens, in the enemy palette with red markings and the emblem.
10. **Parachutes and drop platform:** a personnel canopy (deploying, open and collapsed states), a cargo-chute cluster, and a drop platform for buggies and tanks.

### 14.2 Non-Blender assets

- **Terrain:** Roblox terrain for the basin floor, roads, and riverbeds, using custom PBR material variants.
- **Small props:** sandbags, barriers, crates, parachutes, wreck debris, searchlights, and environment dressing (scrub, rocks, burnt-out hulks, wire, power poles, ruined walls) — simple meshes with textures (primitives acceptable only for tiny or distant details).
- **Textures and particles:** original or generated textures; particle flipbooks for fire, smoke, dust, and sparks.

All assets must be original. CC0 (public-domain) source material, such as Poly Haven textures and HDRIs, may be used as raw input when it is substantially modified and baked into the game's own assets; every such source is credited in `assets/source/CC0_CREDITS.md`. Free assets owned by Roblox may be used where they fit the style. Paid assets may not be used.

---

## 15. Audio

Sound reinforces gameplay. Use only free Roblox-provided audio (e.g. from the Creator Store at no Robux cost) or original, self-generated sounds. No copyrighted or paid audio. **Every sound must fail gracefully:** a missing or unavailable sound must never break gameplay.

Priority order:

1. **Weapon sounds:**
   - machine-gun fire
   - overheat warning and lock
   - rocket launch
   - missile launch
   - lock-on tones
   - empty/reload feedback
2. **Explosions and impacts:** vehicle destruction, aircraft destruction, ricochets on armor.
3. **Threat cues:**
   - jet siren and flyover
   - helicopter rotors
   - tank engine and cannon
   - Siege Crawler main-cannon charge-up
   - transport aircraft drone, ramp opening, parachute deploy, landing thuds
4. **Feedback:**
   - taking damage
   - low-integrity alarm
   - wave start stinger
   - wave clear
   - supply crate pickup
   - victory and defeat
5. **Ambience and music (optional):** wind, blowing sand, distant battle, a tension track.

---

## 16. Technical and Product Requirements

- The game launches directly into a functional, playable experience (title screen → Start → wave 1).
- Important gameplay logic is **server-authoritative** where appropriate:
  - enemy spawning
  - enemy health and destruction
  - damage to the outpost
  - wave progression
  - scoring
  - victory/defeat
  - crates

  Presentation (camera, HUD, effects, sounds) may be client-side.
- Wave progression, spawning, and completion are reliable and never require manual intervention.
- Enemies are cleaned up correctly on death, at wave end, on restart, and on retry. No leaks or orphaned enemies/effects accumulating over a full run.
- Restart and Retry Wave both return the game to a clean, correct state.
- No critical runtime errors in the console during a normal full playthrough.
- Performance remains smooth during the busiest waves (limit simultaneous effects/debris as needed).
- Built as a single-player experience. If multiple players join the same server, the game does not need to support them properly, but should not crash.

---

## 17. Restrictions

- Do not publish the experience publicly.
- Do not spend Robux or purchase paid assets or services.
- Do not copy, extract, or imitate assets, music, sounds, maps, UI, models, textures, or names from Beach Head 2000 or other copyrighted games.
- Do not modify unrelated Roblox experiences or cloud assets. Do not interact with production experiences.
- Do not require external paid services.
- Keep all project source assets and scripts organized within this project.

---

## 18. Out of Scope

- Multiplayer or co-op
- Gamepad or mobile controls
- Multiple maps or emplacements
- Upgrades, shops, currencies, unlocks, or meta-progression
- Persistent saves or leaderboards
- Special/emergency weapons beyond the three defined
- Additional enemy types or elite variants beyond those defined

---

## 19. Definition of Done

The game is **not** done just because the systems and assets exist. It is done when all of the following are verified in Roblox Studio playtests:

From a fresh game session, the player can:

1. Launch and see the title screen with controls; press Start and enter the emplacement.
2. Understand the controls and battlefield state from the HUD and tips.
3. Begin wave 1.
4. Aim and fire the machine gun, with tracers, impacts, and hit feedback; experience overheat.
5. Fight all five distinct enemy types across the waves, each behaving per its identity.
6. Switch weapons when threats require it — rockets destroy tanks, AA missiles lock onto and destroy aircraft.
7. Take damage with clear directional feedback, and see enemies clearly destroyed.
8. Collect at least one supply crate.
9. Complete successive waves with working intermissions (tally, repair, resupply, preview), and see the waves escalate.
10. Experience increasing combined-arms pressure from multiple directions.
11. Destroy the Siege Crawler's weak points and core in wave 10.
12. Reach an unmistakable victory state, and start a fresh run with Play Again.

Additionally:

- **Defeat** works correctly when integrity reaches 0, and both **Restart** and **Retry Wave** return the game to a clean, correct state.
- All major screens (title, HUD in combat, intermission, victory, defeat) and all battlefield areas and times of day have been visually inspected via screenshots.
- There are no known critical runtime errors.
- A final complete end-to-end playthrough from a fresh start has succeeded.
