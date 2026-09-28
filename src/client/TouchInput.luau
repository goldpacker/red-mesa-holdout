--!strict
-- Touch aim and trigger state (MOBILE-1), read by AimController and
-- WeaponController and fed by TouchControls. A finger that lands on the
-- open screen (not on a button) aims: its movement adds up to a delta in
-- GUI points that AimController takes once per frame. A finger on a FIRE
-- button holds the trigger and aims too while it drags (`press`). The SIGHT
-- button toggles the gunsight. Nothing is tracked outside touch mode.

local UserInputService = game:GetService("UserInputService")

local InputMode = require(script.Parent.InputMode)

local TouchInput = {}

-- Aiming touches and their last position; the subset holding a trigger.
local tracked: { [InputObject]: Vector2 } = {}
local triggers: { [InputObject]: true } = {}
local delta = Vector2.zero
local sight = false
-- A FIRE press not yet seen by WeaponController: a quick tap can begin and
-- end between two of its frames, and must still fire.
local pressLatched = false

local function position(input: InputObject): Vector2
	return Vector2.new(input.Position.X, input.Position.Y)
end

local function track(input: InputObject)
	tracked[input] = position(input)
end

local function release(input: InputObject)
	tracked[input] = nil
	triggers[input] = nil
end

-- A touch (or, when Studio forces touch mode, a click) on a FIRE button.
function TouchInput.press(input: InputObject)
	if not InputMode.isTouch() then
		return
	end
	track(input)
	triggers[input] = true
	pressLatched = true
end

function TouchInput.release(input: InputObject)
	release(input)
end

function TouchInput.firing(): boolean
	return next(triggers) ~= nil
end

-- True once per FIRE press, even if the finger has already lifted.
function TouchInput.consumePress(): boolean
	local pressed = pressLatched
	pressLatched = false
	return pressed
end

-- True while `input` (a FIRE button's touch) is still held down.
function TouchInput.holding(input: InputObject): boolean
	return triggers[input] ~= nil
end

-- The aim movement since the last call, in GUI points.
function TouchInput.consumeDelta(): Vector2
	local d = delta
	delta = Vector2.zero
	return d
end

function TouchInput.sightOn(): boolean
	return sight
end

function TouchInput.setSight(on: boolean)
	sight = on
end

-- Drops every touch, the trigger, the pending aim and the gunsight (new
-- camera mode, or leaving touch mode).
function TouchInput.reset()
	table.clear(tracked)
	table.clear(triggers)
	delta = Vector2.zero
	sight = false
	pressLatched = false
end

UserInputService.TouchStarted:Connect(function(input, processed)
	-- Touches that land on a button are the button's (processed).
	if not processed and InputMode.isTouch() then
		track(input)
	end
end)

UserInputService.TouchMoved:Connect(function(input)
	local last = tracked[input]
	if last then
		local now = position(input)
		delta += now - last
		tracked[input] = now
	end
end)

UserInputService.TouchEnded:Connect(release)
UserInputService.InputEnded:Connect(function(input)
	if tracked[input] then
		release(input)
	end
end)

-- Backgrounding the app (a call, the home gesture) can swallow TouchEnded:
-- let go of everything rather than keep firing.
UserInputService.WindowFocusReleased:Connect(function()
	table.clear(tracked)
	table.clear(triggers)
	delta = Vector2.zero
	pressLatched = false
end)

InputMode.changed(function(isTouch)
	if not isTouch then
		TouchInput.reset()
	end
end)

return TouchInput
