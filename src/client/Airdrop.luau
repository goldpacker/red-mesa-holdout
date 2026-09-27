--!strict
-- Client airdrop presentation (AD-1 core, AD-2 presentation): draws each
-- sortie the server announces ("AirdropSortie", docs/ARCHITECTURE.md) from
-- its timeline (shared/AirdropPath): the transport crossing the basin
-- (AirdropTransport), every load leaving the ramp, streaming, opening,
-- swinging down and touching down at landPos exactly at landT
-- (AirdropTrooper / AirdropCargo), the HUD cues (AirdropHud) and sounds.
--
-- Hand-off: the server spawns the real enemy at landT with attribute
-- DropLoadId; the frame it replicates, the load's body is hidden (no pop:
-- both stand at landPos, same facing). A vehicle killed on its landing
-- tick reaches the client already in Workspace.Wrecks (its wreck takes
-- over the same way); a model the client never sees at all (added and
-- removed within one replication step) is covered by a short grace after
-- landT (AirdropStyle.HANDOFF_GRACE), after which the body is retired as
-- if handed off. Canopies and pallets stay behind a few seconds, capped.
--
-- Airborne loads are invincible because the server has nothing to hit. A
-- machine-gun round that meets one here shows "no effect" (AirdropFx:
-- spark + ping + ricochet off bodies, platforms and transports; a puff
-- through canopies), never a hit marker (WeaponController.airborneHit).
-- Everything lives under Workspace.AirdropFx, attribute/tag Airborne,
-- CanQuery false except during that one raycast.

local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local AirdropPath = require(ReplicatedStorage.Shared.AirdropPath)
local Cargo = require(script.Parent.AirdropCargo)
local Fx = require(script.Parent.AirdropFx)
local GameState = require(script.Parent.GameState)
local Hud = require(script.Parent.AirdropHud)
local Style = require(script.Parent.AirdropStyle)
local Transport = require(script.Parent.AirdropTransport)
local Trooper = require(script.Parent.AirdropTrooper)
local TrooperBody = require(script.Parent.AirdropTrooperBody)

local Airdrop = {}

type SortieState = {
	data: AirdropPath.Sortie,
	path: Transport.Path,
	transport: Transport.T?,
	endT: number,
	loads: { LoadState },
	flying: boolean,
	entered: boolean,
}

-- "Stowed" (in the transport), "Air", "Landed" (on the ground), "Done".
type LoadState = {
	data: AirdropPath.Load,
	sortie: SortieState,
	visual: any?, -- Trooper.Load | Cargo.Load
	mod: any?, -- the module drawing it
	state: string,
	landedAt: number,
	handed: boolean,
}

local sorties: { [number]: SortieState } = {}
-- DropLoadId -> the landed enemy model (in Enemies, or its wreck in
-- Wrecks), once it has replicated. Kept until the load is done, even if
-- the model leaves again, so an add + remove between two frames is still
-- seen.
local landed: { [number]: Model } = {}
local fxFolder: Folder? = nil
local sawCanopy = false

local hitParams = RaycastParams.new()
hitParams.FilterType = Enum.RaycastFilterType.Include

-- Studio QA A/B (docs/PERF_BUDGET.md): Workspace attribute AirdropFxOff =
-- true parks the whole folder out of the world and pauses the visuals.
local function fxOff(): boolean
	return Workspace:GetAttribute("AirdropFxOff") == true
end

local parked = false

local function folder(): Folder
	local f = fxFolder
	if f and (f.Parent or parked) then
		if fxOff() then
			if f.Parent then
				f.Parent = nil
			end
			parked = true
		elseif parked then
			f.Parent = Workspace
			parked = false
		end
		return f
	end
	local existing = Workspace:FindFirstChild("AirdropFx")
	local made = if existing and existing:IsA("Folder") then existing else Instance.new("Folder")
	made.Name = "AirdropFx"
	made.Parent = Workspace
	fxFolder = made
	return made
end

local function bump(name: string, by: number?)
	local f = folder()
	f:SetAttribute(name, ((f:GetAttribute(name) :: number?) or 0) + (by or 1))
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
	local clean: { AirdropPath.Load } = {}
	for _, l in p.loads do
		if isLoad(l) then
			table.insert(clean, l)
		end
	end
	data.loads = clean
	local path = Transport.path(data)
	local s: SortieState = {
		data = data,
		path = path,
		transport = nil,
		endT = AirdropPath.endTime(data) + Style.Transport.END_GRACE,
		loads = {},
		flying = true,
		entered = false,
	}
	for _, l in clean do
		table.insert(s.loads, { data = l, sortie = s, visual = nil, mod = nil, state = "Stowed", landedAt = 0, handed = false })
	end
	sorties[data.id] = s
end

