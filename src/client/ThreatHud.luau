--!strict
-- Threat awareness HUD: off-screen arrows toward enemies in attack range,
-- the jet warning (banner + siren), the Siege Crawler boss bar and main
-- cannon charge warning, and first-encounter tips per enemy type.

local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local GameState = require(script.Parent.GameState)
local Hud = require(script.Parent.Hud)
local Sfx = require(script.Parent.Sfx)
local Ui = require(script.Parent.Ui)

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
local arrows: { Frame } = {}
local jetBanner: Frame
local jetText: TextLabel
local jetUntil = 0
local bossPanel: Frame
local bossPips: { [string]: Frame } = {}
local bossCoreBar: Frame
local chargePanel: Frame
local chargeBar: Frame
local chargeEndsAt = 0
local chargeDuration = 1
local seenKinds: { [string]: boolean } = {}

local function makeArrow(): Frame
	local holder = Ui.new("Frame", {
		Name = "ThreatArrow",
		BackgroundTransparency = 1,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Size = UDim2.fromOffset(44, 44),
		Visible = false,
		Parent = root,
	})
	-- Chevron made of two bars meeting at the tip (pointing up at rotation 0).
	for _, side in { -1, 1 } do
		Ui.new("Frame", {
			Name = "Bar",
			BackgroundColor3 = C.Red,
			BorderSizePixel = 0,
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.new(0.5, side * 7, 0.5, 2),
			Rotation = side * 40,
			Size = UDim2.fromOffset(6, 24),
			Parent = holder,
		}, { Ui.new("UIStroke", { Color = Color3.new(0, 0, 0), Thickness = 1, Transparency = 0.3 }) })
	end
	return holder
end

local function build(parent: Frame)
	root = Ui.new("Frame", { Name = "Threats", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = parent })
	for _ = 1, MAX_ARROWS do
		table.insert(arrows, makeArrow())
	end

	jetBanner = Ui.panel({ Name = "JetWarning", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 160), Size = UDim2.fromOffset(420, 52), Visible = false, Parent = root })
	jetBanner.BackgroundColor3 = Color3.fromRGB(90, 12, 8)
	jetText = Ui.label({ Text = "⚠ INCOMING JET", FontFace = F.Header, TextSize = 30, TextColor3 = C.White, TextXAlignment = Enum.TextXAlignment.Center, Size = UDim2.fromScale(1, 1), Parent = jetBanner })

	bossPanel = Ui.panel({ Name = "BossBar", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 96), Size = UDim2.fromOffset(520, 64), Visible = false, Parent = root })
	Ui.label({ Text = "SIEGE CRAWLER", FontFace = F.Header, TextSize = 20, TextColor3 = C.Red, Position = UDim2.fromOffset(12, 4), Size = UDim2.fromOffset(200, 24), Parent = bossPanel })
	for i, name in { "TurretLeft", "MainCannon", "TurretRight" } do
		local label = ({ TurretLeft = "L TURRET", MainCannon = "CANNON", TurretRight = "R TURRET" })[name]
		local pip = Ui.new("Frame", {
			Name = name,
			BackgroundColor3 = C.Red,
			BorderSizePixel = 0,
			Position = UDim2.fromOffset(12 + (i - 1) * 104, 32),
			Size = UDim2.fromOffset(96, 22),
			Parent = bossPanel,
		}, { Ui.new("UIStroke", { Color = Color3.new(0, 0, 0), Thickness = 1 }) })
		Ui.label({ Text = label, FontFace = F.Label, TextSize = 14, TextColor3 = C.White, TextXAlignment = Enum.TextXAlignment.Center, Size = UDim2.fromScale(1, 1), Parent = pip })
		bossPips[name] = pip
	end
	Ui.label({ Text = "CORE", FontFace = F.Label, TextSize = 14, TextColor3 = C.Amber, Position = UDim2.fromOffset(330, 6), Size = UDim2.fromOffset(60, 20), Parent = bossPanel })
	local coreBack = Ui.new("Frame", { BackgroundColor3 = Color3.fromRGB(40, 16, 12), BorderSizePixel = 0, Position = UDim2.fromOffset(330, 32), Size = UDim2.fromOffset(178, 22), Parent = bossPanel })
	bossCoreBar = Ui.new("Frame", { BackgroundColor3 = Color3.fromRGB(110, 110, 110), BorderSizePixel = 0, Size = UDim2.fromScale(1, 1), Parent = coreBack })

	chargePanel = Ui.panel({ Name = "CannonCharge", AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 168), Size = UDim2.fromOffset(380, 44), Visible = false, Parent = root })
	chargePanel.BackgroundColor3 = Color3.fromRGB(90, 30, 8)
	Ui.label({ Text = "MAIN CANNON CHARGING", FontFace = F.HeaderBold, TextSize = 18, TextColor3 = C.Amber, TextXAlignment = Enum.TextXAlignment.Center, Size = UDim2.new(1, 0, 0, 24), Parent = chargePanel })
	local chargeBack = Ui.new("Frame", { BackgroundColor3 = Color3.fromRGB(30, 20, 14), BorderSizePixel = 0, Position = UDim2.new(0, 10, 0, 26), Size = UDim2.new(1, -20, 0, 10), Parent = chargePanel })
	chargeBar = Ui.new("Frame", { BackgroundColor3 = C.Red, BorderSizePixel = 0, Size = UDim2.fromScale(0, 1), Parent = chargeBack })
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
			local color = if model:GetAttribute("IsAir") == true then AIR_COLOR else C.Red
			local pulse = 0.15 + 0.15 * math.sin(os.clock() * 10)
			for _, bar in arrow:GetChildren() do
				(bar :: Frame).BackgroundColor3 = color;
				(bar :: Frame).BackgroundTransparency = pulse
			end
		end
	end
	for i = used + 1, MAX_ARROWS do
		arrows[i].Visible = false
	end
