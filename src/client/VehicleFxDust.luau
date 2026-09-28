--!strict
-- Motion dust (VFX-3): wheel dust behind buggies, track dust behind tanks
-- and the Siege Crawler (rate from speed), rotor downwash under low
-- helicopters and the jet's wake over the basin floor on low passes. Dust
-- takes the colour of the ground it's over (sand, road, wash, rock).
--
-- Sources are the vehicles' contract parts and attachments
-- (docs/ASSET_CONTRACTS.md): Buggy WheelRL/WheelRR, Tank and SiegeCrawler
-- TrackL/TrackR, Helicopter MainRotor, Jet Exhaust. The emitters sit on
-- world attachments that follow those children every frame; the model root
-- is never moved (Look's EnemyMotion owns root smoothing), so rebuilt
-- meshes with the same names pick the dust up unchanged.
--
-- LOD: client/EffectsLod (fewer, larger particles far away, none beyond a
-- per-kind cutoff) plus a global cap of MAX_RATE particles/s.
-- Low sun (VFX-4, AD-2 carry-in): client/EffectsLight darkens the dust tint
-- with the sun's height, more where the terrain shadows it (particles are
-- never shadowed in Roblox and get the full sun, so pale sunset dust burned
-- out to white and hid the tank), and thins it when the camera looks into
-- the sun through it.
-- Studio QA: Workspace attribute FxDustOff = true stops new dust (A/B);
-- FxDustLightOff = true turns the low-sun light off; FxDustRate /
-- FxDustSources publish the live totals.

local Debris = game:GetService("Debris")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local FrameProfile = require(script.Parent.FrameProfile)

local Effects = require(script.Parent.Effects)
local Light = require(script.Parent.EffectsLight)
local Lod = require(script.Parent.EffectsLod)

local Dust = {}

local UP = Vector3.yAxis
local TICK = 0.2 -- s between ground probes and rate updates per source
local MAX_RATE = 420 -- particles/s over all motion dust, after LOD
local SPEED_TAU = 0.3 -- s: smooths the replicated (stepped) motion
local MIN_SPEED = 1.5 -- studs/s: parked vehicles raise nothing

local seq = Effects.seq
local WIND = Effects.WIND
-- Soft, edgeless dust cloud sheet (tools/vfx/sheets/drift.py).
local DUST = "DustDrift"

-- ZOffset on every dust emitter pulls the sprites toward the camera so the
-- ground doesn't cut them off in hard lines; small on ground vehicles so the
-- dust still sits behind the hull it rolls off.

-- Opacity over a particle's life: dense where it leaves the ground (the
-- sheet itself has no edge to show), thinning out over the last two thirds.
local function thins(start: number, mid: number): NumberSequence
	return NumberSequence.new({
		NumberSequenceKeypoint.new(0, start),
		NumberSequenceKeypoint.new(0.35, mid),
		NumberSequenceKeypoint.new(1, 1),
	})
end

-- Sizes with a random spread (envelope) so a trail of puffs doesn't read
-- as a string of identical balls.
local function sizes(a: number, b: number, c: number, spread: number): NumberSequence
	return NumberSequence.new({
		NumberSequenceKeypoint.new(0, a, a * spread),
		NumberSequenceKeypoint.new(0.5, b, b * spread),
		NumberSequenceKeypoint.new(1, c, c * spread),
	})
end

-- Dust tint by the ground under the source: the ground's on-screen colour
-- lifted toward white, since a cloud of fine dust scatters light and reads
-- paler than the ground it came off (matched side by side in Studio; the
-- plain ground colour made the dust vanish into the sand).
local LIFT = 0.3
local function lifted(c: Color3): Color3
	return c:Lerp(Color3.new(1, 1, 1), LIFT)
