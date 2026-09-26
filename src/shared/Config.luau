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

Config.Crates = {
	START_HEIGHT = 190,
	FALL_SPEED = 4.2, -- studs/s; ~45 s from drop to touchdown
	DRIFT_SPEED = 14,
	GROUND_HEIGHT = 6,
	LIFETIME = 50,
	MAX_LIVE = 3,
	BIAS_WEIGHT = 0.75, -- chance a biased request yields its bias
	CONTENTS = {
		Rockets = { weight = 40, amount = 3 },
		Missiles = { weight = 35, amount = 2 },
		Repair = { weight = 25, amount = 10 },
	},
}

Config.Timing = {
	WAVE_BANNER = 3,
	INTERMISSION = 12,
	WAVE_MAX_DURATION = 300, -- safety: stragglers are dismissed after this
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

-- Wave definitions (GAME_SPEC §8). Each group spawns `count` enemies of
-- `kind` on `lane` starting at `at` seconds, one every `spacing` seconds.
-- `time` selects the lighting preset (TimeOfDay.luau); `crates` lists the
-- seconds at which a supply crate drops. Kinds missing at runtime are
-- skipped with a warning, so waves never hang on unfinished content.
local function g(kind: string, lane: string, count: number, at: number, spacing: number)
	return { kind = kind, lane = lane, count = count, at = at, spacing = spacing }
end

Config.Waves = {
	{ -- 1: learn aiming, the machine gun and overheat
		hint = "INFANTRY ADVANCING",
		time = "Afternoon",
		groups = {
			g("Infantry", "Road", 4, 1, 1.2),
			g("Infantry", "Road", 5, 14, 1.0),
			g("Infantry", "ScrubLeft", 3, 24, 1.2),
			g("Infantry", "ScrubRight", 3, 30, 1.2),
			g("Infantry", "Road", 6, 40, 0.8),
		},
	},
	{ -- 2: traverse the arc; fast targets on the flanks
		hint = "FAST MOVERS ON THE FLANKS",
		time = "Afternoon",
		groups = {
			g("Infantry", "Road", 5, 1, 1.0),
			g("Buggy", "WashLeft", 2, 10, 3),
			g("Infantry", "ScrubLeft", 4, 18, 0.9),
			g("Buggy", "WashRight", 2, 26, 3),
			g("Infantry", "ScrubRight", 4, 34, 0.9),
			g("Buggy", "WashLeft", 1, 46, 1),
			g("Buggy", "WashRight", 1, 50, 1),
			g("Infantry", "Road", 6, 52, 0.7),
		},
	},
	{ -- 3: rockets and basic prioritisation
		hint = "ARMOR INCOMING",
		time = "Afternoon",
		crates = { 28, 70 },
		groups = {
			g("Infantry", "Road", 5, 1, 1.0),
			g("Tank", "Road", 1, 8, 1),
			g("Infantry", "ScrubLeft", 4, 20, 1.0),
			g("Infantry", "ScrubRight", 4, 26, 1.0),
			g("Tank", "Road", 1, 40, 1),
			g("Infantry", "Road", 6, 50, 0.8),
		},
	},
	{ -- 4: AA lock-on and off-screen warnings
		hint = "AIR THREAT",
		time = "LateAfternoon",
		crates = { 35 },
		groups = {
			g("Infantry", "Road", 5, 1, 1.0),
			g("Helicopter", "AirLeft", 1, 12, 1),
			g("Infantry", "ScrubRight", 4, 22, 1.0),
			g("Helicopter", "AirRight", 1, 34, 1),
			g("Infantry", "ScrubLeft", 5, 44, 0.9),
			g("Helicopter", "AirCenter", 1, 56, 1),
			g("Infantry", "Road", 5, 62, 0.8),
		},
	},
	{ -- 5: juggling three ground threats on every lane
		hint = "ALL LANES ACTIVE",
		time = "Sunset",
		crates = { 30, 75 },
		groups = {
			g("Infantry", "Road", 6, 1, 0.9),
			g("Buggy", "WashLeft", 2, 8, 2.5),
			g("Tank", "Road", 1, 14, 1),
			g("Infantry", "ScrubLeft", 5, 22, 0.8),
			g("Buggy", "WashRight", 2, 30, 2.5),
			g("Infantry", "ScrubRight", 5, 38, 0.8),
			g("Tank", "Road", 1, 48, 1),
			g("Buggy", "WashLeft", 1, 58, 1),
			g("Buggy", "WashRight", 1, 60, 1),
			g("Infantry", "Road", 8, 64, 0.6),
		},
	},
	{ -- 6: "look up now" reactions
		hint = "JETS INBOUND",
		time = "Sunset",
		crates = { 25, 65 },
		groups = {
			g("Infantry", "Road", 6, 1, 0.9),
			g("Helicopter", "AirLeft", 1, 10, 1),
			g("Jet", "CanyonRun", 1, 22, 1),
			g("Infantry", "ScrubRight", 5, 28, 0.8),
			g("Helicopter", "AirRight", 1, 38, 1),
			g("Jet", "CrossLeft", 1, 50, 1),
			g("Infantry", "ScrubLeft", 6, 56, 0.7),
			g("Jet", "CrossRight", 1, 72, 1),
		},
	},
	{ -- 7: armored push with rocket scarcity
		hint = "ARMORED PUSH",
		time = "Sunset",
		crates = { 30, 60, 90 },
		groups = {
			g("Tank", "Road", 1, 1, 1),
			g("Buggy", "WashLeft", 2, 6, 2),
			g("Buggy", "WashRight", 2, 12, 2),
			g("Infantry", "Road", 6, 16, 0.8),
			g("Tank", "Road", 1, 26, 1),
			g("Jet", "CanyonRun", 1, 34, 1),
			g("Tank", "Road", 1, 50, 1),
			g("Buggy", "WashLeft", 1, 56, 1),
			g("Buggy", "WashRight", 1, 58, 1),
			g("Jet", "CrossRight", 1, 66, 1),
			g("Infantry", "ScrubLeft", 5, 70, 0.7),
			g("Infantry", "ScrubRight", 5, 72, 0.7),
		},
	},
	{ -- 8: missile scarcity, machine-gun fallback
		hint = "AIR ASSAULT",
		time = "Dusk",
		crates = { 25, 55, 85 },
		groups = {
			g("Helicopter", "AirLeft", 1, 1, 1),
			g("Helicopter", "AirRight", 1, 6, 1),
			g("Infantry", "Road", 8, 10, 0.6),
			g("Jet", "CanyonRun", 1, 22, 1),
			g("Infantry", "ScrubLeft", 6, 28, 0.6),
			g("Infantry", "ScrubRight", 6, 30, 0.6),
			g("Helicopter", "AirCenter", 1, 40, 1),
			g("Jet", "CrossLeft", 1, 52, 1),
			g("Helicopter", "AirLeft", 1, 60, 1),
			g("Helicopter", "AirRight", 1, 64, 1),
			g("Infantry", "Road", 10, 68, 0.5),
			g("Jet", "CrossRight", 1, 80, 1),
		},
	},
	{ -- 9: everything at once, from every direction
		hint = "FULL ASSAULT",
		time = "Night",
		crates = { 20, 50, 80, 105 },
		groups = {
			g("Infantry", "Road", 8, 1, 0.6),
			g("Buggy", "WashLeft", 2, 6, 2),
			g("Buggy", "WashRight", 2, 8, 2),
			g("Tank", "Road", 1, 12, 1),
			g("Helicopter", "AirLeft", 1, 18, 1),
			g("Infantry", "ScrubLeft", 6, 24, 0.6),
			g("Infantry", "ScrubRight", 6, 26, 0.6),
			g("Jet", "CanyonRun", 1, 34, 1),
			g("Tank", "Road", 1, 42, 1),
			g("Helicopter", "AirRight", 1, 48, 1),
			g("Buggy", "WashLeft", 2, 54, 1.5),
			g("Buggy", "WashRight", 2, 56, 1.5),
			g("Jet", "CrossLeft", 1, 64, 1),
			g("Helicopter", "AirCenter", 1, 72, 1),
			g("Tank", "Road", 1, 76, 1),
			g("Infantry", "Road", 10, 80, 0.5),
			g("Jet", "CrossRight", 1, 92, 1),
		},
	},
	{ -- 10: the Siege Crawler (it spawns and manages its own escorts)
		hint = "SIEGE CRAWLER",
		time = "Night",
		maxDuration = 720,
		crates = { 30, 70 },
		groups = {
			g("SiegeCrawler", "Road", 1, 2, 1),
			g("Infantry", "ScrubLeft", 5, 10, 0.8),
			g("Infantry", "ScrubRight", 5, 14, 0.8),
		},
	},
}

return Config
