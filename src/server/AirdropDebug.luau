--!strict
-- Studio-only airdrop QA commands behind ServerStorage.RedMesaDebug
-- (GameController.installDebugHooks). See tools/qa/BEAUTY.md §8.
--   airdrop        { kind = "Infantry", count = 8, lane = "Road", at = s? }:
--                  fly a sortie in the running wave (counts toward it);
--                  with `at` (wave seconds) the first touchdown is aimed there
--   dropZoneCheck  { samples = 600, seed = 1, wave = n? }: plans many sorties with the
--                  gameplay planner (touchdown-timed and enter-now, single
--                  transports and formations) and re-checks every landing
--                  point, walk to the lane and flight line independently:
--                  denser rule sampling plus rays against the real geometry
--                  (terrain, landscape meshes, rock kit); with `wave`, the
--                  planner uses that wave's `dropCentre` bands (AD-4)
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
-- A visible surface this far above the terrain is an obstacle (strips and
-- decals lie ~0.3 above it; pebbles and scrub are non-colliding clutter).
local SURFACE_TOLERANCE = 0.1

local OPEN: { [Enum.Material]: boolean } = {}
for _, name in GROUND.MATERIALS do
	OPEN[(Enum.Material :: any)[name]] = true
end

local terrainParams = RaycastParams.new()
terrainParams.FilterType = Enum.RaycastFilterType.Include
terrainParams.FilterDescendantsInstances = { Workspace.Terrain }

-- Real solid geometry: terrain, landscape meshes and the rock kit.
local solidParams = RaycastParams.new()
solidParams.FilterType = Enum.RaycastFilterType.Include

-- Everything visible (for turret line of sight), minus enemies and effects.
local sightParams = RaycastParams.new()
sightParams.FilterType = Enum.RaycastFilterType.Include

local function probe(x: number, z: number): RaycastResult?
	return Workspace:Raycast(Vector3.new(x, 500, z), Vector3.new(0, -620, 0), terrainParams)
end

local function solid(x: number, z: number): RaycastResult?
	return Workspace:Raycast(Vector3.new(x, 500, z), Vector3.new(0, -620, 0), solidParams)
end

local function fmt(p: Vector3 | Vector2): string
	if typeof(p) == "Vector3" then
		return string.format("(%d,%d,%d)", p.X, p.Y, p.Z)
	end
	return string.format("(%d,%d)", (p :: Vector2).X, (p :: Vector2).Y)
end

-- Runs `fn` with the landscape, rock kit and other visible world parts
-- queryable (restored after), and the ray filters pointed at them.
local function withGeometry<R>(fn: () -> R): R
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local solidRoots: { Instance } = { Workspace.Terrain }
	local sightRoots: { Instance } = { Workspace.Terrain }
	local toggled: { BasePart } = {}
	if battlefield then
		for _, name in { "Landscape", "RockKit" } do
			local f = battlefield:FindFirstChild(name)
			if f then
				table.insert(solidRoots, f)
			end
		end
		local emplacement = battlefield:FindFirstChild("Emplacement")
		for _, child in battlefield:GetChildren() do
			if child ~= emplacement then
				table.insert(sightRoots, child)
			end
		end
		for _, d in battlefield:GetDescendants() do
			if d:IsA("BasePart") and not d.CanQuery and d.Transparency < 0.9 then
				d.CanQuery = true
				table.insert(toggled, d)
			end
		end
	end
	solidParams.FilterDescendantsInstances = solidRoots
	sightParams.FilterDescendantsInstances = sightRoots
	local ok, result = pcall(fn)
	for _, p in toggled do
		p.CanQuery = false
	end
	if not ok then
		error(result, 0)
	end
	return result
end

