--!strict
-- Owns the turret aim (yaw/pitch), the camera and the visible turret model.
-- Modes: "Title" (slow pan), "Turret" (player control), "Defeat" (pull back).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Aim = require(ReplicatedStorage.Shared.Aim)

local AimController = {}

local camera = Workspace.CurrentCamera
local player = Players.LocalPlayer
local CAM = Config.Camera

local mode = "Title"
local modeStarted = os.clock()
local yaw, pitch = 0, -4
local visualYaw, visualPitch = 0, -4
local aiming = false
local trauma = 0
local recoil = 0
local fovCurrent = CAM.FOV_DEFAULT

local emplacement: Instance? = nil
local turretYaw: Model? = nil
local turretGun: Model? = nil

local aimParams = RaycastParams.new()
aimParams.FilterType = Enum.RaycastFilterType.Exclude

local function findTurret()
	if turretGun and turretGun.Parent then
		return
	end
	local battlefield = Workspace:FindFirstChild("Battlefield")
	emplacement = battlefield and battlefield:FindFirstChild("Emplacement")
	if emplacement then
		turretYaw = emplacement:FindFirstChild("TurretYaw") :: Model?
		turretGun = emplacement:FindFirstChild("TurretGun") :: Model?
		aimParams.FilterDescendantsInstances = { emplacement, Workspace:FindFirstChild("Projectiles") :: Instance }
	end
end

-- In the gunsight view the whole emplacement is hidden so sandbags don't
-- block steep downward shots (they never block the actual raycast).
local function setTurretHidden(hidden: boolean)
	local static = emplacement and emplacement:FindFirstChild("Static")
	for _, model in { turretGun, turretYaw, static } do
		if model then
			for _, part in model:GetDescendants() do
				if part:IsA("BasePart") then
					part.LocalTransparencyModifier = if hidden then 1 else 0
				end
			end
		end
	end
end

function AimController.setMode(newMode: string)
	if mode == newMode then
		return
	end
	mode = newMode
	modeStarted = os.clock()
	if newMode == "Turret" then
		yaw, pitch = 0, -4
	end
	if newMode ~= "Turret" then
		aiming = false
		setTurretHidden(false)
	end
end

function AimController.getMode(): string
	return mode
end

function AimController.isAiming(): boolean
	return aiming
end

function AimController.getAngles(): (number, number)
	return yaw, pitch
end

-- Adds camera shake. `amount` 0..1, decays over time.
function AimController.shake(amount: number)
	trauma = math.min(1, trauma + amount)
end

function AimController.kick(amount: number)
	recoil = math.min(1, recoil + amount)
end

-- Where the crosshair points in the world, and the muzzle direction that
-- converges on it (the direction sent to the server).
function AimController.getAimTarget(): (Vector3, Vector3)
	local look = Aim.direction(yaw, pitch)
	local camPos = camera.CFrame.Position
	local result = Workspace:Raycast(camPos, look * Config.MachineGun.RANGE, aimParams)
	local target = if result then result.Position else camPos + look * Config.MachineGun.RANGE
	local origin = Config.TURRET_PIVOT + look * Config.MUZZLE_OFFSET
	local dir = (target - origin).Unit
	return target, dir
end

function AimController.getMuzzlePosition(): Vector3
	local muzzle = turretGun and turretGun:FindFirstChild("Muzzle") :: BasePart?
	if muzzle then
		return muzzle.Position
	end
	return Aim.muzzle(yaw, pitch)
end

local function readInput()
	local delta = UserInputService:GetMouseDelta()
	local sens = if aiming then CAM.SENSITIVITY_AIM else CAM.SENSITIVITY
	yaw -= delta.X * sens
	pitch -= delta.Y * sens

	if RunService:IsStudio() then
		local dy = player:GetAttribute("DebugYaw")
		local dp = player:GetAttribute("DebugPitch")
		if typeof(dy) == "number" then
			yaw = dy
		end
		if typeof(dp) == "number" then
			pitch = dp
		end
	end
	yaw, pitch = Aim.clampAngles(yaw, pitch)
	aiming = UserInputService:IsMouseButtonPressed(Enum.UserInputType.MouseButton2)
		or player:GetAttribute("DebugAiming") == true
end

local function shakeOffset(dt: number): CFrame
	trauma = math.max(0, trauma - dt * 1.6)
	if trauma <= 0 then
		return CFrame.identity
	end
	local s = trauma * trauma
	local t = os.clock() * 30
	return CFrame.Angles(
		math.rad((math.noise(t, 1) * 2) * s * 2.5),
		math.rad((math.noise(t, 2) * 2) * s * 2.5),
		math.rad((math.noise(t, 3) * 2) * s * 1.5)
	)
