--!strict
-- Owns the turret aim (yaw/pitch), the camera and the visible turret model.
-- Modes: "Title" (slow pan), "Turret" (player control), "Defeat" (pull back).
--
-- Motion (LOOK-3). The player's aim (yaw/pitch) is offset only by recoil;
-- everything else is on the drawn turret or a centre-preserving camera move:
--   - aim recoil (playtest round 2, "the aim should shake a little"): each
--     MG round kicks the aim up and to a random side, and a stiff spring
--     pulls it back. The camera's view direction and the ray the shot
--     follows both use the recoiled aim (aimAngles), so the view shakes but
--     the reticle still shows exactly where each round goes;
--   - turret model: a sprung look-lag (slight overshoot), a cant while it
--     slews, an idle sway once the gun is left alone, and a per-weapon kick
--     (recoil back, muzzle climb, twist);
--   - camera: a per-weapon shove back along the view axis, a roll and an
--     FOV punch, and a slow idle roll in the gunsight. Moving along the
--     view axis, rolling about it and zooming all keep the screen centre on
--     the same world ray, so the reticle stays exactly where the shot goes.
--
-- Input path (PERF-1, measured): the mouse delta is polled in the camera
-- step (RenderPriority.Camera + 1, after input processing) and the camera
-- CFrame is written in the same step, so the view follows the mouse in the
-- frame the delta arrives, with no smoothing. The sprung turret never feeds
-- the camera or the aim; in the gunsight the muzzle effects start from the
-- aim, not from the hidden, lagging barrel (toAimFrame).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")
local FrameProfile = require(script.Parent.FrameProfile)

local Config = require(ReplicatedStorage.Shared.Config)
local Aim = require(ReplicatedStorage.Shared.Aim)

local AimController = {}

local camera = Workspace.CurrentCamera
local player = Players.LocalPlayer
local CAM = Config.Camera

local mode = "Title"
local modeStarted = os.clock()
local yaw, pitch = 0, -4
local aiming = false
local trauma = 0
local fovCurrent = CAM.FOV_DEFAULT

-- Damped springs for the drawn turret and the camera kick (LOOK-3).
type Spring = { x: number, v: number, w: number, z: number }
local function spring(hz: number, damping: number, x: number?): Spring
	return { x = x or 0, v = 0, w = 2 * math.pi * hz, z = damping }
end
local function stepSpring(s: Spring, target: number, dt: number)
	local n = math.max(1, math.ceil(dt / (1 / 120)))
	local h = dt / n
	for _ = 1, n do
		s.v += (s.w * s.w * (target - s.x) - 2 * s.z * s.w * s.v) * h
		s.x += s.v * h
	end
end

-- Turret look-lag. PERF-1 (playtest: "mouse feels laggy"): 8 Hz, damping
-- 0.75 (was 4 Hz / 0.72). The drawn gun settles on a flick in ~7 frames
-- instead of ~15 and trails a 60 deg/s slew by ~1.3 deg instead of ~2.7, with
-- a hint of overshoot left; the camera and the aim never wait for it.
local lagYaw, lagPitch = spring(8, 0.75), spring(8, 0.75, -4)
local gunBack, gunClimb, gunTwist = spring(5, 0.6), spring(3.5, 0.45), spring(3, 0.5)
local camShove, camRoll, fovPunch = spring(4, 0.55), spring(3, 0.5), spring(3, 0.7)
-- Aim recoil (degrees). 7 Hz, damping 0.5: a round's kick is mostly gone
-- before the next (~11 rounds/s), so a burst shakes the aim by about its
-- per-round kick while the mean climb stays ~0.05 deg, well inside the
-- server's 0.5 deg MG spread.
local recoilYaw, recoilPitch = spring(7, 0.5), spring(7, 0.5)
-- A kick lands after this frame's camera step (WeaponController fires at
-- Camera+4), so the next camera step shows it at full size before the
-- spring starts pulling it back; otherwise a slow frame (15-30 fps) eats
-- most of it before it is ever drawn.
local recoilFresh = false
local idle = 0
local lastActive = os.clock()

