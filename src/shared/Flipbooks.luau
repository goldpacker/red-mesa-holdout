--!strict
-- VFX texture catalogue: flipbook sheets and single textures rendered by
-- tools/vfx (see tools/vfx/README.md). Owned by the VFX workstream; other
-- workstreams may read it. Nothing here creates instances on require.
--
-- Sheets are 1024x1024 8x8 grids (64 frames, row-major from the top left)
-- for ParticleEmitter.FlipbookLayout = Grid8x8. `tinted` sheets are
-- greyscale: the emitter's Color gives them their colour (sand dust vs soot
-- share a sheet). `anchor` is where the effect's origin sits in the frame
-- (0..1 from the top left); offset the particle when it isn't the centre,
-- e.g. SandKick's ground line is near the bottom.
--
-- VelocityParallel (verified in Studio): Roblox lays the texture's X axis
-- along the velocity; Rotation = -90 puts the texture's top along it, which
-- is how MuzzleFlashSide and RocketExhaust are drawn (tip/tail at the top).
--
-- Flipbooks.apply(emitter, name, scale?) sets texture + flipbook playback and
-- the suggested look; callers still own Rate/Speed/Acceleration/Enabled.
-- Returns false (and changes nothing) when the texture isn't uploaded.
--
-- Brightness values are the afternoon ones, tuned in game at real weapon
-- distances against LightingRig's bloom (VFX-2). At lower bloom
-- thresholds (dusk/night) scale emissive Brightness by
-- client/Effects.exposure() (~0.57 at night) or flashes turn into white
-- halos.

local Flipbooks = {}

export type Suggest = {
	lifetime: { number }?, -- NumberRange min, max (seconds)
	size: { number }?, -- NumberSequence keypoints, evenly spaced (studs)
	transparency: { number }?, -- NumberSequence keypoints, evenly spaced
	color: Color3?,
	lightEmission: number?,
	lightInfluence: number?,
	brightness: number?,
	orientation: Enum.ParticleOrientation?,
	rotation: { number }?, -- NumberRange degrees
	rotSpeed: { number }?, -- NumberRange degrees/s
}

export type Entry = {
	kind: "Sheet" | "Single",
	frames: number,
	mode: Enum.ParticleFlipbookMode?,
	fps: number?, -- FlipbookFramerate (OneShot plays over the lifetime instead)
	startRandom: boolean?,
	tinted: boolean,
	anchor: Vector2,
	size: Vector2, -- texture pixels
	notes: string,
	suggest: Suggest,
}

-- BEGIN GENERATED IDS (tools/vfx/upload.py)
local IDS: { [string]: string } = {
	Fireball = "rbxassetid://106963804797541",
	SmokeDark = "rbxassetid://75400629363258",
	DustPuff = "rbxassetid://79963003186563",
	SandKick = "rbxassetid://134050843014153",
	MissileTrail = "rbxassetid://90904188681683",
	MuzzleFlashFront = "rbxassetid://111983300404616",
	MuzzleFlashSide = "rbxassetid://125690822846683",
	MuzzleFlashBurst = "rbxassetid://100409497539336",
	RocketExhaust = "rbxassetid://78564296486904",
	Sparks = "rbxassetid://105554500519561",
	Flames = "rbxassetid://112483539287686",
	RockChips = "rbxassetid://124013513360860",
	DustDrift = "rbxassetid://94318599595582",
	TracerBeam = "rbxassetid://72994897813399",
	ShockwaveRing = "rbxassetid://96437980176600",
	ScorchMark = "rbxassetid://135513625298189",
}
-- END GENERATED IDS

local CENTRE = Vector2.new(0.5, 0.5)
local SHEET = Vector2.new(1024, 1024)

