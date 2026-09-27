-- LOOK-6 bench 3: fast paired alternation (Client datamodel, Studio play only).
-- Bench 1-2 showed block-to-block drift (sd ~0.45 ms over 2.5 s blocks) much
-- larger than frame noise averages out to, so here every variant gets a
-- short block (SETTLE frames discarded, then MEASURE frames of
-- Stats.RenderGPUFrameTime), the variants run in a fresh random order each
-- cycle, and every variant is paired with "none" of the same cycle (~0.5 s
-- apart). Variants are { name, on(), off() } so the same harness drives
-- emulated layers and the real FilmFx (Workspace FilmFxOff).
-- Poll: return game.Players.LocalPlayer:GetAttribute("L6Status"), game.Players.LocalPlayer:GetAttribute("L6Result")
local SECONDS = tonumber(game.Players.LocalPlayer:GetAttribute("L6Seconds")) or 150
local SETTLE, MEASURE = 6, 24 -- frames
local LABEL = tostring(game.Players.LocalPlayer:GetAttribute("L6Label") or "bench3")

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Stats = game:GetService("Stats")
local Workspace = game:GetService("Workspace")
local plr = Players.LocalPlayer
local pg = plr:WaitForChild("PlayerGui")

local IDS = {
	grain = "rbxassetid://80382475593624",
	corner = "rbxassetid://98162240916225",
}
for _, c in pg:GetChildren() do
	if string.sub(c.Name, 1, 4) == "L6B_" then
		c:Destroy()
	end
end

local jitterLabels: { ImageLabel } = {}
local jitterBoxes: { Frame } = {}
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
-- The LOOK-5 grain: 128 tile 1:1, 40 px margin, 6 %, jittered at 24 Hz.
local function addGrain(s, alpha)
	local g = label(s)
	g.Name = "Grain"
	g.Image = IDS.grain
	g.ScaleType = Enum.ScaleType.Tile
	g.TileSize = UDim2.fromOffset(128, 128)
	g.Size = UDim2.new(1, 40, 1, 40)
	g.ImageTransparency = 1 - (alpha or 0.06)
	g.ZIndex = 5
	table.insert(jitterLabels, g)
	return g
end
local CORNERS = {
	{ Vector2.new(0, 0), 0 }, { Vector2.new(1, 0), 90 }, { Vector2.new(1, 1), 180 }, { Vector2.new(0, 1), 270 },
}
local function addCorners(s, size)
	for _, c in CORNERS do
		local v = label(s)
		v.Image = IDS.corner
		v.AnchorPoint = c[1]
		v.Position = UDim2.fromScale(c[1].X, c[1].Y)
		v.SizeConstraint = Enum.SizeConstraint.RelativeYY
		v.Size = UDim2.fromScale(size, size)
		v.Rotation = c[2]
		v.ImageTransparency = 1 - 0.22
		v.ZIndex = 4
	end
end
local function guiVariant(name, build)
	local s = screen(name)
	build(s)
	return {
		name = name,
		on = function() s.Enabled = true end,
		off = function() s.Enabled = false end,
	}
end

-- Variant set: pick with the L6Set attribute.
local set = tostring(plr:GetAttribute("L6Set") or "design")
local variants = {}
local function none()
	return { name = "none", on = function() end, off = function() end }
end
if set == "design" or set == "live" then
	variants = {
		none(),
		guiVariant("old", function(s) addCorners(s, 0.42); addGrain(s) end),
		guiVariant("grain", function(s) addGrain(s) end),
		guiVariant("corners42", function(s) addCorners(s, 0.42) end),
		guiVariant("corners30", function(s) addCorners(s, 0.30) end),
		guiVariant("grainTopHalf", function(s)
			local g = addGrain(s)
			g.Size = UDim2.new(1, 40, 0.5, 20)
		end),
		-- One coverage: 4 corner pieces (stand-in texture for a baked vignette+grain corner)
		-- and three tiled grain bands filling the cross between them, no overlap.
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
		guiVariant("frame", function(s)
			local f = Instance.new("Frame")
			f.BorderSizePixel = 0
			f.BackgroundColor3 = Color3.new(0, 0, 0)
			f.BackgroundTransparency = 0.95
			f.Size = UDim2.fromScale(1, 1)
			f.Parent = s
		end),
	}
end
if set == "live" then
	local keep = { none = true, old = true, grain = true, merged = true, corners42 = true }
	local kept = {}
	for _, v in variants do
		if keep[v.name] then
			table.insert(kept, v)
		else
			v.off()
		end
	end
	variants = kept
