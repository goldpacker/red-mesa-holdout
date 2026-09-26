--!strict
-- In-combat HUD: integrity, weapon strip + heat, wave/score/combo, radar,
-- crosshair, hit markers, damage direction indicators and the low-integrity
-- vignette. Only visible while the player is in the turret.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Aim = require(ReplicatedStorage.Shared.Aim)
local AimController = require(script.Parent.AimController)
local GameState = require(script.Parent.GameState)
local Ui = require(script.Parent.Ui)
local WeaponHud = require(script.Parent.WeaponHud)

local Hud = {}

local C = Ui.Colors
local F = Ui.Fonts
local RADAR_RANGE = 1000
local RADAR_SIZE = 190

local gui: ScreenGui
local root: Frame
local refs: { [string]: any } = {}

local function build()
	gui = Ui.new("ScreenGui", {
		Name = "Hud",
		IgnoreGuiInset = true,
		ResetOnSpawn = false,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
		Parent = Players.LocalPlayer:WaitForChild("PlayerGui"),
	})
	root = Ui.new("Frame", { Name = "Root", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = gui })

	-- Low-integrity vignette + damage flash (behind everything else).
	-- Low-integrity vignette: four red edge bands fading toward the centre.
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
	local top = Ui.panel({ Name = "Top", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 12), Size = UDim2.fromOffset(520, 56), Parent = root })
	refs.wave = Ui.label({ Name = "Wave", Text = "WAVE 1/10", FontFace = F.Header, TextSize = 26, TextColor3 = C.Amber, Position = UDim2.fromOffset(16, 0), Size = UDim2.new(0, 170, 1, 0), Parent = top })
	refs.score = Ui.label({ Name = "Score", Text = "0", FontFace = F.Mono, TextSize = 30, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.fromScale(0.5, 0), Size = UDim2.new(0, 180, 1, 0), Parent = top })
	refs.combo = Ui.label({ Name = "Combo", Text = "x1", FontFace = F.Header, TextSize = 30, TextColor3 = C.Text, TextXAlignment = Enum.TextXAlignment.Right, AnchorPoint = Vector2.new(1, 0), Position = UDim2.new(1, -16, 0, 0), Size = UDim2.new(0, 120, 1, 0), Parent = top })
	refs.comboScale = Ui.new("UIScale", { Parent = refs.combo })
	refs.remaining = Ui.label({ Name = "Remaining", Text = "", FontFace = F.Label, TextSize = 16, TextColor3 = C.Text, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 1, 4), Size = UDim2.fromOffset(300, 20), Parent = top })
	Ui.outline(refs.remaining)

	-- Integrity (bottom left).
	local integrity = Ui.panel({ Name = "Integrity", AnchorPoint = Vector2.new(0, 1), Position = UDim2.new(0, 16, 1, -16), Size = UDim2.fromOffset(300, 70), Parent = root })
	Ui.label({ Text = "OUTPOST INTEGRITY", FontFace = F.Label, TextSize = 16, TextColor3 = C.Olive, Position = UDim2.fromOffset(12, 6), Size = UDim2.fromOffset(200, 18), Parent = integrity })
	refs.integrityText = Ui.label({ Text = "100%", FontFace = F.Mono, TextSize = 20, TextXAlignment = Enum.TextXAlignment.Right, Position = UDim2.new(1, -92, 0, 4), Size = UDim2.fromOffset(80, 22), Parent = integrity })
	local barBack = Ui.new("Frame", { BackgroundColor3 = Color3.fromRGB(40, 20, 16), BorderSizePixel = 0, Position = UDim2.fromOffset(12, 32), Size = UDim2.new(1, -24, 0, 24), Parent = integrity })
	refs.integrityBar = Ui.new("Frame", { BackgroundColor3 = C.Olive, BorderSizePixel = 0, Size = UDim2.fromScale(1, 1), Parent = barBack })
	for i = 1, 9 do
		Ui.new("Frame", { BackgroundColor3 = C.Panel, BackgroundTransparency = 0.4, BorderSizePixel = 0, Position = UDim2.fromScale(i / 10, 0), Size = UDim2.new(0, 2, 1, 0), Parent = barBack })
	end

	-- Radar (bottom right): the 270 degree arc, rotated to the aim direction.
	local radar = Ui.panel({ Name = "Radar", AnchorPoint = Vector2.new(1, 1), Position = UDim2.new(1, -16, 1, -16), Size = UDim2.fromOffset(RADAR_SIZE + 16, RADAR_SIZE + 16), Parent = root })
	local disc = Ui.new("Frame", {
		Name = "Disc",
		BackgroundColor3 = Color3.fromRGB(20, 30, 14),
		BackgroundTransparency = 0.2,
		Position = UDim2.fromOffset(8, 8),
		Size = UDim2.fromOffset(RADAR_SIZE, RADAR_SIZE),
		ClipsDescendants = true,
		Parent = radar,
	}, {
		Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }),
		Ui.new("UIStroke", { Color = C.Olive, Thickness = 2 }),
	})
	for _, r in { 0.33, 0.66 } do
		Ui.new("Frame", {
			BackgroundTransparency = 1,
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.fromScale(r, r),
			Parent = disc,
		}, {
			Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }),
			Ui.new("UIStroke", { Color = C.OliveDark, Thickness = 1 }),
		})
	end
	-- Forward view cone marker.
	Ui.new("Frame", { Name = "ViewLine", BackgroundColor3 = C.Amber, BackgroundTransparency = 0.4, BorderSizePixel = 0, AnchorPoint = Vector2.new(0.5, 1), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.new(0, 2, 0.5, 0), Parent = disc })
	refs.radarDisc = disc
	refs.radarBlips = {}
	-- Rear dead zone marker; the container rotates about the disc centre.
	refs.radarBlocked = Ui.new("Frame", {
		Name = "RearArc",
		BackgroundTransparency = 1,
		Size = UDim2.fromScale(1, 1),
		Parent = disc,
	}, {
		Ui.new("Frame", {
			BackgroundColor3 = C.Red,
			BackgroundTransparency = 0.5,
			BorderSizePixel = 0,
			AnchorPoint = Vector2.new(0.5, 0),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.new(0, 3, 0.5, 0),
		}),
	})
	Ui.label({ Text = "RADAR", FontFace = F.Label, TextSize = 12, TextColor3 = C.Olive, Position = UDim2.fromOffset(10, 4), Size = UDim2.fromOffset(60, 14), Parent = radar })

	WeaponHud.build(root)

	refs.indicators = Ui.new("Frame", { Name = "DamageIndicators", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = root })
	refs.popups = Ui.new("Frame", { Name = "Popups", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = root })

	refs.tip = Ui.panel({ Name = "Tip", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 104), Size = UDim2.fromOffset(520, 44), Visible = false, Parent = root })
	refs.tipText = Ui.label({ Text = "", FontFace = F.Label, TextSize = 20, TextXAlignment = Enum.TextXAlignment.Center, RichText = true, Size = UDim2.fromScale(1, 1), Parent = refs.tip })
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
	refs.integrityBar.Size = UDim2.fromScale(frac, 1)
	refs.integrityBar.BackgroundColor3 = if integrity <= Config.Integrity.LOW_THRESHOLD then C.Red elseif integrity <= 60 then C.Amber else C.Olive
