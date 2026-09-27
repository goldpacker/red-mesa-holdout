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
--     (it crosses the horizon ~23-40 s earlier), so an `at` under ~26 s
--     lands as early as the flight allows (~25-26 s). A group larger than
--     one transport's capacity (8 infantry, 2 buggies, 1 tank) flies as a
--     formation, each extra transport trailing by max(`spacing`, 2.5) s.
--   * Helicopter, Jet and SiegeCrawler spawn at `at`, one every `spacing`
--     seconds, as before.
-- Pacing after the airdrop change (AD-3 retune, measured with the QA bots):
--   * each wave opens with its first transport entering at ~0 s (`at` 25)
--     and a second one a few seconds later, so the sky is busy while the
--     first stick descends; groups then touch down every ~6-10 s and the
--     largest group comes last (the peak);
--   * a perfect player never waits more than ~10 s with loads in the air
--     and nothing to shoot; waves 1-9 last ~60-107 s for the perfect-aim bot,
--     a full run ~16 min;
--   * buggies land >= 10 s after a tank touches down, never just before
--     one (waves 5, 7 and 9): the human-like bot's losses came from buggies
--     strafing, and troopers walking in, while it rocketed a tank.
-- `time` selects the lighting preset (TimeOfDay.luau; daylight only:
-- Afternoon, LateAfternoon, Sunset); `crates` lists the seconds at which a
-- supply crate drops. Kinds missing at runtime are skipped with a warning,
-- so waves never hang on unfinished content. Other per-wave fields may be
-- added (e.g. VFX's `weather`).
-- `weather` (VFX-4, client visuals only, no gameplay effect):
--   weather = { storm = { at = <s>, hold = <s>, amount = <0..1> } }
--   a dust storm's wall reaches the outpost `at` seconds into the wave
--   (it appears on the horizon ~38 s earlier), holds `hold` seconds, then
--   clears within ~16 s; `amount` caps Lighting.StormAmount at the peak
--   (client/DustStorm; readability-checked at the wave's preset).
local function g(kind: string, lane: string, count: number, at: number, spacing: number)
	return { kind = kind, lane = lane, count = count, at = at, spacing = spacing }
end

Config.Waves = {
	{ -- 1: learn aiming, the machine gun and overheat
		hint = "INFANTRY ADVANCING",
		time = "Afternoon",
		groups = {
			g("Infantry", "Road", 4, 25, 1.2),
			g("Infantry", "ScrubLeft", 3, 32, 1.2),
			g("Infantry", "Road", 5, 40, 1.0),
			g("Infantry", "ScrubRight", 3, 47, 1.2),
			g("Infantry", "Road", 6, 56, 0.8),
		},
	},
	{ -- 2: traverse the arc; fast targets on the flanks
		hint = "FAST MOVERS ON THE FLANKS",
		time = "Afternoon",
		groups = {
			g("Infantry", "Road", 5, 25, 1.0),
			g("Buggy", "WashLeft", 2, 31, 3),
			g("Infantry", "ScrubLeft", 4, 38, 0.9),
			g("Buggy", "WashRight", 2, 44, 3),
			g("Infantry", "ScrubRight", 4, 51, 0.9),
			g("Buggy", "WashLeft", 1, 57, 1),
			g("Buggy", "WashRight", 1, 59, 1),
			g("Infantry", "Road", 6, 64, 0.7),
		},
	},
	{ -- 3: rockets and basic prioritisation
		hint = "ARMOR INCOMING",
		time = "Afternoon",
		crates = { 20, 50 },
		crateBias = "Rockets",
		weather = { storm = { at = 44, hold = 16, amount = 1 } },
		groups = {
			g("Infantry", "Road", 5, 25, 1.0),
			g("Tank", "Road", 1, 32, 1),
			g("Infantry", "ScrubLeft", 4, 40, 1.0),
			g("Infantry", "ScrubRight", 4, 46, 1.0),
			g("Tank", "Road", 1, 54, 1),
			g("Infantry", "Road", 6, 62, 0.8),
		},
	},
	{ -- 4: AA lock-on and off-screen warnings
		hint = "AIR THREAT",
		time = "LateAfternoon",
		crates = { 32 },
		groups = {
			g("Helicopter", "AirLeft", 1, 10, 1),
			g("Infantry", "Road", 5, 25, 1.0),
			g("Infantry", "ScrubRight", 4, 35, 1.0),
			g("Helicopter", "AirRight", 1, 38, 1),
			g("Infantry", "ScrubLeft", 5, 46, 0.9),
			g("Helicopter", "AirCenter", 1, 54, 1),
			g("Infantry", "Road", 5, 63, 0.8),
		},
	},
	{ -- 5: juggling three ground threats on every lane
		hint = "ALL LANES ACTIVE",
		time = "LateAfternoon",
		crates = { 28, 64 },
		groups = {
			g("Infantry", "Road", 6, 25, 0.9),
			g("Tank", "Road", 1, 31, 1),
			g("Buggy", "WashLeft", 2, 41, 2.5),
			g("Infantry", "ScrubLeft", 5, 45, 0.8),
			g("Buggy", "WashRight", 2, 52, 2.5),
			g("Infantry", "ScrubRight", 5, 57, 0.8),
			g("Tank", "Road", 1, 62, 1),
			g("Buggy", "WashLeft", 1, 72, 1),
			g("Buggy", "WashRight", 1, 74, 1),
			g("Infantry", "Road", 7, 80, 0.6),
		},
	},
	{ -- 6: "look up now" reactions
		hint = "JETS INBOUND",
		time = "LateAfternoon",
		crates = { 25, 55 },
		groups = {
			g("Helicopter", "AirLeft", 1, 8, 1),
			g("Jet", "CanyonRun", 1, 20, 1),
			g("Infantry", "Road", 6, 25, 0.9),
			g("Helicopter", "AirRight", 1, 34, 1),
			g("Infantry", "ScrubRight", 5, 44, 0.8),
			g("Jet", "CrossLeft", 1, 50, 1),
			g("Infantry", "ScrubLeft", 6, 62, 0.7),
			g("Jet", "CrossRight", 1, 70, 1),
		},
	},
	{ -- 7: armored push with rocket scarcity
		hint = "ARMORED PUSH",
		time = "Sunset",
		crates = { 28, 52, 76 },
		crateBias = "Rockets",
		-- capped at 0.8: at 1 the gunsight probe read 2.80-2.92:1 (< 3)
		weather = { storm = { at = 46, hold = 18, amount = 0.8 } },
		groups = {
			g("Jet", "CanyonRun", 1, 10, 1),
			g("Tank", "Road", 1, 25, 1),
			g("Infantry", "Road", 6, 32, 0.8),
			g("Buggy", "WashLeft", 2, 42, 2.5),
			g("Jet", "CrossRight", 1, 48, 1),
			g("Tank", "Road", 1, 52, 1),
			g("Buggy", "WashRight", 2, 64, 2.5),
			g("Tank", "Road", 1, 72, 1),
			g("Infantry", "ScrubLeft", 5, 80, 0.7),
			g("Infantry", "ScrubRight", 5, 82, 0.7),
		},
	},
	{ -- 8: missile scarcity, machine-gun fallback
		hint = "AIR ASSAULT",
		time = "Sunset",
		crates = { 18, 40, 60, 80 },
		crateBias = "Missiles",
		groups = {
			g("Helicopter", "AirLeft", 1, 1, 1),
			g("Helicopter", "AirRight", 1, 8, 1),
			g("Jet", "CanyonRun", 1, 20, 1),
			g("Infantry", "Road", 6, 28, 0.7),
			g("Infantry", "ScrubLeft", 5, 38, 0.7),
			g("Infantry", "ScrubRight", 5, 44, 0.7),
			g("Jet", "CrossLeft", 1, 50, 1),
			g("Helicopter", "AirLeft", 1, 56, 1),
			g("Helicopter", "AirRight", 1, 62, 1),
			g("Jet", "CrossRight", 1, 72, 1),
			g("Infantry", "Road", 8, 82, 0.6),
		},
	},
	{ -- 9: everything at once, from every direction
		hint = "FULL ASSAULT",
		time = "Sunset",
		crates = { 16, 40, 64, 86, 102 },
		groups = {
			g("Helicopter", "AirLeft", 1, 18, 1),
			g("Infantry", "Road", 6, 25, 0.7),
			g("Tank", "Road", 1, 35, 1),
			g("Jet", "CanyonRun", 1, 38, 1),
			g("Buggy", "WashLeft", 1, 48, 1),
			g("Infantry", "ScrubLeft", 3, 50, 0.7),
			g("Helicopter", "AirRight", 1, 54, 1),
			g("Buggy", "WashRight", 1, 56, 1),
			g("Infantry", "ScrubRight", 3, 60, 0.7),
			g("Tank", "Road", 1, 66, 1),
			g("Helicopter", "AirCenter", 1, 74, 1),
			g("Buggy", "WashLeft", 1, 80, 1),
			g("Buggy", "WashRight", 1, 86, 1),
			g("Jet", "CrossRight", 1, 90, 1),
			g("Tank", "Road", 1, 96, 1),
			g("Infantry", "Road", 7, 104, 0.6),
		},
	},
	{ -- 10: the Siege Crawler (it spawns and manages its own escorts)
		hint = "SIEGE CRAWLER",
		time = "Sunset",
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
