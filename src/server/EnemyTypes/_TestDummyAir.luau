--!strict
-- Studio-only weapon practice target (air, IsAir = true). Never used in
-- real waves. Spawn during a wave with
--   ServerStorage.RedMesaDebug:Invoke("spawn", { kind = "TestDummyAir", lane = "0,120,-400" })
-- `lane` is "x,y,z" (y = height above the terrain) with an optional 4th
-- value: orbit speed in studs/s (circles the spawn point, radius 120), e.g.
-- "0,120,-400,90". A lane name hovers 110 studs above its middle waypoint.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Types = require(script.Parent.Parent.Types)

local Dummy = {}
Dummy.kind = "TestDummyAir"

local HEALTH = 150
local SIZE = Vector3.new(8, 5, 26)
local ORBIT_RADIUS = 120

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include
groundParams.FilterDescendantsInstances = { Workspace.Terrain }

local function groundY(x: number, z: number): number
	local result = Workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -600, 0), groundParams)
	return if result then result.Position.Y else 0
end

local function parse(lane: string): (Vector3, number)
	local nums = {}
	for n in string.gmatch(lane, "%-?[%d%.]+") do
		table.insert(nums, tonumber(n) :: number)
	end
	if #nums >= 3 then
		return Vector3.new(nums[1], groundY(nums[1], nums[3]) + nums[2], nums[3]), nums[4] or 0
	end
	local points = Config.Lanes[lane]
	local flat = if points then points[math.max(1, math.ceil(#points / 2))] else Vector2.new(0, -400)
	return Vector3.new(flat.X, groundY(flat.X, flat.Y) + 110, flat.Y), 0
end

function Dummy.spawn(_ctx: Types.Context, lane: string, _rng: Random): Types.Enemy
	local center, speed = parse(lane)

	local model = Instance.new("Model")
	model.Name = "TestDummyAir"
	local root = Instance.new("Part")
	root.Name = "Root"
	root.Size = SIZE
	root.Anchored = true
	root.CanCollide = false
	root.Material = Enum.Material.Metal
	root.Color = Color3.fromRGB(50, 52, 58)
	root.CFrame = CFrame.new(center)
	root.Parent = model
	local wing = Instance.new("Part")
	wing.Name = "Wing"
	wing.Size = Vector3.new(26, 0.8, 6)
	wing.Anchored = true
	wing.CanCollide = false
	wing.Material = Enum.Material.Metal
	wing.Color = Color3.fromRGB(200, 32, 28)
	wing.CFrame = root.CFrame
	wing.Parent = model
	model.PrimaryPart = root

	local enemy: Types.Enemy = {
		id = 0,
		kind = Dummy.kind,
		model = model,
		root = root,
		health = HEALTH,
		maxHealth = HEALTH,
		dead = false,
		points = 0,
		isAir = true,
		resist = { MG = 0.5 },
	}

	local angle = 0
	function enemy.update(dt: number)
		if speed == 0 then
			return
		end
		angle += speed / ORBIT_RADIUS * dt
		local pos = center + Vector3.new(math.cos(angle), 0, math.sin(angle)) * ORBIT_RADIUS
		local ahead = center + Vector3.new(math.cos(angle + 0.1), 0, math.sin(angle + 0.1)) * ORBIT_RADIUS
		local cf = CFrame.lookAt(pos, ahead)
		root.CFrame = cf
		wing.CFrame = cf
	end

	function enemy.die()
		model:SetAttribute("State", "Dead")
		for _, d in model:GetDescendants() do
			if d:IsA("BasePart") then
				d.CanQuery = false
				local fall = d.CFrame * CFrame.new(0, -60, -20) * CFrame.Angles(math.rad(-50), 0, math.rad(40))
				TweenService:Create(d, TweenInfo.new(1.6, Enum.EasingStyle.Quad, Enum.EasingDirection.In), { CFrame = fall, Color = Color3.fromRGB(20, 18, 16) }):Play()
			end
		end
		task.delay(1.7, function()
			model:Destroy()
		end)
	end

	function enemy.distanceToOutpost(): number
		local p = root.Position
		return Vector2.new(p.X, p.Z).Magnitude
	end

	return enemy
end

return Dummy
