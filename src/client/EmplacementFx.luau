--!strict
-- Emplacement motion (HS-2), client-only and purely visual:
--   * the ammo belt feeding into the machine gun while it fires: pooled
--     round meshes walk the feed path from the can into the receiver, one
--     link pitch per shot (the static `Belt` part is hidden once they run);
--   * ejected brass: pooled casing meshes thrown out of the right side of
--     the receiver, bouncing once on the floor (capped, oldest recycled);
--   * barrel heat glow from the same MG heat the HUD shows;
--   * wind: the radio whip sways, the camo net ripples (EmplacementFxWind).
-- Muzzle flashes, tracers and the rocket backblast are VFX's (Effects /
-- WeaponFx*); nothing here duplicates them. Nothing here touches gameplay,
-- the server or any raycast: every part is anchored, CanQuery/CanCollide/
-- CanTouch off. Started from WeaponFxTurret.start(); listens to
-- WeaponController's "Shot" event.
--
-- Asset contract (docs/ASSET_CONTRACTS.md, Emplacement): MachineGun holds
-- `Belt`, the hidden templates `BeltRound` and `EjectCase` (built at the
-- asset origin in the belt/casing frames below) and the barrel runs along
-- -Z at y = BARREL_Y in MachineGun space.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")
local FrameProfile = require(script.Parent.FrameProfile)

local Config = require(ReplicatedStorage.Shared.Config)
local AimController = require(script.Parent.AimController)
local WeaponController = require(script.Parent.WeaponController)
local Wind = require(script.Parent.EmplacementFxWind)

local EmplacementFx = {}

-- Belt feed path in MachineGun space (Roblox axes; models/emplacement.py
-- belt_along rotated by rb()). The first point is inside the ammo can and
-- the last inside the receiver, so rounds appear and vanish out of sight.
local BELT_PATH = {
	Vector3.new(-1.02, 0.08, -0.75),
	Vector3.new(-1.0, 0.4, -0.75),
	Vector3.new(-0.95, 0.64, -0.75),
	Vector3.new(-0.8, 0.76, -0.75),
	Vector3.new(-0.6, 0.76, -0.75),
	Vector3.new(-0.42, 0.62, -0.75),
	Vector3.new(-0.18, 0.5, -0.75),
}
local BELT_REST_START = 2 -- the static belt starts at BELT_PATH[2]
local BELT_ROUNDS = 7 -- rounds on the static belt between points 2 and 6
local BELT_UP = Vector3.new(0, -1, 0) -- belt_along's up=(0, 0, -1) in Roblox axes
local FEED_TIME = 0.045 -- seconds the feed pawl takes to pull one link

