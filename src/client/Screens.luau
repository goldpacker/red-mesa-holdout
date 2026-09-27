--!strict
-- Full-screen and banner UI: title, wave banners, intermission tally,
-- defeat and victory screens. LOOK-2: kit panels and buttons (UiKit),
-- banners that slide in and out between stencilled stripes, a tally that
-- reveals its rows and counts them up, and end screens whose title lands,
-- stats count up and buttons rise in. LOOK-4: the title shows the Blender
-- key art (an airdrop over the basin at sunset) under the stencilled metal
-- logo (UiKitArt); both are released when the game starts.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local GameState = require(script.Parent.GameState)
local Ui = require(script.Parent.Ui)
local UiKit = require(script.Parent.UiKit)
local UiKitArt = require(script.Parent.UiKitArt)

local Screens = {}

local C = Ui.Colors
local F = Ui.Fonts
local remotes = ReplicatedStorage:WaitForChild("Remotes")

local BANNER_Y = 0.36
local END_TOP = 0.12

type Row = { label: TextLabel, value: TextLabel }

local gui: ScreenGui
local title: Frame
-- LOOK-4 title art: the key art backdrop and the metal logo (title only;
-- released when the game starts), with the text title as their fallback.
local backdrop: UiKitArt.Backdrop? = nil
local logo: ImageLabel? = nil
local logoSlide = { inst = nil :: GuiObject?, delay = 0 }
local titleText: { TextLabel } = {}
local titleParts: { { inst: GuiObject?, delay: number } } = {}
local banner: CanvasGroup
local bannerMain: TextLabel
local bannerSub: TextLabel
local bannerStripes: { ImageLabel } = {}
local tally: ImageLabel
local tallyRows: { Row } = {}
local tallyNext: TextLabel
local endScreen: Frame
local endTitle: TextLabel
local endTitleScale: UIScale
local endSub: TextLabel
local endPanel: ImageLabel
local endRows: { Row } = {}
local endKillsHeader: TextLabel
local endKills: { Row } = {}
local retryButton: ImageButton
local restartButton: ImageButton
local tallyNextBase = ""
local tallyCountdown = true -- false after the last wave (victory follows, not a wave)

-- Label + right-aligned value on one line inside `parent`.
local function row(parent: Instance, y: number, width: number, textSize: number?): Row
	local size = textSize or 20
	return {
		label = Ui.label({ Text = "", FontFace = F.Label, TextSize = size - 1, TextColor3 = C.Text, Position = UDim2.fromOffset(20, y), Size = UDim2.fromOffset(width * 0.62, size + 4), Parent = parent }),
		value = Ui.label({ Text = "", FontFace = F.Mono, TextSize = size, TextColor3 = C.Text, TextXAlignment = Enum.TextXAlignment.Right, Position = UDim2.fromOffset(width - 20 - width * 0.4, y), Size = UDim2.fromOffset(width * 0.4, size + 4), Parent = parent }),
	}
end

local function titleSlide(inst: GuiObject, delay: number)
	table.insert(titleParts, { inst = inst, delay = delay })
end

