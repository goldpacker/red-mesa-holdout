--!strict
-- Runs one wave: announces its groups on schedule and reports completion
-- when every enemy has arrived and died. Stragglers are dismissed after a
-- safety timeout so a wave can never hang.
--
-- Infantry, buggies and tanks arrive by airdrop (server/Airdrop, GAME_SPEC
-- §6.1): a group's `at` is its first touchdown (+/- a small jitter). The
-- group is planned PLAN_LEAD s earlier (or at wave start), its transport
-- timed to meet `at`. Helicopters, jets and the Siege Crawler spawn at
-- `at + i * spacing` as before. The Siege Crawler's escorts (ctx.spawn)
-- are air-dropped too. Loads still in the air count as remaining, so a
-- wave can't end while a drop is pending.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AirdropConfig = require(ReplicatedStorage.Shared.AirdropConfig)
local Config = require(ReplicatedStorage.Shared.Config)
local Airdrop = require(script.Parent.Airdrop)
local Enemies = require(script.Parent.Enemies)
local Types = require(script.Parent.Types)

-- `count` enemies (a whole airdropped group, or one direct spawn), handled
-- at `due` (a drop group is planned ahead of its touchdown `at`).
type SpawnEvent = { due: number, at: number, kind: string, lane: string, count: number, spacing: number, drop: boolean }

export type Director = {
	waveNumber: number,
	elapsed: number,
	pending: { SpawnEvent },
	spawned: number,
	total: number,
	finished: boolean,
	update: (self: Director, dt: number) -> (),
	remaining: (self: Director) -> number,
}

-- When one of these dies its escorts break off: pending drops are dropped.
local BOSS_KINDS = { SiegeCrawler = true }

local WaveDirector = {}
WaveDirector.__index = WaveDirector

local function buildSchedule(wave: any): { SpawnEvent }
	local events: { SpawnEvent } = {}
	for _, group in wave.groups do
		if Airdrop.isDropped(group.kind) then
			local due = math.max(0, group.at - AirdropConfig.PLAN_LEAD)
			table.insert(events, { due = due, at = group.at, kind = group.kind, lane = group.lane, count = group.count, spacing = group.spacing, drop = true })
		else
			for i = 0, group.count - 1 do
				local at = group.at + i * group.spacing
				table.insert(events, { due = at, at = at, kind = group.kind, lane = group.lane, count = 1, spacing = 0, drop = false })
			end
		end
	end
	table.sort(events, function(a, b)
		if a.due ~= b.due then
			return a.due < b.due
		end
		return a.at < b.at
	end)
	return events
end

local function countOf(events: { SpawnEvent }): number
	local n = 0
	for _, e in events do
		n += e.count
	end
	return n
end

function WaveDirector.new(ctx: Types.Context, waveNumber: number): Director
	local wave = Config.Waves[waveNumber]
	assert(wave, "no wave " .. waveNumber)
	local schedule = buildSchedule(wave)
	local crateTimes = table.clone(wave.crates or {})
	table.sort(crateTimes)
	local drops = Airdrop.new(ctx, waveNumber)
	local self = setmetatable({
		crateTimes = crateTimes,
		maxDuration = wave.maxDuration or Config.Timing.WAVE_MAX_DURATION,
		crateBias = wave.crateBias,
		drops = drops,
		bosses = {} :: { Types.Enemy },
		waveNumber = waveNumber,
		elapsed = 0,
		pending = schedule,
		unannounced = countOf(schedule),
		spawned = 0,
		total = countOf(schedule),
		finished = false,
	}, WaveDirector)
	-- Enemies spawned by this director get a context whose spawn() drops
	-- infantry, buggies and tanks from the air (boss escorts).
	local wrapped = table.clone(ctx :: any)
	wrapped.spawn = function(kind: string, lane: string): Types.Enemy?
		if self.finished then
			return nil
		end
		if Airdrop.isDropped(kind) then
			return drops:request(kind, lane)
		end
		return ctx.spawn(kind, lane)
	end
	self.ctx = wrapped :: Types.Context
	return (self :: any) :: Director
end

function WaveDirector.announce(self: any, event: SpawnEvent)
	self.unannounced -= event.count
	self.spawned += event.count
	if event.drop then
		if not Enemies.has(event.kind) then
			warn("[RedMesa] no enemy type " .. event.kind .. "; airdrop skipped")
			return
		end
		local ok, err = pcall(self.drops.group, self.drops, event.kind, event.lane, event.count, event.spacing, event.at)
		if not ok then
			warn("[RedMesa] airdrop failed: " .. tostring(err))
		end
		return
	end
	local ok, enemy = pcall(Enemies.spawn, self.ctx, event.kind, event.lane)
	if not ok then
		warn("[RedMesa] spawn failed: " .. tostring(enemy))
	elseif BOSS_KINDS[event.kind] then
		table.insert(self.bosses, enemy)
	end
end

function WaveDirector.update(self: any, dt: number)
	if self.finished then
		return
	end
	self.elapsed += dt
	-- The boss fell: its escorts still in the air break off with it (before
	-- any of them can land this frame).
	for i = #self.bosses, 1, -1 do
		if self.bosses[i].dead then
			table.remove(self.bosses, i)
			if self.drops:pendingCount() > 0 then
				self.drops:cancel("Dismissed")
			end
		end
	end
	-- At most one airdrop group is planned per frame (spreads the raycasts).
	local plannedDrop = false
	while #self.pending > 0 and self.pending[1].due <= self.elapsed do
		if self.pending[1].drop then
			if plannedDrop then
				break
			end
			plannedDrop = true
		end
		self:announce(table.remove(self.pending, 1) :: SpawnEvent)
	end
	self.drops:update()
	while #self.crateTimes > 0 and self.crateTimes[1] <= self.elapsed do
		table.remove(self.crateTimes, 1)
		self.ctx.dropCrate(self.crateBias)
	end
	Enemies.update(dt)

	if #self.pending == 0 and self.drops:pendingCount() == 0 and Enemies.count() == 0 then
		self.finished = true
	elseif self.elapsed > self.maxDuration then
		warn(string.format("[RedMesa] wave %d timed out; dismissing %d enemies", self.waveNumber, Enemies.count()))
		for _, enemy in Enemies.all() do
			Enemies.remove(enemy)
		end
		table.clear(self.pending)
		self.unannounced = 0
		self.drops:cancel("Timeout")
		self.finished = true
	end
end

-- Enemies still to defeat this wave (alive + in the air + not announced yet).
function WaveDirector.remaining(self: any): number
	return Enemies.count() + self.unannounced + self.drops:pendingCount()
end

return WaveDirector
