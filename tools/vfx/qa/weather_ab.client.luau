--!nocheck
-- Paired in-session GPU A/B for the weather (VFX-4). Paste into MCP
-- execute_luau (Client) during a Studio playtest with Studio in front; it
-- starts in the background and returns at once. Poll
--   return workspace:GetAttribute("WeatherAB")
-- until it no longer starts with "running".
-- Alternates two states ROUNDS times (order swapped every round); each
-- block waits WARM seconds (particles build up / die out), then samples
-- Stats render times every 0.1 s for SAMPLE seconds. Reports per-state
-- means and the paired difference (B - A) per round (mean, median, range).
--   MODE "weather": A = weather off (Workspace.WeatherOff), B = on
--   MODE "peak":    A = weather on, no storm; B = WeatherStormForce = 1
--   MODE "wall":    A = weather on, no storm; B = the wall held at
--                   WALL_AT studs (WeatherStormFrontAt)
-- Also reports the weather's live particle estimate and enabled wall beams
-- in the B blocks.
local MODE = "weather"
local ROUNDS = 16 -- 16 for "weather", 12 for "peak"/"wall" (VFX-4 runs)
local WARM = 3
local SAMPLE = 2.5
local WALL_AT = -1100

local Stats = game:GetService("Stats")
local Workspace = game:GetService("Workspace")

local function read(name)
	local ok, v = pcall(function()
		return Stats[name]
	end)
	return ok and type(v) == "number" and v or nil
end

local WEATHER_NAMES = {
	SandStreamer = true, CrestStreamer = true, RimPlume = true, DevilColumn = true, DevilSkirt = true,
	WreckSmoke = true, StormCrest = true, StormBody = true, StormNear = true,
}
local function weatherLoad()
	local n, beams = 0, 0
	for _, d in Workspace:GetDescendants() do
		if d:IsA("ParticleEmitter") and WEATHER_NAMES[d.Name] and d.Enabled then
			n += d.Rate * (d.Lifetime.Min + d.Lifetime.Max) * 0.5
		elseif d:IsA("Beam") and d.Name == "StormWall" and d.Enabled then
			beams += 1
		end
	end
	return n, beams
end

local function set(state)
	if MODE == "weather" then
		Workspace:SetAttribute("WeatherOff", if state == "A" then true else nil)
	elseif MODE == "peak" then
		Workspace:SetAttribute("WeatherStormForce", if state == "B" then 1 else nil)
	else
		Workspace:SetAttribute("WeatherStormFrontAt", if state == "B" then WALL_AT else nil)
	end
end

local function block(state)
	set(state)
	task.wait(WARM)
	local gpu, cpu, tris, dc, n = 0, 0, 0, 0, 0
	local t0 = os.clock()
	while os.clock() - t0 < SAMPLE do
		gpu += (read("RenderGPUFrameTime") or 0) * 1000 -- Stats report seconds
		cpu += (read("RenderCPUFrameTime") or 0) * 1000
		tris += read("SceneTriangleCount") or 0
		dc += read("SceneDrawcallCount") or 0
		n += 1
		task.wait(0.1)
	end
	local parts, beams = 0, 0
	if state == "B" then
		parts, beams = weatherLoad()
	end
	return { gpu = gpu / n, cpu = cpu / n, tris = tris / n, dc = dc / n, parts = parts, beams = beams, dens = Workspace:GetAttribute("WeatherDensity") or 1 }
end

local function mean(list, key)
	local s = 0
	for _, x in list do
		s += if key then x[key] else x
	end
	return s / #list
end

Workspace:SetAttribute("WeatherAB", "running " .. MODE)
task.spawn(function()
	local A, B, diffs = {}, {}, {}
	for r = 1, ROUNDS do
		local a, b
		if r % 2 == 1 then
			a = block("A")
			b = block("B")
		else
			b = block("B")
			a = block("A")
		end
		table.insert(A, a)
		table.insert(B, b)
		table.insert(diffs, b.gpu - a.gpu)
		Workspace:SetAttribute("WeatherAB", string.format("running %s round %d/%d", MODE, r, ROUNDS))
	end
	set("A")
	Workspace:SetAttribute("WeatherOff", nil)
	table.sort(diffs)
	local median = if #diffs % 2 == 0 then (diffs[#diffs / 2] + diffs[#diffs / 2 + 1]) / 2 else diffs[math.ceil(#diffs / 2)]
	Workspace:SetAttribute("WeatherAB", string.format(
		"[%s] %d rounds x (%.0f+%.0f s)  A: gpu %.2f cpu %.2f tris %.0fk dc %.0f | B: gpu %.2f cpu %.2f tris %.0fk dc %.0f, weather particles ~%.0f, wall beams %.0f, density %.2f | paired B-A gpu mean %+.2f median %+.2f range %+.2f..%+.2f ms",
		MODE, ROUNDS, WARM, SAMPLE,
		mean(A, "gpu"), mean(A, "cpu"), mean(A, "tris") / 1000, mean(A, "dc"),
		mean(B, "gpu"), mean(B, "cpu"), mean(B, "tris") / 1000, mean(B, "dc"), mean(B, "parts"), mean(B, "beams"), mean(B, "dens"),
		mean(diffs), median, diffs[1], diffs[#diffs]
	))
end)
return "started " .. MODE
