--!strict
-- First-person sight meshes (HS-2). While aiming, the current weapon's sight
-- model is drawn in front of the camera: the machine gun's ring sight and
-- rear leaf, the rocket sight box with its eyepiece window, the AA seeker
-- unit's hooded display bezel. Models come from
-- ReplicatedStorage.Assets.Gunsights (tools/assets/models/gunsights.py),
-- built in eye space: each sub-model's pivot is the eye, so it is pivoted
-- to the camera every frame. The GUI keeps the reticle marks and the lock
-- box; WeaponHud.setSightModel hides the GUI rings a model replaces.
--
-- Purely visual and client-only: parts are anchored, CanQuery/CanCollide/
-- CanTouch off and cast no shadow, so aiming, raycasts and lock-on are
-- untouched. Without the asset nothing is drawn and the GUI sights stay.

local ContentProvider = game:GetService("ContentProvider")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local AimController = require(script.Parent.AimController)
local LockOn = require(script.Parent.LockOn)
local WeaponController = require(script.Parent.WeaponController)
local WeaponHud = require(script.Parent.WeaponHud)

local GunsightModels = {}

local MODEL_FOR = { MG = "IronSight", Rocket = "RocketScope", Missile = "AASeeker" }
local RAISE_TIME = 0.16 -- seconds to bring the sight up to the eye
local DROP_ANGLE = math.rad(22) -- lowered pose: pitched below the view
local AA_DEPTH = 0.7 -- AASeeker bezel depth (gunsights.py AA_D)
local AA_EDGE_MARGIN = 0.03 -- side bars' inner edge, tan units inside the viewport edge
local AA_SIDE_INNER = 0.195 -- |x| of the side bars' inner edge as built (gunsights.py AA_SIDE_INNER)
-- AASeeker parts that slide with a viewport edge: the side bars, and the
-- lamp box (Controls) and Lamp riding the right one. Keeps the lamp box
-- beside the centred, fixed-pixel HUD panels at any aspect.
local AA_SIDE = { Left = -1, Right = 1, Controls = 1, Lamp = 1 }
local KICK_MG = math.rad(0.3) -- sight jump per MG round (capped at KICK_MG_MAX)
local KICK_MG_MAX = math.rad(1.1)
local KICK_HEAVY = math.rad(2.4) -- rocket / missile launch
local KICK_RETURN = 14 -- 1/s, settles in ~0.25 s

local LAMP = {
	Idle = { color = Color3.fromRGB(70, 130, 50), transparency = 0.55 },
	Acquiring = { color = Color3.fromRGB(255, 178, 36), transparency = 0.1 },
	Locked = { color = Color3.fromRGB(230, 52, 38), transparency = 0 },
}

type Piece = { part: BasePart, rel: CFrame, side: number }
type Sight = { model: Model, pieces: { Piece }, lamp: BasePart? }

local sights: { [string]: Sight } = {}
local shown: string? = nil -- weapon whose model is parented
local WARM_TIME = 2.5
local warmUntil = 0 -- os.clock() until which all models are drawn nearly invisible
local warming = false
local raise = 0
local kick = 0 -- pitch-up of the sight (rad)
local jitter = 0 -- MG roll jitter (rad)

local function prepare(model: Model): Sight
	local pivot = model:GetPivot()
	local pieces = {}
	local lamp: BasePart? = nil
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = true
			d.CanCollide = false
			d.CanQuery = false
			d.CanTouch = false
			d.CastShadow = false
			d.Locked = true
			local rel = pivot:ToObjectSpace(d.CFrame)
			local side = AA_SIDE[d.Name] or 0
			table.insert(pieces, { part = d, rel = rel, side = side })
			if d.Name == "Lamp" then
				lamp = d
			end
		end
	end
	return { model = model, pieces = pieces, lamp = lamp }
end

local function load(): boolean
	local assets = ReplicatedStorage:FindFirstChild("Assets")
	local source = assets and assets:FindFirstChild("Gunsights")
	if not source then
		return false
	end
	for weapon, name in MODEL_FOR do
		local original = source:FindFirstChild(name)
		if original and original:IsA("Model") then
			local model = original:Clone()
			model.Name = "Gunsight" .. name
			sights[weapon] = prepare(model)
		end
	end
	return next(sights) ~= nil
end

local function show(weapon: string?)
	if weapon == shown then
		return
	end
	if shown and sights[shown] then
		sights[shown].model.Parent = nil
	end
	shown = weapon
	if weapon and sights[weapon] then
		sights[weapon].model.Parent = Workspace.CurrentCamera
	end
	WeaponHud.setSightModel(weapon)
