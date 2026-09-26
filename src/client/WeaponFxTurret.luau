--!strict
-- Makes the selected weapon visible on the turret model: the active weapon
-- swings up level and raises; the others stow nose-down (rocket pod,
-- missile rack) or retract (machine-gun barrel). Also hides the rail
-- missile while the rack is empty or reloading, and exposes each weapon's
-- world muzzle for the launch effects.
--
-- Works with the Blender asset (TurretGun sub-models MachineGun /
-- RocketPod / MissileRack, muzzles RocketMuzzle / MissileMuzzle) and falls
-- back to the primitive placeholder parts (Barrel, RocketPod, MissileRail,
-- Missile). Runs after AimController has pivoted the gun each frame.

local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local TurretPose = {}

type Group = {
	items: { { inst: PVInstance, base: CFrame } },
	hinge: CFrame, -- relative to the gun pivot
	stowed: CFrame,
	active: CFrame,
	t: number,
	missiles: { BasePart },
}

local CANDIDATES: { [string]: { { string } } } = {
	MG = { { "MachineGun" }, { "Barrel", "BarrelShroud", "Muzzle" } },
	Rocket = { { "RocketPod" } },
	Missile = { { "MissileRack" }, { "MissileRail", "Missile" } },
}

local POSES = {
	MG = { stowed = CFrame.new(0, -0.1, 0.7), active = CFrame.identity },
	Rocket = { stowed = CFrame.new(0, -0.35, 0.2) * CFrame.Angles(math.rad(-16), 0, 0), active = CFrame.new(0, 0.3, -0.25) },
	Missile = { stowed = CFrame.new(0, -0.35, 0.2) * CFrame.Angles(math.rad(-16), 0, 0), active = CFrame.new(0, 0.3, -0.25) },
}
local SWING_SPEED = 9 -- 1/s, about 0.2 s to swing into place

local gun: Model? = nil
local groups: { [string]: Group } = {}
local activeWeapon = "MG"
local missileLoaded = true
local missileShown: boolean? = nil

local function sizeOf(inst: PVInstance): Vector3
	if inst:IsA("BasePart") then
		return inst.Size
	elseif inst:IsA("Model") then
		return inst:GetExtentsSize()
	end
	return Vector3.one
end

-- Half the extent of a box (size, orientation `rel` in gun space) along
-- the gun-space `axis`.
local function halfExtent(rel: CFrame, size: Vector3, axis: Vector3): number
	return (math.abs(rel.RightVector:Dot(axis)) * size.X + math.abs(rel.UpVector:Dot(axis)) * size.Y + math.abs(rel.LookVector:Dot(axis)) * size.Z) / 2
end

local function findGun(): Model?
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local emplacement = battlefield and battlefield:FindFirstChild("Emplacement")
	local model = emplacement and emplacement:FindFirstChild("TurretGun")
	return if model and model:IsA("Model") then model else nil
end

local function buildGroup(model: Model, weapon: string): Group?
	local pivot = model:GetPivot()
	for _, names in CANDIDATES[weapon] do
		local items = {}
		for _, name in names do
			local inst = model:FindFirstChild(name)
			if inst and inst:IsA("PVInstance") then
				table.insert(items, { inst = inst, base = pivot:ToObjectSpace(inst:GetPivot()) })
			end
		end
		if #items > 0 then
			-- Hinge at the rear of the first piece so it swings like a mount.
			local first = items[1]
			local hinge = if weapon == "MG"
				then CFrame.identity
				else CFrame.new(first.base.Position + Vector3.new(0, 0, halfExtent(first.base, sizeOf(first.inst), Vector3.zAxis)))
			local missiles = {}
			for _, item in items do
				local inst = item.inst :: Instance
				if inst.Name == "Missile" and inst:IsA("BasePart") then
					table.insert(missiles, inst)
				end
				for _, d in inst:GetDescendants() do
					if d:IsA("BasePart") and string.match(d.Name, "^Missile%d*$") then
						table.insert(missiles, d)
					end
				end
			end
			local pose = POSES[weapon]
			return {
				items = items,
				hinge = hinge,
				stowed = pose.stowed,
				active = pose.active,
				t = if weapon == activeWeapon then 1 else 0,
				missiles = missiles,
			}
		end
	end
	return nil
end

local function discover()
	local model = findGun()
	if model == gun then
		return
	end
	gun = model
	table.clear(groups)
	missileShown = nil
	if not model then
		return
	end
	for weapon in CANDIDATES do
		local g = buildGroup(model, weapon)
		if g then
			groups[weapon] = g
		end
	end
end

local function setMissilesVisible(g: Group, visible: boolean)
	if missileShown == visible then
		return
	end
	missileShown = visible
	for _, part in g.missiles do
		part.Transparency = if visible then 0 else 1
	end
end

local function update(dt: number)
	discover()
	local model = gun
	if not model or not model.Parent then
		return
	end
	local pivot = model:GetPivot()
	local k = math.min(1, dt * SWING_SPEED)
	for weapon, g in groups do
		local goal = if weapon == activeWeapon then 1 else 0
		g.t += (goal - g.t) * k
		if math.abs(goal - g.t) < 0.002 then
			g.t = goal
		end
		local pose = g.stowed:Lerp(g.active, g.t)
		local swing = g.hinge * pose * g.hinge:Inverse()
		for _, item in g.items do
			if item.inst.Parent then
				item.inst:PivotTo(pivot * swing * item.base)
			end
		end
		if weapon == "Missile" then
			setMissilesVisible(g, missileLoaded)
		end
	end
end

function TurretPose.setActive(weapon: string)
	activeWeapon = weapon
end

function TurretPose.setMissileLoaded(loaded: boolean)
	missileLoaded = loaded
end

local function findMuzzle(model: Model, name: string): Vector3?
	local inst = model:FindFirstChild(name, true)
	if inst and inst:IsA("BasePart") then
		return inst.Position
	elseif inst and inst:IsA("Attachment") then
		return inst.WorldPosition
	end
	return nil
end

-- World position a rocket/missile visually leaves from, or nil.
function TurretPose.muzzle(weapon: string): Vector3?
	local model = gun
	if not model or not model.Parent then
		return nil
	end
	local named = findMuzzle(model, if weapon == "Rocket" then "RocketMuzzle" else "MissileMuzzle")
	if named then
		return named
	end
	local g = groups[weapon]
	if not g then
		return nil
	end
	local inst = if weapon == "Missile" and g.missiles[1] then g.missiles[1] else g.items[1].inst
	local gunCf = model:GetPivot()
	local rel = gunCf:ToObjectSpace(inst:GetPivot())
	local front = rel.Position - Vector3.new(0, 0, halfExtent(rel, sizeOf(inst), Vector3.zAxis))
	return gunCf:PointToWorldSpace(front)
end

function TurretPose.start()
	RunService:BindToRenderStep("RedMesaWeaponPose", Enum.RenderPriority.Camera.Value + 2, update)
end

return TurretPose
