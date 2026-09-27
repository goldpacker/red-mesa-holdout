-- Client, LOOK-5 fix: same-camera telephoto readability probe.
-- _G.L5T.base()            remember the current (turret) camera position
-- _G.L5T.aim(group)        "ground" | "heli" | "boss" | "all": telephoto from that position onto the group; returns rects
-- _G.L5T.paint(on)         enemies solid magenta Neon (mask capture) / restore
-- _G.L5T.release()         unbind, restore HUD
local RunService = game:GetService("RunService")
local Players = game:GetService("Players")
local cam = workspace.CurrentCamera
local T = {}
local basePos: Vector3? = nil
local hidden = {}
local saved = {}
local STEP = "L5Tele"

function T.base()
	basePos = cam.CFrame.Position
	return tostring(basePos)
end

local function members(group)
	local out = {}
	for _, m in workspace.Enemies:GetChildren() do
		if m:IsA("Model") then
			local kind = m:GetAttribute("Kind") or m.Name
			local ok = group == "all" or group == "boss"
				or (group == "ground" and (kind == "Infantry" or kind == "Buggy" or kind == "Tank"))
				or (group == "heli" and kind == "Helicopter")
			if ok then table.insert(out, m) end
		end
	end
	return out
end

local function corners(m)
	local cf, size = m:GetBoundingBox()
	local pts = {}
	for _, sx in { -0.5, 0.5 } do for _, sy in { -0.5, 0.5 } do for _, sz in { -0.5, 0.5 } do
		table.insert(pts, (cf * CFrame.new(size.X * sx, size.Y * sy, size.Z * sz)).Position)
	end end end
	return pts, cf.Position
end

function T.aim(group)
	assert(basePos, "call base() first")
	local ms = members(group)
	if #ms == 0 then return "no members" end
	local c = Vector3.zero
	for _, m in ms do local _, p = corners(m); c += p end
	c /= #ms
	local look = CFrame.lookAt(basePos, c)
	local vp = cam.ViewportSize
	local aspect = vp.X / vp.Y
	local maxY = 0
	for _, m in ms do
		local pts = corners(m)
		for _, q in pts do
			local l = look:PointToObjectSpace(q)
			local z = -l.Z
			maxY = math.max(maxY, math.atan(math.abs(l.Y) / z), math.atan(math.abs(l.X) / z) / aspect)
		end
	end
	local fov = math.clamp(math.deg(maxY) * 2 * 1.35, 1.5, 70)
	-- hide the HUD (not the film layer)
	for _, g in Players.LocalPlayer.PlayerGui:GetChildren() do
		if g:IsA("ScreenGui") and g.Enabled and g.Name ~= "FilmFx" then
			g.Enabled = false
			table.insert(hidden, g)
		end
	end
	RunService:UnbindFromRenderStep(STEP)
	RunService:BindToRenderStep(STEP, Enum.RenderPriority.Last.Value + 30, function()
		cam.CFrame = look
		cam.FieldOfView = fov
	end)
	task.wait(0.6)
	local lines = { string.format("# group %s fov %.2f vp %dx%d", group, fov, vp.X, vp.Y) }
	for _, m in workspace.Enemies:GetChildren() do
		if m:IsA("Model") then
			local pts, p = corners(m)
			local x0, y0, x1, y1 = math.huge, math.huge, -math.huge, -math.huge
			local front = true
			for _, q in pts do
				local v = cam:WorldToViewportPoint(q)
				if v.Z <= 0 then front = false end
				x0, y0 = math.min(x0, v.X), math.min(y0, v.Y)
				x1, y1 = math.max(x1, v.X), math.max(y1, v.Y)
			end
			if front and x1 > 0 and y1 > 0 and x0 < vp.X and y0 < vp.Y then
				table.insert(lines, string.format("%s_%s %.1f %.1f %.1f %.1f %.0f", tostring(m:GetAttribute("Kind") or m.Name), tostring(m:GetAttribute("EnemyId") or ""), x0, y0, x1, y1, (p - basePos).Magnitude))
			end
		end
	end
	return table.concat(lines, "\n")
end

function T.paint(on)
	if on then
		for _, m in workspace.Enemies:GetChildren() do
			for _, d in m:GetDescendants() do
				if d:IsA("BasePart") then
					if d.Transparency < 0.99 and d.LocalTransparencyModifier < 0.99 then
						saved[d] = { Color = d.Color, Material = d.Material }
						if d:IsA("MeshPart") then saved[d].TextureID = d.TextureID; d.TextureID = "" end
						d.Material = Enum.Material.Neon
						d.Color = Color3.fromRGB(255, 0, 255)
					end
				elseif d:IsA("SurfaceAppearance") then
					saved[d] = { Parent = d.Parent }
					d.Parent = nil
				elseif d:IsA("Decal") or d:IsA("Texture") then
					saved[d] = { Transparency = d.Transparency }
					d.Transparency = 1
				elseif d:IsA("ParticleEmitter") or d:IsA("Beam") or d:IsA("Light") then
					saved[d] = { Enabled = d.Enabled }
					d.Enabled = false
				end
			end
		end
	else
		for inst, props in saved do
			for k, v in props do
				pcall(function() (inst :: any)[k] = v end)
			end
		end
		table.clear(saved)
	end
	task.wait(0.4)
	return "paint " .. tostring(on)
end

function T.release()
	RunService:UnbindFromRenderStep(STEP)
	for _, g in hidden do g.Enabled = true end
	table.clear(hidden)
	cam.FieldOfView = 70
	return "released"
end

_G.L5T = T
return "installed"
