--!strict
-- Builds the Red Mesa battlefield at server start: terrain, lanes, props,
-- the player emplacement and base lighting. Everything is generated from
-- code so the place is reproducible from the repo.

local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Emplacement = require(script.Parent.Emplacement)

local WorldBuilder = {}

local terrain = Workspace.Terrain
local M = Enum.Material

local MATERIAL_COLORS = {
	[M.Sand] = Color3.fromRGB(196, 104, 58), -- basin floor
	[M.Sandstone] = Color3.fromRGB(158, 62, 38), -- mesa + cliffs
	[M.Ground] = Color3.fromRGB(176, 128, 86), -- dusty road
	[M.Salt] = Color3.fromRGB(206, 160, 112), -- dry washes
	[M.Rock] = Color3.fromRGB(122, 58, 40),
	[M.Limestone] = Color3.fromRGB(190, 92, 60),
}

local FLOOR_HALF_X = 1000
local FLOOR_MIN_Z = -1500
local FLOOR_MAX_Z = 400

local function fillBlock(center: Vector3, size: Vector3, material: Enum.Material)
	terrain:FillBlock(CFrame.new(center), size, material)
end

local function paintStrip(a: Vector2, b: Vector2, width: number, material: Enum.Material, depth: number)
	local mid = (a + b) / 2
	local delta = b - a
	local length = delta.Magnitude
	local yaw = math.atan2(delta.X, delta.Y)
	local cf = CFrame.new(mid.X, -depth / 2 + 0.5, mid.Y) * CFrame.Angles(0, yaw, 0)
	terrain:FillBlock(cf, Vector3.new(width, depth, length + width), material)
end

local function carveStrip(a: Vector2, b: Vector2, width: number, depth: number)
	local mid = (a + b) / 2
	local delta = b - a
	local yaw = math.atan2(delta.X, delta.Y)
	local cf = CFrame.new(mid.X, -depth / 2 + 1, mid.Y) * CFrame.Angles(0, yaw, 0)
	terrain:FillBlock(cf, Vector3.new(width, depth, delta.Magnitude + width), M.Air)
	local bed = CFrame.new(mid.X, -depth - 1, mid.Y) * CFrame.Angles(0, yaw, 0)
	terrain:FillBlock(bed, Vector3.new(width + 4, 4, delta.Magnitude + width), M.Salt)
end

local function buildTerrain()
	terrain:Clear()
	for material, color in MATERIAL_COLORS do
		terrain:SetMaterialColor(material, color)
	end
	terrain.WaterWaveSize = 0

	-- Basin floor.
	fillBlock(Vector3.new(0, -6, (FLOOR_MIN_Z + FLOOR_MAX_Z) / 2), Vector3.new(FLOOR_HALF_X * 2, 12, FLOOR_MAX_Z - FLOOR_MIN_Z), M.Sand)

	-- The mesa: stepped sandstone terraces rising to a small knob, so the gun
	-- on top can see all the way down to the foot of the slope. A ridge ties
	-- it to the rear cliffs.
	local top = Config.MESA_TOP
	local terraces = {
		{ radius = 66, bottom = -4, top = 8 },
		{ radius = 51, bottom = 8, top = 22 },
		{ radius = 37, bottom = 22, top = 38 },
		{ radius = 25, bottom = 38, top = 50 },
		{ radius = 15, bottom = 50, top = top },
	}
	for i, t in terraces do
		local height = t.top - t.bottom
		terrain:FillCylinder(CFrame.new(0, t.bottom + height / 2, 0), height, t.radius, if i % 2 == 0 then M.Rock else M.Sandstone)
	end
	fillBlock(Vector3.new(0, 26, 110), Vector3.new(60, 60, 200), M.Sandstone)
	fillBlock(Vector3.new(0, 10, 90), Vector3.new(130, 28, 200), M.Sandstone)

	-- Rear cliff wall protects the back of the position.
	fillBlock(Vector3.new(0, 60, 260), Vector3.new(FLOOR_HALF_X * 2, 150, 220), M.Sandstone)
	fillBlock(Vector3.new(0, 120, 330), Vector3.new(FLOOR_HALF_X * 2, 60, 120), M.Rock)

	-- Flank canyon walls (helicopters will rise from behind these).
	for _, side in { -1, 1 } do
		fillBlock(Vector3.new(side * 900, 70, -400), Vector3.new(200, 170, 1600), M.Sandstone)
		fillBlock(Vector3.new(side * 780, 35, -300), Vector3.new(80, 90, 900), M.Limestone)
	end

	-- Far canyon wall closes the horizon at the end of the basin.
	fillBlock(Vector3.new(0, 50, -1420), Vector3.new(FLOOR_HALF_X * 2, 150, 160), M.Sandstone)
	fillBlock(Vector3.new(0, 110, -1480), Vector3.new(FLOOR_HALF_X * 2, 60, 80), M.Limestone)

	-- Distant buttes along the canyon axis for the horizon.
	local buttes = {
		{ Vector3.new(-380, 40, -1120), 90, 80 },
		{ Vector3.new(260, 55, -1150), 110, 120 },
		{ Vector3.new(-60, 30, -1180), 60, 70 },
		{ Vector3.new(620, 45, -1060), 90, 90 },
	}
	for _, b in buttes do
		terrain:FillCylinder(CFrame.new(b[1]), b[2], b[3], M.Sandstone)
	end

	-- Central road.
	local road = Config.Lanes.Road
	for i = 1, #road - 1 do
		paintStrip(road[i], road[i + 1], 26, M.Ground, 3)
	end

	-- Dry washes on the flanks.
	for _, laneName in { "WashLeft", "WashRight" } do
		local lane = Config.Lanes[laneName]
		for i = 1, #lane - 1 do
			carveStrip(lane[i], lane[i + 1], 44, 5)
		end
	end
