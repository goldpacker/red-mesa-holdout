--!strict
-- Base lighting and post-effect rig for Red Mesa. WorldBuilder calls
-- LightingRig.build() once at server start; TimeOfDay then re-keys the same
-- Lighting properties and named effects (Atmosphere, Bloom, SunRays, Grade)
-- per time-of-day preset and asks LightingRig for the preset's sky.
--
-- Sky: ENV publishes per-preset skybox faces, Sky settings and Clouds in
-- ReplicatedStorage.Shared.SkyAssets (pcall-required). Any preset or field
-- missing there falls back to the sky the place started with. Skybox faces
-- can't be tweened, so a tweened transition swaps them at `SWAP_AT` of the
-- transition while TimeOfDay swells the atmosphere haze over the sky.

local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local LightingRig = {}

LightingRig.SWAP_AT = 0.5 -- fraction of a tweened transition when faces swap

local FACES = { "SkyboxBk", "SkyboxDn", "SkyboxFt", "SkyboxLf", "SkyboxRt", "SkyboxUp" }
local SKY_PROPS = { "CelestialBodiesShown", "SunAngularSize", "MoonAngularSize", "StarCount", "SunTextureId", "MoonTextureId" }
local CLOUD_TWEEN = { "Cover", "Density", "Color" }

type SkyEntry = {
	faces: { [string]: string }?,
	sky: { [string]: any }?,
	clouds: { [string]: any }?,
}

local fallback: { faces: { [string]: string }, sky: { [string]: any }, clouds: { [string]: any } } = {
	faces = {},
	sky = {},
	clouds = { Enabled = false, Cover = 0, Density = 0, Color = Color3.new(1, 1, 1) },
}
local skyAssets: { [string]: SkyEntry }? = nil
local skyLoaded = false
local currentFaces: { [string]: string } = {}
local swapToken = 0
local cloudTween: Tween? = nil

local function ensureEffect(className: string, name: string): Instance
	local existing = Lighting:FindFirstChild(name)
	if existing then
		return existing
	end
	local inst = Instance.new(className)
	inst.Name = name
	inst.Parent = Lighting
	return inst
end

local function sky(): Sky
	local existing = Lighting:FindFirstChildOfClass("Sky")
	if existing then
		return existing
	end
	local created = Instance.new("Sky")
	created.Name = "Sky"
	created.Parent = Lighting
	return created
end

local function clouds(): Clouds
	local terrain = Workspace.Terrain
	local existing = terrain:FindFirstChildOfClass("Clouds")
	if existing then
		return existing
	end
	local created = Instance.new("Clouds")
	created.Enabled = false
	created.Cover = 0
	created.Density = 0
	created.Parent = terrain
	return created
end

-- Remembers the sky the place starts with; it is the fallback for anything
-- SkyAssets doesn't provide.
local function snapshotSky()
	local s = sky()
	for _, face in FACES do
		fallback.faces[face] = (s :: any)[face]
	end
	for _, prop in SKY_PROPS do
		fallback.sky[prop] = (s :: any)[prop]
	end
	local c = Workspace.Terrain:FindFirstChildOfClass("Clouds")
	if c then
		fallback.clouds = { Enabled = c.Enabled, Cover = c.Cover, Density = c.Density, Color = c.Color }
	end
	currentFaces = table.clone(fallback.faces)
end

local function loadSkyAssets(): { [string]: SkyEntry }?
	if skyLoaded then
		return skyAssets
	end
	skyLoaded = true
	local module = ReplicatedStorage:FindFirstChild("Shared") and ReplicatedStorage.Shared:FindFirstChild("SkyAssets")
	if not module then
		return nil
	end
	local ok, result = pcall(require, module)
	if ok and type(result) == "table" and type((result :: any).PRESETS) == "table" then
		skyAssets = (result :: any).PRESETS
	elseif not ok then
		warn("[RedMesa] SkyAssets failed to load, keeping the default sky: " .. tostring(result))
	end
	return skyAssets
