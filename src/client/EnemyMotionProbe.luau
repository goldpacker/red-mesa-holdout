--!strict
-- Studio-only instrumentation for EnemyMotion (LOOK-3 evidence). A client
-- BindableFunction ReplicatedStorage.EnemyMotionDebug answers:
--   ("stats")                      per-track sample rate, jitter and offsets
--   ("log", { id = n, seconds = s }) starts a per-frame log of one enemy
--   ("getlog")                     returns rows { t, new (a sample arrived
--                                  this frame), sampleT, then 12 CFrame
--                                  components each of: the smoothed pose,
--                                  the drawn Root (incl. body motion), the
--                                  newest server sample }
--   ("cost")                       mean / max Luau ms per frame since last call
-- In a live game it does nothing.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Probe = {}

local enabled = RunService:IsStudio()
local costSum, costMax, costFrames = 0, 0, 0
local logId: number? = nil
local logUntil = 0
local logRows: { { number } } = {}
local tracksRef: { [Model]: any } = {}

local function idOf(model: Model): number?
	local id = model:GetAttribute("EnemyId")
	return if type(id) == "number" then id else nil
end

function Probe.frame(tracks: { [Model]: any }, now: number, cost: number)
	if not enabled then
		return
	end
	costSum += cost
	costFrames += 1
	costMax = math.max(costMax, cost)
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
		})
	end
	return out
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
			local r = { meanMs = if costFrames > 0 then costSum / costFrames * 1000 else 0, maxMs = costMax * 1000, frames = costFrames }
			costSum, costMax, costFrames = 0, 0, 0
			return r
		end
		return nil
	end
	fn.Parent = ReplicatedStorage
end

return Probe
