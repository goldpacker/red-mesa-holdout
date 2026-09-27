--!strict
-- Client combat effects (VFX-2): the building blocks every effect module
-- uses (emitters on the custom flipbooks in shared/Flipbooks, never a
-- built-in texture; pooled "rigs" and Beam tracers), and the gunfire
-- effects: our MG muzzle flash, bullet impacts by the surface the raycast
-- hit (sand, rock, metal, soldier), enemy muzzle flashes, rifles, grenades.
-- Explosions, debris, scorch, fires: VehicleFxParticles (required lazily).
-- Cap: MAX_LIVE tracers; distance LOD in EffectsLod. Studio QA: Workspace
-- attribute FxFreeze pauses tracers/debris for captures (tools/vfx/qa).

local Debris = game:GetService("Debris")
local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Flipbooks = require(ReplicatedStorage.Shared.Flipbooks)
local Lod = require(script.Parent.EffectsLod)
local Surface = require(script.Parent.EffectsSurface)

local Effects = {}

local MAX_LIVE = 160 -- live tracers (the original cap on short-lived effect parts)
local MAX_TRACERS = 48
local PIVOT = Config.TURRET_PIVOT
local WIND = (require(ReplicatedStorage.Shared.Wind) :: any).DIRECTION * 2.8 -- smoke drift (studs/s^2): shared/Wind's mean wind

local AMBER = Color3.fromRGB(255, 178, 36) -- art bible: our tracer amber
local RED = Color3.fromRGB(255, 74, 58) -- enemy tracer red
local FIRE_LIGHT = Color3.fromRGB(255, 150, 70)
local FLASH_WARM = Color3.fromRGB(255, 196, 128) -- our MG flash tint at night
local SMOKE = Color3.fromRGB(74, 68, 61)
-- Sunlight multiplies lit particles up, so these sit darker than the ochre
-- floor they should match on screen (checked side by side in Studio).
local SAND = Color3.fromRGB(172, 128, 90)
local DUST = Color3.fromRGB(180, 140, 100)
local ROCK = Color3.fromRGB(150, 84, 58)
local ROCK_DUST = Color3.fromRGB(178, 122, 92)

Effects.AMBER = AMBER
Effects.RED = RED
Effects.SMOKE = SMOKE
Effects.DUST = DUST
Effects.SAND = SAND
Effects.ROCK = ROCK
Effects.ROCK_DUST = ROCK_DUST
Effects.FIRE_LIGHT = FIRE_LIGHT
Effects.WIND = WIND

local live = 0

-- VehicleFxParticles requires this module: required on first use.
local blastModule: any = nil
local function blasts(): any
	if not blastModule then
		blastModule = require(script.Parent.VehicleFxParticles) :: any
	end
	return blastModule
end

---------------------------------------------------------------------------
-- Basics
---------------------------------------------------------------------------

