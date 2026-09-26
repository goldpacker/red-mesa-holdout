--!strict
-- Primitive fallback models for the tank and buggy, built to the asset
-- contract (docs/ASSET_CONTRACTS.md): forward -Z, pivot at ground centre,
-- same part/attachment names as the Blender assets.

local Kit = require(script.Parent.Kit)

local GroundModels = {}

local GM, CH, DK, RB, RED = Kit.GUNMETAL, Kit.CHARCOAL, Kit.DARK, Kit.RUBBER, Kit.RED
local DIAMOND = Enum.Material.DiamondPlate

local function at(x: number, y: number, z: number): CFrame
	return CFrame.new(x, y, z)
end

-- Main battle tank, ~26 studs long.
function GroundModels.tank(): Model
	local m = Instance.new("Model")
	m.Name = "Tank"

	-- Hull
	Kit.box(m, "Root", Vector3.new(10.4, 2.8, 22.6), at(0, 3.1, 0), GM)
	Kit.box(m, "HullUpper", Vector3.new(10.8, 2.0, 15), at(0, 5.5, 2.2), GM)
	Kit.wedge(m, "Glacis", Vector3.new(10.8, 2.0, 5.6), at(0, 5.5, -8.1), GM)
	Kit.wedge(m, "LowerGlacis", Vector3.new(10.4, 2.8, 2.2), at(0, 3.1, -12.4) * CFrame.Angles(0, 0, math.pi), GM)
	Kit.box(m, "RearPlate", Vector3.new(10.4, 3.6, 0.6), at(0, 4.4, 11.6), CH)
	for _, x in { -3.2, 3.2 } do
		Kit.decor(Kit.box(m, "Exhaust", Vector3.new(2.2, 0.5, 1.4), at(x, 6.6, 9.4), DK, DIAMOND))
	end
	-- Tracks, fenders, road wheels
	for _, side in { -1, 1 } do
		local name = if side < 0 then "TrackL" else "TrackR"
		Kit.box(m, name, Vector3.new(2.6, 3.9, 24.6), at(side * 6.4, 2.0, 0), RB, DIAMOND)
		Kit.box(m, "Fender", Vector3.new(3.2, 0.35, 25.4), at(side * 6.3, 4.45, 0), CH)
		Kit.box(m, "SideSkirt", Vector3.new(0.3, 1.5, 18), at(side * 7.95, 3.5, -0.6), CH)
		Kit.decor(Kit.box(m, "Stripe", Vector3.new(0.1, 0.35, 12), at(side * 8.12, 3.6, -0.6), RED, Enum.Material.SmoothPlastic))
		for i = 0, 5 do
			Kit.decor(Kit.cyl(m, "RoadWheel", 0.5, 2.4, at(side * 7.8, 1.5, -8.5 + i * 3.4), DK))
		end
		Kit.decor(Kit.cyl(m, "Sprocket", 0.6, 2.8, at(side * 7.8, 2.6, -11.3), DK))
		Kit.decor(Kit.cyl(m, "Idler", 0.6, 2.6, at(side * 7.8, 2.6, 11.3), DK))
	end
	-- Headlights with spotlights (night readability).
	for _, x in { -4.3, 4.3 } do
		local lamp = Kit.lamp(m, "Headlight", Vector3.new(0.9, 0.6, 0.3), at(x, 5.1, -11.0), Kit.LAMP)
		Kit.spotlight(lamp, 60, 50, 1.6)
	end

	-- Turret (pivot at the turret ring)
	local turret = Instance.new("Model")
	turret.Name = "Turret"
	turret.Parent = m
	local body = Kit.box(turret, "TurretBody", Vector3.new(7.8, 2.5, 8.6), at(0, 7.8, 2.0), CH)
	turret.PrimaryPart = body
	Kit.wedge(turret, "TurretFront", Vector3.new(7.8, 2.5, 2.6), at(0, 7.8, -3.6), CH)
	Kit.box(turret, "Bustle", Vector3.new(7.0, 2.0, 2.6), at(0, 8.0, 7.6), CH)
	Kit.box(turret, "Mantlet", Vector3.new(2.8, 1.8, 1.2), at(0, 7.7, -5.2), GM)
	local barrel = Kit.barrel(turret, "Barrel", 13, 0.75, Vector3.new(0, 7.7, -11.9), GM)
	Kit.barrel(turret, "BoreEvacuator", 1.6, 1.05, Vector3.new(0, 7.7, -11), DK)
	Kit.barrel(turret, "MuzzleBrake", 1.2, 1.15, Vector3.new(0, 7.7, -18.2), DK)
	Kit.attachment(barrel, "Muzzle", Vector3.new(0, 7.7, -18.9), Vector3.new(0, 0, -1))
	Kit.decor(Kit.post(turret, "Hatch", 0.5, 2.1, Vector3.new(-1.9, 9.3, 3.4), GM))
	Kit.decor(Kit.box(turret, "RoofMG", Vector3.new(0.3, 0.3, 2.6), at(1.8, 9.6, 2.0), DK))
	Kit.decor(Kit.box(turret, "Sight", Vector3.new(1.2, 0.9, 1.0), at(1.8, 9.4, 0.2), DK))
	Kit.decor(Kit.box(turret, "Antenna", Vector3.new(0.12, 5, 0.12), at(-2.8, 11.5, 7.8), DK))
	for _, side in { -1, 1 } do
		Kit.decor(Kit.box(turret, "Stripe", Vector3.new(0.1, 0.5, 6.4), at(side * 3.95, 8.55, 2.2), RED, Enum.Material.SmoothPlastic))
		Kit.decor(Kit.box(turret, "SmokeLaunchers", Vector3.new(0.9, 0.7, 1.4), at(side * 3.5, 9.1, -1.2), DK))
		Kit.chevron(turret, CFrame.lookAt(Vector3.new(side * 3.92, 7.6, 4.6), Vector3.new(side * 10, 7.6, 4.6)), 1.6)
	end
	turret.WorldPivot = at(0, 6.5, 1.5)
	-- Barrel grime ring
	Kit.decor(Kit.barrel(turret, "BarrelBand", 0.4, 0.82, Vector3.new(0, 7.7, -14.5), RED))

	m.WorldPivot = CFrame.identity
	return m
