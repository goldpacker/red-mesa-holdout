--!strict
-- One paratrooper's descent (AD-2), on the HS-6 `Parachute` and the
-- skinned soldier (AirdropTrooperBody):
--   exit     at releaseT he steps off the opened ramp's lip with the
--            aircraft's speed, chin down, legs together;
--   streamer the static line pulls the deployment bag out: the Deploying
--            "squid" trails up toward the aircraft;
--   open     at openT (openPos) the canopy snaps open (blossom with a small
--            overshoot, a chute pop), he swings forward under it and the
--            swing dies away; a slow wind sway; he turns to face his lane;
--   flare    the sway has settled and he pulls the risers down: the sink
--            rate eases off (same endpoints) and the knees soften;
--   touch    feet on landPos exactly at landT: dust puff and a thud; the
--            canopy tips over downwind and collapses to the HS-6 mesh.
-- The body is hidden the moment the replicated enemy with this DropLoadId
-- appears (client/Airdrop), at the same place and time.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local AirdropPath = require(ReplicatedStorage.Shared.AirdropPath)
local Audio = require(script.Parent.AirdropAudio)
local Body = require(script.Parent.AirdropTrooperBody)
local Canopy = require(script.Parent.AirdropCanopy)
local Fx = require(script.Parent.AirdropFx)
local Motion = require(script.Parent.AirdropMotion)
local Style = require(script.Parent.AirdropStyle)

local Trooper = {}

local T = Style.Trooper

export type Load = {
	kind: string,
	data: AirdropPath.Load,
	sortie: AirdropPath.Sortie,
	model: Model,
	anchor: BasePart,
	canopy: Canopy.C?,
	body: Body.B,
	lip: Vector3, -- where he left the ramp (feet)
	v0: Vector3,
	aircraft: (number) -> Vector3, -- the ramp lip at time t (streamer target)
	heading: Vector3,
	seed: number,
	opened: boolean,
	touched: boolean,
	handed: boolean,
	retireAt: number?, -- no enemy seen in time: fading out since then
	fading: { BasePart },
	centre: Vector3,
	radius: number,
}

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include
groundParams.FilterDescendantsInstances = { Workspace.Terrain }

local function newAnchor(model: Model): Part
	local a = Instance.new("Part")
	a.Name = "Anchor"
	a.Size = Vector3.new(0.2, 0.2, 0.2)
	a.Transparency = 1
	a.Anchored = true
	a.CanCollide = false
	a.CanQuery = false
	a.CanTouch = false
	a.CastShadow = false
	a.Parent = model
	model.PrimaryPart = a
	return a
end

function Trooper.new(parent: Instance, sortie: AirdropPath.Sortie, l: AirdropPath.Load, lip: Vector3, v0: Vector3, aircraft: (number) -> Vector3): Load
	local model = Instance.new("Model")
	model.Name = "Load_" .. l.loadId
	model:SetAttribute("LoadId", l.loadId)
	model:SetAttribute("LoadKind", l.kind)
	model:SetAttribute("Airborne", true)
	local anchor = newAnchor(model)
	anchor.CFrame = CFrame.new(lip + Vector3.new(0, T.HARNESS_UP, 0))
	local canopy = Canopy.new("Parachute", model, anchor, CFrame.identity)
	local seed = l.loadId
	local body = Body.new(model, anchor, seed)
	model.Parent = parent
	return {
		kind = l.kind,
		data = l,
		sortie = sortie,
		model = model,
		anchor = anchor,
		canopy = canopy,
		body = body,
		lip = lip,
		v0 = v0,
		aircraft = aircraft,
		heading = Motion.flatUnit(AirdropPath.heading(sortie), Vector3.new(1, 0, 0)),
		seed = (seed * 1.618) % (math.pi * 2),
		opened = false,
		touched = false,
		handed = false,
		retireAt = nil,
		fading = {},
		centre = lip,
		radius = 26,
	}
end

