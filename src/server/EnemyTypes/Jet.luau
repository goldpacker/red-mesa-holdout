--!strict
-- Jet: a very fast bombing run (CanyonRun along the canyon axis, or
-- CrossLeft / CrossRight diagonally across the basin). Announces itself
-- with a JetWarning {id, eta} on its first frame; if it reaches its release
-- point (RELEASE_DISTANCE from the outpost) it drops bombs for heavy
-- damage, then climbs away over the mesa and despawns, so a run never
-- hangs a wave. One AA missile (resist Missile = 10) kills it: it breaks
-- apart and falls trailing smoke.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Config = require(ReplicatedStorage.Shared.Config)
local EnemyConfig = require(ReplicatedStorage.Shared.EnemyConfig)
local Types = require(script.Parent.Parent.Types)
local AirModels = require(script.Parent.Common.AirModels)
local Dress = require(script.Parent.Common.Dress)
local Kit = require(script.Parent.Common.Kit)
local Rig = require(script.Parent.Common.Rig)

local Jet = {}
Jet.kind = "Jet"

local CFG = EnemyConfig.Jet
local FLIGHT = EnemyConfig.Flight
local PIVOT = Config.TURRET_PIVOT
local PIVOT2 = Vector2.new(PIVOT.X, PIVOT.Z)

local function build(): Model
	local asset = Kit.loadAsset("Jet", { "Root", "Exhaust", "BombBay" })
	if asset then
		Dress.jet(asset)
	end
	local model = asset or AirModels.jet()
	model.Name = "Jet"
	return model
end

local function runFor(name: string, rng: Random): any
	local runs = EnemyConfig.JetRuns :: any
	if runs[name] then
		return runs[name]
	end
	if string.find(name, "Right") then
		return runs.CrossRight
	elseif string.find(name, "Left") then
		return runs.CrossLeft
	end
	return runs.CanyonRun
end

-- Distance along the run (from `start` heading `dir`) at which the jet
-- first comes within `radius` of the outpost, or its closest approach.
local function releaseAlong(start: Vector2, dir: Vector2, radius: number): number
	local toPivot = PIVOT2 - start
	local along = toPivot:Dot(dir)
	local perp = (toPivot - dir * along).Magnitude
	if perp >= radius then
		return along
	end
	return along - math.sqrt(radius * radius - perp * perp)
end

