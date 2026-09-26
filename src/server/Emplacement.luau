--!strict
-- Player emplacement on the mesa top: sandbag ring, platform and the
-- three-weapon turret. Placeholder primitive geometry until the Blender
-- hero asset replaces it; part names are the contract the client uses.
--
-- Workspace.Battlefield.Emplacement
--   Static        (sandbags, platform, props)
--   TurretYaw     (Model, pivot = Aim.cframe(yaw, 0))
--   TurretGun     (Model, pivot = Aim.cframe(yaw, pitch)), contains Muzzle

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Aim = require(ReplicatedStorage.Shared.Aim)

local Emplacement = {}

local SAND = Color3.fromRGB(196, 170, 120)
local TAN = Color3.fromRGB(170, 146, 102)
local OLIVE = Color3.fromRGB(96, 104, 58)
local OLIVE_DARK = Color3.fromRGB(66, 72, 40)
local GUNMETAL = Color3.fromRGB(52, 54, 56)

type PartSpec = {
	name: string?,
	size: Vector3,
	cframe: CFrame,
	color: Color3,
	material: Enum.Material?,
	shape: Enum.PartType?,
	collide: boolean?,
}

local function makePart(spec: PartSpec, parent: Instance): Part
	local part = Instance.new("Part")
	part.Name = spec.name or "Part"
	part.Anchored = true
	part.CanCollide = spec.collide == true
	part.Size = spec.size
	part.CFrame = spec.cframe
	part.Color = spec.color
	part.Material = spec.material or Enum.Material.SmoothPlastic
	part.Shape = spec.shape or Enum.PartType.Block
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.CastShadow = true
	part.Parent = parent
	return part
end

-- Cylinders in Roblox run along X; this rotates them to run along -Z.
local ALONG_Z = CFrame.Angles(0, math.rad(90), 0)
-- And this makes them stand upright (axis along Y).
local UPRIGHT = CFrame.Angles(0, 0, math.rad(90))

local function buildStatic(parent: Instance)
	local static = Instance.new("Folder")
	static.Name = "Static"
	static.Parent = parent

	local base = Config.TURRET_PIVOT - Vector3.new(0, 6, 0)
	local bunkerHeight = base.Y - Config.MESA_TOP + 1

	makePart({
		name = "Bunker",
		size = Vector3.new(bunkerHeight, 27, 27),
		cframe = CFrame.new(base.X, Config.MESA_TOP - 1 + bunkerHeight / 2, base.Z) * UPRIGHT,
		color = Color3.fromRGB(150, 128, 92),
		material = Enum.Material.Concrete,
		shape = Enum.PartType.Cylinder,
		collide = true,
	}, static)

	makePart({
		name = "Platform",
		size = Vector3.new(1, 26, 26),
		cframe = CFrame.new(base + Vector3.new(0, 0.5, 0)) * UPRIGHT,
		color = TAN,
		material = Enum.Material.Concrete,
		shape = Enum.PartType.Cylinder,
		collide = true,
	}, static)

	-- Sandbag ring: two courses of bags around the front 300 degrees.
	for course = 0, 1 do
		local count = 26
		for i = 0, count - 1 do
			local angle = math.rad(-150 + (300 / (count - 1)) * i + course * 5)
			local radius = 13.5
			local pos = base + Vector3.new(-math.sin(angle) * radius, 1.6 + course * 1.5, -math.cos(angle) * radius)
			makePart({
				name = "Sandbag",
				size = Vector3.new(3.4, 1.5, 1.8),
				cframe = CFrame.lookAt(pos, Vector3.new(base.X, pos.Y, base.Z)),
				color = if (i + course) % 2 == 0 then SAND else TAN,
				material = Enum.Material.Fabric,
			}, static)
		end
	end

	-- Turret pedestal.
	makePart({
		name = "Pedestal",
		size = Vector3.new(4.5, 3.2, 3.2),
		cframe = CFrame.new(base + Vector3.new(0, 3.2, 0)) * UPRIGHT,
		color = OLIVE_DARK,
		material = Enum.Material.Metal,
		shape = Enum.PartType.Cylinder,
	}, static)

	-- Ammo crates and a jerrycan for set dressing.
	makePart({ name = "AmmoCrate", size = Vector3.new(3, 1.6, 2), cframe = CFrame.new(base + Vector3.new(6, 1.8, 5)) * CFrame.Angles(0, 0.3, 0), color = OLIVE, material = Enum.Material.Wood }, static)
	makePart({ name = "AmmoCrate", size = Vector3.new(3, 1.6, 2), cframe = CFrame.new(base + Vector3.new(6.4, 3.4, 5.2)) * CFrame.Angles(0, 0.1, 0), color = OLIVE_DARK, material = Enum.Material.Wood }, static)
	makePart({ name = "AmmoCrate", size = Vector3.new(2.4, 1.4, 1.6), cframe = CFrame.new(base + Vector3.new(-6, 1.7, 6)) * CFrame.Angles(0, -0.4, 0), color = OLIVE, material = Enum.Material.Wood }, static)
