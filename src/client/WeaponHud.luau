--!strict
-- Weapon HUD: weapon strip (slots, ammo, heat, reload), per-weapon
-- crosshairs, lock-on box, hit markers, status callouts and the per-weapon
-- gunsight overlays (machine-gun iron sight, rocket scope, AA seeker).
-- The core Hud creates the root frame and calls build/update. The strip,
-- slots, heat and reload bars use the LOOK-2 kit (UiKit): eased fills, a
-- colour-ramped heat bar with a hot sheen and scrolling hazard stripes on
-- overheat, reload-complete flashes and bracket motion on weapon select.
-- MOBILE-1: the strip lives in the HUD's safe-area root; in touch mode its
-- slots are tap targets (they select the weapon) and lose the 1/2/3 keys.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local WeaponConfig = require(ReplicatedStorage.Shared.WeaponConfig)
local AimController = require(script.Parent.AimController)
local LockOn = require(script.Parent.LockOn)
local PostFxAssets = require(script.Parent.PostFxAssets)
local Ui = require(script.Parent.Ui)
local UiKit = require(script.Parent.UiKit)
local UiKitArt = require(script.Parent.UiKitArt)
local UiScale = require(script.Parent.UiScale)
local WeaponController = require(script.Parent.WeaponController)

local WeaponHud = {}

local C = Ui.Colors
local F = Ui.Fonts
local DIM = Color3.fromRGB(120, 120, 110)
local INK = Color3.fromRGB(16, 16, 12)
local SEEKER = Color3.fromRGB(150, 230, 120)
local SLOTS = WeaponConfig.SLOTS
local refs: { [string]: any } = {}

local statusText = ""
local statusColor = C.Amber
local statusUntil = 0

local function bar(parent: Instance, props: { [string]: any }): Frame
	local defaults = { BackgroundColor3 = C.Amber, BorderSizePixel = 0, AnchorPoint = Vector2.new(0.5, 0.5) }
	for k, v in props do
		defaults[k] = v
	end
	defaults.Parent = parent
	return Ui.new("Frame", defaults)
end

local function ring(parent: Instance, props: { [string]: any }, stroke: { [string]: any }): Frame
	local defaults = { BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5) }
	for k, v in props do
		defaults[k] = v
	end
	defaults.Parent = parent
	return Ui.new("Frame", defaults, {
		Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }),
		Ui.new("UIStroke", stroke),
	})
end

-- Four L-shaped corner brackets filling `parent`.
local function brackets(parent: Instance, color: Color3, length: number, thickness: number)
	for _, corner in { Vector2.new(0, 0), Vector2.new(1, 0), Vector2.new(0, 1), Vector2.new(1, 1) } do
		local pos = UDim2.fromScale(corner.X, corner.Y)
		bar(parent, { Name = "H", BackgroundColor3 = color, AnchorPoint = corner, Position = pos, Size = UDim2.fromOffset(length, thickness) })
		bar(parent, { Name = "V", BackgroundColor3 = color, AnchorPoint = corner, Position = pos, Size = UDim2.fromOffset(thickness, length) })
	end
end

-- Heat colour ramp: olive -> amber -> red.
local function heatColor(heat: number): Color3
	if heat < 0.5 then
		return C.Olive:Lerp(C.Amber, heat / 0.5)
	end
	return C.Amber:Lerp(C.Red, math.clamp((heat - 0.5) / 0.35, 0, 1))
end

