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

## Assets

| Name | Required structure |
|---|---|
| `Emplacement` | Folder/Model with `Static` (bunker top, sandbags, props; bunker top surface at local y = −6 from the turret pivot), `TurretYaw` (Model, WorldPivot at turret pivot, rotates on Y), `TurretGun` (Model, WorldPivot at turret pivot, pitches) containing sub-models `MachineGun`, `RocketPod`, `MissileRack` and parts/attachments `Muzzle` (MG), `RocketMuzzle`, `MissileMuzzle`. Asset space origin = turret pivot. |
| `Infantry` | Model with parts `Root` (invisible, hip height), `Torso`, `Head`, `LeftArm`, `RightArm`, `LeftLeg`, `RightLeg`, `Rifle`; each limb's origin at its joint (hip/shoulder/neck) so Motor6D C1 can be identity. Red armband/helmet marking. |
| `Tank` | `Root` (hull, pivot at ground centre), sub-model `Turret` (pivot at turret ring, yaws), part `Barrel` inside `Turret`, attachment `Muzzle` at barrel tip, `TrackL`/`TrackR`. |
| `Buggy` | `Root`, `WheelFL`,`WheelFR`,`WheelRL`,`WheelRR` (spin on X), `Gun` with attachment `Muzzle`, attachment `Headlight`. |
| `Helicopter` | `Root` (pivot at centre of mass), `MainRotor` (spins on Y), `TailRotor` (spins on X), attachments `RocketMuzzleL`, `RocketMuzzleR`, `Searchlight`. |
| `Jet` | `Root`, attachments `Exhaust`, `BombBay`, `NavLightL`, `NavLightR`. |
| `SiegeCrawler` | `Root` (hull), `Core` (part, initially armoured/hidden behind `CoreArmor`), separable sub-models `TurretLeft`, `TurretRight`, `MainCannon` (each with attachment `Muzzle`), `CannonGlow` part (charge-up glow), `TrackL`/`TrackR`. |
| `SupplyCrate` | `Root` crate with `Parachute` sub-model attached above, bright marking. |
| `Rock_*`, `Cliff_*` | Mesa/canyon rock kit pieces, pivot at base centre. |
| `Wreck_*` | Optional burnt variants per vehicle (`Wreck_Tank`, …). |