local ENTRIES: { [string]: Entry } = {
	Fireball = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.OneShot,
		fps = 40,
		tinted = false,
		anchor = CENTRE,
		size = SHEET,
		notes = "Mantaflow explosion: white-hot ignition, orange fire, dark red embers in oily smoke, fades out. Colour baked.",
		suggest = {
			lifetime = { 1.1, 1.5 },
			size = { 9, 20, 24 },
			transparency = { 0, 0, 0.15 },
			color = Color3.new(1, 1, 1),
			lightEmission = 0.25,
			lightInfluence = 0.15,
			brightness = 1.3,
			orientation = Enum.ParticleOrientation.FacingCamera,
			rotation = { 0, 360 },
			rotSpeed = { -20, 20 },
		},
	},
	SmokeDark = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.OneShot,
		fps = 16,
		tinted = true,
		anchor = CENTRE,
		size = SHEET,
		notes = "Dense crisp billowing smoke that roils, grows and thins at the end. Greyscale with a dark underside; tint near-black for oily smoke, grey-brown for dust-laden smoke.",
		suggest = {
			lifetime = { 4, 6.5 },
			size = { 8, 18, 26 },
			transparency = { 0.1, 0.2, 0.6 },
			color = Color3.fromRGB(74, 68, 61),
			lightEmission = 0,
			lightInfluence = 0.9,
			orientation = Enum.ParticleOrientation.FacingCamera,
			rotation = { 0, 360 },
			rotSpeed = { -8, 8 },
		},
	},
	DustPuff = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.OneShot,
		fps = 32,
		tinted = true,
		anchor = CENTRE,
		size = SHEET,
		notes = "Soft lumpy dust burst that billows out and thins away. Greyscale; tint with bleached sand.",
		suggest = {
			lifetime = { 1.6, 2.4 },
			size = { 4, 10, 13 },
			transparency = { 0.15, 0.3, 1 },
			color = Color3.fromRGB(217, 185, 140),
			lightEmission = 0,
			lightInfluence = 1,
			orientation = Enum.ParticleOrientation.FacingCamera,
			rotation = { 0, 360 },
			rotSpeed = { -15, 15 },
		},
	},
	DustDrift = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.OneShot,
		fps = 24,
		tinted = true,
		anchor = CENTRE,
		size = SHEET,
		notes = "VFX-3 motion dust: a soft, edgeless dust cloud that spreads and thins (painted, tools/vfx/sheets/drift.py). Many overlapping particles merge into one haze, so trails behind wheels and tracks, rotor downwash and jet wakes don't read as strings of puffs. Greyscale, lit from above; tint to the ground.",
		suggest = {
			lifetime = { 1.8, 2.8 },
			size = { 5, 12, 16 },
			transparency = { 0.4, 0.55, 1 },
			color = Color3.fromRGB(214, 160, 110),
			lightEmission = 0,
			lightInfluence = 1,
			orientation = Enum.ParticleOrientation.FacingCamera,
			rotation = { 0, 360 },
			rotSpeed = { -10, 10 },
		},
	},
	SandKick = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.OneShot,
		fps = 64,
		tinted = true,
		anchor = Vector2.new(0.5, 0.885),
		size = SHEET,
		notes = "Sand spurt thrown up from an impact (clumps, grains, base ring) falling back. Ground line at 88.5% down: spawn at hit + up * 0.385 * size. Keep upright with FacingCameraWorldUp; no rotation.",
		suggest = {
			lifetime = { 0.8, 1.1 },
			size = { 5, 6 },
			transparency = { 0, 0, 0.2 },
			color = Color3.fromRGB(201, 162, 122),
			lightEmission = 0,
			lightInfluence = 1,
			orientation = Enum.ParticleOrientation.FacingCameraWorldUp,
			rotation = { 0, 0 },
			rotSpeed = { 0, 0 },
		},
	},
	MissileTrail = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.OneShot,
		fps = 30,
		tinted = true,
		anchor = CENTRE,
		size = SHEET,
		notes = "One trail puff: small and dense, blooms into a wispy cloud, dissolves. Emit densely along the flight path. Greyscale.",
		suggest = {
			lifetime = { 1.6, 2.6 },
			size = { 1.4, 5, 8 },
			transparency = { 0.1, 0.35, 1 },
			color = Color3.fromRGB(230, 226, 218),
			lightEmission = 0,
			lightInfluence = 1,
			orientation = Enum.ParticleOrientation.FacingCamera,
			rotation = { 0, 360 },
			rotSpeed = { -30, 30 },
		},
	},
	MuzzleFlashFront = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.Loop,
		fps = 1,
		startRandom = true,
		tinted = false,
		anchor = CENTRE,
		size = SHEET,
		notes = "64 variants of a 4-6 prong star flash seen down the barrel. startRandom + low fps = one random variant per particle. Colour baked.",
		suggest = {
			lifetime = { 0.04, 0.06 },
			size = { 3, 3.6 },
			transparency = { 0, 0.4 },
			color = Color3.new(1, 1, 1),
			lightEmission = 1,
			lightInfluence = 0,
			brightness = 0.9,
			orientation = Enum.ParticleOrientation.FacingCamera,
			rotation = { 0, 360 },
			rotSpeed = { 0, 0 },
		},
	},
	MuzzleFlashSide = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.Loop,
		fps = 1,
		startRandom = true,
		tinted = false,
		anchor = Vector2.new(0.5, 0.725),
		size = SHEET,
		notes = "64 variants of a side-on flash pointing up the texture (with brake jets). Muzzle 22.5% below centre: spawn at muzzle + forward * 0.225 * size, velocity along the barrel, VelocityParallel with Rotation -90. Colour baked.",
		suggest = {
			lifetime = { 0.04, 0.06 },
			size = { 3.4, 4.2 },
			transparency = { 0, 0.4 },
			color = Color3.new(1, 1, 1),
			lightEmission = 1,
			lightInfluence = 0,
			brightness = 1.1,
			orientation = Enum.ParticleOrientation.VelocityParallel,
			rotation = { -90, -90 },
			rotSpeed = { 0, 0 },
		},
	},
	MuzzleFlashBurst = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.Loop,
		fps = 1,
		startRandom = true,
		tinted = false,
		anchor = CENTRE,
		size = SHEET,
		notes = "64 variants of a round launch/cannon blast with flame licks (rocket pod, tank gun, AA launch). Colour baked.",
		suggest = {
			lifetime = { 0.06, 0.1 },
			size = { 5, 7 },
			transparency = { 0, 0.5 },
			color = Color3.new(1, 1, 1),
			lightEmission = 1,
			lightInfluence = 0,
			brightness = 1.2,
			orientation = Enum.ParticleOrientation.FacingCamera,
			rotation = { 0, 360 },
			rotSpeed = { 0, 0 },
		},
	},
	RocketExhaust = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.Loop,
		fps = 30,
		startRandom = true,
		tinted = false,
		anchor = Vector2.new(0.5, 0.85),
		size = SHEET,
		notes = "Seamless 64-frame loop of a flame plume; nozzle 35% below centre, tail toward the top. With VelocityParallel + Rotation -90 emit backwards (texture top = away from the rocket); spawn at nozzle - forward * 0.35 * size. Colour baked.",
		suggest = {
			lifetime = { 0.05, 0.08 },
			size = { 2.6, 3.2 },
			transparency = { 0, 0.3 },
			color = Color3.new(1, 1, 1),
			lightEmission = 1,
			lightInfluence = 0,
			brightness = 1.2,
			orientation = Enum.ParticleOrientation.VelocityParallel,
			rotation = { -90, -90 },
			rotSpeed = { 0, 0 },
		},
	},
	Sparks = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.OneShot,
		fps = 90,
		tinted = false,
		anchor = CENTRE,
		size = SHEET,
		notes = "Burst of hot sparks: impact glow, motion-blurred streaks arcing under gravity, cooling white to orange. Keep upright (FacingCameraWorldUp). Colour baked.",
		suggest = {
			lifetime = { 0.55, 0.75 },
			size = { 5, 6 },
			transparency = { 0, 0 },
			color = Color3.new(1, 1, 1),
			lightEmission = 1,
			lightInfluence = 0,
			brightness = 1.6,
			orientation = Enum.ParticleOrientation.FacingCameraWorldUp,
			rotation = { 0, 0 },
			rotSpeed = { 0, 0 },
		},
	},
	Flames = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.Loop,
		fps = 30,
		startRandom = true,
		tinted = false,
		anchor = Vector2.new(0.5, 0.89),
		size = SHEET,
		notes = "Seamless 64-frame loop of licking flames for lasting fires (wrecks, the emplacement at defeat, crashing aircraft). Base line 39% below centre: spawn at fire base + up * 0.39 * size. Keep upright (FacingCameraWorldUp, no rotation); overlap 2-4 particles with a fade-in/out Transparency. Colour baked (yellow core, orange body, red tips).",
		suggest = {
			lifetime = { 0.8, 1.2 },
			size = { 3.2, 4.2, 3.6 },
			transparency = { 0.6, 0.05, 0.1, 1 },
			color = Color3.new(1, 1, 1),
			lightEmission = 0.55,
			lightInfluence = 0,
			brightness = 1.4,
			orientation = Enum.ParticleOrientation.FacingCameraWorldUp,
			rotation = { 0, 0 },
			rotSpeed = { 0, 0 },
		},
	},
	RockChips = {
		kind = "Sheet",
		frames = 64,
		mode = Enum.ParticleFlipbookMode.OneShot,
		fps = 64,
		tinted = true,
		anchor = CENTRE,
		size = SHEET,
		notes = "Bullet hit on rock: dark motion-blurred chips thrown up and out under gravity, and a dust cloud that swells and thins. Greyscale: tint to the rock (cliff rust ~150,84,58). Keep upright (FacingCameraWorldUp).",
		suggest = {
			lifetime = { 0.7, 0.9 },
			size = { 4.2, 5 },
			transparency = { 0, 0 },
			color = Color3.fromRGB(150, 84, 58),
			lightEmission = 0,
			lightInfluence = 1,
			orientation = Enum.ParticleOrientation.FacingCameraWorldUp,
			rotation = { 0, 0 },
			rotSpeed = { 0, 0 },
		},
	},
	TracerBeam = {
		kind = "Single",
		frames = 1,
		tinted = true,
		anchor = CENTRE,
		size = Vector2.new(512, 128),
		notes = "Beam texture: U (x) runs along the beam and tiles, V across: white-hot core, soft halo. TextureMode Stretch (or Wrap), LightEmission 1, Brightness 2-4; Color amber for ours (255,179,71), red for the enemy (255,74,54). Fade the tail with Beam.Transparency; a second thin white beam adds a whiter core.",
		suggest = {
			color = Color3.fromRGB(255, 179, 71),
			lightEmission = 1,
			lightInfluence = 0,
			brightness = 3,
		},
	},
	ShockwaveRing = {
		kind = "Single",
		frames = 1,
		tinted = true,
		anchor = CENTRE,
		size = SHEET,
		notes = "Top-down ring: sharp front at 80% radius, soft streaky trail inside. Lay it flat (ParticleEmitter Orientation VelocityPerpendicular with upward speed, or a flat part/Decal) and grow it fast. Tint warm for air bursts, dusty for ground blasts.",
		suggest = {
			lifetime = { 0.3, 0.35 },
			size = { 2, 36 },
			transparency = { 0.15, 1 },
			color = Color3.fromRGB(255, 226, 184),
			lightEmission = 0.5,
			lightInfluence = 0.5,
			orientation = Enum.ParticleOrientation.VelocityPerpendicular,
			rotation = { 0, 360 },
			rotSpeed = { 0, 0 },
		},
	},
	ScorchMark = {
		kind = "Single",
		frames = 1,
		tinted = false,
		anchor = CENTRE,
		size = SHEET,
		notes = "Top-down burn decal (charred centre, burnt edge, radial splatter), colour baked. Put it on the top face of a thin non-colliding transparent part on the ground (Decal), ~10-14 studs for a rocket hit; fade it out over ~20 s.",
		suggest = {},
	},
}

