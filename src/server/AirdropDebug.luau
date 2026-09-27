--!strict
-- Studio-only airdrop QA commands behind ServerStorage.RedMesaDebug
-- (GameController.installDebugHooks). See tools/qa/BEAUTY.md §8.
--   airdrop        { kind = "Infantry", count = 8, lane = "Road" }: fly a
--                  sortie now in the running wave (counts toward it)
--   dropZoneCheck  { samples = 600, seed = 1 }: plans many sorties with the
--                  gameplay planner and re-checks every landing point and
--                  flight line with stricter, independent sampling
--   airdropStats   counters since the last reset ({ reset = true } clears)
--   airdropSeed    n pins the run seed (nil = fresh seed each run)

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local AirdropConfig = require(ReplicatedStorage.Shared.AirdropConfig)
local AirdropPath = require(ReplicatedStorage.Shared.AirdropPath)
local Config = require(ReplicatedStorage.Shared.Config)
local Airdrop = require(script.Parent.Airdrop)
local AirdropLanding = require(script.Parent.AirdropLanding)
local AirdropPlan = require(script.Parent.AirdropPlan)
local AirdropZone = require(script.Parent.AirdropZone)

local AirdropDebug = {}

local KINDS = AirdropConfig.KINDS
local GROUND = AirdropConfig.Ground
local T = AirdropConfig.Transport
local PIVOT = Config.TURRET_PIVOT
-- The basin interior a transport must start and end outside of.
local BASIN_X = 1000
local BASIN_Z = { -1500, 400 }
-- Sideways drift under canopy faster than this reads as a pop.
local MAX_DRIFT_SPEED = 9

local OPEN: { [Enum.Material]: boolean } = {}
for _, name in GROUND.MATERIALS do
	OPEN[(Enum.Material :: any)[name]] = true
end

local terrainParams = RaycastParams.new()
terrainParams.FilterType = Enum.RaycastFilterType.Include
terrainParams.FilterDescendantsInstances = { Workspace.Terrain }

local function probe(x: number, z: number): RaycastResult?
	return Workspace:Raycast(Vector3.new(x, 500, z), Vector3.new(0, -620, 0), terrainParams)
end

local function fmt(p: Vector3 | Vector2): string
	if typeof(p) == "Vector3" then
		return string.format("(%d,%d,%d)", p.X, p.Y, p.Z)
	end
	return string.format("(%d,%d)", (p :: Vector2).X, (p :: Vector2).Y)
end

-- Independent, denser re-check of one landing point. Returns reasons.
local function recheck(kind: string, laneName: string, p: Vector2, landY: number, others: { AirdropZone.Taken }): { string }
	local reasons = {}
	local def = KINDS[kind]
	local d = AirdropLanding.distance(p)
	if d < AirdropConfig.BAND[1] - 0.01 or d > AirdropConfig.BAND[2] + 0.01 then
		table.insert(reasons, string.format("band %.0f", d))
	end
	local hit = probe(p.X, p.Y)
	if not hit then
		table.insert(reasons, "ground none")
		return reasons
	end
	if not OPEN[hit.Material] then
		table.insert(reasons, "ground " .. hit.Material.Name)
	end
	if hit.Position.Y < GROUND.FLOOR_Y[1] or hit.Position.Y > GROUND.FLOOR_Y[2] then
		table.insert(reasons, string.format("ground y %.1f", hit.Position.Y))
	end
	if math.abs(hit.Position.Y - landY) > 0.05 then
		table.insert(reasons, string.format("landY %.2f vs ground %.2f", landY, hit.Position.Y))
	end
	-- Slope: 12 samples on the footprint rim and 6 at half radius.
	local tanMax = math.tan(math.rad(GROUND.MAX_SLOPE)) + 0.03
	for _, ring in { { def.footprint, 12 }, { def.footprint * 0.5, 6 } } do
		local r, n = ring[1], ring[2]
		for k = 0, n - 1 do
			local a = k / n * math.pi * 2 + 0.13
			local q = p + Vector2.new(math.cos(a), math.sin(a)) * r
			local h = probe(q.X, q.Y)
			if not h or not OPEN[h.Material] then
				table.insert(reasons, "footprint " .. (if h then h.Material.Name else "none"))
				break
			elseif math.abs(h.Position.Y - hit.Position.Y) / r > tanMax then
				table.insert(reasons, string.format("slope %.0f deg", math.deg(math.atan(math.abs(h.Position.Y - hit.Position.Y) / r))))
				break
			end
		end
	end
	for _, o in others do
		local gap = (o.p - p).Magnitude
		if gap < math.max(def.spacing, o.spacing) - 0.01 then
			table.insert(reasons, string.format("spacing %.1f", gap))
			break
		end
	end
	-- Reach: every 3 studs to the join waypoint, which must be ahead.
	local lane = Config.Lanes[laneName]
	local join = AirdropLanding.joinIndex(lane, p)
	local goal = lane[join]
	if AirdropLanding.distance(goal) >= d then
		table.insert(reasons, "reach: join waypoint not ahead")
	end
	local delta = goal - p
	local n = math.max(1, math.ceil(delta.Magnitude / 3))
	local lastY = hit.Position.Y
	local maxPerStud = GROUND.REACH_MAX_STEP / GROUND.REACH_STEP
	for k = 1, n do
		local q = p + delta * (k / n)
		local h = probe(q.X, q.Y)
		if not h or h.Position.Y > GROUND.FLOOR_Y[2] or h.Position.Y < GROUND.FLOOR_Y[1] then
			table.insert(reasons, "reach: off the floor at " .. fmt(q))
			break
		end
		if math.abs(h.Position.Y - lastY) / (delta.Magnitude / n) > maxPerStud * 1.5 then
			table.insert(reasons, string.format("reach: step %.1f at %s", math.abs(h.Position.Y - lastY), fmt(q)))
			break
		end
		lastY = h.Position.Y
	end
	return reasons
