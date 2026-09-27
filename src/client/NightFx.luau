--!strict
-- Client-side night ambience: sweeps the mesa searchlights across the basin
-- and pops illumination flares over the battlefield at dusk and night so
-- enemies stay readable (GAME_SPEC §7.1). The searchlight beams get a dusty
-- volumetric look here (textured cone + soft outer glow, LOOK-1); the tower
-- meshes and the server-side beam/light instances belong to WorldBuilder.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Aim = require(ReplicatedStorage.Shared.Aim)
local Config = require(ReplicatedStorage.Shared.Config)
local AimController = require(script.Parent.AimController)
local GameState = require(script.Parent.GameState)
local PostFxAssets = require(script.Parent.PostFxAssets)

local NightFx = {}

-- The beauty-shot rig (Studio-only QaDebug) is the only thing that sets the
-- BeautyShot attribute, so live clients skip the per-frame read (QA-B).
local IS_STUDIO = RunService:IsStudio()

-- Warm practical lights against the cool moonlight key (ART_BIBLE §4).
local LAMP_WARM = Color3.fromRGB(255, 210, 150)
-- Two layers of the same dusty-cone texture: a hot narrow core and a wide
-- soft body (tuned in Studio at dusk/night, LOOK-1).
local CONE_CORE = {
	width0 = 2,
	width1 = 34,
	speed = 0.05,
	transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.5),
		NumberSequenceKeypoint.new(0.4, 0.75),
		NumberSequenceKeypoint.new(0.85, 0.9),
		NumberSequenceKeypoint.new(1, 1),
	}),
}
local CONE_BODY = {
	width0 = 6,
	width1 = 96,
	speed = 0.02,
	transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.45),
		NumberSequenceKeypoint.new(0.5, 0.62),
		NumberSequenceKeypoint.new(0.85, 0.8),
		NumberSequenceKeypoint.new(1, 1),
	}),
}

-- Warm work lamp in the gun pit at dusk and night: fills the back of the
-- gun and the sandbag ring the turret camera always sees, so they read as
-- olive and burlap against the cool moonlight instead of a silhouette.
-- Sits behind and above the gun, following the turret yaw.
local PIT_LAMP = {
	back = 10,
	up = 6.5,
	range = 22,
	angle = 80,
	brightness = 1.6,
	color = Color3.fromRGB(255, 200, 146),
}

local FLARE_INTERVAL = { 7, 12 }
local FLARE_FALL = 5
local FLARE_LIFETIME = 16

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include

type Light = { model: Model, head: BasePart, lens: BasePart, pool: BasePart?, base: CFrame, phase: number, beam: Beam?, glow: Beam? }
local lights: { Light } = {}
local nextFlare = 0

local function isNight(): boolean
	local t = Workspace:GetAttribute("TimeOfDay")
	return t == "Night" or t == "Dusk"
end

-- Dusty cone: the server's flat beam becomes the hot core of a textured
-- cone, and a wider client-only "Glow" beam forms its soft body (it mirrors
-- the core's Enabled state every frame).
local function styleLayer(beam: Beam, layer: typeof(CONE_CORE))
	beam.Texture = PostFxAssets.searchlight_cone
	beam.TextureMode = Enum.TextureMode.Stretch
	beam.TextureLength = 1
	-- Dust drift pauses while a beauty shot is staged (deterministic frames).
	beam.TextureSpeed = if Workspace:GetAttribute("BeautyShot") ~= nil then 0 else layer.speed
	beam.Width0 = layer.width0
	beam.Width1 = layer.width1
	beam.FaceCamera = true
	beam.LightEmission = 1
	beam.LightInfluence = 0
	beam.Color = ColorSequence.new(LAMP_WARM)
	beam.Transparency = layer.transparency
end

local function styleBeam(lens: BasePart): (Beam?, Beam?)
	local beam: Beam? = nil
	for _, child in lens:GetChildren() do
		if child:IsA("Beam") and child.Name ~= "Glow" then
			beam = child
			break
		end
	end
	if not beam then
		return nil, nil
	end
	styleLayer(beam, CONE_CORE)
	local glow = lens:FindFirstChild("Glow") :: Beam?
	if not glow then
		local created = Instance.new("Beam")
		created.Name = "Glow"
		created.Attachment0 = beam.Attachment0
		created.Attachment1 = beam.Attachment1
		created.Segments = 1
		created.Parent = lens
		glow = created
	end
	local body = glow :: Beam
	styleLayer(body, CONE_BODY)
	body.Enabled = beam.Enabled
	return beam, body
end

local function collect()
	table.clear(lights)
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local folder = battlefield and battlefield:FindFirstChild("Searchlights")
	if not folder then
		return
	end
	for i, model in folder:GetChildren() do
		local head = model:FindFirstChild("Head") :: BasePart?
		local lens = model:FindFirstChild("Lens") :: BasePart?
		if model:IsA("Model") and head and lens then
			local beam, glow = styleBeam(lens)
			table.insert(lights, {
				model = model,
				head = head,
				lens = lens,
				pool = model:FindFirstChild("Pool") :: BasePart?,
				base = head.CFrame,
				phase = i * 2.1,
				beam = beam,
				glow = glow,
			})
		end
	end
	groundParams.FilterDescendantsInstances = { Workspace.Terrain }
end

local function sweep(t: number)
	for _, light in lights do
		local pos = light.base.Position
		-- Slow figure-eight sweep across the front arc.
		local yaw = math.sin(t * 0.23 + light.phase) * math.rad(55)
		local pitch = math.rad(-9) + math.sin(t * 0.37 + light.phase * 1.7) * math.rad(4)
		local cf = CFrame.new(pos) * CFrame.Angles(0, yaw, 0) * CFrame.Angles(pitch, 0, 0)
		light.model:PivotTo(cf)
		if light.pool then
			local hit = Workspace:Raycast(light.lens.Position, cf.LookVector * 900, groundParams)
			if hit then
				light.pool.CFrame = CFrame.new(hit.Position + Vector3.new(0, 45, 0))
			end
		end
	end
end

local function launchFlare(color: Color3?)
	local target = Vector3.new(math.random(-420, 420), 150 + math.random(0, 40), math.random(-650, -220))
	local flare = Instance.new("Part")
	flare.Name = "Flare"
	flare.Shape = Enum.PartType.Ball
	flare.Size = Vector3.new(1.6, 1.6, 1.6)
	flare.Material = Enum.Material.Neon
	flare.Color = color or Color3.fromRGB(255, 236, 190)
	flare.Anchored = true
	flare.CanCollide = false
	flare.CanQuery = false
	flare.CastShadow = false
	flare.CFrame = CFrame.new(target)
	local light = Instance.new("PointLight")
	light.Range = 60
	light.Brightness = 3
	light.Color = color or Color3.fromRGB(255, 228, 180)
	light.Parent = flare
	local trail = Instance.new("ParticleEmitter")
	trail.Rate = 18
	trail.Lifetime = NumberRange.new(2, 3)
	trail.Speed = NumberRange.new(0.5, 1)
	trail.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.5), NumberSequenceKeypoint.new(1, 6) })
	trail.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.6), NumberSequenceKeypoint.new(1, 1) })
	trail.Color = ColorSequence.new(Color3.fromRGB(180, 170, 160))
	trail.LightInfluence = 1
	trail.Acceleration = Vector3.new(0, 2, 0)
	trail.Parent = flare
	flare.Parent = Workspace:FindFirstChild("Projectiles") or Workspace

	local born = os.clock()
	local connection: RBXScriptConnection
	connection = RunService.RenderStepped:Connect(function(dt)
		local age = os.clock() - born
		if age > FLARE_LIFETIME or not flare.Parent then
			connection:Disconnect()
			flare:Destroy()
			return
		end
		local drift = Vector3.new(math.sin(age * 0.8) * 0.6, -FLARE_FALL, 0) * dt
		flare.CFrame = flare.CFrame + drift
		-- Flicker, then burn out over the last few seconds.
		local fade = math.clamp((FLARE_LIFETIME - age) / 3, 0, 1)
		light.Brightness = (2.6 + math.noise(age * 8) * 0.8) * fade
	end)
