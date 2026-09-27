-- LOOK-6 live-wave staging (Server datamodel), after QA-F's protocol
-- (PERF_BUDGET §6): airdropSeed 7, integrity held at 100, three extra debug
-- sorties at 34 s (8 Infantry Road, 1 Tank ScrubLeft, 2 Buggy ScrubRight).
-- Set WAVE below (9 = busy wave, Sunset; 10 = boss). The client runs the MG
-- bot (bot_idle.client.luau) and the bench.
local WAVE = 10
local dbg = game.ServerStorage.RedMesaDebug
dbg:Invoke("airdropSeed", 7)
dbg:Invoke("startWave", WAVE)
local token = os.clock()
workspace:SetAttribute("L6StageToken", token)
task.spawn(function()
	while workspace:GetAttribute("L6StageToken") == token do
		dbg:Invoke("setIntegrity", 100)
		task.wait(2)
	end
end)
task.delay(34, function()
	if workspace:GetAttribute("L6StageToken") ~= token then
		return
	end
	dbg:Invoke("airdrop", { kind = "Infantry", count = 8, lane = "Road" })
	dbg:Invoke("airdrop", { kind = "Tank", count = 1, lane = "ScrubLeft" })
	dbg:Invoke("airdrop", { kind = "Buggy", count = 2, lane = "ScrubRight" })
end)
return "wave " .. WAVE .. " started, ToD " .. tostring(workspace:GetAttribute("TimeOfDay"))
