--!strict
-- Birds (VFX-4): life over the basin.
--   Vultures  a handful circling high in two thermals over the far basin:
--             soaring (no flapping), banked into the turn by their speed and
--             radius, rocking a little; the thermals wander slowly. They sit
--             out dust storms.
--   Flocks    small flocks of dark birds that burst up and scatter from
--             nearby explosions (client/VehicleFxParticles.onExplosion):
--             they take off from the ground near the blast, flee away from
--             it and from the gun, flapping (wings rotate about the
--             shoulder), climb, glide in between, and fade out far away.
-- Meshes: ReplicatedStorage.Assets.VfxBirds (tools/assets/models/vfx_birds.py;
-- untextured, 484 tris in all). Missing assets = no birds.
-- Cheap: every bird part moves by one Workspace:BulkMoveTo per frame;
-- caps MAX_FLOCKS flocks of up to FLOCK_MAX birds, VULTURES vultures.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Weather = require(script.Parent.Weather)

local Birds = {}

local IS_STUDIO = RunService:IsStudio()
local G = 35 -- studs/s^2 (1 stud ~ 0.28 m)
local VULTURES = 5
local THERMALS = {
	{ centre = Vector3.new(-380, 0, -920), alt = { 190, 260 }, radius = { 70, 110 }, birds = 3 },
	{ centre = Vector3.new(420, 0, -1180), alt = { 170, 230 }, radius = { 60, 95 }, birds = 2 },
}
local SOAR_SPEED = { 28, 34 } -- studs/s
local MAX_FLOCKS = 2
local FLOCK_SIZE = { 7, 12 }
local FLOCK_MAX = 12
local FLOCK_COOLDOWN = 12 -- s between flocks
local FLOCK_LIFE = 14 -- s before a flock fades out
local FLOCK_MIN_SCALE = 0.8 -- blast scale that scatters birds
local FLAP_HZ = { 5.5, 7 }
local FLAP_DEG = 42
local FLEE_SPEED = { 26, 34 }
local FLEE_RANGE = 1500 -- studs from the turret: gone beyond this

type Vulture = {
	part: BasePart,
	thermal: number,
	alt: number,
	radius: number,
	speed: number,
	angle: number,
	dirSign: number,
	rock: number,
}
type Crow = {
	body: BasePart,
	wingL: BasePart,
	wingR: BasePart,
	pos: Vector3,
	vel: Vector3,
	delay: number,
	flapHz: number,
	flapPhase: number,
	glide: number, -- time left gliding
	offset: Vector3, -- place in the loose flock
	seed: number,
}
type Flock = { birds: { Crow }, age: number, heading: Vector3, climb: number, fade: number }

local template: Model? = nil
local wingOffsetL = CFrame.identity
local wingOffsetR = CFrame.identity
local vultures: { Vulture } = {}
local flocks: { Flock } = {}
local spare: { Crow } = {}
local lastFlock = -math.huge
local enabled = true
local rng = Random.new()
local parts: { BasePart } = {}
local frames: { CFrame } = {}

local function clone(name: string): BasePart?
	local t = template and template:FindFirstChild(name)
	if not (t and t:IsA("BasePart")) then
		return nil
	end
	local p = t:Clone() :: BasePart
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Parent = Weather.folder()
	return p
end

-- CFrame at `p` flying along `forward` with its up tilted toward `inward`
-- by `bank` radians.
local function flight(p: Vector3, forward: Vector3, up: Vector3): CFrame
	local f = forward.Unit
	local u = (up - f * up:Dot(f))
	u = if u.Magnitude > 1e-3 then u.Unit else Vector3.yAxis
	return CFrame.fromMatrix(p, f:Cross(u), u, -f)
end

---------------------------------------------------------------------------
-- Vultures
---------------------------------------------------------------------------

local function spawnVultures()
	for ti, th in THERMALS do
		for _ = 1, th.birds do
			local part = clone("Vulture")
			if not part then
				return
			end
			table.insert(vultures, {
				part = part,
				thermal = ti,
				alt = rng:NextNumber(th.alt[1], th.alt[2]),
				radius = rng:NextNumber(th.radius[1], th.radius[2]),
				speed = rng:NextNumber(SOAR_SPEED[1], SOAR_SPEED[2]),
				angle = rng:NextNumber(0, 2 * math.pi),
				dirSign = if ti == 1 then 1 else -1,
				rock = rng:NextNumber(0, 10),
			})
		end
	end
	if #vultures > VULTURES then
		for i = #vultures, VULTURES + 1, -1 do
			vultures[i].part:Destroy()
			vultures[i] = nil
		end
	end
end

local function thermalCentre(i: number, t: number, wind: Vector3): Vector3
	local th = THERMALS[i]
	-- Slow wander, leaning a little downwind.
	local wander = Vector3.new(math.sin(t / 53 + i) * 160, 0, math.sin(t / 71 + 2 * i) * 120)
	return th.centre + wander + wind * 12
end