end

local function entryFor(name: string): SkyEntry
	local assets = loadSkyAssets()
	return (assets and assets[name]) or {}
end

-- Resolved sky for a preset: SkyAssets values over the fallback, per field.
-- `sunAsMoon` (TimeOfDay's day-for-night) draws the sun disc with the moon
-- texture and size, since the sun then stands in for the moon.
local function resolve(name: string, sunAsMoon: boolean?): ({ [string]: string }, { [string]: any }, { [string]: any })
	local entry = entryFor(name)
	local faces = table.clone(fallback.faces)
	for face, id in entry.faces or {} do
		faces[face] = id
	end
	local props = table.clone(fallback.sky)
	for key, value in entry.sky or {} do
		props[key] = value
	end
	if sunAsMoon then
		props.SunTextureId = props.MoonTextureId
		props.SunAngularSize = props.MoonAngularSize
	end
	local cloud = table.clone(fallback.clouds)
	for key, value in entry.clouds or {} do
		cloud[key] = if key == "Color" and type(value) == "string" then Color3.fromHex(value) else value
	end
	return faces, props, cloud
end

local function applyFaces(faces: { [string]: string }, props: { [string]: any })
	local s = sky()
	for face, id in faces do
		(s :: any)[face] = id
	end
	for key, value in props do
		local ok = pcall(function()
			(s :: any)[key] = value
		end)
		if not ok then
			warn("[RedMesa] SkyAssets: unknown Sky property " .. key)
		end
	end
	currentFaces = table.clone(faces)
end

-- True when switching to `name` changes the skybox faces (the swap needs
-- hiding behind the haze swell).
function LightingRig.skyChanges(name: string, sunAsMoon: boolean?): boolean
	local faces = resolve(name, sunAsMoon)
	for face, id in faces do
		if currentFaces[face] ~= id then
			return true
		end
	end
	return false
end

-- Moves sky and clouds to preset `name`; duration 0 snaps.
function LightingRig.setSky(name: string, duration: number, sunAsMoon: boolean?)
	local faces, props, cloud = resolve(name, sunAsMoon)
	swapToken += 1
	local token = swapToken
	if duration <= 0 then
		applyFaces(faces, props)
	else
		task.delay(duration * LightingRig.SWAP_AT, function()
			if swapToken == token then
				applyFaces(faces, props)
			end
		end)
	end

	if cloudTween then
		cloudTween:Cancel()
		cloudTween = nil
	end
	local c = clouds()
	local goal = {}
	for _, key in CLOUD_TWEEN do
		goal[key] = cloud[key]
	end
	if not cloud.Enabled then
		goal.Cover = 0
	end
	if cloud.Enabled then
		c.Enabled = true
	end
	if duration <= 0 then
		for key, value in goal do
			(c :: any)[key] = value
		end
		c.Enabled = cloud.Enabled
		return
	end
	local tween = TweenService:Create(c, TweenInfo.new(duration, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut), goal)
	tween.Completed:Once(function(state)
		if state == Enum.PlaybackState.Completed and swapToken == token then
			c.Enabled = cloud.Enabled
		end
	end)
	cloudTween = tween
	tween:Play()
end

function LightingRig.build()
	-- The default place template ships blur effects we don't want.
	for _, child in Lighting:GetChildren() do
		if child:IsA("DepthOfFieldEffect") or child:IsA("BlurEffect") then
			child:Destroy()
		end
	end
	Lighting.ClockTime = 15.2
	-- Keep at 30: ENV's skyboxes are painted for the sun path at this latitude.
	Lighting.GeographicLatitude = 30
	Lighting.GlobalShadows = true

	ensureEffect("Atmosphere", "Atmosphere")
	ensureEffect("BloomEffect", "Bloom")
	ensureEffect("SunRaysEffect", "SunRays")
	ensureEffect("ColorCorrectionEffect", "Grade")
	snapshotSky()
end

return LightingRig
