--!strict
-- Airdrop runtime (AD-1, GAME_SPEC §6.1): infantry, buggies and tanks
-- arrive by parachute from transports. One `Drops` object per wave
-- director turns wave groups (and Siege Crawler escort requests) into
-- transport sorties planned by AirdropPlan, announces each sortie to
-- clients (GameEvent "AirdropSortie", docs/ARCHITECTURE.md), and at each
-- load's landT spawns the real enemy through
-- Enemies.spawn(ctx, kind, lane, { landAt, loadId }).
--
-- Timing: a wave group's first touchdown is aimed at its `at` (wave
-- seconds, +/- TOUCHDOWN_JITTER); the director plans it up to PLAN_LEAD s
-- ahead, so a sortie can be announced before its transport enters (t0 in
-- the future). Escort requests and debug sorties enter now.
-- Seeds: a new run (Start, Restart, Play Again) rolls a fresh run seed;
-- Retry Wave replays the same drops for that wave.
--
-- Loads in the air do not exist on the server, so nothing can damage,
-- splash or lock them; clients draw them from the sortie timeline. Pending
-- loads count toward the wave's remaining enemies. The server does no
-- per-frame work per airborne load: a queue sorted by landT is checked
-- from the front each frame.
--
-- "AirdropClear" {reason} tells clients to drop pending descents when the
-- wave ends or is abandoned (phase leaves Wave: WaveClear, Defeat,
-- Restart/Retry/Play Again via WaveIntro), on the wave timeout, and when
-- the boss dies ("Dismissed").

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local AirdropConfig = require(ReplicatedStorage.Shared.AirdropConfig)
local AirdropPlan = require(script.Parent.AirdropPlan)
local AirdropZone = require(script.Parent.AirdropZone)
local Enemies = require(script.Parent.Enemies)
local Types = require(script.Parent.Types)

local Airdrop = {}

local KINDS = AirdropConfig.KINDS
local T = AirdropConfig.Transport

-- Timing record of one wave group (QA: intended vs measured touchdown).
type GroupRecord = {
	wave: number,
	kind: string,
	lane: string,
	at: number?, -- wave seconds asked for (nil = entered now)
	target: number?, -- wave seconds aimed at (at + jitter)
	planned: number, -- wave seconds of the planned first touchdown
	landed: number?, -- wave seconds the first load actually landed
	late: number,
}

type Load = {
	loadId: number,
	group: GroupRecord?,
	kind: string,
	lane: string,
	planned: boolean,
	sortie: number,
	releaseT: number,
	openT: number,
	landT: number,
	openPos: Vector3,
	landPos: Vector3,
	face: Vector3,
	enemy: Types.Enemy?,
	cancelled: boolean,
}

type Batch = { kind: string, lane: string, loads: { Load }, flushAt: number }

export type Drops = {
	wave: number,
	closed: boolean,
	group: (self: Drops, kind: string, lane: string, count: number, spacing: number?, landAt: number?) -> (),
	request: (self: Drops, kind: string, lane: string) -> Types.Enemy?,
	update: (self: Drops) -> (),
	pendingCount: (self: Drops) -> number,
	cancel: (self: Drops, reason: string) -> (),
}

-- Counters for QA (RedMesaDebug "airdropStats"); reset with resetStats.
local function freshStats()
	return {
		sorties = 0,
		announced = {} :: { [string]: number },
		landed = {} :: { [string]: number },
		cancelled = 0,
		spawnFailed = 0,
		fallbacks = 0,
		nudged = 0,
		minLand = math.huge,
		maxLand = 0,
		maxPlanMs = 0,
		late = 0,
		maxLate = 0,
		groups = {} :: { GroupRecord },
		-- One row per transport (QA pacing, AD-3): wave seconds of its entry,
		-- first canopy opening, first and last touchdown.
		sortieLog = {} :: { any },
		lastSortie = nil :: any,
	}
end
Airdrop.stats = freshStats()

function Airdrop.resetStats()
	Airdrop.stats = freshStats()
end

local seedSource = Random.new()
local fixedSeed: number? = nil
local runSeed: number? = nil
local nextSortieId = 0
local nextLoadId = 0
local active: any = nil

local function now(): number
	return Workspace:GetServerTimeNow()
end

function Airdrop.isDropped(kind: string): boolean
	return KINDS[kind] ~= nil
end

