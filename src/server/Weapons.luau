--!strict
-- Server-authoritative weapon fire. The client sends a unit direction from
-- the muzzle; the server validates rate, heat, ammo, reload and aim limits,
-- then raycasts (machine gun) or launches a simulated projectile (rockets,
-- missiles; see Projectiles.luau) and applies damage.
--
-- Remotes.FireWeapon messages (client -> server):
--   ("MG", dir)
--   ("Rocket", dir, token)
--   ("Missile", dir, token, targetEnemyId)   -- requires a lock (below)
--   ("Lock", targetEnemyId | nil)             -- client started acquiring
-- Ammo lives on the Player as attributes (WeaponConfig.Attr).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local WeaponConfig = require(ReplicatedStorage.Shared.WeaponConfig)
local Enemies = require(script.Parent.Enemies)
local Projectiles = require(script.Parent.Projectiles)
local Types = require(script.Parent.Types)

export type Hooks = {
	canFire: () -> boolean,
	onShot: (player: Player) -> (),
	onHit: (player: Player, enemy: Types.Enemy, killed: boolean, position: Vector3, headshot: boolean) -> (),
	-- Optional: any weapon hit a non-enemy part (supply crates).
	onWorldHit: ((player: Player, part: BasePart, position: Vector3) -> ())?,
}

type GunState = {
	heat: number,
	lastShot: number,
	lockedUntil: number,
	lastRicochet: number,
}

type LockState = { id: number, since: number }

local Weapons = {}

local MG = Config.MachineGun
local ROCKET = WeaponConfig.Rocket
local MISSILE = WeaponConfig.Missile
local SERVER = WeaponConfig.Server
local ATTR = WeaponConfig.Attr
-- Client and server simulate heat independently; allow a little slack so
-- network jitter never rejects a shot the client legitimately fired.
local HEAT_TOLERANCE = 1.15
local RATE_TOLERANCE = 0.6

local states: { [Player]: GunState } = {}
local locks: { [Player]: LockState } = {}
local hooks: Hooks
local gameEvent: RemoteEvent

local rayParams = RaycastParams.new()
rayParams.FilterType = Enum.RaycastFilterType.Exclude

local function stateFor(player: Player): GunState
	local s = states[player]
	if not s then
		s = { heat = 0, lastShot = -math.huge, lockedUntil = 0, lastRicochet = 0 }
		states[player] = s
	end
	return s
end

local function validDirection(dir: any): boolean
	if typeof(dir) ~= "Vector3" then
		return false
	end
	local m = dir.Magnitude
	if m ~= m or m < 0.95 or m > 1.05 then
		return false
	end
	local yaw = math.deg(math.atan2(-dir.X, -dir.Z))
	local pitch = math.deg(math.asin(math.clamp(dir.Y, -1, 1)))
	return math.abs(yaw) <= Config.YAW_LIMIT + 8 and pitch >= Config.PITCH_MIN - 20 and pitch <= Config.PITCH_MAX + 8
end

local function muzzleOrigin(dir: Vector3): Vector3
	return Config.TURRET_PIVOT + dir * Config.MUZZLE_OFFSET
end

local function worldHit(player: Player, part: BasePart, position: Vector3)
	local fn = hooks.onWorldHit
	if fn then
		local ok, err = pcall(fn, player, part, position)
		if not ok then
			warn("[RedMesa] onWorldHit failed: " .. tostring(err))
		end
	end
end

-- Rockets and missiles only fire in combat proper: during the intermission
-- they would burn ammo after the restock.
local function heavyAllowed(): boolean
	local gameState = ReplicatedStorage:FindFirstChild("GameState")
	local phase = gameState and gameState:GetAttribute("Phase")
	return phase == "Wave" or phase == "WaveIntro"
end

local function ricochet(player: Player, s: GunState, enemy: Types.Enemy, position: Vector3)
	local resist = enemy.resist and enemy.resist.MG
	if resist == nil or resist > SERVER.RICOCHET_RESIST then
		return
	end
	local now = os.clock()
	if now - s.lastRicochet < SERVER.RICOCHET_INTERVAL then
		return
	end
	s.lastRicochet = now
	gameEvent:FireClient(player, "Ricochet", { position = position })
end

local function fireMachineGun(player: Player, dir: Vector3)
	local now = os.clock()
	local s = stateFor(player)
	if now < s.lockedUntil then
		return
	end
	local since = now - s.lastShot
	if since < MG.FIRE_INTERVAL * RATE_TOLERANCE then
		return
	end
	if since > MG.COOL_DELAY then
		s.heat = math.max(0, s.heat - MG.COOL_RATE * (since - MG.COOL_DELAY))
	end
	s.heat += MG.HEAT_PER_SHOT
	s.lastShot = now
	if s.heat >= MG.MAX_HEAT * HEAT_TOLERANCE then
		s.lockedUntil = now + MG.OVERHEAT_LOCK
		s.heat = 0
	end

	hooks.onShot(player)

	local origin = muzzleOrigin(dir)
	rayParams.FilterDescendantsInstances = { Workspace.Battlefield.Emplacement, Workspace.Projectiles }
	local result = Workspace:Raycast(origin, dir * MG.RANGE, rayParams)
	if not result then
		return
	end
	local enemy = Enemies.fromPart(result.Instance)
	if not enemy then
		worldHit(player, result.Instance :: BasePart, result.Position)
		return
	end
	local headshot = result.Instance.Name == "Head"
	local damage = MG.DAMAGE * (if headshot then MG.HEADSHOT_MULTIPLIER else 1)
	local killed = Enemies.damage(enemy, damage, "MG", result.Instance :: BasePart)
	hooks.onHit(player, enemy, killed, result.Position, headshot)
	if not killed then
		ricochet(player, s, enemy, result.Position)
	end
