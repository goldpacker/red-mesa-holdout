# Beauty shots, comparisons, LOS check and perf probe

QA tooling for the visual face-lift (`docs/FACELIFT_PLAN.md` §5,
`docs/FACELIFT_TEAM.md` quality gates). Owner: QA-tools. Everything here
works from an agent session with the Roblox Studio MCP, the computer-use
tools (to bring Studio forward) and Bash.

| What | Command |
|---|---|
| Capture a set (full or subset) | §2 — `python3 tools/qa/beauty_plan.py <set> [--shots 2,4] [--tods sunset,night]` prints the steps |
| File the captures | `tools/qa/py tools/qa/beauty_save.py --set <set> --since <epoch> <names…>` |
| Before/after pairs + contact sheet | `tools/qa/py tools/qa/beauty_compare.py p0-baseline <set> [--gray]` |
| Grayscale readability sheet | `tools/qa/py tools/qa/grayscale.py --set <set>` or `… <images> --out <dir>` |
| Turret line of sight to every lane end | `ServerStorage.RedMesaDebug:Invoke("losCheck")` (Server) |
| Lane ground heights | `ServerStorage.RedMesaDebug:Invoke("groundCheck", { verbose = true })` (Server) |
| Perf probe | paste `tools/qa/perf_probe.client.luau` into execute_luau (Client) |
| Texture cost per asset (model) | `tools/qa/py tools/qa/texture_budget.py report [inventory.txt]` — `docs/PERF_BUDGET.md` §5.4 |
| Texture id → source file, size | `tools/qa/py tools/qa/texture_map.py [--json out.json]` |
| What's referenced in game / make it resident | paste `tools/qa/texture_inventory.client.luau` / `texture_tour.client.luau` (Client) |
| Additive texture A/B with never-drawn ids | `tools/qa/texture_calib.client.luau` (Client, fresh play) |

`tools/qa/py` runs the Python tools in a project-local venv (`.venv-qa`,
git-ignored) and creates it with Pillow on first use. Nothing else is
needed. Baseline set: `qa/beauty/p0-baseline/` (contact sheet
`contact.jpg`); LOS/ground baseline: `tools/qa/baselines/p0-los-ground.txt`;
perf baseline: `docs/PERF_BUDGET.md`.

---

## 1. The six shots

Defined in `src/shared/BeautyShots.luau` (camera, FOV, mode, staging),
captured at each of the five time-of-day presets → 30 images per full set,
named `qa/beauty/<set>/<tod>_<n>-<shot>.jpg` at **1190×1080**.

| # | Name | Mode | What it shows | HUD |
|---|---|---|---|---|
| 1 | `title` | title screen, camera = the title pan frozen at t = 0 | title UI over the mesa, basin, washes and far wall | title UI |
| 2 | `turret` | player turret camera, yaw −2°, pitch −7.5° | the normal third-person view over the gun: road column, helicopter, basin, cliffs, sky | yes |
| 3 | `gunsight` | machine-gun gunsight (aiming), yaw −3.5°, pitch −13.5° | infantry, buggy and tank on the road at 220–410 studs | yes |
| 4 | `flank` | free camera (430, 70, −700) → (−20, 25, −190), FOV 45 | the basin from the right flank: mesa + emplacement, rear/flank cliffs, basin floor, the column | hidden |
| 5 | `night` | free camera (95, 30, −560) → (−50, 70, −40), FOV 45 | from the basin back up at the mesa: searchlights, emplacement lights, flares, enemy lights | hidden |
| 6 | `boss` | player turret camera, yaw −1°, pitch −6° | the Siege Crawler coming up the road (425 studs) with three escorts; boss bar | yes |

ToD tags: `afternoon`, `lateafternoon`, `sunset`, `dusk`, `night` (the
`TimeOfDay` presets `Afternoon`, `LateAfternoon`, `Sunset`, `Dusk`,
`Night`). The HUD shows wave 3/4/7/8/9 by preset (10 for the boss) and a
fixed score of 12480.

**Staged subjects** (frozen: no movement, firing, damage or despawn):
- shots 2–5: 5 infantry (aim pose) on the road, a buggy, a tank, a hovering
  helicopter; at dusk and night three fixed flares.
- shot 6: the Siege Crawler + 3 infantry.

What makes it deterministic: the preset is set directly (no tween); the
wave director is stopped so `Enemies.update` never runs; positions and
headings are fixed; the searchlights are pinned to fixed angles and
NightFx's random flares are replaced by fixed ones; first-encounter tips
are waited out. Two captures of the same shot in different play sessions
differ by a mean of 1.4/255 (rotor angle, dust particles, shadow jitter).

