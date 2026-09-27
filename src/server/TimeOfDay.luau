--!strict
-- Lighting presets for the wave progression (GAME_SPEC §7.1, daylight only):
-- afternoon (waves 1-3) → late afternoon (4-6) → sunset (7-10, the climax
-- and the boss). Transitions are tweened during intermissions; new runs and
-- retries snap straight to the wave's preset. Each preset is keyed against
-- its written intent in docs/ART_BIBLE.md §4 (warm key, cooler ambient
-- fill, per-preset atmosphere/grade/bloom/sun rays); the client adds its
-- own layers per preset (client/PostFxPresets: low dust, sun shafts, film).
--
-- ClockTime and LightingRig's GeographicLatitude (30) set the sun path the
-- ENV skyboxes are painted for (SkyAssets clockTime/authoredSun); keep
-- them in step with ENV if either side changes. The sun stands low in the
-- west (-X) from late afternoon on, just over the left canyon wall.
--
-- Dusk and night were removed from the game (spec §7.1, 3397923). The
-- searchlight towers are dormant props: WorldBuilder builds their lights
-- off and nothing turns them on.

local Lighting = game:GetService("Lighting")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local LightingRig = require(script.Parent.LightingRig)

local TimeOfDay = {}

type Preset = {
	lighting: { [string]: any },
	atmosphere: { [string]: any },
	grade: { [string]: any },
	bloom: { [string]: any },
	rays: { [string]: any },
}

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

-- Haze added over the sky while a tweened transition swaps skybox faces.
local SWAP_HAZE = 2.6

-- Retired preset names still in a wave table (until it is retuned) play
-- as the climax light.
local RETIRED: { [string]: string } = { Dusk = "Sunset", Night = "Sunset" }

local PRESETS: { [string]: Preset } = {
	-- High warm-white sun, crisp short shadows, cool sky fill; clearest preset.
	-- LOOK-5: a harder key over a darker, cooler fill and a stronger, cleaner
	-- grade (less orange, deeper sky); pale dust haze that sets the far wall
	-- back behind the buttes.
	Afternoon = {
		lighting = {
			ClockTime = 15.2, Brightness = 4.1, ExposureCompensation = -0.12,
			Ambient = rgb(66, 70, 82), OutdoorAmbient = rgb(80, 88, 114),
			ColorShift_Top = rgb(255, 236, 206), ColorShift_Bottom = rgb(70, 84, 120),
			EnvironmentDiffuseScale = 0.5, EnvironmentSpecularScale = 1, ShadowSoftness = 0.08,
		},
		-- Density 0.27 (LOOK-5 fix 1): 0.30 lifted the darks of a tank at
		-- 430 studs (inside its firing window) to 2.84:1 against the road;
		-- 0.27 gives 4.17:1 (darkest quartile, LOOK-5 report). Offset and
		-- Haze only shape the far wall and sky (measured: no change on basin
		-- subjects), so they stay and keep the depth.
		atmosphere = { Density = 0.27, Offset = 0.3, Haze = 0.9, Glare = 0.2, Color = rgb(226, 212, 198), Decay = rgb(178, 150, 128) },
		grade = { Contrast = 0.34, Saturation = -0.08, TintColor = rgb(255, 252, 248), Brightness = -0.03 },
		bloom = { Intensity = 0.45, Size = 24, Threshold = 2.4 },
		rays = { Intensity = 0.04, Spread = 0.5 },
	},
	-- Lower, golden sun (16.85, ~17° up): warm amber key, longer shadows
	-- raking across the basin, haze layering the far wall and buttes.
	-- LOOK-5: golden key against a cooler violet fill, stronger grade, warm
	-- dust haze low in the basin and shafts of light over the west rim.
	LateAfternoon = {
		lighting = {
			ClockTime = 16.85, Brightness = 3.8, ExposureCompensation = -0.05,
			Ambient = rgb(70, 64, 84), OutdoorAmbient = rgb(84, 84, 126),
			ColorShift_Top = rgb(255, 196, 132), ColorShift_Bottom = rgb(88, 86, 136),
			EnvironmentDiffuseScale = 0.46, EnvironmentSpecularScale = 1, ShadowSoftness = 0.1,
		},
		-- Density 0.24 (LOOK-5 fix 1): at 0.28 the warm haze lifted a 430-stud
		-- tank to 2.36:1 against the orange road (pre-LOOK-5 already read
		-- 2.61); 0.24 gives 3.98:1 (darkest quartile, LOOK-5 report).
		atmosphere = { Density = 0.24, Offset = 0.3, Haze = 1.2, Glare = 0.6, Color = rgb(236, 196, 160), Decay = rgb(160, 112, 100) },
		grade = { Contrast = 0.32, Saturation = -0.06, TintColor = rgb(255, 242, 228), Brightness = -0.02 },
		bloom = { Intensity = 0.55, Size = 24, Threshold = 2.2 },
		rays = { Intensity = 0.16, Spread = 0.65 },
	},
	-- Long raking shadows, orange key, violet bounce, strong horizon glow.
	-- LOOK-5: less monochrome red: desaturated, higher-contrast grade, cooler
	-- violet shadows, a thinner rose haze, shafts over the west rim.
	Sunset = {
		lighting = {
			ClockTime = 17.25, Brightness = 3.9, ExposureCompensation = 0,
			Ambient = rgb(64, 60, 88), OutdoorAmbient = rgb(78, 78, 130),
			ColorShift_Top = rgb(255, 170, 110), ColorShift_Bottom = rgb(110, 90, 160),
			EnvironmentDiffuseScale = 0.42, EnvironmentSpecularScale = 1, ShadowSoftness = 0.14,
		},
		atmosphere = { Density = 0.25, Offset = 0.32, Haze = 1.3, Glare = 0.7, Color = rgb(232, 182, 156), Decay = rgb(118, 88, 112) },
		grade = { Contrast = 0.32, Saturation = -0.16, TintColor = rgb(255, 244, 238), Brightness = -0.02 },
		bloom = { Intensity = 0.8, Size = 26, Threshold = 1.8 },
		rays = { Intensity = 0.2, Spread = 0.7 },
	},
}

