-- QA watcher for bot runs (AD-1). Paste into execute_luau (**Server**
-- datamodel) during a Studio playtest, before or alongside
-- tools/qa/autoplay_full.client.luau. Prints "[AD-QA]" lines to the
-- output (read them with get_console_output):
--   * every phase change with wave, integrity, score and airdrop counters;
--   * every Infantry/Buggy/Tank that appears: whether it came by airdrop
--     (DropLoadId) and its landing distance;
--   * STUCK: a ground enemy still walking/driving that has not moved 2
--     studs in 15 s;
--   * a summary per wave (landed, direct spawns, out of band, stuck);
--   * TIMING: each airdropped group's `at`, the jittered target, the planned
--     and the measured first touchdown (wave seconds) and any lateness
--     (set ServerStorage attribute AdWatchTiming = false to skip these);
--   * PACE (AD-3), one line per wave attempt: duration; integrity at the
--     start, at the end (before the intermission repair) and the lowest;
--     attempt number; the opening (first transport entry, first canopies,
--     first touchdown, first enemy on the field); "idle in flight" = the
--     longest stretch with nothing alive to shoot while loads were in the
--     air, after the first enemy appeared; "beat gap" = the longest stretch
--     with nothing to shoot and no new airdrop beat (a transport entering,
--     canopies opening, a stick touching down) or aircraft arriving,
--     including the opening; the idle stretches over 8 s;
--   * RUN at Victory: run time from wave 1's intro and total retries.
-- PACE rows are also appended as JSON lines to ServerStorage.AdPaceLog
-- (a StringValue) for collection after the run.
-- Stop: game.ServerStorage:SetAttribute("AdWatch", false).
local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerStorage = game:GetService("ServerStorage")
local Workspace = game:GetService("Workspace")

local state = ReplicatedStorage.GameState
local dbg = ServerStorage:WaitForChild("RedMesaDebug")
local GROUND = { Infantry = true, Buggy = true, Tank = true }
local MOVING = { Walk = true, Drive = true }
local PIVOT = Vector3.new(0, 72, 0)

ServerStorage:SetAttribute("AdWatch", true)
local watch = {}
local wave = { landed = 0, direct = 0, outOfBand = 0, stuck = 0, minD = math.huge, maxD = 0 }

local function flat(p: Vector3): number
	return Vector2.new(p.X - PIVOT.X, p.Z - PIVOT.Z).Magnitude
end

local printedGroups = 0
local function timing()
	local s = dbg:Invoke("airdropStats")
	if ServerStorage:GetAttribute("AdWatchTiming") == false then
		printedGroups = #s.groups
		return
	end
	for i = printedGroups + 1, #s.groups do
		local g = s.groups[i]
		print(string.format(
			"[AD-QA] TIMING wave %d %s/%s at %s target %s planned %.2f landed %s (landed-target %s) late %.2f",
			g.wave,
			g.kind,
			g.lane,
			if g.at then string.format("%.1f", g.at) else "-",
			if g.target then string.format("%.2f", g.target) else "-",
			g.planned,
			if g.landed then string.format("%.2f", g.landed) else "-",
			if g.landed and g.target then string.format("%+.2f", g.landed - g.target) else "-",
			g.late
		))
	end
	printedGroups = #s.groups
end

local function stats(): string
	local s = dbg:Invoke("airdropStats")
	local announced, landed = 0, 0
	for _, n in s.announced do
		announced += n
	end
	for _, n in s.landed do
		landed += n
	end
	return string.format("drops announced %d landed %d cancelled %d pending %d fallbacks %d nudged %d late %d (max %.2fs) land %.0f-%.0f maxPlan %.1fms", announced, landed, s.cancelled, s.pending, s.fallbacks, s.nudged, s.late, s.maxLate, s.minLand, s.maxLand, s.maxPlanMs)
end

