--!strict
-- Body motion for EnemyMotion (LOOK-3): a small offset of the whole model
-- about a roll/pitch centre, driven by the smoothed server motion.
--   Ground vehicles: suspension heave and pitch/roll bumps scaled by speed,
--     squat under acceleration, nose dive when braking, body roll away from
--     the turn, recoil rock when the main gun fires.
--   Helicopter: pendulum lean into acceleration (flare when braking) on top
--     of the server's velocity tilt, and a slow hover buffet.
--   Jet: bank into any lateral acceleration (coordinated turn), a light wing
--     rock, a lift when the bombs release.
-- Amplitudes are small on purpose: the server hit volumes don't follow the
-- body, so the drawn hull stays within a stud of them (LOOK-3 report).

local Workspace = game:GetService("Workspace")

local Body = {}

type Spring = { x: number, v: number, w: number, z: number }

type Profile = {
	ground: boolean,
	height: number, -- roll/pitch centre above the model pivot (studs)
	refSpeed: number, -- studs/s at which the bumps reach full size
	bumpFreq: number, -- bumps per stud travelled
	heave: number, -- studs
	bumpPitch: number, -- degrees
	bumpRoll: number,
	accelPitch: number, -- degrees per stud/s^2 of forward acceleration
	latRoll: number, -- degrees per stud/s^2 of lateral acceleration
	maxPitch: number,
	maxRoll: number,
	hz: number, -- body spring frequency
	damping: number,
	buffet: number, -- time-driven wobble (degrees), aircraft only
	bank: number, -- jets: gravity used for the coordinated bank (studs/s^2)
}

local PROFILES: { [string]: Profile } = {
	Buggy = { ground = true, height = 1.6, refSpeed = 40, bumpFreq = 0.42, heave = 0.12, bumpPitch = 0.9, bumpRoll = 0.8, accelPitch = 0.08, latRoll = 0.035, maxPitch = 3, maxRoll = 3.5, hz = 2.1, damping = 0.35, buffet = 0, bank = 0 },
	Tank = { ground = true, height = 1.8, refSpeed = 10, bumpFreq = 0.22, heave = 0.04, bumpPitch = 0.35, bumpRoll = 0.25, accelPitch = 0.25, latRoll = 0.12, maxPitch = 2, maxRoll = 1.5, hz = 1.1, damping = 0.5, buffet = 0, bank = 0 },
	SiegeCrawler = { ground = true, height = 3, refSpeed = 5, bumpFreq = 0.12, heave = 0.03, bumpPitch = 0.15, bumpRoll = 0.12, accelPitch = 0.3, latRoll = 0.2, maxPitch = 0.8, maxRoll = 0.6, hz = 0.8, damping = 0.6, buffet = 0, bank = 0 },
	Helicopter = { ground = false, height = 0, refSpeed = 60, bumpFreq = 0, heave = 0.35, bumpPitch = 0, bumpRoll = 0, accelPitch = -0.12, latRoll = 0.12, maxPitch = 4, maxRoll = 4, hz = 0.7, damping = 0.45, buffet = 1, bank = 0 },
	Jet = { ground = false, height = 0, refSpeed = 245, bumpFreq = 0, heave = 0.25, bumpPitch = 0, bumpRoll = 0, accelPitch = 0, latRoll = 0, maxPitch = 1.5, maxRoll = 25, hz = 0.9, damping = 0.7, buffet = 2.2, bank = 90 },
}

-- Recoil (pitch-rate impulse in degrees/s, heave-rate in studs/s) per attack.
local RECOIL: { [string]: { pitch: number, heave: number } } = {
	Shell = { pitch = 14, heave = 0.1 },
	BossCannon = { pitch = 5, heave = 0.1 },
	BossTurret = { pitch = 1.5, heave = 0 },
	BuggyBurst = { pitch = 2.5, heave = 0 },
	Rocket = { pitch = 4, heave = 0 },
	Bombs = { pitch = 3, heave = 1.2 },
}

export type State = {
	profile: Profile,
	pivot: CFrame, -- Root space -> roll/pitch centre
	seed: number,
	dist: number,
	lastVel: Vector3?,
	accel: Vector3,
	pitch: Spring,
	roll: Spring,
	heave: Spring,
	yaw: Spring,
	id: number?, -- EnemyId, for recoil kicks
}

local byId: { [number]: State } = {}

local function spring(hz: number, damping: number): Spring
	return { x = 0, v = 0, w = 2 * math.pi * hz, z = damping }
end

-- Semi-implicit Euler, sub-stepped so a long frame can't blow it up.
local function stepSpring(s: Spring, target: number, dt: number)
	local n = math.max(1, math.ceil(dt / (1 / 120)))
	local h = dt / n
	for _ = 1, n do
		local a = s.w * s.w * (target - s.x) - 2 * s.z * s.w * s.v
		s.v += a * h
		s.x += s.v * h
	end
end

