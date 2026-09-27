--!strict
-- Dust storms (VFX-4): on a wave whose Config.Waves entry has
--   weather = { storm = { at = <s>, hold = <s>, amount = <0..1> } }
-- a wall of dust rolls in across the basin, reaches the outpost `at`
-- seconds into the wave, the storm holds for `hold` seconds, then clears
-- within CLEAR seconds. `amount` caps the peak (readability).
--
-- Two halves (docs/FACELIFT_TEAM.md Update 2, "Storms"):
--   * lighting: Look's client/PostFxStorm blends toward the storm look by
--     Lighting.StormAmount, which only this module writes (client-local:
--     the storm is a client visual, like the rest of the weather);
--   * particles and the wall, here:
--       Wall   vertical Beam curtains (Look's dust-band texture, no new
--              map) in two layers on an arc around the outpost, closing in
--              at FRONT_SPEED, following the ground in PIECES pieces: the
--              dark base and the paler sunlit top;
--       Crest  big soft DustDrift billows along the front, only within
--              CREST_RANGE (Roblox stops drawing particles ~1,200-1,700
--              studs out: a sprite at 1,216 drew, one at 1,740 did not);
--       Body   pale veils of dust streaming downwind high over the basin
--              ahead of the camera during the storm (above the enemies);
--       Near   wide, flat sand streaks blowing past the gun (not through
--              the gunsight);
--     plus the storm weight (Weather.setStormParticles) that thickens the
--     sand streamers, stops dust devils, grounds the vultures, and the
--     storm wind (shared/Wind.setStorm: the wind turns to the storm's
--     direction and blows up to STORM_GAIN x harder).
-- The storm blows along STORM_DIR, the mean wind turned toward the mesa
-- (the storm wind); the wall is an arc at the front's distance from the
-- outpost across the upwind side of the view (VFX-4 fix 1: a straight wall
-- line seen obliquely rose to a sharp tent-shaped apex at its nearest
-- point; on the arc every piece is at the same distance, so the top edge
-- is the billow alone).
-- The radar and HUD are untouched (they draw over everything).
--
-- Envelope along the front's position s (studs from the outpost, negative
-- while it approaches; s = 0 when it arrives): StormAmount rises a little while the
-- wall is still far (it covers the low sun), most of the way over the last
-- 700 studs, holds, then clears. If the wave ends early (clear, defeat) the
-- storm clears over CLEAR_FAST seconds.
--
-- Studio test hooks (Workspace attributes, Client datamodel):
--   WeatherStormTest = <hold s>   run a storm now: the wall appears at once
--                                 and arrives FRONT_TIME seconds later
--                                 (WeatherStormPeak = amount, default 1)
--   WeatherStormForce = <0..1>    hold a static storm at that amount (no
--                                 wall); remove it to clear
--   WeatherStormFrontAt = <s>     hold the wall at s (-2100..0 studs along
--                                 its path), with the StormAmount it has there
--   published: WeatherStorm = "amount front-s phase"

local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Effects = require(script.Parent.Effects)
local GameState = require(script.Parent.GameState)
local Light = require(script.Parent.EffectsLight)
local Weather = require(script.Parent.Weather)
local Wind = require(ReplicatedStorage.Shared.Wind)

local Storm = {}

local IS_STUDIO = RunService:IsStudio()
local FRONT_SPEED = 55 -- studs/s (a haboob front, ~15 m/s)
local S_START = -2100 -- where the wall appears (upwind of the outpost)
local FRONT_TIME = -S_START / FRONT_SPEED -- ~38 s from appearing to arrival
local CLEAR = 16 -- s to clear after the hold
local CLEAR_FAST = 6 -- s to clear when the wave ends early
local STORM_GAIN = 2.6 -- wind strength x at full storm