-- Boss death: airborne escorts must be dropped, never land afterwards.
local bossDownAt: number? = nil
local wrecksConn = Workspace.Wrecks.ChildAdded:Connect(function(model)
	if model:GetAttribute("Kind") == "SiegeCrawler" and not bossDownAt then
		bossDownAt = os.clock()
		local s = dbg:Invoke("airdropStats")
		print(string.format("[AD-QA] BOSS DOWN: %d loads pending at that moment (cancelled so far %d)", s.pending, s.cancelled))
		task.delay(0.5, function()
			local after = dbg:Invoke("airdropStats")
			print(string.format("[AD-QA] 0.5 s later: pending %d, cancelled %d", after.pending, after.cancelled))
		end)
	end
end)

local addedConn = Workspace.Enemies.ChildAdded:Connect(function(model)
	if not model:IsA("Model") or not GROUND[model:GetAttribute("Kind")] then
		return
	end
	if bossDownAt and model:GetAttribute("DropLoadId") ~= nil then
		print(string.format("[AD-QA] LANDED AFTER BOSS DOWN (+%.2f s)", os.clock() - bossDownAt))
	end
	local root = model.PrimaryPart or model:FindFirstChild("Root")
	if not (root and root:IsA("BasePart")) then
		return
	end
	local d = flat(root.Position)
	if model:GetAttribute("DropLoadId") == nil then
		wave.direct += 1
		print(string.format("[AD-QA] DIRECT %s at %.0f (no DropLoadId)", model:GetAttribute("Kind"), d))
	else
		wave.landed += 1
		wave.minD, wave.maxD = math.min(wave.minD, d), math.max(wave.maxD, d)
		if d < 298 or d > 802 then
			wave.outOfBand += 1
			print(string.format("[AD-QA] OUT OF BAND %s at %.0f", model:GetAttribute("Kind"), d))
		end
	end
	watch[model] = { last = (root :: BasePart).Position, since = os.clock(), flagged = false }
end)

-- Pacing (AD-3) ----------------------------------------------------------
local AIR = { Helicopter = true, Jet = true, SiegeCrawler = true }
local SAMPLE = 0.2
local paceLog = ServerStorage:FindFirstChild("AdPaceLog") :: StringValue?
if not paceLog then
	local v = Instance.new("StringValue")
	v.Name = "AdPaceLog"
	v.Parent = ServerStorage
	paceLog = v
end
local pace: any = nil
local defeats: { [number]: number } = {}
local run = { start = nil :: number?, retries = 0 }
local lastPhase = state:GetAttribute("Phase")
-- Sortie rows logged before this index belong to earlier waves (taken at
-- the wave intro, before the director can announce anything).
local logFromNext: number? = nil

local function serverNow(): number
	return Workspace:GetServerTimeNow()
end

local function aliveEnemies(): number
	local n = 0
	for _, m in Workspace.Enemies:GetChildren() do
		if m:IsA("Model") and m:GetAttribute("State") ~= "Dead" then
			n += 1
		end
	end
	return n
end

local function sortieCount(): number
	return #(dbg:Invoke("airdropStats").sortieLog or {})
end

local function paceBegin()
	local integrity = state:GetAttribute("Integrity") or 0
	pace = {
		wave = state:GetAttribute("Wave"),
		start = serverNow(),
		intStart = integrity,
		intEnd = integrity,
		intMin = integrity,
		idle = {} :: { { number } },
		idleFrom = 0 :: number?,
		air = {} :: { number },
		lifetimes = {} :: { number },
		logFrom = logFromNext or sortieCount(),
	}
	logFromNext = nil
end

-- Longest part of [a, b] not interrupted by any time in `beats`.
local function longestSplit(a: number, b: number, beats: { number }): (number, number)
	local best, at, from = 0, a, a
	local cuts = {}
	for _, t in beats do
		if t > a and t < b then
			table.insert(cuts, t)
		end
	end
	table.sort(cuts)
	table.insert(cuts, b)
	for _, t in cuts do
		if t - from > best then
			best, at = t - from, from
		end
		from = t
	end
	return best, at
end