function Effects.seq(...: number): NumberSequence
	local values = { ... }
	if #values == 1 then
		return NumberSequence.new(values[1])
	end
	local keys = table.create(#values)
	for i, v in values do
		keys[i] = NumberSequenceKeypoint.new((i - 1) / (#values - 1), v)
	end
	return NumberSequence.new(keys)
end
local seq = Effects.seq

local function sized(scale: number, ...: number): NumberSequence
	local values = { ... }
	for i, v in values do
		values[i] = v * scale
	end
	return seq(table.unpack(values))
end
Effects.sized = sized

function Effects.folder(): Instance
	local f = Workspace:FindFirstChild("CombatFx")
	if not f then
		f = Instance.new("Folder")
		f.Name = "CombatFx"
		f.Parent = Workspace
	end
	return f
end

function Effects.frozen(): boolean
	return Workspace:GetAttribute("FxFreeze") == true
end
local frozen = Effects.frozen

-- Emissive brightness scale for the time of day: LightingRig's bloom
-- threshold drops from 2.4 (afternoon) to 0.95 (night); this keeps fire and
-- flashes from ballooning into white halos, and offsets exposure boosts.
local bloom: BloomEffect? = nil
function Effects.exposure(): number
	if not (bloom and bloom.Parent) then
		bloom = Lighting:FindFirstChildOfClass("BloomEffect")
	end
	local threshold = if bloom and bloom.Enabled then bloom.Threshold else 2.4
	local k = math.clamp((threshold / 2.4) ^ 0.6, 0.55, 1)
	return math.clamp(k * 2 ^ (-0.85 * Lighting.ExposureCompensation), 0.3, 1)
end

function Effects.camDistance(p: Vector3): number
	return (Workspace.CurrentCamera.CFrame.Position - p).Magnitude
end
local camDistance = Effects.camDistance
Effects.lod = Lod.count -- one-shot particle count after distance LOD

-- A ParticleEmitter showing flipbook `name` (suggested look from Flipbooks,
-- sizes x `scale`), then `props`. nil if the texture isn't available.
function Effects.emitter(parent: Instance, name: string, scale: number, props: { [string]: any }?): ParticleEmitter?
	local e = Instance.new("ParticleEmitter")
	if not Flipbooks.apply(e, name, scale) then
		e:Destroy()
		return nil
	end
	e.Enabled = false
	e.Rate = 0
	e.LockedToPart = false
	e.Speed = NumberRange.new(0)
	for k, v in props or {} do
		(e :: any)[k] = v
	end
	e.Parent = parent
	return e
end
local emitter = Effects.emitter

local function emit(e: ParticleEmitter?, n: number)
	if e and n > 0 then
		e:Emit(n)
		Lod.note(e, n)
	end
end
Effects.emit = emit

-- CFrame at `p` whose +Y (particle emission direction) is `up`.
function Effects.upFrame(p: Vector3, up: Vector3): CFrame
	local axis = if up.Magnitude > 1e-3 then up.Unit else Vector3.yAxis
	local ref = if math.abs(axis.Y) < 0.95 then Vector3.yAxis else Vector3.xAxis
	return CFrame.fromMatrix(p, ref:Cross(axis).Unit, axis)
end
local upFrame = Effects.upFrame

-- A world-space Attachment (in Terrain) removed after `lifetime`.
function Effects.anchor(cf: CFrame, lifetime: number): Attachment
	local a = Instance.new("Attachment")
	a.Name = "Fx"
	a.CFrame = cf
	a.Parent = Workspace.Terrain
	Debris:AddItem(a, lifetime)
	return a
end

-- A PointLight that fades out over `duration`.
function Effects.flash(parent: Instance, color: Color3, range: number, brightness: number, duration: number): PointLight
	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = range
	light.Brightness = brightness
	light.Shadows = false
	light.Parent = parent
	TweenService:Create(light, TweenInfo.new(duration, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { Brightness = 0 }):Play()
	return light
end

-- Pooled rigs: emitters on world Attachments, built once, moved to each use.
-- An Emit() spawns where the emitter is at its next particle update, so one
-- emitter serves one position per frame: a ring of `count` copies per key.
type Rig = { e: { [string]: ParticleEmitter? }, light: PointLight? }
type RigSet = { list: { Rig }, turn: number }
local rigSets: { [string]: RigSet } = {}

-- An emitter on its own world Attachment, for rigs.
function Effects.slot(flipbook: string, scale: number, props: { [string]: any }?): ParticleEmitter?
	local att = Instance.new("Attachment")
	att.Name = "FxSlot"
	att.Parent = Workspace.Terrain
	local e = emitter(att, flipbook, scale, props)
	if not e then
		att:Destroy()
	end
	return e
end
local slot = Effects.slot

function Effects.rig(key: string, build: () -> { [string]: ParticleEmitter? }, lightRange: number?, count: number?): Rig
	local set = rigSets[key]
	if not set then
		set = { list = {}, turn = 0 }
		rigSets[key] = set
	end
	set.turn = set.turn % (count or 4) + 1
	local r = set.list[set.turn]
	if r then
		return r
	end
	local light: PointLight? = nil
	if lightRange then
		local att = Instance.new("Attachment")
		att.Name = "FxLight_" .. key
		att.Parent = Workspace.Terrain
		local l = Instance.new("PointLight")
		l.Range = lightRange
		l.Brightness = 0
		l.Shadows = false
		l.Enabled = false
		l.Parent = att
		light = l
	end
	r = { e = build(), light = light }
	set.list[set.turn] = r
	return r
end
local rig = Effects.rig

-- Moves a rig emitter to `cf` and emits `n` particles there.
function Effects.emitAt(e: ParticleEmitter?, cf: CFrame, n: number)
	local att = e and e.Parent
	if e and n > 0 and att and att:IsA("Attachment") then
		att.CFrame = cf
		e:Emit(n)
		Lod.note(e, n)
	end
end
local emitAt = Effects.emitAt

-- Moves a rig light to `cf`.
function Effects.placeLight(light: PointLight?, cf: CFrame)
	local att = light and light.Parent
	if att and att:IsA("Attachment") then
		att.CFrame = cf
	end
end

local lightTokens: { [PointLight]: number } = {}
-- Turns a rig light on for `duration` seconds (re-triggering extends it).
function Effects.pulse(light: PointLight?, color: Color3, brightness: number, duration: number)
	if not light then
		return
	end
	light.Color = color
	light.Brightness = brightness
	light.Enabled = true
	local token = (lightTokens[light] or 0) + 1
	lightTokens[light] = token
	task.delay(duration, function()
		if lightTokens[light] == token then
			light.Enabled = false
		end
	end)
end
local pulse = Effects.pulse

---------------------------------------------------------------------------
-- Surfaces
---------------------------------------------------------------------------

local ROCKY = {
	[Enum.Material.Rock] = true,
	[Enum.Material.Sandstone] = true,
	[Enum.Material.Slate] = true,
	[Enum.Material.Basalt] = true,
	[Enum.Material.Limestone] = true,
	[Enum.Material.Granite] = true,
	[Enum.Material.Marble] = true,
	[Enum.Material.Pavement] = true,
	[Enum.Material.Cobblestone] = true,
	[Enum.Material.Brick] = true,
	[Enum.Material.Concrete] = true,
	[Enum.Material.CrackedLava] = true,
	[Enum.Material.Wood] = true,
	[Enum.Material.WoodPlanks] = true,
}
local METAL = {
	[Enum.Material.Metal] = true,
	[Enum.Material.DiamondPlate] = true,
	[Enum.Material.CorrodedMetal] = true,
	[Enum.Material.Foil] = true,
}

local surfaceParams = RaycastParams.new()
surfaceParams.FilterType = Enum.RaycastFilterType.Exclude

-- "Sand" | "Rock" | "Metal" | "Soldier" for a raycast hit.
function Effects.surfaceOf(result: RaycastResult?): string
	if not result then
		return "Sand"
	end
	local inst = result.Instance
	local model = inst:FindFirstAncestorOfClass("Model")
	while model do
		local kind = model:GetAttribute("Kind")
		if kind ~= nil then
			return if kind == "Infantry" then "Soldier" else "Metal"
		end
		model = model:FindFirstAncestorOfClass("Model")
	end
	local material = result.Material
	if METAL[material] then
		return "Metal"
	end
	-- Rock, or terrain too steep to hold sand (wall feet under landscape meshes).
	return if ROCKY[material] or (inst == Workspace.Terrain and result.Normal.Y < 0.6) then "Rock" else "Sand"
end

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include

-- The terrain (gameplay surface) under `p` within `drop` studs.
function Effects.groundBelow(p: Vector3, drop: number): RaycastResult?
	groundParams.FilterDescendantsInstances = { Workspace.Terrain }
	return Workspace:Raycast(p + Vector3.new(0, 2, 0), Vector3.new(0, -(drop + 2), 0), groundParams)
end
local groundBelow = Effects.groundBelow

function Effects.isRocky(result: RaycastResult?): boolean
	return result ~= nil and ROCKY[result.Material] == true
end

-- Re-casts a short ray through `position` along `from -> position` to find
-- the surface (WeaponController only passes the hit point).
local function probe(position: Vector3, from: Vector3?): RaycastResult?
	local origin = from or PIVOT
	local d = position - origin
	if d.Magnitude < 0.5 then
		return nil
	end
	local dir = d.Unit
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local list: { Instance } = { Effects.folder() }
	local emplacement = battlefield and battlefield:FindFirstChild("Emplacement")
	if emplacement and not from then
		table.insert(list, emplacement)
	end
	local projectiles = Workspace:FindFirstChild("Projectiles")
	if projectiles then
		table.insert(list, projectiles)
	end
	surfaceParams.FilterDescendantsInstances = list
	return Workspace:Raycast(position - dir * 3, dir * 6, surfaceParams)
end

---------------------------------------------------------------------------
-- Tracers (pooled Beams: textured hot core + soft halo, tail fades)
---------------------------------------------------------------------------

type Tracer = {
	a0: Attachment,
	a1: Attachment,
	d0: Attachment,
	d1: Attachment,
	glow: Beam,
	core: Beam,
	dot: Beam,
	dotBase: number,
	from: Vector3,
	dir: Vector3,
	dist: number,
	speed: number,
	len: number,
	t: number,
}
local tracerPool: { Tracer } = {}
local tracersActive: { Tracer } = {}
local tracerTex = Flipbooks.texture("TracerBeam")

local function newTracer(): Tracer
	local a0 = Instance.new("Attachment")
	a0.Name = "TracerTail"
	a0.Parent = Workspace.Terrain
	local a1 = Instance.new("Attachment")
	a1.Name = "TracerHead"
	a1.Parent = Workspace.Terrain
	local d0 = Instance.new("Attachment")
	d0.Name = "TracerDotA"
	d0.Parent = Workspace.Terrain
	local d1 = Instance.new("Attachment")
	d1.Name = "TracerDotB"
	d1.Parent = Workspace.Terrain
	local function beam(name: string, p0: Attachment?, p1: Attachment?): Beam
		local b = Instance.new("Beam")
		b.Name = name
		b.Attachment0 = p0 or a0
		b.Attachment1 = p1 or a1
		b.Texture = tracerTex or ""
		b.TextureMode = Enum.TextureMode.Stretch
		b.TextureLength = 1
		b.FaceCamera = true
		b.LightEmission = 1
		b.LightInfluence = 0
		b.Segments = 1
		b.Enabled = false
		b.Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 1),
			NumberSequenceKeypoint.new(0.55, 0.55),
			NumberSequenceKeypoint.new(1, 0),
		})
		b.Parent = a0
		return b
	end
	local glow = beam("TracerGlow")
	local core = beam("TracerCore")
	-- The round's hot head as a soft dot: a streak seen end-on (from behind
	-- the gun, or an enemy round coming straight at us) has no length on
	-- screen, and a camera-facing beam along the view ray has no width.
	local dot = beam("TracerDot", d0, d1)
	dot.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 1),
		NumberSequenceKeypoint.new(0.5, 0),
		NumberSequenceKeypoint.new(1, 1),
	})
	return {
		a0 = a0,
		a1 = a1,
		d0 = d0,
		d1 = d1,
		glow = glow,
		core = core,
		dot = dot,
		dotBase = 1,
		from = Vector3.zero,
		dir = Vector3.zAxis,
		dist = 0,
		speed = 900,
		len = 24,
		t = 0,
	}
