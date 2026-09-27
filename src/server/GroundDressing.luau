--!strict
-- Road and wash edge strips and ground dressing (FACELIFT_PLAN §4 Phase 1c
-- and 1d, ENV-3; density and zoning pass ENV-4). Visual only.
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
-- ENV-4 zones the scatter (zoneOf): scrub-heavy flats, rocky rises (dune
-- caps: rock clusters, pebbles, gravel patches), pebble fans below the
-- cliffs and buttes, and trampled ground along the scrub lanes (flat
-- trample ribbons, GroundPatches.rbxmx), plus flat patches (gravel, dry
-- stubble, dark soil), tyre tracks along the road shoulders and the wash
-- approaches, and more old craters with a coarse-sand dip under them.
-- Flat pieces lie on the floor and are drawn even on the lanes; they block
-- nothing (every piece is non-colliding and non-queryable).
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
local RunService = game:GetService("RunService")
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
-- Dressing casts shadows only this close to the turret (studs). ENV-4: 300
-- (was 480): the busy night wave is GPU-bound and a bush beyond 300 studs
-- is a few pixels; its shadow only costs shadow-pass triangles.
local SHADOW_RANGE = 300
-- The wash strips' alpha pebble-bed fringe (…_bankA) is dropped for chunks
-- whose centre is farther than this from the turret (ENV-4 GPU offset).
local BANK_ALPHA_RANGE = 500
-- Strip parts thicker than this (studs) get precise collision (see buildStrips).
local PRECISE_ABOVE = 0.6
local SCRUB_LANES = { "ScrubLeft", "ScrubRight" }
-- ENV-4: the dirt track from the road's far end to the ruined compound on
-- the left flank (ConflictLayout.GROUPS[1]); all beyond the drop band.
local COMPOUND_TRACK = { Vector2.new(-58, -884), Vector2.new(-160, -852), Vector2.new(-262, -836), Vector2.new(-322, -838) }

-- name: count, clearance from any lane (studs), scale range, min spacing,
-- clustered (scrub grows in loose groups), flat decal (needs level ground),
-- sway (wind hook, see the header).
-- Heights: nothing is taller than 3/4 of a soldier (Infantry is 7.2 studs;
-- the creosote at scale 1.0 is 5.4), so an airdropped soldier crossing the
-- basin floor always shows head and shoulders over the scrub.
-- ENV-4: `kit` (default GroundDressing; GroundPatches for the flat
-- patches), `zones` = acceptance weight per zone (see zoneOf; missing = 1),
-- `near` = only within this distance of the turret.
type Kind = { name: string, count: number, clear: number, scale: { number }, spacing: number, cluster: boolean?, flat: boolean?, sway: number?, kit: string?, zones: { [string]: number }?, near: number?, dip: boolean? }
local SCRUB = { flat = 1, rise = 0.3, fan = 0.2 }
local STONY = { flat = 0.12, rise = 1, fan = 1 }
local SCATTER: { Kind } = {
	{ name = "Scrub_A", count = 260, clear = 26, scale = { 0.7, 1.25 }, spacing = 7, cluster = true, sway = 0.05, zones = SCRUB },
	{ name = "Scrub_B", count = 150, clear = 26, scale = { 0.7, 1.2 }, spacing = 7, cluster = true, sway = 0.05, zones = { flat = 1, rise = 0.5, fan = 0.5 } },
	{ name = "Creosote", count = 90, clear = 32, scale = { 0.75, 1.0 }, spacing = 10, cluster = true, sway = 0.035, zones = SCRUB },
	{ name = "Saltbush", count = 80, clear = 30, scale = { 0.7, 1.15 }, spacing = 10, cluster = true, sway = 0.04, zones = SCRUB },
	{ name = "Grass", count = 320, clear = 22, scale = { 0.75, 1.3 }, spacing = 4, cluster = true, sway = 0.1, zones = { flat = 1, rise = 0.35, fan = 0.3 } },
	{ name = "Branch_A", count = 45, clear = 22, scale = { 0.8, 1.3 }, spacing = 8 },
	{ name = "Branch_B", count = 45, clear = 22, scale = { 0.8, 1.3 }, spacing = 8 },
	-- ENV-4 GPU offset: pebble patches 220 -> 110, now on the rises and fans.
	{ name = "Pebbles_A", count = 55, clear = 18, scale = { 0.8, 1.4 }, spacing = 6, zones = STONY },
	{ name = "Pebbles_B", count = 55, clear = 18, scale = { 0.8, 1.4 }, spacing = 6, zones = STONY },
	{ name = "Rocks_A", count = 36, clear = 24, scale = { 0.6, 1.2 }, spacing = 14, zones = { flat = 0.08, rise = 1, fan = 1 } },
	{ name = "Rocks_B", count = 28, clear = 24, scale = { 0.6, 1.1 }, spacing = 14, zones = { flat = 0.08, rise = 1, fan = 1 } },
	{ name = "Crater", count = 26, clear = 30, scale = { 0.7, 1.3 }, spacing = 45, flat = true, dip = true },
	{ name = "Patch_Gravel", kit = "GroundPatches", count = 130, clear = 16, scale = { 0.6, 1.4 }, spacing = 16, flat = true, zones = { flat = 0.3, rise = 1, fan = 1 } },
	{ name = "Patch_Stubble", kit = "GroundPatches", count = 180, clear = 18, scale = { 0.7, 1.5 }, spacing = 12, flat = true, cluster = true, zones = { flat = 1, rise = 0.25, fan = 0.1 } },
	{ name = "Patch_Stain", kit = "GroundPatches", count = 50, clear = 12, scale = { 0.8, 1.6 }, spacing = 26, flat = true, zones = { flat = 1, rise = 0.3, fan = 0.2 }, near = 750 },
}

