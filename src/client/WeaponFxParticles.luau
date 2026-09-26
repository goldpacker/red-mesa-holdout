--!strict
-- Particle recipes for our heavy weapons (VFX-2): rocket/missile exhaust
-- and smoke trails, their explosions, ricochet sparks off armour and the
-- launch backblast (flash plus dust blown back and down into the gun pit).
-- Custom flipbooks only (client/Effects); everything is short-lived.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Effects = require(script.Parent.Effects)
local Blasts = require(script.Parent.VehicleFxParticles)

local Particles = {}

local seq, slot, emitAt, rig, upFrame = Effects.seq, Effects.slot, Effects.emitAt, Effects.rig, Effects.upFrame
local emitter = Effects.emitter
Particles.seq = seq

-- Our rocket (scale 1) or missile air burst.
function Particles.explosion(position: Vector3, scale: number, air: boolean)
	Blasts.explosion(position, scale, { air = air, set = "surface" })
end

-- Hot sparks glancing off armour (the server's Ricochet event).
function Particles.ricochet(position: Vector3, _normal: Vector3?)
	Effects.impact(position, true, nil, "Metal")
end

local function buildBackblast(): { [string]: ParticleEmitter? }
	return {
		flash = slot("MuzzleFlashBurst", 0.75, { Lifetime = NumberRange.new(0.06, 0.1) }),
		side = slot("MuzzleFlashSide", 1.1, { Speed = NumberRange.new(0.5), EmissionDirection = Enum.NormalId.Top }),
		-- Launch smoke hanging at the tube mouth.
		smoke = slot("MissileTrail", 1.1, {
			Color = ColorSequence.new(Color3.fromRGB(214, 206, 194)),
			Transparency = seq(0.3, 0.5, 1),
			Lifetime = NumberRange.new(1.2, 1.8),
			Speed = NumberRange.new(4, 10),
			SpreadAngle = Vector2.new(30, 30),
			Drag = 3,
			Acceleration = Vector3.new(0, 2, 0),
		}),
		-- Backblast dust thrown back and down into the pit, rolling out low.
		dust = slot("DustPuff", 0.7, {
			Color = ColorSequence.new(Effects.DUST),
			Transparency = seq(0.35, 0.55, 1),
			Lifetime = NumberRange.new(1.0, 1.6),
			Speed = NumberRange.new(9, 16),
			SpreadAngle = Vector2.new(45, 45),
			Drag = 4,
			Acceleration = Effects.WIND * 0.5 + Vector3.new(0, 1.5, 0),
		}),
	}
end

-- Launch effects at the muzzle; `dir` is the flight direction and
-- `bright` marks the missile (whiter flash, white smoke).
function Particles.backblast(position: Vector3, dir: Vector3, bright: boolean)
	local r = rig("Backblast", buildBackblast, 14, 2)
	local d = if dir.Magnitude > 1e-3 then dir.Unit else Vector3.zAxis
	local k = Effects.exposure()
	local e = r.e
	local mouth = upFrame(position + d * 1.1, d)
	for _, name in { "flash", "side" } do
		local em = e[name]
		if em then
			em.Brightness = (if bright then 1.3 else 1.1) * k
		end
	end
	-- Down the gunsight the camera sits at the tubes: no sprites in its face.
	local sighted = Effects.camDistance(position) < 10
	if not sighted then
		emitAt(e.flash, mouth, 1)
		emitAt(e.side, mouth, 1)
		emitAt(e.smoke, mouth, if bright then 4 else 3)
	end
	-- The pod's exhaust leaves the rear of the tubes: aim the dust back
	-- and down into the gun pit so it stays under the camera's view.
	local back = Vector3.new(-d.X, 0, -d.Z)
	back = if back.Magnitude > 1e-3 then back.Unit else Vector3.zAxis
	local rear = Config.TURRET_PIVOT + back * 3 + Vector3.new(0, -3.5, 0)
	emitAt(e.dust, upFrame(rear, (back - Vector3.new(0, 1.2, 0)).Unit), if bright then 2 else 4)
	Effects.placeLight(r.light, mouth)
	Effects.pulse(r.light, if bright then Color3.fromRGB(255, 236, 206) else Color3.fromRGB(255, 176, 96), 2.6 * k, 0.12)
end

-- Continuous emitters on a projectile's tail attachment (+Y points out of
-- the back). Returned so the caller can disable them on impact.
function Particles.trail(tail: Attachment, kind: string): { ParticleEmitter }
	local missile = kind == "Missile"
	local k = Effects.exposure()
	local out = {}
	local flame = emitter(tail, "RocketExhaust", if missile then 0.8 else 0.6, {
		Speed = NumberRange.new(1),
		LockedToPart = true,
		Brightness = 1.2 * k,
		Rate = 45,
	})
	-- Seen from the gun the trail runs along the line of sight and its puffs
	-- stack up: keep the rocket's short and thin (the missile's curves away).
	local smoke = emitter(tail, "MissileTrail", if missile then 1 else 0.7, {
		Color = ColorSequence.new(if missile then Color3.fromRGB(226, 224, 218) else Color3.fromRGB(168, 160, 148)),
		Transparency = if missile then seq(0.1, 0.35, 1) else seq(0.5, 0.7, 1),
		Lifetime = if missile then NumberRange.new(1.8, 2.6) else NumberRange.new(0.7, 1.1),
		Rate = if missile then 70 else 28,
		Speed = NumberRange.new(0.5, 2),
		SpreadAngle = Vector2.new(10, 10),
		Drag = 1,
		Acceleration = Vector3.new(0, 1.2, 0),
	})
	if flame then
		flame.Enabled = true
		table.insert(out, flame)
	end
	if smoke then
		table.insert(out, smoke)
		-- Start the smoke trail a few dozen studs out so it never drifts
		-- across the gunsight the round was fired from.
		task.delay(if missile then 0.16 else 0.09, function()
			if smoke.Parent and tail.Parent and not tail:GetAttribute("Done") then
				smoke.Enabled = true
			end
		end)
	end
	return out
end

return Particles