end

local function stepTracers(dt: number)
	if frozen() then
		return
	end
	local cam = Workspace.CurrentCamera.CFrame
	for i = #tracersActive, 1, -1 do
		local tr = tracersActive[i]
		tr.t += dt
		local head = math.min(tr.dist, tr.speed * tr.t)
		local tail = math.max(0, math.min(tr.dist, tr.speed * tr.t - tr.len))
		if tail >= tr.dist - 0.05 then
			tr.glow.Enabled = false
			tr.core.Enabled = false
			tr.dot.Enabled = false
			table.remove(tracersActive, i)
			table.insert(tracerPool, tr)
			live -= 1
		else
			local headPos = tr.from + tr.dir * math.max(head, tail + 0.05)
			tr.a0.WorldPosition = tr.from + tr.dir * tail
			tr.a1.WorldPosition = headPos
			-- Dot size grows a little with distance so it stays a few pixels.
			local size = math.clamp((headPos - cam.Position).Magnitude * 0.006, 0.7, 2.6) * tr.dotBase
			local half = cam.RightVector * size * 0.5
			tr.dot.Width0, tr.dot.Width1 = size, size
			tr.d0.WorldPosition = headPos - half
			tr.d1.WorldPosition = headPos + half
			if tail >= head - 0.1 then
				tr.dot.Enabled = false
			end
			-- A streak seen almost end-on degenerates into a flat band across
			-- the screen (gunsight view, enemy rounds coming at us): show only
			-- the head dot then.
			local toHead = headPos - cam.Position
			local endOn = toHead.Magnitude > 1 and math.abs(tr.dir:Dot(toHead.Unit)) > 0.996
			tr.glow.Enabled = not endOn
			tr.core.Enabled = not endOn
		end
	end
