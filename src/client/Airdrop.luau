--!strict
-- Client airdrop presentation (AD-1): draws each sortie announced by the
-- server ("AirdropSortie", docs/ARCHITECTURE.md) from its timeline
-- (shared/AirdropPath): the transport crossing the basin, every load
-- leaving the ramp, falling free, descending under canopy and touching
-- down at landPos exactly at landT. The server spawns the real enemy at
-- that moment with attribute DropLoadId; when it replicates, the load's
-- visual is removed (hand-off) and its canopy collapses and fades.
--
-- Airborne loads are invincible because the server has nothing to hit. A
-- machine-gun round that meets one here shows "no effect": a deflect spark
-- and no hit marker (WeaponController.airborneHit hook). Rockets, missiles,
-- aim and effect raycasts pass through (every part is CanQuery = false).
-- Visuals: client/AirdropVisuals (placeholder art, swapped by AD-2).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local AirdropConfig = require(ReplicatedStorage.Shared.AirdropConfig)
local AirdropPath = require(ReplicatedStorage.Shared.AirdropPath)
local Effects = require(script.Parent.Effects)
local GameState = require(script.Parent.GameState)
local Sfx = require(script.Parent.Sfx)
local Visuals = require(script.Parent.AirdropVisuals)

local Airdrop = {}

type SortieState = {
	data: AirdropPath.Sortie,
	transport: Visuals.Transport?,
	endT: number,
	loads: { LoadState },
	flying: boolean,
}

-- "Stowed" (in the transport), "Air", "Landed" (collapsing), "Done".
type LoadState = {
	data: AirdropPath.Load,
	sortie: SortieState,
	visual: Visuals.Load?,
	state: string,
	landedAt: number,
	handed: boolean,
}

local sorties: { [number]: SortieState } = {}
-- DropLoadId -> the landed enemy model, once it has replicated.
local landed: { [number]: Model } = {}
local fxFolder: Folder? = nil

local hitParams = RaycastParams.new()
hitParams.FilterType = Enum.RaycastFilterType.Include
local lastPing = 0

local function folder(): Folder
	local f = fxFolder
	if f and f.Parent then
		return f
	end
	local existing = Workspace:FindFirstChild("AirdropFx")
	local made = if existing and existing:IsA("Folder") then existing else Instance.new("Folder")
	made.Name = "AirdropFx"
	made.Parent = Workspace
	fxFolder = made
	return made
end

local function isLoad(l: any): boolean
	return typeof(l) == "table"
		and typeof(l.loadId) == "number"
		and typeof(l.kind) == "string"
		and typeof(l.releaseT) == "number"
		and typeof(l.openT) == "number"
		and typeof(l.landT) == "number"
		and typeof(l.openPos) == "Vector3"
		and typeof(l.landPos) == "Vector3"
		and typeof(l.face) == "Vector3"
end

local function onSortie(p: any)
	if typeof(p) ~= "table" or typeof(p.id) ~= "number" or typeof(p.from) ~= "Vector3" or typeof(p.to) ~= "Vector3" then
		return
	end
	if typeof(p.speed) ~= "number" or p.speed <= 0 or typeof(p.t0) ~= "number" or typeof(p.loads) ~= "table" then
		return
	end
	local data = p :: AirdropPath.Sortie
	local s: SortieState = { data = data, transport = nil, endT = AirdropPath.endTime(data), loads = {}, flying = true }
	for _, l in p.loads do
		if isLoad(l) then
			table.insert(s.loads, { data = l, sortie = s, visual = nil, state = "Stowed", landedAt = 0, handed = false })
		end
	end
	sorties[data.id] = s
end

local function smooth(u: number): number
	return u * u * (3 - 2 * u)
end

-- Flat facing turned from `a` toward `b` by fraction u (shortest way).
local function turn(a: Vector3, b: Vector3, u: number): Vector3
	local ya = math.atan2(a.X, a.Z)
	local yb = math.atan2(b.X, b.Z)
	local d = (yb - ya + math.pi) % (math.pi * 2) - math.pi
	local y = ya + d * u
	return Vector3.new(math.sin(y), 0, math.cos(y))