-- Touch: a press on a slot selects its weapon (on press, not release, so
-- a quick switch-and-fire isn't held up).
local function tapTarget(plate: ImageLabel, weapon: string): TextButton
	local button = Ui.new("TextButton", {
		Name = "Tap",
		Text = "",
		BackgroundTransparency = 1,
		AutoButtonColor = false,
		Position = UDim2.fromOffset(-4, -6),
		Size = UDim2.new(1, 8, 1, 12),
		Visible = false,
		ZIndex = 8,
		Parent = plate,
	})
	button.InputBegan:Connect(function(input)
		local kind = input.UserInputType
		if kind == Enum.UserInputType.Touch or kind == Enum.UserInputType.MouseButton1 then
			if AimController.getMode() == "Turret" then
				WeaponController.select(weapon)
			end
		end
	end)
	return button
end

local function buildSlots(root: Frame)
	local strip = UiKit.panel({ Name = "Weapons", AnchorPoint = Vector2.new(0.5, 1), Position = UDim2.new(0.5, 0, 1, -16), Size = UDim2.fromOffset(436, 98), Parent = root }, { stripe = true })
	refs.strip = strip
	refs.slots = {}
	for i, weapon in SLOTS do
		local plate = UiKit.sprite("button", {
			Name = "Slot" .. i,
			ImageColor3 = UiKit.Tints.PlateDim,
			Position = UDim2.fromOffset(8 + (i - 1) * 140, 10),
			Size = UDim2.fromOffset(134, 54),
			Parent = strip,
		})
		local brackets = UiKit.brackets(plate, C.Amber, 3)
		brackets.Visible = false
		local slot = {
			frame = plate,
			brackets = brackets,
			name = Ui.label({ Text = WeaponConfig.SLOT_NAMES[weapon], FontFace = F.Label, TextSize = 14, TextColor3 = DIM, Position = UDim2.fromOffset(24, 5), Size = UDim2.fromOffset(104, 16), Parent = plate }),
			ammo = Ui.label({ Text = if weapon == "MG" then "∞" else "--", FontFace = F.Mono, TextSize = 20, TextColor3 = DIM, TextXAlignment = Enum.TextXAlignment.Right, Position = UDim2.fromOffset(0, 19), Size = UDim2.new(1, -10, 0, 22), Parent = plate }),
			status = Ui.label({ Text = "", FontFace = F.Label, TextSize = 13, TextColor3 = C.Amber, Position = UDim2.fromOffset(9, 22), Size = UDim2.fromOffset(80, 18), ZIndex = 3, Parent = plate }),
			-- LOOK-4: the weapon's icon left of the ammo count (the status
			-- callout sits over it, dimming it, while one shows).
			icon = UiKitArt.weaponIcon(weapon, { Position = UDim2.fromOffset(9, 18), Size = UDim2.fromOffset(75, 25), ImageColor3 = DIM, ZIndex = 2, Parent = plate }),
			reload = nil :: UiKit.Bar?,
			key = nil :: TextLabel?,
			tap = nil :: TextButton?,
			wasReloading = false,
			readyUntil = 0,
		}
		if slot.icon then
			Ui.outline(slot.status, 1.5)
		end
		slot.key = Ui.label({ Text = tostring(i), FontFace = F.Header, TextSize = 18, TextColor3 = C.Amber, Position = UDim2.fromOffset(8, 4), Size = UDim2.fromOffset(16, 18), Parent = plate })
		slot.tap = tapTarget(plate, weapon)
		if weapon ~= "MG" then
			local bar = UiKit.bar(plate, { Position = UDim2.new(0, 6, 1, -13), Size = UDim2.new(1, -12, 0, 9), SliceScale = 0.6 }, { color = C.Olive, rate = 18 })
			bar.fill.SliceScale = 0.6
			slot.reload = bar
		end
		refs.slots[i] = slot
	end
	Ui.label({ Text = "HEAT", FontFace = F.Label, TextSize = 14, TextColor3 = C.Olive, Position = UDim2.fromOffset(12, 72), Size = UDim2.fromOffset(40, 18), Parent = strip })
	refs.heat = UiKit.bar(strip, { Position = UDim2.fromOffset(52, 72), Size = UDim2.new(1, -64, 0, 16) }, { color = C.Olive, value = 0, rate = 16 })
	local sheen = Ui.new("UIGradient", {
		Name = "Sheen",
		Color = ColorSequence.new({
			ColorSequenceKeypoint.new(0, Color3.fromRGB(205, 205, 205)),
			ColorSequenceKeypoint.new(0.42, Color3.fromRGB(205, 205, 205)),
			ColorSequenceKeypoint.new(0.5, Color3.new(1, 1, 1)),
			ColorSequenceKeypoint.new(0.58, Color3.fromRGB(205, 205, 205)),
			ColorSequenceKeypoint.new(1, Color3.fromRGB(205, 205, 205)),
		}),
		Enabled = false,
		Parent = refs.heat.fill,
	})
	refs.heatSheen = sheen
	refs.overheatStripes = UiKit.hazard(refs.heat.trough, { Position = UDim2.fromOffset(2, 2), Size = UDim2.new(1, -4, 1, -4), Visible = false, ZIndex = 4 }, C.Red, 60)
	refs.overheat = Ui.label({ Text = "OVERHEAT", FontFace = F.Header, TextSize = 14, TextColor3 = C.White, TextXAlignment = Enum.TextXAlignment.Center, Size = UDim2.fromScale(1, 1), Visible = false, ZIndex = 5, Parent = refs.heat.trough })
	Ui.outline(refs.overheat, 1.5)
