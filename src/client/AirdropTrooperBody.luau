--!strict
-- The paratrooper's body for the airdrop descent (AD-2): a client clone of
-- the skinned infantry (Infantry_Skinned_<Variant>, CHAR-2) at the landed
-- enemy's scale, posed with Bone.Transform (hanging in the harness, arms
-- up on the risers, legs dangling; tucked in free fall; the landing flare).
-- Falls back to a clone of the rigid `Infantry` asset (static) when the
-- skinned templates can't be prepared.
--
-- Skinning (docs/ASSET_PIPELINE.md "Skinned meshes", gotcha 1): a MeshPart
-- built by Rojo isn't skinned. Each variant is prepared once here, on a
-- private clone of the template (ApplyMesh of a fresh CreateMeshPartAsync),
-- and every load clones that. The mesh is jointed straight to its bone
-- holder (anchor -> SkinRoot -> Body/BodyLOD, gotcha 2).

local AssetService = game:GetService("AssetService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AssetLibrary = require(ReplicatedStorage.Shared.AssetLibrary)
local Pose = require(script.Parent.InfantryRigPose)
local Style = require(script.Parent.AirdropStyle)

local Body = {}

local VARIANTS = { "Rifleman", "Grenadier", "Rifleman", "Radio" }
local prepared: { [string]: Model } = {}
local preparing = false

export type B = {
	model: Model,
	parts: { BasePart },
	skinRoot: BasePart?,
	full: BasePart?,
	lod: BasePart?,
	useLod: boolean,
	bones: { Bone }, -- Pose.BONES order
	nextPose: number,
	seed: number,
}

---------------------------------------------------------------------------
-- Poses (Bone.Transform Euler degrees, Pose.BONES names; Hips carries an
-- offset too). Model faces -Z; +X rotation swings a limb forward, +Z swings
-- the right arm out (left arm: -Z).
---------------------------------------------------------------------------
type PoseTable = { [string]: { number } }

local HANG: PoseTable = {
	Hips = { 0, 0, 0, 0, 0, 0 },
	Spine = { 3, 0, 0 },
	Chest = { 2, 0, 0 },
	NeckBone = { -4, 0, 0 },
	HeadBone = { 6, 0, 0 },
	RightUpperArm = { 8, 0, 122 },
	RightLowerArm = { 0, 0, 75 },
	RightHand = { 0, 0, 0 },
	LeftUpperArm = { 8, 0, -122 },
	LeftLowerArm = { 0, 0, -75 },
	LeftHand = { 0, 0, 0 },
	RightUpperLeg = { 12, 0, -2 },
	RightLowerLeg = { -20, 0, 0 },
	RightFoot = { 22, 0, 0 },
	LeftUpperLeg = { 8, 0, 2 },
	LeftLowerLeg = { -16, 0, 0 },
	LeftFoot = { 22, 0, 0 },
}

-- Free fall: chin down, arms braced forward, legs together and bent.
local TUCK: PoseTable = {
	Hips = { 0, 0, 0, 0, 0, 0 },
	Spine = { 12, 0, 0 },
	Chest = { 8, 0, 0 },
	NeckBone = { 10, 0, 0 },
	HeadBone = { 8, 0, 0 },
	RightUpperArm = { 24, 0, -4 },
	RightLowerArm = { 45, 0, 0 },
	RightHand = { 0, 0, 0 },
	LeftUpperArm = { 24, 0, 4 },
	LeftLowerArm = { 45, 0, 0 },
	LeftHand = { 0, 0, 0 },
	RightUpperLeg = { 28, 0, -3 },
	RightLowerLeg = { -45, 0, 0 },
	RightFoot = { 15, 0, 0 },
	LeftUpperLeg = { 28, 0, 3 },
	LeftLowerLeg = { -45, 0, 0 },
	LeftFoot = { 15, 0, 0 },
}

-- Landing flare: risers pulled down, feet and knees together, knees soft.
local FLARE: PoseTable = {
	Hips = { 0, 0, 0, 0, 0, 0 },
	Spine = { 6, 0, 0 },
	Chest = { 4, 0, 0 },
	NeckBone = { 6, 0, 0 },
	HeadBone = { 8, 0, 0 },
	RightUpperArm = { 20, 0, 98 },
	RightLowerArm = { 0, 0, 95 },
	RightHand = { 0, 0, 0 },
	LeftUpperArm = { 20, 0, -98 },
	LeftLowerArm = { 0, 0, -95 },
	LeftHand = { 0, 0, 0 },
	RightUpperLeg = { 22, 0, -3 },
	RightLowerLeg = { -30, 0, 0 },
	RightFoot = { 10, 0, 0 },
	LeftUpperLeg = { 22, 0, 3 },
	LeftLowerLeg = { -30, 0, 0 },
	LeftFoot = { 10, 0, 0 },
}

local function compile(t: PoseTable): { CFrame }
	local out = {}
	for i, name in Pose.BONES do
		local r = t[name] or { 0, 0, 0 }
		local cf = CFrame.Angles(math.rad(r[1]), math.rad(r[2]), math.rad(r[3]))
		if r[4] then
			cf = CFrame.new(r[4], r[5], r[6]) * cf
		end
		out[i] = cf
	end
	return out
end

Body.POSES = { Hang = compile(HANG), Tuck = compile(TUCK), Flare = compile(FLARE) }

---------------------------------------------------------------------------
-- Templates
---------------------------------------------------------------------------

local function skin(part: Instance?): boolean
	if not (part and part:IsA("MeshPart")) then
		return false
	end
	if part.HasSkinnedMesh then
		return true
	end
	local ok = pcall(function()
		local fresh = AssetService:CreateMeshPartAsync(Content.fromUri(part.MeshId), {
			CollisionFidelity = Enum.CollisionFidelity.Box,
		})
		part:ApplyMesh(fresh)
		fresh:Destroy()
	end)
	return ok and part.HasSkinnedMesh
end

-- Prepares the skinned variants once (yields; call from a task).
function Body.prepare()
	if preparing then
		return
	end
	preparing = true
	for _, variant in { "Rifleman", "Grenadier", "Radio" } do
		local copy = AssetLibrary.clone("Infantry_Skinned_" .. variant)
		if copy and copy:IsA("Model") then
			local root = copy:FindFirstChild("Root")
			if root and root:IsA("BasePart") and skin(copy:FindFirstChild("Body")) then
				skin(copy:FindFirstChild("BodyLOD"))
				copy.PrimaryPart = root
				copy:ScaleTo(Style.Trooper.SCALE)
				copy:PivotTo(CFrame.identity)
				prepared[variant] = copy
			else
				copy:Destroy()
			end
		elseif copy then
			copy:Destroy()
		end
	end
end

function Body.ready(): boolean
	return next(prepared) ~= nil
end

---------------------------------------------------------------------------
-- Build
---------------------------------------------------------------------------

local function quiet(p: BasePart)
	p.Anchored = false
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Massless = true
end

local function weld(part0: BasePart, part1: BasePart, c0: CFrame): Weld
	local w = Instance.new("Weld")
	w.Name = "AirdropWeld"
	w.Part0 = part0
	w.Part1 = part1
	w.C0 = c0
	w.Parent = part1
	return w
end

-- Skinned body hung from `anchor` (at the harness = shoulders), or nil.
local function skinned(parent: Instance, anchor: BasePart, seed: number): B?
	local variant = VARIANTS[seed % #VARIANTS + 1]
	local template = prepared[variant] or prepared.Rifleman or select(2, next(prepared))
	if not template then
		return nil
	end
	local model = (template :: Model):Clone()
	model.Name = "Trooper"
	local skinRoot = model:FindFirstChild("Root") :: BasePart
	local full = model:FindFirstChild("Body") :: BasePart?
	local lod = model:FindFirstChild("BodyLOD") :: BasePart?
	skinRoot.Name = "SkinRoot"
	skinRoot.Transparency = 1
	quiet(skinRoot)
	weld(anchor, skinRoot, CFrame.new(0, -Style.Trooper.ROOT_BELOW_HARNESS, 0))
	local parts: { BasePart } = {}
	for _, p in { full, lod } do
		if p then
			quiet(p)
			p.CastShadow = true
			weld(skinRoot, p, skinRoot.CFrame:ToObjectSpace(p.CFrame))
			table.insert(parts, p)
		end
	end
	if full then
		full.Transparency = 1
	end
	if lod then
		lod.Transparency = 0
	elseif full then
		full.Transparency = 0
	end
	local bones: { Bone } = {}
	for i, name in Pose.BONES do
		local b = skinRoot:FindFirstChild(name, true)
		if b and b:IsA("Bone") then
			bones[i] = b
		end
	end
	model.Parent = parent
	return {
		model = model,
		parts = parts,
		skinRoot = skinRoot,
		full = full,
		lod = lod,
		useLod = lod ~= nil,
		bones = bones,
		nextPose = 0,
		seed = seed,
	}
end

-- Static fallback: the rigid soldier, feet on the load point.
local function rigid(parent: Instance, anchor: BasePart): B
	local model = Instance.new("Model")
	model.Name = "Trooper"
	local copy = AssetLibrary.clone("Infantry")
	local parts: { BasePart } = {}
	if copy and copy:IsA("Model") then
		copy:ScaleTo(copy:GetScale() * Style.Trooper.SCALE)
		copy:PivotTo(CFrame.identity)
		local box, size = copy:GetBoundingBox()
		local shift = CFrame.new(-box.Position.X, size.Y / 2 - box.Position.Y - Style.Trooper.HARNESS_UP, -box.Position.Z)
		for _, d in copy:GetDescendants() do
			if d:IsA("BaseScript") or d:IsA("JointInstance") or d:IsA("WeldConstraint") or d:IsA("Light") then
				d:Destroy()
			end
		end
		for _, d in copy:GetDescendants() do
			if d:IsA("BasePart") then
				quiet(d)
				if d.Name == "Root" or d.Transparency > 0.95 then
					d.Transparency = 1
				end
				weld(anchor, d, shift * d.CFrame)
				table.insert(parts, d)
			end
		end
		copy.Parent = model
	else
		if copy then
			copy:Destroy()
		end
		local p = Instance.new("Part")
		p.Name = "Hull"
		p.Size = Vector3.new(2, 6.5, 1.4)
		p.Color = Color3.fromRGB(56, 58, 64)
		p.Material = Enum.Material.Fabric
		quiet(p)
		p.Parent = model
		weld(anchor, p, CFrame.new(0, 3.25 - Style.Trooper.HARNESS_UP, 0))
		table.insert(parts, p)
	end
	model.Parent = parent
	return { model = model, parts = parts, skinRoot = nil, full = nil, lod = nil, useLod = false, bones = {}, nextPose = math.huge, seed = 0 }
end

function Body.new(parent: Instance, anchor: BasePart, seed: number): B
	return skinned(parent, anchor, seed) or rigid(parent, anchor)
end

---------------------------------------------------------------------------
-- Pose
---------------------------------------------------------------------------

local function blend(a: { CFrame }, b: { CFrame }, w: number, i: number): CFrame
	if w <= 0 then
		return a[i]
	elseif w >= 1 then
		return b[i]
	end
	return a[i]:Lerp(b[i], w)
end

local LEGS = { Pose.index.RightUpperLeg, Pose.index.LeftUpperLeg, Pose.index.RightLowerLeg, Pose.index.LeftLowerLeg }

-- Poses the bones: `tuck` 0..1 (free fall), `flare` 0..1 (landing), and a
-- slow leg dangle. Distant bodies update less often; LOD mesh by distance.
function Body.pose(b: B, now: number, tuck: number, flare: number, viewDistance: number)
	if #b.bones == 0 or now < b.nextPose then
		return
	end
	local T = Style.Trooper
	b.nextPose = now + (if viewDistance < 400 then T.POSE_RATE_NEAR else T.POSE_RATE_FAR)
	local wantLod = viewDistance > T.LOD_BODY
	if wantLod ~= b.useLod and b.lod and b.full then
		b.useLod = wantLod
		b.lod.Transparency = if wantLod then 0 else 1
		b.full.Transparency = if wantLod then 1 else 0
	end
	local P = Body.POSES
	local dangle = math.sin(now * 1.7 + b.seed) * 0.5 + 0.5
	for i, bone in b.bones do
		local cf = blend(P.Hang, P.Tuck, tuck, i)
		if flare > 0 then
			cf = cf:Lerp(P.Flare[i], math.clamp(flare, 0, 1))
		end
		bone.Transform = cf
	end
	-- Legs swing a little on their own (not in the tuck or the flare).
	local free = (1 - tuck) * (1 - flare)
	if free > 0.01 then
		for k, i in LEGS do
			local bone = b.bones[i]
			if bone then
				local side = if k % 2 == 0 then -1 else 1
				local a = math.rad(5) * free * (dangle - 0.5) * side * (if k > 2 then 0.8 else 1)
				bone.Transform = bone.Transform * CFrame.Angles(a, 0, 0)
			end
		end
	end
end

-- Hides the body (the landed enemy took over).
function Body.hide(b: B)
	for _, p in b.parts do
		p.Transparency = 1
	end
	b.nextPose = math.huge
end

function Body.destroy(b: B)
	b.model:Destroy()
end

return Body
