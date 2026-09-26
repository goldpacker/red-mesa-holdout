--!strict
-- Full-screen and banner UI: title, wave banners, intermission tally,
-- defeat and victory screens.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local GameState = require(script.Parent.GameState)
local Ui = require(script.Parent.Ui)

local Screens = {}

local C = Ui.Colors
local F = Ui.Fonts
local remotes = ReplicatedStorage:WaitForChild("Remotes")

local gui: ScreenGui
local title: Frame
local banner: Frame
local bannerMain: TextLabel
local bannerSub: TextLabel
local tally: Frame
local tallyRows: TextLabel
local tallyNext: TextLabel
local endScreen: Frame
local endTitle: TextLabel
local endSub: TextLabel
local endStats: TextLabel
local retryButton: TextButton
local restartButton: TextButton
local tallyNextBase = ""

local function buildTitle()
	title = Ui.new("Frame", { Name = "Title", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = gui })
	Ui.new("Frame", {
		BackgroundColor3 = Color3.new(0, 0, 0),
		BackgroundTransparency = 0.55,
		BorderSizePixel = 0,
		Size = UDim2.new(0, 560, 1, 0),
		Parent = title,
	}, {
		Ui.new("UIGradient", { Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(0.8, 0.3), NumberSequenceKeypoint.new(1, 1) }) }),
	})
	local name = Ui.label({ Text = "RED MESA", FontFace = F.Header, TextSize = 92, TextColor3 = C.Amber, Position = UDim2.new(0, 60, 0.18, 0), Size = UDim2.fromOffset(600, 96), Parent = title })
	Ui.outline(name, 3)
	local name2 = Ui.label({ Text = "HOLDOUT", FontFace = F.Header, TextSize = 72, TextColor3 = C.Text, Position = UDim2.new(0, 64, 0.18, 88), Size = UDim2.fromOffset(600, 76), Parent = title })
	Ui.outline(name2, 3)
	local tagline = Ui.label({ Text = "HOLD THE MESA. SURVIVE 10 WAVES.", FontFace = F.Label, TextSize = 22, TextColor3 = C.Olive, Position = UDim2.new(0, 68, 0.18, 170), Size = UDim2.fromOffset(500, 26), Parent = title })
	Ui.outline(tagline)

	local card = Ui.panel({ Name = "Controls", Position = UDim2.new(0, 64, 0.18, 220), Size = UDim2.fromOffset(380, 196), Parent = title })
	Ui.label({ Text = "CONTROLS", FontFace = F.HeaderBold, TextSize = 20, TextColor3 = C.Amber, Position = UDim2.fromOffset(14, 8), Size = UDim2.fromOffset(200, 22), Parent = card })
	local rows = {
		{ "MOUSE", "Aim turret" },
		{ "LEFT MOUSE", "Fire" },
		{ "RIGHT MOUSE (HOLD)", "Gunsight view" },
		{ "1 / 2 / 3", "Machine gun / Rockets / AA" },
		{ "MOUSE WHEEL", "Cycle weapons" },
	}
	for i, row in rows do
		local y = 38 + (i - 1) * 30
		Ui.label({ Text = row[1], FontFace = F.Label, TextSize = 17, TextColor3 = C.Amber, Position = UDim2.fromOffset(14, y), Size = UDim2.fromOffset(170, 24), Parent = card })
		Ui.label({ Text = row[2], FontFace = F.Body, TextSize = 17, Position = UDim2.fromOffset(186, y), Size = UDim2.fromOffset(190, 24), Parent = card })
	end

	local start = Ui.button({ Name = "StartButton", Text = "LOADING…", TextSize = 36, Position = UDim2.new(0, 64, 0.18, 436), Size = UDim2.fromOffset(240, 64), Parent = title })
	start.AutoButtonColor = false
	start.Activated:Connect(function()
		if start:GetAttribute("Ready") then
			(remotes:WaitForChild("StartGame") :: RemoteEvent):FireServer()
		end
	end)
	local status = Ui.label({ Name = "LoadStatus", Text = "SURVEYING BATTLEFIELD…", FontFace = F.Label, TextSize = 16, TextColor3 = C.Olive, Position = UDim2.new(0, 68, 0.18, 506), Size = UDim2.fromOffset(400, 20), Parent = title })
	Ui.outline(status)
	task.spawn(function()
		Screens.waitForWorld()
		start:SetAttribute("Ready", true)
		start.AutoButtonColor = true
		start.Text = "START"
		status.Visible = false
	end)
