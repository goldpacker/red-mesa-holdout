--!strict
-- Client-side presentation effects: tracers, muzzle flash, impacts,
-- explosions, enemy fire. All parts are short-lived and capped.

local Debris = game:GetService("Debris")
local TweenService = game:GetService("TweenService")
local Workspace = game:GetService("Workspace")

local Effects = {}

local MAX_LIVE = 160
local live = 0

local function container(): Instance
	return Workspace:FindFirstChild("Projectiles") or Workspace
end

local function track(inst: Instance, lifetime: number)
	live += 1
	Debris:AddItem(inst, lifetime)
	task.delay(lifetime, function()
		live -= 1
	end)
end

local function budget(): boolean
	return live < MAX_LIVE
end

local function fxPart(props: { [string]: any }): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Material = Enum.Material.Neon
	for k, v in props do
		(p :: any)[k] = v
	end
	p.Parent = container()
	return p
end

local function fade(part: BasePart, duration: number, goal: { [string]: any })
	goal.Transparency = 1
	TweenService:Create(part, TweenInfo.new(duration, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), goal):Play()
end

-- A glowing streak that travels from `from` to `to`.
function Effects.tracer(from: Vector3, to: Vector3, color: Color3?, width: number?)
	if not budget() then
		return
	end
	local dist = (to - from).Magnitude
	if dist < 1 then
		return
	end
	local length = math.min(dist, 22)
	local w = width or 0.35
	local streak = fxPart({
		Size = Vector3.new(w, w, length),
		Color = color or Color3.fromRGB(255, 214, 120),
		CFrame = CFrame.lookAt(from, to) * CFrame.new(0, 0, -length / 2),
	})
	local travel = math.clamp(dist / 900, 0.04, 0.35)
	local endCf = CFrame.lookAt(from, to) * CFrame.new(0, 0, -(dist - length / 2))
	TweenService:Create(streak, TweenInfo.new(travel, Enum.EasingStyle.Linear), { CFrame = endCf }):Play()
	track(streak, travel + 0.02)
end

function Effects.muzzleFlash(position: Vector3, direction: Vector3)
	if not budget() then
		return
	end
	local flash = fxPart({
		Shape = Enum.PartType.Ball,
		Size = Vector3.new(1.6, 1.6, 1.6),
		Color = Color3.fromRGB(255, 200, 90),
		CFrame = CFrame.new(position + direction * 0.6),
	})
	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(255, 180, 80)
	light.Range = 14
	light.Brightness = 3
	light.Parent = flash
	fade(flash, 0.06, { Size = Vector3.new(2.6, 2.6, 2.6) })
	track(flash, 0.07)
end

-- Dust puff on terrain, sparks on metal/enemies.
function Effects.impact(position: Vector3, onEnemy: boolean)
	if not budget() then
		return
	end
	if onEnemy then
		local spark = fxPart({
			Shape = Enum.PartType.Ball,
			Size = Vector3.new(1.2, 1.2, 1.2),
			Color = Color3.fromRGB(255, 240, 180),
			CFrame = CFrame.new(position),
		})
		fade(spark, 0.12, { Size = Vector3.new(2.4, 2.4, 2.4) })
		track(spark, 0.13)
	else
		local puff = fxPart({
			Shape = Enum.PartType.Ball,
			Material = Enum.Material.SmoothPlastic,
			Size = Vector3.new(2, 2, 2),
			Color = Color3.fromRGB(214, 160, 110),
			Transparency = 0.2,
			CFrame = CFrame.new(position),
		})
		fade(puff, 0.5, { Size = Vector3.new(6, 5, 6), CFrame = CFrame.new(position + Vector3.new(0, 2.5, 0)) })
		track(puff, 0.52)
	end
end

function Effects.explosion(position: Vector3, scale: number)
	local fireball = fxPart({
		Shape = Enum.PartType.Ball,
		Size = Vector3.one * 2 * scale,
		Color = Color3.fromRGB(255, 150, 40),
		CFrame = CFrame.new(position),
	})
	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(255, 140, 60)
	light.Range = 30 * scale
	light.Brightness = 5
	light.Parent = fireball
	fade(fireball, 0.35, { Size = Vector3.one * 9 * scale })
	track(fireball, 0.36)

	for i = 1, 3 do
		local smoke = fxPart({
			Shape = Enum.PartType.Ball,
			Material = Enum.Material.SmoothPlastic,
			Size = Vector3.one * 3 * scale,
			Color = Color3.fromRGB(50, 44, 40),
			Transparency = 0.15,
			CFrame = CFrame.new(position + Vector3.new(math.random(-2, 2), i, math.random(-2, 2)) * scale * 0.5),
		})
		fade(smoke, 1.4 + i * 0.2, {
			Size = Vector3.one * (7 + i * 2) * scale,
			CFrame = CFrame.new(position + Vector3.new(0, (6 + i * 3) * scale, 0)),
		})
		track(smoke, 1.5 + i * 0.2)
	end
end

-- A grenade arcing from `from` to `to` over `duration`, exploding on landing.
function Effects.grenade(from: Vector3, to: Vector3, duration: number)
	local g = fxPart({
		Shape = Enum.PartType.Ball,
		Material = Enum.Material.SmoothPlastic,
		Size = Vector3.new(0.9, 0.9, 0.9),
		Color = Color3.fromRGB(40, 44, 36),
	})
	track(g, duration + 0.1)
	local start = os.clock()
	local height = 26
	task.spawn(function()
		while g.Parent do
			local t = math.min(1, (os.clock() - start) / duration)
			local p = from:Lerp(to, t) + Vector3.new(0, math.sin(t * math.pi) * height, 0)
			g.CFrame = CFrame.new(p)
			if t >= 1 then
				break
			end
			task.wait()
		end
		g:Destroy()
		Effects.explosion(to, 1.2)
	end)
end

-- Persistent fire and smoke column; destroy the returned part to stop it.
function Effects.burning(position: Vector3, scale: number): BasePart
	local anchor = fxPart({
		Transparency = 1,
		Size = Vector3.one,
		CFrame = CFrame.new(position),
	})
	local fire = Instance.new("Fire")
	fire.Size = 10 * scale
	fire.Heat = 15
	fire.Color = Color3.fromRGB(255, 130, 40)
	fire.SecondaryColor = Color3.fromRGB(255, 220, 90)
	fire.Parent = anchor
	local smoke = Instance.new("Smoke")
	smoke.Size = 12 * scale
	smoke.RiseVelocity = 18
	smoke.Opacity = 0.35
	smoke.Color = Color3.fromRGB(40, 36, 34)
	smoke.Parent = anchor
	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(255, 130, 50)
	light.Range = 30
	light.Brightness = 3
	light.Parent = anchor
	return anchor
end

-- Makes enemy muzzle flashes easy to see from the mesa.
function Effects.enemyShot(from: Vector3, to: Vector3)
	local flash = fxPart({
		Shape = Enum.PartType.Ball,
		Size = Vector3.new(2.2, 2.2, 2.2),
		Color = Color3.fromRGB(255, 90, 60),
		CFrame = CFrame.new(from),
	})
	fade(flash, 0.15, {})
	track(flash, 0.16)
	-- Rifle rounds visibly fall a little short around the sandbags.
	local scatter = Vector3.new(math.random(-6, 6), math.random(-3, 1), math.random(-6, 6))
	Effects.tracer(from, to + scatter, Color3.fromRGB(255, 80, 60), 0.3)
end

return Effects
