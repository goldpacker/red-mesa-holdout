-- Perf probe (docs/PERF_BUDGET.md). Paste into execute_luau (Client
-- datamodel) during a Studio playtest with Studio in front; it samples for
-- SECONDS and returns a one-screen report. Change LABEL to name the scene.
-- Frame times come from RenderStepped; memory from Stats by tag; render
-- stats (triangles, draw calls, CPU/GPU frame time) when Studio exposes them.
local LABEL = "scene"
local SECONDS = 8

local RunService = game:GetService("RunService")
local Stats = game:GetService("Stats")
local Workspace = game:GetService("Workspace")

local function read(name: string): number?
	local ok, value = pcall(function()
		return (Stats :: any)[name]
	end)
	return if ok and type(value) == "number" then value else nil
end

local RENDER_STATS = {
	"SceneTriangleCount", "SceneDrawcallCount", "ShadowsTriangleCount", "ShadowsDrawcallCount",
	"UI2DTriangleCount", "UI2DDrawcallCount", "UI3DTriangleCount", "UI3DDrawcallCount",
	"RenderCPUFrameTime", "RenderGPUFrameTime", "FrameTime",
}

local frames: { number } = {}
local samples: { [string]: { number } } = {}
local conn = RunService.RenderStepped:Connect(function(dt)
	table.insert(frames, dt)
end)
local started = os.clock()
while os.clock() - started < SECONDS do
	for _, name in RENDER_STATS do
		local v = read(name)
		if v then
			samples[name] = samples[name] or {}
			table.insert(samples[name], v)
		end
	end
	task.wait(0.25)
end
conn:Disconnect()

local lines = {}
local function add(fmt: string, ...)
	table.insert(lines, string.format(fmt, ...))
end

local quality = "?"
pcall(function()
	quality = tostring(settings().Rendering.QualityLevel)
end)
local camera = Workspace.CurrentCamera
add("[%s] %s  %.0fs  viewport %dx%d  quality %s  ToD %s  phase %s", LABEL, os.date("%Y-%m-%d %H:%M"), SECONDS,
	camera.ViewportSize.X, camera.ViewportSize.Y, quality, tostring(Workspace:GetAttribute("TimeOfDay")),
	tostring(game.ReplicatedStorage.GameState:GetAttribute("Phase")))

-- Frame rate: average and 1% low (99th percentile frame time).
local total = 0
for _, dt in frames do
	total += dt
end
table.sort(frames)
if #frames > 0 then
	local p99 = frames[math.max(1, math.ceil(#frames * 0.99))]
	add("fps avg %.1f  1%%-low %.1f  (frames %d, worst %.1f ms)", #frames / total, 1 / p99, #frames, frames[#frames] * 1000)
else
	add("fps: no frames rendered (is Studio in front? run caffeinate -u)")
end

-- Render stats (averaged) where readable.
local render = {}
for _, name in RENDER_STATS do
	local list = samples[name]
	if list then
		local sum = 0
		for _, v in list do
			sum += v
		end
		table.insert(render, string.format("%s %.1f", name, sum / #list))
	end
end
add("render: %s", if #render > 0 then table.concat(render, "  ") else "not readable from scripts (use Shift+F2 screenshot)")

-- Memory by tag (MB).
add("memory total %.0f MB", Stats:GetTotalMemoryUsageMb())
local tags = {}
for _, tag in Enum.DeveloperMemoryTag:GetEnumItems() do
	local ok, mb = pcall(function()
		return Stats:GetMemoryUsageMbForTag(tag)
	end)
	if ok and mb >= 0.5 then
		table.insert(tags, { tag.Name, mb })
	end
end
table.sort(tags, function(a, b)
	return a[2] > b[2]
end)
local tagText = {}
for _, t in tags do
	table.insert(tagText, string.format("%s %.0f", t[1], t[2]))
end
add("memory by tag: %s", table.concat(tagText, "  "))

-- Instance counts in the Workspace.
local counts = { parts = 0, meshParts = 0, unions = 0, surfaceAppearances = 0, decals = 0, emitters = 0, emittersOn = 0, beams = 0, trails = 0, lights = 0, lightsOn = 0, all = 0 }
for _, d in Workspace:GetDescendants() do
	counts.all += 1
	if d:IsA("MeshPart") then
		counts.meshParts += 1
	elseif d:IsA("UnionOperation") then
		counts.unions += 1
	elseif d:IsA("BasePart") and d ~= Workspace.Terrain then
		counts.parts += 1
	elseif d:IsA("SurfaceAppearance") then
		counts.surfaceAppearances += 1
	elseif d:IsA("Decal") then
		counts.decals += 1
	elseif d:IsA("ParticleEmitter") then
		counts.emitters += 1
		if d.Enabled then
			counts.emittersOn += 1
		end
	elseif d:IsA("Beam") then
		counts.beams += 1
	elseif d:IsA("Trail") then
		counts.trails += 1
	elseif d:IsA("Light") then
		counts.lights += 1
		if d.Enabled then
			counts.lightsOn += 1
		end
	end
end
add("workspace: %d instances  %d MeshParts  %d Parts  %d Unions  %d SurfaceAppearances  %d Decals/Textures",
	counts.all, counts.meshParts, counts.parts, counts.unions, counts.surfaceAppearances, counts.decals)
add("effects: %d emitters (%d on)  %d beams  %d trails  %d lights (%d on)",
	counts.emitters, counts.emittersOn, counts.beams, counts.trails, counts.lights, counts.lightsOn)
local enemies = {}
for _, m in (Workspace:FindFirstChild("Enemies") :: Instance):GetChildren() do
	local kind = tostring(m:GetAttribute("Kind") or m.Name)
	enemies[kind] = (enemies[kind] or 0) + 1
end
local enemyText = {}
for kind, n in enemies do
	table.insert(enemyText, kind .. " " .. n)
end
table.sort(enemyText)
add("enemies: %s", if #enemyText > 0 then table.concat(enemyText, ", ") else "none")
local variants = #game:GetService("MaterialService"):GetDescendants()
add("MaterialService descendants (MaterialVariants etc.): %d", variants)
return table.concat(lines, "\n")