function Jet.spawn(ctx: Types.Context, laneName: string, rng: Random): Types.Enemy
	local run = runFor(laneName, rng)
	local model = build()
	local root = Rig.prepare(model, {})
	local rootOffset = Rig.rootOffset(root)
	local bays = model:FindFirstChild("BombBay", true)
	local bayLocal = if bays and bays:IsA("Attachment") then model:GetPivot():ToObjectSpace(bays.WorldCFrame) else CFrame.new(0, -2, 0)

	local aim = run.aim + Vector2.new(rng:NextNumber(-40, 40), rng:NextNumber(-30, 30))
	local startDir = (aim - run.from).Unit
	local start = run.from + Vector2.new(-startDir.Y, startDir.X) * rng:NextNumber(-run.jitter, run.jitter)
	local dir2 = (aim - start).Unit
	local altitude = run.altitude + rng:NextNumber(-15, 15)

	local position = Vector3.new(start.X, altitude, start.Y)
	local velocity = Vector3.new(dir2.X, 0, dir2.Y) * CFG.SPEED
	local frame = CFrame.lookAt(position, position + velocity)
	root.CFrame = frame * rootOffset

	local enemy: Types.Enemy = {
		id = 0,
		kind = "Jet",
		model = model,
		root = root,
		health = CFG.HEALTH,
		maxHealth = CFG.HEALTH,
		dead = false,
		points = CFG.POINTS,
		isAir = true,
		resist = CFG.RESIST,
	}

	local releaseAt = releaseAlong(start, dir2, CFG.RELEASE_DISTANCE)
	local travelled = 0
	local age = 0
	local warned = false
	local released = false
	local roll = 0
	model:SetAttribute("State", "Inbound")

	local function drop()
		released = true
		model:SetAttribute("State", "Egress")
		for _, d in model:GetDescendants() do
			-- Fallback bombs carry a Bomb attribute; the asset's ordnance is its `Bombs` part.
			if d:IsA("BasePart") and (d:GetAttribute("Bomb") or d.Name == "BombBand" or d.Name == "Bombs") then
				d.Transparency = 1
				d.CanQuery = false
			end
		end
		local from = (frame * bayLocal).Position
		local to = Kit.impactPoint(from, rng)
		ctx.enemyFired(enemy, "Bombs", from, to)
		local at = position
		task.delay(FLIGHT.BOMB, function()
			ctx.damageOutpost(CFG.BOMB_DAMAGE, at, true)
		end)
	end

	local function leave()
		enemy.dead = true
		model:Destroy()
	end

	function enemy.update(dt: number)
		if not warned then
			warned = true
			ctx.emit("JetWarning", { id = enemy.id, eta = math.max(0, releaseAt / CFG.SPEED) })
		end
		age += dt
		travelled += CFG.SPEED * dt
		if released then
			velocity = Vector3.new(velocity.X, math.min(velocity.Y + CFG.CLIMB_RATE * 2 * dt, CFG.CLIMB_RATE), velocity.Z)
			roll = math.min(roll + dt * 0.9, math.rad(35))
		elseif releaseAt - travelled < 400 then
			-- Settle into a shallow dive on the final approach.
			velocity = Vector3.new(velocity.X, math.max(velocity.Y - 30 * dt, -18), velocity.Z)
		end
		position += velocity * dt
		frame = CFrame.lookAt(position, position + velocity) * CFrame.Angles(0, 0, roll)
		root.CFrame = frame * rootOffset

		if not released and travelled >= releaseAt then
			if Kit.inArc(position) then
				drop()
			elseif travelled > releaseAt + 200 then
				-- Overshot the arc without a legal release: abort the run.
				released = true
				model:SetAttribute("State", "Egress")
			end
		end
		local away = Kit.outpostDistance(position)
		if (released and away > CFG.EXIT_DISTANCE and travelled > releaseAt) or age > CFG.MAX_LIFETIME then
			leave()
		end
	end

	function enemy.isThreatening(): boolean
		return not released
	end

	function enemy.distanceToOutpost(): number
		return Kit.outpostDistance(position)
	end

	function enemy.die()
		Kit.noQuery(model)
		Kit.toWrecks(model, "Crashing", 1.3)
		-- A wing tears off and tumbles away on its own smoke trail.
		local wing = Kit.detach(model, if rng:NextNumber() < 0.5 then "WingL" else "WingR")
		if wing then
			wing:SetAttribute("FxScale", 0.5)
			wing:SetAttribute("State", "Thrown")
			Kit.fling(wing, velocity * 0.35 + Vector3.new(0, 25, 0), Vector3.new(rng:NextNumber(-6, 6), rng:NextNumber(-6, 6), rng:NextNumber(-6, 6)), "Debris")
		end
		local v = velocity * 0.6
		local cf = frame
		local rollRate = rng:NextNumber(2.5, 4) * (if rng:NextNumber() < 0.5 then 1 else -1)
		local elapsed = 0
		local conn: RBXScriptConnection
		conn = RunService.Heartbeat:Connect(function(dt)
			if not model.Parent then
				conn:Disconnect()
				return
			end
			elapsed += dt
			v = Vector3.new(v.X * (1 - dt * 0.35), v.Y - 90 * dt, v.Z * (1 - dt * 0.35))
			local nextPos = cf.Position + v * dt
			local hit = Kit.terrainHit(cf.Position, nextPos + v.Unit * 3)
			if hit or elapsed > 8 then
				conn:Disconnect()
				local landing = hit or nextPos
				local flat = Vector3.new(v.X, 0, v.Z)
				local heading = if flat.Magnitude > 1 then flat.Unit else Vector3.new(0, 0, -1)
				root.CFrame = CFrame.lookAt(landing + Vector3.new(0, 2, 0), landing + Vector3.new(0, 2, 0) + heading)
					* CFrame.Angles(math.rad(-8), 0, math.rad(rng:NextNumber(-40, 40)))
					* rootOffset
				Kit.char(model)
				model:SetAttribute("State", "Wreck")
				return
			end
			cf = CFrame.lookAt(nextPos, nextPos + v) * CFrame.Angles(0, 0, elapsed * rollRate)
			root.CFrame = cf * rootOffset
		end)
	end

	return enemy
end

return Jet