local function paceEnd(outcome: string)
	local p = pace
	pace = nil
	if not p then
		return
	end
	local t = serverNow() - p.start
	if p.idleFrom then
		table.insert(p.idle, { p.idleFrom, t })
	end
	local log = dbg:Invoke("airdropStats").sortieLog or {}
	local rows = {}
	for i = p.logFrom + 1, #log do
		if log[i].wave == p.wave then
			table.insert(rows, log[i])
		end
	end
	local firstEntry, firstOpen, firstLand = math.huge, math.huge, math.huge
	local beats = table.clone(p.air)
	local flights = {}
	for _, r in rows do
		firstEntry = math.min(firstEntry, r.t0)
		firstOpen = math.min(firstOpen, r.open)
		firstLand = math.min(firstLand, r.land)
		for _, b in { r.t0, r.open, r.land, r.lastLand } do
			table.insert(beats, b)
		end
		table.insert(flights, { r.t0, r.lastLand })
	end
	-- First enemy on the field = end of the opening idle stretch.
	local firstEngage = if p.idle[1] and p.idle[1][1] <= SAMPLE * 2 then p.idle[1][2] else 0
	local inFlight, inFlightAt = 0, 0
	local beatGap, beatGapAt = 0, 0
	local longIdle = {}
	for _, iv in p.idle do
		local a, b = iv[1], iv[2]
		local g, at = longestSplit(a, b, beats)
		if g > beatGap then
			beatGap, beatGapAt = g, at
		end
		if b - a > 8 then
			table.insert(longIdle, string.format("%.0f-%.0f", a, b))
		end
		if a >= firstEngage - 1e-3 and a > 0 then
			for _, f in flights do
				local lo, hi = math.max(a, f[1]), math.min(b, f[2])
				if hi - lo > inFlight then
					inFlight, inFlightAt = hi - lo, lo
				end
			end
		end
	end
	local lt = table.clone(p.lifetimes)
	table.sort(lt)
	local function q(f: number): number
		return if #lt > 0 then lt[math.clamp(math.ceil(#lt * f), 1, #lt)] else 0
	end
	local attempt = (defeats[p.wave] or 0) + 1
	print(string.format(
		"[AD-QA] PACE wave %d attempt %d %s: %.1fs | integrity %.0f -> %.0f (min %.0f) | entry %.1f chutes %.1f land %.1f engage %.1f | idle-in-flight %.1fs @%.0f | beat gap %.1fs @%.0f | sorties %d | land->kill median %.1fs p90 %.1fs (n %d) | idle>8s: %s",
		p.wave, attempt, outcome, t, p.intStart, p.intEnd, p.intMin,
		firstEntry, firstOpen, firstLand, firstEngage,
		inFlight, inFlightAt, beatGap, beatGapAt, #rows, q(0.5), q(0.9), #lt,
		if #longIdle > 0 then table.concat(longIdle, " ") else "none"
	))
	local row = {
		wave = p.wave, attempt = attempt, outcome = outcome, duration = t,
		intStart = p.intStart, intEnd = p.intEnd, intMin = p.intMin,
		entry = firstEntry, chutes = firstOpen, land = firstLand, engage = firstEngage,
		idleInFlight = inFlight, beatGap = beatGap, killMedian = q(0.5), killP90 = q(0.9),
		seed = dbg:Invoke("airdropStats").seed,
	}
	local ok, json = pcall(HttpService.JSONEncode, HttpService, row)
	if ok and paceLog then
		paceLog.Value ..= json .. "\n"
	end
end

local integrityConn = state:GetAttributeChangedSignal("Integrity"):Connect(function()
	if pace and state:GetAttribute("Phase") == "Wave" then
		local v = state:GetAttribute("Integrity") or 0
		pace.intEnd = v
		pace.intMin = math.min(pace.intMin, v)
	end
end)

