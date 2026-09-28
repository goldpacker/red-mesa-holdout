--!strict
-- UI scale (MOBILE-1). The HUD and screens are laid out in design units
-- and scaled to the device: an attached root covers its parent at 1/scale
-- and carries a UIScale, so offset-sized panels shrink with the screen
-- while scale-positioned ones still track its edges. Keyboard and mouse
-- keep 1:1 down to a 1150x700 window; touch (InputMode) lays out on a
-- smaller 1100x560 canvas, so text and buttons stay large on phones.
--
-- `canvas()` is the safe viewport in design units. `fromScreen()` maps a
-- GUI-space point (Camera:WorldToScreenPoint) into an attached root's
-- offsets. Not viewport points: on a notched phone the viewport starts at
-- the safe area's edge while the 3D view (and its field of view) spans the
-- whole screen (measured in Studio's device emulator). `changed` fires
-- after the scale, the screen size, the Roblox top bar or the input mode
-- changes, so layouts can re-run.

local GuiService = game:GetService("GuiService")
local Workspace = game:GetService("Workspace")

local InputMode = require(script.Parent.InputMode)

local UiScale = {}

local DESKTOP = Vector2.new(1150, 700)
local TOUCH = Vector2.new(1100, 560)
local MIN_SCALE = 0.5
-- Canvases shorter than this get the compact title and end screens.
local SHORT_CANVAS = 700
-- Roblox's top bar height when the engine reports none (points).
local TOPBAR_FALLBACK = 58

type Attached = { root: GuiObject, scale: UIScale }

local scale = 1
local attached: { Attached } = {}
local listeners: { () -> () } = {}
local cameraConn: RBXScriptConnection? = nil

local function viewport(): Vector2
	local camera = Workspace.CurrentCamera
	local size = if camera then camera.ViewportSize else Vector2.zero
	-- The first frames can report a 1x1 viewport.
	return if size.X < 100 or size.Y < 100 then Vector2.new(1280, 720) else size
end

local function compute(): number
	local size = viewport()
	local design = if InputMode.isTouch() then TOUCH else DESKTOP
	return math.clamp(math.min(size.X / design.X, size.Y / design.Y), MIN_SCALE, 1)
end

local function apply(entry: Attached)
	entry.root.AnchorPoint = Vector2.zero
	entry.root.Position = UDim2.fromScale(0, 0)
	entry.root.Size = UDim2.fromScale(1 / scale, 1 / scale)
	entry.scale.Scale = scale
end

local function update()
	scale = compute()
	for _, entry in attached do
		apply(entry)
	end
	for _, fn in listeners do
		task.spawn(fn)
	end
end

local function watchCamera()
	if cameraConn then
		cameraConn:Disconnect()
	end
	local camera = Workspace.CurrentCamera
	if camera then
		cameraConn = camera:GetPropertyChangedSignal("ViewportSize"):Connect(update)
	end
	update()
end

function UiScale.get(): number
	return scale
end

-- Makes `root` cover its parent in design units at the current scale.
function UiScale.attach(root: GuiObject)
	local entry = { root = root, scale = Instance.new("UIScale") }
	entry.scale.Name = "DeviceScale"
	entry.scale.Parent = root
	apply(entry)
	table.insert(attached, entry)
end

-- The safe viewport in design units.
function UiScale.canvas(): Vector2
	return viewport() / scale
end

-- A GUI-space point (WorldToScreenPoint, AbsolutePosition) as offsets in
-- `root`, an attached root or any frame filling one.
function UiScale.fromScreen(root: GuiObject, point: Vector2): Vector2
	return (point - root.AbsolutePosition) / scale
end

-- `root`'s size in design units.
function UiScale.size(root: GuiObject): Vector2
	return root.AbsoluteSize / scale
end

-- True when the canvas is too short for the full title and end screens.
function UiScale.short(): boolean
	return UiScale.canvas().Y < SHORT_CANVAS
end

-- Bottom of Roblox's top bar (menu and chat buttons), in design units.
function UiScale.topbar(): number
	local inset = GuiService.TopbarInset
	local height = if inset.Height > 0 then inset.Max.Y else TOPBAR_FALLBACK
	return height / scale
end

-- Calls `fn()` after any change that can move a layout.
function UiScale.changed(fn: () -> ())
	table.insert(listeners, fn)
end

Workspace:GetPropertyChangedSignal("CurrentCamera"):Connect(watchCamera)
GuiService:GetPropertyChangedSignal("TopbarInset"):Connect(update)
InputMode.changed(update)
watchCamera()

return UiScale