end

local function buildTurretYaw(parent: Instance): Model
	local model = Instance.new("Model")
	model.Name = "TurretYaw"
	local pivot = Aim.cframe(0, 0)

	makePart({
		name = "Ring",
		size = Vector3.new(0.8, 5.5, 5.5),
		cframe = pivot * CFrame.new(0, -3.2, 0) * UPRIGHT,
		color = OLIVE,
		material = Enum.Material.Metal,
		shape = Enum.PartType.Cylinder,
	}, model)
	for _, side in { -1, 1 } do
		makePart({
			name = "Yoke",
			size = Vector3.new(0.6, 3.4, 1.4),
			cframe = pivot * CFrame.new(side * 2.2, -1.5, 0),
			color = OLIVE_DARK,
			material = Enum.Material.Metal,
		}, model)
	end
	makePart({
		name = "Seat",
		size = Vector3.new(2, 0.5, 1.6),
		cframe = pivot * CFrame.new(0, -2.4, 3),
		color = GUNMETAL,
		material = Enum.Material.Metal,
	}, model)

	model.WorldPivot = pivot
	model.Parent = parent
	return model
end

local function buildTurretGun(parent: Instance): Model
	local model = Instance.new("Model")
	model.Name = "TurretGun"
	local pivot = Aim.cframe(0, 0)

	makePart({ name = "Receiver", size = Vector3.new(1.8, 1.6, 4), cframe = pivot, color = OLIVE, material = Enum.Material.Metal }, model)
	makePart({ name = "Shield", size = Vector3.new(6.4, 3, 0.3), cframe = pivot * CFrame.new(0, -0.2, -2.1) * CFrame.Angles(math.rad(-8), 0, 0), color = OLIVE_DARK, material = Enum.Material.Metal }, model)
	makePart({ name = "BarrelShroud", size = Vector3.new(3, 0.8, 0.8), cframe = pivot * CFrame.new(0, 0.1, -3.4) * ALONG_Z, color = GUNMETAL, material = Enum.Material.Metal, shape = Enum.PartType.Cylinder }, model)
	makePart({ name = "Barrel", size = Vector3.new(3.4, 0.4, 0.4), cframe = pivot * CFrame.new(0, 0.1, -5.6) * ALONG_Z, color = GUNMETAL, material = Enum.Material.Metal, shape = Enum.PartType.Cylinder }, model)
	makePart({ name = "Muzzle", size = Vector3.new(0.6, 0.6, 0.6), cframe = pivot * CFrame.new(0, 0.1, -Config.MUZZLE_OFFSET - 1.3), color = GUNMETAL, material = Enum.Material.Metal }, model)
	makePart({ name = "AmmoBox", size = Vector3.new(1.2, 1.2, 1.6), cframe = pivot * CFrame.new(-1.4, -0.2, 0.2), color = OLIVE_DARK, material = Enum.Material.Metal }, model)

	-- Rocket pod (right) and AA missile rack (left): inactive this milestone.
	makePart({ name = "RocketPod", size = Vector3.new(1.8, 1.8, 3.2), cframe = pivot * CFrame.new(2.9, 0.6, -0.6), color = OLIVE, material = Enum.Material.Metal }, model)
	makePart({ name = "MissileRail", size = Vector3.new(0.6, 0.4, 3.6), cframe = pivot * CFrame.new(-3.0, 1.1, -0.4), color = OLIVE_DARK, material = Enum.Material.Metal }, model)
	makePart({ name = "Missile", size = Vector3.new(3.2, 0.5, 0.5), cframe = pivot * CFrame.new(-3.0, 1.6, -0.6) * ALONG_Z, color = Color3.fromRGB(220, 220, 210), material = Enum.Material.SmoothPlastic, shape = Enum.PartType.Cylinder }, model)

	for _, part in model:GetDescendants() do
		if part:IsA("BasePart") then
			part.CanQuery = false
		end
	end

	model.WorldPivot = pivot
	model.Parent = parent
	return model
end

function Emplacement.build(parent: Instance)
	local folder = Instance.new("Folder")
	folder.Name = "Emplacement"
	folder.Parent = parent
	buildStatic(folder)
	buildTurretYaw(folder)
	buildTurretGun(folder)
end

return Emplacement
