-- LOOK-3B: EnemyMotionWatch unit test. Paste into execute_luau (Client
-- datamodel) during a Studio playtest. It requires a private clone of the
-- module (fresh state, its own queue), builds synthetic models that are
-- never parented to the Workspace, and checks every qualification rule and
-- event path. Returns one PASS/FAIL line per check.
local src = game:GetService("Players").LocalPlayer.PlayerScripts:WaitForChild("Client")
local folder = Instance.new("Folder")
src.EnemyMotionProbe:Clone().Parent = folder
local wm = src.EnemyMotionWatch:Clone()
wm.Parent = folder
local W = require(wm) :: any

local out = {}
local fails = 0
local function check(name: string, cond: boolean, detail: any?)
	if not cond then
		fails += 1
	end
	table.insert(out, (if cond then "PASS " else "FAIL ") .. name .. (if detail ~= nil then "  [" .. tostring(detail) .. "]" else ""))
end

local verdict: { [Model]: { root: BasePart?, ignored: number, n: number, nils: number } } = {}
local throwOn: { [Model]: number } = {} -- failures still to inject when smoothable
local function apply(model: Model, root: BasePart?, ignored: number)
	if root ~= nil and (throwOn[model] or 0) > 0 then
		throwOn[model] -= 1
		error("injected failure")
	end
	local v = verdict[model] or { root = nil, ignored = 0, n = 0, nils = 0 }
	v.root, v.ignored, v.n = root, ignored, v.n + 1
	if root == nil then
		v.nils += 1
	end
	verdict[model] = v
end
local function part(parent: Instance, name: string, anchored: boolean, query: boolean): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Anchored = anchored
	p.CanQuery = query
	p.Parent = parent
	return p
end
local function drain(): number
	task.wait() -- deferred signals fire
	return W.drain(apply)
end
local WARN_WAIT = 5.2 -- s: EnemyMotionWatch's WARN_EVERY plus a margin

-- 1. A plain enemy: anchored Root (PrimaryPart), welded hull, turret sub-model.
local m = Instance.new("Model")
m:SetAttribute("Kind", "Buggy")
local root = part(m, "Root", true, false)
m.PrimaryPart = root
local hull = part(m, "Hull", false, true)
local turret = Instance.new("Model")
turret.Name = "Turret"
turret.Parent = m
local gun = part(turret, "Gun", false, true)
W.add(m)
check("new model judged on first drain", drain() == 1)
check("smoothable, root found", verdict[m] and verdict[m].root == root and verdict[m].ignored == 0)
check("idle: nothing to judge", drain() == 0 and drain() == 0)

-- 2. Decorative anchored part (LampGlow): ignored.
local lamp = part(m, "LampGlow", true, false)
check("decorative part added -> re-judged", drain() == 1)
check("decorative part ignored, still smoothable", verdict[m].root == root and verdict[m].ignored == 1, verdict[m].ignored)
lamp.Parent = turret
drain()
check("decorative part moved inside the model: still ignored once", verdict[m].root == root and verdict[m].ignored == 1, verdict[m].ignored)

-- 3. Anchored hit volume added, then removed.
local wing = part(m, "Wing", true, true)
drain()
check("anchored hit volume blocks", verdict[m].root == nil)
wing.Parent = nil
drain()
check("hit volume removed -> smoothable again", verdict[m].root == root)

-- 4. In-place flips on existing parts.
hull.Anchored = true
drain()
check("welded query part anchored in place blocks", verdict[m].root == nil)
hull.Anchored = false
drain()
check("... unanchored again -> smoothable", verdict[m].root == root)
lamp.CanQuery = true
drain()
check("decorative part turned queryable blocks", verdict[m].root == nil)
lamp.CanQuery = false
drain()
check("... back to no-query -> smoothable, ignored 1", verdict[m].root == root and verdict[m].ignored == 1)

-- 5. Kit.detach transient: anchored in place and moved out in one step.
local nilsBefore = verdict[m].nils
gun.Anchored = true
turret.Parent = nil
drain()
check("detach transient never blocks", verdict[m].root == root and verdict[m].nils == nilsBefore, verdict[m].nils - nilsBefore)
check("detached piece forgotten (no stale signals)", (function()
	gun.CanQuery = false
	return drain() == 0
end)())

