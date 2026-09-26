--!strict
-- Infantry: blocky soldiers that advance along a lane, snipe with rifles
-- from mid range and lob grenades once they reach the foot of the mesa.
-- The server owns position and behaviour; clients animate limbs via the
-- Motor6D joints (see client/EnemyVisuals).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Types = require(script.Parent.Types)

local Infantry = {}

local UNIFORM = Color3.fromRGB(56, 58, 64)
local UNIFORM_DARK = Color3.fromRGB(38, 40, 44)
local MARKING = Color3.fromRGB(200, 32, 28)
local SKIN = Color3.fromRGB(150, 120, 100)
-- Soldiers are oversized so they stay readable across the basin.
local SCALE = 1.5
local HIP_HEIGHT = 3.4 * SCALE
local CFG = Config.Infantry

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include
groundParams.FilterDescendantsInstances = { Workspace.Terrain }

local function groundY(x: number, z: number): number
	local result = Workspace:Raycast(Vector3.new(x, 300, z), Vector3.new(0, -400, 0), groundParams)
	return if result then result.Position.Y else 0
end

local function part(model: Model, name: string, size: Vector3, color: Color3, shape: Enum.PartType?): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.Color = color
	p.Material = Enum.Material.SmoothPlastic
	p.Shape = shape or Enum.PartType.Block
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.CanCollide = false
	p.Massless = true
	p.Anchored = false
	p.Parent = model
	return p
end

local function joint(name: string, parent: BasePart, child: BasePart, c0: CFrame, c1: CFrame, className: string?): Instance
	local j = Instance.new(className or "Motor6D") :: any
	j.Name = name
	j.Part0 = parent
	j.Part1 = child
	j.C0 = c0
	j.C1 = c1
	j.Parent = parent
	return j
end

local function buildModel(cframe: CFrame): (Model, BasePart)
	local model = Instance.new("Model")
	model.Name = "Infantry"

	local root = part(model, "Root", Vector3.new(2, 2, 1), UNIFORM)
	root.Transparency = 1
	root.Anchored = true
	root.CanQuery = false
	root.CFrame = cframe

	local torso = part(model, "Torso", Vector3.new(2.2, 2.8, 1.3), UNIFORM)
	local head = part(model, "Head", Vector3.new(1.4, 1.4, 1.4), SKIN)
	local helmet = part(model, "Helmet", Vector3.new(1.8, 0.9, 1.8), UNIFORM_DARK)
	local stripe = part(model, "Stripe", Vector3.new(1.84, 0.28, 1.84), MARKING)
	local leftLeg = part(model, "LeftLeg", Vector3.new(0.9, 3.4, 1), UNIFORM_DARK)
	local rightLeg = part(model, "RightLeg", Vector3.new(0.9, 3.4, 1), UNIFORM_DARK)
	local leftArm = part(model, "LeftArm", Vector3.new(0.8, 2.6, 0.8), UNIFORM)
	local rightArm = part(model, "RightArm", Vector3.new(0.8, 2.6, 0.8), UNIFORM)
	local band = part(model, "Armband", Vector3.new(0.86, 0.5, 0.86), MARKING)
	local rifle = part(model, "Rifle", Vector3.new(0.35, 0.5, 3.2), Color3.fromRGB(30, 30, 30))
	local pack = part(model, "Pack", Vector3.new(1.6, 1.6, 0.8), Color3.fromRGB(70, 66, 58))
	helmet.CanQuery = false
	stripe.CanQuery = false
	band.CanQuery = false

	joint("RootJoint", root, torso, CFrame.new(0, 1.4, 0), CFrame.new())
	joint("Neck", torso, head, CFrame.new(0, 1.4, 0), CFrame.new(0, -0.7, 0))
	joint("HelmetWeld", head, helmet, CFrame.new(0, 0.55, 0), CFrame.new(), "Weld")
	joint("StripeWeld", helmet, stripe, CFrame.new(0, -0.1, 0), CFrame.new(), "Weld")
	joint("LeftHip", torso, leftLeg, CFrame.new(-0.55, -1.4, 0), CFrame.new(0, 1.7, 0))
	joint("RightHip", torso, rightLeg, CFrame.new(0.55, -1.4, 0), CFrame.new(0, 1.7, 0))
	joint("LeftShoulder", torso, leftArm, CFrame.new(-1.5, 1.1, 0), CFrame.new(0, 1.1, 0))
	joint("RightShoulder", torso, rightArm, CFrame.new(1.5, 1.1, 0), CFrame.new(0, 1.1, 0))
	joint("BandWeld", leftArm, band, CFrame.new(0, 0.6, 0), CFrame.new(), "Weld")
	joint("RifleWeld", rightArm, rifle, CFrame.new(-0.2, -1.1, -1.0), CFrame.new(), "Weld")
	joint("PackWeld", torso, pack, CFrame.new(0, 0.2, 1.0), CFrame.new(), "Weld")

	model.PrimaryPart = root
	model:ScaleTo(SCALE)
	return model, root
end

