-- LOOK-6 final paired A/B (Client datamodel, Studio play only, Studio focused).
-- Variants: none = the real FilmFx off (Workspace FilmFxOff), new = the real
-- (LOOK-6) FilmFx on, old = the LOOK-5 layer emulated exactly (full-screen
-- 128 px grain tile with a 40 px margin jittered 0-40 px at 24 Hz, 6 %, under
-- four rotated 0.42 x height vignette_corner pieces at 22 %) with the real one off.
-- Random order per cycle, every block paired with "none" of the same cycle.
-- Blocks: SETTLE frames dropped, then MEASURE frames sampled inside
-- RenderStepped (reading Stats after RenderStepped:Wait() returns zeros).
-- Attributes on LocalPlayer: L6Metric "gpu" (Stats.RenderGPUFrameTime, the
-- 60 fps protocol) or "dt" (frame time; use with a GPU-bound load),
-- L6Seconds, L6Label. Stops early if the game phase changes.
-- Guard: a block with any zero GPU sample or any frame over 40 ms (Studio
-- unfocused -> 10-15 fps and GPU stat 0) voids its whole cycle.
-- Each block is summarised by the mean and by the median of its frames.
-- Poll: LocalPlayer L6Status / L6Result.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Stats = game:GetService("Stats")
local Workspace = game:GetService("Workspace")
local plr = Players.LocalPlayer
local pg = plr:WaitForChild("PlayerGui")
local METRIC = tostring(plr:GetAttribute("L6Metric") or "gpu")
local SECONDS = tonumber(plr:GetAttribute("L6Seconds")) or 150
local LABEL = tostring(plr:GetAttribute("L6Label") or "final")
local SETTLE, MEASURE = 10, 60
local state = game.ReplicatedStorage.GameState
local phase0 = state:GetAttribute("Phase")

for _, c in pg:GetChildren() do
	if string.sub(c.Name, 1, 4) == "L6B_" then
		c:Destroy()
	end
end
local old = Instance.new("ScreenGui")
old.Name = "L6B_old"
old.IgnoreGuiInset = true
old.ResetOnSpawn = false
old.DisplayOrder = -20
old.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
old.Enabled = false
old.Parent = pg
local oldGrain = Instance.new("ImageLabel")
oldGrain.BackgroundTransparency = 1
oldGrain.BorderSizePixel = 0
oldGrain.Image = "rbxassetid://80382475593624"
oldGrain.ScaleType = Enum.ScaleType.Tile
oldGrain.TileSize = UDim2.fromOffset(128, 128)
oldGrain.Size = UDim2.new(1, 40, 1, 40)
oldGrain.ImageTransparency = 0.94
oldGrain.ZIndex = 5
oldGrain.Parent = old
for _, c in { { Vector2.new(0, 0), 0 }, { Vector2.new(1, 0), 90 }, { Vector2.new(1, 1), 180 }, { Vector2.new(0, 1), 270 } } do
	local v = Instance.new("ImageLabel")
	v.BackgroundTransparency = 1
	v.BorderSizePixel = 0
	v.Image = "rbxassetid://98162240916225"
	v.AnchorPoint = c[1]
	v.Position = UDim2.fromScale(c[1].X, c[1].Y)
	v.SizeConstraint = Enum.SizeConstraint.RelativeYY
	v.Size = UDim2.fromScale(0.42, 0.42)
	v.Rotation = c[2]
	v.ImageTransparency = 0.78
	v.ZIndex = 4
	v.Parent = old
end

local function realOn()
	Workspace:SetAttribute("FilmFxOff", nil)
end
local function realOff()
	Workspace:SetAttribute("FilmFxOff", true)
end
local variants = {
	{ name = "none", on = realOff, off = function() end },
	{ name = "new", on = realOn, off = realOff },
	{ name = "old", on = function() realOff(); old.Enabled = true end, off = function() old.Enabled = false end },
}
local wasOff = Workspace:GetAttribute("FilmFxOff")
realOff()

local results, medians = {}, {}
for _, v in variants do
	results[v.name] = {}
	medians[v.name] = {}
