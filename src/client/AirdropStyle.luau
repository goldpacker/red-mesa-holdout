--!strict
-- Airdrop presentation tuning (AD-2): timings, sizes, caps and colours for
-- the client visuals (AirdropTransport, AirdropTrooper, AirdropCargo,
-- AirdropFx, AirdropHud). Visual only: the timeline itself
-- (release, open and touchdown times and points) is the server's
-- (shared/AirdropPath + the AirdropSortie payload) and nothing here moves a
-- load's landPos or landT.
--
-- Wind: VFX publishes src/shared/Wind.luau (VFX-4). Until it exists (or if
-- it doesn't expose `at(t)`), AirdropStyle.wind() is a small constant
-- breeze along the same direction the game's smoke and dust already drift
-- (client/Effects.WIND), so collapsed canopies drape the way the landing
-- dust blows.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Style = {}

---------------------------------------------------------------------------
-- Transport
---------------------------------------------------------------------------
Style.Transport = {
	-- Straight drop run around the releases; outside it the aircraft flies
	-- gentle arcs that bend away from the outpost (never toward the mesa).
	RUN_IN = 9, -- s before the first release the run starts
	RUN_OUT = 4, -- s after the last release it ends
	ENTRY_TURN = math.rad(18), -- heading change of the arc onto the run
	EXIT_TURN = math.rad(28), -- heading change of the break-away arc
	TURN_RADIUS = 950, -- studs
	BANK_EASE = 1.6, -- s to roll into / out of a bank
	GRAVITY = 35, -- studs/s^2 (1 stud ~ 0.28 m): bank = atan(v^2 / (R g))
	CLIMB = 3.5, -- studs/s climb after the break-away starts
	-- Air: tiny slow roll/pitch/heave so it never looks rail-mounted.
	WOBBLE_ROLL = math.rad(0.7),
	WOBBLE_PITCH = math.rad(0.35),
	WOBBLE_HEAVE = 0.8,
	-- Ramp and cargo door (HS-6 contract: 21.8 deg and 60 deg open).
	RAMP_OPEN_DEG = 21.8,
	DOOR_OPEN_DEG = 60,
	RAMP_LEAD = 5.5, -- s before the first release the ramp starts to open
	RAMP_TIME = 2.6, -- s to open or close
	RAMP_CLOSE_AFTER = 1.6, -- s after the last release it starts closing
	-- Props: blades turn at a watchable rate under the blur discs.
	PROP_RATE = 11, -- rad/s (the discs carry the "fast" look)
	DISC_TRANSPARENCY = 0.72,
	-- Far LOD (HS-6 LODHull + discs): by distance x zoom, with hysteresis.
	LOD_IN = 1450,
	LOD_OUT = 1300,
	-- Visual lingers this long past the server's path end (it is far out).
	END_GRACE = 2,
}

---------------------------------------------------------------------------
-- Loads
---------------------------------------------------------------------------
Style.Trooper = {
	-- Harness (the chute pivot) above the feet, and the skinned soldier's
	-- Root below the harness, both at the landed enemy's scale (1.1).
	SCALE = 1.1,
	HARNESS_UP = 5.25 * 1.1, -- shoulders above the feet (skinned rig, measured)
	-- Its Root (hips) below the shoulders, less 0.14: measured in play, the
	-- landed enemy's Root stands 0.14 higher than the rig alone puts it.
	ROOT_BELOW_HARNESS = 1.8 * 1.1 - 0.14,
	STREAMER_AT = 0.3, -- fraction of the free fall when the bag is out
	OPEN_TIME = 0.55, -- s: open snap (canopy blossoms, slight overshoot)
	SWING_ANGLE = math.rad(24), -- opening swing amplitude
	SWING_PERIOD = 3.4, -- s
	SWING_DECAY = 0.35, -- 1/s
	SWAY = math.rad(3.2), -- steady wind sway amplitude
	SWAY_PERIOD = 4.6,
	BREATHE = 0.025, -- canopy breathing (scale)
	SWAY_SETTLE = 2.4, -- s before touchdown the sway has died out
	FLARE = 0.55, -- landing flare: descent slows to 1 - FLARE of its rate
	FLARE_SHARP = 10, -- how late the flare starts (higher = later)
	COLLAPSE_TIME = 0.85, -- s: open canopy tips over and deflates
	LOD_BODY = 230, -- camera distance x zoom below which the full mesh draws
	POSE_RATE_NEAR = 1 / 30,
	POSE_RATE_FAR = 1 / 8,
}

Style.Cargo = {
	CHUTES = { Buggy = 2, Tank = 4 },
	TILT = { Buggy = math.rad(19), Tank = math.rad(29) }, -- 28-30: no skirt overlap
	OPEN_TIME = 0.9,
	SWING_ANGLE = math.rad(12),
	SWING_PERIOD = 5.2,
	SWING_DECAY = 0.3,
	SWAY = math.rad(2.2),
	SWAY_PERIOD = 6.5,
	SWAY_SETTLE = 2.2,
	PAD_HEIGHT = 2.3, -- DropPlatform LoadAttach above its base
	CRUSH_TIME = 0.12, -- s the pads crush (the pallet beds into the sand)
	COLLAPSE_TIME = 1.5,
	PALLET_LINGER = 6, -- s the pallet stays after the vehicle drives off
	TIP_DEG = 16, -- nose-down pitch as the platform rolls off the ramp
}

-- Collapsed canopies and pallets lying on the ground: how long they stay,
-- how they fade, and how many may exist at once (oldest go first).
Style.Ground = {
	CANOPY_LINGER = 4,
	FADE_TIME = 1.2,
	SINK = 0.9, -- studs a fading canopy sinks into the sand
	MAX_COLLAPSED = 18,
}

-- Hand-off safety net: if no model with the load's DropLoadId (in Enemies
-- or Wrecks) has reached this client this long after landT, the body is
-- retired anyway (canopy/pallet behave as after a normal hand-off). The
-- replicated enemy's first frame came 17-53 ms after landT in every
-- measured Studio hand-off (logs/ad-2); this leaves room for a real
-- player's network latency while keeping a never-seen enemy's stand-in
-- under half a second.
Style.HANDOFF_GRACE = 0.4

