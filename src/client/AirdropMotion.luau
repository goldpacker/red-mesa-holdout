--!strict
-- Load motion for the airdrop visuals (AD-2). Pure functions.
--
-- The server timeline (shared/AirdropPath) is the contract: a load is at
-- `openPos` at `openT` and at `landPos` exactly at `landT`. The visuals
-- keep those two points and times and only restyle the motion around them:
--   * free fall starts at the opened ramp's lip (not the aircraft's centre)
--     with the aircraft's velocity, and eases (cubic Hermite) onto the
--     canopy-phase pose at openT;
--   * under canopy the horizontal track is AirdropPath's; the vertical is
--     reshaped by an optional landing flare with the same endpoints.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AirdropPath = require(ReplicatedStorage.Shared.AirdropPath)
local Style = require(script.Parent.AirdropStyle)

local Motion = {}

-- Cubic Hermite from (p0, v0) at time 0 to (p1, v1) at time T; returns the
-- position and velocity at time s.
function Motion.hermite(p0: Vector3, v0: Vector3, p1: Vector3, v1: Vector3, T: number, s: number): (Vector3, Vector3)
	local u = math.clamp(s / math.max(T, 1e-3), 0, 1)
	local u2, u3 = u * u, u * u * u
	local h00 = 2 * u3 - 3 * u2 + 1
	local h10 = u3 - 2 * u2 + u
	local h01 = -2 * u3 + 3 * u2
	local h11 = u3 - u2
	local pos = p0 * h00 + v0 * (T * h10) + p1 * h01 + v1 * (T * h11)
	local d00 = 6 * u2 - 6 * u
	local d10 = 3 * u2 - 4 * u + 1
	local d01 = -6 * u2 + 6 * u
	local d11 = 3 * u2 - 2 * u
	local vel = (p0 * d00 + p1 * d01) / math.max(T, 1e-3) + v0 * d10 + v1 * d11
	return pos, vel
end

-- Canopy-phase reference point (a load's lowest point) at t in
-- [openT, landT]: AirdropPath's horizontal drift, flared vertical.
function Motion.canopy(s: AirdropPath.Sortie, l: AirdropPath.Load, t: number, flare: number?, sharp: number?): (Vector3, number)
	local pos, _, u = AirdropPath.loadAt(s, l, math.clamp(t, l.openT, l.landT))
	if flare and flare > 0 then
		local g = Style.flare(u, flare, sharp or 10)
		local y = l.openPos.Y + (l.landPos.Y - l.openPos.Y) * g
		pos = Vector3.new(pos.X, y, pos.Z)
	end
	return pos, u
end

-- Sink rate (studs/s, positive down) under canopy.
function Motion.sinkRate(l: AirdropPath.Load): number
	return (l.openPos.Y - l.landPos.Y) / math.max(l.landT - l.openT, 1e-3)
end

-- Flat unit facing turned from `a` toward `b` by fraction u (shortest way).
function Motion.turn(a: Vector3, b: Vector3, u: number): Vector3
	local ya = math.atan2(a.X, a.Z)
	local yb = math.atan2(b.X, b.Z)
	local d = (yb - ya + math.pi) % (math.pi * 2) - math.pi
	local y = ya + d * u
	return Vector3.new(math.sin(y), 0, math.cos(y))
end

function Motion.flatUnit(v: Vector3, fallback: Vector3): Vector3
	local f = Vector3.new(v.X, 0, v.Z)
	return if f.Magnitude > 1e-3 then f.Unit else fallback
end

return Motion
