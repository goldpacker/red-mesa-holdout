--!strict
-- Primitive fallback models for the attack helicopter and the jet, built
-- to the asset contract: forward -Z, pivot at the centre of mass.

local Kit = require(script.Parent.Kit)

local AirModels = {}

local GM, CH, DK, RED = Kit.GUNMETAL, Kit.CHARCOAL, Kit.DARK, Kit.RED
local NAV_RED = Color3.fromRGB(255, 40, 30)
local NAV_GREEN = Color3.fromRGB(40, 255, 90)
local NAV_WHITE = Color3.fromRGB(255, 250, 240)

local function at(x: number, y: number, z: number): CFrame
	return CFrame.new(x, y, z)
end

local function navLight(parent: Instance, name: string, pos: Vector3, color: Color3): Part
	local p = Kit.lamp(parent, name, Vector3.new(0.8, 0.8, 0.8), CFrame.new(pos), color)
	p.Shape = Enum.PartType.Ball
	Kit.glow(p, 18, 2, color)
	return p
end

-- A faint light shaft (only shown at night by client/VehicleFx).
local function searchBeam(parent: Instance, from: Vector3, dir: Vector3, length: number, width: number)
	local centre = from + dir.Unit * (length / 2)
	local beam = Kit.cyl(parent, "SearchBeam", length, width, CFrame.lookAt(centre, centre + dir) * CFrame.Angles(0, math.rad(90), 0), Kit.LAMP, Enum.Material.Neon)
	beam.Transparency = 1
	beam.CastShadow = false
	Kit.decor(beam)
	return beam
end