end

local function recordHandOff(ls: LoadState, model: Model)
	local f = folder()
	local delay = Workspace:GetServerTimeNow() - ls.data.landT
	local root = model.PrimaryPart
	local offset = if root then AirdropPath.flat(root.Position, ls.data.landPos) else -1
	f:SetAttribute("Handoffs", ((f:GetAttribute("Handoffs") :: number?) or 0) + 1)
	f:SetAttribute("HandoffMaxDelay", math.max((f:GetAttribute("HandoffMaxDelay") :: number?) or -1e6, delay))
	f:SetAttribute("HandoffMaxOffset", math.max((f:GetAttribute("HandoffMaxOffset") :: number?) or 0, offset))
end

local function touchdown(ls: LoadState)
	local v = ls.visual
	if not v then
		return
	end
	ls.state = "Landed"
	ls.landedAt = os.clock()
	Visuals.touchdown(v, AirdropPath.heading(ls.sortie.data))
end

local function stepLoad(ls: LoadState, t: number)
	local l = ls.data
	if ls.state == "Stowed" then
		if t < l.releaseT then
			return
		end
		ls.visual = Visuals.load(folder(), l.kind, l.loadId)
		ls.state = "Air"
	end
	local v = ls.visual
	if not v then
		ls.state = "Done"
		return
	end
	if ls.state == "Air" then
		local pos, phase, u = AirdropPath.loadAt(ls.sortie.data, l, t)
		local heading = AirdropPath.heading(ls.sortie.data)
		local facing = if phase == "Canopy" then turn(heading, l.face, smooth(u)) elseif phase == "Landed" then l.face else heading
		Visuals.poseLoad(v, pos, facing, phase, u, t)
		if phase == "Landed" or landed[l.loadId] then
			touchdown(ls)
		end
		return
	end
	-- Landed: wait for the real enemy, then remove the load; the canopy
	-- collapses, lingers and fades either way.
	local age = os.clock() - ls.landedAt
	if not ls.handed then
		local model = landed[l.loadId]
		if model or age > AirdropConfig.HANDOFF_TIMEOUT then
			ls.handed = true
			if model then
				recordHandOff(ls, model)
			end
			Visuals.handOff(v)
		end
	end
	if Visuals.stepCollapse(v, age, AirdropConfig.CANOPY_LINGER) and ls.handed then
		Visuals.destroy(v)
		ls.visual = nil
		ls.state = "Done"
	end
end

local function step()
	if next(sorties) == nil then
		return
	end
	local t = Workspace:GetServerTimeNow()
	for id, s in sorties do
		if s.flying then
			if t > s.endT + 0.5 then
				if s.transport then
					Visuals.destroy(s.transport)
					s.transport = nil
				end
				s.flying = false
			elseif t >= s.data.t0 - 0.2 then
				local transport = s.transport or Visuals.transport(folder())
				s.transport = transport
				Visuals.poseTransport(transport, AirdropPath.transportFrame(s.data, t), t)
			end
		end
		local busy = s.flying
		for _, ls in s.loads do
			if ls.state ~= "Done" then
				stepLoad(ls, t)
				busy = busy or ls.state ~= "Done"
			end
		end
		if not busy then
			sorties[id] = nil
		end
	end
end

-- Drops loads still in the air (or stowed); with `everything`, landed
-- canopies and transports too.
local function clear(everything: boolean)
	for id, s in sorties do
		for _, ls in s.loads do
			local airborne = ls.state == "Stowed" or ls.state == "Air"
			if (airborne or everything) and ls.state ~= "Done" then
				if ls.visual then
					Visuals.destroy(ls.visual)
					ls.visual = nil
				end
				ls.state = "Done"
			end
		end
		if everything then
			if s.transport then
				Visuals.destroy(s.transport)
				s.transport = nil
			end
			sorties[id] = nil
		end
	end
	if everything then
		table.clear(landed)
	end
end