end

local function reloadReady(player: Player, attr: string): boolean
	local endsAt = player:GetAttribute(attr)
	return typeof(endsAt) ~= "number" or Workspace:GetServerTimeNow() >= endsAt - SERVER.RELOAD_TOLERANCE
end

local function takeAmmo(player: Player, ammoAttr: string, reloadAttr: string, reload: number): boolean
	local ammo = player:GetAttribute(ammoAttr)
	if typeof(ammo) ~= "number" or ammo <= 0 or not reloadReady(player, reloadAttr) then
		return false
	end
	player:SetAttribute(ammoAttr, ammo - 1)
	player:SetAttribute(reloadAttr, Workspace:GetServerTimeNow() + reload)
	return true
end

local function fireRocket(player: Player, dir: Vector3, token: any)
	if not heavyAllowed() or not takeAmmo(player, ATTR.Rockets, ATTR.RocketReloadEndsAt, ROCKET.RELOAD) then
		return
	end
	hooks.onShot(player)
	Projectiles.fireRocket(player, muzzleOrigin(dir), dir, token)
end

-- The missile target must be a live aircraft the client has been tracking
-- for most of the lock time, roughly along the fire direction, in range.
local function validLockTarget(player: Player, dir: Vector3, targetId: any): Types.Enemy?
	if type(targetId) ~= "number" then
		return nil
	end
	local enemy = Enemies.all()[targetId]
	if not enemy or enemy.dead or not enemy.isAir then
		return nil
	end
	local lock = locks[player]
	if not lock or lock.id ~= targetId or os.clock() - lock.since < MISSILE.LOCK_TIME * SERVER.LOCK_TIME_TOLERANCE then
		return nil
	end
	local offset = enemy.root.Position - muzzleOrigin(dir)
	if offset.Magnitude > MISSILE.LOCK_RANGE * 1.1 then
		return nil
	end
	local angle = math.deg(math.acos(math.clamp(offset.Unit:Dot(dir), -1, 1)))
	if angle > MISSILE.BREAK_DEG + SERVER.LOCK_CONE_TOLERANCE_DEG then
		return nil
	end
	return enemy
end

local function fireMissile(player: Player, dir: Vector3, token: any, targetId: any)
	if not heavyAllowed() then
		return
	end
	local target = validLockTarget(player, dir, targetId)
	if not target then
		return
	end
	if not takeAmmo(player, ATTR.Missiles, ATTR.MissileReloadEndsAt, MISSILE.RELOAD) then
		return
	end
	hooks.onShot(player)
	Projectiles.fireMissile(player, muzzleOrigin(dir), dir, target, token)
	locks[player] = nil
end

local function noteLock(player: Player, targetId: any)
	if type(targetId) ~= "number" then
		locks[player] = nil
		return
	end
	local current = locks[player]
	if current and current.id == targetId then
		return
	end
	locks[player] = { id = targetId, since = os.clock() }
end

local function restock(player: Player)
	player:SetAttribute(ATTR.Rockets, ROCKET.AMMO)
	player:SetAttribute(ATTR.Missiles, MISSILE.AMMO)
	player:SetAttribute(ATTR.RocketReloadEndsAt, 0)
	player:SetAttribute(ATTR.MissileReloadEndsAt, 0)
end

local function onFire(player: Player, weapon: any, a: any, b: any, c: any)
	if weapon == "Lock" then
		noteLock(player, a)
		return
	end
	if not hooks.canFire() or not validDirection(a) then
		return
	end
	local dir = (a :: Vector3).Unit
	if weapon == "MG" then
		fireMachineGun(player, dir)
	elseif weapon == "Rocket" then
		fireRocket(player, dir, b)
	elseif weapon == "Missile" then
		fireMissile(player, dir, b, c)
	end
end

function Weapons.init(h: Hooks)
	hooks = h
	gameEvent = ReplicatedStorage.Remotes.GameEvent :: RemoteEvent
	Projectiles.init({
		hit = function(player, enemy, killed, position)
			hooks.onHit(player, enemy, killed, position, false)
		end,
		worldHit = worldHit,
	})
	local remote = ReplicatedStorage.Remotes.FireWeapon :: RemoteEvent
	remote.OnServerEvent:Connect(onFire)
	Players.PlayerAdded:Connect(restock)
	for _, player in Players:GetPlayers() do
		restock(player)
	end
	Players.PlayerRemoving:Connect(function(player)
		states[player] = nil
		locks[player] = nil
	end)
end

-- Full restock, heat reset and in-flight projectiles cleared. Called at every
-- intermission, new run and retry.
function Weapons.resetAll()
	table.clear(states)
	table.clear(locks)
	Projectiles.clear()
	for _, player in Players:GetPlayers() do
		restock(player)
	end
end

-- Adds ammo from a supply crate to every player (single player game),
-- capped at the weapon's MAX_AMMO. Returns the new count of the first player.
function Weapons.addAmmo(kind: string, amount: number): number
	local attr = if kind == "Rockets" then ATTR.Rockets elseif kind == "Missiles" then ATTR.Missiles else nil
	if not attr or type(amount) ~= "number" then
		warn("[RedMesa] Weapons.addAmmo: bad args " .. tostring(kind) .. " " .. tostring(amount))
		return 0
	end
	local cap = if kind == "Rockets" then ROCKET.MAX_AMMO else MISSILE.MAX_AMMO
	local result = 0
	for i, player in Players:GetPlayers() do
		local current = player:GetAttribute(attr)
		local new = math.clamp((if typeof(current) == "number" then current else 0) + math.floor(amount), 0, cap)
		player:SetAttribute(attr, new)
		if i == 1 then
			result = new
		end
	end
	return result
end

return Weapons