end
local TINT: { [string]: Color3 } = {
	Sand = lifted(Color3.fromRGB(214, 160, 110)),
	Road = lifted(Color3.fromRGB(160, 122, 92)),
	Wash = lifted(Color3.fromRGB(200, 178, 146)),
	Rock = lifted(Effects.ROCK_DUST),
}
-- Dusk and night: the dust is lit by the vehicles' own headlights and the
-- pale day tints blow out in the beams. Toward the night the dust takes a
-- darker, cooler tint, dimmer brightness and thinner opacity, so it stays a
-- subtle haze in the beams (VFX-3 fix 1). Keyed on TimeOfDay's preset
-- (Workspace attribute TimeOfDay, as client/VehicleFx reads it).
local DIM: { [string]: number } = { Dusk = 0.65, Night = 1 }
local NIGHT_TINT = Color3.fromRGB(88, 86, 90) -- near-neutral: the moonlight already cools it
local NIGHT_TINT_MIX = 0.75 -- share of NIGHT_TINT in the colour at full dim
local NIGHT_BRIGHTNESS = 0.4 -- emitter Brightness at full dim (1 by day)
local NIGHT_THIN = 0.35 -- extra transparency at full dim

local SURFACE: { [Enum.Material]: string } = {
	[Enum.Material.Ground] = "Road",
	[Enum.Material.Salt] = "Wash",
}

type Mode = "wheel" | "track" | "rotor" | "wake"
type Spec = {
	mode: Mode,
	sources: { { string } }, -- per source: contract names, first found wins
	rate: number, -- particles/s per source at full strength, close up
	cutoff: number, -- zoom-corrected camera distance with no dust beyond
	scale: number, -- particle size
	refSpeed: number?, -- wheel/track: speed for full strength (studs/s)
	low: number?, -- rotor/wake: full strength at or below this height (studs)
	high: number?, -- rotor/wake: none at or above this height
}

local SPECS: { [string]: Spec } = {
	Buggy = { mode = "wheel", sources = { { "WheelRL" }, { "WheelRR" } }, rate = 22, cutoff = 1500, scale = 1, refSpeed = 40 },
	Tank = { mode = "track", sources = { { "TrackL" }, { "TrackR" } }, rate = 12, cutoff = 1800, scale = 1.2, refSpeed = 10 },
	SiegeCrawler = { mode = "track", sources = { { "TrackL" }, { "TrackR" } }, rate = 10, cutoff = 2600, scale = 2.2, refSpeed = 5 },
	-- Hover heights are ~100-160 studs over the basin: a faint haze at the
	-- bottom of that window, a full ring when a helicopter comes down low.
	Helicopter = { mode = "rotor", sources = { { "MainRotor", "Root" } }, rate = 18, cutoff = 2200, scale = 1, low = 50, high = 145 },
	-- Jets run ~200-220 studs over the basin floor (~57 over the canyon rims).
	Jet = { mode = "wake", sources = { { "Exhaust", "Root" } }, rate = 90, cutoff = 2800, scale = 1, low = 150, high = 270 },
}
Dust.SPECS = SPECS

type Emitter = { e: ParticleEmitter, rate: number, size: NumberSequence, transparency: NumberSequence }
type Source = {
	inst: Instance,
	att: Attachment,
	emitters: { Emitter },
	last: Vector3?,
	vel: Vector3,
	ground: RaycastResult?,
	color: Color3,
	target: Color3,
	strength: number,
	rateK: number,
	sizeK: number,
	bright: number, -- emitter Brightness last written
	thin: number, -- extra transparency last written
	desired: number,
}
type Rig = { model: Model, spec: Spec, sources: { Source }, due: number }

