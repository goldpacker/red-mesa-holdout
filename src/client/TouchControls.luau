--!strict
-- On-screen touch controls (MOBILE-1), shown in the turret while the player
-- uses touch (InputMode): a large FIRE button bottom right with the SIGHT
-- toggle above it, and a second FIRE button on the left, so one thumb can
-- hold the trigger while the other aims. Dragging anywhere else on the
-- screen aims (TouchInput); the FIRE buttons aim too while dragged. The
-- weapon strip's slots are the weapon buttons (WeaponHud).
--
-- The FIRE buttons show the selected weapon's icon and say why it can't
-- fire (HOT, RELOAD, EMPTY); with AA missiles they turn red once a target
-- is locked. Built into the HUD's safe-area root (Hud.getSafeRoot), so they
-- clear notches and the home indicator. The buttons are parented to that
-- root directly: a full-screen holder frame in the same ScreenGui takes the
-- taps meant for the weapon strip under it (measured in the emulator).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local AimController = require(script.Parent.AimController)
local FrameProfile = require(script.Parent.FrameProfile)
local Hud = require(script.Parent.Hud)
local InputMode = require(script.Parent.InputMode)
local LockOn = require(script.Parent.LockOn)
local TouchInput = require(script.Parent.TouchInput)
local Ui = require(script.Parent.Ui)
local UiKitArt = require(script.Parent.UiKitArt)
local WeaponController = require(script.Parent.WeaponController)

local WeaponConfig = require(ReplicatedStorage.Shared.WeaponConfig)

local TouchControls = {}

local C = Ui.Colors
local F = Ui.Fonts
local INK = Color3.fromRGB(16, 16, 12)

-- Diameters and centres (design units, from the safe area's corners).
local FIRE_SIZE, FIRE_LEFT_SIZE, SIGHT_SIZE = 150, 124, 96
local FIRE_POS = UDim2.new(1, -99, 1, -101)
local SIGHT_POS = UDim2.new(1, -199, 1, -201)
local FIRE_LEFT_POS = UDim2.new(0, 98, 1, -132)
local IDLE_FILL, PRESSED_FILL = 0.42, 0.12

type RoundButton = {
	button: TextButton,
	stroke: UIStroke,
	scale: UIScale,
	label: TextLabel,
	icons: { [string]: ImageLabel },
	held: { [InputObject]: true },
}

local parent: Frame
local visible = false
local fireButtons: { RoundButton } = {}
local sight: RoundButton
local sightGlyph: { GuiObject } = {}

local function pressable(input: InputObject): boolean
	local kind = input.UserInputType
	return kind == Enum.UserInputType.Touch or kind == Enum.UserInputType.MouseButton1
end

local function roundButton(name: string, size: number, position: UDim2): RoundButton
	local button = Ui.new("TextButton", {
		Name = name,
		Text = "",
		AutoButtonColor = false,
		BackgroundColor3 = C.Panel,
		BackgroundTransparency = IDLE_FILL,
		BorderSizePixel = 0,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = position,
		Size = UDim2.fromOffset(size, size),
		Visible = false,
		ZIndex = 5,
		Parent = parent,
	}, {
		Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }),
		Ui.new("Frame", {
			Name = "Ring",
			BackgroundTransparency = 1,
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.5),
			Size = UDim2.new(1, -14, 1, -14),
		}, {
			Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }),
			Ui.new("UIStroke", { Color = C.AmberDim, Thickness = 1.5, Transparency = 0.35 }),
		}),
	})
	local stroke = Ui.new("UIStroke", { Color = C.Amber, Thickness = 3, Transparency = 0.1, ApplyStrokeMode = Enum.ApplyStrokeMode.Border, Parent = button })
	local label = Ui.label({
		Name = "Label",
		Text = "",
		FontFace = F.Header,
		TextSize = math.floor(size * 0.17),
		TextColor3 = C.Amber,
		TextXAlignment = Enum.TextXAlignment.Center,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Size = UDim2.new(1, 0, 0, math.floor(size * 0.2)),
		ZIndex = 3,
		Parent = button,
	})
	Ui.outline(label, 1.5)
	return {
		button = button,
		stroke = stroke,
		scale = Ui.new("UIScale", { Parent = button }),
		label = label,
		icons = {},
		held = {},
	}
end

local function fireButton(name: string, size: number, position: UDim2): RoundButton
	local rb = roundButton(name, size, position)
	rb.label.Text = "FIRE"
	rb.label.Position = UDim2.fromScale(0.5, 0.69)
	local width = math.floor(size * 0.62)
	for _, weapon in WeaponConfig.SLOTS do
		local icon = UiKitArt.weaponIcon(weapon, {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(0.5, 0.42),
			Size = UDim2.fromOffset(width, math.floor(width / 3)),
			ImageColor3 = C.Text,
			Visible = false,
			ZIndex = 2,
			Parent = rb.button,
		})
		if icon then
			rb.icons[weapon] = icon
		end
	end
	if next(rb.icons) == nil then
		rb.label.Position = UDim2.fromScale(0.5, 0.5)
	end
	rb.button.InputBegan:Connect(function(input)
		if pressable(input) then
			TouchInput.press(input)
			rb.held[input] = true
		end
	end)
	table.insert(fireButtons, rb)
	return rb
