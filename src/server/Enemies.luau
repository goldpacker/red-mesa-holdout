--!strict
-- Registry of live enemies: spawning, per-frame updates, damage and cleanup.
-- Enemy kinds are loaded from every ModuleScript in server/EnemyTypes that
-- returns { kind = string, spawn = function } (see Types.EnemyType).

local Workspace = game:GetService("Workspace")

local Types = require(script.Parent.Types)

local Enemies = {}

-- Landing entry (AD-1): `landAt` starts a ground enemy at an airdrop
-- touchdown point instead of its lane start; `loadId` tags the model
-- (attribute DropLoadId) so clients hand off from the descent visual.
export type SpawnOptions = { landAt: Vector3?, loadId: number? }

local SPAWNERS: { [string]: (Types.Context, string, Random, SpawnOptions?) -> Types.Enemy } = {}
for _, module in script.Parent.EnemyTypes:GetChildren() do
	if module:IsA("ModuleScript") then
		local ok, def = pcall(require, module)
		if ok and type(def) == "table" and def.kind and def.spawn then
			SPAWNERS[def.kind] = def.spawn
		else
			warn("[RedMesa] failed to load enemy type " .. module.Name .. ": " .. tostring(def))
		end
	end
end

local alive: { [number]: Types.Enemy } = {}
local nextId = 0
local rng = Random.new()

local function folder(): Folder
	return Workspace:WaitForChild("Enemies") :: Folder
end

function Enemies.has(kind: string): boolean
	return SPAWNERS[kind] ~= nil
end

function Enemies.spawn(ctx: Types.Context, kind: string, lane: string, opts: SpawnOptions?): Types.Enemy
	local spawner = SPAWNERS[kind]
	assert(spawner, "no spawner for " .. kind)
	local enemy = spawner(ctx, lane, rng, opts)
	nextId += 1
	enemy.id = nextId
	enemy.model:SetAttribute("EnemyId", enemy.id)
	enemy.model:SetAttribute("Kind", kind)
	enemy.model:SetAttribute("IsAir", enemy.isAir)
	if opts and opts.loadId then
		enemy.model:SetAttribute("DropLoadId", opts.loadId)
	end
	enemy.model.Parent = folder()
	alive[enemy.id] = enemy
	return enemy
end

function Enemies.update(dt: number)
	for id, enemy in alive do
		if enemy.dead or not enemy.model.Parent then
			alive[id] = nil
			continue
		end
		local ok, err = pcall(enemy.update, dt)
		if not ok then
			warn(string.format("[RedMesa] enemy %s#%d update failed: %s", enemy.kind, id, tostring(err)))
			Enemies.remove(enemy)
			continue
		end
		local threatening = enemy.isThreatening ~= nil and enemy.isThreatening()
		if enemy.model:GetAttribute("Threat") ~= threatening then
			enemy.model:SetAttribute("Threat", threatening)
		end
	end
end

-- Finds the live enemy owning a part hit by a raycast.
function Enemies.fromPart(part: Instance): Types.Enemy?
	local model = part:FindFirstAncestorOfClass("Model")
	while model and model:GetAttribute("EnemyId") == nil do
		model = model:FindFirstAncestorOfClass("Model")
	end
	if not model then
		return nil
	end
	local enemy = alive[model:GetAttribute("EnemyId") :: number]
	if enemy and not enemy.dead then
		return enemy
	end
	return nil
end

-- Applies damage from `weapon` ("MG", "Rocket", "Missile"), honouring the
-- enemy's resistances and onDamage hook. Returns true if this hit killed it.
function Enemies.damage(enemy: Types.Enemy, amount: number, weapon: string, part: BasePart?): boolean
	if enemy.dead then
		return false
	end
	local resist = enemy.resist and enemy.resist[weapon]
	local dealt = amount * (if resist then resist else 1)
	if enemy.onDamage then
		local ok, result = pcall(enemy.onDamage, dealt, weapon, part)
		dealt = if ok and type(result) == "number" then result else 0
	end
	enemy.health -= dealt
	if enemy.health > 0 then
		return false
	end
	enemy.dead = true
	alive[enemy.id] = nil
	local ok, err = pcall(enemy.die)
	if not ok then
		warn("[RedMesa] enemy die failed: " .. tostring(err))
		enemy.model:Destroy()
	end
	return true
end

-- Splash damage with linear falloff to 25% at the edge. Returns every enemy
-- touched with whether it died, nearest first.
function Enemies.damageRadius(center: Vector3, radius: number, amount: number, weapon: string): { { enemy: Types.Enemy, killed: boolean } }
	local hits = {}
	for _, enemy in alive do
		local dist = (enemy.root.Position - center).Magnitude
		if dist <= radius then
			table.insert(hits, { enemy = enemy, dist = dist })
		end
	end
	table.sort(hits, function(a, b)
		return a.dist < b.dist
	end)
	local results = {}
	for _, h in hits do
		local falloff = 1 - 0.75 * (h.dist / radius)
		local killed = Enemies.damage(h.enemy, amount * falloff, weapon, nil)
		table.insert(results, { enemy = h.enemy, killed = killed })
	end
	return results
end

function Enemies.remove(enemy: Types.Enemy)
	enemy.dead = true
	alive[enemy.id] = nil
	enemy.model:Destroy()
end

function Enemies.count(): number
	local n = 0
	for _ in alive do
		n += 1
	end
	return n
end

function Enemies.all(): { [number]: Types.Enemy }
	return alive
end

-- Removes every enemy, corpse and wreck from the battlefield.
function Enemies.clearAll()
	for _, enemy in alive do
		enemy.dead = true
	end
	table.clear(alive)
	for _, name in { "Enemies", "Wrecks", "Projectiles" } do
		local f = Workspace:FindFirstChild(name)
		if f then
			f:ClearAllChildren()
		end
	end
end

return Enemies