end

local function buildBanner()
	banner = Ui.new("Frame", { Name = "Banner", BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.36), Size = UDim2.fromOffset(900, 150), Visible = false, Parent = gui })
	Ui.new("Frame", {
		BackgroundColor3 = C.Panel,
		BackgroundTransparency = 0.25,
		BorderSizePixel = 0,
		Position = UDim2.fromOffset(0, 18),
		Size = UDim2.new(1, 0, 0, 116),
		Parent = banner,
	}, {
		Ui.new("UIGradient", { Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.2, 0.2), NumberSequenceKeypoint.new(0.8, 0.2), NumberSequenceKeypoint.new(1, 1) }) }),
	})
	bannerMain = Ui.label({ Name = "Main", Text = "", FontFace = F.Header, TextSize = 64, TextColor3 = C.Amber, TextXAlignment = Enum.TextXAlignment.Center, Position = UDim2.fromOffset(0, 22), Size = UDim2.new(1, 0, 0, 70), Parent = banner })
	Ui.outline(bannerMain, 3)
	bannerSub = Ui.label({ Name = "Sub", Text = "", FontFace = F.Label, TextSize = 26, TextXAlignment = Enum.TextXAlignment.Center, Position = UDim2.fromOffset(0, 92), Size = UDim2.new(1, 0, 0, 30), Parent = banner })
	Ui.outline(bannerSub, 2)
end

local function buildTally()
	tally = Ui.panel({ Name = "Tally", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(460, 210), Visible = false, Parent = gui })
	tallyRows = Ui.label({ Text = "", FontFace = F.Mono, TextSize = 20, RichText = true, TextYAlignment = Enum.TextYAlignment.Top, Position = UDim2.fromOffset(20, 14), Size = UDim2.new(1, -40, 0, 140), Parent = tally })
	tallyNext = Ui.label({ Text = "", FontFace = F.HeaderBold, TextSize = 22, TextColor3 = C.Amber, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 1), Position = UDim2.new(0.5, 0, 1, -12), Size = UDim2.new(1, -20, 0, 28), Parent = tally })
end

local function buildEndScreen()
	endScreen = Ui.new("Frame", { Name = "EndScreen", BackgroundColor3 = Color3.new(0, 0, 0), BackgroundTransparency = 0.45, BorderSizePixel = 0, Size = UDim2.fromScale(1, 1), Visible = false, Parent = gui })
	endTitle = Ui.label({ Text = "", FontFace = F.Header, TextSize = 88, TextColor3 = C.Red, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.fromScale(0.5, 0.12), Size = UDim2.fromOffset(900, 96), Parent = endScreen })
	Ui.outline(endTitle, 3)
	endSub = Ui.label({ Text = "", FontFace = F.Label, TextSize = 28, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0.12, 100), Size = UDim2.fromOffset(900, 32), Parent = endScreen })
	local panel = Ui.panel({ AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0.12, 150), Size = UDim2.fromOffset(460, 330), Parent = endScreen })
	endStats = Ui.label({ Text = "", FontFace = F.Mono, TextSize = 20, RichText = true, TextYAlignment = Enum.TextYAlignment.Top, Position = UDim2.fromOffset(20, 16), Size = UDim2.new(1, -40, 1, -32), Parent = panel })

	restartButton = Ui.button({ Name = "RestartButton", Text = "RESTART", Size = UDim2.fromOffset(220, 58), AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, -120, 0.12, 500), Parent = endScreen })
	retryButton = Ui.button({ Name = "RetryButton", Text = "RETRY WAVE", Size = UDim2.fromOffset(220, 58), AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 120, 0.12, 500), Parent = endScreen })
	restartButton.Activated:Connect(function()
		(remotes:WaitForChild("Restart") :: RemoteEvent):FireServer()
	end)
	retryButton.Activated:Connect(function()
		(remotes:WaitForChild("RetryWave") :: RemoteEvent):FireServer()
	end)
