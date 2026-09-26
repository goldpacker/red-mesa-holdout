--!strict
-- Helicopter: rises from behind a flank canyon wall (AirLeft / AirRight)
-- or the far wall (AirCenter), flies in to hover at mid range out on the
-- flank of the player's view, and fires telegraphed rocket salvos
-- ("SalvoWarn" then "RocketSalvo"). Repositions between salvos. One AA
-- missile (resist Missile = 10) or a long machine-gun burst kills it; it
-- then spins down trailing smoke and crashes into a burning wreck.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Config = require(ReplicatedStorage.Shared.Config)
local EnemyConfig = require(ReplicatedStorage.Shared.EnemyConfig)
local Types = require(script.Parent.Parent.Types)
local AirModels = require(script.Parent.Common.AirModels)
local Kit = require(script.Parent.Common.Kit)
local Rig = require(script.Parent.Common.Rig)

local Helicopter = {}
Helicopter.kind = "Helicopter"

local CFG = EnemyConfig.Helicopter
local FLIGHT = EnemyConfig.Flight
local PIVOT = Config.TURRET_PIVOT

local function build(): Model
	local model = Kit.loadAsset("Helicopter", { "Root", "MainRotor", "TailRotor", "RocketMuzzleL", "RocketMuzzleR" })
		or AirModels.helicopter()
	model.Name = "Helicopter"
	return model
end

local function laneFor(name: string, rng: Random): any
	local lanes = EnemyConfig.AirLanes :: any
	if lanes[name] then
		return lanes[name]
	end
	if string.find(name, "Right") then
		return lanes.AirRight
	elseif string.find(name, "Left") then
		return lanes.AirLeft
	elseif string.find(name, "Center") or string.find(name, "Road") then
		return lanes.AirCenter
	end
	return if rng:NextNumber() < 0.5 then lanes.AirLeft else lanes.AirRight
end

local function range(r: { number }, rng: Random): number
	return rng:NextNumber(r[1], r[2])
end

-- A hover point inside the lane's window, clear of terrain and in the arc.
local function hoverPoint(lane: any, rng: Random): Vector3
	for _ = 1, 12 do
		local yaw = math.rad(range(lane.yaw, rng))
		local r = range(lane.radius, rng)
		local x = PIVOT.X - math.sin(yaw) * r
		local z = math.min(PIVOT.Z - math.cos(yaw) * r, CFG.MAX_Z)
		local ground = Kit.groundY(x, z)
		local y = math.max(range(lane.altitude, rng), ground + CFG.MIN_CLEARANCE)
		local p = Vector3.new(x, y, z)
		if Kit.inArc(p) then
			return p
		end
	end
	return Vector3.new(0, 130, -420)
end