local function recordHandOff(ls: LoadState, model: Model)
	local delay = Workspace:GetServerTimeNow() - ls.data.landT
	local root = model.PrimaryPart
	local offset = if root then AirdropPath.flat(root.Position, ls.data.landPos) else -1
	local f = folder()
	bump("Handoffs")
	f:SetAttribute("HandoffMaxDelay", math.max((f:GetAttribute("HandoffMaxDelay") :: number?) or -1e6, delay))
	f:SetAttribute("HandoffMaxOffset", math.max((f:GetAttribute("HandoffMaxOffset") :: number?) or 0, offset))
end

local function airborneCount(): number
	local n = 0
	for _, s in sorties do
		for _, ls in s.loads do
			if ls.state == "Air" and ls.visual then
				n += 1
			end
		end
	end
	return n
end

local function spawnVisual(ls: LoadState, t: number)
	local s = ls.sortie
	local l = ls.data
	if airborneCount() >= Style.Caps.LOADS_AIRBORNE then
		bump("CappedLoads")
		return
	end
	local lip, vel = Transport.releaseAt(s.path, l.releaseT)
	local path = s.path
	local function aircraft(time: number): Vector3
		return (Transport.releaseAt(path, time))
	end
	local mod: any = if l.kind == "Infantry" then Trooper else Cargo
	local ok, v = pcall(mod.new, folder(), s.data, l, lip, vel, aircraft)
	if ok and v then
		CollectionService:AddTag(v.model, "Airborne")
		ls.visual = v
		ls.mod = mod
	else
		warn("[RedMesa] airdrop load visual failed: " .. tostring(v))
	end
end

local function touchdown(ls: LoadState, t: number)
	ls.state = "Landed"
	ls.landedAt = t
	local v = ls.visual
	if v then
		ls.mod.touchdown(v, t)
	end
end

local function stepLoad(ls: LoadState, t: number)
	local l = ls.data
	if ls.state == "Stowed" then
		if t < l.releaseT then
			return
		end
		ls.state = "Air"
		spawnVisual(ls, t)
	end
	if ls.state == "Air" then
		if t >= l.landT or landed[l.loadId] then
			touchdown(ls, t)
		else
			local v = ls.visual
			if v then
				ls.mod.pose(v, t)
			end
			if not sawCanopy and t >= l.openT then
				sawCanopy = true
				Hud.canopy()
			end
			return
		end
	end
	-- Landed: hide the body the frame the real enemy (or its wreck)
	-- appears, or once the grace after landT has passed with nothing seen;
	-- canopies/pallets linger and fade either way.
	local v = ls.visual
	if not ls.handed then
		local model = landed[l.loadId]
		if model or t - l.landT > Style.HANDOFF_GRACE then
			ls.handed = true
			if model then
				recordHandOff(ls, model)
			else
				bump("HandoffsRetired")
			end
			if v then
				ls.mod.handOff(v)
			end
		end
	end
	if not v then
		if ls.handed then
			ls.state = "Done"
			landed[l.loadId] = nil
		end
		return
	end
	if ls.mod.stepGround(v, t) and ls.handed then
		ls.mod.destroy(v)
		ls.visual = nil
		ls.state = "Done"
		landed[l.loadId] = nil
	end
end

-- Collapsed canopies on the ground are capped: the oldest fade first.
local function capGround(t: number)
	local grounded: { LoadState } = {}
	for _, s in sorties do
		for _, ls in s.loads do
			if ls.state == "Landed" and ls.visual and ls.mod.onGround(ls.visual) then
				table.insert(grounded, ls)
			end
		end
	end
	local extra = #grounded - Style.Ground.MAX_COLLAPSED
	if extra <= 0 then
		return
	end
	table.sort(grounded, function(a, b)
		return a.landedAt < b.landedAt
	end)
	for i = 1, extra do
		grounded[i].mod.expire(grounded[i].visual, t)
	end
end

local lastCap = 0

local function stepTransport(s: SortieState, t: number)
	if not s.flying then
		return
	end
	if t > s.endT then
		if s.transport then
			Transport.destroy(s.transport)
			s.transport = nil
		end
		Hud.transport(s.data.id, nil, nil)
		s.flying = false
		return
	end
	if t < s.data.t0 - 0.2 then
		return
	end
	if not s.entered and t >= s.data.t0 then
		s.entered = true
		-- A sortie heard late (after its loads landed) gets no banner.
		local last = -math.huge
		for _, l in s.data.loads do
			last = math.max(last, l.landT)
		end
		if t < last then
			Hud.entered(s.data, t)
		end
	end
	local tr = s.transport
	if not tr then
		local count = 0
		for _, other in sorties do
			if other.transport then
				count += 1
			end
		end
		if count >= Style.Caps.TRANSPORTS then
			return
		end
		local ok, made = pcall(Transport.new, folder(), s.data, s.path)
		if not ok then
			warn("[RedMesa] airdrop transport failed: " .. tostring(made))
			s.flying = false
			return
		end
		tr = made
		CollectionService:AddTag(made.model, "Airborne")
		s.transport = made
	end
	local transport = tr :: Transport.T
	Transport.pose(transport, t)
	Hud.transport(s.data.id, transport.pose.Position, transport.velocity.Unit)