end

local function updateBanners()
	local now = os.clock()
	if jetBanner.Visible then
		if now > jetUntil or GameState.phase() ~= "Wave" then
			jetBanner.Visible = false
		else
			local blink = math.floor(now * 4) % 2 == 0
			jetBanner.BackgroundColor3 = if blink then Color3.fromRGB(150, 16, 10) else Color3.fromRGB(70, 10, 6)
		end
	end
	if chargePanel.Visible then
		local remaining = chargeEndsAt - now
		if remaining <= 0 or GameState.phase() ~= "Wave" then
			chargePanel.Visible = false
		else
			chargeBar.Size = UDim2.fromScale(1 - remaining / chargeDuration, 1)
		end
	end
	if bossPanel.Visible and GameState.phase() ~= "Wave" and GameState.phase() ~= "WaveIntro" then
		bossPanel.Visible = false
	end
end

local function onJetWarning(payload: any)
	jetUntil = os.clock() + math.clamp((payload and payload.eta) or 6, 3, 10)
	jetText.Text = "⚠ INCOMING JET ⚠"
	jetBanner.Visible = true
	Sfx.play("JetSiren")
end

local function onBossUpdate(payload: any)
	bossPanel.Visible = true
	local weak = (payload and payload.weakPoints) or {}
	local allDown = true
	for name, pip in bossPips do
		-- weakPoints[name] == true means the weak point is still intact.
		local intact = weak[name] ~= false
		pip.BackgroundColor3 = if intact then C.Red else Color3.fromRGB(50, 50, 50)
		pip.BackgroundTransparency = if intact then 0 else 0.4
		if intact then
			allDown = false
		end
	end
	local core = math.clamp((payload and payload.core) or 1, 0, 1)
	bossCoreBar.Size = UDim2.fromScale(core, 1)
	bossCoreBar.BackgroundColor3 = if allDown then C.Amber else Color3.fromRGB(110, 110, 110)
end

local function onBossCharge(payload: any)
	chargeDuration = math.max(0.5, (payload and payload.duration) or 3)
	chargeEndsAt = os.clock() + chargeDuration
	chargePanel.Visible = true
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
	RunService.RenderStepped:Connect(function()
		updateArrows()
		updateBanners()
	end)
end

return ThreatHud
