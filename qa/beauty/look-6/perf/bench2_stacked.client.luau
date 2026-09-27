-- LOOK-6 micro-benchmark (Client datamodel, Studio play only).
-- Builds candidate film-layer variants as separate ScreenGuis (the real
-- FilmFx is switched off with Workspace FilmFxOff for the run) and cycles
-- them in paired rounds, order reversed every other round. Each block:
-- SETTLE s after the switch, then RenderGPUFrameTime sampled every frame for
-- MEASURE s. Result: per-variant paired difference vs "none" in the same
-- round. Poll with: return game.Players.LocalPlayer:GetAttribute("L6Status"),
-- game.Players.LocalPlayer:GetAttribute("L6Result")
local ROUNDS = tonumber(game.Players.LocalPlayer:GetAttribute("L6Rounds")) or 10
local COPIES = 4 -- bench 2: stack each layer x4 so its cost stands out of the block noise
local SETTLE = 0.8
local MEASURE = 1.7

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Stats = game:GetService("Stats")
local Workspace = game:GetService("Workspace")
local plr = Players.LocalPlayer
local pg = plr:WaitForChild("PlayerGui")

local IDS = {
	grain = "rbxassetid://80382475593624",
	corner = "rbxassetid://98162240916225",
	vig = "rbxassetid://128569175998849",
}

for _, c in pg:GetChildren() do
	if string.sub(c.Name, 1, 4) == "L6B_" then
		c:Destroy()
	end
end

local function screen(name: string): ScreenGui
	local s = Instance.new("ScreenGui")
	s.Name = "L6B_" .. name
	s.IgnoreGuiInset = true
	s.ResetOnSpawn = false
	s.DisplayOrder = -20
	s.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
	s.Enabled = false
	s.Parent = pg
	return s
end
local function label(parent: Instance): ImageLabel
	local l = Instance.new("ImageLabel")
	l.BackgroundTransparency = 1
	l.BorderSizePixel = 0
	l.Active = false
	l.Parent = parent
	return l
end
local function addGrain(s: Instance, tile: number, alpha: number): ImageLabel
	local g = label(s)
	g.Name = "Grain"
	g.Image = IDS.grain
	g.ScaleType = Enum.ScaleType.Tile
	g.TileSize = UDim2.fromOffset(tile, tile)
	g.Size = UDim2.new(1, 40, 1, 40)
	g.ImageTransparency = 1 - alpha
	g.ZIndex = 5
	return g
end
local CORNERS = {
	{ Vector2.new(0, 0), 0 }, { Vector2.new(1, 0), 90 }, { Vector2.new(1, 1), 180 }, { Vector2.new(0, 1), 270 },
}
local function addCorners(s: Instance, size: number, rotated: boolean)
	for _, c in CORNERS do
		local v = label(s)
		v.Image = IDS.corner
		v.AnchorPoint = c[1]
		v.Position = UDim2.fromScale(c[1].X, c[1].Y)
		v.SizeConstraint = Enum.SizeConstraint.RelativeYY
		v.Size = UDim2.fromScale(size, size)
		v.Rotation = if rotated then c[2] else 0
		v.ImageTransparency = 1 - 0.22
		v.ZIndex = 4
	end
end

type Variant = { name: string, gui: ScreenGui, grain: ImageLabel?, jitter: boolean, gpu: { number }, cpu: { number }, gpuMed: { number } }
local variants: { Variant } = {}
local function variant(name: string, build: (ScreenGui) -> ImageLabel?, jitter: boolean)
	local s = screen(name)
	local g = build(s)
	table.insert(variants, { name = name, gui = s, grain = g, jitter = jitter, gpu = {}, cpu = {}, gpuMed = {} })
end

local function stack(build)
	return function(s)
		local first = nil
		for _ = 1, COPIES do
			first = build(s) or first
		end
		return first
	end
end
local function grainAll(s)
	-- every stacked grain copy jitters: return a folder-like marker via the first; the driver moves all "Grain" labels
	return addGrain(s, 128, 0.06)
end
variant("none", function() return nil end, false)
variant("grain24x4", stack(grainAll), true)
variant("grainStaticx4", stack(grainAll), false)
variant("framex4", stack(function(s)
	local f = Instance.new("Frame")
	f.BorderSizePixel = 0
	f.BackgroundColor3 = Color3.new(0, 0, 0)
	f.BackgroundTransparency = 0.95
	f.Size = UDim2.fromScale(1, 1)
	f.Parent = s
	return nil
end), false)
variant("vigFullx4", stack(function(s)
	local v = label(s)
	v.Image = IDS.vig
	v.Size = UDim2.fromScale(1, 1)
	v.ImageTransparency = 0.8
	return nil
end), false)
variant("cornersRotx4", stack(function(s) addCorners(s, 0.42, true); return nil end), false)
variant("cornersFlatx4", stack(function(s) addCorners(s, 0.42, false); return nil end), false)
variant("halfGrainx4", stack(function(s)
	local g = addGrain(s, 128, 0.06)
	g.Size = UDim2.new(1, 40, 0.5, 20)
	g.Position = UDim2.fromScale(0, 0.5)
	return nil
end), false)

