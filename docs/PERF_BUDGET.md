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
