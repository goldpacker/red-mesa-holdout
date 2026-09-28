--!strict
-- Per-frame script cost by system (PERF-1). Every per-frame client system
-- wraps its step with FrameProfile.wrap(name, fn):
--   * the MicroProfiler shows it as "RM:<name>" (debug.profilebegin; the
--     cost with the profiler closed is a few tenths of a microsecond);
--   * in Studio, while Workspace attribute `FrameProfile` is true, the
--     wrapper also sums os.clock() time and calls per name and publishes the
--     running totals every 0.5 s as JSON in the LocalPlayer attribute
--     `FrameProfileOut` ({ name = { s = seconds, n = calls, max = seconds } },
--     plus `frames`). Read it twice and difference the totals.
-- Nothing is measured or published in live games.

local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local FrameProfile = {}

type Entry = { s: number, n: number, max: number }

local IS_STUDIO = RunService:IsStudio()
local enabled = false
local totals: { [string]: Entry } = {}
local frames = 0
local publishing = false

local function publish()
	if publishing then
		return
	end
	publishing = true
	task.spawn(function()
		local player = Players.LocalPlayer
		while enabled do
			local out: { [string]: any } = { frames = frames }
			for name, e in totals do
				out[name] = { s = e.s, n = e.n, max = e.max }
			end
			pcall(function()
				player:SetAttribute("FrameProfileOut", HttpService:JSONEncode(out))
			end)
			task.wait(0.5)
		end
		publishing = false
	end)
end

local function refresh()
	enabled = IS_STUDIO and Workspace:GetAttribute("FrameProfile") == true
	if enabled then
		publish()
	end
end

if IS_STUDIO then
	Workspace:GetAttributeChangedSignal("FrameProfile"):Connect(refresh)
	refresh()
	RunService.PreRender:Connect(function()
		if enabled then
			frames += 1
		end
	end)
end

-- Returns `fn` wrapped with a profiler label and, in Studio, a timer.
function FrameProfile.wrap<A...>(name: string, fn: (A...) -> ()): (A...) -> ()
	local label = "RM:" .. name
	return function(...: A...)
		debug.profilebegin(label)
		if enabled then
			local t0 = os.clock()
			fn(...)
			local dt = os.clock() - t0
			local e = totals[name]
			if not e then
				e = { s = 0, n = 0, max = 0 }
				totals[name] = e
			end
			e.s += dt
			e.n += 1
			if dt > e.max then
				e.max = dt
			end
		else
			fn(...)
		end
		debug.profileend()
	end
end

return FrameProfile
