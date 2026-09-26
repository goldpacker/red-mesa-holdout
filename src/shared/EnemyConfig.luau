--!strict
-- Tuning and flight paths for buggies, tanks, helicopters, jets and the
-- Siege Crawler. Owned by the enemies workstream. (Infantry tuning and
-- ground lanes live in Config.)
--
-- Health is tuned against WeaponConfig: MG 12/bullet (~11/s, overheats
-- after ~31 shots); rocket 60 direct + up to 60 splash (radius 20, measured
-- to the enemy root); missile 240. Every `*_DAMAGE` here is outpost
-- integrity (0-100).

local EnemyConfig = {}

-- Seconds a projectile takes from muzzle to the outpost. Shared so the
-- client's visuals land exactly when the server applies damage.
EnemyConfig.Flight = {
	BUGGY_ROUND = 0.25,
	TANK_SHELL = 0.55,
	HELI_ROCKET = 1.15,
	SALVO_SPACING = 0.2,
	BOMB = 1.7,
	BOSS_SHELL = 0.45,
	BOSS_TURRET = 0.3,
}

EnemyConfig.Buggy = {
	HEALTH = 90, -- ~8 MG hits; one rocket
	POINTS = 50,
	SPEED = 48, -- studs/s while running up the wash
	TURN_RATE = 2.6, -- rad/s
	WEAVE_AMPLITUDE = 9,
	WEAVE_FREQUENCY = 0.45, -- Hz
	ENGAGE_RANGE = 330, -- starts circling once this close (horizontal)
	STRAFE_SPEED = 30,
	STRAFE_RADIUS = { 230, 320 },
	STRAFE_YAW_LIMIT = 92, -- degrees either side of forward
	GUN_RANGE = 460,
	BURST_INTERVAL = 2.6,
	BURST_ROUNDS = 5,
	BURST_DAMAGE = 1.1, -- per burst (~0.4 integrity/s per strafing buggy)
	RIDE_HEIGHT = 0,
}

EnemyConfig.Tank = {
	HEALTH = 180, -- one rocket (<=120) never kills, two (>=186) always do
	RESIST = { MG = 0.03, Rocket = 1, Missile = 0.5 },
	POINTS = 150,
	SPEED = 11,
	TURN_RATE = 0.7,
	LATERAL_JITTER = 7,
	FIRE_DISTANCE = { 390, 560 }, -- stops at a random distance in this range
	FIRE_INTERVAL = 7,
	AIM_TIME = 1.8, -- telegraph: turret swings on, muzzle glints
	SHELL_DAMAGE = 7,
	SPACING = 34, -- keeps queued tanks from stacking on the road
}

-- Helicopter approach lanes. `spawn` is hidden behind a canyon wall; the
-- helicopter climbs vertically to `riseTo`, then flies to hover points
-- picked from the yaw/radius/altitude windows (degrees, + = player's left).
EnemyConfig.AirLanes = {
	AirLeft = {
		spawnX = { -1070, -1040 },
		spawnZ = { -820, -260 },
		spawnY = 45,
		riseTo = 200,
		yaw = { 32, 100 },
		radius = { 300, 500 },
		altitude = { 100, 150 },
	},
	AirRight = {
		spawnX = { 1040, 1070 },
		spawnZ = { -820, -260 },
		spawnY = 45,
		riseTo = 200,
		yaw = { -100, -32 },
		radius = { 300, 500 },
		altitude = { 100, 150 },
	},
	AirCenter = {
		spawnX = { -320, 320 },
		spawnZ = { -1590, -1560 },
		spawnY = 50,
		riseTo = 215,
		yaw = { -50, 50 },
		radius = { 380, 560 },
		altitude = { 105, 160 },
	},
}

EnemyConfig.Helicopter = {
	HEALTH = 300, -- 25 MG hits (~2.3 s on target, just short of overheat)
	RESIST = { Missile = 10, Rocket = 1.2 },
	POINTS = 100,
	RISE_SPEED = 30,
	CRUISE_SPEED = 62,
	ACCELERATION = 28,
	ATTACK_RANGE = 700,
	SALVO_INTERVAL = 7.5,
	SALVO_WARN = 1.2, -- nose dips, searchlight flares before rockets leave
	SALVO_ROCKETS = 4,
	ROCKET_DAMAGE = 1.25,
	REPOSITION_AFTER = { 9, 14 }, -- seconds hovering before moving on
	MIN_CLEARANCE = 55, -- above terrain
	MAX_Z = -40, -- never drifts behind the mesa line
}

-- Jet runs: start (XZ), the aim point the run passes over, altitude.
EnemyConfig.JetRuns = {
	CanyonRun = { from = Vector2.new(0, -2350), jitter = 260, aim = Vector2.new(0, -120), altitude = 230 },
	CrossLeft = { from = Vector2.new(-1750, -1650), jitter = 200, aim = Vector2.new(60, -140), altitude = 220 },
	CrossRight = { from = Vector2.new(1750, -1650), jitter = 200, aim = Vector2.new(-60, -140), altitude = 220 },
}

EnemyConfig.Jet = {
	HEALTH = 150,
	RESIST = { Missile = 10, Rocket = 1 },
	POINTS = 200,
	SPEED = 245,
	RELEASE_DISTANCE = 340, -- horizontal distance from the outpost
	BOMB_DAMAGE = 12,
	BOMB_COUNT = 4,
	CLIMB_RATE = 60, -- studs/s after the release
	EXIT_DISTANCE = 1500, -- despawns this far past the outpost
	MAX_LIFETIME = 22,
}

EnemyConfig.SiegeCrawler = {
	POINTS = 5000,
	WEAK_POINT_POINTS = 1000,
	RESIST = { MG = 0, Missile = 0.3 },
	-- Weak points only take rockets. A direct rocket hit deals 60 to the
	-- part it strikes (the splash of that same rocket is ignored); a near
	-- miss that only splashes credits half to the nearest intact target.
	WEAK_POINT_HEALTH = { TurretLeft = 120, TurretRight = 120, MainCannon = 180 }, -- 2 / 2 / 3 rockets
	CORE_HEALTH = 240, -- 4 rockets
	SPLASH_CREDIT = 0.5,
	SPEED = 5.5, -- ~100 s from the far road to its siege position
	TURN_RATE = 0.12,
	STOP_DISTANCE = 330,
	CANNON_INTERVAL = 11, -- cooldown after each shot
	CANNON_FIRST = 9,
	CANNON_CHARGE = 5.5,
	CANNON_DAMAGE = 20,
	TURRET_INTERVAL = 4.5,
	TURRET_DAMAGE = 1.5,
	TURRET_RANGE = 700,
	CANNON_RANGE = 820, -- harmless while it is still far out
	CRATE_FIRST = 10,
	CRATE_INTERVAL = 17,
	ESCORT_FIRST = 12,
	ESCORT_INTERVAL = 13,
	ESCORT_MAX_LIVE = 9,
	-- Cycled in order; each entry spawns `count` of `kind` on a random lane.
	ESCORTS = {
		{ kind = "Infantry", count = 4, lanes = { "ScrubLeft", "ScrubRight" } },
		{ kind = "Helicopter", count = 1, lanes = { "AirLeft", "AirRight" } },
		{ kind = "Infantry", count = 4, lanes = { "ScrubLeft", "ScrubRight", "Road" } },
		{ kind = "Jet", count = 1, lanes = { "CanyonRun", "CrossLeft", "CrossRight" } },
	},
	DEATH_SEQUENCE = 2.6, -- seconds of chained blasts before the final one
}

return EnemyConfig
