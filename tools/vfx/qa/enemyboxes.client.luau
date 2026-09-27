--!nocheck
-- Enemy screen boxes for the readability probe (VFX-4). Paste into MCP
-- execute_luau (Client) right before (or after) a screen_capture of the
-- same frame; save the returned JSON and pass it with the capture to
-- tools/vfx/qa/readability.py. Each live enemy's bounding box corners are
-- projected with Camera:WorldToViewportPoint (viewport pixels).
local Workspace = game:GetService("Workspace")
local HttpService = game:GetService("HttpService")
local cam = Workspace.CurrentCamera
local out = {
	viewport = { cam.ViewportSize.X, cam.ViewportSize.Y },
	fov = cam.FieldOfView,
	storm = game:GetService("Lighting"):GetAttribute("StormAmount") or 0,
	preset = Workspace:GetAttribute("TimeOfDay"),
	enemies = {},
}
local folder = Workspace:FindFirstChild("Enemies")
for _, m in folder and folder:GetChildren() or {} do
	if m:IsA("Model") then
		local cf, size = m:GetBoundingBox()
		local x0, y0, x1, y1 = math.huge, math.huge, -math.huge, -math.huge
		local front = true
		for _, sx in { -0.5, 0.5 } do
			for _, sy in { -0.5, 0.5 } do
				for _, sz in { -0.5, 0.5 } do
					local p = cf:PointToWorldSpace(size * Vector3.new(sx, sy, sz))
					local v = cam:WorldToViewportPoint(p)
					if v.Z <= 0 then
						front = false
					end
					x0, y0 = math.min(x0, v.X), math.min(y0, v.Y)
					x1, y1 = math.max(x1, v.X), math.max(y1, v.Y)
				end
			end
		end
		table.insert(out.enemies, {
			kind = m:GetAttribute("Kind"),
			dist = math.floor((cf.Position - cam.CFrame.Position).Magnitude + 0.5),
			box = { x0, y0, x1, y1 },
			front = front,
		})
	end
end
return HttpService:JSONEncode(out)
