-- QA helper: paste into execute_luau (Client datamodel) during a Studio
-- playtest. Aims the turret through the camera at the nearest enemy and
-- fires via the Studio-only Debug* player attributes read by the client.
-- Stop with: game.Players.LocalPlayer:SetAttribute("AutoPlay", false)
-- Tune with player attributes AutoRange (default 700) and AutoFire (false = aim only).
local plr = game.Players.LocalPlayer
plr:SetAttribute("AutoPlay", true)
task.spawn(function()
	local pivot = Vector3.new(0, 72, 0) -- keep in sync with Config.TURRET_PIVOT
	local back, up = 13, 8 -- Config.Camera.THIRD_PERSON_BACK / _UP
	while plr:GetAttribute("AutoPlay") do
		local best, bd
		for _, m in ipairs(workspace.Enemies:GetChildren()) do
			if m.PrimaryPart and m:GetAttribute("State") ~= "Dead" and m:FindFirstChild("Torso") then
				local d = (m.PrimaryPart.Position - pivot).Magnitude
				if not bd or d < bd then
					best, bd = m, d
				end
			end
		end
		if best and bd < (plr:GetAttribute("AutoRange") or 700) then
			local target = best.Torso.Position
			local dv = target - pivot
			local look = dv.Unit
			local flat = Vector3.new(dv.X, 0, dv.Z).Unit
			local offsetDir = if look.Y < 0 then look else flat
			local cam = pivot - offsetDir * back + Vector3.new(0, up, 0)
			local dir = (target - cam).Unit
			plr:SetAttribute("DebugYaw", math.deg(math.atan2(-dir.X, -dir.Z)))
			plr:SetAttribute("DebugPitch", math.deg(math.asin(dir.Y)))
			plr:SetAttribute("DebugFire", plr:GetAttribute("AutoFire") ~= false)
		else
			plr:SetAttribute("DebugFire", false)
		end
		task.wait(0.05)
	end
	plr:SetAttribute("DebugFire", false)
end)
return "autoplay started"
