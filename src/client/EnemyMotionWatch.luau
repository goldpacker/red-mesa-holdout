--!strict
-- Which enemies EnemyMotion may smooth (LOOK-3B), kept current from events
-- instead of a periodic re-scan: an idle enemy costs nothing.
--
-- The rules (unchanged from LOOK-3):
--   - Root is the model's PrimaryPart when it is called "Root", else its
--     child (or descendant) "Root", and it must be anchored: the server
--     moves the whole enemy by setting that one CFrame (EnemyTypes/Common/
--     Rig, Infantry).
--   - Any other anchored part is judged on its own:
--       decorative (CanQuery = false): ignored. Client-side extras their
--         owners re-pose from the drawn model every frame, e.g. InfantryRig's
--         LampGlow (created when a helmet lamp turns on at dusk/night); a
--         detached piece on its way to Wrecks is also no-query.
--       a hit volume (CanQuery = true): the server places it on its own
--         (TestDummyAir's Wing; a weak point mid-detach). Moving Root alone
--         would pull the drawn model off that hit box, so the model is not
--         smoothed while such a part is there.
--
-- How it stays current:
--   - A model is scanned once (GetDescendants) on its first drain after it
--     enters Workspace.Enemies. Every BasePart gets Anchored/CanQuery change
--     signals; the model gets DescendantAdded/Removing, PrimaryPart and the
--     Kind attribute; the Root also its Name.
--   - A signal only marks that part (or the root lookup) dirty and queues
--     the model. `drain`, run first thing in EnemyMotion's render step,
--     re-judges just the dirty parts from their current state and hands the
--     verdict to EnemyMotion. Judging state, not events, one frame later
--     means a transient inside one replication batch (Kit.detach anchors a
--     weak point and moves it to Wrecks in the same server step) never
--     releases a model, whichever SignalBehavior the place uses.
--   - A drain spends at most DRAIN_BUDGET per frame (always at least one
--     model); the rest stays queued for the next frame.
--   - Failures stay contained: each model is judged under its own pcall, so
--     one bad model can't stop the render step or strand the models queued
--     behind it. A model that fails is re-scanned from scratch on the next
--     frame, up to MAX_STRIKES times, then left unsmoothed while in play.
--     Warnings name the model and are rate-limited (WARN_EVERY). If the
--     drain itself ever failed, every watched model is re-queued.

local Probe = require(script.Parent.EnemyMotionProbe)

local Watch = {}

local NONE, DECOR, BLOCK = 0, 1, 2
local DRAIN_BUDGET = 0.0005 -- s per frame
local MAX_PASSES = 4 -- root re-resolves per refresh (a guard; 2 is the most seen)
local MAX_STRIKES = 3 -- failed judgements before a model is given up on
local WARN_EVERY = 5 -- s between warnings

type Entry = {
	model: Model,
	scanned: boolean,
	queued: boolean,
	root: BasePart?,
	rootDirty: boolean,
	rootName: RBXScriptConnection?,
	anchoredConn: { [BasePart]: RBXScriptConnection },
	queryConn: { [BasePart]: RBXScriptConnection },
	class: { [BasePart]: number }, -- DECOR or BLOCK; absent = neither
	decor: number,
	block: number,
	dirty: { [BasePart]: boolean },
	spare: { [BasePart]: boolean },
	conns: { RBXScriptConnection },
}

-- `apply(model, root, ignored)`: root is nil while the model can't be
-- smoothed; ignored counts its decorative anchored parts.
export type Apply = (Model, BasePart?, number) -> ()

local entries: { [Model]: Entry } = {}
local queue: { Entry } = {}
local spareQueue: { Entry } = {}
local strikes: { [Model]: number } = {}
local timing = Probe.enabled -- handlers time themselves in Studio only
local lastWarn = -math.huge
local unreported = 0

local function enqueue(e: Entry)
	if not e.queued then
		e.queued = true
		table.insert(queue, e)
	end
end

local function classOf(e: Entry, p: BasePart): number
	if p == e.root or not p.Anchored then
		return NONE
	end
	return if p.CanQuery then BLOCK else DECOR
end

local function setClass(e: Entry, p: BasePart, c: number)
	local old = e.class[p] or NONE
	if old == c then
		return
	end
	if old == DECOR then
		e.decor -= 1
	elseif old == BLOCK then
		e.block -= 1
	end
	if c == DECOR then
		e.decor += 1
	elseif c == BLOCK then
		e.block += 1
	end
	e.class[p] = if c == NONE then nil else c
end

local function connectPart(e: Entry, p: BasePart)
	local function changed()
		local t0 = if timing then os.clock() else 0
		e.dirty[p] = true
		enqueue(e)
		if timing then
			Probe.work(os.clock() - t0)
		end
	end
	e.anchoredConn[p] = p:GetPropertyChangedSignal("Anchored"):Connect(changed)
	e.queryConn[p] = p:GetPropertyChangedSignal("CanQuery"):Connect(changed)
end

local function dropPart(e: Entry, p: BasePart)
	local a, q = e.anchoredConn[p], e.queryConn[p]
	if a then
		a:Disconnect()
		e.anchoredConn[p] = nil
	end
	if q then
		q:Disconnect()
		e.queryConn[p] = nil
	end
	setClass(e, p, NONE)
end

-- Re-judges one part from its current state.
local function syncPart(e: Entry, p: BasePart)
	if p:IsDescendantOf(e.model) then
		if not e.anchoredConn[p] then
			connectPart(e, p)
		end
		setClass(e, p, classOf(e, p))
	else
		dropPart(e, p)
		if p == e.root then
			e.rootDirty = true
		end
	end
end

local function resolveRoot(e: Entry)
	e.rootDirty = false
	local model = e.model
	local found: Instance? = model.PrimaryPart
	if not (found and found.Name == "Root") then
		found = model:FindFirstChild("Root") or model:FindFirstChild("Root", true)
	end
	local root = if found and found:IsA("BasePart") then found else nil
	if root == e.root then
		return
	end
	local old = e.root
	e.root = root
	-- The old root is judged as an ordinary part now, the new one isn't.
	if old then
		e.dirty[old] = true
	end
	if root then
		e.dirty[root] = true
		-- Watch the Root's name (renamed away = no longer the Root). With no
		-- Root found, keep watching the last one so a rename back is seen.
		if e.rootName then
			e.rootName:Disconnect()
		end
		e.rootName = root:GetPropertyChangedSignal("Name"):Connect(function()
			e.rootDirty = true
			enqueue(e)
		end)
	end
end

local function scan(e: Entry)
	e.scanned = true
	local model = e.model
	resolveRoot(e)
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			connectPart(e, d)
			setClass(e, d, classOf(e, d))
		end
	end
	local function touched(d: Instance)
		local t0 = if timing then os.clock() else 0
		if d:IsA("BasePart") then
			e.dirty[d] = true
			enqueue(e)
		end
		if d.Name == "Root" then
			e.rootDirty = true
			enqueue(e)
		end
		if timing then
			Probe.work(os.clock() - t0)
		end
	end
	local function requeue()
		e.rootDirty = true
		enqueue(e)
	end
	table.insert(e.conns, model.DescendantAdded:Connect(touched))
	table.insert(e.conns, model.DescendantRemoving:Connect(touched))
	table.insert(e.conns, model:GetPropertyChangedSignal("PrimaryPart"):Connect(requeue))
	table.insert(e.conns, model:GetAttributeChangedSignal("Kind"):Connect(function()
		enqueue(e)
	end))
end

local function refresh(e: Entry)
	if not e.scanned then
		scan(e)
	end
	for _ = 1, MAX_PASSES do
		if e.rootDirty then
			resolveRoot(e)
		end
		if next(e.dirty) == nil then
			break
		end
		local dirty = e.dirty
		e.dirty = e.spare
		e.spare = dirty
		for p in dirty do
			syncPart(e, p)
		end
		table.clear(dirty)
	end
	-- Still unsettled after MAX_PASSES: finish on the next frame rather
	-- than keep a stale verdict until some other event.
	if e.rootDirty or next(e.dirty) ~= nil then
		enqueue(e)
	end
end

local function verdict(e: Entry): BasePart?
	local root = e.root
	if root and root.Anchored and e.block == 0 then
		return root
	end
	return nil
end

-- Starts watching a model that entered Workspace.Enemies (judged on the
-- next drain).
function Watch.add(model: Model)
	if entries[model] then
		return
	end
	local e: Entry = {
		model = model,
		scanned = false,
		queued = false,
		root = nil,
		rootDirty = false,
		rootName = nil,
		anchoredConn = {},
		queryConn = {},
		class = {},
		decor = 0,
		block = 0,
		dirty = {},
		spare = {},
		conns = {},
	}
	entries[model] = e
	enqueue(e)
end

local function unwatch(e: Entry)
	if entries[e.model] == e then
		entries[e.model] = nil
	end
	for _, c in e.conns do
		c:Disconnect()
	end
	for _, c in e.anchoredConn do
		c:Disconnect()
	end
	for _, c in e.queryConn do
		c:Disconnect()
	end
	if e.rootName then
		e.rootName:Disconnect()
	end
	table.clear(e.conns)
	table.clear(e.anchoredConn)
	table.clear(e.queryConn)
	table.clear(e.class)
	table.clear(e.dirty)
end

-- Stops watching (the model left Workspace.Enemies).
function Watch.remove(model: Model)
	strikes[model] = nil
	local e = entries[model]
	if e then
		unwatch(e)
	end
end

local function describe(model: Model?): string
	if not model then
		return "the queue"
	end
	local kind, id = model:GetAttribute("Kind"), model:GetAttribute("EnemyId")
	return string.format("%s#%s (%s)", tostring(kind), tostring(id), model:GetFullName())
end

-- One warning per WARN_EVERY at most; the next one says how many were held.
-- The message is built before the slot is taken, so a failure while naming
-- the model can't silence the warning that follows it.
local function report(model: Model?, err: any, action: string)
	local now = os.clock()
	if now - lastWarn < WARN_EVERY then
		unreported += 1
		return
	end
	local held = if unreported > 0 then string.format(" (+%d more since the last warning)", unreported) else ""
	local message = string.format("[RedMesa] enemy motion watch failed for %s: %s; %s%s", describe(model), tostring(err), action, held)
	lastWarn = now
	unreported = 0
	warn(message)
end

local function judge(e: Entry, apply: Apply)
	refresh(e)
	apply(e.model, verdict(e), e.decor)
end

-- A model whose judgement raised: start it over from a fresh scan next
-- frame, or after MAX_STRIKES leave it unsmoothed while it is in play.
local function fail(e: Entry, apply: Apply, err: any)
	local model = e.model
	unwatch(e)
	local n = (strikes[model] or 0) + 1
	strikes[model] = n
	if n < MAX_STRIKES then
		report(model, err, string.format("re-scanning next frame (%d/%d)", n, MAX_STRIKES))
		Watch.add(model)
	else
		report(model, err, "giving up: not smoothed while in play")
		pcall(apply, model, nil, 0)
	end
end

local function drainQueue(apply: Apply): number
	local n = #queue
	local list = queue
	queue = spareQueue
	spareQueue = list
	local t0 = os.clock()
	local judged = 0
	for i = 1, n do
		local e = list[i]
		if i > 1 and os.clock() - t0 > DRAIN_BUDGET then
			-- Over budget: the rest (still marked queued) waits a frame.
			table.move(list, i, n, #queue + 1, queue)
			break
		end
		e.queued = false
		if entries[e.model] == e then
			local ok, err = pcall(judge, e, apply)
			if not ok then
				fail(e, apply, err)
			end
			judged += 1
		end
	end
	table.clear(list)
	return judged
end

-- Last resort if the drain itself raised: nothing may stay marked queued
-- while out of the queue, so every watched model is judged again.
local function recover()
	table.clear(queue)
	table.clear(spareQueue)
	for _, e in entries do
		e.queued = false
		enqueue(e)
	end
end

-- Re-judges the queued models and hands each verdict to `apply`. Returns
-- how many were judged. Nothing queued: returns at once.
function Watch.drain(apply: Apply): number
	if #queue == 0 then
		return 0
	end
	local ok, judged = pcall(drainQueue, apply)
	if ok then
		return judged
	end
	recover()
	pcall(report, nil, judged, "re-queueing every watched model")
	return 0
end

-- Studio QA: re-queues every watched model (the drain's recovery path).
function Watch.recover()
	recover()
end

-- Studio QA: how many models are watched and part signals connected.
function Watch.counts(): (number, number)
	local models, parts = 0, 0
	for _, e in entries do
		models += 1
		for _ in e.anchoredConn do
			parts += 1
		end
	end
	return models, parts
end

return Watch
