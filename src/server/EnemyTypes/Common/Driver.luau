--!strict
-- Ground steering: follows a lane's XZ waypoints with a limited turn rate
-- (pure pursuit), an optional lateral lane offset and weave. Arrival radius
-- scales with the turning circle so a vehicle can never orbit a waypoint.

export type Driver = {
	position: Vector2,
	heading: Vector2,
	waypoint: number,
	finished: boolean,
	step: (self: Driver, dt: number, speed: number, turnRate: number, weave: number?) -> (),
}

local Driver = {}
Driver.__index = Driver

local function perp(v: Vector2): Vector2
	return Vector2.new(-v.Y, v.X)
end

function Driver.new(lane: { Vector2 }, lateral: number, startJitter: Vector2?): Driver
	local start = lane[1] + (startJitter or Vector2.zero)
	local toward = (lane[2] - lane[1]).Unit
	local self = setmetatable({
		lane = lane,
		lateral = lateral,
		position = start + perp(toward) * lateral,
		heading = toward,
		waypoint = 2,
		finished = false,
		stall = 0,
		lastGap = math.huge,
	}, Driver)
	return (self :: any) :: Driver
end

function Driver.target(self: any): Vector2
	local lane = self.lane
	local i = self.waypoint
	local p = lane[i]
	if i >= #lane then
		return p
	end
	local dir = (lane[i + 1] - lane[i - 1]).Unit
	return p + perp(dir) * self.lateral
end

function Driver.step(self: any, dt: number, speed: number, turnRate: number, weave: number?)
	if self.finished then
		return
	end
	local goal = Driver.target(self)
	local toGoal = goal - self.position
	local gap = toGoal.Magnitude
	local arrive = math.max(10, 1.25 * speed / math.max(turnRate, 0.05))
	if self.waypoint >= #self.lane then
		arrive = math.max(4, speed * dt * 1.5)
	end
	if gap <= arrive then
		if self.waypoint >= #self.lane then
			self.finished = true
			return
		end
		self.waypoint += 1
		self.stall = 0
		self.lastGap = math.huge
		return
	end
	-- Safety net: if the gap to the goal stops shrinking, skip ahead.
	if gap < self.lastGap - 0.05 then
		self.stall = 0
	else
		self.stall += dt
		if self.stall > 5 and self.waypoint < #self.lane then
			self.waypoint += 1
			self.stall = 0
		end
	end
	self.lastGap = gap
	local desired = toGoal.Unit
	if weave and weave ~= 0 then
		desired = (desired + perp(desired) * weave).Unit
	end
	local a = math.atan2(self.heading.Y, self.heading.X)
	local b = math.atan2(desired.Y, desired.X)
	local delta = (b - a + math.pi) % (2 * math.pi) - math.pi
	local maxTurn = turnRate * dt
	local n = a + math.clamp(delta, -maxTurn, maxTurn)
	self.heading = Vector2.new(math.cos(n), math.sin(n))
	-- Slow down for tight turns so vehicles don't skid wide.
	local slow = 1 - 0.45 * math.min(1, math.abs(delta) / math.rad(90))
	self.position += self.heading * speed * slow * dt
end

return Driver