end

local function outlined(parent: Instance): { [string]: any }
	return { Parent = parent, Color = Color3.new(0, 0, 0), Thickness = 1, Transparency = 0.3 }
end

local function buildCrosshairs(root: Frame)
	local function holder(name: string): Frame
		return Ui.new("Frame", { Name = name, BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(160, 160), ZIndex = 3, Parent = root })
	end
	-- Machine gun: open cross.
	refs.crossMG = holder("CrosshairMG")
	for _, spec in { { 0, -13, 2, 10 }, { 0, 13, 2, 10 }, { -13, 0, 10, 2 }, { 13, 0, 10, 2 } } do
		local b = bar(refs.crossMG, { Position = UDim2.new(0.5, spec[1], 0.5, spec[2]), Size = UDim2.fromOffset(spec[3], spec[4]) })
		Ui.new("UIStroke", outlined(b))
	end
	bar(refs.crossMG, { Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(3, 3) })

	-- Rockets: stadia line with lead ticks and drop chevrons below.
	refs.crossRocket = holder("CrosshairRocket")
	for _, side in { -1, 1 } do
		local b = bar(refs.crossRocket, { Position = UDim2.new(0.5, side * 30, 0.5, 0), Size = UDim2.fromOffset(40, 2) })
		Ui.new("UIStroke", outlined(b))
		for _, x in { 22, 44 } do
			bar(refs.crossRocket, { Position = UDim2.new(0.5, side * x, 0.5, 4), Size = UDim2.fromOffset(2, 6) })
		end
	end
	for i, y in { 14, 24, 34 } do
		local b = bar(refs.crossRocket, { Position = UDim2.new(0.5, 0, 0.5, y), Size = UDim2.fromOffset(16 - i * 3, 2) })
		Ui.new("UIStroke", outlined(b))
	end
	ring(refs.crossRocket, { Size = UDim2.fromOffset(10, 10) }, { Color = C.Amber, Thickness = 2 })

	-- AA missiles: seeker circle sized to the acquire cone + centre pip.
	refs.crossMissile = holder("CrosshairMissile")
	refs.seekerRing = ring(refs.crossMissile, { Size = UDim2.fromOffset(80, 80) }, { Color = SEEKER, Thickness = 1.5, Transparency = 0.2 })
	for _, spec in { { 0, -6, 2, 6 }, { 0, 6, 2, 6 }, { -6, 0, 6, 2 }, { 6, 0, 6, 2 } } do
		bar(refs.crossMissile, { BackgroundColor3 = SEEKER, Position = UDim2.new(0.5, spec[1], 0.5, spec[2]), Size = UDim2.fromOffset(spec[3], spec[4]) })
	end

	-- Lock box (tracks the target on screen).
	refs.lockBox = Ui.new("Frame", { Name = "LockBox", BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Size = UDim2.fromOffset(100, 100), Visible = false, ZIndex = 3, Parent = root })
	refs.lockBrackets = UiKit.brackets(refs.lockBox, C.Amber, 0, { SliceScale = 1.4 })
	refs.lockLabel = Ui.label({ Text = "", FontFace = F.Header, TextSize = 16, TextColor3 = C.Amber, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 1, 4), Size = UDim2.fromOffset(120, 18), Parent = refs.lockBox })
	Ui.outline(refs.lockLabel, 1.5)

	-- Status callout under the crosshair.
	refs.status = Ui.label({ Text = "", FontFace = F.Header, TextSize = 18, TextColor3 = C.Amber, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0.5, 48), Size = UDim2.fromOffset(320, 22), ZIndex = 3, Parent = root })
	Ui.outline(refs.status, 2)
