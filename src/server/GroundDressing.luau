--!strict
-- Road and wash edge strips and ground dressing (FACELIFT_PLAN §4 Phase 1c
-- and 1d, ENV-3). Visual only.
--
-- Strips (assets/roblox/GroundStrips.rbxmx, built by tools/env/ground/):
-- mesh ribbons lying 0.1-0.3 studs over the live terrain along the road and
-- both washes, so the voxel-stepped paint edges sit under them. They are
-- placed where the rbxmx puts them. Wash pieces get a precise collision
-- shape at runtime (off-thread), so the QA line-of-sight check, which makes
-- visible parts queryable, sees the bank surface and not a box spanning the
-- trough.
--
-- Dressing (assets/roblox/GroundDressing.rbxmx: a few shared meshes on one
-- atlas): scrub, creosote, saltbush and grass cards, dead branches,
-- pebbles, rock clusters at boulder feet, old tyre tracks and craters,
-- scattered from a fixed seed on the basin floor. Density falls off with
-- distance from the turret; nothing taller than a pebble within reach of
-- the lanes (infantry walk up to 14 studs off a lane), and nothing on the
-- road/wash strips.
--
-- Everything is anchored, non-colliding, CanQuery/CanTouch false, parented
-- under Battlefield.GroundDressing (not Battlefield.Landscape, so effects
-- land on the terrain under the strips, not on their boxes). Missing assets
-- leave the plain terrain (and WorldBuilder's old scrub). Nothing here
-- blocks movement, raycasts or the airdrop landing sampler (terrain only).
--
-- Wind hook (Update 2, not built yet): the foliage folders under
-- GroundDressing.Dressing (Scrub_A/B, Creosote, Saltbush, Grass) carry a
-- `Sway` attribute, the tilt amplitude in radians. Every piece's pivot is
-- its ground point, so a client module can read src/shared/Wind.luau and
-- tilt the pieces near the camera about their pivot (CFrame, client-side)
-- without touching anything else.

local AssetService = game:GetService("AssetService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local TerrainBuilder = require(script.Parent.TerrainBuilder)

local GroundDressing = {}

local SEED = 31626
local TURRET = Vector2.new(Config.TURRET_PIVOT.X, Config.TURRET_PIVOT.Z)
-- The road and wash strips reach this far from their lane (wash spill <= ~36).
local STRIP_LANES = { Road = 30, WashLeft = 40, WashRight = 40 }
-- Basin floor where dressing may go (clear of the mesa, walls and buttes).
local BASIN = { minX = -690, maxX = 690, minZ = -1270, maxZ = 90, mesa = 118 }
local BUTTES = {
	{ Vector2.new(-380, -1120), 80 },
	{ Vector2.new(260, -1150), 120 },
	{ Vector2.new(-60, -1180), 70 },
	{ Vector2.new(620, -1060), 90 },
}
local FLOOR_MATERIALS = { [Enum.Material.Sand] = true, [Enum.Material.Mud] = true }
-- Dressing casts shadows only this close to the turret (studs).
local SHADOW_RANGE = 480
-- Strip parts thicker than this (studs) get precise collision (see buildStrips).
local PRECISE_ABOVE = 0.6
local SCRUB_LANES = { "ScrubLeft", "ScrubRight" }

-- name: count, clearance from any lane (studs), scale range, min spacing,
-- clustered (scrub grows in loose groups), flat decal (needs level ground),
-- sway (wind hook, see the header).
-- Heights: nothing is taller than 3/4 of a soldier (Infantry is 7.2 studs;
-- the creosote at scale 1.0 is 5.4), so an airdropped soldier crossing the
-- basin floor always shows head and shoulders over the scrub.
type Kind = { name: string, count: number, clear: number, scale: { number }, spacing: number, cluster: boolean?, flat: boolean?, sway: number? }
local SCATTER: { Kind } = {
	{ name = "Scrub_A", count = 240, clear = 26, scale = { 0.7, 1.25 }, spacing = 7, cluster = true, sway = 0.05 },
	{ name = "Scrub_B", count = 150, clear = 26, scale = { 0.7, 1.2 }, spacing = 7, cluster = true, sway = 0.05 },
	{ name = "Creosote", count = 80, clear = 32, scale = { 0.75, 1.0 }, spacing = 10, cluster = true, sway = 0.035 },
	{ name = "Saltbush", count = 70, clear = 30, scale = { 0.7, 1.15 }, spacing = 10, cluster = true, sway = 0.04 },
	{ name = "Grass", count = 260, clear = 22, scale = { 0.75, 1.3 }, spacing = 4, cluster = true, sway = 0.1 },
	{ name = "Branch_A", count = 45, clear = 22, scale = { 0.8, 1.3 }, spacing = 8 },
	{ name = "Branch_B", count = 45, clear = 22, scale = { 0.8, 1.3 }, spacing = 8 },
	{ name = "Pebbles_A", count = 110, clear = 18, scale = { 0.8, 1.4 }, spacing = 6 },
	{ name = "Pebbles_B", count = 110, clear = 18, scale = { 0.8, 1.4 }, spacing = 6 },
	{ name = "Crater", count = 9, clear = 30, scale = { 0.8, 1.25 }, spacing = 60, flat = true },
}

local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Include

local function templates(): Instance?
	local assets = ReplicatedStorage:FindFirstChild("Assets")
	return assets and assets:FindFirstChild("GroundDressing")
end

local function prepare(part: BasePart)
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
end

local function distanceToSegment(p: Vector2, a: Vector2, b: Vector2): number
	local ab = b - a
	local t = math.clamp((p - a):Dot(ab) / ab:Dot(ab), 0, 1)
	return (p - (a + ab * t)).Magnitude
end

local function laneDistance(p: Vector2, name: string): number
	local lane = Config.Lanes[name]
	local best = math.huge
	for i = 1, #lane - 1 do
		best = math.min(best, distanceToSegment(p, lane[i], lane[i + 1]))
	end
	return best
end

-- Clear of the lanes (by `clear`) and of the strips, inside the basin.
local function allowed(p: Vector2, clear: number): boolean
	if p.X < BASIN.minX or p.X > BASIN.maxX or p.Y < BASIN.minZ or p.Y > BASIN.maxZ then
		return false
	end
	if p.Magnitude < BASIN.mesa then
		return false
	end
	for _, b in BUTTES do
		if (p - b[1]).Magnitude < b[2] + 28 then
			return false
		end
	end
	if clear > 0 and TerrainBuilder.laneDistance(p) < clear then
		return false
	end
	for name, reach in STRIP_LANES do
		if laneDistance(p, name) < reach then
			return false
		end
	end
	return true
end

-- Density with distance from the turret: full in the combat range, thinning
-- toward the far wall (where it is only a few pixels anyway).
local function density(p: Vector2): number
	local d = (p - TURRET).Magnitude
	if d < 450 then
		return 1
	end
	return math.max(0.35, 1 - (d - 450) / 650 * 0.65)
end

local function ground(p: Vector2): RaycastResult?
	params.FilterDescendantsInstances = { Workspace.Terrain }
	local hit = Workspace:Raycast(Vector3.new(p.X, 300, p.Y), Vector3.new(0, -400, 0), params)
	if hit and FLOOR_MATERIALS[hit.Material] and hit.Normal.Y > 0.93 then
		return hit
	end
	return nil
end

-- Level ground under a flat decal of radius r (craters, tracks).
local function level(p: Vector2, r: number, y: number): boolean
	for _, o in { Vector2.new(r, 0), Vector2.new(-r, 0), Vector2.new(0, r), Vector2.new(0, -r), Vector2.new(r * 0.7, r * 0.7), Vector2.new(-r * 0.7, -r * 0.7) } do
		local hit = ground(p + o)
		if not hit or math.abs(hit.Position.Y - y) > 0.08 then
			return false
		end
	end
	return true
end

-- Spatial hash for minimum spacing.
local Spacing = {}
Spacing.__index = Spacing
function Spacing.new(cell: number)
	return setmetatable({ cell = cell, grid = {} :: { [string]: { Vector2 } } }, Spacing)
end
function Spacing:free(p: Vector2, r: number): boolean
	local cx, cz = math.floor(p.X / self.cell), math.floor(p.Y / self.cell)
	for dx = -1, 1 do
		for dz = -1, 1 do
			local list = self.grid[(cx + dx) .. ":" .. (cz + dz)]
			if list then
				for _, q in list do
					if (q - p).Magnitude < r then
						return false
					end
				end
			end
		end
	end
	return true
end
function Spacing:add(p: Vector2)
	local key = math.floor(p.X / self.cell) .. ":" .. math.floor(p.Y / self.cell)
	self.grid[key] = self.grid[key] or {}
	table.insert(self.grid[key], p)
end

local function place(template: BasePart, folder: Instance, at: Vector3, normal: Vector3, yaw: number, scale: number, tilt: boolean)
	local part = template:Clone()
	prepare(part)
	-- Shadows where they read (the combat range); beyond it a bush is a few
	-- pixels and its shadow only costs shadow-pass triangles.
	part.CastShadow = template.CastShadow and (Vector2.new(at.X, at.Z) - TURRET).Magnitude < SHADOW_RANGE
	part.Size = template.Size * scale
	part.PivotOffset = CFrame.new(template.PivotOffset.Position * scale)
	local up = if tilt then normal else Vector3.yAxis
	local cf = CFrame.new(at) * CFrame.fromRotationBetweenVectors(Vector3.yAxis, up) * CFrame.Angles(0, yaw, 0)
	part:PivotTo(cf)
	part.Parent = folder
end

local function scatter(kit: Instance, folder: Instance, rng: Random): number
	local spacing = Spacing.new(32)
	local placed = 0
	-- Loose groups for scrub: shared cluster centres, members around them.
	local centres: { Vector2 } = {}
	for _ = 1, 400 do
		local p = Vector2.new(rng:NextNumber(BASIN.minX, BASIN.maxX), rng:NextNumber(BASIN.minZ, BASIN.maxZ))
		if allowed(p, 30) and rng:NextNumber() < density(p) then
			table.insert(centres, p)
		end
	end
	for _, kind in SCATTER do
		local template = kit:FindFirstChild(kind.name)
		if template and template:IsA("BasePart") then
			local sub = Instance.new("Folder")
			sub.Name = kind.name
			if kind.sway then
				sub:SetAttribute("Sway", kind.sway)
			end
			local count, tries = 0, 0
			while count < kind.count and tries < kind.count * 30 do
				tries += 1
				local p
				if kind.cluster and #centres > 0 and rng:NextNumber() < 0.8 then
					local c = centres[rng:NextInteger(1, #centres)]
					p = c + Vector2.new(rng:NextNumber(-1, 1), rng:NextNumber(-1, 1)).Unit * math.abs(rng:NextNumber(-1, 1)) * 26
				else
					p = Vector2.new(rng:NextNumber(BASIN.minX, BASIN.maxX), rng:NextNumber(BASIN.minZ, BASIN.maxZ))
				end
				local scale = rng:NextNumber(kind.scale[1], kind.scale[2])
				if allowed(p, kind.clear) and rng:NextNumber() < density(p) and spacing:free(p, kind.spacing * scale) then
					local hit = ground(p)
					if hit and (not kind.flat or level(p, 9 * scale, hit.Position.Y)) then
						place(template, sub, hit.Position, hit.Normal, rng:NextNumber(0, math.pi * 2), scale, not kind.flat)
						spacing:add(p)
						count += 1
					end
				end
			end
			sub.Parent = folder
			placed += count
		end
	end
	return placed
end

-- Old tyre tracks where buggies strafe (a ring 190-390 studs round the gun).
local function tracks(kit: Instance, folder: Instance, rng: Random): number
	local sub = Instance.new("Folder")
	sub.Name = "Tracks"
	local count = 0
	for _ = 1, 400 do
		if count >= 16 then
			break
		end
		local name = if rng:NextNumber() < 0.5 then "Tracks_A" else "Tracks_B"
		local template = kit:FindFirstChild(name)
		local radius = rng:NextNumber(190, 390)
		local angle = rng:NextNumber(-math.pi * 0.85, -math.pi * 0.15) -- in front of the gun (-Z)
		local p = TURRET + Vector2.new(math.cos(angle), math.sin(angle)) * radius
		if template and template:IsA("BasePart") and allowed(p, 0) then
			-- the ribbon is ~80 studs long: keep its whole length clear of the strips
			local tangent = Vector2.new(-math.sin(angle), math.cos(angle))
			local clear = true
			for _, k in { -40, -20, 0, 20, 40 } do
				local q = p + tangent * k
				clear = clear and allowed(q, 0)
				for _, lane in SCRUB_LANES do
					clear = clear and laneDistance(q, lane) > 18
				end
			end
			local hit = ground(p)
			if hit and clear and level(p, 30, hit.Position.Y) then
				local yaw = math.atan2(-tangent.Y, tangent.X) + rng:NextNumber(-0.15, 0.15)
				place(template, sub, hit.Position, hit.Normal, yaw, rng:NextNumber(0.9, 1.1), false)
				count += 1
			end
		end
	end
	sub.Parent = folder
	return count
end

-- Rock clusters and pebbles at the feet of the terrain boulders and the
-- rock-kit rocks.
local function boulderFeet(kit: Instance, folder: Instance, rng: Random): number
	local sub = Instance.new("Folder")
	sub.Name = "BoulderFeet"
	local count = 0
	local spots: { { p: Vector2, size: number } } = {}
	for _, b in TerrainBuilder.boulders do
		table.insert(spots, b)
	end
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local rockKit = battlefield and battlefield:FindFirstChild("RockKit")
	if rockKit then
		for _, m in rockKit:GetChildren() do
			if m:IsA("Model") then
				local cf, size = m:GetBoundingBox()
				table.insert(spots, { p = Vector2.new(cf.Position.X, cf.Position.Z), size = math.max(size.X, size.Z) * 0.5 })
			end
		end
	end
	for _, spot in spots do
		for _, pick in { { "Rocks_A", 0.45 }, { "Rocks_B", 0.3 }, { "Pebbles_A", 0.5 }, { "Pebbles_B", 0.35 } } do
			local template = kit:FindFirstChild(pick[1])
			if template and template:IsA("BasePart") and rng:NextNumber() < pick[2] then
				local dir = rng:NextNumber(0, math.pi * 2)
				local p = spot.p + Vector2.new(math.cos(dir), math.sin(dir)) * (spot.size * rng:NextNumber(0.9, 1.4))
				local hit = ground(p)
				if hit and TerrainBuilder.laneDistance(p) > 24 and allowed(p, 0) then
					local scale = math.clamp(spot.size / 5, 0.5, 1.4) * rng:NextNumber(0.8, 1.15)
					place(template, sub, hit.Position - Vector3.new(0, 0.1 * scale, 0), hit.Normal, dir, scale, true)
					count += 1
				end
			end
		end
	end
	sub.Parent = folder
	return count
end

-- Precise collision for the wash strips (see the header). ~0.3 s each.
local function applyCollision(parts: { MeshPart })
	for _, part in parts do
		local ok, err = pcall(function()
			local shaped = AssetService:CreateMeshPartAsync(Content.fromUri(part.MeshId), {
				CollisionFidelity = Enum.CollisionFidelity.PreciseConvexDecomposition,
				RenderFidelity = Enum.RenderFidelity.Precise,
			})
			part:ApplyMesh(shaped)
			shaped:Destroy()
		end)
		if not ok then
			warn(string.format("[RedMesa] strip collision for %s unavailable: %s", part.Name, tostring(err)))
		end
	end
end

local function buildStrips(folder: Instance): boolean
	local assets = ReplicatedStorage:FindFirstChild("Assets")
	local source = assets and assets:FindFirstChild("GroundStrips")
	if not source then
		return false
	end
	local ok, copy = pcall(function()
		return source:Clone()
	end)
	if not ok or not copy then
		return false
	end
	copy.Name = "Strips"
	local precise: { MeshPart } = {}
	for _, d in copy:GetDescendants() do
		if d:IsA("BasePart") then
			prepare(d)
			-- Wash pieces span the trough; a strip end climbing onto the mesa
			-- foot is taller than a flat road chunk. Their boxes would stand
			-- proud of the surface, so they get the real shape.
			if d:IsA("MeshPart") and (string.sub(d.Name, 1, 4) == "Wash" or d.Size.Y > PRECISE_ABOVE) then
				table.insert(precise, d)
			end
		end
	end
	copy.Parent = folder
	if #precise > 0 then
		task.spawn(applyCollision, precise)
	end
	return true
end

-- Builds the strips now and scatters the dressing once the terrain is
-- raycastable (after WorldBuilder's rock kit). Returns false when the
-- dressing kit is missing, so the caller can keep its old scrub.
function GroundDressing.build(parent: Instance): boolean
	local folder = Instance.new("Folder")
	folder.Name = "GroundDressing"
	folder.Parent = parent
	buildStrips(folder)
	local kit = templates()
	if not kit then
		return false
	end
	task.delay(1.6, function()
		local started = os.clock()
		local rng = Random.new(SEED)
		local dressing = Instance.new("Folder")
		dressing.Name = "Dressing"
		local n = scatter(kit, dressing, rng)
		n += tracks(kit, dressing, rng)
		n += boulderFeet(kit, dressing, rng)
		dressing.Parent = folder
		folder:SetAttribute("DressingCount", n)
		folder:SetAttribute("DressingSeconds", math.floor((os.clock() - started) * 100) / 100)
	end)
	return true
end

return GroundDressing