end

-- A glowing round travelling from `from` to `to`. Ours amber by default.
function Effects.tracer(from: Vector3, to: Vector3, color: Color3?, width: number?)
	if live >= MAX_LIVE or #tracersActive >= MAX_TRACERS or not tracerTex then
		return
	end
	local d = to - from
	local dist = d.Magnitude
	-- Seen down the gunsight the first stretch would be a glaring blob in
	-- the player's face: start the visible round a little downrange.
	if camDistance(from) < 10 and dist > 30 then
		from += d / dist * 14
		d = to - from
		dist = d.Magnitude
	end
	if dist < 1 then
		return
	end
	local tr = table.remove(tracerPool) or newTracer()
	local w = (width or 0.35) * 3.2
	local travel = math.clamp(dist / 900, 0.04, 0.35)
	tr.from, tr.dir, tr.dist, tr.t = from, d / dist, dist, 0
	tr.speed = dist / travel
	tr.len = math.min(dist * 0.6, 26)
	local k = Effects.exposure()
	local tint = color or AMBER
	tr.glow.Color = ColorSequence.new(tint)
	tr.glow.Width0, tr.glow.Width1 = w * 0.55, w
	tr.glow.Brightness = 2.4 * k
	-- The hot core keeps the tracer's hue (a white core reads white at range).
	tr.core.Color = ColorSequence.new(tint:Lerp(Color3.new(1, 1, 1), 0.45))
	tr.core.Width0, tr.core.Width1 = w * 0.15, w * 0.32
	tr.core.Brightness = 1.2 * k
	tr.dot.Color = ColorSequence.new(tint:Lerp(Color3.new(1, 1, 1), 0.3))
	tr.dot.Brightness = 2 * k
	tr.dotBase = w * 0.9
	tr.a0.WorldPosition = from
	tr.a1.WorldPosition = from + tr.dir * 0.05
	tr.d0.WorldPosition = from
	tr.d1.WorldPosition = from + Vector3.new(0.05, 0, 0)
	tr.glow.Enabled = true
	tr.core.Enabled = true
	tr.dot.Enabled = true
	live += 1
	table.insert(tracersActive, tr)
