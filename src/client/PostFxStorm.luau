--!strict
-- Dust-storm lighting state (LOOK-5), the lighting half of VFX-4's storms.
--
-- Interface (docs/FACELIFT_TEAM.md, Update 2 contracts): the attribute
-- `Lighting.StormAmount`, a number 0..1, written by one owner (VFX-4's
-- weather; a server write replicates, a client write stays local). 0 or
-- absent = the preset's own look; 1 = full storm. Look blends toward the
-- storm look at that amount on every client:
--   * the sun dims and its shadows go soft (Brightness × 0.55-0.6,
--     ShadowSoftness → 0.75), exposure lifts a little so the mid-tones
--     don't turn to mud;
--   * the ambient fill turns warm brown at the preset's own brightness;
--   * the Atmosphere thickens into warm-brown haze (Density, Haze up,
--     Offset down) so the view distance shortens; glare and sun rays go;
--   * a client-only grade (Camera.StormGrade) warms and desaturates;
--   * the low dust layers thicken and brown, the sun shafts and glare go
--     (client/PostFxAir, client/PostFxFilm).
-- The storm look is keyed per preset (tan by day, rust-brown at sunset).
--
-- The server's TimeOfDay owns these Lighting/Atmosphere properties. This
-- module overrides them locally only while the storm is above 0, and
-- tracks the server's values as they replicate (a transition, a snap on
-- retry), so the blend always starts from the current preset and the exact
-- server values come back when the storm clears.

local Lighting = game:GetService("Lighting")
local Workspace = game:GetService("Workspace")

local Storm = {}

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