end

local function updateRadar()
	local yaw = AimController.getAngles()
	local seen: { [Instance]: boolean } = {}
	local enemies = Workspace:FindFirstChild("Enemies")
	if enemies then
		for _, model in enemies:GetChildren() do
			local rootPart = (model :: Model).PrimaryPart
			if not rootPart or model:GetAttribute("State") == "Dead" then
				continue
			end
			local offset = rootPart.Position - Config.TURRET_PIVOT
			local dist = Vector2.new(offset.X, offset.Z).Magnitude
			local rel = math.rad(Aim.yawTo(rootPart.Position) - yaw)
			local r = math.min(dist / RADAR_RANGE, 1) * 0.5
			local blip = refs.radarBlips[model]
			if not blip then
				local isAir = model:GetAttribute("IsAir") == true
				blip = Ui.new("Frame", {
					BackgroundColor3 = if isAir then Color3.fromRGB(90, 200, 255) else C.Red,
					BorderSizePixel = 0,
					AnchorPoint = Vector2.new(0.5, 0.5),
					Size = UDim2.fromOffset(6, 6),
					Parent = refs.radarDisc,
				}, { Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }) })
				refs.radarBlips[model] = blip
			end
			blip.Position = UDim2.fromScale(0.5 - math.sin(rel) * r, 0.5 - math.cos(rel) * r)
			seen[model] = true
		end
	end
	for model, blip in refs.radarBlips do
		if not seen[model] then
			blip:Destroy()
			refs.radarBlips[model] = nil
		end
	end
	-- Rear dead zone indicator: points behind the turret relative to aim.
	refs.radarBlocked.Rotation = yaw