end

-- SIGHT: a small reticle glyph over the word; toggles the gunsight.
local function buildSight()
	sight = roundButton("Sight", SIGHT_SIZE, SIGHT_POS)
	sight.label.Text = "SIGHT"
	sight.label.TextSize = 15
	sight.label.Position = UDim2.fromScale(0.5, 0.72)
	local glyph = Ui.new("Frame", {
		Name = "Reticle",
		BackgroundTransparency = 1,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.4),
		Size = UDim2.fromOffset(34, 34),
		ZIndex = 2,
		Parent = sight.button,
	}, {
		Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }),
		Ui.new("UIStroke", { Color = C.Text, Thickness = 2 }),
	})
	table.insert(sightGlyph, glyph)
	for _, spec in { { 0.5, 0, 2, 10 }, { 0.5, 1, 2, 10 }, { 0, 0.5, 10, 2 }, { 1, 0.5, 10, 2 } } do
		table.insert(sightGlyph, Ui.new("Frame", {
			BackgroundColor3 = C.Text,
			BorderSizePixel = 0,
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromScale(spec[1], spec[2]),
			Size = UDim2.fromOffset(spec[3], spec[4]),
			ZIndex = 2,
			Parent = glyph,
		}))
	end
	sight.button.InputBegan:Connect(function(input)
		if pressable(input) and AimController.getMode() == "Turret" then
			TouchInput.setSight(not TouchInput.sightOn())
		end
	end)
end

local function build(root: Frame)
	parent = root
	fireButton("Fire", FIRE_SIZE, FIRE_POS)
	fireButton("FireLeft", FIRE_LEFT_SIZE, FIRE_LEFT_POS)
	buildSight()
end

-- What the FIRE buttons say and how they're lit for the selected weapon.
local function fireState(weapon: string): (string, Color3, boolean)
	if weapon == "MG" then
		if WeaponController.getLockRemaining() > 0 then
			return "HOT", C.Red, false
		end
		return "FIRE", C.Amber, false
	end
	if WeaponController.getAmmo(weapon) <= 0 then
		return "EMPTY", C.Red, false
	elseif WeaponController.getReload(weapon) > 0 then
		return "RELOAD", C.AmberDim, false
	elseif weapon == "Missile" then
		local state = LockOn.getState()
		if state == "Locked" then
			return "FIRE", C.Red, true
		end
	end
	return "FIRE", C.Amber, false
end

local function setVisible(on: boolean)
	if on == visible then
		return
	end
	visible = on
	for _, rb in fireButtons do
		rb.button.Visible = on
	end
	sight.button.Visible = on
end

local function update()
	setVisible(InputMode.isTouch())
	if not visible then
		return
	end
	local weapon = WeaponController.getWeapon()
	local text, color, locked = fireState(weapon)
	local blink = locked and math.floor(os.clock() * 6) % 2 == 0
	for _, rb in fireButtons do
		for input in rb.held do
			if not TouchInput.holding(input) then
				rb.held[input] = nil
			end
		end
		local down = next(rb.held) ~= nil
		rb.button.BackgroundTransparency = if down then PRESSED_FILL else IDLE_FILL
		rb.button.BackgroundColor3 = if blink then Color3.fromRGB(90, 16, 12) else C.Panel
		rb.scale.Scale = if down then 0.93 else 1
		rb.stroke.Color = color
		rb.label.Text = text
		rb.label.TextColor3 = color
		for name, icon in rb.icons do
			icon.Visible = name == weapon
		end
	end
	local on = TouchInput.sightOn()
	sight.button.BackgroundColor3 = if on then C.Amber else C.Panel
	sight.button.BackgroundTransparency = if on then 0.1 else IDLE_FILL
	sight.label.TextColor3 = if on then INK else C.Amber
	-- Dark text on the lit plate needs no black outline.
	local outline = sight.label:FindFirstChildOfClass("UIStroke")
	if outline then
		outline.Enabled = not on
	end
	local glyphColor = if on then INK else C.Text
	for _, part in sightGlyph do
		if part:IsA("Frame") and part.BackgroundTransparency < 1 then
			part.BackgroundColor3 = glyphColor
		end
		local stroke = part:FindFirstChildOfClass("UIStroke")
		if stroke then
			stroke.Color = glyphColor
		end
	end
end

function TouchControls.start()
	build(Hud.getSafeRoot())
	RunService.RenderStepped:Connect(FrameProfile.wrap("TouchControls", function()
		if parent.Visible then
			update()
		end
	end))
end

return TouchControls
