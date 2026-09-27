--!strict
-- Placeholder airdrop art (AD-1): a simple four-engine transport, a canopy
-- (or a cargo-chute cluster) with rigging over a clone of the load's
-- asset. Everything here is visual only and lives under Workspace.AirdropFx
-- on the client; client/Airdrop drives it from the sortie timeline.
-- AD-2 swaps this module's builders and pose functions for the real art
-- (HS-6 transport, parachutes, platforms) without touching the timeline.
--
-- Every part is CanQuery = false, CanCollide = false: client raycasts
-- (aim, rockets, effects) pass through. Only client/Airdrop's own
-- "no effect" test turns a candidate's parts queryable for one raycast.

local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AssetLibrary = require(ReplicatedStorage.Shared.AssetLibrary)

local Visuals = {}

export type Transport = {
	model: Model,
	root: BasePart,
	parts: { BasePart },
	radius: number,
}

export type Load = {
	kind: string,
	model: Model,
	root: BasePart, -- anchored, invisible; at the load's lowest point
	body: { BasePart },
	canopies: { BasePart },
	beams: { Beam },
	height: number, -- canopy centre above the root
	radius: number, -- bounding sphere radius around root + up * height / 2
	spin: number, -- per-load sway phase
	openAt: number?, -- client clock when the canopy began to open
	collapse: { part: BasePart, from: CFrame, to: CFrame, scale: Vector3 }?,
}

local GUNMETAL = Color3.fromRGB(62, 66, 71)
local CHARCOAL = Color3.fromRGB(42, 44, 48)
local RED = Color3.fromRGB(186, 28, 24)
local CANOPY = Color3.fromRGB(96, 92, 72) -- drab olive, dark against the sky
local CANOPY_TRIM = Color3.fromRGB(150, 36, 30)
local LINE = Color3.fromRGB(40, 38, 34)

local ASSET = { Infantry = "Infantry", Buggy = "Buggy", Tank = "Tank" }
-- Same scale the server gives the landed enemy (EnemyTypes/Infantry ASSET_SCALE).
local ASSET_SCALE = { Infantry = 1.1 }
-- Canopy layout per kind: diameter, rigging length above the load, count.
local CHUTES = {
	Infantry = { diameter = 13, lines = 9, count = 1 },
	Buggy = { diameter = 22, lines = 16, count = 3 },
	Tank = { diameter = 26, lines = 20, count = 4 },
}

local function tag(model: Model)
	model:SetAttribute("Airborne", true)
	CollectionService:AddTag(model, "Airborne")
end

local function quiet(p: BasePart)
	p.Anchored = false
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Massless = true
end

local function part(parent: Instance, name: string, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material?, shape: Enum.PartType?): Part
	local p = Instance.new("Part")
	p.Name = name
	p.Shape = shape or Enum.PartType.Block
	p.Size = size
	p.CFrame = cf
	p.Color = color
	p.Material = material or Enum.Material.Metal
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	quiet(p)
	p.Parent = parent
	return p
end

local function weld(root: BasePart, p: BasePart)
	local w = Instance.new("WeldConstraint")
	w.Part0 = root
	w.Part1 = p
	w.Parent = p
end

local function newRoot(model: Model, cf: CFrame): Part
	local root = part(model, "Root", Vector3.new(1, 1, 1), cf, CHARCOAL)
	root.Anchored = true
	root.Transparency = 1
	model.PrimaryPart = root
	return root
end

---------------------------------------------------------------------------
-- Transport
---------------------------------------------------------------------------

