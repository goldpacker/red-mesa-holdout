--!strict
-- Client weapon handling: selection (1/2/3, mouse wheel), predicted machine
-- gun heat/overheat, rocket and missile fire requests (ammo and reload are
-- server-owned player attributes), lock-on, and the local fire effects.
-- Every shot is sent to the server for authority.
--
-- Listener events (WeaponController.on): "Shot", "Overheat", "Cooled",
-- "Switched" (weapon), "Fired" (weapon), "Empty" (weapon), "NoLock",
-- "Reloaded" (weapon), "Hold" (weapon; heavy weapons outside combat).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local WeaponConfig = require(ReplicatedStorage.Shared.WeaponConfig)
local AimController = require(script.Parent.AimController)
local Effects = require(script.Parent.Effects)
local GameState = require(script.Parent.GameState)
local LockOn = require(script.Parent.LockOn)
local Sfx = require(script.Parent.Sfx)
local TurretPose = require(script.Parent.WeaponFxTurret)
local WeaponFx = require(script.Parent.WeaponFx)

local WeaponController = {}

local MG = Config.MachineGun
local ATTR = WeaponConfig.Attr
local SLOTS = WeaponConfig.SLOTS
local player = Players.LocalPlayer
local fireRemote = ReplicatedStorage:WaitForChild("Remotes"):WaitForChild("FireWeapon") :: RemoteEvent

local heat = 0
local lastShot = -math.huge
local lockedUntil = 0

local current = "MG"
local switchedAt = -math.huge
local triggerWasHeld = false
local nextToken = 0
-- Guards against double sends before the server's reload attribute lands.
local localReady: { [string]: number } = { Rocket = 0, Missile = 0 }
local wasReloading: { [string]: boolean } = { Rocket = false, Missile = false }

local HEAVY = {
	Rocket = { ammo = ATTR.Rockets, reload = ATTR.RocketReloadEndsAt, time = WeaponConfig.Rocket.RELOAD, sound = "RocketLaunch" },
	Missile = { ammo = ATTR.Missiles, reload = ATTR.MissileReloadEndsAt, time = WeaponConfig.Missile.RELOAD, sound = "MissileLaunch" },
}

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

function WeaponController.getWeapon(): string
	return current
end

-- 0..1 progress of the current weapon swap (1 = ready).
function WeaponController.getSwitchProgress(): number
	return math.clamp((os.clock() - switchedAt) / WeaponConfig.SWITCH_TIME, 0, 1)
end

-- Ammo for "Rocket" / "Missile" from the server attributes.
function WeaponController.getAmmo(weapon: string): number
	local def = HEAVY[weapon]
	local n = def and player:GetAttribute(def.ammo)
	return if typeof(n) == "number" then n else 0
end

-- Fraction of the reload still remaining (0 = ready).
function WeaponController.getReload(weapon: string): number
	local def = HEAVY[weapon]
	if not def then
		return 0
	end
	local endsAt = player:GetAttribute(def.reload)
	local serverEnds = if typeof(endsAt) == "number" then endsAt else 0
	local remaining = math.max(serverEnds, localReady[weapon]) - Workspace:GetServerTimeNow()
	return math.clamp(remaining / def.time, 0, 1)
end

function WeaponController.reset()
	heat = 0
	lockedUntil = 0
	lastShot = -math.huge
	localReady.Rocket = 0
	localReady.Missile = 0
	LockOn.reset()
end

function WeaponController.select(weapon: string)
	if weapon == current or not HEAVY[weapon] and weapon ~= "MG" then
		return
	end
	current = weapon
	switchedAt = os.clock()
	TurretPose.setActive(weapon)
	Sfx.play("WeaponSwitch")
	emit("Switched", weapon)
end

local function cycle(delta: number)
	local index = table.find(SLOTS, current) or 1
	index = (index - 1 + delta) % #SLOTS + 1
	WeaponController.select(SLOTS[index])
end

local function triggerHeld(): boolean
	if UserInputService:IsMouseButtonPressed(Enum.UserInputType.MouseButton1) then
		return true
	end
	return RunService:IsStudio() and player:GetAttribute("DebugFire") == true
end

local function fireMachineGun()
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

local function heavyAllowed(): boolean
	local phase = GameState.phase()
	return phase == "Wave" or phase == "WaveIntro"
end

