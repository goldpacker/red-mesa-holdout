--!strict
-- Lighting presets for the wave progression (GAME_SPEC §7.1): afternoon →
-- late afternoon → sunset → dusk → night. Transitions are tweened during
-- intermissions; new runs and retries snap straight to the wave's preset.
-- Night keeps enemies readable through ambient fill, exposure and the
-- mesa searchlights (Workspace.Battlefield.Searchlights) enabled here.

local Lighting = game:GetService("Lighting")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local TimeOfDay = {}

type Preset = {
	lighting: { [string]: any },
	atmosphere: { [string]: any },
	grade: { [string]: any },
	bloom: { [string]: any },
	rays: { [string]: any },
	searchlights: boolean,
}

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

local PRESETS: { [string]: Preset } = {
	Afternoon = {
		lighting = { ClockTime = 15.2, Brightness = 3, ExposureCompensation = 0, Ambient = rgb(90, 70, 60), OutdoorAmbient = rgb(150, 120, 100), ColorShift_Top = rgb(255, 244, 225) },
		atmosphere = { Density = 0.2, Haze = 0.5, Glare = 0.1, Color = rgb(235, 190, 150), Decay = rgb(190, 120, 90) },
		grade = { Contrast = 0.12, Saturation = 0.08, TintColor = rgb(255, 244, 232), Brightness = 0 },
		bloom = { Intensity = 0.6, Threshold = 1.6 },
		rays = { Intensity = 0.06 },
		searchlights = false,
	},
	LateAfternoon = {
		lighting = { ClockTime = 16.6, Brightness = 2.8, ExposureCompensation = 0, Ambient = rgb(95, 70, 58), OutdoorAmbient = rgb(150, 115, 92), ColorShift_Top = rgb(255, 225, 190) },
		atmosphere = { Density = 0.22, Haze = 0.7, Glare = 0.25, Color = rgb(240, 185, 140), Decay = rgb(200, 115, 80) },
		grade = { Contrast = 0.14, Saturation = 0.12, TintColor = rgb(255, 236, 214), Brightness = 0 },
		bloom = { Intensity = 0.7, Threshold = 1.5 },
		rays = { Intensity = 0.09 },
		searchlights = false,
	},
	Sunset = {
		lighting = { ClockTime = 17.25, Brightness = 2.8, ExposureCompensation = 0.2, Ambient = rgb(110, 80, 70), OutdoorAmbient = rgb(165, 120, 100), ColorShift_Top = rgb(255, 180, 120) },
		atmosphere = { Density = 0.22, Haze = 1.0, Glare = 0.5, Color = rgb(250, 170, 120), Decay = rgb(180, 95, 80) },
		grade = { Contrast = 0.16, Saturation = 0.18, TintColor = rgb(255, 222, 196), Brightness = 0.02 },
		bloom = { Intensity = 0.9, Threshold = 1.3 },
		rays = { Intensity = 0.14 },
		searchlights = false,
	},
	Dusk = {
		lighting = { ClockTime = 18.1, Brightness = 2.0, ExposureCompensation = 0.5, Ambient = rgb(95, 78, 92), OutdoorAmbient = rgb(135, 112, 140), ColorShift_Top = rgb(230, 140, 125) },
		atmosphere = { Density = 0.28, Haze = 1.4, Glare = 0.3, Color = rgb(170, 110, 130), Decay = rgb(90, 60, 90) },
		grade = { Contrast = 0.18, Saturation = 0.05, TintColor = rgb(236, 220, 240), Brightness = 0.03 },
		bloom = { Intensity = 1.0, Threshold = 1.1 },
		rays = { Intensity = 0.05 },
		searchlights = true,
	},
	Night = {
		lighting = { ClockTime = 0.4, Brightness = 1.4, ExposureCompensation = 0.85, Ambient = rgb(70, 76, 104), OutdoorAmbient = rgb(104, 114, 158), ColorShift_Top = rgb(160, 180, 230) },
		atmosphere = { Density = 0.3, Haze = 0.9, Glare = 0, Color = rgb(70, 80, 110), Decay = rgb(40, 44, 70) },
		grade = { Contrast = 0.2, Saturation = -0.05, TintColor = rgb(214, 226, 255), Brightness = 0.04 },
		bloom = { Intensity = 1.2, Threshold = 0.9 },
		rays = { Intensity = 0 },
		searchlights = true,
	},
}

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
	TweenService:Create(target, TweenInfo.new(duration, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut), goal):Play()
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

-- Moves the lighting to `name`; duration 0 snaps.
function TimeOfDay.set(name: string, duration: number)
	local preset = PRESETS[name] or PRESETS.Afternoon
	apply(Lighting, preset.lighting, duration)
	apply(effect("Atmosphere"), preset.atmosphere, duration)
	apply(effect("Grade"), preset.grade, duration)
	apply(effect("Bloom"), preset.bloom, duration)
	apply(effect("SunRays"), preset.rays, duration)
	Workspace:SetAttribute("TimeOfDay", name)
	if duration > 0 then
		task.delay(duration * 0.5, setSearchlights, preset.searchlights)
	else
		setSearchlights(preset.searchlights)
	end
end

return TimeOfDay
