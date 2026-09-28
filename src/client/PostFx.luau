--!strict
-- Client-local post effects (LOOK-1, FACELIFT_PLAN Phase 2):
--   * gunsight depth of field: while aiming, a subtle near blur that keeps
--     the target and everything beyond it sharp (no far blur at all);
--   * heat haze: faint shimmering bands low over the hot basin, daytime
--     only (scrolling-texture Beams facing the turret; no custom shaders);
--   * LOOK-5 (one per-frame step drives them all, PostFxPresets first):
--     PostFxAir (low dust layers, sun shafts), PostFxFilm (grain, vignette,
--     sun glare; `FilmFxOff` turns it off) and PostFxStorm (the storm
--     lighting state driven by Lighting.StormAmount).
-- Everything here is created on the client, so it costs the server nothing
-- and toggles per frame without replication.

local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")
local FrameProfile = require(script.Parent.FrameProfile)

local AimController = require(script.Parent.AimController)
local Air = require(script.Parent.PostFxAir)
local Assets = require(script.Parent.PostFxAssets)
local Film = require(script.Parent.PostFxFilm)
local Governor = require(script.Parent.PerfGovernor)
local Presets = require(script.Parent.PostFxPresets)
local Storm = require(script.Parent.PostFxStorm)

local PostFx = {}

-- Depth of field in the gunsight. Focus sits on the aim point; the in-focus
-- radius reaches back to ~40 studs in front of the lens, so only the pit,
-- sight hardware and the mesa lip right under the view soften.
local DOF = {
	NEAR_INTENSITY = 0.32,
	NEAR_SHARP = 40, -- studs from the camera where sharp focus begins
	MIN_FOCUS = 120,
	MAX_FOCUS = 500, -- DepthOfFieldEffect clamps FocusDistance/InFocusRadius at 500
	FADE = 0.18, -- seconds to blend in/out
}

-- Heat-haze bands: distance down range (studs, along -Z from the turret),
-- half-width across the basin, band height, strength multiplier.
local HAZE_BANDS = {
	{ z = -360, halfWidth = 480, width = 8, strength = 0.6, speed = 0.05 },
	{ z = -520, halfWidth = 640, width = 11, strength = 0.85, speed = -0.04 },
	{ z = -700, halfWidth = 820, width = 14, strength = 1, speed = 0.03 },
}
local HAZE_TRANSPARENCY = 0.84 -- at full strength (texture alpha does the rest)
local HAZE_COLOR = Color3.fromRGB(255, 236, 214)
-- Off at sunset (LOOK-5): at a quarter strength it barely showed, and the
-- busy sunset waves are where the GPU budget binds.
local HAZE_STRENGTH: { [string]: number } = {
	Afternoon = 1,
	LateAfternoon = 0.75,
	Sunset = 0,
}

local camera = Workspace.CurrentCamera
local dof: DepthOfFieldEffect? = nil
local dofWeight = 0

type HazeBeam = { beam: Beam, fadeIn: boolean, fadeOut: boolean, speed: number }
type Band = { beams: { HazeBeam }, strength: number }
local bands: { Band } = {}
local hazeLevel = -1
local hazeFolder: Folder? = nil

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include

-- ------------------------------------------------------------------ DoF
local function ensureDof(): DepthOfFieldEffect
	if dof and dof.Parent then
		return dof
	end
	local effect = Instance.new("DepthOfFieldEffect")
	effect.Name = "GunsightDoF"
	effect.FarIntensity = 0
	effect.NearIntensity = 0
	effect.FocusDistance = DOF.MIN_FOCUS
	effect.InFocusRadius = DOF.MIN_FOCUS - DOF.NEAR_SHARP
	effect.Enabled = false
	effect.Parent = camera
	dof = effect
	return effect
end

local function updateDof(dt: number)
	local effect = ensureDof()
	-- Governor tier 2 drops the near blur (PERF-1).
	local aiming = AimController.getMode() == "Turret" and AimController.isAiming() and Governor.tier() < 2
	local step = dt / DOF.FADE
	dofWeight = math.clamp(dofWeight + (if aiming then step else -step), 0, 1)
	if dofWeight <= 0 then
		effect.Enabled = false
		return
	end
	local target = AimController.getAimTarget()
	local distance = (target - camera.CFrame.Position).Magnitude
	local focus = math.clamp(distance, DOF.MIN_FOCUS, DOF.MAX_FOCUS)
	effect.Enabled = true
	effect.FocusDistance = focus
	effect.InFocusRadius = focus - DOF.NEAR_SHARP
	effect.FarIntensity = 0
	effect.NearIntensity = DOF.NEAR_INTENSITY * dofWeight
end

-- ------------------------------------------------------------------ heat haze
local function groundHit(x: number, z: number): RaycastResult?
	groundParams.FilterDescendantsInstances = { Workspace.Terrain }
	return Workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -800, 0), groundParams)
end

local function groundY(x: number, z: number): number
	local hit = groundHit(x, z)
	return if hit then hit.Position.Y else 0
end

local function makeBeam(parent: Instance, a0: Attachment, a1: Attachment, width: number, speed: number, length: number): Beam
	local beam = Instance.new("Beam")
	beam.Attachment0 = a0
	beam.Attachment1 = a1
	beam.Width0 = width
	beam.Width1 = width
	beam.FaceCamera = true
	beam.Segments = 1
	beam.Texture = Assets.heat_haze
	beam.TextureMode = Enum.TextureMode.Wrap
	beam.TextureLength = length
	beam.TextureSpeed = speed
	beam.LightEmission = 0.2
	beam.LightInfluence = 1
	beam.Color = ColorSequence.new(HAZE_COLOR)
	beam.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.5, 1), NumberSequenceKeypoint.new(1, 1) })
	beam.Enabled = false
	beam.Parent = parent
	return beam
