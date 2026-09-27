--!strict
-- Airdrop tuning (GAME_SPEC §6.1, docs/AIRDROP_ENVIRONMENT_PLAN.md §1).
-- Owned by the Airdrop workstream. Shared: the server plans sorties from
-- these values; clients only read the per-load times and positions the
-- sortie event carries, never recompute them.
--
-- Timeline of one load (studs, seconds; the basin floor is y ~ 0):
--   the transport flies a straight line at ALTITUDE, entering at t0;
--   the load leaves the ramp at releaseT and falls free for FREE_FALL s,
--   carried CARRY studs forward and dropping FREE_FALL_DROP studs; the
--   canopy opens at openT (openPos) and the load sinks at DESCENT studs/s,
--   drifting sideways onto landPos, which it reaches exactly at landT.

local AirdropConfig = {}

-- Kinds that arrive by air, with their per-transport load and stick.
--   capacity   loads per transport
--   stick      seconds between loads leaving the ramp
--   centre     horizontal distance band (from the outpost) for the stick's
--              centre; every landing point must also fall inside BAND
--   scatter    +/- lateral offset of the stick centre from the lane
--   drift      max random horizontal drift of each load under canopy
--   spacing    min distance between two landing points
--   footprint  radius checked for flat, open ground around a landing point
--   nudge      max distance a bad landing point may be moved
AirdropConfig.KINDS = {
	Infantry = {
		capacity = 8,
		stick = 0.4,
		centre = { 340, 760 },
		scatter = 45,
		drift = 16,
		spacing = 14,
		footprint = 3,
		nudge = 64,
		FREE_FALL = 1.1,
		FREE_FALL_DROP = 26,
		CARRY = 36,
		DESCENT = 17,
	},
	Buggy = {
		capacity = 2,
		stick = 1.2,
		centre = { 380, 760 },
		scatter = 30,
		drift = 10,
		spacing = 36,
		footprint = 6,
		nudge = 56,
		FREE_FALL = 1.4,
		FREE_FALL_DROP = 34,
		CARRY = 46,
		DESCENT = 23,
	},
	Tank = {
		capacity = 1,
		stick = 0,
		-- Beyond the tank's firing distance (EnemyConfig.Tank.FIRE_DISTANCE)
		-- so it drives onto the road before it stops to shoot.
		centre = { 580, 780 },
		scatter = 22,
		drift = 8,
		spacing = 46,
		footprint = 9,
		nudge = 48,
		FREE_FALL = 1.6,
		FREE_FALL_DROP = 40,
		CARRY = 52,
		DESCENT = 21,
	},
}

-- Hard limits for every landing point: horizontal distance from the outpost.
AirdropConfig.BAND = { 300, 800 }

AirdropConfig.Transport = {
	SPEED = 90, -- studs/s
	ALTITUDE = { 250, 350 }, -- above the basin floor (y ~ 0)
	-- Closest approach of the flight line to the outpost (horizontal), so a
	-- transport never passes over the mesa.
	MIN_CLEARANCE = 280,
	-- Planning margin on top of MIN_CLEARANCE.
	CLEARANCE_MARGIN = 12,
	-- How far (degrees) the heading may swing off the tangent to the outpost
	-- at the stick centre; the clearance limit narrows it further.
	MAX_TILT = 45,
	-- Transports enter and leave where their line crosses this box, beyond
	-- the canyon walls (basin interior |x| < 740, far wall z ~ -1340..-1520,
	-- rear cliffs z ~ 150..370).
	BOX_X = 1150,
	BOX_Z = { -1700, 550 },
	-- Groups larger than one load fly in formation: each extra transport
	-- trails by max(group spacing, FORMATION_TRAIL) s, offset sideways.
	FORMATION_TRAIL = 2.5,
	FORMATION_OFFSET = 70,
	FORMATION_CLIMB = 18,
}

-- Landing-point rules (drop-zone sampler, server/AirdropZone).
AirdropConfig.Ground = {
	-- Terrain materials that are open basin floor: sand, coarse sand
	-- patches, the road and the wash beds. Rock, sandstone, limestone and
	-- slate are cliffs, buttes, scree and boulders.
	MATERIALS = { "Sand", "Mud", "Ground", "Salt" },
	-- Basin floor height window: dunes rise ~4.5, wash beds sit ~5.5 down.
	FLOOR_Y = { -9, 9 },
	-- Max ground slope under a load's footprint (vehicles must drive off).
	MAX_SLOPE = 22,
	-- Lane reachability: samples every REACH_STEP studs from the landing
	-- point to its join waypoint must stay on the floor and never rise or
	-- drop more than REACH_MAX_STEP between samples (~37 deg: no cliff or
	-- boulder in the way; a wash bank is ~33 deg).
	REACH_STEP = 3,
	REACH_MAX_STEP = 2.25,
	-- The join waypoint is the first lane waypoint at least this much
	-- closer to the outpost than the landing point.
	JOIN_AHEAD = 40,
	NUDGE_STEP = 8,
	-- Planning attempts per transport before the fallback (loads placed on
	-- their lane at the same distance).
	ATTEMPTS = 10,
}

-- Siege Crawler escorts (ctx.spawn) requested within this many seconds on
-- the same lane share one transport.
AirdropConfig.ESCORT_BATCH = 3.0

-- Client: how long a landed load waits for its replicated enemy before it
-- is removed anyway, and how long a collapsed canopy lingers.
AirdropConfig.HANDOFF_TIMEOUT = 4
AirdropConfig.CANOPY_LINGER = 4

return AirdropConfig
