--!strict
-- Siege Crawler (wave 10 boss): a huge multi-turreted land fortress that
-- grinds up the Road. Its three weak points (TurretLeft, TurretRight,
-- MainCannon) take rocket hits through onDamage; each one destroyed awards
-- 1000 points and is blown off the hull, leaving a fire. With all three
-- gone the CoreArmor blows off and the Core can be killed (5000 points).
-- The main cannon fires a devastating shot after a long visible charge
-- (BossCharge {duration}; model attributes Charging/ChargeEnd drive the
-- glow). It calls in escorts, requests rocket-biased crates, and on death
-- dismisses every remaining enemy so the wave ends.
--
-- Events: BossUpdate { weakPoints = { TurretLeft = intact?, ... },
-- core = 0..1, exposed = bool, dead = bool? } on spawn and every change.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local EnemyConfig = require(ReplicatedStorage.Shared.EnemyConfig)
local Types = require(script.Parent.Parent.Types)
local CrawlerModel = require(script.Parent.Common.CrawlerModel)
local Dress = require(script.Parent.Common.Dress)
local Driver = require(script.Parent.Common.Driver)
local Kit = require(script.Parent.Common.Kit)
local Rig = require(script.Parent.Common.Rig)

local SiegeCrawler = {}
SiegeCrawler.kind = "SiegeCrawler"

local CFG = EnemyConfig.SiegeCrawler
local FLIGHT = EnemyConfig.Flight
local PIVOT = Config.TURRET_PIVOT
local WEAK_POINTS = { "TurretLeft", "TurretRight", "MainCannon" }
-- A splash hit this soon after a direct (part) hit is the same rocket.
local SPLASH_DEDUPE = 0.3

type WeakPoint = { name: string, health: number, maxHealth: number, intact: boolean, pivot: CFrame, muzzle: CFrame, timer: number }

local function build(): Model
	local asset = Kit.loadAsset("SiegeCrawler", { "Root", "Core", "CoreArmor", "TurretLeft", "TurretRight", "MainCannon", "CannonGlow" })
	if asset then
		Dress.crawler(asset)
	end
	local model = asset or CrawlerModel.build()
	model.Name = "SiegeCrawler"
	return model
end