end

local function distanceToSegment(p: Vector2, a: Vector2, b: Vector2): number
	local ab = b - a
	local t = math.clamp((p - a):Dot(ab) / ab:Dot(ab), 0, 1)
	return (p - (a + ab * t)).Magnitude
end

local function nearAnyLane(p: Vector2, margin: number): boolean
	for _, lane in Config.Lanes do
		for i = 1, #lane - 1 do
			if distanceToSegment(p, lane[i], lane[i + 1]) < margin then
				return true
			end
		end
	end
	return false
end

local function buildRocks(parent: Instance)
	local rng = Random.new(1987)
	local folder = Instance.new("Folder")
	folder.Name = "Rocks"
	folder.Parent = parent
	local placed = 0
	local attempts = 0
	while placed < 70 and attempts < 800 do
		attempts += 1
		local p = Vector2.new(rng:NextNumber(-720, 720), rng:NextNumber(-1000, -120))
		if not nearAnyLane(p, 38) then
			placed += 1
			local size = rng:NextNumber(6, 18)
			local rock = Instance.new("Part")
			rock.Name = "Rock"
			rock.Anchored = true
			rock.Material = M.Slate
			rock.Color = Color3.fromRGB(128 + rng:NextInteger(-12, 12), 64, 44)
			rock.Size = Vector3.new(size * rng:NextNumber(0.8, 1.6), size * rng:NextNumber(0.5, 0.9), size)
			rock.CFrame = CFrame.new(p.X, size * 0.2, p.Y)
				* CFrame.Angles(rng:NextNumber(-0.4, 0.4), rng:NextNumber(0, math.pi * 2), rng:NextNumber(-0.4, 0.4))
			rock.TopSurface = Enum.SurfaceType.Smooth
			rock.BottomSurface = Enum.SurfaceType.Smooth
			rock.Parent = folder
		end
	end

	-- Dry scrub bushes: small olive-brown clumps.
	for _ = 1, 90 do
		local p = Vector2.new(rng:NextNumber(-700, 700), rng:NextNumber(-1000, -110))
		if not nearAnyLane(p, 20) then
			local bush = Instance.new("Part")
			bush.Name = "Scrub"
			bush.Shape = Enum.PartType.Ball
			bush.Anchored = true
			bush.CanCollide = false
			bush.CanQuery = false
			bush.Material = M.Grass
			bush.Color = Color3.fromRGB(120, 108, 60)
			local s = rng:NextNumber(3, 6)
			bush.Size = Vector3.new(s, s * 0.7, s)
			bush.Position = Vector3.new(p.X, s * 0.2, p.Y)
			bush.Parent = folder
		end
	end
end