-- The hanging load's frame (feet, facing) at t in the canopy phase, with
-- the opening swing and the wind sway (both settle out before touchdown).
local function canopyFrame(ld: Load, t: number): CFrame
	local l = ld.data
	local ref, u = Motion.canopy(ld.sortie, l, t, T.FLARE, T.FLARE_SHARP)
	local facing = Motion.turn(ld.heading, l.face, Style.smooth(u))
	local base = CFrame.lookAt(ref, ref + facing)
	local settle = Style.smooth((l.landT - t) / T.SWAY_SETTLE)
	local swing = Style.swing(t - l.openT, T.SWING_ANGLE, T.SWING_PERIOD, T.SWING_DECAY) * settle
	local wind = Style.downwind(t)
	local sway = T.SWAY * math.sin(2 * math.pi * t / T.SWAY_PERIOD + ld.seed) * settle
	local sway2 = T.SWAY * 0.5 * math.sin(2 * math.pi * t / (T.SWAY_PERIOD * 1.37) + ld.seed * 2) * settle
	-- Feet swing forward along the flight line (the canopy snatched them
	-- back first); the sway rocks across and along the wind.
	local axisA = Vector3.yAxis:Cross(ld.heading).Unit -- rotating about it moves feet along heading
	local axisB = Vector3.yAxis:Cross(wind).Unit
	local axisC = wind
	local rot = CFrame.fromAxisAngle(axisA, -swing) * CFrame.fromAxisAngle(axisB, -sway) * CFrame.fromAxisAngle(axisC, sway2)
	local canopyHeight = if ld.canopy then ld.canopy.height else 30
	local pivot = ref + Vector3.new(0, T.HARNESS_UP + canopyHeight * 0.75, 0)
	return CFrame.new(pivot) * rot * CFrame.new(-pivot) * base
end

