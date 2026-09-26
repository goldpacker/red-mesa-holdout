--!strict
-- Buggy: fast light attack vehicle. Weaves up a dry wash (default
-- WashLeft/WashRight) to mid range, then circles the mesa at 230-320 studs
-- strafing with its pintle gun in short bursts. A machine-gun burst or a
-- well-led rocket kills it.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local EnemyConfig = require(ReplicatedStorage.Shared.EnemyConfig)
local Types = require(script.Parent.Parent.Types)
local Dress = require(script.Parent.Common.Dress)
local Driver = require(script.Parent.Common.Driver)
local GroundModels = require(script.Parent.Common.GroundModels)
local Kit = require(script.Parent.Common.Kit)
local Rig = require(script.Parent.Common.Rig)

local Buggy = {}
Buggy.kind = "Buggy"

local CFG = EnemyConfig.Buggy
local FLIGHT = EnemyConfig.Flight
local PIVOT = Config.TURRET_PIVOT

local function build(): Model
	local asset = Kit.loadAsset("Buggy", { "Root", "WheelFL", "WheelFR", "WheelRL", "WheelRR", "Gun", "Muzzle" })
	if asset then
		Dress.ground(asset)
	end
	local model = asset or GroundModels.buggy()
	model.Name = "Buggy"
	return model
end

-- Live buggies -> flat position, so strafing buggies spread out instead of
-- stacking. Entries whose model left Workspace.Enemies are pruned.
type Slot = { position: Vector2, model: Model }
local pack: { [{}]: Slot } = {}

local function crowded(self: {}, pos: Vector2): boolean
	for other, slot in pack do
		local parent = slot.model.Parent
		if not parent or parent.Name ~= "Enemies" then
			pack[other] = nil
		elseif other ~= self and (slot.position - pos).Magnitude < 22 then
			return true
		end
	end
	return false
end

