--!strict
-- Which controls the player is using (MOBILE-1). Touch shows the on-screen
-- controls (TouchControls) and the touch layouts; otherwise the game is
-- played with keyboard and mouse. Follows UserInputService.PreferredInput,
-- which moves with the device the player last used (a touchscreen laptop
-- switches back and forth); a gamepad keeps the current mode (gamepad play
-- is out of scope). Studio QA: player attribute DebugTouch (true/false)
-- forces a mode, nil follows the device.

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local InputMode = {}

local player = Players.LocalPlayer
local touch = false
local listeners: { (boolean) -> () } = {}

local function preferredInput(): EnumItem?
	local ok, value = pcall(function()
		return (UserInputService :: any).PreferredInput
	end)
	return if ok and typeof(value) == "EnumItem" then value else nil
end

local function detect(): boolean
	if RunService:IsStudio() then
		local forced = player:GetAttribute("DebugTouch")
		if type(forced) == "boolean" then
			return forced
		end
	end
	local preferred = preferredInput()
	if preferred then
		if preferred == (Enum :: any).PreferredInput.Touch then
			return true
		elseif preferred == (Enum :: any).PreferredInput.KeyboardAndMouse then
			return false
		end
		return touch
	end
	-- Engines without PreferredInput: the last input type decides.
	local last = UserInputService:GetLastInputType()
	if last == Enum.UserInputType.Touch then
		return true
	elseif last == Enum.UserInputType.Keyboard or last.Name:match("^Mouse") then
		return false
	end
	return UserInputService.TouchEnabled and not UserInputService.KeyboardEnabled
end

local function refresh()
	local now = detect()
	if now == touch then
		return
	end
	touch = now
	for _, fn in listeners do
		task.spawn(fn, now)
	end
end

function InputMode.isTouch(): boolean
	return touch
end

-- Calls `fn(isTouch)` whenever the mode changes.
function InputMode.changed(fn: (boolean) -> ())
	table.insert(listeners, fn)
end

touch = detect()
if preferredInput() then
	UserInputService:GetPropertyChangedSignal("PreferredInput" :: any):Connect(refresh)
else
	UserInputService.LastInputTypeChanged:Connect(refresh)
end
player:GetAttributeChangedSignal("DebugTouch"):Connect(refresh)

return InputMode
