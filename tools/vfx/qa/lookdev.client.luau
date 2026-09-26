--!nocheck
-- Look-dev board (Studio playtest, Client datamodel): fixes the camera on a
-- patch of basin floor and fires every VFX-2 effect in a row through the
-- real client modules, so one capture shows them side by side at a known
-- distance. Paste into MCP execute_luau (Client) after `beauty` staging;
-- run `_G.fxBoardEnd()` (Client) to give the camera back.
local RunService = game:GetService("RunService")
local cs = game:GetService("Players").LocalPlayer.PlayerScripts.Client
local E = require(cs.Effects)
local P = require(cs.VehicleFxParticles)
local W = require(cs.WeaponFxParticles)

local CAM_AT = Vector3.new(-150, 40, -150)
local LOOK_AT = Vector3.new(-150, 8, -260)
local camera = workspace.CurrentCamera
RunService:BindToRenderStep("FxBoard", Enum.RenderPriority.Last.Value + 20, function()
	camera.CFrame = CFrame.lookAt(CAM_AT, LOOK_AT)
	camera.FieldOfView = 50
end)
_G.fxBoardEnd = function()
	RunService:UnbindFromRenderStep("FxBoard")
end

local function ground(x, z)
	local hit = E.groundBelow(Vector3.new(x, 200, z), 400)
	return hit and hit.Position or Vector3.new(x, 2, z)
end

local which = _G.fxBoardWhich or "impacts"
if which == "impacts" then
	for i = 0, 5 do
		task.delay(i * 0.12, function()
			E.impact(ground(-190 + i * 2, -250), false, nil, "Sand")
			E.impact(ground(-160 + i * 2, -250) + Vector3.new(0, 3, 0), false, nil, "Rock")
			E.impact(ground(-130 + i * 2, -250) + Vector3.new(0, 3, 0), true, nil, "Metal")
			E.impact(ground(-100 + i * 2, -250) + Vector3.new(0, 3, 0), true, nil, "Soldier")
		end)
	end
elseif which == "explosions" then
	P.explosion(ground(-195, -270), 1, { set = "surface" })
	P.explosion(ground(-150, -270) + Vector3.new(0, 3, 0), 1.7, {})
	P.explosion(ground(-105, -270) + Vector3.new(0, 20, 0), 1.1, { air = true })
elseif which == "muzzles" then
	for i, s in { 0.35, 0.6, 1, 2.2 } do
		E.enemyMuzzle(ground(-195 + i * 18, -240) + Vector3.new(0, 3, 0), Vector3.new(0, 0, 1), s)
	end
	W.backblast(ground(-110, -240) + Vector3.new(0, 4, 0), Vector3.new(1, 0.1, 0), false)
elseif which == "fires" then
	local part = Instance.new("Part")
	part.Anchored, part.Transparency, part.CanQuery = true, 1, false
	part.Size = Vector3.new(6, 2, 10)
	part.CFrame = CFrame.new(ground(-150, -255) + Vector3.new(0, 1, 0))
	part.Parent = E.folder()
	P.burn(part, 1.4, Vector3.new(0, 1, 0))
	task.delay(30, function() part:Destroy() end)
end
return "board " .. which