local function numberSequence(values: { number }): NumberSequence
	if #values == 1 then
		return NumberSequence.new(values[1])
	end
	local keys = {}
	for i, v in values do
		table.insert(keys, NumberSequenceKeypoint.new((i - 1) / (#values - 1), v))
	end
	return NumberSequence.new(keys)
end

local function scaled(values: { number }, scale: number): { number }
	local out = table.create(#values)
	for i, v in values do
		out[i] = v * scale
	end
	return out
end

-- The catalogue entry, or nil for an unknown name.
function Flipbooks.get(name: string): Entry?
	return ENTRIES[name]
end

-- "rbxassetid://..." for an uploaded texture, else nil (callers fall back).
function Flipbooks.texture(name: string): string?
	return IDS[name]
end

function Flipbooks.names(): { string }
	local out = {}
	for name in ENTRIES do
		table.insert(out, name)
	end
	table.sort(out)
	return out
end

-- Configures `emitter` for the named sheet: texture, flipbook playback and
-- the suggested look (size scaled by `scale`, default 1).
function Flipbooks.apply(emitter: ParticleEmitter, name: string, scale: number?): boolean
	local entry = ENTRIES[name]
	local id = IDS[name]
	if not entry or not id then
		return false
	end
	local k = scale or 1
	emitter.Texture = id
	if entry.kind == "Sheet" then
		emitter.FlipbookLayout = Enum.ParticleFlipbookLayout.Grid8x8
		emitter.FlipbookMode = entry.mode or Enum.ParticleFlipbookMode.OneShot
		emitter.FlipbookFramerate = NumberRange.new(entry.fps or 30)
		emitter.FlipbookStartRandom = entry.startRandom == true
	else
		emitter.FlipbookLayout = Enum.ParticleFlipbookLayout.None
	end
	local s = entry.suggest
	if s.lifetime then
		emitter.Lifetime = NumberRange.new(s.lifetime[1], s.lifetime[2] or s.lifetime[1])
	end
	if s.size then
		emitter.Size = numberSequence(scaled(s.size, k))
	end
	if s.transparency then
		emitter.Transparency = numberSequence(s.transparency)
	end
	if s.color then
		emitter.Color = ColorSequence.new(s.color)
	end
	if s.lightEmission then
		emitter.LightEmission = s.lightEmission
	end
	if s.lightInfluence then
		emitter.LightInfluence = s.lightInfluence
	end
	if s.brightness then
		emitter.Brightness = s.brightness
	end
	if s.orientation then
		emitter.Orientation = s.orientation
	end
	if s.rotation then
		emitter.Rotation = NumberRange.new(s.rotation[1], s.rotation[2] or s.rotation[1])
	end
	if s.rotSpeed then
		emitter.RotSpeed = NumberRange.new(s.rotSpeed[1], s.rotSpeed[2] or s.rotSpeed[1])
	end
	return true
end

return Flipbooks
