--!strict
-- Studio-only weapon practice target (ground). Never used in real waves.
-- Spawn during a wave with
--   ServerStorage.RedMesaDebug:Invoke("spawn", { kind = "TestDummyGround", lane = "0,-300" })
-- `lane` is "x,z" (placed on the terrain) or a Config.Lanes name (placed
-- at the lane's middle waypoint). An armoured block: the machine gun only
-- ricochets off it, rockets kill it in ~2 hits. See _TestDummyAir for air.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Types = require(script.Parent.Parent.Types)

local Dummy = {}
Dummy.kind = "TestDummyGround"

local HEALTH = 200
local SIZE = Vector3.new(12, 6, 22)

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include
groundParams.FilterDescendantsInstances = { Workspace.Terrain }

local function groundY(x: number, z: number): number
	local result = Workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -600, 0), groundParams)
	return if result then result.Position.Y else 0
end

-- Parses "x,z" or a lane name into a flat XZ position.
function Dummy.position(lane: string): Vector2
	local x, z = string.match(lane, "^%s*(%-?[%d%.]+)%s*,%s*(%-?[%d%.]+)%s*$")
	if x and z then
		return Vector2.new(tonumber(x) :: number, tonumber(z) :: number)
	end
	local points = Config.Lanes[lane]
	if points then
		return points[math.max(1, math.ceil(#points / 2))]
	end
	return Vector2.new(0, -300)
end

function Dummy.spawn(_ctx: Types.Context, lane: string, _rng: Random): Types.Enemy
	local flat = Dummy.position(lane)
	local pos = Vector3.new(flat.X, groundY(flat.X, flat.Y) + SIZE.Y / 2, flat.Y)

	local model = Instance.new("Model")
	model.Name = "TestDummyGround"
	local root = Instance.new("Part")
	root.Name = "Root"
	root.Size = SIZE
	root.Anchored = true
	root.CanCollide = false
	root.Material = Enum.Material.DiamondPlate
	root.Color = Color3.fromRGB(58, 60, 64)
	root.CFrame = CFrame.lookAt(pos, Vector3.new(0, pos.Y, 0))
	root.Parent = model
	local stripe = Instance.new("Part")
	stripe.Name = "Stripe"
	stripe.Size = Vector3.new(SIZE.X + 0.2, 1.2, 3)
	stripe.Anchored = true
	stripe.CanCollide = false
	stripe.CanQuery = false
	stripe.Material = Enum.Material.SmoothPlastic
	stripe.Color = Color3.fromRGB(200, 32, 28)
	stripe.CFrame = root.CFrame * CFrame.new(0, SIZE.Y / 2 - 0.4, 0)
	stripe.Parent = model
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
		isAir = false,
		resist = { MG = 0.05 },
	}

	function enemy.update(_dt: number) end

	function enemy.die()
		model:SetAttribute("State", "Dead")
		for _, d in model:GetDescendants() do
			if d:IsA("BasePart") then
				d.CanQuery = false
				TweenService:Create(d, TweenInfo.new(0.6), { Color = Color3.fromRGB(20, 18, 16) }):Play()
			end
		end
		task.delay(3, function()
			model:Destroy()
		end)
	end

	function enemy.distanceToOutpost(): number
		return Vector2.new(pos.X, pos.Z).Magnitude
	end

	return enemy
end

return Dummy
