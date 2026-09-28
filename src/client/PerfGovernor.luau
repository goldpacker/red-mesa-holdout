--!strict
-- Adaptive quality governor (PERF-1). When the frame rate stays low it
-- steps the optional post layers down, and back up once there is headroom:
--   tier 0: everything on;
--   tier 1: no film layer (grain, corner vignette, glare) and no heat haze;
--   tier 2: also no low dust bands / sun shafts (PostFxAir) and no gunsight
--           depth of field.
-- These layers are pure atmosphere: enemies, the HUD, the storm, lighting,
-- shadows and every gameplay cue are the same at every tier (the storm's
-- readability is Look's lighting state, not these layers).
--
-- Signal: the mean frame time over 1 s windows while the game window has
-- focus. Down after DOWN_AFTER windows in a row slower than DOWN_DT (~52
-- fps), up after UP_AFTER windows in a row faster than UP_DT (~58 fps). A
-- 60 fps cap reads 16.7 ms, so a machine holding its cap never steps down;
-- Roblox's own frame-rate manager (Automatic quality) still acts on top.
-- In Studio it only runs when Workspace attribute `PerfGovernor` is true
-- (captures and A/Bs stay deterministic); Workspace `PerfTier` (0-2) forces
-- a tier there. The live tier is mirrored to Workspace `PerfTierNow`
-- (client-local) in Studio.

local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local Workspace = game:GetService("Workspace")

local PerfGovernor = {}

PerfGovernor.MAX_TIER = 2
local WINDOW = 1 -- s per sample
local DOWN_DT = 1 / 52
local UP_DT = 1 / 58
local DOWN_AFTER = 3
local UP_AFTER = 20

local IS_STUDIO = RunService:IsStudio()
local tier = 0
local focused = true
local sum, frames, windowStart = 0, 0, os.clock()
local slow, fast = 0, 0

function PerfGovernor.tier(): number
	if IS_STUDIO then
		local forced = Workspace:GetAttribute("PerfTier")
		if type(forced) == "number" then
			return math.clamp(math.floor(forced), 0, PerfGovernor.MAX_TIER)
		end
	end
	return tier
end

local function active(): boolean
	if not focused then
		return false
	end
	if IS_STUDIO then
		return Workspace:GetAttribute("PerfGovernor") == true and Workspace:GetAttribute("BeautyShot") == nil
	end
	return true
end

local function setTier(value: number)
	tier = math.clamp(value, 0, PerfGovernor.MAX_TIER)
	slow, fast = 0, 0
	if IS_STUDIO then
		Workspace:SetAttribute("PerfTierNow", tier)
	end
end

local function step(dt: number)
	if not active() then
		sum, frames, windowStart = 0, 0, os.clock()
		slow, fast = 0, 0
		return
	end
	sum += dt
	frames += 1
	local now = os.clock()
	if now - windowStart < WINDOW then
		return
	end
	local mean = sum / math.max(frames, 1)
	sum, frames, windowStart = 0, 0, now
	if mean > DOWN_DT then
		slow += 1
		fast = 0
		if slow >= DOWN_AFTER and tier < PerfGovernor.MAX_TIER then
			setTier(tier + 1)
		end
	elseif mean < UP_DT then
		fast += 1
		slow = 0
		if fast >= UP_AFTER and tier > 0 then
			setTier(tier - 1)
		end
	else
		slow, fast = 0, 0
	end
end

function PerfGovernor.start()
	UserInputService.WindowFocused:Connect(function()
		focused = true
	end)
	UserInputService.WindowFocusReleased:Connect(function()
		focused = false
	end)
	RunService.RenderStepped:Connect(step)
end

return PerfGovernor
