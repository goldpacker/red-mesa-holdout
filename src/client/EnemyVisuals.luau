--!strict
-- Procedural limb animation for infantry, driven by the server-set "State"
-- attribute. Motor6D.Transform is local-only, so this costs no bandwidth.
-- Also starts VehicleFx (vehicle animation and destruction effects).

local Lighting = game:GetService("Lighting")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local VehicleFx = require(script.Parent.VehicleFx)

local EnemyVisuals = {}

type Rig = { [string]: Motor6D }
local rigs: { [Model]: Rig } = {}

local function rigFor(model: Model): Rig?
	local rig = rigs[model]
	if rig then
		return rig
	end
	local torso = model:FindFirstChild("Torso")
	local root = model:FindFirstChild("Root")
	if not torso or not root then
		return nil
	end
	rig = {}
	for _, name in { "LeftHip", "RightHip", "LeftShoulder", "RightShoulder" } do
		local m = torso:FindFirstChild(name)
		if m and m:IsA("Motor6D") then
			rig[name] = m
		end
	end
	local rootJoint = root:FindFirstChild("RootJoint")
	if rootJoint and rootJoint:IsA("Motor6D") then
		rig.RootJoint = rootJoint
	end
	rigs[model] = rig
	return rig
end

local function animate(model: Model, rig: Rig, t: number)
	local state = model:GetAttribute("State")
	local phase = t * 7 + (model:GetAttribute("EnemyId") :: number? or 0)
	local lh, rh, ls, rs = rig.LeftHip, rig.RightHip, rig.LeftShoulder, rig.RightShoulder
	if not (lh and rh and ls and rs) then
		return
	end
	if state == "Walk" then
		local swing = math.sin(phase) * 0.7
		lh.Transform = CFrame.Angles(swing, 0, 0)
		rh.Transform = CFrame.Angles(-swing, 0, 0)
		ls.Transform = CFrame.Angles(-swing * 0.6, 0, 0)
		-- Models face -Z, so a positive X rotation swings an arm forward.
		rs.Transform = CFrame.Angles(math.rad(40), 0, 0)
		if rig.RootJoint then
			rig.RootJoint.Transform = CFrame.new(0, math.abs(math.sin(phase)) * 0.25, 0)
		end
	elseif state == "Aim" then
		lh.Transform = CFrame.Angles(math.rad(-10), 0, 0)
		rh.Transform = CFrame.Angles(math.rad(20), 0, 0)
		ls.Transform = CFrame.Angles(math.rad(80), math.rad(-25), 0)
		rs.Transform = CFrame.Angles(math.rad(90), 0, 0)
	elseif state == "Throw" then
		local wind = (math.sin(t * 2.2 + phase) + 1) / 2
		lh.Transform = CFrame.Angles(math.rad(-15), 0, 0)
		rh.Transform = CFrame.Angles(math.rad(15), 0, 0)
		ls.Transform = CFrame.Angles(math.rad(30), 0, 0)
		-- Wind back behind the shoulder, then over the top and forward.
		rs.Transform = CFrame.Angles(math.rad(-50 + 210 * wind), 0, 0)
	else
		lh.Transform = CFrame.identity
		rh.Transform = CFrame.identity
		ls.Transform = CFrame.identity
		rs.Transform = CFrame.identity
	end
end

local function isNight(): boolean
	local t = Lighting.ClockTime
	return t >= 18.3 or t < 6
end

-- Helmet lamps keep soldiers readable at dusk and night.
local function setLamp(model: Model, on: boolean)
	local lamp = model:FindFirstChild("HelmetLamp")
	if lamp and lamp:IsA("BasePart") and (lamp.Transparency < 0.5) ~= on then
		lamp.Transparency = if on then 0 else 1
		local light = lamp:FindFirstChildWhichIsA("PointLight")
		if light then
			light.Enabled = on
		end
	end
end

function EnemyVisuals.start()
	VehicleFx.start()
	local lampClock = 0
	RunService.Heartbeat:Connect(function(dt)
		lampClock -= dt
		if lampClock > 0 then
			return
		end
		lampClock = 0.5
		local night = isNight()
		local folder = Workspace:FindFirstChild("Enemies")
		if folder then
			for _, model in folder:GetChildren() do
				if model:IsA("Model") and model.Name == "Infantry" then
					setLamp(model, night and model:GetAttribute("State") ~= "Dead")
				end
			end
		end
	end)
	local enemies = Workspace:WaitForChild("Enemies")
	enemies.ChildRemoved:Connect(function(child)
		rigs[child :: Model] = nil
	end)
	RunService.Stepped:Connect(function(t)
		for _, model in enemies:GetChildren() do
			if model:IsA("Model") and model.Name == "Infantry" then
				local rig = rigFor(model)
				if rig then
					animate(model, rig, t)
				end
			end
		end
	end)
end

return EnemyVisuals
