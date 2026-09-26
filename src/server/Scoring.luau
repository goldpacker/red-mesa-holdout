--!strict
-- Score, combo multiplier and run statistics.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)

export type Stats = {
	score: number,
	kills: { [string]: number },
	shots: number,
	hits: number,
	bestCombo: number,
}

export type Scoring = {
	stats: Stats,
	multiplier: number,
	chain: number,
	lastKillAt: number,
	waveKills: number,
	waveScore: number,
	sessionBest: number,
	registerKill: (self: Scoring, kind: string, points: number, now: number) -> number,
	tick: (self: Scoring, now: number) -> boolean,
	beginWave: (self: Scoring) -> (),
	addBonus: (self: Scoring, amount: number) -> (),
	snapshot: (self: Scoring) -> Stats,
	restore: (self: Scoring, stats: Stats) -> (),
	reset: (self: Scoring) -> (),
}

local Scoring = {}
Scoring.__index = Scoring

local function emptyStats(): Stats
	return { score = 0, kills = {}, shots = 0, hits = 0, bestCombo = 1 }
end

local function copyStats(s: Stats): Stats
	return {
		score = s.score,
		kills = table.clone(s.kills),
		shots = s.shots,
		hits = s.hits,
		bestCombo = s.bestCombo,
	}
end

function Scoring.new(): Scoring
	local self = setmetatable({
		stats = emptyStats(),
		multiplier = 1,
		chain = 0,
		lastKillAt = -math.huge,
		waveKills = 0,
		waveScore = 0,
		sessionBest = 0,
	}, Scoring)
	return (self :: any) :: Scoring
end

-- Multiplier steps up every two chained kills: x1, x1, x2, x2, x3, x3, x4...
local function multiplierFor(chain: number): number
	return math.min(Config.Score.MAX_MULTIPLIER, 1 + math.floor((chain - 1) / 2))
end

function Scoring.registerKill(self: Scoring, kind: string, points: number, now: number): number
	if now - self.lastKillAt <= Config.Score.COMBO_WINDOW then
		self.chain += 1
	else
		self.chain = 1
	end
	self.lastKillAt = now
	self.multiplier = multiplierFor(self.chain)
	self.stats.bestCombo = math.max(self.stats.bestCombo, self.multiplier)
	local awarded = points * self.multiplier
	self.stats.score += awarded
	self.stats.kills[kind] = (self.stats.kills[kind] or 0) + 1
	self.waveKills += 1
	self.waveScore += awarded
	self.sessionBest = math.max(self.sessionBest, self.stats.score)
	return awarded
end

-- Drops the combo after the window lapses. Returns true when it changed.
function Scoring.tick(self: Scoring, now: number): boolean
	if self.multiplier > 1 and now - self.lastKillAt > Config.Score.COMBO_WINDOW then
		self.multiplier = 1
		self.chain = 0
		return true
	end
	return false
end

function Scoring.beginWave(self: Scoring)
	self.waveKills = 0
	self.waveScore = 0
end

function Scoring.addBonus(self: Scoring, amount: number)
	self.stats.score += amount
	self.sessionBest = math.max(self.sessionBest, self.stats.score)
end

function Scoring.snapshot(self: Scoring): Stats
	return copyStats(self.stats)
end

function Scoring.restore(self: Scoring, stats: Stats)
	self.stats = copyStats(stats)
	self.multiplier = 1
	self.chain = 0
	self.lastKillAt = -math.huge
end

function Scoring.reset(self: Scoring)
	self:restore(emptyStats())
end

return Scoring