-- The first solid surface under (x, z) must be terrain, at terrain height.
local function solidReason(q: Vector2, terrainY: number): string?
	local hit = solid(q.X, q.Y)
	if hit and hit.Instance ~= Workspace.Terrain and hit.Position.Y > terrainY + SURFACE_TOLERANCE then
		return (hit.Instance :: Instance):GetFullName()
	end
	return nil
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
	-- Footprint: denser than the planner and at other angles. Margin ring
	-- (open floor, and nothing solid above the terrain), rim and half-rim
	-- slope rings, and the centre.
	local tanMax = math.tan(math.rad(GROUND.MAX_SLOPE))
	-- 1.5x the planner's ring density, at offset angles.
	local rings = { { def.footprint * 1.25, false }, { def.footprint, true }, { def.footprint * 0.5, true }, { 0, false } }
	for _, ring in rings do
		local r, slope = ring[1], ring[2]
		local n = if r > 0 then math.max(18, math.ceil(2 * math.pi * r / GROUND.RING_SPACING * 1.5)) else 1
		local bad: string? = nil
		for k = 0, n - 1 do
			local a = k / n * math.pi * 2 + 0.13
			local q = p + Vector2.new(math.cos(a), math.sin(a)) * r
			local h = probe(q.X, q.Y)
			if not h or not OPEN[h.Material] or h.Position.Y < GROUND.FLOOR_Y[1] or h.Position.Y > GROUND.FLOOR_Y[2] then
				bad = "footprint " .. (if h then h.Material.Name else "none")
			elseif slope and math.abs(h.Position.Y - hit.Position.Y) / r > tanMax then
				bad = string.format("slope %.0f deg", math.deg(math.atan(math.abs(h.Position.Y - hit.Position.Y) / r)))
			else
				local blocker = solidReason(q, h.Position.Y)
				if blocker then
					bad = "solid " .. blocker
				end
			end
			if bad then
				table.insert(reasons, bad)
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
	-- Reach: twice as dense as the planner (and offset from its samples),
	-- to the join waypoint (ahead of the landing): on the floor, no rise
	-- over any planner-length window above the planner's limit, nothing
	-- solid in the way.
	local lane = Config.Lanes[laneName]
	local goal = lane[AirdropLanding.joinIndex(lane, p)]
	if AirdropLanding.distance(goal) >= d then
		table.insert(reasons, "reach: join waypoint not ahead")
	end
	local delta = goal - p
	local n = math.max(2, math.ceil(delta.Magnitude / (GROUND.REACH_STEP / 2)))
	local stepLen = delta.Magnitude / n
	local ys = { hit.Position.Y }
	for k = 1, n do
		local q = p + delta * (k / n)
		local h = probe(q.X, q.Y)
		if not h or h.Position.Y > GROUND.FLOOR_Y[2] or h.Position.Y < GROUND.FLOOR_Y[1] or not OPEN[h.Material] then
			table.insert(reasons, "reach: off the floor (" .. (if h then h.Material.Name else "none") .. ") at " .. fmt(q))
			break
		end
		ys[k + 1] = h.Position.Y
		-- Rise over the planner's step length (two of these samples).
		local back = ys[math.max(1, k - 1)]
		local window = stepLen * math.min(2, k)
		if math.abs(h.Position.Y - back) > GROUND.REACH_MAX_STEP * window / GROUND.REACH_STEP + 1e-3 then
			table.insert(reasons, string.format("reach: rise %.2f over %.2f at %s", math.abs(h.Position.Y - back), window, fmt(q)))
			break
		end
		local blocker = solidReason(q, h.Position.Y)
		if blocker then
			table.insert(reasons, "reach: solid " .. blocker .. " at " .. fmt(q))
			break
		end
	end
	return reasons
end

local sightExamples: { string } = {}

