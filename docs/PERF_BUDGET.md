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
| Texture memory | **< ~250 MB** | `Stats:GetMemoryUsageMbForTag(Enum.DeveloperMemoryTag.GraphicsTexture)` |
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
