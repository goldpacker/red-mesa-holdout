-- Camera tour that makes every staged texture resident (QA-B,
-- docs/PERF_BUDGET.md §5). Client datamodel, Studio playtest, after the
-- scene is staged. Roblox loads a texture's top mips only once it is drawn
-- large, so an "everything loaded" number needs close views of everything.
-- Returns GraphicsTexture before/after and the number of views.
local RunService = game:GetService("RunService")
local Stats = game:GetService("Stats")
local Players = game:GetService("Players")

local HOLD = 0.25
local camera = workspace.CurrentCamera
local target: CFrame? = nil
RunService:BindToRenderStep("QATour", Enum.RenderPriority.Last.Value + 20, function()
	if target then
		camera.CFrame = target
	end
end)

local function tex(): number
	return Stats:GetMemoryUsageMbForTag(Enum.DeveloperMemoryTag.GraphicsTexture)
end
local views = 0
local function look(from: Vector3, at: Vector3, hold: number?)
	target = CFrame.lookAt(from, at)
	views += 1
	task.wait(hold or HOLD)
end
local function closeUp(inst: Instance, distance: number?, both: boolean?)
	local cf, size
	if inst:IsA("Model") then
		cf, size = inst:GetBoundingBox()
	elseif inst:IsA("BasePart") then
		cf, size = inst.CFrame, inst.Size
	else
		return
	end
	local r = distance or math.max(size.Magnitude * 0.8, 8)
	local c = cf.Position
	look(c + Vector3.new(r, r * 0.35, r), c)
	if both then
		look(c + Vector3.new(-r, r * 0.35, -r), c)
	end
end

local before = tex()
-- 1. All round from the turret, level and looking down.
local pivot = Vector3.new(0, 80, 0)
for i = 0, 11 do
	local a = math.rad(i * 30)
	local dir = Vector3.new(math.sin(a), 0, -math.cos(a))
	look(pivot, pivot + dir * 100 + Vector3.new(0, -8, 0))
	look(pivot, pivot + dir * 100 + Vector3.new(0, -45, 0))
end
-- 2. Beauty-shot free cameras (flank, night) and a high basin overview.
look(Vector3.new(430, 70, -700), Vector3.new(-20, 25, -190), 0.6)
look(Vector3.new(95, 30, -560), Vector3.new(-50, 70, -40), 0.6)
look(Vector3.new(0, 400, 300), Vector3.new(0, 0, -700), 0.6)
-- 3. Close-ups of every enemy, wreck and crate model.
for _, name in { "Enemies", "Wrecks", "Crates" } do
	local folder = workspace:FindFirstChild(name)
	if folder then
		for _, m in folder:GetChildren() do
			closeUp(m, nil, true)
		end
	end
end
-- 4. Every textured MeshPart larger than 20 studs (landscape chunks, cliff
--    kit, the emplacement's big pieces), and one of each smaller mesh.
local seenMesh: { [string]: boolean } = {}
for _, d in workspace:GetDescendants() do
	if d:IsA("MeshPart") and d:FindFirstChildOfClass("SurfaceAppearance") then
		local big = d.Size.Magnitude > 20
		local key = d.MeshId
		if big or not seenMesh[key] then
			seenMesh[key] = true
			closeUp(d, if big then d.Size.Magnitude * 0.6 else nil, big)
		end
	end
end
-- 5. The gunsight (aiming) for a moment.
target = nil
local player = Players.LocalPlayer
player:SetAttribute("DebugAiming", true)
task.wait(1.5)
player:SetAttribute("DebugAiming", false)
task.wait(1)
RunService:UnbindFromRenderStep("QATour")
task.wait(3)
return string.format("tour: %d views; GraphicsTexture %.1f -> %.1f MB", views, before, tex())
