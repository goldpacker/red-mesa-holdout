--!strict
-- Registry of live enemies: spawning, per-frame updates, damage and cleanup.

local Workspace = game:GetService("Workspace")

local Types = require(script.Parent.Types)
local Infantry = require(script.Parent.Infantry)

local Enemies = {}

local SPAWNERS: { [string]: (Types.Context, string, Random) -> Types.Enemy } = {
	Infantry = Infantry.spawn,
}

local alive: { [number]: Types.Enemy } = {}
local nextId = 0
local rng = Random.new()

local function folder(): Folder
	return Workspace:WaitForChild("Enemies") :: Folder
end

function Enemies.spawn(ctx: Types.Context, kind: string, lane: string): Types.Enemy
	local spawner = SPAWNERS[kind]
	assert(spawner, "no spawner for " .. kind)
	local enemy = spawner(ctx, lane, rng)
	nextId += 1
	enemy.id = nextId
	enemy.model:SetAttribute("EnemyId", enemy.id)
	enemy.model:SetAttribute("Kind", kind)
	enemy.model:SetAttribute("IsAir", enemy.isAir)
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

-- Applies damage; returns true if this hit killed the enemy.
function Enemies.damage(enemy: Types.Enemy, amount: number): boolean
	if enemy.dead then
		return false
	end
	enemy.health -= amount
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
