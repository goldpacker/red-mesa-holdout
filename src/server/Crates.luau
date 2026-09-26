--!strict
-- Supply crates (GAME_SPEC §10): parachute drops that drift across the
-- basin; shooting one with any weapon collects extra rockets, missiles or a
-- small repair. Crates vanish if they touch down uncollected.

local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local AssetLibrary = require(ReplicatedStorage.Shared.AssetLibrary)
local Config = require(ReplicatedStorage.Shared.Config)

export type Callbacks = {
	addAmmo: (kind: string, amount: number) -> (),
	repair: (amount: number) -> (),
	emit: (kind: string, payload: any) -> (),
}

type Crate = {
	model: Model,
	contents: string,
	velocity: Vector3,
	age: number,
	collected: boolean,
}

local Crates = {}

local CFG = Config.Crates
local TAG = "SupplyCrate"
local ORANGE = Color3.fromRGB(255, 120, 20)
local CANOPY = Color3.fromRGB(235, 230, 215)

local callbacks: Callbacks
local live: { Crate } = {}
local rng = Random.new()

local function folder(): Instance
	return Workspace:WaitForChild("Crates")
end

local function part(model: Model, name: string, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material?): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Size = size
	p.CFrame = cf
	p.Color = color
	p.Material = material or Enum.Material.SmoothPlastic
	p.Anchored = true
	p.CanCollide = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = model
	return p
end

-- Primitive fallback: bright crate under a canopy with rigging lines.
local function buildFallback(): Model
	local model = Instance.new("Model")
	local root = part(model, "Root", Vector3.new(5, 4, 5), CFrame.new(), ORANGE, Enum.Material.Metal)
	for _, x in { -1.6, 1.6 } do
		part(model, "Band", Vector3.new(0.4, 4.1, 5.1), CFrame.new(x, 0, 0), Color3.fromRGB(40, 40, 40), Enum.Material.Metal)
	end
	part(model, "Cross", Vector3.new(0.2, 2.6, 2.6), CFrame.new(2.55, 0, 0), Color3.new(1, 1, 1), Enum.Material.Neon)
	local canopy = part(model, "Canopy", Vector3.new(16, 5, 16), CFrame.new(0, 14, 0), CANOPY, Enum.Material.Fabric)
	canopy.Shape = Enum.PartType.Ball
	local stripe = part(model, "CanopyStripe", Vector3.new(1.2, 16.2, 16.2), CFrame.new(0, 13.2, 0) * CFrame.Angles(0, 0, math.rad(90)), ORANGE, Enum.Material.Fabric)
	stripe.Shape = Enum.PartType.Cylinder
	for _, corner in { Vector3.new(2.4, 2, 2.4), Vector3.new(-2.4, 2, 2.4), Vector3.new(2.4, 2, -2.4), Vector3.new(-2.4, 2, -2.4) } do
		local top = Vector3.new(corner.X * 2.8, 12, corner.Z * 2.8)
		local mid = (corner + top) / 2
		local line = part(model, "Line", Vector3.new(0.12, 0.12, (top - corner).Magnitude), CFrame.lookAt(mid, top), Color3.fromRGB(60, 60, 60))
		line.CanQuery = false
	end
	model.PrimaryPart = root
	return model
end

local function buildModel(): Model
	local asset = AssetLibrary.clone("SupplyCrate")
	if asset and asset:IsA("Model") then
		if not asset.PrimaryPart then
			asset.PrimaryPart = asset:FindFirstChild("Root", true) :: BasePart?
		end
		for _, d in asset:GetDescendants() do
			if d:IsA("BasePart") then
				d.Anchored = true
				d.CanCollide = false
			end
		end
		return asset
	end
	return buildFallback()
end

local function pickContents(bias: string?): string
	if bias and CFG.CONTENTS[bias] then
		if rng:NextNumber() < CFG.BIAS_WEIGHT then
			return bias
		end
	end
	local total = 0
	for _, entry in CFG.CONTENTS do
		total += entry.weight
	end
	local roll = rng:NextNumber() * total
	for name, entry in CFG.CONTENTS do
		roll -= entry.weight
		if roll <= 0 then
			return name
		end
	end
	return "Rockets"
end

function Crates.init(cb: Callbacks)
	callbacks = cb
end

function Crates.spawn(bias: string?)
	if #live >= CFG.MAX_LIVE then
		return
	end
	local side = if rng:NextNumber() < 0.5 then -1 else 1
	local start = Vector3.new(side * rng:NextNumber(420, 560), CFG.START_HEIGHT, rng:NextNumber(-520, -260))
	local drift = Vector3.new(-side * CFG.DRIFT_SPEED, -CFG.FALL_SPEED, rng:NextNumber(-2, 2))
	local model = buildModel()
	model.Name = "SupplyCrate"
	model:PivotTo(CFrame.new(start))
	local contents = pickContents(bias)
	model:SetAttribute("Contents", contents)
	CollectionService:AddTag(model, TAG)
	model.Parent = folder()
	table.insert(live, { model = model, contents = contents, velocity = drift, age = 0, collected = false })
	callbacks.emit("CrateSpawned", { position = start, contents = contents })
end

local function remove(index: number)
	local crate = live[index]
	table.remove(live, index)
	crate.model:Destroy()
end

function Crates.update(dt: number)
	for i = #live, 1, -1 do
		local crate = live[i]
		crate.age += dt
		local pivot = crate.model:GetPivot()
		local sway = CFrame.Angles(0, 0, math.sin(crate.age * 1.3) * 0.08)
		local pos = pivot.Position + crate.velocity * dt
		crate.model:PivotTo(CFrame.new(pos) * sway)
		if pos.Y < CFG.GROUND_HEIGHT or crate.age > CFG.LIFETIME or not crate.model.Parent then
			remove(i)
		end
	end
end

-- Called for any weapon hit on a non-enemy part. Returns true if collected.
function Crates.tryCollect(hitPart: Instance): boolean
	for i, crate in live do
		if not crate.collected and hitPart:IsDescendantOf(crate.model) then
			crate.collected = true
			local entry = CFG.CONTENTS[crate.contents]
			local position = crate.model:GetPivot().Position
			if crate.contents == "Repair" then
				callbacks.repair(entry.amount)
			else
				callbacks.addAmmo(crate.contents, entry.amount)
			end
			callbacks.emit("CratePickup", { contents = crate.contents, amount = entry.amount, position = position })
			remove(i)
			return true
		end
	end
	return false
end

function Crates.clearAll()
	for i = #live, 1, -1 do
		remove(i)
	end
	local f = Workspace:FindFirstChild("Crates")
	if f then
		f:ClearAllChildren()
	end
end

return Crates