end

local function buildHitMarker(root: Frame)
	refs.hitmarker = Ui.new("Frame", { Name = "HitMarker", BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(44, 44), Visible = false, ZIndex = 4, Parent = root })
	refs.hitScale = Ui.new("UIScale", { Parent = refs.hitmarker })
	for _, rot in { 45, -45, 135, -135 } do
		local rad = math.rad(rot)
		Ui.new("Frame", {
			Name = "Tick",
			BackgroundColor3 = C.White,
			BorderSizePixel = 0,
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.new(0.5, math.sin(rad) * 15, 0.5, -math.cos(rad) * 15),
			Rotation = rot,
			Size = UDim2.fromOffset(3, 11),
			Parent = refs.hitmarker,
		})
	end
end

local function buildIronSight(parent: Frame): Frame
	local sight = Ui.new("Frame", { Name = "IronSight", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = parent })
	local outer = ring(sight, { Size = UDim2.fromOffset(220, 220) }, { Color = INK, Thickness = 6 })
	ring(outer, { Size = UDim2.fromOffset(120, 120) }, { Color = INK, Thickness = 2, Transparency = 0.3 })
	bar(sight, { BackgroundColor3 = INK, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0.5, 6), Size = UDim2.fromOffset(6, 110) })
	for _, side in { -1, 1 } do
		bar(sight, { BackgroundColor3 = INK, AnchorPoint = Vector2.new(if side < 0 then 1 else 0, 0.5), Position = UDim2.new(0.5, side * 118, 0.5, 0), Size = UDim2.new(0.5, -118, 0, 4) })
	end
	return sight
end

-- Rocket scope: black mask around a round lens, mil reticle with lead and
-- range marks.
local function buildRocketScope(parent: Frame): Frame
	local scope = Ui.new("Frame", { Name = "RocketScope", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = parent })
	local lens = ring(scope, { Size = UDim2.fromScale(0.62, 0.62), SizeConstraint = Enum.SizeConstraint.RelativeYY }, { Color = Color3.new(0, 0, 0), Thickness = 1600 })
	ring(lens, { Size = UDim2.fromScale(1, 1) }, { Color = Color3.fromRGB(10, 10, 8), Thickness = 26, Transparency = 0.35, ApplyStrokeMode = Enum.ApplyStrokeMode.Border })
	ring(lens, { Size = UDim2.new(1, -6, 1, -6) }, { Color = C.AmberDim, Thickness = 1.5, Transparency = 0.3 })
	-- Horizontal stadia with lead ticks every 30 px, vertical post below.
	for _, side in { -1, 1 } do
		bar(lens, { BackgroundColor3 = INK, AnchorPoint = Vector2.new(if side < 0 then 1 else 0, 0.5), Position = UDim2.new(0.5, side * 14, 0.5, 0), Size = UDim2.new(0.5, -14, 0, 2) })
		for k = 1, 5 do
			bar(lens, { BackgroundColor3 = INK, Position = UDim2.new(0.5, side * k * 30, 0.5, 0), Size = UDim2.fromOffset(2, if k % 2 == 0 then 14 else 8) })
		end
	end
	bar(lens, { BackgroundColor3 = INK, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0.5, 14), Size = UDim2.new(0, 2, 0.5, -14) })
	for k, label in { "2", "4", "6" } do
		local y = 14 + k * 26
		bar(lens, { BackgroundColor3 = INK, Position = UDim2.new(0.5, 0, 0.5, y), Size = UDim2.fromOffset(22 - k * 4, 2) })
		Ui.label({ Text = label, FontFace = F.Mono, TextSize = 12, TextColor3 = INK, Position = UDim2.new(0.5, 14, 0.5, y - 8), Size = UDim2.fromOffset(20, 14), Parent = lens })
	end
	ring(lens, { Size = UDim2.fromOffset(8, 8) }, { Color = C.Red, Thickness = 2 })
	Ui.label({ Text = "RKT · 1.5 RELOAD", FontFace = F.Mono, TextSize = 13, TextColor3 = C.AmberDim, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 40), Size = UDim2.fromOffset(200, 16), TextXAlignment = Enum.TextXAlignment.Center, Parent = lens })
	return scope
