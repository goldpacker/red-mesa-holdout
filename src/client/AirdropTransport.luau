--!strict
-- The airdrop transport (AD-2) on the HS-6 `Transport` art
-- (docs/ASSET_CONTRACTS.md): flight path, bank, props, ramp, far LOD and
-- the engine drone. Client-only and untouchable. The game is daylight only
-- (GAME_SPEC §7.1): the asset's neon nav lamps show as authored, nothing
-- more.
--
-- Path: the server's straight line (AirdropSortie from -> to at `speed`,
-- at `from` at t0) is flown exactly during the drop run, from RUN_IN s
-- before the first release to RUN_OUT s after the last. Before the run the
-- aircraft comes in on an arc that rolls out onto the line; after it, it
-- breaks away on another arc and climbs. Both arcs bend away from the
-- outpost, so the aircraft never gets closer to the mesa than the line
-- (the server's clearance rule). Bank follows the turn: atan(v^2 / (R g)).
--
-- The whole model moves with one anchored part (Root, the fuselage); every
-- other part hangs on a Weld whose C0 animates the props, ramp and door.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AirdropPath = require(ReplicatedStorage.Shared.AirdropPath)
local AssetLibrary = require(ReplicatedStorage.Shared.AssetLibrary)
local Audio = require(script.Parent.AirdropAudio)
local Style = require(script.Parent.AirdropStyle)

local Transport = {}

local S = Style.Transport

export type Path = {
	sortie: AirdropPath.Sortie,
	h: Vector3, -- flat heading of the line
	side: Vector3, -- flat, perpendicular, away from the outpost
	tA: number, -- run start / end (server time)
	tB: number,
	entryArcT: number, -- seconds the entry / exit arcs last
	exitArcT: number,
	bank: number, -- bank angle inside the arcs
	seed: number,
}

type Prop = { weld: Weld, hub: CFrame, blades: CFrame, disc: BasePart, spin: number }
type Hinged = { weld: Weld, hinge: CFrame, part: CFrame, open: number }

export type T = {
	model: Model,
	root: BasePart,
	rootOffset: CFrame, -- model pivot -> Root part
	parts: { BasePart }, -- for the "no effect" test
	radius: number,
	path: Path,
	props: { Prop },
	ramp: Hinged?,
	door: Hinged?,
	lodParts: { [BasePart]: number }, -- full-detail parts -> their transparency
	hull: BasePart?,
	lod: boolean,
	drone: Sound?,
	rampOpening: boolean,
	pose: CFrame,
	velocity: Vector3,
}

-- The opened ramp's lip (ReleasePoint) in the model's frame (HS-6 contract:
-- closed at (0, -3.8, 37.25), hinge (0, -8.8, 26), opened 21.8 deg -> the
-- values HS-6 measured in Studio). Refined from the asset when it loads.
local lipLocal = Vector3.new(0, -8.34, 38.3)
local releaseInfo = false

local OUTPOST = Vector3.zero -- Config.TURRET_PIVOT, flat

local function flat(v: Vector3): Vector3
	return Vector3.new(v.X, 0, v.Z)
end

---------------------------------------------------------------------------
-- Path (pure: needs only the sortie)
---------------------------------------------------------------------------

function Transport.path(s: AirdropPath.Sortie): Path
	local h = flat(AirdropPath.heading(s))
	h = if h.Magnitude > 1e-3 then h.Unit else Vector3.new(1, 0, 0)
	local side = Vector3.new(-h.Z, 0, h.X)
	-- Closest point of the line to the outpost; side points away from it.
	local rel = flat(OUTPOST - s.from)
	local closest = flat(s.from) + h * rel:Dot(h)
	if side:Dot(closest - OUTPOST) < 0 then
		side = -side
	end
	local first, last = math.huge, -math.huge
	for _, l in s.loads do
		first = math.min(first, l.releaseT)
		last = math.max(last, l.releaseT)
	end
	if first == math.huge then
		first = s.t0 + AirdropPath.duration(s) * 0.5
		last = first
	end
	local radius = S.TURN_RADIUS
	return {
		sortie = s,
		h = h,
		side = side,
		tA = first - S.RUN_IN,
		tB = last + S.RUN_OUT,
		entryArcT = S.ENTRY_TURN * radius / s.speed,
		exitArcT = S.EXIT_TURN * radius / s.speed,
		bank = math.atan(s.speed * s.speed / (radius * S.GRAVITY)),
		seed = (s.id * 0.7548) % 1 * math.pi * 2,
	}
end

local function lineAt(p: Path, t: number): Vector3
	local s = p.sortie
	return s.from + p.h * (s.speed * (t - s.t0))
end

-- Position, flat direction of travel and bank weight (0..1) at time t.
local function track(p: Path, t: number): (Vector3, Vector3, number)
	local s = p.sortie
	local R = S.TURN_RADIUS
	if t < p.tA then
		local start = lineAt(p, p.tA)
		local d = s.speed * (p.tA - t)
		local arcLen = S.ENTRY_TURN * R
		local phi = math.min(d, arcLen) / R
		local pos = start - p.h * (R * math.sin(phi)) + p.side * (R * (1 - math.cos(phi)))
		local dir = p.h * math.cos(phi) - p.side * math.sin(phi)
		if d > arcLen then
			pos -= dir * (d - arcLen)
		end
		local arcStart = p.tA - p.entryArcT
		local w = Style.smooth((t - arcStart) / S.BANK_EASE) * Style.smooth((p.tA - t) / S.BANK_EASE)
		return pos, dir, w
	elseif t > p.tB then
		local start = lineAt(p, p.tB)
		local d = s.speed * (t - p.tB)
		local arcLen = S.EXIT_TURN * R
		local phi = math.min(d, arcLen) / R
		local pos = start + p.h * (R * math.sin(phi)) + p.side * (R * (1 - math.cos(phi)))
		local dir = p.h * math.cos(phi) + p.side * math.sin(phi)
		if d > arcLen then
			pos += dir * (d - arcLen)
		end
		local w = Style.smooth((t - p.tB) / S.BANK_EASE) * Style.smooth((p.tB + p.exitArcT - t) / S.BANK_EASE)
		return pos, dir, w
	end
	return lineAt(p, t), p.h, 0
end

-- The model pivot's frame at time t (nose -Z along the direction of travel).
function Transport.frameAt(p: Path, t: number): (CFrame, Vector3)
	local pos, dir, w = track(p, t)
	-- Climb out after the break-away starts.
	local c = math.max(0, t - p.tB - 1)
	local climb = S.CLIMB * c * c / (c + 2)
	local vy = S.CLIMB * (c * c + 4 * c) / ((c + 2) * (c + 2))
	local seed = p.seed
	local heave = S.WOBBLE_HEAVE * math.sin(t * 0.21 + seed)
	pos += Vector3.new(0, climb + heave, 0)
	local speed = p.sortie.speed
	local vel = dir * speed + Vector3.new(0, vy, 0)
	local look = vel.Unit
	-- Bank toward the turn centre (both arcs turn toward `side`).
	local lateral = p.side - look * p.side:Dot(look)
	lateral = if lateral.Magnitude > 1e-3 then lateral.Unit else p.side
	local bank = p.bank * w + S.WOBBLE_ROLL * math.sin(t * 0.37 + seed * 1.7)
	local up = (Vector3.yAxis + lateral * math.tan(bank)).Unit
	local cf = CFrame.lookAt(pos, pos + look, up) * CFrame.Angles(S.WOBBLE_PITCH * math.sin(t * 0.29 + seed * 2.3), 0, 0)
	return cf, vel
end

-- Where (and how fast) a load leaving the opened ramp at time t starts.
function Transport.releaseAt(p: Path, t: number): (Vector3, Vector3)
	local cf, vel = Transport.frameAt(p, t)
	return cf:PointToWorldSpace(lipLocal), vel
end

---------------------------------------------------------------------------
-- Model
---------------------------------------------------------------------------

local function weldTo(root: BasePart, part: BasePart): Weld
	local w = Instance.new("Weld")
	w.Name = "AirdropWeld"
	w.Part0 = root
	w.Part1 = part
	w.C0 = root.CFrame:ToObjectSpace(part.CFrame)
	w.C1 = CFrame.identity
	w.Parent = part
	return w
end

local function quiet(p: BasePart)
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Massless = true
end

-- Local (model-pivot) frame of a sub-model's WorldPivot.
local function subPivot(model: Model, name: string): (Model?, CFrame?)
	local sub = model:FindFirstChild(name)
	if sub and sub:IsA("Model") then
		return sub, model:GetPivot():ToObjectSpace(sub:GetPivot())
	end
	return nil, nil
end

local function learnLip(model: Model, hinge: CFrame?)
	if releaseInfo or not hinge then
		return
	end
	local rampModel = model:FindFirstChild("Ramp")
	local door = rampModel and rampModel:FindFirstChild("RampDoor")
	local att = door and door:FindFirstChild("ReleasePoint")
	if att and att:IsA("Attachment") then
		local closed = model:GetPivot():PointToObjectSpace(att.WorldPosition)
		local open = hinge * CFrame.Angles(math.rad(S.RAMP_OPEN_DEG), 0, 0) * hinge:Inverse()
		lipLocal = open:PointToWorldSpace(closed)
		releaseInfo = true
	end
end

-- A fallback silhouette when the asset is missing (never expected).
local function fallbackModel(): Model
	local model = Instance.new("Model")
	model.Name = "Transport"
	local root = Instance.new("Part")
	root.Name = "Root"
	root.Size = Vector3.new(13, 13, 100)
	root.Color = Color3.fromRGB(52, 55, 60)
	root.Material = Enum.Material.Metal
	root.Parent = model
	local wing = Instance.new("Part")
	wing.Name = "Wings"
	wing.Size = Vector3.new(140, 2, 15)
	wing.CFrame = CFrame.new(0, 6, 0)
	wing.Color = root.Color
	wing.Material = Enum.Material.Metal
	wing.Parent = model
	model.PrimaryPart = root
	return model
end

function Transport.new(parent: Instance, sortie: AirdropPath.Sortie, path: Path): T
	local asset = AssetLibrary.clone("Transport")
	local model: Model = if asset and asset:IsA("Model") then asset else fallbackModel()
	if asset and not asset:IsA("Model") then
		asset:Destroy()
	end
	model.Name = "Transport_" .. sortie.id
	local root = (model:FindFirstChild("Root") or model.PrimaryPart) :: BasePart
	model.PrimaryPart = root
	-- Asset space: pivot at the origin.
	model:PivotTo(CFrame.identity)
	local rootOffset = root.CFrame

	local parts: { BasePart } = {}
	local lodParts: { [BasePart]: number } = {}
	local props: { Prop } = {}
	local _, rampHinge = subPivot(model, "Ramp")
	local _, doorHinge = subPivot(model, "CargoDoor")
	learnLip(model, rampHinge)

	for _, d in model:GetDescendants() do
		if d:IsA("BaseScript") or d:IsA("Sound") or d:IsA("Light") or d:IsA("JointInstance") or d:IsA("WeldConstraint") then
			d:Destroy()
		end
	end
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			quiet(d)
			if d ~= root then
				d.Anchored = false
			end
			local name = d.Name
			local isLamp = name:find("Lamp") ~= nil
			local isDisc = name:match("^Disc%d") ~= nil
			if isLamp then
				-- Tiny neon nav lamps: left as authored.
			elseif name == "LODHull" or name == "FormationLights" then
				-- Shown by LOD / at night only.
			elseif not isDisc then
				lodParts[d] = d.Transparency
				table.insert(parts, d)
			end
		end
	end
	root.Anchored = true

	-- Welds (built in asset space, before the model moves).
	local rampWeld: Weld? = nil
	local doorWeld: Weld? = nil
	local rampPart: CFrame? = nil
	local doorPart: CFrame? = nil
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and d ~= root then
			local w = weldTo(root, d)
			if d.Name == "RampDoor" then
				rampWeld, rampPart = w, d.CFrame
			elseif d.Name == "CargoDoorPanel" then
				doorWeld, doorPart = w, d.CFrame
			end
		end
	end
	for k = 1, 4 do
		local sub, hub = subPivot(model, "Prop" .. k)
		local blades = sub and sub:FindFirstChild("Blades" .. k)
		local disc = sub and sub:FindFirstChild("Disc" .. k)
		if sub and hub and blades and blades:IsA("BasePart") and disc and disc:IsA("BasePart") then
			local w = blades:FindFirstChild("AirdropWeld") :: Weld
			disc.Transparency = S.DISC_TRANSPARENCY
			table.insert(props, {
				weld = w,
				hub = hub,
				blades = hub:ToObjectSpace(blades.CFrame),
				disc = disc,
				spin = k * 1.3,
			})
		end
	end

	local lod = model:FindFirstChild("LOD")
	local hull = lod and lod:FindFirstChild("LODHull")
	model:SetAttribute("Airborne", true)
	model:SetAttribute("SortieId", sortie.id)
	model.Parent = parent

	local t: T = {
		model = model,
		root = root,
		rootOffset = rootOffset,
		parts = parts,
		radius = 80,
		path = path,
		props = props,
		ramp = if rampWeld and rampHinge and rampPart then { weld = rampWeld, hinge = rampHinge, part = rampPart, open = 0 } else nil,
		door = if doorWeld and doorHinge and doorPart then { weld = doorWeld, hinge = doorHinge, part = doorPart, open = 0 } else nil,
		lodParts = lodParts,
		hull = if hull and hull:IsA("BasePart") then hull else nil,
		lod = false,
		drone = nil,
		rampOpening = false,
		pose = CFrame.identity,
		velocity = Vector3.zero,
	}
	t.drone = Audio.drone(root, sortie.id)
	return t
end

---------------------------------------------------------------------------
-- Per frame
---------------------------------------------------------------------------

local function setHinge(t: T, h: Hinged?, angle: number)
	if not h or math.abs(h.open - angle) < 1e-4 then
		return
	end
	h.open = angle
	local world = h.hinge * CFrame.Angles(angle, 0, 0) * h.hinge:Inverse() * h.part
	h.weld.C0 = t.rootOffset:ToObjectSpace(world)
end

-- Ramp/door opening 0..1 at time t, from the load release times.
local function rampAmount(p: Path, t: number): number
	local first, last = math.huge, -math.huge
	for _, l in p.sortie.loads do
		first = math.min(first, l.releaseT)
		last = math.max(last, l.releaseT)
	end
	if first == math.huge then
		return 0
	end
	local opening = Style.smooth((t - (first - S.RAMP_LEAD)) / S.RAMP_TIME)
	local closing = Style.smooth((t - (last + S.RAMP_CLOSE_AFTER)) / S.RAMP_TIME)
	return math.clamp(opening - closing, 0, 1)
end

local function setLod(t: T, far: boolean)
	if far == t.lod then
		return
	end
	t.lod = far
	for p, base in t.lodParts do
		p.Transparency = if far then 1 else base
	end
	if t.hull then
		t.hull.Transparency = if far then 0 else 1
	end
end

function Transport.pose(t: T, now: number)
	local cf, vel = Transport.frameAt(t.path, now)
	t.pose = cf
	t.velocity = vel
	t.root.CFrame = cf * t.rootOffset
	local open = rampAmount(t.path, now)
	if open > 0 and not t.rampOpening then
		t.rampOpening = true
		-- The clunk (1.72 s into the sound) lands as the ramp locks open.
		task.delay(math.max(0, S.RAMP_TIME - 1.72), Audio.playAt, "RampOpen", t.root)
	elseif open <= 0 then
		t.rampOpening = false
	end
	setHinge(t, t.ramp, math.rad(S.RAMP_OPEN_DEG) * open)
	setHinge(t, t.door, math.rad(S.DOOR_OPEN_DEG) * Style.smooth(open * 1.15))
	local far = Style.viewDistance(cf.Position)
	if far > S.LOD_IN then
		setLod(t, true)
	elseif far < S.LOD_OUT then
		setLod(t, false)
	end
	if not t.lod then
		for _, pr in t.props do
			local angle = now * S.PROP_RATE + pr.spin
			pr.weld.C0 = t.rootOffset:ToObjectSpace(pr.hub * CFrame.Angles(0, 0, angle) * pr.blades)
		end
	end
	-- Fade the drone in over the first seconds and out at the path end.
	local s = t.path.sortie
	local fade = math.min((now - s.t0) / 3, (AirdropPath.endTime(s) + S.END_GRACE - now) / 3)
	Audio.stepDrone(t.drone, cf.Position, vel, fade)
end

-- Server time after which the visual can go (far beyond the basin).
function Transport.endTime(t: T): number
	return AirdropPath.endTime(t.path.sortie) + S.END_GRACE
end

function Transport.destroy(t: T)
	if t.drone then
		t.drone:Destroy()
		t.drone = nil
	end
	t.model:Destroy()
end

return Transport
