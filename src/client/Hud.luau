--!strict
-- In-combat HUD: integrity, weapon strip + heat, wave/score/combo, radar,
-- crosshair, hit markers, damage direction indicators and the low-integrity
-- vignette. Only visible while the player is in the turret. Panels, bars
-- and the radar come from the LOOK-2 kit (UiKit, UiKitRadar).
--
-- MOBILE-1: both roots are scaled to the device (UiScale). Full-screen
-- layers, the top bar, tips and markers sit in `root` (whole screen); the
-- corner panels, the weapon strip and the touch controls sit in `safeRoot`,
-- a second ScreenGui inside the device safe area (notches, home
-- indicator). Touch mode moves the integrity panel under Roblox's top bar
-- (top left) and the radar to the top right, clearing the bottom corners
-- for the FIRE buttons.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local StarterGui = game:GetService("StarterGui")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")
local FrameProfile = require(script.Parent.FrameProfile)

local Config = require(ReplicatedStorage.Shared.Config)
local AimController = require(script.Parent.AimController)
local GameState = require(script.Parent.GameState)
local InputMode = require(script.Parent.InputMode)
local Sfx = require(script.Parent.Sfx)
local Ui = require(script.Parent.Ui)
local UiKit = require(script.Parent.UiKit)
local UiKitRadar = require(script.Parent.UiKitRadar)
local UiScale = require(script.Parent.UiScale)
local WeaponHud = require(script.Parent.WeaponHud)

local Hud = {}

local C = Ui.Colors
local F = Ui.Fonts
local RADAR_SIZE = 206
local RADAR_SIZE_TOUCH = 170
local INDICATOR_RADIUS = 175

local gui: ScreenGui
local root: Frame
local safeGui: ScreenGui
local safeRoot: Frame
local refs: { [string]: any } = {}
local integrityBar: UiKit.Bar