end

---------------------------------------------------------------------------
-- Our MG muzzle flash: side flash, camera-facing star, a wisp of smoke and
-- a toned-down light ~2 studs ahead so the sandbags don't blow out.
---------------------------------------------------------------------------

local shotCount = 0

local function buildMuzzleRig(): { [string]: ParticleEmitter? }
	return {
		side = slot("MuzzleFlashSide", 0.85, { Speed = NumberRange.new(0.5), EmissionDirection = Enum.NormalId.Top }),
		front = slot("MuzzleFlashFront", 0.55, {}),
		smoke = slot("DustPuff", 0.3, {
			Color = ColorSequence.new(Color3.fromRGB(196, 190, 180)),
			Transparency = seq(0.72, 0.85, 1),
			Lifetime = NumberRange.new(0.6, 1),
			Speed = NumberRange.new(3, 6),
			SpreadAngle = Vector2.new(15, 15),
			Drag = 3,
			Acceleration = Vector3.new(0, 3, 0),
		}),
	}
end

function Effects.muzzleFlash(position: Vector3, direction: Vector3)
	local r = rig("MgMuzzle", buildMuzzleRig, 7, 2)
	local dir = if direction.Magnitude > 1e-3 then direction.Unit else Vector3.zAxis
	local k = Effects.exposure()
	-- In the gunsight the camera sits just behind the muzzle: no sprites in
	-- its face, only the light.
	local sighted = camDistance(position) < 8
	if not sighted then
		local side, front = r.e.side, r.e.front
		-- Warmer as the bloom threshold drops: a white core reads cold
		-- under the blue night grade.
		local tint = ColorSequence.new(Color3.new(1, 1, 1):Lerp(FLASH_WARM, math.clamp((1 - k) / 0.45, 0, 1)))
		if side then
			side.Brightness = 1.1 * k
			side.Color = tint
		end
		if front then
			front.Brightness = 0.9 * k
			front.Color = tint
		end
		emitAt(side, upFrame(position + dir * 0.85, dir), 1)
		emitAt(front, upFrame(position + dir * 0.35, dir), 1)
		shotCount += 1
		if shotCount % 3 == 0 then
			emitAt(r.e.smoke, upFrame(position + dir * 1.2, dir), 1)
		end
	end
	Effects.placeLight(r.light, CFrame.new(position + dir * 2.2))
	pulse(r.light, Color3.fromRGB(255, 184, 96), 1.2 * k, 0.05)
