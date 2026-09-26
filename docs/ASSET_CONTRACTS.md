# Asset contracts

Art direction: GAME_SPEC.md §13 (grounded semi-realistic, PBR, real
proportions). Every asset lands in `ReplicatedStorage.Assets.<Name>` (from
`assets/roblox/`) and is fetched with `AssetLibrary.clone(name)`. Gameplay
code always keeps a primitive fallback, so assets can land in any order.

## Conventions
- **Scale:** 1 stud ≈ 0.28 m. A soldier is ~6.5 studs tall; a main battle
  tank ~26 studs long; a buggy ~13 studs; attack helicopter ~40 studs
  (rotor); jet ~50 studs; Siege Crawler 80–110 studs long.
- **Orientation:** model forward is **-Z**, up is +Y. `PrimaryPart` named
  `Root`, pivot at the ground contact / centre of mass as noted.
- **Palette:** outpost sand/tan/olive drab; enemy force dark gunmetal /
  charcoal with red markings and the original enemy emblem (a red
  downward chevron over a broken circle — design it once, reuse it).
- **Materials:** MeshParts with `SurfaceAppearance` (ColorMap, NormalMap,
  RoughnessMap, MetalnessMap). Keep triangle counts reasonable
  (infantry < 3k, vehicles < 15k, boss < 40k).
- **Hit boxes:** keep `CanQuery = true` on parts that should take bullets;
  decorative bits (antennae, straps) `CanQuery = false`.
- Every named part/attachment below is required; extra detail is welcome.

## What the generated models look like (pipeline facts, verified in Studio)
- Each named part is a `MeshPart` whose `CFrame` is the centre of its
  bounding box with **identity rotation** in asset space (Roblox re-centres
  imported meshes). Do not rely on a MeshPart's origin being a joint or
  hinge; use the model pivots, `PivotOffset` and attachments listed here.
- Sub-model pivots are explicit `WorldPivot`s (turret rings, rotor hubs).
  When a model has a `Root` it is the `PrimaryPart`, and its `PivotOffset`
  makes `model:GetPivot()` the asset origin described per asset.
- All parts: `Anchored = true`, `CanTouch = false`, `CanCollide = false`
  unless noted, `CanQuery = true` unless noted, `CollisionFidelity = Box`
  (one hit box per part). There are no welds; move models with `PivotTo`
  (unanchor + add your own welds if you want physics wrecks).
- Markers (e.g. `Muzzle`) are invisible 0.3-stud `Part`s (`CanQuery`/
  `CanCollide` false) oriented so their `LookVector` points out of the
  barrel. Attachments are oriented the same way.
- Glowing bits (lights, cannon glow) are MeshParts with `Material = Neon`
  and no SurfaceAppearance, so their `Color` can be animated.

## Assets

