--!strict
-- Primitive fallback for the Siege Crawler boss (~100 studs long), built to
-- the asset contract: Root hull, Core behind CoreArmor, separable sub-models
-- TurretLeft / TurretRight / MainCannon (each with a Muzzle attachment),
-- CannonGlow, TrackL / TrackR. Forward -Z, pivot at ground centre.

local Kit = require(script.Parent.Kit)

local CrawlerModel = {}

local GM, CH, DK, RB, RED = Kit.GUNMETAL, Kit.CHARCOAL, Kit.DARK, Kit.RUBBER, Kit.RED
local DIAMOND = Enum.Material.DiamondPlate
local CORE_COLOR = Color3.fromRGB(255, 86, 30)

local function at(x: number, y: number, z: number): CFrame
	return CFrame.new(x, y, z)
end

local function sideTurret(m: Model, name: string, x: number): Model
	local t = Instance.new("Model")
	t.Name = name
	t.Parent = m
	local body = Kit.box(t, name .. "Body", Vector3.new(7.5, 4.2, 9), at(x, 28.4, -12), CH)
	t.PrimaryPart = body
	Kit.post(t, "Ring", 2, 8.5, Vector3.new(x, 25.6, -12), GM)
	Kit.wedge(t, "Front", Vector3.new(7.5, 4.2, 3), at(x, 28.4, -18), CH)
	Kit.decor(Kit.box(t, "Band", Vector3.new(7.6, 0.6, 9.1), at(x, 29.6, -12), RED, Enum.Material.SmoothPlastic))
	local muzzleZ = -30.5
	for _, dx in { -1.3, 1.3 } do
		local b = Kit.barrel(t, "Barrel", 12, 0.95, Vector3.new(x + dx, 28.6, -24), GM)
		Kit.decor(Kit.barrel(t, "Flash", 1.2, 1.3, Vector3.new(x + dx, 28.6, -29.6), DK))
		if dx > 0 then
			Kit.attachment(b, "Muzzle", Vector3.new(x, 28.6, muzzleZ), Vector3.new(0, 0, -1))
		end
	end
	Kit.decor(Kit.box(t, "Sensor", Vector3.new(1.4, 1.2, 1.4), at(x, 31.1, -10), DK))
	t.WorldPivot = at(x, 26.5, -12)
	return t
end