-- Aircraft arrivals are beats; every dropped load's time from touchdown
-- to death (how fast the bot reacts to a landing and kills it).
local airConn = Workspace.Enemies.ChildAdded:Connect(function(model)
	task.defer(function()
		local p = pace
		if not p then
			return
		end
		local kind = model:GetAttribute("Kind")
		if AIR[kind] then
			table.insert(p.air, serverNow() - p.start)
		elseif GROUND[kind] and model:GetAttribute("DropLoadId") ~= nil then
			local born = serverNow()
			local done = false
			local function finish()
				if not done then
					done = true
					if pace == p then
						table.insert(p.lifetimes, serverNow() - born)
					end
				end
			end
			model:GetAttributeChangedSignal("State"):Connect(function()
				if model:GetAttribute("State") == "Dead" then
					finish()
				end
			end)
			model.AncestryChanged:Connect(function()
				if not model:IsDescendantOf(Workspace.Enemies) then
					finish()
				end
			end)
		end
	end)
end)

task.spawn(function()
	while ServerStorage:GetAttribute("AdWatch") do
		local p = pace
		if p and state:GetAttribute("Phase") == "Wave" then
			local t = serverNow() - p.start
			local idle = aliveEnemies() == 0
			if idle and not p.idleFrom then
				p.idleFrom = t
			elseif not idle and p.idleFrom then
				table.insert(p.idle, { p.idleFrom, t })
				p.idleFrom = nil
			end
		end
		task.wait(SAMPLE)
	end
	integrityConn:Disconnect()
	airConn:Disconnect()
end)

local phaseConn = state:GetAttributeChangedSignal("Phase"):Connect(function()
	local phase = state:GetAttribute("Phase")
	local previous = lastPhase
	lastPhase = phase
	if phase == "Wave" then
		paceBegin()
	elseif phase == "WaveIntro" then
		logFromNext = sortieCount()
		if state:GetAttribute("Wave") == 1 and previous ~= "Defeat" then
			run.start, run.retries = serverNow(), 0
			table.clear(defeats)
		end
	end
	if phase == "Intermission" or phase == "Defeat" or phase == "Victory" then
		if pace then
			paceEnd(phase)
		end
		if phase == "Defeat" then
			local w = state:GetAttribute("Wave")
			defeats[w] = (defeats[w] or 0) + 1
			run.retries += 1
		elseif phase == "Victory" and run.start then
			print(string.format("[AD-QA] RUN victory in %.1f min (from wave 1 intro), %d retries, score %d", (serverNow() - run.start) / 60, run.retries, state:GetAttribute("Score")))
		end
		timing()
		print(string.format(
			"[AD-QA] wave %d %s: landed %d direct %d outOfBand %d stuck %d land %.0f-%.0f | integrity %.0f score %d | %s",
			state:GetAttribute("Wave"),
			phase,
			wave.landed,
			wave.direct,
			wave.outOfBand,
			wave.stuck,
			wave.minD,
			wave.maxD,
			state:GetAttribute("Integrity"),
			state:GetAttribute("Score"),
			stats()
		))
		wave = { landed = 0, direct = 0, outOfBand = 0, stuck = 0, minD = math.huge, maxD = 0 }
	else
		print(string.format("[AD-QA] phase %s wave %d t=%.0f", tostring(phase), state:GetAttribute("Wave"), os.clock()))
	end
end)

task.spawn(function()
	while ServerStorage:GetAttribute("AdWatch") do
		for model, w in watch do
			local root = model.PrimaryPart or model:FindFirstChild("Root") :: BasePart?
			if not model.Parent or model.Parent.Name ~= "Enemies" or not root then
				watch[model] = nil
				continue
			end
			local moved = (root.Position - w.last).Magnitude > 2
			if moved or not MOVING[model:GetAttribute("State")] then
				w.last, w.since, w.flagged = root.Position, os.clock(), false
			elseif os.clock() - w.since > 15 and not w.flagged then
				w.flagged = true
				wave.stuck += 1
				print(string.format("[AD-QA] STUCK %s state %s at %s (%.0f from outpost)", model:GetAttribute("Kind"), tostring(model:GetAttribute("State")), tostring(root.Position), flat(root.Position)))
			end
		end
		task.wait(1)
	end
	addedConn:Disconnect()
	phaseConn:Disconnect()
	wrecksConn:Disconnect()
end)
return "airdrop watch started"
