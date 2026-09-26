--!strict
-- Weapon HUD: weapon strip (slots, ammo, heat, reload), crosshair, hit
-- markers and the gunsight overlay. Owned by the weapons workstream; the
-- core Hud creates the root frame and calls build/update.

local AimController = require(script.Parent.AimController)
local Ui = require(script.Parent.Ui)
local WeaponController = require(script.Parent.WeaponController)

local WeaponHud = {}

local C = Ui.Colors
local F = Ui.Fonts
local refs: { [string]: any } = {}

function WeaponHud.build(root: Frame)
	-- Weapon strip (bottom centre).
	local strip = Ui.panel({ Name = "Weapons", AnchorPoint = Vector2.new(0.5, 1), Position = UDim2.new(0.5, 0, 1, -16), Size = UDim2.fromOffset(420, 86), Parent = root })
	local slots = { { "1", "MACHINE GUN", "∞" }, { "2", "ROCKETS", "--" }, { "3", "AA MISSILES", "--" } }
	refs.slots = {}
	for i, slot in slots do
		local frame = Ui.new("Frame", {
			Name = "Slot" .. i,
			BackgroundColor3 = if i == 1 then C.OliveDark else C.Panel,
			BackgroundTransparency = if i == 1 then 0.1 else 0.5,
			BorderSizePixel = 0,
			Position = UDim2.fromOffset(8 + (i - 1) * 136, 8),
			Size = UDim2.fromOffset(130, 44),
			Parent = strip,
		}, {
			Ui.new("UIStroke", { Color = if i == 1 then C.Amber else C.OliveDark, Thickness = 2 }),
		})
		Ui.label({ Text = slot[1], FontFace = F.Header, TextSize = 18, TextColor3 = C.Amber, Position = UDim2.fromOffset(6, 2), Size = UDim2.fromOffset(16, 18), Parent = frame })
		Ui.label({ Text = slot[2], FontFace = F.Label, TextSize = 14, TextColor3 = if i == 1 then C.Text else Color3.fromRGB(120, 120, 110), Position = UDim2.fromOffset(24, 3), Size = UDim2.fromOffset(104, 16), Parent = frame })
		Ui.label({ Name = "Ammo", Text = slot[3], FontFace = F.Mono, TextSize = 18, TextColor3 = if i == 1 then C.Amber else Color3.fromRGB(120, 120, 110), TextXAlignment = Enum.TextXAlignment.Right, Position = UDim2.fromOffset(0, 20), Size = UDim2.new(1, -8, 0, 20), Parent = frame })
		refs.slots[i] = frame
	end
	Ui.label({ Text = "HEAT", FontFace = F.Label, TextSize = 14, TextColor3 = C.Olive, Position = UDim2.fromOffset(10, 58), Size = UDim2.fromOffset(40, 18), Parent = strip })
	local heatBack = Ui.new("Frame", { BackgroundColor3 = Color3.fromRGB(30, 30, 24), BorderSizePixel = 0, Position = UDim2.fromOffset(52, 60), Size = UDim2.new(1, -62, 0, 14), Parent = strip })
	refs.heatBar = Ui.new("Frame", { BackgroundColor3 = C.Amber, BorderSizePixel = 0, Size = UDim2.fromScale(0, 1), Parent = heatBack })
	refs.overheat = Ui.label({ Text = "OVERHEAT", FontFace = F.Header, TextSize = 14, TextColor3 = C.White, TextXAlignment = Enum.TextXAlignment.Center, Size = UDim2.fromScale(1, 1), Visible = false, Parent = heatBack })

	-- Crosshair + hit marker + gunsight overlay.
	refs.crosshair = Ui.new("Frame", { Name = "Crosshair", BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(40, 40), Parent = root })
	for _, spec in { { 0, -13, 2, 10 }, { 0, 13, 2, 10 }, { -13, 0, 10, 2 }, { 13, 0, 10, 2 } } do
		Ui.new("Frame", {
			BackgroundColor3 = C.Amber,
			BorderSizePixel = 0,
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.new(0.5, spec[1], 0.5, spec[2]),
			Size = UDim2.fromOffset(spec[3], spec[4]),
			Parent = refs.crosshair,
		}, { Ui.new("UIStroke", { Color = Color3.new(0, 0, 0), Thickness = 1, Transparency = 0.3 }) })
	end
	Ui.new("Frame", { BackgroundColor3 = C.Amber, BorderSizePixel = 0, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(3, 3), Parent = refs.crosshair })

	refs.hitmarker = Ui.new("Frame", { Name = "HitMarker", BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(44, 44), Visible = false, Parent = root })
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

	refs.sight = Ui.new("Frame", { Name = "Gunsight", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Visible = false, Parent = root })
	local ring = Ui.new("Frame", { BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(220, 220), Parent = refs.sight }, {
		Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }),
		Ui.new("UIStroke", { Color = Color3.fromRGB(20, 20, 16), Thickness = 6 }),
	})
	Ui.new("Frame", { BackgroundTransparency = 1, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(120, 120), Parent = ring }, {
		Ui.new("UICorner", { CornerRadius = UDim.new(0.5, 0) }),
		Ui.new("UIStroke", { Color = Color3.fromRGB(20, 20, 16), Thickness = 2, Transparency = 0.3 }),
	})
	-- Iron-sight post.
	Ui.new("Frame", { BackgroundColor3 = Color3.fromRGB(20, 20, 16), BorderSizePixel = 0, AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0.5, 6), Size = UDim2.fromOffset(6, 110), Parent = refs.sight })
	for _, side in { -1, 1 } do
		Ui.new("Frame", { BackgroundColor3 = Color3.fromRGB(20, 20, 16), BorderSizePixel = 0, AnchorPoint = Vector2.new(if side < 0 then 1 else 0, 0.5), Position = UDim2.new(0.5, side * 118, 0.5, 0), Size = UDim2.new(0.5, -118, 0, 4), Parent = refs.sight })
	end

end

local function updateHeat()
	local heat = WeaponController.getHeat()
	local locked = WeaponController.getLockRemaining() > 0
	refs.heatBar.Size = UDim2.fromScale(heat, 1)
	if locked then
		local blink = math.floor(os.clock() * 8) % 2 == 0
		refs.heatBar.BackgroundColor3 = if blink then C.Red else C.Amber
		refs.overheat.Visible = true
	else
		refs.heatBar.BackgroundColor3 = if heat > 0.75 then C.Red elseif heat > 0.5 then C.Amber else C.Olive
		refs.overheat.Visible = false
	end
end

function WeaponHud.update()
	updateHeat()
	refs.sight.Visible = AimController.isAiming()
	refs.crosshair.Visible = true
end

function WeaponHud.showHitMarker(killed: boolean)
	local marker = refs.hitmarker :: Frame
	marker.Visible = true
	for _, tick in marker:GetChildren() do
		(tick :: Frame).BackgroundColor3 = if killed then C.Red else C.White
	end
	marker.Size = if killed then UDim2.fromOffset(60, 60) else UDim2.fromOffset(44, 44)
	local token = os.clock()
	marker:SetAttribute("Token", token)
	task.delay(if killed then 0.25 else 0.1, function()
		if marker:GetAttribute("Token") == token then
			marker.Visible = false
		end
	end)
end

return WeaponHud
