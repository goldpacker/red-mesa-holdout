--!strict
-- Air with depth (LOOK-5): the low dust layer of the basin and sun shafts
-- through the dust at low sun. The server's Atmosphere gives the distance
-- fall-off over everything (TimeOfDay); these client layers add what it
-- can't: dust that is thick near the floor and gone higher up, so the wall
-- feet, buttes and far basin sit in dust while the rims, the sky, aircraft
-- and transports stay clean.
--
-- Dust bands: camera-facing Beams lying on the floor along the foot of the
-- far wall, the buttes and each canyon wall. The texture's soft
-- across-profile is zero at both edges and the band's lower edge sits on
-- the ground, so it meets the ground with no visible line; the wall feet
-- and butte bases sit in dust while their tops stay sharp, which separates
-- the basin from the walls and the buttes from the wall behind them. The
-- dust toward the sun glows (backlit). Bands near the camera fade out (free
-- cameras never look through a veil). Texture: the old searchlight cone's
-- dust streaks, reused (no new map).
--
-- Sun shafts: at late afternoon and sunset the sun stands low in the west
-- (-X, 11-17° up), just over the left canyon wall. Light pouring over notches
-- in that rim becomes a few broad, soft, additive Beams (same texture) that
-- start at the rim and slant down along the sun direction into the basin,
-- fading in off the rim and out before they reach the floor. Their start
-- points follow the terrain rim height; the slant follows the live sun.
--
-- Both follow the preset transition and Lighting.StormAmount
-- (client/PostFxPresets): a storm thickens and browns the dust layer and
-- hides the shafts. Studio A/B: Workspace attribute `AirFxOff = true` hides
-- both.

local Lighting = game:GetService("Lighting")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Assets = require(script.Parent.PostFxAssets)

local Air = {}

local IS_STUDIO = RunService:IsStudio()

type BandSpec = {
	axis: "x" | "z", -- "x": a row across the basin at depth `at` (z); "z": along a wall at x = `at`
	at: number,
	from: number,
	to: number,
	height: number, -- studs from the ground to the band's top edge
	weight: number, -- × the preset's peak opacity
	wall: boolean?, -- uses the wall-foot colour/opacity
}

-- The basin floor spans x ±780 between the canyon walls, z 0 (mesa) to the
-- far wall at ~-1340 (server/TerrainBuilder).
-- GPU (QA-B: the busy wave-9 scene sits at the 6 ms limit, and measured in
-- Studio a full-screen translucent layer costs ~0.5 ms): the dust is kept
-- where it reads, at the feet of the walls and buttes, not as rows over the
-- bright basin floor (where it barely showed), and each band is a few long
-- beams. Four bands, ~15 beams, covering a strip of screen near the horizon.
local BANDS: { BandSpec } = {
	{ axis = "x", at = -1000, from = -820, to = 820, height = 90, weight = 0.8 },
	{ axis = "x", at = -1290, from = -860, to = 860, height = 110, weight = 1, wall = true },
	{ axis = "z", at = -700, from = -1280, to = -120, height = 96, weight = 1, wall = true },
	{ axis = "z", at = 700, from = -1280, to = -120, height = 96, weight = 1, wall = true },
}
local SEGMENT = 420 -- studs per beam along a band (the floor is near flat)
local TEXTURE_LENGTH = 300 -- studs per texture tile along a band
local NEAR_FADE = { 120, 320 } -- camera distance: invisible .. full

type ShaftSpec = {
	z: number, -- where along the left (west) rim the light pours over
	width: number, -- at the rim; the far end is 2.4x wider
	weight: number,
}
local SHAFT_RIM_X = -790 -- the left canyon wall's face (server/TerrainBuilder)
local SHAFT_MAX_LENGTH = 1500
-- Three shafts (five cost ~0.3 ms more in the busy sunset wave for little
-- extra read, LOOK-5 A/B).
local SHAFTS: { ShaftSpec } = {
	{ z = -960, width = 66, weight = 1 },
	{ z = -560, width = 54, weight = 0.9 },
	{ z = -330, width = 42, weight = 0.7 },
}

local STORM = {
	dustColor = Color3.fromRGB(176, 128, 88),
	dustBoost = 1.6, -- × opacity at full storm
	heightBoost = 1.25, -- × band height at full storm
}

type Piece = {
	beam: Beam,
	weight: number,
	wall: boolean,
	mid: Vector3,
	height: number,
	a0: Attachment,
	a1: Attachment,
	g0: Vector3, -- ground under each end
	g1: Vector3,
}
type Shaft = { beam: Beam, weight: number, spec: ShaftSpec, a0: Attachment, a1: Attachment, rim: Vector3 }

local folder: Folder? = nil
local pieces: { Piece } = {}
local shafts: { Shaft } = {}
local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include

