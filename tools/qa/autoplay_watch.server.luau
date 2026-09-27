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
--     and the measured first touchdown (wave seconds) and any lateness.
-- Stop: game.ServerStorage:SetAttribute("AdWatch", false).
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

local phaseConn = state:GetAttributeChangedSignal("Phase"):Connect(function()
	local phase = state:GetAttribute("Phase")
	if phase == "Intermission" or phase == "Defeat" or phase == "Victory" then
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
