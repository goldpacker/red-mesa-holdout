# Progress

## Milestone 1 — First playable ✅ (2026-09-26)

Scope: title → Start → turret control → machine gun → infantry waves →
integrity/damage → wave clear intermission → defeat (Restart / Retry Wave)
→ victory (Play Again). Two infantry-only waves are defined in
`src/shared/Config.luau`; later waves/enemies come in later milestones.

### Completed
- Rojo 7.7 project (`default.project.json`), `src/` live-synced into Studio.
- Battlefield generated at server start (`src/server/WorldBuilder.luau`):
  terraced red mesa, rear cliffs, flank canyon walls, far canyon wall,
  buttes, central road, two dry washes, rocks and scrub, afternoon lighting.
- Emplacement on a bunker atop the mesa with a three-weapon turret
  (primitive placeholder until the Blender hero asset).
- Title screen with controls card, slow camera pan, Start button.
- Turret camera: mouse-locked aim, 270° traverse, third-person orbit that
  rises when aiming down, hold-RMB gunsight view with narrow FOV.
- Machine gun: server-authoritative raycast hits, client tracers, muzzle
  flash, impact puffs/sparks, recoil + light shake, heat and 2 s overheat lock.
- Infantry: oversized blocky soldiers with procedural walk/aim/throw
  animation, rifle chip damage in range, grenades at the mesa foot,
  topple on death.
- Game state machine (server): WaveIntro → Wave → Intermission → … →
  Victory, Defeat with checkpoint-based Retry Wave and full Restart.
- Scoring: kill points, combo multiplier (x1–x4, 3 s window), wave clear +
  integrity bonus, accuracy, best combo, session best.
- HUD: integrity bar, weapon strip + heat bar, wave/score/combo (pulses),
  hostiles remaining, radar with rear dead-zone marker, crosshair,
  hit/kill markers, score popups, directional damage indicators + flash,
  low-integrity vignette, first-encounter tips.
- Screens: wave banners, intermission tally with countdown and next-wave
  preview, defeat (emplacement explodes and burns, camera pulls out over the
  basin), victory.
- QA tooling: Studio-only debug attributes (DebugYaw/DebugPitch/DebugFire/
  DebugAiming) and `ServerStorage.RedMesaDebug`; autoplay helper in
  `tools/qa/autoplay.client.luau`.

### Current work
- None in progress; milestone 1 verified. Next: milestone 2.

### Known bugs / gaps
- **Audio:** only Studio's built-in explosion sound is wired. The free
  Creator Store results found were user uploads of unclear provenance
  (some ripped from other games), so none were used. Plan: synthesize
  original sounds (Python) and upload via Studio's asset manager — upload may
  need a human.
- Runtime terrain takes ~30–45 s to replicate/mesh on the client; the title
  screen shows a partial world during that time.
- Turret, emplacement, infantry and rocks are primitive placeholders and
  infantry are oversized 1.5x; both conflict with the new art direction.
- Rockets / AA missiles slots are shown but inactive.
- Low-integrity alarm sound, jet siren etc. not yet implemented.

### Last successful playtest
- 2026-09-26, full milestone loop in Studio: title → START → wave 1 cleared
  → intermission (tally, repair, preview, countdown) → wave 2 cleared →
  victory screen → PLAY AGAIN resets to wave 1 (session best kept).
  Separately: infantry reaching the mesa foot drained integrity to 0 →
  defeat sequence → RETRY WAVE restored the wave-start checkpoint, RESTART
  began a fresh run. Gunsight view checked at steep downward aim.
  Console clean (no game errors). Firing was driven by the QA autoplay
  helper; real mouse-look has not been exercised by a human yet.

### Next planned task
- Art direction changed to grounded semi-realistic (GAME_SPEC §13/§14,
  2026-09-26). Next: a visual-foundation pass before more enemies, so every
  later asset is built once in the final style — terrain material variants,
  lighting/sky, rock kit, emplacement + turret hero asset, human-scale
  infantry mesh, particle effects.
- Then milestone 2: rockets + tanks, supply crates (wave 3), buggies.