-- Readability cap per time-of-day preset (GAME_SPEC §13: weather never hides
-- an enemy at its engagement range; docs/ART_BIBLE.md §6, >= 3:1). Every
-- storm is clamped to this whatever Config.Waves asks for, so a later edit
-- of the wave table can't break the rule. Measured in the gunsight (shot 3,
-- FOV 32: infantry 230-276 studs, buggy 312, tank 414) with
-- tools/vfx/qa/readability.py + enemyboxes.client.luau, storm particles on
-- (VFX-4 report, "Readability at the storm peak"; qa/beauty/vfx-4/readability/):
--   Afternoon      1.0 -> min 3.17 (tank 414)
--   Sunset         0.8 -> min 3.00 (infantry 230; lighting alone also 3.00)
--                  1.0 -> 2.80-2.92: too dark
--   LateAfternoon  none: Look's storm lighting alone puts the tank at
--                  2.81 / 2.88 / 2.83 at 0.6 / 0.8 / 1 (3.83 without a storm)
-- Re-run the probe before raising any of these. Unknown presets get no storm.
local PRESET_CAP: { [string]: number } = {
	Afternoon = 1,
	LateAfternoon = 0,
	Sunset = 0.8,
}
Storm.PRESET_CAP = PRESET_CAP

-- The cap for the preset now on screen (Workspace.TimeOfDay, TimeOfDay's
-- preset name). Studio only: Workspace.WeatherStormUncapped = true lifts it
-- for measurements (e.g. probing a storm at 1 at Sunset).
local function cap(): number
	if IS_STUDIO and Workspace:GetAttribute("WeatherStormUncapped") == true then
		return 1
	end
	local name = Workspace:GetAttribute("TimeOfDay")
	return if type(name) == "string" then PRESET_CAP[name] or 0 else 0
end

-- The storm's travel direction: the mean wind turned 35 degrees toward +Z.
local STORM_DIR = (function(): Vector3
	local d = Wind.DIRECTION
	local yaw = math.atan2(d.Z, d.X) + math.rad(35)
	return Vector3.new(math.cos(yaw), 0, math.sin(yaw))
end)()

-- Wall bands: `back` studs behind the front, `height` tall, `sink` of the
-- height below the ground (the texture's soft lower edge is buried, so the
-- dense core sits on the floor), `opacity` peak, colour key.
-- The wall is an arc of radius (front distance + back) around the outpost,
-- from ARC_FROM to ARC_TO (world yaw, atan2(z, x); the turret's forward -Z
-- is -90 degrees, its left toward -180): 85 degrees left of forward to 45
-- right, centred toward the upwind side. PIECES chords per layer share their
-- end points, so each layer is one continuous ribbon over the ground; each
-- piece's TextureLength is its own chord length, so the texture repeats a
-- whole number of times per piece and runs on across the joints. Only
-- pieces in view are drawn (each Beam is a draw call).
-- Budget (fix 1, wave-9 Sunset paired GPU A/B, wall held at 1,100 studs):
-- 3 layers x 12 pieces over 150 degrees (27 beams in view) cost +0.28 ms,
-- the arc spanning the horizon overdraws a wide band; 2 layers x 10 pieces
-- over 130 degrees (16 in view) measured +0.03 / +0.19 in two runs.
local ARC_FROM = math.rad(-175)
local ARC_TO = math.rad(-45)
local PIECES = 10
local LAYERS = {
	{ back = 0, height = 340, sink = 0.35, opacity = 1, tint = "base" },
	{ back = 220, height = 820, sink = 0.28, opacity = 0.85, tint = "top" },
}
local CREST_RANGE = 1150 -- crest billows only this close (particles cull farther)
local SLOTS = 26
local CREST_RATE = 1 -- per slot, particles/s
local BOUNDS = { minX = -2200, maxX = 2200, minZ = -2800, maxZ = 900 }
local BODY_RATE = 24 -- particles/s at full storm
local NEAR_RATE = 45
local STREAK = Color3.fromRGB(240, 214, 188) -- pale sand (as client/WeatherStreamers)
local UPDATE = 0.2

