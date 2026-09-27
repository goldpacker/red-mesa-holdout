--!strict
-- Airdrop effects (AD-2) on VFX's flipbooks (shared/Flipbooks, through the
-- pooled emitter rigs in client/Effects): the landing dust puff, and the
-- airborne "no effect" feedback for machine-gun rounds:
--   * a round that meets a load's body, a platform or a transport sparks
--     off with a soft ping and glances away as a short ricochet tracer
--     (no hit marker, no score: the server never sees it);
--   * a round through a canopy leaves a small puff of fabric and keeps
--     going (the tracer carries on to wherever it was going).
-- Both wait for the tracer to arrive (Effects.tracer's travel time).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Effects = require(script.Parent.Effects)
local Sfx = require(script.Parent.Sfx)
local Style = require(script.Parent.AirdropStyle)

local Fx = {}

local seq = Effects.seq
local SAND = Effects.SAND
local DUST = Effects.DUST
local FABRIC = Color3.fromRGB(104, 100, 80)
local RICOCHET = Color3.fromRGB(255, 214, 150)

local function buildDust(): { [string]: ParticleEmitter? }
	local wind = Style.wind(0) * 0.6
	return {
		-- Ground burst: pushed out and up from the touchdown, short-lived so
		-- it never hides the landed enemy for long (checked at Sunset, when
		-- the low sun makes dust glow).
		burst = Effects.slot("DustPuff", 1, {
			Color = ColorSequence.new(SAND),
			Transparency = seq(0.35, 0.55, 1),
			Lifetime = NumberRange.new(1.0, 1.6),
			Speed = NumberRange.new(6, 11),
			SpreadAngle = Vector2.new(70, 70),
			Drag = 2.8,
			Acceleration = wind + Vector3.new(0, 1.5, 0),
			EmissionDirection = Enum.NormalId.Top,
			Brightness = 0.75,
		}),
		-- A thin cloud that hangs a moment and drifts downwind.
		cloud = Effects.slot("DustDrift", 1, {
			Color = ColorSequence.new(DUST),
			Transparency = seq(0.55, 0.7, 1),
			Lifetime = NumberRange.new(1.6, 2.4),
			Speed = NumberRange.new(2, 4),
			SpreadAngle = Vector2.new(60, 60),
			Drag = 1.2,
			Acceleration = wind + Vector3.new(0, 0.6, 0),
			EmissionDirection = Enum.NormalId.Top,
			Brightness = 0.7,
		}),
	}
end

-- Per kind: particle counts, size scales (x the flipbook's suggestion) and
-- how high above the ground the burst starts (big billboards starting at
-- ground level slice into it with a hard edge).
local SIZES = {
	Infantry = { burst = 3, burstScale = 0.45, cloud = 1, cloudScale = 0.45, lift = 1 },
	Buggy = { burst = 4, burstScale = 0.8, cloud = 2, cloudScale = 0.8, lift = 2.5 },
	Tank = { burst = 6, burstScale = 1.05, cloud = 2, cloudScale = 1.05, lift = 3.5 },
}

-- Dust at a touchdown point (feet, wheels or the platform's base).
function Fx.touchdown(position: Vector3, kind: string)
	local size = SIZES[kind] or SIZES.Infantry
	local r = Effects.rig("AirdropDust", buildDust, nil, 6)
	local e = r.e
	local at = Effects.upFrame(position + Vector3.new(0, size.lift, 0), Vector3.yAxis)
	local burst, cloud = e.burst, e.cloud
	if burst then
		burst.Size = Effects.sized(size.burstScale, 4, 10, 13)
		Effects.emitAt(burst, at, Effects.lod(size.burst, position))
	end
	if cloud then
		cloud.Size = Effects.sized(size.cloudScale, 5, 12, 16)
		Effects.emitAt(cloud, at, Effects.lod(size.cloud, position))
	end
end

-- Seconds a tracer from the turret takes to reach `position`
-- (Effects.tracer: dist / 900, clamped to 0.04..0.35).
local function arrival(position: Vector3): number
	return math.clamp((position - Config.TURRET_PIVOT).Magnitude / 900, 0.04, 0.35)
end

local lastPing = 0
local lastRicochet = 0

-- A round sparks off an invulnerable load or transport at `position`.
function Fx.deflect(position: Vector3, from: Vector3, normal: Vector3?)
	task.delay(arrival(position), function()
		Effects.impact(position, true, from, "Metal")
		local now = os.clock()
		if now - lastPing > 0.12 then
			lastPing = now
			Sfx.play("DeflectPing", 0.15)
		end
		if now - lastRicochet > 0.1 then
			lastRicochet = now
			-- Glance off: reflect about the surface normal, scattered.
			local incoming = (position - from).Unit
			local n = normal or -incoming
			local out = incoming - n * 2 * incoming:Dot(n)
			local jitter = Vector3.new(math.random() - 0.5, math.random() * 0.6, math.random() - 0.5)
			local dir = (out + jitter * 0.8).Unit
			Effects.tracer(position, position + dir * (22 + math.random() * 18), RICOCHET, 0.22)
		end
	end)
end

local lastPuff = 0
local function buildCloth(): { [string]: ParticleEmitter? }
	return {
		puff = Effects.slot("DustPuff", 0.3, {
			Color = ColorSequence.new(FABRIC),
			Transparency = seq(0.3, 0.55, 1),
			Lifetime = NumberRange.new(0.5, 0.8),
			Speed = NumberRange.new(1, 3),
		}),
	}
end

-- A round passes through a canopy at `position`.
function Fx.passThrough(position: Vector3)
	local now = os.clock()
	if now - lastPuff < 0.08 then
		return
	end
	lastPuff = now
	task.delay(arrival(position), function()
		local r = Effects.rig("AirdropCloth", buildCloth, nil, 4)
		Effects.emitAt(r.e.puff, CFrame.new(position), 1)
	end)
end

return Fx