-- 6. Root unanchored / re-anchored.
root.Anchored = false
drain()
check("unanchored Root -> not smoothable", verdict[m].root == nil)
root.Anchored = true
drain()
check("re-anchored Root -> smoothable", verdict[m].root == root)

-- 7. Root replaced.
root:Destroy()
drain()
check("Root destroyed -> not smoothable", verdict[m].root == nil)
local root2 = part(m, "Root", true, false)
m.PrimaryPart = root2
drain()
check("new Root found", verdict[m].root == root2)
root2.Name = "Hull2"
drain()
check("Root renamed away -> not smoothable", verdict[m].root == nil)
root2.Name = "Root"
drain()
check("renamed back -> smoothable again", verdict[m].root == root2)

-- 8. Kind attribute change re-judges.
m:SetAttribute("Kind", "Tank")
check("Kind change re-judges", drain() == 1)

-- 9. Root nested, no PrimaryPart.
local n = Instance.new("Model")
n:SetAttribute("Kind", "Infantry")
local body = Instance.new("Model")
body.Parent = n
local nroot = part(body, "Root", true, false)
W.add(n)
drain()
check("nested Root without PrimaryPart found", verdict[n] and verdict[n].root == nroot)

-- 10. Removed models are left alone.
W.remove(n)
part(n, "Blocker", true, true)
check("removed model: no work", drain() == 0)

-- 11. Existing blocker at spawn (TestDummyAir-like): never smoothable, no retries.
local d = Instance.new("Model")
d:SetAttribute("Kind", "Helicopter")
local droot = part(d, "Root", true, false)
d.PrimaryPart = droot
part(d, "Wing", true, true)
W.add(d)
drain()
check("spawned with a hit volume: not smoothable", verdict[d] and verdict[d].root == nil)
check("... and no re-scans afterwards", drain() == 0 and drain() == 0)
W.remove(d)

-- 12. Failure isolation (LOOK-3B fix 1): a model whose judgement raises
-- doesn't stop the drain or strand the models queued behind it; it is
-- re-scanned on the next frames, then given up on after 3 strikes; the
-- warning names it and is rate-limited.
local warnings: { string } = {}
local logConn = game:GetService("LogService").MessageOut:Connect(function(msg, kind)
	if kind == Enum.MessageType.MessageWarning and string.find(msg, "enemy motion watch failed", 1, true) then
		table.insert(warnings, msg)
	end
end)
local function enemy(kind: string, id: number): (Model, BasePart)
	local x = Instance.new("Model")
	x.Name = kind .. "Test"
	x:SetAttribute("Kind", kind)
	x:SetAttribute("EnemyId", id)
	local r = part(x, "Root", true, false)
	x.PrimaryPart = r
	return x, r