elseif set == "final" then
	-- none = real FilmFx off; new = real FilmFx on (the shipped code);
	-- old = the LOOK-5 layer emulated (grain + 4 rotated 0.42 corners), real FilmFx off.
	local realOn = function() Workspace:SetAttribute("FilmFxOff", nil) end
	local realOff = function() Workspace:SetAttribute("FilmFxOff", true) end
	local old = guiVariant("old", function(s) addCorners(s, 0.42); addGrain(s) end)
	variants = {
		{ name = "none", on = realOff, off = function() end },
		{ name = "new", on = realOn, off = realOff },
		{ name = "old", on = function() realOff(); old.on() end, off = old.off },
	}
end

local wasOff = Workspace:GetAttribute("FilmFxOff")
Workspace:SetAttribute("FilmFxOff", true)

local nextJitter = 0
local jitterConn = RunService.RenderStepped:Connect(function()
	local now = os.clock()
	if now >= nextJitter then
		nextJitter = now + 1 / 24
		for _, g in jitterLabels do
			g.Position = UDim2.fromOffset(-math.random(0, 40), -math.random(0, 40))
		end
		for _, b in jitterBoxes do
			b.Position = UDim2.fromOffset(-math.random(0, 12), -math.random(0, 12))
		end
	end
end)

local function mean(t)
	local s = 0
	for _, x in t do s += x end
	return if #t > 0 then s / #t else 0 / 0
end
local function median(t)
	local c = table.clone(t)
	table.sort(c)
	local n = #c
	if n == 0 then return 0 / 0 end
	return if n % 2 == 1 then c[(n + 1) / 2] else (c[n / 2] + c[n / 2 + 1]) / 2
end
local function sd(t)
	local m = mean(t)
	local s = 0
	for _, x in t do s += (x - m) ^ 2 end
	return if #t > 1 then math.sqrt(s / (#t - 1)) else 0
end

local function block(v)
	v.on()
	for _ = 1, SETTLE do
		RunService.RenderStepped:Wait()
	end
	local gpu, cpu = {}, {}
	for _ = 1, MEASURE do
		RunService.RenderStepped:Wait()
		table.insert(gpu, Stats.RenderGPUFrameTime * 1000)
		table.insert(cpu, Stats.RenderCPUFrameTime * 1000)
	end
	v.off()
	return mean(gpu), mean(cpu)
end

task.spawn(function()
	plr:SetAttribute("L6Result", nil)
	local started = os.clock()
	local results = {}
	for _, v in variants do
		results[v.name] = { gpu = {}, cpu = {} }
	end
	local cycles = 0
	while os.clock() - started < SECONDS do
		cycles += 1
		plr:SetAttribute("L6Status", string.format("cycle %d, %.0f/%d s", cycles, os.clock() - started, SECONDS))
		local order = table.clone(variants)
		for i = #order, 2, -1 do
			local j = math.random(1, i)
			order[i], order[j] = order[j], order[i]
		end
		for _, v in order do
			local g, c = block(v)
			table.insert(results[v.name].gpu, g)
			table.insert(results[v.name].cpu, c)
		end
	end
	jitterConn:Disconnect()
	for _, c in pg:GetChildren() do
		if string.sub(c.Name, 1, 4) == "L6B_" then
			c:Destroy()
		end
	end
	Workspace:SetAttribute("FilmFxOff", wasOff)
	local base = results.none.gpu
	local lines = {
		string.format("[%s] %s set %s: %d cycles x %d variants, block %d+%d frames, %.0f s, viewport %s, ToD %s, phase %s",
			LABEL, os.date("%H:%M:%S"), set, cycles, #variants, SETTLE, MEASURE, os.clock() - started,
			tostring(Workspace.CurrentCamera.ViewportSize), tostring(Workspace:GetAttribute("TimeOfDay")),
			tostring(game.ReplicatedStorage.GameState:GetAttribute("Phase"))),
	}
	for _, v in variants do
		local r = results[v.name]
		local diffs = {}
		for i = 1, #r.gpu do
			diffs[i] = r.gpu[i] - base[i]
		end
		table.insert(lines, string.format("%-13s GPU %.2f  CPU %.2f  vs none: mean %+.3f  median %+.3f  se %.3f  (n %d)",
			v.name, mean(r.gpu), mean(r.cpu), mean(diffs), median(diffs), sd(diffs) / math.sqrt(#diffs), #diffs))
	end
	plr:SetAttribute("L6Result", table.concat(lines, "\n"))
	plr:SetAttribute("L6Status", "done")
end)
return "bench3 started: set " .. set .. ", " .. SECONDS .. " s"
