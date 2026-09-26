--!strict
-- Client weapon handling: input, predicted heat/overheat, and the local
-- fire effects. Each shot's direction is sent to the server for authority.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local AimController = require(script.Parent.AimController)
local Effects = require(script.Parent.Effects)
local GameState = require(script.Parent.GameState)
local Sfx = require(script.Parent.Sfx)

local WeaponController = {}

local MG = Config.MachineGun
local player = Players.LocalPlayer
local fireRemote = ReplicatedStorage:WaitForChild("Remotes"):WaitForChild("FireWeapon") :: RemoteEvent

local heat = 0
local lastShot = -math.huge
local lockedUntil = 0

local effectParams = RaycastParams.new()
effectParams.FilterType = Enum.RaycastFilterType.Exclude

local listeners: { [string]: { (any) -> () } } = {}

local function emit(kind: string, payload: any)
	for _, fn in listeners[kind] or {} do
		task.spawn(fn, payload)
	end
end

function WeaponController.on(kind: string, fn: (any) -> ())
	listeners[kind] = listeners[kind] or {}
	table.insert(listeners[kind], fn)
end

function WeaponController.getHeat(): number
	return heat / MG.MAX_HEAT
end

-- 0 when usable; otherwise fraction of the overheat lock remaining.
function WeaponController.getLockRemaining(): number
	local remaining = lockedUntil - os.clock()
	if remaining <= 0 then
		return 0
	end
	return remaining / MG.OVERHEAT_LOCK
end

function WeaponController.reset()
	heat = 0
	lockedUntil = 0
	lastShot = -math.huge
end

local function triggerHeld(): boolean
	if UserInputService:IsMouseButtonPressed(Enum.UserInputType.MouseButton1) then
		return true
	end
	return RunService:IsStudio() and player:GetAttribute("DebugFire") == true
end

local function fireOnce()
	local now = os.clock()
	heat += MG.HEAT_PER_SHOT
	lastShot = now
	if heat >= MG.MAX_HEAT then
		heat = MG.MAX_HEAT
		lockedUntil = now + MG.OVERHEAT_LOCK
		emit("Overheat", nil)
		Sfx.play("Overheat")
	end

	local target, dir = AimController.getAimTarget()
	local spread = math.rad(MG.SPREAD_DEG)
	dir = (CFrame.lookAt(Vector3.zero, dir) * CFrame.Angles((math.random() - 0.5) * spread, (math.random() - 0.5) * spread, 0)).LookVector
	fireRemote:FireServer("MG", dir)

	local muzzle = AimController.getMuzzlePosition()
	local origin = Config.TURRET_PIVOT + dir * Config.MUZZLE_OFFSET
	effectParams.FilterDescendantsInstances = { Workspace.Battlefield.Emplacement, Workspace.Projectiles }
	local result = Workspace:Raycast(origin, dir * MG.RANGE, effectParams)
	local hitPos = if result then result.Position else origin + dir * MG.RANGE
	local hitEnemy = result ~= nil and result.Instance:FindFirstAncestor("Enemies") ~= nil

	Effects.muzzleFlash(muzzle, dir)
	Effects.tracer(muzzle, hitPos)
	if result then
		Effects.impact(hitPos, hitEnemy)
	end
	AimController.kick(0.5)
	AimController.shake(0.04)
	Sfx.play("MachineGun")
	emit("Shot", target)
end

local function step(dt: number)
	local now = os.clock()
	local canShoot = AimController.getMode() == "Turret" and GameState.isCombat()

	if now >= lockedUntil and lockedUntil > 0 then
		lockedUntil = 0
		heat = 0
		emit("Cooled", nil)
	end

	if canShoot and triggerHeld() and lockedUntil == 0 then
		if now - lastShot >= MG.FIRE_INTERVAL then
			fireOnce()
		end
	else
		if lockedUntil == 0 and now - lastShot > MG.COOL_DELAY then
			heat = math.max(0, heat - MG.COOL_RATE * dt)
		end
	end
	if lockedUntil > 0 then
		heat = MG.MAX_HEAT * WeaponController.getLockRemaining()
	end
end

function WeaponController.start()
	RunService.RenderStepped:Connect(step)
	GameState.onChanged("Phase", function(phase)
		if phase == "Intermission" or phase == "Title" then
			WeaponController.reset()
		end
	end)
end

return WeaponController
