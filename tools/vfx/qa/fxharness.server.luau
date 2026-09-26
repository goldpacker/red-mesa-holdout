--!nocheck
-- VFX capture harness (Studio playtest only, Server datamodel).
-- Install once per Play session by pasting this file into MCP execute_luau
-- (Server); it creates ServerStorage.FxHarnessServer. Then:
--   local S = require(game.ServerStorage.FxHarnessServer)
--   S.shell()            -- the staged tank fires a shell at the outpost
--   S.volley(3)          -- infantry rifles + buggy bursts for 3 s
--   S.bombs()            -- a jet bomb stick on the outpost
-- It only fires the same "EnemyFire" GameEvents the enemies send, so the
-- client renders them through client/EnemyFireFx exactly as in play.
local source = [==[
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")
local S = {}
local PIVOT = Vector3.new(0, 72, 0)
local event = ReplicatedStorage.Remotes.GameEvent

function S.enemy(kind, index)
	local n = 0
	for _, m in Workspace.Enemies:GetChildren() do
		if m:GetAttribute("Kind") == kind then
			n += 1
			if n == (index or 1) then
				return m
			end
		end
	end
	return nil
end

function S.all(kind)
	local out = {}
	for _, m in Workspace.Enemies:GetChildren() do
		if m:GetAttribute("Kind") == kind then
			table.insert(out, m)
		end
	end
	return out
end

function S.point(model, names)
	for _, name in names do
		local a = model:FindFirstChild(name, true)
		if a and a:IsA("Attachment") then
			return a.WorldPosition
		elseif a and a:IsA("BasePart") then
			return a.Position
		end
	end
	return model:GetPivot().Position + Vector3.new(0, 4, 0)
end

-- Same rule as EnemyTypes/Common/Kit.impactPoint.
function S.impact(from, rng)
	local flat = Vector3.new(from.X - PIVOT.X, 0, from.Z - PIVOT.Z)
	local dir = if flat.Magnitude > 0.1 then flat.Unit else Vector3.new(0, 0, -1)
	local r = rng or Random.new()
	return PIVOT + dir * r:NextNumber(10, 15) + Vector3.new(r:NextNumber(-3, 3), -9, r:NextNumber(-3, 3))
end

function S.send(kind, attack, from, to)
	event:FireAllClients("EnemyFire", { kind = kind, attack = attack, from = from, to = to, id = 0 })
end

function S.shell()
	local tank = S.enemy("Tank")
	local from = S.point(tank, { "Muzzle" })
	S.send("Tank", "Shell", from, S.impact(from))
	return from
end

function S.tankAim(seconds)
	local tank = S.enemy("Tank")
	S.send("Tank", "TankAim", S.point(tank, { "Muzzle" }), PIVOT)
end

function S.heliRockets(count)
	local heli = S.enemy("Helicopter")
	for i = 1, count or 4 do
		local from = S.point(heli, { if i % 2 == 0 then "RocketMuzzleL" else "RocketMuzzleR" })
		S.send("Helicopter", "Rocket", from, S.impact(from))
		task.wait(0.18)
	end
end

function S.bombs(from)
	local origin = from or Vector3.new(-30, 190, -170)
	S.send("Jet", "Bombs", origin, S.impact(origin))
end

-- Rifle fire from every staged soldier plus buggy bursts, for `seconds`.
function S.volley(seconds)
	task.spawn(function()
		local stop = os.clock() + (seconds or 3)
		while os.clock() < stop do
			for _, m in S.all("Infantry") do
				if math.random() < 0.35 then
					local from = S.point(m, { "RifleMuzzle" })
					S.send("Infantry", "Rifle", from, PIVOT)
				end
			end
			local buggy = S.enemy("Buggy")
			if buggy and math.random() < 0.25 then
				local from = S.point(buggy, { "Muzzle" })
				S.send("Buggy", "BuggyBurst", from, S.impact(from))
			end
			task.wait(0.15)
		end
	end)
end

return S
]==]
local ss = game:GetService("ServerStorage")
local old = ss:FindFirstChild("FxHarnessServer")
if old then
	old:Destroy()
end
local m = Instance.new("ModuleScript")
m.Name = "FxHarnessServer"
m.Source = source
m.Parent = ss
return "installed"
