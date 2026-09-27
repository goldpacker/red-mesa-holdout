--!strict
-- Particle light for a low sun (VFX-4), shared by the dust effects (motion
-- dust in VehicleFxDust, sand streamers, dust devils, storm dust).
--
-- Roblox lights a particle with the full sun whichever way the camera sees
-- it and never shadows it (checked in Studio: a dust emitter in the mesa's
-- shadow at sunset rendered exactly as bright as one in the sun), while the
-- ground it rolls over gets only sin(elevation) of that sun. The tints were
-- tuned by day (sun ~42 degrees up); at sunset (11 degrees) the same pale
-- dust burns out to white, in the sun and in the mesa's long shadow alike:
-- backlit tank dust hid the tank for seconds in AD-2's sunset captures.
-- ParticleEmitter.Brightness does nothing visible on lit particles (Studio
-- A/B), so the fix scales the particle Color:
--   sunK()        colour multiplier for the sun's height: 1 at the day
--                 reference, 0.64 at LateAfternoon (17 degrees), ~0.51 at
--                 Sunset (11 degrees).
--   shadowed(p)   the terrain blocks the sun at p (mesa shadow, canyon
--                 walls): such dust gets SHADOW_K of that.
--   backlit(p)    0..1, how directly the camera looks toward the sun through
--                 p; dust there is thinned (forward scatter is Look's glow on
--                 the dust bands, not something to hide an enemy with).
--   dust(p)       (colour multiplier, extra transparency 0..1) for dust at p.
--   scale(c, k)   c with each channel times k.
-- Calibrated in Studio at Sunset: x0.5 in the sun and x0.4 in the shadow
-- sit a little paler than the ground around them (x1 was white, x0.3 in the
-- sun already darker than the ground, and a dust devil at x0.3 in the mesa's
-- shadow read as a smoke column).
-- Studio A/B: Workspace attribute FxDustLightOff = true returns (1, 0).

local Lighting = game:GetService("Lighting")
local Workspace = game:GetService("Workspace")

local Light = {}

local SIN_REF = math.sin(math.rad(40)) -- the day reference (Afternoon: 41.7 degrees)
local MIN_K = 0.4 -- floor of sunK
local K_POWER = 0.56 -- (sin 11.2 / sin 40) ^ 0.56 = 0.51 at Sunset
local SHADOW_K = 0.8 -- share left in the terrain's shadow (sky light only; 0.6 read as smoke)
local BACKLIT_THIN = 0.5 -- extra transparency looking straight into a low sun
local SHADOW_REACH = 1600 -- studs toward the sun a shadow ray checks

local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Include

local cachedAt = -1
local cachedSun = Vector3.new(0, 1, 0)

-- Unit vector toward the sun (cached per frame-ish).
function Light.sun(): Vector3
	local now = os.clock()
	if now - cachedAt > 0.25 then
		cachedAt = now
		cachedSun = Lighting:GetSunDirection()
	end
	return cachedSun
end

function Light.off(): boolean
	return Workspace:GetAttribute("FxDustLightOff") == true
end

-- Colour multiplier for the sun's height (1 by day, lower toward sunset).
function Light.sunK(): number
	local s = math.max(Light.sun().Y, 0)
	return math.clamp((s / SIN_REF) ^ K_POWER, MIN_K, 1)
end

-- How far below full day light the sun is (0 high sun .. 1 at the floor).
function Light.lowSun(): number
	return math.clamp((1 - Light.sunK()) / (1 - MIN_K), 0, 1)
end

function Light.shadowed(p: Vector3): boolean
	local sun = Light.sun()
	if sun.Y <= 0.01 then
		return true
	end
	params.FilterDescendantsInstances = { Workspace.Terrain }
	return Workspace:Raycast(p + Vector3.new(0, 3, 0), sun * SHADOW_REACH, params) ~= nil
end

function Light.backlit(p: Vector3): number
	local camera = Workspace.CurrentCamera
	local view = p - camera.CFrame.Position
	if view.Magnitude < 1 then
		view = camera.CFrame.LookVector
	end
	return math.max(view.Unit:Dot(Light.sun()), 0)
end

-- (colour multiplier, extra transparency) for dust at `p`. `inShadow`
-- may be passed when the caller already knows it (cached ray).
function Light.dust(p: Vector3, inShadow: boolean?): (number, number)
	if Light.off() then
		return 1, 0
	end
	local k = Light.sunK()
	local shade = if inShadow == nil then Light.shadowed(p) else inShadow
	if shade then
		k *= SHADOW_K
	end
	local b = Light.backlit(p)
	local thin = BACKLIT_THIN * b * b * Light.lowSun()
	return k, thin
end

function Light.scale(c: Color3, k: number): Color3
	return Color3.new(c.R * k, c.G * k, c.B * k)
end

-- `s` with every opacity scaled by (1 - k): k = 0 unchanged, 1 invisible.
function Light.thinner(s: NumberSequence, k: number): NumberSequence
	if k <= 0 then
		return s
	end
	local keys = table.create(#s.Keypoints)
	for i, kp in s.Keypoints do
		keys[i] = NumberSequenceKeypoint.new(kp.Time, 1 - (1 - kp.Value) * (1 - k), kp.Envelope)
	end
	return NumberSequence.new(keys)
end

return Light