end

local bannerToken = 0
function Screens.banner(main: string, sub: string, duration: number, color: Color3?)
	bannerToken += 1
	local my = bannerToken
	bannerMain.Text = main
	bannerMain.TextColor3 = color or C.Amber
	bannerSub.Text = sub
	banner.Visible = true
	local scale = banner:FindFirstChildOfClass("UIScale") or Ui.new("UIScale", { Parent = banner })
	scale.Scale = 1.4
	TweenService:Create(scale, TweenInfo.new(0.3, Enum.EasingStyle.Back, Enum.EasingDirection.Out), { Scale = 1 }):Play()
	task.delay(duration, function()
		if bannerToken == my then
			banner.Visible = false
		end
	end)
end

local KIND_LABELS = {
	Infantry = "INFANTRY",
	Buggy = "BUGGIES",
	Tank = "TANKS",
	Helicopter = "HELICOPTERS",
	Jet = "JETS",
	SiegeCrawler = "SIEGE CRAWLER",
}
local KIND_ORDER = { "Infantry", "Buggy", "Tank", "Helicopter", "Jet", "SiegeCrawler" }

-- One kill type per line, aligned, in threat order.
local function formatKills(kills: { [string]: number }): string
	local lines = {}
	for _, kind in KIND_ORDER do
		local count = kills[kind]
		if count and count > 0 then
			table.insert(lines, string.format("  %-14s %d", KIND_LABELS[kind], count))
		end
	end
	return if #lines > 0 then "KILLS\n" .. table.concat(lines, "\n") else "KILLS         NONE"
end

local function showEnd(victory: boolean, stats: any)
	endScreen.Visible = true
	endTitle.Text = if victory then "MESA HELD!" else "OUTPOST LOST"
	endTitle.TextColor3 = if victory then C.Amber else C.Red
	endSub.Text = if victory
		then "All waves repelled. The Red Mesa stands."
		else string.format("Overrun on wave %d of %d", stats.wave, stats.totalWaves)
	endStats.Text = table.concat({
		string.format("FINAL SCORE   <font color='#FFB224'>%d</font>", stats.score),
		string.format("WAVE REACHED  %d / %d", stats.wave, stats.totalWaves),
		string.format("ACCURACY      %d%%", math.floor(stats.accuracy * 100 + 0.5)),
		string.format("BEST COMBO    x%d", stats.bestCombo),
		string.format("SESSION BEST  %d", stats.sessionBest),
		"",
		formatKills(stats.kills),
	}, "\n")
	retryButton.Visible = not victory
	restartButton.Text = if victory then "PLAY AGAIN" else "RESTART"
	restartButton.Position = if victory then UDim2.new(0.5, 0, 0.12, 500) else UDim2.new(0.5, -120, 0.12, 500)
end

function Screens.showWaveClear(payload: any)
	Screens.banner("WAVE " .. payload.wave .. " CLEAR", "", 3.5, C.Green)
	tallyRows.Text = table.concat({
		string.format("HOSTILES DOWN    %d", payload.kills),
		string.format("WAVE SCORE       %d", payload.waveScore),
		string.format("CLEAR BONUS      +%d", payload.clearBonus),
		string.format("INTEGRITY BONUS  +%d", payload.integrityBonus),
		string.format("REPAIRS          <font color='#7ED250'>+%d%%</font>", math.floor(payload.repaired + 0.5)),
	}, "\n")
	tallyNextBase = if payload.nextWave then string.format("NEXT: WAVE %d · %s", payload.nextWave, payload.nextHint or "") else "FINAL WAVE HELD"
	tallyNext.Text = tallyNextBase
	tally.Visible = true
