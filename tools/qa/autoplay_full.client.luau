-- QA bot for full playthroughs. Paste into execute_luau (Client datamodel)
-- during a Studio playtest. Uses all three weapons through the Studio-only
-- Debug* attributes: machine gun for infantry/buggies, rockets (with lead)
-- for tanks and the Siege Crawler's weak points/core, AA missiles (holds
-- the lock ~1.2 s) for helicopters and jets, and shoots supply crates when
-- nothing urgent is on screen. On defeat it presses Retry Wave (counted in
-- player attribute QA_Retries; QA_MaxRetries caps the retries of any one
-- wave, after which the bot stops at the Defeat screen).
-- Stop: player:SetAttribute("AutoPlay", false).
-- Airdrops (AD-1): loads in the air are client-only visuals under
-- Workspace.AirdropFx (attribute Airborne), never in Workspace.Enemies, so
-- the bot never fires at them; it only picks enemies that have landed.
-- It prints the outpost damage per wave by attack ("[QA] DAMAGE ...") and
-- audits arrivals: QA_Drops counts landed Infantry/Buggy/Tank
-- (attribute DropLoadId), QA_GroundNoDrop those that appeared without one,
-- QA_DropOutOfBand landings outside 300-800 studs (horizontal).
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local plr = Players.LocalPlayer
local remotes = ReplicatedStorage.Remotes
local state = ReplicatedStorage.GameState
local PIVOT = Vector3.new(0, 72, 0) -- Config.TURRET_PIVOT
local BACK, UP = 13, 8 -- Config.Camera third-person offsets
local ROCKET_SPEED = 340 -- WeaponConfig rocket speed

-- Optional "human-like" handicaps (player attributes, read each tick):
--   QA_Range (studs, default 900), QA_AimError (degrees, default 0),
--   QA_Reaction (seconds before engaging a new target, default 0),
--   QA_Burst (true = machine gun in ~1 s bursts), QA_NoCrates (true).
--   QA_RangeBoss (studs): QA_Range for the boss wave (wave 10), if set.
-- Presets: set QA_Human before pasting. true = the human-like bot the waves
-- were balanced against (DONE.md; settings of the original tuning runs,
-- AD-3): range 700 (1000 in the boss wave, whose cannon reaches ~820), aim
-- error 0.6 deg, reaction 0.7 s, bursts. false = the perfect-aim bot (all
-- handicaps off). With airdrops the reaction delay also applies to each
-- load that lands (it becomes a new target), so the bot reacts to
-- touchdowns like a player.
local PRESETS = {
	[true] = { QA_Range = 700, QA_RangeBoss = 1000, QA_AimError = 0.6, QA_Reaction = 0.7, QA_Burst = true },
	[false] = { QA_Range = 900, QA_RangeBoss = 900, QA_AimError = 0, QA_Reaction = 0, QA_Burst = false },
}
local preset = PRESETS[plr:GetAttribute("QA_Human") :: any]
if preset then
	for name, value in preset do
		plr:SetAttribute(name, value)
	end
end
plr:SetAttribute("AutoPlay", true)
plr:SetAttribute("QA_Retries", plr:GetAttribute("QA_Retries") or 0)
for _, name in { "QA_Drops", "QA_GroundNoDrop", "QA_DropOutOfBand" } do
	plr:SetAttribute(name, plr:GetAttribute(name) or 0)
end

local GROUND_KINDS = { Infantry = true, Buggy = true, Tank = true }
local function bump(name: string)
	plr:SetAttribute(name, (plr:GetAttribute(name) or 0) + 1)
end
local auditConn = workspace.Enemies.ChildAdded:Connect(function(model)
	task.defer(function()
		local kind = model:GetAttribute("Kind")
		if not GROUND_KINDS[kind] or not model:IsA("Model") then
			return
		end
		if model:GetAttribute("DropLoadId") == nil then
			bump("QA_GroundNoDrop")
			return
		end
		bump("QA_Drops")
		local root = model.PrimaryPart
		if root then
			local d = Vector2.new(root.Position.X - PIVOT.X, root.Position.Z - PIVOT.Z).Magnitude
			if d < 298 or d > 802 then
				bump("QA_DropOutOfBand")
			end
		end
	end)
end)