-- Tandem-seat attack helicopter, ~40 studs rotor to tail.
function AirModels.helicopter(): Model
	local m = Instance.new("Model")
	m.Name = "Helicopter"

	Kit.box(m, "Root", Vector3.new(4.6, 5.0, 12), at(0, 0, 0.5), GM)
	Kit.box(m, "Belly", Vector3.new(3.6, 1.2, 10), at(0, -3.0, 0), CH)
	Kit.box(m, "NoseBay", Vector3.new(3.6, 3.4, 4.2), at(0, -0.8, -7.4), GM)
	Kit.wedge(m, "NoseTip", Vector3.new(3.6, 2.0, 2.6), at(0, -1.5, -10.8) * CFrame.Angles(0, 0, math.pi), GM)
	Kit.decor(Kit.ball(m, "SensorBall", 1.8, Vector3.new(0, -2.8, -9.8), DK))
	-- Stepped tandem canopy
	Kit.wedge(m, "CanopyFront", Vector3.new(3.2, 2.0, 3.2), at(0, 1.9, -7.2), Kit.GLASS, Enum.Material.Glass)
	Kit.box(m, "CanopyRear", Vector3.new(3.4, 2.4, 4.4), at(0, 3.4, -3.4), Kit.GLASS, Enum.Material.Glass)
	Kit.wedge(m, "CanopyStep", Vector3.new(3.4, 1.0, 1.6), at(0, 2.3, -6.3), Kit.GLASS, Enum.Material.Glass)
	-- Engines and exhausts
	for _, side in { -1, 1 } do
		Kit.box(m, "Engine", Vector3.new(1.8, 1.9, 5.6), at(side * 2.4, 3.3, 2.2), CH)
		Kit.decor(Kit.barrel(m, "EngineExhaust", 1.4, 1.2, Vector3.new(side * 2.4, 3.4, 5.6), DK))
		Kit.decor(Kit.box(m, "Stripe", Vector3.new(0.08, 0.4, 5), at(side * 2.34, -0.4, 1), RED, Enum.Material.SmoothPlastic))
	end
	Kit.box(m, "Doghouse", Vector3.new(2.6, 1.8, 6), at(0, 3.5, 1.4), CH)
	-- Tail boom, fin, stabiliser
	Kit.box(m, "TailBoom", Vector3.new(1.9, 2.0, 16), at(0, 0.9, 14.2), GM)
	Kit.wedge(m, "TailFin", Vector3.new(0.45, 5.4, 3.4), at(0, 4.2, 21.2), CH)
	Kit.box(m, "Stabiliser", Vector3.new(6.2, 0.3, 2.0), at(0, 1.0, 20.2), CH)
	Kit.decor(Kit.box(m, "TailBand", Vector3.new(1.95, 2.05, 1.0), at(0, 0.9, 17.4), RED, Enum.Material.SmoothPlastic))
	Kit.chevron(m, CFrame.lookAt(Vector3.new(0.25, 4.0, 21.4), Vector3.new(5, 4.0, 21.4)), 1.8)
	Kit.chevron(m, CFrame.lookAt(Vector3.new(-0.25, 4.0, 21.4), Vector3.new(-5, 4.0, 21.4)), 1.8)
	-- Stub wings and rocket pods
	Kit.box(m, "StubWings", Vector3.new(11.5, 0.5, 2.6), at(0, -0.6, 0.8), CH)
	for _, side in { -1, 1 } do
		local pod = Kit.barrel(m, "RocketPod", 4.2, 1.5, Vector3.new(side * 4.6, -1.6, 0.4), DK)
		Kit.decor(Kit.barrel(m, "PodRing", 0.3, 1.6, Vector3.new(side * 4.6, -1.6, -1.6), RED))
		Kit.attachment(pod, if side < 0 then "RocketMuzzleL" else "RocketMuzzleR", Vector3.new(side * 4.6, -1.6, -2.6), Vector3.new(0, 0, -1))
		Kit.decor(Kit.box(m, "Pylon", Vector3.new(0.4, 0.8, 1.4), at(side * 4.6, -0.9, 0.6), DK))
		-- Skids
		Kit.decor(Kit.box(m, "Skid", Vector3.new(0.35, 0.35, 11), at(side * 2.5, -4.6, 0.2), DK))
		Kit.decor(Kit.box(m, "SkidStrutF", Vector3.new(0.3, 1.6, 0.3), at(side * 2.3, -3.8, -3.2), DK))
		Kit.decor(Kit.box(m, "SkidStrutR", Vector3.new(0.3, 1.6, 0.3), at(side * 2.3, -3.8, 3.2), DK))
	end
	-- Chin cannon
	Kit.decor(Kit.barrel(m, "ChinGun", 2.4, 0.3, Vector3.new(0, -3.4, -8.0), DK))

	-- Nav lights and strobe
	navLight(m, "NavLeft", Vector3.new(-5.9, -0.6, 0.8), NAV_RED)
	navLight(m, "NavRight", Vector3.new(5.9, -0.6, 0.8), NAV_GREEN)
	navLight(m, "NavStrobe", Vector3.new(0, 7.0, 22.4), NAV_RED)

	-- Searchlight under the nose
	local search = Kit.lamp(m, "SearchlightLens", Vector3.new(0.9, 0.9, 0.3), at(0, -3.9, -6.2) * CFrame.Angles(math.rad(-25), 0, 0), Kit.LAMP)
	Kit.attachment(search, "Searchlight", search.Position, search.CFrame.LookVector)
	Kit.spotlight(search, 120, 30, 2.2)
	searchBeam(m, search.Position, search.CFrame.LookVector, 70, 4)
	navLight(m, "NavStrobe", Vector3.new(0, -3.7, 2), NAV_WHITE)

	-- Main rotor (spins on Y)
	local rotor = Instance.new("Model")
	rotor.Name = "MainRotor"
	rotor.Parent = m
	local hub = Kit.post(rotor, "Hub", 1.4, 1.5, Vector3.new(0, 5.6, 0.4), DK)
	rotor.PrimaryPart = hub
	Kit.decor(Kit.post(rotor, "Mast", 1.2, 0.6, Vector3.new(0, 4.8, 0.4), DK))
	for i = 0, 3 do
		local a = i * math.pi / 2
		local blade = Kit.box(rotor, "Blade", Vector3.new(18.5, 0.16, 1.2), CFrame.new(0, 6.0, 0.4) * CFrame.Angles(0, a, 0) * CFrame.new(9.6, 0, 0), DK)
		Kit.decor(blade)
		Kit.decor(Kit.box(rotor, "BladeTip", Vector3.new(1.0, 0.18, 1.22), CFrame.new(0, 6.0, 0.4) * CFrame.Angles(0, a, 0) * CFrame.new(18.4, 0, 0), RED, Enum.Material.SmoothPlastic))
	end
	local blur = Kit.post(rotor, "RotorBlur", 0.1, 39, Vector3.new(0, 6.0, 0.4), DK, Enum.Material.SmoothPlastic)
	blur.Transparency = 0.86
	blur.CastShadow = false
	Kit.decor(blur)
	rotor.WorldPivot = at(0, 6.0, 0.4)

	-- Tail rotor (spins on X)
	local tail = Instance.new("Model")
	tail.Name = "TailRotor"
	tail.Parent = m
	local thub = Kit.cyl(tail, "TailHub", 0.6, 0.8, at(0.7, 4.4, 22.0), DK)
	tail.PrimaryPart = thub
	Kit.decor(Kit.box(tail, "TailBladeA", Vector3.new(0.12, 6.0, 0.6), at(0.95, 4.4, 22.0), DK))
	Kit.decor(Kit.box(tail, "TailBladeB", Vector3.new(0.12, 0.6, 6.0), at(0.95, 4.4, 22.0), DK))
	tail.WorldPivot = at(0.7, 4.4, 22.0)

	m.WorldPivot = CFrame.identity
	return m
end

