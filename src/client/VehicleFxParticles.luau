--!strict
-- Particle building blocks for enemy destruction and enemy fire: layered
-- explosions (flash, fireball, sparks, smoke, dust ring, debris), lasting
-- fires with smoke columns, smoke trails, muzzle blasts and flying
-- projectiles. Uses Roblox's built-in particle textures; every effect is
-- time-limited and budgeted. Local-only instances live in
-- Workspace.VehicleFxLocal so server-side folder clears don't cut them off.

local Debris = game:GetService("Debris")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Particles = {}

local TEX = {
	fire = "rbxasset://textures/particles/fire_main.dds",
	smoke = "rbxasset://textures/particles/smoke_main.dds",
	sparkle = "rbxasset://textures/particles/sparkles_main.dds",
	sparks = "rbxasset://textures/particles/fire_sparks_main.dds",
}

local FIRE_COLORS = ColorSequence.new({
	ColorSequenceKeypoint.new(0, Color3.fromRGB(255, 244, 200)),
	ColorSequenceKeypoint.new(0.2, Color3.fromRGB(255, 170, 60)),
	ColorSequenceKeypoint.new(0.6, Color3.fromRGB(220, 80, 30)),
	ColorSequenceKeypoint.new(1, Color3.fromRGB(60, 40, 30)),
})
local SMOKE_COLORS = ColorSequence.new(Color3.fromRGB(38, 34, 31), Color3.fromRGB(92, 84, 76))
local DUST_COLORS = ColorSequence.new(Color3.fromRGB(196, 140, 96), Color3.fromRGB(170, 124, 90))

local MAX_EXPLOSIONS = 14
local MAX_BURNS = 16
local liveExplosions = 0
local liveBurns = 0
local flickering: { [PointLight]: boolean } = {}

local function ns(points: { { number } }): NumberSequence
	local keys = {}
	for _, p in points do
		table.insert(keys, NumberSequenceKeypoint.new(p[1], p[2], p[3] or 0))
	end
	return NumberSequence.new(keys)
end

local function folder(): Instance
	local f = Workspace:FindFirstChild("VehicleFxLocal")
	if not f then
		f = Instance.new("Folder")
		f.Name = "VehicleFxLocal"
		f.Parent = Workspace
	end
	return f
end

-- Invisible anchored carrier part for particles and lights.
function Particles.anchor(cf: CFrame, size: Vector3?): Part
	local p = Instance.new("Part")
	p.Name = "Fx"
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Transparency = 1
	p.Size = size or Vector3.one
	p.CFrame = cf
	p.Parent = folder()
	return p
end

local function emitter(parent: Instance, props: { [string]: any }): ParticleEmitter
	local e = Instance.new("ParticleEmitter")
	e.Enabled = false
	e.LockedToPart = false
	e.Rotation = NumberRange.new(0, 360)
	e.RotSpeed = NumberRange.new(-40, 40)
	for k, v in props do
		(e :: any)[k] = v
	end
	e.Parent = parent
	return e
end