| Name | Required structure |
|---|---|
| `Emplacement` | Model with `Static` (Model: `Bunker` (CanCollide), `Pedestal`, `SandbagsLeft/Front/Right`, `Props`, `Casings`, `Searchlight` with attachment `SearchlightBeam`; bunker top surface at local y = −6 from the turret pivot, walls down to −14), `TurretYaw` (Model, WorldPivot at turret pivot, rotates on Y; part `Mount`), `TurretGun` (Model, WorldPivot at turret pivot, pitches; parts `Cradle` (with gun shield), marker part `Muzzle` (MG, **direct child** of TurretGun)) containing sub-models `MachineGun` (part `Gun`, WorldPivot at turret pivot), `RocketPod` (part `Pod`, marker `RocketMuzzle`), `MissileRack` (part `Rail`, `Missile1`, `Missile2`, marker `MissileMuzzle` in front of Missile1). Asset space origin = turret pivot. Turret parts CanQuery false. **Extras (HS-1, additive):** `Static` also holds `BunkerWall` (CanCollide; outer ring, lip, wall, ladder — `Bunker` is now the inner floor disc r ≤ 11 + plinth), `Drifts`, `Stores` (ammo point), `Casings` (brass + a loose belt), model `Antenna` (WorldPivot at the whip base; parts `Whip` = base and spring, `Whip2`, `Whip3`, `Whip4` = the three straight whip links bottom to top, each link's bottom-centre is its joint, the tape flag is on `Whip4`; all CanQuery false) and model `CamoNet` (WorldPivot at the net's ridge between its two poles, part `Net`, CanQuery false; its mesh is copied into an EditableMesh at runtime) — client/EmplacementFx(Wind) bends the whip links as a chain and ripples the net; `MachineGun` also holds part `Belt` (the brass rounds from the ammo can into the feed tray, moves with the gun) and two hidden templates (Transparency 1, CanQuery false, no shadow) that client/EmplacementFx clones: `BeltRound` (one belted round + its two links, built at the asset origin in the belt frame: X = feed direction, −Z = round axis, bullet toward −Z, Y = X × (−Z)) and `EjectCase` (one spent case, axis along Y). **HS-2 motion also assumes** the belt path, ejection port and barrel line in `client/EmplacementFx.luau` (barrel along −Z at y = 0.2 in MachineGun space, exposed from z = −3.66 to −6.74) — rebuild both together. |
| `Gunsights` | First-person sight meshes (HS-2, `client/GunsightModels.luau`), built in **eye space**: asset origin = the camera, −Z = view direction, +Y = camera up; designed for FieldOfView 32 (vertical half-view tan 16° = 0.2867 per stud of depth). Sub-models, each WorldPivot at the origin: `IronSight` (parts `Ring` = front ring sight on its stalk 4 studs ahead, `Rear` = rear sight leaf at the bottom edge), `RocketScope` (part `Housing`: sight-box rear face with a round window whose radius is exactly the GUI scope lens, 0.62 × screen height), `AASeeker` (parts `Top`, `Bottom`, `Left`, `Right` = hooded display bezel at depth 0.7; `Plate` = "IR SEEKER" data plate at the top-left corner, `Controls` = lamp/tone/toggle box at the top-right corner, `Lamp` = Neon lock lamp in the Controls bezel, Color/Transparency animated. The client slides `Left`, `Plate` (−X) and `Right`, `Controls`, `Lamp` (+X) so the side bars' inner edge (built at |x| = 0.195) sits 0.03 tan units inside the viewport edge; readable parts must stay on these edge pieces — the centred HUD panels are fixed-pixel, so anything on the centred bars can land behind them). All parts CanQuery/CanCollide false, CastShadow false. |
| `Infantry` | Model with parts `Root` (invisible Part, hip height, PrimaryPart), `Torso`, `Head`, `LeftArm`, `RightArm`, `LeftLeg`, `RightLeg`, `Rifle` (attachment `RifleMuzzle`); arm/leg origins at their joint (shoulder/hip) so Motor6D C1 can be identity — achieved by padding the mesh bbox, so those parts' `Size` is larger than the visible limb; `Head` origin is the head centre. Rest pose: arms hanging, rifle along the right arm (muzzle down). Red armband/helmet marking. The model's bounding box (~7.6) is taller than the soldier (~6.5 from feet to helmet top): normalise height with the Head top, not `GetBoundingBox`. |
| `Tank` | `Root` (hull, pivot at ground centre), sub-model `Turret` (pivot at turret ring, yaws; parts `TurretBody`, `Barrel`), attachment `Muzzle` on `Barrel` at the tip, `TrackL`/`TrackR` (tracks + wheels). **HS-3 (additive):** every contract part keeps its pre-HS-3 bounding box exactly (= Box hit volume and the sizes `VehicleFx`/`VehicleFxDust` read; locked by the build: Root 11.52×3.8×26.62 at (0, 3.4, 0.74), TrackL/R 2.28×3.49×23.24 at (∓4.35, 1.695, 0.27), TurretBody 8.83×6.75×13.24 at (0, 8.325, 0.98), Barrel 1.1×1.07×12.55 at (0, 6.35, −11.475)); new non-hittable parts (CanQuery false): `Skirts` (spaced-armour skirt modules, inside Root's box), `HullKit` (grilles, headlights, tools, tow cable, jerrycans, spare links) and `Turret/TurretKit` (stowage basket, periscopes, whips, rails, mantlet cover; follows the turret); two attachments `Headlight` on `Root` at the headlight lenses (Dress.ground makes two small round lamps when a model has two or more). |
| `Buggy` | `Root`, `WheelFL`,`WheelFR`,`WheelRL`,`WheelRR` (centred on axles, spin on X), `Gun` (Model, WorldPivot at the pintle; part `GunBody`) with attachment `Muzzle`, attachment `Headlight` on Root. **HS-3 (additive):** contract parts keep their pre-HS-3 bounding boxes exactly (locked by the build: Root 7.6×4.95×12.95 at (0, 3.375, −0.566), wheels 1.15×2.9×2.9 at (±3.35, 1.35, ∓4.3), GunBody 1.59×1.52×5.46 at (0, 5.94, −0.045)); new non-hittable part `BuggyKit` (lamps, louvres, radiator, spare wheel, jerrycans, tarp, ammo cans, sand ladders, shovel, whip with pennant, mesh sunroof). Wheels are trim parts (shared `TrimEnemy` textures). |
| `Helicopter` | `Root` (fuselage, pivot at centre of mass), `MainRotor` (origin = hub, spins on Y, CanQuery false), `TailRotor` (origin = hub, spins on X, CanQuery false), attachments on Root `RocketMuzzleL`, `RocketMuzzleR`, `Searchlight` (looks forward/down), `GunMuzzle` (chin cannon). |
| `Jet` | `Root` (airframe, pivot at centre of mass) + part `Bombs` (wing ordnance), attachments on Root `Exhaust` (looks aft), `BombBay` (looks down), `NavLightL`, `NavLightR` (wing tips), `Cockpit`. |
| `SiegeCrawler` | `Root` (hull, pivot at ground centre), `TrackL`/`TrackR`, `Deck` (superstructure/tower/stacks), `Core` (Neon sphere, colour animatable, hidden inside `CoreArmor` dome), `CoreArmor` (armoured dome part), separable sub-models `TurretLeft`, `TurretRight` (part `TurretLeftBody`/`TurretRightBody`), `MainCannon` (parts `CannonTurret`, `CannonBarrel`, `CannonGlow`) — each with WorldPivot at its ring and attachment `Muzzle`; `CannonGlow` is a Neon sphere at the muzzle, Transparency 1 in the file; `Beacons` (Neon red warning lights). |
| `SupplyCrate` | `Root` crate (PrimaryPart, CanCollide, pivot = crate bottom centre) with attachment `Top`, and `Parachute` sub-model (`Canopy`, `Lines`, CanQuery false; WorldPivot = crate top centre) above, bright marking (orange/white canopy, fluorescent panel, orange straps). |
| `Rock_*`, `Cliff_*` | Mesa/canyon rock kit: `Rock_Boulder_A/B/C`, `Rock_Slab`, `Rock_Spire` (hoodoo), `Rock_Rubble`, `Cliff_Wall_A` (64×40×16), `Cliff_Wall_B` (48×34×18), `Cliff_Corner` (32×40×32), `Cliff_Butte` (40×28×30). Each a Model with one MeshPart `Root` (PrimaryPart, CanCollide, Box collision), pivot at base centre, sunk ~0.4 below the pivot; cliff faces look along −Z (model front). Layered sandstone matched to the terrain palette. Scale with `Model:ScaleTo`. |
| `Wreck_*` | Optional burnt variants per vehicle (`Wreck_Tank`, …). |
| `TrimEnemy` | Texture-only trim sheet (HS-3, `models/trim_enemy.py`, no model/rbxmx): one 1024² set (colour/normal/roughness/metalness, ids in `assets/exported/TrimEnemy/roblox_ids.json`) shared by the enemy vehicles' trim parts (Tank `TrackL`/`TrackR`, `HullKit`, `Turret/TurretKit`; Buggy wheels and `BuggyKit`; see ASSET_PIPELINE "Hard-surface tooling"). Strips and templates are listed in `trim.json`; rebuilding it means rebuilding and re-uploading every asset that maps into it. |
