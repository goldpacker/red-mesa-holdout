--!strict
-- Tank: slow and heavily armoured. Grinds up its lane (default Road) to a
-- firing position, then every few seconds swings its turret onto the
-- outpost (telegraph: "TankAim", State "Aim") and fires a heavy shell.
-- Machine gun is nearly useless (resist 0.03); about two rockets kill it.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local EnemyConfig = require(ReplicatedStorage.Shared.EnemyConfig)
local Types = require(script.Parent.Parent.Types)
local Driver = require(script.Parent.Common.Driver)
local GroundModels = require(script.Parent.Common.GroundModels)
local Kit = require(script.Parent.Common.Kit)
local Rig = require(script.Parent.Common.Rig)

local Tank = {}
Tank.kind = "Tank"

local CFG = EnemyConfig.Tank
local FLIGHT = EnemyConfig.Flight

-- Live tanks -> ground position, for road spacing. Entries whose model
-- has left Workspace.Enemies (killed, dismissed, cleared) are pruned.
type Slot = { position: Vector2, model: Model }
local convoy: { [{}]: Slot } = {}

local function prune()
	for token, slot in convoy do
		local parent = slot.model.Parent
		if not parent or parent.Name ~= "Enemies" then
			convoy[token] = nil
		end
	end
end

local function build(): (Model, BasePart)
	local model = Kit.loadAsset("Tank", { "Root", "Turret", "Barrel", "Muzzle" }) or GroundModels.tank()
	model.Name = "Tank"
	local root = Rig.prepare(model, { "Turret" })
	return model, root
end

-- True if another tank sits just ahead (closer to the outpost) of `pos`.
local function blocked(self: {}, pos: Vector2, heading: Vector2): boolean
	prune()
	for other, slot in convoy do
		if other ~= self then
			local d = slot.position - pos
			if d.Magnitude < CFG.SPACING and d:Dot(heading) > 0 then
				return true
			end
		end
	end
	return false
end

function Tank.spawn(ctx: Types.Context, laneName: string, rng: Random): Types.Enemy
	local lane = Kit.groundLane(laneName, "Road")
	local model, root = build()
	local rootOffset = Rig.rootOffset(root)
	local turretLocal, muzzleLocal = Kit.moverFrames(model, "Turret", "Muzzle")

	prune()
	local count = 0
	for _ in convoy do
		count += 1
	end
	local lateral = (if count % 2 == 0 then -1 else 1) * rng:NextNumber(2, CFG.LATERAL_JITTER)
	local driver = Driver.new(lane, lateral, Vector2.new(rng:NextNumber(-4, 4), rng:NextNumber(-8, 8)))
	local health = CFG.HEALTH

	local enemy: Types.Enemy = {
		id = 0,
		kind = "Tank",
		model = model,
		root = root,
		health = health,
		maxHealth = health,
		dead = false,
		points = CFG.POINTS,
		isAir = false,
		resist = CFG.RESIST,
	}
	local token = {}

	local stopDistance = rng:NextNumber(CFG.FIRE_DISTANCE[1], CFG.FIRE_DISTANCE[2])
	local state = "Drive"
	local timer = 0
	local cooldown = rng:NextNumber(1.2, 2.5)
	local blockedFor = 0
	local ignoreBlockFor = 0
	local frame = CFrame.identity

	local function place()
		frame = Kit.groundFrame(driver.position, driver.heading, 10, 5, 0)
		root.CFrame = frame * rootOffset
		convoy[token] = { position = driver.position, model = model }
	end
	place()

	local function setState(s: string)
		state = s
		model:SetAttribute("State", s)
	end
	setState("Drive")

	local function muzzle(): Vector3
		local yaw = Kit.aimYaw(frame, turretLocal, Config.TURRET_PIVOT)
		return Kit.muzzleWorld(frame, turretLocal, muzzleLocal, yaw)
	end

	local function fire()
		local from = muzzle()
		local to = Kit.impactPoint(from, rng)
		ctx.enemyFired(enemy, "Shell", from, to)
		local position = frame.Position
		task.delay(FLIGHT.TANK_SHELL, function()
			ctx.damageOutpost(CFG.SHELL_DAMAGE, position, true)
		end)
	end

	function enemy.update(dt: number)
		if state == "Drive" then
			local distance = Kit.outpostDistance(frame.Position)
			if distance <= stopDistance or driver.finished then
				setState("Hold")
				return
			end
			ignoreBlockFor = math.max(0, ignoreBlockFor - dt)
			if ignoreBlockFor <= 0 and blocked(token, driver.position, driver.heading) then
				blockedFor += dt
				if blockedFor > 4 then
					-- Pull out beside the tank ahead rather than queueing forever.
					(driver :: any).lateral = -((driver :: any).lateral :: number) + (if lateral > 0 then -6 else 6)
					blockedFor = 0
					ignoreBlockFor = 6
				end
				return
			end
			blockedFor = 0
			driver:step(dt, CFG.SPEED, CFG.TURN_RATE)
			place()
			return
		end

		timer -= dt
		if state == "Aim" then
			if timer <= 0 then
				fire()
				setState("Fire")
				timer = 0.6
			end
		elseif state == "Fire" then
			if timer <= 0 then
				setState("Hold")
				cooldown = CFG.FIRE_INTERVAL * rng:NextNumber(0.85, 1.15)
			end
		else -- Hold
			cooldown -= dt
			if cooldown <= 0 and Kit.inArc(frame.Position) then
				setState("Aim")
				timer = CFG.AIM_TIME
				ctx.enemyFired(enemy, "TankAim", muzzle(), Config.TURRET_PIVOT)
			end
		end
	end

	function enemy.isThreatening(): boolean
		return state ~= "Drive" or Kit.outpostDistance(frame.Position) <= stopDistance + 60
	end

	function enemy.distanceToOutpost(): number
		return Kit.outpostDistance(frame.Position)
	end

	function enemy.die()
		convoy[token] = nil
		model:SetAttribute("State", "Dead")
		-- The turret cooks off and is thrown clear.
		local turret = Kit.detach(model, "Turret")
		if turret then
			Kit.char(turret)
			turret:SetAttribute("FxScale", 0.6)
			turret:SetAttribute("State", "Thrown")
			local yaw = rng:NextNumber(0, math.pi * 2)
			local velocity = Vector3.new(math.cos(yaw) * 10, rng:NextNumber(38, 48), math.sin(yaw) * 10)
			local spin = Vector3.new(rng:NextNumber(-2, 2), rng:NextNumber(-3, 3), rng:NextNumber(-2, 2))
			Kit.fling(turret, velocity, spin, "Debris")
		end
		root.CFrame = root.CFrame * CFrame.Angles(math.rad(rng:NextNumber(-3, 3)), 0, math.rad(rng:NextNumber(-4, 4)))
		Kit.char(model)
		Kit.toWrecks(model, "Dead", 1.4)
	end

	return enemy
end

return Tank
