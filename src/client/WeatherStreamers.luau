--!strict
-- Sand streamers (VFX-4): wind-blown sand flowing low over the basin floor,
-- off dune crests and off the canyon rims, in gusts (shared/Wind).
--
--   Tiles   the basin floor is cut into TILES_X x TILES_Z tiles, each an
--           invisible box-shaped emitter lying on the floor (y ~2-5) and
--           turned to the wind. Low, flat smears (the soft DustDrift sheet,
--           camera-facing, squashed wide: Squash < 0 widens) run downwind.
--           Velocity-aligned sprites stood up as bright vertical shafts
--           wherever the wind blew toward the camera (Studio look-dev). Each tile's
--           rate follows the gust envelope delayed by its upwind distance,
--           so a gust visibly sweeps across the basin as a band of moving
--           sand (GUST_SPEED). Denser near the camera: the zoom-corrected
--           distance LOD (EffectsLod) thins far tiles and enlarges their
--           streaks, so the screen density falls off with distance.
--   Crests  small streaming puffs off the dune crests found by the survey.
--   Rims    big, faint plumes spilling off the lee edge of the canyon rims
--           and butte tops upwind of the basin (the survey finds rim cells
--           with a cliff drop downwind).
-- The survey (once, a few seconds after start) ray-casts the terrain on a
-- 40-stud grid; it is spread over frames.
-- Storms (Weather frame `storm`) multiply rates, speed and the cap.
-- Cap: MAX_RATE particles/s over all streamers (x (1 + storm)).

local Workspace = game:GetService("Workspace")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Effects = require(script.Parent.Effects)
local Light = require(script.Parent.EffectsLight)
local Lod = require(script.Parent.EffectsLod)
local Weather = require(script.Parent.Weather)
local Wind = require(ReplicatedStorage.Shared.Wind)

local Streamers = {}

local FLOOR_Y = 2 -- the basin floor (ENV-4 survey: 92 % of it meshes at y 2.0)
local TILE = 420
local TILES_X = { -840, -420, 0, 420, 840 } -- tile centres (x)
local TILES_Z = { -1260, -840, -420 } -- tile centres (z); the mesa covers z > -150
local TILE_RATE = 40 -- particles/s of one tile at the top of a gust, close up
local CREST_RATE = 8
local RIM_RATE = 1.6
local MAX_RATE = 130 -- all streamers, particles/s (x (1 + storm))
local GUST_SPEED = 70 -- studs/s a gust band travels downwind
local UPDATE = 0.25 -- s between rate/LOD updates
local CUTOFF = 2600 -- zoom-corrected distance with no streamers beyond
local RIM_CUTOFF = 3000

-- Pale sand: it must read paler than the floor in every light (the plain
-- lifted dust tint vanished into the sunset floor). Its light factor is
-- EffectsLight's ^ 0.8 (a touch brighter than dust at low sun).
local SAND = Color3.fromRGB(240, 214, 188)
local LIGHT_POWER = 0.8
local ROCK = Effects.ROCK_DUST:Lerp(Color3.new(1, 1, 1), 0.3)

type Source = {
	e: ParticleEmitter,
	at: Vector3, -- centre (for LOD, light and the gust delay)
	near: Vector3?, -- nearest point to use for LOD (tiles: clamped per update)
	half: number?, -- tiles: half extent
	base: number, -- particles/s at full gust
	size: NumberSequence,
	transparency: NumberSequence,
	color: Color3, -- day colour (scaled by EffectsLight)
	sizeK: number,
	bright: number,
	thin: number,
	shade: boolean, -- terrain shadow at the source (cached: the sun moves only between presets)
	shadeDue: number,
	desired: number,
	kind: "tile" | "crest" | "rim",
	carrier: BasePart?,
	att: Attachment?,
}

local sources: { Source } = {}
local due = 0
local surveyed = false
local crests: { Vector3 } = {}
local rims: { Vector3 } = {}
local enabled = true

local function sizes(a: number, b: number, c: number, spread: number): NumberSequence
	return NumberSequence.new({
		NumberSequenceKeypoint.new(0, a, a * spread),
		NumberSequenceKeypoint.new(0.5, b, b * spread),
		NumberSequenceKeypoint.new(1, c, c * spread),
	})
end

local function fades(a: number, b: number): NumberSequence
	return NumberSequence.new({
		NumberSequenceKeypoint.new(0, 1),
		NumberSequenceKeypoint.new(0.15, a),
		NumberSequenceKeypoint.new(0.6, b),
		NumberSequenceKeypoint.new(1, 1),
	})