local grounded = false -- vultures sit out dust storms

local function stepVultures(frame: Weather.Frame)
	local down = frame.storm > 0.3
	if down ~= grounded then
		grounded = down
		for _, v in vultures do
			v.part.Parent = if down then nil else Weather.folder()
		end
	end
	if down then
		return
	end
	for _, v in vultures do
		local centre = thermalCentre(v.thermal, frame.t, frame.wind)
		v.angle += v.dirSign * v.speed / v.radius * frame.dt
		local radial = Vector3.new(math.cos(v.angle), 0, math.sin(v.angle))
		local tangent = Vector3.new(-radial.Z, 0, radial.X) * v.dirSign
		local alt = v.alt + math.sin(frame.t / 9 + v.rock) * 12
		local p = centre + radial * v.radius + Vector3.new(0, alt, 0)
		local bank = math.atan(v.speed * v.speed / (G * v.radius)) + math.rad(4) * math.sin(frame.t * 1.3 + v.rock)
		local up = Vector3.yAxis * math.cos(bank) - radial * math.sin(bank)
		table.insert(parts, v.part)
		table.insert(frames, flight(p, tangent, up))
	end
end

---------------------------------------------------------------------------
-- Flocks
---------------------------------------------------------------------------

local function newCrow(): Crow?
	local c = table.remove(spare)
	if c then
		for _, p in { c.body, c.wingL, c.wingR } do
			p.Transparency = 0
			p.Parent = Weather.folder()
		end
		return c
	end
	local body, wl, wr = clone("Crow"), clone("CrowWingL"), clone("CrowWingR")
	if not (body and wl and wr) then
		for _, p in { body, wl, wr } do
			if p then
				p:Destroy()
			end
		end
		return nil
	end
	return {
		body = body, wingL = wl, wingR = wr, pos = Vector3.zero, vel = Vector3.zero, delay = 0,
		flapHz = 6, flapPhase = 0, glide = 0, offset = Vector3.zero, seed = 0,
	}
end

local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Include

local function scatter(at: Vector3, scale: number)
	if not enabled or not template or scale < FLOCK_MIN_SCALE then
		return
	end
	local now = os.clock()
	if now - lastFlock < FLOCK_COOLDOWN or #flocks >= MAX_FLOCKS then
		return
	end
	local flat = Vector3.new(at.X, 0, at.Z)
	if flat.Magnitude < 180 or at.Y > 40 then
		return -- not on the basin floor (the mesa, the gun, the air)
	end
	-- Take off from open ground near the blast, on the far side from the gun.
	params.FilterDescendantsInstances = { Workspace.Terrain }
	local away = flat.Unit
	local side = Vector3.new(-away.Z, 0, away.X)
	local spot = flat + away * rng:NextNumber(50, 120) + side * rng:NextNumber(-80, 80)
	local hit = Workspace:Raycast(Vector3.new(spot.X, 300, spot.Z), Vector3.new(0, -400, 0), params)
	if not hit or hit.Position.Y > 30 then
		return
	end
	lastFlock = now
	local fleeDir = (Vector3.new(hit.Position.X - at.X, 0, hit.Position.Z - at.Z).Unit * 0.6 + away * 0.8).Unit
	local flock: Flock = { birds = {}, age = 0, heading = fleeDir, climb = rng:NextNumber(55, 110), fade = 0 }
	local n = math.min(rng:NextInteger(FLOCK_SIZE[1], FLOCK_SIZE[2]), FLOCK_MAX)
	for _ = 1, n do
		local c = newCrow()
		if not c then
			break
		end
		c.pos = hit.Position + Vector3.new(rng:NextNumber(-12, 12), 0.6, rng:NextNumber(-12, 12))
		local out = Vector3.new(c.pos.X - at.X, 0, c.pos.Z - at.Z)
		out = if out.Magnitude > 1e-3 then out.Unit else fleeDir
		c.vel = (out * rng:NextNumber(14, 22) + Vector3.new(0, rng:NextNumber(10, 16), 0))
		c.delay = rng:NextNumber(0, 0.45)
		c.flapHz = rng:NextNumber(FLAP_HZ[1], FLAP_HZ[2])
		c.flapPhase = rng:NextNumber(0, 2 * math.pi)
		c.glide = 0
		c.offset = Vector3.new(rng:NextNumber(-14, 14), rng:NextNumber(-6, 6), rng:NextNumber(-14, 14))
		c.seed = rng:NextNumber(0, 100)
		table.insert(flock.birds, c)
	end
	if #flock.birds > 0 then
		table.insert(flocks, flock)
	end
end

local function releaseFlock(f: Flock)
	for _, c in f.birds do
		for _, p in { c.body, c.wingL, c.wingR } do
			p.Parent = nil
		end
		table.insert(spare, c)
	end
end

