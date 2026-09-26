--!strict
-- Clip library for the skinned infantry (face-lift CHAR-2): compiles the
-- generated keyframes in InfantryRigClips (authored with IK in
-- tools/assets/models/infantry_anim.py) into CFrames once, and samples
-- them per bone. Transform convention: docs/ASSET_PIPELINE.md "Skinned
-- meshes" (Motor6D-style angles, model faces -Z).

local Data = require(script.Parent.InfantryRigClips)

local Pose = {}

export type Clip = {
	name: string,
	frames: number,
	loop: boolean,
	duration: number,
	cycle: number,
	cf: { { CFrame } }, -- [bone index][frame]
}

Pose.BONES = Data.bones :: { string }
Pose.FPS = Data.fps :: number
Pose.index = {} :: { [string]: number }
for i, name in Pose.BONES do
	Pose.index[name] = i
end

-- Body halves blend separately (legs can start walking while the rifle is
-- still shouldered).
local LOWER_NAMES = {
	Hips = true,
	RightUpperLeg = true,
	RightLowerLeg = true,
	RightFoot = true,
	LeftUpperLeg = true,
	LeftLowerLeg = true,
	LeftFoot = true,
}
Pose.LOWER = {} :: { number }
Pose.UPPER = {} :: { number }
for i, name in Pose.BONES do
	table.insert(if LOWER_NAMES[name] then Pose.LOWER else Pose.UPPER, i)
end

local rad = math.rad

local function compile(name: string, c: any): Clip
	local cf = {}
	for i, bone in Pose.BONES do
		local track = c.tracks[bone]
		local stride = if bone == "Hips" then 6 else 3
		local list = table.create(c.frames)
		for f = 0, c.frames - 1 do
			local o = f * stride
			local r = CFrame.Angles(rad(track[o + 1]), rad(track[o + 2]), rad(track[o + 3]))
			list[f + 1] = if stride == 6 then CFrame.new(track[o + 4], track[o + 5], track[o + 6]) * r else r
		end
		cf[i] = list
	end
	return {
		name = name,
		frames = c.frames,
		loop = c.loop,
		duration = c.duration or (c.frames - 1) / Pose.FPS,
		cycle = c.cycle or 0,
		cf = cf,
	}
end

Pose.clips = {} :: { [string]: Clip }
for name, c in Data.clips do
	Pose.clips[name] = compile(name, c)
end

-- Frames to blend for a clip at time t (s), or at `phase` (0..1) for the
-- distance-driven Walk cycle: (frame a, frame b, weight of b).
function Pose.cursor(clip: Clip, t: number, phase: number?): (number, number, number)
	local n = clip.frames
	if n == 1 then
		return 1, 1, 0
	end
	local pos
	if phase then
		pos = (phase % 1) * n
	elseif clip.loop then
		pos = (t * Pose.FPS) % n
	else
		pos = math.clamp(t * Pose.FPS, 0, n - 1)
	end
	local i0 = math.floor(pos)
	local i1 = i0 + 1
	if i1 >= n then
		i1 = if clip.loop then 0 else n - 1
	end
	return i0 + 1, i1 + 1, pos - i0
end

function Pose.sample(clip: Clip, bone: number, i0: number, i1: number, a: number): CFrame
	local list = clip.cf[bone]
	if a < 1e-3 or i0 == i1 then
		return list[i0]
	end
	return list[i0]:Lerp(list[i1], a)
end

return Pose
