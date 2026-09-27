--!strict
-- Client-side look values per time-of-day preset (LOOK-5): the low dust
-- layers and sun shafts (client/PostFxAir), the film treatment
-- (client/PostFxFilm) and the storm blend (client/PostFxStorm). The server's
-- TimeOfDay owns Lighting and the post chain; these are the client-only
-- layers keyed against the same written intents (docs/ART_BIBLE.md §4).
--
-- `current()` follows the server's transition: Workspace.TimeOfDay names
-- the preset and Workspace.TimeOfDayFade is its duration (0 = snap: new run,
-- retry, beauty shot), so every client layer eases with the lighting.
-- `storm()` is Lighting.StormAmount (0..1, written by VFX-4's weather),
-- lightly smoothed so a snapped value never pops.

local Lighting = game:GetService("Lighting")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local PostFxPresets = {}

export type Look = {
	dustColor: Color3, -- low dust layer tint (the basin bands)
	dustAlpha: number, -- peak opacity of one band at full weight
	wallColor: Color3, -- dust at the foot of the canyon walls
	wallAlpha: number,
	shaftColor: Color3, -- sun shafts through the dust (low sun only)
	shaftAlpha: number, -- peak opacity of one shaft; 0 = off
	dustGlow: number, -- dust toward the sun glows (backlit, forward scatter)
	grain: number, -- film grain overlay opacity
	vignette: number, -- film vignette opacity (the gunsight adds its own)
	glare: number, -- sun glare strength when looking toward the sun; 0 = off
	glareColor: Color3,
}

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

-- Opacities are peaks: the dust texture's soft profile averages ~40 % of
-- that across a band, and each band is further weighted by distance
-- (client/PostFxAir BANDS).
local PRESETS: { [string]: Look } = {
	Afternoon = {
		dustColor = rgb(232, 214, 192), dustAlpha = 0.22,
		wallColor = rgb(228, 212, 196), wallAlpha = 0.45,
		shaftColor = rgb(255, 236, 206), shaftAlpha = 0, dustGlow = 0.25,
		grain = 0.05, vignette = 0.16,
		glare = 0.8, glareColor = rgb(255, 244, 226),
	},
	LateAfternoon = {
		dustColor = rgb(240, 200, 158), dustAlpha = 0.24,
		wallColor = rgb(238, 198, 162), wallAlpha = 0.45,
		shaftColor = rgb(255, 206, 146), shaftAlpha = 0.22, dustGlow = 0.55,
		grain = 0.055, vignette = 0.2,
		glare = 1, glareColor = rgb(255, 214, 160),
	},
	Sunset = {
		dustColor = rgb(236, 176, 146), dustAlpha = 0.24,
		wallColor = rgb(230, 170, 150), wallAlpha = 0.42,
		shaftColor = rgb(255, 178, 116), shaftAlpha = 0.3, dustGlow = 0.65,
		grain = 0.06, vignette = 0.22,
		glare = 1, glareColor = rgb(255, 190, 132),
	},
}
PostFxPresets.PRESETS = PRESETS

local IS_STUDIO = RunService:IsStudio()
local STORM_TAU = 0.35 -- seconds; smoothing of Lighting.StormAmount

local fromLook: Look = PRESETS.Afternoon
local toLook: Look = PRESETS.Afternoon
local fadeStart = 0
local fadeTime = 0
local preset = "Afternoon"
local blended: Look = table.clone(PRESETS.Afternoon)
local stormValue = 0
local lastStep = os.clock()

local function lerpLook(a: Look, b: Look, t: number): Look
	local out = {}
	for key, value in a :: any do
		local other = (b :: any)[key]
		if typeof(value) == "Color3" then
			out[key] = (value :: Color3):Lerp(other, t)
		else
			out[key] = value + (other - value) * t
		end
	end
	return (out :: any) :: Look
end

local function progress(): number
	if fadeTime <= 0 then
		return 1
	end
	local t = math.clamp((os.clock() - fadeStart) / fadeTime, 0, 1)
	return t * t * (3 - 2 * t)
end

local function onPreset()
	local name = Workspace:GetAttribute("TimeOfDay")
	local key = if type(name) == "string" and PRESETS[name] then name else "Afternoon"
	local fade = Workspace:GetAttribute("TimeOfDayFade")
	-- Start from wherever the running blend is, so a new transition never pops.
	fromLook = lerpLook(fromLook, toLook, progress())
	toLook = PRESETS[key]
	preset = key
	fadeStart = os.clock()
	fadeTime = if type(fade) == "number" then fade else 0
end

-- The preset's client look right now (mid-transition values while fading).
function PostFxPresets.current(): Look
	return blended
end

function PostFxPresets.preset(): string
	return preset
end

-- True while a transition is still easing (layers refresh every frame then).
function PostFxPresets.fading(): boolean
	return progress() < 1
end

-- Smoothed Lighting.StormAmount, 0..1.
function PostFxPresets.storm(): number
	return stormValue
end

local function readStorm(): number
	local value = Lighting:GetAttribute("StormAmount")
	return if type(value) == "number" then math.clamp(value, 0, 1) else 0
end

-- Advances the blend once per frame (PostFx calls it first in its step).
function PostFxPresets.step()
	local now = os.clock()
	local dt = math.min(now - lastStep, 0.25)
	lastStep = now
	local t = progress()
	blended = if t >= 1 then toLook else lerpLook(fromLook, toLook, t)
	local target = readStorm()
	local beauty = IS_STUDIO and Workspace:GetAttribute("BeautyShot") ~= nil
	if beauty or math.abs(target - stormValue) < 1e-3 then
		stormValue = target
	else
		stormValue += (target - stormValue) * (1 - math.exp(-dt / STORM_TAU))
	end
end

function PostFxPresets.start()
	onPreset()
	fromLook = toLook
	blended = toLook
	stormValue = readStorm()
	Workspace:GetAttributeChangedSignal("TimeOfDay"):Connect(onPreset)
end

return PostFxPresets