-- Turret sight line to a landed soldier's hip (information only: a load
-- may land in dead ground and walk into view). Returns nil when visible,
-- else what blocks it (the Battlefield child, or "Terrain").
local function blockedBy(landPos: Vector3): string?
	local target = landPos + Vector3.new(0, 3, 0)
	local origin = PIVOT + (target - PIVOT).Unit * Config.MUZZLE_OFFSET
	local delta = target - origin
	local hit = Workspace:Raycast(origin, delta - delta.Unit * 0.25, sightParams)
	if not hit then
		return nil
	end
	local inst: Instance = hit.Instance
	if #sightExamples < 3 then
		table.insert(sightExamples, string.format("%s: %s at %s", fmt(landPos), inst:GetFullName(), fmt(hit.Position)))
	end
	if inst == Workspace.Terrain then
		return "Terrain"
	end
	local battlefield = Workspace:FindFirstChild("Battlefield")
	while inst.Parent and inst.Parent ~= battlefield do
		inst = inst.Parent
	end
	return inst.Name
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
	if plan.altitude < T.ALTITUDE[1] - 1e-6 or plan.altitude > T.ALTITUDE[2] + 1e-6 then
		table.insert(reasons, string.format("altitude %.0f", plan.altitude))
	end
	if not outsideBasin(plan.from) then
		table.insert(reasons, "entry inside basin " .. fmt(plan.from))
	end
	if not outsideBasin(plan.to) then
		table.insert(reasons, "exit inside basin " .. fmt(plan.to))
	end
	local endT = AirdropPath.endTime(s)
	local first = math.huge
	for _, l in plan.loads do
		first = math.min(first, l.landT)
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
	if math.abs(first - plan.firstLand) > 1e-6 then
		table.insert(reasons, "firstLand mismatch")
	end
	return reasons
end

-- kind, lane, count (> capacity = a formation).
local COMBOS = {
	{ "Infantry", "Road", 8 },
	{ "Infantry", "ScrubLeft", 6 },
	{ "Infantry", "ScrubRight", 5 },
	{ "Buggy", "WashLeft", 2 },
	{ "Infantry", "Road", 12 },
	{ "Buggy", "WashRight", 3 },
	{ "Tank", "Road", 1 },
	{ "Infantry", "WashLeft", 4 },
	{ "Tank", "Road", 2 },
	{ "Infantry", "WashRight", 8 },
}

