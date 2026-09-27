--!strict
-- Plans one transport sortie (AD-1): the flight line, the stick of loads
-- and, for every load, the exact release, canopy-open and landing times and
-- positions, before anything is announced. Pure computation on the terrain
-- (no events, no state), deterministic for a given Random, so the gameplay
-- path and the dropZoneCheck debug command run the same code.
--
-- Geometry: the stick centre is picked on the group's lane at a distance
-- inside the kind's centre band, with lateral scatter. The transport flies
-- a straight line through it, roughly tangent to the outpost (never closer
-- than Transport.MIN_CLEARANCE, so never over the mesa), entering and
-- leaving beyond the canyon walls, in either direction. Loads leave in a
-- stick along the line; each one's landing point is its canopy-open point
-- plus a random drift, checked and nudged by AirdropZone.
--
-- Timing: either the transport enters at a given time (`{ t0 = ... }`,
-- escorts and debug sorties), or the first touchdown is aimed at a given
-- time (`{ land = ..., earliest = ... }`, wave groups): the planner builds
-- the path, measures entry -> first touchdown and sets the entry time
-- from it. When the time left is short it caps the altitude (shorter
-- descent) and tries the other entry side before giving up; a target that
-- no path can meet lands as early as possible (`late` > 0).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AirdropConfig = require(ReplicatedStorage.Shared.AirdropConfig)
local Config = require(ReplicatedStorage.Shared.Config)
local AirdropLanding = require(script.Parent.AirdropLanding)
local AirdropZone = require(script.Parent.AirdropZone)

local AirdropPlan = {}

export type PlannedLoad = {
	index: number,
	kind: string,
	lane: string,
	releaseT: number,
	openT: number,
	landT: number,
	openPos: Vector3,
	landPos: Vector3,
	face: Vector3,
	-- How far the sampler moved the landing point from its drift target.
	nudged: number,
}

export type Plan = {
	kind: string,
	lane: string,
	from: Vector3,
	to: Vector3,
	speed: number,
	t0: number,
	altitude: number,
	heading: Vector2,
	centre: Vector2,
	loads: { PlannedLoad },
	attempts: number,
	fallback: boolean,
	-- Server time of the first touchdown, the time asked for (nil when the
	-- entry time was given) and how many seconds after it the plan lands.
	firstLand: number,
	target: number?,
	late: number,
}

-- `t0`: enter at this server time. `land` (+ `earliest`): aim the first
-- touchdown at this server time, entering no earlier than `earliest`.
export type Timing = { t0: number?, land: number?, earliest: number? }

-- Formation: a follower flies its leader's line, offset sideways.
export type Follow = { heading: Vector2, altitude: number, centre: Vector2, slot: number }

local KINDS = AirdropConfig.KINDS
local T = AirdropConfig.Transport
local GROUND = AirdropConfig.Ground
local BAND = AirdropConfig.BAND
local PIVOT = Vector2.new(Config.TURRET_PIVOT.X, Config.TURRET_PIVOT.Z)

local function perp(v: Vector2): Vector2
	return Vector2.new(-v.Y, v.X)
end

local function rotate(v: Vector2, a: number): Vector2
	local c, s = math.cos(a), math.sin(a)
	return Vector2.new(v.X * c - v.Y * s, v.X * s + v.Y * c)
end

-- The lane a kind uses for `laneName`, resolved the way the enemy types
-- fall back (Buggy: by Left/Right, else WashLeft; others: Road).
function AirdropPlan.resolveLane(kind: string, laneName: string): string
	if Config.Lanes[laneName] then
		return laneName
	end
	if kind == "Buggy" then
		return if string.find(laneName, "Right") then "WashRight" else "WashLeft"
	end
	return "Road"
end

-- Horizontal closest approach of the line through `c` along `h` to the outpost.
function AirdropPlan.lineClearance(c: Vector2, h: Vector2): number
	local rel = c - PIVOT
	return math.abs(rel.X * h.Y - rel.Y * h.X)
end

-- Where the line through `c` along unit `h` leaves the flight box, as
-- signed distances along `h` (back, forward).
local function clip(c: Vector2, h: Vector2): (number, number)
	local sMin, sMax = -math.huge, math.huge
	local function axis(origin: number, dir: number, lo: number, hi: number)
		if math.abs(dir) < 1e-9 then
			return
		end
		local s1, s2 = (lo - origin) / dir, (hi - origin) / dir
		sMin = math.max(sMin, math.min(s1, s2))
		sMax = math.min(sMax, math.max(s1, s2))
	end
	axis(c.X, h.X, -T.BOX_X, T.BOX_X)
	axis(c.Y, h.Y, T.BOX_Z[1], T.BOX_Z[2])
	return sMin, sMax