local function horizontalDistance(a: Vector3, b: Vector3): number
	return Vector2.new(a.X - b.X, a.Z - b.Z).Magnitude
end

function Infantry.spawn(ctx: Types.Context, laneName: string, rng: Random): Types.Enemy
	local lane = Config.Lanes[laneName]
	assert(lane, "unknown lane " .. laneName)

	local lateral = rng:NextNumber(-14, 14)
	local start = lane[1] + Vector2.new(rng:NextNumber(-10, 10), rng:NextNumber(-20, 20))
	local y = groundY(start.X, start.Y) + HIP_HEIGHT
	local toward = lane[2] - lane[1]
	local cf = CFrame.lookAt(Vector3.new(start.X, y, start.Y), Vector3.new(start.X + toward.X, y, start.Y + toward.Y))
	local model, root = buildModel(cf)

	local enemy: Types.Enemy = {
		id = 0,
		kind = "Infantry",
		model = model,
		root = root,
		health = CFG.HEALTH,
		maxHealth = CFG.HEALTH,
		dead = false,
		points = CFG.POINTS,
		isAir = false,
	}

	local speed = CFG.SPEED * rng:NextNumber(0.85, 1.15)
	local waypoint = 2
	local position = Vector3.new(start.X, y, start.Y)
	local rifleTimer = CFG.RIFLE_INTERVAL * rng:NextNumber(0.5, 1.5)
	local grenadeTimer = rng:NextNumber(0.5, 2)
	local aimTimer = 0
	local atBase = false

	local function target(i: number): Vector2
		local p = lane[i]
		if i == #lane then
			return p
		end
		local dir = (lane[i + 1] - p).Unit
		return p + Vector2.new(-dir.Y, dir.X) * lateral
	end

	local function face(point: Vector3)
		local flat = Vector3.new(point.X, position.Y, point.Z)
		if (flat - position).Magnitude > 0.01 then
			root.CFrame = CFrame.lookAt(position, flat)
		else
			root.CFrame = CFrame.new(position) * root.CFrame.Rotation
		end
	end

	function enemy.update(dt: number)
		local pivot = Config.TURRET_PIVOT
		if aimTimer > 0 then
			aimTimer -= dt
			if aimTimer <= 0 then
				ctx.enemyFired(enemy, "Rifle", position + Vector3.new(0, 2.5 * SCALE, 0), pivot)
				ctx.damageOutpost(CFG.RIFLE_DAMAGE, position, false)
			end
			return
		end

		if atBase then
			model:SetAttribute("State", "Throw")
			grenadeTimer -= dt
			face(pivot)
			if grenadeTimer <= 0 then
				grenadeTimer = CFG.GRENADE_INTERVAL * rng:NextNumber(0.8, 1.2)
				local from = position + Vector3.new(0, 3.5 * SCALE, 0)
				local landing = pivot + Vector3.new(rng:NextNumber(-8, 8), -5, rng:NextNumber(-8, 4))
				ctx.enemyFired(enemy, "Grenade", from, landing)
				task.delay(CFG.GRENADE_FLIGHT, function()
					ctx.damageOutpost(CFG.GRENADE_DAMAGE, position, false)
				end)
			end
			return
		end

		model:SetAttribute("State", "Walk")
		local goal = target(waypoint)
		local flatPos = Vector2.new(position.X, position.Z)
		local toGoal = goal - flatPos
		local step = speed * dt
		if toGoal.Magnitude <= step then
			flatPos = goal
			if waypoint >= #lane then
				atBase = true
			else
				waypoint += 1
			end
		else
			flatPos += toGoal.Unit * step
		end
		local newY = groundY(flatPos.X, flatPos.Y) + HIP_HEIGHT
		local newPos = Vector3.new(flatPos.X, newY, flatPos.Y)
		local heading = newPos - position
		position = newPos
		if heading.Magnitude > 0.001 then
			face(position + heading)
		end

		if (position - pivot).Magnitude <= CFG.RIFLE_RANGE then
			rifleTimer -= dt
			if rifleTimer <= 0 then
				rifleTimer = CFG.RIFLE_INTERVAL * rng:NextNumber(0.7, 1.3)
				aimTimer = 0.8
				model:SetAttribute("State", "Aim")
				face(pivot)
			end
		end
	end

	function enemy.die()
		model:SetAttribute("State", "Dead")
		local fallDir = if math.random() < 0.5 then 1 else -1
		local fallen = root.CFrame * CFrame.new(0, -HIP_HEIGHT + 1.2, 0) * CFrame.Angles(math.rad(85) * fallDir, 0, 0)
		TweenService:Create(root, TweenInfo.new(0.45, Enum.EasingStyle.Quad, Enum.EasingDirection.In), { CFrame = fallen }):Play()
		for _, d in model:GetDescendants() do
			if d:IsA("BasePart") then
				d.CanQuery = false
			end
		end
		task.delay(4, function()
			model:Destroy()
		end)
	end

	function enemy.distanceToOutpost(): number
		return horizontalDistance(position, Config.TURRET_PIVOT)
	end

	return enemy
end

return Infantry