end

local function step()
	local t = Workspace:GetServerTimeNow()
	if parked or fxOff() then
		folder() -- parks, or brings the folder back once the switch clears
		if fxOff() then
			return
		end
	end
	if next(sorties) ~= nil then
		for id, s in sorties do
			stepTransport(s, t)
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
		if t - lastCap > 0.5 then
			lastCap = t
			capGround(t)
		end
	end
	Hud.step(t)
end

-- Drops loads still in the air (or stowed); with `everything`, landed
-- canopies and transports too.
local function clear(everything: boolean)
	for id, s in sorties do
		for _, ls in s.loads do
			local airborne = ls.state == "Stowed" or ls.state == "Air"
			if (airborne or everything) and ls.state ~= "Done" then
				if ls.visual then
					ls.mod.destroy(ls.visual)
					ls.visual = nil
				end
				ls.state = "Done"
			end
		end
		if everything then
			if s.transport then
				Transport.destroy(s.transport)
				s.transport = nil
			end
			sorties[id] = nil
		end
	end
	if everything then
		table.clear(landed)
		Hud.clear()
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

-- One Include raycast against `parts`, queryable for this call only.
local function castAt(origin: Vector3, dir: Vector3, maxDist: number, parts: { BasePart }): RaycastResult?
	if #parts == 0 then
		return nil
	end
	for _, p in parts do
		p.CanQuery = true
	end
	hitParams.FilterDescendantsInstances = parts
	local result = Workspace:Raycast(origin, dir * maxDist, hitParams)
	for _, p in parts do
		p.CanQuery = false
	end
	return result
end

-- WeaponController hook: a machine-gun round from `origin` along unit
-- `dir` that would travel `maxDist` studs. A load's body, platform or a
-- transport in the way: "no effect" deflect there, returns that point (the
-- tracer ends there, no impact on the ground). A canopy in the way: a
-- fabric puff and the round carries on (nil). Nothing: nil.
function Airdrop.airborneHit(origin: Vector3, dir: Vector3, maxDist: number): Vector3?
	local bodies: { BasePart } = {}
	local fabric: { BasePart } = {}
	for _, s in sorties do
		local tr = s.transport
		if tr and rayNearSphere(origin, dir, maxDist, tr.root.Position, tr.radius) then
			table.move(tr.parts, 1, #tr.parts, #bodies + 1, bodies)
		end
		for _, ls in s.loads do
			local v = ls.visual
			if v and ls.state == "Air" and rayNearSphere(origin, dir, maxDist, v.centre, v.radius) then
				local b, f = ls.mod.hitParts(v)
				table.move(b, 1, #b, #bodies + 1, bodies)
				table.move(f, 1, #f, #fabric + 1, fabric)
			end
		end
	end
	if #bodies == 0 and #fabric == 0 then
		return nil
	end
	local hard = castAt(origin, dir, maxDist, bodies)
	local soft = castAt(origin, dir, if hard then hard.Distance else maxDist, fabric)
	if soft then
		bump("PassThroughs")
		Fx.passThrough(soft.Position)
	end
	if not hard then
		return nil
	end
	bump("Deflects")
	Fx.deflect(hard.Position, origin, hard.Normal)
	return hard.Position
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

local function watchFolder(name: string)
	local f = Workspace:WaitForChild(name, 30)
	if not f then
		return
	end
	local function added(child: Instance)
		local id = child:GetAttribute("DropLoadId")
		if typeof(id) == "number" and child:IsA("Model") and not landed[id] then
			landed[id] = child
		end
	end
	for _, child in f:GetChildren() do
		added(child)
	end
	f.ChildAdded:Connect(added)
end

function Airdrop.start()
	folder()
	Hud.start()
	task.spawn(TrooperBody.prepare)
	GameState.onEvent("AirdropSortie", onSortie)
	GameState.onEvent("AirdropClear", onClear)
	GameState.onChanged("Phase", function(phase)
		if phase == "Title" or phase == "WaveIntro" or phase == "Defeat" or phase == "Victory" then
			clear(true)
		end
	end)
	task.spawn(watchFolder, "Enemies")
	-- A vehicle killed on its landing tick replicates straight into Wrecks.
	task.spawn(watchFolder, "Wrecks")
	local WeaponController = require(script.Parent.WeaponController) :: any
	WeaponController.airborneHit = Airdrop.airborneHit
	-- A failure in the visuals never breaks the game or floods the output:
	-- it is reported at most every 10 s and the next frame carries on.
	local lastWarn = -math.huge
	RunService:BindToRenderStep("RedMesaAirdrop", Enum.RenderPriority.Camera.Value + 2, function()
		local ok, err = pcall(step)
		if not ok and os.clock() - lastWarn > 10 then
			lastWarn = os.clock()
			warn("[RedMesa] airdrop visuals: " .. tostring(err))
		end
	end)
end

return Airdrop
