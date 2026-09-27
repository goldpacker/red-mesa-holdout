-- MG bot as QA-F ran it (Client): tools/qa/autoplay.client.luau with range
-- 450 and, with no target in range, the turret beauty angle (yaw -2, pitch
-- -7.5) instead of a stale aim. Stop: LocalPlayer AutoPlay = false.
local plr = game.Players.LocalPlayer
plr:SetAttribute("AutoPlay", true)
plr:SetAttribute("AutoRange", 450)
task.spawn(function()
	local pivot = Vector3.new(0, 72, 0)
	local back, up = 13, 8
	while plr:GetAttribute("AutoPlay") do
		local best, bd
		for _, m in ipairs(workspace.Enemies:GetChildren()) do
			if m.PrimaryPart and m:GetAttribute("State") ~= "Dead" and not m:GetAttribute("Airborne") and m:FindFirstChild("Torso") then
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
			plr:SetAttribute("DebugFire", true)
		else
			plr:SetAttribute("DebugYaw", -2)
			plr:SetAttribute("DebugPitch", -7.5)
			plr:SetAttribute("DebugFire", false)
		end
		task.wait(0.05)
	end
	plr:SetAttribute("DebugFire", false)
end)
return "bot started"