-- A high-wing, four-turboprop cargo aircraft (~100 studs long), nose -Z.
function Visuals.transport(parent: Instance): Transport
	local model = Instance.new("Model")
	model.Name = "Transport"
	local root = newRoot(model, CFrame.new())
	local parts: { BasePart } = {}
	local function add(p: BasePart)
		weld(root, p)
		table.insert(parts, p)
	end
	local axisZ = CFrame.Angles(0, math.rad(90), 0)
	add(part(model, "Fuselage", Vector3.new(96, 13, 13), CFrame.new(0, 0, 0) * axisZ, GUNMETAL, nil, Enum.PartType.Cylinder))
	add(part(model, "Nose", Vector3.new(13, 13, 13), CFrame.new(0, -0.5, -47), GUNMETAL, nil, Enum.PartType.Ball))
	add(part(model, "Cockpit", Vector3.new(8, 3, 6), CFrame.new(0, 4.6, -42), CHARCOAL, Enum.Material.Glass))
	add(part(model, "Wing", Vector3.new(140, 2.2, 15), CFrame.new(0, 6.4, -8), GUNMETAL))
	for _, x in { -46, -24, 24, 46 } do
		add(part(model, "Engine", Vector3.new(16, 4.4, 4.4), CFrame.new(x, 4.2, -14) * axisZ, CHARCOAL, nil, Enum.PartType.Cylinder))
		-- Prop disc: a faint blur (AD-2 brings real blades).
		local prop = part(model, "Prop", Vector3.new(0.4, 11, 11), CFrame.new(x, 4.2, -22.6) * axisZ, CHARCOAL, Enum.Material.Metal, Enum.PartType.Cylinder)
		prop.Transparency = 0.75
		prop.CastShadow = false
		add(prop)
	end
	-- Upswept tail with the ramp underneath.
	add(part(model, "TailBoom", Vector3.new(10, 8, 22), CFrame.new(0, 3, 55) * CFrame.Angles(math.rad(-12), 0, 0), GUNMETAL))
	add(part(model, "Fin", Vector3.new(1.6, 22, 15), CFrame.new(0, 17, 60), GUNMETAL))
	add(part(model, "Stabiliser", Vector3.new(46, 1.4, 10), CFrame.new(0, 8, 62), GUNMETAL))
	add(part(model, "Ramp", Vector3.new(10, 1, 16), CFrame.new(0, -5, 52) * CFrame.Angles(math.rad(14), 0, 0), CHARCOAL))
	-- Red markings: fin band and wing-root chevrons.
	add(part(model, "Marking", Vector3.new(1.7, 4, 9), CFrame.new(0, 21, 60), RED, Enum.Material.Metal))
	for _, x in { -30, 30 } do
		add(part(model, "Marking", Vector3.new(8, 0.2, 5), CFrame.new(x, 7.6, -8), RED, Enum.Material.Metal))
	end
	-- Wingtip navigation lamps.
	add(part(model, "NavLeft", Vector3.new(1.2, 1.2, 1.2), CFrame.new(-70.5, 6.4, -8), Color3.fromRGB(255, 60, 50), Enum.Material.Neon))
	add(part(model, "NavRight", Vector3.new(1.2, 1.2, 1.2), CFrame.new(70.5, 6.4, -8), Color3.fromRGB(80, 255, 120), Enum.Material.Neon))
	tag(model)
	model.Parent = parent
	return { model = model, root = root, parts = parts, radius = 75 }
end

function Visuals.poseTransport(v: Transport, cf: CFrame, _t: number)
	v.root.CFrame = cf
end

---------------------------------------------------------------------------
-- Loads
---------------------------------------------------------------------------

local function fallbackBody(model: Model, kind: string): Model
	local body = Instance.new("Model")
	body.Name = "Body"
	local size = if kind == "Tank" then Vector3.new(11, 6, 20) elseif kind == "Buggy" then Vector3.new(6, 4, 10) else Vector3.new(2, 6.5, 1.4)
	part(body, "Hull", size, CFrame.new(0, size.Y / 2, 0), GUNMETAL)
	body.Parent = model
	return body
end

local function bodyModel(model: Model, kind: string): Model
	local copy = AssetLibrary.clone(ASSET[kind] or "")
	if not (copy and copy:IsA("Model")) then
		if copy then
			copy:Destroy()
		end
		return fallbackBody(model, kind)
	end
	local body = copy :: Model
	body.Name = "Body"
	for _, d in body:GetDescendants() do
		if d:IsA("BaseScript") or d:IsA("Sound") or d:IsA("Light") or d:IsA("JointInstance") or d:IsA("WeldConstraint") then
			d:Destroy()
		elseif d:IsA("BasePart") then
			d.Anchored = true
			d.CanCollide = false
			d.CanQuery = false
			d.CanTouch = false
			-- The soldier's Root is an invisible hip box (vehicle roots are hulls).
			if (kind == "Infantry" and d.Name == "Root") or d.Transparency > 0.95 then
				d.Transparency = 1
			end
		end
	end
	local scale = ASSET_SCALE[kind]
	if scale then
		body:ScaleTo(body:GetScale() * scale)
	end
	body.Parent = model
	return body
