--!strict
-- Drop-zone sampler (AD-1): decides whether a landing point is good and
-- nudges bad ones. A good point is
--   * band:    300-800 studs (horizontal) from the outpost;
--   * spacing: clear of every other pending landing point;
--   * ground:  open basin floor (sand, coarse sand, road, wash bed) at floor
--              height, never a cliff, butte, the mesa slope or a boulder;
--   * slope:   flat enough under the load's footprint to drive off (so
--              never on a wash bank or a dune flank);
--   * rock:    clear of the queryable rock kit (Battlefield.RockKit and any
--              other queryable part in the basin) and of the terrain
--              boulders, footprint and path;
--   * reach:   a clear walk/drive to its lane's join waypoint.
-- Heights are measured on the terrain (the gameplay surface); landscape and
-- dressing meshes are visual only (CanQuery = false) and sit on it.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local AirdropConfig = require(ReplicatedStorage.Shared.AirdropConfig)
local AirdropLanding = require(script.Parent.AirdropLanding)
local TerrainBuilder = require(script.Parent.TerrainBuilder)

local AirdropZone = {}

export type Taken = { p: Vector2, spacing: number }

local GROUND = AirdropConfig.Ground
local BAND = AirdropConfig.BAND
-- The planner stays SLOPE_MARGIN / REACH_MARGIN inside the audited limits.
local MAX_SLOPE_TAN = math.tan(math.rad(GROUND.MAX_SLOPE - GROUND.SLOPE_MARGIN))
-- Footprint rings: (fraction of the footprint radius, slope checked),
-- sampled every RING_SPACING studs of arc (at least 12 samples). The outer
-- ring is a margin: open floor only, any slope.
local FOOTPRINT_RINGS = { { 1.25, false }, { 1, true }, { 0.5, true } }

local OPEN: { [Enum.Material]: boolean } = {}
for _, name in GROUND.MATERIALS do
	OPEN[(Enum.Material :: any)[name]] = true
end

local terrainParams = RaycastParams.new()
terrainParams.FilterType = Enum.RaycastFilterType.Include
terrainParams.FilterDescendantsInstances = { Workspace.Terrain }

-- Terrain height and material under (x, z); nil off the terrain.
function AirdropZone.ground(x: number, z: number): (number?, Enum.Material?)
	local hit = Workspace:Raycast(Vector3.new(x, 500, z), Vector3.new(0, -620, 0), terrainParams)
	if not hit then
		return nil, nil
	end
	return hit.Position.Y, hit.Material
end

-- Queryable rock in the basin as bounding circles, rebuilt when the world
-- changes (the rock kit is placed a second after the world is built).
export type Rock = { p: Vector2, r: number }
local rocks: { Rock } = {}
local rocksKey = ""
local rocksAt = -math.huge

local function circleOf(cf: CFrame, size: Vector3): Rock
	return { p = Vector2.new(cf.X, cf.Z), r = math.sqrt(size.X * size.X + size.Z * size.Z) / 2 }
end

