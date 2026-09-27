--!strict
-- Studio-only instrumentation for EnemyMotion (LOOK-3 evidence). A client
-- BindableFunction ReplicatedStorage.EnemyMotionDebug answers:
--   ("stats")                      per-track sample rate, jitter, offsets,
--                                  ignored decorative parts, age of the track
--   ("log", { id = n, seconds = s }) starts a per-frame log of one enemy
--   ("getlog")                     returns rows { t, new (a sample arrived
--                                  this frame), sampleT, then 12 CFrame
--                                  components each of: the smoothed pose,
--                                  the drawn Root (incl. body motion), the
--                                  newest server sample }
--   ("cost")                       Luau ms per frame since the last call:
--                                  meanMs / maxMs     everything EnemyMotion ran,
--                                  stepMeanMs / stepMaxMs  the per-frame track loop,
--                                  watchMeanMs / watchMaxMs  qualification work
--                                    (registration, re-checks, event handlers;
--                                    work done between frames is charged to
--                                    the next frame),
--                                  watchCalls         how many pieces of it ran,
--                                  worstFrameMs       the longest render frame,
--                                  frames,
--                                  perKind            while profiling: mean us per
--                                    track-frame by kind (live / wreck)
--   ("profile", on)                times every track separately (adds a
--                                  little cost of its own; off by default)
-- In a live game it does nothing.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Probe = {}

local enabled = RunService:IsStudio()
Probe.enabled = enabled
Probe.profiling = false -- read by EnemyMotion's step

type Cost = {
	frames: number,
	sum: number,
	max: number,
	stepSum: number,
	stepMax: number,
	watchSum: number,
	watchMax: number,
	watchCalls: number,
	worstFrame: number,
}

local function newCost(): Cost
	return { frames = 0, sum = 0, max = 0, stepSum = 0, stepMax = 0, watchSum = 0, watchMax = 0, watchCalls = 0, worstFrame = 0 }
end

local cost = newCost()
local perKind: { [string]: { n: number, sum: number } } = {}
local pendingWatch = 0 -- s of qualification work since the last frame
local logId: number? = nil
local logUntil = 0
local logRows: { { number } } = {}
local tracksRef: { [Model]: any } = {}

local function idOf(model: Model): number?
	local id = model:GetAttribute("EnemyId")
	return if type(id) == "number" then id else nil
end

-- Charges `seconds` of qualification work to the next frame; `calls`
-- (default 1) is how many pieces of work that was.
function Probe.work(seconds: number, calls: number?)
	if enabled then
		pendingWatch += seconds
		cost.watchCalls += calls or 1
	end
end

-- One track's step while profiling.
function Probe.kind(track: any, seconds: number)
	local key = track.kind .. (if track.wreck then " wreck" else "")
	local k = perKind[key]
	if not k then
		k = { n = 0, sum = 0 }
		perKind[key] = k
	end
	k.n += 1
	k.sum += seconds
end

-- `step`: s spent in the track loop this frame; `dt`: the render frame time.
function Probe.frame(tracks: { [Model]: any }, now: number, step: number, dt: number)
	if not enabled then
		return
	end
	local watch = pendingWatch
	pendingWatch = 0
	local total = step + watch
	cost.frames += 1
	cost.sum += total
	cost.max = math.max(cost.max, total)
	cost.stepSum += step
	cost.stepMax = math.max(cost.stepMax, step)
	cost.watchSum += watch
	cost.watchMax = math.max(cost.watchMax, watch)
	cost.worstFrame = math.max(cost.worstFrame, dt)
	if not logId then
		return
	end
	if now > logUntil then
		logId = nil
		return
	end
	for model, track in tracks do
		if idOf(model) == logId then
			local samples = track.samples
			local last = samples[#samples]
			local isNew = last and last.t == now
			local render = CFrame.new(track.pos) * track.rot
			local drawn = track.written or render
			local row = { now, if isNew then 1 else 0, last.t }
			for _, cf in { render, drawn, CFrame.new(last.pos) * last.rot } do
				for _, c in { cf:GetComponents() } do
					table.insert(row, c)
				end
			end
			table.insert(logRows, row)
		end
	end
end

local function stats(): { any }
	local out = {}
	for model, track in tracksRef do
		local last = track.samples[#track.samples]
		local drawn = track.written and track.written.Position or track.pos
		table.insert(out, {
			id = idOf(model),
			kind = track.kind,
			samples = #track.samples,
			intervalMs = math.floor(track.interval * 10000) / 10,
			jitterMs = math.floor(track.jitter * 10000) / 10,
			speed = math.floor(track.vel.Magnitude * 10) / 10,
			renderToServer = math.floor((track.pos - last.pos).Magnitude * 1000) / 1000,
			bodyOffset = math.floor((drawn - track.pos).Magnitude * 1000) / 1000,
			wreck = track.wreck,
			treads = track.tracks ~= nil,
			ignored = track.ignored,
			ageS = if track.born then math.floor((os.clock() - track.born) * 100) / 100 else nil,
		})
	end
	return out
end

local function ms(seconds: number): number
	return math.floor(seconds * 1e6) / 1e3
end

local function report(): { [string]: any }
	local c = cost
	local n = math.max(c.frames, 1)
	cost = newCost()
	local kinds: { [string]: string }? = nil
	if next(perKind) then
		local byKind: { [string]: string } = {}
		for key, k in perKind do
			byKind[key] = string.format("%.1f us x %d", k.sum / k.n * 1e6, k.n)
		end
		kinds = byKind
		table.clear(perKind)
	end
	return {
		perKind = kinds,
		meanMs = ms(c.sum / n),
		maxMs = ms(c.max),
		stepMeanMs = ms(c.stepSum / n),
		stepMaxMs = ms(c.stepMax),
		watchMeanMs = ms(c.watchSum / n),
		watchMaxMs = ms(c.watchMax),
		watchCalls = c.watchCalls,
		worstFrameMs = ms(c.worstFrame),
		frames = c.frames,
	}
end

function Probe.start(tracks: { [Model]: any })
	tracksRef = tracks
	if not enabled then
		return
	end
	local fn = Instance.new("BindableFunction")
	fn.Name = "EnemyMotionDebug"
	fn.OnInvoke = function(cmd: string, arg: any): any
		if cmd == "stats" then
			return stats()
		elseif cmd == "log" then
			logRows = {}
			logId = arg.id
			logUntil = os.clock() + (arg.seconds or 5)
			return true
		elseif cmd == "getlog" then
			return logRows
		elseif cmd == "cost" then
			return report()
		elseif cmd == "profile" then
			Probe.profiling = arg == true
			table.clear(perKind)
			return Probe.profiling
		end
		return nil
	end
	fn.Parent = ReplicatedStorage
end

return Probe
