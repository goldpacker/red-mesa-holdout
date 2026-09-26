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
| `Emplacement` | Model with `Static` (Model: `Bunker` (CanCollide), `Pedestal`, `SandbagsLeft/Front/Right`, `Props`, `Casings`, `Searchlight` with attachment `SearchlightBeam`; bunker top surface at local y = −6 from the turret pivot, walls down to −14), `TurretYaw` (Model, WorldPivot at turret pivot, rotates on Y; part `Mount`), `TurretGun` (Model, WorldPivot at turret pivot, pitches; parts `Cradle` (with gun shield), marker part `Muzzle` (MG, **direct child** of TurretGun)) containing sub-models `MachineGun` (part `Gun`, WorldPivot at turret pivot), `RocketPod` (part `Pod`, marker `RocketMuzzle`), `MissileRack` (part `Rail`, `Missile1`, `Missile2`, marker `MissileMuzzle` in front of Missile1). Asset space origin = turret pivot. Turret parts CanQuery false. **Extras (HS-1, additive):** `Static` also holds `BunkerWall` (CanCollide; outer ring, lip, wall, ladder — `Bunker` is now the inner floor disc r ≤ 11 + plinth), `Drifts`, `Stores` (ammo point), `Casings` (brass + a loose belt), model `Antenna` (WorldPivot at the whip base, part `Whip`, CanQuery false) and model `CamoNet` (WorldPivot at the net's ridge between its two poles, part `Net`, CanQuery false) — both pivots exist so HS-2 can sway/ripple them; `MachineGun` also holds part `Belt` (the brass rounds from the ammo can into the feed tray, moves with the gun). |
| `Infantry` | Model with parts `Root` (invisible Part, hip height, PrimaryPart), `Torso`, `Head`, `LeftArm`, `RightArm`, `LeftLeg`, `RightLeg`, `Rifle` (attachment `RifleMuzzle`); arm/leg origins at their joint (shoulder/hip) so Motor6D C1 can be identity — achieved by padding the mesh bbox, so those parts' `Size` is larger than the visible limb; `Head` origin is the head centre. Rest pose: arms hanging, rifle along the right arm (muzzle down). Red armband/helmet marking. The model's bounding box (~7.6) is taller than the soldier (~6.5 from feet to helmet top): normalise height with the Head top, not `GetBoundingBox`. |
| `Tank` | `Root` (hull, pivot at ground centre), sub-model `Turret` (pivot at turret ring, yaws; parts `TurretBody`, `Barrel`), attachment `Muzzle` on `Barrel` at the tip, `TrackL`/`TrackR` (tracks + wheels). |
| `Buggy` | `Root`, `WheelFL`,`WheelFR`,`WheelRL`,`WheelRR` (centred on axles, spin on X), `Gun` (Model, WorldPivot at the pintle; part `GunBody`) with attachment `Muzzle`, attachment `Headlight` on Root. |
| `Helicopter` | `Root` (fuselage, pivot at centre of mass), `MainRotor` (origin = hub, spins on Y, CanQuery false), `TailRotor` (origin = hub, spins on X, CanQuery false), attachments on Root `RocketMuzzleL`, `RocketMuzzleR`, `Searchlight` (looks forward/down), `GunMuzzle` (chin cannon). |
| `Jet` | `Root` (airframe, pivot at centre of mass) + part `Bombs` (wing ordnance), attachments on Root `Exhaust` (looks aft), `BombBay` (looks down), `NavLightL`, `NavLightR` (wing tips), `Cockpit`. |
| `SiegeCrawler` | `Root` (hull, pivot at ground centre), `TrackL`/`TrackR`, `Deck` (superstructure/tower/stacks), `Core` (Neon sphere, colour animatable, hidden inside `CoreArmor` dome), `CoreArmor` (armoured dome part), separable sub-models `TurretLeft`, `TurretRight` (part `TurretLeftBody`/`TurretRightBody`), `MainCannon` (parts `CannonTurret`, `CannonBarrel`, `CannonGlow`) — each with WorldPivot at its ring and attachment `Muzzle`; `CannonGlow` is a Neon sphere at the muzzle, Transparency 1 in the file; `Beacons` (Neon red warning lights). |
| `SupplyCrate` | `Root` crate (PrimaryPart, CanCollide, pivot = crate bottom centre) with attachment `Top`, and `Parachute` sub-model (`Canopy`, `Lines`, CanQuery false; WorldPivot = crate top centre) above, bright marking (orange/white canopy, fluorescent panel, orange straps). |
| `Rock_*`, `Cliff_*` | Mesa/canyon rock kit: `Rock_Boulder_A/B/C`, `Rock_Slab`, `Rock_Spire` (hoodoo), `Rock_Rubble`, `Cliff_Wall_A` (64×40×16), `Cliff_Wall_B` (48×34×18), `Cliff_Corner` (32×40×32), `Cliff_Butte` (40×28×30). Each a Model with one MeshPart `Root` (PrimaryPart, CanCollide, Box collision), pivot at base centre, sunk ~0.4 below the pivot; cliff faces look along −Z (model front). Layered sandstone matched to the terrain palette. Scale with `Model:ScaleTo`. |
| `Wreck_*` | Optional burnt variants per vehicle (`Wreck_Tank`, …). |
