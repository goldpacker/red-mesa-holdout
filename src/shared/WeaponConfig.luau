--!strict
-- Tuning for weapon selection, rockets and AA missiles, plus the small pure
-- flight helpers the server simulation and client visuals share so both
-- fly the same path. Owned by the weapons workstream.
-- (Machine gun tuning lives in Config.MachineGun.)

local WeaponConfig = {}

-- Slot order for keys 1/2/3 and the mouse wheel.
WeaponConfig.SLOTS = { "MG", "Rocket", "Missile" }
WeaponConfig.SLOT_NAMES = { MG = "MACHINE GUN", Rocket = "ROCKETS", Missile = "AA MISSILES" }
-- Time after a switch before the new weapon can fire (turret swap animation).
WeaponConfig.SWITCH_TIME = 0.22

-- Player attribute names (server-owned, replicated to the client).
WeaponConfig.Attr = {
	Rockets = "Rockets",
	Missiles = "Missiles",
	RocketReloadEndsAt = "RocketReloadEndsAt", -- Workspace:GetServerTimeNow() seconds
	MissileReloadEndsAt = "MissileReloadEndsAt",
}

WeaponConfig.Rocket = {
	AMMO = 8, -- restocked to this every intermission
	MAX_AMMO = 16, -- cap when crates add more
	RELOAD = 1.5,
	SPEED = 340, -- studs/s, no drop: fast, but buggies still need leading
	MAX_RANGE = 1700,
	DIRECT_DAMAGE = 60, -- to the enemy the rocket struck
	SPLASH_DAMAGE = 60, -- at the centre, linear falloff to 25% at the edge
	SPLASH_RADIUS = 20,
	SHAKE_RADIUS = 260, -- camera shake fades out over this distance
}

WeaponConfig.Missile = {
	AMMO = 4,
	MAX_AMMO = 8,
	RELOAD = 1.0,
	-- Lock-on: keep an aircraft within ACQUIRE_DEG of the crosshair for
	-- LOCK_TIME seconds. The lock holds until it drifts past BREAK_DEG.
	LOCK_TIME = 1.0,
	ACQUIRE_DEG = 7,
	BREAK_DEG = 13,
	LOCK_RANGE = 1500,
	LOCK_DECAY = 2.5, -- progress lost per second while off target
	-- Flight.
	LAUNCH_SPEED = 170,
	MAX_SPEED = 560,
	ACCEL = 700,
	BOOST_TIME = 0.18, -- flies straight off the rail before steering
	TURN_RATE_DEG = 200,
	PROXIMITY = 14, -- detonates this close to the target
	LIFETIME = 7,
	DAMAGE = 240,
	SPLASH_DAMAGE = 40,
	SPLASH_RADIUS = 18,
	SHAKE_RADIUS = 200,
	-- Firing without a lock is refused (with a "NO LOCK" warning) so a
	-- scarce missile is never wasted on the ground.
}

-- Server-side validation slack.
WeaponConfig.Server = {
	RELOAD_TOLERANCE = 0.2, -- seconds early a shot may arrive (network jitter)
	LOCK_TIME_TOLERANCE = 0.7, -- fraction of LOCK_TIME the server requires
	LOCK_CONE_TOLERANCE_DEG = 10, -- extra cone slack for fire direction vs target
	RICOCHET_RESIST = 0.35, -- MG resist at or below this shows ricochet sparks
	RICOCHET_INTERVAL = 0.08,
}

-- Rotates unit vector `dir` toward unit vector `desired` by at most
-- `maxAngle` radians.
function WeaponConfig.steer(dir: Vector3, desired: Vector3, maxAngle: number): Vector3
	local dot = math.clamp(dir:Dot(desired), -1, 1)
	local angle = math.acos(dot)
	if angle <= maxAngle or angle < 1e-4 then
		return desired
	end
	local axis = dir:Cross(desired)
	if axis.Magnitude < 1e-5 then
		axis = if math.abs(dir.Y) < 0.9 then dir:Cross(Vector3.yAxis) else dir:Cross(Vector3.xAxis)
	end
	return (CFrame.fromAxisAngle(axis.Unit, maxAngle) * dir).Unit
end

-- Aim point that leads a target moving at `targetVel`, for a missile at
-- `pos` flying at `speed`. Falls back to the target's current position.
function WeaponConfig.intercept(pos: Vector3, speed: number, targetPos: Vector3, targetVel: Vector3): Vector3
	local dist = (targetPos - pos).Magnitude
	local t = math.clamp(dist / math.max(speed, 1), 0, 1.5)
	return targetPos + targetVel * t
end

-- One missile flight step shared by the server simulation and the client
-- visual. Returns the new position, direction and speed.
function WeaponConfig.missileStep(
	pos: Vector3,
	dir: Vector3,
	speed: number,
	age: number,
	dt: number,
	targetPos: Vector3?,
	targetVel: Vector3?
): (Vector3, Vector3, number)
	local M = WeaponConfig.Missile
	speed = math.min(M.MAX_SPEED, speed + M.ACCEL * dt)
	if targetPos and age >= M.BOOST_TIME then
		local aimAt = WeaponConfig.intercept(pos, speed, targetPos, targetVel or Vector3.zero)
		local to = aimAt - pos
		if to.Magnitude > 0.01 then
			dir = WeaponConfig.steer(dir, to.Unit, math.rad(M.TURN_RATE_DEG) * dt)
		end
	end
	return pos + dir * speed * dt, dir, speed
end

return WeaponConfig
