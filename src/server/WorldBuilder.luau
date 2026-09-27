--!strict
-- Builds the Red Mesa battlefield at server start: terrain, lanes, props,
-- the player emplacement and base lighting (LightingRig). Everything is
-- generated from code so the place is reproducible from the repo.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local ConflictDressing = require(script.Parent.ConflictDressing)
local Emplacement = require(script.Parent.Emplacement)
local GroundDressing = require(script.Parent.GroundDressing)
local Landscape = require(script.Parent.Landscape)
local LightingRig = require(script.Parent.LightingRig)
local TerrainBuilder = require(script.Parent.TerrainBuilder)
local AssetLibrary = require(ReplicatedStorage.Shared.AssetLibrary)

local WorldBuilder = {}


-- Fallback when the ground dressing kit is missing: sparse ball scrub
-- between the lanes (boulders are terrain, see TerrainBuilder).
local function buildScrub(parent: Instance)
	local rng = Random.new(1987)
	local folder = Instance.new("Folder")
	folder.Name = "Scrub"
	folder.Parent = parent
	for _ = 1, 70 do
		local p = Vector2.new(rng:NextNumber(-700, 700), rng:NextNumber(-1000, -110))
		if TerrainBuilder.laneDistance(p) > 22 then
			local bush = Instance.new("Part")
			bush.Name = "Scrub"
			bush.Shape = Enum.PartType.Ball
			bush.Anchored = true
			bush.CanCollide = false
			bush.CanQuery = false
			bush.CastShadow = false
			bush.Material = Enum.Material.Grass
			bush.Color = Color3.fromRGB(104, 92, 56)
			local size = rng:NextNumber(2.5, 4.5)
			bush.Size = Vector3.new(size, size * 0.6, size)
			bush.Position = Vector3.new(p.X, size * 0.15, p.Y)
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
		-- Short and moderate: the visible Beam and ground pool carry the look;
		-- a long cone would wash over the emplacement above it.
		spot.Range = 30
		spot.Brightness = 3
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

-- Scatters the Blender rock kit (if present) across the basin, snapped to
-- the terrain and kept clear of the lanes. Purely visual cover; missing
-- assets simply leave the terrain boulders on their own.
local ROCK_KIT = { "Rock_Boulder_A", "Rock_Boulder_B", "Rock_Boulder_C", "Rock_Slab", "Rock_Spire", "Rock_Rubble" }

local function buildRockKit(parent: Instance)
	local available = {}
	for _, name in ROCK_KIT do
		if AssetLibrary.has(name) then
			table.insert(available, name)
		end
	end
	if #available == 0 then
		return
	end
	local folder = Instance.new("Folder")
	folder.Name = "RockKit"
	folder.Parent = parent
	local rng = Random.new(4242)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { Workspace.Terrain }
	local placed = 0
	for _ = 1, 600 do
		if placed >= 55 then
			break
		end
		local p = Vector2.new(rng:NextNumber(-740, 740), rng:NextNumber(-1100, -140))
		if TerrainBuilder.laneDistance(p) > 40 and p.Magnitude > 130 then
			local name = available[rng:NextInteger(1, #available)]
			local rock = AssetLibrary.clone(name)
			local hit = Workspace:Raycast(Vector3.new(p.X, 300, p.Y), Vector3.new(0, -400, 0), params)
			if rock and rock:IsA("Model") and hit then
				rock:ScaleTo(rng:NextNumber(0.7, 1.5))
				local sink = rng:NextNumber(0.3, 1.2)
				rock:PivotTo(CFrame.new(hit.Position - Vector3.new(0, sink, 0)) * CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), 0))
				for _, d in rock:GetDescendants() do
					if d:IsA("BasePart") then
						d.Anchored = true
						d.CanCollide = false
					end
				end
				rock.Parent = folder
				placed += 1
			end
		end
	end
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

	TerrainBuilder.build()
	Landscape.build(battlefield)
	if not GroundDressing.build(battlefield) then
		buildScrub(battlefield)
	end
	-- Terrain written this frame isn't raycastable yet; place rocks shortly after.
	task.delay(1, buildRockKit, battlefield)
	-- Conflict dressing (ENV-4) sits on the terrain too; visual only.
	task.delay(1.3, function()
		if GroundDressing.BEFORE then
			return -- Studio-only ENV-4 perf "before" build (see GroundDressing)
		end
		local ok, err = pcall(ConflictDressing.build, battlefield)
		if not ok then
			warn("[RedMesa] conflict dressing unavailable: " .. tostring(err))
		end
	end)
	buildSearchlights(battlefield)
	LightingRig.build()
	Emplacement.build(battlefield)

	for _, name in { "Enemies", "Projectiles", "Wrecks", "Crates" } do
		local folder = Instance.new("Folder")
		folder.Name = name
		folder.Parent = Workspace
	end

	print(string.format("[RedMesa] world built in %.2fs", os.clock() - started))
end

return WorldBuilder
