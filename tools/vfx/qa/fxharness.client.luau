--!nocheck
-- VFX capture harness (Studio playtest only, Client datamodel).
-- Install once per Play session by pasting this whole file into MCP
-- execute_luau (Client); it creates ReplicatedStorage.FxHarness (a local
-- ModuleScript) and returns "installed". Later snippets use:
--   local H = require(game.ReplicatedStorage.FxHarness)
--   H.aimAt(Vector3.new(-40, 0, -260), true)   -- y = 0: snap to ground
--   H.fire(true); task.wait(1); return "firing"
-- Drives the real client code paths only through the Studio debug hooks
-- (DebugYaw/DebugPitch/DebugAiming/DebugFire/DebugWeapon). `freeze`
-- pauses every ParticleEmitter (TimeScale 0) and sets Workspace attribute
-- FxFreeze (client/Effects stops advancing tracers/debris while it is set).
local source = [==[
local Players = game:GetService("Players")
local Workspace = game:GetService("Workspace")
local H = {}
local PIVOT = Vector3.new(0, 72, 0)
local player = Players.LocalPlayer

function H.groundY(x, z)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { Workspace.Terrain }
	local hit = Workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -800, 0), params)
	return hit and hit.Position.Y or 0
end

function H.angles(pos)
	local d = pos - PIVOT
	local yaw = math.deg(math.atan2(-d.X, -d.Z))
	local pitch = math.deg(math.atan2(d.Y, Vector2.new(d.X, d.Z).Magnitude))
	return yaw, pitch
end

-- Aims the turret at a world point (y == 0 snaps it to the terrain).
function H.aimAt(pos, aiming)
	if pos.Y == 0 then
		pos = Vector3.new(pos.X, H.groundY(pos.X, pos.Z), pos.Z)
	end
	local yaw, pitch = H.angles(pos)
	H.aim(yaw, pitch, aiming)
	return yaw, pitch
end

function H.aim(yaw, pitch, aiming)
	player:SetAttribute("DebugYaw", yaw)
	player:SetAttribute("DebugPitch", pitch)
	player:SetAttribute("DebugAiming", aiming == true)
end

function H.fire(on)
	player:SetAttribute("DebugFire", on == true)
end

function H.weapon(w)
	player:SetAttribute("DebugWeapon", w)
end

-- One trigger press (rockets/missiles fire on the press edge).
function H.pull()
	H.fire(true)
	task.wait(0.12)
	H.fire(false)
end

function H.enemy(kind)
	for _, folderName in { "Enemies", "Wrecks" } do
		local folder = Workspace:FindFirstChild(folderName)
		for _, m in folder and folder:GetChildren() or {} do
			if m:GetAttribute("Kind") == kind then
				return m
			end
		end
	end
	return nil
end

function H.centre(model)
	local cf = model:GetBoundingBox()
	return cf.Position
end

function H.freeze()
	Workspace:SetAttribute("FxFreeze", true)
	for _, d in Workspace:GetDescendants() do
		if d:IsA("ParticleEmitter") then
			d.TimeScale = 0
		end
	end
end

function H.unfreeze()
	Workspace:SetAttribute("FxFreeze", nil)
	for _, d in Workspace:GetDescendants() do
		if d:IsA("ParticleEmitter") then
			d.TimeScale = 1
		end
	end
end

-- Freezes `delay` s after an instance named `name` appears (e.g. an
-- "EnemyProjectile"), to catch an impact at a known phase.
function H.watch(name, delay)
	local conn
	conn = Workspace.DescendantAdded:Connect(function(d)
		if d.Name == name then
			conn:Disconnect()
			task.delay(delay, H.freeze)
		end
	end)
	task.delay(20, function()
		conn:Disconnect()
	end)
end

-- Fixed free camera (look-dev boards); H.boardEnd() gives it back.
function H.board(camAt, lookAt, fov)
	local camera = Workspace.CurrentCamera
	game:GetService("RunService"):BindToRenderStep("FxBoard", Enum.RenderPriority.Last.Value + 20, function()
		camera.CFrame = CFrame.lookAt(camAt, lookAt)
		camera.FieldOfView = fov or 50
	end)
end

function H.boardEnd()
	game:GetService("RunService"):UnbindFromRenderStep("FxBoard")
end

-- Raycast from the pivot along yaw/pitch: what the MG would hit.
function H.probe(yaw, pitch)
	local look = (CFrame.new(PIVOT) * CFrame.Angles(0, math.rad(yaw), 0) * CFrame.Angles(math.rad(pitch), 0, 0)).LookVector
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { Workspace.Battlefield.Emplacement }
	local hit = Workspace:Raycast(PIVOT + look * 6, look * 1600, params)
	if not hit then
		return "nothing"
	end
	return string.format("%s %s %s (%.0f,%.0f,%.0f) d=%.0f", hit.Instance:GetFullName(), tostring(hit.Material), tostring(hit.Normal), hit.Position.X, hit.Position.Y, hit.Position.Z, (hit.Position - PIVOT).Magnitude)
end

-- Counts live effect instances (for the perf notes).
function H.counts()
	local emitters, particlesOn, beams, lights, parts = 0, 0, 0, 0, 0
	for _, d in Workspace:GetDescendants() do
		if d:IsA("ParticleEmitter") then
			emitters += 1
			if d.Enabled then
				particlesOn += 1
			end
		elseif d:IsA("Beam") then
			beams += 1
		elseif d:IsA("Light") and d.Enabled then
			lights += 1
		end
	end
	local fx = Workspace:FindFirstChild("CombatFx")
	parts = fx and #fx:GetChildren() or 0
	return string.format("emitters %d (on %d) beams %d lights %d fxparts %d", emitters, particlesOn, beams, lights, parts)
end

return H
]==]
local rs = game:GetService("ReplicatedStorage")
local old = rs:FindFirstChild("FxHarness")
if old then
	old:Destroy()
end
local m = Instance.new("ModuleScript")
m.Name = "FxHarness"
m.Source = source
m.Parent = rs
return "installed"
