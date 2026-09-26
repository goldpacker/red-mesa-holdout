# Asset status

Live list of art assets available in `ReplicatedStorage.Assets` (via
`AssetLibrary.clone(name)`). Per-part mesh ids and texture ids are in
`assets/exported/<Name>/roblox_ids.json`; structure in
`assets/exported/<Name>/manifest.json`; pipeline in `docs/ASSET_PIPELINE.md`.
"Model id" is the private Open Cloud Model upload the meshes came from.

Open Cloud key: working (asset:read + asset:write), last used 2026-09-26.

| Asset | Status | Model id | Tris | Notes |
|---|---|---|---|---|
| `SupplyCrate` | ✅ in game (Crates.luau picks it up) | 116407268224811 | 8.3k | Plywood air-drop crate on skid, cargo straps, fluorescent marker panel, stencils; `Parachute` (Canopy, Lines) with orange/white gores. PrimaryPart `Root`, pivot = crate bottom centre. `Parachute` pivot = crate top. Attachment `Root.Top`. Canopy/Lines CanQuery false. |
| `Emplacement` | ✅ in game (`Emplacement.luau` uses it, primitive fallback kept) | 91820343938141 | 46k | Concrete gun pit (bunker top y=66, walls to y=58), 4-course sandbag parapet with rear opening + ladder, props (ammo cans, rocket crates, spare missile tubes, jerrycans, radio, searchlight, brass casings). Sandbags/concrete kept mid-value so close lights don't blow them out (see night note below). Turret: `TurretYaw.Mount`, `TurretGun.Cradle` (+ shield), `MachineGun.Gun`, `RocketPod.Pod` (7 tubes), `MissileRack.Rail` + `Missile1`/`Missile2`. Markers `Muzzle` (TurretGun), `RocketMuzzle`, `MissileMuzzle`; attachment `Static.Searchlight.SearchlightBeam`. |
| `Infantry` | ✅ in game (Infantry.luau `rigAsset` picks it up) | 98448598946485 | 4.0k | Enemy rifleman ~6.5 studs: charcoal camo, plate carrier, pouches, pack + antenna, gunmetal helmet with red band, goggles, red armband, emblem shoulder patch, original carbine. Limb origins **exactly on the joints** (LeftLeg/RightLeg at hips y=3.45, LeftArm/RightArm at shoulders y=5.3; Head at its centre) via bbox padding: arm/leg part *sizes* are inflated (legs 6.9 tall), so hit boxes extend above the joint and the model bbox is ~7.6 tall (real figure 6.5). Root = invisible Part at hip height (PrimaryPart). Rifle carried along the right arm, muzzle down at rest → points forward when the arm is raised 90° forward. Attachment `Rifle.RifleMuzzle`. |
| `Tank` | ✅ in game (Tank.luau) | 90941646117725 | 13.8k | Original MBT, dark gunmetal, red "217" turret numbers, red bustle band, emblem on skirts. Root = hull (pivot ground centre); `TrackL`/`TrackR` include road wheels/sprockets/idlers; `Turret` model (WorldPivot = turret ring, y=5.0) with `TurretBody`, `Barrel`; attachment `Barrel.Muzzle` (~17.8 studs forward of centre). |
| `Buggy` | ✅ in game (Buggy.luau) | 129795986212385 | 7.7k | Tubular-frame desert raider, charcoal with red accents, light bar, rear engine, spare wheel, jerrycans. Wheels centred on axles (`WheelFL/FR/RL/RR`, spin about X). `Gun` is a **Model** (WorldPivot at the pintle on the post behind the seats) containing `GunBody` + attachment `Muzzle`. Attachment `Root.Headlight` (light bar, facing forward). |
| `Helicopter` | ✅ in game (Helicopter.luau) | 74665553782031 | 5.0k | Tandem attack helicopter, gunmetal with panel seams, red tail band/fin tip, "07" nose number, emblem on the boom. `MainRotor` (4 blades, 38.6 dia) and `TailRotor` origins on their hubs (padded). Stub wings with 7-tube rocket pods (`RocketMuzzleL/R`) and missile racks, chin cannon (`GunMuzzle`), `Searchlight` attachment under the chin, wheeled gear. |
| `Jet` | ✅ in game (Jet.luau) | 101659641813930 | 2.3k | Twin-engine twin-tail strike jet, 48 long / 32 span, panel seams, red fin tips and nose band, "31", emblems on the fins. Parts `Root` + `Bombs` (4 under-wing bombs, can be hidden on release). Attachments `Exhaust`, `BombBay`, `NavLightL/R`, `Cockpit`. |
| `SiegeCrawler` | ✅ in game (SiegeCrawler.luau) | 78159105760275 | 18.9k | ~95-stud land fortress: twin giant tracks, armoured hull with ram plow + hazard stripes, add-on armour, deck superstructure, command tower, exhaust stacks, railings, big emblems. Movers `MainCannon` (CannonTurret, CannonBarrel, CannonGlow), `TurretLeft`/`TurretRight` (twin autocannons), each with `Muzzle`. `Core` (Neon, orange-red) inside `CoreArmor` dome on the rear deck. `Beacons` Neon red lights. |
| Rock kit | ✅ available (not yet placed; lead's TerrainBuilder can use them) | see ids.json | 1–8k each | `Rock_Boulder_A` 83691249310224, `Rock_Boulder_B` 120040242554044, `Rock_Boulder_C` 102347733369083, `Rock_Slab` 113438742504655, `Rock_Spire` 132597563756192 (hoodoo with cap rock), `Rock_Rubble` 138698239137297, `Cliff_Wall_A` 125481892463149, `Cliff_Wall_B` 71129746600270, `Cliff_Corner` 126497793998678, `Cliff_Butte` 101571513664755. Layered sandstone matching terrain Sandstone/Rock colours; single `Root` MeshPart each, CanCollide, Box collision; pivot at base centre. |
| `Wreck_*` | ⏭ skipped | – | – | Optional; enemy code already chars and detaches wrecks at runtime (`Kit.char`, `Kit.detach`), nothing consumes `Wreck_*`. |
| VFX textures | ✅ uploaded (VFX-1); consumed from VFX-2 on | see `assets/vfx/roblox_ids.json` | – | 13 private Images listed in `src/shared/Flipbooks.luau` (`Flipbooks.apply`): 8x8 1024² flipbooks `Fireball`, `SmokeDark`, `DustPuff`, `SandKick`, `MissileTrail`, `MuzzleFlashFront/Side/Burst`, `RocketExhaust`, `Sparks`; singles `TracerBeam` (512x128 Beam), `ShockwaveRing`, `ScorchMark`. Built by `tools/vfx/render.sh`, uploaded by `tools/vfx/upload.py`. |

### Night lighting note (2026-09-26)
The orange blow-out of the sandbags at sunset/night is caused by lights in
lead-owned code, not by the asset (verified in Studio at Night with A/B
light toggles): (1) `Effects.luau` muzzle flash PointLight, Range 14 /
Brightness 3, sits ~5 studs from the front sandbags at ~11 Hz;
(2) `WorldBuilder` searchlight SpotLights (Range 60, Brightness 6) at
(±27, 48, −19) sweep across the bunker from below. With both disabled the
emplacement reads correctly at night while firing. Suggested: muzzle flash
Range ~6, Brightness ~1.2 (or place it ~2 studs in front of the muzzle);
searchlights Range ~35 or aim them so the cone never reaches the bunker.
The asset side was toned down too (darker sandbag/concrete albedo).