function AirdropZone.rocks(): { Rock }
	if os.clock() - rocksAt < 2 then
		return rocks
	end
	rocksAt = os.clock()
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local kit = battlefield and battlefield:FindFirstChild("RockKit")
	local key = tostring(battlefield) .. ":" .. tostring(kit and #kit:GetChildren() or 0) .. ":" .. #TerrainBuilder.boulders
	if battlefield and key == rocksKey then
		return rocks
	end
	rocksKey = key
	local list: { Rock } = {}
	if battlefield then
		local skip = battlefield:FindFirstChild("Emplacement")
		for _, child in battlefield:GetChildren() do
			if child == skip then
				continue
			end
			-- One circle per model (a rock), or per loose queryable part.
			for _, item in (if child:IsA("Folder") then child:GetChildren() else { child }) do
				if item:IsA("Model") then
					local queryable = false
					for _, d in item:GetDescendants() do
						if d:IsA("BasePart") and d.CanQuery and d.Transparency < 1 then
							queryable = true
							break
						end
					end
					if queryable then
						local cf, size = item:GetBoundingBox()
						table.insert(list, circleOf(cf, size))
					end
				elseif item:IsA("BasePart") and item.CanQuery and item.Transparency < 1 then
					table.insert(list, circleOf(item.CFrame, item.Size))
				end
			end
		end
	end
	for _, b in TerrainBuilder.boulders do
		table.insert(list, { p = b.p, r = b.size * GROUND.BOULDER_EXTENT })
	end
	-- Only what can matter to a landing or a walk to a lane.
	local basin: { Rock } = {}
	for _, rock in list do
		local d = AirdropLanding.distance(rock.p)
		if d + rock.r > BAND[1] - 120 and d - rock.r < BAND[2] + 120 and rock.r < 80 then
			table.insert(basin, rock)
		end
	end
	rocks = basin
	return rocks
end

local function segmentDistance(p: Vector2, a: Vector2, b: Vector2): number
	local ab = b - a
	local len2 = ab:Dot(ab)
	local t = if len2 > 1e-9 then math.clamp((p - a):Dot(ab) / len2, 0, 1) else 0
	return (p - (a + ab * t)).Magnitude
end

local function onFloor(y: number?, material: Enum.Material?): boolean
	return y ~= nil and material ~= nil and OPEN[material] == true and y >= GROUND.FLOOR_Y[1] and y <= GROUND.FLOOR_Y[2]
end

-- "band", "spacing", "rock", "ground", "slope" or nil.
local function checkSpot(p: Vector2, spacing: number, footprint: number, taken: { Taken }): string?
	local d = AirdropLanding.distance(p)
	if d < BAND[1] or d > BAND[2] then
		return "band"
	end
	for _, other in taken do
		if (other.p - p).Magnitude < math.max(spacing, other.spacing) then
			return "spacing"
		end
	end
	local clear = footprint * FOOTPRINT_RINGS[1][1] + GROUND.ROCK_CLEARANCE
	for _, rock in AirdropZone.rocks() do
		if (rock.p - p).Magnitude < rock.r + clear then
			return "rock"
		end
	end
	local y, material = AirdropZone.ground(p.X, p.Y)
	if not onFloor(y, material) then
		return "ground"
	end
	local centreY = y :: number
	local low, high = centreY, centreY
	for _, ring in FOOTPRINT_RINGS do
		local r = footprint * ring[1]
		local n = math.max(12, math.ceil(2 * math.pi * r / GROUND.RING_SPACING))
		for k = 0, n - 1 do
			local a = k / n * math.pi * 2
			local q = p + Vector2.new(math.cos(a), math.sin(a)) * r
			local qy, qm = AirdropZone.ground(q.X, q.Y)
			if not onFloor(qy, qm) then
				return "ground"
			end
			if ring[2] then
				low, high = math.min(low, qy :: number), math.max(high, qy :: number)
				if math.abs((qy :: number) - centreY) > r * MAX_SLOPE_TAN then
					return "slope"
				end
			end
		end
	end
	if high - low > footprint * MAX_SLOPE_TAN * 2 then
		return "slope"
	end
	return nil
end

-- Walkable/drivable straight line from `p` to its lane's join waypoint:
-- on the floor, no step steeper than REACH_MAX_STEP, clear of rock.
function AirdropZone.reach(p: Vector2, lane: { Vector2 }): boolean
	local goal = lane[AirdropLanding.joinIndex(lane, p)]
	for _, rock in AirdropZone.rocks() do
		if segmentDistance(rock.p, p, goal) < rock.r + GROUND.ROCK_CLEARANCE then
			return false
		end
	end
	local delta = goal - p
	local n = math.max(1, math.ceil(delta.Magnitude / GROUND.REACH_STEP))
	local maxStep = GROUND.REACH_MAX_STEP * GROUND.REACH_MARGIN * (delta.Magnitude / n) / GROUND.REACH_STEP
	local lastY: number? = nil
	for k = 0, n do
		local q = p + delta * (k / n)
		local y, material = AirdropZone.ground(q.X, q.Y)
		if not onFloor(y, material) then
			return false
		end
		if lastY and math.abs(y - lastY) > maxStep then
			return false
		end
		lastY = y
	end
	return true
end

-- Why `p` is not a good landing point for `kind` on `lane` (nil = good).
function AirdropZone.check(p: Vector2, kind: string, lane: { Vector2 }, taken: { Taken }): string?
	local def = AirdropConfig.KINDS[kind]
	local reason = checkSpot(p, def.spacing, def.footprint, taken)
	if reason then
		return reason
	end
	if not AirdropZone.reach(p, lane) then
		return "reach"
	end
	return nil
end

-- `p` if it is good, else the nearest good point found on rings around it
-- (up to `maxRadius`), else nil and the reason `p` failed. Gives up (nil,
-- "budget") once os.clock() passes `deadline`.
function AirdropZone.settle(p: Vector2, kind: string, lane: { Vector2 }, taken: { Taken }, maxRadius: number, deadline: number?): (Vector2?, string?)
	local reason = AirdropZone.check(p, kind, lane, taken)
	if not reason then
		return p, nil
	end
	local step = GROUND.NUDGE_STEP
	local r = step
	while r <= maxRadius + 1e-6 do
		if deadline and os.clock() > deadline then
			return nil, "budget"
		end
		local n = math.max(6, math.floor(2 * math.pi * r / step))
		local offset = r * 0.37
		for k = 0, n - 1 do
			local a = offset + k / n * math.pi * 2
			local q = p + Vector2.new(math.cos(a), math.sin(a)) * r
			if not AirdropZone.check(q, kind, lane, taken) then
				return q, nil
			end
		end
		r += step
	end
	return nil, reason
end

-- The point on a lane polyline at horizontal distance `d` from the outpost
-- and the lane direction there (lanes run from far to near).
function AirdropZone.lanePoint(lane: { Vector2 }, d: number): (Vector2, Vector2)
	for i = 1, #lane - 1 do
		local a, b = lane[i], lane[i + 1]
		local da, db = AirdropLanding.distance(a), AirdropLanding.distance(b)
		if da >= d and db <= d then
			local lo, hi = 0, 1
			for _ = 1, 24 do
				local mid = (lo + hi) / 2
				if AirdropLanding.distance(a:Lerp(b, mid)) > d then
					lo = mid
				else
					hi = mid
				end
			end
			return a:Lerp(b, (lo + hi) / 2), (b - a).Unit
		end
	end
	if d > AirdropLanding.distance(lane[1]) then
		return lane[1], (lane[2] - lane[1]).Unit
	end
	return lane[#lane], (lane[#lane] - lane[#lane - 1]).Unit
end

return AirdropZone