end

---------------------------------------------------------------------------
-- Bullet impacts by surface
---------------------------------------------------------------------------

local function buildImpactRig(): { [string]: ParticleEmitter? }
	return {
		kick = slot("SandKick", 1.2, { Color = ColorSequence.new(SAND) }),
		puff = slot("DustPuff", 0.45, {
			Color = ColorSequence.new(DUST),
			Transparency = seq(0.35, 0.55, 1),
			Lifetime = NumberRange.new(1.1, 1.7),
			Speed = NumberRange.new(1, 3),
			Acceleration = WIND * 0.4 + Vector3.new(0, 0.6, 0),
		}),
		chips = slot("RockChips", 1, {
			Color = ColorSequence.new(ROCK),
			Size = seq(5.5, 6.5),
			Lifetime = NumberRange.new(0.7, 0.9),
			Orientation = Enum.ParticleOrientation.FacingCameraWorldUp,
			LightInfluence = 1,
		}),
		rockDust = slot("DustPuff", 0.6, {
			Color = ColorSequence.new(ROCK_DUST),
			Transparency = seq(0.3, 0.5, 1),
			Lifetime = NumberRange.new(0.9, 1.4),
			Speed = NumberRange.new(2, 4),
		}),
		sparks = slot("Sparks", 1.1, {}),
		glint = slot("MuzzleFlashFront", 0.55, { Lifetime = NumberRange.new(0.04, 0.06) }),
		cloth = slot("DustPuff", 0.22, {
			Color = ColorSequence.new(Color3.fromRGB(128, 118, 104)),
			Transparency = seq(0.35, 0.6, 1),
			Lifetime = NumberRange.new(0.5, 0.8),
			Speed = NumberRange.new(1, 3),
		}),
	}