-- Yaw of a flat position around the outpost (degrees, + = player's left).
local function yawOf(p: Vector2): number
	return math.deg(math.atan2(-(p.X - PIVOT.X), -(p.Y - PIVOT.Z)))
end

local function pointAt(yawDeg: number, radius: number): Vector2
	local y = math.rad(yawDeg)
	return Vector2.new(PIVOT.X - math.sin(y) * radius, PIVOT.Z - math.cos(y) * radius)
end

function Buggy.spawn(ctx: Types.Context, laneName: string, rng: Random): Types.Enemy
	local fallback = if string.find(laneName, "Right") then "WashRight" elseif string.find(laneName, "Left") then "WashLeft" else Kit.pick({ "WashLeft", "WashRight" }, rng)
	local lane = Kit.groundLane(laneName, fallback)
	local model = build()
	local root = Rig.prepare(model, { "Gun", "WheelFL", "WheelFR", "WheelRL", "WheelRR" })
	local rootOffset = Rig.rootOffset(root)
	local gunLocal, muzzleLocal = Kit.moverFrames(model, "Gun", "Muzzle")

	local driver = Driver.new(lane, rng:NextNumber(-8, 8), Vector2.new(rng:NextNumber(-8, 8), rng:NextNumber(-12, 12)))
	local enemy: Types.Enemy = {
		id = 0,
		kind = "Buggy",
		model = model,
		root = root,
		health = CFG.HEALTH,
		maxHealth = CFG.HEALTH,
		dead = false,
		points = CFG.POINTS,
		isAir = false,
	}

	local state = "Drive"
	local clock = rng:NextNumber(0, 10)
	local burstTimer = rng:NextNumber(0.8, 1.6)
	local frame = CFrame.identity
	local heading = driver.heading
	local position = driver.position
	-- Strafing state: orbit toward a target yaw at a target radius.
	local targetYaw = 0
	local radius = 0
	local targetRadius = 0
	local token = {}
	local spreadCooldown = 0

	local function place(pos: Vector2, dir: Vector2, bank: number)
		frame = Kit.groundFrame(pos, dir, 4.5, 2.6, CFG.RIDE_HEIGHT) * CFrame.Angles(0, 0, bank)
		root.CFrame = frame * rootOffset
		pack[token] = { position = pos, model = model }
	end
	place(position, heading, 0)
	model:SetAttribute("State", "Drive")

	local function pickStrafeTarget()
		local current = yawOf(position)
		local limit = CFG.STRAFE_YAW_LIMIT
		for _ = 1, 8 do
			local candidate = rng:NextNumber(-limit, limit)
			if math.abs(candidate - current) >= 45 then
				targetYaw = candidate
				break
			end
		end
		targetRadius = rng:NextNumber(CFG.STRAFE_RADIUS[1], CFG.STRAFE_RADIUS[2])
	end

	local function burst()
		local yaw = Kit.aimYaw(frame, gunLocal, PIVOT)
		local from = Kit.muzzleWorld(frame, gunLocal, muzzleLocal, yaw)
		local to = Kit.impactPoint(from, rng)
		ctx.enemyFired(enemy, "BuggyBurst", from, to)
		local at = frame.Position
		task.delay(FLIGHT.BUGGY_ROUND + 0.3, function()
			if not enemy.dead then
				ctx.damageOutpost(CFG.BURST_DAMAGE, at, false)
			end
		end)
	end

	local function drive(dt: number)
		clock += dt
		local weave = math.sin(clock * CFG.WEAVE_FREQUENCY * 2 * math.pi) * (CFG.WEAVE_AMPLITUDE / 18)
		driver:step(dt, CFG.SPEED, CFG.TURN_RATE, weave)
		local bank = math.clamp(-weave * 0.12, -0.1, 0.1)
		position, heading = driver.position, driver.heading
		place(position, heading, bank)
		if Kit.outpostDistance(frame.Position) <= CFG.ENGAGE_RANGE or driver.finished then
			state = "Strafe"
			model:SetAttribute("State", "Strafe")
			local offset = position - Vector2.new(PIVOT.X, PIVOT.Z)
			radius = math.clamp(offset.Magnitude, CFG.STRAFE_RADIUS[1] * 0.8, CFG.STRAFE_RADIUS[2] * 1.2)
			pickStrafeTarget()
		end
	end

	local function strafe(dt: number)
		local currentYaw = yawOf(position)
		spreadCooldown -= dt
		if spreadCooldown <= 0 and crowded(token, position) then
			-- Too close to another buggy: peel off to a new line and range.
			spreadCooldown = 2.5
			pickStrafeTarget()
			targetRadius = math.clamp(radius + (if rng:NextNumber() < 0.5 then -40 else 40), CFG.STRAFE_RADIUS[1], CFG.STRAFE_RADIUS[2] + 30)
		end
		local delta = targetYaw - currentYaw
		if math.abs(delta) < 4 then
			pickStrafeTarget()
			delta = targetYaw - currentYaw
		end
		radius += math.clamp(targetRadius - radius, -8 * dt, 8 * dt)
		local stepDeg = math.deg(CFG.STRAFE_SPEED * dt / radius)
		local newYaw = math.clamp(currentYaw + math.clamp(delta, -stepDeg, stepDeg), -CFG.STRAFE_YAW_LIMIT, CFG.STRAFE_YAW_LIMIT)
		local goal = pointAt(newYaw, radius)
		local move = goal - position
		-- Ease the heading toward the direction of travel so it drifts, not snaps.
		if move.Magnitude > 1e-3 then
			heading = Kit.turnToward(heading, move, CFG.TURN_RATE * dt)
		end
		position = position + heading * math.min(move.Magnitude, CFG.STRAFE_SPEED * dt * 1.3)
		place(position, heading, if delta > 0 then -0.06 else 0.06)
	end

	function enemy.update(dt: number)
		if state == "Drive" then
			drive(dt)
		else
			strafe(dt)
		end
		local distance = Kit.outpostDistance(frame.Position)
		if distance <= CFG.GUN_RANGE and Kit.inArc(frame.Position) then
			burstTimer -= dt
			if burstTimer <= 0 then
				burstTimer = CFG.BURST_INTERVAL * rng:NextNumber(0.8, 1.2)
				burst()
			end
		end
	end

	function enemy.isThreatening(): boolean
		return Kit.outpostDistance(frame.Position) <= CFG.GUN_RANGE
	end

	function enemy.distanceToOutpost(): number
		return Kit.outpostDistance(frame.Position)
	end

	function enemy.die()
		pack[token] = nil
		model:SetAttribute("State", "Dead")
		Kit.char(model)
		-- The blast flips it onto its side, thrown a little along its travel.
		local flip = if rng:NextNumber() < 0.5 then 1 else -1
		root.CFrame = frame * CFrame.new(flip * 1.5, 1.2, -3) * CFrame.Angles(math.rad(rng:NextNumber(-10, 10)), 0, math.rad(95 * flip)) * rootOffset
		Kit.toWrecks(model, "Dead", 0.8)
	end

	return enemy
end

return Buggy
