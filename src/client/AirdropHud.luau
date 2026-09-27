--!strict
-- Airdrop HUD (AD-2, GAME_SPEC §6.1, §8.2, §12): an "INCOMING AIRDROP"
-- banner with the drop's direction, transport blips and landing markers on
-- the threat radar, and the first-airdrop tip. Built into Look's HUD root
-- (client/Hud) so it shows and hides with the rest of the HUD; the radar
-- layer sits on UiKitRadar's screen and uses its mapping.
--
-- Cues fire when a transport enters the basin (the sortie's t0), not when
-- the event arrives (it can come up to 45 s early). client/Airdrop calls
-- AirdropHud.entered(sortie) at t0 and AirdropHud.canopy() at the first
-- canopy opening (the tip: after the wave-1 "fire" tip, and when chutes
-- are actually in the sky).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AirdropPath = require(ReplicatedStorage.Shared.AirdropPath)
local Aim = require(ReplicatedStorage.Shared.Aim)
local AimController = require(script.Parent.AimController)
local GameState = require(script.Parent.GameState)
local Hud = require(script.Parent.Hud)
local Ui = require(script.Parent.Ui)
local UiKit = require(script.Parent.UiKit)
local UiKitRadar = require(script.Parent.UiKitRadar)

local AirdropHud = {}

local C = Ui.Colors
local F = Ui.Fonts
local BANNER_Y = 160 -- the jet warning's row; steps below it while that shows
local BANNER_Y_LOW = 232
local BANNER_HOLD = 4.2
local TRANSPORT = Color3.fromRGB(255, 214, 140)
local LANDING = Color3.fromRGB(255, 120, 70)
local CENTRE_DEG = 18 -- landing yaw within this of forward reads "CENTRE"
local AHEAD_DEG = 14 -- within this of the current aim: no turn arrow
local TIP = "Paratroopers can't be hit in the air — pick them off when they land."

local KIND_LABEL = { Infantry = "PARATROOPERS", Buggy = "BUGGIES", Tank = "ARMOR" }

type Mark = {
	sortie: AirdropPath.Sortie,
	centre: Vector3, -- landing centroid
	lastLand: number,
	blip: ImageLabel?,
	ring: Frame?,
	transportPos: Vector3?,
	transportDir: Vector3?,
}

local banner: ImageLabel
local title: TextLabel
local sub: TextLabel
local bannerUntil = 0
local recent: { number } = {} -- entry times, for "AIRDROPS x2"
local current: Mark? = nil
local layer: Frame? = nil
local marks: { [number]: Mark } = {}

local function build(root: Frame)
	banner = UiKit.panel({
		Name = "AirdropWarning",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, BANNER_Y),
		Size = UDim2.fromOffset(470, 64),
		Visible = false,
		Parent = root,
	}, { brackets = true, stripe = true, accent = C.Amber })
	title = Ui.label({
		Text = "INCOMING AIRDROP",
		FontFace = F.Header,
		TextSize = 27,
		TextColor3 = C.Amber,
		TextXAlignment = Enum.TextXAlignment.Center,
		Position = UDim2.fromOffset(0, 4),
		Size = UDim2.new(1, 0, 0, 30),
		ZIndex = 2,
		Parent = banner,
	})
	Ui.outline(title, 2)
	sub = Ui.label({
		Text = "",
		FontFace = F.Label,
		TextSize = 18,
		TextColor3 = C.Text,
		TextXAlignment = Enum.TextXAlignment.Center,
		Position = UDim2.fromOffset(0, 34),
		Size = UDim2.new(1, 0, 0, 22),
		ZIndex = 2,
		Parent = banner,
	})
	Ui.outline(sub, 1)
end

local function radarLayer(): Frame?
	if layer and layer.Parent then
		return layer
	end
	local screen = UiKitRadar.screen()
	if not screen then
		return nil
	end
	local f = Instance.new("Frame")
	f.Name = "AirdropMarks"
	f.BackgroundTransparency = 1
	f.Size = UDim2.fromScale(1, 1)
	f.ZIndex = 3
	f.Parent = screen
	layer = f
	return f
end

-- Is ThreatHud's jet warning up (it uses the BANNER_Y row)?
local function jetVisible(): boolean
	local root = Hud.getRoot()
	local threats = root and root:FindFirstChild("Threats")
	local jet = threats and threats:FindFirstChild("JetWarning")
	return jet ~= nil and (jet :: GuiObject).Visible
end

local function sector(yaw: number): string
	if yaw > CENTRE_DEG then
		return "LEFT FLANK"
	elseif yaw < -CENTRE_DEG then
		return "RIGHT FLANK"
	end
	return "CENTRE"
end

local function subline(m: Mark): string
	local yaw = Aim.yawTo(m.centre)
	local aimYaw = AimController.getAngles()
	local rel = yaw - aimYaw
	local text = sector(yaw) .. "  ·  " .. (KIND_LABEL[m.sortie.kind] or "TROOPS")
	if rel > AHEAD_DEG then
		return "◀  " .. text
	elseif rel < -AHEAD_DEG then
		return text .. "  ▶"
	end
	return "▲  " .. text
end