end

local function outsideBasin(p: Vector3): boolean
	return math.abs(p.X) >= BASIN_X or p.Z <= BASIN_Z[1] or p.Z >= BASIN_Z[2]
end

-- Checks the flight line and timeline of a plan. Returns reasons.
local function checkPath(plan: AirdropPlan.Plan): { string }
	local reasons = {}
	local s: AirdropPath.Sortie = { id = 0, kind = plan.kind, lane = plan.lane, from = plan.from, to = plan.to, speed = plan.speed, t0 = plan.t0, loads = {} }
	local clearance = AirdropPath.clearance(s, PIVOT)
	if clearance < T.MIN_CLEARANCE then
		table.insert(reasons, string.format("clearance %.0f", clearance))
	end
	if plan.altitude < T.ALTITUDE[1] or plan.altitude > T.ALTITUDE[2] then
		table.insert(reasons, string.format("altitude %.0f", plan.altitude))
	end
	if not outsideBasin(plan.from) then
		table.insert(reasons, "entry inside basin " .. fmt(plan.from))
	end
	if not outsideBasin(plan.to) then
		table.insert(reasons, "exit inside basin " .. fmt(plan.to))
	end
	local endT = AirdropPath.endTime(s)
	for _, l in plan.loads do
		if l.releaseT < plan.t0 or l.releaseT > endT then
			table.insert(reasons, "release off the path")
		end
		if not (l.openT > l.releaseT and l.landT > l.openT) then
			table.insert(reasons, "timeline order")
		end
		local drift = AirdropPath.flat(l.openPos, l.landPos) / math.max(l.landT - l.openT, 1e-3)
		if drift > MAX_DRIFT_SPEED then
			table.insert(reasons, string.format("drift %.1f studs/s", drift))
		end
	end
	return reasons
end

local COMBOS = {
	{ "Infantry", "Road" },
	{ "Infantry", "ScrubLeft" },
	{ "Infantry", "ScrubRight" },
	{ "Buggy", "WashLeft" },
	{ "Infantry", "Road" },
	{ "Buggy", "WashRight" },
	{ "Tank", "Road" },
	{ "Infantry", "WashLeft" },
	{ "Infantry", "WashRight" },
}

