--!strict
-- Lighting presets for the wave progression (GAME_SPEC §7.1): afternoon →
-- late afternoon → sunset → dusk → night. Transitions are tweened during
-- intermissions; new runs and retries snap straight to the wave's preset.
-- Each preset is keyed against its written intent in docs/ART_BIBLE.md §4
-- (warm key, cooler ambient fill, per-preset grade/bloom/sun rays). Night
-- keeps enemies readable through ambient fill, exposure and the mesa
-- searchlights (Workspace.Battlefield.Searchlights) enabled here.
--
-- ClockTime and LightingRig's GeographicLatitude (30) set the sun path the
-- ENV skyboxes are painted for; keep them unless the skies are re-rendered.
--
-- Roblox darkens the skybox as soon as the sun is below the horizon, so a
-- painted night sky is invisible at a real night ClockTime. Night is
-- therefore "day for night" (`moonlit`): the clock sits at noon, where the
-- sun stands where ENV's moon is painted (near the zenith), the sun disc is
-- drawn with the moon texture, and the light is keyed dim and cool. Moving
-- into or out of a moonlit preset jumps the clock at the sky swap, hidden
-- by the haze swell and a brightness dip. Clients read night from
-- Workspace.TimeOfDay, never from ClockTime.

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
	searchlights: boolean,
	moonlit: boolean?, -- day-for-night (see header)
}

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

-- Haze added over the sky while a tweened transition swaps skybox faces.
local SWAP_HAZE = 2.6
-- Light level at the moment the clock jumps into/out of a moonlit preset.
local DIP_BRIGHTNESS = 0.35

