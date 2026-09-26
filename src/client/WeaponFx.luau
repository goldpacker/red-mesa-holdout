--!strict
-- Client rendering of server-simulated rockets and missiles, their
-- explosions, and machine-gun ricochets on armour. VFX-2: the rocket is
-- the VfxDebris.Rocket mesh and the missile a copy of the rack's missile,
-- with flipbook exhaust, smoke trails and layered explosions.
--
-- Server events (Remotes.GameEvent):
--   Projectile    {id, kind, origin, dir, speed, t0, owner, token, targetId}
--   ProjectileEnd {id, kind, position, exploded, air?, enemy?}
--   Ricochet      {position}
-- The firing client predicts its own shot immediately (WeaponFx.predict)
-- and adopts the server's id when the matching `Projectile` event arrives.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local WeaponConfig = require(ReplicatedStorage.Shared.WeaponConfig)
local Flipbooks = require(ReplicatedStorage.Shared.Flipbooks)
local AimController = require(script.Parent.AimController)
local Blasts = require(script.Parent.VehicleFxParticles)
local Effects = require(script.Parent.Effects)
local Surface = require(script.Parent.EffectsSurface)
local GameState = require(script.Parent.GameState)
local Particles = require(script.Parent.WeaponFxParticles)
local Sfx = require(script.Parent.Sfx)

local WeaponFx = {}

type Visual = {
	kind: string,
	part: BasePart,
	emitters: { ParticleEmitter },
	pos: Vector3, -- simulated (server-path) position
	dir: Vector3,
	speed: number,
	age: number,
	offset: Vector3, -- muzzle-to-server-origin blend, decays to zero
	target: Model?,
	targetLast: Vector3?,
	targetVel: Vector3,
	exploded: Vector3?, -- where it visibly detonated locally
	onRock: boolean?, -- ...on a landscape mesh face, in front of the server's terrain hit
	done: boolean,
	confirmed: boolean,
}

local ROCKET = WeaponConfig.Rocket
local MISSILE = WeaponConfig.Missile
local BLEND_TIME = 0.2
local UNCONFIRMED_TIMEOUT = 1.2
local MAX_VISUALS = 12
local SMOKE_LINGER = 2.6

local player = Players.LocalPlayer
local byId: { [number]: Visual } = {}
local byToken: { [number]: Visual } = {}
local visuals: { Visual } = {}

local rayParams = RaycastParams.new()
rayParams.FilterType = Enum.RaycastFilterType.Exclude

local function container(): Instance
	return Workspace:FindFirstChild("Projectiles") or Workspace
end

local function refreshFilter()
	local list: { Instance } = { container() }
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local emplacement = battlefield and battlefield:FindFirstChild("Emplacement")
	if emplacement then
		table.insert(list, emplacement)
	end
	local wrecks = Workspace:FindFirstChild("Wrecks")
	if wrecks then
		table.insert(list, wrecks)
	end
	rayParams.FilterDescendantsInstances = list
end

local function enemyModel(id: number?): Model?
	if not id then
		return nil
	end
	local folder = Workspace:FindFirstChild("Enemies")
	if not folder then
		return nil
	end
	for _, m in folder:GetChildren() do
		if m:GetAttribute("EnemyId") == id and m:IsA("Model") then
			return m
		end
	end
	return nil
end

-- The rack's own missile mesh (HS asset), so the round that leaves the
-- rail looks like the one that was on it.
local function missileMesh(): BasePart?
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local emplacement = battlefield and battlefield:FindFirstChild("Emplacement")
	local rack = emplacement and emplacement:FindFirstChild("Missile1", true)
	if rack and rack:IsA("BasePart") then
		local copy = rack:Clone()
		copy:ClearAllChildren()
		for _, name in { "SurfaceAppearance" } do
			local sa = rack:FindFirstChildOfClass(name)
			if sa then
				sa:Clone().Parent = copy
			end
		end
		copy.Transparency = 0
		copy.LocalTransparencyModifier = 0
		return copy
	end
	return nil
end