-- Ejection port (right side of the receiver) and casing flight.
local PORT = Vector3.new(0.44, 0.28, -0.35)
local EJECT_VEL = Vector3.new(5.5, 4.2, 0.6) -- MachineGun space: right, up, slightly back
local EJECT_JITTER = Vector3.new(1.4, 1.2, 1.0)
local CASE_GRAVITY = 42 -- studs/s^2 (slower than the world's 196 so the arc reads)
local CASE_RADIUS = 0.055
local FLOOR_Y = -6 -- bunker top below the turret pivot
local MAX_CASINGS = 28
local CASE_REST_TIME = 1.6 -- seconds a casing lies on the floor before it is recycled

-- Barrel heat glow: an additive Beam laid along the exposed barrel (jacket
-- to muzzle brake), hottest next to the jacket and fading toward the
-- muzzle, plus a small red light at night. Dull cherry red when warm,
-- orange-red at overheat; muted in daylight presets, where a hot barrel
-- barely shows.
local BARREL_Y = 0.2
local BARREL_FROM, BARREL_TO = -3.66, -6.74 -- exposed barrel, MachineGun-space z
local BARREL_WIDTH = 0.27 -- barrel diameter 0.26 plus a hair of halo
local BARREL_FALLOFF = 0.55 -- glow at the muzzle end relative to the jacket end
local GLOW_FROM = 0.45 -- heat fraction where the barrel starts to glow
local GLOW_TAU_UP = 0.35
local GLOW_TAU_DOWN = 1.1
local GLOW_MAX_OPACITY = 0.85
local GLOW_COLD = Color3.fromRGB(110, 8, 2)
local GLOW_HOT = Color3.fromRGB(255, 70, 20)
local GLOW_BRIGHTNESS = 3 -- Beam.Brightness at full glow (1 = plain additive)
local GLOW_LIFT = 0.16 -- Beam.ZOffset: render the ribbon on the camera side of the barrel
-- Workspace TimeOfDay -> glow scale: a hot barrel barely shows in sunlight.
local GLOW_DAY = { Afternoon = 0.35, LateAfternoon = 0.4, Sunset = 0.65 }

type Casing = {
	part: BasePart,
	pos: Vector3,
	vel: Vector3,
	rot: CFrame,
	spin: Vector3,
	bounced: boolean,
	restUntil: number,
	active: boolean,
}

local emplacement: Instance? = nil -- last Battlefield.Emplacement seen
local mg: Model? = nil
local staticBelt: BasePart? = nil
local roundTemplate: BasePart? = nil
local caseTemplate: BasePart? = nil
local roundRel = CFrame.identity
local caseRel = CFrame.identity
local rounds: { BasePart } = {}
local glowBeam: Beam? = nil
local glowLight: PointLight? = nil
local glowShown = -1 -- last applied glow level (skip unchanged frames)
local folder: Folder? = nil
local casings: { Casing } = {}
local nextCasing = 1

local pathLengths: { number } = {}
local pathTotal = 0
local pitch = 0.12
local restOffset = 0 -- arc length where the static belt starts
local feed = 0 -- arc length fed so far (mod pitch)
local feedTarget = 0
local feedDirty = false
local glow = 0
local lastAiming = false
-- Studio-only QA: Workspace attribute HsFxProfile = true publishes the mean
-- cost of this module's frame step (ms, wind included) as HsFxMs once a
-- second; HsFxOff = true pauses the module (qaOff, below).
local profileTime, profileFrames, profileSince = 0, 0, os.clock()

-- ------------------------------------------------------------------ belt
local function buildPath()
	table.clear(pathLengths)
	pathTotal = 0
	for i = 1, #BELT_PATH - 1 do
		local len = (BELT_PATH[i + 1] - BELT_PATH[i]).Magnitude
		pathLengths[i] = len
		pathTotal += len
	end
	restOffset = pathLengths[1]
	local beltLen = 0
	for i = BELT_REST_START, BELT_REST_START + 3 do
		beltLen += pathLengths[i]
	end
	pitch = beltLen / BELT_ROUNDS
end

-- Point and unit tangent at arc length `s` (clamped to the path).
local function pathAt(s: number): (Vector3, Vector3)
	s = math.clamp(s, 0, pathTotal)
	for i, len in pathLengths do
		if s <= len or i == #pathLengths then
			local a, b = BELT_PATH[i], BELT_PATH[i + 1]
			return a:Lerp(b, math.clamp(s / len, 0, 1)), (b - a).Unit
		end
		s -= len
	end
	return BELT_PATH[1], Vector3.yAxis
end

-- Round frame at arc length `s`: tangent smoothed over +-0.06 studs so the
-- rounds turn gently round the bends. Canonical round frame (asset
-- emplacement.py belt_round): X = belt tangent, -Z = round axis (across),
-- Y = tangent x across.
local function roundFrame(s: number): CFrame
	local pos = pathAt(s)
	local p0 = pathAt(s - 0.06)
	local p1 = pathAt(s + 0.06)
	local tangent = (p1 - p0).Unit
	local across = tangent:Cross(BELT_UP).Unit
	local normal = tangent:Cross(across)
	return CFrame.fromMatrix(pos, tangent, normal, -across)
end

local function placeRounds()
	local model = mg
	if not model or #rounds == 0 then
		return
	end
	local pivot = model:GetPivot()
	local phase = feed % pitch
	for k, part in rounds do
		-- Round k sits (k - 2.5) pitches from the static belt's start: two
		-- are waiting inside the can, the rest ride the visible belt.
		local s = restOffset + (k - 2.5) * pitch + phase
		part.CFrame = pivot * roundFrame(s) * roundRel
		part.Transparency = if s > pathTotal then 1 else 0
	end
end

local function makeRounds(model: Model, template: BasePart)
	for _, part in rounds do
		part:Destroy()
	end
	table.clear(rounds)
	local count = math.floor((pathTotal - restOffset) / pitch + 2.5) + 1
	for _ = 1, count do
		local part = template:Clone()
		part.Name = "FeedRound"
		part.Transparency = 0
		part.CanQuery = false
		part.CastShadow = false
		part.Parent = model
		table.insert(rounds, part)
	end
end

local function onShot()
	if #rounds > 0 then
		feedTarget += pitch
		feedDirty = true
	end
end

local function stepBelt(dt: number)
	if not feedDirty then
		return
	end
	feed = math.min(feedTarget, feed + pitch / FEED_TIME * dt)
	if feed >= feedTarget then
		feedDirty = false
		-- Keep the numbers small; whole pitches look identical.
		local whole = math.floor(feed / pitch) * pitch
		feed -= whole
		feedTarget -= whole
	end
	placeRounds()
end

-- --------------------------------------------------------------- casings
local function makeCasings(template: BasePart)
	local f = folder
	if not f then
		return
	end
	for _, c in casings do
		c.part:Destroy()
	end
	table.clear(casings)
	for _ = 1, MAX_CASINGS do
		local part = template:Clone()
		part.Name = "Casing"
		part.Transparency = 1
		part.CanQuery = false
		part.CastShadow = false
		part.Parent = f
		table.insert(casings, {
			part = part,
			pos = Vector3.zero,
			vel = Vector3.zero,
			rot = CFrame.identity,
			spin = Vector3.zero,
			bounced = false,
			restUntil = 0,
			active = false,
		})
	end
end

local function jitter(v: Vector3): Vector3
	return Vector3.new((math.random() - 0.5) * 2 * v.X, (math.random() - 0.5) * 2 * v.Y, (math.random() - 0.5) * 2 * v.Z)
end

local function ejectCasing()
	local model = mg
	if not model or #casings == 0 then
		return
	end
	local c = casings[nextCasing]
	nextCasing = nextCasing % #casings + 1
	local pivot = model:GetPivot()
	c.pos = pivot:PointToWorldSpace(PORT)
	c.vel = pivot:VectorToWorldSpace(EJECT_VEL + jitter(EJECT_JITTER))
	-- Lying across the gun (axis along the receiver's right), spinning end over end.
	c.rot = pivot.Rotation * CFrame.Angles(0, 0, math.rad(90))
	c.spin = pivot:VectorToWorldSpace(Vector3.new((math.random() - 0.5) * 8, (math.random() - 0.5) * 6, 18 + math.random() * 14))
	c.bounced = false
	c.restUntil = 0
	c.active = true
	c.part.Transparency = 0
end

local casingParts: { BasePart } = {} -- BulkMoveTo buffers, reused every frame
local casingFrames: { CFrame } = {}

local function stepCasings(dt: number, floorY: number, hidden: boolean)
	local parts, frames = casingParts, casingFrames
	table.clear(parts)
	table.clear(frames)
	local now = os.clock()
	-- Beauty shots (tools/qa/BEAUTY.md) are captured with no loose brass.
	local clear = Workspace:GetAttribute("BeautyShot") ~= nil
	for _, c in casings do
		if not c.active then
			continue
		end
		if clear then
			c.active = false
			c.part.Transparency = 1
			continue
		end
		if c.restUntil > 0 then
			if now >= c.restUntil then
				c.active = false
				c.part.Transparency = 1
			end
			continue
		end
		c.vel -= Vector3.new(0, CASE_GRAVITY * dt, 0)
		c.pos += c.vel * dt
		local w = c.spin.Magnitude
		if w > 1e-3 then
			c.rot = CFrame.fromAxisAngle(c.spin / w, w * dt) * c.rot
		end
		if c.pos.Y <= floorY + CASE_RADIUS then
			c.pos = Vector3.new(c.pos.X, floorY + CASE_RADIUS, c.pos.Z)
			if not c.bounced and c.vel.Y < -2 then
				c.bounced = true
				c.vel = Vector3.new(c.vel.X * 0.35, -c.vel.Y * 0.28, c.vel.Z * 0.35)
				c.spin *= 0.4
			else
				-- Settle on its side: keep the heading, lay the axis flat.
				local axis = c.rot.YVector
				local flat = Vector3.new(axis.X, 0, axis.Z)
				flat = if flat.Magnitude > 1e-3 then flat.Unit else Vector3.xAxis
				c.rot = CFrame.fromMatrix(Vector3.zero, flat:Cross(Vector3.yAxis), flat)
				c.restUntil = now + CASE_REST_TIME
			end
		end
		table.insert(parts, c.part)
		table.insert(frames, CFrame.new(c.pos) * c.rot * caseRel.Rotation)
	end
	if #parts > 0 then
		Workspace:BulkMoveTo(parts, frames, Enum.BulkMoveMode.FireCFrameChanged)
	end
	if hidden ~= lastAiming then
		for _, c in casings do
			c.part.LocalTransparencyModifier = if hidden then 1 else 0
		end
	end
end

-- ------------------------------------------------------------------ heat
local function makeGlow(model: Model)
	if glowBeam then
		glowBeam:Destroy()
		glowBeam = nil
	end
	local gun = model:FindFirstChild("Gun")
	if not gun or not gun:IsA("BasePart") then
		return
	end
	local pivot = model:GetPivot()
	local function attach(name: string, z: number): Attachment
		local a = Instance.new("Attachment")
		a.Name = name
		a.Position = gun.CFrame:PointToObjectSpace(pivot:PointToWorldSpace(Vector3.new(0, BARREL_Y, z)))
		a.Parent = gun
		return a
	end
	local a0, a1 = attach("HeatFrom", BARREL_FROM), attach("HeatTo", BARREL_TO)
	local beam = Instance.new("Beam")
	beam.Name = "BarrelHeat"
	beam.Attachment0, beam.Attachment1 = a0, a1
	beam.FaceCamera = true
	beam.Segments = 1
	beam.Width0, beam.Width1 = BARREL_WIDTH, BARREL_WIDTH
	beam.LightEmission = 1
	beam.LightInfluence = 0
	beam.ZOffset = GLOW_LIFT
	beam.Transparency = NumberSequence.new(1)
	beam.Enabled = false
	beam.Parent = gun
	glowBeam = beam
	glowShown = -1
	local light = Instance.new("PointLight")
	light.Name = "BarrelHeatLight"
	light.Color = GLOW_HOT
	light.Range = 5
	light.Brightness = 0
	light.Shadows = false
	light.Enabled = false
	light.Parent = a0
	glowLight = light
end

local function stepHeat(dt: number, hidden: boolean)
	local beam = glowBeam
	if not beam then
		return
	end
	local heat = WeaponController.getHeat()
	local tau = if heat > glow then GLOW_TAU_UP else GLOW_TAU_DOWN
	glow += (heat - glow) * (1 - math.exp(-dt / tau))
	local v = math.clamp((glow - GLOW_FROM) / (1 - GLOW_FROM), 0, 1)
	v = v * v * (3 - 2 * v)
	local day = GLOW_DAY[Workspace:GetAttribute("TimeOfDay") :: any] or 1
	local level = if hidden then 0 else math.floor(v * day * 200 + 0.5) / 200
	if level == glowShown then
		return
	end
	glowShown = level
	beam.Enabled = level > 0
	local light = glowLight
	if light then
		light.Enabled = level > 0.02
		light.Brightness = 1.4 * level
	end
	if level <= 0 then
		return
	end
	local hotEnd, coolEnd = v, v * (1 - BARREL_FALLOFF)
	beam.Brightness = 1 + (GLOW_BRIGHTNESS - 1) * level
	beam.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 1 - GLOW_MAX_OPACITY * hotEnd * day),
		NumberSequenceKeypoint.new(0.5, 1 - GLOW_MAX_OPACITY * (hotEnd + coolEnd) / 2 * day),
		NumberSequenceKeypoint.new(1, 1 - GLOW_MAX_OPACITY * coolEnd * day),
	})
	beam.Color = ColorSequence.new(GLOW_COLD:Lerp(GLOW_HOT, hotEnd), GLOW_COLD:Lerp(GLOW_HOT, coolEnd))