end

-- A bullet hitting `position`: sand spurt on sand/ground, rock chips on
-- cliffs and rock, sparks on metal, a dust puff on soldiers. `from` is the
-- shooter (default: our turret); `surface` skips the probe.
function Effects.impact(position: Vector3, onEnemy: boolean, from: Vector3?, surface: string?)
	local kind = surface
	if not kind then
		local result = probe(position, from)
		if not result and not onEnemy then
			-- Enemy rounds aim at points around the outpost: drop to the ground.
			result = groundBelow(position, 8)
			if not result then
				return
			end
			position = result.Position
		end
		kind = Effects.surfaceOf(result)
		if onEnemy and kind == "Sand" then
			kind = "Metal"
		end
		-- Landscape meshes stand in front of the terrain the ray hit.
		local rock = if onEnemy then nil else Surface.hit(from or PIVOT, position)
		position, kind = if rock then rock.Position else position, if rock then "Rock" else kind
	end
	local r = rig("Impact", buildImpactRig, nil, 6)
	local e = r.e
	local k = Effects.exposure()
	local at = CFrame.new(position)
	if kind == "Metal" then
		if e.sparks then
			e.sparks.Brightness = 1.6 * k
		end
		if e.glint then
			e.glint.Brightness = 1.2 * k
		end
		emitAt(e.sparks, at, 1)
		emitAt(e.glint, at, 1)
	elseif kind == "Soldier" then
		emitAt(e.cloth, at, 1)
	elseif kind == "Rock" then
		-- Start the chips just in front of the surface.
		local toShooter = (from or PIVOT) - position
		at = if toShooter.Magnitude > 2 then CFrame.new(position + toShooter.Unit * 1.4) else at
		emitAt(e.chips, at, 1)
		emitAt(e.rockDust, at, 1)
	else
		-- SandKick's ground line sits 38.5% of its size below the centre.
		emitAt(e.kick, CFrame.new(position + Vector3.new(0, 0.385 * 6.6, 0)), 1)
		emitAt(e.puff, CFrame.new(position + Vector3.new(0, 1, 0)), 1)
	end
end

---------------------------------------------------------------------------
-- Explosions and fires (implemented in VehicleFxParticles)
---------------------------------------------------------------------------

-- Layered explosion; see VehicleFxParticles.explosion for the options.
function Effects.explosion(position: Vector3, scale: number, opts: { [string]: any }?)
	blasts().explosion(position, scale, opts)
end

-- Persistent fire and smoke column; destroy the returned part to stop it.
function Effects.burning(position: Vector3, scale: number): BasePart
	local carrier = Instance.new("Part")
	carrier.Name = "Burning"
	carrier.Anchored = true
	carrier.CanCollide = false
	carrier.CanQuery = false
	carrier.CanTouch = false
	carrier.CastShadow = false
	carrier.Transparency = 1
	carrier.Size = Vector3.one
	carrier.CFrame = CFrame.new(position)
	carrier.Parent = Effects.folder()
	blasts().burn(carrier, scale * 1.1, Vector3.zero)
	return carrier
end

---------------------------------------------------------------------------
-- Enemy rifle shot and grenade (EnemyFireFx)
---------------------------------------------------------------------------

-- A rifle shot from an enemy: muzzle flash readable from the mesa, a red
-- tracer, and the round landing short around the sandbags.
function Effects.enemyShot(from: Vector3, to: Vector3)
	local flashTo = (to - from)
	Effects.enemyMuzzle(from, if flashTo.Magnitude > 1e-3 then flashTo.Unit else Vector3.zAxis, 0.35)
	local scatter = Vector3.new(math.random(-6, 6), math.random(-3, 1), math.random(-6, 6))
	Effects.tracer(from, to + scatter, RED, 0.3)
end

