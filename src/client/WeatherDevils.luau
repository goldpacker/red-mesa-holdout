--!strict
-- Dust devils (VFX-4): a few whirling dust columns wandering the basin,
-- born and dying naturally (they spin up over a few seconds, wander with
-- the wind for 15-30 s, then weaken and collapse).
--
-- Look: a spinning funnel. Particles leave a point that orbits the axis at
-- ORBIT_R studs, thrown up and along the orbit's tangent, so each one flies
-- out on its own spiral and the column widens upward; the sprites spin
-- (RotSpeed) and the top leans downwind. A low skirt of dust swirls at the
-- foot. Soft DustDrift sheet, tinted to the ground.
--
-- Placement and rules:
--   * at most MAX_LIVE at once (none while a storm is up), a new one every
--     SPAWN_GAP seconds;
--   * born on open floor (sand, coarse sand, clay pans, road) 380-1300
--     studs from the turret, inside the arc the player can see, at least
--     AIM_CLEAR degrees off the current aim;
--   * never in front of the turret's aim for long: if one stays within the
--     centre of the view (a zoom-corrected cone) for AIM_LIMIT seconds it
--     starts to die;
--   * drift with the wind (x DRIFT) plus a slow wander, and die if they
--     leave the basin.
-- LOD: EffectsLod (zoom-corrected rate and size) on both emitters.

local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Effects = require(script.Parent.Effects)
local Light = require(script.Parent.EffectsLight)
local Lod = require(script.Parent.EffectsLod)
local Weather = require(script.Parent.Weather)

local Devils = {}

local MAX_LIVE = 2
local SPAWN_GAP = { 14, 34 } -- s between births
local FIRST = { 6, 14 }
local GROW, DECAY = 4, 5 -- s to spin up / collapse
local LIFE = { 15, 30 } -- s at full strength
local DRIFT = 4 -- x the wind's drift velocity
local WANDER = 5 -- studs/s of wander on top
local ORBIT_R = 1.6
local ORBIT_HZ = 1.4
local COLUMN_RATE = 45 -- particles/s at full strength, close up (a thinner column read as a smudge)
local SKIRT_RATE = 14
local CUTOFF = 2600
local AIM_CLEAR = 22 -- degrees off the aim at birth
local AIM_CONE = 0.35 -- fraction of the half-FOV counted as "in the aim"
local AIM_LIMIT = 2.5 -- s in the aim before it dies
local BASIN = { minX = -900, maxX = 900, minZ = -1450, maxZ = -150 }
local OPEN: { [Enum.Material]: boolean } = {
	[Enum.Material.Sand] = true,
	[Enum.Material.Mud] = true,
	[Enum.Material.Salt] = true,
	[Enum.Material.Ground] = true,
}
local SAND = Color3.fromRGB(214, 160, 110):Lerp(Color3.new(1, 1, 1), 0.3)
local ROAD = Color3.fromRGB(160, 122, 92):Lerp(Color3.new(1, 1, 1), 0.3)
local WASH = Color3.fromRGB(200, 178, 146):Lerp(Color3.new(1, 1, 1), 0.3)

type Devil = {
	pos: Vector3, -- ground point under the axis
	age: number,
	life: number,
	dying: number?, -- age at which the collapse started
	inAim: number,
	phase: number,
	seed: number,
	column: ParticleEmitter,
	skirt: ParticleEmitter,
	colAtt: Attachment,
	skirtAtt: Attachment,
	columnSize: NumberSequence,
	skirtSize: NumberSequence,
	columnT: NumberSequence,
	skirtT: NumberSequence,
	lastLight: number,
	base: Color3, -- day tint of the ground it rose from
}

local devils: { Devil } = {}
local pool: { Devil } = {}
local nextBirth = 0
local enabled = true
local rng = Random.new()

local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Include

local function ground(x: number, z: number): RaycastResult?
	params.FilterDescendantsInstances = { Workspace.Terrain }
	return Workspace:Raycast(Vector3.new(x, 300, z), Vector3.new(0, -400, 0), params)
end

local function sizes(a: number, b: number, c: number, spread: number): NumberSequence
	return NumberSequence.new({
		NumberSequenceKeypoint.new(0, a, a * spread),
		NumberSequenceKeypoint.new(0.45, b, b * spread),
		NumberSequenceKeypoint.new(1, c, c * spread),
	})
end

local function fades(a: number, b: number): NumberSequence
	return NumberSequence.new({
		NumberSequenceKeypoint.new(0, 1),
		NumberSequenceKeypoint.new(0.12, a),
		NumberSequenceKeypoint.new(0.55, b),
		NumberSequenceKeypoint.new(1, 1),
	})
end