end

function Screens.start()
	gui = Ui.new("ScreenGui", {
		Name = "Screens",
		IgnoreGuiInset = true,
		ResetOnSpawn = false,
		DisplayOrder = 5,
		Parent = Players.LocalPlayer:WaitForChild("PlayerGui"),
	})
	buildTitle()
	buildBanner()
	buildTally()
	buildEndScreen()
	game:GetService("RunService").RenderStepped:Connect(function()
		if tally.Visible and GameState.phase() == "Intermission" then
			tallyNext.Text = string.format("%s  ·  %ds", tallyNextBase, math.ceil(Screens.phaseRemaining()))
		end
	end)

	GameState.onEvent("WaveStart", function(p)
		Screens.banner(string.format("WAVE %d", p.wave), p.hint or "", 3)
	end)
	GameState.onEvent("WaveClear", Screens.showWaveClear)
	GameState.onEvent("Defeat", function(stats)
		task.delay(2.5, function()
			if GameState.phase() == "Defeat" then
				showEnd(false, stats)
			end
		end)
	end)
	GameState.onEvent("Victory", function(stats)
		Screens.banner("VICTORY", "The Red Mesa holds", 3, C.Amber)
		task.delay(2.5, function()
			if GameState.phase() == "Victory" then
				showEnd(true, stats)
			end
		end)
	end)
end

-- Syncs which screens are visible with the current phase.
function Screens.applyPhase(phase: string)
	title.Visible = phase == "Title"
	if phase ~= "Intermission" then
		tally.Visible = false
	end
	if phase ~= "Defeat" and phase ~= "Victory" then
		endScreen.Visible = false
	end
	if phase == "Defeat" then
		Screens.banner("OUTPOST LOST", "", 2.4, C.Red)
	end
end

-- Blocks until the generated battlefield has replicated to this client
-- (terrain at the far end of the basin, the emplacement, fonts and the sound
-- sheet), or a safety timeout passes, so the title never offers a half-built
-- world. Terrain meshing can still lag a little behind on slow machines.
function Screens.waitForWorld()
	local started = os.clock()
	local probes = {
		Vector3.new(0, -4, -1100),
		Vector3.new(-600, -4, -400),
		Vector3.new(600, -4, -400),
		Vector3.new(0, 40, 0),
	}
	local function terrainReady(): boolean
		for _, p in probes do
			local region = Region3.new(p - Vector3.new(2, 2, 2), p + Vector3.new(2, 2, 2)):ExpandToGrid(4)
			local ok, materials = pcall(function()
				return Workspace.Terrain:ReadVoxels(region, 4)
			end)
			if not ok or materials[1][1][1] == Enum.Material.Air then
				return false
			end
		end
		return Workspace:FindFirstChild("Battlefield") ~= nil
	end
	while not terrainReady() and os.clock() - started < 45 do
		task.wait(0.5)
	end
	pcall(function()
		local ContentProvider = game:GetService("ContentProvider")
		local sheet = Instance.new("Sound")
		sheet.SoundId = require(script.Parent.SfxSheet).SoundId
		ContentProvider:PreloadAsync({ sheet, title })
		sheet:Destroy()
	end)
	-- Give the renderer a moment to mesh what just arrived.
	local minimum = 3
	local elapsed = os.clock() - started
	if elapsed < minimum then
		task.wait(minimum - elapsed)
	end
end

-- Seconds left in the current phase (for countdowns).
function Screens.phaseRemaining(): number
	local endsAt = GameState.get("PhaseEndsAt") or 0
	return math.max(0, endsAt - Workspace:GetServerTimeNow())
end

return Screens
