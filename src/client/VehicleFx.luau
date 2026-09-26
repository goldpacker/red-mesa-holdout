--!strict
-- Client presentation for enemy vehicles: turret tracking, rotor and wheel
-- spin, blinking nav strobes, engine loops, the Siege Crawler's cannon
-- charge glow, and every destruction effect (explosions, burning wrecks,
-- smoke trails of crashing aircraft and thrown debris, boss death).
--
-- Driven entirely by replicated state: models in Workspace.Enemies (Kind +
-- State attributes, "<Name>Motor" Motor6Ds from EnemyTypes/Common/Rig) and
-- models entering Workspace.Wrecks with State = Dead | Crashing | Thrown |
-- Debris | Dying | Wreck and an FxScale attribute.

local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Particles = require(script.Parent.VehicleFxParticles)
local Sfx = require(script.Parent.Sfx)

local VehicleFx = {}

local PIVOT = Config.TURRET_PIVOT
local ENGINE_LOOPS = { Tank = "TankEngine", Buggy = "BuggyEngine", Helicopter = "HeliRotor", SiegeCrawler = "TankEngine" }
local TURRET_RATE = { Tank = 1.1, Buggy = 3.5, SiegeCrawler = 0.5 }
local AIMING_STATES = { Aim = true, Fire = true, Hold = true }

type Vehicle = {
	model: Model,
	kind: string,
	root: BasePart,
	motors: { [string]: Motor6D },
	yaw: { [string]: number },
	spin: number,
	lastPos: Vector3,
	loop: Sound?,
	strobes: { BasePart },
	beams: { BasePart },
	flyby: boolean,
}

local night = false
local function isNight(): boolean
	local t = Lighting.ClockTime
	return t >= 18.3 or t < 6
end

local vehicles: { [Model]: Vehicle } = {}
local aimController: any = nil

local function shake(amount: number)
	if not aimController then
		local ok, mod = pcall(require, script.Parent.AimController)
		aimController = if ok then mod else false
	end
	if aimController and aimController.shake then
		pcall(aimController.shake, amount)
	end
end

-- Camera shake scaled down with distance from the outpost.
local function shakeFor(position: Vector3, scale: number)
	local d = (position - PIVOT).Magnitude
	local amount = scale * 0.5 * math.clamp(1 - d / 700, 0, 1)
	if amount > 0.04 then
		shake(amount)
	end
end

local function centre(model: Model): (Vector3, Vector3)
	local ok, cf, size = pcall(function()
		local c, s = model:GetBoundingBox()
		return c, s
	end)
	if ok then
		return (cf :: CFrame).Position, size :: Vector3
	end
	local root = model.PrimaryPart
	return if root then root.Position else Vector3.zero, Vector3.new(8, 4, 8)
end

local function rootOf(model: Model): BasePart?
	local r = model.PrimaryPart or model:FindFirstChild("Root", true)
	return if r and r:IsA("BasePart") then r else nil
end

local function stopLoop(v: Vehicle)
	if v.loop then
		v.loop:Destroy()
		v.loop = nil
	end
end

