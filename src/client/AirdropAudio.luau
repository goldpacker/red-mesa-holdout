--!strict
-- Airdrop sounds (AD-2): the transport's positional engine drone (a loop
-- that swells as it passes, with a small doppler shift), and positional
-- one-shots for the ramp, canopy pops and landings, carried much further
-- than Sfx.playAt's combat falloff because drops happen 300-800 studs out.
-- Everything plays a region of the synthesized sound sheet (SfxSheet); a
-- name the sheet doesn't have yet (the new sheet still in moderation), a
-- failed load or any error is silently skipped (GAME_SPEC §15).

local Workspace = game:GetService("Workspace")

local Sfx = require(script.Parent.Sfx)
local SfxSheet = require(script.Parent.SfxSheet)

local Audio = {}

type Mix = { volume: number, min: number, max: number, voices: number, jitter: number }

-- Distance falloff (InverseTapered): full volume inside `min`, silent at `max`.
local MIX: { [string]: Mix } = {
	RampOpen = { volume = 1.1, min = 260, max = 2400, voices = 3, jitter = 0.06 },
	ChutePop = { volume = 0.9, min = 170, max = 1800, voices = 5, jitter = 0.18 },
	LandingThud = { volume = 1.0, min = 120, max = 1400, voices = 4, jitter = 0.2 },
	PlatformThud = { volume = 1.4, min = 240, max = 2200, voices = 3, jitter = 0.08 },
}

local DRONE = { volume = 0.9, min = 240, max = 2800 }
local SOUND_SPEED = 1200 -- studs/s (343 m/s at 1 stud ~ 0.28 m)

local live: { [string]: number } = {}

local function region(name: string): any
	local regions = (SfxSheet :: any).Regions
	return regions and regions[name]
end

-- Positional one-shot at `where` (a point, or a part it follows).
function Audio.playAt(name: string, where: Vector3 | BasePart, volumeScale: number?)
	local mix = MIX[name]
	local r = region(name)
	if not (mix and r) then
		return
	end
	if (live[name] or 0) >= mix.voices then
		return
	end
	local ok = pcall(function()
		local parent: Instance
		local holder: Attachment? = nil
		if typeof(where) == "Vector3" then
			local a = Instance.new("Attachment")
			a.Name = "AirdropSound"
			a.WorldPosition = where
			a.Parent = Workspace.Terrain
			holder = a
			parent = a
		else
			parent = where
		end
		local s = Instance.new("Sound")
		s.Name = name
		s.SoundId = SfxSheet.SoundId
		s.PlaybackRegionsEnabled = true
		s.PlaybackRegion = NumberRange.new(r.start, r.stop)
		s.RollOffMode = Enum.RollOffMode.InverseTapered
		s.RollOffMinDistance = mix.min
		s.RollOffMaxDistance = mix.max
		s.Volume = mix.volume * (volumeScale or 1)
		s.PlaybackSpeed = 1 + (math.random() - 0.5) * mix.jitter
		s.TimePosition = r.start
		s.Parent = parent
		s:Play()
		live[name] = (live[name] or 0) + 1
		local length = (r.stop - r.start) / s.PlaybackSpeed + 0.2
		task.delay(length, function()
			live[name] = math.max(0, (live[name] or 1) - 1)
			if holder then
				holder:Destroy()
			else
				s:Destroy()
			end
		end)
	end)
	if not ok then
		live[name] = live[name] or 0
	end
end

-- The drone loop on a transport part, or nil (no region / failure).
function Audio.drone(part: BasePart, seed: number): Sound?
	local s = Sfx.attachLoop("TransportDrone", part)
	if not s then
		return nil
	end
	pcall(function()
		s.RollOffMode = Enum.RollOffMode.InverseTapered
		s.RollOffMinDistance = DRONE.min
		s.RollOffMaxDistance = DRONE.max
		s.Volume = DRONE.volume
		-- Formations don't phase against each other.
		s:SetAttribute("BasePitch", 0.96 + ((seed * 0.618) % 1) * 0.08)
		-- Start at a different point of the loop per aircraft.
		local r = region("TransportDrone")
		if r then
			s.TimePosition = r.start + ((seed * 1.37) % 1) * (r.stop - r.start) * 0.9
		end
	end)
	return s
end

-- Doppler: pitch from the aircraft's velocity toward/away from the camera.
function Audio.stepDrone(s: Sound?, position: Vector3, velocity: Vector3, fade: number)
	if not s then
		return
	end
	local cam = Workspace.CurrentCamera
	if not cam then
		return
	end
	local toListener = cam.CFrame.Position - position
	local closing = if toListener.Magnitude > 1 then velocity:Dot(toListener.Unit) else 0
	local base = (s:GetAttribute("BasePitch") :: number?) or 1
	s.PlaybackSpeed = base / math.max(0.5, 1 - closing / SOUND_SPEED)
	s.Volume = DRONE.volume * math.clamp(fade, 0, 1)
end

return Audio
