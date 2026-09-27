--!strict
-- Victory flares: a volley of coloured signal flares over the basin when the
-- run is won (client/init: GameState "Victory").
--
-- Daylight only (spec §7.1, 3397923): the night work that lived here (the
-- searchlight sweep and dusty cones, the random illumination flares, the
-- warm pit lamp) was retired with the dusk and night presets. The
-- searchlight towers WorldBuilder builds stay as dormant props, lights off.

local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local NightFx = {}

local FLARE_FALL = 5
local FLARE_LIFETIME = 16
local VOLLEY = {
	Color3.fromRGB(120, 255, 120),
	Color3.fromRGB(255, 190, 60),
	Color3.fromRGB(255, 90, 70),
	Color3.fromRGB(255, 245, 220),
}

local function launchFlare(color: Color3)
	local target = Vector3.new(math.random(-420, 420), 150 + math.random(0, 40), math.random(-650, -220))
	local flare = Instance.new("Part")
	flare.Name = "Flare"
	flare.Shape = Enum.PartType.Ball
	flare.Size = Vector3.new(1.6, 1.6, 1.6)
	flare.Material = Enum.Material.Neon
	flare.Color = color
	flare.Anchored = true
	flare.CanCollide = false
	flare.CanQuery = false
	flare.CastShadow = false
	flare.CFrame = CFrame.new(target)
	local light = Instance.new("PointLight")
	light.Range = 60
	light.Brightness = 3
	light.Color = color
	light.Parent = flare
	local trail = Instance.new("ParticleEmitter")
	trail.Rate = 18
	trail.Lifetime = NumberRange.new(2, 3)
	trail.Speed = NumberRange.new(0.5, 1)
	trail.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.5), NumberSequenceKeypoint.new(1, 6) })
	trail.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.6), NumberSequenceKeypoint.new(1, 1) })
	trail.Color = ColorSequence.new(Color3.fromRGB(180, 170, 160))
	trail.LightInfluence = 1
	trail.Acceleration = Vector3.new(0, 2, 0)
	trail.Parent = flare
	flare.Parent = Workspace:FindFirstChild("Projectiles") or Workspace

	local born = os.clock()
	local connection: RBXScriptConnection
	connection = RunService.RenderStepped:Connect(function(dt)
		local age = os.clock() - born
		if age > FLARE_LIFETIME or not flare.Parent then
			connection:Disconnect()
			flare:Destroy()
			return
		end
		local drift = Vector3.new(math.sin(age * 0.8) * 0.6, -FLARE_FALL, 0) * dt
		flare.CFrame = flare.CFrame + drift
		-- Flicker, then burn out over the last few seconds.
		local fade = math.clamp((FLARE_LIFETIME - age) / 3, 0, 1)
		light.Brightness = (2.6 + math.noise(age * 8) * 0.8) * fade
	end)
end

-- Victory celebration: a volley of coloured flares over the basin.
function NightFx.celebrate()
	for i = 1, 12 do
		task.delay(i * 0.35, launchFlare, VOLLEY[(i - 1) % #VOLLEY + 1])
	end
end

return NightFx