local function fly(c: Crow, f: Flock, frame: Weather.Frame)
	local dt = frame.dt
	-- Steer toward the flock's escape line and climb height, loosely.
	local speed = FLEE_SPEED[1] + (FLEE_SPEED[2] - FLEE_SPEED[1]) * (0.5 + 0.5 * math.noise(c.seed, frame.t * 0.3))
	local ground = f.climb
	local wantUp = math.clamp((ground - (c.pos.Y - 2)) * 0.25, -4, 12)
	local desired = f.heading * speed + Vector3.new(0, wantUp, 0) + c.offset * 0.15
	local turn = math.min(1, dt * (if f.age < 1.2 then 1.2 else 2.2))
	c.vel = c.vel:Lerp(desired, turn)
	c.pos += c.vel * dt
	-- Flap, with short glides once airborne.
	if c.glide > 0 then
		c.glide -= dt
	elseif f.age > 2.5 and rng:NextNumber() < dt * 0.35 then
		c.glide = rng:NextNumber(0.5, 1.2)
	end
end

local function stepCrow(c: Crow, f: Flock, frame: Weather.Frame)
	if c.delay > 0 then
		-- Still on the ground, beating its wings to take off.
		c.delay -= frame.dt
	else
		fly(c, f, frame)
	end
	local flap = if c.glide > 0 then math.rad(8) else math.rad(FLAP_DEG) * math.sin(c.flapPhase + frame.t * c.flapHz * 2 * math.pi) + math.rad(10)
	local cf = flight(c.pos, if c.vel.Magnitude > 1 then c.vel else f.heading, Vector3.yAxis)
	table.insert(parts, c.body)
	table.insert(frames, cf)
	table.insert(parts, c.wingR)
	table.insert(frames, cf * wingOffsetR * CFrame.Angles(0, 0, flap))
	table.insert(parts, c.wingL)
	table.insert(frames, cf * wingOffsetL * CFrame.Angles(0, 0, -flap))
end

local function stepFlocks(frame: Weather.Frame)
	for i = #flocks, 1, -1 do
		local f = flocks[i]
		f.age += frame.dt
		-- The flock leaves when its time is up or it has flown out past the
		-- basin (FLEE_RANGE from the turret); it fades out over 1.2 s.
		local far = true
		for _, c in f.birds do
			stepCrow(c, f, frame)
			if Vector2.new(c.pos.X, c.pos.Z).Magnitude < FLEE_RANGE then
				far = false
			end
		end
		if f.age > FLOCK_LIFE or far then
			f.fade += frame.dt
			local tr = math.clamp(f.fade / 1.2, 0, 1)
			for _, c in f.birds do
				c.body.Transparency = tr
				c.wingL.Transparency = tr
				c.wingR.Transparency = tr
			end
			if tr >= 1 then
				releaseFlock(f)
				table.remove(flocks, i)
			end
		end
	end
end

---------------------------------------------------------------------------

function Birds.start()
	task.spawn(function()
		local a = ReplicatedStorage:WaitForChild("Assets", 30)
		local m = a and a:WaitForChild("VfxBirds", 30)
		if not (m and m:IsA("Model")) then
			return
		end
		template = m
		local body = m:FindFirstChild("Crow")
		local wl = m:FindFirstChild("CrowWingL")
		local wr = m:FindFirstChild("CrowWingR")
		if body and wl and wr and body:IsA("BasePart") and wl:IsA("BasePart") and wr:IsA("BasePart") then
			wingOffsetL = body.CFrame:ToObjectSpace(wl.CFrame)
			wingOffsetR = body.CFrame:ToObjectSpace(wr.CFrame)
		end
		spawnVultures()
	end)
	local ok, particles = pcall(require, script.Parent.VehicleFxParticles)
	if ok and typeof(particles) == "table" and (particles :: any).onExplosion then
		(particles :: any).onExplosion(scatter)
	end
end

function Birds.setActive(value: boolean)
	enabled = value
	for _, v in vultures do
		v.part.Parent = if value then Weather.folder() else nil
	end
	if not value then
		for i = #flocks, 1, -1 do
			releaseFlock(flocks[i])
			flocks[i] = nil
		end
	end
end

function Birds.step(frame: Weather.Frame)
	if not enabled then
		return
	end
	table.clear(parts)
	table.clear(frames)
	stepVultures(frame)
	stepFlocks(frame)
	if #parts > 0 then
		Workspace:BulkMoveTo(parts, frames, Enum.BulkMoveMode.FireCFrameChanged)
	end
	if IS_STUDIO then
		-- Studio test hook: WeatherBirdsAt = Vector3 scatters a flock there.
		local at = Workspace:GetAttribute("WeatherBirdsAt")
		if typeof(at) == "Vector3" then
			Workspace:SetAttribute("WeatherBirdsAt", nil)
			lastFlock = -math.huge
			scatter(at, 1)
		end
		local n = 0
		for _, f in flocks do
			n += #f.birds
		end
		Workspace:SetAttribute("WeatherBirds", string.format("%d vultures, %d flocks, %d birds", #vultures, #flocks, n))
	end
end

return Birds
