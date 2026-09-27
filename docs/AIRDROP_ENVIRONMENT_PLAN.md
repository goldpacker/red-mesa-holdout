# Airdrop Arrivals and Cinematic Environment — Plan

User feedback (2026-09-26), now in `GAME_SPEC.md` §6.1, §7, §8, §13–15:

1. **Airdrop arrivals.** Infantry, buggies and tanks parachute in from
   enemy transport aircraft instead of appearing at the far end of the
   basin. They are invincible in the air and land scattered across the
   basin, 300–800 studs from the outpost. Transports are untouchable.
2. **Cinematic environment.** Visual effort moves from individual models to
   the overall environment. The reference is modern military shooter desert
   maps. Priorities: atmosphere and light, ground realism, weather and life.
   The performance budget stays the same.

**Decision update (2026-09-26, 23:10): daylight only.** Night and dusk are
removed to keep the busiest waves inside the GPU budget. Waves 1–3 run in
afternoon, 4–6 in late afternoon, 7–10 in sunset (spec §7.1). Night-only
work in this plan is dropped: load lights, searchlight dust, night
readability tuning, and the Dusk/Night skies. The searchlights and flares
are retired.

User decisions from the interview:
- Everything that drives or walks is dropped; the Siege Crawler still
  drives in.
- Transports can't be shot.
- The drop zone is the mid-to-far basin.
- Shots at airborne loads show a visible "no effect".
- Environment priorities are atmosphere & light, ground realism, and
  weather & life (not distant vistas).
- The look reference is a modern military shooter.
- The budget stays at 60 fps mid-range / ~250 MB.

Lead calls where the interview left no answer (reversible; tell me if you
disagree):
- **Headshots and lag compensation:** stay out of scope; they are still
  open decisions in `PROGRESS.md`.
- **Unfinished face-lift work:**
  - The ENV-3 road/wash edges and ground dressing fold into the
    environment track.
  - The small motion-performance fix (LOOK-3 round 2) is done first.
  - Weapon icons and title key art (LOOK-4) move to the end, so the key art
    shows the new environment and airdrops.

---

## 1. Airdrop design

### Flow of one drop
1. **Sortie.** The wave director turns each wave group into one or more
   transport passes. For example, 6–8 paratroopers, 2 buggies or 1 tank per
   transport; large groups fly in formation.
2. **Approach.** The transport enters from beyond the basin edge at 250–350
   studs above the floor. It flies a straight or gently curved path across
   the basin and exits without ever passing over the mesa. Engine drone,
   and a radar blip announce it; the
   HUD shows "INCOMING AIRDROP" with a direction.
3. **Release.** Over the drop point the ramp opens and the load leaves in a
   stick along the flight line: troopers about 0.5 s apart, vehicles on
   platforms. Canopies blossom after a short free fall. Troopers sway down
   at ~15–20 studs/s, and vehicles under 3–4 cargo chutes at ~20–25 studs/s.
4. **Invincible descent.** Nothing airborne can be damaged or locked. MG
   rounds that hit a chute or load show a deflect/pass-through with no hit
   marker. Rockets and missiles pass through.
5. **Touchdown.** The load lands on open basin floor 300–800 studs from the
   outpost. It never lands on cliffs, buttes or the mesa slope, and never
   inside a wash bank. Dust puffs and the canopy collapses and drapes,
   lingering a few seconds. The real enemy takes over at the same spot:
   - Troopers unclip and head for the nearest forward waypoint of their
     lane.
   - Vehicles unhook and drive onto their lane (buggies into their wash,
     tanks onto the road).
6. From then on, everything behaves exactly as today: attacks, damage,
   wrecks and wave completion.

### Architecture (recommended)
- **Server owns the timeline.** A new `Airdrop` server module turns wave
  groups into sorties. For each load it computes the path, release times
  and **exact landing point and time**, deterministic from the wave RNG.
  It announces the sortie to clients in one event
  (`AirdropSortie {id, path, speed, t0, loads = {kind, lane, releaseT, landT, landPos}}`).
  At `landT` it spawns the real enemy through `Enemies.spawn(ctx, kind, lane, {landAt = …})`.
