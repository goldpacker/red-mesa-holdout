--!strict
-- Shared wind (VFX-4, docs/FACELIFT_TEAM.md "Update 2" contracts): the one
-- definition of wind direction, strength and gusts. Deterministic in time
-- and cheap (a few sines and hashes, no state), so the server, every client
-- and every module agree on it at the same instant. Nothing else defines
-- wind: sand streamers, dust devils, wreck smoke and wire flutter
-- (client/Weather*), chute drift (client/AirdropStyle), and Look's dust
-- layers read it here.
--
--   Wind.at(t)        -> velocity: Vector3, strength: number, gust: number
--       t is Workspace:GetServerTimeNow() (any number works: the same t
--       gives the same wind everywhere).
--       velocity  flat (Y = 0) drift of smoke and dust, studs/s. At
--                 strength 1 it is SPEED (2.8) along DIRECTION: the scale
--                 the effects already used for their drift (the old
--                 client/Effects.WIND), so it can stand in for it. Effects
--                 that need faster motion (sand streaming along the ground)
--                 scale it by their own gain.
--       strength  1 = the mean breeze; ~0.8..1.25 between gusts, up to ~2.2
--                 at the top of a strong gust.
--       gust      0..1 gust envelope (rises over ~2 s, dies over ~4 s; a
--                 gust every ~9 s on average, some calmer spells).
--   Wind.now()        Wind.at(server time now).
--   Wind.direction(t) flat unit downwind direction at t.
--   Wind.gust(t)      the gust envelope alone.
--   Wind.base(t)      Wind.at without the storm overlay (below).
--
-- Storm overlay (client only): during a dust storm client/DustStorm calls
-- Wind.setStorm(amount, direction, gain); Wind.at then turns the wind
-- toward the storm's direction and multiplies its strength by up to `gain`,
-- in proportion to `amount` (0..1). The server never sets it, and with no
-- storm Wind.at is purely a function of t.
--
-- The mean wind blows from the basin's far left (west, the low sun's side)
-- toward the right and a little toward the mesa: DIRECTION = (2.6, 0, 1.1)
-- normalised, the way the game's smoke and dust always drifted. It veers
-- slowly by up to ~12 degrees either side.

local Workspace = game:GetService("Workspace")

local Wind = {}

Wind.DIRECTION = Vector3.new(2.6, 0, 1.1).Unit
Wind.SPEED = 2.8 -- studs/s of drift at strength 1

local BASE_YAW = math.atan2(Wind.DIRECTION.Z, Wind.DIRECTION.X)
local VEER = math.rad(12) -- slow direction wander (amplitude)
local GUST_GAIN = 0.8 -- strength x (1 + GUST_GAIN * gust)

-- Gusts: one candidate per CELL seconds, present with probability
-- GUST_CHANCE, peaking somewhere in its cell.
local CELL = 9
local GUST_CHANCE = 0.72
local RISE = 1.8 -- s from calm to a gust's peak
local FALL = 3.6 -- s from its peak back to calm (smooth)

-- Deterministic 0..1 hash of a number.
local function hash(n: number): number
	local x = math.sin(n * 12.9898 + 78.233) * 43758.5453
	return x - math.floor(x)
end

local function smooth(u: number): number
	u = math.clamp(u, 0, 1)
	return u * u * (3 - 2 * u)
end

-- One gust's envelope `dt` seconds after its peak (negative = before).
local function pulse(dt: number): number
	if dt < 0 then
		return smooth(1 + dt / RISE)
	end
	return 1 - smooth(dt / FALL)
end

function Wind.gust(t: number): number
	local cell = math.floor(t / CELL)
	local g = 0
	for k = cell - 1, cell + 1 do
		if hash(k * 3 + 1) < GUST_CHANCE then
			local peak = (k + 0.15 + 0.7 * hash(k * 3 + 2)) * CELL
			local amp = 0.45 + 0.55 * hash(k * 3 + 3)
			g = math.max(g, amp * pulse(t - peak))
		end
	end
	return g
end

-- Slow swell of the mean breeze between gusts (0.77..1.23).
local function base(t: number): number
	return 1 + 0.15 * math.sin(t * (2 * math.pi / 71) + 1.3) + 0.08 * math.sin(t * (2 * math.pi / 23) + 0.4)
end

function Wind.direction(t: number): Vector3
	local yaw = BASE_YAW + VEER * (0.7 * math.sin(t * (2 * math.pi / 97)) + 0.3 * math.sin(t * (2 * math.pi / 41) + 2))
	return Vector3.new(math.cos(yaw), 0, math.sin(yaw))
end

function Wind.base(t: number): (Vector3, number, number)
	local gust = Wind.gust(t)
	local strength = base(t) * (1 + GUST_GAIN * gust)
	return Wind.direction(t) * (Wind.SPEED * strength), strength, gust
end

local stormAmount = 0
local stormDirection = Wind.DIRECTION
local stormGain = 1

function Wind.setStorm(amount: number, direction: Vector3?, gain: number?)
	stormAmount = math.clamp(amount, 0, 1)
	if direction and direction.Magnitude > 1e-3 then
		stormDirection = Vector3.new(direction.X, 0, direction.Z).Unit
	end
	stormGain = gain or stormGain
end

function Wind.at(t: number): (Vector3, number, number)
	local v, strength, gust = Wind.base(t)
	if stormAmount <= 0 then
		return v, strength, gust
	end
	local k = stormAmount
	local d = v.Unit:Lerp(stormDirection, k)
	d = if d.Magnitude > 1e-3 then d.Unit else stormDirection
	strength *= 1 + (stormGain - 1) * k
	gust = math.max(gust, 0.5 * k)
	return d * (Wind.SPEED * strength), strength, gust
end

function Wind.now(): (Vector3, number, number)
	return Wind.at(Workspace:GetServerTimeNow())
end

return Wind
