# Performance budget

The face-lift adds geometry, textures and particles; this page sets the
limits and records where the game stands before any of it (Phase 0). Every
workstream that adds geometry, textures or particles re-measures with the
same probe at its quality gate (`docs/FACELIFT_TEAM.md` gate 7) and adds a
row to §4. Owner: QA-tools.

## 1. Budget

| Metric | Budget | How measured |
|---|---|---|
| Frame rate | **60 fps on a mid-range PC at graphics level 8**, in the busiest waves (8–10 at night) | Studio caps at 60 fps on the measuring Mac, so track frame *times* (below) rather than fps |
| Triangles on screen | **< ~1,000,000** (scene) | `Stats.SceneTriangleCount` |
| Texture memory | **< ~250 MB** | `Stats:GetMemoryUsageMbForTag(Enum.DeveloperMemoryTag.GraphicsTexture)`. In Studio this tag is process-wide and carries history (§5.3); per asset, use the calibrated model (`tools/qa/texture_budget.py report`, §5.4) |
| Render frame time on the measuring Mac (M4 Pro, Studio, QualityLevel 15) | working limit **≤ 6 ms CPU and ≤ 6 ms GPU** in the busy scene | `Stats.RenderCPUFrameTime`, `Stats.RenderGPUFrameTime`. Heuristic: a mid-range PC is ~2.5× slower, which keeps it inside 16.7 ms |
| Draw calls | guidance: scene ≤ ~600, shadows ≤ ~250 | `Stats.SceneDrawcallCount`, `Stats.ShadowsDrawcallCount` |

"Graphics level 8" is the in-game slider; Studio's `QualityLevel` has 21
steps, and we assume slider N ≈ `Level(2N−1)`, i.e. level 8 ≈ `Level15` —
the same level the beauty shots use. Measure at `Level15`.

## 2. How to measure

1. Studio lock, `caffeinate -u -t 2`, Studio in front, Play, Client
   `settings().Rendering.QualityLevel = Enum.QualityLevel.Level15`, wait 40 s
   (see `tools/qa/BEAUTY.md` §2.1).
2. Stage the scene (Server datamodel):
   - **Title:** a fresh Play (or `RedMesaDebug:Invoke("beautyEnd")`).
   - **Wave 1 afternoon:** `RedMesaDebug:Invoke("startWave", 1)`, start the
     MG bot (`tools/qa/autoplay.client.luau`, Client), probe ~25 s in.
   - **Busy late wave at night:** `RedMesaDebug:Invoke("startWave", 9)`,
     keep integrity up (`task.spawn` a loop of `Invoke("setIntegrity", 100)`
     every 2 s), MG bot on, probe ~50 s in.
3. Paste `tools/qa/perf_probe.client.luau` (Client) with `LABEL` set
   (prefix `task.wait(n)` to time it). It samples 8 s and returns frame
   rate, render stats, memory by tag and instance/effect counts.
4. Add a row to §4 with the date, commit and scene.

The authoritative protocol (QA-B, §5.1) adds: the viewport check
(`tools/qa/BEAUTY.md` §2.5), a quiet machine (`tools/blender-lock.sh status`
free, no `Blender -b` process), the Edit-datamodel `GraphicsTexture` just
before Play, three fresh plays that each run title → wave 1 → wave 9 →
wave 10 in that order, and the boss wave probed ~45 s in. A texture A/B
must be **additive** (show textures that were never drawn in this Studio
process, early in a session) — removing things doesn't free their memory
(§5.3).

Notes on the numbers:
- Studio totals (`GetTotalMemoryUsageMb`, the `Internal`, `LuaHeap`,
  `Instances` tags) include the Studio process and both play DataModels;
  they are not the game's footprint. Track the `Graphics*` tags.
- fps is vsync-capped at 60; the 1 %-low is sensitive to hitches from the
  MCP call itself. Frame times and triangle/draw-call counts are the
  comparable numbers.
- `UI2D*` stats read 2 triangles / 1 draw call even with the HUD up; Studio
  doesn't seem to report the game UI there.

## 3. Phase 0 baseline (2026-09-26, visuals of 9206a52)

Apple M4 Pro, Roblox Studio playtest, `QualityLevel` 15, viewport
1177×1068, `Lighting.Technology` Future, streaming off.

| Scene | fps avg / 1 % low | Scene tris | Scene draw calls | Shadow tris / draw calls | Render CPU / GPU ms | GraphicsTexture MB | GraphicsTerrain / Particles / MeshParts / Parts MB | Workspace MeshParts / Parts / SurfaceAppearances | Emitters (on) / lights (on) / beams | Enemies |
|---|---|---|---|---|---|---|---|---|---|---|
| Title (afternoon) | 59.6 / 26.2 | 308,734 | 193 | 68,587 / 38 | 5.66 / 8.92 | 86 | 75 / 27 / 3 / 2 | 76 / 81 / 73 | 0 / 4 (0) / 2 | none |
| Wave 1 afternoon, ~25 s in, MG firing | 60.0 / 53.3 | 322,228 | 193 | 168,402 / 75 | 3.28 / 4.13 | 86 | 75 / 27 / 3 / 2 | 132 / 100 / 129 | 0 / 13 (1) / 2 | Infantry 8 |
| Wave 9 night, ~50 s in, MG firing | 60.0 / 52.4 | 327,941 | 212 | 164,555 / 75 | 2.76 / 2.97 | 86 | 75 / 27 / 3 / 2 | 122 / 124 / 119 | 31 (9) / 47 (43) / 2 | Buggy 4, Helicopter 2, Tank 2 |

Evidence: probe output in `.superpowers/sdd/FACELIFT_PLAN/reports/P0.md`;
wave 9 frame `qa/beauty/perf/p0-wave9-night.jpg`.

Reading it:
- **Triangles:** ~310–330k on screen, dominated by terrain (the title view
  with no enemies is already 309k). Headroom ≈ **670k**.
- **Textures:** 86 MB. Headroom ≈ **164 MB**. Terrain uses no
  MaterialVariants yet (MaterialService is empty).
- **Frame time:** GPU is highest on the title pan (8.9 ms — it looks across
  the whole basin); combat views are 3–4 ms. The title view is the one to
  watch as the landscape gets heavier.
- **Draw calls:** ~190–210 scene, 38–75 shadow.

### Split of the headroom (confirmed by the lead, 2026-09-26)

| Workstream | Extra triangles on screen | Extra texture memory |
|---|---|---|
| ENV (landscape meshes, dressing, MaterialVariants, sky) | ≤ 400k | ≤ 90 MB |
| HS (emplacement, vehicles, boss, wrecks) | ≤ 120k | ≤ 40 MB |
| CHAR (infantry, up to ~20 on screen) | ≤ 60k | ≤ 10 MB |
| VFX (flipbooks, debris) | ≤ 20k | ≤ 15 MB |
| Look (UI, post) | — | ≤ 5 MB |
| **Total after the face-lift** | ≲ 930k | ≲ 246 MB |

## 4. Measurements log

