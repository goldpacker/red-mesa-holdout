--!strict
-- Bone animation for one skinned infantry soldier (face-lift CHAR-2).
-- Driven by the server "State" attribute (Walk / Aim / Throw / Dead) and
-- the EnemyFire events (grenade throw, rifle recoil):
--   * clips from InfantryRigPose, played per body half with cross-fades;
--     the jog cycle advances with the distance the root actually moves,
--     so feet don't skate whatever the soldier's speed;
--   * small procedural layers: aim elevation toward the gun, aim sway and
--     breathing, rifle recoil, a head that scans while jogging;
--   * Body <-> BodyLOD swap and a distance-based update rate;
--   * the helmet lamp, following the posed head.
-- Bone.Transform is local to this client (no bandwidth). Only bones are
-- animated: the model root belongs to the server and to Look's EnemyMotion.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Pose = require(script.Parent.InfantryRigPose)

local InfantryRig = {}

type Clip = Pose.Clip

type Layer = {
	bones: { number },
	clip: Clip,
	t0: number,
	from: { CFrame }?,
	fadeT0: number,
	fade: number,
	pending: { clip: Clip, at: number, fade: number }?,
}

export type Rig = {
	model: Model,
	root: BasePart,
	skinRoot: BasePart,
	body: BasePart,
	lod: BasePart?,
	bones: { Bone },
	rest: { [string]: CFrame },
	scale: number,
	seed: number,
	state: string,
	lower: Layer,
	upper: Layer,
	base: { CFrame },
	out: { CFrame },
	phase: number,
	speed: number,
	walkW: number,
	aimW: number,
	lastPos: Vector3?,
	recoilAt: number,
	throwing: boolean,
	lastUpdate: number,
	nextUpdate: number,
	useLod: boolean,
	lamp: BasePart?,
	lampOn: boolean,
}

local CLIPS = Pose.clips
local WALK = CLIPS.Walk
local PATROL = CLIPS.Patrol
local HIPS = Pose.index.Hips
local SPINE = Pose.index.Spine
local CHEST = Pose.index.Chest
local NECK = Pose.index.NeckBone
local HEAD = Pose.index.HeadBone

-- Projected distance (studs at a 70 degree FOV) -> seconds between updates.
local RATE_TIERS = { { 140, 0 }, { 320, 1 / 30 }, { 650, 1 / 15 }, { math.huge, 1 / 8 } }
local LOD_IN, LOD_OUT = 200, 180 -- BodyLOD (1.6k tris) beyond ~27 px tall
local THROW_LEAD = 0.06 -- the grenade leaves at the event; skip part of the wind-up
local LAMP_COLOR = Color3.fromRGB(255, 120, 90)
local LAMP_CHAIN = { "Hips", "Spine", "Chest", "NeckBone", "HeadBone" }
local MUZZLE_CHAIN = { "Hips", "Spine", "Chest", "RightUpperArm", "RightLowerArm", "RightHand" }

local function smoothstep(x: number): number
	x = math.clamp(x, 0, 1)
	return x * x * (3 - 2 * x)
end

local function newLayer(bones: { number }, clip: Clip): Layer
	return { bones = bones, clip = clip, t0 = 0, from = nil, fadeT0 = 0, fade = 0.2, pending = nil }
end

-- Switch a layer to `clip`, cross-fading from the pose it shows now.
local function play(rig: Rig, layer: Layer, clip: Clip, now: number, fade: number, delay: number?)
	if delay and delay > 0 then
		layer.pending = { clip = clip, at = now + delay, fade = fade }
		return
	end
	layer.pending = nil
	if layer.clip == clip and clip.loop then
		return
	end
	local from = layer.from or {}
	for _, b in layer.bones do
		from[b] = rig.base[b]
	end
	layer.from = from
	layer.fadeT0 = now
	layer.fade = fade
	layer.clip = clip
	layer.t0 = now
end