-- Colours per preset. Beams are unlit (these are screen colours, before
-- Look's storm haze over them); `crest` is a lit particle tint (scaled by
-- EffectsLight's sun factor).
type Palette = { base: Color3, body: Color3, top: Color3, crest: Color3 }
local COLORS: { [string]: Palette } = {
	Afternoon = { base = Color3.fromRGB(122, 92, 66), body = Color3.fromRGB(156, 120, 88), top = Color3.fromRGB(196, 164, 128), crest = Color3.fromRGB(176, 140, 104) },
	LateAfternoon = { base = Color3.fromRGB(118, 80, 56), body = Color3.fromRGB(152, 106, 74), top = Color3.fromRGB(200, 150, 106), crest = Color3.fromRGB(180, 128, 92) },
	Sunset = { base = Color3.fromRGB(96, 60, 46), body = Color3.fromRGB(130, 82, 60), top = Color3.fromRGB(186, 118, 84), crest = Color3.fromRGB(172, 110, 82) },
}

type Schedule = { at: number, hold: number, amount: number }
local schedule: Schedule? = nil
local forced: number? = nil -- WeatherStormForce
local clearFrom: { t: number, from: number }? = nil
local amountNow = 0
local frontS: number? = nil
local written = -1

type Band = { beam: Beam, a0: Attachment, a1: Attachment, layer: number, k: number, y0: number, y1: number }
local bands: { Band } = {}
type Slot = { att: Attachment, index: number, e: ParticleEmitter }
local slots: { Slot } = {}
local body: ParticleEmitter? = nil
local bodyPart: BasePart? = nil
local near: ParticleEmitter? = nil
local nearPart: BasePart? = nil
local due = 0
local groundDue = 0

local function smooth(u: number): number
	u = math.clamp(u, 0, 1)
	return u * u * (3 - 2 * u)
end

local function now(): number
	return Workspace:GetServerTimeNow()
end

---------------------------------------------------------------------------
-- Envelope
---------------------------------------------------------------------------

local frontHold: number? = nil -- WeatherStormFrontAt (Studio)

-- StormAmount and wall weight for the front at s (s < 0: approaching).
local function approach(s: number, peak: number): (number, number)
	local amount = peak * (0.18 * smooth((s + 1700) / 1000) + 0.82 * smooth((s + 700) / 700))
	-- the wall fades in on the horizon and dissolves into the haze from
	-- 1,000 studs out, gone by ~650 (nearer, the bands read as flat veils
	-- with hard edges over the cliffs: Studio)
	local front = smooth((s - S_START) / 400) * (1 - smooth((s + 1000) / 350))
	return amount, front
end

-- (StormAmount, front position s or nil, wall weight 0..1)
local function envelope(t: number): (number, number?, number)
	if frontHold then
		local amount, front = approach(frontHold, 1)
		return amount, frontHold, front
	end
	if forced then
		return forced, nil, 0
	end
	local amount, s, front = 0, nil, 0
	local sch = schedule
	if sch then
		local fs = FRONT_SPEED * (t - sch.at)
		if fs < 0 then
			amount = approach(fs, sch.amount)
		elseif t <= sch.at + sch.hold then
			amount = sch.amount
		else
			amount = sch.amount * (1 - smooth((t - sch.at - sch.hold) / CLEAR))
			if t > sch.at + sch.hold + CLEAR then
				schedule = nil
			end
		end
		if fs >= S_START and fs <= 0 then
			s = fs
			local _, w = approach(fs, sch.amount)
			front = w
		end
	end
	local c = clearFrom
	if c then
		-- The storm was cut short (wave over, test storm removed): it
		-- fades from where it was, whatever the schedule said.
		local k = 1 - smooth((t - c.t) / CLEAR_FAST)
		amount = c.from * k
		front *= k
		if k <= 0 then
			clearFrom = nil
		end
	end
	return amount, s, front
end

local function clearNow()
	if amountNow > 0.001 then
		clearFrom = { t = now(), from = amountNow }
	end
	schedule = nil
end

---------------------------------------------------------------------------
-- Build
---------------------------------------------------------------------------

local function sizes(a: number, b: number, c: number, spread: number): NumberSequence
	return NumberSequence.new({
		NumberSequenceKeypoint.new(0, a, a * spread),
		NumberSequenceKeypoint.new(0.5, b, b * spread),
		NumberSequenceKeypoint.new(1, c, c * spread),
	})
end

local function fades(a: number, b: number): NumberSequence
	return NumberSequence.new({
		NumberSequenceKeypoint.new(0, 1),
		NumberSequenceKeypoint.new(0.15, a),
		NumberSequenceKeypoint.new(0.6, b),
		NumberSequenceKeypoint.new(1, 1),
	})
end

local function buildWall()
	local ok, assets = pcall(require, script.Parent.PostFxAssets)
	local texture = if ok and type(assets) == "table" then (assets :: any).searchlight_cone else nil
	for layer in LAYERS do
		for k = 1, PIECES do
			local a0 = Weather.attachment("StormWallA")
			local a1 = Weather.attachment("StormWallB")
			local beam = Instance.new("Beam")
			beam.Name = "StormWall"
			beam.Attachment0 = a0
			beam.Attachment1 = a1
			-- A vertical curtain, not camera-facing: with FaceCamera the long
			-- pieces twisted into bowties (Studio). With FaceCamera off the
			-- width lies along the attachments' Y axis (Studio: identity
			-- attachments give a vertical band), and from the turret the
			-- front faces the camera.
			beam.FaceCamera = false
			beam.Segments = 1
			if texture then
				beam.Texture = texture
			end
			beam.TextureMode = Enum.TextureMode.Wrap
			beam.TextureLength = 400
			beam.TextureSpeed = 0
			beam.LightEmission = 0
			beam.LightInfluence = 0
			beam.Width0 = LAYERS[layer].height
			beam.Width1 = LAYERS[layer].height
			beam.Enabled = false
			beam.Parent = Weather.folder()
			table.insert(bands, { beam = beam, a0 = a0, a1 = a1, layer = layer, k = k, y0 = 2, y1 = 2 })
		end
	end
	for index = 1, SLOTS do
		local att = Weather.attachment("StormCrest")
		local e = Effects.emitter(att, "DustDrift", 0, {
			Name = "StormCrest",
			Size = sizes(160, 240, 290, 0.2),
			Transparency = fades(0.4, 0.5),
			Lifetime = NumberRange.new(6, 8),
			Speed = NumberRange.new(FRONT_SPEED - 3, FRONT_SPEED + 4),
			SpreadAngle = Vector2.new(12, 12),
			EmissionDirection = Enum.NormalId.Top,
			Acceleration = Vector3.new(0, 3, 0),
			Rotation = NumberRange.new(0, 360),
			RotSpeed = NumberRange.new(-6, 6),
			ZOffset = 10,
			LightEmission = 0,
			LightInfluence = 1,
		})
		if e then
			e.Enabled = true
			Weather.register(e)
			table.insert(slots, { att = att, index = index, e = e })
		else
			att:Destroy()
		end
	end
