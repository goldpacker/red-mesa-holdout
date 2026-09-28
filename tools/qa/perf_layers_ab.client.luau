-- PERF-1 paired layer A/B at the GPU's top clock (Client datamodel, Studio
-- play, Studio focused). K near-transparent full-screen sheets follow the
-- camera so every frame is GPU-bound (~25-28 ms at K = 80 on the M4 Pro at
-- 1670x1005) and frame time measures work, not the GPU clock's hunting at
-- 60 fps. Each cycle runs every variant once in random order (SETTLE frames
-- dropped, MEASURE frames averaged) and pairs it with "none" of the same
-- cycle; a block with a frame over 100 ms is dropped. Variants switch a
-- layer OFF on the client, so "vs none" is minus that layer's cost.
-- Inputs (LocalPlayer attributes, optional): P1AbVariants
-- "none,dof,rays,bloom,haze,film,air,weather,hud,shadows,tier1,tier2",
-- P1AbCycles 12, P1K 80, P1AbLabel. Output: LocalPlayer P1AbText (poll).
-- Set the view first (DebugAiming / DebugWeapon / DebugYaw / DebugPitch).
local RunService = game:GetService("RunService")
local Lighting = game:GetService("Lighting")
local Workspace = game:GetService("Workspace")
local plr = game.Players.LocalPlayer
local cam = Workspace.CurrentCamera

local VARIANTS = {}
for item in string.gmatch(tostring(plr:GetAttribute("P1AbVariants") or "none,dof,rays,bloom,haze,film,air,weather,hud,shadows"), "[^,%s]+") do
	table.insert(VARIANTS, item)
end
local CYCLES = tonumber(plr:GetAttribute("P1AbCycles")) or 12
local K = tonumber(plr:GetAttribute("P1K")) or 80
local LABEL = tostring(plr:GetAttribute("P1AbLabel") or "ab")
local SETTLE, MEASURE = 8, 30

local inert = game:GetService("ReplicatedStorage")
local stash: { [string]: any } = {}
local function attr(name: string): { on: () -> (), off: () -> () }
	return {
		on = function()
			Workspace:SetAttribute(name, true)
		end,
		off = function()
			Workspace:SetAttribute(name, nil)
		end,
	}
end
local function effect(name: string): { on: () -> (), off: () -> () }
	return {
		on = function()
			local e = Lighting:FindFirstChild(name) :: any
			if e then
				stash[name] = e.Enabled
				e.Enabled = false
			end
		end,
		off = function()
			local e = Lighting:FindFirstChild(name) :: any
			if e and stash[name] ~= nil then
				e.Enabled = stash[name]
			end
		end,
	}
end
local V: { [string]: { on: () -> (), off: () -> () } } = {
	none = { on = function() end, off = function() end },
	-- PostFx re-enables the gunsight DoF every frame: park it where it can't render.
	dof = {
		on = function()
			local d = cam:FindFirstChild("GunsightDoF")
			if d then
				stash.dof = d
				d.Parent = inert
			end
		end,
		off = function()
			if stash.dof then
				stash.dof.Parent = cam
				stash.dof = nil
			end
		end,
	},
	rays = effect("SunRays"),
	bloom = effect("Bloom"),
	haze = {
		on = function()
			stash.haze = {}
			local folder = Workspace:FindFirstChild("PostFxHaze")
			for _, b in if folder then folder:GetChildren() else {} do
				stash.haze[b] = (b :: Beam).Enabled;
				(b :: Beam).Enabled = false
			end
		end,
		off = function()
			for b, on in stash.haze or {} do
				b.Enabled = on
			end
		end,
	},
	film = attr("FilmFxOff"),
	air = attr("AirFxOff"),
	weather = attr("WeatherOff"),
	hud = {
		on = function()
			local g = plr.PlayerGui:FindFirstChild("Hud") :: ScreenGui?
			if g then
				g.Enabled = false
			end
		end,
		off = function()
			local g = plr.PlayerGui:FindFirstChild("Hud") :: ScreenGui?
			if g then
				g.Enabled = true
			end
		end,
	},
	shadows = {
		on = function()
			Lighting.GlobalShadows = false
		end,
		off = function()
			Lighting.GlobalShadows = true
		end,
	},
	tier1 = {
		on = function()
			Workspace:SetAttribute("PerfTier", 1)
		end,
		off = function()
			Workspace:SetAttribute("PerfTier", nil)
		end,
	},
	tier2 = {
		on = function()
			Workspace:SetAttribute("PerfTier", 2)
		end,
		off = function()
			Workspace:SetAttribute("PerfTier", nil)
		end,
	},
}