local function flash(parent: Instance, color: Color3, range: number, brightness: number, duration: number)
	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = range
	light.Brightness = brightness
	light.Shadows = false
	light.Parent = parent
	TweenService:Create(light, TweenInfo.new(duration, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { Brightness = 0 }):Play()
end

local function debrisChunks(position: Vector3, scale: number, count: number)
	for _ = 1, count do
		local chunk = Instance.new("Part")
		chunk.Name = "Chunk"
		local s = (0.4 + math.random() * 0.9) * scale
		chunk.Size = Vector3.new(s, s * 0.5, s * 0.8)
		chunk.Color = Color3.fromRGB(34, 32, 30)
		chunk.Material = Enum.Material.Metal
		chunk.CanQuery = false
		chunk.CanTouch = false
		chunk.CastShadow = false
		chunk.CFrame = CFrame.new(position + Vector3.new(0, 1, 0)) * CFrame.Angles(math.random() * 6, math.random() * 6, 0)
		chunk.Parent = folder()
		local dir = Vector3.new(math.random() - 0.5, 0.6 + math.random(), math.random() - 0.5).Unit
		chunk.AssemblyLinearVelocity = dir * (35 + math.random() * 45) * math.sqrt(scale)
		chunk.AssemblyAngularVelocity = Vector3.new(math.random() - 0.5, math.random() - 0.5, math.random() - 0.5) * 20
		local trail = emitter(chunk, {
			Texture = TEX.smoke,
			Color = SMOKE_COLORS,
			Size = ns({ { 0, 0.6 * scale }, { 1, 2.5 * scale } }),
			Transparency = ns({ { 0, 0.4 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.6, 1.1),
			Rate = 30,
			Speed = NumberRange.new(0),
		})
		trail.Enabled = true
		Debris:AddItem(chunk, 2.5 + math.random())
	end
end

-- A layered, particle-based explosion. `scale` ~1 for a buggy, ~1.5 for
-- a tank, 3-4 for the Siege Crawler's final blast.
-- opts.near: an impact right in front of the player's gun: no smoke or dust
-- (they would blind the camera), just flash, flame and sparks.
function Particles.explosion(position: Vector3, scale: number, opts: { air: boolean?, light: boolean?, debris: boolean?, near: boolean? }?)
	if liveExplosions >= MAX_EXPLOSIONS then
		return
	end
	liveExplosions += 1
	task.delay(5, function()
		liveExplosions -= 1
	end)
	local o = opts or {}
	local s = scale
	local anchor = Particles.anchor(CFrame.new(position))
	Debris:AddItem(anchor, 7)
	flash(anchor, Color3.fromRGB(255, 170, 90), 30 + 30 * s, 9, 0.7)

	emitter(anchor, { -- white-hot core
		Texture = TEX.sparkle,
		Color = ColorSequence.new(Color3.fromRGB(255, 240, 210)),
		LightEmission = 1,
		Size = ns({ { 0, 6 * s }, { 1, 12 * s } }),
		Transparency = ns({ { 0, 0 }, { 1, 1 } }),
		Lifetime = NumberRange.new(0.12, 0.18),
		Speed = NumberRange.new(0),
	}):Emit(3)
	emitter(anchor, { -- fireball
		Texture = TEX.fire,
		Color = FIRE_COLORS,
		LightEmission = 0.85,
		LightInfluence = 0,
		Size = ns({ { 0, 3 * s }, { 0.35, 8 * s }, { 1, 10 * s } }),
		Transparency = ns({ { 0, 0.05 }, { 0.6, 0.35 }, { 1, 1 } }),
		Lifetime = NumberRange.new(0.35, 0.8),
		Speed = NumberRange.new(8 * s, 26 * s),
		SpreadAngle = Vector2.new(180, 180),
		Drag = 4,
		Acceleration = Vector3.new(0, 8 * s, 0),
	}):Emit(math.floor(18 + 6 * s))
	emitter(anchor, { -- sparks / burning fragments
		Texture = TEX.sparks,
		Color = ColorSequence.new(Color3.fromRGB(255, 210, 120), Color3.fromRGB(255, 110, 40)),
		LightEmission = 1,
		Size = ns({ { 0, 0.5 * math.sqrt(s) }, { 1, 0.1 } }),
		Lifetime = NumberRange.new(0.6, 1.4),
		Speed = NumberRange.new(45 * math.sqrt(s), 110 * math.sqrt(s)),
		SpreadAngle = Vector2.new(180, 180),
		Acceleration = Vector3.new(0, -80, 0),
		Drag = 1,
		Orientation = Enum.ParticleOrientation.VelocityParallel,
	}):Emit(math.floor(24 + 8 * s))
	if o.near then
		return
	end
	emitter(anchor, { -- rolling smoke
		Texture = TEX.smoke,
		Color = SMOKE_COLORS,
		Size = ns({ { 0, 4 * s }, { 1, (if o.light then 12 else 20) * s } }),
		Transparency = ns({ { 0, 0.2 }, { 0.7, 0.55 }, { 1, 1 } }),
		Lifetime = if o.light then NumberRange.new(1.2, 2.2) else NumberRange.new(2.5, 4.5),
		Speed = NumberRange.new(4 * s, 12 * s),
		SpreadAngle = Vector2.new(180, 180),
		Drag = 1.5,
		Acceleration = Vector3.new(1.5, 5, 0.5),
		RotSpeed = NumberRange.new(-20, 20),
	}):Emit(math.floor(10 + 5 * s))
	if not o.air then
		emitter(anchor, { -- ground dust ring
			Texture = TEX.smoke,
			Color = DUST_COLORS,
			Size = ns({ { 0, 3 * s }, { 1, 12 * s } }),
			Transparency = ns({ { 0, 0.35 }, { 1, 1 } }),
			Lifetime = NumberRange.new(1.0, 1.8),
			Speed = NumberRange.new(28 * s, 40 * s),
			SpreadAngle = Vector2.new(85, 85),
			EmissionDirection = Enum.NormalId.Top,
			Drag = 3.5,
			Acceleration = Vector3.new(0, -4, 0),
		}):Emit(math.floor(14 + 4 * s))
	end
	if o.debris ~= false and s >= 0.8 then
		debrisChunks(position, math.min(s, 2), if s >= 2 then 7 else 4)
	end
end

-- Lasting fire and a leaning smoke column on `part` (a wreck). Destroyed
-- with the part. Beyond the budget only smoke is added.
function Particles.burn(part: BasePart, scale: number, offset: Vector3?, smokeOnly: boolean?)
	local att = Instance.new("Attachment")
	att.Name = "Burn"
	att.Position = offset or Vector3.new(0, part.Size.Y * 0.4, 0)
	att.Parent = part
	local s = scale
	local full = not smokeOnly and liveBurns < MAX_BURNS
	if full then
		liveBurns += 1
		att.Destroying:Connect(function()
			liveBurns -= 1
		end)
		local fire = emitter(att, {
			Texture = TEX.fire,
			Color = FIRE_COLORS,
			LightEmission = 0.8,
			LightInfluence = 0,
			Size = ns({ { 0, 3 * s }, { 0.4, 4.8 * s }, { 1, 1 * s } }),
			Transparency = ns({ { 0, 0.15 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.5, 1.1),
			Rate = 20 * s + 8,
			Speed = NumberRange.new(4, 9),
			SpreadAngle = Vector2.new(18, 18),
			Acceleration = Vector3.new(0, 7, 0),
		})
		fire.Enabled = true
		local light = Instance.new("PointLight")
		light.Name = "BurnLight"
		light.Color = Color3.fromRGB(255, 130, 50)
		light.Range = 16 + 10 * s
		light.Brightness = 2
		light.Shadows = false
		light.Parent = att
		flickering[light] = true
		light.Destroying:Connect(function()
			flickering[light] = nil
		end)
	end
	local smoke = emitter(att, {
		Texture = TEX.smoke,
		Color = SMOKE_COLORS,
		Size = ns({ { 0, 2.5 * s }, { 1, 18 * s } }),
		Transparency = ns({ { 0, 0.4 }, { 0.75, 0.6 }, { 1, 1 } }),
		Lifetime = NumberRange.new(5, 8.5),
		Rate = 3 + 3 * s,
		Speed = NumberRange.new(7, 12),
		SpreadAngle = Vector2.new(8, 8),
		Acceleration = Vector3.new(2.4, 0.8, 0.9),
		RotSpeed = NumberRange.new(-15, 15),
	})
	smoke.Enabled = true
end

-- Smoke trail (plus flames) streaming behind a falling aircraft/debris.
function Particles.trail(part: BasePart, scale: number): { ParticleEmitter }
	local s = scale
	local smoke = emitter(part, {
		Texture = TEX.smoke,
		Color = SMOKE_COLORS,
		Size = ns({ { 0, 2 * s }, { 1, 11 * s } }),
		Transparency = ns({ { 0, 0.25 }, { 1, 1 } }),
		Lifetime = NumberRange.new(2, 3.5),
		Rate = 45,
		Speed = NumberRange.new(0, 2),
		Acceleration = Vector3.new(0, 3, 0),
	})
	smoke.Name = "TrailSmoke"
	smoke.Enabled = true
	local fire = emitter(part, {
		Texture = TEX.fire,
		Color = FIRE_COLORS,
		LightEmission = 0.8,
		Size = ns({ { 0, 2 * s }, { 1, 0.5 * s } }),
		Transparency = ns({ { 0, 0.1 }, { 1, 1 } }),
		Lifetime = NumberRange.new(0.25, 0.5),
		Rate = 40,
		Speed = NumberRange.new(1, 3),
	})
	fire.Name = "TrailFire"
	fire.Enabled = true
	return { smoke, fire }
end

-- Muzzle blast: flame burst along `direction`, smoke puff, light flash.
function Particles.muzzle(position: Vector3, direction: Vector3, scale: number, color: Color3?)
	local s = scale
	local anchor = Particles.anchor(CFrame.lookAt(position, position + direction))
	Debris:AddItem(anchor, 3)
	flash(anchor, color or Color3.fromRGB(255, 180, 90), 12 + 14 * s, 6, 0.15)
	emitter(anchor, {
		Texture = TEX.fire,
		Color = FIRE_COLORS,
		LightEmission = 1,
		LightInfluence = 0,
		Size = ns({ { 0, 1.4 * s }, { 1, 2.6 * s } }),
		Transparency = ns({ { 0, 0 }, { 1, 1 } }),
		Lifetime = NumberRange.new(0.06, 0.14),
		Speed = NumberRange.new(20 * s, 40 * s),
		SpreadAngle = Vector2.new(12, 12),
		EmissionDirection = Enum.NormalId.Front,
	}):Emit(math.floor(4 + 3 * s))
	if s >= 0.6 then
		emitter(anchor, {
			Texture = TEX.smoke,
			Color = ColorSequence.new(Color3.fromRGB(120, 112, 104)),
			Size = ns({ { 0, 1.5 * s }, { 1, 7 * s } }),
			Transparency = ns({ { 0, 0.45 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.8, 1.6),
			Speed = NumberRange.new(4 * s, 12 * s),
			SpreadAngle = Vector2.new(40, 40),
			EmissionDirection = Enum.NormalId.Front,
			Drag = 2.5,
		}):Emit(math.floor(4 + 3 * s))
	end
end

-- A pulsing lens glint (telegraph) at `position` for `duration` seconds.
function Particles.glint(position: Vector3, duration: number, color: Color3, size: number): Part
	local anchor = Particles.anchor(CFrame.new(position))
	Debris:AddItem(anchor, duration + 0.3)
	local e = emitter(anchor, {
		Texture = TEX.sparkle,
		Color = ColorSequence.new(color),
		LightEmission = 1,
		LightInfluence = 0,
		Size = ns({ { 0, size * 0.4 }, { 0.5, size }, { 1, size * 0.3 } }),
		Transparency = ns({ { 0, 0.1 }, { 1, 1 } }),
		Lifetime = NumberRange.new(0.25, 0.35),
		Rate = 14,
		Speed = NumberRange.new(0),
		RotSpeed = NumberRange.new(-120, 120),
	})
	e.Enabled = true
	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = 18
	light.Brightness = 0
	light.Shadows = false
	light.Parent = anchor
	TweenService:Create(light, TweenInfo.new(duration, Enum.EasingStyle.Quad, Enum.EasingDirection.In), { Brightness = 6 }):Play()
	return anchor
end

-- Moves `body` from `from` to `to` over `duration` with an optional arc,
-- nose along the path, then calls `onArrive` and removes the body.
function Particles.fly(body: BasePart, from: Vector3, to: Vector3, duration: number, arc: number, onArrive: (() -> ())?)
	body.Anchored = true
	body.CanCollide = false
	body.CanQuery = false
	body.CanTouch = false
	body.CastShadow = false
	body.Parent = folder()
	local start = os.clock()
	local last = from
	local conn: RBXScriptConnection
	conn = RunService.RenderStepped:Connect(function()
		local t = math.min(1, (os.clock() - start) / duration)
		local p = from:Lerp(to, t) + Vector3.new(0, math.sin(t * math.pi) * arc, 0)
		if (p - last).Magnitude > 1e-3 then
			body.CFrame = CFrame.lookAt(p, p + (p - last))
		end
		last = p
		if t >= 1 then
			conn:Disconnect()
			-- Let trailing particles fade before the carrier goes.
			body.Transparency = 1
			for _, d in body:GetDescendants() do
				if d:IsA("ParticleEmitter") then
					d.Enabled = false
				elseif d:IsA("BasePart") then
					d.Transparency = 1
				elseif d:IsA("Light") then
					d.Enabled = false
				end
			end
			Debris:AddItem(body, 4)
			if onArrive then
				onArrive()
			end
		end
	end)
	Debris:AddItem(body, duration + 5)
end

-- A small projectile body: `core` glowing streak and optional smoke trail.
function Particles.projectile(length: number, width: number, color: Color3, smoky: boolean, glow: number?): Part
	local body = Instance.new("Part")
	body.Name = "EnemyProjectile"
	body.Size = Vector3.new(width, width, length)
	body.Color = color
	body.Material = Enum.Material.Neon
	if glow and glow > 0 then
		local light = Instance.new("PointLight")
		light.Color = color
		light.Range = glow
		light.Brightness = 3
		light.Shadows = false
		light.Parent = body
	end
	if smoky then
		local e = emitter(body, {
			Texture = TEX.smoke,
			Color = ColorSequence.new(Color3.fromRGB(150, 142, 134), Color3.fromRGB(110, 104, 98)),
			Size = ns({ { 0, width * 1.5 }, { 1, width * 7 } }),
			Transparency = ns({ { 0, 0.3 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.8, 1.4),
			Rate = 90,
			Speed = NumberRange.new(0, 1),
			EmissionDirection = Enum.NormalId.Back,
		})
		e.Enabled = true
		local f = emitter(body, {
			Texture = TEX.fire,
			Color = FIRE_COLORS,
			LightEmission = 1,
			Size = ns({ { 0, width * 2 }, { 1, width * 0.5 } }),
			Transparency = ns({ { 0, 0 }, { 1, 1 } }),
			Lifetime = NumberRange.new(0.05, 0.12),
			Rate = 80,
			Speed = NumberRange.new(2, 4),
			EmissionDirection = Enum.NormalId.Back,
		})
		f.Enabled = true
	end
	return body
end

-- Flickers every burn light a little each frame (one loop for all).
function Particles.startFlicker()
	RunService.Heartbeat:Connect(function()
		local t = os.clock()
		for light in flickering do
			if light.Parent then
				light.Brightness = 1.6 + math.noise(t * 6, light.Range) * 1.4
			else
				flickering[light] = nil
			end
		end
	end)
end

return Particles