local function noise(x: number, seed: number, channel: number): number
	return math.clamp(math.noise(x, seed, channel) * 2, -1, 1)
end

function Body.new(model: Model, root: BasePart, kind: string): State?
	local profile = PROFILES[kind]
	if not profile then
		return nil
	end
	local id = model:GetAttribute("EnemyId")
	local seed = (if type(id) == "number" then id else math.random(1, 999)) * 1.618
	local state: State = {
		profile = profile,
		pivot = root.PivotOffset * CFrame.new(0, profile.height, 0),
		seed = seed % 97,
		dist = 0,
		lastVel = nil,
		accel = Vector3.zero,
		pitch = spring(profile.hz, profile.damping),
		roll = spring(profile.hz * 0.9, profile.damping),
		heave = spring(profile.hz * 1.25, profile.damping),
		yaw = spring(profile.hz, 0.6),
		id = if type(id) == "number" then id else nil,
	}
	if type(id) == "number" then
		byId[id] = state
	end
	return state
end

-- Forgets a state whose track ended (EnemyMotion calls this).
function Body.drop(s: State?)
	if s and s.id and byId[s.id] == s then
		byId[s.id] = nil
	end
end

-- Returns the body offset in Root space for this frame.
function Body.update(s: State, dt: number, now: number, _pos: Vector3, rot: CFrame, vel: Vector3, _spin: Vector3): CFrame
	if dt <= 0 or Workspace:GetAttribute("BeautyShot") ~= nil then
		return CFrame.identity
	end
	local p = s.profile
	-- Level heading frame: the server already pitches and rolls the body
	-- (terrain, the jet's egress roll), and measuring acceleration against
	-- those tilted axes would leak a climb into "lateral" acceleration.
	local flat = Vector3.new(rot.LookVector.X, 0, rot.LookVector.Z)
	local look = if flat.Magnitude > 1e-3 then flat.Unit else Vector3.new(0, 0, -1)
	local left = Vector3.yAxis:Cross(look)
	local speed = vel.Magnitude
	-- Acceleration from the smoothed velocity, low-passed (~0.2 s).
	local last = s.lastVel or vel
	s.lastVel = vel
	local raw = (vel - last) / dt
	s.accel += (raw - s.accel) * (1 - math.exp(-dt / 0.2))
	local aFwd = s.accel:Dot(look)
	local aLeft = s.accel:Dot(left)
	local k = math.clamp(speed / p.refSpeed, 0, 1)
	s.dist += speed * dt

	local pitchT, rollT, heaveT, yawT = 0, 0, 0, 0
	if p.ground then
		local d = s.dist * p.bumpFreq
		heaveT = p.heave * k * noise(d, s.seed, 0.5)
		pitchT = p.bumpPitch * k * noise(d * 0.8, s.seed, 1.5) + math.clamp(p.accelPitch * aFwd, -p.maxPitch, p.maxPitch)
		rollT = p.bumpRoll * k * noise(d * 0.9, s.seed, 2.5) - math.clamp(p.latRoll * aLeft, -p.maxRoll, p.maxRoll)
	else
		local calm = 1 - 0.6 * k
		local t = now * (if p.bank > 0 then 0.35 else 0.3)
		pitchT = math.clamp(p.accelPitch * aFwd, -p.maxPitch, p.maxPitch) + p.buffet * 0.35 * calm * noise(t, s.seed, 1.5)
		rollT = p.buffet * calm * noise(t * 0.9, s.seed, 2.5)
		heaveT = p.heave * calm * noise(t * 0.8, s.seed, 0.5)
		yawT = p.buffet * 0.4 * calm * noise(t * 0.7, s.seed, 3.5)
		if p.bank > 0 then
			rollT += math.clamp(math.deg(math.atan2(aLeft, p.bank)), -p.maxRoll, p.maxRoll)
		else
			rollT += math.clamp(p.latRoll * aLeft, -p.maxRoll, p.maxRoll)
		end
	end
	stepSpring(s.pitch, pitchT, dt)
	stepSpring(s.roll, rollT, dt)
	stepSpring(s.heave, heaveT, dt)
	stepSpring(s.yaw, yawT, dt)
	local offset = CFrame.new(0, s.heave.x, 0) * CFrame.Angles(math.rad(s.pitch.x), math.rad(s.yaw.x), math.rad(s.roll.x))
	return s.pivot * offset * s.pivot:Inverse()
end

-- Kicks the body when its gun fires (EnemyFire events carry the enemy id).
local function onFire(p: any)
	if type(p) ~= "table" or type(p.id) ~= "number" then
		return
	end
	local s = byId[p.id]
	local r = RECOIL[p.attack]
	if s and r then
		s.pitch.v += r.pitch
		s.heave.v += r.heave
	end
end

function Body.start()
	local ok, GameState = pcall(require, script.Parent.GameState)
	if ok then
		GameState.onEvent("EnemyFire", onFire)
	end
end

return Body