end

local function buildBody()
	bodyPart = Weather.carrier("StormBody", Vector3.new(1700, 1700, 180))
	body = Effects.emitter(bodyPart :: BasePart, "DustDrift", 0, {
		Name = "StormBody",
		Size = sizes(50, 90, 120, 0.3),
		Transparency = fades(0.74, 0.72),
		Lifetime = NumberRange.new(6, 8),
		Speed = NumberRange.new(24, 36),
		SpreadAngle = Vector2.new(10, 10),
		Drag = 0.15,
		EmissionDirection = Enum.NormalId.Top,
		Shape = Enum.ParticleEmitterShape.Box,
		ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume,
		RotSpeed = NumberRange.new(-10, 10),
		Rotation = NumberRange.new(0, 360),
		ZOffset = 4,
		LightEmission = 0,
		LightInfluence = 1,
	})
	nearPart = Weather.carrier("StormNear", Vector3.new(260, 260, 40))
	near = Effects.emitter(nearPart :: BasePart, "DustDrift", 0, {
		Name = "StormNear",
		Size = sizes(10, 20, 26, 0.3),
		Transparency = fades(0.55, 0.55),
		Squash = NumberSequence.new(-2), -- wide, flat streaks (Squash < 0 widens)
		Lifetime = NumberRange.new(1.2, 1.8),
		Speed = NumberRange.new(55, 75),
		SpreadAngle = Vector2.new(4, 6),
		EmissionDirection = Enum.NormalId.Top,
		Shape = Enum.ParticleEmitterShape.Box,
		ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume,
		Rotation = NumberRange.new(-3, 3),
		RotSpeed = NumberRange.new(0),
		LightEmission = 0,
		LightInfluence = 1,
	})
	for _, e in { body, near } do
		if e then
			e.Enabled = true
			Weather.register(e)
		end
	end