-- Delta-wing strike jet, ~50 studs long.
function AirModels.jet(): Model
	local m = Instance.new("Model")
	m.Name = "Jet"

	Kit.box(m, "Root", Vector3.new(4.0, 3.8, 28), at(0, 0, 1), GM)
	Kit.barrel(m, "NoseSection", 7, 3.4, Vector3.new(0, -0.1, -16.3), GM)
	Kit.barrel(m, "NoseCone", 3.2, 2.4, Vector3.new(0, -0.1, -21.2), CH)
	Kit.decor(Kit.ball(m, "NoseTip", 2.1, Vector3.new(0, -0.1, -22.7), DK))
	Kit.box(m, "Canopy", Vector3.new(2.2, 1.6, 6.2), at(0, 2.4, -10.5), Kit.GLASS, Enum.Material.Glass)
	Kit.wedge(m, "CanopyFront", Vector3.new(2.2, 1.6, 2.4), at(0, 2.4, -14.8), Kit.GLASS, Enum.Material.Glass)
	Kit.wedge(m, "Spine", Vector3.new(2.4, 1.6, 12), at(0, 2.6, 1.0) * CFrame.Angles(0, math.pi, 0), CH)
	-- Intakes
	for _, side in { -1, 1 } do
		Kit.box(m, "Intake", Vector3.new(1.6, 2.8, 8), at(side * 2.6, -0.4, -4), CH)
		Kit.decor(Kit.box(m, "IntakeMouth", Vector3.new(1.4, 2.4, 0.2), at(side * 2.6, -0.4, -8.05), DK))
	end
	-- Delta wings (WedgeParts laid flat: root chord along the fuselage)
	for _, side in { -1, 1 } do
		local span, chord = 11, 17
		local cf = CFrame.new(side * (2.0 + span / 2), -0.4, 4.5) * CFrame.Angles(0, 0, side * -math.pi / 2)
		Kit.wedge(m, if side < 0 then "WingL" else "WingR", Vector3.new(0.5, span, chord), cf, GM)
		Kit.decor(Kit.box(m, "WingStripe", Vector3.new(4.0, 0.54, 1.4), CFrame.new(side * 10.9, -0.4, 12.2), RED, Enum.Material.SmoothPlastic))
		-- Stabilisers
		local scf = CFrame.new(side * (2.0 + 2.6), 0, 14) * CFrame.Angles(0, 0, side * -math.pi / 2)
		Kit.wedge(m, "Stab", Vector3.new(0.35, 5.2, 6), scf, CH)
		-- Underwing bombs (hidden once released)
		local bomb = Kit.barrel(m, "Bomb", 4.2, 1.1, Vector3.new(side * 6.5, -1.6, 6.5), DK)
		bomb:SetAttribute("Bomb", true)
		Kit.decor(Kit.barrel(m, "BombBand", 0.3, 1.14, Vector3.new(side * 6.5, -1.6, 5.4), RED))
	end
	-- Vertical fin with emblem
	Kit.wedge(m, "Fin", Vector3.new(0.45, 7.5, 7.5), at(0, 5.4, 11.5), CH)
	Kit.decor(Kit.box(m, "FinTip", Vector3.new(0.5, 1.0, 1.4), at(0, 8.7, 14.4), RED, Enum.Material.SmoothPlastic))
	Kit.chevron(m, CFrame.lookAt(Vector3.new(0.25, 4.6, 12.6), Vector3.new(5, 4.6, 12.6)), 2.2)
	Kit.chevron(m, CFrame.lookAt(Vector3.new(-0.25, 4.6, 12.6), Vector3.new(-5, 4.6, 12.6)), 2.2)
	-- Engine nozzle
	local nozzle = Kit.barrel(m, "Nozzle", 3.0, 3.2, Vector3.new(0, 0, 16.4), DK)
	Kit.attachment(nozzle, "Exhaust", Vector3.new(0, 0, 18.0), Vector3.new(0, 0, 1))
	local burner = Kit.lamp(m, "Afterburner", Vector3.new(2.2, 2.2, 0.2), at(0, 0, 17.95), Color3.fromRGB(255, 150, 70))
	Kit.glow(burner, 24, 2.5, Color3.fromRGB(255, 140, 60))
	Kit.attachment(m.Root :: BasePart, "BombBay", Vector3.new(0, -2.0, 2), Vector3.new(0, -1, 0))
	-- Nav lights
	local l = navLight(m, "NavLeft", Vector3.new(-12.9, -0.4, 12.6), NAV_RED)
	Kit.attachment(l, "NavLightL", l.Position)
	local r = navLight(m, "NavRight", Vector3.new(12.9, -0.4, 12.6), NAV_GREEN)
	Kit.attachment(r, "NavLightR", r.Position)
	navLight(m, "NavStrobe", Vector3.new(0, 9.3, 14.8), NAV_WHITE)
	-- Landing light, lit on the run in (night readability)
	local landing = Kit.lamp(m, "LandingLight", Vector3.new(0.7, 0.7, 0.2), at(0, -1.9, -12), Kit.LAMP)
	Kit.spotlight(landing, 90, 35, 2.5)

	m.WorldPivot = CFrame.identity
	return m
end

return AirModels
