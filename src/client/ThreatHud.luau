--!strict
-- Threat awareness HUD: off-screen arrows toward enemies in attack range,
-- the jet warning (banner + siren), the Siege Crawler boss bar and main
-- cannon charge warning, and first-encounter tips per enemy type. Panels,
-- bars, chevrons and hazard stripes come from the LOOK-2 kit (UiKit); the
-- warnings slide in and the boss bars ease.

local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")
local FrameProfile = require(script.Parent.FrameProfile)

local GameState = require(script.Parent.GameState)
local Hud = require(script.Parent.Hud)
local Sfx = require(script.Parent.Sfx)
local Ui = require(script.Parent.Ui)
local UiKit = require(script.Parent.UiKit)

local ThreatHud = {}

local C = Ui.Colors
local F = Ui.Fonts
local AIR_COLOR = Color3.fromRGB(90, 200, 255)
local EDGE_MARGIN = 70
local MAX_ARROWS = 12

local TIPS: { [string]: string } = {
	Buggy = "Fast buggy on the flank! <b>Short machine-gun bursts</b> or a well-led rocket.",
	Tank = "Bullets can't stop armor — press <b>2</b> for rockets.",
	Helicopter = "Air threat — press <b>3</b>, hold on target to lock.",
	Jet = "Incoming jet! <b>Lock and fire</b> before it drops its bombs.",
	SiegeCrawler = "SIEGE CRAWLER! Rocket the <b>side turrets and main cannon</b>, then the core.",
}

local root: Frame
local arrows: { ImageLabel } = {}
local jetBanner: ImageLabel
local jetText: TextLabel
local jetGlow: Frame
local jetUntil = 0
local bossPanel: ImageLabel
local bossPips: { [string]: { bar: UiKit.Bar, label: TextLabel, intact: boolean } } = {}
local bossCore: UiKit.Bar
local chargePanel: ImageLabel
local chargeBar: UiKit.Bar
local chargeEndsAt = 0
local chargeDuration = 1
local seenKinds: { [string]: boolean } = {}

local JET_Y = 160

local function makeArrow(): ImageLabel
	return UiKit.sprite("chevron", {
		Name = "ThreatArrow",
		ImageColor3 = C.Red,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Size = UDim2.fromOffset(40, 40),
		Visible = false,
		Parent = root,
	})
end

local function build(parent: Frame)
	root = Ui.new("Frame", { Name = "Threats", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = parent })
	for _ = 1, MAX_ARROWS do
		table.insert(arrows, makeArrow())
	end

	-- Jet warning: red-brown plate between scrolling hazard stripes.
	jetBanner = UiKit.panel({ Name = "JetWarning", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, JET_Y), Size = UDim2.fromOffset(440, 62), Visible = false, Parent = root }, { brackets = true, accent = C.Red, tint = UiKit.Tints.Warning })
	jetGlow = Ui.new("Frame", { Name = "Glow", BackgroundColor3 = C.Red, BackgroundTransparency = 0.4, BorderSizePixel = 0, Position = UDim2.fromOffset(8, 13), Size = UDim2.new(1, -16, 1, -26), ZIndex = 0, Parent = jetBanner })
	for _, y in { 5, 49 } do
		UiKit.hazard(jetBanner, { Position = UDim2.fromOffset(9, y), Size = UDim2.new(1, -18, 0, 8), ZIndex = 1 }, C.Red, 50)
	end
	jetText = Ui.label({ Text = "⚠ INCOMING JET", FontFace = F.Header, TextSize = 30, TextColor3 = C.White, TextXAlignment = Enum.TextXAlignment.Center, Position = UDim2.fromOffset(0, 1), Size = UDim2.fromScale(1, 1), ZIndex = 2, Parent = jetBanner })
	Ui.outline(jetText, 2)

	-- Boss bar: weak-point pips and the core, all eased bars.
	bossPanel = UiKit.panel({ Name = "BossBar", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 96), Size = UDim2.fromOffset(540, 70), Visible = false, Parent = root }, { brackets = true, stripe = true, accent = C.Red })
	Ui.label({ Text = "SIEGE CRAWLER", FontFace = F.Header, TextSize = 20, TextColor3 = C.Red, Position = UDim2.fromOffset(14, 8), Size = UDim2.fromOffset(200, 24), Parent = bossPanel })
	for i, name in { "TurretLeft", "MainCannon", "TurretRight" } do
		local text = ({ TurretLeft = "L TURRET", MainCannon = "CANNON", TurretRight = "R TURRET" })[name]
		local bar = UiKit.bar(bossPanel, { Name = name, Position = UDim2.fromOffset(12 + (i - 1) * 106, 36), Size = UDim2.fromOffset(100, 24) }, { color = C.Red, ghost = Color3.fromRGB(255, 226, 170), rate = 8 })
		local label = Ui.label({ Text = text, FontFace = F.Label, TextSize = 14, TextColor3 = C.White, TextXAlignment = Enum.TextXAlignment.Center, Size = UDim2.fromScale(1, 1), ZIndex = 4, Parent = bar.trough })
		Ui.outline(label, 1)
		bossPips[name] = { bar = bar, label = label, intact = true }
	end
	Ui.label({ Text = "CORE", FontFace = F.Label, TextSize = 14, TextColor3 = C.Amber, Position = UDim2.fromOffset(342, 12), Size = UDim2.fromOffset(60, 20), Parent = bossPanel })
	bossCore = UiKit.bar(bossPanel, { Name = "Core", Position = UDim2.fromOffset(342, 36), Size = UDim2.fromOffset(184, 24) }, { color = Color3.fromRGB(110, 110, 110), ghost = Color3.fromRGB(255, 226, 170), rate = 8 })

	-- Main cannon charge: amber hazard stripes over a filling red bar.
	chargePanel = UiKit.panel({ Name = "CannonCharge", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 174), Size = UDim2.fromOffset(400, 54), Visible = false, Parent = root }, { brackets = true, accent = C.Amber, tint = UiKit.Tints.Warning })
	Ui.label({ Text = "MAIN CANNON CHARGING", FontFace = F.HeaderBold, TextSize = 18, TextColor3 = C.Amber, TextXAlignment = Enum.TextXAlignment.Center, Position = UDim2.fromOffset(0, 6), Size = UDim2.new(1, 0, 0, 22), Parent = chargePanel })
	chargeBar = UiKit.bar(chargePanel, { Position = UDim2.fromOffset(12, 30), Size = UDim2.new(1, -24, 0, 14) }, { color = C.Red, value = 0, rate = 30 })
	UiKit.hazard(chargeBar.trough, { Position = UDim2.fromOffset(2, 2), Size = UDim2.new(1, -4, 1, -4), ZIndex = 0 }, C.AmberDim, 30, 0.55)
