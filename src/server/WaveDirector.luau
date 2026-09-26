--!strict
-- Runs one wave: spawns its groups on schedule and reports completion when
-- every scheduled enemy has spawned and died. Stragglers are dismissed after
-- a safety timeout so a wave can never hang.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Enemies = require(script.Parent.Enemies)
local Types = require(script.Parent.Types)

type SpawnEvent = { at: number, kind: string, lane: string }

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

local WaveDirector = {}
WaveDirector.__index = WaveDirector

local function buildSchedule(wave: any): { SpawnEvent }
	local events: { SpawnEvent } = {}
	for _, group in wave.groups do
		for i = 0, group.count - 1 do
			table.insert(events, { at = group.at + i * group.spacing, kind = group.kind, lane = group.lane })
		end
	end
	table.sort(events, function(a, b)
		return a.at < b.at
	end)
	return events
end

function WaveDirector.new(ctx: Types.Context, waveNumber: number): Director
	local wave = Config.Waves[waveNumber]
	assert(wave, "no wave " .. waveNumber)
	local schedule = buildSchedule(wave)
	local self = setmetatable({
		ctx = ctx,
		waveNumber = waveNumber,
		elapsed = 0,
		pending = schedule,
		spawned = 0,
		total = #schedule,
		finished = false,
	}, WaveDirector)
	return (self :: any) :: Director
end

function WaveDirector.update(self: any, dt: number)
	if self.finished then
		return
	end
	self.elapsed += dt
	while #self.pending > 0 and self.pending[1].at <= self.elapsed do
		local event = table.remove(self.pending, 1) :: SpawnEvent
		local ok, err = pcall(Enemies.spawn, self.ctx, event.kind, event.lane)
		if not ok then
			warn("[RedMesa] spawn failed: " .. tostring(err))
		end
		self.spawned += 1
	end
	Enemies.update(dt)

	if #self.pending == 0 and Enemies.count() == 0 then
		self.finished = true
	elseif self.elapsed > Config.Timing.WAVE_MAX_DURATION then
		warn(string.format("[RedMesa] wave %d timed out; dismissing %d enemies", self.waveNumber, Enemies.count()))
		for _, enemy in Enemies.all() do
			Enemies.remove(enemy)
		end
		table.clear(self.pending)
		self.finished = true
	end
end

-- Enemies still to defeat this wave (alive + not yet spawned).
function WaveDirector.remaining(self: any): number
	return Enemies.count() + #self.pending
end

return WaveDirector