local function build(): Devil
	local colAtt = Weather.attachment("DustDevil")
	local skirtAtt = Weather.attachment("DustDevilFoot")
	local column = Effects.emitter(colAtt, "DustDrift", 0, {
		Name = "DevilColumn",
		Size = sizes(4, 9, 18, 0.25),
		Transparency = fades(0.3, 0.45),
		ZOffset = 2,
		Lifetime = NumberRange.new(3.2, 4.2),
		Speed = NumberRange.new(18, 24),
		SpreadAngle = Vector2.new(4, 4),
		Drag = 0.1,
		EmissionDirection = Enum.NormalId.Top,
		RotSpeed = NumberRange.new(120, 200),
		Rotation = NumberRange.new(0, 360),
		LightEmission = 0,
		LightInfluence = 1,
	}) :: ParticleEmitter
	local skirt = Effects.emitter(skirtAtt, "DustDrift", 0, {
		Name = "DevilSkirt",
		Size = sizes(5, 9, 12, 0.3),
		Transparency = fades(0.35, 0.5),
		ZOffset = 2,
		Lifetime = NumberRange.new(1.4, 2),
		Speed = NumberRange.new(6, 10),
		SpreadAngle = Vector2.new(75, 75),
		Drag = 0.8,
		EmissionDirection = Enum.NormalId.Top,
		RotSpeed = NumberRange.new(80, 140),
		Rotation = NumberRange.new(0, 360),
		Acceleration = Vector3.new(0, 2, 0),
		LightEmission = 0,
		LightInfluence = 1,
	}) :: ParticleEmitter
	for _, e in { column, skirt } do
		e.Enabled = true
		Weather.register(e)
	end
	return {
		pos = Vector3.zero, age = 0, life = 20, dying = nil, inAim = 0, phase = 0, seed = 0,
		column = column, skirt = skirt, colAtt = colAtt, skirtAtt = skirtAtt,
		columnSize = column.Size, skirtSize = skirt.Size, columnT = column.Transparency, skirtT = skirt.Transparency,
		lastLight = -1,
		base = SAND,
	}
end

-- Angle (fraction of the half-FOV) between the view centre and `p` on screen.
local function aimFraction(frame: Weather.Frame, p: Vector3): number
	local rel = frame.cam:PointToObjectSpace(p)
	if rel.Z > -1 then
		return math.huge
	end
	local halfV = math.tan(math.rad(frame.fov) * 0.5)
	return Vector2.new(rel.X / -rel.Z, rel.Y / -rel.Z).Magnitude / halfV
end

local function tint(hit: RaycastResult): Color3
	if hit.Material == Enum.Material.Ground then
		return ROAD
	elseif hit.Material == Enum.Material.Salt then
		return WASH
	end
	return SAND
end

local function tryBirth(frame: Weather.Frame): boolean
	local look = Vector3.new(frame.look.X, 0, frame.look.Z)
	look = if look.Magnitude > 1e-3 then look.Unit else Vector3.new(0, 0, -1)
	for _ = 1, 12 do
		-- inside the arc the turret sees (+-110 degrees of forward -Z)
		local yaw = math.rad(rng:NextNumber(-110, 110))
		local dist = rng:NextNumber(380, 1300)
		local dirv = Vector3.new(-math.sin(yaw), 0, -math.cos(yaw))
		local p = dirv * dist
		if p.X < BASIN.minX or p.X > BASIN.maxX or p.Z < BASIN.minZ or p.Z > BASIN.maxZ then
			continue
		end
		if math.deg(math.acos(math.clamp(dirv:Dot(look), -1, 1))) < AIM_CLEAR then
			continue
		end
		local hit = ground(p.X, p.Z)
		if not hit or not OPEN[hit.Material] or hit.Normal.Y < 0.93 or hit.Position.Y > 20 then
			continue
		end
		local d = table.remove(pool) or build()
		d.pos = hit.Position
		d.age = 0
		d.life = rng:NextNumber(LIFE[1], LIFE[2])
		d.dying = nil
		d.inAim = 0
		d.phase = rng:NextNumber(0, 2 * math.pi)
		d.seed = rng:NextNumber(0, 100)
		d.lastLight = -1
		d.base = tint(hit)
		table.insert(devils, d)
		return true
	end
	return false
end

local function retire(i: number)
	local d = table.remove(devils, i) :: Devil
	d.column.Rate = 0
	d.skirt.Rate = 0
	table.insert(pool, d)
end

local function strengthOf(d: Devil): number
	local s = math.clamp(d.age / GROW, 0, 1)
	if d.dying then
		s *= 1 - math.clamp((d.age - d.dying) / DECAY, 0, 1)
	end
	return s * s * (3 - 2 * s)
end

