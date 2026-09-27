--!strict
-- Smoke from old wrecks (VFX-4): a thin smoke column rising from each of
-- ENV-4's burnt-out hulks that asks for one, bending and drifting with the
-- wind (shared/Wind; gusts lean it over further).
--
-- Contract with ENV-4 (server/ConflictDressing): hulks are Models under
-- Battlefield.ConflictDressing.Hulks with attribute `Smoke` ("light" |
-- "none") and an Attachment "SmokeAnchor" at the engine deck. "light" gets
-- one thin column; anything else none.
-- Look: the soft DustDrift sheet tinted smoke grey (a smouldering wreck, not
-- burning fuel), thin, rising and leaning downwind; LOD via EffectsLod.track.
-- (SmokeDark read as a trail of brown discs lying on the ground from the
-- mesa: Studio.)

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Effects = require(script.Parent.Effects)
local Light = require(script.Parent.EffectsLight)
local Lod = require(script.Parent.EffectsLod)
local Weather = require(script.Parent.Weather)
local Wind = require(ReplicatedStorage.Shared.Wind)

local Smoke = {}

local RATE = 4 -- particles/s per column, close up
local CUTOFF = 2800
local SMOKE = Color3.fromRGB(92, 86, 80) -- grey smoke, darker than the sand it rises over
-- ~800+ studs out the haze lifts it to the sky's colour: much darker there
-- (lit grey vanished; this reads as a faint dark column in the gunsight)
local SMOKE_FAR = Color3.fromRGB(46, 43, 40)
local RISE = 1.4 -- studs/s^2 of buoyancy
local DRIFT = 0.6 -- x the wind velocity as acceleration
local UPDATE = 0.5

type Column = { e: ParticleEmitter, att: Attachment, at: Vector3, bright: number, tint: Color3 }
local columns: { [Model]: Column } = {}
local enabled = true
local due = 0

local function sizes(a: number, b: number, c: number, spread: number): NumberSequence
	return NumberSequence.new({
		NumberSequenceKeypoint.new(0, a, a * spread),
		NumberSequenceKeypoint.new(0.5, b, b * spread),
		NumberSequenceKeypoint.new(1, c, c * spread),
	})
end

local function add(model: Model)
	if columns[model] or model:GetAttribute("Smoke") ~= "light" then
		return
	end
	local anchor = model:FindFirstChild("SmokeAnchor", true)
	if not (anchor and anchor:IsA("Attachment")) then
		return
	end
	-- ENV-4 sets the anchor's WorldPosition before parenting it to the hulk's
	-- root, so it ends up offset by the root's frame (Studio: the smoke rose
	-- 100-300 studs from its hulk). Use the anchor only when it lies within
	-- the hulk's box; otherwise ENV's intended point: the box centre lifted
	-- 35 % of its height (ConflictDressing).
	local cf, size = model:GetBoundingBox()
	local at = anchor.WorldPosition
	local rel = cf:PointToObjectSpace(at)
	if math.abs(rel.X) > size.X * 0.6 or math.abs(rel.Y) > size.Y * 0.6 or math.abs(rel.Z) > size.Z * 0.6 then
		at = cf.Position + Vector3.new(0, size.Y * 0.35, 0)
	end
	local att = Weather.attachment("WreckSmoke")
	att.CFrame = CFrame.new(at)
	-- Far columns (the convoy at ~870 studs) sink into the depth haze: denser
	-- and wider there (Studio: at the near values the far column was
	-- invisible; a magenta probe showed it was drawn).
	local far = math.clamp((Vector2.new(at.X, at.Z).Magnitude - 300) / 500, 0, 1)
	local k = 1 + 0.6 * far
	local tint = SMOKE:Lerp(SMOKE_FAR, far)
	local e = Effects.emitter(att, "DustDrift", 0, {
		Name = "WreckSmoke",
		Size = sizes(3 * k, 11 * k, 22 * k, 0.25),
		Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 1),
			NumberSequenceKeypoint.new(0.1, 0.5 - 0.2 * far),
			NumberSequenceKeypoint.new(0.5, 0.66 - 0.2 * far),
			NumberSequenceKeypoint.new(1, 1),
		}),
		Color = ColorSequence.new(tint),
		Lifetime = NumberRange.new(10, 13),
		Speed = NumberRange.new(4, 6),
		SpreadAngle = Vector2.new(6, 6),
		Drag = 0.3,
		EmissionDirection = Enum.NormalId.Top,
		Acceleration = Wind.DIRECTION * Wind.SPEED * DRIFT + Vector3.new(0, RISE, 0),
		RotSpeed = NumberRange.new(-8, 8),
		ZOffset = 1,
		LightEmission = 0,
		LightInfluence = 1,
	})
	if not e then
		att:Destroy()
		return
	end
	e.Rate = RATE
	e.Enabled = enabled
	Weather.register(e)
	Lod.track(e, CUTOFF)
	columns[model] = { e = e, att = att, at = at, bright = -1, tint = tint }
	model.Destroying:Connect(function()
		local c = columns[model]
		if c then
			columns[model] = nil
			c.e.Enabled = false
			task.delay(12, function()
				c.att:Destroy()
			end)
		end
	end)
end

local function watch(hulks: Instance)
	for _, m in hulks:GetChildren() do
		if m:IsA("Model") then
			add(m)
		end
	end
	hulks.ChildAdded:Connect(function(m)
		if m:IsA("Model") then
			task.defer(add, m)
		end
	end)
end

function Smoke.start()
	task.spawn(function()
		local battlefield = Workspace:WaitForChild("Battlefield", 60)
		local dressing = battlefield and battlefield:WaitForChild("ConflictDressing", 60)
		local hulks = dressing and dressing:WaitForChild("Hulks", 60)
		if hulks then
			watch(hulks)
		end
	end)
end

function Smoke.setActive(value: boolean)
	enabled = value
	for _, c in columns do
		c.e.Enabled = value
	end
end

function Smoke.step(frame: Weather.Frame)
	local now = os.clock()
	if now < due then
		return
	end
	due = now + UPDATE
	local gain = DRIFT * (1 + 1.5 * frame.storm)
	for _, c in columns do
		Lod.setRate(c.e, RATE * (0.5 + 0.5 * frame.density))
		c.e.Acceleration = frame.wind * gain + Vector3.new(0, RISE, 0)
		-- smoke is darker than dust already: half the low-sun darkening
		local k = math.sqrt(Light.sunK())
		if math.abs(k - c.bright) > 0.03 then
			c.bright = k
			c.e.Color = ColorSequence.new(Light.scale(c.tint, k))
		end
	end
end

return Smoke
