--!strict
-- Server-authoritative rockets and AA missiles. Each projectile is simulated
-- here (a raycast per step, homing for missiles) and all damage is applied
-- here. Clients only render: they receive a `Projectile` event with the
-- launch state and a `ProjectileEnd` event where it detonated.

local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local WeaponConfig = require(ReplicatedStorage.Shared.WeaponConfig)
local Enemies = require(script.Parent.Enemies)
local Types = require(script.Parent.Types)

export type Reporter = {
	-- A projectile damaged `enemy` (routes to Weapons hooks.onHit).
	hit: (player: Player, enemy: Types.Enemy, killed: boolean, position: Vector3) -> (),
	-- A projectile struck or splashed a non-enemy part (supply crates).
	worldHit: (player: Player, part: BasePart, position: Vector3) -> (),
}

type Projectile = {
	id: number,
	kind: string, -- "Rocket" | "Missile"
	owner: Player,
	pos: Vector3,
	dir: Vector3,
	speed: number,
	age: number,
	target: Types.Enemy?,
	targetLast: Vector3?,
	targetVel: Vector3,
}

local Projectiles = {}

local ROCKET = WeaponConfig.Rocket
local MISSILE = WeaponConfig.Missile
local CRATE_TAG = "SupplyCrate"
local CRATE_MARGIN = 4 -- crates are a few studs across; count near misses

local live: { [number]: Projectile } = {}
local nextId = 0
local reporter: Reporter? = nil
local gameEvent: RemoteEvent? = nil

local rayParams = RaycastParams.new()
rayParams.FilterType = Enum.RaycastFilterType.Exclude

local function broadcast(kind: string, payload: any)
	if gameEvent then
		gameEvent:FireAllClients(kind, payload)
	end
end

local function refreshFilter()
	local list: { Instance } = {}
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local emplacement = battlefield and battlefield:FindFirstChild("Emplacement")
	for _, inst in { emplacement, Workspace:FindFirstChild("Projectiles"), Workspace:FindFirstChild("Wrecks") } do
		if inst then
			table.insert(list, inst)
		end
	end
	rayParams.FilterDescendantsInstances = list
end

-- Closest distance from point `p` to the segment a->b.
local function segmentDistance(a: Vector3, b: Vector3, p: Vector3): number
	local ab = b - a
	local len2 = ab:Dot(ab)
	if len2 < 1e-6 then
		return (p - a).Magnitude
	end
	local t = math.clamp((p - a):Dot(ab) / len2, 0, 1)
	return (a + ab * t - p).Magnitude
end

local function crateParts(center: Vector3, radius: number, skip: Instance?): { BasePart }
	local found = {}
	for _, tagged in CollectionService:GetTagged(CRATE_TAG) do
		if not tagged:IsDescendantOf(Workspace) or (skip and (skip == tagged or skip:IsDescendantOf(tagged))) then
			continue
		end
		local part: BasePart? = nil
		local position: Vector3
		if tagged:IsA("Model") then
			part = tagged.PrimaryPart or tagged:FindFirstChildWhichIsA("BasePart", true)
			position = tagged:GetPivot().Position
		elseif tagged:IsA("BasePart") then
			part = tagged
			position = tagged.Position
		else
			continue
		end
		if part and (position - center).Magnitude <= radius + CRATE_MARGIN then
			table.insert(found, part)
		end
	end
	return found
end

local function crateRoot(part: BasePart): Instance?
	for _, tagged in CollectionService:GetTagged(CRATE_TAG) do
		if tagged == part or part:IsDescendantOf(tagged) then
			return tagged
		end
	end
	return nil
end

-- Applies direct + splash damage and reports every result. The primary
-- enemy (direct hit, or nearest in the blast) is always reported so the
-- player gets a hit marker; other splashed enemies only when killed, which
-- keeps accuracy stats close to "one shot, one hit".
local function detonate(p: Projectile, position: Vector3, part: BasePart?)
	local cfg = if p.kind == "Rocket" then ROCKET else MISSILE
	local order: { Types.Enemy } = {}
	local outcome: { [Types.Enemy]: boolean } = {}

	local direct = part and Enemies.fromPart(part)
	if direct then
		local amount = if p.kind == "Rocket" then ROCKET.DIRECT_DAMAGE else MISSILE.DAMAGE
		outcome[direct] = Enemies.damage(direct, amount, p.kind, part)
		table.insert(order, direct)
	elseif p.kind == "Missile" and p.target and not p.target.dead then
		local target = p.target
		if (target.root.Position - position).Magnitude <= MISSILE.PROXIMITY * 1.6 then
			outcome[target] = Enemies.damage(target, MISSILE.DAMAGE, "Missile", nil)
			table.insert(order, target)
		end
	end

	for _, r in Enemies.damageRadius(position, cfg.SPLASH_RADIUS, cfg.SPLASH_DAMAGE, p.kind) do
		if outcome[r.enemy] == nil then
			outcome[r.enemy] = r.killed
			table.insert(order, r.enemy)
		elseif r.killed then
			outcome[r.enemy] = true
		end
	end

	local rep = reporter
	if rep and p.owner.Parent then
		for i, enemy in order do
			local killed = outcome[enemy]
			if i == 1 or killed then
				rep.hit(p.owner, enemy, killed, if i == 1 then position else enemy.root.Position)
			end
		end
		local skip: Instance? = nil
		if part and not direct then
			rep.worldHit(p.owner, part, position)
			skip = crateRoot(part)
		end
		for _, cratePart in crateParts(position, cfg.SPLASH_RADIUS, skip) do
			rep.worldHit(p.owner, cratePart, position)
		end
	end

	broadcast("ProjectileEnd", {
		id = p.id,
		kind = p.kind,
		position = position,
		exploded = true,
		air = part == nil,
		enemy = direct ~= nil or #order > 0,
	})
