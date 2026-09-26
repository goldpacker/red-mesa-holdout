--!strict
-- Infantry: human-sized soldiers that advance along a lane, snipe with
-- rifles from mid range and lob grenades once they reach the foot of the
-- mesa. The server owns position and behaviour; clients animate limbs via
-- the Motor6D joints (see client/EnemyVisuals). Uses the Blender
-- "Infantry" asset when present, else a primitive soldier.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Types = require(script.Parent.Parent.Types)
local Kit = require(script.Parent.Common.Kit)

local Infantry = {}
Infantry.kind = "Infantry"

local UNIFORM = Color3.fromRGB(56, 58, 64)
local UNIFORM_DARK = Color3.fromRGB(38, 40, 44)
local MARKING = Color3.fromRGB(200, 32, 28)
local SKIN = Color3.fromRGB(150, 120, 100)
-- Real proportions (GAME_SPEC §13): a soldier stands ~6.5 studs; we render
-- them 1.1x (7.2 studs incl. helmet) so hits still feel fair at range.
-- Readability comes from the dark uniform against orange ground, the red
-- helmet band and a helmet lamp at night.
local TARGET_HEIGHT = 7.2
local ASSET_SCALE = 1.1
local CFG = Config.Infantry
local LIMBS = { "Torso", "Head", "LeftArm", "RightArm", "LeftLeg", "RightLeg" }

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
	p.Material = Enum.Material.Fabric
	p.Shape = shape or Enum.PartType.Block
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.CanCollide = false
	p.CanTouch = false
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

local function addLamp(model: Model, head: BasePart)
	local lamp = part(model, "HelmetLamp", Vector3.new(0.35, 0.25, 0.2), Color3.fromRGB(255, 120, 90))
	lamp.Material = Enum.Material.Neon
	lamp.CanQuery = false
	lamp.CastShadow = false
	-- Dark by day; client/EnemyVisuals lights it at dusk and night.
	lamp.Transparency = 1
	local light = Instance.new("PointLight")
	light.Enabled = false
	light.Color = Color3.fromRGB(255, 110, 80)
	light.Range = 7
	light.Brightness = 1.2
	light.Parent = lamp
	joint("LampWeld", head, lamp, CFrame.new(0, head.Size.Y * 0.45, -head.Size.X * 0.62), CFrame.new(), "Weld")
end

-- Primitive soldier; root sits at hip height, facing -Z.
local function buildFallback(): Model
	local model = Instance.new("Model")
	model.Name = "Infantry"

	local root = part(model, "Root", Vector3.new(2, 2, 1), UNIFORM)
	root.Transparency = 1
	root.CanQuery = false

	local torso = part(model, "Torso", Vector3.new(2.0, 2.7, 1.2), UNIFORM)
	local head = part(model, "Head", Vector3.new(1.2, 1.3, 1.2), SKIN)
	head.Material = Enum.Material.SmoothPlastic
	local helmet = part(model, "Helmet", Vector3.new(1.6, 0.8, 1.7), UNIFORM_DARK)
	local stripe = part(model, "Stripe", Vector3.new(1.64, 0.26, 1.74), MARKING)
	local vest = part(model, "Vest", Vector3.new(2.15, 1.6, 1.4), Color3.fromRGB(64, 62, 56))
	local leftLeg = part(model, "LeftLeg", Vector3.new(0.85, 3.3, 0.95), UNIFORM_DARK)
	local rightLeg = part(model, "RightLeg", Vector3.new(0.85, 3.3, 0.95), UNIFORM_DARK)
	local leftArm = part(model, "LeftArm", Vector3.new(0.7, 2.6, 0.75), UNIFORM)
	local rightArm = part(model, "RightArm", Vector3.new(0.7, 2.6, 0.75), UNIFORM)
	local band = part(model, "Armband", Vector3.new(0.76, 0.45, 0.8), MARKING)
	local rifle = part(model, "Rifle", Vector3.new(0.3, 0.5, 3.1), Color3.fromRGB(30, 30, 30))
	rifle.Material = Enum.Material.Metal
	local pack = part(model, "Pack", Vector3.new(1.5, 1.6, 0.8), Color3.fromRGB(70, 66, 58))
	for _, p in { helmet, stripe, band, vest } do
		p.CanQuery = false
	end

	joint("RootJoint", root, torso, CFrame.new(0, 1.35, 0), CFrame.new())
	joint("Neck", torso, head, CFrame.new(0, 1.35, 0), CFrame.new(0, -0.65, 0))
	joint("HelmetWeld", head, helmet, CFrame.new(0, 0.5, 0.05), CFrame.new(), "Weld")
	joint("StripeWeld", helmet, stripe, CFrame.new(0, -0.1, 0), CFrame.new(), "Weld")
	joint("VestWeld", torso, vest, CFrame.new(0, 0.35, 0), CFrame.new(), "Weld")
	joint("LeftHip", torso, leftLeg, CFrame.new(-0.5, -1.35, 0), CFrame.new(0, 1.65, 0))
	joint("RightHip", torso, rightLeg, CFrame.new(0.5, -1.35, 0), CFrame.new(0, 1.65, 0))
	joint("LeftShoulder", torso, leftArm, CFrame.new(-1.38, 1.05, 0), CFrame.new(0, 1.05, 0))
	joint("RightShoulder", torso, rightArm, CFrame.new(1.38, 1.05, 0), CFrame.new(0, 1.05, 0))
	joint("BandWeld", leftArm, band, CFrame.new(0, 0.6, 0), CFrame.new(), "Weld")
	joint("RifleWeld", rightArm, rifle, CFrame.new(-0.2, -1.1, -1.0), CFrame.new(), "Weld")
	joint("PackWeld", torso, pack, CFrame.new(0, 0.2, 1.0), CFrame.new(), "Weld")
	addLamp(model, head)

	model.PrimaryPart = root
	return model