-- Hard caps (waves 8-10 can have many loads airborne at once).
Style.Caps = {
	LOADS_AIRBORNE = 48, -- beyond this new loads fall as a canopy-only visual
	TRANSPORTS = 10,
}

---------------------------------------------------------------------------
-- Wind
---------------------------------------------------------------------------
local FALLBACK_WIND = Vector3.new(2.6, 0, 1.1).Unit * 1.6 -- studs/s, Effects.WIND's direction

local windModule: any = nil
local windChecked = false
local function windSource(): any
	if windChecked then
		return windModule
	end
	windChecked = true
	local shared = ReplicatedStorage:FindFirstChild("Shared")
	local m = shared and shared:FindFirstChild("Wind")
	if m and m:IsA("ModuleScript") then
		local ok, result = pcall(require, m)
		if ok and typeof(result) == "table" and typeof((result :: any).at) == "function" then
			windModule = result
		end
	end
	return windModule
end

-- Wind velocity (studs/s, horizontal) at server time t. Swap point for
-- VFX-4's shared/Wind.luau: uses `Wind.at(t)` (a Vector3) when present.
function Style.wind(t: number): Vector3
	local w = windSource()
	if w then
		local ok, v = pcall(w.at, t)
		if ok and typeof(v) == "Vector3" then
			return Vector3.new(v.X, 0, v.Z)
		end
	end
	return FALLBACK_WIND
end

-- Flat unit downwind direction at t.
function Style.downwind(t: number): Vector3
	local w = Style.wind(t)
	return if w.Magnitude > 1e-3 then w.Unit else Vector3.new(1, 0, 0)
end

---------------------------------------------------------------------------
-- Small maths shared by the visual modules
---------------------------------------------------------------------------
function Style.smooth(u: number): number
	u = math.clamp(u, 0, 1)
	return u * u * (3 - 2 * u)
end

-- Damped pendulum angle for a swing that started `age` seconds ago.
function Style.swing(age: number, amplitude: number, period: number, decay: number): number
	if age < 0 then
		return amplitude
	end
	return amplitude * math.exp(-decay * age) * math.cos(2 * math.pi * age / period)
end

-- Descent reshaped for a landing flare: g(0) = 0, g(1) = 1, g'(1) = 1 - k.
-- The sink rate eases off over the last part of the descent only; the
-- endpoints (openPos at openT, landPos at landT) are exactly the server's.
function Style.flare(u: number, k: number, sharp: number): number
	u = math.clamp(u, 0, 1)
	return u + k * (u ^ sharp) * (1 - u)
end

-- Projected-size distance: camera distance scaled by the zoom (FOV), so the
-- gunsight (narrow FOV) counts as closer.
function Style.viewDistance(p: Vector3): number
	local cam = Workspace.CurrentCamera
	if not cam then
		return 1e6
	end
	local d = (cam.CFrame.Position - p).Magnitude
	return d * math.tan(math.rad(cam.FieldOfView) * 0.5) / math.tan(math.rad(35))
end

return Style