end

local function buildHaze()
	if hazeFolder and hazeFolder.Parent then
		return
	end
	local folder = Instance.new("Folder")
	folder.Name = "PostFxHaze"
	table.clear(bands)
	for i, spec in HAZE_BANDS do
		-- Band follows the basin floor: one segment per ~120 studs so it
		-- hugs the terrain instead of floating over dips.
		local segments = math.max(2, math.ceil(spec.halfWidth * 2 / 120))
		local attachments: { Attachment } = {}
		for s = 0, segments do
			local x = -spec.halfWidth + (spec.halfWidth * 2) * s / segments
			local a = Instance.new("Attachment")
			a.Name = string.format("Haze%d_%d", i, s)
			a.WorldPosition = Vector3.new(x, groundY(x, spec.z) + spec.width * 0.3, spec.z)
			a.Parent = Workspace.Terrain
			table.insert(attachments, a)
		end
		local beams: { HazeBeam } = {}
		for s = 1, #attachments - 1 do
			local first, last = s == 1, s == #attachments - 1
			local a0, a1 = attachments[s], attachments[s + 1]
			local speed2 = -spec.speed * 1.7
			table.insert(beams, { beam = makeBeam(folder, a0, a1, spec.width, spec.speed, 70), fadeIn = first, fadeOut = last, speed = spec.speed })
			-- A second, faster layer moving the other way makes the shimmer boil.
			table.insert(beams, { beam = makeBeam(folder, a0, a1, spec.width * 0.7, speed2, 43), fadeIn = first, fadeOut = last, speed = speed2 })
		end
		table.insert(bands, { beams = beams, strength = spec.strength })
	end
	folder.Parent = Workspace
	hazeFolder = folder
	hazeLevel = -1
end

-- One driver value (0..1 haze strength) for every band; a new time of day
-- cancels the running fade so tweens never fight.
local hazeDriver = Instance.new("NumberValue")
local hazeTween: Tween? = nil

local hazeStorm = 0 -- a dust storm hides the shimmer

local function applyHazeStrength(level: number)
	level *= 1 - hazeStorm
	-- Governor tier 1+ drops the shimmer (PERF-1).
	if Governor.tier() >= 1 then
		level = 0
	end
	for _, band in bands do
		local v = 1 - (1 - HAZE_TRANSPARENCY) * level * band.strength
		for _, item in band.beams do
			item.beam.Enabled = level > 0.001
			item.beam.Transparency = NumberSequence.new({
				NumberSequenceKeypoint.new(0, if item.fadeIn then 1 else v),
				NumberSequenceKeypoint.new(0.5, v),
				NumberSequenceKeypoint.new(1, if item.fadeOut then 1 else v),
			})
		end
	end
end

local function setHaze(level: number, fade: number)
	if level == hazeLevel then
		return
	end
	hazeLevel = level
	if hazeTween then
		hazeTween:Cancel()
		hazeTween = nil
	end
	if fade <= 0 then
		hazeDriver.Value = level
		applyHazeStrength(level)
		return
	end
	local tween = TweenService:Create(hazeDriver, TweenInfo.new(fade, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut), { Value = level })
	hazeTween = tween
	tween:Play()
end

local function updateHaze()
	local tod = Workspace:GetAttribute("TimeOfDay")
	local level = HAZE_STRENGTH[tod :: string] or 0
	-- Follow the server's lighting transition: TimeOfDay publishes its
	-- duration (0 = snap: new runs, retries, beauty shots).
	local fade = Workspace:GetAttribute("TimeOfDayFade")
	setHaze(level, if type(fade) == "number" then fade else 0)
end

-- The beauty-shot rig wants deterministic frames: freeze the shimmer.
local function pauseForBeauty()
	local beauty = Workspace:GetAttribute("BeautyShot") ~= nil
	for _, band in bands do
		for _, item in band.beams do
			item.beam.TextureSpeed = if beauty then 0 else item.speed
		end
	end
end

-- ------------------------------------------------------------------ LOOK-5 step
local airReady = false
local hazeTier = 0

local function step(dt: number)
	updateDof(dt)
	local tier = Governor.tier()
	if tier ~= hazeTier then
		hazeTier = tier
		applyHazeStrength(hazeDriver.Value)
	end
	Presets.step()
	local look = Presets.current()
	local storm = Presets.storm()
	Film.update(dt, look, storm)
	Storm.update(storm, Presets.preset())
	if airReady then
		Air.update(look, storm, Presets.fading())
	end
	if math.abs(storm - hazeStorm) > 0.01 or (storm == 0 and hazeStorm ~= 0) then
		hazeStorm = storm
		applyHazeStrength(hazeDriver.Value)
	end
end

function PostFx.start()
	Governor.start()
	ensureDof()
	Presets.start()
	Film.start()
	Storm.start()
	task.spawn(function()
		-- Terrain is written by the server at start and replicates after the
		-- Battlefield folder; wait until the basin floor is raycastable.
		local waited = 0
		while waited < 60 and not (Workspace:FindFirstChild("Battlefield") and groundHit(0, -400)) do
			task.wait(0.5)
			waited += 0.5
		end
		hazeDriver.Changed:Connect(applyHazeStrength)
		buildHaze()
		updateHaze()
		Air.build()
		airReady = true
		Workspace:GetAttributeChangedSignal("TimeOfDay"):Connect(updateHaze)
		Workspace:GetAttributeChangedSignal("BeautyShot"):Connect(pauseForBeauty)
		pauseForBeauty()
	end)
	RunService.RenderStepped:Connect(FrameProfile.wrap("PostFx", step))
end

return PostFx
