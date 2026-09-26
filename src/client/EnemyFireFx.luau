--!strict
-- Client presentation for enemy attacks ("EnemyFire" GameEvents): tracers,
-- grenade arcs, shells, rocket salvos, bombs. Owned by the enemies workstream.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Effects = require(script.Parent.Effects)
local Hud = require(script.Parent.Hud)
local Sfx = require(script.Parent.Sfx)

local EnemyFireFx = {}

-- payload: { kind, attack, from, to, id }
function EnemyFireFx.handle(p: any)
	if p.attack == "Grenade" then
		Effects.grenade(p.from, p.to, Config.Infantry.GRENADE_FLIGHT)
		task.delay(Config.Infantry.GRENADE_FLIGHT, function()
			Sfx.play("GrenadeBlast", 0.2)
		end)
		Hud.tipOnce("grenade", "Infantry at the mesa base throw grenades — <b>clear them fast!</b>", 5)
	elseif p.attack == "Rifle" then
		Effects.enemyShot(p.from, p.to)
	end
end

return EnemyFireFx
