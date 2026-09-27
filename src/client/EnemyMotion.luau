--!strict
-- Client-side enemy motion (face-lift LOOK-3). Rendering only: the server's
-- CFrames stay authoritative and every hit is still resolved against them.
--
-- 1. Root smoothing. The server moves each enemy by setting one anchored
--    `Root` CFrame per Heartbeat (EnemyTypes/Common/Rig); every other part
--    is welded to it. Replication hands the client those poses unevenly
--    (0, 1 or 2 per rendered frame), which reads as stepping. Each frame,
--    first thing in the render step, this module:
--      - reads Root.CFrame; if it differs from what we wrote last frame the
--        replicator has delivered a new server pose -> a timestamped sample;
--      - fits position (least squares) and spin over the last ~100 ms of
--        samples and evaluates the fit *now* (a short extrapolation, then a
--        hold once the server stops sending, i.e. the enemy stopped);
--      - dead-reckons the rendered pose with that velocity and bleeds the
--        remaining error off with a 50 ms time constant;
--      - writes Root.CFrame = smoothed pose * body motion.
--    There is no fixed interpolation delay: the target is always the newest
--    server pose, so on straight runs the render sits on the server pose
--    and on turns it stays within a fraction of a stud (see the LOOK-3
--    report for the measured offsets). A replicated pose is always read
--    before it is overwritten, so the two never fight.
-- 2. Body motion (EnemyMotionBody): suspension bob, pitch/roll from
--    acceleration and turns, helicopter lean, jet bank, recoil rock.
-- 3. Tank/crawler track scrolling (EnemyMotionTracks).
--
-- Child parts (turrets, rotors, wheels) stay with VehicleFx; buggy wheels
-- ask `wheelCounter` so they stay planted while the body bobs and rolls.
-- Studio QA: Workspace attribute MotionOff = true shows the raw replicated
-- poses (A/B), MotionBodyOff = true keeps the smoothing but drops the body
-- motion; ReplicatedStorage.EnemyMotionDebug (client, Studio only) returns
-- stats and per-frame logs (EnemyMotionProbe).

local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Body = require(script.Parent.EnemyMotionBody)
local Probe = require(script.Parent.EnemyMotionProbe)
local Tracks = require(script.Parent.EnemyMotionTracks)

local EnemyMotion = {}

local WINDOW = 0.1 -- s of samples in the fit
local MIN_SAMPLES = 3 -- kept even when older than WINDOW
local MAX_SAMPLES = 12
local MAX_AGE = 0.5 -- s: older samples are never used
local TAU = 0.05 -- s: residual error decay
local EASE = 0.05 -- s: extrapolation fade once a sample is overdue
local SNAP_DIST = 25 -- studs: farther than this is a teleport, not motion
local SNAP_ANGLE = math.rad(60)
local EPS_POS = 1e-3
local EPS_DOT = 1 - 1e-7

type Sample = { t: number, pos: Vector3, rot: CFrame }

export type Track = {
	model: Model,
	root: BasePart,
	kind: string,
	samples: { Sample },
	written: CFrame?,
	pos: Vector3,
	rot: CFrame,
	vel: Vector3,
	spinAxis: Vector3,
	spinRate: number,
	interval: number,
	jitter: number,
	offset: CFrame,
	body: Body.State?,
	tracks: Tracks.State?,
	wreck: boolean,
	raw: boolean,
}

local tracks: { [Model]: Track } = {}
local isStudio = RunService:IsStudio()

local function same(a: CFrame, b: CFrame): boolean
	return (a.Position - b.Position).Magnitude < EPS_POS
		and a.LookVector:Dot(b.LookVector) > EPS_DOT
		and a.UpVector:Dot(b.UpVector) > EPS_DOT
end

-- Only models moved as one welded assembly under an anchored Root can be
-- smoothed by moving Root alone (Rig.prepare, Infantry).
local function rootOf(model: Model): BasePart?
	local root = model:FindFirstChild("Root")
	if not (root and root:IsA("BasePart") and root.Anchored) then
		return nil
	end
	for _, d in model:GetDescendants() do
		if d ~= root and d:IsA("BasePart") and d.Anchored then
			return nil
		end
	end
	return root
end

local function register(model: Model)
	if tracks[model] or not model.Parent then
		return
	end
	local root = rootOf(model)
	local kind = model:GetAttribute("Kind")
	if not root or type(kind) ~= "string" then
		return
	end
	local cf = root.CFrame
	local track: Track = {
		model = model,
		root = root,
		kind = kind,
		samples = { { t = os.clock(), pos = cf.Position, rot = cf.Rotation } },
		written = cf,
		pos = cf.Position,
		rot = cf.Rotation,
		vel = Vector3.zero,
		spinAxis = Vector3.yAxis,
		spinRate = 0,
		interval = 1 / 60,
		jitter = 0.004,
		offset = CFrame.identity,
		body = Body.new(model, root, kind),
		tracks = Tracks.new(model, kind, root),
		wreck = false,
		raw = false,
	}
	tracks[model] = track