end

local function updateVignette()
	local integrity = GameState.get("Integrity") or 100
	local group = refs.vignetteFrame :: CanvasGroup
	if integrity <= Config.Integrity.LOW_THRESHOLD and GameState.phase() == "Wave" then
		group.GroupTransparency = 0.35 + 0.25 * math.sin(os.clock() * 6)
	else
		group.GroupTransparency = 1
	end
end

Hud.showHitMarker = WeaponHud.showHitMarker

function Hud.scorePopup(worldPos: Vector3, text: string)
	local camera = Workspace.CurrentCamera
	local screen, onScreen = camera:WorldToViewportPoint(worldPos)
	if not onScreen then
		return
	end
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
	TweenService:Create(label, TweenInfo.new(0.9, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
		Position = UDim2.fromOffset(screen.X, screen.Y - 60),
		TextTransparency = 1,
	}):Play()
	task.delay(0.95, function()
		label:Destroy()
	end)
end

-- Red wedge at the screen edge pointing toward the damage source.
function Hud.damageIndicator(from: Vector3, heavy: boolean)
	local camera = Workspace.CurrentCamera
	local look = camera.CFrame.LookVector
	local toSource = from - camera.CFrame.Position
	local angle = math.atan2(toSource.X, -toSource.Z) - math.atan2(look.X, -look.Z)
	local radius = 180
	local wedge = Ui.new("Frame", {
		BackgroundColor3 = C.Red,
		BackgroundTransparency = 0.1,
		BorderSizePixel = 0,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.new(0.5, math.sin(angle) * radius, 0.5, -math.cos(angle) * radius),
		Rotation = math.deg(angle),
		Size = UDim2.fromOffset(if heavy then 90 else 60, if heavy then 14 else 8),
		Parent = refs.indicators,
	}, { Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }) })
	TweenService:Create(wedge, TweenInfo.new(1.1), { BackgroundTransparency = 1 }):Play()
	task.delay(1.15, function()
		wedge:Destroy()
	end)

	local flash = refs.flash :: Frame
	flash.BackgroundTransparency = if heavy then 0.55 else 0.8
	TweenService:Create(flash, TweenInfo.new(0.35), { BackgroundTransparency = 1 }):Play()
end

local tipToken = 0
function Hud.showTip(text: string, duration: number?)
	tipToken += 1
	local my = tipToken
	refs.tipText.Text = text
	refs.tip.Visible = true
	task.delay(duration or 5, function()
		if tipToken == my then
			refs.tip.Visible = false
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

function Hud.setVisible(visible: boolean)
	root.Visible = visible
end

function Hud.start()
	build()
	root.Visible = false
	for _, attr in { "Wave", "TotalWaves", "Score", "Multiplier", "Integrity" } do
		GameState.onChanged(attr, refreshStats)
	end
	refreshStats()
	RunService.RenderStepped:Connect(function()
		if not root.Visible then
			return
		end
		WeaponHud.update()
		updateRadar()
		updateVignette()
		local remaining = GameState.get("Remaining") or 0
		refs.remaining.Text = if GameState.phase() == "Wave" then string.format("HOSTILES REMAINING: %d", remaining) else ""
	end)
end

return Hud