-- Two searchlight towers on the upper terrace flanking the emplacement.
-- The client (NightFx) sweeps the heads and drives the ground light pools;
-- TimeOfDay enables them at dusk and night.
local function buildSearchlights(parent: Instance)
	local folder = Instance.new("Folder")
	folder.Name = "Searchlights"
	folder.Parent = parent
	local steel = Color3.fromRGB(58, 60, 56)
	for i, x in { -27, 27 } do
		local model = Instance.new("Model")
		model.Name = "Searchlight" .. i
		local base = Vector3.new(x, 38, -18)
		local function piece(name: string, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material): Part
			local p = Instance.new("Part")
			p.Name = name
			p.Size = size
			p.CFrame = cf
			p.Color = color
			p.Material = material
			p.Anchored = true
			p.CanCollide = false
			p.CanQuery = false
			p.Parent = model
			return p
		end
		for _, off in { Vector3.new(-1.2, 0, -1.2), Vector3.new(1.2, 0, -1.2), Vector3.new(-1.2, 0, 1.2), Vector3.new(1.2, 0, 1.2) } do
			piece("Leg", Vector3.new(0.35, 9, 0.35), CFrame.new(base + off + Vector3.new(0, 4.5, 0)), steel, Enum.Material.DiamondPlate)
		end
		piece("Deck", Vector3.new(3.6, 0.4, 3.6), CFrame.new(base + Vector3.new(0, 9, 0)), steel, Enum.Material.DiamondPlate)
		local head = piece("Head", Vector3.new(2.6, 2.6, 2.4), CFrame.lookAt(base + Vector3.new(0, 10.6, 0), base + Vector3.new(0, 8, -40)), Color3.fromRGB(70, 74, 60), Enum.Material.Metal)
		local lens = piece("Lens", Vector3.new(2.1, 2.1, 0.2), head.CFrame * CFrame.new(0, 0, -1.25), Color3.fromRGB(255, 244, 214), Enum.Material.Glass)
		local spot = Instance.new("SpotLight")
		spot.Angle = 30
		spot.Range = 60
		spot.Brightness = 6
		spot.Color = Color3.fromRGB(255, 240, 210)
		spot.Face = Enum.NormalId.Front
		spot.Enabled = false
		spot.Parent = lens
		-- Visible beam: a long Beam from the lens along the look direction.
		local a0 = Instance.new("Attachment")
		a0.Name = "BeamStart"
		a0.Parent = lens
		local a1 = Instance.new("Attachment")
		a1.Name = "BeamEnd"
		a1.Position = Vector3.new(0, 0, -420)
		a1.Parent = lens
		local beam = Instance.new("Beam")
		beam.Attachment0 = a0
		beam.Attachment1 = a1
		beam.Width0 = 2
		beam.Width1 = 46
		beam.FaceCamera = true
		beam.LightEmission = 1
		beam.LightInfluence = 0
		beam.Color = ColorSequence.new(Color3.fromRGB(255, 240, 205))
		beam.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.55), NumberSequenceKeypoint.new(1, 1) })
		beam.Segments = 1
		beam.Enabled = false
		beam.Parent = lens
		-- Ground pool of light the client moves to where the beam lands.
		local pool = piece("Pool", Vector3.new(1, 1, 1), CFrame.new(base + Vector3.new(0, 60, -200)), Color3.new(1, 1, 1), Enum.Material.SmoothPlastic)
		pool.Transparency = 1
		local poolLight = Instance.new("SpotLight")
		poolLight.Face = Enum.NormalId.Bottom
		poolLight.Angle = 70
		poolLight.Range = 60
		poolLight.Brightness = 4
		poolLight.Color = Color3.fromRGB(255, 240, 210)
		poolLight.Enabled = false
		poolLight.Parent = pool
		model.PrimaryPart = head
		model.Parent = folder
	end
end

local function ensureEffect(className: string, name: string): Instance
	local existing = Lighting:FindFirstChild(name)
	if existing then
		return existing
	end
	local inst = Instance.new(className)
	inst.Name = name
	inst.Parent = Lighting
	return inst
end

local function buildLighting()
	-- The default place template ships blur effects we don't want.
	for _, child in Lighting:GetChildren() do
		if child:IsA("DepthOfFieldEffect") or child:IsA("BlurEffect") then
			child:Destroy()
		end
	end
	Lighting.ClockTime = 15.2
	Lighting.GeographicLatitude = 30
	Lighting.Brightness = 3
	Lighting.Ambient = Color3.fromRGB(90, 70, 60)
	Lighting.OutdoorAmbient = Color3.fromRGB(150, 120, 100)
	Lighting.EnvironmentDiffuseScale = 0.6
	Lighting.EnvironmentSpecularScale = 0.4
	Lighting.GlobalShadows = true

	local atmosphere = ensureEffect("Atmosphere", "Atmosphere") :: Atmosphere
	atmosphere.Density = 0.2
	atmosphere.Offset = 0.05
	atmosphere.Color = Color3.fromRGB(235, 190, 150)
	atmosphere.Decay = Color3.fromRGB(190, 120, 90)
	atmosphere.Glare = 0.1
	atmosphere.Haze = 0.5

	local bloom = ensureEffect("BloomEffect", "Bloom") :: BloomEffect
	bloom.Intensity = 0.6
	bloom.Size = 28
	bloom.Threshold = 1.6

	local rays = ensureEffect("SunRaysEffect", "SunRays") :: SunRaysEffect
	rays.Intensity = 0.06
	rays.Spread = 0.6

	local grade = ensureEffect("ColorCorrectionEffect", "Grade") :: ColorCorrectionEffect
	grade.Contrast = 0.12
	grade.Saturation = 0.08
	grade.TintColor = Color3.fromRGB(255, 244, 232)
end

function WorldBuilder.build()
	local started = os.clock()
	local existing = Workspace:FindFirstChild("Battlefield")
	if existing then
		existing:Destroy()
	end
	for _, name in { "Baseplate", "SpawnLocation" } do
		local inst = Workspace:FindFirstChild(name)
		if inst then
			inst:Destroy()
		end
	end

	local battlefield = Instance.new("Folder")
	battlefield.Name = "Battlefield"
	battlefield.Parent = Workspace

	buildTerrain()
	buildRocks(battlefield)
	buildSearchlights(battlefield)
	buildLighting()
	Emplacement.build(battlefield)

	for _, name in { "Enemies", "Projectiles", "Wrecks", "Crates" } do
		local folder = Instance.new("Folder")
		folder.Name = name
		folder.Parent = Workspace
	end

	print(string.format("[RedMesa] world built in %.2fs", os.clock() - started))
end

return WorldBuilder
