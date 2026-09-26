# Architecture & team contracts

Red Mesa Holdout is built by several agents in parallel on one branch. This
file is the contract between them. `GAME_SPEC.md` is the product source of
truth; `PROGRESS.md` is the status log (lead-owned).

## Code layout (Rojo, `default.project.json`)

| Repo path | Studio location |
|---|---|
| `src/shared/` | `ReplicatedStorage.Shared` |
| `src/server/` | `ServerScriptService.Server` (entry `init.server.luau`) |
| `src/client/` | `StarterPlayer.StarterPlayerScripts.Client` (entry `init.client.luau`) |
| `assets/roblox/` | `ReplicatedStorage.Assets` (imported art, see ASSET_CONTRACTS.md) |
| (project file) | `ReplicatedStorage.Remotes.*` RemoteEvents, `ReplicatedStorage.GameState` |

`rojo serve --port 34872` must be running and the Studio plugin connected.
Edits sync to the Edit datamodel; restart the playtest to pick them up.

## Ownership

Edit only files you own. If you need a change in someone else's file, keep
it minimal and additive (a new function, a new event handler line) and say so
in your final report. Never reformat or restructure another owner's file.

| Owner | Files |
|---|---|
| **Lead** | `src/server/{init.server,GameController,WaveDirector,Scoring,WorldBuilder,Crates*}.luau`, `src/shared/{Config,Aim}.luau`, `src/client/{init.client,AimController,GameState,Hud,Screens,Effects,Sfx,Ui}.luau`, `PROGRESS.md`, `GAME_SPEC.md`, `docs/ARCHITECTURE.md` |
| **Weapons** | `src/server/Weapons.luau`, `src/server/Projectiles*.luau`, `src/shared/WeaponConfig.luau`, `src/client/{WeaponController,WeaponHud,LockOn*,WeaponFx*}.luau` |
| **Enemies** | `src/server/EnemyTypes/*`, `src/shared/EnemyConfig.luau`, `src/client/{EnemyVisuals,EnemyFireFx,VehicleFx*}.luau` |
| **Assets** | `assets/**`, `tools/assets/**`, `src/shared/AssetLibrary.luau`, `src/server/Emplacement.luau`, `docs/ASSET_CONTRACTS.md` |

Shared config: `Config.luau` holds core geometry, machine gun, infantry,
lanes and **waves** (lead). Weapon and enemy tuning go in
`WeaponConfig.luau` / `EnemyConfig.luau`.

## Key contracts

### Enemies (server)
- Each file in `src/server/EnemyTypes/` returns `{ kind = "Tank", spawn = function(ctx, lane, rng) -> Enemy }`.
  `Enemies.luau` auto-registers it; wave configs refer to it by `kind`.
- `Enemy` fields: see `src/server/Types.luau` (`resist`, `isThreatening`,
  `onDamage`, `isAir`, `update`, `die`, …). Models get attributes
  `EnemyId`, `Kind`, `IsAir`, `Threat` automatically. Set a `State`
  attribute on the model for client animation.
- `lane` is a key of `Config.Lanes` (ground) or of lanes/paths the enemy
  module defines in `EnemyConfig` (air). Unknown lanes must fall back sanely.
- Enemies must never get stuck, spawn inside terrain, or be unreachable;
  the wave director dismisses stragglers after `Config.Timing.WAVE_MAX_DURATION`.
- Death: `die()` must visibly destroy the enemy (wreck in `Workspace.Wrecks`
  or topple) and clean up after itself. Wrecks persist until the lead's
  intermission cleanup (`Enemies.clearAll`).
- `Context` (`ctx`) gives `damageOutpost(amount, from, heavy)`,
  `enemyFired(enemy, attack, from, to)` (→ client `EnemyFire`),
  `emit(kind, payload)`, `spawn(kind, lane)`, `dropCrate(bias)`,
  `awardPoints(points, position, label)`.

### Damage (server)
- `Enemies.damage(enemy, amount, weapon, part?) -> killed` where weapon is
  `"MG" | "Rocket" | "Missile"`. Resistances and `onDamage` apply there.
- `Enemies.damageRadius(center, radius, amount, weapon)` for splash.
- Weapons report every hit through the `Weapons.init` hooks
  (`onShot`, `onHit(player, enemy, killed, position, headshot)`) so scoring
  and hit markers work for every weapon.

### Events (server → client, `Remotes.GameEvent`, `(kind, payload)`)
Existing: `WaveStart`, `WaveClear`, `Kill {kind, points, multiplier, position}`,
`Hit {position, killed, headshot}`, `Damage {amount, from, heavy, integrity}`,
`EnemyFire {kind, attack, from, to, id}`, `Points {points, position, label}`,
`Defeat`, `Victory`.
Reserved for new work: `JetWarning {id, eta}`, `BossUpdate {weakPoints, core}`,
`BossCharge {duration}`, `CrateSpawned`, `CratePickup {contents, amount}`,
`AmmoUpdate` (weapons may instead use player attributes).
Weapons: `Projectile {id, kind, origin, dir, speed, t0, owner, token, targetId}`, `ProjectileEnd {id, kind, position, exploded, air, enemy}`, `Ricochet {position}` (to the shooter only).
Add new kinds to this list when you introduce them.

### Game state (`ReplicatedStorage.GameState` attributes)
`Phase` (`Title|WaveIntro|Wave|Intermission|Defeat|Victory`), `Wave`,
`TotalWaves`, `Integrity`, `Score`, `Multiplier`, `SessionBest`,
`Remaining`, `PhaseEndsAt`. Weapons ammo should live on the Player as
attributes (e.g. `Rockets`, `Missiles`) set by the server.

## Testing

- `tools/check.sh` — syntax check of all Luau (run before every commit).
- **Studio is a single shared instance.** Before any playtest or
  `screen_capture`, run `tools/studio-lock.sh acquire <your-name>`; after
  stopping play run `tools/studio-lock.sh release <your-name>`. Keep sessions
  short (a few minutes). Never leave a playtest running.
- Studio id: call `list_roblox_studios` (name "Place1").
- The Mac's display idles/sleeps when nobody is at it, which pauses Studio
  rendering. Run `caffeinate -u -t 2` right before any playtest or
  `screen_capture` (check with a RenderStepped counter: 0 fps = asleep).
- Studio must be frontmost/visible or rendering stops (RenderStepped halts,
  `screen_capture` times out): `open_application("RobloxStudio")` via
  computer-use. For visual QA, in the Client datamodel run
  `settings().Rendering.QualityLevel = Enum.QualityLevel.Level15`, and wait
  ~40 s after Play for terrain to finish meshing.
- Debug hooks (Studio only): player attributes `DebugYaw`, `DebugPitch`,
  `DebugFire`, `DebugAiming`; `ServerStorage.RedMesaDebug:Invoke(cmd, arg)`
  with `state`, `setIntegrity`, `killAll`, `startWave`.
  `tools/qa/autoplay.client.luau` auto-aims and fires at the nearest enemy.
- Temporary test waves: don't edit `Config.Waves`; instead use
  `RedMesaDebug:Invoke("startWave", n)` or spawn directly from a Server
  execute_luau via the debug hook the lead exposes (`spawn`).

## Git

- Same branch for everyone. Commit only your own files:
  `git add <your paths> && git commit -m "<type>: <msg>"` with the
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` trailer.
  If `index.lock` exists, wait a few seconds and retry. Never force-push,
  never push, never rewrite history, never `git add -A`.