end

local function forget(model: Model)
	local track = tracks[model]
	if track then
		tracks[model] = nil
		Tracks.destroy(track.tracks)
	end
end

-- A dead vehicle keeps its smoothing (crashing aircraft still fly on the
-- server) but loses its body motion and track scroll.
local function toWreck(track: Track)
	track.wreck = true
	track.body = nil
	Tracks.destroy(track.tracks)
	track.tracks = nil
end

local function addSample(track: Track, now: number, cf: CFrame)
	local samples = track.samples
	local last = samples[#samples]
	if last then
		local gap = now - last.t
		if gap > 0 and gap < 0.25 then
			track.interval += (gap - track.interval) * 0.1
			track.jitter += (math.abs(gap - track.interval) - track.jitter) * 0.1
		end
		-- Teleported (spawn placement, beauty staging, a death flip): start over.
		if (cf.Position - last.pos).Magnitude > SNAP_DIST + track.vel.Magnitude * math.max(gap, 0) then
			table.clear(samples)
		end
	end
	table.insert(samples, { t = now, pos = cf.Position, rot = cf.Rotation })
	while #samples > MAX_SAMPLES or (#samples > MIN_SAMPLES and now - samples[1].t > WINDOW) do
		table.remove(samples, 1)
	end
	while #samples > 1 and now - samples[1].t > MAX_AGE do
		table.remove(samples, 1)
	end
end

-- Server states in which an enemy stands still (EnemyTypes/*). The server
-- stops sending CFrames when a model stops, so silence alone can't tell a
-- stop from a slow stretch of replication (distant tanks get a pose only
-- every 50-150 ms); the State attribute can.
local PARKED: { [string]: { [string]: boolean } } = {
	Tank = { Hold = true, Aim = true, Fire = true, Dead = true },
	Infantry = { Aim = true, Throw = true, Dead = true },
	SiegeCrawler = { Siege = true, Wreck = true },
	Buggy = { Dead = true },
}

-- How long after the newest sample the fit may still be extrapolated. A
-- parked enemy holds a little after the usual spacing; a moving one rides
-- out gaps of a few intervals (up to 0.4 s) before it is held.
local function holdAfter(track: Track): number
	local parked = PARKED[track.kind]
	local state = track.model:GetAttribute("State")
	if state == "Dead" or state == "Wreck" or (parked and type(state) == "string" and parked[state]) then
		return math.clamp(track.interval + 3 * track.jitter + 0.004, 0.02, 0.12)
	end
	return math.clamp(2.5 * track.interval + 3 * track.jitter, 0.05, 0.4)
end

local function advance(track: Track, now: number, dt: number)
	local samples = track.samples
	local n = #samples
	local last = samples[n]
	local age = now - last.t
	local holding = n < 2 or age > holdAfter(track)

	-- Position: least-squares line over the window, evaluated now.
	-- Past the usual spacing the extrapolation eases off (time constant
	-- EASE): a late sample slows the render a little instead of stalling it,
	-- and a real stop overshoots by well under a stud.
	local lead, rateScale = age, 1
	if age > track.interval then
		local over = age - track.interval
		rateScale = math.exp(-over / EASE)
		lead = track.interval + EASE * (1 - rateScale)
	end
	local target, vel
	if holding then
		target, vel = last.pos, Vector3.zero
	else
		local mt, mp = 0, Vector3.zero
		for i = 1, n do
			mt += samples[i].t
			mp += samples[i].pos
		end
		mt /= n
		mp /= n
		local stt, stp = 0, Vector3.zero
		for i = 1, n do
			local d = samples[i].t - mt
			stt += d * d
			stp += (samples[i].pos - mp) * d
		end
		vel = if stt > 1e-8 then stp / stt else Vector3.zero
		target = mp + vel * (last.t + lead - mt)
	end

	-- Spin: mean rate from the oldest to the newest sample in the window.
	local axis, rate = Vector3.yAxis, 0
	if not holding then
		local first = samples[1]
		local span = last.t - first.t
		if span > 1e-3 then
			local ax, angle = (last.rot * first.rot:Inverse()):ToAxisAngle()
			if angle > 1e-6 and angle < math.pi and ax.Magnitude > 0.5 then
				axis, rate = ax.Unit, angle / span
			end
		end
	end
	local targetRot = if rate > 0 then CFrame.fromAxisAngle(axis, rate * lead) * last.rot else last.rot

	local predPos = track.pos + vel * (dt * rateScale)
	local predRot = if rate > 0 then CFrame.fromAxisAngle(axis, rate * dt * rateScale) * track.rot else track.rot
	local k = 1 - math.exp(-dt / TAU)
	if (target - predPos).Magnitude > SNAP_DIST or predRot.LookVector:Dot(targetRot.LookVector) < math.cos(SNAP_ANGLE) then
		track.pos, track.rot = target, targetRot
	else
		track.pos = predPos + (target - predPos) * k
		track.rot = predRot:Lerp(targetRot, k):Orthonormalize()
	end
	-- Settle exactly on a held pose so a parked enemy is left untouched.
	if holding and (track.pos - target).Magnitude < 2e-3 and track.rot.LookVector:Dot(targetRot.LookVector) > EPS_DOT then
		track.pos, track.rot = target, targetRot
	end
	track.vel, track.spinAxis, track.spinRate = vel * rateScale, axis, rate * rateScale
end

local function stepTrack(track: Track, now: number, dt: number, off: boolean, bodyOff: boolean)
	local root = track.root
	local cf = root.CFrame
	local written = track.written
	if written == nil or not same(cf, written) then
		addSample(track, now, cf)
	end
	if off then
		-- Raw replicated poses (A/B): put the newest server pose back once.
		if not track.raw then
			track.raw = true
			local last = track.samples[#track.samples]
			root.CFrame = CFrame.new(last.pos) * last.rot
			if track.tracks then
				Tracks.update(track.tracks, 0, last.rot, Vector3.zero, CFrame.identity)
			end
		end
		track.written = root.CFrame
		local last = track.samples[#track.samples]
		track.pos, track.rot, track.vel = last.pos, last.rot, Vector3.zero
		return
	end
	track.raw = false
	advance(track, now, dt)
	local offset = CFrame.identity
	if track.body and not bodyOff then
		offset = Body.update(track.body, dt, now, track.pos, track.rot, track.vel, track.spinAxis * track.spinRate)
	end
	track.offset = offset
	if track.tracks then
		Tracks.update(track.tracks, dt, track.rot, track.vel, offset)
	end
	local final = CFrame.new(track.pos) * track.rot * offset
	if written == nil or not same(final, written) or track.samples[#track.samples].t == now then
		root.CFrame = final
		track.written = root.CFrame
	end
end

local function step(dt: number)
	local now = os.clock()
	local off = isStudio and Workspace:GetAttribute("MotionOff") == true
	local bodyOff = isStudio and Workspace:GetAttribute("MotionBodyOff") == true
	local t0 = os.clock()
	for model, track in tracks do
		if not model.Parent or not track.root.Parent then
			forget(model)
		elseif track.wreck and now - track.samples[#track.samples].t > 2 then
			-- Landed and settled on the server pose: nothing left to smooth.
			forget(model)
		else
			local ok, err = pcall(stepTrack, track, now, dt, off, bodyOff)
			if not ok then
				warn("[RedMesa] enemy motion failed for " .. track.kind .. ": " .. tostring(err))
				forget(model)
			end
		end
	end
	Probe.frame(tracks, now, os.clock() - t0)
end

-- The newest server pose of a model's Root (nil if not tracked).
function EnemyMotion.serverPose(model: Model): CFrame?
	local track = tracks[model]
	local last = track and track.samples[#track.samples]
	return if last then CFrame.new(last.pos) * last.rot else nil
end

-- The body-motion offset applied this frame, in Root space.
function EnemyMotion.bodyOffset(model: Model): CFrame
	local track = tracks[model]
	return if track then track.offset else CFrame.identity
end

-- A Motor6D.Transform prefix that cancels the body motion for one child
-- (VehicleFx: buggy wheels stay on the ground while the body moves).
function EnemyMotion.wheelCounter(model: Model, motor: Motor6D): CFrame
	local track = tracks[model]
	if not track or track.offset == CFrame.identity then
		return CFrame.identity
	end
	local c0 = motor.C0
	return c0:Inverse() * track.offset:Inverse() * c0
end

local function watch()
	local enemies = Workspace:WaitForChild("Enemies")
	local wrecks = Workspace:WaitForChild("Wrecks")
	local function added(child: Instance)
		if child:IsA("Model") then
			-- Attributes and welds replicate with the model; wait a frame so
			-- every descendant has arrived.
			task.defer(register, child)
		end
	end
	for _, child in enemies:GetChildren() do
		added(child)
	end
	enemies.ChildAdded:Connect(added)
	enemies.ChildRemoved:Connect(function(child)
		-- Moving to Wrecks keeps the track (no snap); anything else ends it.
		task.defer(function()
			local track = tracks[child :: Model]
			if track and child.Parent == wrecks then
				toWreck(track)
			elseif track and child.Parent ~= enemies then
				forget(child :: Model)
			end
		end)
	end)
	wrecks.ChildRemoved:Connect(function(child)
		if tracks[child :: Model] then
			forget(child :: Model)
		end
	end)
end

function EnemyMotion.start()
	Body.start(tracks)
	Probe.start(tracks)
	-- First in the frame: before the camera, VehicleFx, InfantryRig, the HUD
	-- and the dust read any enemy position.
	RunService:BindToRenderStep("RedMesaEnemyMotion", Enum.RenderPriority.First.Value, step)
	task.spawn(watch)
end

return EnemyMotion