end

---------------------------------------------------------------------------
-- Update
---------------------------------------------------------------------------

-- Frame with +Y along `d` (emission) and +X across it, at `p`.
local function windFrame(p: Vector3, d: Vector3): CFrame
	local across = Vector3.yAxis:Cross(d)
	across = if across.Magnitude > 1e-3 then across.Unit else Vector3.xAxis
	return CFrame.fromMatrix(p, across, d.Unit)
end

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include

local function groundY(x: number, z: number): number
	groundParams.FilterDescendantsInstances = { Workspace.Terrain }
	local hit = Workspace:Raycast(Vector3.new(x, 800, z), Vector3.new(0, -1000, 0), groundParams)
	return if hit then hit.Position.Y else 2
end

local function palette(): Palette
	local name = Workspace:GetAttribute("TimeOfDay")
	return COLORS[if type(name) == "string" and COLORS[name] then name else "Afternoon"]
end

local function inBounds(q: Vector3): boolean
	return q.X > BOUNDS.minX and q.X < BOUNDS.maxX and q.Z > BOUNDS.minZ and q.Z < BOUNDS.maxZ
end

-- Point j (0..PIECES) of the arc of radius r, flat (y = 0).
local function arcPoint(r: number, j: number): Vector3
	local yaw = ARC_FROM + (ARC_TO - ARC_FROM) * j / PIECES
	return Vector3.new(math.cos(yaw) * r, 0, math.sin(yaw) * r)
end

-- Height factor of a layer at arc joint j (~0.72..1.28), drifting slowly.
-- One smooth low-frequency term (a feature every ~3-4 pieces), so the
-- straight chords between joints add up to a rounded billowing top (fix 1:
-- a second term at a shorter wavelength than a piece zigzagged into peaks).
local function billow(j: number, layer: number, t: number): number
	return 1 + 0.28 * math.noise(j * 0.3 + layer * 3.7, t * 0.05, layer * 1.3)
end

-- Every frame: slide the bands with the front (their ground heights and
-- looks are refreshed four times a second).
local function placeWall(s: number?, weight: number, frame: Weather.Frame?)
	local on = s ~= nil and weight > 0.002
	local t = os.clock()
	local reground = t >= groundDue
	if reground then
		groundDue = t + 0.25
	end
	local colors = palette()
	for _, b in bands do
		if not on then
			if b.beam.Enabled then
				b.beam.Enabled = false
			end
			continue
		end
		local spec = LAYERS[b.layer]
		local r = -(s :: number) + spec.back
		local p0, p1 = arcPoint(r, b.k - 1), arcPoint(r, b.k)
		local mid = (p0 + p1) * 0.5
		local seen = frame == nil
			or Weather.inView(frame, Vector3.new(mid.X, b.y0 + spec.height * 0.25, mid.Z), 0.9)
			or Weather.inView(frame, Vector3.new(p0.X, b.y0 + spec.height * 0.25, p0.Z), 0.3)
			or Weather.inView(frame, Vector3.new(p1.X, b.y1 + spec.height * 0.25, p1.Z), 0.3)
		if not (inBounds(p0) or inBounds(p1)) or not seen then
			b.beam.Enabled = false
			continue
		end
		if reground or not b.beam.Enabled then
			b.y0 = groundY(p0.X, p0.Z)
			b.y1 = groundY(p1.X, p1.Z)
			-- the two outermost pieces at each end of the arc taper off
			local e0 = math.min(math.clamp((b.k - 1) / 2, 0, 1), math.clamp((PIECES - b.k + 1) / 2, 0, 1))
			local e1 = math.min(math.clamp(b.k / 2, 0, 1), math.clamp((PIECES - b.k) / 2, 0, 1))
			b.beam.Transparency = NumberSequence.new(1 - spec.opacity * weight * e0, 1 - spec.opacity * weight * e1)
			b.beam.Color = ColorSequence.new((colors :: any)[spec.tint])
			-- the texture repeats exactly once per chord: continuous at joints
			b.beam.TextureLength = (p1 - p0).Magnitude
		end
		-- Shared joints get the same height, so each layer's top is one
		-- continuous edge; the billow is smooth over several pieces.
		local h0 = spec.height * billow(b.k - 1, b.layer, t)
		local h1 = spec.height * billow(b.k, b.layer, t)
		b.beam.Width0 = h0
		b.beam.Width1 = h1
		b.a0.WorldPosition = Vector3.new(p0.X, b.y0 + h0 * (0.5 - spec.sink), p0.Z)
		b.a1.WorldPosition = Vector3.new(p1.X, b.y1 + h1 * (0.5 - spec.sink), p1.Z)
		b.beam.Enabled = true
	end
