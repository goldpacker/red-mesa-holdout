--!strict
-- AA missile lock-on. While the missile rack is selected, the aircraft
-- closest to the crosshair (within ACQUIRE_DEG, in range) is tracked;
-- keeping it there for LOCK_TIME locks it. Ground targets are never
-- considered (model attribute IsAir must be true). The server is told which
-- target is being acquired so it can validate the eventual missile shot.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Aim = require(ReplicatedStorage.Shared.Aim)
local WeaponConfig = require(ReplicatedStorage.Shared.WeaponConfig)
local AimController = require(script.Parent.AimController)
local Sfx = require(script.Parent.Sfx)

local LockOn = {}

export type State = "Idle" | "Acquiring" | "Locked"

local M = WeaponConfig.Missile
local TONE_SLOW, TONE_FAST = 0.3, 0.08

local fireRemote = ReplicatedStorage:WaitForChild("Remotes"):WaitForChild("FireWeapon") :: RemoteEvent
local state: State = "Idle"
local target: Model? = nil
local progress = 0
local nextTone = 0
local reported: number? = nil

local function report(id: number?)
	if reported ~= id then
		reported = id
		fireRemote:FireServer("Lock", id)
	end
end

local function rootOf(model: Model): BasePart?
	if not model.Parent or model:GetAttribute("State") == "Dead" or model:GetAttribute("IsAir") ~= true then
		return nil
	end
	return model.PrimaryPart
end

-- Angle (degrees) between the aim line and the target, or nil if the
-- target is invalid or out of range.
local function angleTo(model: Model, eye: Vector3, look: Vector3): number?
	local root = rootOf(model)
	if not root then
		return nil
	end
	local offset = root.Position - eye
	local dist = offset.Magnitude
	if dist > M.LOCK_RANGE or dist < 1 then
		return nil
	end
	return math.deg(math.acos(math.clamp(offset.Unit:Dot(look), -1, 1)))
end

local function bestCandidate(eye: Vector3, look: Vector3): Model?
	local folder = Workspace:FindFirstChild("Enemies")
	if not folder then
		return nil
	end
	local best: Model? = nil
	local bestAngle = M.ACQUIRE_DEG
	for _, m in folder:GetChildren() do
		if m:IsA("Model") and m:GetAttribute("IsAir") == true then
			local angle = angleTo(m, eye, look)
			if angle and angle <= bestAngle then
				best, bestAngle = m, angle
			end
		end
	end
	return best
end

local function setIdle()
	state = "Idle"
	target = nil
	progress = 0
end

function LockOn.reset()
	setIdle()
	report(nil)
end

local function tone(now: number)
	if now >= nextTone then
		Sfx.play("LockTone")
		nextTone = now + TONE_SLOW + (TONE_FAST - TONE_SLOW) * progress
	end
end

-- `active` = missiles selected and the player is in control.
function LockOn.update(dt: number, active: boolean)
	if not active then
		if state ~= "Idle" or reported then
			LockOn.reset()
		end
		return
	end
	local yaw, pitch = AimController.getAngles()
	local look = Aim.direction(yaw, pitch)
	local eye = Workspace.CurrentCamera.CFrame.Position
	local now = os.clock()

	local angle = if target then angleTo(target, eye, look) else nil
	if target and not angle then
		setIdle()
	end

	if state == "Locked" then
		if not angle or angle > M.BREAK_DEG then
			setIdle()
		end
	elseif state == "Acquiring" then
		if angle and angle <= M.ACQUIRE_DEG * 1.3 then
			progress = math.min(1, progress + dt / M.LOCK_TIME)
			tone(now)
			if progress >= 1 then
				state = "Locked"
				Sfx.play("LockAcquired")
			end
		else
			progress -= M.LOCK_DECAY * dt
			if progress <= 0 then
				setIdle()
			end
		end
	end

	if state == "Idle" then
		local candidate = bestCandidate(eye, look)
		if candidate then
			state = "Acquiring"
			target = candidate
			progress = 0
			nextTone = now
		end
	end
	local id = target and target:GetAttribute("EnemyId")
	report(if type(id) == "number" then id else nil)
end

function LockOn.getState(): (State, Model?, number)
	return state, target, progress
end

-- EnemyId of the locked target, or nil.
function LockOn.lockedId(): number?
	if state ~= "Locked" or not target then
		return nil
	end
	local id = target:GetAttribute("EnemyId")
	return if type(id) == "number" then id else nil
end

function LockOn.lockedModel(): Model?
	return if state == "Locked" then target else nil
end

-- Clears the lock after a missile leaves (the next shot needs a new lock).
-- The server drops its lock record on launch, so re-report next frame.
function LockOn.consume()
	setIdle()
	reported = nil
end

return LockOn