-- Streamer frame (in the anchor's space): the Deploying mesh's +Y toward
-- the aircraft, stretching out as the bag pulls away.
local function streamerAttach(ld: Load, anchorCf: CFrame, t: number): CFrame
	local harness = anchorCf.Position
	local toward = ld.aircraft(t) - harness
	local up = if toward.Magnitude > 1 then toward.Unit else Vector3.yAxis
	local side = up:Cross(ld.heading)
	side = if side.Magnitude > 1e-3 then side.Unit else Vector3.xAxis
	local world = CFrame.fromMatrix(harness, side, up)
	return anchorCf:ToObjectSpace(world)
end

local function easeOutBack(k: number): number
	local c = 1.9
	k = math.clamp(k, 0, 1) - 1
	return 1 + (c + 1) * k * k * k + c * k * k
end

-- Poses the load while it is in the air (releaseT <= t < landT).
function Trooper.pose(ld: Load, t: number)
	local l = ld.data
	local anchorCf: CFrame
	local tuck, flare = 0, 0
	local view = Style.viewDistance(ld.anchor.Position)
	if t < l.openT then
		local fallT = math.max(l.openT - l.releaseT, 0.05)
		local s = math.clamp(t - l.releaseT, 0, fallT)
		local u = s / fallT
		local open = canopyFrame(ld, l.openT)
		local up = Vector3.new(0, T.HARNESS_UP, 0)
		local p1 = open:PointToWorldSpace(up)
		local v1 = ld.heading * 18 - Vector3.new(0, Motion.sinkRate(l) * 1.6, 0)
		local harness = Motion.hermite(ld.lip + up, ld.v0, p1, v1, fallT, s)
		-- Tumble forward off the ramp, then the canopy pulls him upright
		-- into the opening frame.
		local tumble = CFrame.lookAt(Vector3.zero, ld.heading) * CFrame.Angles(math.rad(-10 - 35 * u), 0, math.rad(8 * math.sin(u * 5 + ld.seed)))
		local rot = tumble:Lerp(open.Rotation, Style.smooth((u - 0.55) / 0.45))
		anchorCf = CFrame.new(harness) * rot
		tuck = 1 - Style.smooth((u - 0.6) / 0.4)
		local c = ld.canopy
		if c then
			if u >= T.STREAMER_AT then
				Canopy.show(c, "Deploying")
				local k = (u - T.STREAMER_AT) / (1 - T.STREAMER_AT)
				ld.anchor.CFrame = anchorCf
				Canopy.set(c, streamerAttach(ld, anchorCf, t), 0.55 + 0.45 * k, 0.35 + 0.65 * k)
			end
		end
	else
		local frame = canopyFrame(ld, t)
		anchorCf = frame * CFrame.new(0, T.HARNESS_UP, 0)
		local age = t - l.openT
		local c = ld.canopy
		if not ld.opened then
			ld.opened = true
			if c then
				Canopy.show(c, "Open")
			end
			Audio.playAt("ChutePop", anchorCf.Position, 0.8)
		end
		if c then
			if age < T.OPEN_TIME * 1.6 then
				local k = age / T.OPEN_TIME
				local sx = 0.5 + 0.5 * easeOutBack(k)
				local sy = 1.35 - 0.35 * Style.smooth(k)
				Canopy.set(c, CFrame.identity, sx, sy)
			elseif c.sx ~= 1 or c.sy ~= 1 then
				Canopy.set(c, CFrame.identity, 1, 1)
			end
		end
		flare = Style.smooth((t - (l.landT - 1.4)) / 0.9)
	end
	ld.anchor.CFrame = anchorCf
	ld.centre = anchorCf.Position + Vector3.new(0, 10, 0)
	Body.pose(ld.body, t, tuck, flare, view)
end

-- Ground frame at the landing spot: +Y the terrain normal, +Z downwind.
function Trooper.groundFrame(at: Vector3, downwind: Vector3): CFrame
	local hit = Workspace:Raycast(at + Vector3.new(0, 12, 0), Vector3.new(0, -30, 0), groundParams)
	local pos = if hit then hit.Position else at
	local n = if hit then hit.Normal else Vector3.yAxis
	local fwd = downwind - n * downwind:Dot(n)
	fwd = if fwd.Magnitude > 1e-3 then fwd.Unit else Vector3.zAxis
	-- CFrame whose +Z is `fwd` and +Y is `n`.
	local x = n:Cross(fwd).Unit
	return CFrame.fromMatrix(pos, x, n, fwd)
end

-- Touchdown at landT: feet on landPos, canopy collapses, dust and thud.
function Trooper.touchdown(ld: Load, t: number)
	if ld.touched then
		return
	end
	ld.touched = true
	local l = ld.data
	local facing = l.face
	ld.anchor.CFrame = CFrame.lookAt(l.landPos, l.landPos + facing) * CFrame.new(0, T.HARNESS_UP, 0)
	Body.pose(ld.body, t + 1, 0, 1, 0)
	local c = ld.canopy
	if c then
		Canopy.collapse(c, Trooper.groundFrame(l.landPos, Style.downwind(t)), t, T.COLLAPSE_TIME)
	end
	Fx.touchdown(l.landPos, "Infantry")
	Audio.playAt("LandingThud", l.landPos)
end

-- The replicated enemy appeared: the body goes, the canopy stays.
function Trooper.handOff(ld: Load)
	if ld.handed then
		return
	end
	ld.handed = true
	Body.hide(ld.body)
end

-- No replicated enemy in time (client/Airdrop's latency-aware grace): the
-- body fades out over Style.Handoff.RETIRE_FADE instead of vanishing.
function Trooper.retire(ld: Load, t: number)
	if ld.handed or ld.retireAt then
		return
	end
	ld.retireAt = t
	for _, p in ld.body.parts do
		if p.Transparency < 1 then
			table.insert(ld.fading, p)
		end
	end
end

-- After touchdown: returns true when everything has faded and can go.
function Trooper.stepGround(ld: Load, t: number): boolean
	local retireAt = ld.retireAt
	if retireAt and not ld.handed then
		local k = (t - retireAt) / Style.Handoff.RETIRE_FADE
		if k >= 1 then
			Trooper.handOff(ld)
		else
			for _, p in ld.fading do
				p.Transparency = math.clamp(k, 0, 1)
			end
		end
	end
	local c = ld.canopy
	if not c then
		return ld.handed
	end
	local G = Style.Ground
	return Canopy.stepGround(c, t, G.CANOPY_LINGER, G.FADE_TIME, G.SINK) and ld.handed
end

function Trooper.onGround(ld: Load): boolean
	return ld.canopy ~= nil and Canopy.onGround(ld.canopy :: Canopy.C)
end

function Trooper.expire(ld: Load, t: number)
	if ld.canopy then
		Canopy.expire(ld.canopy, t, Style.Ground.CANOPY_LINGER)
	end
end

function Trooper.hitParts(ld: Load): ({ BasePart }, { BasePart })
	local bodies: { BasePart } = {}
	for _, p in ld.body.parts do
		if p.Transparency < 1 then
			table.insert(bodies, p)
		end
	end
	local fabric: { BasePart } = {}
	if ld.canopy then
		Canopy.hitParts(ld.canopy, fabric)
	end
	return bodies, fabric
end

function Trooper.destroy(ld: Load)
	ld.model:Destroy()
end

return Trooper
