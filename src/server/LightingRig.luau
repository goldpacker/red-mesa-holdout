--!strict
-- Base lighting and post-effect rig for Red Mesa. WorldBuilder calls
-- LightingRig.build() once at server start; TimeOfDay then re-keys the same
-- Lighting properties and named effects (Atmosphere, Bloom, SunRays, Grade)
-- per time-of-day preset.

local Lighting = game:GetService("Lighting")

local LightingRig = {}

local function ensureEffect(className: string, name: string): Instance
	local existing = Lighting:FindFirstChild(name)
	if existing then
		return existing
	end
	local inst = Instance.new(className)
	inst.Name = name
	inst.Parent = Lighting
	return inst
end

function LightingRig.build()
	-- The default place template ships blur effects we don't want.
	for _, child in Lighting:GetChildren() do
		if child:IsA("DepthOfFieldEffect") or child:IsA("BlurEffect") then
			child:Destroy()
		end
	end
	Lighting.ClockTime = 15.2
	Lighting.GeographicLatitude = 30
	Lighting.Brightness = 3
	Lighting.Ambient = Color3.fromRGB(90, 70, 60)
	Lighting.OutdoorAmbient = Color3.fromRGB(150, 120, 100)
	Lighting.EnvironmentDiffuseScale = 0.6
	Lighting.EnvironmentSpecularScale = 0.4
	Lighting.GlobalShadows = true

	local atmosphere = ensureEffect("Atmosphere", "Atmosphere") :: Atmosphere
	atmosphere.Density = 0.2
	atmosphere.Offset = 0.05
	atmosphere.Color = Color3.fromRGB(235, 190, 150)
	atmosphere.Decay = Color3.fromRGB(190, 120, 90)
	atmosphere.Glare = 0.1
	atmosphere.Haze = 0.5

	local bloom = ensureEffect("BloomEffect", "Bloom") :: BloomEffect
	bloom.Intensity = 0.6
	bloom.Size = 28
	bloom.Threshold = 1.6

	local rays = ensureEffect("SunRaysEffect", "SunRays") :: SunRaysEffect
	rays.Intensity = 0.06
	rays.Spread = 0.6

	local grade = ensureEffect("ColorCorrectionEffect", "Grade") :: ColorCorrectionEffect
	grade.Contrast = 0.12
	grade.Saturation = 0.08
	grade.TintColor = Color3.fromRGB(255, 244, 232)
end

return LightingRig
