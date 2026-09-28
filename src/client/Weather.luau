--!strict
-- Weather and life (VFX-4; docs/AIRDROP_ENVIRONMENT_PLAN.md §2, GAME_SPEC
-- §13 "Weather and life"): the client-only layer that makes the basin feel
-- alive, driven by the shared wind (shared/Wind):
--   WeatherStreamers  sand streaming low over the ground in travelling
--                     gusts, off dune crests and off the canyon rims
--   WeatherDevils     a few dust devils wandering the basin
--   WeatherSmoke      thin smoke columns from ENV's burnt-out hulks
--   Birds             vultures circling high; small flocks that scatter
--                     from explosions
--   DustStorm         dust storms on the waves whose Config.Waves entry has
--                     a `weather.storm` (the wall of dust, the storm body,
--                     Lighting.StormAmount for Look's storm lighting)
-- The emplacement's radio whip and camo net (HS, client/EmplacementFxWind)
-- lean with the same wind direction.
-- Visual only: nothing here touches gameplay, collisions or raycasts
-- (every part is CanQuery/CanCollide/CanTouch false, emitters sit on
-- world attachments in Terrain or on invisible carrier parts).
--
-- One render-step loop feeds each module a Frame (wind, camera, storm).
-- Budget: every emitter is on EffectsLod's zoom-corrected distance LOD and
-- each module has a hard cap (see the module headers); textures are the
-- existing flipbooks (DustDrift, SmokeDark) and the VfxBirds meshes.
--
-- Studio switches (Workspace attributes):
--   WeatherOff = true   no weather at all (perf A/B; storms' lighting too)
--   WeatherLive = true  keep weather running during a staged beauty shot
--                       (otherwise it is cleared and hidden for the shot:
--                       tools/qa/BEAUTY.md §6)
-- DustStorm has its own test hooks (see that module).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local FrameProfile = require(script.Parent.FrameProfile)

local Wind = require(ReplicatedStorage.Shared.Wind)

local Weather = {}

local REF_HALF_FOV = math.tan(math.rad(35)) -- turret view FOV 70 (EffectsLod)
local IS_STUDIO = RunService:IsStudio()

export type Frame = {
	t: number, -- server time
	dt: number,
	wind: Vector3, -- flat drift velocity (studs/s), shared/Wind
	strength: number,
	gust: number,
	dir: Vector3, -- flat unit downwind
	cam: CFrame,
	camPos: Vector3,
	look: Vector3,
	fov: number, -- vertical FOV (degrees)
	zoom: number, -- tan(fov/2) / tan(35 degrees): 1 turret, ~0.41 gunsight
	aspect: number,
	storm: number, -- storm particle weight 0..1 (DustStorm)
	density: number, -- ambient weather density 0..1 (thins in busy fights)
}

export type Module = {
	start: (() -> ())?,
	step: (frame: Frame) -> (),
	setActive: ((active: boolean) -> ())?,
}

local modules: { Module } = {}
local density: () -> number
local emitters: { [ParticleEmitter]: boolean } = {}
local paused = false
local active = true
local folder: Folder? = nil

-- The folder for weather parts (birds, carriers), client-only.
function Weather.folder(): Folder
	if folder then
		return folder
	end
	local f = Workspace:FindFirstChild("WeatherFx")
	if not (f and f:IsA("Folder")) then
		f = Instance.new("Folder")
		f.Name = "WeatherFx"
		f.Parent = Workspace
	end
	folder = f :: Folder
	return folder :: Folder
end

-- An invisible, non-interacting anchored part (a carrier for box-shaped
-- emitters: ParticleEmitter.Shape needs a BasePart parent).
function Weather.carrier(name: string, size: Vector3): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Transparency = 1
	p.Size = size
	p.Parent = Weather.folder()
	return p
end

-- A world Attachment in Terrain.
function Weather.attachment(name: string): Attachment
	local a = Instance.new("Attachment")
	a.Name = name
	a.Parent = Workspace.Terrain
	return a
end

-- Emitters registered here freeze (TimeScale 0) while the weather pauses.
function Weather.register(e: ParticleEmitter?)
	if not e then
		return
	end
	emitters[e] = true
	e.TimeScale = if paused then 0 else 1
	e.Destroying:Connect(function()
		emitters[e] = nil
	end)
end

function Weather.paused(): boolean
	return paused
end

function Weather.active(): boolean
	return active
end

local function beautyPaused(): boolean
	return IS_STUDIO and Workspace:GetAttribute("BeautyShot") ~= nil and Workspace:GetAttribute("WeatherLive") ~= true
end

-- A staged beauty shot (tools/qa/BEAUTY.md §6) shows no weather at all, so
-- the sets stay deterministic and comparable with earlier ones: particles
-- are cleared and frozen, and the WeatherFx folder (birds, wall beams,
-- carriers) is taken out of the world until the shot ends.
local function setPaused(value: boolean)
	if value == paused then
		return
	end
	paused = value
	for e in emitters do
		e.TimeScale = if value then 0 else 1
		if value then
			e:Clear()
		end
	end
	local f = Weather.folder()
	f.Parent = if value then nil else Workspace
end

local function setActive(value: boolean)
	if value == active then
		return
	end
	active = value
	for _, m in modules do
		if m.setActive then
			m.setActive(value)
		end
	end
	if not value then
		-- Off means off at once (a clean A/B): drop the particles in flight.
		for e in emitters do
			e:Clear()
		end
	end
end

-- Screen-space test: is world point `p` within the view (with `margin`
-- extra on each side, in fractions of the half-extent)?
function Weather.inView(frame: Frame, p: Vector3, margin: number): boolean
	local rel = frame.cam:PointToObjectSpace(p)
	if rel.Z > -1 then
		return false
	end
	local halfV = math.tan(math.rad(frame.fov) * 0.5)
	local halfH = halfV * frame.aspect
	local x = rel.X / -rel.Z
	local y = rel.Y / -rel.Z
	return math.abs(x) <= halfH * (1 + margin) and math.abs(y) <= halfV * (1 + margin)
end

-- Ambient density: the GPU budget is tightest in the busiest waves
-- (wave 9 at sunset sits at ~5.5-6 of 6 ms), so the ambient layers
-- (streamers, crests, rim plumes, devils, wreck smoke) thin out as the
-- number of live enemies grows: 1 up to DENSE_FROM enemies, down to
-- DENSITY_MIN at DENSE_TO. It eases over a few seconds. Storm particles are
-- not thinned (the storm waves are 3 and 7, not the busiest).
local DENSE_FROM, DENSE_TO, DENSITY_MIN = 4, 12, 0.35
local densityNow = 1
local densityDue = 0
local enemiesFolder: Instance? = nil
density = function(): number
	local now = os.clock()
	if now >= densityDue then
		densityDue = now + 0.5
		if not (enemiesFolder and enemiesFolder.Parent) then
			enemiesFolder = Workspace:FindFirstChild("Enemies")
		end
		local n = if enemiesFolder then #enemiesFolder:GetChildren() else 0
		local goal = 1 - (1 - DENSITY_MIN) * math.clamp((n - DENSE_FROM) / (DENSE_TO - DENSE_FROM), 0, 1)
		densityNow += math.clamp(goal - densityNow, -0.08, 0.08)
		if IS_STUDIO then
			Workspace:SetAttribute("WeatherDensity", math.round(densityNow * 100) / 100)
		end
	end
	return densityNow
end

local lastT = 0
local function step(dt: number)
	local camera = Workspace.CurrentCamera
	if not camera then
		return
	end
	setPaused(beautyPaused())
	setActive(not (IS_STUDIO and Workspace:GetAttribute("WeatherOff") == true))
	if paused then
		return
	end
	local t = Workspace:GetServerTimeNow()
	local wind, strength, gust = Wind.at(t)
	local cf = camera.CFrame
	local vp = camera.ViewportSize
	local frame: Frame = {
		t = t,
		dt = math.clamp(if lastT > 0 then t - lastT else dt, 0, 0.25),
		wind = wind,
		strength = strength,
		gust = gust,
		dir = if wind.Magnitude > 1e-3 then wind.Unit else Wind.DIRECTION,
		cam = cf,
		camPos = cf.Position,
		look = cf.LookVector,
		fov = camera.FieldOfView,
		zoom = math.tan(math.rad(camera.FieldOfView) * 0.5) / REF_HALF_FOV,
		aspect = if vp.Y > 0 then vp.X / vp.Y else 1.1,
		storm = Weather.stormParticles(),
		density = density(),
	}
	lastT = t
	for _, m in modules do
		m.step(frame)
	end
end

-- Storm particle weight (set by DustStorm; 0 when there is no storm).
local stormWeight = 0
function Weather.stormParticles(): number
	return if active then stormWeight else 0
end
function Weather.setStormParticles(value: number)
	stormWeight = math.clamp(value, 0, 1)
end

function Weather.start()
	local list = {
		require(script.Parent.DustStorm) :: any,
		require(script.Parent.WeatherStreamers) :: any,
		require(script.Parent.WeatherDevils) :: any,
		require(script.Parent.WeatherSmoke) :: any,
		require(script.Parent.Birds) :: any,
	}
	for _, m in list do
		table.insert(modules, m :: Module)
		if m.start then
			m.start()
		end
	end
	RunService:BindToRenderStep("Weather", Enum.RenderPriority.Last.Value - 2, FrameProfile.wrap("Weather", step))
end

return Weather
