--!strict
-- Distance level of detail for particles (VFX-3), shared by the effect
-- modules, on top of their live-effect caps.
--   factor(p, cutoff)  continuous emitters: rate and size multipliers.
--                      Full inside NEAR; fewer, larger particles out to
--                      `cutoff` (size ~ 1/sqrt(rate) so a cloud keeps its
--                      coverage); none beyond it.
--   count(n, p)        one-shot bursts: x1 / 0.7 / 0.45 by distance band.
--   track(e, cutoff)   keeps a continuous emitter's Rate/Size on its LOD as
--                      the camera moves (fires, smoke columns, trails); it
--                      drops out when the emitter is destroyed.
-- Distances are zoom-corrected: through the gunsight (FOV 32) a thing
-- 1000 studs out looks as big as one at ~410 in the turret view (FOV 70).
-- Studio QA: Workspace attribute FxLodOff = true turns LOD off (perf A/B);
-- `note` keeps a live estimate of one-shot particles, published in Studio
-- as the Workspace attribute FxOneShotLive.

local RunService = game:GetService("RunService")
local Workspace = game:GetService("Workspace")

local Lod = {}

local NEAR = 250 -- full detail inside this (zoom-corrected) distance
local MIN_RATE = 0.2 -- rate multiplier at the cutoff
local MAX_SIZE = 2 -- size multiplier cap
local REF_HALF_FOV = math.tan(math.rad(35)) -- turret view (Config Camera.FOV_DEFAULT 70)
local UPDATE = 0.25 -- s between tracked-emitter updates
Lod.DEFAULT_CUTOFF = 2400

local studio = RunService:IsStudio()

function Lod.off(): boolean
	return Workspace:GetAttribute("FxLodOff") == true
end

-- Camera distance to `p`, scaled by the current zoom.
function Lod.distance(p: Vector3): number
	local camera = Workspace.CurrentCamera
	local zoom = math.tan(math.rad(camera.FieldOfView) * 0.5) / REF_HALF_FOV
	return (camera.CFrame.Position - p).Magnitude * zoom
end

-- (rate multiplier, size multiplier) for a continuous emitter at `p`.
function Lod.factor(p: Vector3, cutoff: number?): (number, number)
	if Lod.off() then
		return 1, 1
	end
	local far = cutoff or Lod.DEFAULT_CUTOFF
	local d = Lod.distance(p)
	if d <= NEAR then
		return 1, 1
	elseif d >= far then
		return 0, MAX_SIZE
	end
	local t = (d - NEAR) / (far - NEAR)
	local rate = 1 + (MIN_RATE - 1) * t ^ 0.8
	return rate, math.min(MAX_SIZE, 1 / math.sqrt(rate))
end

-- One-shot particle count after distance LOD (at least one).
function Lod.count(n: number, p: Vector3): number
	if Lod.off() then
		return n
	end
	local d = Lod.distance(p)
	local k = if d < 300 then 1 elseif d < 650 then 0.7 else 0.45
	return math.max(1, math.round(n * k))
end

function Lod.scaleSeq(s: NumberSequence, k: number): NumberSequence
	local keys = table.create(#s.Keypoints)
	for i, kp in s.Keypoints do
		keys[i] = NumberSequenceKeypoint.new(kp.Time, kp.Value * k, kp.Envelope * k)
	end
	return NumberSequence.new(keys)
end

---------------------------------------------------------------------------
-- Tracked continuous emitters
---------------------------------------------------------------------------

type Tracked = { rate: number, size: NumberSequence, cutoff: number, sizeK: number, resize: boolean }
local tracked: { [ParticleEmitter]: Tracked } = {}

local function where(e: ParticleEmitter): Vector3?
	local parent = e.Parent
	if parent and parent:IsA("Attachment") then
		return parent.WorldPosition
	elseif parent and parent:IsA("BasePart") then
		return parent.Position
	end
	return nil
end

-- Keeps `e`'s Rate (as set now) and Size on the LOD for its position.
-- `fixedSize`: rate only (e.g. flames whose base line is placed by size).
function Lod.track(e: ParticleEmitter?, cutoff: number?, fixedSize: boolean?)
	if not e then
		return
	end
	tracked[e] = { rate = e.Rate, size = e.Size, cutoff = cutoff or Lod.DEFAULT_CUTOFF, sizeK = 1, resize = fixedSize ~= true }
	e.Destroying:Connect(function()
		tracked[e] = nil
	end)
end

-- Changes a tracked emitter's base rate (e.g. a fire burning down).
function Lod.setRate(e: ParticleEmitter, rate: number)
	local t = tracked[e]
	if t then
		t.rate = rate
	else
		e.Rate = rate
	end
end

local function updateTracked()
	for e, t in tracked do
		local p = where(e)
		if not p then
			tracked[e] = nil
			continue
		end
		local rateK, sizeK = Lod.factor(p, t.cutoff)
		e.Rate = t.rate * rateK
		if t.resize and math.abs(sizeK - t.sizeK) > 0.04 then
			t.sizeK = sizeK
			e.Size = Lod.scaleSeq(t.size, sizeK)
		end
	end
end

---------------------------------------------------------------------------
-- Live one-shot particle estimate (Studio QA)
---------------------------------------------------------------------------

local BUCKET = 0.1 -- s
local BUCKETS = 120 -- 12 s horizon (longest one-shot lifetime is ~7.5 s)
local expiring = table.create(BUCKETS, 0)
local oneShotLive = 0
local swept = math.floor(os.clock() / BUCKET)

-- Records `n` particles emitted by `e` (for the Studio estimate only).
function Lod.note(e: ParticleEmitter, n: number)
	if not studio then
		return
	end
	local life = (e.Lifetime.Min + e.Lifetime.Max) * 0.5 / math.max(e.TimeScale, 0.05)
	local slot = math.floor((os.clock() + math.min(life, BUCKET * (BUCKETS - 1))) / BUCKET)
	local i = slot % BUCKETS + 1
	expiring[i] += n
	oneShotLive += n
end

local function sweep()
	local now = math.floor(os.clock() / BUCKET)
	while swept < now do
		swept += 1
		local i = swept % BUCKETS + 1
		oneShotLive -= expiring[i]
		expiring[i] = 0
	end
end

function Lod.oneShotLive(): number
	sweep()
	return oneShotLive
end

local nextUpdate = 0
local nextPublish = 0
RunService.Heartbeat:Connect(function()
	local now = os.clock()
	if now >= nextUpdate then
		nextUpdate = now + UPDATE
		updateTracked()
	end
	if studio and now >= nextPublish then
		nextPublish = now + 0.5
		Workspace:SetAttribute("FxOneShotLive", Lod.oneShotLive())
	end
end)

return Lod