local function build()
	gui = Ui.new("ScreenGui", {
		Name = "Hud",
		-- The whole screen, notch and home-indicator strips included.
		ScreenInsets = Enum.ScreenInsets.None,
		ClipToDeviceSafeArea = false,
		ResetOnSpawn = false,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = Players.LocalPlayer:WaitForChild("PlayerGui"),
	})
	root = Ui.new("Frame", { Name = "Root", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = gui })
	UiScale.attach(root)
	safeGui = Ui.new("ScreenGui", {
		Name = "HudSafe",
		ScreenInsets = Enum.ScreenInsets.DeviceSafeInsets,
		ClipToDeviceSafeArea = false,
		DisplayOrder = 1,
		ResetOnSpawn = false,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = Players.LocalPlayer:WaitForChild("PlayerGui"),
	})
	safeRoot = Ui.new("Frame", { Name = "Root", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = safeGui })
	UiScale.attach(safeRoot)

	-- Low-integrity vignette: four red edge bands fading toward the centre
	-- (behind everything else), plus the damage flash.
	refs.vignetteFrame = Ui.new("CanvasGroup", {
		Name = "LowIntegrity",
		BackgroundTransparency = 1,
		GroupTransparency = 1,
		Size = UDim2.fromScale(1, 1),
		Parent = root,
	})
	local edges = {
		{ UDim2.fromScale(1, 0.22), UDim2.fromScale(0, 0), 90 },
		{ UDim2.fromScale(1, 0.22), UDim2.fromScale(0, 0.78), -90 },
		{ UDim2.fromScale(0.16, 1), UDim2.fromScale(0, 0), 0 },
		{ UDim2.fromScale(0.16, 1), UDim2.fromScale(0.84, 0), 180 },
	}
	for _, e in edges do
		Ui.new("Frame", {
			BackgroundColor3 = C.Red,
			BorderSizePixel = 0,
			Size = e[1],
			Position = e[2],
			Parent = refs.vignetteFrame,
		}, {
			Ui.new("UIGradient", {
				Rotation = e[3],
				Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(1, 1) }),
			}),
		})
	end
	refs.flash = Ui.new("Frame", {
		Name = "DamageFlash",
		BackgroundColor3 = C.Red,
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		Size = UDim2.fromScale(1, 1),
		Parent = root,
	})

	-- Top bar: wave, score, combo.
	local top = UiKit.panel({ Name = "Top", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 12), Size = UDim2.fromOffset(520, 56), Parent = root }, { brackets = true, stripe = true })
	refs.wave = Ui.label({ Name = "Wave", Text = "WAVE 1/10", FontFace = F.Header, TextSize = 26, TextColor3 = C.Amber, Position = UDim2.fromOffset(18, 2), Size = UDim2.new(0, 170, 1, 0), Parent = top })
	refs.score = Ui.label({ Name = "Score", Text = "0", FontFace = F.Mono, TextSize = 30, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 2), Size = UDim2.new(0, 180, 1, 0), Parent = top })
	refs.combo = Ui.label({ Name = "Combo", Text = "x1", FontFace = F.Header, TextSize = 30, TextColor3 = C.Text, TextXAlignment = Enum.TextXAlignment.Right, AnchorPoint = Vector2.new(1, 0), Position = UDim2.new(1, -18, 0, 2), Size = UDim2.new(0, 120, 1, 0), Parent = top })
	refs.comboScale = Ui.new("UIScale", { Parent = refs.combo })
	refs.remaining = Ui.label({ Name = "Remaining", Text = "", FontFace = F.Label, TextSize = 16, TextColor3 = C.Text, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 1, 7), Size = UDim2.fromOffset(300, 20), Parent = top })
	Ui.outline(refs.remaining)

	-- Integrity (bottom left): segmented bar with a lagging damage ghost.
	local integrity = UiKit.panel({ Name = "Integrity", AnchorPoint = Vector2.new(0, 1), Position = UDim2.new(0, 16, 1, -16), Size = UDim2.fromOffset(300, 72), Parent = safeRoot }, { stripe = true })
	refs.integrity = integrity
	Ui.label({ Text = "OUTPOST INTEGRITY", FontFace = F.Label, TextSize = 16, TextColor3 = C.Olive, Position = UDim2.fromOffset(14, 10), Size = UDim2.fromOffset(200, 18), Parent = integrity })
	refs.integrityText = Ui.label({ Text = "100%", FontFace = F.Mono, TextSize = 20, TextXAlignment = Enum.TextXAlignment.Right, Position = UDim2.new(1, -94, 0, 8), Size = UDim2.fromOffset(80, 22), Parent = integrity })
	integrityBar = UiKit.bar(integrity, { Position = UDim2.fromOffset(12, 34), Size = UDim2.new(1, -24, 0, 26) }, { color = C.Olive, segments = 10, ghost = Color3.fromRGB(255, 226, 170), rate = 10 })

	-- Radar (bottom right): the 270 degree arc, rotated to the aim direction.
	refs.radar = UiKitRadar.build(safeRoot, RADAR_SIZE)

	WeaponHud.build(root, safeRoot)

	refs.indicators = Ui.new("Frame", { Name = "DamageIndicators", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = root })
	refs.popups = Ui.new("Frame", { Name = "Popups", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = root })

	refs.tip = UiKit.panel({ Name = "Tip", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 104), Size = UDim2.fromOffset(540, 46), Visible = false, Parent = root }, { stripe = true, solid = true })
	refs.tipText = Ui.label({ Text = "", FontFace = F.Label, TextSize = 20, TextXAlignment = Enum.TextXAlignment.Center, RichText = true, Position = UDim2.fromOffset(12, 2), Size = UDim2.new(1, -24, 1, 0), Parent = refs.tip })
end

-- Desktop or touch placement of the corner panels, the strip and the tip.
local function layout()
	local touch = InputMode.isTouch()
	local integrity = refs.integrity :: GuiObject
	local radar = refs.radar :: GuiObject
	if touch then
		integrity.AnchorPoint = Vector2.new(0, 0)
		integrity.Position = UDim2.fromOffset(16, UiScale.topbar() + 6)
		integrity.Size = UDim2.fromOffset(240, 72)
		radar.AnchorPoint = Vector2.new(1, 0)
		radar.Position = UDim2.new(1, -16, 0, 12)
		radar.Size = UDim2.fromOffset(RADAR_SIZE_TOUCH, RADAR_SIZE_TOUCH)
	else
		integrity.AnchorPoint = Vector2.new(0, 1)
		integrity.Position = UDim2.new(0, 16, 1, -16)
		integrity.Size = UDim2.fromOffset(300, 72)
		radar.AnchorPoint = Vector2.new(1, 1)
		radar.Position = UDim2.new(1, -16, 1, -16)
		radar.Size = UDim2.fromOffset(RADAR_SIZE, RADAR_SIZE)
	end
	refs.tip.Size = UDim2.fromOffset(if touch then 480 else 540, 46)
	WeaponHud.layout(touch)
end

local function pulseCombo()
	refs.comboScale.Scale = 1.6
	TweenService:Create(refs.comboScale, TweenInfo.new(0.35, Enum.EasingStyle.Back, Enum.EasingDirection.Out), { Scale = 1 }):Play()