end

local function updateTurret(dt: number)
	findTurret()
	local alpha = 1 - math.exp(-dt * 22)
	visualYaw += (yaw - visualYaw) * alpha
	visualPitch += (pitch - visualPitch) * alpha
	recoil = math.max(0, recoil - dt * 9)
	local kickBack = CFrame.new(0, 0, recoil * 0.35)
	if turretYaw then
		turretYaw:PivotTo(Aim.cframe(visualYaw, 0))
	end
	if turretGun then
		turretGun:PivotTo(Aim.cframe(visualYaw, visualPitch) * kickBack)
	end
end

local function turretCamera(dt: number)
	readInput()
	updateTurret(dt)
	UserInputService.MouseBehavior = Enum.MouseBehavior.LockCenter
	UserInputService.MouseIconEnabled = false

	local look = Aim.direction(yaw, pitch)
	local pos: Vector3
	if aiming then
		pos = Config.TURRET_PIVOT + look * 1.5 + Vector3.new(0, 0.9, 0)
	else
		-- Orbit behind the gun: when aiming down the camera rises so the turret
		-- stays below the crosshair; when aiming up it stays level.
		local flat = Vector3.new(look.X, 0, look.Z).Unit
		local back = if look.Y < 0 then look else flat
		pos = Config.TURRET_PIVOT - back * CAM.THIRD_PERSON_BACK + Vector3.new(0, CAM.THIRD_PERSON_UP, 0)
	end
	setTurretHidden(aiming)
	local targetFov = if aiming then CAM.FOV_AIM else CAM.FOV_DEFAULT
	fovCurrent += (targetFov - fovCurrent) * (1 - math.exp(-dt * 14))
	camera.FieldOfView = fovCurrent
	camera.CFrame = CFrame.lookAt(pos, pos + look) * shakeOffset(dt)
end

local function titleCamera(_dt: number)
	UserInputService.MouseBehavior = Enum.MouseBehavior.Default
	UserInputService.MouseIconEnabled = true
	updateTurret(0.016)
	local t = os.clock() - modeStarted
	-- High behind the mesa, drifting slowly so the basin reads as a panorama.
	-- Eye moved ~30 studs along the view (LOOK-2) so the whole pan clears
	-- ENV-2's rear-wall mesh; keep BeautyShots.SHOTS[1].camera in step.
	local pos = Vector3.new(-62 + math.sin(t * 0.04) * 45, 122, 122)
	camera.FieldOfView = 60
	camera.CFrame = CFrame.lookAt(pos, Vector3.new(90 + math.sin(t * 0.04) * 30, 0, -420))
end

local function defeatCamera(dt: number)
	UserInputService.MouseBehavior = Enum.MouseBehavior.Default
	UserInputService.MouseIconEnabled = true
	local t = math.min(1, (os.clock() - modeStarted) / 6)
	local eased = 1 - (1 - t) ^ 3
	-- Swing out over the basin and look back at the burning emplacement.
	local pos = Config.TURRET_PIVOT + Vector3.new(20 + 40 * eased, 10 + 45 * eased, -30 - 110 * eased)
	camera.FieldOfView = 60
	camera.CFrame = CFrame.lookAt(pos, Config.TURRET_PIVOT) * shakeOffset(dt)
end

-- Victory: rise off the mesa and drift out over the basin, looking down
-- the road toward the burning Siege Crawler and the flare volley.
local function victoryCamera(_dt: number)
	UserInputService.MouseBehavior = Enum.MouseBehavior.Default
	UserInputService.MouseIconEnabled = true
	local t = math.min(1, (os.clock() - modeStarted) / 8)
	local eased = 1 - (1 - t) ^ 3
	local drift = (os.clock() - modeStarted) * 0.03
	local pos = Config.TURRET_PIVOT + Vector3.new(math.sin(drift) * 60, 20 + 60 * eased, 30 - 90 * eased)
	camera.FieldOfView = 60
	camera.CFrame = CFrame.lookAt(pos, Vector3.new(0, 10, -360))
end

function AimController.start()
	camera.CameraType = Enum.CameraType.Scriptable
	RunService:BindToRenderStep("RedMesaCamera", Enum.RenderPriority.Camera.Value + 1, function(dt)
		camera.CameraType = Enum.CameraType.Scriptable
		if mode == "Turret" then
			turretCamera(dt)
		elseif mode == "Defeat" then
			defeatCamera(dt)
		elseif mode == "Victory" then
			victoryCamera(dt)
		else
			titleCamera(dt)
		end
	end)
end

return AimController
