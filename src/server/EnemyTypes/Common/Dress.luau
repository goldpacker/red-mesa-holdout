--!strict
-- Adds gameplay lighting to imported Blender vehicles (the fallbacks build
-- their own): headlights, searchlights and nav lights at the contract
-- attachments, so night waves stay readable whichever model is in use.
-- Call before Rig.prepare (new parts are welded like any other part).

local Kit = require(script.Parent.Kit)

local Dress = {}

local NAV_RED = Color3.fromRGB(255, 40, 30)
local NAV_GREEN = Color3.fromRGB(40, 255, 90)

local function hostPart(model: Model): BasePart?
	local root = model:FindFirstChild("Root", true)
	return if root and root:IsA("BasePart") then root else nil
end

local function lampAt(model: Model, name: string, cf: CFrame, size: Vector3, color: Color3): Part
	return Kit.lamp(model, name, size, cf, color)
end

local function eachAttachment(model: Model, name: string, fn: (Attachment) -> ())
	for _, d in model:GetDescendants() do
		if d:IsA("Attachment") and d.Name == name then
			fn(d)
		end
	end
end

local function hasLights(model: Model): boolean
	return model:FindFirstChildWhichIsA("SpotLight", true) ~= nil
end

-- Ground vehicles: headlights at a Headlight attachment, else a pair at
-- the front of the hull.
function Dress.ground(model: Model)
	if hasLights(model) then
		return
	end
	local found = false
	local count = 0
	eachAttachment(model, "Headlight", function()
		count += 1
	end)
	-- One attachment = a light bar; a pair = two round lamps (HS-3 tank).
	local size = if count >= 2 then Vector3.new(0.45, 0.45, 0.12) else Vector3.new(1.2, 0.5, 0.25)
	eachAttachment(model, "Headlight", function(a)
		found = true
		local lamp = lampAt(model, "Headlight", a.WorldCFrame, size, Kit.LAMP)
		Kit.spotlight(lamp, 70, if count >= 2 then 45 else 55, if count >= 2 then 1.4 else 1.8)
	end)
	if found then
		return
	end
	local root = hostPart(model)
	if not root then
		return
	end
	local front = root.CFrame * CFrame.new(0, root.Size.Y * 0.2, -root.Size.Z / 2 - 0.1)
	for _, side in { -1, 1 } do
		local lamp = lampAt(model, "Headlight", front * CFrame.new(side * root.Size.X * 0.34, 0, 0), Vector3.new(0.9, 0.55, 0.25), Kit.LAMP)
		Kit.spotlight(lamp, 60, 50, 1.6)
	end
end

function Dress.helicopter(model: Model)
	if hasLights(model) then
		return
	end
	eachAttachment(model, "Searchlight", function(a)
		local lamp = lampAt(model, "SearchlightLens", a.WorldCFrame, Vector3.new(0.9, 0.9, 0.3), Kit.LAMP)
		Kit.spotlight(lamp, 120, 30, 2.2)
	end)
	local root = hostPart(model)
	if root then
		for _, side in { -1, 1 } do
			local p = lampAt(model, if side < 0 then "NavLeft" else "NavRight", root.CFrame * CFrame.new(side * (root.Size.X / 2 + 0.3), 0, 0), Vector3.new(0.8, 0.8, 0.8), if side < 0 then NAV_RED else NAV_GREEN)
			Kit.glow(p, 18, 2, p.Color)
		end
		local strobe = lampAt(model, "NavStrobe", root.CFrame * CFrame.new(0, -root.Size.Y / 2 - 0.3, 0), Vector3.new(0.8, 0.8, 0.8), NAV_RED)
		Kit.glow(strobe, 18, 2, NAV_RED)
		Kit.glow(root, 16, 0.9, Color3.fromRGB(255, 225, 190))
	end
end

function Dress.jet(model: Model)
	if model:FindFirstChild("NavStrobe", true) then
		return
	end
	eachAttachment(model, "NavLightL", function(a)
		Kit.glow(lampAt(model, "NavLeft", a.WorldCFrame, Vector3.new(0.8, 0.8, 0.8), NAV_RED), 18, 2, NAV_RED)
	end)
	eachAttachment(model, "NavLightR", function(a)
		Kit.glow(lampAt(model, "NavRight", a.WorldCFrame, Vector3.new(0.8, 0.8, 0.8), NAV_GREEN), 18, 2, NAV_GREEN)
	end)
	eachAttachment(model, "Exhaust", function(a)
		local burner = lampAt(model, "Afterburner", a.WorldCFrame, Vector3.new(2, 2, 0.2), Color3.fromRGB(255, 150, 70))
		Kit.glow(burner, 24, 2.5, Color3.fromRGB(255, 140, 60))
	end)
	local root = hostPart(model)
	if root then
		local strobe = lampAt(model, "NavStrobe", root.CFrame * CFrame.new(0, root.Size.Y / 2 + 0.3, 0), Vector3.new(0.8, 0.8, 0.8), Color3.new(1, 1, 1))
		Kit.glow(strobe, 18, 2, Color3.new(1, 1, 1))
		Kit.glow(root, 22, 0.8, Color3.fromRGB(255, 225, 190))
	end
end

function Dress.crawler(model: Model)
	if hasLights(model) then
		return
	end
	Dress.ground(model)
	local glow = model:FindFirstChild("CannonGlow", true)
	if glow and glow:IsA("BasePart") and not glow:FindFirstChildWhichIsA("PointLight") then
		glow.Transparency = 1
		local light = Kit.glow(glow, 40, 0, Color3.fromRGB(255, 110, 50))
		light.Name = "ChargeLight"
	end
end

return Dress
