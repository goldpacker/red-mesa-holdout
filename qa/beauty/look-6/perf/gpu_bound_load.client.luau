-- LOOK-6: pins the GPU at its top clock for work-proportional A/Bs (Client,
-- Studio play only, client-local parts). 120 translucent 40x40-stud sheets
-- stacked 6-8.4 studs in front of the current (frozen, beauty-staged) camera
-- push the frame to ~28-31 ms (~33 fps, not vsync-quantised); each sheet is
-- ~0.21 ms there. Then run a bench with frame time (dt) as the metric.
-- Remove with workspace.L6Load:Destroy().
local N = 120
local cam = workspace.CurrentCamera
local folder = Instance.new("Folder")
folder.Name = "L6Load"
folder.Parent = workspace
for i = 1, N do
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	p.Material = Enum.Material.SmoothPlastic
	p.Transparency = 0.985
	p.Color = Color3.new(0.5, 0.5, 0.5)
	p.Size = Vector3.new(40, 40, 0.05)
	p.CFrame = cam.CFrame * CFrame.new(0, 0, -6 - i * 0.02)
	p.Parent = folder
end
return "load: " .. N .. " sheets"
