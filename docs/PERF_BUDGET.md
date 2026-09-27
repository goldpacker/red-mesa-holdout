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
| 2026-09-26 | QA-B r1–r2 123467e, r3 4aa152d + LOOK-5 work in progress | **Title**, 3 fresh plays (mean, range) | 448,470 (448,198–448,757) | 367 (344–412) | 2.95 / 5.71 (CPU 2.90–3.05, GPU 5.01–6.38) | 224.2 (210.4–232.4) | QA-B authoritative set, §5.2. r3's +67 draw calls and +1.0 ms GPU come with LOOK-5's work in progress (106 more beams at the title). |
| 2026-09-26 | same | **Wave 1 afternoon**, ~25 s in, MG bot | 466,060 (457,525–471,635) | 416 (384–473) | 3.05 / 5.53 (CPU 2.91–3.16, GPU 5.19–6.05) | 232.7 (215.1–246.6) | 1–4 infantry on screen (airdrops land from ~15 s). |
| 2026-09-26 | same | **Wave 9 night**, ~50 s in, integrity held, MG bot | 486,448 (474,669–498,680) | 414 (392–449) | 2.96 / 6.23 (CPU 2.93–3.01, GPU 5.57–6.78) | 254.1 (253.1–254.7) | Buggy 2, Helicopter 1, Jet 1, Tank 1 in all three; shadows 248.7k tris / 134 DC. GPU over the 6 ms limit in r2 (6.35) and r3 (6.78, LOOK-5 WIP). |
| 2026-09-26 | same | **Wave 10 boss**, ~45 s in, integrity held, MG bot | 477,425 (470,500–487,007) | 385 (357–431) | 2.88 / 5.79 (CPU 2.85–2.92, GPU 4.77–6.77) | 258.9 (255.4–263.8) | Siege Crawler + helicopter + 5–9 infantry. |
| 2026-09-26 | QA-B s1 aecd5a1 + then-WIP (AD-1, ENV-3F, LOOK-3B), s4 4aa152d + LOOK-5 WIP | **Everything drawn once** (every enemy kind live and wrecked, crate, all presets visited, 430–480-view close-up tour) | — | — | — | 301.9 (s1), 298.0 (s4); peak 308.5 | Upper bound of what a long run makes resident in this Studio process; game-owned share per the model 157.8 MB (§5.4). |

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

### 5.2 Results (mean, range over 3 plays)

| Scene | Render CPU / GPU ms | Scene tris | Scene DC | Shadow tris / DC | GraphicsTexture MB | GraphicsParticles / Terrain / MeshParts / Parts MB | fps / 1 %-low |
|---|---|---|---|---|---|---|---|
| Title | 2.95 (2.90–3.05) / 5.71 (5.01–6.38) | 448,470 (448,198–448,757) | 367 (344–412) | 55,984 / 45 | 224.2 (210.4–232.4) | 79.9 / 77.7 / 11.8 / 9.8 | 60.0 / 55.9 |
| Wave 1 afternoon | 3.05 (2.91–3.16) / 5.53 (5.19–6.05) | 466,060 (457,525–471,635) | 416 (384–473) | 143,352 / 80 | 232.7 (215.1–246.6) | 80.4 / 77.2 / 13.2 / 10.1 | 60.0 / 55.9 |
| Wave 9 night | 2.96 (2.93–3.01) / 6.23 (5.57–6.78) | 486,448 (474,669–498,680) | 414 (392–449) | 248,728 / 134 | 254.1 (253.1–254.7) | 80.6 / 77.2 / 13.2 / 10.4 | 60.0 / 55.5 |
| Wave 10 boss | 2.88 (2.85–2.92) / 5.79 (4.77–6.77) | 477,425 (470,500–487,007) | 385 (357–431) | 237,567 / 130 | 258.9 (255.4–263.8) | 80.7 / 77.2 / 13.2 / 10.4 | 60.0 / 55.3 |
| Everything drawn once | — | — | — | — | 298.0–301.9 (peak 308.5 during the tour) | — | — |

Same-build spread (r1, r2): GPU within ±0.5 ms, GraphicsTexture ±1–5 MB
per scene. r3 (LOOK-5 WIP): +0.8 to +1.5 ms GPU and +53 to +86 draw calls
against the r1–r2 mean in every scene; its title texture reading is 20 MB
lower, which is history, not the build (the next fresh play of the same
build read 235.5).

Reading it:
- **Frame time:** CPU ~3 ms everywhere. GPU sits at 5–6.8 ms, and the busy
  night wave (6.23 mean) is over the 6 ms working limit; r3 suggests
  LOOK-5's post layers cost ~+1 ms, so LOOK-5 needs its own A/B before it
  lands.
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

### 5.6 Recommendation

- Hold the **game-owned** texture total (model, everything drawn once) to a
  budget instead of the raw Studio reading: 157.8 MB today. P0's 86 MB
  Studio reading (pre-face-lift assets, stock sky) suggests a fresh-process
  floor of ~50–80 MB, so ~170 MB game-owned matches the ~250 MB line.
- For QA-F: restart Studio when nobody holds the lock, read the Edit
  datamodel's GraphicsTexture (the floor), then run §5.1 once. That is the
  only history-free Studio number.