end

-- AA seeker display: green-tinted glass, frame brackets, horizon ladder.
local function buildSeeker(parent: Frame): Frame
	local seeker = Ui.new("Frame", { Name = "AASeeker", BackgroundColor3 = Color3.fromRGB(20, 60, 30), BackgroundTransparency = 0.86, BorderSizePixel = 0, Size = UDim2.fromScale(1, 1), Parent = parent })
	local box = Ui.new("Frame", { BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromScale(0.62, 0.62), SizeConstraint = Enum.SizeConstraint.RelativeYY, Parent = seeker })
	brackets(box, SEEKER, 40, 2)
	for _, side in { -1, 1 } do
		for k = -2, 2 do
			bar(seeker, { BackgroundColor3 = SEEKER, BackgroundTransparency = 0.3, Position = UDim2.new(0.5, side * 220, 0.5, k * 48), Size = UDim2.fromOffset(if k == 0 then 60 else 30, 2) })
		end
	end
	Ui.label({ Text = "IR SEEKER · AIR TARGETS ONLY", FontFace = F.Mono, TextSize = 14, TextColor3 = SEEKER, TextXAlignment = Enum.TextXAlignment.Center, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0.19, 12), Size = UDim2.fromOffset(320, 18), Parent = seeker })
	return seeker
end

-- `root` covers the whole screen (sights, crosshairs, markers); `safe`,
-- when given, is the safe-area root that takes the weapon strip.
function WeaponHud.build(root: Frame, safe: Frame?)
	refs.root = root
	-- Sights sit behind every other HUD panel (ZIndex 0).
	refs.sight = Ui.new("Frame", { Name = "Gunsight", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Visible = false, ZIndex = 0, Parent = root })
	-- Lens vignette (gunsight only, LOOK-1): darkens the frame edges under
	-- every sight overlay.
	Ui.new("ImageLabel", {
		Name = "Vignette",
		BackgroundTransparency = 1,
		Image = PostFxAssets.vignette,
		ImageTransparency = 0.5,
		ScaleType = Enum.ScaleType.Stretch,
		Size = UDim2.fromScale(1, 1),
		ZIndex = 0,
		Parent = refs.sight,
	})
	refs.sights = {
		MG = buildIronSight(refs.sight),
		Rocket = buildRocketScope(refs.sight),
		Missile = buildSeeker(refs.sight),
	}
	buildSlots(safe or root)
	buildCrosshairs(root)
	buildHitMarker(root)

	WeaponController.on("Switched", function(weapon)
		WeaponHud.flash(WeaponConfig.SLOT_NAMES[weapon], C.Text, 0.7)
	end)
	WeaponController.on("Empty", function(weapon)
		WeaponHud.flash(if weapon == "Rocket" then "NO ROCKETS" else "NO MISSILES", C.Red, 1)
	end)
	WeaponController.on("NoLock", function()
		WeaponHud.flash("NO LOCK — HOLD ON AN AIRCRAFT", C.Red, 1.1)
	end)
	WeaponController.on("Hold", function()
		WeaponHud.flash("HOLD FIRE", C.Amber, 0.8)
	end)
