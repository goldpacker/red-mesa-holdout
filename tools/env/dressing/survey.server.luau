-- ENV-4 basin survey (Studio playtest, Server datamodel; Studio only).
-- Posts survey.json to the local sink (tools/env/ground/sink.py <dir>):
--   grid:     terrain height/material/normal.Y every STEP studs over the basin
--   boulders: TerrainBuilder.boulders; rocks: Battlefield.RockKit bounding circles
--   drops:    landing points of SORTIES planned with the gameplay planner
--             (AirdropPlan.sortie, the drop-zone check's kind/lane mix) and each
--             one's join waypoint (the straight walk/drive to the lane)
-- tools/env/dressing/survey.py renders it as the layout board.
local Http = game:GetService("HttpService")
local Server = game:GetService("ServerScriptService").Server
local TerrainBuilder = require(Server.TerrainBuilder)
local AirdropPlan = require(Server.AirdropPlan)
local AirdropLanding = require(Server.AirdropLanding)
local Config = require(game:GetService("ReplicatedStorage").Shared.Config)
local AirdropConfig = require(game:GetService("ReplicatedStorage").Shared.AirdropConfig)

local STEP = 8
local X0, X1, Z0, Z1 = -800, 800, -1400, 200
local SORTIES = 900
local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Include
params.FilterDescendantsInstances = { workspace.Terrain }

local rows = {}
for z = Z0, Z1, STEP do
	local row = table.create(math.floor((X1 - X0) / STEP) + 1)
	for x = X0, X1, STEP do
		local hit = workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -520, 0), params)
		if hit then
			row[#row + 1] = string.format("%.1f,%s,%.2f", hit.Position.Y, hit.Material.Name, hit.Normal.Y)
		else
			row[#row + 1] = ""
		end
	end
	rows[#rows + 1] = table.concat(row, ";")
	if #rows % 40 == 0 then
		task.wait()
	end
end

local boulders = {}
for _, b in TerrainBuilder.boulders do
	boulders[#boulders + 1] = { b.p.X, b.p.Y, b.size }
end
local rocks = {}
local kit = workspace.Battlefield:FindFirstChild("RockKit")
if kit then
	for _, m in kit:GetChildren() do
		if m:IsA("Model") then
			local cf, size = m:GetBoundingBox()
			rocks[#rocks + 1] = { cf.X, cf.Z, math.sqrt(size.X * size.X + size.Z * size.Z) / 2, size.Y, m.Name }
		end
	end
end

local COMBOS = {
	{ "Infantry", "Road", 8 }, { "Infantry", "ScrubLeft", 6 }, { "Infantry", "ScrubRight", 5 },
	{ "Buggy", "WashLeft", 2 }, { "Infantry", "Road", 12 }, { "Buggy", "WashRight", 3 },
	{ "Tank", "Road", 1 }, { "Infantry", "WashLeft", 4 }, { "Tank", "Road", 2 }, { "Infantry", "WashRight", 8 },
}
local rng = Random.new(4040)
local taken = {}
local drops = {}
for i = 1, SORTIES do
	local combo = COMBOS[(i - 1) % #COMBOS + 1]
	local kind, laneName, total = combo[1], combo[2], combo[3]
	if i % 4 == 1 then
		table.clear(taken)
	end
	local timing = if i % 2 == 0 then { land = rng:NextNumber(30, 45), earliest = 0 } else { t0 = 0 }
	local n = math.min(AirdropConfig.KINDS[kind].capacity, total)
	local ok, plan = pcall(AirdropPlan.sortie, rng, kind, laneName, n, timing, taken)
	if ok and plan then
		local lane = Config.Lanes[AirdropPlan.resolveLane(kind, laneName)]
		for _, l in plan.loads do
			local p = Vector2.new(l.landPos.X, l.landPos.Z)
			local goal = lane[AirdropLanding.joinIndex(lane, p)]
			drops[#drops + 1] = { math.floor(p.X * 10) / 10, math.floor(p.Y * 10) / 10, kind, laneName, goal.X, goal.Y }
			table.insert(taken, { p = p, spacing = AirdropConfig.KINDS[kind].spacing })
		end
	end
	if i % 25 == 0 then
		task.wait()
	end
end

-- Placed conflict dressing (bounding circles), if the build has it.
local pieces = {}
local cd = workspace.Battlefield:FindFirstChild("ConflictDressing")
if cd then
	for _, folder in cd:GetChildren() do
		for _, item in folder:GetChildren() do
			local cf, size
			if item:IsA("Model") then
				cf, size = item:GetBoundingBox()
			elseif item:IsA("BasePart") and item.Transparency < 1 then
				cf, size = item.CFrame, item.Size
			end
			if cf then
				pieces[#pieces + 1] = { math.floor(cf.X * 10) / 10, math.floor(cf.Z * 10) / 10, math.floor(math.sqrt(size.X * size.X + size.Z * size.Z) * 5) / 10, math.floor(size.Y * 10) / 10, folder.Name .. "/" .. item.Name }
			end
		end
	end
end

local out = Http:JSONEncode({
	step = STEP, x0 = X0, x1 = X1, z0 = Z0, z1 = Z1, rows = rows,
	boulders = boulders, rocks = rocks, drops = drops, pieces = pieces,
})
local was = Http.HttpEnabled
Http.HttpEnabled = true
Http:PostAsync("http://localhost:34999/survey.json", out, Enum.HttpContentType.ApplicationJson)
Http.HttpEnabled = was
return string.format("survey: %d rows, %d boulders, %d rocks, %d drops, %d pieces, %d bytes", #rows, #boulders, #rocks, #drops, #pieces, #out)