end

-- Frame whose +Y (emission) is `d` and +X across it.
local function windFrame(p: Vector3, d: Vector3): CFrame
	local across = Vector3.yAxis:Cross(d)
	across = if across.Magnitude > 1e-3 then across.Unit else Vector3.xAxis
	local up = d.Unit
	return CFrame.fromMatrix(p, across, up)
end

local function tilted(dir: Vector3, degrees: number): Vector3
	local r = math.rad(degrees)
	return (dir * math.cos(r) + Vector3.yAxis * math.sin(r)).Unit
end

---------------------------------------------------------------------------
-- Emitters
---------------------------------------------------------------------------

local function streak(parent: Instance, name: string, s: number, speed: number, life: { number }): ParticleEmitter?
	local e = Effects.emitter(parent, "DustDrift", 0, {
		Name = name,
		Size = sizes(8 * s, 14 * s, 18 * s, 0.35),
		Transparency = fades(0.45, 0.5),
		Orientation = Enum.ParticleOrientation.FacingCamera,
		Squash = NumberSequence.new(-2),
		ZOffset = 4,
		Lifetime = NumberRange.new(life[1], life[2]),
		Speed = NumberRange.new(speed * 0.75, speed * 1.25),
		SpreadAngle = Vector2.new(4, 10),
		Drag = 0.25,
		Acceleration = Vector3.new(0, -0.6, 0),
		EmissionDirection = Enum.NormalId.Top,
		Rotation = NumberRange.new(-3, 3),
		RotSpeed = NumberRange.new(0),
		Color = ColorSequence.new(SAND),
		LightEmission = 0,
		LightInfluence = 1,
	})
	if e then
		e.Enabled = true
		Weather.register(e)
	end
	return e
end

local function addSource(src: Source)
	src.size = src.e.Size
	src.transparency = src.e.Transparency
	table.insert(sources, src)
end

local function buildTiles()
	local d = Wind.DIRECTION
	for _, x in TILES_X do
		for _, z in TILES_Z do
			local at = Vector3.new(x, FLOOR_Y + 1.6, z)
			local part = Weather.carrier("StreamerTile", Vector3.new(TILE * 1.1, TILE * 1.1, 3))
			part.CFrame = windFrame(at, tilted(d, 3))
			local e = streak(part, "SandStreamer", 1, 20, { 1.8, 3 })
			if e then
				e.Shape = Enum.ParticleEmitterShape.Box
				e.ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume
				e.ShapeInOut = Enum.ParticleEmitterShapeInOut.Outward
				addSource({
					e = e, at = at, half = TILE * 0.5, base = TILE_RATE, size = e.Size, transparency = e.Transparency, color = SAND,
					sizeK = 1, bright = -1, thin = -1, shade = false, shadeDue = 0, desired = 0, kind = "tile", carrier = part,
				})
			else
				part:Destroy()
			end
		end
	end
end

local function buildCrests()
	for _, p in crests do
		local att = Weather.attachment("CrestStreamer")
		att.CFrame = windFrame(p + Vector3.new(0, 1.2, 0), tilted(Wind.DIRECTION, 12))
		local e = streak(att, "CrestStreamer", 0.7, 14, { 1.4, 2.2 })
		if e then
			addSource({
				e = e, at = p, base = CREST_RATE, size = e.Size, transparency = e.Transparency, color = SAND,
				sizeK = 1, bright = -1, thin = -1, shade = false, shadeDue = 0, desired = 0, kind = "crest", att = att,
			})
		end
	end
end

local function buildRims()
	for _, p in rims do
		local att = Weather.attachment("RimPlume")
		att.CFrame = windFrame(p + Vector3.new(0, 4, 0), tilted(Wind.DIRECTION, -16))
		local e = Effects.emitter(att, "DustDrift", 0, {
			Name = "RimPlume",
			Size = sizes(24, 46, 62, 0.3),
			Transparency = fades(0.84, 0.8),
			ZOffset = 6,
			Lifetime = NumberRange.new(5, 7),
			Speed = NumberRange.new(12, 20),
			SpreadAngle = Vector2.new(10, 18),
			Drag = 0.3,
			Acceleration = Vector3.new(0, -1.4, 0),
			EmissionDirection = Enum.NormalId.Top,
			Color = ColorSequence.new(ROCK),
			LightEmission = 0,
			LightInfluence = 1,
		})
		if e then
			e.Enabled = true
			Weather.register(e)
			addSource({
				e = e, at = p, base = RIM_RATE, size = e.Size, transparency = e.Transparency, color = ROCK,
				sizeK = 1, bright = -1, thin = -1, shade = false, shadeDue = 0, desired = 0, kind = "rim", att = att,
			})
		end
	end