---

## 2. Capture procedure (full set or subset)

A subset of 4–6 images takes about 3–4 minutes including setup.

### 2.1 Setup (once per Studio session)

```bash
tools/studio-lock.sh acquire <you>      # waits for the lock
caffeinate -u -t 2                      # wake the display
```
- computer-use: `open_application("RobloxStudio")` (Studio must be visible
  or it stops rendering and `screen_capture` hangs). Leave the Studio window
  and panel layout alone: the viewport must stay 1190×1080 (see §6).
- `list_roblox_studios` → the id of "Place1".
- **Check the viewport size** (§2.5) before the first capture of a session.
- `start_stop_play(true)`, then in the **Client** datamodel:
  ```lua
  settings().Rendering.QualityLevel = Enum.QualityLevel.Level15
  task.wait(40) -- terrain meshing
  return "ready"
  ```
- Sessions over 15 minutes count as stale: run
  `tools/studio-lock.sh refresh <you>` between batches.

### 2.2 Capture

Print the exact steps for your set:
```bash
python3 tools/qa/beauty_plan.py p1-env --shots 2,4,5 --tods sunset,night
```
It prints a `SINCE=<epoch>` line, then for each image two MCP calls:

1. `execute_luau` in the **Server** datamodel:
   ```lua
   return game.ServerStorage.RedMesaDebug:Invoke("beauty", { shot = 4, tod = "Sunset" })
   ```
   It stages the shot, waits for the client to settle (2 s, or 7.5 s the
   first time a kind of enemy appears so its tip fades) and returns
   `staged sunset_4-flank (waited 2.0s)`. `shot` takes a number or a
   name, `tod` a preset or tag; `settle = <seconds>` overrides the wait.
2. `screen_capture` (any `capture_id`). **Look at the image** it returns.

Then file every capture since `SINCE`, in order:
```bash
tools/qa/py tools/qa/beauty_save.py --set p1-env --since 1790436000 \
    sunset_2-turret night_2-turret sunset_4-flank night_4-flank sunset_5-night night_5-night
```
This copies the MCP's image blobs (saved by Claude Code under
`~/.claude/projects/-Users-xichaowang-projects-beach-head-opus/**/tool-results/mcp-Roblox_Studio-blob-*.jpg`)
into `qa/beauty/p1-env/`, normalises them to 1190×1080, records
`manifest.json` (capture time, source size, git HEAD) and rebuilds
`contact.jpg`. It refuses if the number of captures since `SINCE` differs
from the number of names (a failed or extra capture): re-run with a later
`--since`, or file a single newest capture with no `--since`.
View `contact.jpg` and redo anything wrong.

### 2.3 Finish

```lua
-- Server datamodel
return game.ServerStorage.RedMesaDebug:Invoke("beautyEnd")
```
then `start_stop_play(false)` and `tools/studio-lock.sh release <you>`.

### 2.4 Full set

`python3 tools/qa/beauty_plan.py <set>` (all 6 shots × 5 presets, 30
captures, ~6 minutes). Commit the set folder with your milestone:
`git add qa/beauty/<set> && git commit -m "…" -- qa/beauty/<set>`.

### 2.5 Viewport size check

Captures and perf numbers are only comparable at the baseline viewport:
**`ViewportSize` 1177×1068**, which `screen_capture` returns as a
**1190×1080** image (the size in `qa/beauty/p0-baseline/manifest.json`).
Docking a panel beside the 3D view narrows it: opening the Terrain Editor
and the Toolbox left it at 893×1068 (captures ~896 px wide) until QA-B
closed them.

1. Edit (or Client) datamodel:
   ```lua
   return tostring(workspace.CurrentCamera.ViewportSize) -- must be "1177, 1068"
   ```
2. If it's narrower, take a computer-use `screenshot` and close whatever is
   docked left or right of the viewport (panel title bar ×; the usual
   layout is only Explorer + Properties + Assistant on the right and the
   command bar below). Don't resize or move the Studio window. Re-check 1.
3. Check capture: one `screen_capture` must be 1190×1080. The perf probe
   also prints `viewport WxH` on its first line, and `beauty_save.py`
   marks a wrong size `[resized]`/`[cropped …]`.

QA-B check capture (2026-09-26): `qa/beauty/qa-b/`.

---

## 3. Compare and readability