end

-- A heading through `centre`: the tangent to the outpost swung by up to
-- MAX_TILT (less when needed to keep the clearance), in either direction.
local function pickHeading(rng: Random, centre: Vector2): Vector2
	local r = centre - PIVOT
	local d = r.Magnitude
	local tangent = perp(if d > 1e-3 then r.Unit else Vector2.new(0, -1))
	local need = T.MIN_CLEARANCE + T.CLEARANCE_MARGIN
	local tilt = if d > need then math.min(math.rad(T.MAX_TILT), math.acos(need / d)) else 0
	local a = rng:NextNumber(-tilt, tilt)
	local sign = if rng:NextNumber() < 0.5 then -1 else 1
	return rotate(tangent, a) * sign
end

-- Along-line offset (from the stick centre) of the first release.
local function firstRelease(kind: string, count: number): number
	local def = KINDS[kind]
	return (1 - (count + 1) / 2) * T.SPEED * def.stick - def.CARRY
end

-- Highest altitude from which the first load still touches down within
-- `budget` s of entering (assuming the lowest floor, the longest descent).
local function altitudeCap(kind: string, approach: number, budget: number): number
	local def = KINDS[kind]
	return (budget - approach - def.FREE_FALL) * def.DESCENT + def.FREE_FALL_DROP + GROUND.FLOOR_Y[1]
end

-- Last resort for one load: the point on its lane at the same distance
-- from the outpost (lanes are open, flat floor), settled if possible.
local function fallbackSpot(kind: string, lane: { Vector2 }, near: Vector2, placed: { AirdropZone.Taken }, deadline: number): Vector2
	local def = KINDS[kind]
	local d = math.clamp(AirdropLanding.distance(near), BAND[1] + 10, BAND[2] - 10)
	local onLane, dir = AirdropZone.lanePoint(lane, d)
	local settled = AirdropZone.settle(onLane, kind, lane, placed, def.nudge * 2, deadline + 0.01)
	if settled then
		return settled
	end
	for k = 1, 6 do
		local shift = (if k % 2 == 1 then 1 else -1) * math.ceil(k / 2) * def.spacing
		local q = onLane + dir * shift
		if not AirdropZone.check(q, kind, lane, placed) then
			return q
		end
	end
	return onLane
end

-- Builds a plan with times relative to entry (t0 = 0), or nil.
local function build(
	rng: Random,
	kind: string,
	laneName: string,
	lane: { Vector2 },
	count: number,
	taken: { AirdropZone.Taken },
	centre: Vector2,
	heading: Vector2,
	altitude: number,
	fallback: boolean,
	deadline: number
): Plan?
	if AirdropPlan.lineClearance(centre, heading) < T.MIN_CLEARANCE then
		return nil
	end
	local def = KINDS[kind]
	local speed = T.SPEED
	local sMin, sMax = clip(centre, heading)
	local placed: { AirdropZone.Taken } = table.clone(taken)
	local loads: { PlannedLoad } = {}
	local gap = speed * def.stick
	local firstLand = math.huge
	for i = 1, count do
		local along = (i - (count + 1) / 2) * gap
		local open2 = centre + heading * along
		local a = rng:NextNumber(0, math.pi * 2)
		local r = def.drift * math.sqrt(rng:NextNumber())
		local nominal = open2 + Vector2.new(math.cos(a), math.sin(a)) * r
		local land2: Vector2
		if fallback then
			land2 = fallbackSpot(kind, lane, nominal, placed, deadline)
		else
			local settled = AirdropZone.settle(nominal, kind, lane, placed, def.nudge, deadline)
			if not settled then
				return nil
			end
			land2 = settled
		end
		table.insert(placed, { p = land2, spacing = def.spacing })
		local releaseT = (along - def.CARRY - sMin) / speed
		local openT = releaseT + def.FREE_FALL
		local openY = altitude - def.FREE_FALL_DROP
		local groundY = AirdropZone.ground(land2.X, land2.Y) or 0
		local face = AirdropLanding.facing(lane, land2)
		local landT = openT + (openY - groundY) / def.DESCENT
		firstLand = math.min(firstLand, landT)
		table.insert(loads, {
			index = i,
			kind = kind,
			lane = laneName,
			releaseT = releaseT,
			openT = openT,
			landT = landT,
			openPos = Vector3.new(open2.X, openY, open2.Y),
			landPos = Vector3.new(land2.X, groundY, land2.Y),
			face = Vector3.new(face.X, 0, face.Y),
			nudged = (land2 - nominal).Magnitude,
		})
	end
	local from = centre + heading * sMin
	local to = centre + heading * sMax
	return {
		kind = kind,
		lane = laneName,
		from = Vector3.new(from.X, altitude, from.Y),
		to = Vector3.new(to.X, altitude, to.Y),
		speed = speed,
		t0 = 0,
		altitude = altitude,
		heading = heading,
		centre = centre,
		loads = loads,
		attempts = 0,
		fallback = fallback,
		firstLand = firstLand,
		target = nil,
		late = 0,
	}