local PRESETS: { [string]: Preset } = {
	-- High warm-white sun, crisp short shadows, cool sky fill; clearest preset.
	Afternoon = {
		lighting = {
			ClockTime = 15.2, Brightness = 3.8, ExposureCompensation = 0,
			Ambient = rgb(70, 72, 84), OutdoorAmbient = rgb(88, 96, 122),
			ColorShift_Top = rgb(255, 236, 206), ColorShift_Bottom = rgb(70, 84, 120),
			EnvironmentDiffuseScale = 0.65, EnvironmentSpecularScale = 1, ShadowSoftness = 0.08,
		},
		atmosphere = { Density = 0.24, Offset = 0.1, Haze = 0.6, Glare = 0.15, Color = rgb(222, 196, 172), Decay = rgb(160, 120, 96) },
		grade = { Contrast = 0.18, Saturation = 0.04, TintColor = rgb(255, 248, 238), Brightness = -0.02 },
		bloom = { Intensity = 0.45, Size = 24, Threshold = 2.4 },
		rays = { Intensity = 0.04, Spread = 0.5 },
		searchlights = false,
	},
	-- Lower amber-white sun; shadows start to rake, haze layers the far wall.
	LateAfternoon = {
		lighting = {
			ClockTime = 16.6, Brightness = 3.7, ExposureCompensation = 0.05,
			Ambient = rgb(74, 70, 86), OutdoorAmbient = rgb(92, 92, 124),
			ColorShift_Top = rgb(255, 212, 160), ColorShift_Bottom = rgb(84, 86, 132),
			EnvironmentDiffuseScale = 0.58, EnvironmentSpecularScale = 1, ShadowSoftness = 0.1,
		},
		atmosphere = { Density = 0.25, Offset = 0.1, Haze = 1.1, Glare = 0.4, Color = rgb(234, 186, 150), Decay = rgb(146, 100, 92) },
		grade = { Contrast = 0.19, Saturation = 0.04, TintColor = rgb(255, 242, 230), Brightness = -0.015 },
		bloom = { Intensity = 0.55, Size = 24, Threshold = 2.2 },
		rays = { Intensity = 0.08, Spread = 0.55 },
		searchlights = false,
	},
	-- Long raking shadows, orange key, violet bounce, strong horizon glow.
	Sunset = {
		lighting = {
			ClockTime = 17.25, Brightness = 3.6, ExposureCompensation = 0.2,
			Ambient = rgb(80, 70, 92), OutdoorAmbient = rgb(104, 92, 142),
			ColorShift_Top = rgb(255, 170, 110), ColorShift_Bottom = rgb(110, 90, 160),
			EnvironmentDiffuseScale = 0.5, EnvironmentSpecularScale = 1, ShadowSoftness = 0.14,
		},
		atmosphere = { Density = 0.27, Offset = 0.1, Haze = 1.5, Glare = 0.9, Color = rgb(228, 164, 136), Decay = rgb(124, 80, 100) },
		grade = { Contrast = 0.2, Saturation = -0.08, TintColor = rgb(255, 238, 230), Brightness = -0.01 },
		bloom = { Intensity = 0.8, Size = 26, Threshold = 1.8 },
		rays = { Intensity = 0.14, Spread = 0.6 },
		searchlights = false,
	},
	-- Sun at the canyon rim: violet-magenta sky with the first stars, cool
	-- sky light, no hard sun shadows; artificial lights take over. The clock
	-- stays just above the horizon (17.7) because Roblox blacks out the
	-- skybox once the sun sets. Lifted so dark enemies stay readable.
	Dusk = {
		lighting = {
			ClockTime = 17.7, Brightness = 2.6, ExposureCompensation = 1.15,
			Ambient = rgb(80, 78, 108), OutdoorAmbient = rgb(128, 122, 178),
			ColorShift_Top = rgb(225, 170, 200), ColorShift_Bottom = rgb(72, 80, 126),
			EnvironmentDiffuseScale = 0.45, EnvironmentSpecularScale = 0.9, ShadowSoftness = 0.4,
		},
		atmosphere = { Density = 0.26, Offset = 0.08, Haze = 2, Glare = 0.6, Color = rgb(170, 128, 168), Decay = rgb(84, 66, 116) },
		grade = { Contrast = 0.3, Saturation = -0.24, TintColor = rgb(230, 228, 255), Brightness = 0 },
		bloom = { Intensity = 0.9, Size = 26, Threshold = 1.25 },
		rays = { Intensity = 0.03, Spread = 0.5 },
		searchlights = true,
	},
	-- Cool moonlight key from high above (day-for-night: the noon sun is the
	-- moon), starry painted sky, silvery sand, deep but not crushed shadows,
	-- dark enemy silhouettes against lit ground and sky; warm practical
	-- lights (searchlights, flares, lamps) as accents.
	Night = {
		lighting = {
			ClockTime = 12, Brightness = 1.5, ExposureCompensation = 0.1,
			Ambient = rgb(50, 58, 86), OutdoorAmbient = rgb(64, 82, 132),
			ColorShift_Top = rgb(120, 160, 255), ColorShift_Bottom = rgb(30, 36, 60),
			EnvironmentDiffuseScale = 0.4, EnvironmentSpecularScale = 0.6, ShadowSoftness = 0.25,
		},
		atmosphere = { Density = 0.28, Offset = 0.05, Haze = 0.6, Glare = 0, Color = rgb(60, 74, 110), Decay = rgb(30, 36, 60) },
		grade = { Contrast = 0.3, Saturation = -0.3, TintColor = rgb(196, 220, 255), Brightness = 0 },
		bloom = { Intensity = 1.1, Size = 24, Threshold = 0.95 },
		rays = { Intensity = 0, Spread = 0.5 },
		searchlights = true,
		moonlit = true,
	},
}

TimeOfDay.PRESETS = PRESETS

local function effect(name: string): Instance?
	return Lighting:FindFirstChild(name)
end

-- ClockTime is clamped to [0, 24), so a plain tween from 18.45 to 0.4 would
-- run backwards through the day. Drive it through a NumberValue that keeps
-- counting past 24 and wrap when writing.
local clockTween: Tween? = nil
local function tweenClock(target: number, duration: number)
	if clockTween then
		clockTween:Cancel()
		clockTween = nil
	end
	local from = Lighting.ClockTime
	local to = target
	if to < from - 6 then
		to += 24
	end
	if duration <= 0 then
		Lighting.ClockTime = target
		return
	end
	local value = Instance.new("NumberValue")
	value.Value = from
	value.Changed:Connect(function(v)
		Lighting.ClockTime = v % 24
	end)
	local tween = TweenService:Create(value, TweenInfo.new(duration, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut), { Value = to })
	tween.Completed:Once(function()
		value:Destroy()
	end)
	clockTween = tween
	tween:Play()
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
	local goal = table.clone(props)
	if target == Lighting and goal.ClockTime then
		tweenClock(goal.ClockTime, duration)
		goal.ClockTime = nil
	end
	if duration <= 0 then
		for key, value in goal do
			(target :: any)[key] = value
		end
		return
	end
	play(TweenService:Create(target, tweenInfo(duration), goal))