local function enterState(rig: Rig, state: string, now: number)
	local previous = rig.state
	rig.state = state
	rig.throwing = false
	if state == "Dead" then
		local clip = if rig.model:GetAttribute("DeathFall") == -1 then CLIPS.DeathFront else CLIPS.DeathBack
		play(rig, rig.lower, clip, now, 0.1)
		play(rig, rig.upper, clip, now, 0.1)
	elseif state == "Aim" then
		play(rig, rig.lower, CLIPS.Aim, now, 0.25)
		play(rig, rig.upper, CLIPS.Aim, now, 0.2)
	elseif state == "Throw" then
		play(rig, rig.lower, CLIPS.ThrowReady, now, 0.3)
		play(rig, rig.upper, CLIPS.ThrowReady, now, 0.3)
	else
		play(rig, rig.lower, WALK, now, 0.25)
		-- After a shot the rifle stays up a beat while the legs move off.
		play(rig, rig.upper, WALK, now, 0.3, if previous == "Aim" then 0.18 else nil)
	end
end

function InfantryRig.attach(model: Model): Rig?
	local root = model.PrimaryPart or model:FindFirstChild("Root")
	local skinRoot = model:FindFirstChild("SkinRoot")
	local body = model:FindFirstChild("Body")
	if not (root and root:IsA("BasePart") and skinRoot and skinRoot:IsA("BasePart") and body and body:IsA("BasePart")) then
		return nil
	end
	local bones: { Bone } = {}
	local rest: { [string]: CFrame } = {}
	for _, d in skinRoot:GetDescendants() do
		if d:IsA("Bone") then
			rest[d.Name] = d.CFrame
		end
	end
	for i, name in Pose.BONES do
		local bone = skinRoot:FindFirstChild(name, true)
		if not (bone and bone:IsA("Bone")) then
			return nil
		end
		bones[i] = bone
	end
	local lod = model:FindFirstChild("BodyLOD")
	local base = {}
	for i in Pose.BONES do
		base[i] = PATROL.cf[i][1]
	end
	local seed = (model:GetAttribute("EnemyId") :: number?) or math.random(1, 1000)
	local rig: Rig = {
		model = model,
		root = root :: BasePart,
		skinRoot = skinRoot,
		body = body,
		lod = if lod and lod:IsA("BasePart") then lod else nil,
		bones = bones,
		rest = rest,
		scale = (model:GetAttribute("SkinScale") :: number?) or 1,
		seed = seed,
		state = "",
		lower = newLayer(Pose.LOWER, PATROL),
		upper = newLayer(Pose.UPPER, PATROL),
		base = base,
		out = table.clone(base),
		phase = (seed * 0.37) % 1,
		speed = 0,
		walkW = 0,
		aimW = 0,
		lastPos = nil,
		recoilAt = -math.huge,
		throwing = false,
		lastUpdate = os.clock(),
		nextUpdate = 0,
		useLod = false,
		lamp = nil,
		lampOn = false,
	}
	return rig
end

-- EnemyFire events for this soldier.
function InfantryRig.onFire(rig: Rig, attack: string, now: number)
	if rig.state == "Dead" then
		return
	end
	if attack == "Grenade" then
		rig.throwing = true
		play(rig, rig.lower, CLIPS.Throw, now, 0.08)
		play(rig, rig.upper, CLIPS.Throw, now, 0.08)
		rig.lower.t0 = now - THROW_LEAD
		rig.upper.t0 = now - THROW_LEAD
	elseif attack == "Rifle" then
		rig.recoilAt = now
	end
end

local function sampleLayer(rig: Rig, layer: Layer, now: number)
	local pending = layer.pending
	if pending and now >= pending.at then
		play(rig, layer, pending.clip, now, pending.fade)
	end
	local clip = layer.clip
	local i0, i1, a
	if clip == WALK then
		i0, i1, a = Pose.cursor(clip, 0, rig.phase)
	else
		i0, i1, a = Pose.cursor(clip, now - layer.t0)
	end
	local w = 1
	local from = layer.from
	if from then
		w = smoothstep((now - layer.fadeT0) / layer.fade)
	end
	local walkW = rig.walkW
	for _, b in layer.bones do
		local cf = Pose.sample(clip, b, i0, i1, a)
		if clip == WALK and walkW < 0.999 then
			cf = PATROL.cf[b][1]:Lerp(cf, walkW)
		end
		if from and w < 1 then
			cf = from[b]:Lerp(cf, w)
		end
		rig.base[b] = cf
	end
	if w >= 1 then
		layer.from = nil
	end
