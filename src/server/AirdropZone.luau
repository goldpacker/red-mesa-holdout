--!strict
-- Drop-zone sampler (AD-1): decides whether a landing point is good and
-- nudges bad ones. A good point is
--   * band:    300-800 studs (horizontal) from the outpost;
--   * spacing: clear of every other pending landing point;
--   * ground:  open basin floor (sand, coarse sand, road, wash bed) at floor
--              height, never a cliff, butte, the mesa slope or a boulder;
--   * slope:   flat enough under the load's footprint to drive off (so
--              never on a wash bank or a dune flank);
--   * reach:   a clear walk/drive to its lane's join waypoint.
-- Everything is measured on the terrain (the gameplay surface); landscape
-- and dressing meshes are ignored.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local AirdropConfig = require(ReplicatedStorage.Shared.AirdropConfig)
local AirdropLanding = require(script.Parent.AirdropLanding)

local AirdropZone = {}

export type Taken = { p: Vector2, spacing: number }

local GROUND = AirdropConfig.Ground
local BAND = AirdropConfig.BAND
local MAX_SLOPE_TAN = math.tan(math.rad(GROUND.MAX_SLOPE))
-- Footprint rings: (fraction of the footprint radius, samples, slope
-- checked). The outer ring is a margin: open floor only, any slope.
local FOOTPRINT_RINGS = { { 1.25, 16, false }, { 1, 12, true }, { 0.5, 6, true } }

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

local function onFloor(y: number?, material: Enum.Material?): boolean
	return y ~= nil and material ~= nil and OPEN[material] == true and y >= GROUND.FLOOR_Y[1] and y <= GROUND.FLOOR_Y[2]
end

-- "band", "spacing", "ground", "slope" or nil.
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
	local y, material = AirdropZone.ground(p.X, p.Y)
	if not onFloor(y, material) then
		return "ground"
	end
	local centreY = y :: number
	local low, high = centreY, centreY
	for _, ring in FOOTPRINT_RINGS do
		local r = footprint * ring[1]
		local n = ring[2]
		for k = 0, n - 1 do
			local a = k / n * math.pi * 2
			local q = p + Vector2.new(math.cos(a), math.sin(a)) * r
			local qy, qm = AirdropZone.ground(q.X, q.Y)
			if not onFloor(qy, qm) then
				return "ground"
			end
			if ring[3] then
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

-- Walkable/drivable straight line from `p` to its lane's join waypoint.
function AirdropZone.reach(p: Vector2, lane: { Vector2 }): boolean
	local goal = lane[AirdropLanding.joinIndex(lane, p)]
	local delta = goal - p
	local n = math.max(1, math.ceil(delta.Magnitude / GROUND.REACH_STEP))
	local lastY: number? = nil
	for k = 0, n do
		local q = p + delta * (k / n)
		local y, material = AirdropZone.ground(q.X, q.Y)
		if y == nil or material == nil or y < GROUND.FLOOR_Y[1] or y > GROUND.FLOOR_Y[2] then
			return false
		end
		if lastY and math.abs(y - lastY) > GROUND.REACH_MAX_STEP then
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
-- (up to `maxRadius`), else nil and the reason `p` failed.
function AirdropZone.settle(p: Vector2, kind: string, lane: { Vector2 }, taken: { Taken }, maxRadius: number): (Vector2?, string?)
	local reason = AirdropZone.check(p, kind, lane, taken)
	if not reason then
		return p, nil
	end
	local step = GROUND.NUDGE_STEP
	local r = step
	while r <= maxRadius + 1e-6 do
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