TimeOfDay.PRESETS = PRESETS

local function effect(name: string): Instance?
	return Lighting:FindFirstChild(name)
end

local function tweenInfo(duration: number): TweenInfo
	return TweenInfo.new(duration, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut)
end

-- Tweens of the running transition; a new set() cancels them so a snap is
-- never overwritten by a stale tween.
local active: { Tween } = {}
local function play(tween: Tween)
	table.insert(active, tween)
	tween:Play()
end
local function cancelActive()
	for _, tween in active do
		tween:Cancel()
	end
	table.clear(active)
end

local function apply(target: Instance?, props: { [string]: any }, duration: number)
	if not target then
		return
	end
	if duration <= 0 then
		for key, value in props do
			(target :: any)[key] = value
		end
		return
	end
	play(TweenService:Create(target, tweenInfo(duration), props))
end

-- Atmosphere tween that swells the haze over the sky around the moment the
-- skybox faces swap (LightingRig.SWAP_AT), so the swap reads as dust
-- drifting across rather than a pop.
local atmosphereToken = 0
local function applyAtmosphere(props: { [string]: any }, duration: number, swap: boolean)
	local target = effect("Atmosphere")
	atmosphereToken += 1
	if not target or duration <= 0 or not swap then
		apply(target, props, duration)
		return
	end
	local token = atmosphereToken
	local atmosphere = target :: Atmosphere
	local first = duration * LightingRig.SWAP_AT
	local mid = {}
	for key, value in props do
		if typeof(value) == "Color3" then
			mid[key] = (atmosphere :: any)[key]:Lerp(value, 0.5)
		elseif type(value) == "number" then
			mid[key] = ((atmosphere :: any)[key] + value) * 0.5
		end
	end
	mid.Haze = math.max(atmosphere.Haze, props.Haze or 0) + SWAP_HAZE
	local swell = TweenService:Create(atmosphere, TweenInfo.new(first, Enum.EasingStyle.Sine, Enum.EasingDirection.In), mid)
	swell.Completed:Once(function(state)
		if state == Enum.PlaybackState.Completed and atmosphereToken == token then
			play(TweenService:Create(atmosphere, TweenInfo.new(duration - first, Enum.EasingStyle.Sine, Enum.EasingDirection.Out), props))
		end
	end)
	play(swell)
end

-- A SunRaysEffect at intensity 0 still costs a full-screen pass: it is
-- switched off whenever a preset doesn't use it, and on before any tween
-- that raises it.
local raysToken = 0
local function setRaysEnabled(intensity: number, duration: number)
	local rays = effect("SunRays")
	if not rays then
		return
	end
	raysToken += 1
	local token = raysToken
	if intensity > 0 then
		(rays :: SunRaysEffect).Enabled = true
	elseif duration <= 0 then
		(rays :: SunRaysEffect).Enabled = false
	else
		task.delay(duration, function()
			if raysToken == token then
				(rays :: SunRaysEffect).Enabled = false
			end
		end)
	end
end

function TimeOfDay.presetFor(waveNumber: number, waves: { any }): string
	local wave = waves[waveNumber]
	return (wave and wave.time) or "Afternoon"
end

-- Moves the lighting to `name`; duration 0 snaps.
function TimeOfDay.set(name: string, duration: number)
	local key = RETIRED[name] or name
	key = if PRESETS[key] then key else "Afternoon"
	local preset = PRESETS[key]
	local swap = duration > 0 and LightingRig.skyChanges(key)
	cancelActive()
	apply(Lighting, preset.lighting, duration)
	applyAtmosphere(preset.atmosphere, duration, swap)
	apply(effect("Grade"), preset.grade, duration)
	apply(effect("Bloom"), preset.bloom, duration)
	apply(effect("SunRays"), preset.rays, duration)
	setRaysEnabled(preset.rays.Intensity, duration)
	LightingRig.setSky(key, duration)
	-- Clients follow the same transition (PostFx layers): duration first.
	Workspace:SetAttribute("TimeOfDayFade", math.max(duration, 0))
	Workspace:SetAttribute("TimeOfDay", key)
end

return TimeOfDay