end

-- Desktop or touch placement of the strip and its slots.
function WeaponHud.layout(touch: boolean)
	if not refs.strip then
		return
	end
	refs.strip.Position = UDim2.new(0.5, 0, 1, if touch then -10 else -16)
	for i, slot in refs.slots do
		slot.tap.Visible = touch
		slot.key.Visible = not touch
		slot.name.Position = UDim2.fromOffset(if touch then 9 else 24, 5)
		slot.name.Text = WeaponConfig.SLOT_NAMES[SLOTS[i]]
	end
end

-- HS-2 hook (client/GunsightModels): while a 3D sight model stands in
-- front of the camera for `weapon` (nil = none), the GUI rings that model
-- replaces are hidden: the whole iron sight (the model has the ring sight
-- and rear leaf) and the rocket scope's mask and lens rims (strokes on
-- round frames at least 40 px across). Reticle marks, crosshairs, the
-- seeker display and the lock box stay.
local sightModel: string? = nil
local hiddenBySightModel: { Instance } = {}

function WeaponHud.setSightModel(weapon: string?)
	if weapon == sightModel or not refs.sights then
		return
	end
	sightModel = weapon
	for _, inst in hiddenBySightModel do
		if inst:IsA("UIStroke") then
			inst.Enabled = true
		elseif inst:IsA("GuiObject") then
			inst.Visible = true
		end
	end
	table.clear(hiddenBySightModel)
	local sight = weapon and refs.sights[weapon]
	if not sight then
		return
	end
	if weapon == "MG" then
		for _, child in sight:GetChildren() do
			if child:IsA("GuiObject") and child.Visible then
				child.Visible = false
				table.insert(hiddenBySightModel, child)
			end
		end
		return
	end
	for _, d in sight:GetDescendants() do
		local frame = d.Parent
		if
			d:IsA("UIStroke")
			and d.Enabled
			and frame
			and frame:IsA("GuiObject")
			and frame:FindFirstChildOfClass("UICorner")
			and frame.AbsoluteSize.X >= 40
		then
			d.Enabled = false
			table.insert(hiddenBySightModel, d)
		end
	end
end

function WeaponHud.flash(text: string, color: Color3, duration: number)
	statusText = text
	statusColor = color
	statusUntil = os.clock() + duration
end

local function updateHeat(dt: number)
	local heat = WeaponController.getHeat()
	local locked = WeaponController.getLockRemaining() > 0
	local bar = refs.heat :: UiKit.Bar
	UiKit.setBar(bar, heat)
	UiKit.stepBar(bar, dt)
	refs.overheat.Visible = locked
	refs.overheatStripes.Visible = locked
	local sheen = refs.heatSheen :: UIGradient
	if locked then
		local blink = math.floor(os.clock() * 6) % 2 == 0
		bar.fill.ImageColor3 = C.Red
		refs.overheat.TextColor3 = if blink then C.White else C.Amber
		sheen.Enabled = false
	else
		bar.fill.ImageColor3 = heatColor(bar.shown)
		-- Hot barrel: a bright sheen runs along the fill, faster as it heats.
		sheen.Enabled = bar.shown > 0.55
		if sheen.Enabled then
			local speed = 0.6 + 1.6 * bar.shown
			sheen.Offset = Vector2.new(((os.clock() * speed) % 2) - 1, 0)
		end
	end
end

local lastWeapon: string? = nil

