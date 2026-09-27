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
-- GPU: a full-screen translucent layer costs ~0.5 ms in the busy scene
-- (measured, LOOK-5 report), so the vignette is four corner pieces and the
-- glare has no full-screen veil; the grain is the one full-screen layer.
--
-- One switch turns the whole treatment off: `FilmFx.ENABLED = false` here,
-- or at runtime the Workspace attribute `FilmFxOff = true`.

local Lighting = game:GetService("Lighting")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Assets = require(script.Parent.PostFxAssets)

local FilmFx = {}

FilmFx.ENABLED = true

local IS_STUDIO = RunService:IsStudio()
local GRAIN_TILE = 128 -- px, drawn 1:1
local GRAIN_FPS = 24
local GRAIN_JITTER = 40 -- px of random offset per grain frame
local DISPLAY_ORDER = -20 -- under every HUD/screen gui
local GLARE = {
	cone = math.rad(45), -- no glare beyond this angle from the view centre
	fadeIn = 0.25, -- s, glare rising when the sun clears the rim
	fadeOut = 0.12, -- s, glare dropping when terrain covers the sun
	glowSize = 0.45, -- × viewport height at full strength
	glowAlpha = 0.35,
	streakAlpha = 0.2,
	rayLength = 4000,
}

-- Film vignette: one corner texture, rotated into each screen corner.
local VIGNETTE_SIZE = 0.62 -- × viewport height per corner piece
local VIGNETTE_CORNERS = {
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
local grain: ImageLabel? = nil
local corners: { ImageLabel } = {}
local glow: ImageLabel? = nil
local streak: ImageLabel? = nil
local ghosts: { ImageLabel } = {}
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

local function build()
	local playerGui = Players.LocalPlayer:WaitForChild("PlayerGui")
	local screen = Instance.new("ScreenGui")
	screen.Name = "FilmFx"
	screen.IgnoreGuiInset = true
	screen.ResetOnSpawn = false
	screen.DisplayOrder = DISPLAY_ORDER
	screen.ZIndexBehavior = Enum.ZIndexBehavior.Sibling

	local g = image(screen, "Grain")
	g.Image = Assets.film_grain
	g.ScaleType = Enum.ScaleType.Tile
	g.TileSize = UDim2.fromOffset(GRAIN_TILE, GRAIN_TILE)
	-- Only GRAIN_JITTER px larger than the screen (every covered pixel costs
	-- GPU); the per-frame jitter stays inside that margin.
	g.Size = UDim2.new(1, GRAIN_JITTER, 1, GRAIN_JITTER)
	g.ZIndex = 5
	grain = g

	-- Vignette as four corner pieces, not a full-screen image: the centre of
	-- a vignette is empty anyway, and a full-screen translucent layer costs
	-- ~0.5 ms of GPU in the busy scene (LOOK-5 report).
	for i, corner in VIGNETTE_CORNERS do
		local v = image(screen, "Vignette" .. i)
		v.Image = Assets.vignette_corner
		v.AnchorPoint = corner.at
		v.Position = UDim2.fromScale(corner.at.X, corner.at.Y)
		v.SizeConstraint = Enum.SizeConstraint.RelativeYY
		v.Size = UDim2.fromScale(VIGNETTE_SIZE, VIGNETTE_SIZE)
		v.Rotation = corner.rotation
		v.ZIndex = 4
		table.insert(corners, v)
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
end

local function enabled(): boolean
	return FilmFx.ENABLED and Workspace:GetAttribute("FilmFxOff") ~= true
end

local function updateGrain(amount: number, frozen: boolean)
	local g = grain :: ImageLabel
	g.ImageTransparency = 1 - amount
	local now = os.clock()
	if frozen or now < nextGrain then
		return
	end
	nextGrain = now + 1 / GRAIN_FPS
	g.Position = UDim2.fromOffset(-math.random(0, GRAIN_JITTER), -math.random(0, GRAIN_JITTER))
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
	local viewport = camera.ViewportSize
	local sunPoint = camera:WorldToViewportPoint(camera.CFrame.Position + Lighting:GetSunDirection() * 1000)
	local sun2 = Vector2.new(sunPoint.X, sunPoint.Y)
	local centre = viewport * 0.5
	local h = viewport.Y
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
	local on = enabled()
	-- Part of the picture, not the HUD: the switch alone decides (the beauty
	-- rig hides every ScreenGui for free cameras; this layer comes back).
	if screen.Enabled ~= on then
		screen.Enabled = on
	end
	if not on then
		return
	end
	local camera = Workspace.CurrentCamera
	local frozen = IS_STUDIO and Workspace:GetAttribute("BeautyShot") ~= nil
	updateGrain(look.grain * (1 + 0.4 * storm), frozen)
	local vig = 1 - look.vignette * (1 + 0.3 * storm)
	for _, v in corners do
		v.ImageTransparency = vig
	end
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