-- Per-weapon kick: gun recoil (studs), muzzle climb and twist (degrees),
-- camera shove back along the view (studs), camera roll (degrees), FOV
-- punch (degrees), aim recoil up and to a random side (degrees, capped at
-- AIM_KICK_MAX). `nominal` is the amount WeaponController passes.
type Kick = {
	nominal: number,
	back: number,
	climb: number,
	twist: number,
	shove: number,
	roll: number,
	fov: number,
	aimUp: number,
	aimSide: number,
}
local KICK: { [string]: Kick } = {
	MG = { nominal = 0.5, back = 0.2, climb = 0.45, twist = 0.2, shove = 0.03, roll = 0.08, fov = 0, aimUp = 0.18, aimSide = 0.1 },
	-- Rockets and missiles: no aim recoil (one launch, then a reload; their
	-- camera kick already sells it, and an AA lock must not be jolted).
	Rocket = { nominal = 1, back = 0.75, climb = 3.2, twist = 1.4, shove = 0.4, roll = 0.9, fov = 2.4, aimUp = 0, aimSide = 0 },
	Missile = { nominal = 1, back = 0.45, climb = 1.6, twist = 0.7, shove = 0.22, roll = 0.5, fov = 1.3, aimUp = 0, aimSide = 0 },
}
local AIM_KICK_MAX = 0.5
-- Turret cant while slewing (degrees per degree/s of lag velocity), idle
-- sway (degrees) and the gunsight's idle roll (degrees).
local CANT = 0.011
local SWAY_YAW, SWAY_PITCH, SWAY_ROLL = 0.35, 0.25, 0.12
local IDLE_AFTER = 0.8 -- s without input or fire before the sway fades in

local emplacement: Instance? = nil
local turretYaw: Model? = nil
local turretGun: Model? = nil
-- Where the drawn gun is this frame (lagged, swayed, kicked) and where an
-- un-lagged gun would be (the aim). Effects that start at the muzzle map
-- through these in the gunsight (AimController.toAimFrame).
local drawnGunCf = CFrame.identity
local aimGunCf = CFrame.identity

local aimParams = RaycastParams.new()
aimParams.FilterType = Enum.RaycastFilterType.Exclude

-- In the gunsight view the whole emplacement is hidden so sandbags don't
-- block steep downward shots (they never block the actual raycast). The
-- parts are gathered once (and as they are added), and written only when
-- the state changes (PERF-1: this walked ~every emplacement descendant and
-- rewrote it every frame).
local hideParts: { [BasePart]: true } = {}
local hideConnections: { RBXScriptConnection } = {}
local hidden = false

local function watchHidden(model: Instance?)
	if not model then
		return
	end
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			hideParts[d] = true
			d.LocalTransparencyModifier = if hidden then 1 else 0
		end
	end
	table.insert(hideConnections, model.DescendantAdded:Connect(function(d)
		if d:IsA("BasePart") then
			hideParts[d] = true
			d.LocalTransparencyModifier = if hidden then 1 else 0
		end
	end))
	table.insert(hideConnections, model.DescendantRemoving:Connect(function(d)
		hideParts[d :: BasePart] = nil
	end))
end

local staticWatched = false

local function findTurret()
	if turretGun and turretGun.Parent then
		if not staticWatched and emplacement then
			local static = emplacement:FindFirstChild("Static")
			if static then
				staticWatched = true
				watchHidden(static)
			end
		end
		return
	end
	local battlefield = Workspace:FindFirstChild("Battlefield")
	emplacement = battlefield and battlefield:FindFirstChild("Emplacement")
	if emplacement then
		turretYaw = emplacement:FindFirstChild("TurretYaw") :: Model?
		turretGun = emplacement:FindFirstChild("TurretGun") :: Model?
		aimParams.FilterDescendantsInstances = { emplacement, Workspace:FindFirstChild("Projectiles") :: Instance }
		for _, connection in hideConnections do
			connection:Disconnect()
		end
		table.clear(hideConnections)
		table.clear(hideParts)
		staticWatched = false
		if turretGun then
			watchHidden(turretGun)
			watchHidden(turretYaw)
		end
	end
end

local function setTurretHidden(hide: boolean)
	if hide == hidden then
		return
	end
	hidden = hide
	for part in hideParts do
		part.LocalTransparencyModifier = if hide then 1 else 0
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
		recoilYaw.x, recoilYaw.v, recoilPitch.x, recoilPitch.v = 0, 0, 0, 0
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

-- The player's aim, without recoil (radar, airdrop HUD and lock-on read
-- this; they shouldn't jitter while the MG fires).
function AimController.getAngles(): (number, number)
	return yaw, pitch
end

-- The aim the camera looks along and the shot follows: the player's aim
-- plus the current recoil, kept inside the turret's arc.
local function aimAngles(): (number, number)
	return Aim.clampAngles(yaw + recoilYaw.x, pitch + recoilPitch.x)
