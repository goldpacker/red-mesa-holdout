--!strict
-- Studio-only QA commands behind ServerStorage.RedMesaDebug (GameController
-- installs them only when RunService:IsStudio()). See tools/qa/BEAUTY.md.
--   losCheck    turret line of sight to every lane end (+ along each lane)
--   groundCheck terrain height enemies snap to along every lane
--   beauty      stage a frozen beauty shot: { shot = 1..6 | name, tod = preset }
--   beautyEnd   leave beauty mode (back to a clean title screen)

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local BeautyShots = require(ReplicatedStorage.Shared.BeautyShots)
local Config = require(ReplicatedStorage.Shared.Config)
local EnemyConfig = require(ReplicatedStorage.Shared.EnemyConfig)
local Enemies = require(script.Parent.Enemies)
local Kit = require(script.Parent.EnemyTypes.Common.Kit)
local TimeOfDay = require(script.Parent.TimeOfDay)
local Weapons = require(script.Parent.Weapons)

export type Api = {
	context: any,
	clearBattlefield: () -> (),
	-- Stops the wave director (enemies freeze), refills integrity and
	-- publishes `phase` with `wave` on the HUD.
	freeze: (phase: string, wave: number) -> (),
	setScore: (score: number) -> (),
}

local QaDebug = {}
local api: Api? = nil

local SAMPLE_STEP = 20 -- studs between samples along a lane
-- Target heights above the ground: feet, hip/hull (the pass criterion), head.
local TARGET_HEIGHTS = { feet = 0.5, hip = 3, head = 6.5 }

-- Ground-frame footprints, mirroring each EnemyTypes/<Kind> place().
local GROUND_FRAME = {
	Tank = { 10, 5 },
	Buggy = { 4.5, 2.6, (EnemyConfig :: any).Buggy and (EnemyConfig :: any).Buggy.RIDE_HEIGHT or 0 },
	SiegeCrawler = { 40, 20 },
}

local function f1(n: number): string
	return string.format("%.1f", n)
end

-- ------------------------------------------------------------ raycasting

-- Everything a sight line may pass through: the emplacement, enemies,
-- projectiles, wrecks, crates and player characters.
local function excludedRoots(): { Instance }
	local list: { Instance } = {}
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local emplacement = battlefield and battlefield:FindFirstChild("Emplacement")
	if emplacement then
		table.insert(list, emplacement)
	end
	for _, name in { "Enemies", "Projectiles", "Wrecks", "Crates" } do
		local folder = Workspace:FindFirstChild(name)
		if folder then
			table.insert(list, folder)
		end
	end
	for _, player in Players:GetPlayers() do
		if player.Character then
			table.insert(list, player.Character)
		end
	end
	return list
end

local function isUnder(inst: Instance, roots: { Instance }): boolean
	for _, root in roots do
		if inst:IsDescendantOf(root) then
			return true
		end
	end
	return false
end

-- Runs `fn` with every visible CanQuery=false part (landscape and dressing
-- meshes, scrub) made queryable, so sight lines see what the player sees.
-- Synchronous: gameplay raycasts can't run in between.
local function withVisibleGeometry<T>(fn: () -> T): (T, number)
	local roots = excludedRoots()
	local toggled: { BasePart } = {}
	for _, d in Workspace:GetDescendants() do
		if d:IsA("BasePart") and not d.CanQuery and d.Transparency < 0.9 and not isUnder(d, roots) then
			d.CanQuery = true
			table.insert(toggled, d)
		end
	end
	local ok, result = pcall(fn)
	for _, part in toggled do
		part.CanQuery = false
	end
	if not ok then
		error(result, 0)
	end
	return result, #toggled
end

local function blockerName(inst: Instance): string
	if inst == Workspace.Terrain then
		return "Terrain"
	end
	return inst:GetFullName()
end

local terrainParams = RaycastParams.new()
terrainParams.FilterType = Enum.RaycastFilterType.Include

-- Height of the terrain enemies snap to (same ray as Kit.groundY).
local function terrainY(x: number, z: number): number?
	terrainParams.FilterDescendantsInstances = { Workspace.Terrain }
	local hit = Workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -520, 0), terrainParams)
	return if hit then hit.Position.Y else nil
end

-- Top of whatever is visible at (x, z): terrain or any mesh/part on it.
local function surfaceY(x: number, z: number, params: RaycastParams): (number?, Instance?)
	local hit = Workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -520, 0), params)
	if hit then
		return hit.Position.Y, hit.Instance
	end
	return nil, nil
end

