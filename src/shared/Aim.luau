--!strict
-- Converts turret yaw/pitch (degrees) to world directions and back.

local Config = require(script.Parent.Config)

local Aim = {}

function Aim.clampAngles(yaw: number, pitch: number): (number, number)
	return math.clamp(yaw, -Config.YAW_LIMIT, Config.YAW_LIMIT), math.clamp(pitch, Config.PITCH_MIN, Config.PITCH_MAX)
end

-- CFrame at the pivot, looking along the aim direction.
function Aim.cframe(yaw: number, pitch: number): CFrame
	return CFrame.new(Config.TURRET_PIVOT)
		* CFrame.Angles(0, math.rad(yaw), 0)
		* CFrame.Angles(math.rad(pitch), 0, 0)
end

function Aim.direction(yaw: number, pitch: number): Vector3
	return Aim.cframe(yaw, pitch).LookVector
end

function Aim.muzzle(yaw: number, pitch: number): Vector3
	return Config.TURRET_PIVOT + Aim.direction(yaw, pitch) * Config.MUZZLE_OFFSET
end

-- Signed yaw (degrees) of a world position relative to FORWARD, positive = left.
function Aim.yawTo(position: Vector3): number
	local d = position - Config.TURRET_PIVOT
	return math.deg(math.atan2(-d.X, -d.Z))
end

function Aim.isInArc(position: Vector3): boolean
	return math.abs(Aim.yawTo(position)) <= Config.YAW_LIMIT
end

return Aim