end

-- -------------------------------------------------------------- discovery
local function findTemplates(model: Model)
	staticBelt = model:FindFirstChild("Belt") :: BasePart?
	roundTemplate = model:FindFirstChild("BeltRound") :: BasePart?
	caseTemplate = model:FindFirstChild("EjectCase") :: BasePart?
	local pivot = model:GetPivot()
	if roundTemplate then
		roundRel = pivot:ToObjectSpace(roundTemplate.CFrame)
	end
	if caseTemplate then
		caseRel = pivot:ToObjectSpace(caseTemplate.CFrame)
	end
end

local function discover()
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local found = battlefield and battlefield:FindFirstChild("Emplacement")
	if found == emplacement and (mg == nil or mg.Parent ~= nil) then
		return
	end
	emplacement = found
	mg = nil
	if not found then
		return
	end
	Wind.attach(found)
	local gun = found:FindFirstChild("MachineGun", true)
	if not gun or not gun:IsA("Model") then
		return -- primitive fallback emplacement: nothing to animate
	end
	mg = gun
	findTemplates(gun)
	if roundTemplate then
		makeRounds(gun, roundTemplate)
		feed, feedTarget, feedDirty = 0, 0, false
		placeRounds()
		if staticBelt then
			staticBelt.Transparency = 1
		end
	end
	if caseTemplate then
		makeCasings(caseTemplate)
	end
	makeGlow(gun)