-- Studio QA: pin the run seed (nil = a fresh seed every new run).
function Airdrop.setSeed(seed: number?)
	fixedSeed = seed
	runSeed = seed
end

function Airdrop.seed(): number?
	return runSeed
end

-- The drops object of the current (or last) wave director.
function Airdrop.active(): Drops?
	return active
end

-- Stand-in returned to ctx.spawn callers (Siege Crawler escorts) for a load
-- still in the air: reads through to the real enemy once it has landed; a
-- cancelled load reads as dead with no model, so escort lists prune it.
local AIRBORNE_MODEL = { Parent = Workspace }
local NO_MODEL = { Parent = nil }

local function proxy(load: Load): Types.Enemy
	return setmetatable({}, {
		__index = function(_, key)
			local enemy = load.enemy
			if enemy then
				return (enemy :: any)[key]
			elseif key == "dead" then
				return load.cancelled
			elseif key == "model" then
				return if load.cancelled then NO_MODEL else AIRBORNE_MODEL
			elseif key == "kind" then
				return load.kind
			end
			return nil
		end,
	}) :: any
end

local Drops = {}
Drops.__index = Drops

-- True from a new run (Start, Restart, Play Again) until its first wave's
-- drops are seeded; Retry Wave leaves it false, so the retried wave replays.
local newRunPending = true

