-- Client entry point for Red Mesa Holdout: wires input, camera, HUD,
-- screens and effects to the server's game state.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AimController = require(script.AimController)
local Effects = require(script.Effects)
local EnemyFireFx = require(script.EnemyFireFx)
local EnemyVisuals = require(script.EnemyVisuals)
local GameState = require(script.GameState)
local Hud = require(script.Hud)
local NightFx = require(script.NightFx)
local PostFx = require(script.PostFx)
local Screens = require(script.Screens)
local Sfx = require(script.Sfx)
local ThreatHud = require(script.ThreatHud)
local WeaponController = require(script.WeaponController)

local Config = require(ReplicatedStorage.Shared.Config)

Sfx.preload()
AimController.start()
WeaponController.start()
Hud.start()
Screens.start()
ThreatHud.start()
EnemyVisuals.start()
NightFx.start()
PostFx.start()
-- Studio-only beauty-shot rig (tools/qa/BEAUTY.md); a no-op in live games.
require(ReplicatedStorage.Shared.BeautyShots).startClient()

local tipOnce = Hud.tipOnce

local function applyPhase(phase: string)
	Screens.applyPhase(phase)
	if phase == "Title" then
		AimController.setMode("Title")
		Hud.setVisible(false)
	elseif phase == "Defeat" or phase == "Victory" then
		AimController.setMode(phase)
		Hud.setVisible(false)
	else
		AimController.setMode("Turret")
		Hud.setVisible(true)
	end
end

GameState.onChanged("Phase", applyPhase)
GameState.onChanged("Phase", function(phase)
	-- Desert wind under the whole battle.
	Sfx.setLoop("Wind", phase ~= "Title")
end)
applyPhase(GameState.phase())

GameState.onEvent("WaveStart", function(p)
	if p.wave == 1 then
		tipOnce("fire", "Hold <b>LEFT MOUSE</b> to fire · hold <b>RIGHT MOUSE</b> for the gunsight", 7)
	end
end)

GameState.onEvent("Hit", function(p)
	Hud.showHitMarker(p.killed)
	Sfx.play(if p.killed then "Kill" else "Hit", 0.1)
end)

GameState.onEvent("WaveStart", function()
	Sfx.play("WaveStart")
end)
GameState.onEvent("WaveClear", function()
	Sfx.play("WaveClear")
end)
GameState.onEvent("Victory", function()
	Sfx.play("Victory")
	NightFx.celebrate()
end)
GameState.onEvent("Defeat", function()
	task.delay(1.2, Sfx.play, "Defeat")
end)

GameState.onEvent("Kill", function(p)
	local label = "+" .. p.points
	if p.multiplier > 1 then
		label ..= "  x" .. p.multiplier
	end
	Hud.scorePopup(p.position + Vector3.new(0, 4, 0), label)
	if p.kind == "Infantry" then
		Sfx.playAt("InfantryDeath", p.position, 0.3)
	end
end)

GameState.onEvent("EnemyFire", EnemyFireFx.handle)

-- Defeat: the emplacement erupts and keeps burning until the next run.
local burning: { BasePart } = {}
GameState.onEvent("Defeat", function()
	local pivot = Config.TURRET_PIVOT
	for i = 0, 3 do
		task.delay(i * 0.35, function()
			local offset = Vector3.new(math.random(-6, 6), math.random(-2, 3), math.random(-6, 6))
			Effects.explosion(pivot + offset, 2.2)
			Sfx.play("Explosion", 0.3)
			AimController.shake(0.5)
		end)
	end
	table.insert(burning, Effects.burning(pivot + Vector3.new(0, -3, 0), 1.6))
	table.insert(burning, Effects.burning(pivot + Vector3.new(7, -5, 4), 1))
end)
GameState.onChanged("Phase", function(phase)
	if phase ~= "Defeat" then
		for _, part in burning do
			part:Destroy()
		end
		table.clear(burning)
	end
end)

GameState.onEvent("Damage", function(p)
	Hud.damageIndicator(p.from, p.heavy)
	Sfx.play(if p.heavy then "HeavyHit" else "Damage", 0.2)
	AimController.shake(if p.heavy then 0.6 else 0.15)
end)

WeaponController.on("Overheat", function()
	tipOnce("overheat", "Gun overheated! Fire in <b>short bursts</b> to keep heat down", 5)
	AimController.shake(0.2)
end)

-- LOOK-3: enemy root smoothing and body motion (rendering only).
require(script.EnemyMotion).start()
-- AD-1: transports, parachute descents and the airborne "no effect".
require(script.Airdrop).start()

print("[RedMesa] client ready")
