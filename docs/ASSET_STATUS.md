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
| `Emplacement` | ✅ in game (`Emplacement.luau` uses it, primitive fallback kept) | 98270106261276 | 46k | Concrete gun pit (bunker top y=66, walls to y=58), 4-course sandbag parapet with rear opening + ladder, props (ammo cans, rocket crates, spare missile tubes, jerrycans, radio, searchlight, brass casings). Turret: `TurretYaw.Mount`, `TurretGun.Cradle` (+ shield), `MachineGun.Gun`, `RocketPod.Pod` (7 tubes), `MissileRack.Rail` + `Missile1`/`Missile2`. Markers `Muzzle` (TurretGun), `RocketMuzzle`, `MissileMuzzle`; attachment `Static.Searchlight.SearchlightBeam`. |
| `Infantry` | ✅ in game (Infantry.luau `rigAsset` picks it up) | 98448598946485 | 4.0k | Enemy rifleman ~6.5 studs: charcoal camo, plate carrier, pouches, pack + antenna, gunmetal helmet with red band, goggles, red armband, emblem shoulder patch, original carbine. Limb origins **exactly on the joints** (LeftLeg/RightLeg at hips y=3.45, LeftArm/RightArm at shoulders y=5.3; Head at its centre) via bbox padding: arm/leg part *sizes* are inflated (legs 6.9 tall), so hit boxes extend above the joint and the model bbox is ~7.6 tall (real figure 6.5). Root = invisible Part at hip height (PrimaryPart). Rifle carried along the right arm, muzzle down at rest → points forward when the arm is raised 90° forward. Attachment `Rifle.RifleMuzzle`. |
| `Tank` | ✅ in game (Tank.luau) | 90941646117725 | 13.8k | Original MBT, dark gunmetal, red "217" turret numbers, red bustle band, emblem on skirts. Root = hull (pivot ground centre); `TrackL`/`TrackR` include road wheels/sprockets/idlers; `Turret` model (WorldPivot = turret ring, y=5.0) with `TurretBody`, `Barrel`; attachment `Barrel.Muzzle` (~17.8 studs forward of centre). |
| `Buggy` | ✅ in game (Buggy.luau) | 129795986212385 | 7.7k | Tubular-frame desert raider, charcoal with red accents, light bar, rear engine, spare wheel, jerrycans. Wheels centred on axles (`WheelFL/FR/RL/RR`, spin about X). `Gun` is a **Model** (WorldPivot at the pintle on the post behind the seats) containing `GunBody` + attachment `Muzzle`. Attachment `Root.Headlight` (light bar, facing forward). |