local function samplesAlong(lane: { Vector2 }, step: number): { Vector2 }
	local out = {}
	for i = 1, #lane - 1 do
		local a, b = lane[i], lane[i + 1]
		local n = math.max(1, math.floor((b - a).Magnitude / step))
		for k = 0, n - 1 do
			table.insert(out, a:Lerp(b, k / n))
		end
	end
	table.insert(out, lane[#lane])
	return out
end

local function sortedLaneNames(): { string }
	local names = {}
	for name in Config.Lanes do
		table.insert(names, name)
	end
	table.sort(names)
	return names
end

-- ------------------------------------------------------------- LOS check

type Sight = { visible: boolean, blocker: string?, hit: Vector3? }

local function sight(target: Vector3, params: RaycastParams): Sight
	local pivot = Config.TURRET_PIVOT
	local dir = (target - pivot).Unit
	local origin = pivot + dir * Config.MUZZLE_OFFSET
	local delta = target - origin
	local hit = Workspace:Raycast(origin, delta - delta.Unit * 0.25, params)
	if hit then
		return { visible = false, blocker = blockerName(hit.Instance), hit = hit.Position }
	end
	return { visible = true }
end

local function losCheck(): (boolean, string, any)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = excludedRoots()
	local function run()
		local lines = {}
		local data = {}
		local allPass = true
		for _, name in sortedLaneNames() do
			local lane = Config.Lanes[name]
			local finish = lane[#lane]
			local ground = terrainY(finish.X, finish.Y) or 0
			local marks = {}
			local views: { [string]: Sight } = {}
			for label, height in TARGET_HEIGHTS do
				views[label] = sight(Vector3.new(finish.X, ground + height, finish.Y), params)
			end
			for _, label in { "feet", "hip", "head" } do
				table.insert(marks, label .. (if views[label].visible then "+" else "-"))
			end
			local pass = views.hip.visible
			allPass = allPass and pass
			-- Along the lane: hip-height sight line every SAMPLE_STEP studs.
			local blocked = {}
			local points = samplesAlong(lane, SAMPLE_STEP)
			for _, p in points do
				local y = terrainY(p.X, p.Y) or 0
				local s = sight(Vector3.new(p.X, y + TARGET_HEIGHTS.hip, p.Y), params)
				if not s.visible then
					table.insert(blocked, string.format("(%d,%d)", p.X, p.Y))
				end
			end
			local line = string.format(
				"%-10s end (%d,%d) ground %s  %s  %s  | along lane: %d/%d samples visible",
				name,
				finish.X,
				finish.Y,
				f1(ground),
				if pass then "PASS" else "FAIL",
				table.concat(marks, " "),
				#points - #blocked,
				#points
			)
			if not pass then
				local v = views.hip
				line ..= string.format("\n           blocked by %s at %s", tostring(v.blocker), tostring(v.hit))
			end
			if #blocked > 0 then
				line ..= "\n           hidden samples: " .. table.concat(blocked, " ")
			end
			table.insert(lines, line)
			data[name] = { pass = pass, ground = ground, views = views, hidden = blocked, samples = #points }
		end
		return { pass = allPass, lines = lines, data = data }
	end
	local result, toggled = withVisibleGeometry(run)
	local header = string.format(
		"LOS check from turret muzzle %s (hip = ground+%s; %d non-query visible parts included): %s",
		tostring(Config.TURRET_PIVOT),
		f1(TARGET_HEIGHTS.hip),
		toggled,
		if result.pass then "ALL PASS" else "FAIL"
	)
	return result.pass, header .. "\n" .. table.concat(result.lines, "\n"), result.data
end

-- ---------------------------------------------------------- ground check

local function groundCheck(arg: any): (string, any)
	local verbose = type(arg) == "table" and arg.verbose
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = excludedRoots()
	local function run()
		local lines = {}
		local data = {}
		for _, name in sortedLaneNames() do
			local heights = {}
			local minY, maxY, sum, digest = math.huge, -math.huge, 0, 0
			local worstLift, worstAt = 0, ""
			for i, p in samplesAlong(Config.Lanes[name], SAMPLE_STEP) do
				local y = terrainY(p.X, p.Y) or 0
				local top, inst = surfaceY(p.X, p.Y, params)
				local lift = if top then top - y else 0
				if math.abs(lift) > math.abs(worstLift) then
					worstLift = lift
					worstAt = string.format("(%d,%d) %s", p.X, p.Y, if inst then blockerName(inst) else "?")
				end
				minY, maxY, sum = math.min(minY, y), math.max(maxY, y), sum + y
				digest += math.floor(y * 10 + 0.5) * i
				table.insert(heights, math.floor(y * 10 + 0.5) / 10)
			end
			local line = string.format(
				"%-10s %2d samples  terrain y min %s max %s mean %s  digest %d  max surface-above-terrain %s%s",
				name,
				#heights,
				f1(minY),
				f1(maxY),
				f1(sum / #heights),
				digest,
				f1(worstLift),
				if worstLift ~= 0 then " at " .. worstAt else ""
			)
			if verbose then
				local parts = {}
				for _, h in heights do
					table.insert(parts, f1(h))
				end
				line ..= "\n           y: " .. table.concat(parts, " ")
			end
			table.insert(lines, line)
			data[name] = { heights = heights, digest = digest, worstLift = worstLift }
		end
		return { lines = lines, data = data }
	end
	local result = withVisibleGeometry(run)
	local header = string.format("Ground check: terrain height enemies snap to, every %d studs along each lane", SAMPLE_STEP)
	return header .. "\n" .. table.concat(result.lines, "\n"), result.data
end

-- -------------------------------------------------------- beauty staging

local stagedSet: string? = nil
local seenKinds: { [string]: boolean } = {}

local function place(enemy: any, subject: BeautyShots.Subject)
	local root = enemy.root :: BasePart
	local at = subject.at
	local face = subject.face or Vector2.zero
	if subject.altitude then
		local position = Vector3.new(at.X, subject.altitude, at.Y)
		local frame = CFrame.lookAt(position, Vector3.new(face.X, subject.altitude, face.Y))
		root.CFrame = frame * root.PivotOffset:Inverse()
	elseif enemy.kind == "Infantry" then
		-- Infantry roots sit at hip height above the terrain.
		local spawnGround = Kit.groundY(root.Position.X, root.Position.Z)
		local hip = root.Position.Y - spawnGround
		local y = Kit.groundY(at.X, at.Y) + hip
		root.CFrame = CFrame.lookAt(Vector3.new(at.X, y, at.Y), Vector3.new(face.X, y, face.Y))
		enemy.model:SetAttribute("State", subject.state or "Aim")
	else
		local footprint = GROUND_FRAME[enemy.kind] or { 5, 3 }
		local frame = Kit.groundFrame(at, face - at, footprint[1], footprint[2], footprint[3] or 0)
		root.CFrame = frame * root.PivotOffset:Inverse()
	end
end

-- Spawns a stage's subjects frozen in place. Returns true if a kind appears
-- for the first time this session (the client shows a 6 s tip for it).
local function spawnStage(name: string): boolean
	local a = api :: Api
	a.clearBattlefield()
	local newKind = false
	for _, subject in BeautyShots.STAGES[name] or {} do
		local lane = if subject.altitude then "AirCenter" else "Road"
		local ok, enemy = pcall(Enemies.spawn, a.context, subject.kind, lane)
		if ok and enemy then
			place(enemy, subject)
			if not seenKinds[subject.kind] then
				seenKinds[subject.kind] = true
				newKind = true
			end
		else
			warn("[RedMesa] beauty: spawn " .. subject.kind .. " failed: " .. tostring(enemy))
		end
	end
	stagedSet = name
	return newKind
end

local function beauty(arg: any): string
	local a = api :: Api
	assert(type(arg) == "table", "beauty expects { shot = n, tod = preset }")
	local shot = BeautyShots.get(arg.shot)
	local preset = BeautyShots.preset(arg.tod or "Afternoon")
	assert(shot, "unknown shot " .. tostring(arg.shot))
	assert(preset, "unknown time of day " .. tostring(arg.tod))
	local wave = if shot.phase == "Title" then 0 else (shot.wave or BeautyShots.WAVE_FOR[preset])
	a.freeze(shot.phase, wave)
	Weapons.resetAll()
	a.setScore(if shot.phase == "Title" then 0 else BeautyShots.SCORE)
	TimeOfDay.set(preset, 0)
	local newKind = false
	if stagedSet ~= shot.stage then
		newKind = spawnStage(shot.stage)
	end
	local state = ReplicatedStorage:FindFirstChild("GameState")
	if state then
		state:SetAttribute("Remaining", #(BeautyShots.STAGES[shot.stage] or {}) + 6)
	end
	if shot.stage == "boss" then
		a.context.emit("BossUpdate", { weakPoints = { TurretLeft = true, TurretRight = true, MainCannon = true }, core = 1, exposed = false })
	end
	Workspace:SetAttribute("BeautyToD", preset)
	Workspace:SetAttribute("BeautyShot", shot.id)
	-- Let the client replicate, frame and settle (first-encounter tips last 6 s).
	local settle = if newKind then 7.5 else 2
	if type(arg.settle) == "number" then
		settle = arg.settle
	end
	task.wait(settle)
	return string.format("staged %s (waited %.1fs)", BeautyShots.fileName(shot, preset), settle)
end

local function beautyEnd(): string
	local a = api :: Api
	a.clearBattlefield()
	stagedSet = nil
	Workspace:SetAttribute("BeautyShot", nil)
	Workspace:SetAttribute("BeautyToD", nil)
	a.freeze("Title", 0)
	a.setScore(0)
	TimeOfDay.set("Afternoon", 0)
	return "beauty mode off"
end

-- ------------------------------------------------------------- dispatch

local COMMANDS: { [string]: (any) -> ...any } = {
	losCheck = function(_arg)
		return losCheck()
	end,
	groundCheck = groundCheck,
	beauty = beauty,
	beautyEnd = function(_arg)
		return beautyEnd()
	end,
}

function QaDebug.init(a: Api)
	api = a
end

function QaDebug.has(cmd: string): boolean
	return COMMANDS[cmd] ~= nil
end

function QaDebug.run(cmd: string, arg: any): ...any
	return COMMANDS[cmd](arg)
end

return QaDebug