local function buildTitle()
	-- Hidden until applyPhase("Title"), which plays the intro.
	title = Ui.new("Frame", { Name = "Title", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Visible = false, Parent = gui })
	Ui.new("Frame", {
		Name = "Shade",
		BackgroundColor3 = Color3.fromRGB(8, 9, 5),
		BackgroundTransparency = 0.5,
		BorderSizePixel = 0,
		Size = UDim2.new(0, 580, 1, 0),
		Parent = title,
	}, {
		Ui.new("UIGradient", { Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(0.75, 0.3), NumberSequenceKeypoint.new(1, 1) }) }),
	})
	local name = Ui.label({ Text = "RED MESA", FontFace = F.Header, TextSize = 92, TextColor3 = C.Amber, Position = UDim2.new(0, 60, 0.18, 0), Size = UDim2.fromOffset(600, 96), Parent = title })
	Ui.outline(name, 3)
	titleSlide(name, 0)
	local name2 = Ui.label({ Text = "HOLDOUT", FontFace = F.Header, TextSize = 72, TextColor3 = C.Text, Position = UDim2.new(0, 64, 0.18, 88), Size = UDim2.fromOffset(600, 76), Parent = title })
	Ui.outline(name2, 3)
	titleSlide(name2, 0.06)
	titleText = { name, name2 }
	table.insert(titleParts, logoSlide)
	local rule = Ui.new("ImageLabel", {
		Name = "Rule",
		BackgroundTransparency = 1,
		Image = UiKit.Assets.strip,
		ImageColor3 = C.Amber,
		ScaleType = Enum.ScaleType.Tile,
		TileSize = UDim2.fromOffset(64, 8),
		Position = UDim2.new(0, 66, 0.18, 164),
		Size = UDim2.fromOffset(380, 8),
		Parent = title,
	})
	titleSlide(rule, 0.1)
	local tagline = Ui.label({ Text = "HOLD THE MESA. SURVIVE 10 WAVES.", FontFace = F.Label, TextSize = 22, TextColor3 = C.Olive, Position = UDim2.new(0, 68, 0.18, 176), Size = UDim2.fromOffset(500, 26), Parent = title })
	Ui.outline(tagline)
	titleSlide(tagline, 0.12)

	local card = UiKit.panel({ Name = "Controls", Position = UDim2.new(0, 64, 0.18, 222), Size = UDim2.fromOffset(390, 200), Parent = title }, { brackets = true, stripe = true })
	titleSlide(card, 0.2)
	Ui.label({ Text = "CONTROLS", FontFace = F.HeaderBold, TextSize = 20, TextColor3 = C.Amber, Position = UDim2.fromOffset(16, 12), Size = UDim2.fromOffset(200, 22), Parent = card })
	local rows = {
		{ "MOUSE", "Aim turret" },
		{ "LEFT MOUSE", "Fire" },
		{ "RIGHT MOUSE (HOLD)", "Gunsight view" },
		{ "1 / 2 / 3", "Machine gun / Rockets / AA" },
		{ "MOUSE WHEEL", "Cycle weapons" },
	}
	for i, r in rows do
		local y = 42 + (i - 1) * 30
		if i > 1 then
			Ui.new("Frame", { Name = "Divider", BackgroundColor3 = C.OliveDark, BackgroundTransparency = 0.3, BorderSizePixel = 0, Position = UDim2.fromOffset(14, y - 3), Size = UDim2.new(1, -28, 0, 1), Parent = card })
		end
		Ui.label({ Text = r[1], FontFace = F.Label, TextSize = 17, TextColor3 = C.Amber, Position = UDim2.fromOffset(16, y), Size = UDim2.fromOffset(170, 24), Parent = card })
		Ui.label({ Text = r[2], FontFace = F.Body, TextSize = 17, Position = UDim2.fromOffset(190, y), Size = UDim2.fromOffset(190, 24), Parent = card })
	end

	local start = UiKit.button({ Name = "StartButton", Position = UDim2.new(0, 68, 0.18, 442), Size = UDim2.fromOffset(240, 64), Parent = title }, "LOADING…", 36)
	titleSlide(start, 0.28)
	local startLabel = start:FindFirstChild("Label") :: TextLabel
	startLabel.TextColor3 = C.AmberDim -- dim until the world is ready
	start.Activated:Connect(function()
		if start:GetAttribute("Ready") then
			(remotes:WaitForChild("StartGame") :: RemoteEvent):FireServer()
		end
	end)
	local status = Ui.label({ Name = "LoadStatus", Text = "SURVEYING BATTLEFIELD…", FontFace = F.Label, TextSize = 16, TextColor3 = C.Olive, Position = UDim2.new(0, 70, 0.18, 514), Size = UDim2.fromOffset(400, 20), Parent = title })
	Ui.outline(status)
	task.spawn(function()
		Screens.waitForWorld()
		start:SetAttribute("Ready", true)
		startLabel.Text = "START"
		startLabel.TextColor3 = C.Amber
		status.Visible = false
		-- Ready: the button's brackets breathe until it is pressed.
		local brackets = start:FindFirstChild("Brackets") :: ImageLabel
		local pulse = TweenService:Create(brackets, TweenInfo.new(0.9, Enum.EasingStyle.Sine, Enum.EasingDirection.InOut, -1, true), { ImageTransparency = 0.55 })
		pulse:Play()
	end)