-- Tries to fire a rocket or missile; gives feedback when it can't.
local function fireHeavy(weapon: string)
	local def = HEAVY[weapon]
	if not heavyAllowed() then
		emit("Hold", weapon)
		return
	end
	if WeaponController.getReload(weapon) > 0 then
		return
	end
	if WeaponController.getAmmo(weapon) <= 0 then
		Sfx.play("Empty")
		emit("Empty", weapon)
		return
	end
	local targetModel: Model? = nil
	local targetId: number? = nil
	if weapon == "Missile" then
		targetId = LockOn.lockedId()
		targetModel = LockOn.lockedModel()
		if not targetId then
			Sfx.play("Empty")
			emit("NoLock", nil)
			return
		end
	end

	local _, dir = AimController.getAimTarget()
	local origin = Config.TURRET_PIVOT + dir * Config.MUZZLE_OFFSET
	nextToken += 1
	fireRemote:FireServer(weapon, dir, nextToken, targetId)
	localReady[weapon] = Workspace:GetServerTimeNow() + def.time
	wasReloading[weapon] = true

	local visualOrigin = TurretPose.muzzle(weapon) or AimController.getMuzzlePosition()
	WeaponFx.predict(weapon, nextToken, origin, visualOrigin, dir, targetModel)
	if weapon == "Missile" then
		LockOn.consume()
	end
	AimController.kick(1)
	AimController.shake(if weapon == "Rocket" then 0.22 else 0.14)
	Sfx.play(def.sound)
	emit("Fired", weapon)
end

local function stepMachineGun(dt: number, canShoot: boolean, held: boolean)
	local now = os.clock()
	if now >= lockedUntil and lockedUntil > 0 then
		lockedUntil = 0
		heat = 0
		emit("Cooled", nil)
	end
	local firing = canShoot and current == "MG" and held and lockedUntil == 0
	if firing then
		if now - lastShot >= MG.FIRE_INTERVAL then
			fireMachineGun()
		end
	elseif lockedUntil == 0 and now - lastShot > MG.COOL_DELAY then
		heat = math.max(0, heat - MG.COOL_RATE * dt)
	end
	if lockedUntil > 0 then
		heat = MG.MAX_HEAT * WeaponController.getLockRemaining()
	end
end

-- Plays the reload-complete cue once per reload.
local function stepReloads()
	for weapon in HEAVY do
		local reloading = WeaponController.getReload(weapon) > 0
		if wasReloading[weapon] and not reloading then
			if WeaponController.getAmmo(weapon) > 0 then
				Sfx.play("Reload")
				emit("Reloaded", weapon)
			end
		end
		wasReloading[weapon] = reloading
	end
	local missileReady = WeaponController.getAmmo("Missile") > 0 and WeaponController.getReload("Missile") <= 0
	TurretPose.setMissileLoaded(missileReady)
end

local function step(dt: number)
	local inTurret = AimController.getMode() == "Turret"
	local canShoot = inTurret and GameState.isCombat() and WeaponController.getSwitchProgress() >= 1
	local held = triggerHeld()
	local pressed = held and not triggerWasHeld
	triggerWasHeld = held

	stepMachineGun(dt, canShoot, held)
	LockOn.update(dt, inTurret and current == "Missile" and GameState.isCombat())
	if canShoot and pressed and current ~= "MG" then
		fireHeavy(current)
	end
	stepReloads()
end

local KEY_SLOTS = {
	[Enum.KeyCode.One] = 1,
	[Enum.KeyCode.Two] = 2,
	[Enum.KeyCode.Three] = 3,
	[Enum.KeyCode.KeypadOne] = 1,
	[Enum.KeyCode.KeypadTwo] = 2,
	[Enum.KeyCode.KeypadThree] = 3,
}

local function connectInput()
	UserInputService.InputBegan:Connect(function(input, processed)
		if processed then
			return
		end
		local slot = KEY_SLOTS[input.KeyCode]
		if slot then
			WeaponController.select(SLOTS[slot])
		end
	end)
	UserInputService.InputChanged:Connect(function(input, processed)
		if processed or input.UserInputType ~= Enum.UserInputType.MouseWheel then
			return
		end
		if AimController.getMode() ~= "Turret" then
			return
		end
		if input.Position.Z > 0 then
			cycle(-1)
		elseif input.Position.Z < 0 then
			cycle(1)
		end
	end)
	-- Studio QA hook: DebugWeapon = 1/2/3 or "MG"/"Rocket"/"Missile".
	player:GetAttributeChangedSignal("DebugWeapon"):Connect(function()
		if not RunService:IsStudio() then
			return
		end
		local value = player:GetAttribute("DebugWeapon")
		local weapon = if type(value) == "number" then SLOTS[value] else value
		if type(weapon) == "string" then
			WeaponController.select(weapon)
		end
	end)
end

function WeaponController.start()
	TurretPose.start()
	WeaponFx.start()
	connectInput()
	RunService:BindToRenderStep("RedMesaWeapons", Enum.RenderPriority.Camera.Value + 4, step)
	GameState.onChanged("Phase", function(phase)
		if phase == "Intermission" or phase == "Title" or phase == "WaveIntro" then
			WeaponController.reset()
		end
	end)
end

return WeaponController
