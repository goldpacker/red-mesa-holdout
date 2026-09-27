-- Texture memory calibration (QA-B, docs/PERF_BUDGET.md §5). Client
-- datamodel, fresh Studio playtest (title), QualityLevel 15, after the
-- 40 s terrain wait. Shows textures that nothing in the scene uses yet on a
-- screen-filling mesh high above the world, one experiment at a time, and
-- records how much GraphicsTexture grows. Removing a texture doesn't free
-- its memory reliably (the cache keeps it), so this adds instead: every
-- experiment must use ids that are not resident yet.
--   return _G.QACalib.run(1, 5)
local RunService = game:GetService("RunService")
local Stats = game:GetService("Stats")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local function id(n: string): string
	return "rbxassetid://" .. n
end

-- Unused in a fresh title session at Afternoon (tools/qa/texture_map.py):
-- rigid Infantry set (1024², no longer drawn since CHAR-2), SupplyCrate
-- (1024²/512², only while a crate falls), VfxDebris (512², only on
-- explosions), Sunset sky faces (1024² RGBA, opaque), Gunsights (1024²).
local EXPERIMENTS = {
	{ name = "SA colour 1024 RGB (Infantry)", sa = { ColorMap = id("134939120069664") } },
	{ name = "SA normal 1024 RGB (Infantry)", sa = { NormalMap = id("77528582608279") } },
	{ name = "SA rough 1024 L (Infantry)", sa = { RoughnessMap = id("127206998440979") } },
	{ name = "SA metal 1024 L (Infantry)", sa = { MetalnessMap = id("103818437308657") } },
	{ name = "SA full set 1024 RGB x4 (SupplyCrate main)", sa = {
		ColorMap = id("73209436041062"), NormalMap = id("107665647166257"),
		RoughnessMap = id("135979901582421"), MetalnessMap = id("134684642630387") } },
	{ name = "SA full set 512 (VfxDebris)", sa = {
		ColorMap = id("109435103168248"), NormalMap = id("102552230643784"),
		RoughnessMap = id("88890466724347"), MetalnessMap = id("81215834459528") } },
	{ name = "SA colour 1024 RGBA opaque (Sunset sky Ft)", sa = { ColorMap = id("122718924848530") } },
	{ name = "Decal 1024 RGBA opaque (Sunset sky Bk)", decal = id("112841514772254") },
	{ name = "SA colour 1024 RGB (Gunsights sights)", sa = { ColorMap = id("87952288802766") } },
	{ name = "SA normal 1024 RGB (Gunsights sights)", sa = { NormalMap = id("124225991884726") } },
}

local function tex(): number
	return Stats:GetMemoryUsageMbForTag(Enum.DeveloperMemoryTag.GraphicsTexture)
end

local function settle(maxWait: number): (number, number)
	local started = os.clock()
	local last = tex()
	local stable = 0
	while os.clock() - started < maxWait do
		task.wait(0.5)
		local now = tex()
		if math.abs(now - last) < 0.02 then
			stable += 1
			if stable >= 6 then
				return now, os.clock() - started
			end
		else
			stable = 0
		end
		last = now
	end
	return last, os.clock() - started
end

-- A plain mesh to carry the appearance: the rock slab's MeshPart (UVs over
-- the whole 0..1 square are not needed; the part fills the screen, so the
-- top mip is sampled).
local function template(): MeshPart
	local model = ReplicatedStorage.Assets:FindFirstChild("Rock_Slab")
	local part = model and model:FindFirstChildWhichIsA("MeshPart", true)
	assert(part, "Rock_Slab MeshPart not found")
	return part :: MeshPart
end

local ORIGIN = Vector3.new(0, 3000, 0)
local camera = workspace.CurrentCamera
RunService:BindToRenderStep("QACalib", Enum.RenderPriority.Last.Value + 30, function()
	camera.CFrame = CFrame.lookAt(ORIGIN, ORIGIN + Vector3.new(0, 0.35, -1))
end)

local current: Instance? = nil
local function show(e: any): Instance
	local part = template():Clone()
	for _, c in part:GetChildren() do
		c:Destroy()
	end
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.Material = Enum.Material.SmoothPlastic
	part.Size = part.Size * (60 / part.Size.Magnitude)
	part.CFrame = CFrame.lookAt(ORIGIN + Vector3.new(0, 7, -20), ORIGIN)
	if e.sa then
		local sa = Instance.new("SurfaceAppearance")
		for prop, value in e.sa do
			(sa :: any)[prop] = value
		end
		sa.Parent = part
	elseif e.decal then
		for _, face in Enum.NormalId:GetEnumItems() do
			local d = Instance.new("Decal")
			d.Texture = e.decal
			d.Face = face
			d.Parent = part
		end
	end
	part.Parent = workspace
	return part
end

local QACalib = { log = {} :: { string } }
function QACalib.run(first: number, last: number): string
	local lines = {}
	local base = settle(6)
	for i = first, math.min(last, #EXPERIMENTS) do
		local e = EXPERIMENTS[i]
		if current then
			current:Destroy()
		end
		current = show(e)
		local after, waited = settle(12)
		local line = string.format("%02d %-46s %7.2f -> %7.2f  (+%5.2f MB)  %.1fs", i, e.name, base, after, after - base, waited)
		table.insert(lines, line)
		table.insert(QACalib.log, line)
		base = after
	end
	return table.concat(lines, "\n")
end
function QACalib.stop(): string
	if current then
		current:Destroy()
	end
	RunService:UnbindFromRenderStep("QACalib")
	return "calibration camera released"
end

_G.QACalib = QACalib
return string.format("installed %d experiments; GraphicsTexture %.2f", #EXPERIMENTS, tex())