end

-- Slides a warning panel down into place and fades it in.
local function slideIn(panel: ImageLabel, y: number)
	panel.Visible = true
	panel.Position = UDim2.new(0.5, 0, 0, y - 28)
	panel.ImageTransparency = 0.7
	UiKit.tween(panel, 0.32, { Position = UDim2.new(0.5, 0, 0, y), ImageTransparency = 0 }, Enum.EasingStyle.Back)
end

-- Places arrows at the screen edge for threatening enemies that are off
-- screen (or behind the camera).
local function updateArrows()
	local camera = Workspace.CurrentCamera
	local viewport = camera.ViewportSize
	local center = viewport / 2
	local used = 0
	local enemies = Workspace:FindFirstChild("Enemies")
	if enemies and GameState.phase() == "Wave" then
		for _, model in enemies:GetChildren() do
			if used >= MAX_ARROWS then
				break
			end
			local rootPart = (model :: Model).PrimaryPart
			if not rootPart or model:GetAttribute("Threat") ~= true or model:GetAttribute("State") == "Dead" then
				continue
			end
			local screen, onScreen = camera:WorldToViewportPoint(rootPart.Position)
			if onScreen then
				continue
			end
			-- Direction in screen space; flip when the point is behind us.
			local dir = Vector2.new(screen.X, screen.Y) - center
			if screen.Z < 0 then
				dir = -dir
			end
			if dir.Magnitude < 1 then
				dir = Vector2.new(0, -1)
			end
			dir = dir.Unit
			local halfW, halfH = center.X - EDGE_MARGIN, center.Y - EDGE_MARGIN
			local scale = math.min(halfW / math.max(math.abs(dir.X), 1e-3), halfH / math.max(math.abs(dir.Y), 1e-3))
			local pos = center + dir * scale
			used += 1
			local arrow = arrows[used]
			arrow.Visible = true
			arrow.Position = UDim2.fromOffset(pos.X, pos.Y)
			arrow.Rotation = math.deg(math.atan2(dir.X, -dir.Y))
			arrow.ImageColor3 = if model:GetAttribute("IsAir") == true then AIR_COLOR else C.Red
			arrow.ImageTransparency = 0.1 + 0.2 * (0.5 + 0.5 * math.sin(os.clock() * 10))
			local pulse = 1 + 0.12 * math.max(0, math.sin(os.clock() * 10))
			arrow.Size = UDim2.fromOffset(40 * pulse, 40 * pulse)
		end
	end
	for i = used + 1, MAX_ARROWS do
		arrows[i].Visible = false
	end
end

local function updateBanners(dt: number)
	local now = os.clock()
	if jetBanner.Visible then
		if now > jetUntil or GameState.phase() ~= "Wave" then
			jetBanner.Visible = false
		else
			local blink = math.floor(now * 4) % 2 == 0
			jetBanner.ImageColor3 = if blink then UiKit.Tints.Warning else Color3.fromRGB(190, 120, 110)
			jetGlow.BackgroundTransparency = if blink then 0.3 else 0.62
			jetText.TextColor3 = if blink then C.White else Color3.fromRGB(255, 200, 190)
		end
	end
	if chargePanel.Visible then
		local remaining = chargeEndsAt - now
		if remaining <= 0 or GameState.phase() ~= "Wave" then
			chargePanel.Visible = false
		else
			UiKit.setBar(chargeBar, 1 - remaining / chargeDuration)
			UiKit.stepBar(chargeBar, dt)
		end
	end
	if bossPanel.Visible then
		if GameState.phase() ~= "Wave" and GameState.phase() ~= "WaveIntro" then
			bossPanel.Visible = false
		else
			UiKit.stepBar(bossCore, dt)
			for _, pip in bossPips do
				UiKit.stepBar(pip.bar, dt)
			end
		end
	end