end

local pitLamp: SpotLight? = nil
local pitLampPart: Part? = nil

local function updatePitLamp(active: boolean)
	if not pitLamp or not pitLampPart or not pitLampPart.Parent then
		local part = Instance.new("Part")
		part.Name = "PitLamp"
		part.Size = Vector3.new(0.2, 0.2, 0.2)
		part.Transparency = 1
		part.Anchored = true
		part.CanCollide = false
		part.CanQuery = false
		part.CanTouch = false
		part.CastShadow = false
		local light = Instance.new("SpotLight")
		light.Face = Enum.NormalId.Front
		light.Range = PIT_LAMP.range
		light.Angle = PIT_LAMP.angle
		light.Brightness = PIT_LAMP.brightness
		light.Color = PIT_LAMP.color
		light.Shadows = true
		light.Parent = part
		part.Parent = Workspace
		pitLampPart = part
		pitLamp = light
	end
	local lamp = pitLamp :: SpotLight
	lamp.Enabled = active
	if active then
		local yaw = AimController.getAngles()
		local forward = Aim.direction(yaw, 0)
		local pos = Config.TURRET_PIVOT - forward * PIT_LAMP.back + Vector3.new(0, PIT_LAMP.up, 0);
		(pitLampPart :: Part).CFrame = CFrame.lookAt(pos, Config.TURRET_PIVOT - Vector3.new(0, 1.5, 0))
	end
end

-- Victory celebration: a volley of coloured flares over the basin.
function NightFx.celebrate()
	local colors = { Color3.fromRGB(120, 255, 120), Color3.fromRGB(255, 190, 60), Color3.fromRGB(255, 90, 70), Color3.fromRGB(255, 245, 220) }
	for i = 1, 12 do
		task.delay(i * 0.35, launchFlare, colors[(i - 1) % #colors + 1])
	end
end

function NightFx.start()
	collect()
	Workspace.ChildAdded:Connect(function(child)
		if child.Name == "Battlefield" then
			task.wait(1)
			collect()
		end
	end)
	RunService.RenderStepped:Connect(function()
		if (#lights == 0 or not lights[1].model.Parent) and Workspace:FindFirstChild("Battlefield") then
			collect()
		end
		local beauty = IS_STUDIO and Workspace:GetAttribute("BeautyShot") ~= nil
		for _, light in lights do
			if light.beam and light.glow then
				light.glow.Enabled = light.beam.Enabled
				light.beam.TextureSpeed = if beauty then 0 else CONE_CORE.speed
				light.glow.TextureSpeed = if beauty then 0 else CONE_BODY.speed
			end
		end
		updatePitLamp(isNight())
		-- Studio beauty-shot rig (shared/BeautyShots) pins the lights and flares.
		if beauty then
			return
		end
		local night = isNight()
		if night then
			sweep(os.clock())
		end
		local now = os.clock()
		if night and GameState.phase() == "Wave" and now >= nextFlare then
			nextFlare = now + math.random(FLARE_INTERVAL[1] * 10, FLARE_INTERVAL[2] * 10) / 10
			launchFlare()
		end
	end)
end

return NightFx