end

local function updateCrest(frame: Weather.Frame, s: number?, weight: number, sunK: number)
	local tint = ColorSequence.new(Light.scale(palette().crest, sunK))
	local face = LAYERS[1].height * (1 - LAYERS[1].sink)
	for _, slot in slots do
		local rate = 0
		if s and weight > 0.001 then
			local q = arcPoint(-s, (slot.index - 0.5) / SLOTS * PIECES)
			local flatDist = Vector2.new(q.X - frame.camPos.X, q.Z - frame.camPos.Z).Magnitude
			if inBounds(q) and flatDist > 300 and flatDist < CREST_RANGE and Weather.inView(frame, Vector3.new(q.X, face, q.Z), 0.5) then
				local y = groundY(q.X, q.Z)
				-- rolling in toward the outpost with the wall
				local inward = Vector3.new(-q.X, 0, -q.Z).Unit
				slot.att.CFrame = Effects.upFrame(Vector3.new(q.X, y + face * 0.8, q.Z), inward * FRONT_SPEED + Vector3.new(0, 5, 0))
				local edge = math.min(slot.index - 1, SLOTS - slot.index) / 3
				-- fade in with distance so the billows join the far bands smoothly
				local nearK = 1 - smooth((flatDist - (CREST_RANGE - 250)) / 250)
				rate = CREST_RATE * weight * math.clamp(edge, 0.2, 1) * nearK
			end
		end
		slot.e.Rate = rate
		slot.e.Color = tint
	end
end

local function updateBody(frame: Weather.Frame, amount: number, sunK: number)
	local look = Vector3.new(frame.look.X, 0, frame.look.Z)
	look = if look.Magnitude > 1e-3 then look.Unit else Vector3.new(0, 0, -1)
	local d = frame.dir
	local pale = ColorSequence.new(Light.scale(STREAK, sunK ^ 0.8))
	local b, bp = body, bodyPart
	if b and bp then
		-- Up in the air (y ~150-330), above the ground enemies: pale veils
		-- over a tank or a soldier lifted their darks below 3:1 (probe).
		local centre = Vector3.new(frame.camPos.X, 240, frame.camPos.Z) + look * 700 - d * 160
		bp.CFrame = windFrame(centre, d)
		b.Rate = BODY_RATE * amount
		local speed = 24 + 12 * frame.strength
		b.Speed = NumberRange.new(speed, speed * 1.4)
		-- pale veils of dust against the brown haze (the haze colour itself
		-- made them invisible)
		b.Color = pale
	end
	local n, np = near, nearPart
	if n and np then
		local centre = frame.camPos + look * 95 - d * 70 - Vector3.new(0, 14, 0)
		np.CFrame = windFrame(centre, d)
		-- None through the gunsight: magnified across the aim line, one
		-- streak over the 414-stud tank took it from 3.18:1 to 2.08:1
		-- (probe, Sunset, storm 1). Zoom is 1 in the turret view, 0.41
		-- aiming.
		local aimK = math.clamp((frame.zoom - 0.6) / 0.4, 0, 1)
		n.Rate = NEAR_RATE * amount * amount * aimK
		local speed = 50 + 18 * frame.strength
		n.Speed = NumberRange.new(speed, speed * 1.3)
		n.Color = pale
	end
end