local lastCamera = Vector3.new(math.huge, 0, 0)
local lastKey = ""
local lastSun = Vector3.zero
local lastLook: any = nil
local hidden = false

local function groundY(x: number, z: number): number
	groundParams.FilterDescendantsInstances = { Workspace.Terrain }
	local hit = Workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -800, 0), groundParams)
	return if hit then hit.Position.Y else 0
end

local function attachment(name: string, position: Vector3): Attachment
	local a = Instance.new("Attachment")
	a.Name = name
	a.WorldPosition = position
	a.Parent = Workspace.Terrain
	return a
end

local function makeBeam(name: string, a0: Attachment, a1: Attachment): Beam
	local beam = Instance.new("Beam")
	beam.Name = name
	beam.Attachment0 = a0
	beam.Attachment1 = a1
	beam.FaceCamera = true
	beam.Segments = 1
	beam.Texture = Assets.searchlight_cone
	beam.TextureMode = Enum.TextureMode.Wrap
	beam.TextureLength = TEXTURE_LENGTH
	beam.TextureSpeed = 0
	beam.LightEmission = 0
	beam.LightInfluence = 0
	beam.Enabled = false
	beam.Parent = folder
	return beam
end

local function point(spec: BandSpec, s: number): (number, number)
	if spec.axis == "x" then
		return s, spec.at
	end
	return spec.at, s
end

local function buildBands()
	for i, spec in BANDS do
		local count = math.max(1, math.ceil((spec.to - spec.from) / SEGMENT))
		local ground: { Vector3 } = {}
		for k = 0, count do
			local x, z = point(spec, spec.from + (spec.to - spec.from) * k / count)
			table.insert(ground, Vector3.new(x, groundY(x, z), z))
		end
		for k = 1, count do
			-- A beam is centred on its attachments: lift them half the band
			-- height so the band's lower (zero-opacity) edge rests on the floor.
			local lift = Vector3.new(0, spec.height * 0.5, 0)
			local a0 = attachment(string.format("Dust%d_%da", i, k), ground[k] + lift)
			local a1 = attachment(string.format("Dust%d_%db", i, k), ground[k + 1] + lift)
			local beam = makeBeam(string.format("Dust%d_%d", i, k), a0, a1)
			beam.Width0 = spec.height
			beam.Width1 = spec.height
			table.insert(pieces, {
				beam = beam,
				weight = spec.weight,
				wall = spec.wall == true,
				mid = (ground[k] + ground[k + 1]) * 0.5,
				height = spec.height,
				a0 = a0,
				a1 = a1,
				g0 = ground[k],
				g1 = ground[k + 1],
			})
		end
	end
end

local function rimHeight(z: number): number
	-- Highest terrain along a short run over the wall top.
	local top = 0
	for x = SHAFT_RIM_X - 60, SHAFT_RIM_X - 180, -40 do
		top = math.max(top, groundY(x, z))
	end
	return if top > 20 then top else 160
end

local function buildShafts()
	for i, spec in SHAFTS do
		local rim = Vector3.new(SHAFT_RIM_X, rimHeight(spec.z) + 4, spec.z)
		local a0 = attachment("Shaft" .. i .. "a", rim)
		local a1 = attachment("Shaft" .. i .. "b", rim)
		local beam = makeBeam("Shaft" .. i, a0, a1)
		beam.TextureMode = Enum.TextureMode.Stretch
		beam.TextureLength = 1
		beam.LightEmission = 1
		beam.Width0 = spec.width
		beam.Width1 = spec.width * 2.4
		table.insert(shafts, { beam = beam, weight = spec.weight, spec = spec, a0 = a0, a1 = a1, rim = rim })
	end
end

local function sequence(peak: number, fadeIn: boolean): NumberSequence
	local v = 1 - math.clamp(peak, 0, 1)
	if fadeIn then
		-- shafts: fade in off the rim, strongest mid-air, gone by the floor
		return NumberSequence.new({
			NumberSequenceKeypoint.new(0, 1),
			NumberSequenceKeypoint.new(0.18, 1 - (1 - v) * 0.7),
			NumberSequenceKeypoint.new(0.5, v),
			NumberSequenceKeypoint.new(0.82, 1 - (1 - v) * 0.5),
			NumberSequenceKeypoint.new(1, 1),
		})
	end
	return NumberSequence.new(v)
end

local function nearFade(distance: number): number
	local t = math.clamp((distance - NEAR_FADE[1]) / (NEAR_FADE[2] - NEAR_FADE[1]), 0, 1)
	return t * t * (3 - 2 * t)
end

local function smooth(e0: number, e1: number, x: number): number
	local t = math.clamp((x - e0) / (e1 - e0), 0, 1)
	return t * t * (3 - 2 * t)
end