function SiegeCrawler.spawn(ctx: Types.Context, laneName: string, rng: Random): Types.Enemy
	local lane = Kit.groundLane(laneName, "Road")
	local model = build()
	local root = Rig.prepare(model, WEAK_POINTS)
	local rootOffset = Rig.rootOffset(root)
	local coreHealth = CFG.CORE_HEALTH

	local weak: { [string]: WeakPoint } = {}
	for _, name in WEAK_POINTS do
		local pivot, muzzle = Kit.moverFrames(model, name, "Muzzle")
		local hp = (CFG.WEAK_POINT_HEALTH :: any)[name]
		weak[name] = { name = name, health = hp, maxHealth = hp, intact = true, pivot = pivot, muzzle = muzzle, timer = rng:NextNumber(2, 4) }
	end
	local core = model:FindFirstChild("Core", true) :: BasePart?

	local driver = Driver.new(lane, 0, Vector2.zero)
	local enemy: Types.Enemy = {
		id = 0,
		kind = "SiegeCrawler",
		model = model,
		root = root,
		health = coreHealth,
		maxHealth = coreHealth,
		dead = false,
		points = CFG.POINTS,
		isAir = false,
		resist = CFG.RESIST,
	}

	local frame = CFrame.identity
	local moving = true
	local announced = false
	local exposed = false
	local charging = false
	local chargeTimer = 0
	local cannonTimer: number = CFG.CANNON_FIRST
	local crateTimer: number = CFG.CRATE_FIRST
	local escortTimer: number = CFG.ESCORT_FIRST
	local escortIndex = 0
	local escorts: { Types.Enemy } = {}
	local lastDirectHit = -math.huge

	local function place()
		frame = Kit.groundFrame(driver.position, driver.heading, 40, 20, 0)
		root.CFrame = frame * rootOffset
	end
	place()
	model:SetAttribute("State", "Advance")

	local function update()
		local flags = {}
		for name, w in weak do
			flags[name] = w.intact
		end
		ctx.emit("BossUpdate", {
			weakPoints = flags,
			core = math.clamp(enemy.health / enemy.maxHealth, 0, 1),
			exposed = exposed,
			dead = enemy.dead or nil,
		})
	end

	local function worldOf(w: WeakPoint): Vector3
		return (frame * w.pivot).Position
	end

	local function cancelCharge()
		if charging then
			charging = false
			model:SetAttribute("Charging", false)
			ctx.emit("BossCharge", { duration = 0, cancelled = true })
		end
	end

	-- A fire left burning in the socket of a destroyed weak point.
	local function socketFire(position: Vector3, scale: number)
		local anchor = Instance.new("Part")
		anchor.Name = "SocketFire"
		anchor.Size = Vector3.one
		anchor.Transparency = 1
		anchor.CanCollide = false
		anchor.CanQuery = false
		anchor.CanTouch = false
		anchor.Massless = true
		anchor.Anchored = false
		anchor.CFrame = CFrame.new(position)
		anchor:SetAttribute("Burning", scale)
		local weld = Instance.new("Weld")
		weld.Part0 = root
		weld.Part1 = anchor
		weld.C0 = root.CFrame:ToObjectSpace(anchor.CFrame)
		weld.Parent = anchor
		anchor.Parent = model
	end

	local function throwPiece(name: string, scale: number)
		local piece = Kit.detach(model, name)
		if not piece then
			return
		end
		Kit.char(piece)
		piece:SetAttribute("FxScale", scale)
		piece:SetAttribute("State", "Thrown")
		local out = (piece:GetPivot().Position - frame.Position) * Vector3.new(1, 0, 1)
		local dir = if out.Magnitude > 1 then out.Unit else frame.RightVector
		Kit.fling(piece, dir * rng:NextNumber(14, 22) + Vector3.new(0, rng:NextNumber(30, 40), 0), Vector3.new(rng:NextNumber(-1.5, 1.5), rng:NextNumber(-1, 1), rng:NextNumber(-1.5, 1.5)), "Debris")
	end

	local function exposeCore()
		exposed = true
		model:SetAttribute("CoreExposed", true)
		throwPiece("CoreArmor", 0.9)
		if core then
			core.Material = Enum.Material.Neon
			core.Color = (core:GetAttribute("CoreColor") :: Color3?) or Color3.fromRGB(255, 86, 30)
			Kit.glow(core, 45, 3, Color3.fromRGB(255, 90, 40))
		end
	end

	local function destroyWeakPoint(w: WeakPoint)
		w.intact = false
		local at = worldOf(w)
		ctx.awardPoints(CFG.WEAK_POINT_POINTS, at, "WEAK POINT")
		if w.name == "MainCannon" then
			cancelCharge()
		end
		throwPiece(w.name, if w.name == "MainCannon" then 1.3 else 0.9)
		socketFire(at, if w.name == "MainCannon" then 1.4 else 1)
		local remaining = 0
		for _, other in weak do
			if other.intact then
				remaining += 1
			end
		end
		if remaining == 0 then
			exposeCore()
		end
	end

	local function owner(part: BasePart): string?
		local node: Instance? = part
		while node and node ~= model do
			if weak[node.Name] then
				return node.Name
			elseif node.Name == "Core" or node.Name == "CoreArmor" then
				return node.Name
			end
			node = node.Parent
		end
		return nil
	end

	-- Splash with no part: credit the intact target nearest the outpost.
	local function nearestTarget(): string?
		if exposed then
			return "Core"
		end
		local best, bestDist = nil, math.huge
		for name, w in weak do
			if w.intact then
				local d = (worldOf(w) - PIVOT).Magnitude
				if d < bestDist then
					best, bestDist = name, d
				end
			end
		end
		return best
	end

	function enemy.onDamage(amount: number, weapon: string, part: BasePart?): number
		if weapon == "Debug" then
			return amount
		end
		local target: string?
		if part then
			lastDirectHit = os.clock()
			target = owner(part)
			if not target then
				-- Hull hit: partial credit to the nearest intact target so a
				-- rocket into the middle of the hulk is never wasted.
				target = nearestTarget()
				amount *= CFG.SPLASH_CREDIT
			end
		elseif os.clock() - lastDirectHit > SPLASH_DEDUPE then
			target = nearestTarget()
			amount *= CFG.SPLASH_CREDIT
		end
		if not target then
			return 0
		end
		if target == "Core" then
			if not exposed then
				return 0
			end
			task.defer(update)
			return amount
		end
		local w = weak[target]
		if not w or not w.intact then
			return 0
		end
		w.health -= amount
		if w.health <= 0 then
			destroyWeakPoint(w)
			update()
		end
		return 0
	end

	local function spawnEscorts()
		for i = #escorts, 1, -1 do
			local e = escorts[i]
			if e.dead or not e.model.Parent then
				table.remove(escorts, i)
			end
		end
		if #escorts >= CFG.ESCORT_MAX_LIVE then
			return
		end
		escortIndex = escortIndex % #CFG.ESCORTS + 1
		local wave = CFG.ESCORTS[escortIndex]
		local laneChoice = Kit.pick(wave.lanes, rng)
		for i = 1, wave.count do
			task.delay((i - 1) * 0.9, function()
				if enemy.dead then
					return
				end
				local e = ctx.spawn(wave.kind, laneChoice)
				if e then
					table.insert(escorts, e)
				end
			end)
		end
	end

	local function fireTurret(w: WeakPoint)
		local yaw = Kit.aimYaw(frame, w.pivot, PIVOT)
		local from = Kit.muzzleWorld(frame, w.pivot, w.muzzle, yaw)
		local to = Kit.impactPoint(from, rng)
		ctx.enemyFired(enemy, "BossTurret", from, to)
		local at = frame.Position
		task.delay(FLIGHT.BOSS_TURRET + 0.3, function()
			if not enemy.dead then
				ctx.damageOutpost(CFG.TURRET_DAMAGE, at, false)
			end
		end)
	end

	local function fireCannon()
		local w = weak.MainCannon
		local yaw = Kit.aimYaw(frame, w.pivot, PIVOT)
		local from = Kit.muzzleWorld(frame, w.pivot, w.muzzle, yaw)
		local to = Kit.impactPoint(from, rng)
		ctx.enemyFired(enemy, "BossCannon", from, to)
		local at = frame.Position
		task.delay(FLIGHT.BOSS_SHELL, function()
			ctx.damageOutpost(CFG.CANNON_DAMAGE, at, true)
		end)
	end

	function enemy.update(dt: number)
		if not announced then
			announced = true
			update()
		end
		if moving then
			driver:step(dt, CFG.SPEED, CFG.TURN_RATE)
			place()
			if Kit.outpostDistance(frame.Position) <= CFG.STOP_DISTANCE or driver.finished then
				moving = false
				model:SetAttribute("State", "Siege")
			end
		end
		local inArc = Kit.inArc(frame.Position)

		-- Main cannon: long visible charge, then a devastating shot.
		local cannon = weak.MainCannon
		if cannon.intact then
			if charging then
				chargeTimer -= dt
				if chargeTimer <= 0 then
					charging = false
					model:SetAttribute("Charging", false)
					fireCannon()
					cannonTimer = CFG.CANNON_INTERVAL
				end
			else
				cannonTimer -= dt
				if cannonTimer <= 0 and inArc and Kit.outpostDistance(frame.Position) <= CFG.CANNON_RANGE then
					charging = true
					chargeTimer = CFG.CANNON_CHARGE
					model:SetAttribute("ChargeEnd", Workspace:GetServerTimeNow() + CFG.CANNON_CHARGE)
					model:SetAttribute("Charging", true)
					ctx.emit("BossCharge", { duration = CFG.CANNON_CHARGE })
				end
			end
		end

		-- Side turrets: steady autocannon bursts.
		for _, name in { "TurretLeft", "TurretRight" } do
			local w = weak[name]
			if w.intact then
				w.timer -= dt
				if w.timer <= 0 and inArc and Kit.outpostDistance(frame.Position) <= CFG.TURRET_RANGE then
					w.timer = CFG.TURRET_INTERVAL * rng:NextNumber(0.8, 1.2)
					fireTurret(w)
				end
			end
		end

		crateTimer -= dt
		if crateTimer <= 0 then
			crateTimer = CFG.CRATE_INTERVAL
			ctx.dropCrate("Rockets")
		end
		escortTimer -= dt
		if escortTimer <= 0 then
			escortTimer = CFG.ESCORT_INTERVAL
			spawnEscorts()
		end
	end

	function enemy.isThreatening(): boolean
		return Kit.outpostDistance(frame.Position) <= CFG.TURRET_RANGE
	end

	function enemy.distanceToOutpost(): number
		return Kit.outpostDistance(frame.Position)
	end

	-- Every other enemy breaks off: they die where they stand (no points)
	-- so the wave can end as soon as the boss falls.
	local function dismissAll()
		local ok, Enemies = pcall(require, script.Parent.Parent.Enemies)
		if not ok then
			return
		end
		for _, other in (Enemies :: any).all() do
			if other ~= enemy and not other.dead then
				other.dead = true
				local fine, err = pcall(other.die)
				if not fine then
					warn("[RedMesa] escort dismiss failed: " .. tostring(err))
					other.model:Destroy()
				end
			end
		end
	end

	function enemy.die()
		cancelCharge()
		update()
		dismissAll()
		Kit.noQuery(model)
		model:SetAttribute("DeathDuration", CFG.DEATH_SEQUENCE)
		Kit.toWrecks(model, "Dying", 3.5)
		task.delay(CFG.DEATH_SEQUENCE, function()
			if not model.Parent then
				return
			end
			for _, name in WEAK_POINTS do
				if weak[name].intact then
					throwPiece(name, 0.8)
				end
			end
			if not exposed then
				throwPiece("CoreArmor", 0.8)
			end
			root.CFrame = root.CFrame * CFrame.new(0, -1.5, 0) * CFrame.Angles(math.rad(2), 0, math.rad(-3))
			Kit.char(model)
			model:SetAttribute("State", "Wreck")
		end)
	end

	return enemy
end

return SiegeCrawler