-- Selected slot: brackets snap in from further out and the plate flashes.
local function selectMotion(slot: any)
	local brackets = slot.brackets :: ImageLabel
	brackets.Position = UDim2.fromOffset(-12, -12)
	brackets.Size = UDim2.new(1, 24, 1, 24)
	brackets.ImageTransparency = 0.6
	UiKit.tween(brackets, 0.22, { Position = UDim2.fromOffset(-3, -3), Size = UDim2.new(1, 6, 1, 6), ImageTransparency = 0 }, Enum.EasingStyle.Back)
	slot.frame.ImageColor3 = Color3.fromRGB(255, 240, 200)
	UiKit.tween(slot.frame, 0.35, { ImageColor3 = UiKit.Tints.Plate })
end

-- Icon tint: cream when selected, grey idle, red when out of ammo; dimmed
-- under a status callout so the word reads.
local function paintIcon(slot: any, selected: boolean, empty: boolean)
	local icon = slot.icon :: ImageLabel?
	if not icon then
		return
	end
	icon.ImageColor3 = if empty then C.Red elseif selected then C.Text else DIM
	local base = if selected then 0 else 0.25
	icon.ImageTransparency = if slot.status.Text ~= "" then math.max(base, 0.7) else base
end

local function updateSlots(current: string, lockState: string, dt: number)
	local switched = current ~= lastWeapon
	lastWeapon = current
	local now = os.clock()
	for i, weapon in SLOTS do
		local slot = refs.slots[i]
		local selected = weapon == current
		slot.brackets.Visible = selected
		if switched then
			if selected then
				selectMotion(slot)
			else
				slot.frame.ImageColor3 = UiKit.Tints.PlateDim
			end
		end
		slot.frame.ImageTransparency = if selected then 0 else 0.2
		slot.name.TextColor3 = if selected then C.Text else DIM
		if weapon == "MG" then
			slot.ammo.TextColor3 = if selected then C.Amber else DIM
			slot.status.Text = if WeaponController.getLockRemaining() > 0 then "OVERHEAT" else ""
			slot.status.TextColor3 = C.Red
			paintIcon(slot, selected, false)
			continue
		end
		local ammo = WeaponController.getAmmo(weapon)
		local reload = WeaponController.getReload(weapon)
		local bar = slot.reload :: UiKit.Bar
		slot.ammo.Text = tostring(ammo)
		slot.ammo.TextColor3 = if ammo == 0 then C.Red elseif selected then C.Amber else DIM
		local reloading = reload > 0 and ammo > 0
		if slot.wasReloading and not reloading and ammo > 0 then
			-- Reload complete: the bar flashes and READY shows briefly.
			slot.readyUntil = now + 0.7
			bar.fill.ImageColor3 = Color3.fromRGB(255, 244, 210)
			UiKit.tween(bar.fill, 0.5, { ImageColor3 = C.Olive })
		end
		slot.wasReloading = reloading
		UiKit.setBar(bar, if ammo == 0 then 0 else 1 - reload)
		UiKit.stepBar(bar, dt)
		if reloading then
			bar.fill.ImageColor3 = C.AmberDim
		elseif now >= slot.readyUntil then
			bar.fill.ImageColor3 = C.Olive
		end
		local status, color = "", C.Amber
		if ammo == 0 then
			status, color = "EMPTY", C.Red
		elseif reloading then
			status = "RELOAD"
		elseif now < slot.readyUntil then
			status, color = "READY", C.Green
		elseif weapon == "Missile" and selected and lockState ~= "Idle" then
			status, color = if lockState == "Locked" then "LOCKED" else "LOCKING", if lockState == "Locked" then C.Red else C.Amber
		end
		slot.status.Text = status
		slot.status.TextColor3 = color
		paintIcon(slot, selected, ammo == 0)
	end
end

local function coneRadius(): number
	local camera = Workspace.CurrentCamera
	local half = math.rad(camera.FieldOfView / 2)
	-- The field of view spans the whole screen (the HUD root), which on a
	-- notched phone is taller than the viewport.
	local height = UiScale.size(refs.root).Y
	return math.tan(math.rad(WeaponConfig.Missile.ACQUIRE_DEG)) / math.tan(half) * height / 2
