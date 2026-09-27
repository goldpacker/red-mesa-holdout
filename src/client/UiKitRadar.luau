--!strict
-- Threat radar instrument (LOOK-2): phosphor screen in a worn bezel, a
-- rotating sweep line with a fading tail, blips that flare as the sweep
-- passes and fade until the next pass, and the hatched rear dead zone (the
-- 90° the turret can't reach). Aim-relative: forward is always up, as
-- before (spec §12: the 270° arc, ground vs air colours).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Config = require(ReplicatedStorage.Shared.Config)
local Aim = require(ReplicatedStorage.Shared.Aim)
local Ui = require(script.Parent.Ui)
local UiKit = require(script.Parent.UiKit)

local UiKitRadar = {}

local C = Ui.Colors
local RANGE = 1000 -- studs at the screen rim
local SCREEN = 0.925 -- phosphor screen radius as a fraction of the face (ui_kit_textures.SCREEN)
local PERIOD = 2.4 -- seconds per sweep revolution
local BLIP_MIN = 0.5 -- blip opacity just before the sweep comes round again
local AIR = Color3.fromRGB(90, 200, 255)
local SWEEP = Color3.fromRGB(170, 215, 110)

type Blip = { image: ImageLabel, ping: number, angle: number }

local face: ImageLabel
local sweep: ImageLabel
local dead: ImageLabel
local blipLayer: Frame
local blips: { [Instance]: Blip } = {}
local sweepAngle = 0

function UiKitRadar.build(parent: Instance, size: number): GuiObject
	local holder = Ui.new("Frame", {
		Name = "Radar",
		BackgroundTransparency = 1,
		AnchorPoint = Vector2.new(1, 1),
		Position = UDim2.new(1, -16, 1, -16),
		Size = UDim2.fromOffset(size, size),
		Parent = parent,
	})
	face = UiKit.sprite("radar_face", { Name = "Face", Size = UDim2.fromScale(1, 1), Parent = holder })
	-- The screen area (inside the bezel) hosts the moving layers.
	local screen = Ui.new("Frame", {
		Name = "Screen",
		BackgroundTransparency = 1,
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(1, 1),
		Parent = face,
	})
	dead = UiKit.sprite("radar_dead", { Name = "RearArc", ImageColor3 = C.Red, ImageTransparency = 0.55, Size = UDim2.fromScale(1, 1), ZIndex = 1, Parent = screen })
	sweep = UiKit.sprite("radar_sweep", { Name = "Sweep", ImageColor3 = SWEEP, ImageTransparency = 0.1, Size = UDim2.fromScale(1, 1), ZIndex = 2, Parent = screen })
	blipLayer = Ui.new("Frame", { Name = "Blips", BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), ZIndex = 3, Parent = screen })
	local tag = UiKit.panel({
		Name = "Tag",
		AnchorPoint = Vector2.new(0, 0),
		Position = UDim2.fromOffset(-6, -4),
		Size = UDim2.fromOffset(60, 22),
		ZIndex = 4,
		Parent = holder,
	}, { grain = false })
	Ui.label({ Text = "RADAR", FontFace = Ui.Fonts.Label, TextSize = 13, TextColor3 = C.Olive, TextXAlignment = Enum.TextXAlignment.Center, Size = UDim2.fromScale(1, 1), ZIndex = 5, Parent = tag })
	return holder
end

local function angleDiff(a: number, b: number): number
	return (a - b) % 360
end

function UiKitRadar.update(dt: number, yaw: number)
	local now = os.clock()
	local previous = sweepAngle
	sweepAngle = (sweepAngle + dt * 360 / PERIOD) % 360
	local advanced = angleDiff(sweepAngle, previous)
	sweep.Rotation = sweepAngle
	dead.Rotation = yaw

	local seen: { [Instance]: boolean } = {}
	local enemies = Workspace:FindFirstChild("Enemies")
	if enemies then
		for _, model in enemies:GetChildren() do
			local rootPart = (model :: Model).PrimaryPart
			if not rootPart or model:GetAttribute("State") == "Dead" then
				continue
			end
			local offset = rootPart.Position - Config.TURRET_PIVOT
			local dist = Vector2.new(offset.X, offset.Z).Magnitude
			local rel = math.rad(Aim.yawTo(rootPart.Position) - yaw)
			local r = math.min(dist / RANGE, 1) * 0.5 * SCREEN * 0.96
			local blip = blips[model]
			if not blip then
				local isAir = model:GetAttribute("IsAir") == true
				blip = {
					image = UiKit.sprite("blip", {
						Name = "Blip",
						ImageColor3 = if isAir then AIR else C.Red,
						AnchorPoint = Vector2.new(0.5, 0.5),
						Size = UDim2.fromOffset(14, 14),
						Parent = blipLayer,
					}),
					ping = now,
					angle = 0,
				}
				blips[model] = blip
			end
			blip.image.Position = UDim2.fromScale(0.5 - math.sin(rel) * r, 0.5 - math.cos(rel) * r)
			-- Screen angle of the blip, clockwise from up (same frame as the sweep).
			blip.angle = (-math.deg(rel)) % 360
			if angleDiff(sweepAngle, blip.angle) <= advanced then
				blip.ping = now
			end
			local age = math.clamp((now - blip.ping) / PERIOD, 0, 1)
			blip.image.ImageTransparency = (1 - BLIP_MIN) * age
			local s = 14 + 8 * math.max(0, 1 - age * 4)
			blip.image.Size = UDim2.fromOffset(s, s)
			seen[model] = true
		end
	end
	for model, blip in blips do
		if not seen[model] then
			blip.image:Destroy()
			blips[model] = nil
		end
	end
end

-- AD-2 (additive): the radar mapping for other layers (airdrop markers).
-- Scale position of a world point on the radar screen for aim yaw `yaw`,
-- and the screen frame to parent such a layer to (nil before build).
function UiKitRadar.project(position: Vector3, yaw: number): UDim2
	local offset = position - Config.TURRET_PIVOT
	local dist = Vector2.new(offset.X, offset.Z).Magnitude
	local rel = math.rad(Aim.yawTo(position) - yaw)
	local r = math.min(dist / RANGE, 1) * 0.5 * SCREEN * 0.96
	return UDim2.fromScale(0.5 - math.sin(rel) * r, 0.5 - math.cos(rel) * r)
end

function UiKitRadar.screen(): Frame?
	return if blipLayer then blipLayer.Parent :: Frame else nil
end

return UiKitRadar