local function stepDevil(d: Devil, frame: Weather.Frame): boolean
	local dt = frame.dt
	d.age += dt
	if not d.dying and d.age > GROW + d.life then
		d.dying = d.age
	end
	-- Aim rule: dying early if it sits in the centre of the view (Studio
	-- captures can suspend it with Workspace.WeatherDevilAimOff = true).
	local aimOff = RunService:IsStudio() and Workspace:GetAttribute("WeatherDevilAimOff") == true
	if not aimOff and aimFraction(frame, d.pos + Vector3.new(0, 25, 0)) < AIM_CONE then
		d.inAim += dt
		if d.inAim > AIM_LIMIT and not d.dying then
			d.dying = d.age
		end
	else
		d.inAim = math.max(d.inAim - dt * 0.5, 0)
	end
	if frame.storm > 0.2 and not d.dying then
		d.dying = d.age
	end
	local s = strengthOf(d)
	if d.dying and s <= 0.001 then
		return false
	end
	-- Move: drift with the wind plus a slow wander, stay on the ground.
	local wander = Vector3.new(math.noise(d.seed, frame.t * 0.07), 0, math.noise(d.seed + 17, frame.t * 0.07)) * (WANDER * 2)
	local nextPos = d.pos + (frame.wind * DRIFT + wander) * dt
	local hit = ground(nextPos.X, nextPos.Z)
	if not hit or hit.Position.Y > 20 or nextPos.X < BASIN.minX - 100 or nextPos.X > BASIN.maxX + 100 or nextPos.Z < BASIN.minZ - 100 or nextPos.Z > BASIN.maxZ + 60 then
		if not d.dying then
			d.dying = d.age
		end
	else
		d.pos = hit.Position
	end
	-- The emission point orbits the axis; particles leave up and along the
	-- orbit's tangent (the spin), leaning downwind.
	d.phase += dt * ORBIT_HZ * 2 * math.pi
	local radial = Vector3.new(math.cos(d.phase), 0, math.sin(d.phase))
	local tangent = Vector3.new(-radial.Z, 0, radial.X)
	local up = (Vector3.yAxis + tangent * 0.24 + frame.dir * 0.1).Unit
	d.colAtt.CFrame = Effects.upFrame(d.pos + radial * ORBIT_R + Vector3.new(0, 1.5, 0), up)
	d.skirtAtt.CFrame = Effects.upFrame(d.pos + Vector3.new(0, 1, 0), Vector3.yAxis)
	return true
end

local lodDue = 0
local function lod(d: Devil, frame: Weather.Frame)
	local s = strengthOf(d)
	local rateK, sizeK = Lod.factor(d.pos + Vector3.new(0, 20, 0), CUTOFF)
	local on = if enabled then 1 else 0
	local dense = 0.5 + 0.5 * frame.density
	d.column.Rate = COLUMN_RATE * s * rateK * on * dense
	d.skirt.Rate = SKIRT_RATE * s * rateK * on * dense
	-- Grows taller as it spins up (speed), and the sprites scale with LOD.
	d.column.Speed = NumberRange.new(10 + 8 * s, 13 + 11 * s)
	d.column.Size = Lod.scaleSeq(d.columnSize, sizeK * (0.6 + 0.4 * s))
	d.skirt.Size = Lod.scaleSeq(d.skirtSize, sizeK)
	d.column.Acceleration = frame.wind * 1.6 + Vector3.new(0, 0.5, 0)
	local lightK, thin = Light.dust(d.pos + Vector3.new(0, 8, 0))
	if math.abs(lightK - d.lastLight) > 0.03 then
		d.lastLight = lightK
		local c = ColorSequence.new(Light.scale(d.base, lightK))
		d.column.Color = c
		d.skirt.Color = c
		d.column.Transparency = Light.thinner(d.columnT, thin)
		d.skirt.Transparency = Light.thinner(d.skirtT, thin)
	end
end

function Devils.setActive(value: boolean)
	enabled = value
	if not value then
		for i = #devils, 1, -1 do
			retire(i)
		end
	end
end

function Devils.step(frame: Weather.Frame)
	for i = #devils, 1, -1 do
		if not stepDevil(devils[i], frame) then
			retire(i)
		end
	end
	local now = os.clock()
	if now >= lodDue then
		lodDue = now + 0.2
		for _, d in devils do
			lod(d, frame)
		end
	end
	if not enabled then
		return
	end
	-- Studio test hook: Workspace attribute WeatherDevilNow = true spawns
	-- one now (the placement rules still apply); it clears itself.
	if RunService:IsStudio() and Workspace:GetAttribute("WeatherDevilNow") == true then
		Workspace:SetAttribute("WeatherDevilNow", nil)
		if #devils < MAX_LIVE + 1 then
			tryBirth(frame)
		end
	end
	if nextBirth == 0 then
		nextBirth = now + rng:NextNumber(FIRST[1], FIRST[2])
	elseif now >= nextBirth then
		-- one at a time in busy fights (Weather density), none in storms
		local cap = if frame.storm > 0.05 then 0 elseif frame.density < 0.75 then 1 else MAX_LIVE
		if #devils < cap and tryBirth(frame) then
			nextBirth = now + rng:NextNumber(SPAWN_GAP[1], SPAWN_GAP[2])
		else
			nextBirth = now + 3
		end
	end
	if RunService:IsStudio() then
		Workspace:SetAttribute("WeatherDevils", #devils)
	end
end


return Devils