function Helicopter.spawn(ctx: Types.Context, laneName: string, rng: Random): Types.Enemy
	local lane = laneFor(laneName, rng)
	local model = build()
	local root = Rig.prepare(model, { "MainRotor", "TailRotor" })
	local rootOffset = Rig.rootOffset(root)
	local ground = model:GetPivot()
	local muzzles: { CFrame } = {}
	for _, name in { "RocketMuzzleL", "RocketMuzzleR" } do
		local a = model:FindFirstChild(name, true)
		if a and a:IsA("Attachment") then
			table.insert(muzzles, ground:ToObjectSpace(a.WorldCFrame))
		end
	end
	if #muzzles == 0 then
		muzzles = { CFrame.new(-4, -1.5, -3), CFrame.new(4, -1.5, -3) }
	end

	local position = Vector3.new(range(lane.spawnX, rng), lane.spawnY, range(lane.spawnZ, rng))
	local velocity = Vector3.zero
	local yaw = math.atan2(-(PIVOT.X - position.X), -(PIVOT.Z - position.Z)) -- facing the mesa
	local frame = CFrame.new(position) * CFrame.Angles(0, yaw, 0)
	root.CFrame = frame * rootOffset

	local enemy: Types.Enemy = {
		id = 0,
		kind = "Helicopter",
		model = model,
		root = root,
		health = CFG.HEALTH,
		maxHealth = CFG.HEALTH,
		dead = false,
		points = CFG.POINTS,
		isAir = true,
		resist = CFG.RESIST,
	}

	local state = "Rise"
	local timer = 0
	local hoverFor = 0
	local salvoTimer = rng:NextNumber(1.5, 3)
	local target = hoverPoint(lane, rng)
	local tilt = CFrame.identity
	model:SetAttribute("State", state)

	local function setState(s: string)
		state = s
		model:SetAttribute("State", s)
	end

	local function steer(dt: number, goal: Vector3, maxSpeed: number)
		local toGoal = goal - position
		local distance = toGoal.Magnitude
		-- Arrive: slow down inside the braking distance.
		local desiredSpeed = math.min(maxSpeed, math.sqrt(2 * CFG.ACCELERATION * distance))
		local desired = if distance > 0.5 then toGoal.Unit * desiredSpeed else Vector3.zero
		local dv = desired - velocity
		local maxDv = CFG.ACCELERATION * dt
		if dv.Magnitude > maxDv then
			dv = dv.Unit * maxDv
		end
		velocity += dv
		position += velocity * dt
		-- Keep clear of terrain.
		local floor = Kit.groundY(position.X, position.Z) + CFG.MIN_CLEARANCE * 0.6
		if state ~= "Rise" and position.Y < floor then
			position = Vector3.new(position.X, floor, position.Z)
		end
	end

	local function orient(dt: number, faceOutpost: boolean)
		local desiredYaw = yaw
		local flat = Vector2.new(velocity.X, velocity.Z)
		if faceOutpost or flat.Magnitude < 8 then
			desiredYaw = math.atan2(-(PIVOT.X - position.X), -(PIVOT.Z - position.Z))
		else
			desiredYaw = math.atan2(-flat.X, -flat.Y)
		end
		local delta = (desiredYaw - yaw + math.pi) % (2 * math.pi) - math.pi
		yaw += math.clamp(delta, -1.4 * dt, 1.4 * dt)
		-- Pitch nose-down with forward speed, roll into sideways motion.
		local basis = CFrame.Angles(0, yaw, 0)
		local localVel = basis:VectorToObjectSpace(velocity)
		local pitch = math.clamp(localVel.Z / CFG.CRUISE_SPEED, -1, 1) * math.rad(14)
		local roll = math.clamp(-localVel.X / CFG.CRUISE_SPEED, -1, 1) * math.rad(18)
		tilt = tilt:Lerp(CFrame.Angles(pitch, 0, roll), math.min(1, dt * 3))
		frame = CFrame.new(position) * basis * tilt
		root.CFrame = frame * rootOffset
	end

	local function salvo()
		local count = CFG.SALVO_ROCKETS
		for i = 1, count do
			local m = muzzles[(i - 1) % #muzzles + 1]
			local from = (frame * m).Position
			local to = Kit.impactPoint(from, rng)
			local delay = (i - 1) * FLIGHT.SALVO_SPACING
			task.delay(delay, function()
				if enemy.dead or not model.Parent then
					return
				end
				ctx.enemyFired(enemy, "Rocket", (frame * m).Position, to)
				local at = position
				task.delay(FLIGHT.HELI_ROCKET, function()
					ctx.damageOutpost(CFG.ROCKET_DAMAGE, at, false)
				end)
			end)
		end
	end

	function enemy.update(dt: number)
		if state == "Rise" then
			local goal = Vector3.new(position.X, lane.riseTo, position.Z)
			steer(dt, goal, CFG.RISE_SPEED)
			orient(dt, true)
			if position.Y >= lane.riseTo - 6 then
				setState("Transit")
			end
			return
		end
		if state == "Transit" then
			steer(dt, target, CFG.CRUISE_SPEED)
			orient(dt, (target - position).Magnitude < 60)
			timer += dt
			if (target - position).Magnitude < 8 or timer > 25 then
				timer = 0
				setState("Hover")
				hoverFor = range(CFG.REPOSITION_AFTER, rng)
			end
			return
		end
		-- Hover / Aim: hold station with a gentle bob, attack on a cadence.
		local t = os.clock()
		local bob = Vector3.new(math.sin(t * 0.7) * 3, math.sin(t * 1.1) * 1.5, math.cos(t * 0.5) * 3)
		steer(dt, target + bob, 12)
		orient(dt, true)
		if state == "Aim" then
			timer -= dt
			if timer <= 0 then
				salvo()
				setState("Hover")
				salvoTimer = CFG.SALVO_INTERVAL * rng:NextNumber(0.85, 1.15)
			end
			return
		end
		hoverFor -= dt
		salvoTimer -= dt
		local distance = (position - PIVOT).Magnitude
		if salvoTimer <= 0 and distance <= CFG.ATTACK_RANGE and Kit.inArc(position) then
			setState("Aim")
			timer = CFG.SALVO_WARN
			ctx.enemyFired(enemy, "SalvoWarn", frame.Position, PIVOT)
		elseif hoverFor <= 0 and salvoTimer > 2 then
			target = hoverPoint(lane, rng)
			timer = 0
			setState("Transit")
		end
	end

	function enemy.isThreatening(): boolean
		return (state == "Hover" or state == "Aim") and (position - PIVOT).Magnitude <= CFG.ATTACK_RANGE
	end

	function enemy.distanceToOutpost(): number
		return Kit.outpostDistance(position)
	end

	function enemy.die()
		Kit.noQuery(model)
		Kit.toWrecks(model, "Crashing", 1.1)
		-- Spin down out of control, trailing smoke, then hit the ground.
		local v = velocity + Vector3.new(0, 4, 0)
		local spin = 0
		local cf = frame
		local elapsed = 0
		local conn: RBXScriptConnection
		conn = RunService.Heartbeat:Connect(function(dt)
			if not model.Parent then
				conn:Disconnect()
				return
			end
			elapsed += dt
			spin = math.min(spin + dt * 5, 7)
			v = Vector3.new(v.X * (1 - dt * 0.5), v.Y - 55 * dt, v.Z * (1 - dt * 0.5))
			local nextPos = cf.Position + v * dt
			local hit = Kit.terrainHit(cf.Position, nextPos + Vector3.new(0, -3, 0))
			if hit or elapsed > 7 then
				conn:Disconnect()
				local landing = hit or nextPos
				root.CFrame = CFrame.new(landing + Vector3.new(0, 2.5, 0)) * cf.Rotation * CFrame.Angles(0, 0, math.rad(70)) * rootOffset
				Kit.char(model)
				model:SetAttribute("State", "Wreck")
				return
			end
			cf = CFrame.new(nextPos) * cf.Rotation * CFrame.Angles(0, spin * dt, dt * 0.3)
			root.CFrame = cf * rootOffset
		end)
	end

	return enemy
end

return Helicopter