- **Airborne loads are client-rendered.** Clients animate the transport, the
  stick and the descent from the sortie data. It costs no bandwidth, it's
  smooth, and the loads are trivially invincible because the server has
  nothing to hit. The client applies the MG "no effect" feedback on its own
  raycast against the airborne visuals. Hand-off: the descending visual
  lands at `landPos` at `landT`, then hides once the replicated enemy
  appears, with no pop.
- **Enemy types gain a landing entry.** `spawn(ctx, lane, rng, opts)`
  accepts `opts.landAt`. It starts the enemy there and picks the next lane
  waypoint ahead of it (closer to the mesa). Nothing else in the enemy
  types changes.
- **Wave accounting.** Loads in the air count toward the wave's remaining
  enemies, so a wave can't end early and can never hang. The anti-softlock
  timeout still applies.
- **Drop-zone sampler.** Picks landing points inside the 300–800 stud band
  near each group's lane with lateral scatter. It checks every point is
  open, flat enough floor (terrain height and material, landscape meshes
  excluded) and keeps a spacing between loads. It is seeded per wave and
  run, so drops vary. The LOS check and the ground check still pass.
- **Unchanged:** helicopters, jets, the Siege Crawler's own approach, supply
  crates (they already parachute) and all damage rules for landed enemies.

### Presentation
- **New art (Blender, original):**
  - The transport aircraft: four turboprops, high wing, rear ramp that
    opens, enemy gunmetal with red markings and the emblem.
  - A personnel parachute: deploy, open and collapsed states.
  - A cargo-chute cluster and a drop platform with straps.
- **Motion:**
  - Canopy deploy snap and sway, and trooper legs dangling.
  - Vehicles swing gently under their chutes.
  - Landing flare, dust puff, canopy collapse and drape.
  - Transports get prop blur and ramp animation.
- **HUD:**
  - "INCOMING AIRDROP ◂ LEFT" banner.
  - Transport and landing markers on the radar.
  - The first-airdrop tip from spec §8.2.
- **Audio:** transport drone (positional), ramp clunk, chute pop, landing
  thuds, and a deflect ping. These are new synthesized sounds added to the
  sound sheet.

### Balance
Arrival changes pacing: enemies spend 10–20 s in flight but land closer
than today's spawn points. Retune the wave groups (timing, counts, drop
bands) with the QA bots so waves 1–9 clear on the first try with the
human-like bot and the boss stays a climax. Update the bots so they don't
waste fire on airborne loads.

---

## 2. Cinematic environment

**Look:** crisp, high-contrast, lived-in battlefield (Battlefield / Call of
Duty desert maps), readable combat spaces. The budget stays at 60 fps
mid-range at graphics level 8 with ~250 MB of textures, and texture memory
is already at the line. So the first step is an authoritative measurement
and a reclaim list, and new work favours reuse (shared atlases, instancing,
particles) over new maps.

### Atmosphere and light (Look)
- Depth-layered haze: thicker low dust in the basin, clean upper air, and
  distance fall-off that separates the foreground, the basin and the walls.
- Sun shafts through dust at low sun (sunset, late afternoon).
- A crisp modern-shooter grade: stronger local contrast, clean whites, no
  mud, with a per-time-of-day refresh of the light keys in
  `docs/ART_BIBLE.md`.
- A restrained film treatment: subtle animated grain, a gentle vignette,
  and a sun glare/lens response when looking toward the sun. It never
  reduces readability.
- Dust-storm lighting states for the weather events below.

### Ground realism (Environment)
- Finish the paused ENV-3 work: road and wash edge strips and the
  shared-atlas ground dressing, then review it.
- A second pass for density and variety by zone:
  - scrub, rock and pebble scatter;
  - tyre tracks following the lanes;
  - old craters;
  - eroded wash banks.
  No bare repeating sand should be visible from any beauty camera.