end
local cycleMeans, cycleMedians = {}, {}
local voided = 0
local bad = false
local samples = {}
local order, idx, frame = {}, 0, 0
local cycles, started, nextJitter = 0, os.clock(), 0
local current = nil
local stopped = ""
local conn
local function mean(t) local s = 0 for _, x in t do s += x end return if #t > 0 then s / #t else 0 / 0 end
local function median(t) local c = table.clone(t) table.sort(c) local m = #c if m == 0 then return 0 / 0 end return if m % 2 == 1 then c[(m + 1) / 2] else (c[m / 2] + c[m / 2 + 1]) / 2 end
local function sd(t) local m = mean(t) local s = 0 for _, x in t do s += (x - m) ^ 2 end return if #t > 1 then math.sqrt(s / (#t - 1)) else 0 end
local function report(tbl, title)
	local k = #tbl.none
	local out = { title }
	for _, v in variants do
		local d = {}
		for i = 1, k do
			d[i] = tbl[v.name][i] - tbl.none[i]
		end
		table.insert(out, string.format("  %-5s %.2f ms  vs none: mean %+.3f  median %+.3f  se %.3f  (n %d)",
			v.name, mean(tbl[v.name]), mean(d), median(d), sd(d) / math.sqrt(math.max(k, 1)), k))
	end
	local d = {}
	for i = 1, k do
		d[i] = tbl.new[i] - tbl.old[i]
	end
	table.insert(out, string.format("  new - old: mean %+.3f  median %+.3f  se %.3f", mean(d), median(d), sd(d) / math.sqrt(math.max(k, 1))))
	return table.concat(out, "\n")
end
local function finish()
	conn:Disconnect()
	old:Destroy()
	Workspace:SetAttribute("FilmFxOff", wasOff)
	local lines = {
		string.format("[%s] %s metric %s: %d valid cycles (%d voided), block %d+%d frames, %.0f s, viewport %s, ToD %s, phase %s -> %s%s",
			LABEL, os.date("%H:%M:%S"), METRIC, #results.none, voided, SETTLE, MEASURE, os.clock() - started,
			tostring(Workspace.CurrentCamera.ViewportSize), tostring(Workspace:GetAttribute("TimeOfDay")),
			tostring(phase0), tostring(state:GetAttribute("Phase")), stopped),
		report(results, "block mean:"),
		report(medians, "block median of frames:"),
	}
	plr:SetAttribute("L6Result", table.concat(lines, "\n"))
	plr:SetAttribute("L6Status", "done")
end
local function nextBlock()
	if current then
		current.off()
	end
	idx += 1
	if idx > #order then
		-- commit the finished cycle unless one of its blocks was void
		if #order > 0 then
			if bad then
				voided += 1
			else
				for _, v in variants do
					table.insert(results[v.name], cycleMeans[v.name])
					table.insert(medians[v.name], cycleMedians[v.name])
				end
			end
		end
		bad = false
		cycleMeans, cycleMedians = {}, {}
		if os.clock() - started >= SECONDS then
			finish()
			return
		end
		cycles += 1
		order = table.clone(variants)
		for i = #order, 2, -1 do
			local j = math.random(1, i)
			order[i], order[j] = order[j], order[i]
		end
		idx = 1
		plr:SetAttribute("L6Status", string.format("cycle %d, %.0f s", cycles, os.clock() - started))
	end
	current = order[idx]
	current.on()
	frame = 0
	samples = {}
end
plr:SetAttribute("L6Result", nil)
conn = RunService.RenderStepped:Connect(function(dt)
	local now = os.clock()
	if now >= nextJitter then
		nextJitter = now + 1 / 24
		oldGrain.Position = UDim2.fromOffset(-math.random(0, 40), -math.random(0, 40))
	end
	if state:GetAttribute("Phase") ~= phase0 then
		stopped = " (stopped early: phase changed)"
		if current then
			current.off()
		end
		finish()
		return
	end
	if not current then
		nextBlock()
		return
	end
	frame += 1
	if frame > SETTLE then
		local gpu = Stats.RenderGPUFrameTime * 1000
		if gpu <= 0 or (METRIC == "gpu" and dt > 0.04) then
			bad = true
		end
		table.insert(samples, if METRIC == "dt" then dt * 1000 else gpu)
		if #samples >= MEASURE then
			cycleMeans[current.name] = mean(samples)
			cycleMedians[current.name] = median(samples)
			nextBlock()
		end
	end
end)
return string.format("final bench started: %s, %s, %d s", LABEL, METRIC, SECONDS)