end

-- Adds camera shake. `amount` 0..1, decays over time.
-- A shake that arrives with a fire kick (WeaponController calls kick, then
-- shake, for every shot) only rolls the view, so firing never pulls the
-- screen centre off the shot line; hits and explosions shake it fully.
local lastKick = -math.huge
local fireTrauma = 0
function AimController.shake(amount: number)
	if os.clock() - lastKick < 0.002 then
		fireTrauma = math.min(1, fireTrauma + amount)
		return
	end
	trauma = math.min(1, trauma + amount)
end

local weaponController: any = nil
local function currentWeapon(): string
	if weaponController == nil then
		-- Lazy: WeaponController requires this module.
		local ok, mod = pcall(require, script.Parent.WeaponController)
		weaponController = if ok then mod else false
	end
	local ok, weapon = pcall(function()
		return weaponController and weaponController.getWeapon()
	end)
	return if ok and type(weapon) == "string" then weapon else "MG"
end

-- Fire kick, scaled by the weapon that fired (WeaponController passes 0.5
-- for a machine-gun round, 1 for a rocket or missile).
function AimController.kick(amount: number)
	local k = KICK[currentWeapon()] or KICK.MG
	local scale = math.clamp(amount / k.nominal, 0, 2)
	local side = if math.random() < 0.5 then -1 else 1
	gunBack.x = math.min(gunBack.x + k.back * scale, k.back * 2.5)
	gunClimb.x += k.climb * scale * (0.8 + 0.4 * math.random())
	gunTwist.x += k.twist * scale * side
	camShove.x = math.min(camShove.x + k.shove * scale, math.max(k.shove * 2, 0.08))
	camRoll.x += k.roll * scale * side
	fovPunch.x += k.fov * scale
	if k.aimUp > 0 then
		local up = k.aimUp * scale * (0.8 + 0.4 * math.random())
		local across = k.aimSide * scale * (0.5 + 0.5 * math.random()) * (if math.random() < 0.5 then -1 else 1)
		recoilPitch.x = math.clamp(recoilPitch.x + up, -AIM_KICK_MAX, AIM_KICK_MAX)
		recoilYaw.x = math.clamp(recoilYaw.x + across, -AIM_KICK_MAX, AIM_KICK_MAX)
		recoilFresh = true
	end
	lastActive = os.clock()
	lastKick = os.clock()
end

-- Where the crosshair points in the world, and the muzzle direction that
-- converges on it (the direction sent to the server).
function AimController.getAimTarget(): (Vector3, Vector3)
	local look = Aim.direction(aimAngles())
	local camPos = camera.CFrame.Position
	local result = Workspace:Raycast(camPos, look * Config.MachineGun.RANGE, aimParams)
	local target = if result then result.Position else camPos + look * Config.MachineGun.RANGE
	local origin = Config.TURRET_PIVOT + look * Config.MUZZLE_OFFSET
	local dir = (target - origin).Unit
	return target, dir
end

-- Maps a point on the drawn gun (sprung look-lag, sway, kick) to the same
-- point on a gun held exactly on the aim, while the gunsight is up. The
-- drawn turret is hidden there, so tracers, flashes and launches must start
-- from where the sight looks, not from a barrel that trails the mouse
-- (PERF-1: up to ~50 px on screen after a quick flick). In the third-person
-- view effects stay on the visible barrel.
function AimController.toAimFrame(point: Vector3): Vector3
	if not aiming or mode ~= "Turret" then
		return point
	end
	return aimGunCf:PointToWorldSpace(drawnGunCf:PointToObjectSpace(point))
end

function AimController.getMuzzlePosition(): Vector3
	local muzzle = turretGun and turretGun:FindFirstChild("Muzzle") :: BasePart?
	if muzzle then
		return AimController.toAimFrame(muzzle.Position)
	end
	return Aim.muzzle(aimAngles())
end

local function readInput()
	local lastYaw, lastPitch = yaw, pitch
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
	if math.abs(yaw - lastYaw) + math.abs(pitch - lastPitch) > 0.01 then
		lastActive = os.clock()
	end
	aiming = UserInputService:IsMouseButtonPressed(Enum.UserInputType.MouseButton2)
		or player:GetAttribute("DebugAiming") == true
end