-- A transport has entered the basin.
function AirdropHud.entered(s: AirdropPath.Sortie, now: number)
	local sum = Vector3.zero
	local n = 0
	local lastLand = now
	for _, l in s.loads do
		sum += l.landPos
		n += 1
		lastLand = math.max(lastLand, l.landT)
	end
	if n == 0 then
		return
	end
	local m: Mark = { sortie = s, centre = sum / n, lastLand = lastLand, blip = nil, ring = nil, transportPos = nil, transportDir = nil }
	marks[s.id] = m
	current = m
	-- Banner: slide in (or refresh) and hold.
	local clock = os.clock()
	table.insert(recent, clock)
	while #recent > 0 and clock - recent[1] > BANNER_HOLD do
		table.remove(recent, 1)
	end
	title.Text = if #recent > 1 then string.format("INCOMING AIRDROPS  ×%d", #recent) else "INCOMING AIRDROP"
	sub.Text = subline(m)
	bannerUntil = clock + BANNER_HOLD
	if not banner.Visible then
		local y = if jetVisible() then BANNER_Y_LOW else BANNER_Y
		banner.Visible = true
		banner.Position = UDim2.new(0.5, 0, 0, y - 26)
		banner.ImageTransparency = 0.7
		UiKit.tween(banner, 0.32, { Position = UDim2.new(0.5, 0, 0, y), ImageTransparency = 0 }, Enum.EasingStyle.Back)
	end
end

-- The first canopy of the session opened: the first-airdrop tip (§8.2).
function AirdropHud.canopy()
	Hud.tipOnce("airdrop", TIP, 6)
end

-- Where a sortie's transport is now (nil when it has left).
function AirdropHud.transport(id: number, position: Vector3?, direction: Vector3?)
	local m = marks[id]
	if m then
		m.transportPos = position
		m.transportDir = direction
	end
end

function AirdropHud.clear()
	for _, m in marks do
		if m.blip then
			m.blip:Destroy()
		end
		if m.ring then
			m.ring:Destroy()
		end
	end
	table.clear(marks)
	current = nil
	banner.Visible = false
end

local function ring(parent: Frame): Frame
	local f = Instance.new("Frame")
	f.Name = "LandingMark"
	f.AnchorPoint = Vector2.new(0.5, 0.5)
	f.BackgroundColor3 = LANDING
	f.BackgroundTransparency = 0.8
	f.Size = UDim2.fromOffset(13, 13)
	f.ZIndex = 3
	local corner = Instance.new("UICorner")
	corner.CornerRadius = UDim.new(0.5, 0)
	corner.Parent = f
	local stroke = Instance.new("UIStroke")
	stroke.Color = LANDING
	stroke.Thickness = 1.6
	stroke.Parent = f
	f.Parent = parent
	return f
end

-- Per frame (from client/Airdrop): banner timing and direction, radar marks.
function AirdropHud.step(now: number)
	local clock = os.clock()
	if banner.Visible then
		if clock > bannerUntil or GameState.phase() ~= "Wave" then
			banner.Visible = false
		elseif current then
			sub.Text = subline(current :: Mark)
			local pulse = 0.5 + 0.5 * math.sin(clock * 7)
			title.TextColor3 = C.Amber:Lerp(C.White, 0.25 * pulse)
			-- The jet warning owns the upper row: step below it.
			if banner.Position.Y.Offset < BANNER_Y_LOW - 1 and jetVisible() then
				UiKit.tween(banner, 0.25, { Position = UDim2.new(0.5, 0, 0, BANNER_Y_LOW) }, Enum.EasingStyle.Quint)
			end
		end
	end
	local parent = radarLayer()
	if not parent then
		return
	end
	local yaw = AimController.getAngles()
	for id, m in marks do
		-- Transport blip: a chevron along its heading, while it flies.
		local tp = m.transportPos
		if tp then
			local blip = m.blip or UiKit.sprite("chevron", {
				Name = "TransportBlip",
				ImageColor3 = TRANSPORT,
				AnchorPoint = Vector2.new(0.5, 0.5),
				Size = UDim2.fromOffset(15, 15),
				ZIndex = 4,
				Parent = parent,
			})
			m.blip = blip
			local a = UiKitRadar.project(tp, yaw)
			local b = UiKitRadar.project(tp + (m.transportDir or Vector3.zAxis) * 120, yaw)
			blip.Position = a
			local d = Vector2.new(b.X.Scale - a.X.Scale, b.Y.Scale - a.Y.Scale)
			if d.Magnitude > 1e-5 then
				blip.Rotation = math.deg(math.atan2(d.X, -d.Y))
			end
			blip.ImageTransparency = 0.1 + 0.15 * (0.5 + 0.5 * math.sin(clock * 4 + id))
		elseif m.blip then
			m.blip:Destroy()
			m.blip = nil
		end
		-- Landing marker: a pulsing ring over the drop zone until the loads
		-- are down, then it fades.
		local left = m.lastLand + 2 - now
		if left > 0 then
			local r = m.ring or ring(parent)
			m.ring = r
			r.Position = UiKitRadar.project(m.centre, yaw)
			local pulse = 0.5 + 0.5 * math.sin(clock * 5 + id)
			local fade = math.clamp(left / 2, 0, 1)
			local size = 11 + 5 * pulse
			r.Size = UDim2.fromOffset(size, size)
			local stroke = r:FindFirstChildOfClass("UIStroke")
			if stroke then
				stroke.Transparency = 1 - fade * (0.55 + 0.45 * pulse)
			end
			r.BackgroundTransparency = 1 - 0.2 * fade
		elseif m.ring then
			m.ring:Destroy()
			m.ring = nil
		end
		if not m.transportPos and left <= 0 then
			marks[id] = nil
			if current == m then
				current = nil
			end
		end
	end
end

function AirdropHud.start()
	build(Hud.getRoot())
	GameState.onChanged("Phase", function(phase)
		if phase ~= "Wave" then
			banner.Visible = false
		end
		if phase == "Title" or phase == "WaveIntro" or phase == "Defeat" or phase == "Victory" then
			AirdropHud.clear()
		end
	end)
end

return AirdropHud
