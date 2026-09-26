--!strict
-- Tiny helpers and the shared palette for the arcade-military HUD look.

local Ui = {}

Ui.Colors = {
	Amber = Color3.fromRGB(255, 178, 36),
	AmberDim = Color3.fromRGB(170, 116, 28),
	Olive = Color3.fromRGB(122, 132, 70),
	OliveDark = Color3.fromRGB(58, 64, 34),
	Panel = Color3.fromRGB(16, 18, 12),
	Text = Color3.fromRGB(240, 228, 196),
	Red = Color3.fromRGB(230, 52, 38),
	Green = Color3.fromRGB(126, 210, 80),
	White = Color3.new(1, 1, 1),
}

Ui.Fonts = {
	Header = Font.new("rbxasset://fonts/families/Sarpanch.json", Enum.FontWeight.Heavy),
	HeaderBold = Font.new("rbxasset://fonts/families/Sarpanch.json", Enum.FontWeight.Bold),
	Label = Font.new("rbxasset://fonts/families/Oswald.json", Enum.FontWeight.Bold),
	Body = Font.new("rbxasset://fonts/families/Oswald.json", Enum.FontWeight.Regular),
	Mono = Font.new("rbxasset://fonts/families/RobotoMono.json", Enum.FontWeight.Bold),
}

function Ui.new(className: string, props: { [string]: any }, children: { Instance }?): any
	local inst = Instance.new(className) :: any
	for key, value in props do
		if key ~= "Parent" then
			inst[key] = value
		end
	end
	if children then
		for _, child in children do
			child.Parent = inst
		end
	end
	if props.Parent then
		inst.Parent = props.Parent
	end
	return inst
end

-- Dark translucent panel with an amber bevel line along the top.
function Ui.panel(props: { [string]: any }): Frame
	local defaults = {
		BackgroundColor3 = Ui.Colors.Panel,
		BackgroundTransparency = 0.3,
		BorderSizePixel = 0,
	}
	for k, v in props do
		defaults[k] = v
	end
	local frame = Ui.new("Frame", defaults, {
		Ui.new("UIStroke", { Color = Ui.Colors.OliveDark, Thickness = 2, Transparency = 0.1 }),
		Ui.new("Frame", {
			Name = "Bevel",
			BackgroundColor3 = Ui.Colors.Amber,
			BackgroundTransparency = 0.35,
			BorderSizePixel = 0,
			Size = UDim2.new(1, 0, 0, 2),
			ZIndex = (props.ZIndex or 1) + 1,
		}),
	})
	return frame
end

function Ui.label(props: { [string]: any }): TextLabel
	local defaults = {
		BackgroundTransparency = 1,
		TextColor3 = Ui.Colors.Text,
		FontFace = Ui.Fonts.Label,
		TextScaled = false,
		TextSize = 18,
		TextXAlignment = Enum.TextXAlignment.Left,
	}
	for k, v in props do
		defaults[k] = v
	end
	return Ui.new("TextLabel", defaults)
end

-- Adds a black outline so text stays readable over the bright desert.
function Ui.outline(label: TextLabel, thickness: number?)
	Ui.new("UIStroke", {
		Parent = label,
		Color = Color3.new(0, 0, 0),
		Thickness = thickness or 1.5,
		Transparency = 0.2,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Contextual,
	})
end

function Ui.button(props: { [string]: any }): TextButton
	local defaults = {
		BackgroundColor3 = Ui.Colors.OliveDark,
		BorderSizePixel = 0,
		TextColor3 = Ui.Colors.Amber,
		FontFace = Ui.Fonts.Header,
		TextSize = 28,
		AutoButtonColor = true,
	}
	for k, v in props do
		defaults[k] = v
	end
	local button = Ui.new("TextButton", defaults, {
		Ui.new("UIStroke", { Color = Ui.Colors.Amber, Thickness = 2, ApplyStrokeMode = Enum.ApplyStrokeMode.Border }),
	})
	return button
end

return Ui