local function buildBody(kind: string): (BasePart, { ParticleEmitter })
	local missile = kind == "Missile"
	local mesh = if missile then missileMesh() else Blasts.piece("Rocket")
	local body: BasePart
	if mesh then
		body = mesh
	else
		-- No mesh available: an invisible carrier (the exhaust carries the look).
		local p = Instance.new("Part")
		p.Size = if missile then Vector3.new(0.45, 0.45, 3.4) else Vector3.new(0.5, 0.5, 2.6)
		p.Transparency = 1
		body = p
	end
	body.Name = kind
	body.Anchored = true
	body.CanCollide = false
	body.CanQuery = false
	body.CanTouch = false
	body.CastShadow = false
	local tail = Instance.new("Attachment")
	tail.Name = "Tail"
	-- Emitters shoot along +Y; point it out of the back (+Z).
	tail.CFrame = CFrame.new(0, 0, body.Size.Z / 2) * CFrame.Angles(math.rad(90), 0, 0)
	tail.Parent = body
	local k = Effects.exposure()
	local light = Instance.new("PointLight")
	light.Color = if missile then Color3.fromRGB(255, 236, 200) else Color3.fromRGB(255, 170, 90)
	light.Range = if missile then 16 else 12
	light.Brightness = (if missile then 3 else 2.2) * k
	light.Shadows = false
	light.Parent = tail
	-- Short hot exhaust streak (textured, fades to the tail).
	local a0 = Instance.new("Attachment")
	a0.Position = Vector3.new(0, 0.15, body.Size.Z / 2)
	a0.Parent = body
	local a1 = Instance.new("Attachment")
	a1.Position = Vector3.new(0, -0.15, body.Size.Z / 2)
	a1.Parent = body
	local trail = Instance.new("Trail")
	trail.Attachment0 = a0
	trail.Attachment1 = a1
	trail.Texture = Flipbooks.texture("TracerBeam") or ""
	trail.TextureMode = Enum.TextureMode.Stretch
	trail.Lifetime = if missile then 0.3 else 0.15
	trail.LightEmission = 1
	trail.Brightness = 1.6 * k
	trail.FaceCamera = true
	trail.WidthScale = NumberSequence.new(1, 0.2)
	trail.Color = if missile
		then ColorSequence.new(Color3.fromRGB(255, 250, 236), Color3.fromRGB(255, 190, 120))
		else ColorSequence.new(Color3.fromRGB(255, 206, 130), Color3.fromRGB(255, 110, 40))
	trail.Transparency = NumberSequence.new(0.1, 1)
	trail.Parent = body
	local emitters = Particles.trail(tail, kind)
	body.Parent = container()
	return body, emitters
end

local function shakeFor(position: Vector3, radius: number, strength: number)
	local camPos = Workspace.CurrentCamera.CFrame.Position
	local k = math.clamp(1 - (position - camPos).Magnitude / radius, 0, 1)
	AimController.shake(0.04 + strength * k * k)
end

local function explodeAt(v: Visual, position: Vector3, air: boolean)
	local missile = v.kind == "Missile"
	Particles.explosion(position, if missile then 0.85 else 1, air)
	Sfx.playAt(if missile then "AirBurst" else "Explosion", position, 0.2)
	shakeFor(position, if missile then MISSILE.SHAKE_RADIUS else ROCKET.SHAKE_RADIUS, 0.6)
end

-- Stops the body and lets the smoke trail dissipate.
local function retire(v: Visual)
	if v.done then
		return
	end
	v.done = true
	local tail = v.part:FindFirstChild("Tail")
	if tail then
		tail:SetAttribute("Done", true) -- stops the delayed smoke start
	end
	for _, e in v.emitters do
		e.Enabled = false
	end
	v.part.Transparency = 1
	for _, d in v.part:GetDescendants() do
		if d:IsA("PointLight") or d:IsA("Trail") then
			d.Enabled = false
		end
	end
	task.delay(SMOKE_LINGER, function()
		v.part:Destroy()
	end)
end

local function newVisual(kind: string, origin: Vector3, visualOrigin: Vector3, dir: Vector3, speed: number, target: Model?): Visual?
	if #visuals >= MAX_VISUALS then
		return nil
	end
	local part, emitters = buildBody(kind)
	local v: Visual = {
		kind = kind,
		part = part,
		emitters = emitters,
		pos = origin,
		dir = dir,
		speed = speed,
		age = 0,
		offset = visualOrigin - origin,
		target = target,
		targetLast = nil,
		targetVel = Vector3.zero,
		exploded = nil,
		done = false,
		confirmed = false,
	}
	part.CFrame = CFrame.lookAt(visualOrigin, visualOrigin + dir)
	table.insert(visuals, v)
	return v
end

local function targetPosition(v: Visual, dt: number): Vector3?
	local model = v.target
	local root = model and model.PrimaryPart
	if not model or not model.Parent or not root or model:GetAttribute("State") == "Dead" then
		v.target = nil
		return nil
	end
	local tp = root.Position
	if v.targetLast and dt > 0 then
		v.targetVel = v.targetVel:Lerp((tp - v.targetLast) / dt, 0.35)
	end
	v.targetLast = tp
	return tp
end