end

local function trackMotion(rig: Rig, dt: number)
	local pos = rig.root.Position
	local last = rig.lastPos
	rig.lastPos = pos
	if not last or dt <= 0 then
		return
	end
	local moved = Vector2.new(pos.X - last.X, pos.Z - last.Z).Magnitude
	if moved > 25 then -- teleported (spawn placement, beauty staging)
		return
	end
	local k = 1 - math.exp(-dt / 0.3)
	rig.speed += (moved / dt - rig.speed) * k
	rig.phase = (rig.phase + moved / (WALK.cycle * rig.scale)) % 1
	local target = if rig.state == "Walk" or rig.state == "" then math.clamp((rig.speed - 1) / 4, 0, 1) else 0
	rig.walkW += (target - rig.walkW) * (1 - math.exp(-dt / 0.2))
end

-- Procedural layers on top of the sampled pose, into rig.out.
local function layers(rig: Rig, now: number, dt: number, frozen: boolean)
	local out, base = rig.out, rig.base
	for i, cf in base do
		out[i] = cf
	end
	local alive = rig.state ~= "Dead"
	local aimTarget = if alive and rig.state == "Aim" then 1 else 0
	rig.aimW += (aimTarget - rig.aimW) * (1 - math.exp(-dt / 0.15))
	if not alive then
		return
	end
	local t = if frozen then 0 else now
	local seed = rig.seed
	-- Lean the shouldered rifle up (or down) toward the gun on the mesa.
	local aimW = rig.aimW
	if aimW > 0.01 then
		local pivot = Config.TURRET_PIVOT
		local chest = rig.root.Position + Vector3.new(0, 1.5 * rig.scale, 0)
		local flat = Vector2.new(pivot.X - chest.X, pivot.Z - chest.Z).Magnitude
		local elevation = math.clamp(math.atan2(pivot.Y - chest.Y, math.max(flat, 1)), -0.35, 0.6)
		local swayYaw = math.rad(1.1) * math.noise(t * 0.55, seed * 0.13, 0.5)
		local swayPitch = math.rad(0.8) * math.noise(seed * 0.29, t * 0.5, 1.5)
		local lean = CFrame.Angles((elevation * 0.45 + swayPitch) * aimW, swayYaw * aimW, 0)
		out[SPINE] = lean * out[SPINE]
		out[CHEST] = CFrame.Angles(elevation * 0.45 * aimW, 0, 0) * out[CHEST]
	end
	-- Breathing on the chest when standing still.
	local still = 1 - rig.walkW
	if still > 0.01 then
		local breath = math.rad(0.7) * math.sin(t * 1.7 + seed) * still
		out[CHEST] = CFrame.Angles(breath, 0, 0) * out[CHEST]
	end
	-- Rifle kick: the chest (and with it both arms and the carbine) snaps up.
	local since = now - rig.recoilAt
	if since < 0.3 then
		local k = (1 - since / 0.3) ^ 2
		out[CHEST] = CFrame.Angles(math.rad(7) * k, math.rad(-1.5) * k, 0) * out[CHEST]
		out[HEAD] = CFrame.Angles(math.rad(-3) * k, 0, 0) * out[HEAD]
	end
	-- Looking around while jogging.
	local scan = rig.walkW * (1 - aimW)
	if scan > 0.01 then
		local yaw = math.rad(16) * math.noise(t * 0.22, seed * 0.71, 2.5) * scan
		out[NECK] = CFrame.Angles(0, yaw * 0.4, 0) * out[NECK]
		out[HEAD] = CFrame.Angles(0, yaw * 0.6, 0) * out[HEAD]
	end
end

local function write(rig: Rig)
	local out, bones = rig.out, rig.bones
	local hips = out[HIPS]
	if rig.scale ~= 1 then
		out[HIPS] = hips.Rotation + hips.Position * rig.scale
	end
	for i, bone in bones do
		bone.Transform = out[i]
	end