end

-- Rigs the Blender soldier: limb origins sit at their joints, so each
-- Motor6D keeps the authored pose in C0 and an identity C1.
local function rigAsset(model: Model): boolean
	local root = model:FindFirstChild("Root", true)
	local torso = model:FindFirstChild("Torso", true)
	if not (root and root:IsA("BasePart") and torso and torso:IsA("BasePart")) then
		return false
	end
	for _, d in model:GetDescendants() do
		if d:IsA("JointInstance") or d:IsA("WeldConstraint") then
			d:Destroy()
		elseif d:IsA("BasePart") then
			d.Anchored = false
			d.CanCollide = false
			d.CanTouch = false
			d.Massless = true
		end
	end
	root.Transparency = 1
	root.CanQuery = false
	joint("RootJoint", root, torso, root.CFrame:ToObjectSpace(torso.CFrame), CFrame.new())
	local names = { Head = "Neck", LeftLeg = "LeftHip", RightLeg = "RightHip", LeftArm = "LeftShoulder", RightArm = "RightShoulder" }
	for limbName, jointName in names do
		local limb = model:FindFirstChild(limbName, true)
		if limb and limb:IsA("BasePart") then
			joint(jointName, torso, limb, torso.CFrame:ToObjectSpace(limb.CFrame), CFrame.new())
		end
	end
	local head = model:FindFirstChild("Head", true) :: BasePart?
	local rightArm = model:FindFirstChild("RightArm", true) :: BasePart?
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and d ~= root and d ~= torso and not names[d.Name] then
			local host: BasePart = torso
			if d.Name == "Rifle" and rightArm then
				host = rightArm
			elseif head and (string.find(d.Name, "Helmet") or string.find(d.Name, "Head")) then
				host = head
			end
			joint(d.Name .. "Weld", host, d, host.CFrame:ToObjectSpace(d.CFrame), CFrame.new(), "Weld")
		end
	end
	if head then
		addLamp(model, head)
	end
	model.PrimaryPart = root
	return true
end

local function buildModel(): (Model, BasePart, number)
	local model = Kit.loadAsset("Infantry", { "Root", "Torso", "Head", "LeftArm", "RightArm", "LeftLeg", "RightLeg", "Rifle" })
	if model and not rigAsset(model) then
		model:Destroy()
		model = nil
	end
	local m = model or buildFallback()
	m.Name = "Infantry"
	local root = m.PrimaryPart :: BasePart
	if model then
		-- The Blender soldier is authored at real scale (~6.5 studs; its
		-- padded limb boxes inflate the bounding box), so scale directly.
		m:ScaleTo(m:GetScale() * ASSET_SCALE)
	else
		-- Normalise the primitive soldier's height.
		local _, size = m:GetBoundingBox()
		if size.Y > 0.5 then
			m:ScaleTo(m:GetScale() * TARGET_HEIGHT / size.Y)
		end
	end
	-- How far the root sits above the feet.
	local box, scaled = m:GetBoundingBox()
	local hip = root.Position.Y - (box.Position.Y - scaled.Y / 2)
	root.Anchored = true
	return m, root, hip
end

local function horizontalDistance(a: Vector3, b: Vector3): number
	return Vector2.new(a.X - b.X, a.Z - b.Z).Magnitude
end

function Infantry.spawn(ctx: Types.Context, laneName: string, rng: Random): Types.Enemy
	local lane = Config.Lanes[laneName] or Config.Lanes.Road

	local lateral = rng:NextNumber(-14, 14)
	local start = lane[1] + Vector2.new(rng:NextNumber(-10, 10), rng:NextNumber(-20, 20))
	local model, root, HIP_HEIGHT = buildModel()
	local y = groundY(start.X, start.Y) + HIP_HEIGHT
	local toward = lane[2] - lane[1]
	root.CFrame = CFrame.lookAt(Vector3.new(start.X, y, start.Y), Vector3.new(start.X + toward.X, y, start.Y + toward.Y))

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
				ctx.enemyFired(enemy, "Rifle", position + Vector3.new(0, HIP_HEIGHT * 0.75, 0), pivot)
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
				local from = position + Vector3.new(0, HIP_HEIGHT * 1.05, 0)
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

	function enemy.isThreatening(): boolean
		return (position - Config.TURRET_PIVOT).Magnitude <= CFG.RIFLE_RANGE
	end

	function enemy.distanceToOutpost(): number
		return horizontalDistance(position, Config.TURRET_PIVOT)
	end

	return enemy
end

return Infantry
