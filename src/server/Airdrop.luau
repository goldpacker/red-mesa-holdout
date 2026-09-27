--!strict
-- Airdrop runtime (AD-1, GAME_SPEC §6.1): infantry, buggies and tanks
-- arrive by parachute from transports. One `Drops` object per wave
-- director turns wave groups (and Siege Crawler escort requests) into
-- transport sorties planned by AirdropPlan, announces each sortie to
-- clients (GameEvent "AirdropSortie", docs/ARCHITECTURE.md), and at each
-- load's landT spawns the real enemy through
-- Enemies.spawn(ctx, kind, lane, { landAt, loadId }).
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

type Load = {
	loadId: number,
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
	group: (self: Drops, kind: string, lane: string, count: number, spacing: number?) -> (),
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

function Airdrop.new(ctx: Types.Context, waveNumber: number): Drops
	if waveNumber == 1 or runSeed == nil then
		runSeed = fixedSeed or seedSource:NextInteger(1, 2 ^ 30)
	end
	local self = setmetatable({
		ctx = ctx,
		wave = waveNumber,
		rng = Random.new((runSeed :: number) + waveNumber * 7919),
		queue = {} :: { Load },
		batches = {} :: { [string]: Batch },
		batched = 0,
		closed = false,
	}, Drops)
	active = self
	return (self :: any) :: Drops
end

local function newLoad(kind: string, lane: string): Load
	nextLoadId += 1
	return {
		loadId = nextLoadId,
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
	self.ctx.emit("AirdropSortie", sortie)
end

-- Plans and announces transports for `loads` (split by capacity; extra
-- transports fly in formation behind the first, `trail` s apart).
function Drops.launch(self: any, kind: string, lane: string, loads: { Load }, t0: number, trail: number)
	local capacity = KINDS[kind].capacity
	local leader: AirdropPlan.Plan? = nil
	local slot = 0
	local i = 1
	while i <= #loads do
		local n = math.min(capacity, #loads - i + 1)
		local chunk = table.move(loads, i, i + n - 1, 1, {})
		local follow: AirdropPlan.Follow? = nil
		if leader then
			follow = { heading = leader.heading, altitude = leader.altitude, centre = leader.centre, slot = slot }
		end
		local clock = os.clock()
		local plan = AirdropPlan.sortie(self.rng, kind, lane, n, t0 + slot * trail, self:taken(), follow)
		Airdrop.stats.maxPlanMs = math.max(Airdrop.stats.maxPlanMs, (os.clock() - clock) * 1000)
		leader = leader or plan
		self:announce(plan, chunk)
		slot += 1
		i += n
	end
end

-- A wave group: `count` loads of `kind` for `lane`, transports entering now.
function Drops.group(self: any, kind: string, lane: string, count: number, spacing: number?)
	if self.closed or count <= 0 then
		return
	end
	local loads = {}
	for _ = 1, count do
		table.insert(loads, newLoad(kind, lane))
	end
	self:launch(kind, lane, loads, now(), math.max(spacing or 0, T.FORMATION_TRAIL))
end

function Drops.flush(self: any, key: string)
	local batch = self.batches[key]
	if not batch then
		return
	end
	self.batches[key] = nil
	self.batched -= #batch.loads
	self:launch(batch.kind, batch.lane, batch.loads, now(), T.FORMATION_TRAIL)
end

-- ctx.spawn for an airdropped kind (Siege Crawler escorts): requests on
-- the same lane within ESCORT_BATCH s share a transport. Returns a
-- stand-in enemy that becomes the real one when it lands.
function Drops.request(self: any, kind: string, lane: string): Types.Enemy?
	if self.closed then
		return nil
	end
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

-- Whenever the phase leaves Wave (wave clear, defeat, restart, retry, play
-- again, debug staging), pending drops are dropped.
do
	local state = ReplicatedStorage:WaitForChild("GameState")
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
