-- LOOK-6 bench 3b / 4 / 5 (session 2): design variants, emulated as separate
-- ScreenGuis with the real FilmFx off. Random order per cycle; each block drops
-- SETTLE frames and samples MEASURE frames INSIDE RenderStepped (bench3_fast,
-- which sampled after RenderStepped:Wait(), read zeros once Studio lost focus);
-- every block is paired with "none" of the same cycle.
-- LocalPlayer attributes: L6Metric "gpu" (RenderGPUFrameTime, bench 3b) or
-- "dt" (frame time, benches 4-5 on top of gpu_bound_load.client.luau),
-- L6Seconds, L6Label. Bench 5 swapped the variant list for grain tile sizes
-- 128/64/32/256 and a single stretched quad.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Stats = game:GetService("Stats")
local Workspace = game:GetService("Workspace")
local plr = Players.LocalPlayer
local pg = plr:WaitForChild("PlayerGui")
local METRIC = tostring(plr:GetAttribute("L6Metric") or "gpu")
local SECONDS = tonumber(plr:GetAttribute("L6Seconds")) or 120
local LABEL = tostring(plr:GetAttribute("L6Label") or "design")
local SETTLE, MEASURE = if METRIC == "dt" then 6 else 10, if METRIC == "dt" then 30 else 60
local IDS = { grain = "rbxassetid://80382475593624", corner = "rbxassetid://98162240916225" }
for _, c in pg:GetChildren() do if string.sub(c.Name, 1, 4) == "L6B_" then c:Destroy() end end
local jitterLabels, jitterBoxes = {}, {}
local function screen(name)
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
local function label(parent)
	local l = Instance.new("ImageLabel")
	l.BackgroundTransparency = 1
	l.BorderSizePixel = 0
	l.Active = false
	l.Parent = parent
	return l
end
local function addGrain(s)
	local g = label(s)
	g.Name = "Grain"
	g.Image = IDS.grain
	g.ScaleType = Enum.ScaleType.Tile
	g.TileSize = UDim2.fromOffset(128, 128)
	g.Size = UDim2.new(1, 40, 1, 40)
	g.ImageTransparency = 0.94
	g.ZIndex = 5
	table.insert(jitterLabels, g)
	return g
end
local CORNERS = { { Vector2.new(0, 0), 0 }, { Vector2.new(1, 0), 90 }, { Vector2.new(1, 1), 180 }, { Vector2.new(0, 1), 270 } }
local function addCorners(s, size)
	for _, c in CORNERS do
		local v = label(s)
		v.Image = IDS.corner
		v.AnchorPoint = c[1]
		v.Position = UDim2.fromScale(c[1].X, c[1].Y)
		v.SizeConstraint = Enum.SizeConstraint.RelativeYY
		v.Size = UDim2.fromScale(size, size)
		v.Rotation = c[2]
		v.ImageTransparency = 0.78
		v.ZIndex = 4
	end
end
local function guiVariant(name, build)
	local s = screen(name)
	build(s)
	return { name = name, on = function() s.Enabled = true end, off = function() s.Enabled = false end }
