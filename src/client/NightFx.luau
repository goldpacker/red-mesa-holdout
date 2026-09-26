--!strict
-- Client-side night ambience: sweeps the mesa searchlights across the basin
-- and pops illumination flares over the battlefield at dusk and night so
-- enemies stay readable (GAME_SPEC §7.1).

local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local GameState = require(script.Parent.GameState)

local NightFx = {}

local FLARE_INTERVAL = { 7, 12 }
local FLARE_FALL = 5
local FLARE_LIFETIME = 16

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include

type Light = { model: Model, head: BasePart, lens: BasePart, pool: BasePart?, base: CFrame, phase: number }
local lights: { Light } = {}
local nextFlare = 0

local function isNight(): boolean
	local t = Workspace:GetAttribute("TimeOfDay")
	return t == "Night" or t == "Dusk"
end

local function collect()
	table.clear(lights)
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local folder = battlefield and battlefield:FindFirstChild("Searchlights")
	if not folder then
		return
	end
	for i, model in folder:GetChildren() do
		local head = model:FindFirstChild("Head") :: BasePart?
		local lens = model:FindFirstChild("Lens") :: BasePart?
		if model:IsA("Model") and head and lens then
			table.insert(lights, {
				model = model,
				head = head,
				lens = lens,
				pool = model:FindFirstChild("Pool") :: BasePart?,
				base = head.CFrame,
				phase = i * 2.1,
			})
		end
	end
	groundParams.FilterDescendantsInstances = { Workspace.Terrain }
end

local function sweep(t: number)
	for _, light in lights do
		local pos = light.base.Position
		-- Slow figure-eight sweep across the front arc.
		local yaw = math.sin(t * 0.23 + light.phase) * math.rad(55)
		local pitch = math.rad(-9) + math.sin(t * 0.37 + light.phase * 1.7) * math.rad(4)
		local cf = CFrame.new(pos) * CFrame.Angles(0, yaw, 0) * CFrame.Angles(pitch, 0, 0)
		light.model:PivotTo(cf)
		if light.pool then
			local hit = Workspace:Raycast(light.lens.Position, cf.LookVector * 900, groundParams)
			if hit then
				light.pool.CFrame = CFrame.new(hit.Position + Vector3.new(0, 45, 0))
			end
		end
	end
end

local function launchFlare()
	local target = Vector3.new(math.random(-420, 420), 150 + math.random(0, 40), math.random(-650, -220))
	local flare = Instance.new("Part")
	flare.Name = "Flare"
	flare.Shape = Enum.PartType.Ball
	flare.Size = Vector3.new(1.6, 1.6, 1.6)
	flare.Material = Enum.Material.Neon
	flare.Color = Color3.fromRGB(255, 236, 190)
	flare.Anchored = true
	flare.CanCollide = false
	flare.CanQuery = false
	flare.CastShadow = false
	flare.CFrame = CFrame.new(target)
	local light = Instance.new("PointLight")
	light.Range = 60
	light.Brightness = 3
	light.Color = Color3.fromRGB(255, 228, 180)
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

function NightFx.start()
	collect()
	Workspace.ChildAdded:Connect(function(child)
		if child.Name == "Battlefield" then
			task.wait(1)
			collect()
		end
	end)
	RunService.RenderStepped:Connect(function()
		if (#lights == 0 or not lights[1].model.Parent) and Workspace:FindFirstChild("Battlefield") then
			collect()
		end
		local night = isNight()
		if night then
			sweep(os.clock())
		end
		local now = os.clock()
		if night and GameState.phase() == "Wave" and now >= nextFlare then
			nextFlare = now + math.random(FLARE_INTERVAL[1] * 10, FLARE_INTERVAL[2] * 10) / 10
			launchFlare()
		end
	end)
end

return NightFx