local rigs: { [Model]: Rig } = {}
local capK = 1
local dim = 0 -- 0 by day, 1 at night (eased toward the preset's value)

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include

local function probe(p: Vector3, depth: number): RaycastResult?
	groundParams.FilterDescendantsInstances = { Workspace.Terrain }
	return Workspace:Raycast(p + UP * 2, -UP * (depth + 2), groundParams)
end

local function tintOf(hit: RaycastResult?): Color3
	if not hit then
		return TINT.Sand
	end
	if Effects.isRocky(hit) then
		return TINT.Rock
	end
	return TINT[SURFACE[hit.Material] or "Sand"]
end

local function positionOf(inst: Instance): Vector3?
	if inst:IsA("Attachment") then
		return inst.WorldPosition
	elseif inst:IsA("BasePart") then
		return inst.Position
	end
	return nil
end

---------------------------------------------------------------------------
-- Emitters per mode
---------------------------------------------------------------------------

local function add(list: { Emitter }, e: ParticleEmitter?, rateShare: number)
	if e then
		e.Enabled = true
		table.insert(list, { e = e, rate = rateShare, size = e.Size, transparency = e.Transparency })
	end
end

local function build(att: Attachment, spec: Spec): { Emitter }
	local s = spec.scale
	local list: { Emitter } = {}
	local emitter = Effects.emitter
	if spec.mode == "wheel" then
		-- A soft plume rolling off the tyre: many overlapping DustDrift
		-- particles merge into one trail (DustPuff's defined billows read as a
		-- string of separate puffs at range).
		add(list, emitter(att, DUST, 0, {
			Name = "WheelDust",
			Size = sizes(4.5 * s, 11 * s, 15 * s, 0.27),
			Transparency = thins(0.1, 0.42),
			ZOffset = 1,
			Lifetime = NumberRange.new(1.6, 2.6),
			Speed = NumberRange.new(3, 8),
			SpreadAngle = Vector2.new(35, 35),
			Drag = 1.6,
			Acceleration = WIND * 0.6 + Vector3.new(0, 1, 0),
		}), 1)
	elseif spec.mode == "track" then
		add(list, emitter(att, DUST, 0, {
			Name = "TrackDust",
			Size = sizes(5 * s, 13 * s, 19 * s, 0.25),
			Transparency = thins(0.05, 0.32),
			ZOffset = 1.5 * s,
			Lifetime = NumberRange.new(2.4, 3.4),
			Speed = NumberRange.new(1.5 * s, 4 * s),
			SpreadAngle = Vector2.new(35, 20),
			Drag = 1,
			Acceleration = WIND * 0.6 + Vector3.new(0, 0.5, 0),
		}), 1)
	elseif spec.mode == "rotor" then
		-- Downwash: dust blown out flat in every direction from under the hub
		-- (EmissionDirection Front + a full yaw spread), and a flat ring.
		add(list, emitter(att, DUST, 0, {
			Name = "Downwash",
			Size = sizes(7 * s, 18 * s, 26 * s, 0.25),
			Transparency = thins(0.25, 0.5),
			ZOffset = 4,
			Lifetime = NumberRange.new(2, 2.8),
			Speed = NumberRange.new(40, 55), -- ~40 studs out (1 rotor diameter)
			EmissionDirection = Enum.NormalId.Front,
			SpreadAngle = Vector2.new(8, 180), -- Y sweeps the yaw (checked in Studio)
			Drag = 1.2,
			Acceleration = WIND * 0.3 + Vector3.new(0, 1.5, 0),
		}), 1)
		add(list, emitter(att, "ShockwaveRing", 0, {
			Name = "DownwashRing",
			Size = seq(30 * s, 90 * s),
			Transparency = seq(0.55, 1),
			Lifetime = NumberRange.new(1.2, 1.5),
			Orientation = Enum.ParticleOrientation.VelocityPerpendicular,
			EmissionDirection = Enum.NormalId.Top,
			Speed = NumberRange.new(0.05),
			SpreadAngle = Vector2.zero,
			LightEmission = 0,
			LightInfluence = 1,
		}), 0.08)
	else
		-- Jet wake: a sheet of dust swept up along the ground track. The jet
		-- covers ~4 studs a frame, so it takes a high rate of large, faint
		-- puffs spread sideways to read as a sheet and not a string of beads.
		add(list, emitter(att, DUST, 0, {
			Name = "JetWake",
			Size = sizes(16 * s, 34 * s, 48 * s, 0.3),
			Transparency = thins(0.35, 0.55),
			-- Drawn this much nearer the camera so the big sprites don't
			-- slice into the ground in hard horizontal bands (no soft
			-- particles in Roblox). Checked in Studio.
			ZOffset = 14,
			Lifetime = NumberRange.new(2.6, 3.8),
			-- Blown out flat to both sides of the ground track, rising slowly.
			Speed = NumberRange.new(12, 24),
			EmissionDirection = Enum.NormalId.Front,
			SpreadAngle = Vector2.new(10, 180),
			Drag = 1.4,
			Acceleration = WIND + Vector3.new(0, 2, 0),
		}), 1)
	end
	for _, em in list do
		em.e.Rate = 0
		em.e.Color = ColorSequence.new(TINT.Sand)
	end
	return list
end

---------------------------------------------------------------------------
-- Rigs
---------------------------------------------------------------------------

local function find(model: Model, names: { string }): Instance?
	for _, name in names do
		local inst = model:FindFirstChild(name, true)
		if inst and (inst:IsA("BasePart") or inst:IsA("Attachment")) then
			return inst
		end
	end
	return nil
end

-- Starts dust for an enemy vehicle model (Kind attribute = `kind`).
function Dust.add(model: Model, kind: string)
	local spec = SPECS[kind]
	if not spec or rigs[model] then
		return
	end
	local sources: { Source } = {}
	for _, names in spec.sources do
		local inst = find(model, names)
		if inst then
			local att = Instance.new("Attachment")
			att.Name = "MotionDust"
			att.Parent = Workspace.Terrain
			table.insert(sources, {
				inst = inst,
				att = att,
				emitters = build(att, spec),
				last = nil,
				vel = Vector3.zero,
				ground = nil,
				color = TINT.Sand,
				target = TINT.Sand,
				strength = 0,
				rateK = 1,
				sizeK = 1,
				bright = -1,
				thin = -1,
				desired = 0,
			})
		end
	end
	if #sources > 0 then
		rigs[model] = { model = model, spec = spec, sources = sources, due = 0 }
	end
end

-- Stops a vehicle's dust; what's in the air fades out on its own.
function Dust.remove(model: Model)
	local rig = rigs[model]
	if not rig then
		return
	end
	rigs[model] = nil
	for _, src in rig.sources do
		for _, em in src.emitters do
			em.e.Enabled = false
		end
		Debris:AddItem(src.att, 6)
	end
end

---------------------------------------------------------------------------
-- Per frame: follow the source; per tick: ground, strength, LOD, rate
---------------------------------------------------------------------------

-- Where the dust starts and which way it's thrown, for this frame.
local function place(spec: Spec, src: Source, p: Vector3)
	local flat = Vector3.new(src.vel.X, 0, src.vel.Z)
	local back = if flat.Magnitude > 0.5 then -flat.Unit else Vector3.zero
	if spec.mode == "wheel" then
		local inst = src.inst
		local radius = if inst:IsA("BasePart") then inst.Size.Y * 0.5 else 1.5
		local contact = p - UP * radius
		src.att.CFrame = Effects.upFrame(contact + UP * 0.8, UP + back * 0.6)
	elseif spec.mode == "track" then
		local inst = src.inst
		local contact = p
		if inst:IsA("BasePart") then
			-- Rear bottom of the track (model forward is -Z).
			contact = inst.CFrame:PointToWorldSpace(Vector3.new(0, -inst.Size.Y * 0.5, inst.Size.Z * 0.5))
		end
		src.att.CFrame = Effects.upFrame(contact + UP * spec.scale, UP * 0.6 + back)
	else
		local ground = src.ground
		if ground then
			local g = Vector3.new(p.X, ground.Position.Y, p.Z)
			src.att.CFrame = CFrame.new(g + UP * (if spec.mode == "rotor" then 1.5 else 2))
		end
	end
end

local function strengthOf(spec: Spec, src: Source, p: Vector3): number
	if spec.mode == "wheel" or spec.mode == "track" then
		local speed = Vector3.new(src.vel.X, 0, src.vel.Z).Magnitude
		local ref = spec.refSpeed or 10
		-- Not on the ground (thrown, airborne): nothing.
		if not src.ground or p.Y - src.ground.Position.Y > 12 * spec.scale then
			return 0
		end
		return math.clamp((speed - MIN_SPEED) / (ref - MIN_SPEED), 0, 1.25)
	end
	local ground = src.ground
	if not ground then
		return 0
	end
	local h = p.Y - ground.Position.Y
	local low, high = spec.low or 40, spec.high or 120
	local t = math.clamp((high - h) / (high - low), 0, 1)
	return t * t * (3 - 2 * t)
end

-- `s` with every opacity scaled by (1 - k).
local function thinner(s: NumberSequence, k: number): NumberSequence
	local keys = table.create(#s.Keypoints)
	for i, kp in s.Keypoints do
		keys[i] = NumberSequenceKeypoint.new(kp.Time, 1 - (1 - kp.Value) * (1 - k), kp.Envelope)
	end
	return NumberSequence.new(keys)
end

local function tick(rig: Rig, dustOff: boolean)
	local spec = rig.spec
	for _, src in rig.sources do
		local p = positionOf(src.inst)
		if not p then
			src.desired = 0
			continue
		end
		if spec.mode == "wheel" or spec.mode == "track" then
			src.ground = probe(p, 16 * spec.scale)
		end
		-- Light (EffectsLight): the sun's height and the terrain's shadow
		-- scale the tint (Brightness does nothing on lit particles); looking
		-- into the sun thins it. Plus the legacy night dimming.
		local lightK, lightThin = Light.dust(src.att.WorldPosition)
		src.target = Light.scale(tintOf(src.ground):Lerp(NIGHT_TINT, NIGHT_TINT_MIX * dim), lightK)
		local bright = 1 + (NIGHT_BRIGHTNESS - 1) * dim
		local thin = math.max(NIGHT_THIN * dim, lightThin)
		if math.abs(bright - src.bright) > 0.03 or math.abs(thin - src.thin) > 0.03 then
			src.bright = bright
			src.thin = thin
			for _, em in src.emitters do
				em.e.Brightness = bright
				em.e.Transparency = thinner(em.transparency, thin)
			end
		end
		src.strength = if dustOff then 0 else strengthOf(spec, src, p)
		local rateK, sizeK = Lod.factor(src.att.WorldPosition, spec.cutoff)
		src.rateK = rateK
		src.desired = spec.rate * src.strength * rateK
		if math.abs(sizeK - src.sizeK) > 0.04 then
			src.sizeK = sizeK
			for _, em in src.emitters do
				em.e.Size = Lod.scaleSeq(em.size, sizeK)
			end
		end
		local c = src.color:Lerp(src.target, 0.35)
		if math.abs(c.R - src.color.R) + math.abs(c.G - src.color.G) + math.abs(c.B - src.color.B) > 0.004 then
			src.color = c
			local cs = ColorSequence.new(c)
			for _, em in src.emitters do
				em.e.Color = cs
			end
		end
		for _, em in src.emitters do
			em.e.Rate = src.desired * em.rate * capK
		end
	end
end

local function step(dt: number)
	if dt <= 0 then
		return
	end
	local now = os.clock()
	local alpha = 1 - math.exp(-dt / SPEED_TAU)
	local dustOff = Workspace:GetAttribute("FxDustOff") == true
	for model, rig in rigs do
		if not model.Parent then
			Dust.remove(model)
			continue
		end
		local spec = rig.spec
		local airborne = spec.mode == "rotor" or spec.mode == "wake"
		for _, src in rig.sources do
			local p = positionOf(src.inst)
			if p then
				if src.last then
					src.vel = src.vel:Lerp((p - (src.last :: Vector3)) / dt, alpha)
				end
				src.last = p
				if airborne then
					-- The ground under an aircraft changes fast (a jet covers 50
					-- studs a tick): probe it every frame.
					src.ground = probe(p, (spec.high or 200) + 20)
				end
				place(spec, src, p)
			end
		end
		if now >= rig.due then
			rig.due = now + TICK
			tick(rig, dustOff)
		end
	end
end

-- Global cap over all dust sources (on top of the per-source LOD).
local function recap()
	local total, count = 0, 0
	for _, rig in rigs do
		for _, src in rig.sources do
			for _, em in src.emitters do
				total += src.desired * em.rate
			end
			count += 1
		end
	end
	capK = if total > MAX_RATE then MAX_RATE / total else 1
	-- Ease toward the preset's night dimming (TimeOfDay blends its lighting
	-- over a few seconds too). Studio A/B: Workspace attribute FxDustDimOff.
	local preset = Workspace:GetAttribute("TimeOfDay")
	local goal = if Workspace:GetAttribute("FxDustDimOff") == true then 0 else DIM[if type(preset) == "string" then preset else ""] or 0
	dim += math.clamp(goal - dim, -0.25, 0.25)
	if RunService:IsStudio() then
		Workspace:SetAttribute("FxDustRate", math.round(total * capK))
		Workspace:SetAttribute("FxDustSources", count)
	end
end

function Dust.start()
	RunService:BindToRenderStep("VehicleFxDust", Enum.RenderPriority.Last.Value, FrameProfile.wrap("VehicleFxDust", step))
	task.spawn(function()
		while true do
			task.wait(0.5)
			recap()
		end
	end)
end

return Dust