```bash
tools/qa/py tools/qa/beauty_compare.py p0-baseline p1-env          # colour
tools/qa/py tools/qa/beauty_compare.py p0-baseline p1-env --gray   # grayscale
```
Writes `qa/beauty/compare/p0-baseline_vs_p1-env[_gray]/`: one labelled
side-by-side per image present in both sets, plus `contact.jpg` (rows =
time of day, columns = shots, before above after). Works for subsets.

```bash
tools/qa/py tools/qa/grayscale.py --set p1-env                      # whole set -> qa/beauty/p1-env/gray/
tools/qa/py tools/qa/grayscale.py qa/beauty/p1-env/*_3-gunsight.jpg --out qa/beauty/p1-env/gray --width 480
```
Writes `<name>_gray.jpg` thumbnails and `readability.jpg` (colour | gray
pairs, three per row) and prints each image's luminance spread
(p5..p95). Smaller `--width` = a harsher engagement-distance test. The
rule it checks is in `docs/ART_BIBLE.md` §6. Baseline reference:
`qa/beauty/p0-baseline/gray/readability.jpg`.

---

## 4. Line-of-sight and ground checks

Server datamodel, during a playtest (the world is built at server start):
```lua
local dbg = game.ServerStorage.RedMesaDebug
local pass, report = dbg:Invoke("losCheck")
return report
```
- Sight lines run from the turret muzzle (`Config.TURRET_PIVOT` +
  `MUZZLE_OFFSET` toward the target) to each lane end at three heights
  above the terrain: feet (+0.5), **hip (+3, the pass criterion)**, head
  (+6.5), and at hip height every 20 studs along each lane.
- Everything blocks except the emplacement, `Enemies`, `Projectiles`,
  `Wrecks`, `Crates` and characters. Visible parts with `CanQuery = false`
  (landscape/dressing meshes, scrub) are made queryable for the duration of
  the check, so a mesh blocks the view even if bullets pass through it.
- Output per lane: `PASS/FAIL`, `feet+ hip+ head+`, samples visible along
  the lane, and on failure the blocking instance and hit point. The third
  return value is the same data as a table.

```lua
return game.ServerStorage.RedMesaDebug:Invoke("groundCheck", { verbose = true })
```
Samples every 20 studs along each lane: the terrain height enemies snap to
(same ray as `Kit.groundY`), min/max/mean, a `digest` that changes if any
sample moves by 0.1 stud, and the largest gap between the visible surface
(meshes included) and the terrain. Compare with
`tools/qa/baselines/p0-los-ground.txt` (Phase 0: all PASS, digests Road
18060, ScrubLeft/Right 16400, WashLeft −34191, WashRight −34501).

---

## 5. Perf probe

Paste `tools/qa/perf_probe.client.luau` into execute_luau (**Client**),
after changing `LABEL`. It samples for 8 s and returns: fps (avg, 1 % low,
worst frame), scene/shadow triangles and draw calls, render CPU/GPU frame
time, memory by tag (Graphics* are the budget tags), instance/effect
counts and enemies on screen. Scenes and baseline numbers:
`docs/PERF_BUDGET.md`. For a busy wave: `RedMesaDebug:Invoke("startWave",
9)`, keep integrity up with `Invoke("setIntegrity", 100)` in a loop, run
`tools/qa/autoplay.client.luau` and probe ~50 s in (prefix the probe with
`task.wait(47)`).

Texture memory caveats (QA-B, `docs/PERF_BUDGET.md` §5.3): Studio's
`GraphicsTexture` is process-wide and keeps other sessions' textures, a
texture loads its full mip chain the first time it's drawn and stays, and
removing an instance doesn't reliably free its memory. So a texture A/B is
additive (never-drawn ids, early in a session), and per-asset costs come from
`texture_budget.py report`.

---

## 6. Rig internals and contracts (read before changing related code)

- **Server:** `src/server/QaDebug.luau` implements `beauty`, `beautyEnd`,
  `losCheck`, `groundCheck`; `GameController.installDebugHooks` installs it
  **only when `RunService:IsStudio()`**. `beauty` stops the wave director,
  publishes the phase (`Title` or `Wave`), snaps `TimeOfDay.set(preset, 0)`,
  spawns the stage's subjects through `Enemies.spawn` and places them
  (`root.CFrame = frame * root.PivotOffset:Inverse()`, ground frames as in
  each `EnemyTypes/<Kind>.place()`), then sets the Workspace attributes
  `BeautyShot` (1–6) and `BeautyToD`.
- **Client:** `BeautyShots.startClient()` (called from `init.client`,
  no-op outside Studio) reacts to those attributes: sets
  `DebugYaw/DebugPitch/DebugAiming` for turret shots, binds a camera
  override at `RenderPriority.Last + 10` for title/free shots, disables
  every `ScreenGui` for free shots, hides the `BossBar` for non-boss shots,
  pins the searchlights (`Battlefield.Searchlights.SearchlightN` with
  `Head`/`Lens`/`Pool`) and creates the fixed flares at dusk/night.