local function advance(v: Visual, dt: number)
	v.age += dt
	local oldPos = v.pos
	if v.kind == "Missile" then
		local tp = targetPosition(v, dt)
		v.pos, v.dir, v.speed = WeaponConfig.missileStep(v.pos, v.dir, v.speed, v.age, dt, tp, v.targetVel)
		if tp and (v.pos - tp).Magnitude < MISSILE.PROXIMITY then
			-- Wait at the target for the server's verdict.
			v.pos = tp
		end
	else
		local delta = v.dir * v.speed * dt
		local result = Workspace:Raycast(oldPos, delta, rayParams)
		-- Landscape meshes are visual only (the terrain behind them takes the
		-- ray): blow up on the rock face the player sees.
		local rock = Surface.hit(oldPos, oldPos + delta)
		if rock and (not result or (rock.Position - oldPos).Magnitude < (result.Position - oldPos).Magnitude) then
			result = rock
			v.onRock = true
		end
		if result then
			v.pos = result.Position
			v.exploded = result.Position
			explodeAt(v, result.Position, false)
			retire(v)
			return
		end
		v.pos += delta
		if v.age * v.speed > ROCKET.MAX_RANGE then
			retire(v)
			return
		end
	end
	local blend = math.max(0, 1 - v.age / BLEND_TIME)
	local shown = v.pos + v.offset * blend
	v.part.CFrame = CFrame.lookAt(shown, shown + v.dir)
	if not v.confirmed and v.age > UNCONFIRMED_TIMEOUT then
		retire(v) -- the server rejected the shot
	end
end

local function step(dt: number)
	if #visuals == 0 then
		return
	end
	refreshFilter()
	for i = #visuals, 1, -1 do
		local v = visuals[i]
		if not v.done then
			advance(v, dt)
		end
		if v.done then
			table.remove(visuals, i)
		end
	end
end

-- Local prediction for the firing client; `token` pairs it with the
-- server's Projectile event. Returns immediately with the launch effects.
function WeaponFx.predict(kind: string, token: number, origin: Vector3, visualOrigin: Vector3, dir: Vector3, target: Model?)
	refreshFilter()
	local speed = if kind == "Rocket" then ROCKET.SPEED else MISSILE.LAUNCH_SPEED
	local v = newVisual(kind, origin, visualOrigin, dir, speed, target)
	if v then
		byToken[token] = v
	end
	Particles.backblast(visualOrigin, dir, kind == "Missile")
end

local function onProjectile(p: any)
	if typeof(p) ~= "table" or type(p.id) ~= "number" then
		return
	end
	if p.owner == player.UserId and p.token and byToken[p.token] then
		local v = byToken[p.token]
		byToken[p.token] = nil
		v.confirmed = true
		byId[p.id] = v
		return
	end
	-- Someone else's shot (or prediction dropped): render from server state.
	local elapsed = math.max(0, Workspace:GetServerTimeNow() - (p.t0 or 0))
	local v = newVisual(p.kind, p.origin, p.origin, p.dir, p.speed, enemyModel(p.targetId))
	if v then
		v.confirmed = true
		byId[p.id] = v
		if elapsed > 0 and elapsed < 1 then
			advance(v, elapsed)
		end
	end
end

local function onProjectileEnd(p: any)
	if typeof(p) ~= "table" or type(p.id) ~= "number" then
		return
	end
	local v = byId[p.id]
	byId[p.id] = nil
	if not p.exploded then
		if v then
			retire(v)
		end
		return
	end
	local already = v and v.exploded
	-- A rocket that burst on a landscape face locally: the server's hit is on
	-- the terrain behind that rock, so don't blow up again inside it.
	local behindRock = v ~= nil and v.onRock == true and already ~= nil and (already - p.position).Magnitude < 160
	if not behindRock and (not already or (already - p.position).Magnitude > 25) then
		local fake: Visual = v or ({ kind = p.kind } :: any)
		explodeAt(fake, p.position, p.air == true)
	end
	if v then
		v.exploded = p.position
		retire(v)
	end
end

local function onRicochet(p: any)
	if typeof(p) ~= "table" or typeof(p.position) ~= "Vector3" then
		return
	end
	local camPos = Workspace.CurrentCamera.CFrame.Position
	Particles.ricochet(p.position, (camPos - p.position).Unit)
	Sfx.play("Ricochet", 0.3, 0.7)
end

function WeaponFx.clear()
	for _, v in visuals do
		retire(v)
	end
	table.clear(visuals)
	table.clear(byId)
	table.clear(byToken)
end

function WeaponFx.start()
	RunService:BindToRenderStep("RedMesaWeaponFx", Enum.RenderPriority.Camera.Value + 3, step)
	GameState.onEvent("Projectile", onProjectile)
	GameState.onEvent("ProjectileEnd", onProjectileEnd)
	GameState.onEvent("Ricochet", onRicochet)
	GameState.onChanged("Phase", function(phase)
		if phase == "Title" or phase == "Defeat" or phase == "Victory" then
			WeaponFx.clear()
		end
	end)
end

return WeaponFx