local function dropZoneCheck(arg: any): (string, any)
	local target = if type(arg) == "table" and arg.samples then arg.samples else 600
	local seed = if type(arg) == "table" and arg.seed then arg.seed else 1
	-- `wave`: plan with that wave's `dropCentre` bands (AD-4), as its drops do.
	local wave = if type(arg) == "table" and arg.wave then Config.Waves[arg.wave] else nil
	local centres: { [string]: { number } } = if wave and wave.dropCentre then wave.dropCentre else {}
	local rng = Random.new(seed)
	local counts: { [string]: number } = {}
	local examples: { string } = {}
	local samples, sorties, formations, fallbacks, nudged, hidden = 0, 0, 0, 0, 0, 0
	local timed, late, maxTimingError = 0, 0, 0
	local minD, maxD, maxPlanMs, maxAir, minAir = math.huge, 0, 0, 0, math.huge
	local taken: { AirdropZone.Taken } = {}
	local blockers: { [string]: number } = {}
	local function violation(category: string, text: string)
		counts[category] = (counts[category] or 0) + 1
		if #examples < 12 then
			table.insert(examples, text)
		end
	end
	local rocks = #AirdropZone.rocks()
	withGeometry(function()
		local i = 0
		while samples < target do
			i += 1
			local combo = COMBOS[(i - 1) % #COMBOS + 1]
			local kind, laneName, total = combo[1], combo[2], combo[3]
			-- A busy wave: up to ~4 groups' landings stay pending together.
			if i % 4 == 1 then
				table.clear(taken)
			end
			-- Every other group is touchdown-timed with a lead the table's
			-- values give (30-45 s); the rest enter now.
			local timing: AirdropPlan.Timing = { t0 = 0 }
			local aim: number? = nil
			if i % 2 == 0 then
				aim = rng:NextNumber(30, AirdropConfig.PLAN_LEAD)
				timing = { land = aim, earliest = 0 }
			end
			local capacity = KINDS[kind].capacity
			local leader: AirdropPlan.Plan? = nil
			local slot, left = 0, total
			while left > 0 do
				local n = math.min(capacity, left)
				local follow: AirdropPlan.Follow? = nil
				local slotTiming = timing
				if leader then
					follow = { heading = leader.heading, altitude = leader.altitude, centre = leader.centre, slot = slot }
					slotTiming = { t0 = leader.t0 + slot * T.FORMATION_TRAIL }
					formations += 1
				end
				local clock = os.clock()
				local plan = AirdropPlan.sortie(rng, kind, laneName, n, slotTiming, taken, follow, centres[kind])
				maxPlanMs = math.max(maxPlanMs, (os.clock() - clock) * 1000)
				sorties += 1
				if plan.fallback then
					fallbacks += 1
				end
				if not leader and aim then
					timed += 1
					if plan.late > 0.05 then
						late += 1
						violation("timing", string.format("sortie %d %s/%s: lands %.2f s late for a %.1f s lead", sorties, kind, laneName, plan.late, aim))
					else
						maxTimingError = math.max(maxTimingError, math.abs(plan.firstLand - aim))
					end
				end
				leader = leader or plan
				for _, reason in checkPath(plan) do
					violation("path", string.format("sortie %d %s/%s: %s", sorties, kind, laneName, reason))
				end
				for _, l in plan.loads do
					local p = Vector2.new(l.landPos.X, l.landPos.Z)
					for _, reason in recheck(kind, laneName, p, l.landPos.Y, taken) do
						local category = string.match(reason, "^(%a+)") or reason
						violation(category, string.format("%s/%s %s: %s", kind, laneName, fmt(p), reason))
					end
					local blocker = blockedBy(l.landPos)
					if blocker then
						hidden += 1
						blockers[blocker] = (blockers[blocker] or 0) + 1
					end
					table.insert(taken, { p = p, spacing = KINDS[kind].spacing })
					local d = AirdropLanding.distance(p)
					minD, maxD = math.min(minD, d), math.max(maxD, d)
					minAir, maxAir = math.min(minAir, l.landT - l.releaseT), math.max(maxAir, l.landT - l.releaseT)
					if l.nudged > KINDS[kind].drift + 0.5 then
						nudged += 1
					end
					samples += 1
				end
				slot += 1
				left -= n
			end
		end
	end)
	local totalViolations = 0
	local parts = {}
	for category, n in counts do
		totalViolations += n
		table.insert(parts, category .. " " .. n)
	end
	table.sort(parts)
	local lines = {
		string.format(
			"dropZoneCheck: %d landing points from %d sorties (%d formation followers), seed %d, %d rocks: %d violations%s",
			samples,
			sorties,
			formations,
			seed,
			rocks,
			totalViolations,
			if totalViolations > 0 then " [" .. table.concat(parts, ", ") .. "]" else ""
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
		string.format("  touchdown-timed groups: %d, late %d, max on-time error %.4f s", timed, late, maxTimingError),
		string.format("  info: %d/%d landings out of the turret's sight at hip height (they walk into view)%s", hidden, samples, (function()
			local parts = {}
			for name, n in blockers do
				table.insert(parts, name .. " " .. n)
			end
			table.sort(parts)
			return if #parts > 0 then "; blocked by " .. table.concat(parts, ", ") else ""
		end)()),
	}
	for _, e in examples do
		table.insert(lines, "  " .. e)
	end
	for _, e in sightExamples do
		table.insert(lines, "  sight: " .. e)
	end
	table.clear(sightExamples)
	return table.concat(lines, "\n"), { violations = totalViolations, counts = counts, samples = samples, sorties = sorties, fallbacks = fallbacks, late = late, hidden = hidden }
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
	local at = if type(arg) == "table" then arg.at else nil
	drops:group(kind, lane, count, 0, at)
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