-- How much a point is seen against the sun from the camera (0 away, 1 into
-- it), horizontally: dust there is backlit and glows.
local function towardSun(camera: Vector3, at: Vector3, sun: Vector3): number
	local flat = Vector3.new(at.X - camera.X, 0, at.Z - camera.Z)
	local sunFlat = Vector3.new(sun.X, 0, sun.Z)
	if flat.Magnitude < 1 or sunFlat.Magnitude < 1e-3 or sun.Y < 0.02 then
		return 0
	end
	return smooth(0.2, 0.9, flat.Unit:Dot(sunFlat.Unit))
end

local function updateBands(look: any, storm: number, camera: Vector3, sun: Vector3)
	local dust = look.dustColor:Lerp(STORM.dustColor, storm)
	local wallColor = look.wallColor:Lerp(STORM.dustColor, storm)
	local boost = 1 + (STORM.dustBoost - 1) * storm
	local grow = 1 + (STORM.heightBoost - 1) * storm
	local dustSeq = ColorSequence.new(dust)
	local wallSeq = ColorSequence.new(wallColor)
	for _, piece in pieces do
		local base = if piece.wall then look.wallAlpha else look.dustAlpha
		local peak = base * piece.weight * boost * nearFade((piece.mid - camera).Magnitude)
		local beam = piece.beam
		beam.Enabled = peak > 0.002
		if beam.Enabled then
			local glow = look.dustGlow * (1 - storm) * towardSun(camera, piece.mid, sun)
			local tint = if piece.wall then wallColor else dust
			beam.Color = if glow > 0.01 then ColorSequence.new(tint:Lerp(look.shaftColor, glow * 0.6)) elseif piece.wall then wallSeq else dustSeq
			beam.LightEmission = glow
			beam.Transparency = sequence(peak, false)
			local h = piece.height * grow
			beam.Width0 = h
			beam.Width1 = h
			local lift = Vector3.new(0, h * 0.5, 0)
			piece.a0.WorldPosition = piece.g0 + lift
			piece.a1.WorldPosition = piece.g1 + lift
		end
	end
end

local function updateShafts(look: any, storm: number, sun: Vector3, camera: Vector3)
	local peakBase = look.shaftAlpha * (1 - storm)
	local up = sun.Y > 0.02
	local colorSeq = ColorSequence.new(look.shaftColor)
	for _, shaft in shafts do
		-- A shaft seen along its length collapses into a bright sliver:
		-- only show it from the side.
		local mid = shaft.rim - sun * 400
		local endOn = math.abs((mid - camera).Unit:Dot(sun))
		local side = 1 - smooth(0.7, 0.88, endOn)
		local peak = if up then peakBase * shaft.weight * side else 0
		local beam = shaft.beam
		beam.Enabled = peak > 0.002
		if beam.Enabled then
			beam.Color = colorSeq
			beam.Transparency = sequence(peak, true)
			-- Along the light: away from the sun until it reaches the floor.
			local length = math.min(shaft.rim.Y / math.max(sun.Y, 0.05), SHAFT_MAX_LENGTH)
			shaft.a1.WorldPosition = shaft.rim - sun * length
		end
	end
end

-- Called every frame by PostFx; only rewrites the beams when something that
-- shapes them changed (preset blend, storm, camera moved, sun moved).
function Air.update(look: any, storm: number, fading: boolean)
	if not folder then
		return
	end
	local off = IS_STUDIO and Workspace:GetAttribute("AirFxOff") == true
	if off ~= hidden then
		hidden = off;
		(folder :: Folder).Parent = if off then nil else Workspace
	end
	if off then
		return
	end
	local camera = Workspace.CurrentCamera.CFrame.Position
	local sun = Lighting:GetSunDirection()
	local key = string.format("%.2f", storm)
	local moved = (camera - lastCamera).Magnitude > 8
	local sunMoved = (sun - lastSun).Magnitude > 0.002
	if not (fading or moved or sunMoved or key ~= lastKey or look ~= lastLook) then
		return
	end
	lastKey = key
	lastSun = sun
	lastLook = look
	if moved then
		lastCamera = camera
	end
	updateBands(look, storm, lastCamera, sun)
	updateShafts(look, storm, sun, lastCamera)
end

-- Beauty shots want still frames: the shaft dust stops drifting.
local function pauseForBeauty()
	local beauty = IS_STUDIO and Workspace:GetAttribute("BeautyShot") ~= nil
	for _, shaft in shafts do
		shaft.beam.TextureSpeed = if beauty then 0 else 0.015
	end
end

-- Builds once the basin floor is raycastable (PostFx waits for it).
function Air.build()
	if folder then
		return
	end
	local f = Instance.new("Folder")
	f.Name = "PostFxAir"
	folder = f
	buildBands()
	buildShafts()
	f.Parent = Workspace
	Workspace:GetAttributeChangedSignal("BeautyShot"):Connect(pauseForBeauty)
	pauseForBeauty()
end

return Air
