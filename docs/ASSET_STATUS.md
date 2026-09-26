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
