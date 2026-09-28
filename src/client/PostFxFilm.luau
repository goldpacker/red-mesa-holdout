--!strict
-- Restrained film treatment (LOOK-5, GAME_SPEC §13): subtle animated grain,
-- a gentle vignette, and a sun glare / lens response when the view turns
-- toward the sun. Roblox has no lens flares, so the glare is a GUI layer: a
-- soft glow on the sun, a short streak and a few aperture ghosts along the
-- sun-to-centre line. Strengths are per preset (client/PostFxPresets); the
-- glare fades out when terrain hides the sun and in a dust storm.
--
-- Readability first: everything draws under the HUD, the grain is a few
-- percent, the vignette only darkens the corners, and the glare only
-- appears within ~45° of the sun.
--
-- GPU (LOOK-6): every pixel is drawn once. LOOK-5 laid a full-screen grain
-- over four vignette corners (~1.6 screens of translucent fill, +0.4..0.6 ms
-- at the 60 fps protocol in the boss wave). Now the corners carry the
-- vignette and the grain baked into one image (film_corner.png) and the tiled
-- grain fills only the cross between them. The whole layer (one Frame) moves
-- a few pixels per grain frame: that renews the grain everywhere and shifts
-- the vignette by under a percent. The layer is skipped while the title key
-- art covers the screen, and the glare has no full-screen veil.
--
-- One switch turns the whole treatment off: `FilmFx.ENABLED = false` here,
-- or at runtime the Workspace attribute `FilmFxOff = true`.

local Lighting = game:GetService("Lighting")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Assets = require(script.Parent.PostFxAssets)
local Governor = require(script.Parent.PerfGovernor)

local FilmFx = {}

FilmFx.ENABLED = true

local IS_STUDIO = RunService:IsStudio()
local GRAIN_FPS = 24
-- px the whole layer moves per grain frame; the grain decorrelates after
-- ~2 px, and the vignette's steepest slope changes < 1 % opacity over this.
local JITTER = 12
local DISPLAY_ORDER = -20 -- under every HUD/screen gui

-- Film layer textures (tools/ui/look_textures.py): the grain tile and the
-- corner with vignette + grain baked in. The grain in the cross is scaled to
-- the corners' texel size so both read as one grain.
local GRAIN_TEXELS = 128 -- film_grain.png
local CORNER_TEXELS = 256 -- film_corner.png
local CORNER_SIZE = 0.34 -- × layer height per corner piece (FILM_CORNER_SIZE)
local CORNER_FULL = 0.75 -- vignette the corner image shows at ImageTransparency 0 (FILM_CORNER_FULL)
local GLARE = {
	cone = math.rad(45), -- no glare beyond this angle from the view centre
	fadeIn = 0.25, -- s, glare rising when the sun clears the rim
	fadeOut = 0.12, -- s, glare dropping when terrain covers the sun
	glowSize = 0.45, -- × viewport height at full strength
	glowAlpha = 0.35,
	streakAlpha = 0.2,
	rayLength = 4000,
}

-- One corner image, rotated into each corner of the layer (darkest texel
-- top-left at rotation 0; Rotation is clockwise).
local CORNERS = {
	{ at = Vector2.new(0, 0), rotation = 0 },
	{ at = Vector2.new(1, 0), rotation = 90 },
	{ at = Vector2.new(1, 1), rotation = 180 },
	{ at = Vector2.new(0, 1), rotation = 270 },
}

-- Lens atlas cells (assets/ui/look/lens_flare.png, tools/ui/look_textures.py).
local CELLS = {
	glow = { Vector2.new(0, 0), Vector2.new(128, 128) },
	ring = { Vector2.new(128, 0), Vector2.new(64, 64) },
	hex = { Vector2.new(192, 0), Vector2.new(64, 64) },
	disc = { Vector2.new(128, 64), Vector2.new(64, 64) },
	streak = { Vector2.new(192, 64), Vector2.new(64, 64) },
}

-- Ghosts along the line from the sun through the screen centre: t = 0 at the
-- sun, 1 at the centre. size × viewport height, alpha at full glare.
local GHOSTS = {
	{ cell = "disc", t = 0.55, size = 0.05, alpha = 0.1, color = Color3.fromRGB(255, 214, 160) },
	{ cell = "hex", t = 1.25, size = 0.09, alpha = 0.07, color = Color3.fromRGB(170, 230, 210) },
	{ cell = "ring", t = 1.55, size = 0.16, alpha = 0.06, color = Color3.fromRGB(255, 200, 150) },
	{ cell = "hex", t = 1.9, size = 0.05, alpha = 0.09, color = Color3.fromRGB(200, 180, 255) },
}

local gui: ScreenGui? = nil
local layer: Frame? = nil -- corners + grain bands, jittered as one
local corners: { ImageLabel } = {}
local bands: { ImageLabel } = {} -- tiled grain: middle column, left and right
local glow: ImageLabel? = nil
local streak: ImageLabel? = nil
local ghosts: { ImageLabel } = {}
local keyArt: ImageLabel? = nil
local nextGrain = 0
local glareLevel = 0

