--!strict
-- Top-level game state machine:
--   Title -> WaveIntro -> Wave -> Intermission -> WaveIntro ... -> Victory
--                           \-> Defeat -> (Restart | RetryWave)
-- Publishes state as attributes on ReplicatedStorage.GameState and pushes
-- one-shot events through Remotes.GameEvent.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Crates = require(script.Parent.Crates)
local Enemies = require(script.Parent.Enemies)
local Scoring = require(script.Parent.Scoring)
local TimeOfDay = require(script.Parent.TimeOfDay)
local Types = require(script.Parent.Types)
local WaveDirector = require(script.Parent.WaveDirector)
local Weapons = require(script.Parent.Weapons)

local GameController = {}

local state = ReplicatedStorage:WaitForChild("GameState") :: Configuration
local remotes = ReplicatedStorage:WaitForChild("Remotes")
local gameEvent = remotes:WaitForChild("GameEvent") :: RemoteEvent

type Checkpoint = { wave: number, integrity: number, stats: Scoring.Stats }

local phase = "Title"
local waveNumber = 0
local integrity = Config.Integrity.MAX
local scoring = Scoring.new()
local director: WaveDirector.Director? = nil
local checkpoint: Checkpoint? = nil
-- Incremented on every transition so stale delayed callbacks can bail out.
local epoch = 0