| Date | Commit | Scene | Scene tris | Scene DC | CPU / GPU ms | GraphicsTexture MB | Notes |
|---|---|---|---|---|---|---|---|
| 2026-09-26 | 9206a52 visuals | Title | 308,734 | 193 | 5.66 / 8.92 | 86 | Phase 0 baseline |
| 2026-09-26 | 9206a52 visuals | Wave 1 afternoon | 322,228 | 193 | 3.28 / 4.13 | 86 | Phase 0 baseline |
| 2026-09-26 | 9206a52 visuals | Wave 9 night | 327,941 | 212 | 2.76 / 2.97 | 86 | Phase 0 baseline |
| 2026-09-26 | HS-1 (a921ce0 + rbxmx) | Turret view, night (beauty shot 2 stage, staged enemies) | 388,057 | 250 | 2.57 / 5.07 | 128 (emplacement 16.0) | HS-1 emplacement: 69.5k tris in the asset (was 46.4k, budget note ≤ ~80k); 9 texture groups (7×1024², 512², 256²; no metalness map on concrete/bags/net). Emplacement texture share measured by detaching it client-side: 128.4 → 112.4 MB. Scene totals include ENV/Look changes landed since P0. fps 60.0 / 1 %-low 56.0 |
| 2026-09-26 | 2c6f21c + CHAR-1 assets | CHAR-1 A/B, one fixed basin view (title-time afternoon), 20 soldiers at 34–60 studs, no enemies | 162,320 empty · 242,120 with 20 rigid `Infantry` · 261,928 with 20 skinned `Infantry_Skinned_*` (animated every frame) | 159 · 166 · 164 | not comparable (an HS Cycles bake was running on the GPU) | 92.8 | Skinned soldier ≈ 4.98k tris vs rigid 3.99k: **+19.8k for 20** (CHAR budget 60k); draw calls −2 (skinned variants batch); LOD meshes (1.6k) unused so far. Re-measure frame times in CHAR-2 on a quiet machine. |
| 2026-09-26 | ENV-1 (006ee48) | Title (afternoon), fresh-play A/B: ENV-1 inputs moved aside vs present, same session, quiet machine | 332,108 → 332,114 | 247 → 253 | 2.55 / 4.44 → 2.80 / 5.23 | 94.5 → 99.3 (+4.8); 107.0 after cycling all 5 presets + staged enemies | ENV-1: 8 terrain MaterialVariants (24 maps, 1024²) + skyboxes (5 presets × 6 faces, 1024²; only the active preset is resident). Terrain geometry unchanged (GraphicsTerrain 77.4 both). Upper bound for ENV-1 textures ≈ 13 MB of the ENV 90 MB share. Client-only override A/B in one session: GPU 3.2 ms stock vs 4.0–4.1 ms with variants. |
| 2026-09-26 | CHAR-2 (13e79f1 + LOD 200) | Live waves, turret camera, quiet machine (Blender slots free): (a) wave 8 Night preset ~35 s, no bot, 16 infantry on screen (all on `BodyLOD`); (b) same wave looking down the road, 24 on screen; (c) wave 8 Dusk ~45 s, MG bot; (d) 8 soldiers at the mesa foot, full-res | (a) 370,223 · (b) 451,938 · (c) 336,898 · (d) 394,904 | (a) 234 · (c) 239 | (a) 2.59 / 3.26 · (b) 2.45 / 5.12 · (c) 2.56 / 6.15 | (a) 131 · (c) 138 | Client-only A/B (hide `Body`/`BodyLOD` with LocalTransparencyModifier): skinned infantry cost **+21.3k tris for 16 on LOD** (a), **+91.6k for 24 (16 full-res at the old 280-stud LOD switch)** (b), **+38.7k for 8 full-res** (d); per soldier 4.8–4.9k full, 1.3–1.6k LOD. The rigid soldier it replaces drew 4.0k, so vs the P0 baseline the net is ≈ +0.9k per full-res and −2.4k per LOD soldier: (b) ≈ −4k, a worst case of 24 full-res ≈ +22k (CHAR budget 60k). LOD switch now at 200 studs (zoom-corrected). Animation: 6.8 µs per soldier update in Luau (24 soldiers at full rate = 0.16 ms/frame), updates thinned by distance (every frame < 140 studs, 30 Hz < 320, 15 Hz < 650, 8 Hz beyond). Textures: one shared 1024 set for all infantry; the rigid parts' SurfaceAppearances are destroyed, so the old Infantry set no longer loads. fps 60.0 (1 % low 51.9–56.6) |
| 2026-09-26 | VFX-2 (363c208 + tracer/brightness follow-up) | Wave 9 night (live wave, integrity held at 100), MG + rocket driver firing at every vehicle, ~60 s in; probe 8 s | 352,988 | 255 | 2.58 / 4.28 | 135.6 (GraphicsParticles 36.5) | VFX-2 effects on custom flipbooks. fps 60.0 / 1 %-low 55.6. Peak live effects over the sample: 242 emitters (16 continuously enabled), 27 beams, 71 lights, 26 CombatFx parts (scorch decals capped at 12, debris at 40). VFX texture share: 15 sheets/singles, GraphicsParticles 27 (P0) → 36.5 MB (+9.5 of the 15 MB share). Debris meshes ≤ 40 × 80 tris + rocket/bomb bodies ≈ ≤ 6k tris. Same scene with the MG autoplay only (vehicles out of its reach): 348,207 tris, 2.14 / 3.31 ms. |
| 2026-09-26 | LOOK-1 (6058923 + others' work to 11:20) | Wave 9 night (live wave, day-for-night preset, integrity held at 100), MG autoplay, ~45 s in; probe 8 s | 360,419 | 252 | 2.65 / 3.45 | 132 | LOOK-1 post and lighting: 3 Look textures (heat haze 128×512, searchlight cone 128×512, vignette 512², ≈ 1.4 MB). Heat haze is ~66 Beam segments on the client, disabled below Sunset (off at night). Night adds a client pit-lamp SpotLight and one "Glow" Beam per searchlight. Gunsight DoF sits on the camera and is disabled outside aiming. Post chain at night: Atmosphere, Grade, Bloom, SunRays (0 intensity). fps 60.0 / 1 %-low 53.0 (worst frame 19.0 ms). Workspace: 158 emitters (2 on), 112 beams, 74 lights (52 on); enemies Buggy 5, Helicopter 3, Infantry 5, Tank 3. Frame `qa/beauty/look-1/extra/perf-wave9-night-busy.jpg`. |
| 2026-09-26 | HS-2 (f13df63 + HS-2 client, working tree 12:10) | Turret view, night (beauty shot 2 stage, staged enemies, BeautyShot cleared client-side so wind/brass run), MG firing continuously; in-session A/B: HS-2 motion on vs paused (`Workspace.HsFxOff`, Studio-only), 3 × 4 s blocks each, interleaved | 368,512 | 253 | on 2.60 / 4.86 · off 2.65 / 4.76 (block-to-block spread ±0.3 GPU) | 129.1 | HS-2 motion: no measurable frame-time change. Lua cost of the whole module (belt feed, 28-casing pool, barrel-heat Beam, whip chain, net EditableMesh ripple at 15 Hz near / 3.75 Hz far) 0.14–0.18 ms/frame firing, 0.06–0.09 ms at the title camera (os.clock, `HsFxMs`). Triangles: emplacement asset 69,726 (+182: templates, whip links); live extras ≤ 12 feed rounds × 120 (static 840-tri `Belt` hidden) + ≤ 28 casings × 40 ≈ +1.7k. Gunsight models 5.9k in the asset, one sight at a time (≤ 3.3k) and only while aiming, when the emplacement is hidden. Textures: `Gunsights` 2 × 1024² sets (8 maps) + a re-baked props set (same size) — ≈ +4.5 MB by HS-1's measured ~0.55 MB per 1024² map (no clean in-session A/B: the maps are warmed at start). HS total ≈ 25k tris / ≈ 20.5 MB of the 120k / 40 MB share. fps 60.0, 1 %-low 57.1. |
| 2026-09-26 | HS-3 (7d3dd72 + HS-3 rbxmx) | Wave 9 night, live wave (integrity held, no bot, extra Tank + Buggy spawned), turret camera; Buggy 5, Helicopter 2, Infantry 14, Tank 3 | 470,699 | 309 | 2.71 / 4.82 | 258.4 | HS-3 Tank 13.8k → 16.0k tris, Buggy 7.7k → 8.7k. In-session A/B (client-side reparent of the 3 tanks + 5 buggies): they draw 49–55k scene tris, ≈ +7k vs the old meshes at the same counts (worst case all 8 on screen ≈ +11.6k). Textures: Tank 2 own 1024² sets + Buggy 1 own set + the shared `TrimEnemy` set (16 maps) replace Tank 3 sets + Buggy 1024²+512² (≈ 17 map-equivalents) → ≈ −0.5 MB (estimate at ~0.55 MB/map; the shared sheet is loaded once for every enemy vehicle). fps 60.0 / 1 %-low 55.3. Note: the GraphicsTexture total (258 MB, all workstreams) is now over the ~250 MB budget. HS running total ≈ 32k tris / ≈ 20 MB of the 120k / 40 MB share. |
| 2026-09-26 | HS-4 (Helicopter 111963666954286, Jet 79567653016658, Emplacement 95300083608534 rbxmx) | Wave 9 night preset, live wave (integrity held at 100), turret camera, extra aircraft spawned; Buggy 4, Helicopter 4, Infantry 16, Jet 1, Tank 3; probe 8 s | 514,932 | 336 | 2.64 / 5.61 | 240.9 | HS-4 aircraft and turret gun assembly. **Texture A/B** (same session type, beauty shot-2 stage + one staged jet, all five presets visited): GraphicsTexture 241.4 MB with the HS-3-era assets → 241.0 MB with HS-4 (−0.4 MB, i.e. no net texture memory); detaching both aircraft client-side frees 5.3 MB in either case. Map accounting: Helicopter 4×1024² + 4×512² → 3×1024² (rotors and small hardware moved to the shared `TrimEnemy` sheet, no metalness map on the painted skin), Jet 4 → 3 maps, turret/weapons atlases re-baked at the same 8 maps → ≈ −3 map-equivalents (≈ −1.6 MB estimate). **Triangles:** Helicopter 5.0k → 9.7k, Jet 2.3k → 5.4k, Emplacement 69.7k → 65.1k (low-poly bevels replaced by the high-poly bake); a wave with 2 helicopters + 1 jet ≈ +7.8k (client-side aircraft detach A/B too noisy in a live wave: ±7k). fps 60.0 / 1 %-low 52.7. HS running total ≈ 40k tris / ≈ 18.5 MB of the 120k / 40 MB share. |
| 2026-09-26 | ENV-2 (landscape meshes, final maps; working tree 14:50) | Title (afternoon), fresh plays in one Studio session: landscape assets stashed in Edit vs present | 273,085 → 380,928 (+108k); in-play client removal 396,367 → 257,254 (−139k) | 257 → 273 | 2.94 / 4.26 → 3.01 / 3.74 (noise; in-play removal 2.87 / 6.04 → 2.68 / 4.98) | 178.7 and 189.3 stashed vs 175.9 present (between-play spread ~±10 MB > the landscape's share) | ENV-2: 30 MeshParts, 190k tris in the assets; shadow tris 53.5k → 72.9k. Textures after the lead's alert: mesa 10 × (1024² colour + 512² normal), walls/buttes 20 × (512² colour + 256² normal), no roughness/metal maps: 19.7 Mpx of maps, down from 45.6 Mpx in the first upload (−57 %) and from 30 extra roughness maps before that. |
| 2026-09-26 | ENV-2 (same build) | Wave 9 night (live, integrity held, turret view, no autoplay), probe ~45 s in; fresh plays: landscape stashed vs present | 337,493 → 429,652 (+92k) | 260 → 285 | 2.44 / 4.88 → 2.60 / 5.42 | 202.2 → 228.9 (**+26.7**) | Best A/B for ENV-2's texture cost: ~27 MB. ENV total ≈ ENV-1 ~5–13 + ENV-2 ~27 ≈ 32–40 MB of the 90 MB share. GraphicsTexture total 228.9 MB with everything loaded (< 250). fps 60.0 / 1 %-low 52.6 → 53.4. |
| 2026-09-26 | LOOK-2 (HUD kit, working tree 15:10) | Wave 9 night, live wave (integrity held), MG autoplay, ~38 s in, probe 8 s; Buggy 1, Helicopter 1, Infantry 1, Tank 2 | 345,592 | 241 | 2.53 / 4.98 | 233.2 | LOOK-2 HUD kit: one 512² atlas + 128² grain + 64² hazard + 64×8 strip tiles, all RGBA ≈ 1.4 MB uncompressed with mips (Look total with LOOK-1 ≈ 2.8 MB of the 5 MB share). Hud ScreenGui: 268 instances, 79 images (kit 9-slices share one atlas). fps 60.0 / 1 %-low 52.9 (worst 19.0 ms). An in-session HUD on/off A/B was attempted but an HS Blender build started mid-run (CPU 8–57 ms), so it is not reported; the quiet probe above matches LOOK-1's 2.65 / 3.45 ms and HS-2's 2.60 / 4.86 ms at the same scene. Frame `qa/beauty/look-2/extra/perf-wave9-night-live-combat.jpg` (taken during the contaminated A/B). |
| 2026-09-26 | VFX-3 (4a44fb3 + downwash retune) | Wave 9 night (live wave, integrity held at 100), MG + rocket driver on every vehicle, ~30 s in; four alternating 8 s probes with particle LOD off/on (Workspace `FxLodOff`) | 340,809–447,592 (enemy count varied between probes) | 257–317 | LOD off 2.34 / 4.02 and 2.57 / 3.43 · LOD on 2.54 / 3.85 and 2.44 / 3.69 | 239 (GraphicsParticles 49.3–49.6) | VFX-3 motion dust (wheels, tracks, rotor downwash, jet wake; `client/VehicleFxDust`) + distance LOD (`client/EffectsLod`). fps 60.0, 1 %-low 51–53 in all four. Live particles (continuous emitters' Rate × lifetime + one-shot estimate, `H.sample`): LOD off 436 / 604, on 429 / 466 avg (peaks 669–869). Paired 1.1 s alternation in the same scene: motion dust 225 → 156 particles/s and continuous live particles 716 → 495 (**−31 %**) with 14 dust sources at 292–568 zoom-corrected studs; no measurable frame-time change either way (all well inside 6 / 6 ms). New texture: `DustDrift` 512² (≈1.3 MB with mips) → VFX texture share ≈ 10.8 of 15 MB. The GraphicsParticles tag now also carries other workstreams' particles and varies with the scene (45–52.5 MB this session), so it no longer isolates VFX. No new triangles. Frame `qa/beauty/vfx-3/perf/night_wave9-busy_turret.jpg`. |
| 2026-09-26 | ENV-2 fix 1 (mesa 11 chunks, rim-knob fix; working tree 16:05) | Wave 9 night (live, integrity held), in-session staged adds after two all-round camera spins per stage (turret fwd/back/left/right, title, defeat, basin, flank) so every texture is resident | — | — | — | 204.5 base → +walls/buttes 218.0 (+13.5) → +mesa 240.0 (+22.0) → +cliff kit 240.6 (+0.5): **landscape total +36.1** | Replaces the earlier ENV-2 estimate (+26.7 MB was a turret-view A/B, not every texture resident). The fix's own cost is one more mesa chunk ≈ +2.0 MB (22.0 / 11). Fresh-play turret-view A/B in the same session: 209.9 → 255.7 (fresh plays differ by ±10 MB; use the staged number). ENV total ≈ ENV-1 5–13 + ENV-2 36 ≈ 41–49 MB of 90. |
| 2026-09-26 | LOOK-3 (1b2c3d7, Studio 17:05) | Wave 8 (live, integrity held, preset forced to Afternoon), turret camera, 33 enemies (Helicopter 6, Tank 1, Infantry 24, Buggy 2), motion dust and HUD on; three alternating 6 s blocks: EnemyMotion on / off (Workspace `MotionOff`) / on | 509,748 / 514,218 / 526,595 | 344 / 353 / 365 | 2.70 / 5.24 · 2.61 / 5.75 · 2.70 / 6.51 | 264.2 (team total) | LOOK-3 enemy motion: **no measurable render cost** (CPU 2.70 vs 2.61 ms; GPU follows the triangles on screen as enemies move, 5.2–6.5 ms). Luau cost of `client/EnemyMotion` (smoothing, body motion, tread scroll): **0.178 ms/frame mean, 0.24 ms max for 33 enemies** (0.05 ms with smoothing off, sampling only); earlier session 0.14–0.16 ms mean for 24 enemies. fps 60.0 in all blocks, 1 %-low 54.3 / 53.8 / 56.3. New textures: `TreadSide` 512×256 + `TreadRoll` 128×1024 RGBA (≈ 1.4 MB with mips, resident only while a tank or the crawler is on the field) → Look total ≈ 4.2 MB of the 5 MB share. No new geometry. GraphicsTexture total (all workstreams, tread maps included) is 264 MB here, over the 250 MB budget; LOOK-3's share of it is ≈ 1.4 MB. |
| 2026-09-26 | HS-5 (2ddd780 + 249b31e; working tree 17:40) | Wave 9 night preset, live wave (integrity held), MG autoplay, all vehicles killed once at 22 s then extra spawns; turret camera; Buggy 4, Helicopter 4, Tank 4 + 4 burning wrecks; probe 8 s | 475,929 | 323 | 2.74 / 6.05 | 253.2 | HS-5 Siege Crawler 18.9k → 32.4k tris (wave 10 only; its 12.8k of kit is culled beyond 800 zoom-corrected studs), wreck looks, vehicle kit LOD. **Kit LOD** (`client/VehicleLod`, `*Kit` parts hidden beyond 400 zoom-corrected studs × vehicle length/26, max 2): live-wave A/B (three alternating 3 s blocks, Workspace `VehicleLodOff`): −4.2k / −7.5k / −9.5k scene tris, frame times unchanged (GPU 4.1–4.7 ms both ways); staged: tank at 433 studs −5.0k (420.6k → 415.6k), crawler at 851 studs −12.8k (394.9k → 382.0k); crop diffs 0.73 and 0.83/255 mean (`qa/beauty/hs-5/lod/`). Engine LOD: every vehicle MeshPart is RenderFidelity Automatic. **Textures:** the crawler itself is 12 × 1024² + 4 × 512² metal + 4 × 512² wreck maps vs 16 × 1024² + 4 × 512² before (wave 10). Unused `Wreck` folders cost 0.00 MB (22 removed client-side in-session). Wreck maps in use (256², crawler 512²) are **not free**: +0.67 MB for the jet + shared trim wreck (two 256² maps, in-session kill A/B), +6.0 MB for a full staged kill of tank/buggy/helicopter/jet vs +1.2 MB for the same kill with tint-only wrecks (≈ +4.8 MB for 6 maps, includes cache effects). The Tank/Buggy metalness maps at 512² (offset) gave no measurable change at 400+ studs (mip streaming). Net: ≈ +2–5 MB when every wave-9 type is burning in view; zero-memory fallback = delete an asset's `wreck.json` and re-publish (Kit.char then tints the live SurfaceAppearance). fps 60.0 / 1 %-low 56.5. Frame `qa/beauty/hs-5/perf/night_wave9-busy_turret.jpg`. |
| 2026-09-26 | ENV-3F (GroundStrips 101169100642499, GroundDressing 77410053337740; working tree 20:25) | Night preset, beauty shot-2 stage (wave director stopped: 5 infantry, buggy, tank, helicopter; no drift between spins), turret camera; one play started with the ENV-3 assets stashed in Edit (WorldBuilder's ball scrub, pre-ENV-3 state), then staged adds in-session, each measured after two all-round camera passes (15 views: turret fwd/left/right/back, title, flank, night, basin, wash/road close-ups) | 411.8k → 496.8k (+85k: dressing solids ~30k, strips ~40k, foliage ~15k) | 277 → 358 (+81) | strips+dressing hidden vs shown, 3 alternations: 2.80 / 4.12 · 2.85 / 5.22 · 2.73 / 4.30 vs 2.90 / 4.83 · 2.97 / 5.94 · 2.99 / 5.70 (≈ +0.2 CPU, ≈ +0.9 ± 0.7 GPU) | base 268.1 (two spins, identical) → +strips 271.1 (**+3.0**) → +dressing 272.3 (**+1.2**) = **ENV-3 net +4.2 MB** | ENV-3/3F road and wash edge strips + ground dressing, inside the +8 MB allowance. Maps: strips 1024×512 RGBA + 512×256 normal, road core 512² + 512², dressing 512² RGBA + 256² normal (the first ENV-3 build had 1024² atlases and reused the terrain road maps, which a SurfaceAppearance can't share). Opaque strip/dressing pieces use AlphaMode Overlay so they share the colour map's single copy. Dressing shadows only within 480 studs of the turret (219 casters). Team total in this scene 268–272 MB, already over 250 before ENV-3 (QA-B's reclaim). GPU in this staged night view stays ≤ 6 ms, but the per-frame numbers swing ±1 ms between identical blocks (other agents' jobs on the machine), so QA-B should confirm the ≈ +0.9 ms in the busy wave-9 scene; cheap cuts if needed: pebble patches 220 → 110 (−~15k tris), shadow range 480 → 300, far-density floor 0.35 → 0.2. |
| 2026-09-26 | HS-6 (Transport 112250308353331, Parachute 94889432475297, ParachuteCargo 77191490075511, DropPlatform 98735928267935, TrimAirdrop maps; working tree 21:45) | Beauty shot-2 stage, turret camera pitched +14° (DebugPitch), a static airdrop tableau staged with execute_luau (not committed): 1 transport (ramp and cargo door open, blur discs at 0.7), 5 troopers under personnel chutes (1 deploying), Tank and Buggy on platforms under 4 and 2 cargo chutes, 2 collapsed chutes on the ground; probe 6 s per block | 467,371 (night, all on) vs 383,069 (tableau removed client-side) | 364 vs 300 | 2.82 / 2.86 and 2.93 / 2.97 on vs 2.78 / 2.80 off | afternoon 217.37 → **217.37** → **218.04**; night 254.0 (all three blocks) | HS-6 airdrop assets. **Texture A/B (afternoon, same session, 12 samples each, every step in view):** base stage 217.37 MB → + transport, two bare platforms (rigging and slings removed), Tank and Buggy **217.37 (+0.00: the transport and platform add no texture, TrimEnemy + Glass only)** → + all chutes, rigging, slings and troopers **218.04 (+0.67 MB = the new `TrimAirdrop` 512² colour/normal/roughness set, no metalness)**. **Triangles:** the tableau adds +84.3k scene tris and +64 draw calls, of which HS-6 assets ≈ 35k (transport 7.7k + discs 0.7k, personnel chute 1.6k each, cargo chute 1.8k each, rigged platform 2.2–2.4k, collapsed 1.7/1.9k); the rest is the Tank (16k), Buggy (8.7k) and 5 skinned soldiers. Frame times unchanged within block noise (fps 60.0 / 1 %-low 54–57). A first probe read 15 fps with GPU 0.00 (Studio unfocused), discarded. Frames `qa/beauty/hs-6/afternoon_turret-drop.jpg`, `night_turret-drop.jpg`. |
| 2026-09-26 | QA-B r1–r2 123467e (clean); r3 4aa152d + LOOK-5 work in progress | **Title**, 3 fresh plays | r1–r2: 448,198 / 448,757 · all 3: 448,470 (448,198–448,757) | r1–r2: 344 / 345 · r3: 412 | **r1–r2 (123467e): 2.98 / 5.38** (GPU 5.01, 5.75) · r3 (LOOK-5 WIP): 2.90 / 6.38 · all 3, mixed builds: 2.95 / 5.71 | r1–r2: 232.4 / 229.9 · all 3: 224.2 (210.4–232.4) | QA-B authoritative set, §5.2. r3's +67 draw calls and +1.0 ms GPU come with LOOK-5's work in progress (106 more beams at the title). |
| 2026-09-26 | same | **Wave 1 afternoon**, ~25 s in, MG bot | r1–r2: 469,019 / 457,525 · all 3: 466,060 (457,525–471,635) | r1–r2: 391 / 384 · r3: 473 | **r1–r2 (123467e): 3.04 / 5.27** (GPU 5.19, 5.34) · r3 (LOOK-5 WIP): 3.09 / 6.05 · all 3, mixed builds: 3.05 / 5.53 | r1–r2: 236.3 / 246.6 · all 3: 232.7 (215.1–246.6) | 1–4 infantry on screen (airdrops land from ~15 s). |
| 2026-09-26 | same | **Wave 9 night**, ~50 s in, integrity held, MG bot | r1–r2: 485,994 / 498,680 · all 3: 486,448 (474,669–498,680) | r1–r2: 400 / 392 · r3: 449 | **r1–r2 (123467e): 2.94 / 5.96** (GPU 5.57, 6.35) · r3 (LOOK-5 WIP): 3.01 / 6.78 · all 3, mixed builds: 2.96 / 6.23 | r1–r2: 254.7 / 254.4 · all 3: 254.1 (253.1–254.7) | Buggy 2, Helicopter 1, Jet 1, Tank 1 in all three; shadows 248.7k tris / 134 DC (all 3). Clean build at the 6 ms limit (mean 5.96), r2 over it on its own (6.35); r3 with LOOK-5 WIP 6.78. |
| 2026-09-26 | same | **Wave 10 boss**, ~45 s in, integrity held, MG bot | r1–r2: 487,007 / 474,767 · all 3: 477,425 (470,500–487,007) | r1–r2: 368 / 357 · r3: 431 | **r1–r2 (123467e): 2.89 / 5.30** (GPU 4.77, 5.82) · r3 (LOOK-5 WIP): 2.85 / 6.77 · all 3, mixed builds: 2.88 / 5.79 | r1–r2: 263.8 / 255.4 · all 3: 258.9 (255.4–263.8) | Siege Crawler + helicopter + 5–9 infantry. |
| 2026-09-26 | QA-B s1 aecd5a1 + then-WIP (AD-1, ENV-3F, LOOK-3B), s4 4aa152d + LOOK-5 WIP | **Everything drawn once** (every enemy kind live and wrecked, crate, all presets visited, 430–480-view close-up tour) | — | — | — | 301.9 (s1), 298.0 (s4); peak 308.5 | Upper bound of what a long run makes resident in this Studio process; game-owned share per the model 157.8 MB (§5.4). |
| 2026-09-27 | RECLAIM-HS (ddb8212 + rbxmx/Flipbooks switch) | Texture model (`texture_budget.py report`, every asset drawn once) + gunsight captures at each vehicle's nearest range (afternoon; crawler also sunset), two fresh plays: 1024² build vs 512² build | — | — | — | model: HS 55.8 → 37.8, VFX 24.0 → 20.0 (**−22.0 MB**) | QA-B items 4, 5, 2 and the HS/CHAR part of 14 (§5.5): Siege Crawler −8.0, Tank/Buggy/Helicopter/Jet −10.0, `ScorchMark` −4.0; never-drawn maps no longer uploaded (0 resident). Captures `qa/beauty/reclaim-hs/`: fine-detail energy (mean \|Laplacian\|) on each vehicle crop before → after: buggy 18.14 → 18.20, tank 17.85 → 17.89, helicopter 11.45 → 11.36, jet 5.85 → 5.86, crawler 7.87 → 7.84 (afternoon) and 7.56 → 7.56 (sunset); the remaining pixel differences are idle motion, rotor phase, clouds and ENV-4's ground dressing between the two plays. Wreck swaps (burnt colour + 512² normal/roughness) and kit LOD checked in play; console clean. |
| 2026-09-27 | AD-2 (7fd29e7) | **Wave 7 Sunset** (daylight-only plan), ~40 s in, integrity held, turret view toward the drops, no bot; 3 extra debug sorties (8 Infantry, Tank, 2 Buggy) + the wave's own, probed while 11 loads and their transports were in the air; in-session A/B with the Studio switch `Workspace.AirdropFxOff` (parks the airdrop visuals), 3 s blocks on/off/on/off | on 629,486 / 641,183 · off 615,208 / 648,442 (the scene moves: +14k tris for 11 loads + a transport in the same pair) | on 453 / 465 · off 446 / 459 (**+7**) | on 3.23 / 6.58, 3.14 / 6.22 · off 3.03 / 7.01, 3.06 / 6.49 (**CPU +0.1–0.2 ms; GPU inside the scene's noise**) | 261.0 (no new maps: HS-6 art + existing flipbooks; TrimAirdrop 0.67 MB per HS-6) | fps 60.0 / 1 %-low 55.6–56.5 all blocks. 41 enemies live (Infantry 30, Buggy 6, Tank 5). AirdropFx 200–242 parts for 11 loads + transports; caps 48 airborne loads, 10 transports, 18 grounded canopies. The GPU sits at/over the 6 ms working limit with or without the airdrop visuals (scene + LOOK-5 WIP in the tree). Session 1 (wave 5 Sunset, 11 loads, 221 parts): 3.29 / 6.22 on vs 3.22 / 6.52 off. |
| 2026-09-27 | LOOK-5 (f7788f2 + final trims: 3 shafts, 0.42 corner vignette, storm values) | **Wave 9 Sunset** (daylight-only), airdrop seed 7, integrity held, MG autoplay (range 450; idle aim = the turret beauty angle), quiet machine (both Blender slots free, load 2.6); paired A/B in one session, 12 rounds × 2.5 s, order alternated: **after** = LOOK-5 vs **before** = the pre-LOOK-5 equivalent emulated client-side (film + air layers off, the old 25 % sunset heat haze back on, the low-integrity CanvasGroup visible as before) | after 523,892 / before 525,520 | 439 / 470 | after 2.99 / **5.72** · before 3.00 / 5.55 · **paired GPU after − before: mean +0.17, median −0.00 ms** (range −0.93..+1.16) | model: +0.33 (film_grain 128², lens_flare 256×128, vignette_corner 128²) − 1.00 (vignette 512² → 256², QA-B reclaim 7) = **−0.67 MB** (GUI images RGBA8 at QA-B's 5.33 MB/1024²; an in-engine A/B at this size is below the ±1–5 MB history spread) | LOOK-5 atmosphere and light. **How it got to GPU-neutral** (all paired in-scene A/Bs, same stage, 8–12 rounds): a full-screen translucent GUI layer costs ~0.5 ms here (plain 5 % Frame +0.54, 3D grain quad +0.69; film v1 with full-screen vignette + veil +0.42..+0.55), so the vignette became 4 corner pieces (0.42 × height), the glare lost its veil, the grain is screen-sized (+40 px jitter); the old full-screen low-integrity CanvasGroup was visible at GroupTransparency 1 and now hides when unused (+0.14..+0.36 recovered); heat haze off at sunset (66 beams, 25 %); dust bands cut from 101 short beams (9 rows) to 15 long ones at the wall/butte feet; sun shafts 5 → 3 (+0.28 for 5); SunRaysEffect disabled when a preset doesn't use it. First WIP build read +0.85 (10 rounds, 17 enemies). Per-part residuals (sunset wave, ~10 rounds each, noisy ±1 ms per block): shafts (5) +0.28, dust +0.07, grain +0.22, corners (0.62 size) +0.36. Draw calls −31 (heat haze gone at sunset). CPU unchanged (Luau: PostFxAir rewrites beams only on camera/sun/preset/storm change; film jitter 24 Hz). Dropping night removed the night-only searchlight cones, pit lamp, flares and mote emitters. |
| 2026-09-27 | ENV-4 step 0 (9fbc847) | Texture model (`texture_budget.py report`, every asset drawn once, one sky preset) | — | — | — | ENV 70.4 → **57.1 (−13.3)** | QA-B reclaim items for ENV: sky `Dn` face 1024² → 64² per preset (box-averaged, same mean; −5.3 MB, and −5.3 off each swap peak), cliff kit 1024² → 512² without metal maps (10.7 → 2.7, −8.0), rock-kit all-zero metal maps dropped (0 resident), terrain MaterialVariant roughness 1024² → 256² (not in GraphicsTexture). Dn face proven never on screen: magenta test face at max downward pitch in turret and gunsight views over five yaws, title, flank, basin and defeat cameras, 0 magenta pixels in 15 captures, 1.04 M in the void control (`qa/beauty/env-4/sky-dn-check/`). Dusk/Night skies retired (daylight only): their faces are no longer referenced. |
| 2026-09-27 | ENV-4 (working tree 01:30; LOOK-5 WIP → f7788f2 synced) | **Wave 9, now Sunset** (daylight-only plan), `airdropSeed` 1234, integrity held, MG bot, two 8 s blocks at ~45 s and ~58 s; fresh plays alternating the ENV-3F state (`Workspace.Env4Before`, Studio-only: ENV-3F scatter, 480-stud shadows, 0.35 far density, wash fringe kept, no zoning/patches/lane wear/conflict dressing) and ENV-4, quiet machine (Blender slots free, load 2.3–3.6) | before 455,814 / 439,475 · 455,079 / 471,009 · 468,466 / 470,241 → ENV-4 final 481,954 / 490,032 · 495,361 / 502,317 (**≈ +32k**) | before 409/401 · 378/371 · 376/367 → 435/408 · 431/413 (**≈ +38**) | before 3.03/5.89, 3.06/5.33 · 2.91/5.38, 2.90/5.26 · 2.98/5.21, 3.02/6.58 (GPU mean **5.61**) → ENV-4 final 3.08/5.60, 3.09/5.63 · 3.09/5.73, 3.04/5.16 (GPU mean **5.53**, CPU +0.07) | 248.5–253.3 → 253.5–254.2 (history-dependent; model: +1.4) | **GPU-neutral** (−0.08 ms, inside the ±0.7 ms block spread). The first ENV-4 build read 6.46 ms (+0.85): 51 wire Beams (+51 draw calls), full-detail far hulks (29k tris) and 2-ring patch discs; fixed by one instanced `Wire_Span` mesh per span, far hulks without kits/tracks (≈4.4k tris each), 1-ring discs and fewer patches/rocks, on top of the ENV-3F cuts (pebble patches 220 → 110, dressing shadows 480 → 300 studs, far density 0.35 → 0.2, wash `bankA` fringe dropped beyond 500 studs). Intermediate builds: 5.71, 5.79. Shadow tris before 273–389k, after 300–371k. **Textures:** two new atlases, `ConflictProps` 512² colour + 512² normal (0.7) and `GroundPatches` 512×256 RGBA + 256×128 normal (0.7) = **+1.4 MB**; hulks reuse the Tank/Buggy wreck sets (already in the model). ENV 58.5, team 123.0 MB. fps 60.0 in every block. |
| 2026-09-27 | ENV-4 fix 1 (weathered jersey barriers, sand drift skirts; working tree 03:50) | Wave 9 Sunset, `airdropSeed` 1234, integrity held, MG bot, two 8 s blocks (~45 s, ~58 s); then the staged Sunset turret view with the checkpoint + props shown/hidden client-side, 4 × 3 s alternations; quiet machine (Blender slots free, load 2.4) | wave 497.6k / 494.2k; staged view: checkpoint + props +9.1k (was +6.0k in the ENV-4 group A/B) | 436 / 399; checkpoint + props +15 (unchanged: same meshes) | wave 3.09 / 5.15, 3.01 / 6.37 (ENV-4 final 5.16–5.73); staged shown vs hidden 5.90 vs 5.63 (pairs swing ±1 ms) | — (model **+0.0**: the ConflictProps atlas is repainted at the same 512² colour + normal) | Fix adds **+3.8k tris** in the assets (Hesco_3 +180 ×12, Jersey +156 ×8, Tyre +72 ×2, Tyres +144 ×2), no draw calls, no texture memory; frame times inside the ENV-4 spread. fps 60.0. |
| 2026-09-27 | LOOK-4 (a06424d) | Texture model (`texture_budget.py report`, QA-B cost model: GUI images RGBA8 + full mips) + title and HUD in Studio (fresh plays, QualityLevel 15) | — (title: 2 ImageLabels; HUD: 3) | — | — | model: Look **4.1 → 4.4 in waves (+0.33, the 256² icon atlas)**; on the title only **+7.0** (key art 1024² 5.33 + logo 1024×256 1.33 + icons 0.33) | LOOK-4 weapon icons, title key art and logo, new `art` set (`assets/ui/art`, owner Look in `texture_map.py`). The key art and logo exist only on the title: `Screens` destroys both ImageLabels when the phase leaves Title (checked: no `KeyArt`/`Logo` under `Screens.Title` once the wave runs; they are rebuilt if the title comes back), so the busy-wave budget sees only the icon atlas; whether Roblox evicts a destroyed image's texture at once isn't measurable in Studio (§5.3: GraphicsTexture is process-wide and keeps history), so the title number is the model's upper bound. Look share with the icons 4.4 of 5 MB. No new geometry, particles or per-frame work (icon tint/transparency set in the existing strip update). |
| 2026-09-27 | VFX-4 (working tree 05:00; HEAD da0441a: LOOK-5 fix 1 and ENV-4 fix 1 in) | **Wave 9 Sunset**, `airdropSeed` 7, integrity held, MG autoplay (range 450; idle aim = turret beauty angle), QualityLevel 15, quiet machine (Blender slots free, load 2.0–3.0); paired in-session A/B, order alternated each round (`tools/vfx/qa/weather_ab.client.luau`): **weather** = all weather on vs `WeatherOff` (16 rounds × 3 + 2.5 s); **storm peak** = `WeatherStormForce` 1 vs none (12 × 4 + 2.5 s); **storm wall** = wall held at 1,100 studs (`WeatherStormFrontAt`) vs none (12 × 3 + 2.5 s) | weather: off 538k / on 541k · peak: 518k / 508k · wall: 513k / 512k | weather: 437 / 448 (**+11**) · peak: 425 / 421 · wall: 443 / 454 (+11; 22 wall beams in view) | weather: off 3.10 / **6.02** → on 3.14 / **5.84**, **paired GPU on − off: mean −0.19, median −0.24 ms** (range −1.44..+1.12) · peak: 3.14 / 6.17 → 3.15 / 6.17, **paired +0.00 / median −0.05** (−0.71..+0.81) · wall: 3.16 / 6.10 → 3.15 / 5.82, **paired −0.27 / −0.31** (−0.92..+0.47) | model **+0.0 MB** (no new textures: `DustDrift`, `searchlight_cone` reused; `VfxBirds` untextured) | **VFX-4 weather and life, GPU-neutral.** Live weather particles ~168 in the busy wave (density 0.52), ~900 at the storm peak, ~400 in the wall phase; streamers capped at 130/s (×(1 + storm)); every emitter on EffectsLod. **How it got neutral:** the first build read +0.44 ms mean (+0.41 median, 12 rounds; ~355 particles). Per-layer A/Bs were noisy (±1 ms blocks) but pointed at the crest and rim plumes (big sprites, one draw call per emitter). Fix: ambient layers thin with the number of live enemies (`Weather` density 1 → 0.35 from 4 to 12 enemies; crest/rim plumes off below density 0.55), 15 instead of 20 streamer tiles, 8 crests (was 14), 5 rims (was 8), rim LOD size ≤ 1.3×; second build +0.10 / +0.28 (16 rounds), final −0.19 / −0.24. fps 60 throughout; CPU unchanged (±0.04). Storm waves are 3 (Afternoon) and 7 (Sunset), both lighter than wave 9. **Fix 1 (storm wall as an arc, no tent peaks):** 3 layers × 12 pieces over 150° (27 beams in view) measured +0.28 / +0.39 ms (12 rounds), cut to 2 layers × 10 pieces over 130° (16 in view): +0.03 / +0.19 and +0.19 / +0.05 in two 12-round runs (ranges −0.90..+0.99, −1.50..+1.80), inside the block noise; +21–33 draw calls while the wall is up (~20 s of a storm wave). |
| 2026-09-27 | QA-F (33f37c4: VFX-4 fix 1 + QA-F VehicleLod 8c8669d; clean tree) | **Title**, 2 fresh plays, quiet machine (Blender slots free, load 1.7–2.6) | 483,677 / 481,651 | 417 / 416 | 3.02 / 6.29 · 3.05 / 6.02 | 222.3 / 228.1 (Edit floor 176.0) | QA-F final set (§6). Title renders the live camera behind LOOK-4's key art. fps 60.0, 1 %-low 53.8–56.9. |
| 2026-09-27 | same | **Wave 8 Sunset** + 3 extra debug sorties at 34 s (8 Infantry Road, Tank ScrubLeft, 2 Buggy ScrubRight), `airdropSeed` 7, integrity held, MG bot range 450 (idle aim = turret beauty angle), probe ~47 s | 529,588 / 522,864 | 437 / 434 | 3.03 / 6.24 · 3.09 / 4.82 (**GPU mean 5.53**) | 256.4 / 256.4 | 11 loads in the air + 4 transports at the probe. Shadows 325k/133, 330k/139. |
| 2026-09-27 | same | **Wave 9 Sunset** + 3 extra sorties (as above) | 583,554 / 586,023 | 480 / 484 | 3.24 / 5.21 · 3.24 / 6.26 (**GPU mean 5.74**) | 251.0 / 256.8 | 19 loads in the air + 8 transports. Shadows 351k/162, 340k/159. **The budget scene: inside the 6 ms working limit at the mean.** |
| 2026-09-27 | same | **Wave 10 boss Sunset** + 3 extra sorties | 554,465 / 550,350 | 461 / 465 | 3.01 / 6.46 · 3.16 / 6.09 (**GPU mean 6.28**) | 254.0 / 254.2 | 12–15 loads in the air + 4 transports, crawler + 10–11 infantry. **Just over the 6 ms working limit** (inside the ±0.7 ms block noise). Layer A/B below. |
| 2026-09-27 | same | **Wave 9 storm peak** (`WeatherStormForce` 1 → capped 0.8 at Sunset), ~58–63 s into wave 9 | 586,529 / 582,227 | 489 / 491 | 3.15 / 6.10 · 3.24 / 6.82 (mean 6.46) | 248.6 / 256.8 | Continuous-emitter particle estimate 890 / 1,319. Probed later in the wave than the no-storm rows (more enemies alive: Buggy 2–4, Tank 1–3, Infantry 4–11), so not a paired A/B; VFX-4's paired A/B (storm peak +0.00 ms) stands. |
| 2026-09-27 | same | **Wave 9 storm wall** held at 1,100 studs (`WeatherStormFrontAt` −1100, StormAmount 0.117) | 578,506 / 568,738 | 498 / 501 | 3.38 / 6.15 · 3.28 / 7.04 (mean 6.60) | 249.7 / 256.8 | Shadows 477k/291 and 476k/285: **over the ~250 shadow draw-call guidance, but not caused by the wall** (a none/wall/none/wall alternation read 88→358→350→377 shadow DC with the wall off as well; WeatherFx has 0 shadow casters). Shadow load follows the view: bot-off yaw sweep 111–291 shadow DC, highest looking east (yaw −80). |
| 2026-09-27 | same | **Boss-wave layer A/B** (wave 10 + 3 sorties, ~30 s in, MG bot; paired, order alternated) | — | FilmFx −10, AirdropFx +30, AirFx +15 | FilmFx on − off **+0.61 / +0.62 ms** (4 × 2.2 s and 6 × 2 s rounds; ranges +0.27..+0.89, +0.10..+1.11) · AirdropFx +0.15 (−0.19..+0.55) · AirFx −0.17 (−1.10..+0.59) · WeatherOff −0.95 (on cheaper; artefact of the switch) | — | The film layer is the single largest measurable layer in the boss wave; its parts (grain, corner vignette) do not A/B separately above the noise. Cheapest lever if the boss wave must be under 6 ms: see QA-F report. |
| 2026-09-27 | same | **Texture model** (`texture_budget.py report`, every asset drawn once, one sky) | — | — | — | model **130.0 MB** game-owned (ENV 58.5, HS 37.8, VFX 20.0, Look 11.1 incl. 7.0 title-only key art/logo, CHAR 2.7); in waves ≈ 123.3 | Inside the ~170 MB model line. No history-free Studio reading: the shared place is an unsaved `Place1`, so Studio was not restarted. Edit datamodel floor 176.0–181.5; busy waves 248.6–256.8 (history-dependent, §5.3). GraphicsParticles reads 144.6 in the Edit datamodel with no play running, so the 133–135 in play is process-wide, not the game's particles. |

## 5. Authoritative measurement and texture model (QA-B, 2026-09-26)

Full data and the per-asset table: `.superpowers/sdd/AIRDROP_ENVIRONMENT_PLAN/reports/QA-B.md`;
raw probe output and every experiment: `qa/beauty/perf/qa-b/`.

### 5.1 Method

- Apple M4 Pro, Studio playtest, `QualityLevel` 15, viewport 1177×1068
  (check capture `qa/beauty/qa-b/afternoon_2-turret.jpg`, 1190×1080),
  `Lighting.Technology` Future, streaming off. Machine quiet for all three
  reps (both Blender slots free, no headless Blender, load < 3.2).
- Three fresh plays. Each: Client QL15 + 40 s → probe **title** → Server
  integrity loop (`setIntegrity 100` every 2 s) + `startWave 1`, MG autoplay
  bot → probe at ~25 s → `startWave 9` → probe at ~50 s → `startWave 10` →
  probe at ~45 s. Probes are 8 s (`tools/qa/perf_probe.client.luau`).
- Commits: r1–r2 at `123467e` with a clean `src`/`assets/roblox`; r3 at
  `4aa152d` with LOOK-5 work in progress synced (`PostFx*`, `NightFx`).
- Everything-loaded: after the boss wave, every enemy kind spawned live and
  killed (wrecks of all kinds), a supply crate, every preset visited, then
  `tools/qa/texture_tour.client.luau` (all-round turret views, free
  cameras, a close-up of every model and every textured mesh, one gunsight
  aim).

### 5.2 Results by build (r1–r2 same build; r3 a later build)

r1 and r2 ran at `123467e` with a clean `src`/`assets/roblox`; r3 ran at
`4aa152d` with LOOK-5's uncommitted work synced (`PostFx*`, `NightFx`). The
**same-build figure is r1–r2**; the "all 3" rows mix builds and are not a
same-build spread.

| Scene | Build (plays) | Render CPU ms | Render GPU ms | Scene tris | Scene DC | Shadow tris / DC | GraphicsTexture MB |
|---|---|---|---|---|---|---|---|
| Title | **123467e clean (r1, r2)** | 2.90, 3.05 → **2.98** | 5.01, 5.75 → **5.38** | 448,198, 448,757 | 344, 345 | 58,380 / 47, 55,139 / 44 | 232.4, 229.9 |
| | 4aa152d + LOOK-5 WIP (r3) | 2.90 | 6.38 | 448,454 | 412 | 54,432 / 44 | 210.4 |
| | all 3, mixed builds | 2.95 (2.90–3.05) | 5.71 (5.01–6.38) | 448,470 (448,198–448,757) | 367 (344–412) | 55,984 / 45 | 224.2 (210.4–232.4) |
| Wave 1 afternoon | **123467e clean (r1, r2)** | 2.91, 3.16 → **3.04** | 5.19, 5.34 → **5.27** | 469,019, 457,525 | 391, 384 | 137,287 / 75, 143,538 / 81 | 236.3, 246.6 |
| | 4aa152d + LOOK-5 WIP (r3) | 3.09 | 6.05 | 471,635 | 473 | 149,231 / 84 | 215.1 |
| | all 3, mixed builds | 3.05 (2.91–3.16) | 5.53 (5.19–6.05) | 466,060 (457,525–471,635) | 416 (384–473) | 143,352 / 80 | 232.7 (215.1–246.6) |
| Wave 9 night | **123467e clean (r1, r2)** | 2.94, 2.93 → **2.94** | 5.57, 6.35 → **5.96** | 485,994, 498,680 | 400, 392 | 247,052 / 134, 237,125 / 125 | 254.7, 254.4 |
| | 4aa152d + LOOK-5 WIP (r3) | 3.01 | 6.78 | 474,669 | 449 | 262,007 / 144 | 253.1 |
| | all 3, mixed builds | 2.96 (2.93–3.01) | 6.23 (5.57–6.78) | 486,448 (474,669–498,680) | 414 (392–449) | 248,728 / 134 | 254.1 (253.1–254.7) |
| Wave 10 boss | **123467e clean (r1, r2)** | 2.86, 2.92 → **2.89** | 4.77, 5.82 → **5.30** | 487,007, 474,767 | 368, 357 | 222,843 / 122, 239,915 / 129 | 263.8, 255.4 |
| | 4aa152d + LOOK-5 WIP (r3) | 2.85 | 6.77 | 470,500 | 431 | 249,943 / 138 | 257.4 |
| | all 3, mixed builds | 2.88 (2.85–2.92) | 5.79 (4.77–6.77) | 477,425 (470,500–487,007) | 385 (357–431) | 237,567 / 130 | 258.9 (255.4–263.8) |
| Everything drawn once | 123467e-era s1, 4aa152d + WIP s4 | — | — | — | — | — | 301.9 (s1), 298.0 (s4); peak 308.5 during the tour |

Every probe: fps 60.0, 1 %-low 53.5–57.1; GraphicsParticles 78.6–83.0,
GraphicsTerrain 77.2–77.7, GraphicsMeshParts 11.8–13.2, GraphicsParts
9.6–10.6 MB.

Same-build spread (r1, r2): GPU within ±0.5 ms, GraphicsTexture ±1–5 MB
per scene. r3 (LOOK-5 WIP): +0.8 to +1.5 ms GPU and +53 to +86 draw calls
against the r1–r2 mean in every scene; its title texture reading is 20 MB
lower, which is history, not the build (the next fresh play of the same
build read 235.5).

Reading it:
- **Frame time:** CPU ~3 ms everywhere. On the clean build (r1–r2) the busy
  night wave reads GPU **5.96 ms mean (5.57, 6.35)**: at the 6 ms working
  limit, with r2 over it on its own. With LOOK-5's work in progress (r3) it
  reads 6.78, ~+0.8–1.5 ms in every scene, so LOOK-5 needs its own A/B
  before it lands. (The 3-play 6.23 mixes the two builds.)
- **Triangles** 450–500k on screen, shadows 55k (title) to 250k (night
  waves); draw calls 345–475; all inside budget.
- **Texture memory:** 224 → 259 MB from title to boss in play, ~300 MB once
  everything has been drawn. What those numbers contain is §5.3; the
  game's own share is §5.4.

### 5.3 What Studio's GraphicsTexture measures

Measured in QA-B sessions 1–4 (logs in `qa/beauty/perf/qa-b/`):

1. **It's process-wide and keeps history.** The Edit datamodel (baseplate,
   stock sky) reads 175–178 MB before or after a play; a fresh play of the
   same build read 210.4 at the title and, five minutes later, 235.5. Some
   of any Studio reading is other sessions' leftovers, which a player's
   client doesn't have. Only a freshly started Studio gives a floor
   (§5.6).
2. **Textures load their full mip chain the first time they're drawn and
   stay.** A SurfaceAppearance, Decal or ImageLabel costs the same drawn
   16 px or full screen; nothing is released when the camera turns away
   (40 s flat after the tour). So a long run converges on the
   "everything drawn once" number, not on the turret-view number.
   **Particle textures are the exception:** they stream by on-screen size
   and stayed at or below mip 1 (14 flipbooks: +0.05 MB as ~50-px
   particles, +13.3 MB as ~700-px particles).
3. **Removing things doesn't reliably free memory** (cache, 0.33 MB steps,
   order-dependent: session 1 freed 137.6 of 301.9 MB and then nothing
   more after deleting the whole world), so remove-A/Bs undercount. Use
   additive A/Bs with never-drawn ids.
4. **Not in this tag:** terrain MaterialVariant textures (a drawn override
   added 0.00 MB to GraphicsTexture), render targets (shadows, post
   effects and QualityLevel 1 changed nothing). `GraphicsParticles`
   (~80 MB, same in the Edit datamodel) is not particle textures: a
   particle's texture lands in GraphicsTexture.

### 5.4 Texture cost model (calibrated in-engine)

Additive, never-drawn ids on a magnified quad (`tools/qa/texture_calib.client.luau`):

| What | Resident at full mips | Per 1024² |
|---|---|---|
| SurfaceAppearance / MaterialVariant colour (no alpha) | 4 bpp (BC1) | 0.67 MB |
| colour with real alpha | ≤ 32 bpp (fits ENV-3F's A/B) | ≤ 5.33 MB |
| normal map | 8 bpp | 1.33 MB |
| roughness + metalness, packed into one map (also present when a normal map is) | 4 bpp | 0.67 MB |
| a full colour/normal/rough/metal set | — | 2.67 MB (measured 2.62–2.67) |
| Sky face, Decal/Texture, ParticleEmitter, Beam, ImageLabel | 32 bpp, uncompressed RGBA8 | 5.33 MB (sky: 6 faces = 32.06 MB measured) |
| particle sheet in play | ≤ mip 1 | ≤ 1.33 MB |

Checks against independent A/Bs: HS-6's TrimAirdrop 512² set (model 0.67,
measured +0.67), ENV-3F strips/dressing (model ≤ 3.6 / 1.4, measured 3.0 /
1.2), the sky (32.0 / 32.06). Large landscape meshes read higher than the
model (ENV-2's staged adds: mesa +22.0 vs 12.8, walls + buttes +13.5 vs
6.0; a wall-chunk clone +4.67 vs 2.67 on the quad) for a reason not found.

`tools/qa/py tools/qa/texture_budget.py report` prints the ranked per-asset
table from the id maps (output: `qa/beauty/perf/qa-b/texture-model.md`; `tools/qa/texture_map.py` finds each id's source
file by its upload hash).

**Game-owned GraphicsTexture with every asset drawn once and one sky
preset: 157.8 MB** — ENV 70.4 (sky 32.0, mesa 12.8, cliff kit 10.7),
HS 55.8 (emplacement 19.5, Siege Crawler 11.3, vehicles 16.1, gunsights
5.3), VFX 24.0 (particle sheets ≤ 1.33 each, the ScorchMark decal 5.33),
Look 5.0, CHAR 2.7. Plus: +32 MB for ~1.5 s at each sky swap (two skies
resident, session 1), and the terrain MaterialVariants (21.3 MB by the
model) outside this tag. Largest single items: the sky (32 MB, uncompressed)
and the emplacement (19.5 MB).

### 5.5 Reclaim list

Ranked cuts with savings, visual risk and owner are in the QA-B report
(§ "Reclaim list"); the lead rules on them and the owners apply them. ~30 MB
is reachable with no visible change at gameplay distances: sky `Dn` face to
64² (5.3), ScorchMark decal to 512² (4.0), cliff kit to 512² (8.0), Siege
Crawler to 512² (8.0), Tank/Buggy/Helicopter/Jet to 512² (10.0) = 35.3 MB.

**Applied (RECLAIM-HS, 2026-09-27):** items 2, 4, 5 and the HS/CHAR part of 14, measured with the model
(`tools/qa/py tools/qa/texture_budget.py report`, before/after tables in the RECLAIM-HS report):

| QA-B item | Cut | Before → after (model MB) | Saved |
|---|---|---|---|
| 4 | Siege Crawler 4 sets colour/normal/roughness 1024² → 512² (metal already 512², wreck 512² kept) | 11.3 → 3.3 | **8.0** |
| 5 | Tank (2 sets), Buggy, Helicopter, Jet colour/normal/roughness 1024² → 512² (`TrimEnemy` kept) | 5.4 + 3 × 2.7 = 13.5 → 1.4 + 3 × 0.7 = 3.5 | **10.0** |
| 2 | `ScorchMark` decal 1024² → 512² RGBA8 | 5.3 → 1.3 | **4.0** |
| 14 | Rigid `Infantry` and `InfantrySpike` maps no longer uploaded or referenced; SupplyCrate chute all-zero metalness dropped; stale `Tank_gear_*`/`Buggy_wheels_*` files deleted | never drawn / packed with roughness | 0 resident |
| | **Total** | HS 55.8 → 37.8, VFX 24.0 → 20.0 | **22.0** |

How: the uploaded maps are 512² box-averaged copies (`GAME_PX`, `docs/ASSET_PIPELINE.md` → "Game-resolution
maps"); the Blender bakes, previews and exported 1024² PNGs are unchanged. At each vehicle's nearest gunsight
range the 512² maps still give ≥ 1.1 texels per screen pixel, so the GPU was already sampling mip ≥ 1 of the
1024² maps. Gunsight before/after captures at those ranges: `qa/beauty/reclaim-hs/`.

### 5.6 Recommendation

- Hold the **game-owned** texture total (model, everything drawn once) to a
  budget instead of the raw Studio reading: 157.8 MB today. P0's 86 MB
  Studio reading (pre-face-lift assets, stock sky) suggests a fresh-process
  floor of ~50–80 MB, so ~170 MB game-owned matches the ~250 MB line.
- For QA-F: restart Studio when nobody holds the lock, read the Edit
  datamodel's GraphicsTexture (the floor), then run §5.1 once. That is the
  only history-free Studio number.

## 6. Final measurement (QA-F, 2026-09-27)

Build `33f37c4` (every Update 2 milestone in, VFX-4 fix 1, QA-F's VehicleLod
fix), clean tree, quiet machine, viewport 1177×1068, QualityLevel 15. Two
fresh plays, each title → wave 8 → wave 9 → storm peak → storm wall → wave
10, all at Sunset with three extra debug sorties on top of each wave's own.
Rows in §4; raw probe output `qa/beauty/perf/qa-f/session1-perf.txt`.

| Scene | GPU ms (2 plays, mean) | CPU ms | Scene tris | Scene DC | Verdict vs §1 |
|---|---|---|---|---|---|
| Title | 6.29, 6.02 (6.16) | 3.0 | 482–484k | 416–417 | over 6 ms by 0.16 (the live camera behind the key art; P0 title was 8.92) |
| Wave 8 Sunset | 6.24, 4.82 (5.53) | 3.0–3.1 | 523–530k | 434–437 | pass |
| **Wave 9 Sunset (budget scene)** | 5.21, 6.26 (**5.74**) | 3.2 | 584–586k | 480–484 | **pass** |
| Wave 10 boss Sunset | 6.46, 6.09 (6.28) | 3.0–3.2 | 550–554k | 461–465 | marginal: +0.28 over the working limit, inside the block noise |
| Wave 9 storm peak (0.8) | 6.10, 6.82 (6.46) | 3.2 | 582–587k | 489–491 | marginal (probed later in a fuller wave; VFX-4 paired A/B: +0.00) |
| Wave 9 storm wall | 6.15, 7.04 (6.60) | 3.3–3.4 | 569–579k | 498–501 | marginal; shadow DC 285–291 over guidance (view, not the wall) |

- Triangles ≤ 587k (< ~1,000,000) and scene draw calls ≤ 501 (< ~600):
  pass everywhere. Shadow draw calls exceed the ~250 guidance in some views
  (east-facing, late in busy waves: up to 377).
- fps 60.0 in every block; 1 %-low 52.9–56.9.
- Texture memory: model 130.0 MB game-owned (§4 row), inside the ~170 MB
  model line; raw Studio 248.6–256.8 MB in the busy waves against the
  ~250 MB line, with 176–182 MB of that already present in the idle Edit
  datamodel (history, §5.3).
- CPU render ≤ 3.4 ms everywhere.
- Heuristic for a mid-range PC (×2.5): the worst mean (storm wall 6.60 ms)
  → 16.5 ms, at the 60 fps line; the budget scene (5.74) → 14.4 ms.

