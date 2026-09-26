--!strict
-- Generates the Red Mesa terrain: a basin floor with low dunes, smooth dry
-- washes, a painted road, the terraced mesa, eroded buttes and canyon walls,
-- and terrain boulders. Shapes are primitives roughened with seeded ball
-- bulges/notches so nothing reads as a perfect cylinder or box.
-- Geometry that gameplay depends on (terrace radii for turret line of
-- sight, lanes kept flat, rear cover) is preserved.
--
-- Surfaces: every painted material gets a custom PBR MaterialVariant
-- (assets/roblox/TerrainMaterials.rbxmx, built by tools/env/) through MaterialService, and
-- large coarse-sand patches (Mud) break up the basin floor's tiling. If the
-- variants are unavailable the stock materials keep their tint colours.

local MaterialService = game:GetService("MaterialService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)

local TerrainBuilder = {}

local terrain = Workspace.Terrain
local M = Enum.Material

-- Tints for the stock materials, used only when a material has no custom
-- variant (terrain colours multiply the variant's colour map too, so covered
-- materials are set to white).
local MATERIAL_COLORS = {
	[M.Sand] = Color3.fromRGB(196, 110, 64), -- basin floor
	[M.Sandstone] = Color3.fromRGB(160, 66, 40), -- mesa + cliffs
	[M.Ground] = Color3.fromRGB(150, 104, 70), -- dusty road
	[M.Salt] = Color3.fromRGB(206, 164, 118), -- dry washes
	[M.Rock] = Color3.fromRGB(112, 56, 40), -- strata + boulders
	[M.Limestone] = Color3.fromRGB(186, 96, 62), -- lighter strata
	[M.Slate] = Color3.fromRGB(92, 50, 38), -- dark caps
}

local VARIANT_FOLDER = "RedMesaTerrain"
-- Coarse-sand patches: Mud voxels (RedMesaSandCoarse) replace Sand where
-- this two-octave noise is above the threshold (about a quarter of the floor).
local PATCH_MATERIAL = M.Mud
local PATCH_SCALE = 150
local PATCH_THRESHOLD = 0.12

local FLOOR_HALF_X = 1000
local FLOOR_MIN_Z = -1500
local FLOOR_MAX_Z = 400

local rng = Random.new(20260926)

local function ball(center: Vector3, radius: number, material: Enum.Material)
	terrain:FillBall(center, radius, material)
end

local function block(center: Vector3, size: Vector3, material: Enum.Material)
	terrain:FillBlock(CFrame.new(center), size, material)
end

local function distanceToSegment(p: Vector2, a: Vector2, b: Vector2): number
	local ab = b - a
	local t = math.clamp((p - a):Dot(ab) / ab:Dot(ab), 0, 1)
	return (p - (a + ab * t)).Magnitude
end

-- Distance from p to the nearest lane polyline (all ground lanes).
function TerrainBuilder.laneDistance(p: Vector2): number
	local best = math.huge
	for _, lane in Config.Lanes do
		for i = 1, #lane - 1 do
			best = math.min(best, distanceToSegment(p, lane[i], lane[i + 1]))
		end
	end
	return best
end

-- Points every `step` studs along a polyline.
local function walk(points: { Vector2 }, step: number): { Vector2 }
	local out = {}
	for i = 1, #points - 1 do
		local a, b = points[i], points[i + 1]
		local n = math.max(1, math.floor((b - a).Magnitude / step))
		for k = 0, n - 1 do
			table.insert(out, a:Lerp(b, k / n))
		end
	end
	table.insert(out, points[#points])
	return out
end

-- Roughens a vertical rock mass: bulges along its outline and a few notches
-- (gullies) cut in, at varied heights. `outline(angleOrT)` returns a surface
-- point and outward normal (XZ).
local function erode(samples: { { pos: Vector3, normal: Vector3 } }, bottom: number, top: number, material: Enum.Material, strength: number)
	for _, s in samples do
		local h = rng:NextNumber(bottom, top)
		local r = rng:NextNumber(4, 10) * strength
		-- Bulge: centred just inside the face so it protrudes a little.
		ball(Vector3.new(s.pos.X, h, s.pos.Z) + s.normal * (r * 0.35), r, material)
		if rng:NextNumber() < 0.28 then
			-- Notch: carve a gully slightly outside the face.
			local nr = rng:NextNumber(3, 7) * strength
			ball(Vector3.new(s.pos.X, rng:NextNumber(bottom, top), s.pos.Z) + s.normal * (nr * 0.8), nr, M.Air)
		end
	end
end

-- Scree: half-buried rubble skirt around a base outline.
local function scree(samples: { { pos: Vector3, normal: Vector3 } }, groundY: number, spread: number)
	for _, s in samples do
		if rng:NextNumber() < 0.7 then
			local r = rng:NextNumber(3, 7)
			local out = rng:NextNumber(0, spread)
			ball(Vector3.new(s.pos.X, groundY - r * 0.45, s.pos.Z) + s.normal * out, r, if rng:NextNumber() < 0.5 then M.Rock else M.Sandstone)
		end
	end
end

local function ringSamples(center: Vector3, radius: number, count: number): { { pos: Vector3, normal: Vector3 } }
	local out = {}
	for i = 1, count do
		local a = (i / count) * math.pi * 2 + rng:NextNumber(-0.1, 0.1)
		local n = Vector3.new(math.cos(a), 0, math.sin(a))
		table.insert(out, { pos = center + n * radius, normal = n })
	end
	return out
end

local function lineSamples(from: Vector3, to: Vector3, normal: Vector3, count: number): { { pos: Vector3, normal: Vector3 } }
	local out = {}
	for i = 0, count do
		local p = from:Lerp(to, i / count) + (to - from).Unit * rng:NextNumber(-6, 6)
		table.insert(out, { pos = p, normal = normal })
	end
	return out
end

local function buildFloor()
	block(Vector3.new(0, -6, (FLOOR_MIN_Z + FLOOR_MAX_Z) / 2), Vector3.new(FLOOR_HALF_X * 2, 12, FLOOR_MAX_Z - FLOOR_MIN_Z), M.Sand)
	-- Low dunes: wide balls mostly buried so only a gentle cap shows.
	local placed = 0
	for _ = 1, 600 do
		if placed >= 140 then
			break
		end
		local p = Vector2.new(rng:NextNumber(-760, 760), rng:NextNumber(-1150, -110))
		local r = rng:NextNumber(24, 60)
		if TerrainBuilder.laneDistance(p) > r * 0.8 + 26 and p.Magnitude > 150 then
			local capHeight = rng:NextNumber(1.2, 4.5)
			ball(Vector3.new(p.X, capHeight - r, p.Y), r, M.Sand)
			placed += 1
		end
	end
end

local function buildWashes()
	for _, laneName in { "WashLeft", "WashRight" } do
		local points = walk(Config.Lanes[laneName], 6)
		local radius, depth = 34, 5.5
		for _, p in points do
			local jitter = Vector2.new(rng:NextNumber(-3, 3), rng:NextNumber(-3, 3))
			local q = p + jitter
			ball(Vector3.new(q.X, radius - depth, q.Y), radius, M.Air)
		end
		-- Paint the channel bed pale (axis-aligned boxes along the path).
		for _, p in points do
			-- Narrower than the trough so the voxel-stepped material edge sits
			-- on the channel floor rather than its visible banks.
			local region = Region3.new(Vector3.new(p.X - 8, -9, p.Y - 8), Vector3.new(p.X + 8, 0, p.Y + 8)):ExpandToGrid(4)
			terrain:ReplaceMaterial(region, 4, M.Sand, M.Salt)
		end
	end
end

local function buildRoad()
	for _, p in walk(Config.Lanes.Road, 5) do
		local region = Region3.new(Vector3.new(p.X - 8, -6, p.Y - 8), Vector3.new(p.X + 8, 2, p.Y + 8)):ExpandToGrid(4)
		terrain:ReplaceMaterial(region, 4, M.Sand, M.Ground)
	end
end

local function buildMesa()
	-- Stepped terraces rising to a small knob; radii are tuned so the gun on
	-- top sees down to the foot of the slope (see GameController LOS notes).
	local top = Config.MESA_TOP
	local terraces = {
		{ radius = 66, bottom = -4, top = 8, material = M.Sandstone },
		{ radius = 51, bottom = 8, top = 22, material = M.Rock },
		{ radius = 37, bottom = 22, top = 38, material = M.Limestone },
		{ radius = 25, bottom = 38, top = 50, material = M.Rock },
		{ radius = 15, bottom = 50, top = top, material = M.Sandstone },
	}
	for _, t in terraces do
		local height = t.top - t.bottom
		terrain:FillCylinder(CFrame.new(0, t.bottom + height / 2, 0), height, t.radius, t.material)
	end
	-- Roughen each terrace face just below its lip (never raising the lip,
	-- which would block the turret's view down the slope).
	for i, t in terraces do
		if i < #terraces then
			local samples = ringSamples(Vector3.zero, t.radius - 2, math.floor(t.radius * 0.7))
			erode(samples, t.bottom + 1, t.top - 3, t.material, 0.6)
		end
	end
	scree(ringSamples(Vector3.zero, 68, 50), 0, 10)
	-- Ridge tying the mesa into the rear cliffs.
	block(Vector3.new(0, 26, 110), Vector3.new(60, 60, 200), M.Sandstone)
	block(Vector3.new(0, 10, 90), Vector3.new(130, 28, 200), M.Sandstone)
	erode(lineSamples(Vector3.new(-30, 0, 20), Vector3.new(-30, 0, 200), Vector3.new(-1, 0, 0), 18), 4, 50, M.Sandstone, 0.9)
	erode(lineSamples(Vector3.new(30, 0, 20), Vector3.new(30, 0, 200), Vector3.new(1, 0, 0), 18), 4, 50, M.Sandstone, 0.9)
end

local function buildCliffs()
	-- Rear cliff wall protects the back of the position.
	block(Vector3.new(0, 60, 260), Vector3.new(FLOOR_HALF_X * 2, 150, 220), M.Sandstone)
	block(Vector3.new(0, 120, 330), Vector3.new(FLOOR_HALF_X * 2, 60, 120), M.Rock)
	erode(lineSamples(Vector3.new(-FLOOR_HALF_X, 0, 150), Vector3.new(FLOOR_HALF_X, 0, 150), Vector3.new(0, 0, -1), 90), 0, 130, M.Sandstone, 1.6)

	-- Flank canyon walls with a lower limestone shelf in front.
	for _, side in { -1, 1 } do
		block(Vector3.new(side * 900, 70, -400), Vector3.new(200, 170, 1600), M.Sandstone)
		block(Vector3.new(side * 780, 35, -300), Vector3.new(80, 90, 900), M.Limestone)
		local faceX = side * 740
		erode(lineSamples(Vector3.new(faceX, 0, -760), Vector3.new(faceX, 0, 150), Vector3.new(-side, 0, 0), 70), 2, 76, M.Limestone, 1.4)
		erode(lineSamples(Vector3.new(side * 800, 0, -1180), Vector3.new(side * 800, 0, -760), Vector3.new(-side, 0, 0), 40), 2, 150, M.Sandstone, 1.8)
		erode(lineSamples(Vector3.new(side * 820, 0, -740), Vector3.new(side * 820, 0, 150), Vector3.new(-side, 0, 0), 60), 80, 150, M.Sandstone, 1.6)
		scree(lineSamples(Vector3.new(faceX, 0, -760), Vector3.new(faceX, 0, 150), Vector3.new(-side, 0, 0), 90), 0, 18)
		-- Dark cap rock along the rim.
		block(Vector3.new(side * 900, 158, -400), Vector3.new(210, 8, 1600), M.Slate)
	end

	-- Far canyon wall closes the horizon at the end of the basin.
	block(Vector3.new(0, 50, -1420), Vector3.new(FLOOR_HALF_X * 2, 150, 160), M.Sandstone)
	block(Vector3.new(0, 110, -1480), Vector3.new(FLOOR_HALF_X * 2, 60, 80), M.Limestone)
	erode(lineSamples(Vector3.new(-FLOOR_HALF_X, 0, -1340), Vector3.new(FLOOR_HALF_X, 0, -1340), Vector3.new(0, 0, 1), 110), 0, 120, M.Sandstone, 2.0)
end

local function buildButtes()
	local buttes = {
		{ Vector3.new(-380, 0, -1120), 90, 80 },
		{ Vector3.new(260, 0, -1150), 110, 120 },
		{ Vector3.new(-60, 0, -1180), 60, 70 },
		{ Vector3.new(620, 0, -1060), 90, 90 },
	}
	for _, b in buttes do
		local base, height, radius = b[1], b[2], b[3]
		-- Slightly tapered two-tier body with a dark cap.
		terrain:FillCylinder(CFrame.new(base + Vector3.new(0, height * 0.35, 0)), height * 0.7, radius, M.Sandstone)
		terrain:FillCylinder(CFrame.new(base + Vector3.new(0, height * 0.82, 0)), height * 0.3, radius * 0.86, M.Limestone)
		terrain:FillCylinder(CFrame.new(base + Vector3.new(0, height + 2, 0)), 5, radius * 0.8, M.Slate)
		erode(ringSamples(base, radius * 0.95, math.floor(radius * 0.45)), 4, height * 0.68, M.Sandstone, 1.5)
		erode(ringSamples(base, radius * 0.82, math.floor(radius * 0.35)), height * 0.7, height * 0.95, M.Limestone, 1.1)
		scree(ringSamples(base, radius + 4, math.floor(radius * 0.5)), 0, 22)
	end
end

-- Organic boulders from clustered terrain balls, kept off the lanes.
local function buildBoulders()
	local placed = 0
	for _ = 1, 900 do
		if placed >= 75 then
			break
		end
		local p = Vector2.new(rng:NextNumber(-720, 720), rng:NextNumber(-1050, -130))
		if TerrainBuilder.laneDistance(p) > 34 and p.Magnitude > 110 then
			placed += 1
			local size = rng:NextNumber(3, 8)
			local material = if rng:NextNumber() < 0.6 then M.Rock else M.Sandstone
			for _ = 1, rng:NextInteger(2, 4) do
				local off = Vector3.new(rng:NextNumber(-1, 1), 0, rng:NextNumber(-1, 1)) * size
				local r = size * rng:NextNumber(0.6, 1.1)
				ball(Vector3.new(p.X, r * 0.35, p.Y) + off, r, material)
			end
		end
	end
end

-- Puts the terrain MaterialVariants into MaterialService and points the
-- base materials at them. Game scripts can't write MaterialVariant
-- properties, so the variants come ready-made from Rojo
-- (ReplicatedStorage.Assets.TerrainMaterials, generated by
-- tools/env/publish_env.py) and are cloned here. Returns the set of base
-- materials that now have a custom look.
local function applyMaterialVariants(): { [Enum.Material]: boolean }
	local covered: { [Enum.Material]: boolean } = {}
	local assets = ReplicatedStorage:FindFirstChild("Assets")
	local source = assets and assets:FindFirstChild("TerrainMaterials")
	if not source then
		return covered
	end
	local folder = MaterialService:FindFirstChild(VARIANT_FOLDER)
	if not folder then
		folder = source:Clone()
		folder.Name = VARIANT_FOLDER
		folder.Parent = MaterialService
	end
	local failures = 0
	local lastError = ""
	for _, variant in (folder :: Instance):GetChildren() do
		if variant:IsA("MaterialVariant") then
			local ok, err = pcall(function()
				MaterialService:SetBaseMaterialOverride(variant.BaseMaterial, variant.Name)
			end)
			if ok then
				covered[variant.BaseMaterial] = true
			else
				failures += 1
				lastError = tostring(err)
			end
		end
	end
	if failures > 0 then
		print(string.format("[RedMesa] %d terrain material overrides unavailable (%s); stock look kept for them", failures, lastError))
	end
	return covered
end

local function patchNoise(x: number, z: number): number
	return math.noise(x / PATCH_SCALE, z / PATCH_SCALE, 3.7) * 0.7
		+ math.noise(x / (PATCH_SCALE * 0.37), z / (PATCH_SCALE * 0.37), 9.1) * 0.3
end

-- Large organic patches of coarse sand over the basin floor so the sand's
-- tiling never reads across the basin. Only Sand voxels change material;
-- occupancy (the shape) is written back unchanged.
local function paintFloorPatches()
	local chunk = 256
	for x0 = -FLOOR_HALF_X, FLOOR_HALF_X - 1, chunk do
		for z0 = FLOOR_MIN_Z, FLOOR_MAX_Z - 1, chunk do
			local lo = Vector3.new(x0, -8, z0)
			local hi = Vector3.new(math.min(x0 + chunk, FLOOR_HALF_X), 8, math.min(z0 + chunk, FLOOR_MAX_Z))
			local region = Region3.new(lo, hi):ExpandToGrid(4)
			local materials, occupancies = terrain:ReadVoxels(region, 4)
			local size = materials.Size
			local corner = region.CFrame.Position - region.Size / 2
			local changed = false
			for ix = 1, size.X do
				local wx = corner.X + (ix - 0.5) * 4
				for iz = 1, size.Z do
					local wz = corner.Z + (iz - 0.5) * 4
					if patchNoise(wx, wz) > PATCH_THRESHOLD then
						for iy = 1, size.Y do
							if materials[ix][iy][iz] == M.Sand then
								materials[ix][iy][iz] = PATCH_MATERIAL
								changed = true
							end
						end
					end
				end
			end
			if changed then
				terrain:WriteVoxels(region, 4, materials, occupancies)
			end
		end
	end
end

function TerrainBuilder.build()
	terrain:Clear()
	local covered = applyMaterialVariants()
	for material, color in MATERIAL_COLORS do
		terrain:SetMaterialColor(material, if covered[material] then Color3.new(1, 1, 1) else color)
	end
	if covered[PATCH_MATERIAL] then
		terrain:SetMaterialColor(PATCH_MATERIAL, Color3.new(1, 1, 1))
	end
	terrain.WaterWaveSize = 0
	pcall(function()
		terrain.Decoration = false
	end)

	buildFloor()
	buildCliffs()
	buildButtes()
	buildMesa()
	buildBoulders()
	buildWashes()
	buildRoad()
	if covered[PATCH_MATERIAL] and covered[M.Sand] then
		paintFloorPatches()
	end
end

return TerrainBuilder