- **Contract for other workstreams:** client visuals that are driven by the
  clock or randomness should pause while `Workspace:GetAttribute("BeautyShot")`
  is set (NightFx does: its sweep and random flares stop). If you rename or
  restructure the searchlights, the `BossBar`, the flare look
  (`BeautyShots.makeFlare` mirrors NightFx's flare) or the title camera
  (`SHOTS[1].camera` mirrors AimController's title pan at t = 0), update
  `BeautyShots.luau` in the same change or tell QA-tools.
- Changing a shot's camera or staging invalidates comparisons with earlier
  sets for that shot: only QA-tools changes them, and then recaptures the
  baseline for that shot.

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `screen_capture` hangs or the image is black / frozen | Studio is hidden or the display slept: `caffeinate -u -t 2`, `open_application("RobloxStudio")`, retry |
| Far terrain missing or blurry | QualityLevel not set in the Client datamodel, or captured < 40 s after Play |
| A "new enemy" tip in the frame | pass `settle = 8` to `beauty` for that capture |
| `[resized]`/`[cropped …]` after a file name | the Studio viewport changed size (panels opened, window resized); restore the layout so captures are 1190×1080, then recapture |
| `found N captures since …` | a capture failed or an extra one was taken; re-file with a later `--since` or one at a time |
| Code changes don't show | Rojo syncs to Edit only: stop and restart Play |
| `RedMesaDebug` missing | not a Studio playtest, or the server errored at start: check `get_console_output` |

---

## 8. Airdrop checks (AD-1)

Server datamodel, during a playtest (`src/server/AirdropDebug.luau`,
registered by `GameController.installDebugHooks`, Studio only):
```lua
local dbg = game.ServerStorage.RedMesaDebug
-- Fly a sortie in the running wave (it counts toward the wave); enters now,
-- or with `at` (wave seconds) its first touchdown is aimed there:
local ok, report = dbg:Invoke("airdrop", { kind = "Infantry", count = 8, lane = "Road" })
-- kind Infantry | Buggy | Tank, any ground lane; count defaults to one transport's capacity.
-- Drop-zone sampler audit (runs any time after the world is built):
local report, data = dbg:Invoke("dropZoneCheck", { samples = 600, seed = 1 })
-- Counters since the last reset (sorties, loads announced/landed per kind,
-- cancelled, fallbacks, landing distance min/max, max plan ms, seed):
local stats = dbg:Invoke("airdropStats")       -- { reset = true } clears them
dbg:Invoke("airdropSeed", 1234)                 -- pin the run seed; nil = fresh per run
```
- `dropZoneCheck` plans sorties with the gameplay planner
  (`server/AirdropPlan`) over every ground kind/lane pairing — half of them
  touchdown-timed (lead 30–45 s, as the wave table uses), half entering
  now, including formations (groups over one transport) — keeping ~4
  groups' landings pending together as in a busy wave, then re-checks each
  landing point more densely than the planner and at other angles:
  **band** (300–800 studs), **ground** (open floor material and height,
  landing height = terrain), **footprint/slope** (margin ring 24, rim 20,
  half-rim 10 samples, ≤ 22°), **solid** (rays against the real geometry —
  terrain, landscape meshes, rock kit — the first surface under every
  footprint sample must be the terrain), **spacing**, **reach** (every
  1.5 studs to the lane's join waypoint, which must be closer to the mesa:
  on the floor, no steeper than the planner's limit, nothing solid in the
  way), each flight line (**path**: clearance ≥ 280, altitude 250–350,
  entry and exit outside the basin, release on the path, drift ≤ 9
  studs/s) and **timing** (a timed group's first touchdown = its target).
  Pass = `0 violations`. It also prints, as information, how many landings
  are out of the turret's sight at hip height.
- Client side, loads in the air are visuals under `Workspace.AirdropFx`
  (models tagged/attributed `Airborne`). That folder's attributes
  `Handoffs`, `HandoffMaxDelay` (s after `landT` the enemy appeared) and
  `HandoffMaxOffset` (studs between `landPos` and the enemy root) measure
  the hand-off.
- `tools/qa/autoplay_full.client.luau` audits arrivals in player
  attributes `QA_Drops`, `QA_GroundNoDrop` (a ground enemy without
  `DropLoadId`: must stay 0) and `QA_DropOutOfBand` (must stay 0).