-- Studio-only perf A/B (ENV-4): with the Workspace attribute `Env4Before`
-- set in Edit before Play, the world is built as ENV-3F left it (this
-- scatter, 480-stud shadows, 0.35 far density, the wash fringe kept, no
-- zoning, lane wear or conflict dressing), so the same wave can be
-- measured before and after. Never set in a live game.
GroundDressing.BEFORE = RunService:IsStudio() and Workspace:GetAttribute("Env4Before") == true
local SCATTER_ENV3: { Kind } = {
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
if GroundDressing.BEFORE then
	SCATTER = SCATTER_ENV3
	SHADOW_RANGE = 480
	BANK_ALPHA_RANGE = math.huge
end

local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Include

local function templates(name: string?): Instance?
	local assets = ReplicatedStorage:FindFirstChild("Assets")
	return assets and assets:FindFirstChild(name or "GroundDressing")
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
	if GroundDressing.BEFORE then
		return math.max(0.35, 1 - (d - 450) / 650 * 0.65)
	end
	-- ENV-4 GPU offset: the far floor is 0.2 (was 0.35); the far basin
	-- reads through the terrain zoning and the conflict dressing instead.
	return math.max(0.2, 1 - (d - 450) / 650 * 0.8)
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

-- ENV-4: the ground under a flat patch of radius r lies on the plane of
-- `hit` (within `tol`), so the patch can be tilted to it without the
-- terrain poking through or the patch floating.
local function planar(p: Vector2, r: number, hit: RaycastResult, tol: number): boolean
	local n, y0 = hit.Normal, hit.Position.Y
	for k = 0, 7 do
		local a = k * math.pi / 4 + 0.3
		local o = Vector2.new(math.cos(a), math.sin(a)) * r
		local h = ground(p + o)
		if not h then
			return false
		end
		local want = y0 - (n.X * o.X + n.Z * o.Y) / n.Y
		if math.abs(h.Position.Y - want) > tol then
			return false
		end
	end
	return true
end

-- ENV-4 zones: "fan" (pebble fans below the flank and far walls and round
-- the buttes), "rise" (dune caps, TerrainBuilder paints them coarse), else
-- "flat" (scrub-heavy flats).
local function zoneOf(p: Vector2, y: number): string
	if math.abs(p.X) > 600 or p.Y < -1170 then
		return "fan"
	end
	for _, b in BUTTES do
		if (p - b[1]).Magnitude < b[2] + 95 then
			return "fan"
		end
	end
	if y > TerrainBuilder.RISE_Y then
		return "rise"
	end
	return "flat"
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

local function place(template: BasePart, folder: Instance, at: Vector3, normal: Vector3, yaw: number, scale: number, tilt: boolean): BasePart
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
	return part
end

local function scatter(kit: Instance, folder: Instance, rng: Random): number
	local spacing = Spacing.new(32)
	local placed = 0
	local dips: { { p: Vector2, r: number } } = {}
	-- Loose groups for scrub: shared cluster centres, members around them.
	local centres: { Vector2 } = {}
	for _ = 1, 400 do
		local p = Vector2.new(rng:NextNumber(BASIN.minX, BASIN.maxX), rng:NextNumber(BASIN.minZ, BASIN.maxZ))
		if allowed(p, 30) and rng:NextNumber() < density(p) then
			table.insert(centres, p)
		end
	end
	for _, kind in SCATTER do
		local source = if kind.kit then templates(kind.kit) else kit
		local template = source and source:FindFirstChild(kind.name)
		if template and template:IsA("BasePart") then
			local sub = Instance.new("Folder")
			sub.Name = kind.name
			if kind.sway then
				sub:SetAttribute("Sway", kind.sway)
			end
			-- patches (flat, GroundPatches kit) keep their own spacing so
			-- they may lie under bushes and rocks
			local grid = if kind.kit then Spacing.new(32) else spacing
			local radius = math.max(template.Size.X, template.Size.Z) / 2
			local count, tries = 0, 0
			while count < kind.count and tries < kind.count * 40 do
				tries += 1
				local p
				if kind.cluster and #centres > 0 and rng:NextNumber() < 0.8 then
					local c = centres[rng:NextInteger(1, #centres)]
					p = c + Vector2.new(rng:NextNumber(-1, 1), rng:NextNumber(-1, 1)).Unit * math.abs(rng:NextNumber(-1, 1)) * 26
				else
					p = Vector2.new(rng:NextNumber(BASIN.minX, BASIN.maxX), rng:NextNumber(BASIN.minZ, BASIN.maxZ))
				end
				local scale = rng:NextNumber(kind.scale[1], kind.scale[2])
				local near = not kind.near or (p - TURRET).Magnitude < kind.near
				if near and allowed(p, kind.clear) and rng:NextNumber() < density(p) and grid:free(p, kind.spacing * scale) then
					local hit = ground(p)
					local weight = if hit and kind.zones then (kind.zones[zoneOf(p, hit.Position.Y)] or 1) else 1
					if hit and rng:NextNumber() < weight then
						local ok
						if kind.kit then
							ok = planar(p, radius * scale * 0.9, hit, 0.12)
						elseif kind.flat then
							ok = level(p, 9 * scale, hit.Position.Y)
						else
							ok = true
						end
						if ok then
							place(template, sub, hit.Position, hit.Normal, rng:NextNumber(0, math.pi * 2), scale, not kind.flat or kind.kit ~= nil)
							if kind.dip then
								-- painted after the scatter (a voxel write can make the
								-- terrain briefly miss raycasts)
								table.insert(dips, { p = p, r = 8 * scale })
							end
							grid:add(p)
							count += 1
						end
					end
				end
			end
			sub.Parent = folder
			placed += count
		end
	end
	for _, d in dips do
		TerrainBuilder.dip(d.p, d.r)
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

-- ENV-4: a ribbon of half-length h along `dir` lies on the plane of the
-- ground at its centre (checked at its ends and quarter points).
local function ribbonFits(p: Vector2, dir: Vector2, h: number, hit: RaycastResult, tol: number): boolean
	local n, y0 = hit.Normal, hit.Position.Y
	for _, k in { -1, -0.5, 0.5, 1 } do
		local o = dir * (h * k)
		local g = ground(p + o)
		if not g then
			return false
		end
		if math.abs(g.Position.Y - (y0 - (n.X * o.X + n.Z * o.Y) / n.Y)) > tol then
			return false
		end
	end
	return true
end

-- ENV-4: flat ribbons chained along a polyline, `offset` studs to its side
-- (both sides when `both`), every `step`; `ok(p)` vetoes a spot.
type Chain = { pts: { Vector2 }, offset: number, both: boolean?, step: number, jitter: number, chance: number, names: { string }, ok: ((Vector2) -> boolean)?, scale: { number }?, swing: number? }

local function chain(kits: { Instance }, folder: Instance, c: Chain, rng: Random): number
	local count = 0
	for i = 1, #c.pts - 1 do
		local a, b = c.pts[i], c.pts[i + 1]
		local d = b - a
		local dir = d.Unit
		local side = Vector2.new(-dir.Y, dir.X)
		local n = math.max(1, math.floor(d.Magnitude / c.step + 0.5))
		for k = 0, n - 1 do
			for _, sgn in (if c.both then { -1, 1 } else { 1 }) do
				if rng:NextNumber() < c.chance then
					local name = c.names[rng:NextInteger(1, #c.names)]
					local template: Instance? = nil
					for _, kit in kits do
						template = template or kit:FindFirstChild(name)
					end
					local p = a + dir * (c.step * (k + 0.5)) + side * sgn * (c.offset + rng:NextNumber(-1, 1) * c.jitter)
					if template and template:IsA("BasePart") and (not c.ok or (c.ok :: any)(p)) then
						local hit = ground(p)
						local swing = rng:NextNumber(-1, 1) * (c.swing or 0.12)
						local along = Vector2.new(dir.X * math.cos(swing) - dir.Y * math.sin(swing), dir.X * math.sin(swing) + dir.Y * math.cos(swing))
						if hit and ribbonFits(p, along, template.Size.X * 0.45, hit, 0.3) then
							local scale = if c.scale then rng:NextNumber(c.scale[1], c.scale[2]) else 1
							if rng:NextNumber() < 0.5 then
								along = -along
							end
							place(template, folder, hit.Position, hit.Normal, math.atan2(-along.Y, along.X), scale, true)
							count += 1
						end
					end
				end
			end
		end
	end
	return count
end

-- ENV-4 lanes and roads: trampled ground on the scrub lanes, tyre tracks
-- along the road shoulders and beside the wash approaches, and a dirt track
-- from the road's far end to the ruined compound (ConflictLayout).
local function laneWear(kit: Instance, patches: Instance?, folder: Instance, rng: Random): number
	local sub = Instance.new("Folder")
	sub.Name = "LaneWear"
	local kits: { Instance } = { kit }
	if patches then
		table.insert(kits, 1, patches)
	end
	local function offStrips(p: Vector2): boolean
		if p.Magnitude < BASIN.mesa + 10 then
			return false
		end
		for name, reach in STRIP_LANES do
			if laneDistance(p, name) < reach then
				return false
			end
		end
		return true
	end
	local function offLanesAndStrips(p: Vector2): boolean
		return offStrips(p) and TerrainBuilder.laneDistance(p) > 16
	end
	local n = 0
	if patches then
		for _, lane in SCRUB_LANES do
			n += chain(kits, sub, { pts = Config.Lanes[lane], offset = 0, step = 64, jitter = 5, chance = 0.7, names = { "Trample" }, ok = offStrips, scale = { 0.8, 1.1 }, swing = 0.08 }, rng)
		end
	end
	-- vehicles that pulled off the road: short arcs leaving it at an angle
	n += chain(kits, sub, { pts = Config.Lanes.Road, offset = 44, both = true, step = 80, jitter = 14, chance = 0.4, names = { "Tracks_A", "Tracks_B" }, ok = offLanesAndStrips, swing = 0.55 }, rng)
	for _, lane in { "WashLeft", "WashRight" } do
		n += chain(kits, sub, { pts = Config.Lanes[lane], offset = 60, both = true, step = 110, jitter = 14, chance = 0.4, names = { "Tracks_A", "Tracks_B" }, ok = offLanesAndStrips, swing = 0.5 }, rng)
		-- eroded banks: stones and dead wood left on the bank tops by floods
		n += chain(kits, sub, { pts = Config.Lanes[lane], offset = 45, both = true, step = 34, jitter = 3, chance = 0.4, names = { "Branch_A", "Pebbles_B", "Pebbles_A" }, ok = offLanesAndStrips, scale = { 0.6, 1.0 } }, rng)
	end
	n += chain(kits, sub, { pts = COMPOUND_TRACK, offset = 0, step = 70, jitter = 1.5, chance = 1, names = { "Tracks_B", "Tracks_A" } }, rng)
	sub.Parent = folder
	return n
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
		if d:IsA("BasePart") and string.sub(d.Name, -6) == "_bankA" and (Vector2.new(d.Position.X, d.Position.Z) - TURRET).Magnitude > BANK_ALPHA_RANGE then
			d:Destroy()
		elseif d:IsA("BasePart") then
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
		if not GroundDressing.BEFORE then
			n += laneWear(kit, templates("GroundPatches"), dressing, rng)
		end
		dressing.Parent = folder
		folder:SetAttribute("DressingCount", n)
		folder:SetAttribute("DressingSeconds", math.floor((os.clock() - started) * 100) / 100)
	end)
	return true
end

return GroundDressing
