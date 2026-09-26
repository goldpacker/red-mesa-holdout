--!strict
-- Explosions, debris, scorch marks and fires for every weapon, plus the
-- enemy-fire pieces (VFX-2). Built on client/Effects (custom flipbooks,
-- never Roblox's built-in particle textures).
--   explosion  flash -> fireball -> shockwave ring -> debris meshes ->
--              smoke column -> ground scorch, scaled per weapon/enemy
--   burn       lasting fire + leaning smoke column on a wreck
--   trail      smoke/fire trail behind a falling aircraft or thrown piece
--   projectile / bomb / fly    enemy shells, rockets and bombs in flight
--   muzzle / glint / chargeFlare / dustRing
-- Caps: MAX_EXPLOSIONS, MAX_BURNS, MAX_DEBRIS, MAX_SCORCH. Local-only
-- instances live in Workspace.CombatFx (client/Effects.folder).

local Debris = game:GetService("Debris")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Flipbooks = require(ReplicatedStorage.Shared.Flipbooks)
local Effects = require(script.Parent.Effects)

local Particles = {}

local MAX_EXPLOSIONS = 14
local MAX_BURNS = 16
local MAX_DEBRIS = 40
local MAX_SCORCH = 12

local seq, sized, emitter, emit, anchor = Effects.seq, Effects.sized, Effects.emitter, Effects.emit, Effects.anchor
local lod, camDistance = Effects.lod, Effects.camDistance
local WIND, SMOKE = Effects.WIND, Effects.SMOKE

local liveExplosions = 0
local liveBurns = 0

---------------------------------------------------------------------------
-- Debris meshes on ballistic arcs (ReplicatedStorage.Assets.VfxDebris)
---------------------------------------------------------------------------

type Chunk = { part: BasePart, vel: Vector3, spin: CFrame, landed: number?, trail: ParticleEmitter? }
local chunks: { Chunk } = {}
local PIECES = {
	vehicle = { "Shard1", "Shard2", "Shard3", "Shard4", "Shard1", "Clod1" },
	ground = { "Clod1", "Clod2", "Chunk1", "Clod2" },
	rock = { "Chunk1", "Chunk2", "Chunk1", "Clod1" },
}
local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include

-- A fresh copy of a VfxDebris piece (Shard1-4, Chunk1-2, Clod1-2, Bomb,
-- Rocket), or nil if the asset isn't there.
function Particles.piece(name: string): BasePart?
	local assets = ReplicatedStorage:FindFirstChild("Assets")
	local lib = assets and assets:FindFirstChild("VfxDebris")
	local template = lib and lib:FindFirstChild(name, true)
	if template and template:IsA("BasePart") then
		local p = template:Clone()
		p.Anchored = true
		p.CanCollide = false
		p.CanQuery = false
		p.CanTouch = false
		p.CastShadow = false
		return p
	end
	return nil
end

local function throwDebris(position: Vector3, scale: number, count: number, set: string, smoky: boolean)
	local names: { string } = (PIECES :: any)[set] or PIECES.ground
	for i = 1, count do
		if #chunks >= MAX_DEBRIS then
			return
		end
		local part = Particles.piece(names[(i - 1) % #names + 1])
		if not part then
			return
		end
		local size = (0.7 + math.random() * 0.9) * math.min(scale, 2.2)
		part.Size = part.Size * size
		part.CFrame = CFrame.new(position + Vector3.new(0, 1.5, 0)) * CFrame.Angles(math.random() * 6.3, math.random() * 6.3, 0)
		part.Parent = Effects.folder()
		local dir = Vector3.new(math.random() - 0.5, 0.7 + math.random() * 0.9, math.random() - 0.5).Unit
		local c: Chunk = {
			part = part,
			vel = dir * (35 + math.random() * 45) * math.sqrt(scale),
			spin = CFrame.Angles((math.random() - 0.5) * 0.5, (math.random() - 0.5) * 0.5, (math.random() - 0.5) * 0.5),
			landed = nil,
			trail = nil,
		}
		if smoky and i <= 3 then
			local e = emitter(part, "MissileTrail", 0.45 * size, {
				Color = ColorSequence.new(SMOKE),
				Rate = 16,
				Lifetime = NumberRange.new(0.7, 1.1),
				Transparency = seq(0.35, 0.6, 1),
			})
			if e then
				e.Enabled = true
				c.trail = e
			end
		end
		table.insert(chunks, c)
		Debris:AddItem(part, 8)
	end
end

local function stepDebris(dt: number)
	if #chunks == 0 or Effects.frozen() then
		return
	end
	groundParams.FilterDescendantsInstances = { Workspace.Terrain }
	local g = Workspace.Gravity * 0.75
	local now = os.clock()
	for i = #chunks, 1, -1 do
		local c = chunks[i]
		local part = c.part
		if not part.Parent then
			table.remove(chunks, i)
		elseif c.landed then
			if now - c.landed > 1.6 then
				part.Transparency = math.min(1, part.Transparency + dt * 1.5)
				if part.Transparency >= 1 then
					part:Destroy()
					table.remove(chunks, i)
				end
			end
		else
			local p0 = part.Position
			c.vel -= Vector3.new(0, g * dt, 0)
			local step = c.vel * dt
			local hit = if c.vel.Y < 0 then Workspace:Raycast(p0, step, groundParams) else nil
			if hit then
				part.CFrame = CFrame.new(hit.Position + hit.Normal * part.Size.Y * 0.3) * part.CFrame.Rotation
				c.landed = now
				if c.trail then
					c.trail.Enabled = false
				end
			else
				part.CFrame = CFrame.new(p0 + step) * part.CFrame.Rotation * c.spin
			end
		end
	end
end

---------------------------------------------------------------------------
-- Scorch decals (on the ground only; fade out; capped)
---------------------------------------------------------------------------

local scorches: { BasePart } = {}
local scorchTex = Flipbooks.texture("ScorchMark")

-- A burn mark on the terrain under `position` (skipped on steep or missing
-- ground). The oldest mark goes when MAX_SCORCH is reached.
function Particles.scorch(position: Vector3, size: number)
	if not scorchTex then
		return
	end
	local hit = Effects.groundBelow(position + Vector3.new(0, 1, 0), 6 + size * 0.4)
	if not hit or hit.Normal.Y < 0.55 then
		return
	end
	while #scorches >= MAX_SCORCH do
		local old = table.remove(scorches, 1)
		if old then
			old:Destroy()
		end
	end
	local p = Instance.new("Part")
	p.Name = "Scorch"
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Transparency = 1
	p.Size = Vector3.new(size, 0.2, size)
	local n = hit.Normal
	local ref = if math.abs(n.X) < 0.9 then Vector3.xAxis else Vector3.zAxis
	p.CFrame = CFrame.fromMatrix(hit.Position + n * 0.12, ref:Cross(n).Unit, n) * CFrame.Angles(0, math.random() * 6.3, 0)
	local decal = Instance.new("Decal")
	decal.Face = Enum.NormalId.Top
	decal.Texture = scorchTex
	decal.Transparency = 0.1
	decal.Parent = p
	p.Parent = Effects.folder()
	table.insert(scorches, p)
	task.delay(14, function()
		if p.Parent then
			TweenService:Create(decal, TweenInfo.new(10, Enum.EasingStyle.Linear), { Transparency = 1 }):Play()
		end
	end)
	task.delay(24.5, function()
		local i = table.find(scorches, p)
		if i then
			table.remove(scorches, i)
		end
		p:Destroy()
	end)
end

---------------------------------------------------------------------------
-- Layered explosion
---------------------------------------------------------------------------

export type Blast = {
	air: boolean?, -- in the air: no ground layers, spherical, lighter smoke
	near: boolean?, -- at the outpost: no smoke column or debris (keeps the view clear)
	light: boolean?, -- small secondary blast: short smoke
	debris: boolean?, -- false: no debris meshes
	scorch: boolean?, -- false: no scorch decal
	set: string?, -- debris: "vehicle" (default) | "ground" | "rock" | "surface" (by what was hit)
}

local DUSTY_SMOKE = Color3.fromRGB(122, 108, 92)

-- A column of billows that rises, drifts downwind and thins out (it must
-- not hide targets for long): a first puff plus `linger` s of trickle.
local function smokeColumn(a: Attachment, s: number, n: number, linger: number, lifetime: { number }, color: Color3)
	local smoke = emitter(a, "SmokeDark", s * 0.6, {
		Color = ColorSequence.new(color),
		Lifetime = NumberRange.new(lifetime[1], lifetime[2]),
		-- Fades in, so the fireball shows first; thins out as it rises.
		Transparency = seq(0.85, 0.42, 0.55, 0.75, 1),
		Speed = NumberRange.new(5 * s, 10 * s),
		SpreadAngle = Vector2.new(25, 25),
		Drag = 0.8,
		Acceleration = WIND + Vector3.new(0, 5 + s, 0),
	})
	emit(smoke, n)
	if smoke and linger > 0 then
		smoke.Rate = 1.2 * s + 0.6
		smoke.Enabled = true
		task.delay(linger, function()
			smoke.Enabled = false
		end)
	end
end

-- Dirt thrown up and a dust ring rolling out along the ground at `at`.
local function groundBlast(at: Vector3, s: number, rocky: boolean, near: boolean)
	local kickSize = 11 * s
	local kickAt = anchor(CFrame.new(at + Vector3.new(0, 0.385 * kickSize, 0)), 4)
	emit(emitter(kickAt, "SandKick", 0, {
		Size = seq(kickSize * 0.8, kickSize),
		Lifetime = NumberRange.new(1.1, 1.4),
		Color = ColorSequence.new(if rocky then Effects.ROCK_DUST else Effects.SAND),
		-- Half lit: the blast's own flash light would bleach it white.
		LightInfluence = 0.5,
	}), if near then 1 else 2)
	local ringAt = anchor(CFrame.new(at + Vector3.new(0, 1, 0)), 4)
	emit(emitter(ringAt, "DustPuff", s, {
		Color = ColorSequence.new(if rocky then Effects.ROCK_DUST else Effects.DUST),
		LightInfluence = 0.5,
		Size = sized(s, 3, 9, 12),
		Transparency = if near then seq(0.5, 0.7, 1) else seq(0.28, 0.45, 1),
		Lifetime = if near then NumberRange.new(0.8, 1.1) else NumberRange.new(1.4, 2.2),
		Speed = NumberRange.new(22 * s, 34 * s),
		SpreadAngle = Vector2.new(82, 82),
		Drag = 4,
		Acceleration = WIND * 0.5,
	}), if near then 2 else lod(7, at))
	emit(emitter(ringAt, "ShockwaveRing", 0.9 * s, {
		Color = ColorSequence.new(Color3.fromRGB(196, 164, 124)),
		Orientation = Enum.ParticleOrientation.VelocityPerpendicular,
		Speed = NumberRange.new(0.05),
		Transparency = seq(0.35, 1),
		SpreadAngle = Vector2.zero,
	}), 1)
end

-- `scale` ~0.5 small burst, 1 = our rocket / a buggy, 1.5-2 tank or bomb,
-- 2.4-4 boss. Ground layers go on the terrain found under `position`.
function Particles.explosion(position: Vector3, scale: number, opts: Blast?)
	-- Big blasts (tank, bomb, boss finale) may exceed the cap a little so a
	-- burst of small ones never swallows them.
	local cap = if scale >= 1.5 then MAX_EXPLOSIONS + 6 else MAX_EXPLOSIONS
	if liveExplosions >= cap then
		return
	end
	liveExplosions += 1
	task.delay(2.5, function()
		liveExplosions -= 1
	end)
	local o: Blast = opts or ({} :: Blast)
	local s = scale
	local k = Effects.exposure()
	local near = o.near == true
	local ground = if o.air then nil else Effects.groundBelow(position, 5 + 5 * s)
	local rocky = Effects.isRocky(ground)
	local a = anchor(CFrame.new(position + Vector3.new(0, if ground then 1.2 * s else 0, 0)), 10)
	Effects.flash(a, Effects.FIRE_LIGHT, if near then 12 + 8 * s else 24 + 18 * s, (if near then 2 else 4) * k, 0.6)

	-- Flash: a short white-hot burst ahead of the fireball. Right in front
	-- of the gun (near) everything is smaller and dimmer so the player can
	-- still see past it.
	-- Near the gun the fireball is capped in size and thrown upward so the
	-- player keeps sight of the road (a bomb stick is four of these).
	local fireScale = if near then math.min(0.4 * s, 0.6) else 0.75 * s
	emit(emitter(a, "MuzzleFlashBurst", if near then math.min(0.6 * s, 0.9) else 1.35 * s, {
		Brightness = (if near then 1 else 1.3) * k,
		Lifetime = NumberRange.new(0.08, 0.12),
	}), 1)
	-- Fireball: a few Mantaflow fireballs pushed apart, rising.
	emit(emitter(a, "Fireball", fireScale, {
		Brightness = (if near then 1 else 1.3) * k,
		LightEmission = 0.25,
		-- Near the gun the fire is thrown up so it clears the parapet.
		Speed = if near then NumberRange.new(8 * s, 15 * s) else NumberRange.new(3 * s, 9 * s),
		SpreadAngle = if near then Vector2.new(40, 40) elseif ground then Vector2.new(70, 70) else Vector2.new(180, 180),
		Drag = 3,
		Acceleration = Vector3.new(0, 5 * s, 0),
		Lifetime = if near then NumberRange.new(0.9, 1.1) else NumberRange.new(1.2, 1.5),
	}), if near then 1 else lod(3 + math.floor(s), position))
	-- Sparks and burning fragments.
	emit(emitter(a, "Sparks", (if near then 1.2 else 1.7) * s, { Brightness = 1.6 * k, Lifetime = NumberRange.new(0.6, 0.85) }), if near then 1 else 2)
	if ground then
		groundBlast(ground.Position, if near then math.min(s, 1) * 0.7 else s, rocky, near)
	elseif near then
		-- A hit on the mesa face below the gun: rock chips and red dust.
		emit(emitter(a, "RockChips", 0, {
			Size = seq(7 * math.min(s, 1.2), 9 * math.min(s, 1.2)),
			Color = ColorSequence.new(Effects.ROCK),
		}), 1)
		emit(emitter(a, "DustPuff", s, {
			Color = ColorSequence.new(Effects.ROCK_DUST),
			LightInfluence = 0.5,
			Transparency = seq(0.4, 0.6, 1),
			Lifetime = NumberRange.new(0.9, 1.3),
			Speed = NumberRange.new(8 * s, 16 * s),
			SpreadAngle = Vector2.new(50, 50),
			Drag = 3,
		}), 2)
	elseif o.air then
		-- A true air burst: a faint, fast camera-facing shock ring.
		emit(emitter(a, "ShockwaveRing", 0.6 * s, {
			Color = ColorSequence.new(Color3.fromRGB(255, 226, 184)),
			Orientation = Enum.ParticleOrientation.FacingCamera,
			Transparency = seq(0.7, 1),
			Lifetime = NumberRange.new(0.2, 0.25),
		}), 1)
	end
	if ground and o.scorch ~= false then
		Particles.scorch(ground.Position, (if near then 7 else 10 + 2 * s) * s)
	end
	if near then
		return
	end
	-- Lingering smoke column: oily black over burning vehicles, dusty
	-- brown-grey for blasts in the dirt.
	local oily = (o.set or "vehicle") == "vehicle"
	local tint = if oily then SMOKE else DUSTY_SMOKE
	task.delay(0.25, function()
		if not a.Parent then
			return
		end
		if o.light or not ground then
			smokeColumn(a, s * 0.8, lod(2 + math.floor(s * 0.5), position), 0, { 2.4, 3.4 }, if ground then tint else Color3.fromRGB(104, 96, 88))
		else
			smokeColumn(a, s, lod(2 + math.floor(s), position), 1 + 0.4 * s, { 3.5, 5.5 }, tint)
		end
	end)
	if o.debris ~= false and s >= 0.7 and camDistance(position) < 900 then
		local set = o.set or "vehicle"
		if set == "surface" then
			set = if rocky then "rock" elseif ground then "ground" else "vehicle"
		end
		throwDebris(position, s, math.floor(3 + 2 * math.min(s, 2.5)), set, s >= 1.2)
	end
end

-- Muzzle blast dust around a firing gun (no fire): kick + rolling ring.
function Particles.dustRing(position: Vector3, scale: number)
	local ground = Effects.groundBelow(position, 8)
	if ground then
		groundBlast(ground.Position, scale * 0.6, Effects.isRocky(ground), false)
	end
end

---------------------------------------------------------------------------
-- Lasting fire + smoke column (wrecks, the emplacement at defeat)
---------------------------------------------------------------------------

local flickering: { [PointLight]: number } = {}

-- Fire and a leaning smoke column on `part`; they go when the part goes.
-- Beyond MAX_BURNS (or with smokeOnly) only the smoke is added.
function Particles.burn(part: BasePart, scale: number, offset: Vector3?, smokeOnly: boolean?)
	local s = scale
	local base = offset or Vector3.new(0, part.Size.Y * 0.4, 0)
	if not smokeOnly and liveBurns < MAX_BURNS then
		liveBurns += 1
		local fireSize = 6.5 * s
		local att = Instance.new("Attachment")
		att.Name = "Burn"
		-- The Flames sheet's base line sits 39% of the particle below its centre.
		att.Position = base + Vector3.new(0, 0.39 * fireSize * 0.9, 0)
		att.Parent = part
		att.Destroying:Connect(function()
			liveBurns -= 1
		end)
		local fire = emitter(att, "Flames", 1, {
			Size = seq(fireSize * 0.75, fireSize, fireSize * 0.85),
			Transparency = seq(0.6, 0.05, 0.1, 1),
			Lifetime = NumberRange.new(0.8, 1.2),
			Rate = 4 + 3 * s,
			Speed = NumberRange.new(0.4, 1.2),
			SpreadAngle = Vector2.new(10, 10),
			Color = ColorSequence.new(Color3.fromRGB(255, 226, 200)),
			LightEmission = 0.55,
			LightInfluence = 0,
			Brightness = 1.4 * Effects.exposure(),
		})
		if fire then
			fire.Enabled = true
		end
		local light = Instance.new("PointLight")
		light.Name = "BurnLight"
		light.Color = Color3.fromRGB(255, 130, 50)
		light.Range = 16 + 10 * s
		light.Brightness = 2
		light.Shadows = false
		light.Parent = att
		flickering[light] = light.Range
		light.Destroying:Connect(function()
			flickering[light] = nil
		end)
	end
	local smokeAtt = Instance.new("Attachment")
	smokeAtt.Name = "BurnSmoke"
	smokeAtt.Position = base + Vector3.new(0, 2 * s, 0)
	smokeAtt.Parent = part
	local smoke = emitter(smokeAtt, "SmokeDark", 0, {
		Color = ColorSequence.new(SMOKE),
		Size = sized(s, 3, 11, 19),
		Transparency = seq(0.35, 0.45, 1),
		Lifetime = NumberRange.new(5, 7.5),
		Rate = 1.4 + 1.6 * s,
		Speed = NumberRange.new(6, 10),
		SpreadAngle = Vector2.new(8, 8),
		Acceleration = WIND + Vector3.new(0, 0.8, 0),
	})
	if smoke then
		smoke.Enabled = true
	end
end

-- Kept for VehicleFx: one Heartbeat loop flickers every burn light.
function Particles.startFlicker() end

---------------------------------------------------------------------------
-- Trails, enemy muzzle flashes, telegraphs
---------------------------------------------------------------------------

-- Smoke trail (plus flames) streaming behind a falling aircraft/debris.
function Particles.trail(part: BasePart, scale: number): { ParticleEmitter }
	local s = scale
	local out = {}
	local smoke = emitter(part, "MissileTrail", 0, {
		Name = "TrailSmoke",
		Color = ColorSequence.new(SMOKE),
		Size = sized(s, 2, 8, 12),
		Transparency = seq(0.2, 0.4, 1),
		Lifetime = NumberRange.new(2, 3.2),
		Rate = 32,
		Speed = NumberRange.new(0, 2),
		Acceleration = Vector3.new(0, 3, 0),
	})
	local fire = emitter(part, "Flames", 0, {
		Name = "TrailFire",
		Size = sized(s, 2.6, 3.2, 2),
		Transparency = seq(0.4, 0.1, 1),
		Lifetime = NumberRange.new(0.3, 0.5),
		Rate = 26,
		Speed = NumberRange.new(1, 3),
		LightEmission = 0.6,
	})
	for _, e in { smoke, fire } do
		if e then
			e.Enabled = true
			table.insert(out, e)
		end
	end
	return out
end

-- Muzzle blast along `direction`; `color` tints the flash light.
function Particles.muzzle(position: Vector3, direction: Vector3, scale: number, color: Color3?)
	Effects.enemyMuzzle(position, direction, scale, color)
end

local function carrier(cf: CFrame, lifetime: number): Part
	local p = Instance.new("Part")
	p.Name = "Fx"
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Transparency = 1
	p.Size = Vector3.one
	p.CFrame = cf
	p.Parent = Effects.folder()
	Debris:AddItem(p, lifetime)
	return p
end

-- A pulsing star glint (telegraph) at `position` for `duration` seconds.
function Particles.glint(position: Vector3, duration: number, color: Color3, size: number): Part
	local p = carrier(CFrame.new(position), duration + 0.3)
	local e = emitter(p, "MuzzleFlashFront", 0, {
		Color = ColorSequence.new(color),
		Size = seq(size * 0.35, size * 0.9, size * 0.3),
		Transparency = seq(0.1, 1),
		Lifetime = NumberRange.new(0.25, 0.35),
		Brightness = 1.2 * Effects.exposure(),
		Rate = 14,
		RotSpeed = NumberRange.new(-120, 120),
	})
	if e then
		e.Enabled = true
	end
	local light = Instance.new("PointLight")
	light.Color = color
	light.Range = 36
	light.Brightness = 0
	light.Shadows = false
	light.Parent = p
	TweenService:Create(light, TweenInfo.new(duration, Enum.EasingStyle.Quad, Enum.EasingDirection.In), { Brightness = 9 * Effects.exposure() }):Play()
	return p
end

-- Charge-up flare for the Siege Crawler's cannon; VehicleFx drives its
-- Rate and Size each frame.
function Particles.chargeFlare(part: BasePart): ParticleEmitter?
	local e = emitter(part, "MuzzleFlashFront", 0, {
		Name = "ChargeFlare",
		Color = ColorSequence.new(Color3.fromRGB(255, 200, 150), Color3.fromRGB(255, 90, 40)),
		Size = seq(6, 14, 4),
		Transparency = seq(0.2, 1),
		Lifetime = NumberRange.new(0.2, 0.35),
		Brightness = 1.3,
		RotSpeed = NumberRange.new(-200, 200),
	})
	if e then
		e.Enabled = true
	end
	return e
end

---------------------------------------------------------------------------
-- Enemy projectiles
---------------------------------------------------------------------------

-- Moves `body` from `from` to `to` over `duration` with an optional arc,
-- nose along the path, then calls `onArrive` and removes the body.
function Particles.fly(body: BasePart, from: Vector3, to: Vector3, duration: number, arc: number, onArrive: (() -> ())?)
	body.Anchored = true
	body.CanCollide = false
	body.CanQuery = false
	body.CanTouch = false
	body.CastShadow = false
	body.CFrame = CFrame.lookAt(from, to)
	body.Parent = Effects.folder()
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
				if d:IsA("ParticleEmitter") or d:IsA("Beam") or d:IsA("Light") then
					d.Enabled = false
				elseif d:IsA("BasePart") then
					d.Transparency = 1
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

-- A projectile in flight: an invisible carrier with a glowing tracer
-- streak along its length, and for rockets an exhaust flame and smoke.
function Particles.projectile(length: number, width: number, color: Color3, smoky: boolean, glow: number?): Part
	local body = Instance.new("Part")
	body.Name = "EnemyProjectile"
	body.Size = Vector3.new(width, width, length)
	body.Transparency = 1
	local tex = Flipbooks.texture("TracerBeam")
	if tex then
		local a0 = Instance.new("Attachment")
		a0.Position = Vector3.new(0, 0, length / 2)
		a0.Parent = body
		local a1 = Instance.new("Attachment")
		a1.Position = Vector3.new(0, 0, -length / 2)
		a1.Parent = body
		local beam = Instance.new("Beam")
		beam.Attachment0 = a0
		beam.Attachment1 = a1
		beam.Texture = tex
		beam.TextureMode = Enum.TextureMode.Stretch
		beam.FaceCamera = true
		beam.LightEmission = 1
		beam.LightInfluence = 0
		beam.Brightness = 2.5 * Effects.exposure()
		beam.Color = ColorSequence.new(color)
		beam.Width0 = width * 1.5
		beam.Width1 = width * 3
		beam.Transparency = NumberSequence.new(1, 0)
		beam.Segments = 1
		beam.Parent = body
	end
	if glow and glow > 0 then
		local light = Instance.new("PointLight")
		light.Color = color
		light.Range = glow
		light.Brightness = 3 * Effects.exposure()
		light.Shadows = false
		light.Parent = body
	end
	if smoky then
		local tail = Instance.new("Attachment")
		tail.Name = "Tail"
		tail.CFrame = CFrame.new(0, 0, length / 2) * CFrame.Angles(math.rad(90), 0, 0)
		tail.Parent = body
		local flame = emitter(tail, "RocketExhaust", width * 0.9, {
			Speed = NumberRange.new(1),
			LockedToPart = true,
			Brightness = 1.2 * Effects.exposure(),
		})
		local smoke = emitter(tail, "MissileTrail", width * 0.9, {
			Color = ColorSequence.new(Color3.fromRGB(176, 168, 158)),
			Rate = 60,
			Speed = NumberRange.new(0.5, 1.5),
			Lifetime = NumberRange.new(0.9, 1.5),
		})
		for _, e in { flame, smoke } do
			if e then
				e.Enabled = true
			end
		end
		if flame then
			flame.Rate = 45
		end
	end
	return body
end

-- A falling enemy bomb (VfxDebris.Bomb, nose along -Z).
function Particles.bomb(): BasePart
	local bomb = Particles.piece("Bomb")
	if bomb then
		bomb.Name = "EnemyProjectile"
		return bomb
	end
	local p = Instance.new("Part")
	p.Name = "EnemyProjectile"
	p.Size = Vector3.new(1, 1, 3.4)
	p.Material = Enum.Material.Metal
	p.Color = Color3.fromRGB(40, 40, 42)
	local mesh = Instance.new("SpecialMesh")
	mesh.MeshType = Enum.MeshType.Sphere
	mesh.Parent = p
	return p
end

RunService.RenderStepped:Connect(stepDebris)

RunService.Heartbeat:Connect(function()
	local t = os.clock()
	local k = Effects.exposure()
	for light, range in flickering do
		if light.Parent then
			light.Brightness = (1.6 + math.noise(t * 6, range) * 1.4) * k
		else
			flickering[light] = nil
		end
	end
end)

return Particles