end

local function showTitleText(visible: boolean)
	for _, label in titleText do
		label.Visible = visible
	end
end

-- LOOK-4 title art (again whenever the title comes back after a release):
-- the key art under everything (the live title camera shows until it has
-- loaded, or for good if it never does) and the stencilled metal logo in
-- place of the text title (the text comes back if the logo never loads).
local function mountTitleArt()
	if not backdrop then
		backdrop = UiKitArt.backdrop(title, 0)
	end
	if logo then
		return
	end
	local image = UiKitArt.logo({ Position = UDim2.new(0, 50, 0.18, 4), Parent = title }, 520, function()
		showTitleText(false)
	end)
	logo = image
	logoSlide.inst = image
	if image then
		showTitleText(false)
		task.delay(8, function()
			if logo == image and not image.IsLoaded then
				showTitleText(true)
			end
		end)
	end
end

-- Staggered slide-in of the title elements (from the left, fading in).
local function playTitleIntro()
	for _, part in titleParts do
		local inst = part.inst
		if not (inst and inst.Parent) then
			continue
		end
		local target = inst:GetAttribute("Home") :: UDim2?
		if not target then
			target = inst.Position
			inst:SetAttribute("Home", target)
		end
		local home = target :: UDim2
		inst.Position = home - UDim2.fromOffset(60, 0)
		if inst:IsA("TextLabel") then
			inst.TextTransparency = 1
		elseif inst:IsA("ImageLabel") or inst:IsA("ImageButton") then
			inst.ImageTransparency = 1
		end
		task.delay(part.delay, function()
			UiKit.tween(inst, 0.45, { Position = home }, Enum.EasingStyle.Quint)
			if inst:IsA("TextLabel") then
				UiKit.tween(inst, 0.35, { TextTransparency = 0 })
			elseif inst:IsA("ImageLabel") or inst:IsA("ImageButton") then
				UiKit.tween(inst, 0.35, { ImageTransparency = 0 })
			end
		end)
	end
end

local function buildBanner()
	-- A CanvasGroup so the whole banner fades as one while it slides.
	banner = Ui.new("CanvasGroup", { Name = "Banner", BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, BANNER_Y), Size = UDim2.fromOffset(900, 150), GroupTransparency = 1, Visible = false, Parent = gui })
	Ui.new("Frame", {
		Name = "Band",
		BackgroundColor3 = Color3.fromRGB(14, 16, 10),
		BackgroundTransparency = 0.2,
		BorderSizePixel = 0,
		Position = UDim2.fromOffset(0, 18),
		Size = UDim2.new(1, 0, 0, 116),
		Parent = banner,
	}, {
		Ui.new("UIGradient", { Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.2, 0.15), NumberSequenceKeypoint.new(0.8, 0.15), NumberSequenceKeypoint.new(1, 1) }) }),
	})
	for _, y in { 14, 130 } do
		local stripe = Ui.new("ImageLabel", {
			Name = "Stripe",
			BackgroundTransparency = 1,
			Image = UiKit.Assets.strip,
			ImageColor3 = C.Amber,
			ScaleType = Enum.ScaleType.Tile,
			TileSize = UDim2.fromOffset(64, 8),
			AnchorPoint = Vector2.new(0.5, 0),
			Position = UDim2.new(0.5, 0, 0, y),
			Size = UDim2.new(0.6, 0, 0, 8),
			Parent = banner,
		}, {
			Ui.new("UIGradient", { Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.15, 0), NumberSequenceKeypoint.new(0.85, 0), NumberSequenceKeypoint.new(1, 1) }) }),
		})
		table.insert(bannerStripes, stripe)
	end
	bannerMain = Ui.label({ Name = "Main", Text = "", FontFace = F.Header, TextSize = 64, TextColor3 = C.Amber, TextXAlignment = Enum.TextXAlignment.Center, Position = UDim2.fromOffset(0, 24), Size = UDim2.new(1, 0, 0, 70), Parent = banner })
	Ui.outline(bannerMain, 3)
	bannerSub = Ui.label({ Name = "Sub", Text = "", FontFace = F.Label, TextSize = 26, TextXAlignment = Enum.TextXAlignment.Center, Position = UDim2.fromOffset(0, 94), Size = UDim2.new(1, 0, 0, 30), Parent = banner })
	Ui.outline(bannerSub, 2)