-- `centres` (a wave's `dropCentre`, AD-4): per-kind stick-centre bands
-- that replace AirdropConfig.KINDS[kind].centre for every drop of this wave,
-- its groups and the Siege Crawler's escorts alike.
function Airdrop.new(ctx: Types.Context, waveNumber: number, centres: { [string]: { number } }?): Drops
	if newRunPending or runSeed == nil then
		runSeed = fixedSeed or seedSource:NextInteger(1, 2 ^ 30)
		newRunPending = false
	end
	local self = setmetatable({
		ctx = ctx,
		wave = waveNumber,
		centres = centres or {},
		startT = now(),
		rng = Random.new((runSeed :: number) + waveNumber * 7919),
		queue = {} :: { Load },
		batches = {} :: { [string]: Batch },
		batched = 0,
		closed = false,
	}, Drops)
	active = self
	return (self :: any) :: Drops
end

local function newLoad(kind: string, lane: string, group: GroupRecord?): Load
	nextLoadId += 1
	return {
		loadId = nextLoadId,
		group = group,
		kind = kind,
		lane = lane,
		planned = false,
		sortie = 0,
		releaseT = math.huge,
		openT = math.huge,
		landT = math.huge,
		openPos = Vector3.zero,
		landPos = Vector3.zero,
		face = Vector3.new(0, 0, 1),
		enemy = nil,
		cancelled = false,
	}
end

local function insertSorted(queue: { Load }, load: Load)
	local i = #queue + 1
	while i > 1 and queue[i - 1].landT > load.landT do
		i -= 1
	end
	table.insert(queue, i, load)
end

-- Landing points still pending, kept clear by the sampler.
function Drops.taken(self: any): { AirdropZone.Taken }
	local list = {}
	for _, load in self.queue do
		table.insert(list, { p = Vector2.new(load.landPos.X, load.landPos.Z), spacing = KINDS[load.kind].spacing })
	end
	return list
end

function Drops.announce(self: any, plan: AirdropPlan.Plan, loads: { Load })
	nextSortieId += 1
	local stats = Airdrop.stats
	stats.sorties += 1
	if plan.fallback then
		stats.fallbacks += 1
	end
	local payload = {}
	for k, planned in plan.loads do
		local load = loads[k]
		load.planned = true
		load.sortie = nextSortieId
		load.releaseT = planned.releaseT
		load.openT = planned.openT
		load.landT = planned.landT
		load.openPos = planned.openPos
		load.landPos = planned.landPos
		load.face = planned.face
		insertSorted(self.queue, load)
		stats.announced[load.kind] = (stats.announced[load.kind] or 0) + 1
		if planned.nudged > (KINDS[load.kind].drift + 0.5) then
			stats.nudged += 1
		end
		table.insert(payload, {
			loadId = load.loadId,
			kind = load.kind,
			lane = load.lane,
			releaseT = load.releaseT,
			openT = load.openT,
			landT = load.landT,
			openPos = load.openPos,
			landPos = load.landPos,
			face = load.face,
		})
	end
	local sortie = {
		id = nextSortieId,
		kind = plan.kind,
		lane = plan.lane,
		from = plan.from,
		to = plan.to,
		speed = plan.speed,
		t0 = plan.t0,
		loads = payload,
	}
	stats.lastSortie = sortie
	local firstOpen, firstLand, lastLand = math.huge, math.huge, 0
	for _, load in payload do
		firstOpen = math.min(firstOpen, load.openT)
		firstLand = math.min(firstLand, load.landT)
		lastLand = math.max(lastLand, load.landT)
	end
	table.insert(stats.sortieLog, {
		wave = self.wave,
		kind = plan.kind,
		lane = plan.lane,
		n = #payload,
		t0 = plan.t0 - self.startT,
		open = firstOpen - self.startT,
		land = firstLand - self.startT,
		lastLand = lastLand - self.startT,
	})
	self.ctx.emit("AirdropSortie", sortie)
end

-- Plans and announces transports for `loads` (split by capacity). The
-- first transport follows `timing`; extra ones fly in formation behind it,
-- entering `trail` s apart. Returns the first plan.
function Drops.launch(self: any, kind: string, lane: string, loads: { Load }, timing: AirdropPlan.Timing, trail: number): AirdropPlan.Plan?
	local capacity = KINDS[kind].capacity
	local leader: AirdropPlan.Plan? = nil
	local slot = 0
	local i = 1
	while i <= #loads do
		local n = math.min(capacity, #loads - i + 1)
		local chunk = table.move(loads, i, i + n - 1, 1, {})
		local follow: AirdropPlan.Follow? = nil
		local slotTiming = timing
		if leader then
			follow = { heading = leader.heading, altitude = leader.altitude, centre = leader.centre, slot = slot }
			slotTiming = { t0 = leader.t0 + slot * trail }
		end
		local clock = os.clock()
		local plan = AirdropPlan.sortie(self.rng, kind, lane, n, slotTiming, self:taken(), follow, self.centres[kind])
		Airdrop.stats.maxPlanMs = math.max(Airdrop.stats.maxPlanMs, (os.clock() - clock) * 1000)
		leader = leader or plan
		self:announce(plan, chunk)
		slot += 1
		i += n
	end
	return leader
end

-- A wave group: `count` loads of `kind` for `lane`. With `landAt` (wave
-- seconds) the first touchdown is aimed there (+/- TOUCHDOWN_JITTER);
-- without it the transports enter now.
function Drops.group(self: any, kind: string, lane: string, count: number, spacing: number?, landAt: number?)
	if self.closed or count <= 0 then
		return
	end
	lane = AirdropPlan.resolveLane(kind, lane)
	local record: GroupRecord = { wave = self.wave, kind = kind, lane = lane, at = landAt, target = nil, planned = 0, landed = nil, late = 0 }
	local loads = {}
	for _ = 1, count do
		table.insert(loads, newLoad(kind, lane, record))
	end
	local timing: AirdropPlan.Timing = { t0 = now() }
	if landAt then
		local jitter = AirdropConfig.TOUCHDOWN_JITTER
		record.target = landAt + self.rng:NextNumber(-jitter, jitter)
		timing = { land = self.startT + (record.target :: number), earliest = now() }
	end
	local plan = self:launch(kind, lane, loads, timing, math.max(spacing or 0, T.FORMATION_TRAIL))
	if plan then
		local stats = Airdrop.stats
		record.planned = plan.firstLand - self.startT
		record.late = plan.late
		if plan.late > 0.05 then
			stats.late += 1
			stats.maxLate = math.max(stats.maxLate, plan.late)
		end
		table.insert(stats.groups, record)
	end
end

function Drops.flush(self: any, key: string)
	local batch = self.batches[key]
	if not batch then
		return
	end
	self.batches[key] = nil
	self.batched -= #batch.loads
	local ok, err = pcall(self.launch, self, batch.kind, batch.lane, batch.loads, { t0 = now() }, T.FORMATION_TRAIL)
	if not ok then
		-- Unplanned loads never land: drop them so the wave can still end.
		for _, load in batch.loads do
			load.cancelled = true
		end
		self:dequeue(batch.loads)
		warn("[RedMesa] escort airdrop failed: " .. tostring(err))
	end
end

-- Removes `loads` from the landing queue (after a failed launch).
function Drops.dequeue(self: any, loads: { Load })
	local drop = {}
	for _, load in loads do
		drop[load] = true
	end
	for i = #self.queue, 1, -1 do
		if drop[self.queue[i]] then
			table.remove(self.queue, i)
		end
	end
end

-- ctx.spawn for an airdropped kind (Siege Crawler escorts): requests on
-- the same lane within ESCORT_BATCH s share a transport. Returns a
-- stand-in enemy that becomes the real one when it lands.
function Drops.request(self: any, kind: string, lane: string): Types.Enemy?
	if self.closed then
		return nil
	end
	lane = AirdropPlan.resolveLane(kind, lane)
	local key = kind .. "|" .. lane
	local batch = self.batches[key]
	if not batch then
		batch = { kind = kind, lane = lane, loads = {}, flushAt = now() + AirdropConfig.ESCORT_BATCH }
		self.batches[key] = batch
	end
	local load = newLoad(kind, lane)
	table.insert(batch.loads, load)
	self.batched += 1
	if #batch.loads >= KINDS[kind].capacity then
		self:flush(key)
	end
	return proxy(load)
end

function Drops.land(self: any, load: Load)
	local ok, enemy = pcall(Enemies.spawn, self.ctx, load.kind, load.lane, { landAt = load.landPos, loadId = load.loadId })
	local stats = Airdrop.stats
	if ok then
		load.enemy = enemy
		local record = load.group
		if record and not record.landed then
			record.landed = now() - self.startT
		end
		stats.landed[load.kind] = (stats.landed[load.kind] or 0) + 1
		local d = Vector2.new(load.landPos.X, load.landPos.Z).Magnitude
		stats.minLand = math.min(stats.minLand, d)
		stats.maxLand = math.max(stats.maxLand, d)
	else
		load.cancelled = true
		stats.spawnFailed += 1
		warn(string.format("[RedMesa] airdrop landing of %s failed: %s", load.kind, tostring(enemy)))
	end
end

-- Once per frame from the wave director: flushes due escort batches and
-- lands every load whose landT has passed.
function Drops.update(self: any)
	if self.closed then
		return
	end
	local t = now()
	for key, batch in self.batches do
		if t >= batch.flushAt then
			self:flush(key)
		end
	end
	local queue = self.queue
	while queue[1] and queue[1].landT <= t do
		self:land(table.remove(queue, 1) :: Load)
	end
end

-- Loads announced or requested but not landed yet.
function Drops.pendingCount(self: any): number
	return #self.queue + self.batched
end

-- Drops every pending load and tells clients. "Dismissed" (the boss died)
-- keeps the object open; any other reason closes it for good.
function Drops.cancel(self: any, reason: string)
	local n = 0
	for _, load in self.queue do
		load.cancelled = true
		n += 1
	end
	for _, batch in self.batches do
		for _, load in batch.loads do
			load.cancelled = true
			n += 1
		end
	end
	table.clear(self.queue)
	table.clear(self.batches)
	self.batched = 0
	Airdrop.stats.cancelled += n
	if reason ~= "Dismissed" then
		self.closed = true
	end
	self.ctx.emit("AirdropClear", { reason = reason, cancelled = n })
end

-- Whenever the phase leaves Wave (wave clear, defeat, debug staging),
-- pending drops are dropped; Retry/Restart/Play Again always follow a
-- Defeat or Victory, so they start clean.
do
	local remotes = ReplicatedStorage:WaitForChild("Remotes")
	local state = ReplicatedStorage:WaitForChild("GameState")
	-- Mirrors GameController's guards: which request starts a new run.
	-- WaveIntro covers GameController's handler having run first.
	for name, phases in { StartGame = { Title = true, WaveIntro = true }, Restart = { Defeat = true, Victory = true, WaveIntro = true } } do
		local remote = remotes:WaitForChild(name, 2)
		if remote and remote:IsA("RemoteEvent") then
			remote.OnServerEvent:Connect(function()
				if phases[state:GetAttribute("Phase")] then
					newRunPending = true
				end
			end)
		end
	end
	local lastPhase = state:GetAttribute("Phase")
	state:GetAttributeChangedSignal("Phase"):Connect(function()
		local phase = state:GetAttribute("Phase")
		if lastPhase == "Wave" and phase ~= "Wave" and active then
			active:cancel(tostring(phase))
		end
		lastPhase = phase
	end)
end

return Airdrop