-- Damage audit: every hit on the outpost, classified by its amount (each
-- attack has its own: Config/EnemyConfig), printed per wave attempt as
-- "[QA] DAMAGE wave N <outcome>: ...".
local DAMAGE_KINDS = { [1] = "rifle", [4] = "grenade", [1.1] = "buggy", [1.25] = "heli", [7] = "tank", [12] = "bomb", [1.5] = "bossTurret", [16] = "bossCannon" }
local damage: { [string]: number } = {}
local damageConn = remotes.GameEvent.OnClientEvent:Connect(function(kind, payload)
	if kind == "Damage" and type(payload) == "table" and type(payload.amount) == "number" then
		local label = "other"
		for amount, name in DAMAGE_KINDS do
			if math.abs(payload.amount - amount) < 0.01 then
				label = name
			end
		end
		damage[label] = (damage[label] or 0) + payload.amount
	end
end)
local phaseConn = state:GetAttributeChangedSignal("Phase"):Connect(function()
	local phase = state:GetAttribute("Phase")
	if phase == "Intermission" or phase == "Defeat" then
		local parts = {}
		for label, total in damage do
			table.insert(parts, string.format("%s %.1f", label, total))
		end
		table.sort(parts)
		print(string.format("[QA] DAMAGE wave %s %s: %s", tostring(state:GetAttribute("Wave")), phase, if #parts > 0 then table.concat(parts, ", ") else "none"))
		table.clear(damage)
	elseif phase == "WaveIntro" then
		table.clear(damage)
	end
end)

local waveRetries: { [number]: number } = {}
local lastPos: { [Instance]: { pos: Vector3, t: number, vel: Vector3 } } = {}
local lockTarget, lockSince = nil, 0
local engaged, engagedSince = nil, 0
local lastPulse = 0

local function velocityOf(model: Model, pos: Vector3): Vector3
	local now = os.clock()
	local rec = lastPos[model]
	if rec and now - rec.t > 0.05 then
		local v = (pos - rec.pos) / (now - rec.t)
		rec.vel = rec.vel:Lerp(v, 0.5)
		rec.pos, rec.t = pos, now
	elseif not rec then
		rec = { pos = pos, t = now, vel = Vector3.zero }
		lastPos[model] = rec
	end
	return rec.vel
end

-- Yaw/pitch so the camera ray (which the gun converges on) passes through T.
local function aimAt(target: Vector3)
	local dir = (target - PIVOT).Unit
	for _ = 1, 3 do
		local flat = Vector3.new(dir.X, 0, dir.Z).Unit
		local back = if dir.Y < 0 then dir else flat
		local cam = PIVOT - back * BACK + Vector3.new(0, UP, 0)
		dir = (target - cam).Unit
	end
	local err = plr:GetAttribute("QA_AimError") or 0
	local jitter = if err > 0 then (math.random() - 0.5) * 2 * err else 0
	local jitter2 = if err > 0 then (math.random() - 0.5) * 2 * err else 0
	plr:SetAttribute("DebugYaw", math.deg(math.atan2(-dir.X, -dir.Z)) + jitter)
	plr:SetAttribute("DebugPitch", math.deg(math.asin(math.clamp(dir.Y, -1, 1))) + jitter2)
end

local function findPart(model: Instance, name: string): BasePart?
	local node = model:FindFirstChild(name, true)
	if node and node:IsA("Model") then
		return node.PrimaryPart or node:FindFirstChildWhichIsA("BasePart", true)
	end
	return if node and node:IsA("BasePart") then node else nil
end

-- Boss: aim at the first intact weak point (destroyed ones are thrown off
-- the model), else the exposed core.
local function bossAimPart(model: Model): BasePart?
	for _, name in { "MainCannon", "TurretLeft", "TurretRight" } do
		local p = findPart(model, name)
		if p then
			return p
		end
	end
	return findPart(model, "Core") or model.PrimaryPart
end

local function pick()
	local rockets = plr:GetAttribute("Rockets") or 0
	local missiles = plr:GetAttribute("Missiles") or 0
	local range = plr:GetAttribute("QA_Range") or 900
	if (state:GetAttribute("Wave") or 0) >= 10 and plr:GetAttribute("QA_RangeBoss") then
		range = plr:GetAttribute("QA_RangeBoss")
	end
	local best, bestScore, bestWeapon, bestPoint = nil, -math.huge, "MG", nil
	for _, model in workspace.Enemies:GetChildren() do
		local root = model:IsA("Model") and model.PrimaryPart
		if not root or model:GetAttribute("State") == "Dead" or model:GetAttribute("Airborne") then
			continue
		end
		local kind = model:GetAttribute("Kind")
		local pos = root.Position
		local dist = (pos - PIVOT).Magnitude
		local score, weapon, point = 0, "MG", pos
		if kind == "Jet" then
			score, weapon = (if missiles > 0 then 1200 else 500), if missiles > 0 then "Missile" else "MG"
		elseif kind == "Helicopter" then
			score, weapon = (if missiles > 0 then 900 else 450), if missiles > 0 then "Missile" else "MG"
		elseif kind == "SiegeCrawler" then
			local part = bossAimPart(model)
			point = if part then part.Position else pos
			score, weapon = (if rockets > 0 then 800 else 100), if rockets > 0 then "Rocket" else "MG"
		elseif kind == "Tank" then
			if rockets == 0 then
				continue
			end
			score, weapon = 700, "Rocket"
		elseif kind == "Buggy" then
			score = 450
		elseif kind == "Infantry" then
			local torso = model:FindFirstChild("Torso")
			point = if torso then torso.Position else pos
			score = if dist < 160 then 650 else 250
		else
			continue
		end
		if dist > range then
			continue
		end
		score += (900 - dist) / 4
		if score > bestScore then
			best, bestScore, bestWeapon, bestPoint = model, score, weapon, point
		end
	end
	-- Crates when nothing pressing (score threshold).
	if bestScore < 500 and not plr:GetAttribute("QA_NoCrates") then
		for _, crate in workspace.Crates:GetChildren() do
			local pivot = crate:GetPivot().Position
			local s = 520
			if s > bestScore then
				best, bestScore, bestWeapon, bestPoint = crate, s, "MG", pivot
			end
		end
	end
	return best, bestWeapon, bestPoint
end

local function pulseFire()
	local now = os.clock()
	if now - lastPulse < 0.35 then
		return
	end
	lastPulse = now
	plr:SetAttribute("DebugFire", false)
	task.delay(0.08, function()
		plr:SetAttribute("DebugFire", true)
		task.delay(0.08, function()
			plr:SetAttribute("DebugFire", false)
		end)
	end)
end

task.spawn(function()
	while plr:GetAttribute("AutoPlay") do
		local phase = state:GetAttribute("Phase")
		if phase == "Defeat" then
			plr:SetAttribute("DebugFire", false)
			task.wait(4)
			if state:GetAttribute("Phase") == "Defeat" then
				local wave = state:GetAttribute("Wave") or 0
				waveRetries[wave] = (waveRetries[wave] or 0) + 1
				local cap = plr:GetAttribute("QA_MaxRetries")
				if cap and waveRetries[wave] > cap then
					print(string.format("[QA] wave %d: retry cap %d reached, bot stopped", wave, cap))
					plr:SetAttribute("AutoPlay", false)
					break
				end
				plr:SetAttribute("QA_Retries", (plr:GetAttribute("QA_Retries") or 0) + 1)
				remotes.RetryWave:FireServer()
			end
		elseif phase == "Wave" then
			local target, weapon, point = pick()
			if target ~= engaged then
				engaged, engagedSince = target, os.clock()
			end
			local reacting = os.clock() - engagedSince < (plr:GetAttribute("QA_Reaction") or 0)
			if target and point and not reacting then
				plr:SetAttribute("DebugWeapon", weapon)
				local aimPoint = point
				if weapon == "Rocket" then
					local vel = velocityOf(target, point)
					local t = (point - PIVOT).Magnitude / ROCKET_SPEED
					aimPoint = point + vel * t
				else
					velocityOf(target, point)
				end
				aimAt(aimPoint)
				if weapon == "MG" then
					local burst = plr:GetAttribute("QA_Burst") and (os.clock() % 1.6) > 1.0
					plr:SetAttribute("DebugFire", not burst)
				elseif weapon == "Rocket" then
					pulseFire()
				elseif weapon == "Missile" then
					if lockTarget ~= target then
						lockTarget, lockSince = target, os.clock()
						plr:SetAttribute("DebugFire", false)
					elseif os.clock() - lockSince > 1.25 then
						pulseFire()
					end
				end
			else
				plr:SetAttribute("DebugFire", false)
			end
		else
			plr:SetAttribute("DebugFire", false)
		end
		task.wait(0.05)
	end
	auditConn:Disconnect()
	damageConn:Disconnect()
	phaseConn:Disconnect()
	plr:SetAttribute("DebugFire", false)
end)
return "full autoplay started"
