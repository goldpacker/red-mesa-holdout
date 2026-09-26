--!strict
-- Turns a built or imported vehicle model into a single moving assembly:
-- Root stays anchored (the server only ever sets Root.CFrame, so one
-- CFrame replicates per vehicle); every other part is unanchored and
-- welded to Root. Named "movers" (turrets, rotors, wheels) get a Motor6D
-- named "<Name>Motor" in Root so the client can animate them through
-- Motor6D.Transform (see client/VehicleFx).

local Rig = {}

local function primaryOf(inst: Instance): BasePart?
	if inst:IsA("BasePart") then
		return inst
	end
	if inst:IsA("Model") then
		if inst.PrimaryPart then
			return inst.PrimaryPart
		end
		local best: BasePart? = nil
		local bestVolume = -1
		for _, d in inst:GetDescendants() do
			if d:IsA("BasePart") then
				local v = d.Size.X * d.Size.Y * d.Size.Z
				if v > bestVolume then
					best, bestVolume = d, v
				end
			end
		end
		return best
	end
	return nil
end

local function pivotOf(inst: Instance): CFrame
	if inst:IsA("Model") then
		return inst:GetPivot()
	end
	return (inst :: BasePart).CFrame
end

local function weld(a: BasePart, b: BasePart)
	local w = Instance.new("WeldConstraint")
	w.Part0 = a
	w.Part1 = b
	w.Parent = b
end

-- `movers` lists child names (Models or BaseParts anywhere in the model)
-- that should pivot relative to Root. Nested movers are not supported;
-- parts under a mover follow it. Returns Root.
function Rig.prepare(model: Model, movers: { string }): BasePart
	local root = model:FindFirstChild("Root", true) :: BasePart
	assert(root and root:IsA("BasePart"), model.Name .. " has no Root part")
	-- Keep the model's authored pivot (ground centre / centre of mass).
	local pivot = model:GetPivot()
	model.PrimaryPart = root
	root.PivotOffset = root.CFrame:ToObjectSpace(pivot)

	-- Map every part to the mover group it belongs to (if any).
	local groupOf: { [BasePart]: string } = {}
	local groupPrimary: { [string]: BasePart } = {}
	local groupPivot: { [string]: CFrame } = {}
	for _, name in movers do
		local inst = model:FindFirstChild(name, true)
		local primary = inst and primaryOf(inst)
		if inst and primary then
			groupPrimary[name] = primary
			groupPivot[name] = pivotOf(inst)
			if inst:IsA("BasePart") then
				groupOf[inst] = name
			end
			for _, d in inst:GetDescendants() do
				if d:IsA("BasePart") then
					groupOf[d] = name
				end
			end
		end
	end

	-- Drop joints the source model may have carried.
	for _, d in model:GetDescendants() do
		if d:IsA("JointInstance") or d:IsA("WeldConstraint") then
			d:Destroy()
		end
	end

	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.CanCollide = false
			d.CanTouch = false
			d.Massless = true
			if d == root then
				d.Anchored = true
				continue
			end
			d.Anchored = false
			local group = groupOf[d]
			if group then
				local primary = groupPrimary[group]
				if d ~= primary then
					weld(primary, d)
				end
			else
				weld(root, d)
			end
		end
	end

	for name, primary in groupPrimary do
		if primary == root then
			continue
		end
		local pivot = groupPivot[name]
		local motor = Instance.new("Motor6D")
		motor.Name = name .. "Motor"
		motor.Part0 = root
		motor.Part1 = primary
		motor.C0 = root.CFrame:ToObjectSpace(pivot)
		motor.C1 = primary.CFrame:ToObjectSpace(pivot)
		motor.Parent = root
	end
	return root
end

-- Root's CFrame relative to the model's pivot (ground centre for ground
-- vehicles), so movement code can place a vehicle by its ground contact
-- point: root.CFrame = ground * offset. Call after Rig.prepare.
function Rig.rootOffset(root: BasePart): CFrame
	return root.PivotOffset:Inverse()
end

return Rig