- Conflict and habitation dressing, off the lanes and out of the LOS
  checks:
  - burnt-out vehicle hulks (reusing wreck assets);
  - hesco/concrete barriers and concertina wire near the road;
  - a line of power poles;
  - a ruined roadside compound on one flank;
  - scattered crates and tyres.

### Weather and life (VFX)
- A shared wind (direction and gusts) that drives sand streamers low over
  the ground, flag/wire flutter, dust off ridges, and smoke drift.
- Dust devils wandering the basin.
- Smoke rising from burning set-dressing wrecks.
- Birds: vultures circling high, and flocks scattering from explosions.
- **Dust storms** on selected waves: a wall of dust rolls in, visibility
  drops, then clears. Tuned with Look's storm lighting so every enemy stays
  readable at its engagement range. The radar and HUD are unaffected.

---

## 3. Milestones and team

Same model as the face-lift: parallel workstreams, file ownership, the FIFO
Studio lock, the Blender lock, and a review of every milestone (diff +
before/after images). The contract is `docs/FACELIFT_TEAM.md`, whose
"Update 2" section gives the new ownership.

| # | Workstream | Milestone | Depends on |
|---|---|---|---|
| 1 | Airdrop (new) | **AD-1** Server timeline, drop-zone sampler, landing spawn, wave accounting, invincible loads, placeholder client visuals, debug hooks | — |
| 2 | Hard-surface | **HS-6** Transport aircraft, personnel chute (3 states), cargo chutes, drop platform | — |
| 3 | Environment | **ENV-3** Finish and review road/wash edges and ground dressing | — |
| 4 | Look | **LOOK-3b** Event-driven EnemyMotion sweep (open face-lift item), then **LOOK-5** atmosphere and light | — |
| 5 | QA | **QA-B** Authoritative perf and texture measurement, ranked reclaim list; the lead rules on the cuts | — |
| 6 | Airdrop | **AD-2** Presentation: transport flight and ramp, chute deploy/sway/collapse, vehicle platforms, "no effect" feedback, HUD banner, radar and tip, new sounds | AD-1, HS-6 |
| 7 | Environment | **ENV-4** Ground density and conflict dressing | ENV-3, QA-B |
| 8 | VFX | **VFX-4** Wind, sand streamers, dust devils, wreck smoke, birds, dust storms | LOOK-5 (storm lighting) |
| 9 | Airdrop | **AD-3** Bot update and wave retune; full-run difficulty check | AD-1 (AD-2 for final) |
| 10 | Look | **LOOK-4** Weapon icons, title key art (new environment + airdrop), logo | ENV-4, AD-2 |
| 11 | QA | **QA-F** Final: perf in waves 8–10, full 10-wave run, final beauty set vs baseline, readability, updated before/after page | all |

## 4. How we'll know it worked
- Ground enemies only ever enter the battle by airdrop. They land 300–800
  studs out, vary between runs, can't be damaged in the air (visible "no
  effect"), and join their lanes without getting stuck.
- Waves feel as fair as before (bot retune), and every wave and the boss
  complete reliably.
- The beauty cameras show no bare repeating sand, visible depth in the air,
  and weather that reads as alive.
- The readability check passes at every time of day and during storms.
- 60 fps and the texture budget hold in the busiest waves (8–10, at sunset).

## 5. Risks
- **Hand-off pops** at touchdown: design the client visual and the server
  spawn to meet at the same point and time, and verify it on video.
- **Enemies landing somewhere unreachable or stuck:** the sampler checks the
  ground and a lane path. Stragglers keep the wave-timeout safety.
- **Texture budget:** already at ~250 MB. The QA-B reclaim comes first, and
  every milestone records its A/B.
- **Weather hurting readability:** the storm intensity is capped by a
  grayscale readability check at engagement range.
- **Sound sheet:** re-uploading the sheet goes through Roblox moderation
  again; sounds fail silently until then.
