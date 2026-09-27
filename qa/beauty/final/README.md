# Final beauty set and QA verdicts (QA-F, Update 2)

Captured 2026-09-27 07:26–07:30 PDT on build **`33f37c4`** (clean tree: every
Update 2 milestone, VFX-4 fix 1 `d23f767`, QA-F's VehicleLod fix `8c8669d`).
Studio viewport 1177×1068, every capture 1190×1080 "exact" (`manifest.json`),
QualityLevel 15, 40 s terrain wait. Daylight presets only (Afternoon,
LateAfternoon, Sunset). Every image listed here was viewed.

Full report with commands and raw numbers:
`.superpowers/sdd/AIRDROP_ENVIRONMENT_PLAN/reports/QA-F.md`.

## 1. The set

18 images: `<tod>_<n>-<shot>.jpg`, six cameras × three presets, contact
sheet `contact.jpg`. Staged with the standard rig (`tools/qa/BEAUTY.md`):
same cameras, subjects and HUD as `p0-baseline`, so every pair compares.

- Ambient weather is hidden in staged shots (the rig's default, so sets stay
  comparable). It appears in the drop, storm and live frames below and in
  `checks/weatherlive_afternoon_4-flank.jpg`.
- The title shot shows LOOK-4's key art; it is the same art at all three
  presets (only the grain differs).
- No debug overlays, test warnings or staging artefacts in the 18 frames
  (checked one by one; the translucent strips in the gunsight foreground are
  ENV-4's concertina coils and barriers seen from above).

**Before/after:** `qa/beauty/compare/p0-baseline_vs_final/` (colour) and
`p0-baseline_vs_final_gray/` (grayscale): 18 labelled pairs each plus
`contact.jpg`. p0-baseline also holds dusk/night; only the three daylight
presets pair up.

Verdict per camera (final vs p0-baseline, all three presets):

| Shot | Verdict |
|---|---|
| 1 title | Clear improvement. Blocky mesa slab and stock terrain → key art: emplacement at sunset, transport and a stick of paratroopers, tank under cargo chutes. |
| 2 turret | Clear improvement. Flat orange sand, voxel walls and a bare sky → zoned basin (scrub, rocks, patches, tyre tracks, checkpoint barriers, hulks), layered sandstone walls fading into haze, clouded sky. |
| 3 gunsight | Clear improvement. The mesa wall and floor now have strata and detail; enemies stay the darkest shapes (probe below). |
| 4 flank | Clear improvement. Bare floor and stamped-crater wall → dressed basin, carved walls with depth haze. |
| 5 basin ("night" camera) | Clear improvement. Same as 4, with the mesa and emplacement modelled. |
| 6 boss | Clear improvement. The crawler reads against a dressed road; the long sunset mesa shadow adds depth. |

No regression found in any pair.

## 2. Drop sequence: `drop/` (`sequence.jpg`)

Wave 7 at Sunset, airdrop seed 7, turret view, live (not staged):

1. `01_sunset_transports-enter_banner-radar.jpg`: two transports crossing, the INCOMING AIRDROP banner (left flank, buggies) and radar marks.
2. `02_sunset_trooper-leaves-ramp.jpg`: a trooper leaves the ramp with his streamer.
3. `03_sunset_canopies-open_tank-cluster.jpg`: a stick of canopies open over the far basin, a tank under four cargo chutes, more transports.
4. `04_sunset_stick-descending.jpg`: a stick of eight descending toward the road.
5. `05_sunset_cargo-cluster-low_buggy-platform.jpg`: a cargo cluster low over the left rim, a buggy platform chute.
6. `06_sunset_landed-running-in_crate-chute.jpg`: the stick has landed and runs in; a supply-crate chute.

Hand-off (no pop) is measured, not just filmed: 233 hand-offs in the full run
with 0 frames where the descending body and the enemy both drew, 0 empty
frames between them, root gap ≤ 0.41 studs (infantry), 0.37 (tanks), 1.68
(buggies, already driving when they replicate). No effect:
`checks/noeffect_gunsight_deflect.jpg` (sparks on a trooper under canopy,
Deflects +7, score unchanged).

## 3. Storm sequence: `storm/` (`sequence.jpg`)

Wave 7's own storm (Sunset, capped at 0.8 by `DustStorm.PRESET_CAP`), live
from the turret, same framing:

1. `01_…_t14_wall-1763`: wall far out (StormAmount 0), a tank under cargo chutes.
2. `02_…_t27_wall-1038_amount-0.11`: warm haze rising over the far rim.
3. `03_…_t38_wall-428_amount-0.36`: the basin browning out, chutes still dark.
4. `04_…_t49_peak-0.80`: peak: the far wall is gone, the floor, lanes and enemies remain.
5. `05_…_t71_clearing-0.49`: clearing, transports and a stick of canopies read as dark shapes.
6. `06_…_clear-0`: 4 s after StormAmount reached 0 (from the first storm run); a light warm haze is still easing out.

Extras: `extra_…peak-0.80_turret-yaw28.jpg`, `extra_…clearing-0.54.jpg`, and
the storm-peak gunsight frames used for readability below. Live peaks from the
full run: `live/live_w3_storm_peak_afternoon.jpg`,
`live/live_w7_storm_peak_sunset.jpg`.

## 4. "Roblox-tell" checklist (FACELIFT_PLAN §5) and Update 2 goals

| Item | Verdict | Image |
|---|---|---|
| No voxel stair-steps | PASS | `afternoon_4-flank.jpg`, `afternoon_5-night.jpg` (modelled, layered walls; p0 had stamped voxel walls) |
| No stock terrain textures | PASS | `afternoon_2-turret.jpg`, `afternoon_4-flank.jpg` (custom sand/road MaterialVariants, patches) |
| No `SmoothPlastic` on hero objects | PASS | `afternoon_6-boss.jpg` (crawler, emplacement), `afternoon_5-night.jpg` (tank, helicopter) |
| No default sky | PASS | every preset's `_2-turret.jpg`, `sunset_5-night.jpg` |
| No built-in particle textures | PASS | `drop/04_sunset_stick-descending.jpg` (wreck fire/smoke), `live/live_w10_boss_cannon_charge.jpg` (blasts, dust) |
| No clean untextured boxes | PASS, one note | Checkpoint barriers and hesco read as weathered blocks up close (`sunset_3-gunsight.jpg`, bottom right); acceptable. `VfxBirds` is untextured but a few pixels wide. |
| No robotic stepped motion | PASS (motion, not stills) | Hand-off recorder 0 pops over 233 landings; LOOK-3/3B smoothing; full-run observation |
| **Update 2: no bare repeating sand** | PASS | `afternoon_2-turret.jpg`, `afternoon_4-flank.jpg`, `lateafternoon_5-night.jpg` |
| **Update 2: depth in the air** | PASS | `afternoon_2-turret.jpg` (far walls and buttes recede in haze), `sunset_4-flank.jpg`, `storm/03_…` |
| **Update 2: living weather** | PASS, subtle | Storm cycle `storm/sequence.jpg`; wreck smoke `drop/04_…`; ambient streamers are faint from the flank camera (`checks/weatherlive_afternoon_4-flank.jpg`), as VFX-4 reported |

## 5. Readability

Probe: `tools/vfx/qa/readability.py` (LOOK-5/VFX-4 measure: darkest 10 % of
each enemy's projected box vs the median of a ring around it; rule ≥ 3:1).
Boxes: `readability/*_boxes.json`; annotated probes `readability/*_probe.jpg`.
Grayscale sheets: `gray/readability.jpg` (whole set),
`gray-storm/readability.jpg` (storm peaks and a drop).

Engagement range (gunsight, FOV 32; 5 infantry 230–276, buggy 312, tank 414):

| Condition | min | mean | limiting enemy |
|---|---|---|---|
| Afternoon | 3.84 | 8.14 | tank 414 |
| LateAfternoon | 3.87 | 5.86 | tank 414 |
| Sunset | **3.10** | 5.08 | infantry 230 (in the mesa shadow) |
| Afternoon storm 1.0 (wave 3) | 3.17 | 7.81 | tank 414 |
| Sunset storm 0.8 (wave 7) | 3.21 | 4.30 | tank 414 (infantry 230: 3.25) |

Every enemy ≥ 3:1 at every preset and at both storm peaks.

Per enemy type at its engagement range:
- **Infantry** (230–276, gunsight): ≥ 3.10. PASS.
- **Buggy** (312, gunsight): 5.54–8.00. PASS.
- **Tank** (414, gunsight): 3.17–5.69. PASS.
- **Siege Crawler** (438, unzoomed boss view): 3.37 / 4.33 / 6.57. PASS.
- **Helicopter** and **jet**: sky subjects, dark silhouettes against the sky in every frame they appear (`*_5-night.jpg`, `*_2-turret.jpg`, `live/live_w6_jet_warning.jpg`, storm frames). PASS by eye.
- **Boss escorts in the unzoomed boss view** (367–390 studs, ~3 px wide): the probe reads 4.30–5.53 for one and 1.49–2.69 for the other two. The figures are plainly dark on the sand in the viewed crops; the probe undercounts figures this thin (the box is 9 px wide). At gunsight zoom infantry are ≥ 3.1. Reported, not counted as a failure.

## 6. Other folders

- `live/`: from the full 10-wave run: storm peaks (waves 3 and 7), the jet warning (wave 6), the LateAfternoon → Sunset intermission (a: WAVE 6 CLEAR during the swap, b: WAVE 7 banner), the boss cannon charge (wave 10).
- `checks/`: no-effect deflect; weather live at the flank camera.
- Perf numbers: `docs/PERF_BUDGET.md` §6 (busy wave 9 Sunset GPU 5.74 ms mean: pass; boss 6.28: marginal).
