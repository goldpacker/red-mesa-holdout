--!strict
-- One vehicle's heavy drop (AD-2): the Buggy or Tank on the HS-6
-- `DropPlatform` under a cluster of `ParachuteCargo` canopies (2 for a
-- buggy, 4 for a tank, tilted 19 / 29 deg so the skirts don't overlap):
--   exit     the platform comes out at the opened ramp's lip, tail first,
--            already clear of the hold (the tank doesn't fit inside), and
--            tips off the lip;
--   streamer the cargo chutes stream up toward the aircraft;
--   open     at openT they blossom (slower than a trooper's), the load
--            swings on its long risers and settles; a slow wind sway;
--   touch    the platform thumps down (dust, a heavy thud) a moment before
--            landT and beds into the sand while the crush pads take the
--            rest: the vehicle is on the ground at landPos exactly at
--            landT, in the frame the server gives the landed vehicle
--            (Kit.groundFrame: pitched and rolled to the terrain);
--            slings and lashings drop, the canopies collapse downwind.
-- The vehicle is hidden when the replicated enemy appears (it drives off
-- the pallet); the pallet lingers a few seconds, then sinks and fades.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local AirdropPath = require(ReplicatedStorage.Shared.AirdropPath)
local AssetLibrary = require(ReplicatedStorage.Shared.AssetLibrary)
local EnemyConfig = require(ReplicatedStorage.Shared.EnemyConfig)
local Audio = require(script.Parent.AirdropAudio)
local Canopy = require(script.Parent.AirdropCanopy)
local Fx = require(script.Parent.AirdropFx)
local Motion = require(script.Parent.AirdropMotion)
local Style = require(script.Parent.AirdropStyle)
local Trooper = require(script.Parent.AirdropTrooper)

local Cargo = {}

local C = Style.Cargo

-- Kit.groundFrame parameters the server uses for each landed vehicle.
local FOOTPRINT = {
	Tank = { 10, 5, 0 },
	Buggy = { 4.5, 2.6, (EnemyConfig :: any).Buggy and (EnemyConfig :: any).Buggy.RIDE_HEIGHT or 0 },
}
local BED = 1.2 -- studs the pallet beds into the sand (pads crush the rest)

export type Load = {
	kind: string,
	data: AirdropPath.Load,
	sortie: AirdropPath.Sortie,
	model: Model,
	vehicleRoot: BasePart,
	palletRoot: BasePart,
	vehicle: { BasePart },
	platform: { BasePart },
	slings: BasePart?,
	rig: BasePart?,
	chutes: { Canopy.C },
	yaws: { number },
	lip: Vector3,
	v0: Vector3,
	aircraft: (number) -> Vector3,
	heading: Vector3,
	seed: number,
	opened: boolean,
	thumped: boolean,
	touched: boolean,
	handed: boolean,
	retireAt: number?, -- no enemy seen in time: fading out since then
	fading: { BasePart },
	final: CFrame?, -- the server's landed frame (vehicle pivot)
	palletFinal: CFrame?,
	groundedAt: number?,
	centre: Vector3,
	radius: number,
}

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include
groundParams.FilterDescendantsInstances = { Workspace.Terrain }

local function groundY(x: number, z: number): number
	local r = Workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -520, 0), groundParams)
	return if r then r.Position.Y else 0
end

-- Same maths as the server's Kit.groundFrame (EnemyTypes/Common/Kit).
local function groundFrame(pos: Vector3, heading: Vector3, halfLength: number, halfWidth: number, lift: number): CFrame
	local p2 = Vector2.new(pos.X, pos.Z)
	local h2 = Vector2.new(heading.X, heading.Z)
	local f = if h2.Magnitude > 1e-3 then h2.Unit else Vector2.new(0, -1)
	local r = Vector2.new(-f.Y, f.X)
	local front, back = p2 + f * halfLength, p2 - f * halfLength
	local left, right = p2 + r * halfWidth, p2 - r * halfWidth
	local yF, yB = groundY(front.X, front.Y), groundY(back.X, back.Y)
	local yL, yR = groundY(left.X, left.Y), groundY(right.X, right.Y)
	local centreY = math.max((yF + yB) / 2, (yL + yR) / 2, groundY(p2.X, p2.Y) - 0.5)
	local forward = Vector3.new(front.X - back.X, yF - yB, front.Y - back.Y).Unit
	local side = Vector3.new(left.X - right.X, yL - yR, left.Y - right.Y).Unit
	local up = side:Cross(forward)
	if up.Y < 0 then
		up = -up
	end
	local position = Vector3.new(p2.X, centreY + lift, p2.Y)
	return CFrame.lookAt(position, position + forward, up)
end

local function quiet(p: BasePart)
	p.Anchored = false
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Massless = true
end

local function anchorPart(model: Model, name: string): Part
	local a = Instance.new("Part")
	a.Name = name
	a.Size = Vector3.new(0.2, 0.2, 0.2)
	a.Transparency = 1
	a.Anchored = true
	a.CanCollide = false
	a.CanQuery = false
	a.CanTouch = false
	a.CastShadow = false
	a.Parent = model
	return a
end

local function weld(p0: BasePart, p1: BasePart, c0: CFrame)
	local w = Instance.new("Weld")
	w.Name = "AirdropWeld"
	w.Part0 = p0
	w.Part1 = p1
	w.C0 = c0
	w.Parent = p1
end

-- Every part of `model` (a clone placed with its pivot at the origin)
-- welded to `anchor` (which stands for that pivot).
local function hang(model: Model, anchor: BasePart): { BasePart }
	for _, d in model:GetDescendants() do
		if d:IsA("BaseScript") or d:IsA("Sound") or d:IsA("Light") or d:IsA("JointInstance") or d:IsA("WeldConstraint") then
			d:Destroy()
		end
	end
	local parts: { BasePart } = {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			quiet(d)
			weld(anchor, d, d.CFrame)
			table.insert(parts, d)
		end
	end
	return parts
end

local function vehicleModel(kind: string): Model
	local copy = AssetLibrary.clone(kind)
	if copy and copy:IsA("Model") then
		local root = copy:FindFirstChild("Root")
		if root and root:IsA("BasePart") and not copy.PrimaryPart then
			copy.PrimaryPart = root
		end
		copy:PivotTo(CFrame.identity)
		return copy
	end
	if copy then
		copy:Destroy()
	end
	local m = Instance.new("Model")
	local hull = Instance.new("Part")
	hull.Name = "Hull"
	hull.Size = if kind == "Tank" then Vector3.new(11, 6, 20) else Vector3.new(6, 4, 10)
	hull.CFrame = CFrame.new(0, hull.Size.Y / 2, 0)
	hull.Color = Color3.fromRGB(52, 55, 60)
	hull.Material = Enum.Material.Metal
	hull.Parent = m
	return m
end

function Cargo.new(parent: Instance, sortie: AirdropPath.Sortie, l: AirdropPath.Load, lip: Vector3, v0: Vector3, aircraft: (number) -> Vector3): Load
	local model = Instance.new("Model")
	model.Name = "Load_" .. l.loadId
	model:SetAttribute("LoadId", l.loadId)
	model:SetAttribute("LoadKind", l.kind)
	model:SetAttribute("Airborne", true)
	local vehicleRoot = anchorPart(model, "VehicleAnchor")
	local palletRoot = anchorPart(model, "PalletAnchor")
	model.PrimaryPart = vehicleRoot

	local vm = vehicleModel(l.kind)
	vm.Name = "Vehicle"
	local vehicle = hang(vm, vehicleRoot)
	vm.Parent = model

	local platform: { BasePart } = {}
	local slings: BasePart? = nil
	local rig: BasePart? = nil
	local apex = CFrame.new(0, 36, 0)
	local pm = AssetLibrary.clone("DropPlatform")
	if pm and pm:IsA("Model") then
		local proot = pm:FindFirstChild("Root")
		if proot and proot:IsA("BasePart") then
			pm.PrimaryPart = proot
		end
		pm:PivotTo(CFrame.identity)
		local unused = pm:FindFirstChild(if l.kind == "Tank" then "BuggyRig" else "TankRig")
		if unused then
			unused:Destroy()
		end
		local att = proot and proot:FindFirstChild("SlingApex")
		if att and att:IsA("Attachment") then
			apex = CFrame.new(att.WorldPosition)
		end
		platform = hang(pm, palletRoot)
		local s = pm:FindFirstChild("Slings")
		slings = if s and s:IsA("BasePart") then s else nil
		local usedRig = pm:FindFirstChild(if l.kind == "Tank" then "TankRig" else "BuggyRig")
		local rp = usedRig and usedRig:FindFirstChildWhichIsA("BasePart")
		rig = rp
		pm.Parent = model
	elseif pm then
		pm:Destroy()
	end

	local n = C.CHUTES[l.kind] or 2
	local chutes: { Canopy.C } = {}
	local yaws: { number } = {}
	for k = 1, n do
		local yaw = (k - 1) / n * math.pi * 2 + (if n == 2 then math.pi / 2 else math.pi / 4)
		local c = Canopy.new("ParachuteCargo", model, palletRoot, apex)
		if c then
			table.insert(chutes, c)
			table.insert(yaws, yaw)
		end
	end
	model.Parent = parent
	local heading = Motion.flatUnit(AirdropPath.heading(sortie), Vector3.new(1, 0, 0))
	local ld: Load = {
		kind = l.kind,
		data = l,
		sortie = sortie,
		model = model,
		vehicleRoot = vehicleRoot,
		palletRoot = palletRoot,
		vehicle = vehicle,
		platform = platform,
		slings = slings,
		rig = rig,
		chutes = chutes,
		yaws = yaws,
		lip = lip,
		v0 = v0,
		aircraft = aircraft,
		heading = heading,
		seed = (l.loadId * 1.618) % (math.pi * 2),
		opened = false,
		thumped = false,
		touched = false,
		handed = false,
		retireAt = nil,
		fading = {},
		final = nil,
		palletFinal = nil,
		groundedAt = nil,
		centre = lip,
		radius = 60,
	}
	return ld
end

-- Apex attach for chute k: open cluster (tilted out), or streaming up
-- toward the aircraft (`up` in the pallet's frame), blended by `open`.
local function chuteAttach(ld: Load, k: number, apexPos: Vector3, upLocal: Vector3, open: number): CFrame
	local tilt = (C.TILT[ld.kind] or math.rad(20)) * (0.25 + 0.75 * open)
	local cluster = CFrame.new(apexPos) * CFrame.Angles(0, ld.yaws[k], 0) * CFrame.Angles(tilt, 0, 0)
	if open >= 1 then
		return cluster
	end
	-- Streaming: +Y along upLocal, fanned a little by the same yaw.
	local side = upLocal:Cross(Vector3.zAxis)
	side = if side.Magnitude > 1e-3 then side.Unit else Vector3.xAxis
	local stream = CFrame.fromMatrix(apexPos, side, upLocal) * CFrame.Angles(0, ld.yaws[k], 0) * CFrame.Angles(math.rad(5), 0, 0)
	return stream:Lerp(cluster, open)
end

-- The hanging load's vehicle-pivot frame in the canopy phase (swing + sway
-- about the cluster's centre of pressure; settled before touchdown).
local function canopyFrame(ld: Load, t: number): CFrame
	local l = ld.data
	local ref, u = Motion.canopy(ld.sortie, l, t)
	local facing = Motion.turn(ld.heading, l.face, Style.smooth(u))
	local base = CFrame.lookAt(ref, ref + facing)
	local settle = Style.smooth((l.landT - t) / C.SWAY_SETTLE)
	local swing = Style.swing(t - l.openT, C.SWING_ANGLE, C.SWING_PERIOD, C.SWING_DECAY) * settle
	local wind = Style.downwind(t)
	local sway = C.SWAY * math.sin(2 * math.pi * t / C.SWAY_PERIOD + ld.seed) * settle
	local axisA = Vector3.yAxis:Cross(ld.heading).Unit
	local axisB = Vector3.yAxis:Cross(wind).Unit
	local rot = CFrame.fromAxisAngle(axisA, -swing) * CFrame.fromAxisAngle(axisB, -sway)
	local pivot = ref + Vector3.new(0, 36 + 50, 0)
	local frame = CFrame.new(pivot) * rot * CFrame.new(-pivot) * base
	-- Last moments: settle into the frame the server gives the landed
	-- vehicle (terrain pitch/roll; within a stud of the timeline point).
	local final = ld.final
	if final then
		local k = Style.smooth((t - (l.landT - 0.45)) / 0.45)
		if k > 0 then
			local target = final * CFrame.new(0, ref.Y - l.landPos.Y, 0)
			frame = frame:Lerp(target, k)
		end
	end
	return frame
end

local function place(ld: Load, vehicleCf: CFrame, palletCf: CFrame)
	ld.vehicleRoot.CFrame = vehicleCf
	ld.palletRoot.CFrame = palletCf
	ld.centre = palletCf.Position + Vector3.new(0, 40, 0)
end

function Cargo.pose(ld: Load, t: number)
	local l = ld.data
	local pad = Vector3.new(0, C.PAD_HEIGHT, 0)
	if not ld.final and t > l.landT - 1.5 then
		local fp = FOOTPRINT[ld.kind] or FOOTPRINT.Tank
		ld.final = groundFrame(l.landPos, l.face, fp[1], fp[2], fp[3])
	end
	if t < l.openT then
		local fallT = math.max(l.openT - l.releaseT, 0.05)
		local s = math.clamp(t - l.releaseT, 0, fallT)
		local u = s / fallT
		local open = canopyFrame(ld, l.openT)
		-- Out tail first: the platform's nose leaves the lip at releaseT.
		local start = ld.lip - ld.heading * 15 + pad
		local v1 = ld.heading * 14 - Vector3.new(0, Motion.sinkRate(l) * 1.4, 0)
		local pos = Motion.hermite(start, ld.v0, open.Position, v1, fallT, s)
		local tip = math.rad(C.TIP_DEG) * math.sin(math.min(u * 1.6, 1) * math.pi * 0.5)
		local level = CFrame.lookAt(Vector3.zero, ld.heading) * CFrame.Angles(tip, 0, 0)
		local rot = level:Lerp(open.Rotation, Style.smooth((u - 0.5) / 0.5))
		local cf = CFrame.new(pos) * rot
		place(ld, cf, cf * CFrame.new(-pad))
		if u >= 0.25 then
			local apexWorld = ld.palletRoot.CFrame:PointToWorldSpace(Vector3.new(0, 36, 0))
			local toward = ld.aircraft(t) - apexWorld
			local upLocal = ld.palletRoot.CFrame:VectorToObjectSpace(if toward.Magnitude > 1 then toward.Unit else Vector3.yAxis)
			local k = (u - 0.25) / 0.75
			for i, c in ld.chutes do
				Canopy.show(c, "Deploying")
				Canopy.set(c, chuteAttach(ld, i, Vector3.new(0, 36, 0), upLocal, 0), 0.5 + 0.5 * k, 0.35 + 0.65 * k)
			end
		end
	else
		local cf = canopyFrame(ld, t)
		local palletCf = cf * CFrame.new(-pad)
		-- The pallet stops when it has bedded into the sand.
		local floor = (if ld.final then (ld.final :: CFrame).Position.Y else l.landPos.Y) - BED
		local base = palletCf.Position.Y
		if base < floor then
			palletCf = palletCf + Vector3.new(0, floor - base, 0)
		end
		if not ld.thumped and base <= floor + BED then
			ld.thumped = true
			Fx.touchdown(Vector3.new(l.landPos.X, floor + BED, l.landPos.Z), ld.kind)
			Audio.playAt("PlatformThud", l.landPos)
		end
		local age = t - l.openT
		if not ld.opened then
			ld.opened = true
			for _, c in ld.chutes do
				Canopy.show(c, "Open")
			end
			Audio.playAt("ChutePop", cf.Position + Vector3.new(0, 60, 0), 1.1)
		end
		local k = math.clamp(age / C.OPEN_TIME, 0, 1)
		local sx = 0.45 + 0.55 * (1 - (1 - k) ^ 3)
		local sy = 1.3 - 0.3 * Style.smooth(k)
		local blend = Style.smooth(k * 1.4)
		for i, c in ld.chutes do
			if age < C.OPEN_TIME * 1.5 or c.sx ~= 1 then
				local attach = if blend >= 1 then chuteAttach(ld, i, Vector3.new(0, 36, 0), Vector3.yAxis, 1) else chuteAttach(ld, i, Vector3.new(0, 36, 0), Vector3.yAxis, blend)
				Canopy.set(c, attach, if k >= 1 then 1 else sx, if k >= 1 then 1 else sy)
			end
		end
		place(ld, cf, palletCf)
	end
end

-- Touchdown at landT: the vehicle stands on landPos in the server's frame;
-- slings and lashings drop; the canopies collapse downwind of the pallet.
function Cargo.touchdown(ld: Load, t: number)
	if ld.touched then
		return
	end
	ld.touched = true
	local l = ld.data
	local fp = FOOTPRINT[ld.kind] or FOOTPRINT.Tank
	local final = ld.final or groundFrame(l.landPos, l.face, fp[1], fp[2], fp[3])
	ld.final = final
	-- Bedded: its base BED below the ground under the vehicle (the pads,
	-- hidden with the lashings, took the rest of PAD_HEIGHT).
	local pallet = final * CFrame.new(0, -BED, 0)
	ld.palletFinal = pallet
	place(ld, final, pallet)
	if not ld.thumped then
		ld.thumped = true
		Fx.touchdown(final.Position, ld.kind)
		Audio.playAt("PlatformThud", final.Position)
	end
	if ld.slings then
		ld.slings.Transparency = 1
	end
	if ld.rig then
		ld.rig.Transparency = 1
	end
	local down = Style.downwind(t)
	local across = Vector3.yAxis:Cross(down).Unit
	for i, c in ld.chutes do
		-- Spread across the wind so the collapsed canopies lie side by side.
		local offset = (i - (#ld.chutes + 1) / 2) * (if ld.kind == "Tank" then 17 else 20)
		local spot = final.Position + across * offset + down * 10
		local dir = (down + across * offset * 0.012).Unit
		Canopy.collapse(c, Trooper.groundFrame(spot, dir), t, C.COLLAPSE_TIME * (0.9 + 0.08 * i))
	end
	ld.groundedAt = t
end

function Cargo.handOff(ld: Load)
	if ld.handed then
		return
	end
	ld.handed = true
	for _, p in ld.vehicle do
		p.Transparency = 1
	end
end

-- No replicated enemy in time (client/Airdrop's latency-aware grace): the
-- vehicle fades out over Style.Handoff.RETIRE_FADE instead of vanishing.
function Cargo.retire(ld: Load, t: number)
	if ld.handed or ld.retireAt then
		return
	end
	ld.retireAt = t
	for _, p in ld.vehicle do
		if p.Transparency < 1 then
			table.insert(ld.fading, p)
		end
	end
end

-- After touchdown: canopies lie, linger and fade; the pallet lingers,
-- then sinks and fades. True when everything is gone.
function Cargo.stepGround(ld: Load, t: number): boolean
	local retireAt = ld.retireAt
	if retireAt and not ld.handed then
		local k = (t - retireAt) / Style.Handoff.RETIRE_FADE
		if k >= 1 then
			Cargo.handOff(ld)
		else
			for _, p in ld.fading do
				p.Transparency = math.clamp(k, 0, 1)
			end
		end
	end
	local G = Style.Ground
	local done = ld.handed
	for _, c in ld.chutes do
		if not Canopy.stepGround(c, t, G.CANOPY_LINGER, G.FADE_TIME, G.SINK) then
			done = false
		end
	end
	local age = t - (ld.groundedAt or t)
	local k = math.clamp((age - C.PALLET_LINGER) / G.FADE_TIME, 0, 1)
	if k > 0 and ld.palletFinal then
		ld.palletRoot.CFrame = (ld.palletFinal :: CFrame) * CFrame.new(0, -1.5 * k, 0)
		for _, p in ld.platform do
			if p ~= ld.slings and p ~= ld.rig then
				p.Transparency = k
			end
		end
	end
	return done and k >= 1
end

function Cargo.onGround(ld: Load): boolean
	return ld.touched
end

function Cargo.expire(ld: Load, t: number)
	for _, c in ld.chutes do
		Canopy.expire(c, t, Style.Ground.CANOPY_LINGER)
	end
end

function Cargo.hitParts(ld: Load): ({ BasePart }, { BasePart })
	local bodies: { BasePart } = {}
	for _, p in ld.vehicle do
		if p.Transparency < 1 then
			table.insert(bodies, p)
		end
	end
	for _, p in ld.platform do
		if p.Transparency < 1 and p ~= ld.slings then
			table.insert(bodies, p)
		end
	end
	local fabric: { BasePart } = {}
	for _, c in ld.chutes do
		Canopy.hitParts(c, fabric)
	end
	return bodies, fabric
end

function Cargo.destroy(ld: Load)
	ld.model:Destroy()
end

return Cargo