end

local lastMultiplier = 1
local function refreshStats()
	local wave = GameState.get("Wave") or 0
	local total = GameState.get("TotalWaves") or 0
	refs.wave.Text = string.format("WAVE %d/%d", wave, total)
	refs.score.Text = tostring(GameState.get("Score") or 0)
	local mult = GameState.get("Multiplier") or 1
	refs.combo.Text = "x" .. mult
	refs.combo.TextColor3 = if mult > 1 then C.Amber else C.Text
	if mult > lastMultiplier then
		pulseCombo()
	end
	lastMultiplier = mult

	local integrity = GameState.get("Integrity") or 100
	local frac = integrity / Config.Integrity.MAX
	refs.integrityText.Text = string.format("%d%%", math.ceil(integrity))
	UiKit.setBar(integrityBar, frac)
	integrityBar.fill.ImageColor3 = if integrity <= Config.Integrity.LOW_THRESHOLD then C.Red elseif integrity <= 60 then C.Amber else C.Olive
	refs.integrityText.TextColor3 = if integrity <= Config.Integrity.LOW_THRESHOLD then C.Red else C.Text
end

local function updateVignette()
	local integrity = GameState.get("Integrity") or 100
	local group = refs.vignetteFrame :: CanvasGroup
	local inWave = GameState.phase() == "Wave"
	local low = integrity <= Config.Integrity.LOW_THRESHOLD and inWave
	-- Hidden, not just transparent, when unused: a full-screen CanvasGroup
	-- still costs GPU at GroupTransparency 1 (LOOK-5 A/B).
	group.Visible = low
	if low then
		group.GroupTransparency = 0.35 + 0.25 * math.sin(os.clock() * 6)
	else
		group.GroupTransparency = 1
	end
	Sfx.setLoop("Alarm", inWave and integrity <= Config.Integrity.ALARM_THRESHOLD)
end

Hud.showHitMarker = WeaponHud.showHitMarker

function Hud.scorePopup(worldPos: Vector3, text: string)
	local camera = Workspace.CurrentCamera
	local point, onScreen = camera:WorldToScreenPoint(worldPos)
	if not onScreen then
		return
	end
	local screen = UiScale.fromScreen(root, Vector2.new(point.X, point.Y))
	local label = Ui.label({
		Text = text,
		FontFace = F.Header,
		TextSize = 24,
		TextColor3 = C.Amber,
		TextXAlignment = Enum.TextXAlignment.Center,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromOffset(screen.X, screen.Y),
		Size = UDim2.fromOffset(120, 30),
		Parent = refs.popups,
	})
	Ui.outline(label, 2)
	local scale = Ui.new("UIScale", { Scale = 0.6, Parent = label })
	UiKit.tween(scale, 0.18, { Scale = 1 }, Enum.EasingStyle.Back)
	TweenService:Create(label, TweenInfo.new(0.9, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
		Position = UDim2.fromOffset(screen.X, screen.Y - 60),
		TextTransparency = 1,
	}):Play()
	task.delay(0.95, function()
		label:Destroy()
	end)
end