end
local a, ar = enemy("Buggy", 701)
local bad = enemy("Tank", 777)
local c, cr = enemy("Helicopter", 702)
throwOn[bad] = 99
W.add(a)
W.add(bad)
W.add(c)
check("failing model in the middle of a batch: whole batch judged", drain() == 3)
check("... models queued behind it not stranded", verdict[a] and verdict[a].root == ar and verdict[c] and verdict[c].root == cr)
check("... failing model re-scanned next frame (strike 2)", drain() == 1 and throwOn[bad] == 97, throwOn[bad])
check("... and again (strike 3) -> given up, left unsmoothed", drain() == 1 and throwOn[bad] == 96 and verdict[bad] and verdict[bad].root == nil)
part(bad, "Blocker", true, true)
check("... given-up model costs nothing afterwards", drain() == 0 and drain() == 0)
task.wait(0.1)
check("one warning for three failures in 5 s (rate-limited)", #warnings == 1, #warnings)
check("warning names the model", warnings[1] ~= nil and string.find(warnings[1], "Tank#777", 1, true) ~= nil and string.find(warnings[1], "TankTest", 1, true) ~= nil, warnings[1])
local flaky, fr = enemy("Buggy", 703)
throwOn[flaky] = 1
W.add(flaky)
drain()
drain()
check("a one-off failure recovers on the re-scan", verdict[flaky] and verdict[flaky].root == fr)
W.recover()
local rejudged = drain()
local watchedNow = W.counts()
check("recover() re-queues every watched model", rejudged == watchedNow and verdict[a].root == ar and verdict[c].root == cr, string.format("%d of %d", rejudged, watchedNow))
for _, x in { a, bad, c, flaky } do
	W.remove(x)
	x:Destroy()
end

-- 13. The drain itself raises (LOOK-3B fix 2). A fake model whose every
-- field access errors fails its judgement, and then fails again inside
-- fail() -> report() -> describe(), so the error escapes the per-model
-- pcall and reaches Watch.drain's own pcall: the real path, no seam.
-- Expected: the drain returns normally, every watched model is re-queued
-- (the one queued behind the fake isn't stranded), the next frame judges
-- each exactly once, one warning, then nothing: no per-frame storm.
task.wait(WARN_WAIT) -- let the rate limiter's window from section 12 pass
local settled: { Model } = {}
for i = 1, 3 do
	local x = enemy("Infantry", 710 + i)
	W.add(x)
	settled[i] = x
end
drain()
local fake = setmetatable({}, {
	__index = function(_, key)
		error("fake model: no " .. tostring(key))
	end,
})
local behind, behindRoot = enemy("Tank", 719)
local before: { [Model]: number } = {}
for _, x in settled do
	before[x] = verdict[x].n
end
local warnedBefore = #warnings
W.add(fake)
W.add(behind)
task.wait()
local okDrain, firstDrain = pcall(W.drain, apply)
check("drain that raises past the per-model pcall is caught", okDrain and firstDrain == 0, tostring(firstDrain))
local watched = W.counts()
local rejudgedAll = drain()
local once = true
for _, x in settled do
	if verdict[x].n ~= before[x] + 1 then
		once = false
	end
end
check("every watched model re-queued and judged once on the next frame", rejudgedAll == watched and once, string.format("%d of %d", rejudgedAll, watched))
check("the model queued behind the failure isn't stranded", verdict[behind] and verdict[behind].root == behindRoot and verdict[behind].n == 1)
check("the failing model is no longer watched", (function()
	for _ = 1, 3 do
		if drain() ~= 0 then
			return false
		end
	end
	return true
end)())
task.wait(0.1)
local newWarnings = #warnings - warnedBefore
check("one warning for the recovery", newWarnings == 1 and string.find(warnings[#warnings], "re-queueing every watched model", 1, true) ~= nil, warnings[#warnings])
local quiet = true
for _ = 1, 10 do
	if drain() ~= 0 then
		quiet = false
	end
end
task.wait(0.1)
check("no per-frame storm afterwards", quiet and #warnings - warnedBefore == 1, #warnings - warnedBefore)
logConn:Disconnect()
W.remove(fake :: any)
for _, x in { behind, table.unpack(settled) } do
	W.remove(x)
	x:Destroy()
end

-- 14. Burst: 60 models of 150 parts arrive at once; the drain budget
-- spreads the scans over frames and every model is judged exactly once.
local burst = {}
for i = 1, 60 do
	local b = Instance.new("Model")
	b:SetAttribute("Kind", "Tank")
	local r = part(b, "Root", true, false)
	b.PrimaryPart = r
	for j = 1, 149 do
		local p = Instance.new("Part")
		p.Anchored = false
		p.Parent = b
	end
	burst[i] = b
	W.add(b)
end
local frames, total, worst, t0 = 0, 0, 0, 0
while total < 60 and frames < 200 do
	task.wait()
	t0 = os.clock()
	local k = W.drain(apply)
	worst = math.max(worst, os.clock() - t0)
	total += k
	frames += 1
end
local judged = 0
for _, b in burst do
	if verdict[b] and verdict[b].root and verdict[b].n == 1 then
		judged += 1
	end
end
check("burst: all 60 judged once", judged == 60, judged)
check("burst spread over frames", frames > 1, string.format("%d frames, worst drain %.3f ms, %.3f ms per 150-part scan", frames, worst * 1000, worst * 1000 / math.max(1, 60 / frames)))
local models, parts = W.counts()
table.insert(out, string.format("watching %d models, %d parts with signals", models, parts))
for _, b in burst do
	W.remove(b)
	b:Destroy()
end
W.remove(m)
m:Destroy()
folder:Destroy()
table.insert(out, 1, if fails == 0 then "ALL PASS" else fails .. " FAILED")
return table.concat(out, "\n")