-- load
local folder = Instance.new("Folder")
folder.Name = "P1AbLoad"
for _ = 1, K do
	local p = Instance.new("Part")
	p.Anchored, p.CanCollide, p.CanQuery, p.CanTouch, p.CastShadow = true, false, false, false, false
	p.Material = Enum.Material.SmoothPlastic
	p.Transparency = 0.985
	p.Size = Vector3.new(3, 3, 0.01)
	p.Parent = folder
end
folder.Parent = Workspace
RunService:BindToRenderStep("P1AbLoad", Enum.RenderPriority.Last.Value + 300, function()
	local items, cfs = folder:GetChildren(), {}
	for i = 1, #items do
		cfs[i] = cam.CFrame * CFrame.new(0, 0, -0.25 - i * 0.002)
	end
	Workspace:BulkMoveTo(items, cfs, Enum.BulkMoveMode.FireCFrameChanged)
end)

plr:SetAttribute("P1AbText", nil)
local results: { [string]: { { number } } } = {}
for _, v in VARIANTS do
	results[v] = {}
end
local order: { string } = {}
local cycle, idx, frame = 0, 0, 0
local current: string? = nil
local sum, n, worst = 0, 0, 0
local cycleVals: { [string]: number } = {}

local function nextBlock(): boolean
	if current then
		V[current].off()
	end
	idx += 1
	if idx > #order then
		if cycle > 0 then
			for v, val in cycleVals do
				table.insert(results[v], { val, cycleVals.none })
			end
		end
		cycle += 1
		if cycle > CYCLES then
			return false
		end
		order = table.clone(VARIANTS)
		for i = #order, 2, -1 do
			local j = math.random(i)
			order[i], order[j] = order[j], order[i]
		end
		idx = 1
		cycleVals = {}
	end
	current = order[idx]
	V[current :: string].on()
	frame, sum, n, worst = 0, 0, 0, 0
	return true
end

local function mean(t: { number }): number
	local s = 0
	for _, x in t do
		s += x
	end
	return if #t > 0 then s / #t else 0
end

local finished = false
nextBlock()
local conn: RBXScriptConnection
conn = RunService.RenderStepped:Connect(function(dt)
	frame += 1
	if frame > SETTLE then
		sum += dt
		n += 1
		worst = math.max(worst, dt)
	end
	if n >= MEASURE then
		if worst < 0.1 then
			cycleVals[current :: string] = sum / n * 1000
		end
		if not nextBlock() then
			conn:Disconnect()
			finished = true
		end
	end
end)
while not finished do
	task.wait(0.5)
end
RunService:UnbindFromRenderStep("P1AbLoad")
folder:Destroy()

local lines = { string.format("[%s] %d cycles, %d+%d frames, K %d, viewport %s", LABEL, CYCLES, SETTLE, MEASURE, K, tostring(cam.ViewportSize)) }
for _, v in VARIANTS do
	local vals, diffs = {}, {}
	for _, pair in results[v] do
		table.insert(vals, pair[1])
		if pair[2] then
			table.insert(diffs, pair[1] - pair[2])
		end
	end
	local m = mean(diffs)
	local ss = 0
	for _, x in diffs do
		ss += (x - m) ^ 2
	end
	local se = if #diffs > 1 then math.sqrt(ss / (#diffs - 1) / #diffs) else 0
	table.sort(diffs)
	local median = if #diffs > 0 then diffs[math.ceil(#diffs / 2)] else 0
	table.insert(lines, string.format("%-8s frame %6.2f ms | off - none: mean %+6.3f se %.3f median %+6.3f (n %d)", v, mean(vals), m, se, median, #diffs))
end
plr:SetAttribute("P1AbText", table.concat(lines, "\n"))
return table.concat(lines, "\n")
