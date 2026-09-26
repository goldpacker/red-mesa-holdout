--!strict
-- Sound playback that never breaks gameplay: unknown or failing sounds are
-- silently skipped. Only Roblox-provided or original audio is referenced.

local SoundService = game:GetService("SoundService")

local Sfx = {}

type SoundDef = { id: string, volume: number, pitch: number? }

local SOUNDS: { [string]: SoundDef } = {
	Explosion = { id = "rbxasset://sounds/impact_explosion_03.mp3", volume = 0.6 },
	GrenadeBlast = { id = "rbxasset://sounds/impact_explosion_03.mp3", volume = 0.45, pitch = 1.4 },
}

local templates: { [string]: Sound } = {}

local function template(name: string): Sound?
	local def = SOUNDS[name]
	if not def then
		return nil
	end
	local existing = templates[name]
	if existing then
		return existing
	end
	local sound = Instance.new("Sound")
	sound.Name = name
	sound.SoundId = def.id
	sound.Volume = def.volume
	sound.PlaybackSpeed = def.pitch or 1
	sound.Parent = SoundService
	templates[name] = sound
	return sound
end

function Sfx.play(name: string, pitchJitter: number?)
	local ok, err = pcall(function()
		local t = template(name)
		if not t then
			return
		end
		local s = t:Clone()
		if pitchJitter then
			s.PlaybackSpeed *= 1 + (math.random() - 0.5) * pitchJitter
		end
		s.Parent = SoundService
		s:Play()
		s.Ended:Once(function()
			s:Destroy()
		end)
		task.delay(6, function()
			if s.Parent then
				s:Destroy()
			end
		end)
	end)
	if not ok then
		warn("[RedMesa] sound failed: " .. name .. " " .. tostring(err))
	end
end

-- Starts or stops a looping sound; repeated calls with the same state are free.
local loops: { [string]: Sound } = {}
function Sfx.setLoop(name: string, playing: boolean)
	local current = loops[name]
	if playing == (current ~= nil) then
		return
	end
	if not playing and current then
		current:Destroy()
		loops[name] = nil
		return
	end
	local ok = pcall(function()
		local t = template(name)
		if not t then
			return
		end
		local s = t:Clone()
		s.Looped = true
		s.Parent = SoundService
		s:Play()
		loops[name] = s
	end)
	if not ok then
		loops[name] = nil
	end
end

return Sfx
