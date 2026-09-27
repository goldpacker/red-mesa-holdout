--!strict
-- Where an air-dropped enemy joins its lane (AD-1). Pure lane maths shared
-- by the drop-zone sampler and the enemy types' landing entry
-- (`opts.landAt` in EnemyTypes/{Infantry,Buggy,Tank}): a landed enemy
-- heads for the first waypoint of its lane that is clearly closer to the
-- mesa than where it touched down, then follows the lane as before.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AirdropConfig = require(ReplicatedStorage.Shared.AirdropConfig)
local Config = require(ReplicatedStorage.Shared.Config)

local AirdropLanding = {}

local PIVOT = Vector2.new(Config.TURRET_PIVOT.X, Config.TURRET_PIVOT.Z)

function AirdropLanding.distance(p: Vector2): number
	return (p - PIVOT).Magnitude
end

-- Index (>= 2) of the first waypoint at least JOIN_AHEAD studs closer to
-- the outpost than `p`; the lane's last waypoint if there is none.
function AirdropLanding.joinIndex(lane: { Vector2 }, p: Vector2): number
	local d = AirdropLanding.distance(p)
	for i = 2, #lane do
		if AirdropLanding.distance(lane[i]) <= d - AirdropConfig.Ground.JOIN_AHEAD then
			return i
		end
	end
	return #lane
end

-- Flat unit direction from `p` toward its join waypoint: the way a landed
-- enemy faces when it takes over from the descent visual.
function AirdropLanding.facing(lane: { Vector2 }, p: Vector2): Vector2
	local toward = lane[AirdropLanding.joinIndex(lane, p)] - p
	if toward.Magnitude < 1e-3 then
		toward = PIVOT - p
	end
	return if toward.Magnitude > 1e-3 then toward.Unit else Vector2.new(0, 1)
end

-- Moves a fresh Driver (EnemyTypes/Common/Driver) onto a landing point:
-- it starts there, facing its join waypoint, and steers for it next.
function AirdropLanding.placeDriver(driver: any, landAt: Vector3)
	local p = Vector2.new(landAt.X, landAt.Z)
	driver.position = p
	driver.waypoint = AirdropLanding.joinIndex(driver.lane, p)
	driver.heading = AirdropLanding.facing(driver.lane, p)
end

return AirdropLanding