end

local function onFired(heavy: boolean)
	if heavy then
		kick += KICK_HEAVY
	else
		kick = math.min(kick + KICK_MG, KICK_MG_MAX)
		jitter = (math.random() - 0.5) * KICK_MG
	end
end

local function easeOut(t: number): number
	return 1 - (1 - t) ^ 3
end

local function updateLamp(sight: Sight)
	local lamp = sight.lamp
	if not lamp then
		return
	end
	local state = LockOn.getState()
	local spec = LAMP[state] or LAMP.Idle
	local transparency = spec.transparency
	if state == "Acquiring" and math.floor(os.clock() * 10) % 2 == 1 then
		transparency = 0.7
	end
	lamp.Color = spec.color
	lamp.Transparency = transparency
end

-- Places every piece of `sight` for the camera frame `base`. The AA side
-- pieces slide so the side bars' inner edges sit AA_EDGE_MARGIN inside the
-- viewport edges: the bezel frames any aspect ratio.
local function place(sight: Sight, base: CFrame, camera: Camera)
	local halfH = math.tan(math.rad(camera.FieldOfView) / 2)
	local viewport = camera.ViewportSize
	local halfW = halfH * viewport.X / math.max(1, viewport.Y)
	local slide = (halfW - AA_EDGE_MARGIN) * AA_DEPTH - AA_SIDE_INNER
	for _, piece in sight.pieces do
		local cf = base * piece.rel
		if piece.side ~= 0 then
			cf = base * CFrame.new(piece.side * slide, 0, 0) * piece.rel
		end
		piece.part.CFrame = cf
	end
end

local function setWarm(on: boolean)
	for _, sight in sights do
		for _, piece in sight.pieces do
			piece.part.LocalTransparencyModifier = if on then 0.995 else 0
		end
		if sight.model.Parent and sight.model ~= (shown and sights[shown] and sights[shown].model) then
			sight.model.Parent = nil
		end
		if on then
			sight.model.Parent = Workspace.CurrentCamera
		end
	end
end

local function step(dt: number)
	if Workspace:GetAttribute("HsFxOff") == true and RunService:IsStudio() then
		show(nil) -- Studio-only QA switch shared with EmplacementFx (perf A/B)
		return
	end
	local camera = Workspace.CurrentCamera
	local aiming = AimController.getMode() == "Turret" and AimController.isAiming()
	local weapon = WeaponController.getWeapon()
	local swap = WeaponController.getSwitchProgress()
	local want = if aiming and sights[weapon] then weapon else nil
	local warm = warmUntil > 0 and os.clock() < warmUntil and not want
	if warm ~= warming then
		warming = warm
		setWarm(warm)
	end
	if warm then
		for _, sight in sights do
			place(sight, camera.CFrame, camera)
		end
		return
	end
	if not want then
		raise = 0
		show(nil)
		return
	end
	if shown ~= want then
		raise = 0
		show(want)
	end
	raise = math.min(1, raise + dt / RAISE_TIME)
	-- Kick: the sight jumps a little per shot and settles back to the eye.
	local decay = math.exp(-KICK_RETURN * dt)
	kick *= decay
	jitter *= decay
	local lowered = (1 - easeOut(raise * swap)) * DROP_ANGLE
	local base = camera.CFrame * CFrame.Angles(kick - lowered, 0, jitter)
	local sight = sights[want]
	place(sight, base, camera)
	updateLamp(sight)
end

-- Fetch the sight meshes and maps now, then draw every model once, almost
-- fully transparent, for WARM_TIME so the renderer has their textures
-- before the first aim (otherwise the first sight shows untextured while
-- its maps stream in).
local function preload()
	local list: { Instance } = {}
	for _, sight in sights do
		table.insert(list, sight.model)
	end
	pcall(function()
		ContentProvider:PreloadAsync(list)
	end)
	warmUntil = os.clock() + WARM_TIME
end

function GunsightModels.start()
	if not load() then
		warn("[RedMesa] Gunsights asset missing; GUI gunsights only")
		return
	end
	task.spawn(preload)
	WeaponController.on("Shot", function()
		onFired(false)
	end)
	WeaponController.on("Fired", function()
		onFired(true)
	end)
	-- After every camera writer (AimController at Camera+1, weapon pose,
	-- post effects) so the sight sits exactly on the rendered view.
	RunService:BindToRenderStep("RedMesaGunsightModels", Enum.RenderPriority.Last.Value, step)
end

return GunsightModels