function CrawlerModel.build(): Model
	local m = Instance.new("Model")
	m.Name = "SiegeCrawler"

	-- Hull
	Kit.box(m, "Root", Vector3.new(38, 12, 84), at(0, 13, 0), GM)
	Kit.box(m, "UpperHull", Vector3.new(32, 8, 58), at(0, 23, 8), GM)
	Kit.wedge(m, "Glacis", Vector3.new(38, 12, 12), at(0, 13, -48), GM)
	Kit.wedge(m, "UpperGlacis", Vector3.new(32, 8, 10), at(0, 23, -26), GM)
	Kit.wedge(m, "Ram", Vector3.new(42, 6, 5), at(0, 3.2, -55.5) * CFrame.Angles(0, 0, math.pi), DK, DIAMOND)
	Kit.box(m, "RearDeck", Vector3.new(30, 4, 12), at(0, 29, 30), CH)
	for _, side in { -1, 1 } do
		-- Tracks and running gear
		Kit.box(m, if side < 0 then "TrackL" else "TrackR", Vector3.new(10, 14, 96), at(side * 24, 7, 0), RB, DIAMOND)
		Kit.box(m, "TrackGuard", Vector3.new(11.5, 1.2, 99), at(side * 24, 14.6, 0), CH)
		Kit.box(m, "SideArmor", Vector3.new(0.8, 6, 80), at(side * 29.6, 10.5, 0), CH)
		Kit.decor(Kit.box(m, "SideStripe", Vector3.new(0.12, 1.2, 60), at(side * 30.05, 12, -2), RED, Enum.Material.SmoothPlastic))
		for i = 0, 7 do
			Kit.decor(Kit.cyl(m, "RoadWheel", 1.2, 8.5, at(side * 29.4, 4.8, -38 + i * 10.85), DK))
		end
		Kit.chevron(m, CFrame.lookAt(Vector3.new(side * 30.1, 9, 18), Vector3.new(side * 40, 9, 18)), 7)
		-- Sponsons carrying the side turrets
		Kit.box(m, "Sponson", Vector3.new(9, 5, 15), at(side * 20, 22, -12), CH)
		-- Smokestacks and hull clutter
		Kit.post(m, "Stack", 10, 3.2, Vector3.new(side * 9, 33, 33), DK)
		Kit.decor(Kit.post(m, "StackBand", 1, 3.4, Vector3.new(side * 9, 36, 33), RED))
		Kit.decor(Kit.box(m, "Vent", Vector3.new(6, 1, 8), at(side * 9, 27.5, 18), DK, DIAMOND))
		-- Floodlights
		local flood = Kit.lamp(m, "Floodlight", Vector3.new(2.2, 1.4, 0.4), at(side * 13, 20.5, -42.3), Kit.LAMP)
		Kit.spotlight(flood, 140, 45, 2.2)
	end

	-- Core (the kill zone) behind its armour plate on the upper glacis
	local core = Kit.box(m, "Core", Vector3.new(10, 6, 3), at(0, 22.8, -30), CORE_COLOR, Enum.Material.Neon)
	core:SetAttribute("CoreColor", CORE_COLOR)
	local armor = Kit.box(m, "CoreArmor", Vector3.new(14, 9, 2.6), at(0, 22.8, -32.4), CH, DIAMOND)
	-- Emblem and bolts ride on the plate so they leave with it.
	Kit.chevron(armor, CFrame.lookAt(armor.Position - Vector3.new(0, 0, 1.35), armor.Position - Vector3.new(0, 0, 10)), 5)
	for _, dx in { -6, 6 } do
		Kit.decor(Kit.box(armor, "ArmorBolt", Vector3.new(1, 9.2, 0.6), at(dx, 22.8, -33.8), DK))
	end

	sideTurret(m, "TurretLeft", -20)
	sideTurret(m, "TurretRight", 20)

	-- Main cannon
	local cannon = Instance.new("Model")
	cannon.Name = "MainCannon"
	cannon.Parent = m
	local house = Kit.box(cannon, "CannonHouse", Vector3.new(16, 8, 20), at(0, 31, 12), CH)
	cannon.PrimaryPart = house
	Kit.wedge(cannon, "CannonFront", Vector3.new(16, 8, 5), at(0, 31, -0.5), CH)
	Kit.box(cannon, "CannonMantlet", Vector3.new(6, 5, 2), at(0, 31, -3.5), GM)
	Kit.barrel(cannon, "CannonBarrel", 46, 2.8, Vector3.new(0, 31, -27), GM)
	Kit.barrel(cannon, "CannonSleeve", 8, 3.6, Vector3.new(0, 31, -8), DK)
	for _, z in { -20, -34 } do
		Kit.decor(Kit.barrel(cannon, "BarrelRing", 1, 3.2, Vector3.new(0, 31, z), RED))
	end
	local brake = Kit.barrel(cannon, "CannonBrake", 3.5, 4.2, Vector3.new(0, 31, -51.5), DK)
	Kit.attachment(brake, "Muzzle", Vector3.new(0, 31, -53.6), Vector3.new(0, 0, -1))
	local glow = Kit.ball(cannon, "CannonGlow", 3.2, Vector3.new(0, 31, -53.4), Color3.fromRGB(255, 120, 60), Enum.Material.Neon)
	glow.Transparency = 1
	glow.CastShadow = false
	Kit.decor(glow)
	local glowLight = Kit.glow(glow, 40, 0, Color3.fromRGB(255, 110, 50))
	glowLight.Name = "ChargeLight"
	Kit.decor(Kit.box(cannon, "Stripe", Vector3.new(16.1, 1, 20.1), at(0, 33.6, 12), RED, Enum.Material.SmoothPlastic))
	local search = Kit.lamp(cannon, "Searchlight", Vector3.new(1.6, 1.6, 0.4), at(5.5, 36, 3), Kit.LAMP)
	Kit.decor(Kit.box(cannon, "SearchlightHousing", Vector3.new(2, 2, 2), at(5.5, 36, 4.2), DK))
	Kit.spotlight(search, 160, 25, 3)
	cannon.WorldPivot = at(0, 27, 12)

	m.WorldPivot = CFrame.identity
	return m
end

return CrawlerModel