end

local function onJetWarning(payload: any)
	jetUntil = os.clock() + math.clamp((payload and payload.eta) or 6, 3, 10)
	jetText.Text = "⚠ INCOMING JET ⚠"
	if not jetBanner.Visible then
		slideIn(jetBanner, JET_Y)
	end
	Sfx.play("JetSiren")
end

local function onBossUpdate(payload: any)
	if not bossPanel.Visible then
		slideIn(bossPanel, 96)
		UiKit.snapBar(bossCore, 1)
		for _, pip in bossPips do
			pip.intact = true
			UiKit.snapBar(pip.bar, 1)
		end
	end
	local weak = (payload and payload.weakPoints) or {}
	local allDown = true
	for name, pip in bossPips do
		-- weakPoints[name] == true means the weak point is still intact.
		local intact = weak[name] ~= false
		if pip.intact and not intact then
			-- Destroyed: the pip drains (ghost) and its label dims.
			pip.bar.fill.ImageColor3 = Color3.fromRGB(255, 240, 210)
			UiKit.tween(pip.bar.fill, 0.4, { ImageColor3 = Color3.fromRGB(60, 60, 60) })
		end
		pip.intact = intact
		UiKit.setBar(pip.bar, if intact then 1 else 0)
		pip.label.TextColor3 = if intact then C.White else Color3.fromRGB(130, 130, 120)
		if intact then
			pip.bar.fill.ImageColor3 = C.Red
			allDown = false
		end
	end
	local core = math.clamp((payload and payload.core) or 1, 0, 1)
	UiKit.setBar(bossCore, core)
	bossCore.fill.ImageColor3 = if allDown then C.Amber else Color3.fromRGB(110, 110, 110)
end

local function onBossCharge(payload: any)
	if payload and payload.cancelled then
		-- The cannon was knocked out mid-charge: drop the warning at once.
		chargePanel.Visible = false
		return
	end
	chargeDuration = math.max(0.5, (payload and payload.duration) or 3)
	chargeEndsAt = os.clock() + chargeDuration
	UiKit.snapBar(chargeBar, 0)
	if not chargePanel.Visible then
		slideIn(chargePanel, 174)
	end
	Sfx.play("CannonCharge")
end

local function watchFirstEncounters()
	local enemies = Workspace:WaitForChild("Enemies")
	enemies.ChildAdded:Connect(function(child)
		task.defer(function()
			local kind = child:GetAttribute("Kind")
			if type(kind) == "string" and not seenKinds[kind] then
				seenKinds[kind] = true
				local tip = TIPS[kind]
				if tip then
					Hud.tipOnce("enemy_" .. kind, tip, 6)
				end
			end
		end)
	end)
end

local function onCrateSpawned()
	Hud.tipOnce("crate", "Supply crate inbound! <b>Shoot it</b> to collect.", 5)
	Sfx.play("CrateDrop")
end

local function onCratePickup(payload: any)
	local names = { Rockets = "ROCKETS", Missiles = "AA MISSILES", Repair = "% INTEGRITY" }
	local text = if payload.contents == "Repair"
		then string.format("+%d%s", payload.amount, names.Repair)
		else string.format("+%d %s", payload.amount, names[payload.contents] or payload.contents)
	local label = Ui.label({
		Text = text,
		FontFace = F.Header,
		TextSize = 34,
		TextColor3 = C.Green,
		TextXAlignment = Enum.TextXAlignment.Center,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.62),
		Size = UDim2.fromOffset(420, 44),
		Parent = root,
	})
	Ui.outline(label, 2)
	TweenService:Create(label, TweenInfo.new(1.6, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
		Position = UDim2.fromScale(0.5, 0.54),
		TextTransparency = 1,
	}):Play()
	task.delay(1.7, function()
		label:Destroy()
	end)
	Sfx.play("CratePickup")
end

function ThreatHud.start()
	build(Hud.getRoot())
	GameState.onEvent("JetWarning", onJetWarning)
	GameState.onEvent("BossUpdate", onBossUpdate)
	GameState.onEvent("BossCharge", onBossCharge)
	GameState.onEvent("CrateSpawned", onCrateSpawned)
	GameState.onEvent("CratePickup", onCratePickup)
	GameState.onEvent("Points", function(p)
		Hud.scorePopup(p.position, string.format("+%d %s", p.points, p.label or ""))
	end)
	GameState.onChanged("Phase", function(phase)
		if phase ~= "Wave" and phase ~= "WaveIntro" then
			bossPanel.Visible = false
			chargePanel.Visible = false
			jetBanner.Visible = false
		end
	end)
	task.spawn(watchFirstEncounters)
	RunService.RenderStepped:Connect(FrameProfile.wrap("ThreatHud", function(dt)
		updateArrows()
		updateBanners(dt)
	end))
end

return ThreatHud
