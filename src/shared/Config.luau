--!strict
-- Tuning values and battlefield geometry shared by server and client.
-- World axes: the mesa sits at the origin, the basin opens toward -Z.

local Config = {}

-- The gun sits on a small bunker atop the mesa's highest knob so it can see
-- down the terraced slopes to the foot of the mesa.
Config.TURRET_PIVOT = Vector3.new(0, 72, 0)
Config.MESA_TOP = 60
Config.FORWARD = Vector3.new(0, 0, -1)
Config.MUZZLE_OFFSET = 6

-- Aim limits (degrees). Yaw is measured from FORWARD, positive = turn left.
Config.YAW_LIMIT = 135
Config.PITCH_MIN = -45
Config.PITCH_MAX = 65

Config.Camera = {
	THIRD_PERSON_BACK = 13,
	THIRD_PERSON_UP = 8,
	FOV_DEFAULT = 70,
	FOV_AIM = 32,
	SENSITIVITY = 0.22, -- degrees per pixel
	SENSITIVITY_AIM = 0.09,
}

Config.MachineGun = {
	FIRE_INTERVAL = 0.09,
	DAMAGE = 12,
	HEADSHOT_MULTIPLIER = 2,
	SPREAD_DEG = 0.5,
	RANGE = 1600,
	HEAT_PER_SHOT = 3.2,
	COOL_RATE = 38, -- heat per second when not firing
	COOL_DELAY = 0.18,
	OVERHEAT_LOCK = 2.0,
	MAX_HEAT = 100,
}

Config.Integrity = {
	MAX = 100,
	INTERMISSION_REPAIR = 25,
	LOW_THRESHOLD = 30,
	ALARM_THRESHOLD = 15,
}

Config.Infantry = {
	HEALTH = 20,
	SPEED = 10.5,
	RIFLE_RANGE = 340,
	RIFLE_INTERVAL = 3.2,
	RIFLE_DAMAGE = 1,
	GRENADE_RANGE = 95, -- horizontal distance from mesa centre
	GRENADE_INTERVAL = 4.5,
	GRENADE_DAMAGE = 5,
	GRENADE_FLIGHT = 1.3,
	POINTS = 10,
}

Config.Score = {
	COMBO_WINDOW = 3,
	MAX_MULTIPLIER = 4,
	WAVE_CLEAR_BONUS = 500,
	INTEGRITY_BONUS_PER_POINT = 10,
}

Config.Timing = {
	WAVE_BANNER = 3,
	INTERMISSION = 12,
	WAVE_MAX_DURATION = 240, -- safety: stragglers are dismissed after this
}

-- Lanes are lists of XZ waypoints from spawn toward the mesa.
Config.Lanes = {
	Road = {
		Vector2.new(-40, -900),
		Vector2.new(60, -720),
		Vector2.new(-30, -540),
		Vector2.new(40, -360),
		Vector2.new(0, -190),
		Vector2.new(0, -92),
	},
	ScrubLeft = {
		Vector2.new(-260, -860),
		Vector2.new(-200, -620),
		Vector2.new(-150, -400),
		Vector2.new(-90, -200),
		Vector2.new(-50, -85),
	},
	ScrubRight = {
		Vector2.new(260, -860),
		Vector2.new(210, -620),
		Vector2.new(150, -400),
		Vector2.new(90, -200),
		Vector2.new(50, -85),
	},
	WashLeft = {
		Vector2.new(-620, -760),
		Vector2.new(-500, -520),
		Vector2.new(-380, -300),
		Vector2.new(-240, -150),
		Vector2.new(-90, -40),
	},
	WashRight = {
		Vector2.new(620, -760),
		Vector2.new(500, -520),
		Vector2.new(380, -300),
		Vector2.new(240, -150),
		Vector2.new(90, -40),
	},
}

-- Wave definitions. Each group spawns `count` enemies of `kind` on `lane`
-- starting at `at` seconds, one every `spacing` seconds.
Config.Waves = {
	{
		hint = "INFANTRY ADVANCING",
		groups = {
			{ kind = "Infantry", lane = "Road", count = 4, at = 1, spacing = 1.2 },
			{ kind = "Infantry", lane = "Road", count = 5, at = 14, spacing = 1.0 },
			{ kind = "Infantry", lane = "ScrubLeft", count = 3, at = 24, spacing = 1.2 },
			{ kind = "Infantry", lane = "ScrubRight", count = 3, at = 30, spacing = 1.2 },
			{ kind = "Infantry", lane = "Road", count = 6, at = 40, spacing = 0.8 },
		},
	},
	{
		hint = "FLANKS ACTIVE",
		groups = {
			{ kind = "Infantry", lane = "Road", count = 5, at = 1, spacing = 1.0 },
			{ kind = "Infantry", lane = "WashLeft", count = 4, at = 10, spacing = 1.0 },
			{ kind = "Infantry", lane = "WashRight", count = 4, at = 18, spacing = 1.0 },
			{ kind = "Infantry", lane = "ScrubLeft", count = 4, at = 28, spacing = 0.9 },
			{ kind = "Infantry", lane = "ScrubRight", count = 4, at = 32, spacing = 0.9 },
			{ kind = "Infantry", lane = "Road", count = 8, at = 44, spacing = 0.7 },
		},
	},
}

return Config
