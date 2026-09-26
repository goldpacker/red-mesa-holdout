--!strict
-- Particle recipes for weapon effects (rocket/missile trails, explosions,
-- ricochet sparks, launch backblast). Uses Roblox built-in particle
-- textures only. One-shot bursts live on Attachments in Terrain, so no
-- parts are created for them; everything is capped and self-cleaning.

local Debris = game:GetService("Debris")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Particles = {}

local TEX = {
	smoke = "rbxasset://textures/particles/smoke_main.dds",
	fire = "rbxasset://textures/particles/fire_main.dds",
	sparks = "rbxasset://textures/particles/sparkles_main.dds",
	core = "rbxasset://textures/particles/explosion01_core_main.dds",
	shock = "rbxasset://textures/particles/explosion01_shockwave_main.dds",
	exSmoke = "rbxasset://textures/particles/explosion01_smoke_main.dds",
}
Particles.TEX = TEX

local MAX_BURSTS = 24
local liveBursts = 0

local function seq(...: number): NumberSequence
	local values = { ... }
	if #values == 1 then
		return NumberSequence.new(values[1])
	end
	local keys = {}
	for i, v in values do
		table.insert(keys, NumberSequenceKeypoint.new((i - 1) / (#values - 1), v))
	end
	return NumberSequence.new(keys)
end
Particles.seq = seq

local function colors(...: Color3): ColorSequence
	local values = { ... }
	if #values == 1 then
		return ColorSequence.new(values[1])
	end
	local keys = {}
	for i, v in values do
		table.insert(keys, ColorSequenceKeypoint.new((i - 1) / (#values - 1), v))
	end
	return ColorSequence.new(keys)
end
Particles.colors = colors

-- Creates a ParticleEmitter with sensible defaults, disabled unless
-- props.Enabled is set.
function Particles.emitter(parent: Instance, props: { [string]: any }): ParticleEmitter
	local e = Instance.new("ParticleEmitter")
	e.Enabled = false
	e.LightInfluence = 0
	e.Rate = 0
	e.RotSpeed = NumberRange.new(-60, 60)
	e.Rotation = NumberRange.new(0, 360)
	for k, v in props do
		(e :: any)[k] = v
	end
	e.Parent = parent
	return e
end

local function flashLight(parent: Instance, color: Color3, range: number, brightness: number, duration: number)
	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = range
	light.Brightness = brightness
	light.Shadows = false
	light.Parent = parent
	TweenService:Create(light, TweenInfo.new(duration, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { Brightness = 0 }):Play()
end

-- A world-space attachment for a one-shot burst; nil when over budget.
local function burstAnchor(position: Vector3, lifetime: number, up: Vector3?): Attachment?
	if liveBursts >= MAX_BURSTS then
		return nil
	end
	liveBursts += 1
	local a = Instance.new("Attachment")
	a.Name = "WeaponFx"
	if up and up.Magnitude > 0.01 then
		-- Emitters shoot along the attachment's +Y.
		local axis = up.Unit
		local ref = if math.abs(axis.Y) < 0.95 then Vector3.yAxis else Vector3.xAxis
		local right = ref:Cross(axis).Unit
		a.WorldCFrame = CFrame.fromMatrix(position, right, axis)
	else
		a.WorldPosition = position
	end
	a.Parent = Workspace.Terrain
	Debris:AddItem(a, lifetime)
	task.delay(lifetime, function()
		liveBursts -= 1
	end)
	return a
end

-- Big layered explosion. `air` skips the ground dust and throws debris
-- outward; `scale` 1 = rocket.
function Particles.explosion(position: Vector3, scale: number, air: boolean)
	local a = burstAnchor(position, 5, nil)
	if not a then
		return
	end
	flashLight(a, Color3.fromRGB(255, 160, 80), 45 * scale, 6, 0.45)

	local core = Particles.emitter(a, {
		Texture = TEX.core,
		Color = colors(Color3.fromRGB(255, 244, 200), Color3.fromRGB(255, 150, 50), Color3.fromRGB(120, 40, 20)),
		LightEmission = 1,
		Size = seq(5 * scale, 16 * scale, 20 * scale),
		Transparency = seq(0, 0.2, 1),
		Lifetime = NumberRange.new(0.25, 0.45),
		Speed = NumberRange.new(4 * scale, 18 * scale),
		SpreadAngle = Vector2.new(180, 180),
		Drag = 6,
		ZOffset = 2,
	})
	core:Emit(14)

	local flames = Particles.emitter(a, {
		Texture = TEX.fire,
		Color = colors(Color3.fromRGB(255, 210, 120), Color3.fromRGB(255, 110, 30), Color3.fromRGB(60, 30, 20)),
		LightEmission = 0.8,
		Size = seq(6 * scale, 13 * scale, 6 * scale),
		Transparency = seq(0.1, 0.3, 1),
		Lifetime = NumberRange.new(0.4, 0.9),
		Speed = NumberRange.new(12 * scale, 34 * scale),
		SpreadAngle = Vector2.new(180, 180),
		Acceleration = Vector3.new(0, 14, 0),
		Drag = 4,
		ZOffset = 1,
	})
	flames:Emit(18)

	local smoke = Particles.emitter(a, {
		Texture = TEX.smoke,
		Color = colors(Color3.fromRGB(58, 50, 44), Color3.fromRGB(96, 88, 80)),
		LightInfluence = 0.8,
		Size = seq(7 * scale, 18 * scale, 28 * scale),
		Transparency = seq(0.15, 0.45, 1),
		Lifetime = NumberRange.new(2.4, 3.8),
		Speed = NumberRange.new(6 * scale, 16 * scale),
		SpreadAngle = Vector2.new(180, 180),
		Acceleration = Vector3.new(0, 7, 0),
		Drag = 1.6,
		RotSpeed = NumberRange.new(-25, 25),
	})
	smoke:Emit(12)

	local debris = Particles.emitter(a, {
		Texture = TEX.sparks,
		Color = colors(Color3.fromRGB(255, 230, 160), Color3.fromRGB(255, 120, 40)),
		LightEmission = 1,
		Size = seq(0.9 * scale, 0.3 * scale),
		Lifetime = NumberRange.new(0.6, 1.3),
		Speed = NumberRange.new(50 * scale, 110 * scale),
		SpreadAngle = Vector2.new(180, 180),
		Acceleration = Vector3.new(0, -110, 0),
		Drag = 1.2,
	})
	debris:Emit(if air then 34 else 24)

	if not air then
		local dust = Particles.emitter(a, {
			Texture = TEX.smoke,
			Color = colors(Color3.fromRGB(196, 150, 104), Color3.fromRGB(176, 136, 98)),
			LightInfluence = 1,
			Size = seq(5 * scale, 14 * scale, 20 * scale),
			Transparency = seq(0.2, 0.5, 1),
			Lifetime = NumberRange.new(1.4, 2.4),
			Speed = NumberRange.new(30 * scale, 48 * scale),
			SpreadAngle = Vector2.new(80, 80),
			Drag = 3.5,
		})
		dust:Emit(10)
	else
		local shock = Particles.emitter(a, {
			Texture = TEX.shock,
			Color = colors(Color3.fromRGB(255, 220, 170)),
			LightEmission = 1,
			Size = seq(2 * scale, 22 * scale),
			Transparency = seq(0.3, 1),
			Lifetime = NumberRange.new(0.25, 0.25),
			Speed = NumberRange.new(0, 0),
			RotSpeed = NumberRange.new(0, 0),
		})
		shock:Emit(1)
	end
end

-- Hot sparks glancing off armour.
function Particles.ricochet(position: Vector3, normal: Vector3?)
	local a = burstAnchor(position, 0.8, normal)
	if not a then
		return
	end
	local sparks = Particles.emitter(a, {
		Texture = TEX.sparks,
		Color = colors(Color3.fromRGB(255, 250, 220), Color3.fromRGB(255, 170, 60)),
		LightEmission = 1,
		Size = seq(0.5, 0.15),
		Lifetime = NumberRange.new(0.15, 0.35),
		Speed = NumberRange.new(35, 75),
		SpreadAngle = Vector2.new(if normal then 60 else 180, if normal then 60 else 180),
		Acceleration = Vector3.new(0, -80, 0),
		Drag = 2,
	})
	sparks:Emit(10)
	flashLight(a, Color3.fromRGB(255, 220, 150), 8, 3, 0.1)
end

-- Launch backblast: flash and a puff of smoke at the muzzle, a smaller puff
-- blown out behind the tube.
function Particles.backblast(position: Vector3, dir: Vector3, bright: boolean)
	local a = burstAnchor(position, 3, dir)
	if not a then
		return
	end
	flashLight(a, if bright then Color3.fromRGB(255, 240, 210) else Color3.fromRGB(255, 170, 90), 22, 6, 0.25)
	local flash = Particles.emitter(a, {
		Texture = TEX.fire,
		Color = colors(Color3.fromRGB(255, 230, 170), Color3.fromRGB(255, 130, 40)),
		LightEmission = 1,
		Size = seq(2.2, 4),
		Transparency = seq(0, 1),
		Lifetime = NumberRange.new(0.08, 0.14),
		Speed = NumberRange.new(10, 20),
		SpreadAngle = Vector2.new(20, 20),
		ZOffset = 1,
	})
	flash:Emit(5)
	local smoke = Particles.emitter(a, {
		Texture = TEX.smoke,
		Color = colors(Color3.fromRGB(206, 200, 190), Color3.fromRGB(160, 154, 146)),
		LightInfluence = 1,
		Size = seq(2, 6, 9),
		Transparency = seq(0.35, 0.6, 1),
		Lifetime = NumberRange.new(1.2, 2),
		Speed = NumberRange.new(4, 14),
		SpreadAngle = Vector2.new(40, 40),
		Drag = 3,
		Acceleration = Vector3.new(0, 3, 0),
	})
	smoke:Emit(8)
end

-- Continuous emitters on a projectile's tail attachment. Returns them so
-- the caller can disable them on impact.
function Particles.trail(tail: Attachment, kind: string): { ParticleEmitter }
	local missile = kind == "Missile"
	local flame = Particles.emitter(tail, {
		Enabled = true,
		Texture = TEX.fire,
		Color = if missile
			then colors(Color3.fromRGB(255, 255, 240), Color3.fromRGB(255, 200, 120))
			else colors(Color3.fromRGB(255, 220, 150), Color3.fromRGB(255, 120, 40)),
		LightEmission = 1,
		Size = if missile then seq(1.6, 0.4) else seq(1.3, 0.3),
		Transparency = seq(0, 1),
		Lifetime = NumberRange.new(0.04, 0.08),
		Rate = 120,
		Speed = NumberRange.new(0, 0),
		LockedToPart = true,
		ZOffset = 1,
	})
	local smoke = Particles.emitter(tail, {
		Enabled = true,
		Texture = TEX.smoke,
		Color = if missile
			then colors(Color3.fromRGB(236, 234, 230), Color3.fromRGB(200, 198, 194))
			else colors(Color3.fromRGB(190, 184, 176), Color3.fromRGB(140, 134, 128)),
		LightInfluence = 1,
		Size = if missile then seq(1.2, 4, 7) else seq(1.4, 4.5, 8),
		Transparency = if missile then seq(0.25, 0.55, 1) else seq(0.3, 0.6, 1),
		Lifetime = if missile then NumberRange.new(1.8, 2.6) else NumberRange.new(1.1, 1.8),
		Rate = if missile then 110 else 90,
		Speed = NumberRange.new(0.5, 2.5),
		SpreadAngle = Vector2.new(12, 12),
		Drag = 1,
		Acceleration = Vector3.new(0, 1.5, 0),
		RotSpeed = NumberRange.new(-40, 40),
	})
	return { flame, smoke }
end

return Particles