local function publish(amount: number)
	local value = math.floor(amount * 1000 + 0.5) / 1000
	if math.abs(value - written) >= 0.004 or (value == 0 and written ~= 0) then
		written = value
		Lighting:SetAttribute("StormAmount", if value > 0 then value else nil)
	end
	Wind.setStorm(amount, STORM_DIR, STORM_GAIN)
end

---------------------------------------------------------------------------
-- Game flow and hooks
---------------------------------------------------------------------------

local function onPhase(phase: string?)
	if phase == "Wave" then
		local wave = GameState.get("Wave")
		local cfg = type(wave) == "number" and Config.Waves[wave]
		local weather = cfg and (cfg :: any).weather
		local storm = weather and weather.storm
		clearFrom = nil
		if storm and type(storm.at) == "number" then
			schedule = {
				at = now() + storm.at,
				hold = if type(storm.hold) == "number" then storm.hold else 18,
				amount = math.clamp(if type(storm.amount) == "number" then storm.amount else 1, 0, 1),
			}
		else
			clearNow()
		end
	else
		clearNow()
	end
end

local function testHooks()
	local test = Workspace:GetAttribute("WeatherStormTest")
	if type(test) == "number" and test > 0 then
		Workspace:SetAttribute("WeatherStormTest", nil)
		local peak = Workspace:GetAttribute("WeatherStormPeak")
		clearFrom = nil
		schedule = { at = now() + FRONT_TIME, hold = test, amount = math.clamp(if type(peak) == "number" then peak else 1, 0, 1) }
	end
	local h = Workspace:GetAttribute("WeatherStormFrontAt")
	frontHold = if type(h) == "number" then math.clamp(h, S_START, 0) else nil
	local f = Workspace:GetAttribute("WeatherStormForce")
	if type(f) == "number" then
		forced = math.clamp(f, 0, 1)
		clearFrom = nil
	elseif forced then
		forced = nil
		clearNow()
	end
end

local function quiet()
	for _, slot in slots do
		slot.e.Rate = 0
	end
	if body then
		body.Rate = 0
	end
	if near then
		near.Rate = 0
	end
	placeWall(nil, 0)
	amountNow = 0
	publish(0)
	Weather.setStormParticles(0)
end

function Storm.start()
	buildWall()
	buildBody()
	GameState.onChanged("Phase", onPhase)
	-- A staged beauty shot shows the preset's own look unless a test storm
	-- is forced (Look's PostFxPresets snaps StormAmount during shots too).
	Workspace:GetAttributeChangedSignal("BeautyShot"):Connect(function()
		if Workspace:GetAttribute("BeautyShot") ~= nil and Workspace:GetAttribute("WeatherStormForce") == nil then
			schedule = nil
			clearFrom = nil
			quiet()
		end
	end)
end

function Storm.setActive(value: boolean)
	if not value then
		quiet()
	end
end

function Storm.step(frame: Weather.Frame)
	if IS_STUDIO then
		testHooks()
	end
	if not Weather.active() then
		return
	end
	local amount, s, front = envelope(frame.t)
	-- The readability cap, whatever the wave table or a test asked for; a
	-- preset with no storm (cap 0) shows no wall either.
	local limit = cap()
	amount = math.min(amount, limit)
	if limit <= 0 then
		s, front = nil, 0
	end
	placeWall(s, front, frame)
	local t = os.clock()
	if t < due then
		return
	end
	due = t + UPDATE
	amountNow = amount
	frontS = s
	publish(amount)
	Weather.setStormParticles(amount)
	local sunK = Light.sunK()
	updateCrest(frame, s, front, sunK)
	updateBody(frame, amount, sunK)
	if IS_STUDIO then
		local phase = if frontHold then "held" elseif forced then "forced" elseif clearFrom then "clearing" elseif schedule then "scheduled" else "none"
		Workspace:SetAttribute("WeatherStorm", string.format("%.3f %s %s", amount, if s then tostring(math.round(s)) else "-", phase))
	end
end

-- Current StormAmount (0..1) and the front position (nil when none).
function Storm.state(): (number, number?)
	return amountNow, frontS
end

return Storm