end

-- Lighting for a transition whose clock must jump (into or out of a
-- moonlit preset): everything but the clock tweens to a dim midpoint by the
-- sky swap, the clock jumps there, then the rest tweens on to the target.
local function applyLightingJump(props: { [string]: any }, duration: number)
	if clockTween then
		clockTween:Cancel()
		clockTween = nil
	end
	local goal = table.clone(props)
	local clock = goal.ClockTime
	goal.ClockTime = nil
	local first = duration * LightingRig.SWAP_AT
	local mid = {}
	for key, value in goal do
		local current = (Lighting :: any)[key]
		if typeof(value) == "Color3" then
			mid[key] = current:Lerp(value, 0.5)
		elseif type(value) == "number" then
			mid[key] = (current + value) * 0.5
		end
	end
	mid.Brightness = math.min(Lighting.Brightness, goal.Brightness or Lighting.Brightness) * DIP_BRIGHTNESS
	local dip = TweenService:Create(Lighting, TweenInfo.new(first, Enum.EasingStyle.Sine, Enum.EasingDirection.In), mid)
	dip.Completed:Once(function(state)
		if state ~= Enum.PlaybackState.Completed then
			return
		end
		if clock then
			Lighting.ClockTime = clock
		end
		play(TweenService:Create(Lighting, TweenInfo.new(duration - first, Enum.EasingStyle.Sine, Enum.EasingDirection.Out), goal))
	end)
	play(dip)
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

local function setSearchlights(enabled: boolean)
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local lights = battlefield and battlefield:FindFirstChild("Searchlights")
	if lights then
		lights:SetAttribute("Enabled", enabled)
		for _, d in lights:GetDescendants() do
			if d:IsA("SpotLight") or d:IsA("SurfaceLight") or d:IsA("PointLight") or d:IsA("Beam") then
				d.Enabled = enabled
			elseif d:IsA("BasePart") and d.Name == "Lens" then
				d.Material = if enabled then Enum.Material.Neon else Enum.Material.Glass
			end
		end
	end
end

function TimeOfDay.presetFor(waveNumber: number, waves: { any }): string
	local wave = waves[waveNumber]
	return (wave and wave.time) or "Afternoon"
end

local currentKey: string? = nil

-- Moves the lighting to `name`; duration 0 snaps.
function TimeOfDay.set(name: string, duration: number)
	local key = if PRESETS[name] then name else "Afternoon"
	local preset = PRESETS[key]
	local from = currentKey and PRESETS[currentKey]
	local jump = duration > 0 and ((preset.moonlit == true) ~= (from ~= nil and from.moonlit == true))
	local swap = duration > 0 and (jump or LightingRig.skyChanges(key, preset.moonlit == true))
	currentKey = key
	cancelActive()
	if jump then
		applyLightingJump(preset.lighting, duration)
	else
		apply(Lighting, preset.lighting, duration)
	end
	applyAtmosphere(preset.atmosphere, duration, swap)
	apply(effect("Grade"), preset.grade, duration)
	apply(effect("Bloom"), preset.bloom, duration)
	apply(effect("SunRays"), preset.rays, duration)
	LightingRig.setSky(key, duration, preset.moonlit == true)
	-- Clients follow the same transition (PostFx heat haze): duration first.
	Workspace:SetAttribute("TimeOfDayFade", math.max(duration, 0))
	Workspace:SetAttribute("TimeOfDay", key)
	if duration > 0 then
		task.delay(duration * 0.5, setSearchlights, preset.searchlights)
	else
		setSearchlights(preset.searchlights)
	end
end

return TimeOfDay