-- Red arc at the screen edge pointing toward the damage source: eases in
-- from further out, holds, then fades as it settles inward.
function Hud.damageIndicator(from: Vector3, heavy: boolean)
	local camera = Workspace.CurrentCamera
	local look = camera.CFrame.LookVector
	local toSource = from - camera.CFrame.Position
	local angle = math.atan2(toSource.X, -toSource.Z) - math.atan2(look.X, -look.Z)
	local function at(radius: number): UDim2
		return UDim2.new(0.5, math.sin(angle) * radius, 0.5, -math.cos(angle) * radius)
	end
	local size = if heavy then Vector2.new(160, 50) else Vector2.new(118, 37)
	local wedge = UiKit.sprite("wedge", {
		Name = "DamageArc",
		ImageColor3 = C.Red,
		ImageTransparency = 1,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = at(INDICATOR_RADIUS + 40),
		Rotation = math.deg(angle),
		Size = UDim2.fromOffset(size.X * 1.25, size.Y * 1.25),
		Parent = refs.indicators,
	})
	UiKit.tween(wedge, 0.16, {
		ImageTransparency = 0,
		Position = at(INDICATOR_RADIUS),
		Size = UDim2.fromOffset(size.X, size.Y),
	}, Enum.EasingStyle.Back)
	task.delay(if heavy then 0.55 else 0.35, function()
		UiKit.tween(wedge, 0.75, { ImageTransparency = 1, Position = at(INDICATOR_RADIUS - 18) }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
	end)
	task.delay(1.4, function()
		wedge:Destroy()
	end)

	local flash = refs.flash :: Frame
	flash.BackgroundTransparency = if heavy then 0.55 else 0.8
	TweenService:Create(flash, TweenInfo.new(0.35), { BackgroundTransparency = 1 }):Play()
end

-- Tip row: under the top bar, or under the boss bar while it is up.
local function tipY(): number
	local threats = root:FindFirstChild("Threats")
	local boss = threats and threats:FindFirstChild("BossBar")
	return if boss and (boss :: GuiObject).Visible then 236 else 104
end

local tipToken = 0
function Hud.showTip(text: string, duration: number?)
	tipToken += 1
	local my = tipToken
	local tip = refs.tip :: ImageLabel
	local y = tipY()
	refs.tipText.Text = text
	tip.Visible = true
	tip.Position = UDim2.new(0.5, 0, 0, y - 16)
	tip.ImageTransparency = 0.6
	refs.tipText.TextTransparency = 1
	UiKit.tween(tip, 0.3, { Position = UDim2.new(0.5, 0, 0, y), ImageTransparency = 0 }, Enum.EasingStyle.Quint)
	UiKit.tween(refs.tipText, 0.3, { TextTransparency = 0 })
	-- The boss bar can arrive a moment after the boss tip: step aside then.
	task.delay(0.4, function()
		if tipToken == my and tipY() ~= y then
			y = tipY()
			UiKit.tween(tip, 0.3, { Position = UDim2.new(0.5, 0, 0, y) }, Enum.EasingStyle.Quint)
		end
	end)
	task.delay(duration or 5, function()
		if tipToken == my then
			UiKit.tween(refs.tipText, 0.2, { TextTransparency = 1 })
			UiKit.tween(tip, 0.25, { Position = UDim2.new(0.5, 0, 0, y - 12), ImageTransparency = 1 }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
			task.delay(0.26, function()
				if tipToken == my then
					tip.Visible = false
				end
			end)
		end
	end)
end

-- Shows a tip only the first time `key` is used this session.
local tipsShown: { [string]: boolean } = {}
function Hud.tipOnce(key: string, text: string, duration: number?)
	if tipsShown[key] then
		return
	end
	tipsShown[key] = true
	Hud.showTip(text, duration)
end

function Hud.getRoot(): Frame
	return root
end

-- The safe-area root (corner panels, weapon strip, touch controls).
function Hud.getSafeRoot(): Frame
	return safeRoot
end

function Hud.setVisible(visible: boolean)
	root.Visible = visible
	safeRoot.Visible = visible
end

-- Single-player game: Roblox's player list only covers the top-right of
-- the view, so hide it (retried: CoreGui may not be ready at startup).
local function hidePlayerList()
	for _ = 1, 20 do
		local ok = pcall(StarterGui.SetCoreGuiEnabled, StarterGui, Enum.CoreGuiType.PlayerList, false)
		if ok and not StarterGui:GetCoreGuiEnabled(Enum.CoreGuiType.PlayerList) then
			return
		end
		task.wait(0.5)
	end
	warn("[RedMesa] could not hide the player list")
end

function Hud.start()
	task.spawn(hidePlayerList)
	UiKit.start()
	build()
	layout()
	UiScale.changed(layout)
	Hud.setVisible(false)
	for _, attr in { "Wave", "TotalWaves", "Score", "Multiplier", "Integrity" } do
		GameState.onChanged(attr, refreshStats)
	end
	refreshStats()
	UiKit.snapBar(integrityBar, (GameState.get("Integrity") or 100) / Config.Integrity.MAX)
	-- A new run or a retried wave refills the bar at once (no drain ghost).
	GameState.onEvent("WaveStart", function()
		UiKit.snapBar(integrityBar, (GameState.get("Integrity") or 100) / Config.Integrity.MAX)
	end)
	RunService.RenderStepped:Connect(FrameProfile.wrap("Hud", function(dt)
		if not root.Visible then
			return
		end
		WeaponHud.update(dt)
		UiKitRadar.update(dt, (AimController.getAngles()))
		UiKit.stepBar(integrityBar, dt)
		updateVignette()
		local remaining = GameState.get("Remaining") or 0
		refs.remaining.Text = if GameState.phase() == "Wave" then string.format("HOSTILES REMAINING: %d", remaining) else ""
	end))
end

return Hud
