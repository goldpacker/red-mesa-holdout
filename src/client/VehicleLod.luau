--!strict
-- Vehicle level of detail (face-lift HS-5, Phase 9). Client, rendering only:
-- nothing here touches what the server hits or moves.
--
-- Two layers:
--   1. Roblox's built-in mesh LOD. Every imported vehicle MeshPart keeps
--      RenderFidelity = Automatic (the default the rbxmx files leave), so
--      the engine already swaps in simplified meshes with distance.
--   2. Kit culling (this module). The crew-scale kit each vehicle carries on
--      the shared TrimEnemy sheet - parts named "*Kit" (HullKit, TurretKit,
--      BuggyKit, HeliKit, JetKit, DeckKit, CannonKit, TurretLeftKit, ...,
--      all CanQuery false, docs/ASSET_CONTRACTS.md) - is hidden with
--      LocalTransparencyModifier beyond LOD_IN studs, zoom-corrected like
--      EffectsLod (through the FOV 32 gunsight a vehicle 1000 studs out
--      looks as big as one at ~410 in the FOV 70 turret view). Past that
--      range the kit (jerrycans, periscopes, rails, whips, grilles) is under
--      2 px per stud on screen; the hull, turret, tracks and skirts that
--      carry the silhouette stay. Bigger vehicles carry bigger kit (the
--      crawler's 13-stud mast), so the distance scales with the vehicle's
--      length over a tank's, up to 2x (crawler 800, jet ~740, helicopter
--      ~570, tank and buggy 400). Hysteresis LOD_IN/LOD_OUT stops flicker.
--
-- Covers live enemies (Workspace.Enemies) and wrecks, including thrown
-- turrets (Workspace.Wrecks). The model root is never moved.
-- Studio QA: Workspace attribute VehicleLodOff = true shows every kit,
-- VehicleLodForce = true hides every kit (A/B captures, triangle counts).

local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local VehicleLod = {}

local LOD_IN = 400 -- zoom-corrected studs: kit hidden beyond this
local LOD_OUT = 370 -- ... and shown again inside this
local REF_HALF_FOV = math.tan(math.rad(35)) -- turret view, Config Camera.FOV_DEFAULT 70
local UPDATE = 0.2 -- s between passes
local REF_LENGTH = 26 -- studs: a tank's length (docs/ASSET_CONTRACTS.md scale)
local MAX_SCALE = 2

type Entry = { model: Model, kit: { BasePart }, far: boolean?, scale: number }

local entries: { [Model]: Entry } = {}
local started = false

local function kitParts(model: Model): { BasePart }
	local out = {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and not d.CanQuery and string.sub(d.Name, -3) == "Kit" then
			table.insert(out, d)
		end
	end
	return out
end

local function track(model: Instance)
	if not model:IsA("Model") or entries[model] then
		return
	end
	if model:GetAttribute("Kind") == "Infantry" then
		return
	end
	local kit = kitParts(model)
	if #kit > 0 then
		local ok, size = pcall(model.GetExtentsSize, model)
		local length = if ok then math.max((size :: Vector3).X, (size :: Vector3).Z) else REF_LENGTH
		entries[model] = { model = model, kit = kit, far = nil, scale = math.clamp(length / REF_LENGTH, 1, MAX_SCALE) }
	end
end

local function untrack(model: Instance)
	if model:IsA("Model") then
		entries[model] = nil
	end
end

local function zoomedDistance(camera: Camera, p: Vector3): number
	local zoom = math.tan(math.rad(camera.FieldOfView) * 0.5) / REF_HALF_FOV
	return (camera.CFrame.Position - p).Magnitude * zoom
end

local function apply(e: Entry, far: boolean)
	e.far = far
	local value = if far then 1 else 0
	for i = #e.kit, 1, -1 do
		local part = e.kit[i]
		if part.Parent and part:IsDescendantOf(e.model) then
			part.LocalTransparencyModifier = value
		else
			-- Moved to its own wreck (a thrown turret), which tracks it now.
			table.remove(e.kit, i)
		end
	end
end

local function pass()
	local camera = Workspace.CurrentCamera
	if not camera then
		return
	end
	local off = Workspace:GetAttribute("VehicleLodOff") == true
	local force = Workspace:GetAttribute("VehicleLodForce") == true
	for model, e in entries do
		if not model.Parent then
			entries[model] = nil
			continue
		end
		local far: boolean
		if off then
			far = false
		elseif force then
			far = true
		else
			local ok, pivot = pcall(model.GetPivot, model)
			if not ok then
				continue
			end
			local d = zoomedDistance(camera, (pivot :: CFrame).Position) / e.scale
			far = if e.far then d > LOD_OUT else d > LOD_IN
		end
		if far ~= e.far then
			apply(e, far)
		end
	end
end

local function watch(folderName: string)
	local function hook(folder: Instance)
		for _, child in folder:GetChildren() do
			track(child)
		end
		folder.ChildAdded:Connect(function(child)
			-- Enemy models arrive dressed; give replication a frame anyway.
			task.defer(track, child)
		end)
		folder.ChildRemoved:Connect(untrack)
	end
	local folder = Workspace:FindFirstChild(folderName)
	if folder then
		hook(folder)
	else
		local conn: RBXScriptConnection
		conn = Workspace.ChildAdded:Connect(function(child)
			if child.Name == folderName then
				conn:Disconnect()
				hook(child)
			end
		end)
	end
end

function VehicleLod.start()
	if started then
		return
	end
	started = true
	watch("Enemies")
	watch("Wrecks")
	local acc = 0
	RunService.Heartbeat:Connect(function(dt)
		acc += dt
		if acc >= UPDATE then
			acc = 0
			pass()
		end
	end)
end

-- Studio QA: how many tracked vehicles are drawing their kit / have it culled.
function VehicleLod.stats(): { near: number, far: number }
	local near, far = 0, 0
	for _, e in entries do
		if e.far then
			far += 1
		else
			near += 1
		end
	end
	return { near = near, far = far }
end

return VehicleLod