end

local function buildTally()
	tally = UiKit.panel({ Name = "Tally", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(460, 222), Visible = false, Parent = gui }, { brackets = true, stripe = true, solid = true })
	for i = 1, 5 do
		tallyRows[i] = row(tally, 16 + (i - 1) * 28, 460)
	end
	Ui.new("Frame", { Name = "Divider", BackgroundColor3 = C.OliveDark, BorderSizePixel = 0, Position = UDim2.new(0, 16, 1, -50), Size = UDim2.new(1, -32, 0, 2), Parent = tally })
	tallyNext = Ui.label({ Text = "", FontFace = F.HeaderBold, TextSize = 22, TextColor3 = C.Amber, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 1), Position = UDim2.new(0.5, 0, 1, -12), Size = UDim2.new(1, -20, 0, 28), Parent = tally })
end

local function buildEndScreen()
	endScreen = Ui.new("Frame", { Name = "EndScreen", BackgroundColor3 = Color3.new(0, 0, 0), BackgroundTransparency = 0.45, BorderSizePixel = 0, Size = UDim2.fromScale(1, 1), Visible = false, Parent = gui })
	endTitle = Ui.label({ Text = "", FontFace = F.Header, TextSize = 88, TextColor3 = C.Red, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.fromScale(0.5, END_TOP), Size = UDim2.fromOffset(900, 96), Parent = endScreen })
	Ui.outline(endTitle, 3)
	endTitleScale = Ui.new("UIScale", { Parent = endTitle })
	endSub = Ui.label({ Text = "", FontFace = F.Label, TextSize = 28, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, END_TOP, 100), Size = UDim2.fromOffset(900, 32), Parent = endScreen })
	Ui.outline(endSub, 2)
	endPanel = UiKit.panel({ Name = "Stats", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, END_TOP, 150), Size = UDim2.fromOffset(460, 330), Parent = endScreen }, { brackets = true, stripe = true, solid = true })
	for i = 1, 5 do
		endRows[i] = row(endPanel, 16 + (i - 1) * 27, 460)
	end
	endKillsHeader = Ui.label({ Text = "KILLS", FontFace = F.HeaderBold, TextSize = 18, TextColor3 = C.Amber, Position = UDim2.fromOffset(20, 158), Size = UDim2.fromOffset(200, 22), Parent = endPanel })
	Ui.new("Frame", { Name = "Divider", BackgroundColor3 = C.OliveDark, BorderSizePixel = 0, Position = UDim2.fromOffset(16, 152), Size = UDim2.new(1, -32, 0, 2), Parent = endPanel })
	for i = 1, 6 do
		endKills[i] = row(endPanel, 180 + (i - 1) * 22, 460, 18)
	end

	restartButton = UiKit.button({ Name = "RestartButton", Size = UDim2.fromOffset(220, 58), AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, -120, END_TOP, 500), Parent = endScreen }, "RESTART", 28)
	retryButton = UiKit.button({ Name = "RetryButton", Size = UDim2.fromOffset(220, 58), AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 120, END_TOP, 500), Parent = endScreen }, "RETRY WAVE", 28)
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
	local accent = color or C.Amber
	bannerMain.Text = main
	bannerMain.TextColor3 = accent
	bannerSub.Text = sub
	for _, stripe in bannerStripes do
		stripe.ImageColor3 = accent
		stripe.Size = UDim2.new(0, 0, 0, 8)
		UiKit.tween(stripe, 0.5, { Size = UDim2.new(0.6, 0, 0, 8) }, Enum.EasingStyle.Quint)
	end
	-- Slide in from the left, hold, slide out to the right.
	banner.Visible = true
	banner.GroupTransparency = 1
	banner.Position = UDim2.new(0.5, -140, BANNER_Y, 0)
	UiKit.tween(banner, 0.4, { Position = UDim2.fromScale(0.5, BANNER_Y), GroupTransparency = 0 }, Enum.EasingStyle.Quint)
	task.delay(math.max(0.5, duration - 0.3), function()
		if bannerToken == my then
			UiKit.tween(banner, 0.3, { Position = UDim2.new(0.5, 140, BANNER_Y, 0), GroupTransparency = 1 }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
		end
	end)
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

local function int(n: number): string
	return tostring(math.floor(n + 0.5))
end

-- Shows a row: label and value slide in after `delay`; numeric values count up.
local function showRow(r: Row, label: string, delay: number, target: number?, format: ((number) -> string)?, color: Color3?)
	r.label.Text = label
	r.label.Visible = true
	r.value.Visible = true
	r.value.TextColor3 = color or C.Text
	UiKit.revealText(r.label, delay)
	UiKit.revealText(r.value, delay, Vector2.new(14, 0))
	if target and format then
		UiKit.countUp(r.value, 0, target, 0.7, format, delay)
	else
		UiKit.stopCount(r.value)
	end
end

local function hideRow(r: Row)
	r.label.Visible = false
	r.value.Visible = false
end

local function showEnd(victory: boolean, stats: any)
	endScreen.Visible = true
	local accent = if victory then C.Amber else C.Red
	endTitle.Text = if victory then "MESA HELD!" else "OUTPOST LOST"
	endTitle.TextColor3 = accent
	endSub.Text = if victory
		then "All waves repelled. The Red Mesa stands."
		else string.format("Overrun on wave %d of %d", stats.wave, stats.totalWaves)
	for _, name in { "Brackets", "Stripe" } do
		local deco = endPanel:FindFirstChild(name)
		if deco and deco:IsA("ImageLabel") then
			deco.ImageColor3 = accent
		end
	end
	-- The title lands, then the subtitle, the stats (counting up) and the buttons.
	endScreen.BackgroundTransparency = 1
	UiKit.tween(endScreen, 0.5, { BackgroundTransparency = 0.45 })
	endTitleScale.Scale = 1.5
	endTitle.TextTransparency = 1
	UiKit.tween(endTitleScale, 0.45, { Scale = 1 }, Enum.EasingStyle.Back)
	UiKit.tween(endTitle, 0.25, { TextTransparency = 0 })
	UiKit.revealText(endSub, 0.25, Vector2.new(0, 10))
	endPanel.Position = UDim2.new(0.5, 0, END_TOP, 180)
	endPanel.ImageTransparency = 1
	task.delay(0.3, function()
		UiKit.tween(endPanel, 0.4, { Position = UDim2.new(0.5, 0, END_TOP, 150), ImageTransparency = 0 }, Enum.EasingStyle.Quint)
	end)
	local accuracy = math.floor(stats.accuracy * 100 + 0.5)
	showRow(endRows[1], "FINAL SCORE", 0.45, stats.score, int, C.Amber)
	showRow(endRows[2], "WAVE REACHED", 0.52)
	endRows[2].value.Text = string.format("%d / %d", stats.wave, stats.totalWaves)
	showRow(endRows[3], "ACCURACY", 0.59, accuracy, function(n)
		return int(n) .. "%"
	end)
	showRow(endRows[4], "BEST COMBO", 0.66)
	endRows[4].value.Text = "x" .. tostring(stats.bestCombo)
	showRow(endRows[5], "SESSION BEST", 0.73, stats.sessionBest, int)
	UiKit.revealText(endKillsHeader, 0.8)
	local n = 0
	for _, kind in KIND_ORDER do
		local count = stats.kills and stats.kills[kind]
		if count and count > 0 and n < #endKills then
			n += 1
			showRow(endKills[n], KIND_LABELS[kind], 0.8 + n * 0.06, count, int)
		end
	end
	if n == 0 then
		n = 1
		showRow(endKills[1], "NONE", 0.86)
		endKills[1].value.Text = ""
	end
	for i = n + 1, #endKills do
		hideRow(endKills[i])
	end

	retryButton.Visible = not victory
	local restartLabel = restartButton:FindFirstChild("Label") :: TextLabel
	restartLabel.Text = if victory then "PLAY AGAIN" else "RESTART"
	local restartX = if victory then 0 else -120
	for i, button in { restartButton, retryButton } do
		local x = if button == restartButton then restartX else 120
		local label = button:FindFirstChild("Label") :: TextLabel
		local brackets = button:FindFirstChild("Brackets") :: ImageLabel
		button.Position = UDim2.new(0.5, x, END_TOP, 530)
		button.ImageTransparency = 1
		label.TextTransparency = 1
		brackets.ImageTransparency = 1
		task.delay(0.9 + i * 0.08, function()
			UiKit.tween(button, 0.35, { Position = UDim2.new(0.5, x, END_TOP, 500), ImageTransparency = 0 }, Enum.EasingStyle.Back)
			UiKit.tween(label, 0.3, { TextTransparency = 0 })
			UiKit.tween(brackets, 0.3, { ImageTransparency = 0 })
		end)
	end
end

function Screens.showWaveClear(payload: any)
	Screens.banner("WAVE " .. payload.wave .. " CLEAR", "", 3.5, C.Green)
	local entries = {
		{ "HOSTILES DOWN", payload.kills, "", C.Text },
		{ "WAVE SCORE", payload.waveScore, "", C.Text },
		{ "CLEAR BONUS", payload.clearBonus, "+", C.Amber },
		{ "INTEGRITY BONUS", payload.integrityBonus, "+", C.Amber },
		{ "REPAIRS", math.floor(payload.repaired + 0.5), "+", C.Green },
	}
	for i, e in entries do
		local prefix, suffix = e[3], if i == 5 then "%" else ""
		showRow(tallyRows[i], e[1], 0.25 + i * 0.12, e[2], function(v)
			return prefix .. int(v) .. suffix
		end, e[4])
	end
	tallyCountdown = payload.nextWave ~= nil
	tallyNextBase = if payload.nextWave then string.format("NEXT: WAVE %d · %s", payload.nextWave, payload.nextHint or "") else "FINAL WAVE HELD"
	tallyNext.Text = tallyNextBase
	UiKit.revealText(tallyNext, 1.0, Vector2.new(0, 8))
	-- The panel rises into place and fades in.
	tally.Visible = true
	tally.Position = UDim2.new(0.5, 0, 0.5, 40)
	tally.ImageTransparency = 1
	UiKit.tween(tally, 0.4, { Position = UDim2.fromScale(0.5, 0.5), ImageTransparency = 0 }, Enum.EasingStyle.Quint)
end

function Screens.start()
	gui = Ui.new("ScreenGui", {
		Name = "Screens",
		IgnoreGuiInset = true,
		ResetOnSpawn = false,
		DisplayOrder = 5,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = Players.LocalPlayer:WaitForChild("PlayerGui"),
	})
	buildTitle()
	buildBanner()
	buildTally()
	buildEndScreen()
	game:GetService("RunService").RenderStepped:Connect(function()
		if tally.Visible and GameState.phase() == "Intermission" and tallyCountdown then
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

-- The key art and logo are only ever on the title: once the game starts
-- they are destroyed so their textures can leave memory during waves. The
-- text title stays as the fallback should the title come back.
local function releaseTitleArt()
	if backdrop then
		backdrop.release()
		backdrop = nil
	end
	if logo then
		logo:Destroy()
		logo = nil
		logoSlide.inst = nil
		showTitleText(true)
	end
end

-- Syncs which screens are visible with the current phase.
function Screens.applyPhase(phase: string)
	local wasTitle = title.Visible
	title.Visible = phase == "Title"
	if phase ~= "Title" then
		releaseTitleArt()
	end
	if phase == "Title" and not wasTitle then
		mountTitleArt()
		playTitleIntro()
	end
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