local function shakeOffset(dt: number): CFrame
	trauma = math.max(0, trauma - dt * 1.6)
	fireTrauma = math.max(0, fireTrauma - dt * 1.6)
	if trauma <= 0 and fireTrauma <= 0 then
		return CFrame.identity
	end
	local s = trauma * trauma
	local t = os.clock() * 30
	local roll = (math.noise(t, 3) * 2) * (s + fireTrauma * fireTrauma) * 1.5
	return CFrame.Angles(math.rad((math.noise(t, 1) * 2) * s * 2.5), math.rad((math.noise(t, 2) * 2) * s * 2.5), math.rad(roll))
end

local function noise(t: number, channel: number): number
	return math.clamp(math.noise(t, channel, 0.5) * 2, -1, 1)
end

-- The drawn turret: sprung look-lag, cant, idle sway and kick.
local function updateTurret(dt: number)
	findTurret()
	dt = math.clamp(dt, 0, 0.1)
	local now = os.clock()
	-- Beauty stills stay deterministic (tools/qa/BEAUTY.md).
	local still = Workspace:GetAttribute("BeautyShot") ~= nil
	local idleTarget = if now - lastActive > IDLE_AFTER and not still then 1 else 0
	idle += (idleTarget - idle) * (1 - math.exp(-dt / (if idleTarget > idle then 0.6 else 0.12)))

	local swayYaw = SWAY_YAW * idle * noise(now * 0.21, 1.5)
	local swayPitch = SWAY_PITCH * idle * (noise(now * 0.27, 2.5) * 0.7 + math.sin(now * 1.6) * 0.3)
	if still then
		recoilYaw.x, recoilYaw.v, recoilPitch.x, recoilPitch.v = 0, 0, 0, 0
	elseif recoilFresh then
		recoilFresh = false
	else
		stepSpring(recoilYaw, 0, dt)
		stepSpring(recoilPitch, 0, dt)
	end
	local aimYaw, aimPitch = aimAngles()
	if still then
		lagYaw.x, lagYaw.v, lagPitch.x, lagPitch.v = aimYaw, 0, aimPitch, 0
	else
		stepSpring(lagYaw, aimYaw, dt)
		stepSpring(lagPitch, aimPitch, dt)
	end
	stepSpring(gunBack, 0, dt)
	stepSpring(gunClimb, 0, dt)
	stepSpring(gunTwist, 0, dt)
	local cant = math.clamp(-lagYaw.v * CANT, -1.5, 1.5)

	local gunYaw = lagYaw.x + swayYaw
	local gunPitch = math.clamp(lagPitch.x + swayPitch, Config.PITCH_MIN - 3, Config.PITCH_MAX + 3)
	local kick = CFrame.new(0, 0, math.max(gunBack.x, -0.1))
		* CFrame.Angles(math.rad(gunClimb.x), 0, math.rad(cant + gunTwist.x))
	drawnGunCf = Aim.cframe(gunYaw, gunPitch) * kick
	aimGunCf = Aim.cframe(aimYaw, aimPitch)
	if turretYaw then
		turretYaw:PivotTo(Aim.cframe(gunYaw, 0))
	end
	if turretGun then
		turretGun:PivotTo(drawnGunCf)
	end
end

-- Centre-preserving camera motion (view-space): shove back along the view
-- axis and roll about it. Returns the offset and the FOV punch.
local function cameraMotion(dt: number): (CFrame, number)
	dt = math.clamp(dt, 0, 0.1)
	stepSpring(camShove, 0, dt)
	stepSpring(camRoll, 0, dt)
	stepSpring(fovPunch, 0, dt)
	local sway = if aiming then SWAY_ROLL * idle * noise(os.clock() * 0.19, 3.5) else 0
	local shove = math.max(camShove.x, -0.05)
	return CFrame.new(0, 0, shove) * CFrame.Angles(0, 0, math.rad(camRoll.x + sway)), fovPunch.x
end

local function turretCamera(dt: number)
	readInput()
	updateTurret(dt)
	UserInputService.MouseBehavior = Enum.MouseBehavior.LockCenter
	UserInputService.MouseIconEnabled = false

	local look = Aim.direction(aimAngles())
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
	local motion, punch = cameraMotion(dt)
	camera.FieldOfView = fovCurrent + punch * fovCurrent / CAM.FOV_DEFAULT
	camera.CFrame = CFrame.lookAt(pos, pos + look) * motion * shakeOffset(dt)
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
	RunService:BindToRenderStep("RedMesaCamera", Enum.RenderPriority.Camera.Value + 1, FrameProfile.wrap("Camera", function(dt)
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
	end))
end

return AimController