end

local function chainCFrame(rig: Rig, chain: { string }, tip: { string }): CFrame
	local cf = rig.skinRoot.CFrame
	for _, name in chain do
		cf = cf * (rig.rest[name] or CFrame.identity) * rig.out[Pose.index[name]]
	end
	for _, name in tip do
		cf = cf * (rig.rest[name] or CFrame.identity)
	end
	return cf
end

-- World position of the carbine's muzzle as posed (for effects).
function InfantryRig.muzzle(rig: Rig): Vector3
	return chainCFrame(rig, MUZZLE_CHAIN, { "RifleBone", "MuzzleBone" }).Position
end

local function lampPart(rig: Rig): BasePart
	local lamp = rig.lamp
	if lamp then
		return lamp
	end
	local p = Instance.new("Part")
	p.Name = "LampGlow"
	p.Shape = Enum.PartType.Ball
	p.Size = Vector3.new(0.26, 0.26, 0.26) * rig.scale
	p.Material = Enum.Material.Neon
	p.Color = LAMP_COLOR
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Transparency = 1
	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(255, 110, 80)
	light.Range = 7
	light.Brightness = 1.2
	light.Enabled = false
	light.Parent = p
	p.Parent = rig.model
	rig.lamp = p
	return p
end

-- Helmet lamp for dusk/night readability (client-only part on the LampBone).
function InfantryRig.setLamp(rig: Rig, on: boolean)
	if rig.lampOn == on then
		return
	end
	rig.lampOn = on
	if not on and not rig.lamp then
		return
	end
	local lamp = lampPart(rig)
	lamp.CFrame = chainCFrame(rig, LAMP_CHAIN, { "LampBone" })
	lamp.Transparency = if on then 0 else 1
	local light = lamp:FindFirstChildWhichIsA("PointLight")
	if light then
		light.Enabled = on
	end
end

local function rateFor(distance: number): number
	for _, tier in RATE_TIERS do
		if distance < tier[1] then
			return tier[2]
		end
	end
	return 1 / 8
end

-- Per frame. `distance` is the camera distance scaled by the zoom, so a
-- soldier in the gunsight counts as close.
function InfantryRig.update(rig: Rig, now: number, distance: number, frozen: boolean)
	if now < rig.nextUpdate then
		return
	end
	local dt = math.min(now - rig.lastUpdate, 0.25)
	rig.lastUpdate = now
	rig.nextUpdate = now + rateFor(distance)

	local state = (rig.model:GetAttribute("State") :: string?) or "Walk"
	if state ~= rig.state then
		enterState(rig, state, now)
	end
	if rig.throwing and now - rig.upper.t0 >= CLIPS.Throw.duration then
		rig.throwing = false
		if rig.state == "Throw" then
			play(rig, rig.lower, CLIPS.ThrowReady, now, 0.2)
			play(rig, rig.upper, CLIPS.ThrowReady, now, 0.2)
		else
			enterState(rig, rig.state, now)
		end
	end
	trackMotion(rig, dt)
	sampleLayer(rig, rig.lower, now)
	sampleLayer(rig, rig.upper, now)
	layers(rig, now, dt, frozen)
	write(rig)

	local lod = rig.lod
	if lod then
		local useLod = if rig.useLod then distance > LOD_OUT else distance > LOD_IN
		if useLod ~= rig.useLod then
			rig.useLod = useLod
			rig.body.Transparency = if useLod then 1 else 0
			lod.Transparency = if useLod then 0 else 1
		end
	end
	if rig.lampOn and rig.lamp then
		rig.lamp.CFrame = chainCFrame(rig, LAMP_CHAIN, { "LampBone" })
	end
end

function InfantryRig.destroy(rig: Rig)
	if rig.lamp then
		rig.lamp:Destroy()
		rig.lamp = nil
	end
end

-- Workspace-level switch used by the beauty rig (frozen captures).
function InfantryRig.frozen(): boolean
	return Workspace:GetAttribute("BeautyShot") ~= nil
end

return InfantryRig