local wasOff = Workspace:GetAttribute("FilmFxOff")
Workspace:SetAttribute("FilmFxOff", true)

local active: Variant? = nil
local measuring = false
local nextJitter = 0
local block: { gpu: { number }, cpu: { number } } = { gpu = {}, cpu = {} }
local conn = RunService.RenderStepped:Connect(function()
	local v = active
	if v and v.jitter then
		local now = os.clock()
		if now >= nextJitter then
			nextJitter = now + 1 / 24
			for _, g in v.gui:GetChildren() do
				if g.Name == "Grain" then
					g.Position = UDim2.fromOffset(-math.random(0, 40), -math.random(0, 40))
				end
			end
		end
	end
	if measuring then
		table.insert(block.gpu, Stats.RenderGPUFrameTime * 1000)
		table.insert(block.cpu, Stats.RenderCPUFrameTime * 1000)
	end
end)

local function mean(t: { number }): number
	local s = 0
	for _, x in t do
		s += x
	end
	return if #t > 0 then s / #t else 0 / 0
end
local function median(t: { number }): number
	local c = table.clone(t)
	table.sort(c)
	local n = #c
	if n == 0 then
		return 0 / 0
	end
	return if n % 2 == 1 then c[(n + 1) / 2] else (c[n / 2] + c[n / 2 + 1]) / 2
end
local function sd(t: { number }): number
	local m = mean(t)
	local s = 0
	for _, x in t do
		s += (x - m) ^ 2
	end
	return if #t > 1 then math.sqrt(s / (#t - 1)) else 0
end

task.spawn(function()
	plr:SetAttribute("L6Result", nil)
	local started = os.clock()
	for r = 1, ROUNDS do
		plr:SetAttribute("L6Status", string.format("round %d/%d", r, ROUNDS))
		local order = {}
		for i = 1, #variants do
			order[i] = if r % 2 == 1 then i else #variants + 1 - i
		end
		for _, i in order do
			local v = variants[i]
			for _, other in variants do
				other.gui.Enabled = other == v
			end
			active = v
			task.wait(SETTLE)
			block = { gpu = {}, cpu = {} }
			measuring = true
			task.wait(MEASURE)
			measuring = false
			table.insert(v.gpu, mean(block.gpu))
			table.insert(v.cpu, mean(block.cpu))
			table.insert(v.gpuMed, median(block.gpu))
		end
	end
	active = nil
	for _, v in variants do
		v.gui.Enabled = false
	end
	conn:Disconnect()
	Workspace:SetAttribute("FilmFxOff", wasOff)
	local none = variants[1]
	local lines = {
		string.format("L6 bench %s  %d rounds x %d variants, settle %.1f + measure %.1f s, %.0f s total, viewport %s, ToD %s",
			os.date("%H:%M:%S"), ROUNDS, #variants, SETTLE, MEASURE, os.clock() - started,
			tostring(Workspace.CurrentCamera.ViewportSize), tostring(Workspace:GetAttribute("TimeOfDay"))),
	}
	for _, v in variants do
		local diffs = {}
		for r = 1, #v.gpu do
			diffs[r] = v.gpu[r] - none.gpu[r]
		end
		local lo, hi = math.huge, -math.huge
		for _, d in diffs do
			lo, hi = math.min(lo, d), math.max(hi, d)
		end
		local mdiffs = {}
		for r = 1, #v.gpuMed do
			mdiffs[r] = v.gpuMed[r] - none.gpuMed[r]
		end
		table.insert(lines, string.format("%-14s GPU %.2f (block sd %.2f)  CPU %.2f  paired vs none: mean %+.2f median %+.2f se %.2f range %+.2f..%+.2f | frame-median blocks: mean %+.2f se %.2f",
			v.name, mean(v.gpu), sd(v.gpu), mean(v.cpu), mean(diffs), median(diffs), sd(diffs) / math.sqrt(#diffs), lo, hi,
			mean(mdiffs), sd(mdiffs) / math.sqrt(#mdiffs)))
	end
	local raw = {}
	for _, v in variants do
		local parts = {}
		for _, x in v.gpu do
			table.insert(parts, string.format("%.2f", x))
		end
		table.insert(raw, v.name .. ": " .. table.concat(parts, " "))
	end
	table.insert(lines, "raw block means (ms):")
	table.insert(lines, table.concat(raw, "\n"))
	plr:SetAttribute("L6Result", table.concat(lines, "\n"))
	plr:SetAttribute("L6Status", "done")
end)
return "bench started"