local function buildEnemyMuzzle(scale: number): () -> { [string]: ParticleEmitter? }
	return function()
		return {
			front = slot("MuzzleFlashFront", 1.1 * scale + 0.9, {}),
			side = slot("MuzzleFlashSide", 1.2 * scale + 0.6, { Speed = NumberRange.new(0.5), EmissionDirection = Enum.NormalId.Top }),
			burst = if scale >= 0.9 then slot("MuzzleFlashBurst", 0.9 * scale, {}) else nil,
			smoke = if scale >= 0.6
				then slot("DustPuff", 0.7 * scale, {
					Color = ColorSequence.new(Color3.fromRGB(150, 140, 128)),
					Transparency = seq(0.45, 0.6, 1),
					Lifetime = NumberRange.new(0.9, 1.6),
					Speed = NumberRange.new(4 * scale, 12 * scale),
					SpreadAngle = Vector2.new(35, 35),
					Drag = 2.5,
					EmissionDirection = Enum.NormalId.Top,
				})
				else nil,
		}
	end
end

-- Enemy muzzle blast along `direction`; `scale` 0.35 rifle/buggy, 0.6
-- rocket pod, 1 boss autocannon, 2.2 tank gun, 4.5 boss cannon. `color`
-- tints the flash light (the sprites keep their baked fire colours).
function Effects.enemyMuzzle(position: Vector3, direction: Vector3, scale: number, color: Color3?)
	local key = string.format("EnemyMuzzle%.2f", scale)
	local r = rig(key, buildEnemyMuzzle(scale), 8 + 14 * scale, if scale < 0.5 then 8 else 3)
	local k = Effects.exposure()
	local dir = if direction.Magnitude > 1e-3 then direction.Unit else Vector3.zAxis
	local e = r.e
	-- The side flash's muzzle sits 22.5% of its size below its centre.
	local sideSize = (1.2 * scale + 0.6) * 3.8
	for _, name in { "front", "side", "burst" } do
		local em = e[name]
		if em then
			em.Brightness = 1.2 * k
		end
	end
	emitAt(e.side, upFrame(position + dir * 0.225 * sideSize, dir), 1)
	local mouth = upFrame(position + dir * 0.3 * scale, dir)
	emitAt(e.front, mouth, 1)
	emitAt(e.burst, mouth, 1)
	emitAt(e.smoke, mouth, math.floor(2 + 2 * scale))
	Effects.placeLight(r.light, mouth)
	pulse(r.light, color or Color3.fromRGB(255, 180, 90), (if scale < 0.5 then 2.5 else 5) * k, 0.12)
end

-- A grenade arcing from `from` to `to` over `duration`, exploding on landing.
function Effects.grenade(from: Vector3, to: Vector3, duration: number)
	local g = Instance.new("Part")
	g.Name = "Grenade"
	g.Anchored = true
	g.CanCollide = false
	g.CanQuery = false
	g.CanTouch = false
	g.CastShadow = false
	g.Material = Enum.Material.Metal
	g.Color = Color3.fromRGB(58, 62, 44)
	g.Size = Vector3.new(0.7, 0.7, 0.95)
	local mesh = Instance.new("SpecialMesh")
	mesh.MeshType = Enum.MeshType.Sphere
	mesh.Parent = g
	g.CFrame = CFrame.new(from)
	g.Parent = Effects.folder()
	Debris:AddItem(g, duration + 1)
	local start = os.clock()
	local height = 26
	task.spawn(function()
		while g.Parent do
			local t = math.min(1, (os.clock() - start) / duration)
			local p = from:Lerp(to, t) + Vector3.new(0, math.sin(t * math.pi) * height, 0)
			g.CFrame = CFrame.new(p) * CFrame.Angles(t * 14, t * 9, 0)
			if t >= 1 then
				break
			end
			task.wait()
		end
		g:Destroy()
		blasts().explosion(to, 1.2, { near = true })
	end)
end

---------------------------------------------------------------------------

RunService.RenderStepped:Connect(stepTracers)

return Effects
