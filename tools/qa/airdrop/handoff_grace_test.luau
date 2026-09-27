-- AD-2 fix round 2: unit test of AirdropStyle.handoffGrace (the
-- latency-aware hand-off grace). Offline, Luau CLI:
--   python3 tools/qa/airdrop/run_grace_test.py
-- (builds a runner that loads src/client/AirdropStyle.luau with minimal
-- Roblox stubs, then runs this file).
local Style = require({ __mod = "AirdropStyle" })
local cases = {
	-- ping (s, round trip), seen (s), expected grace
	{ nil, nil, 0.40 },       -- nothing known yet: the floor
	{ 0, 0, 0.40 },
	{ 0.03, 0.05, 0.40 },     -- Studio-like (17-53 ms seen): floor
	{ 0.08, 0.05, 0.41 },     -- a good home connection
	{ 0.15, 0.05, 0.55 },
	{ 0.30, 0.00, 0.85 },     -- 300 ms ping
	{ 0.05, 0.33, 0.745 },    -- replication seen at 330 ms (e.g. 300 ms incoming lag)
	{ 0.30, 0.33, 0.85 },
	{ 0.60, 0.00, 1.45 },
	{ 1.00, 0.00, 1.50 },     -- ceiling
	{ 0.10, 2.00, 1.50 },
	{ -1, 0 / 0, 0.40 },      -- junk input
}
local fails = 0
for _, c in cases do
	local g = Style.handoffGrace(c[1], c[2])
	local ok = math.abs(g - c[3]) < 1e-9
	if not ok then fails += 1 end
	print(string.format("ping %-5s seen %-5s -> grace %.3f  (expect %.3f) %s", tostring(c[1]), tostring(c[2]), g, c[3], ok and "ok" or "FAIL"))
end
-- A live enemy is never retired while its replication delay d stays below
-- the grace computed from what was observed before (monotone check).
for _, d in { 0.05, 0.2, 0.3, 0.45, 0.8 } do
	local g = Style.handoffGrace(0, d)
	print(string.format("after seeing %.2f s, next grace %.3f (> %.2f: %s)", d, g, d, tostring(g > d)))
	if not (g > d or g == Style.Handoff.MAX) then fails += 1 end
end
print(fails == 0 and "ALL PASS" or ("FAILURES " .. fails))