local function dropZoneCheck(arg: any): (string, any)
	local target = if type(arg) == "table" and arg.samples then arg.samples else 600
	local seed = if type(arg) == "table" and arg.seed then arg.seed else 1
	local rng = Random.new(seed)
	local counts: { [string]: number } = {}
	local examples: { string } = {}
	local samples, sorties, fallbacks, nudged = 0, 0, 0, 0
	local minD, maxD, maxPlanMs, maxAir, minAir = math.huge, 0, 0, 0, math.huge
	local taken: { AirdropZone.Taken } = {}
	local function violation(category: string, text: string)
		counts[category] = (counts[category] or 0) + 1
		if #examples < 12 then
			table.insert(examples, text)
		end
	end
	local i = 0
	while samples < target do
		i += 1
		local combo = COMBOS[(i - 1) % #COMBOS + 1]
		local kind, laneName = combo[1], combo[2]
		-- A busy wave: up to ~4 sorties' landings stay pending together.
		if i % 4 == 1 then
			table.clear(taken)
		end
		local count = rng:NextInteger(1, KINDS[kind].capacity)
		local clock = os.clock()
		local plan = AirdropPlan.sortie(rng, kind, laneName, count, 0, taken)
		maxPlanMs = math.max(maxPlanMs, (os.clock() - clock) * 1000)
		sorties += 1
		if plan.fallback then
			fallbacks += 1
		end
		for _, reason in checkPath(plan) do
			violation("path", string.format("sortie %d %s/%s: %s", sorties, kind, laneName, reason))
		end
		local mine: { AirdropZone.Taken } = {}
		for _, l in plan.loads do
			local p = Vector2.new(l.landPos.X, l.landPos.Z)
			local others = table.clone(taken)
			for _, m in mine do
				table.insert(others, m)
			end
			for _, reason in recheck(kind, laneName, p, l.landPos.Y, others) do
				local category = string.match(reason, "^(%a+)") or reason
				violation(category, string.format("%s/%s %s: %s", kind, laneName, fmt(p), reason))
			end
			table.insert(mine, { p = p, spacing = KINDS[kind].spacing })
			local d = AirdropLanding.distance(p)
			minD, maxD = math.min(minD, d), math.max(maxD, d)
			minAir, maxAir = math.min(minAir, l.landT - l.releaseT), math.max(maxAir, l.landT - l.releaseT)
			if l.nudged > KINDS[kind].drift + 0.5 then
				nudged += 1
			end
			samples += 1
		end
		for _, m in mine do
			table.insert(taken, m)
		end
	end
	local total = 0
	local parts = {}
	for category, n in counts do
		total += n
		table.insert(parts, category .. " " .. n)
	end
	table.sort(parts)
	local lines = {
		string.format(
			"dropZoneCheck: %d landing points from %d sorties (seed %d): %d violations%s",
			samples,
			sorties,
			seed,
			total,
			if total > 0 then " [" .. table.concat(parts, ", ") .. "]" else ""
		),
		string.format(
			"  landing distance %.0f-%.0f studs; air time %.1f-%.1f s; %d nudged beyond drift; %d fallback sorties; max plan %.1f ms",
			minD,
			maxD,
			minAir,
			maxAir,
			nudged,
			fallbacks,
			maxPlanMs
		),
	}
	for _, e in examples do
		table.insert(lines, "  " .. e)
	end
	return table.concat(lines, "\n"), { violations = total, counts = counts, samples = samples, sorties = sorties, fallbacks = fallbacks }
end

local function trigger(arg: any): (boolean, string)
	local drops = Airdrop.active()
	if not drops or drops.closed then
		return false, "no running wave (start one with startWave)"
	end
	local kind = if type(arg) == "table" and arg.kind then arg.kind else "Infantry"
	if not Airdrop.isDropped(kind) then
		return false, kind .. " is not an airdropped kind"
	end
	local lane = if type(arg) == "table" and arg.lane then arg.lane else "Road"
	local count = if type(arg) == "table" and arg.count then arg.count else KINDS[kind].capacity
	drops:group(kind, lane, count, 0)
	local last = Airdrop.stats.lastSortie
	local lines = { string.format("sortie %d: %d x %s on %s", last.id, count, kind, lane) }
	local now = Workspace:GetServerTimeNow()
	for _, l in last.loads do
		table.insert(lines, string.format("  load %d lands %s at %.0f studs in %.1f s", l.loadId, fmt(l.landPos), AirdropLanding.distance(Vector2.new(l.landPos.X, l.landPos.Z)), l.landT - now))
	end
	return true, table.concat(lines, "\n")
end

local COMMANDS: { [string]: (any) -> ...any } = {
	airdrop = trigger,
	dropZoneCheck = dropZoneCheck,
	airdropStats = function(arg: any)
		local stats = table.clone(Airdrop.stats)
		stats.seed = Airdrop.seed()
		stats.pending = if Airdrop.active() then (Airdrop.active() :: any):pendingCount() else 0
		if type(arg) == "table" and arg.reset then
			Airdrop.resetStats()
		end
		return stats
	end,
	airdropSeed = function(arg: any)
		Airdrop.setSeed(if type(arg) == "number" then arg else nil)
		return "airdrop seed " .. tostring(Airdrop.seed())
	end,
}

function AirdropDebug.has(cmd: string): boolean
	return COMMANDS[cmd] ~= nil
end

function AirdropDebug.run(cmd: string, arg: any): ...any
	return COMMANDS[cmd](arg)
end

return AirdropDebug
