# Texture cost model output (QA-B) — `tools/qa/py tools/qa/texture_budget.py report qa/beauty/perf/qa-b/inventory-allloaded.txt`


| # | Asset | Owner | Maps | MB at full res (model) | Drawn in the all-loaded scene | Where it's seen |
|---|---|---|---|---|---|---|
| 1 | sky Afternoon | ENV | 6 (6x 1024x1024) | 32.0 | 0.0 | always, full screen; one preset resident (two for ~1.5 s at a swap) |
| 2 | sky Dusk | ENV | 6 (6x 1024x1024) | 32.0 | 0.0 | always, full screen; one preset resident (two for ~1.5 s at a swap) |
| 3 | sky LateAfternoon | ENV | 6 (6x 1024x1024) | 32.0 | 0.0 | always, full screen; one preset resident (two for ~1.5 s at a swap) |
| 4 | sky Night | ENV | 6 (6x 1024x1024) | 32.0 | 32.0 | always, full screen; one preset resident (two for ~1.5 s at a swap) |
| 5 | sky Sunset | ENV | 6 (6x 1024x1024) | 32.0 | 0.0 | always, full screen; one preset resident (two for ~1.5 s at a swap) |
| 6 | vfx (particles: ≤ mip 1) | VFX | 16 (14x 1024x1024, 1x 512x512, 1x 512x128) | 23.3 | 4.3 | combat effects; resident once used, any wave; size on screen varies |
| 7 | terrain (not in GraphicsTexture) | ENV | 24 (8x color 1024, 8x normal 1024, 8x rough 1024) | 21.3 | 21.3 | always, 20-2000 studs |
| 8 | Emplacement | HS | 32 (7x color 1024, 7x normal 1024, 7x rough 1024, 4x metal 1024, 1x color 512, 1x normal 512, 1x rough 512, 1x color 256, 1x metal 256, 1x normal 256, 1x rough 256) | 19.5 | 19.5 | always, 0-30 studs (the player's own turret pit); title/flank 400-700 |
| 9 | Landscape_Mesa | ENV | 22 (11x color 1024, 11x normal 512) | 12.8 | 12.8 | always, 10-200 studs below/around the turret |
| 10 | SiegeCrawler | HS | 20 (4x color 1024, 4x metal 512, 4x normal 1024, 4x rough 1024, 4x color 512) | 11.3 | 11.3 | wave 10 only, 400-1300 studs (night) |
| 11 | Tank | HS | 10 (2x color 1024, 2x metal 512, 2x normal 1024, 2x rough 1024, 2x color 256) | 5.4 | 5.4 | waves 3, 5, 7, 9; 150-1200 studs |
| 12 | Gunsights | HS | 8 (2x color 1024, 2x metal 1024, 2x normal 1024, 2x rough 1024) | 5.3 | 0.0 | while aiming (right mouse), full screen; preloaded at start |
| 13 | GroundStrips | ENV | 4 (2x normal 512, 1x color 512, 1x color 1024) | 3.6 | 3.6 | road/wash edges, 50-1300 studs |
| 14 | SupplyCrate | HS | 8 (1x color 512, 1x metal 512, 1x normal 512, 1x rough 512, 1x color 1024, 1x metal 1024, 1x normal 1024, 1x rough 1024) | 3.3 | 0.0 | waves with crates (3-10), falling toward the mesa |
| 15 | Buggy | HS | 5 (1x color 1024, 1x metal 512, 1x normal 1024, 1x rough 1024, 1x color 256) | 2.7 | 2.7 | waves 2, 5, 7, 9; 150-1200 studs |
| 16 | Helicopter | HS | 4 (1x color 1024, 1x normal 1024, 1x rough 1024, 1x color 256) | 2.7 | 2.7 | waves 4, 6, 8, 9; 150-900 studs |
| 17 | Jet | HS | 4 (1x color 1024, 1x normal 1024, 1x rough 1024, 1x color 256) | 2.7 | 2.7 | waves 6-9, fast passes 100-1000 studs |
| 18 | TrimEnemy | HS | 5 (1x color 1024, 1x metal 1024, 1x normal 1024, 1x rough 1024, 1x color 256) | 2.7 | 2.7 | every vehicle (waves 2-10) |
| 19 | Cliff_Butte | ENV | 4 (1x color 1024, 1x metal 1024, 1x normal 1024, 1x rough 1024) | 2.7 | 2.7 | wall bases, 500-1400 studs |
| 20 | Cliff_Corner | ENV | 4 (1x color 1024, 1x metal 1024, 1x normal 1024, 1x rough 1024) | 2.7 | 2.7 | wall bases, 500-1400 studs |
| 21 | Cliff_Wall_A | ENV | 4 (1x color 1024, 1x metal 1024, 1x normal 1024, 1x rough 1024) | 2.7 | 2.7 | wall bases, 500-1400 studs |
| 22 | Cliff_Wall_B | ENV | 4 (1x color 1024, 1x metal 1024, 1x normal 1024, 1x rough 1024) | 2.7 | 2.7 | wall bases, 500-1400 studs |
| 23 | Infantry (never drawn) | CHAR | 4 (1x color 1024, 1x metal 1024, 1x normal 1024, 1x rough 1024) | 2.7 | 0.0 | unused since CHAR-2 (rigid parts' appearances destroyed) |
| 24 | InfantrySkinned | CHAR | 4 (1x color 1024, 1x metal 1024, 1x normal 1024, 1x rough 1024) | 2.7 | 2.7 | every wave, 60-700 studs |
| 25 | look | Look | 5 (2x 128x512, 1x 128x128, 1x 256x128, 1x 512x512) | 2.2 | 0.3 | night searchlight cones, heat haze (day), vignette |
| 26 | GroundDressing | ENV | 2 (1x color 512, 1x normal 256) | 1.5 | 1.5 | basin floor, 50-1000 studs (1,214 instances) |
| 27 | kit | Look | 4 (1x 512x512, 1x 128x128, 1x 64x64, 1x 64x8) | 1.4 | 1.4 | HUD, always |
| 28 | motion | Look | 2 (1x 128x1024, 1x 512x256) | 1.3 | 1.3 | tank/crawler treads |
| 29 | Landscape_FarWall | ENV | 8 (4x color 512, 4x normal 256) | 1.2 | 1.2 | far walls/buttes, 600-2000 studs |
| 30 | Landscape_FlankLeft | ENV | 8 (4x color 512, 4x normal 256) | 1.2 | 1.2 | far walls/buttes, 600-2000 studs |
| 31 | Landscape_FlankRight | ENV | 8 (4x color 512, 4x normal 256) | 1.2 | 1.2 | far walls/buttes, 600-2000 studs |
| 32 | Landscape_RearWall | ENV | 8 (4x color 512, 4x normal 256) | 1.2 | 1.2 | far walls/buttes, 600-2000 studs |
| 33 | Rock_Boulder_A | ENV | 4 (1x color 512, 1x metal 512, 1x normal 512, 1x rough 512) | 0.7 | 0.7 | basin floor scatter, 100-1000 studs |
| 34 | Rock_Boulder_B | ENV | 4 (1x color 512, 1x metal 512, 1x normal 512, 1x rough 512) | 0.7 | 0.7 | basin floor scatter, 100-1000 studs |
| 35 | Rock_Boulder_C | ENV | 4 (1x color 512, 1x metal 512, 1x normal 512, 1x rough 512) | 0.7 | 0.7 | basin floor scatter, 100-1000 studs |
| 36 | Rock_Rubble | ENV | 4 (1x color 512, 1x metal 512, 1x normal 512, 1x rough 512) | 0.7 | 0.7 | basin floor scatter, 100-1000 studs |
| 37 | Rock_Slab | ENV | 4 (1x color 512, 1x metal 512, 1x normal 512, 1x rough 512) | 0.7 | 0.7 | basin floor scatter, 100-1000 studs |
| 38 | Rock_Spire | ENV | 4 (1x color 512, 1x metal 512, 1x normal 512, 1x rough 512) | 0.7 | 0.7 | basin floor scatter, 100-1000 studs |
| 39 | TrimAirdrop (not in game yet) | HS | 3 (1x color 512, 1x normal 512, 1x rough 512) | 0.7 | 0.0 | Update 2 shared airdrop trim sheet (HS-6, not in game yet) |
| 40 | VfxDebris | VFX | 4 (1x color 512, 1x metal 512, 1x normal 512, 1x rough 512) | 0.7 | 0.0 | explosion debris, briefly |
| 41 | Landscape_Butte1 | ENV | 2 (1x color 512, 1x normal 256) | 0.3 | 0.3 | far walls/buttes, 600-2000 studs |
| 42 | Landscape_Butte2 | ENV | 2 (1x color 512, 1x normal 256) | 0.3 | 0.3 | far walls/buttes, 600-2000 studs |
| 43 | Landscape_Butte3 | ENV | 2 (1x color 512, 1x normal 256) | 0.3 | 0.3 | far walls/buttes, 600-2000 studs |
| 44 | Landscape_Butte4 | ENV | 2 (1x color 512, 1x normal 256) | 0.3 | 0.3 | far walls/buttes, 600-2000 studs |
| 45 | InfantrySpike (never drawn) | CHAR | 4 (1x color 256, 1x metal 256, 1x normal 256, 1x rough 256) | 0.2 | 0.0 | unused (spike test) |

Game-owned GraphicsTexture, every asset drawn once, one sky preset: **157.8 MB** (ENV 70.4, HS 55.8, VFX 24.0, Look 5.0, CHAR 2.7); +32 MB for ~1.5 s at each sky swap.
Of that, drawn in the inventoried scene: 127.5 MB.