local sunParams = RaycastParams.new()
sunParams.FilterType = Enum.RaycastFilterType.Include

local function image(parent: Instance, name: string, cell: string?): ImageLabel
	local label = Instance.new("ImageLabel")
	label.Name = name
	label.BackgroundTransparency = 1
	label.BorderSizePixel = 0
	label.ImageTransparency = 1
	label.Active = false
	if cell then
		local rect = CELLS[cell]
		label.Image = Assets.lens_flare
		label.ImageRectOffset = rect[1]
		label.ImageRectSize = rect[2]
		label.AnchorPoint = Vector2.new(0.5, 0.5)
	end
	label.Parent = parent
	return label
end

-- Sizes the layer to the screen plus the jitter margin: four corner pieces
-- and the three grain bands that fill the cross between them, no overlap.
local function layout()
	local screen = gui :: ScreenGui
	local frame = layer :: Frame
	local w = math.ceil(screen.AbsoluteSize.X) + JITTER
	local h = math.ceil(screen.AbsoluteSize.Y) + JITTER
	local c = math.min(math.floor(CORNER_SIZE * h + 0.5), math.floor(w / 2))
	frame.Size = UDim2.fromOffset(w, h)
	for i, spec in CORNERS do
		local piece = corners[i]
		piece.Size = UDim2.fromOffset(c, c)
		piece.Position = UDim2.fromOffset(spec.at.X * (w - c), spec.at.Y * (h - c))
	end
	local tile = math.max(1, math.floor(GRAIN_TEXELS * c / CORNER_TEXELS + 0.5))
	local rects = {
		{ c, 0, w - 2 * c, h }, -- middle column, full height
		{ 0, c, c, h - 2 * c }, -- left, between the left corners
		{ w - c, c, c, h - 2 * c }, -- right
	}
	for i, r in rects do
		local band = bands[i]
		band.Position = UDim2.fromOffset(r[1], r[2])
		band.Size = UDim2.fromOffset(r[3], r[4])
		band.TileSize = UDim2.fromOffset(tile, tile)
		band.Visible = r[3] > 0 and r[4] > 0
	end
end

-- The title key art (client/UiKitArt backdrop, "KeyArt") is opaque and
-- covers the screen once faded in; the film under it would be unseen fill.
local function watchKeyArt(playerGui: Instance)
	local function consider(inst: Instance)
		if inst.Name == "KeyArt" and inst:IsA("ImageLabel") then
			keyArt = inst
		end
	end
	for _, inst in playerGui:GetDescendants() do
		consider(inst)
	end
	playerGui.DescendantAdded:Connect(consider)
end

local function keyArtCovers(): boolean
	local art = keyArt
	if not art then
		return false
	end
	local parent = art.Parent
	if not parent then
		keyArt = nil
		return false
	end
	return art.Visible
		and art.IsLoaded
		and art.ImageTransparency < 0.01
		and parent:IsA("GuiObject")
		and (parent :: GuiObject).Visible
end