end
local variants = {
	{ name = "none", on = function() end, off = function() end },
	guiVariant("old", function(s) addCorners(s, 0.42); addGrain(s) end),
	guiVariant("grain", function(s) addGrain(s) end),
	guiVariant("corners42", function(s) addCorners(s, 0.42) end),
	guiVariant("grainTopHalf", function(s) local g = addGrain(s); g.Size = UDim2.new(1, 40, 0.5, 20) end),
	guiVariant("frame", function(s)
		local f = Instance.new("Frame")
		f.BorderSizePixel = 0
		f.BackgroundColor3 = Color3.new(0, 0, 0)
		f.BackgroundTransparency = 0.95
		f.Size = UDim2.fromScale(1, 1)
		f.Parent = s
	end),
	-- the LOOK-6 geometry: 4 corners (stand-in texture) + 3 tiled grain bands, one coverage
	guiVariant("merged", function(s)
		local vp = Workspace.CurrentCamera.ViewportSize
		local W, H = math.floor(vp.X + 12), math.floor(vp.Y + 12)
		local c = math.floor(0.34 * H + 0.5)
		local box = Instance.new("Frame")
		box.BackgroundTransparency = 1
		box.Size = UDim2.fromOffset(W, H)
		box.Parent = s
		for _, k in CORNERS do
			local v = label(box)
			v.Image = IDS.corner
			v.AnchorPoint = k[1]
			v.Position = UDim2.fromScale(k[1].X, k[1].Y)
			v.Size = UDim2.fromOffset(c, c)
			v.Rotation = k[2]
			v.ImageTransparency = 0.78
		end
		local function band(x, y, w, h)
			local g = label(box)
			g.Image = IDS.grain
			g.ScaleType = Enum.ScaleType.Tile
			g.TileSize = UDim2.fromOffset(188, 188)
			g.Position = UDim2.fromOffset(x, y)
			g.Size = UDim2.fromOffset(w, h)
			g.ImageTransparency = 0.94
		end
		band(c, 0, W - 2 * c, H)
		band(0, c, c, H - 2 * c)
		band(W - c, c, c, H - 2 * c)
		table.insert(jitterBoxes, box)
	end),
}
local wasOff = Workspace:GetAttribute("FilmFxOff")
Workspace:SetAttribute("FilmFxOff", true)
local results = {}
for _, v in variants do results[v.name] = {} end
local order, idx, frame, acc, n = {}, 0, 0, 0, 0
local cycles, started, nextJitter = 0, os.clock(), 0
local current = nil
local conn
local function mean(t) local s = 0 for _, x in t do s += x end return if #t > 0 then s / #t else 0 / 0 end
local function median(t) local c = table.clone(t) table.sort(c) local m = #c if m == 0 then return 0 / 0 end return if m % 2 == 1 then c[(m + 1) / 2] else (c[m / 2] + c[m / 2 + 1]) / 2 end
local function sd(t) local m = mean(t) local s = 0 for _, x in t do s += (x - m) ^ 2 end return if #t > 1 then math.sqrt(s / (#t - 1)) else 0 end
local function finish()
	conn:Disconnect()
	for _, c in pg:GetChildren() do if string.sub(c.Name, 1, 4) == "L6B_" then c:Destroy() end end
	Workspace:SetAttribute("FilmFxOff", wasOff)
	local base = results.none
	local lines = { string.format("[%s] %s metric %s: %d cycles x %d variants, block %d+%d frames, %.0f s",
		LABEL, os.date("%H:%M:%S"), METRIC, cycles, #variants, SETTLE, MEASURE, os.clock() - started) }
	for _, v in variants do
		local r = results[v.name]
		local diffs = {}
		for i = 1, math.min(#r, #base) do diffs[i] = r[i] - base[i] end
		table.insert(lines, string.format("%-13s %.2f ms  vs none: mean %+.3f  median %+.3f  se %.3f  (n %d)",
			v.name, mean(r), mean(diffs), median(diffs), sd(diffs) / math.sqrt(#diffs), #diffs))
	end
	plr:SetAttribute("L6Result", table.concat(lines, "\n"))
	plr:SetAttribute("L6Status", "done")
end
local function nextBlock()
	if current then current.off() end
	idx += 1
	if idx > #order then
		if os.clock() - started >= SECONDS then finish() return end
		cycles += 1
		order = table.clone(variants)
		for i = #order, 2, -1 do local j = math.random(1, i) order[i], order[j] = order[j], order[i] end
		idx = 1
		plr:SetAttribute("L6Status", string.format("cycle %d, %.0f s", cycles, os.clock() - started))
	end
	current = order[idx]
	current.on()
	frame, acc, n = 0, 0, 0
end
plr:SetAttribute("L6Result", nil)
conn = RunService.RenderStepped:Connect(function(dt)
	local now = os.clock()
	if now >= nextJitter then
		nextJitter = now + 1 / 24
		for _, g in jitterLabels do g.Position = UDim2.fromOffset(-math.random(0, 40), -math.random(0, 40)) end
		for _, b in jitterBoxes do b.Position = UDim2.fromOffset(-math.random(0, 12), -math.random(0, 12)) end
	end
	if not current then nextBlock() return end
	frame += 1
	if frame > SETTLE then
		acc += if METRIC == "dt" then dt * 1000 else Stats.RenderGPUFrameTime * 1000
		n += 1
		if n >= MEASURE then
			table.insert(results[current.name], acc / n)
			nextBlock()
		end
	end
end)
return "design bench started: " .. METRIC