local function publish()
	state:SetAttribute("Phase", phase)
	state:SetAttribute("Wave", waveNumber)
	state:SetAttribute("TotalWaves", #Config.Waves)
	state:SetAttribute("Integrity", integrity)
	state:SetAttribute("Score", scoring.stats.score)
	state:SetAttribute("Multiplier", scoring.multiplier)
	state:SetAttribute("SessionBest", scoring.sessionBest)
	state:SetAttribute("Remaining", if director then director:remaining() else 0)
end

local function setPhase(newPhase: string, duration: number?)
	phase = newPhase
	epoch += 1
	state:SetAttribute("PhaseEndsAt", if duration then Workspace:GetServerTimeNow() + duration else 0)
	publish()
end

local function emit(kind: string, payload: any)
	gameEvent:FireAllClients(kind, payload)
end

local function endStats(): any
	local s = scoring.stats
	return {
		score = s.score,
		wave = waveNumber,
		totalWaves = #Config.Waves,
		kills = table.clone(s.kills),
		-- Splash can hit several enemies per shot; accuracy is capped at 100%.
		accuracy = if s.shots > 0 then math.min(1, s.hits / s.shots) else 0,
		bestCombo = s.bestCombo,
		sessionBest = scoring.sessionBest,
	}
end

local function after(seconds: number, fn: () -> ())
	local myEpoch = epoch
	task.delay(seconds, function()
		if epoch == myEpoch then
			fn()
		end
	end)
end

local startWave: (n: number) -> ()

local function clearBattlefield()
	Enemies.clearAll()
	Crates.clearAll()
end

local function defeat()
	director = nil
	clearBattlefield()
	setPhase("Defeat")
	emit("Defeat", endStats())
end

local function victory()
	director = nil
	-- Keep the burning boss wreck on screen for the victory sequence; the
	-- next run's startWave clears the battlefield.
	Crates.clearAll()
	setPhase("Victory")
	emit("Victory", endStats())
end

local function waveCleared()
	local cleared = waveNumber
	director = nil
	local integrityBonus = math.floor(integrity) * Config.Score.INTEGRITY_BONUS_PER_POINT
	local clearBonus = Config.Score.WAVE_CLEAR_BONUS
	scoring:addBonus(clearBonus + integrityBonus)
	local before = integrity
	integrity = math.min(Config.Integrity.MAX, integrity + Config.Integrity.INTERMISSION_REPAIR)
	Weapons.resetAll()

	local isLast = cleared >= #Config.Waves
	local nextWave = Config.Waves[cleared + 1]
	if nextWave then
		-- Dusk falls during the intermission, never mid-wave.
		TimeOfDay.set(TimeOfDay.presetFor(cleared + 1, Config.Waves), Config.Timing.INTERMISSION * 0.7)
	end
	setPhase("Intermission", Config.Timing.INTERMISSION)
	emit("WaveClear", {
		wave = cleared,
		kills = scoring.waveKills,
		waveScore = scoring.waveScore,
		clearBonus = clearBonus,
		integrityBonus = integrityBonus,
		repaired = integrity - before,
		nextWave = if isLast then nil else cleared + 1,
		nextHint = if nextWave then nextWave.hint else nil,
		duration = Config.Timing.INTERMISSION,
	})

	Crates.clearAll()
	after(if isLast then 3 else Config.Timing.INTERMISSION, function()
		if not isLast then
			clearBattlefield()
		end
		if isLast then
			victory()
		else
			startWave(cleared + 1)
		end
	end)
end

function startWave(n: number)
	waveNumber = n
	clearBattlefield()
	scoring:beginWave()
	checkpoint = { wave = n, integrity = integrity, stats = scoring:snapshot() }
	TimeOfDay.set(TimeOfDay.presetFor(n, Config.Waves), 0)
	director = nil
	setPhase("WaveIntro", Config.Timing.WAVE_BANNER)
	emit("WaveStart", { wave = n, hint = Config.Waves[n].hint, total = #Config.Waves })
	after(Config.Timing.WAVE_BANNER, function()
		director = WaveDirector.new(GameController.context, n)
		setPhase("Wave")
	end)
end

local function newRun()
	integrity = Config.Integrity.MAX
	scoring:reset()
	Weapons.resetAll()
	startWave(1)
end

GameController.context = {
	damageOutpost = function(amount: number, from: Vector3, heavy: boolean)
		if phase ~= "Wave" then
			return
		end
		integrity = math.max(0, integrity - amount)
		emit("Damage", { amount = amount, from = from, heavy = heavy, integrity = integrity })
		publish()
		if integrity <= 0 then
			defeat()
		end
	end,
	enemyFired = function(enemy: Types.Enemy, attack: string, from: Vector3, to: Vector3)
		if phase == "Wave" then
			emit("EnemyFire", { kind = enemy.kind, attack = attack, from = from, to = to, id = enemy.id })
		end
	end,
	emit = function(kind: string, payload: any)
		emit(kind, payload)
	end,
	spawn = function(kind: string, lane: string): Types.Enemy?
		if phase ~= "Wave" then
			return nil
		end
		local ok, enemy = pcall(Enemies.spawn, GameController.context, kind, lane)
		if not ok then
			warn("[RedMesa] ctx.spawn failed: " .. tostring(enemy))
			return nil
		end
		return enemy
	end,
	dropCrate = function(bias: string?)
		if phase == "Wave" and GameController.onCrateRequest then
			GameController.onCrateRequest(bias)
		end
	end,
	awardPoints = function(points: number, position: Vector3, label: string)
		scoring:addBonus(points)
		scoring.waveScore += points
		emit("Points", { points = points, position = position, label = label })
		publish()
	end,
} :: Types.Context

-- Set by the crate system once it exists; receives the requested bias.
GameController.onCrateRequest = nil :: ((bias: string?) -> ())?

local function onHeartbeat(dt: number)
	if phase == "Wave" then
		Crates.update(dt)
	end
	local current = director
	if phase == "Wave" and current then
		current:update(dt)
		-- update() can trigger defeat, which clears the director.
		if current.finished and director == current and phase == "Wave" then
			waveCleared()
			return
		end
	end
	if scoring:tick(os.clock()) then
		publish()
	end
	if director then
		state:SetAttribute("Remaining", director:remaining())
	end
end

local function connectRemotes()
	(remotes:WaitForChild("StartGame") :: RemoteEvent).OnServerEvent:Connect(function()
		if phase == "Title" then
			newRun()
		end
	end);
	(remotes:WaitForChild("Restart") :: RemoteEvent).OnServerEvent:Connect(function()
		if phase == "Defeat" or phase == "Victory" then
			newRun()
		end
	end);
	(remotes:WaitForChild("RetryWave") :: RemoteEvent).OnServerEvent:Connect(function()
		if phase == "Defeat" and checkpoint then
			integrity = checkpoint.integrity
			scoring:restore(checkpoint.stats)
			Weapons.resetAll()
			startWave(checkpoint.wave)
		end
	end)
end

local function installDebugHooks()
	if not RunService:IsStudio() then
		return
	end
	-- QA-tools commands (LOS/ground checks, beauty-shot staging): server/QaDebug.
	local QaDebug = require(script.Parent.QaDebug)
	QaDebug.init({
		context = GameController.context,
		clearBattlefield = clearBattlefield,
		freeze = function(newPhase: string, wave: number)
			director = nil
			waveNumber = wave
			integrity = Config.Integrity.MAX
			setPhase(newPhase)
		end,
		setScore = function(score: number)
			scoring.stats.score = score
			publish()
		end,
	})
	local debugFn = Instance.new("BindableFunction")
	debugFn.Name = "RedMesaDebug"
	debugFn.OnInvoke = function(cmd: string, arg: any): any
		if cmd == "state" then
			return {
				phase = phase,
				wave = waveNumber,
				integrity = integrity,
				score = scoring.stats.score,
				enemies = Enemies.count(),
				shots = scoring.stats.shots,
				hits = scoring.stats.hits,
				stats = endStats(),
			}
		elseif cmd == "setIntegrity" then
			integrity = arg
			publish()
			if integrity <= 0 and phase == "Wave" then
				defeat()
			end
		elseif cmd == "killAll" then
			for _, enemy in Enemies.all() do
				Enemies.damage(enemy, math.huge, "Debug")
			end
		elseif cmd == "startWave" then
			startWave(arg)
		elseif cmd == "spawn" then
			-- arg = { kind = "Tank", lane = "Road" }; works during a Wave.
			local enemy = GameController.context.spawn(arg.kind, arg.lane)
			return enemy ~= nil
		elseif cmd == "crate" then
			GameController.context.dropCrate(arg)
		elseif QaDebug.has(cmd) then
			return QaDebug.run(cmd, arg)
		end
		return true
	end
	debugFn.Parent = game:GetService("ServerStorage")
end

function GameController.start()
	Weapons.init({
		canFire = function()
			return phase == "Wave" or phase == "WaveIntro" or phase == "Intermission"
		end,
		onShot = function(_player)
			if phase == "Wave" then
				scoring.stats.shots += 1
			end
		end,
		onHit = function(player, enemy, killed, position, headshot)
			scoring.stats.hits += 1
			if killed then
				local awarded = scoring:registerKill(enemy.kind, enemy.points, os.clock())
				emit("Kill", { kind = enemy.kind, points = awarded, multiplier = scoring.multiplier, position = position })
				publish()
			end
			gameEvent:FireClient(player, "Hit", { position = position, killed = killed, headshot = headshot })
		end,
		onWorldHit = function(_player, part, _position)
			if phase == "Wave" then
				Crates.tryCollect(part)
			end
		end,
	} :: any)
	Crates.init({
		addAmmo = function(kind: string, amount: number)
			local addAmmo = (Weapons :: any).addAmmo
			if addAmmo then
				addAmmo(kind, amount)
			end
		end,
		repair = function(amount: number)
			integrity = math.min(Config.Integrity.MAX, integrity + amount)
			publish()
		end,
		emit = emit,
	})
	GameController.onCrateRequest = Crates.spawn
	connectRemotes()
	installDebugHooks()
	RunService.Heartbeat:Connect(onHeartbeat)
	Players.PlayerAdded:Connect(publish)
	TimeOfDay.set("Afternoon", 0)
	setPhase("Title")
end

return GameController
