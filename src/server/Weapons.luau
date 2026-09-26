--!strict
-- Server-authoritative weapon fire. The client sends a unit direction from
-- the muzzle; the server validates rate, heat and aim limits, raycasts and
-- applies damage.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Enemies = require(script.Parent.Enemies)
local Types = require(script.Parent.Types)

export type Hooks = {
	canFire: () -> boolean,
	onShot: (player: Player) -> (),
	onHit: (player: Player, enemy: Types.Enemy, killed: boolean, position: Vector3, headshot: boolean) -> (),
}

type GunState = {
	heat: number,
	lastShot: number,
	lockedUntil: number,
}

local Weapons = {}

local MG = Config.MachineGun
-- Client and server simulate heat independently; allow a little slack so
-- network jitter never rejects a shot the client legitimately fired.
local HEAT_TOLERANCE = 1.15
local RATE_TOLERANCE = 0.6

local states: { [Player]: GunState } = {}
local hooks: Hooks

local rayParams = RaycastParams.new()
rayParams.FilterType = Enum.RaycastFilterType.Exclude

local function stateFor(player: Player): GunState
	local s = states[player]
	if not s then
		s = { heat = 0, lastShot = -math.huge, lockedUntil = 0 }
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

	local origin = Config.TURRET_PIVOT + dir * Config.MUZZLE_OFFSET
	rayParams.FilterDescendantsInstances = { Workspace.Battlefield.Emplacement, Workspace.Projectiles }
	local result = Workspace:Raycast(origin, dir * MG.RANGE, rayParams)
	if not result then
		return
	end
	local enemy = Enemies.fromPart(result.Instance)
	if not enemy then
		return
	end
	local headshot = result.Instance.Name == "Head"
	local damage = MG.DAMAGE * (if headshot then MG.HEADSHOT_MULTIPLIER else 1)
	local killed = Enemies.damage(enemy, damage, "MG", result.Instance :: BasePart)
	hooks.onHit(player, enemy, killed, result.Position, headshot)
end

function Weapons.init(h: Hooks)
	hooks = h
	local remote = ReplicatedStorage.Remotes.FireWeapon :: RemoteEvent
	remote.OnServerEvent:Connect(function(player: Player, weapon: any, dir: any)
		if not hooks.canFire() or weapon ~= "MG" or not validDirection(dir) then
			return
		end
		fireMachineGun(player, (dir :: Vector3).Unit)
	end)
	game:GetService("Players").PlayerRemoving:Connect(function(player)
		states[player] = nil
	end)
end

function Weapons.resetAll()
	table.clear(states)
end

return Weapons
