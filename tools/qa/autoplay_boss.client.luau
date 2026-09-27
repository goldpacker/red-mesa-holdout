-- Boss-fight probe (AD-4). Paste into execute_luau (Client datamodel) next
-- to tools/qa/autoplay_full.client.luau. For every wave-10 attempt it
-- prints one "[BOSS]" summary line and one "[BOSS-T]" timeline line, so the
-- fight's swing factors can be compared attempt by attempt:
--   * outcome, duration, integrity start -> end (min), damage by attack;
--   * rifle damage in 20 s bins, and trooper-seconds spent inside rifle
--     range (sampled every 0.5 s) with the most troopers in range at once;
--   * infantry touchdowns (from the AirdropSortie timeline) per 20 s bin and
--     how many landed nearer than 500 studs;
--   * boss cannon shots and when each weak point, the armour and the core
--     fell; rockets fired, seconds with no rocket left, crates (spawned /
--     collected, by contents: Mi/Re/Ro); jets warned and killed.
-- Player attribute QA_Seed (set by the driver) is echoed as the seed label.
-- An attempt shorter than 10 s (a forced defeat used to restock) is
-- skipped. Stop: player:SetAttribute("BossProbe", false).
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local plr = Players.LocalPlayer
local state = ReplicatedStorage.GameState
local remotes = ReplicatedStorage.Remotes
local PIVOT = Vector3.new(0, 72, 0)
local RIFLE_RANGE = 340 -- Config.Infantry.RIFLE_RANGE (3D, from the pivot)
local LABELS = { [1] = "rifle", [4] = "grenade", [1.1] = "buggy", [1.25] = "heli", [7] = "tank", [12] = "bomb", [1.5] = "bossTurret", [16] = "bossCannon" }

plr:SetAttribute("BossProbe", true)
local attempt: any = nil
local attemptNo = 0

local function now(): number
	return Workspace:GetServerTimeNow()
end

local function bin(list: { number }, t: number)
	local i = math.floor(t / 20) + 1
	for k = #list + 1, i do
		list[k] = 0
	end
	list[i] += 1
end

local function begin()
	attempt = {
		start = now(),
		intStart = state:GetAttribute("Integrity") or 0,
		intMin = state:GetAttribute("Integrity") or 0,
		damage = {} :: { [string]: number },
		rifleBins = {} :: { number },
		cannon = {} :: { number },
		events = {} :: { string },
		lands = {} :: { number },
		landsNear = 0,
		landsTotal = 0,
		rocketsFired = 0,
		starved = 0,
		inRange = 0,
		maxInRange = 0,
		cratesSpawned = {} :: { [string]: number },
		cratesTaken = {} :: { [string]: number },
		jets = 0,
		jetKills = 0,
		heliKills = 0,
		lastRockets = plr:GetAttribute("Rockets") or 0,
		down = {} :: { [string]: boolean },
	}
end

local function mark(label: string)
	if attempt then
		table.insert(attempt.events, string.format("%s@%.0f", label, now() - attempt.start))
	end
end