end

local function updateLockBox(current: string, state: string, target: Model?, progress: number)
	local box = refs.lockBox :: Frame
	local root = target and target.PrimaryPart
	if current ~= "Missile" or state == "Idle" or not root then
		box.Visible = false
		return
	end
	local screen, onScreen = Workspace.CurrentCamera:WorldToScreenPoint(root.Position)
	if not onScreen then
		box.Visible = false
		return
	end
	box.Visible = true
	local at = UiScale.fromScreen(refs.root, Vector2.new(screen.X, screen.Y))
	box.Position = UDim2.fromOffset(at.X, at.Y)
	local locked = state == "Locked"
	local size = if locked then 40 else 110 - 64 * progress
	box.Size = UDim2.fromOffset(size, size)
	local blink = math.floor(os.clock() * (if locked then 4 else 10)) % 2 == 0
	local color = if locked then C.Red elseif blink then C.Amber else C.AmberDim
	refs.lockBrackets.ImageColor3 = color
	refs.lockLabel.Text = if locked then "LOCK" else string.format("%d%%", math.floor(progress * 100))
	refs.lockLabel.TextColor3 = color
end

local function updateStatus(current: string, state: string)
	local label = refs.status :: TextLabel
	if os.clock() < statusUntil then
		label.Text = statusText
		label.TextColor3 = statusColor
	elseif current == "Missile" then
		label.Text = if state == "Locked" then "LOCKED — FIRE" elseif state == "Acquiring" then "ACQUIRING" else "SEEKING AIR TARGET"
		label.TextColor3 = if state == "Locked" then C.Red elseif state == "Acquiring" then C.Amber else SEEKER
	else
		label.Text = ""
	end
end

function WeaponHud.update(dt: number?)
	local step = dt or 1 / 60
	local current = WeaponController.getWeapon()
	local state, target, progress = LockOn.getState()
	local aiming = AimController.isAiming()
	updateHeat(step)
	updateSlots(current, state, step)
	updateLockBox(current, state, target, progress)
	updateStatus(current, state)

	refs.sight.Visible = aiming
	for weapon, sight in refs.sights do
		sight.Visible = weapon == current
	end
	-- The scope and seeker carry their own reticle.
	refs.crossMG.Visible = current == "MG"
	refs.crossRocket.Visible = current == "Rocket" and not aiming
	refs.crossMissile.Visible = current == "Missile"
	if current == "Missile" then
		local r = coneRadius()
		refs.seekerRing.Size = UDim2.fromOffset(r * 2, r * 2)
	end
	-- Swap animation: crosshair fades in as the new weapon comes up.
	local swap = WeaponController.getSwitchProgress()
	refs.crossMG.Rotation = (1 - swap) * 45
	refs.crossRocket.Position = UDim2.new(0.5, 0, 0.5, (1 - swap) * 20)
end

function WeaponHud.showHitMarker(killed: boolean)
	local marker = refs.hitmarker :: Frame
	marker.Visible = true
	for _, tick in marker:GetChildren() do
		if tick:IsA("Frame") then
			tick.BackgroundColor3 = if killed then C.Red else C.White
		end
	end
	-- Pop: the ticks jump out and settle (a kill settles wider).
	local scale = refs.hitScale :: UIScale
	scale.Scale = if killed then 1.75 else 1.35
	UiKit.tween(scale, if killed then 0.16 else 0.08, { Scale = if killed then 1.3 else 1 }, Enum.EasingStyle.Quad)
	local token = os.clock()
	marker:SetAttribute("Token", token)
	task.delay(if killed then 0.25 else 0.1, function()
		if marker:GetAttribute("Token") == token then
			marker.Visible = false
		end
	end)
end

return WeaponHud
