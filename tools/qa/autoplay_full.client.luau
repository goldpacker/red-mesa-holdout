-- QA bot for full playthroughs. Paste into execute_luau (Client datamodel)
-- during a Studio playtest. Uses all three weapons through the Studio-only
-- Debug* attributes: machine gun for infantry/buggies, rockets (with lead)
-- for tanks and the Siege Crawler's weak points/core, AA missiles (holds
-- the lock ~1.2 s) for helicopters and jets, and shoots supply crates when
-- nothing urgent is on screen. On defeat it presses Retry Wave (counted in
-- player attribute QA_Retries). Stop: player:SetAttribute("AutoPlay", false).
-- Airdrops (AD-1): loads in the air are client-only visuals under
-- Workspace.AirdropFx (attribute Airborne), never in Workspace.Enemies, so
-- the bot never fires at them; it only picks enemies that have landed.
-- It also audits arrivals: QA_Drops counts landed Infantry/Buggy/Tank
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
		if dist > (plr:GetAttribute("QA_Range") or 900) then
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
	plr:SetAttribute("DebugFire", false)
end)
return "full autoplay started"
