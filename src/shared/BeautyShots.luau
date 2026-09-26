--!strict
-- Beauty-shot rig (FACELIFT_PLAN §5, tools/qa/BEAUTY.md): six fixed shots,
-- each captured at every time-of-day preset. Studio only.
--
-- The server stages a shot through `ServerStorage.RedMesaDebug:Invoke(
-- "beauty", { shot = 4, tod = "Sunset" })` (server/QaDebug): it snaps the
-- lighting preset, freezes the game (no wave director, so enemies never
-- move, fire or despawn), spawns the frozen subjects below and sets the
-- Workspace attributes `BeautyShot` / `BeautyToD`. The client half of the
-- rig (`startClient`, below) reacts to those attributes: it fixes the
-- camera, hides the HUD for free cameras, pins the searchlights and places
-- fixed flares so every capture of a shot is framed and lit the same way.

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local BeautyShots = {}

-- Time-of-day presets (server/TimeOfDay) in capture order, and the file tag
-- each gets in `qa/beauty/<set>/<tag>_<n>-<shot>.jpg`.
BeautyShots.PRESETS = { "Afternoon", "LateAfternoon", "Sunset", "Dusk", "Night" }
BeautyShots.TAGS = {
	Afternoon = "afternoon",
	LateAfternoon = "lateafternoon",
	Sunset = "sunset",
	Dusk = "dusk",
	Night = "night",
}

-- Wave number shown on the HUD for combat shots at each preset (the first
-- wave that uses that lighting with the staged enemy mix).
BeautyShots.WAVE_FOR = { Afternoon = 3, LateAfternoon = 4, Sunset = 7, Dusk = 8, Night = 9 }
BeautyShots.SCORE = 12480

export type Subject = {
	kind: string,
	at: Vector2, -- XZ position
	face: Vector2?, -- XZ point the subject faces (default: the mesa)
	altitude: number?, -- air: absolute Y
	state: string?, -- infantry pose ("Aim" by default)
}

-- Frozen subjects. "combat" is shared by shots 2–5; "boss" by shot 6.
BeautyShots.STAGES = {
	none = {},
	combat = {
		{ kind = "Infantry", at = Vector2.new(-9, -222) },
		{ kind = "Infantry", at = Vector2.new(5, -233) },
		{ kind = "Infantry", at = Vector2.new(-20, -250) },
		{ kind = "Infantry", at = Vector2.new(15, -249) },
		{ kind = "Infantry", at = Vector2.new(27, -268) },
		{ kind = "Buggy", at = Vector2.new(26, -306), face = Vector2.new(4, -200) },
		{ kind = "Tank", at = Vector2.new(20, -412), face = Vector2.new(40, -360) },
		{ kind = "Helicopter", at = Vector2.new(-70, -340), altitude = 105 },
	} :: { Subject },
	boss = {
		{ kind = "SiegeCrawler", at = Vector2.new(16, -425), face = Vector2.new(40, -360) },
		{ kind = "Infantry", at = Vector2.new(-38, -345) },
		{ kind = "Infantry", at = Vector2.new(52, -352) },
		{ kind = "Infantry", at = Vector2.new(-58, -366) },
	} :: { Subject },
}

export type Shot = {
	id: number,
	name: string,
	-- "title": title screen, fixed camera; "turret"/"gunsight": the player's
	-- turret camera driven by DebugYaw/DebugPitch(/DebugAiming); "free":
	-- fixed camera with the HUD hidden.
	mode: string,
	phase: string, -- GameState phase the server publishes
	stage: string, -- key of STAGES
	camera: CFrame?, -- title/free
	fov: number?,
	yaw: number?, -- turret/gunsight, degrees (see shared/Aim)
	pitch: number?,
	hud: boolean,
	wave: number?, -- fixed HUD wave (otherwise WAVE_FOR[preset])
}