end

local function publishProfile(cost: number)
	profileTime += cost
	profileFrames += 1
	if os.clock() - profileSince >= 1 then
		Workspace:SetAttribute("HsFxMs", profileTime / profileFrames * 1000)
		profileTime, profileFrames, profileSince = 0, 0, os.clock()
	end
end

-- Studio-only QA switch (perf A/B): Workspace attribute HsFxOff = true
-- pauses this module and hides the loose brass.
local function qaOff(): boolean
	if Workspace:GetAttribute("HsFxOff") ~= true or not RunService:IsStudio() then
		return false
	end
	for _, c in casings do
		if c.active then
			c.active = false
			c.part.Transparency = 1
		end
	end
	return true
end

local function step(dt: number)
	if qaOff() then
		return
	end
	local t0 = os.clock()
	discover()
	dt = math.min(dt, 0.1)
	local hidden = AimController.getMode() == "Turret" and AimController.isAiming()
	if emplacement then
		Wind.step(dt, hidden)
	end
	if mg and mg.Parent then
		stepBelt(dt)
		stepCasings(dt, Config.TURRET_PIVOT.Y + FLOOR_Y, hidden)
		stepHeat(dt, hidden)
	end
	lastAiming = hidden
	if Workspace:GetAttribute("HsFxProfile") == true and RunService:IsStudio() then
		publishProfile(os.clock() - t0)
	end
end

function EmplacementFx.start()
	local f = Instance.new("Folder")
	f.Name = "EmplacementFxLocal"
	f.Parent = Workspace
	folder = f
	buildPath()
	WeaponController.on("Shot", function()
		onShot()
		ejectCasing()
	end)
	-- After AimController (Camera+1) and the weapon pose (Camera+2) have
	-- placed the gun this frame.
	RunService:BindToRenderStep("RedMesaEmplacementFx", Enum.RenderPriority.Camera.Value + 3, FrameProfile.wrap("EmplacementFx", step))
end

return EmplacementFx