end

---------------------------------------------------------------------------
-- Survey: dune crests and rim edges from the terrain
---------------------------------------------------------------------------

local GRID = 40
local MIN_X, MAX_X, MIN_Z, MAX_Z = -1500, 1500, -2000, 500
local OPEN: { [Enum.Material]: boolean } = {
	[Enum.Material.Sand] = true,
	[Enum.Material.Mud] = true,
}

local function survey()
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { Workspace.Terrain }
	local nx = math.floor((MAX_X - MIN_X) / GRID) + 1
	local nz = math.floor((MAX_Z - MIN_Z) / GRID) + 1
	local h: { { number } } = table.create(nx)
	local mat: { { Enum.Material? } } = table.create(nx)
	local rays = 0
	for i = 1, nx do
		h[i] = table.create(nz, -1e3)
		mat[i] = {}
		for j = 1, nz do
			local x, z = MIN_X + (i - 1) * GRID, MIN_Z + (j - 1) * GRID
			local hit = Workspace:Raycast(Vector3.new(x, 700, z), Vector3.new(0, -900, 0), params)
			if hit then
				h[i][j] = hit.Position.Y
				mat[i][j] = hit.Material
			end
			rays += 1
			if rays % 400 == 0 then
				RunService.Heartbeat:Wait()
			end
		end
	end
	local function at(i: number, j: number): number
		if i < 1 or i > nx or j < 1 or j > nz then
			return -1e3
		end
		return h[i][j]
	end
	-- Crests: open-floor local maxima standing clear of their surroundings.
	local found: { { p: Vector3, score: number } } = {}
	for i = 3, nx - 2 do
		for j = 3, nz - 2 do
			local y = h[i][j]
			local m = mat[i][j]
			if y > 2.6 and y < 16 and m and OPEN[m] then
				local peak = true
				local ring = 0
				for di = -1, 1 do
					for dj = -1, 1 do
						if (di ~= 0 or dj ~= 0) and at(i + di, j + dj) > y then
							peak = false
						end
					end
				end
				for _, o in { { 2, 0 }, { -2, 0 }, { 0, 2 }, { 0, -2 } } do
					ring += at(i + o[1], j + o[2])
				end
				local prominence = y - ring / 4
				local p = Vector3.new(MIN_X + (i - 1) * GRID, y, MIN_Z + (j - 1) * GRID)
				local d = Vector2.new(p.X, p.Z).Magnitude
				if peak and prominence > 0.8 and d > 180 and d < 1400 then
					table.insert(found, { p = p, score = prominence })
				end
			end
		end
	end
	table.sort(found, function(a, b)
		return a.score > b.score
	end)
	for _, c in found do
		local ok = true
		for _, q in crests do
			if (q - c.p).Magnitude < 160 then
				ok = false
				break
			end
		end
		if ok then
			table.insert(crests, c.p)
			if #crests >= 8 then
				break
			end
		end
	end
	-- Rims: high cells with a cliff drop just downwind (the lee edge).
	local d = Wind.DIRECTION
	local di, dj = math.round(d.X * 2), math.round(d.Z * 2) -- ~80 studs downwind
	local rimFound: { { p: Vector3, score: number } } = {}
	for i = 1, nx do
		for j = 1, nz do
			local y = h[i][j]
			local lee = at(i + di, j + dj)
			if y > 45 and lee > -1e2 and y - lee >= 30 then
				local p = Vector3.new(MIN_X + (i - 1) * GRID, y, MIN_Z + (j - 1) * GRID)
				local flat = Vector2.new(p.X, p.Z)
				local dist = flat.Magnitude
				local yaw = math.deg(math.atan2(-p.X, -p.Z)) -- 0 = the turret's forward (-Z)
				-- within ~1,300 studs: Roblox stops drawing particles farther out
				if dist > 320 and dist < 1300 and math.abs(yaw) < 120 then
					table.insert(rimFound, { p = p, score = -math.abs(dist - 1000) + (y - lee) })
				end
			end
		end
	end
	table.sort(rimFound, function(a, b)
		return a.score > b.score
	end)
	for _, c in rimFound do
		local ok = true
		for _, q in rims do
			if (q - c.p).Magnitude < 280 then
				ok = false
				break
			end
		end
		if ok then
			table.insert(rims, c.p)
			if #rims >= 5 then
				break
			end
		end
	end
	surveyed = true
	if RunService:IsStudio() then
		Workspace:SetAttribute("WeatherSurvey", string.format("%d rays, %d crests, %d rims", rays, #crests, #rims))
	end
	buildCrests()
	buildRims()
end

---------------------------------------------------------------------------
-- Per update
---------------------------------------------------------------------------

local function nearestOnTile(src: Source, camPos: Vector3): Vector3
	local h = src.half or 0
	return Vector3.new(
		math.clamp(camPos.X, src.at.X - h, src.at.X + h),
		src.at.Y,
		math.clamp(camPos.Z, src.at.Z - h, src.at.Z + h)
	)
end

local function update(frame: Weather.Frame)
	local storm = frame.storm
	local total = 0
	local d = frame.dir
	for _, src in sources do
		-- The gust reaching this spot: the envelope delayed by its upwind distance.
		local delay = (src.at.X * d.X + src.at.Z * d.Z) / GUST_SPEED
		local _, strength, gust = Wind.at(frame.t - delay)
		local g = if src.kind == "tile" then 0.12 + 0.88 * gust elseif src.kind == "crest" then math.max(gust - 0.15, 0) ^ 1.5 else 0.15 + gust
		local p = if src.kind == "tile" then nearestOnTile(src, frame.camPos) else src.at
		local rateK, sizeK = Lod.factor(p, if src.kind == "rim" then RIM_CUTOFF else CUTOFF)
		local stormK = 1 + 1.5 * storm
		-- Busy fights (Weather density < 1): everything thins, and the crest
		-- and rim plumes go first (each emitter with live particles is a
		-- draw call; wave-9 GPU A/B).
		local dense = if storm > 0.05 then 1
			elseif src.kind == "tile" then frame.density
			else math.clamp((frame.density - 0.55) / 0.35, 0, 1)
		src.desired = if enabled then src.base * g * strength * rateK * stormK * dense else 0
		total += src.desired
		-- rim plumes are big already: no more than 1.3x (overdraw)
		sizeK = if src.kind == "rim" then math.min(sizeK, 1.3) else sizeK
		if math.abs(sizeK - src.sizeK) > 0.05 then
			src.sizeK = sizeK
			src.e.Size = Lod.scaleSeq(src.size, sizeK)
		end
		local now = os.clock()
		if now >= src.shadeDue then
			src.shadeDue = now + 2 + math.random()
			src.shade = Light.shadowed(src.at + Vector3.new(0, 3, 0))
		end
		local lightK, thin = Light.dust(src.at + Vector3.new(0, 3, 0), src.shade)
		if math.abs(lightK - src.bright) > 0.03 or math.abs(thin - src.thin) > 0.03 then
			src.bright = lightK
			src.thin = thin
			src.e.Color = ColorSequence.new(Light.scale(src.color, if src.kind == "rim" then lightK else lightK ^ LIGHT_POWER))
			src.e.Transparency = Light.thinner(src.transparency, thin)
		end
		local speed = (if src.kind == "rim" then 16 elseif src.kind == "crest" then 14 else 20) * (0.6 + 0.4 * strength) * (1 + 0.8 * storm)
		src.e.Speed = NumberRange.new(speed * 0.75, speed * 1.25)
	end
	local cap = MAX_RATE * (1 + storm)
	local k = if total > cap then cap / total else 1
	for _, src in sources do
		src.e.Rate = src.desired * k
	end
	-- The wind veers slowly: keep the tiles and emitters turned to it.
	for _, src in sources do
		if src.carrier then
			src.carrier.CFrame = windFrame(src.at, tilted(d, 3))
		elseif src.att then
			local tilt = if src.kind == "rim" then -16 else 12
			src.att.CFrame = windFrame(src.att.WorldPosition, tilted(d, tilt))
		end
	end
	if RunService:IsStudio() then
		Workspace:SetAttribute("WeatherStreamerRate", math.round(math.min(total, cap)))
	end
end

function Streamers.start()
	buildTiles()
	task.delay(6, survey)
end

function Streamers.setActive(value: boolean)
	enabled = value
	if not value then
		for _, src in sources do
			src.e.Rate = 0
		end
	end
end

function Streamers.step(frame: Weather.Frame)
	if os.clock() < due then
		return
	end
	due = os.clock() + UPDATE
	update(frame)
end

function Streamers.surveyed(): boolean
	return surveyed
end

return Streamers