end

local function finish(p: Projectile)
	live[p.id] = nil
end

local function stepRocket(p: Projectile, dt: number)
	local delta = p.dir * p.speed * dt
	local result = Workspace:Raycast(p.pos, delta, rayParams)
	if result then
		finish(p)
		detonate(p, result.Position, result.Instance :: BasePart)
		return
	end
	p.pos += delta
	if p.age * p.speed > ROCKET.MAX_RANGE then
		finish(p)
		broadcast("ProjectileEnd", { id = p.id, kind = p.kind, position = p.pos, exploded = false })
	end
end

local function stepMissile(p: Projectile, dt: number)
	local target = p.target
	local targetPos: Vector3? = nil
	if target and not target.dead and target.model.Parent then
		local tp = target.root.Position
		if p.targetLast then
			local instant = (tp - p.targetLast) / math.max(dt, 1 / 240)
			p.targetVel = p.targetVel:Lerp(instant, 0.35)
		end
		p.targetLast = tp
		targetPos = tp
	else
		p.target = nil
	end

	local oldPos = p.pos
	local newPos, newDir, newSpeed = WeaponConfig.missileStep(p.pos, p.dir, p.speed, p.age, dt, targetPos, p.targetVel)
	local result = Workspace:Raycast(oldPos, newPos - oldPos, rayParams)
	if result then
		finish(p)
		detonate(p, result.Position, result.Instance :: BasePart)
		return
	end
	p.pos, p.dir, p.speed = newPos, newDir, newSpeed

	if targetPos and segmentDistance(oldPos, newPos, targetPos) <= MISSILE.PROXIMITY then
		finish(p)
		detonate(p, newPos, nil)
		return
	end
	if p.age >= MISSILE.LIFETIME then
		-- Self-destructs in the air once out of fuel.
		finish(p)
		detonate(p, p.pos, nil)
	end
end

local function step(dt: number)
	if next(live) == nil then
		return
	end
	refreshFilter()
	for _, p in live do
		p.age += dt
		if not p.owner.Parent then
			finish(p)
			continue
		end
		local ok, err = pcall(if p.kind == "Rocket" then stepRocket else stepMissile, p, dt)
		if not ok then
			warn("[RedMesa] projectile step failed: " .. tostring(err))
			finish(p)
		end
	end
end

local function launch(owner: Player, kind: string, origin: Vector3, dir: Vector3, speed: number, token: any, target: Types.Enemy?): number
	nextId += 1
	local p: Projectile = {
		id = nextId,
		kind = kind,
		owner = owner,
		pos = origin,
		dir = dir,
		speed = speed,
		age = 0,
		target = target,
		targetLast = nil,
		targetVel = Vector3.zero,
	}
	live[p.id] = p
	broadcast("Projectile", {
		id = p.id,
		kind = kind,
		origin = origin,
		dir = dir,
		speed = speed,
		t0 = Workspace:GetServerTimeNow(),
		owner = owner.UserId,
		token = if type(token) == "number" then token else nil,
		targetId = if target then target.id else nil,
	})
	return p.id
end

function Projectiles.fireRocket(owner: Player, origin: Vector3, dir: Vector3, token: any): number
	return launch(owner, "Rocket", origin, dir, ROCKET.SPEED, token, nil)
end

function Projectiles.fireMissile(owner: Player, origin: Vector3, dir: Vector3, target: Types.Enemy, token: any): number
	return launch(owner, "Missile", origin, dir, MISSILE.LAUNCH_SPEED, token, target)
end

-- Drops every projectile in flight without detonating (new run / retry).
function Projectiles.clear()
	for id, p in live do
		broadcast("ProjectileEnd", { id = id, kind = p.kind, position = p.pos, exploded = false })
	end
	table.clear(live)
end

function Projectiles.count(): number
	local n = 0
	for _ in live do
		n += 1
	end
	return n
end

function Projectiles.init(rep: Reporter)
	reporter = rep
	gameEvent = ReplicatedStorage:WaitForChild("Remotes"):WaitForChild("GameEvent") :: RemoteEvent
	RunService.Heartbeat:Connect(step)
end

return Projectiles
