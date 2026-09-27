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
	GRENADE_DAMAGE = 4,
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

-- Wave definitions (GAME_SPEC §8). Each group brings `count` enemies of
-- `kind` for `lane`, `at` seconds into the wave:
--   * Infantry, Buggy and Tank arrive by airdrop (server/Airdrop,
--     shared/AirdropConfig): `at` is the group's FIRST TOUCHDOWN (+/- 1.5 s
--     jitter), 300-800 studs out near `lane`; the rest of its stick lands
--     over the next few seconds. The transport is timed backward from it
--     (it crosses the horizon ~22-40 s earlier), so an `at` under ~30 s
--     may land a little later, as early as the flight allows. A group
--     larger than one transport's capacity (8 infantry, 2 buggies, 1 tank)
--     flies as a formation, each extra transport trailing by
--     max(`spacing`, 2.5) s.
--     (AD-1 fix: these `at` values are the old transport-entry times
--     + 28 s, the old average entry -> first touchdown of 28.7 s.)
--   * Helicopter, Jet and SiegeCrawler spawn at `at`, one every `spacing`
--     seconds, as before.
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
			g("Infantry", "Road", 4, 29, 1.2),
			g("Infantry", "Road", 5, 42, 1.0),
			g("Infantry", "ScrubLeft", 3, 52, 1.2),
			g("Infantry", "ScrubRight", 3, 58, 1.2),
			g("Infantry", "Road", 6, 68, 0.8),
		},
	},
	{ -- 2: traverse the arc; fast targets on the flanks
		hint = "FAST MOVERS ON THE FLANKS",
		time = "Afternoon",
		groups = {
			g("Infantry", "Road", 5, 29, 1.0),
			g("Buggy", "WashLeft", 2, 38, 3),
			g("Infantry", "ScrubLeft", 4, 46, 0.9),
			g("Buggy", "WashRight", 2, 54, 3),
			g("Infantry", "ScrubRight", 4, 62, 0.9),
			g("Buggy", "WashLeft", 1, 74, 1),
			g("Buggy", "WashRight", 1, 78, 1),
			g("Infantry", "Road", 6, 80, 0.7),
		},
	},
	{ -- 3: rockets and basic prioritisation
		hint = "ARMOR INCOMING",
		time = "Afternoon",
		crates = { 24, 60 },
		crateBias = "Rockets",
		groups = {
			g("Infantry", "Road", 5, 29, 1.0),
			g("Tank", "Road", 1, 36, 1),
			g("Infantry", "ScrubLeft", 4, 48, 1.0),
			g("Infantry", "ScrubRight", 4, 54, 1.0),
			g("Tank", "Road", 1, 68, 1),
			g("Infantry", "Road", 6, 78, 0.8),
		},
	},
	{ -- 4: AA lock-on and off-screen warnings
		hint = "AIR THREAT",
		time = "LateAfternoon",
		crates = { 35 },
		groups = {
			g("Infantry", "Road", 5, 29, 1.0),
			g("Helicopter", "AirLeft", 1, 12, 1),
			g("Infantry", "ScrubRight", 4, 50, 1.0),
			g("Helicopter", "AirRight", 1, 34, 1),
			g("Infantry", "ScrubLeft", 5, 72, 0.9),
			g("Helicopter", "AirCenter", 1, 56, 1),
			g("Infantry", "Road", 5, 90, 0.8),
		},
	},
	{ -- 5: juggling three ground threats on every lane
		hint = "ALL LANES ACTIVE",
		time = "Sunset",
		crates = { 30, 75 },
		groups = {
			g("Infantry", "Road", 6, 29, 0.9),
			g("Buggy", "WashLeft", 2, 36, 2.5),
			g("Tank", "Road", 1, 42, 1),
			g("Infantry", "ScrubLeft", 5, 50, 0.8),
			g("Buggy", "WashRight", 2, 58, 2.5),
			g("Infantry", "ScrubRight", 5, 66, 0.8),
			g("Tank", "Road", 1, 76, 1),
			g("Buggy", "WashLeft", 1, 86, 1),
			g("Buggy", "WashRight", 1, 88, 1),
			g("Infantry", "Road", 8, 92, 0.6),
		},
	},
	{ -- 6: "look up now" reactions
		hint = "JETS INBOUND",
		time = "Sunset",
		crates = { 25, 65 },
		groups = {
			g("Infantry", "Road", 6, 29, 0.9),
			g("Helicopter", "AirLeft", 1, 10, 1),
			g("Jet", "CanyonRun", 1, 22, 1),
			g("Infantry", "ScrubRight", 5, 56, 0.8),
			g("Helicopter", "AirRight", 1, 38, 1),
			g("Jet", "CrossLeft", 1, 50, 1),
			g("Infantry", "ScrubLeft", 6, 84, 0.7),
			g("Jet", "CrossRight", 1, 72, 1),
		},
	},
	{ -- 7: armored push with rocket scarcity
		hint = "ARMORED PUSH",
		time = "Sunset",
		crates = { 30, 60, 90 },
		crateBias = "Rockets",
		groups = {
			g("Tank", "Road", 1, 29, 1),
			g("Buggy", "WashLeft", 2, 34, 2),
			g("Buggy", "WashRight", 2, 40, 2),
			g("Infantry", "Road", 6, 44, 0.8),
			g("Tank", "Road", 1, 54, 1),
			g("Jet", "CanyonRun", 1, 34, 1),
			g("Tank", "Road", 1, 78, 1),
			g("Buggy", "WashLeft", 1, 84, 1),
			g("Buggy", "WashRight", 1, 86, 1),
			g("Jet", "CrossRight", 1, 66, 1),
			g("Infantry", "ScrubLeft", 5, 98, 0.7),
			g("Infantry", "ScrubRight", 5, 100, 0.7),
		},
	},
	{ -- 8: missile scarcity, machine-gun fallback
		hint = "AIR ASSAULT",
		time = "Dusk",
		crates = { 20, 45, 70, 95 },
		crateBias = "Missiles",
		groups = {
			g("Helicopter", "AirLeft", 1, 1, 1),
			g("Helicopter", "AirRight", 1, 8, 1),
			g("Infantry", "Road", 6, 40, 0.7),
			g("Jet", "CanyonRun", 1, 24, 1),
			g("Infantry", "ScrubLeft", 5, 58, 0.7),
			g("Infantry", "ScrubRight", 5, 62, 0.7),
			g("Jet", "CrossLeft", 1, 52, 1),
			g("Helicopter", "AirLeft", 1, 60, 1),
			g("Helicopter", "AirRight", 1, 66, 1),
			g("Infantry", "Road", 8, 98, 0.6),
			g("Jet", "CrossRight", 1, 84, 1),
		},
	},
	{ -- 9: everything at once, from every direction
		hint = "FULL ASSAULT",
		time = "Night",
		crates = { 18, 42, 66, 90, 110 },
		groups = {
			g("Infantry", "Road", 6, 29, 0.7),
			g("Buggy", "WashLeft", 1, 34, 1),
			g("Buggy", "WashRight", 1, 37, 1),
			g("Tank", "Road", 1, 40, 1),
			g("Helicopter", "AirLeft", 1, 20, 1),
			g("Infantry", "ScrubLeft", 4, 54, 0.7),
			g("Infantry", "ScrubRight", 4, 58, 0.7),
			g("Jet", "CanyonRun", 1, 38, 1),
			g("Tank", "Road", 1, 74, 1),
			g("Helicopter", "AirRight", 1, 52, 1),
			g("Buggy", "WashLeft", 1, 86, 1),
			g("Buggy", "WashRight", 1, 90, 1),
			g("Helicopter", "AirCenter", 1, 74, 1),
			g("Tank", "Road", 1, 108, 1),
			g("Buggy", "WashLeft", 1, 112, 1),
			g("Infantry", "Road", 8, 114, 0.6),
			g("Jet", "CrossRight", 1, 96, 1),
		},
	},
	{ -- 10: the Siege Crawler (it spawns and manages its own escorts)
		hint = "SIEGE CRAWLER",
		time = "Night",
		maxDuration = 720,
		crates = { 30, 70 },
		groups = {
			g("SiegeCrawler", "Road", 1, 2, 1),
			g("Infantry", "ScrubLeft", 5, 38, 0.8),
			g("Infantry", "ScrubRight", 5, 42, 0.8),
		},
	},
}

return Config