local function register(model: Model)
	if vehicles[model] then
		return
	end
	local kind = model:GetAttribute("Kind")
	if type(kind) ~= "string" or kind == "Infantry" then
		return
	end
	local root = rootOf(model)
	if not root then
		return
	end
	local motors = {}
	for _, d in root:GetChildren() do
		if d:IsA("Motor6D") then
			motors[(string.gsub(d.Name, "Motor$", ""))] = d
		end
	end
	local strobes, beams = {}, {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and d.Name == "NavStrobe" then
			table.insert(strobes, d)
		elseif d:IsA("BasePart") and d.Name == "SearchBeam" then
			table.insert(beams, d)
		elseif d:IsA("BasePart") and d:GetAttribute("Burning") then
			Particles.burn(d, d:GetAttribute("Burning") :: number, Vector3.zero)
		end
	end
	local v: Vehicle = {
		model = model,
		kind = kind,
		root = root,
		motors = motors,
		yaw = {},
		spin = 0,
		lastPos = root.Position,
		loop = nil,
		strobes = strobes,
		beams = beams,
		flyby = false,
	}
	local loopName = ENGINE_LOOPS[kind]
	if loopName then
		v.loop = Sfx.attachLoop(loopName, root)
		if v.loop and kind == "SiegeCrawler" then
			v.loop.PlaybackSpeed *= 0.6
			v.loop.Volume *= 1.4
		end
	end
	vehicles[model] = v
	-- Socket fires appear on the boss when a weak point is destroyed.
	model.DescendantAdded:Connect(function(d)
		if d:IsA("BasePart") and d:GetAttribute("Burning") then
			Particles.burn(d, d:GetAttribute("Burning") :: number, Vector3.zero)
		end
	end)
end

local function unregister(model: Model)
	local v = vehicles[model]
	if v then
		stopLoop(v)
		for _, b in v.beams do
			b.Transparency = 1
		end
		vehicles[model] = nil
	end
end

-- Smoothly turns a named turret motor toward `targetYaw`.
local function driveTurret(v: Vehicle, name: string, targetYaw: number, rate: number, dt: number)
	local motor = v.motors[name]
	if not motor then
		return
	end
	local current = v.yaw[name] or 0
	local delta = (targetYaw - current + math.pi) % (2 * math.pi) - math.pi
	current += math.clamp(delta, -rate * dt, rate * dt)
	v.yaw[name] = current
	motor.Transform = CFrame.Angles(0, current, 0)
end

local function yawToOutpost(v: Vehicle, name: string): number
	local motor = v.motors[name]
	if not motor then
		return 0
	end
	local rel = (v.root.CFrame * motor.C0):PointToObjectSpace(PIVOT)
	return math.atan2(-rel.X, -rel.Z)
end

local function animateBoss(v: Vehicle, dt: number, now: number)
	for _, name in { "TurretLeft", "TurretRight", "MainCannon" } do
		driveTurret(v, name, yawToOutpost(v, name), TURRET_RATE.SiegeCrawler * (if name == "MainCannon" then 0.6 else 1), dt)
	end
	local glow = v.model:FindFirstChild("CannonGlow", true)
	if glow and glow:IsA("BasePart") then
		local charging = v.model:GetAttribute("Charging") == true
		local light = glow:FindFirstChildWhichIsA("PointLight")
		local flare = glow:FindFirstChild("ChargeFlare") :: ParticleEmitter?
		if not flare then
			flare = Particles.chargeFlare(glow)
		end
		if charging then
			local ends = (v.model:GetAttribute("ChargeEnd") :: number?) or now
			local total = 5.5
			local frac = math.clamp(1 - (ends - Workspace:GetServerTimeNow()) / total, 0, 1)
			local pulse = 0.85 + 0.15 * math.sin(now * (8 + frac * 20))
			glow.Transparency = 1 - (0.25 + 0.7 * frac) * pulse
			glow.Size = Vector3.one * (2 + frac * 7)
			if light then
				light.Brightness = frac * 12 * pulse
				light.Range = 25 + frac * 50
			end
			if flare then
				flare.Rate = 10 + 50 * frac
				flare.Size = NumberSequence.new({
					NumberSequenceKeypoint.new(0, 4 + 10 * frac),
					NumberSequenceKeypoint.new(0.5, 10 + 22 * frac),
					NumberSequenceKeypoint.new(1, 3),
				})
			end
		else
			glow.Transparency = 1
			if light then
				light.Brightness = 0
			end
			if flare then
				flare.Rate = 0
			end
		end
	end
	if v.model:GetAttribute("CoreExposed") then
		local core = v.model:FindFirstChild("Core", true)
		if core and core:IsA("BasePart") then
			local k = 0.5 + 0.5 * math.sin(now * 5)
			core.Color = Color3.fromRGB(255, 60 + 80 * k, 20 + 30 * k)
		end
	end
end

local function animate(v: Vehicle, dt: number, now: number)
	local model = v.model
	local state = model:GetAttribute("State")
	local pos = v.root.Position
	local speed = if dt > 0 then (pos - v.lastPos).Magnitude / dt else 0
	v.lastPos = pos
	if v.kind == "Tank" then
		local target = if AIMING_STATES[state] then yawToOutpost(v, "Turret") else 0
		driveTurret(v, "Turret", target, TURRET_RATE.Tank, dt)
	elseif v.kind == "Buggy" then
		driveTurret(v, "Gun", yawToOutpost(v, "Gun"), TURRET_RATE.Buggy, dt)
		v.spin -= math.min(speed, 80) / 1.55 * dt
		for _, w in { "WheelFL", "WheelFR", "WheelRL", "WheelRR" } do
			local m = v.motors[w]
			if m then
				m.Transform = CFrame.Angles(v.spin, 0, 0)
			end
		end
	elseif v.kind == "Helicopter" then
		v.spin += dt
		local main, tail = v.motors.MainRotor, v.motors.TailRotor
		if main then
			main.Transform = CFrame.Angles(0, v.spin * 26, 0)
		end
		if tail then
			tail.Transform = CFrame.Angles(v.spin * 40, 0, 0)
		end
	elseif v.kind == "Jet" then
		if not v.flyby and (pos - PIVOT).Magnitude < 700 then
			v.flyby = true
			Sfx.playAt("JetFlyby", pos, 0.1)
		end
	elseif v.kind == "SiegeCrawler" then
		animateBoss(v, dt, now)
	end
	-- Searchlight shafts only read (and only make sense) after dark.
	for _, b in v.beams do
		b.Transparency = if night then 0.9 else 1
	end
	-- Anti-collision strobes: a short flash every 1.1 s.
	if #v.strobes > 0 then
		local on = (now + (model:GetAttribute("EnemyId") :: number? or 0) * 0.37) % 1.1 < 0.12
		for _, s in v.strobes do
			s.Transparency = if on then 0 else 0.85
		end
	end
end

---------------------------------------------------------------------------
-- Destruction
---------------------------------------------------------------------------

local function scaleOf(model: Model): number
	return (model:GetAttribute("FxScale") :: number?) or 1
end

local function explodeModel(model: Model, air: boolean)
	local c = centre(model)
	local s = scaleOf(model)
	Particles.explosion(c, s * 1.2, { air = air })
	Sfx.playAt(if air then "AirBurst" elseif s >= 1 then "Explosion" else "ExplosionSmall", c, 0.15)
	shakeFor(c, s)
end

local function burnModel(model: Model, count: number, scale: number)
	local root = rootOf(model)
	if not root then
		return
	end
	local _, size = centre(model)
	for i = 1, count do
		local offset = if i == 1
			then Vector3.new(0, root.Size.Y * 0.5, 0)
			else Vector3.new((math.random() - 0.5) * size.X * 0.6, root.Size.Y * 0.5, (math.random() - 0.5) * size.Z * 0.6)
		Particles.burn(root, scale * (if i == 1 then 1 else 0.7), offset, i > 2)
	end
end

local trails: { [Model]: { ParticleEmitter } } = {}

local function stopTrail(model: Model)
	local list = trails[model]
	if list then
		for _, e in list do
			e.Enabled = false
		end
		trails[model] = nil
	end
end

-- Boss: a chain of blasts across the hull, then the final one when the
-- server flips State to "Wreck".
local function bossSequence(model: Model)
	local duration = (model:GetAttribute("DeathDuration") :: number?) or 2.6
	local start = os.clock()
	task.spawn(function()
		while model.Parent and os.clock() - start < duration do
			local c, size = centre(model)
			local p = c + Vector3.new((math.random() - 0.5) * size.X * 0.8, (math.random() - 0.2) * size.Y * 0.5, (math.random() - 0.5) * size.Z * 0.8)
			Particles.explosion(p, 1.2 + math.random() * 0.9, { light = true, debris = math.random() < 0.5 })
			Sfx.playAt("Explosion", p, 0.3)
			shake(0.25)
			task.wait(0.18 + math.random() * 0.2)
		end
	end)
end

local function onWreckState(model: Model)
	local state = model:GetAttribute("State")
	local root = rootOf(model)
	if state == "Dead" then
		explodeModel(model, false)
		burnModel(model, if scaleOf(model) >= 1.2 then 2 else 1, scaleOf(model))
	elseif state == "Crashing" then
		local c = centre(model)
		Particles.explosion(c, scaleOf(model) * 0.7, { air = true, debris = false })
		Sfx.playAt("AirBurst", c, 0.15)
		if root then
			trails[model] = Particles.trail(root, scaleOf(model))
		end
	elseif state == "Thrown" then
		local c = centre(model)
		Particles.explosion(c, scaleOf(model), { light = true, debris = false })
		local p = model.PrimaryPart or model:FindFirstChildWhichIsA("BasePart", true)
		if p then
			trails[model] = Particles.trail(p :: BasePart, scaleOf(model) * 0.6)
		end
	elseif state == "Debris" then
		stopTrail(model)
		local p = model.PrimaryPart or model:FindFirstChildWhichIsA("BasePart", true)
		if p then
			Particles.burn(p :: BasePart, scaleOf(model) * 0.6, Vector3.zero, scaleOf(model) < 0.8)
		end
	elseif state == "Dying" then
		bossSequence(model)
	elseif state == "Wreck" then
		stopTrail(model)
		local big = model:GetAttribute("Kind") == "SiegeCrawler"
		explodeModel(model, false)
		if big then
			local c, size = centre(model)
			for i = 1, 4 do
				task.delay(i * 0.12, function()
					local p = c + Vector3.new((math.random() - 0.5) * size.X * 0.6, size.Y * 0.2, (math.random() - 0.5) * size.Z * 0.6)
					Particles.explosion(p, 2.4, {})
				end)
			end
			shake(1)
		end
		burnModel(model, if big then 5 else 1, if big then 2.2 else scaleOf(model))
	end
end

local function watchWreck(child: Instance)
	if not child:IsA("Model") then
		return
	end
	local model = child :: Model
	unregister(model)
	onWreckState(model)
	model:GetAttributeChangedSignal("State"):Connect(function()
		onWreckState(model)
	end)
	model.AncestryChanged:Connect(function()
		if not model:IsDescendantOf(Workspace) then
			trails[model] = nil
		end
	end)
end

function VehicleFx.start()
	Particles.startFlicker()
	local enemies = Workspace:WaitForChild("Enemies")
	local wrecks = Workspace:WaitForChild("Wrecks")
	for _, child in enemies:GetChildren() do
		if child:IsA("Model") then
			register(child)
		end
	end
	enemies.ChildAdded:Connect(function(child)
		if child:IsA("Model") then
			-- Attributes and motors replicate with the model; defer one frame
			-- so every descendant has arrived.
			task.defer(register, child)
		end
	end)
	enemies.ChildRemoved:Connect(function(child)
		if child:IsA("Model") then
			unregister(child)
		end
	end)
	wrecks.ChildAdded:Connect(watchWreck)

	local nightCheck = 0
	RunService.RenderStepped:Connect(function(dt)
		local now = os.clock()
		if now > nightCheck then
			nightCheck = now + 0.5
			night = isNight()
		end
		for model, v in vehicles do
			if not model.Parent then
				unregister(model)
			else
				animate(v, dt, now)
			end
		end
	end)
end

return VehicleFx