end

-- A load hanging under its canopy/canopies: root at the load's feet.
function Visuals.load(parent: Instance, kind: string, loadId: number): Load
	local model = Instance.new("Model")
	model.Name = "Load_" .. loadId
	model:SetAttribute("LoadId", loadId)
	model:SetAttribute("LoadKind", kind)
	local root = newRoot(model, CFrame.new())

	local body = bodyModel(model, kind)
	-- Sit the body's bounding-box bottom on the root, centred over it.
	body:PivotTo(CFrame.new())
	local box, size = body:GetBoundingBox()
	body:PivotTo(CFrame.new(-box.Position.X, size.Y / 2 - box.Position.Y, -box.Position.Z))
	local bodyParts: { BasePart } = {}
	for _, d in body:GetDescendants() do
		if d:IsA("BasePart") then
			quiet(d)
			weld(root, d)
			table.insert(bodyParts, d)
		end
	end

	local chute = CHUTES[kind] or CHUTES.Infantry
	local height = size.Y + chute.lines
	local top = Instance.new("Attachment")
	top.Name = "Rigging"
	-- Risers meet at the harness (the soldier's asset box is padded above the helmet).
	top.Position = Vector3.new(0, size.Y * (if kind == "Infantry" then 0.78 else 0.95), 0)
	top.Parent = root
	local canopies: { BasePart } = {}
	local beams: { Beam } = {}
	for i = 1, chute.count do
		local offset = Vector3.zero
		if chute.count > 1 then
			local a = (i - 1) / chute.count * math.pi * 2
			offset = Vector3.new(math.cos(a), 0, math.sin(a)) * chute.diameter * 0.42
		end
		local centre = Vector3.new(0, height, 0) + offset
		local canopy = part(model, "Canopy", Vector3.new(chute.diameter, chute.diameter * 0.36, chute.diameter), CFrame.new(centre), CANOPY, Enum.Material.Fabric)
		local mesh = Instance.new("SpecialMesh")
		mesh.MeshType = Enum.MeshType.Sphere
		mesh.Parent = canopy
		canopy.Transparency = 1
		weld(root, canopy)
		table.insert(canopies, canopy)
		-- A red crown panel so the canopy reads as the enemy's.
		local crown = part(model, "Crown", Vector3.new(chute.diameter * 0.3, chute.diameter * 0.12, chute.diameter * 0.3), CFrame.new(centre + Vector3.new(0, chute.diameter * 0.15, 0)), CANOPY_TRIM, Enum.Material.Fabric)
		local crownMesh = Instance.new("SpecialMesh")
		crownMesh.MeshType = Enum.MeshType.Sphere
		crownMesh.Parent = crown
		crown.Transparency = 1
		weld(root, crown)
		table.insert(canopies, crown)
		for k = 0, 3 do
			local a = k / 4 * math.pi * 2 + math.pi / 4
			local rim = Instance.new("Attachment")
			rim.Position = Vector3.new(math.cos(a), -0.2, math.sin(a)) * chute.diameter * 0.46
			rim.Parent = canopy
			local beam = Instance.new("Beam")
			beam.Attachment0 = rim
			beam.Attachment1 = top
			beam.Width0 = 0.12
			beam.Width1 = 0.12
			beam.Color = ColorSequence.new(LINE)
			beam.FaceCamera = true
			beam.Segments = 1
			beam.Enabled = false
			beam.Parent = canopy
			table.insert(beams, beam)
		end
	end
	tag(model)
	model.Parent = parent
	return {
		kind = kind,
		model = model,
		root = root,
		body = bodyParts,
		canopies = canopies,
		beams = beams,
		height = height,
		radius = math.max(height, chute.diameter) * 0.6 + size.Magnitude * 0.25,
		spin = (loadId * 1.618) % (math.pi * 2),
		openAt = nil,
		collapse = nil,
	}
end

local OPEN_TIME = 0.45

-- Poses a load: `pos` is its lowest point, `yawDir` the flat facing,
-- `phase` "FreeFall" / "Canopy" / "Landed", `u` the phase progress.
function Visuals.poseLoad(v: Load, pos: Vector3, yawDir: Vector3, phase: string, u: number, t: number)
	local flat = Vector3.new(yawDir.X, 0, yawDir.Z)
	local facing = if flat.Magnitude > 1e-3 then flat.Unit else Vector3.new(0, 0, -1)
	local base = CFrame.lookAt(pos, pos + facing)
	if phase == "FreeFall" then
		-- Tumbling slightly nose-down out of the ramp.
		base *= CFrame.Angles(math.rad(-8 - 10 * u), 0, math.rad(6 * math.sin(t * 3 + v.spin)))
	elseif phase == "Canopy" then
		if not v.openAt then
			v.openAt = t
			for _, c in v.canopies do
				c.Transparency = 0
			end
			for _, b in v.beams do
				b.Enabled = true
			end
		end
		-- Blossom: the canopy snaps open from a narrow streamer.
		local k = math.clamp((t - (v.openAt :: number)) / OPEN_TIME, 0, 1)
		local bloom = 0.25 + 0.75 * (1 - (1 - k) ^ 3)
		for _, c in v.canopies do
			local mesh = c:FindFirstChildOfClass("SpecialMesh")
			if mesh then
				mesh.Scale = Vector3.new(bloom, 1.6 - 0.6 * bloom, bloom)
			end
		end
		-- Pendulum sway about the canopy, settling before touchdown.
		local damp = math.clamp((1 - u) / 0.12, 0, 1)
		local roll = math.rad(7) * math.sin(t * 1.3 + v.spin) * damp
		local pitch = math.rad(4) * math.sin(t * 0.9 + v.spin * 2) * damp
		local pivot = CFrame.new(0, v.height, 0)
		base = base * pivot * CFrame.Angles(pitch, 0, roll) * pivot:Inverse()
	end
	v.root.CFrame = base
end

-- Touchdown: the rigging goes slack and the canopy collapses and drapes
-- downwind of the load.
function Visuals.touchdown(v: Load, drapeDir: Vector3)
	for _, b in v.beams do
		b.Enabled = false
	end
	local dir = Vector3.new(drapeDir.X, 0, drapeDir.Z)
	dir = if dir.Magnitude > 1e-3 then dir.Unit else Vector3.new(1, 0, 0)
	local rootPos = v.root.Position
	local first = true
	for _, c in v.canopies do
		local w = c:FindFirstChildOfClass("WeldConstraint")
		if w then
			w:Destroy()
		end
		c.Anchored = true
		if first then
			first = false
			local size = c.Size
			local landing = rootPos + dir * (size.X * 0.55 + 2) + Vector3.new(0, 0.4, 0)
			v.collapse = { part = c, from = c.CFrame, to = CFrame.lookAt(landing, landing + dir), scale = Vector3.new(1.1, 0.12, 0.8) }
		else
			c.Transparency = 1
		end
	end
end

-- The real enemy took over: the load itself disappears.
function Visuals.handOff(v: Load)
	for _, p in v.body do
		p:Destroy()
	end
	table.clear(v.body)
end

-- Advances the canopy collapse; `age` = seconds since touchdown. Returns
-- true once it has faded out and the visual can be destroyed.
function Visuals.stepCollapse(v: Load, age: number, linger: number): boolean
	local c = v.collapse
	if not c then
		return age > 0.5
	end
	local k = math.clamp(age / 1.4, 0, 1)
	local e = 1 - (1 - k) ^ 2
	c.part.CFrame = c.from:Lerp(c.to, e)
	local mesh = c.part:FindFirstChildOfClass("SpecialMesh")
	if mesh then
		mesh.Scale = Vector3.one:Lerp(c.scale, e)
	end
	if age > linger then
		c.part.Transparency = math.clamp((age - linger) / 1, 0, 1)
	end
	return age > linger + 1
end

-- Parts the "no effect" raycast may hit while the load is in the air.
function Visuals.hitParts(v: Load): { BasePart }
	local list = table.clone(v.body)
	for _, c in v.canopies do
		if c.Transparency < 1 then
			table.insert(list, c)
		end
	end
	return list
end

function Visuals.destroy(v: Load | Transport)
	v.model:Destroy()
end

return Visuals