local function finish(outcome: string)
	local a = attempt
	attempt = nil
	if not a then
		return
	end
	local dur = now() - a.start
	if dur < 10 then
		return
	end
	attemptNo += 1
	local dmg = {}
	for label, v in a.damage do
		table.insert(dmg, string.format("%s %.1f", label, v))
	end
	table.sort(dmg)
	local function counts(t: { [string]: number }): string
		local parts = {}
		for k, v in t do
			table.insert(parts, k:sub(1, 2) .. v)
		end
		table.sort(parts)
		return if #parts > 0 then table.concat(parts, "") else "-"
	end
	local rifle = {}
	for i, v in a.rifleBins do
		table.insert(rifle, tostring(v))
	end
	local lands = {}
	for i, v in a.lands do
		table.insert(lands, tostring(v))
	end
	local cannon = {}
	for _, t in a.cannon do
		table.insert(cannon, string.format("%.0f", t))
	end
	print(string.format(
		"[BOSS] seed %s attempt %d %s %.1fs | integrity %.0f -> %.0f (min %.0f) | dmg %s | cannon shots %d | rifle/20s %s | trooper-s in range %.0f (max %d at once) | inf landed/20s %s (n %d, <500 %d) | rockets fired %d, starved %.0fs | crates spawned %s taken %s | jets %d killed %d, helis killed %d",
		tostring(plr:GetAttribute("QA_Seed")), attemptNo, outcome, dur, a.intStart,
		state:GetAttribute("Integrity") or 0, a.intMin,
		if #dmg > 0 then table.concat(dmg, ", ") else "none",
		#a.cannon, table.concat(rifle, "/"), a.inRange, a.maxInRange,
		table.concat(lands, "/"), a.landsTotal, a.landsNear,
		a.rocketsFired, a.starved, counts(a.cratesSpawned), counts(a.cratesTaken),
		a.jets, a.jetKills, a.heliKills
	))
	print(string.format("[BOSS-T] seed %s attempt %d: cannon %s | %s", tostring(plr:GetAttribute("QA_Seed")), attemptNo,
		if #cannon > 0 then table.concat(cannon, ",") else "-", table.concat(a.events, " ")))
end

local conns = {}
table.insert(conns, remotes.GameEvent.OnClientEvent:Connect(function(kind, payload)
	local a = attempt
	if not a or type(payload) ~= "table" then
		return
	end
	local t = now() - a.start
	if kind == "Damage" and type(payload.amount) == "number" then
		local label = "other"
		for amount, name in LABELS do
			if math.abs(payload.amount - amount) < 0.01 then
				label = name
			end
		end
		a.damage[label] = (a.damage[label] or 0) + payload.amount
		if label == "rifle" then
			bin(a.rifleBins, t)
		elseif label == "bossCannon" then
			table.insert(a.cannon, t)
		end
	elseif kind == "BossUpdate" then
		for name, intact in payload.weakPoints or {} do
			if not intact and not a.down[name] then
				a.down[name] = true
				mark(name .. "Down")
			end
		end
		if payload.exposed and not a.down.Core then
			a.down.Core = true
			mark("CoreExposed")
		end
		if payload.dead then
			mark("BossDead")
		end
	elseif kind == "AirdropSortie" then
		-- Timeline entry: "I4<ScrubLeft>@t0 land 44 d 520-610" (first
		-- touchdown, landing distances from the outpost).
		local first, dMin, dMax = math.huge, math.huge, 0
		for _, load in payload.loads or {} do
			local lt = load.landT - a.start
			local d = Vector2.new(load.landPos.X, load.landPos.Z).Magnitude
			first, dMin, dMax = math.min(first, lt), math.min(dMin, d), math.max(dMax, d)
			if load.kind == "Infantry" then
				bin(a.lands, math.max(0, lt))
				a.landsTotal += 1
				if d < 500 then
					a.landsNear += 1
				end
			end
		end
		mark(string.format("%s%d<%s>land%.0f,d%.0f-%.0f,t0", payload.kind:sub(1, 1), #(payload.loads or {}), payload.lane, first, dMin, dMax))
	elseif kind == "CrateSpawned" then
		a.cratesSpawned[payload.contents] = (a.cratesSpawned[payload.contents] or 0) + 1
	elseif kind == "CratePickup" then
		a.cratesTaken[payload.contents] = (a.cratesTaken[payload.contents] or 0) + 1
		mark("crate" .. tostring(payload.contents):sub(1, 2))
	elseif kind == "JetWarning" then
		a.jets += 1
		mark("jet")
	elseif kind == "Kill" then
		if payload.kind == "Jet" then
			a.jetKills += 1
		elseif payload.kind == "Helicopter" then
			a.heliKills += 1
		end
	end
end))

table.insert(conns, plr:GetAttributeChangedSignal("Rockets"):Connect(function()
	local a = attempt
	local rockets = plr:GetAttribute("Rockets") or 0
	if a and rockets < a.lastRockets then
		a.rocketsFired += a.lastRockets - rockets
	end
	if a then
		a.lastRockets = rockets
	end
end))

table.insert(conns, state:GetAttributeChangedSignal("Integrity"):Connect(function()
	if attempt then
		attempt.intMin = math.min(attempt.intMin, state:GetAttribute("Integrity") or 0)
	end
end))

table.insert(conns, state:GetAttributeChangedSignal("Phase"):Connect(function()
	local phase = state:GetAttribute("Phase")
	if phase == "Wave" and (state:GetAttribute("Wave") or 0) >= 10 then
		begin()
	elseif phase == "Intermission" or phase == "Defeat" or phase == "Victory" then
		finish(phase)
	end
end))

task.spawn(function()
	while plr:GetAttribute("BossProbe") do
		local a = attempt
		if a then
			if (plr:GetAttribute("Rockets") or 0) == 0 then
				a.starved += 0.5
			end
			local n = 0
			for _, m in Workspace.Enemies:GetChildren() do
				if m:IsA("Model") and m:GetAttribute("Kind") == "Infantry" and m:GetAttribute("State") ~= "Dead" and m.PrimaryPart then
					if (m.PrimaryPart.Position - PIVOT).Magnitude <= RIFLE_RANGE then
						n += 1
					end
				end
			end
			a.inRange += n * 0.5
			a.maxInRange = math.max(a.maxInRange, n)
		end
		task.wait(0.5)
	end
	for _, c in conns do
		c:Disconnect()
	end
end)
return "boss probe started"