end

-- Light attack buggy, ~13 studs long, open roll cage, pintle gun.
function GroundModels.buggy(): Model
	local m = Instance.new("Model")
	m.Name = "Buggy"

	Kit.box(m, "Root", Vector3.new(4.8, 0.8, 10.6), at(0, 2.0, 0), CH)
	Kit.wedge(m, "Nose", Vector3.new(4.8, 1.3, 3.0), at(0, 2.95, -4.1), GM)
	Kit.box(m, "Tub", Vector3.new(4.6, 1.2, 4.6), at(0, 3.0, -0.2), GM)
	Kit.box(m, "Engine", Vector3.new(3.8, 1.8, 3.0), at(0, 3.3, 3.7), CH)
	Kit.decor(Kit.box(m, "EngineStripe", Vector3.new(3.85, 0.35, 3.05), at(0, 3.8, 3.7), RED, Enum.Material.SmoothPlastic))
	Kit.decor(Kit.box(m, "Radiator", Vector3.new(3.4, 1.2, 0.3), at(0, 3.4, 5.35), DK, DIAMOND))
	Kit.decor(Kit.box(m, "SkidPlate", Vector3.new(3.6, 0.3, 2.4), at(0, 1.5, -4.4), DK, DIAMOND))
	Kit.decor(Kit.box(m, "Bumper", Vector3.new(5.6, 0.45, 0.45), at(0, 2.4, -5.7), DK))
	-- Side pods with red flashes
	for _, side in { -1, 1 } do
		Kit.box(m, "Pod", Vector3.new(0.8, 1.0, 4.2), at(side * 2.7, 2.8, -0.2), GM)
		Kit.decor(Kit.box(m, "PodStripe", Vector3.new(0.08, 0.3, 3.6), at(side * 3.12, 3.0, -0.2), RED, Enum.Material.SmoothPlastic))
		-- Suspension arms
		Kit.decor(Kit.box(m, "ArmF", Vector3.new(2.0, 0.3, 0.4), at(side * 2.6, 2.0, -3.8), DK))
		Kit.decor(Kit.box(m, "ArmR", Vector3.new(2.0, 0.3, 0.4), at(side * 2.6, 2.0, 3.8), DK))
	end
	-- Roll cage
	local bar = 0.28
	for _, side in { -1, 1 } do
		Kit.decor(Kit.box(m, "CagePostF", Vector3.new(bar, 3.2, bar), at(side * 2.1, 4.9, -1.9) * CFrame.Angles(math.rad(-14), 0, 0), DK))
		Kit.decor(Kit.box(m, "CagePostR", Vector3.new(bar, 3.0, bar), at(side * 2.1, 4.9, 2.0), DK))
		Kit.decor(Kit.box(m, "CageRail", Vector3.new(bar, bar, 4.2), at(side * 2.1, 6.4, 0.1), DK))
		Kit.decor(Kit.box(m, "CageBrace", Vector3.new(bar, bar, 3.2), at(side * 2.1, 5.0, 3.6) * CFrame.Angles(math.rad(35), 0, 0), DK))
	end
	Kit.decor(Kit.box(m, "CageTopF", Vector3.new(4.4, bar, bar), at(0, 6.4, -2.0), DK))
	Kit.decor(Kit.box(m, "CageTopR", Vector3.new(4.4, bar, bar), at(0, 6.4, 2.1), DK))
	-- Crew silhouettes (driver + gunner)
	Kit.box(m, "Driver", Vector3.new(1.3, 1.6, 1.0), at(-0.9, 4.2, -0.4), Color3.fromRGB(52, 54, 58), Enum.Material.Fabric)
	Kit.decor(Kit.ball(m, "DriverHelmet", 0.95, Vector3.new(-0.9, 5.4, -0.4), DK, Enum.Material.SmoothPlastic))
	Kit.decor(Kit.box(m, "Seat", Vector3.new(1.4, 1.2, 0.4), at(-0.9, 3.9, 0.4), RB, Enum.Material.Fabric))
	Kit.decor(Kit.box(m, "SpareWheel", Vector3.new(2.6, 2.6, 0.9), at(0, 5.0, 5.0) * CFrame.Angles(math.rad(-15), 0, 0), RB, Enum.Material.Fabric))

	-- Wheels (spin on X)
	for _, spec in {
		{ "WheelFL", -3.25, -3.8 },
		{ "WheelFR", 3.25, -3.8 },
		{ "WheelRL", -3.25, 3.8 },
		{ "WheelRR", 3.25, 3.8 },
	} do
		local w = Kit.cyl(m, spec[1], 1.3, 3.1, at(spec[2], 1.55, spec[3]), RB, Enum.Material.Fabric)
		Kit.decor(Kit.cyl(w, "Hub", 1.34, 1.3, w.CFrame, DK))
	end

	-- Pintle gun (yaws toward the outpost on the client)
	local gun = Instance.new("Model")
	gun.Name = "Gun"
	gun.Parent = m
	local mount = Kit.post(gun, "GunMount", 1.2, 0.5, Vector3.new(0.6, 6.9, 0.6), DK)
	gun.PrimaryPart = mount
	Kit.box(gun, "Receiver", Vector3.new(0.7, 0.75, 2.2), at(0.6, 7.6, 0.2), GM)
	Kit.decor(Kit.box(gun, "Shield", Vector3.new(2.0, 1.3, 0.15), at(0.6, 7.7, -0.9), CH))
	local gunBarrel = Kit.barrel(gun, "GunBarrel", 2.8, 0.3, Vector3.new(0.6, 7.65, -2.2), DK)
	Kit.attachment(gunBarrel, "Muzzle", Vector3.new(0.6, 7.65, -3.7), Vector3.new(0, 0, -1))
	Kit.decor(Kit.box(gun, "Gunner", Vector3.new(1.2, 1.4, 0.9), at(0.6, 6.8, 1.4), Color3.fromRGB(52, 54, 58), Enum.Material.Fabric))
	Kit.decor(Kit.ball(gun, "GunnerHelmet", 0.9, Vector3.new(0.6, 7.9, 1.5), DK, Enum.Material.SmoothPlastic))
	gun.WorldPivot = at(0.6, 6.9, 0.6)

	-- Headlights + light bar
	local lampHost = Kit.lamp(m, "Headlight", Vector3.new(1.0, 0.5, 0.3), at(-1.2, 3.9, -5.4), Kit.LAMP)
	Kit.lamp(m, "Headlight", Vector3.new(1.0, 0.5, 0.3), at(1.2, 3.9, -5.4), Kit.LAMP)
	Kit.attachment(lampHost, "Headlight", Vector3.new(0, 3.9, -5.6), Vector3.new(0, -0.1, -1))
	Kit.spotlight(lampHost, 70, 55, 1.8)
	local bar2 = Kit.lamp(m, "LightBar", Vector3.new(3.0, 0.35, 0.35), at(0, 6.65, -2.0), Kit.LAMP)
	Kit.spotlight(bar2, 50, 70, 0.9)

	m.WorldPivot = CFrame.identity
	return m
end

return GroundModels