end

-- Moves a relative plan to entry time t0.
local function place(plan: Plan, t0: number, target: number?, attempts: number): Plan
	plan.t0 = t0
	for _, l in plan.loads do
		l.releaseT += t0
		l.openT += t0
		l.landT += t0
	end
	plan.firstLand += t0
	plan.target = target
	plan.late = if target then math.max(0, plan.firstLand - target) else 0
	plan.attempts = attempts
	return plan
end

-- Plans a transport carrying `count` loads of `kind` for `laneName` (see
-- Timing). `taken` holds landing points still pending (kept clear).
-- Always returns a plan; `fallback` is set when no attempt passed every
-- check (within the time budget) and loads were put on their lane instead.
function AirdropPlan.sortie(rng: Random, kind: string, laneName: string, count: number, timing: Timing, taken: { AirdropZone.Taken }, follow: Follow?): Plan
	local def = KINDS[kind]
	assert(def, "not an airdropped kind: " .. kind)
	local deadline = os.clock() + GROUND.PLAN_BUDGET_MS / 1000
	local lane = Config.Lanes[AirdropPlan.resolveLane(kind, laneName)]
	local target = timing.land
	local earliest = timing.earliest or timing.t0 or 0
	local attempts = 0

	if follow then
		attempts += 1
		local side = if follow.slot % 2 == 1 then 1 else -1
		local offset = perp(follow.heading) * side * math.ceil(follow.slot / 2) * T.FORMATION_OFFSET
		local altitude = follow.altitude + T.FORMATION_CLIMB * follow.slot
		if altitude > T.ALTITUDE[2] then
			altitude = follow.altitude - T.FORMATION_CLIMB * follow.slot
		end
		altitude = math.clamp(altitude, T.ALTITUDE[1], T.ALTITUDE[2])
		local plan = build(rng, kind, laneName, lane, count, taken, follow.centre + offset, follow.heading, altitude, false, deadline)
		if plan then
			return place(plan, earliest, nil, attempts)
		end
	end

	local best: Plan? = nil
	local bestLate = math.huge
	for _ = 1, GROUND.ATTEMPTS do
		if os.clock() > deadline then
			break
		end
		local d = rng:NextNumber(def.centre[1], def.centre[2])
		local onLane, dir = AirdropZone.lanePoint(lane, d)
		local centre = onLane + perp(dir) * rng:NextNumber(-def.scatter, def.scatter)
		local heading = pickHeading(rng, centre)
		-- The drawn entry side first, then the other one.
		for flip = 0, 1 do
			attempts += 1
			local h = if flip == 0 then heading else -heading
			local altMax = T.ALTITUDE[2]
			if target then
				local sMin = clip(centre, h)
				local approach = (firstRelease(kind, count) - sMin) / T.SPEED
				altMax = math.min(altMax, altitudeCap(kind, approach, target - earliest))
			end
			local altitude = if altMax >= T.ALTITUDE[1] then rng:NextNumber(T.ALTITUDE[1], altMax) else T.ALTITUDE[1]
			local plan = build(rng, kind, laneName, lane, count, taken, centre, h, altitude, false, deadline)
			if plan then
				if not target then
					return place(plan, earliest, nil, attempts)
				end
				local t0 = target - plan.firstLand
				if t0 >= earliest - 1e-6 then
					return place(plan, t0, target, attempts)
				end
				if earliest - t0 < bestLate then
					best, bestLate = plan, earliest - t0
				end
			end
		end
	end
	if best then
		return place(best, earliest, target, attempts)
	end

	attempts += 1
	local centre = AirdropZone.lanePoint(lane, (def.centre[1] + def.centre[2]) / 2)
	local r = centre - PIVOT
	local heading = perp(r.Unit) * (if rng:NextNumber() < 0.5 then -1 else 1)
	local plan = build(rng, kind, laneName, lane, count, taken, centre, heading, T.ALTITUDE[1], true, deadline) :: Plan
	local t0 = if target then math.max(earliest, target - plan.firstLand) else earliest
	return place(plan, t0, target, attempts)
end

return AirdropPlan