BeautyShots.SHOTS = {
	{
		-- The title screen as the player first sees it: AimController's title
		-- pan frozen at t = 0.
		id = 1,
		name = "title",
		mode = "title",
		phase = "Title",
		stage = "none",
		camera = CFrame.lookAt(Vector3.new(-62, 122, 122), Vector3.new(90, 0, -420)), -- AimController title pan at t = 0 (LOOK-2: clears ENV-2's rear wall)
		fov = 60,
		hud = true,
	},
	{
		id = 2,
		name = "turret",
		mode = "turret",
		phase = "Wave",
		stage = "combat",
		yaw = -2,
		pitch = -7.5,
		hud = true,
	},
	{
		id = 3,
		name = "gunsight",
		mode = "gunsight",
		phase = "Wave",
		stage = "combat",
		yaw = -3.5,
		pitch = -13.5,
		hud = true,
	},
	{
		-- From the right flank of the basin: mesa and emplacement, the far
		-- canyon wall and buttes, the basin and the road column.
		id = 4,
		name = "flank",
		mode = "free",
		phase = "Wave",
		stage = "combat",
		camera = CFrame.lookAt(Vector3.new(430, 70, -700), Vector3.new(-20, 25, -190)),
		fov = 45,
		hud = false,
	},
	{
		-- From the basin looking back up at the mesa: searchlights,
		-- emplacement lights and flares over the column.
		id = 5,
		name = "night",
		mode = "free",
		phase = "Wave",
		stage = "combat",
		camera = CFrame.lookAt(Vector3.new(95, 30, -560), Vector3.new(-50, 70, -40)),
		fov = 45,
		hud = false,
	},
	{
		id = 6,
		name = "boss",
		mode = "turret",
		phase = "Wave",
		stage = "boss",
		yaw = -1,
		pitch = -6,
		hud = true,
		wave = 10,
	},
} :: { Shot }

-- Searchlight aim (degrees, same yaw/pitch convention as client/NightFx)
-- by model name, and the fixed flares shown at dusk and night.
BeautyShots.SEARCHLIGHTS = {
	Searchlight1 = { yaw = 20, pitch = -8 },
	Searchlight2 = { yaw = -28, pitch = -9 },
}
BeautyShots.FLARES = {
	Vector3.new(-60, 150, -300),
	Vector3.new(60, 155, -290),
	Vector3.new(5, 140, -240),
}

function BeautyShots.get(key: any): Shot?
	for _, shot in BeautyShots.SHOTS do
		if shot.id == key or shot.name == key then
			return shot
		end
	end
	return nil
end

-- Accepts a preset name ("LateAfternoon") or its file tag ("lateafternoon").
function BeautyShots.preset(key: any): string?
	for _, name in BeautyShots.PRESETS do
		if name == key or BeautyShots.TAGS[name] == key then
			return name
		end
	end
	return nil
end

-- File name (without extension) for a shot at a preset.
function BeautyShots.fileName(shot: Shot, preset: string): string
	return string.format("%s_%d-%s", BeautyShots.TAGS[preset], shot.id, shot.name)
end

-- ---------------------------------------------------------------- client

local CAMERA_STEP = "RedMesaBeautyCamera"
local PIN_STEP = "RedMesaBeautyPin"
local DEBUG_ATTRIBUTES = { "DebugYaw", "DebugPitch", "DebugAiming" }

local hiddenGuis: { ScreenGui } = {}
local stagedFlares: { BasePart } = {}
local bound = false

local function isNightPreset(preset: any): boolean
	return preset == "Dusk" or preset == "Night"
end

local function makeFlare(position: Vector3): Part
	-- Mirrors client/NightFx launchFlare, frozen in place.
	local flare = Instance.new("Part")
	flare.Name = "BeautyFlare"
	flare.Shape = Enum.PartType.Ball
	flare.Size = Vector3.new(1.6, 1.6, 1.6)
	flare.Material = Enum.Material.Neon
	flare.Color = Color3.fromRGB(255, 236, 190)
	flare.Anchored = true
	flare.CanCollide = false
	flare.CanQuery = false
	flare.CastShadow = false
	flare.CFrame = CFrame.new(position)
	local light = Instance.new("PointLight")
	light.Range = 60
	light.Brightness = 3
	light.Color = Color3.fromRGB(255, 228, 180)
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
	flare.Parent = Workspace
	return flare
end

local searchlightParams = RaycastParams.new()
searchlightParams.FilterType = Enum.RaycastFilterType.Include

-- Runs after client/NightFx's sweep each frame: pins the searchlights to
-- fixed angles and removes NightFx's randomly timed flares.
local function pinNightFeatures()
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local folder = battlefield and battlefield:FindFirstChild("Searchlights")
	if folder then
		searchlightParams.FilterDescendantsInstances = { Workspace.Terrain }
		for _, model in folder:GetChildren() do
			local aim = BeautyShots.SEARCHLIGHTS[model.Name]
			local head = model:FindFirstChild("Head") :: BasePart?
			if aim and head and model:IsA("Model") then
				local cf = CFrame.new(head.Position) * CFrame.Angles(0, math.rad(aim.yaw), 0) * CFrame.Angles(math.rad(aim.pitch), 0, 0)
				model:PivotTo(cf)
				local lens = model:FindFirstChild("Lens") :: BasePart?
				local pool = model:FindFirstChild("Pool") :: BasePart?
				if lens and pool then
					local hit = Workspace:Raycast(lens.Position, cf.LookVector * 900, searchlightParams)
					if hit then
						pool.CFrame = CFrame.new(hit.Position + Vector3.new(0, 45, 0))
					end
				end
			end
		end
	end
	local projectiles = Workspace:FindFirstChild("Projectiles")
	if projectiles then
		for _, child in projectiles:GetChildren() do
			if child.Name == "Flare" then
				child:Destroy()
			end
		end
	end
end

local function clearClient()
	if bound then
		RunService:UnbindFromRenderStep(CAMERA_STEP)
		RunService:UnbindFromRenderStep(PIN_STEP)
		bound = false
	end
	for _, gui in hiddenGuis do
		gui.Enabled = true
	end
	table.clear(hiddenGuis)
	for _, flare in stagedFlares do
		flare:Destroy()
	end
	table.clear(stagedFlares)
	local player = Players.LocalPlayer
	for _, name in DEBUG_ATTRIBUTES do
		player:SetAttribute(name, nil)
	end
end

local function hideHud()
	local playerGui = Players.LocalPlayer:FindFirstChildOfClass("PlayerGui")
	if not playerGui then
		return
	end
	for _, gui in playerGui:GetChildren() do
		if gui:IsA("ScreenGui") and gui.Enabled then
			gui.Enabled = false
			table.insert(hiddenGuis, gui)
		end
	end
end

-- The boss bar stays up once shown (the boss is the last wave), so hide it
-- again for every shot that isn't the boss shot.
local function hideBossBar()
	local playerGui = Players.LocalPlayer:FindFirstChildOfClass("PlayerGui")
	local bar = playerGui and playerGui:FindFirstChild("BossBar", true)
	if bar and bar:IsA("GuiObject") then
		bar.Visible = false
	end
end

local function applyClient()
	clearClient()
	local shot = BeautyShots.get(Workspace:GetAttribute("BeautyShot"))
	if not shot then
		return
	end
	local preset = Workspace:GetAttribute("BeautyToD")
	local player = Players.LocalPlayer
	local camera = Workspace.CurrentCamera
	if shot.mode == "turret" or shot.mode == "gunsight" then
		player:SetAttribute("DebugYaw", shot.yaw)
		player:SetAttribute("DebugPitch", shot.pitch)
		player:SetAttribute("DebugAiming", shot.mode == "gunsight")
	end
	local fixedCamera = shot.camera
	local fov = shot.fov or 70
	RunService:BindToRenderStep(CAMERA_STEP, Enum.RenderPriority.Last.Value + 10, function()
		if fixedCamera then
			camera.CFrame = fixedCamera
			camera.FieldOfView = fov
		end
	end)
	RunService:BindToRenderStep(PIN_STEP, Enum.RenderPriority.Last.Value + 11, pinNightFeatures)
	bound = true
	if not shot.hud then
		hideHud()
	end
	if shot.stage ~= "boss" then
		hideBossBar()
	end
	if shot.phase == "Wave" and isNightPreset(preset) then
		for _, position in BeautyShots.FLARES do
			table.insert(stagedFlares, makeFlare(position))
		end
	end
end

-- Called once from the client entry point; does nothing outside Studio.
function BeautyShots.startClient()
	if not RunService:IsStudio() then
		return
	end
	Workspace:GetAttributeChangedSignal("BeautyShot"):Connect(applyClient)
	Workspace:GetAttributeChangedSignal("BeautyToD"):Connect(applyClient)
	applyClient()
end

return BeautyShots
