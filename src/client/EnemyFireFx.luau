--!strict
-- Client presentation for enemy attacks ("EnemyFire" GameEvents): rifle
-- tracers, grenade arcs, buggy bursts, tank telegraphs and shells,
-- helicopter salvo warnings and rockets, jet bombs, and the Siege
-- Crawler's turrets and main cannon. Flight times come from
-- EnemyConfig.Flight so visuals land when the server applies damage.
-- Owned by the enemies workstream.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local EnemyConfig = require(ReplicatedStorage.Shared.EnemyConfig)
local Effects = require(script.Parent.Effects)
local Hud = require(script.Parent.Hud)
local Particles = require(script.Parent.VehicleFxParticles)
local Sfx = require(script.Parent.Sfx)

local EnemyFireFx = {}

local FLIGHT = EnemyConfig.Flight
local TRACER_RED = Color3.fromRGB(255, 96, 60)
local SHELL_COLOR = Color3.fromRGB(255, 214, 150)
local BOSS_COLOR = Color3.fromRGB(255, 120, 60)

local function dir(from: Vector3, to: Vector3): Vector3
	local d = to - from
	return if d.Magnitude > 1e-3 then d.Unit else Vector3.new(0, 0, 1)
end

local function jitter(v: Vector3, r: number): Vector3
	return v + Vector3.new((math.random() - 0.5) * r, (math.random() - 0.5) * r * 0.4, (math.random() - 0.5) * r)
end

-- Impact at the outpost: flash, flame, sparks and sound, but no smoke so
-- the player's view stays clear (damage feedback itself is the HUD's job
-- via the Damage event).
local function outpostImpact(at: Vector3, scale: number, sound: string)
	Particles.explosion(at, scale, { near = true, debris = false })
	Sfx.playAt(sound, at, 0.2)
end

local function buggyBurst(p: any)
	local rounds = EnemyConfig.Buggy.BURST_ROUNDS
	Sfx.playAt("EnemyRifle", p.from, 0.15)
	for i = 0, rounds - 1 do
		task.delay(i * 0.09, function()
			local to = jitter(p.to, 7)
			Particles.muzzle(p.from, dir(p.from, to), 0.35, TRACER_RED)
			Effects.tracer(p.from, to, TRACER_RED, 0.35)
			task.delay(FLIGHT.BUGGY_ROUND, function()
				Effects.impact(to, false)
			end)
		end)
	end
end

local function tankShell(p: any)
	local d = dir(p.from, p.to)
	Particles.muzzle(p.from, d, 2.2)
	-- Blast dust kicked up around the tank.
	Particles.explosion(p.from - d * 6 - Vector3.new(0, 5, 0), 0.9, { light = true, debris = false })
	Sfx.playAt("TankCannon", p.from, 0.1)
	local shell = Particles.projectile(7, 0.55, SHELL_COLOR, false, 14)
	Particles.fly(shell, p.from, p.to, FLIGHT.TANK_SHELL, 6, function()
		outpostImpact(p.to, 1.3, "Explosion")
	end)
end

local function heliRocket(p: any)
	Particles.muzzle(p.from, dir(p.from, p.to), 0.6)
	Sfx.playAt("HeliRockets", p.from, 0.2)
	local rocket = Particles.projectile(2.2, 0.45, Color3.fromRGB(255, 190, 110), true, 10)
	local to = jitter(p.to, 5)
	Particles.fly(rocket, p.from, to, FLIGHT.HELI_ROCKET, 8 + math.random() * 10, function()
		outpostImpact(to, 0.8, "ExplosionSmall")
	end)
end

local function jetBombs(p: any)
	local count = EnemyConfig.Jet.BOMB_COUNT
	Sfx.play("BombWhistle", 0.1)
	for i = 1, count do
		task.delay((i - 1) * 0.12, function()
			local to = jitter(p.to, 16)
			local bomb = Particles.projectile(3.6, 1.0, Color3.fromRGB(40, 40, 42), false)
			bomb.Material = Enum.Material.Metal
			-- Carries forward under the jet, then falls steeply onto the target.
			local from = p.from + Vector3.new((i - 2.5) * 2, -2, 0)
			Particles.fly(bomb, from, to, FLIGHT.BOMB - (i - 1) * 0.12, 22, function()
				outpostImpact(to, 1.6, "Explosion")
			end)
		end)
	end
end

local function bossTurret(p: any)
	Sfx.playAt("TankCannon", p.from, 0.25)
	for i = 0, 2 do
		task.delay(i * 0.14, function()
			local to = jitter(p.to, 6)
			Particles.muzzle(p.from, dir(p.from, to), 1)
			Effects.tracer(p.from, to, BOSS_COLOR, 0.7)
			task.delay(FLIGHT.BOSS_TURRET, function()
				Particles.explosion(to, 0.5, { near = true, debris = false })
			end)
		end)
	end
end

local function bossCannon(p: any)
	local d = dir(p.from, p.to)
	Particles.muzzle(p.from, d, 4.5, BOSS_COLOR)
	Particles.explosion(p.from + d * 4, 1.6, { air = true, light = true, debris = false })
	Sfx.playAt("TankCannon", p.from, 0)
	Sfx.play("Explosion", 0.05, 0.8)
	local slug = Particles.projectile(14, 2.0, BOSS_COLOR, true, 40)
	Particles.fly(slug, p.from, p.to, FLIGHT.BOSS_SHELL, 10, function()
		Particles.explosion(p.to, 2.4, { near = true })
		Sfx.playAt("Explosion", p.to, 0)
	end)
end

-- payload: { kind, attack, from, to, id }
function EnemyFireFx.handle(p: any)
	local attack = p.attack
	if attack == "Grenade" then
		Effects.grenade(p.from, p.to, Config.Infantry.GRENADE_FLIGHT)
		task.delay(Config.Infantry.GRENADE_FLIGHT, function()
			Sfx.play("GrenadeBlast", 0.2)
		end)
		Hud.tipOnce("grenade", "Infantry at the mesa base throw grenades — <b>clear them fast!</b>", 5)
	elseif attack == "Rifle" then
		Effects.enemyShot(p.from, p.to)
		Sfx.playAt("EnemyRifle", p.from, 0.2)
	elseif attack == "BuggyBurst" then
		buggyBurst(p)
	elseif attack == "TankAim" then
		-- Telegraph: a hot glint on the muzzle while the turret swings on.
		Particles.glint(p.from, EnemyConfig.Tank.AIM_TIME, Color3.fromRGB(255, 236, 190), 18)
	elseif attack == "Shell" then
		tankShell(p)
	elseif attack == "SalvoWarn" then
		Particles.glint(p.from + Vector3.new(0, -3, 0), EnemyConfig.Helicopter.SALVO_WARN, Color3.fromRGB(255, 80, 60), 16)
	elseif attack == "Rocket" then
		heliRocket(p)
	elseif attack == "Bombs" then
		jetBombs(p)
	elseif attack == "BossTurret" then
		bossTurret(p)
	elseif attack == "BossCannon" then
		bossCannon(p)
	end
end

return EnemyFireFx