local function onClear(p: any)
	local reason = if typeof(p) == "table" then p.reason else nil
	-- A wave that ended normally lets its transports fly out.
	clear(reason ~= "Intermission" and reason ~= "Dismissed")
end

-- Ray-vs-sphere prefilter: does the ray reach the sphere within maxDist?
local function rayNearSphere(origin: Vector3, dir: Vector3, maxDist: number, centre: Vector3, radius: number): boolean
	local v = centre - origin
	local along = v:Dot(dir)
	if along < -radius or along - radius > maxDist then
		return false
	end
	return v:Dot(v) - along * along <= radius * radius
end

-- WeaponController hook: a machine-gun round from `origin` along unit
-- `dir` that would travel `maxDist` studs. If an airborne load or a
-- transport is in the way, shows the "no effect" deflect there and returns
-- that point (the tracer ends there, no impact on the ground); else nil.
function Airdrop.airborneHit(origin: Vector3, dir: Vector3, maxDist: number): Vector3?
	local candidates: { BasePart } = {}
	for _, s in sorties do
		local tr = s.transport
		if tr and rayNearSphere(origin, dir, maxDist, tr.root.Position, tr.radius) then
			table.move(tr.parts, 1, #tr.parts, #candidates + 1, candidates)
		end
		for _, ls in s.loads do
			local v = ls.visual
			if v and ls.state == "Air" then
				local centre = v.root.Position + Vector3.new(0, v.height * 0.5, 0)
				if rayNearSphere(origin, dir, maxDist, centre, v.radius) then
					local parts = Visuals.hitParts(v)
					table.move(parts, 1, #parts, #candidates + 1, candidates)
				end
			end
		end
	end
	if #candidates == 0 then
		return nil
	end
	-- Queryable for this one raycast only.
	for _, p in candidates do
		p.CanQuery = true
	end
	hitParams.FilterDescendantsInstances = candidates
	local result = Workspace:Raycast(origin, dir * maxDist, hitParams)
	for _, p in candidates do
		p.CanQuery = false
	end
	if not result then
		return nil
	end
	Effects.impact(result.Position, true, origin, "Metal")
	local f = folder()
	f:SetAttribute("Deflects", ((f:GetAttribute("Deflects") :: number?) or 0) + 1)
	local now = os.clock()
	if now - lastPing > 0.25 then
		lastPing = now
		Sfx.play("Ricochet", 0.3, 0.45)
	end
	return result.Position
end

-- QA: counts of what is on screen.
function Airdrop.debugState(): { [string]: number }
	local out = { sorties = 0, transports = 0, stowed = 0, air = 0, landed = 0 }
	for _, s in sorties do
		out.sorties += 1
		if s.transport then
			out.transports += 1
		end
		for _, ls in s.loads do
			if ls.state == "Stowed" then
				out.stowed += 1
			elseif ls.state == "Air" then
				out.air += 1
			elseif ls.state == "Landed" then
				out.landed += 1
			end
		end
	end
	return out
end

local function watchEnemies()
	local enemies = Workspace:WaitForChild("Enemies")
	local function added(child: Instance)
		local id = child:GetAttribute("DropLoadId")
		if typeof(id) == "number" and child:IsA("Model") then
			landed[id] = child
		end
	end
	for _, child in enemies:GetChildren() do
		added(child)
	end
	enemies.ChildAdded:Connect(added)
end

function Airdrop.start()
	folder()
	GameState.onEvent("AirdropSortie", onSortie)
	GameState.onEvent("AirdropClear", onClear)
	GameState.onChanged("Phase", function(phase)
		if phase == "Title" or phase == "WaveIntro" or phase == "Defeat" or phase == "Victory" then
			clear(true)
		end
	end)
	task.spawn(watchEnemies)
	local WeaponController = require(script.Parent.WeaponController) :: any
	WeaponController.airborneHit = Airdrop.airborneHit
	RunService:BindToRenderStep("RedMesaAirdrop", Enum.RenderPriority.Camera.Value + 2, step)
end

return Airdrop