local function build()
	local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")
	local screen = Instance.new("ScreenGui")
	screen.Name = "FilmFx"
	-- The whole screen, notch and home-indicator strips included (MOBILE-1).
	screen.ScreenInsets = Enum.ScreenInsets.None
	screen.ClipToDeviceSafeArea = false
	screen.ResetOnSpawn = false
	screen.DisplayOrder = DISPLAY_ORDER
	screen.ZIndexBehavior = Enum.ZIndexBehavior.Sibling

	local frame = Instance.new("Frame")
	frame.Name = "Film"
	frame.BackgroundTransparency = 1
	frame.BorderSizePixel = 0
	frame.Position = UDim2.fromOffset(-JITTER // 2, -JITTER // 2)
	frame.ZIndex = 4 -- over the glare
	frame.Parent = screen
	layer = frame
	for i, spec in CORNERS do
		local piece = image(frame, "Corner" .. i)
		piece.Image = Assets.film_corner
		piece.Rotation = spec.rotation
		table.insert(corners, piece)
	end
	for _, name in { "GrainMiddle", "GrainLeft", "GrainRight" } do
		local band = image(frame, name)
		band.Image = Assets.film_grain
		band.ScaleType = Enum.ScaleType.Tile
		table.insert(bands, band)
	end

	glow = image(screen, "GlareGlow", "glow")
	;(glow :: ImageLabel).ZIndex = 2
	streak = image(screen, "GlareStreak", "streak")
	;(streak :: ImageLabel).ZIndex = 2
	for i, spec in GHOSTS do
		local ghost = image(screen, "Ghost" .. i, spec.cell)
		ghost.ImageColor3 = spec.color
		ghost.ZIndex = 3
		table.insert(ghosts, ghost)
	end
	screen.Parent = playerGui
	gui = screen
	layout()
	screen:GetPropertyChangedSignal("AbsoluteSize"):Connect(layout)
	watchKeyArt(playerGui)
end

local function enabled(): boolean
	-- The quality governor drops the layer from tier 1 (PERF-1).
	return FilmFx.ENABLED and Workspace:GetAttribute("FilmFxOff") ~= true and Governor.tier() < 1
end

-- Grain and vignette opacities; the layer jumps to a new offset at GRAIN_FPS
-- (held at the middle of the margin for beauty shots).
local function updateLayer(grain: number, vignette: number, frozen: boolean)
	local bandT = 1 - grain
	for _, band in bands do
		band.ImageTransparency = bandT
	end
	local cornerT = 1 - math.clamp(vignette / CORNER_FULL, 0, 1)
	for _, piece in corners do
		piece.ImageTransparency = cornerT
	end
	local frame = layer :: Frame
	if frozen then
		frame.Position = UDim2.fromOffset(-JITTER // 2, -JITTER // 2)
		return
	end
	local now = os.clock()
	if now < nextGrain then
		return
	end
	nextGrain = now + 1 / GRAIN_FPS
	frame.Position = UDim2.fromOffset(-math.random(0, JITTER), -math.random(0, JITTER))
end

-- 0..1: how strongly the sun should flare this frame (angle, horizon, rim).
local function glareTarget(camera: Camera, strength: number): number
	if strength <= 0 then
		return 0
	end
	local sun = Lighting:GetSunDirection()
	if sun.Y < 0.01 then
		return 0
	end
	local angle = math.acos(math.clamp(camera.CFrame.LookVector:Dot(sun), -1, 1))
	if angle >= GLARE.cone then
		return 0
	end
	sunParams.FilterDescendantsInstances = { Workspace.Terrain }
	if Workspace:Raycast(camera.CFrame.Position, sun * GLARE.rayLength, sunParams) then
		return 0
	end
	local t = 1 - angle / GLARE.cone
	return strength * t
end

local function placeGlare(camera: Camera, level: number, color: Color3)
	local visible = level > 0.002
	-- In this gui's space: on a notched phone the viewport is only the safe
	-- area, while the picture (and this gui) is the whole screen.
	local screen = gui :: ScreenGui
	local sunPoint = camera:WorldToScreenPoint(camera.CFrame.Position + Lighting:GetSunDirection() * 1000)
	local sun2 = Vector2.new(sunPoint.X, sunPoint.Y) - screen.AbsolutePosition
	local centre = screen.AbsoluteSize * 0.5
	local h = screen.AbsoluteSize.Y
	local g = glow :: ImageLabel
	local s = streak :: ImageLabel
	g.Visible, s.Visible = visible, visible
	for _, ghost in ghosts do
		ghost.Visible = visible
	end
	if not visible then
		return
	end
	local size = h * GLARE.glowSize * (0.6 + 0.4 * level)
	g.Position = UDim2.fromOffset(sun2.X, sun2.Y)
	g.Size = UDim2.fromOffset(size, size)
	g.ImageColor3 = color
	g.ImageTransparency = 1 - GLARE.glowAlpha * level
	s.Position = g.Position
	s.Size = UDim2.fromOffset(h * 1.1, h * 0.12)
	s.ImageColor3 = color
	s.ImageTransparency = 1 - GLARE.streakAlpha * level
	for i, spec in GHOSTS do
		local ghost = ghosts[i]
		local p = sun2 + (centre - sun2) * spec.t
		ghost.Position = UDim2.fromOffset(p.X, p.Y)
		ghost.Size = UDim2.fromOffset(h * spec.size, h * spec.size)
		ghost.ImageTransparency = 1 - spec.alpha * level
	end
end

-- Called every frame by PostFx with the blended preset look and storm amount.
function FilmFx.update(dt: number, look: any, storm: number)
	if not gui then
		return
	end
	local screen = gui :: ScreenGui
	local on = enabled() and not keyArtCovers()
	-- Part of the picture, not the HUD: the switch (and the title art) alone
	-- decides (the beauty rig hides every ScreenGui for free cameras; this
	-- layer comes back).
	if screen.Enabled ~= on then
		screen.Enabled = on
	end
	if not on then
		return
	end
	local camera = Workspace.CurrentCamera
	local frozen = IS_STUDIO and Workspace:GetAttribute("BeautyShot") ~= nil
	updateLayer(look.grain * (1 + 0.4 * storm), look.vignette * (1 + 0.3 * storm), frozen)
	local target = glareTarget(camera, look.glare * (1 - storm))
	if frozen then
		glareLevel = target
	else
		local tau = if target > glareLevel then GLARE.fadeIn else GLARE.fadeOut
		glareLevel += (target - glareLevel) * (1 - math.exp(-dt / tau))
	end
	placeGlare(camera, glareLevel, look.glareColor)
end

function FilmFx.start()
	task.spawn(build) -- waits for PlayerGui without holding up the client's start
end

return FilmFx