-- Per preset: haze colour, far-haze decay, the brown the ambient turns to
-- (its brightness is matched to the preset's own ambient), and how much of
-- the sun survives.
type StormLook = { color: Color3, decay: Color3, ambient: Color3, sun: number }
local LOOKS: { [string]: StormLook } = {
	Afternoon = { color = rgb(204, 162, 118), decay = rgb(150, 110, 76), ambient = rgb(255, 214, 170), sun = 0.55 },
	LateAfternoon = { color = rgb(208, 152, 104), decay = rgb(148, 100, 68), ambient = rgb(255, 204, 156), sun = 0.55 },
	Sunset = { color = rgb(198, 134, 98), decay = rgb(128, 82, 62), ambient = rgb(255, 196, 160), sun = 0.6 },
}

local TARGET = {
	exposure = 0.2, -- + EV
	shadowSoftness = 0.75,
	ambientGain = 1.12, -- scattered light lifts the fill a little
	specular = 0.5, -- × EnvironmentSpecularScale
	-- Roblox's Atmosphere is steep: 0.4 / 0.14 already hid a 430-stud tank
	-- and turned the whole view one brown, and 0.34 / 0.21 still greyed the
	-- tank and the helicopter (LOOK-5 captures). Full storm is 0.32 / 0.24:
	-- the far wall goes, the basin stays, and VFX-4's storm particles have
	-- room on top (readability rule).
	density = 0.32, -- Atmosphere.Density at full storm (at least)
	offset = 0.24,
	haze = 1.2, -- + Atmosphere.Haze (mostly the sky: it browns)
	sunTint = rgb(206, 158, 118), -- ColorShift_Top at full storm
	grade = { tint = rgb(255, 238, 214), saturation = -0.1, contrast = 0.04 },
}

local LIGHTING_PROPS = {
	"Brightness",
	"ExposureCompensation",
	"ShadowSoftness",
	"Ambient",
	"OutdoorAmbient",
	"ColorShift_Top",
	"EnvironmentSpecularScale",
}
local ATMOSPHERE_PROPS = { "Density", "Offset", "Haze", "Glare", "Color", "Decay" }
local RAYS_PROPS = { "Intensity" }

type Tracked = { inst: Instance, base: { [string]: any }, written: { [string]: any } }
local tracked: { [string]: Tracked } = {}
local grade: ColorCorrectionEffect? = nil
local applied = -1 -- storm amount last written (-1 = nothing written)
local dirty = false

local function same(a: any, b: any): boolean
	if typeof(a) == "Color3" and typeof(b) == "Color3" then
		return math.abs(a.R - b.R) < 0.002 and math.abs(a.G - b.G) < 0.002 and math.abs(a.B - b.B) < 0.002
	elseif type(a) == "number" and type(b) == "number" then
		return math.abs(a - b) < 1e-4
	end
	return a == b
end

local function track(key: string, inst: Instance, props: { string })
	local entry: Tracked = { inst = inst, base = {}, written = {} }
	for _, prop in props do
		entry.base[prop] = (inst :: any)[prop]
	end
	inst.Changed:Connect(function(prop: string)
		if entry.base[prop] == nil then
			return
		end
		local value = (inst :: any)[prop]
		local mine = entry.written[prop]
		if mine ~= nil and same(mine, value) then
			return -- our own write
		end
		entry.base[prop] = value -- the server moved it (transition, snap)
		dirty = true
	end)
	tracked[key] = entry
end

local function write(entry: Tracked, prop: string, value: any)
	local inst = entry.inst :: any
	-- Mark it ours before assigning: with immediate signals Changed runs
	-- inside the assignment and must not mistake this write for the server.
	entry.written[prop] = value
	inst[prop] = value
	entry.written[prop] = inst[prop]
end

local function restore()
	for _, entry in tracked do
		local props = {}
		for prop in entry.written do
			table.insert(props, prop)
		end
		table.clear(entry.written)
		for _, prop in props do
			(entry.inst :: any)[prop] = entry.base[prop]
		end
	end
end

local function luminance(c: Color3): number
	return 0.2126 * c.R + 0.7152 * c.G + 0.0722 * c.B
end

-- The storm ambient: `hue` at `base`'s brightness (× the gain).
local function warmAmbient(base: Color3, hue: Color3): Color3
	local scale = luminance(base) / math.max(luminance(hue), 1e-3) * TARGET.ambientGain
	return Color3.new(math.min(hue.R * scale, 1), math.min(hue.G * scale, 1), math.min(hue.B * scale, 1))
end

local function lerp(a: any, b: any, t: number): any
	if typeof(a) == "Color3" then
		return (a :: Color3):Lerp(b, t)
	end
	return a + (b - a) * t
end

local function applyLighting(t: number, look: StormLook)
	local l = tracked.Lighting
	if l then
		local b = l.base
		write(l, "Brightness", b.Brightness * lerp(1, look.sun, t))
		write(l, "ExposureCompensation", b.ExposureCompensation + TARGET.exposure * t)
		write(l, "ShadowSoftness", lerp(b.ShadowSoftness, math.max(b.ShadowSoftness, TARGET.shadowSoftness), t))
		write(l, "Ambient", lerp(b.Ambient, warmAmbient(b.Ambient, look.ambient), t))
		write(l, "OutdoorAmbient", lerp(b.OutdoorAmbient, warmAmbient(b.OutdoorAmbient, look.ambient), t))
		write(l, "ColorShift_Top", lerp(b.ColorShift_Top, warmAmbient(b.ColorShift_Top, TARGET.sunTint), t))
		write(l, "EnvironmentSpecularScale", b.EnvironmentSpecularScale * lerp(1, TARGET.specular, t))
	end
	local a = tracked.Atmosphere
	if a then
		local b = a.base
		write(a, "Density", lerp(b.Density, math.max(b.Density, TARGET.density), t))
		write(a, "Offset", lerp(b.Offset, TARGET.offset, t))
		write(a, "Haze", b.Haze + TARGET.haze * t)
		write(a, "Glare", b.Glare * (1 - t))
		write(a, "Color", lerp(b.Color, look.color, t))
		write(a, "Decay", lerp(b.Decay, look.decay, t))
	end
	local r = tracked.SunRays
	if r then
		write(r, "Intensity", r.base.Intensity * (1 - t))
	end
end

local function applyGrade(t: number)
	local camera = Workspace.CurrentCamera
	if not grade or grade.Parent ~= camera then
		local effect = Instance.new("ColorCorrectionEffect")
		effect.Name = "StormGrade"
		effect.Enabled = false
		effect.Parent = camera
		grade = effect
	end
	local g = grade :: ColorCorrectionEffect
	g.Enabled = t > 0
	g.TintColor = Color3.new(1, 1, 1):Lerp(TARGET.grade.tint, t)
	g.Saturation = TARGET.grade.saturation * t
	g.Contrast = TARGET.grade.contrast * t
end

-- Called every frame by PostFx with the smoothed storm amount and preset.
function Storm.update(amount: number, preset: string)
	if amount <= 0.001 then
		if applied ~= -1 then
			restore()
			applyGrade(0)
			applied = -1
		end
		dirty = false
		return
	end
	if not dirty and math.abs(amount - applied) < 0.002 then
		return
	end
	dirty = false
	applied = amount
	applyLighting(amount, LOOKS[preset] or LOOKS.Afternoon)
	applyGrade(amount)
end

-- Starts tracking once the server's rig exists (LightingRig.build names the
-- Atmosphere and SunRays; they replicate with Lighting).
function Storm.start()
	track("Lighting", Lighting, LIGHTING_PROPS)
	task.spawn(function()
		local atmosphere = Lighting:WaitForChild("Atmosphere", 30)
		if atmosphere then
			track("Atmosphere", atmosphere, ATMOSPHERE_PROPS)
		end
		local rays = Lighting:WaitForChild("SunRays", 30)
		if rays then
			track("SunRays", rays, RAYS_PROPS)
		end
	end)
end

return Storm
