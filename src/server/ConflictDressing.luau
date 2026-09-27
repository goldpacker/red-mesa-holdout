--!strict
-- Conflict and habitation dressing (ENV-4, docs/AIRDROP_ENVIRONMENT_PLAN.md
-- §2 "Ground realism", GAME_SPEC §13): signs of an ongoing war and of past
-- life, placed as a composition (ConflictLayout), not scattered:
--   * burnt-out hulks: the enemy Tank/Buggy assets in their burnt wreck
--     look (each part's `Wreck` SurfaceAppearance, HS-5), tilted and sunk;
--   * the outpost's checkpoint where the road meets the mesa foot: hesco
--     bastions, jersey barriers, concertina wire on pickets;
--   * a power line with sagging wires across the far basin;
--   * a ruined roadside compound on the left flank (adobe walls, a
--     collapsed roof, rubble);
--   * crates, tyres and fuel drums where people worked, scorched ground
--     under the hulks.
-- Meshes: assets/roblox/ConflictDressing.rbxmx and GroundPatches.rbxmx
-- (tools/env/dressing/: meshes.py, textures.py; one atlas each).
--
-- Visual only. Every part is anchored and CanCollide/CanQuery/CanTouch
-- false, so bullets, the drop-zone sampler, Kit.groundY and enemies never
-- see it. The layout keeps every piece off the lanes and out of the
-- turret's sight lines to them (QA losCheck), and the big pieces out of the
-- airdrop landings and walks to the lanes (ENV-4 survey: 900 sorties
-- planned with the gameplay planner, tools/env/dressing/survey.py).
-- Missing assets leave that piece out.
--
-- Hooks for VFX-4 (wind, wreck smoke; src/shared/Wind.luau when it exists):
--   * Battlefield.ConflictDressing.Wires: one `Wire_Span` MeshPart per span
--     (three sagging wires, pivot at the span's mid-point at insulator
--     height, X along the span); folder attribute `Flutter` = sway
--     amplitude (degrees of roll about the span's X axis) for a gust of 1.
--     Meshes, not Beams: 51 Beams cost 51 draw calls (ENV-4 A/B), the
--     instanced spans cost one.
--   * Battlefield.ConflictDressing.Hulks: each hulk Model has attribute
--     `Smoke` ("light" | "none") and an Attachment "SmokeAnchor" at its
--     engine deck for a thin smoke column.
--   * Wire coils (Battlefield.ConflictDressing.Checkpoint.Wire_Coil*) carry
--     attribute `Sway` like the foliage.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Layout = require(script.Parent.ConflictLayout)

local ConflictDressing = {}

-- The wires' centre on the Pole mesh, relative to its ground pivot
-- (meshes.py POLE_H 30, ARM_Y 28.4: the insulator tops); Wire_Span is
-- built for SPAN studs and stretched along X to each span.
local WIRE_TOP = Vector3.new(0, 29.3, 0)
local SPAN = 74
-- Dressing casts shadows only this close to the turret (studs), and only
-- pieces taller than SHADOW_MIN_HEIGHT.
local SHADOW_RANGE = 320
local SHADOW_MIN_HEIGHT = 2.5

local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Include

local function assets(): Instance?
	return ReplicatedStorage:FindFirstChild("Assets")
end

local function template(kit: string, name: string): BasePart?
	local a = assets()
	local folder = a and a:FindFirstChild(kit)
	local t = folder and folder:FindFirstChild(name)
	return if t and t:IsA("BasePart") then t else nil
end

local function prepare(part: BasePart)
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
end

local function ground(p: Vector2): (number, Vector3)
	params.FilterDescendantsInstances = { Workspace.Terrain }
	local hit = Workspace:Raycast(Vector3.new(p.X, 300, p.Y), Vector3.new(0, -400, 0), params)
	if hit then
		return hit.Position.Y, hit.Normal
	end
	return 0, Vector3.yAxis
end

local function shadowFor(at: Vector3, height: number): boolean
	return height >= SHADOW_MIN_HEIGHT and Vector2.new(at.X, at.Z).Magnitude < SHADOW_RANGE
end

-- Places a template at a ground point. `yaw` degrees (0: the mesh's front
-- faces -Z), `lean` tilts toward the terrain normal (0 upright, 1 fully),
-- `sink` studs into the ground, `roll`/`pitch` extra degrees.
export type Place = { at: Vector2, yaw: number?, lean: number?, sink: number?, roll: number?, pitch: number?, scale: number?, y: number? }

local function placePart(t: BasePart, parent: Instance, spec: Place, name: string?): BasePart
	local part = t:Clone()
	prepare(part)
	local scale = spec.scale or 1
	if scale ~= 1 then
		part.Size = t.Size * scale
		part.PivotOffset = CFrame.new(t.PivotOffset.Position * scale)
	end
	local y, normal = ground(spec.at)
	y = spec.y or y
	local up = Vector3.yAxis:Lerp(normal, spec.lean or 0).Unit
	local at = Vector3.new(spec.at.X, y - (spec.sink or 0), spec.at.Y)
	local cf = CFrame.new(at)
		* CFrame.fromRotationBetweenVectors(Vector3.yAxis, up)
		* CFrame.Angles(0, math.rad(spec.yaw or 0), 0)
		* CFrame.Angles(math.rad(spec.pitch or 0), 0, math.rad(spec.roll or 0))
	part:PivotTo(cf)
	part.CastShadow = t.CastShadow and shadowFor(at, part.Size.Y)
	if name then
		part.Name = name
	end
	part.Parent = parent
	return part
end

---------------------------------------------------------------------------
-- Hulks
---------------------------------------------------------------------------

-- Parts of a vehicle asset a hulk drops: detail kits beyond this distance
-- (they are hidden there on live vehicles too, client/VehicleLod), and any
-- part named in `drop`.
local KIT_RANGE = 420

local function burn(model: Instance, tint: Color3)
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			prepare(d)
			local folder = d:FindFirstChild("Wreck")
			local wreck = folder and folder:FindFirstChildWhichIsA("SurfaceAppearance")
			local live = d:FindFirstChildWhichIsA("SurfaceAppearance")
			if wreck and live then
				live:Destroy()
				wreck.Color = tint
				wreck.Parent = d
			elseif live then
				live.Color = Color3.fromRGB(88, 70, 58)
			else
				d.Color = d.Color:Lerp(Color3.fromRGB(22, 20, 19), 0.6)
				if d.Material == Enum.Material.Neon or d.Material == Enum.Material.Glass then
					d.Material = Enum.Material.Slate
				end
			end
			if folder then
				folder:Destroy()
			end
			if d.Transparency > 0.5 then
				d.Transparency = 1
			end
		elseif d:IsA("Light") or d:IsA("ParticleEmitter") or d:IsA("Beam") or d:IsA("Trail") or d:IsA("Sound") or d:IsA("Script") or d:IsA("LocalScript") then
			d:Destroy()
		end
	end
end

export type Hulk = Place & { kind: string, turret: number?, drop: { string }?, smoke: string? }

local function buildHulk(spec: Hulk, parent: Instance): Model?
	local a = assets()
	local src = a and a:FindFirstChild(spec.kind)
	if not (src and src:IsA("Model")) then
		return nil
	end
	local model = src:Clone()
	local y, normal = ground(spec.at)
	local far = spec.at.Magnitude > KIT_RANGE
	for _, name in spec.drop or {} do
		local p = model:FindFirstChild(name, true)
		if p then
			p:Destroy()
		end
	end
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and far and (string.sub(d.Name, -3) == "Kit" or string.sub(d.Name, 1, 5) == "Track") then
			-- far hulks: no detail kits and no tracks (a burnt tank sits on
			-- its belly behind its skirts); ~4.4k triangles instead of ~16k
			d:Destroy()
		elseif d:IsA("Attachment") or d:IsA("Constraint") or d:IsA("JointInstance") or d:IsA("WeldConstraint") then
			d:Destroy()
		end
	end
	local k = (spec.at.X * 0.37 + spec.at.Y * 0.11) % 1
	burn(model, Color3.new(1, 1, 1):Lerp(Color3.fromRGB(214, 200, 188), k))
	-- Turret knocked round on its ring (rotate the Turret sub-model about the hull's up axis).
	local turret = model:FindFirstChild("Turret")
	if turret and turret:IsA("Model") and spec.turret then
		local pivot = turret:GetPivot()
		turret:PivotTo(pivot * CFrame.Angles(0, math.rad(spec.turret), 0))
	end
	local up = Vector3.yAxis:Lerp(normal, spec.lean or 0.6).Unit
	-- without its tracks a tank hull would float by their ground clearance
	local belly = if far and spec.kind == "Tank" then 1.5 else 0
	local at = Vector3.new(spec.at.X, y - (spec.sink or 0.6) - belly, spec.at.Y)
	-- The asset's pivot is its ground contact (Kit.groundFrame places it so).
	model:PivotTo(CFrame.new(at) * CFrame.fromRotationBetweenVectors(Vector3.yAxis, up) * CFrame.Angles(0, math.rad(spec.yaw or 0), 0) * CFrame.Angles(math.rad(spec.pitch or 0), 0, math.rad(spec.roll or 0)))
	local near = Vector2.new(at.X, at.Z).Magnitude < SHADOW_RANGE
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.CastShadow = near and d.Size.Magnitude > 4
		end
	end
	local cf, size = model:GetBoundingBox()
	local anchor = Instance.new("Attachment")
	anchor.Name = "SmokeAnchor"
	local root = model.PrimaryPart or model:FindFirstChild("Root", true)
	if root and root:IsA("BasePart") then
		anchor.WorldPosition = cf.Position + Vector3.new(0, size.Y * 0.35, 0)
		anchor.Parent = root
	end
	model:SetAttribute("Smoke", spec.smoke or "none")
	model:SetAttribute("SetDressing", true)
	model.Name = "Hulk_" .. spec.kind
	model.Parent = parent
	return model
end

---------------------------------------------------------------------------
-- Rows, clusters, the power line
---------------------------------------------------------------------------

-- Pieces every `step` studs along from -> to (yaw along the row), with a
-- little jitter; `every`/`extra` interleave a second piece (wire pickets).
export type Row = { kit: string, piece: string, from: Vector2, to: Vector2, step: number, jitter: number?, yawJitter: number?, lean: number?, sink: number?, skip: { number }?, extra: string?, extraStep: number? }

local function buildRow(row: Row, parent: Instance, rng: Random): number
	local t = template(row.kit, row.piece)
	if not t then
		return 0
	end
	local d = row.to - row.from
	local len = d.Magnitude
	local dir = d.Unit
	local side = Vector2.new(-dir.Y, dir.X)
	local yaw = math.deg(math.atan2(-dir.Y, dir.X))
	local n = math.max(1, math.floor(len / row.step + 0.5))
	local skip: { [number]: boolean } = {}
	for _, i in row.skip or {} do
		skip[i] = true
	end
	local placed = 0
	for i = 0, n - 1 do
		if not skip[i + 1] then
			local p = row.from + dir * (row.step * (i + 0.5)) + side * rng:NextNumber(-1, 1) * (row.jitter or 0)
			placePart(t, parent, {
				at = p,
				yaw = yaw + rng:NextNumber(-1, 1) * (row.yawJitter or 0),
				lean = row.lean or 0.5,
				sink = row.sink or 0.15,
			})
			placed += 1
		end
	end
	local extra = row.extra and template(row.kit, row.extra)
	if extra and row.extraStep then
		for i = 0, math.floor(len / row.extraStep) do
			local p = row.from + dir * (row.extraStep * i)
			placePart(extra, parent, { at = p + side * 0.2, yaw = yaw, lean = 0.2, sink = 0.2 })
			placed += 1
		end
	end
	return placed
end

export type Piece = Place & { kit: string, piece: string }

local function buildPieces(list: { Piece }, parent: Instance): number
	local placed = 0
	for _, spec in list do
		local t = template(spec.kit, spec.piece)
		if t then
			placePart(t, parent, spec, spec.piece)
			placed += 1
		end
	end
	return placed
end

-- A group of pieces laid out around `origin` (offsets rotated by `yaw`).
export type Group = { origin: Vector2, yaw: number, pieces: { Piece } }

local function buildGroup(group: Group, parent: Instance): number
	local c, s = math.cos(math.rad(group.yaw)), math.sin(math.rad(group.yaw))
	local list: { Piece } = {}
	for _, p in group.pieces do
		local o = p.at
		local world = group.origin + Vector2.new(o.X * c + o.Y * s, -o.X * s + o.Y * c)
		local q = table.clone(p) :: any
		q.at = world
		q.yaw = (p.yaw or 0) + group.yaw
		table.insert(list, q)
	end
	return buildPieces(list, parent)
end

-- One Wire_Span mesh from world point `a` to `b` (stretched along X).
local function wireSpan(t: BasePart, a: Vector3, b: Vector3, parent: Instance)
	local d = b - a
	local len = d.Magnitude
	if len < 1 then
		return
	end
	local part = t:Clone()
	prepare(part)
	local k = len / SPAN
	part.Size = Vector3.new(t.Size.X * k, t.Size.Y, t.Size.Z)
	part.PivotOffset = CFrame.new(t.PivotOffset.Position * Vector3.new(k, 1, 1))
	local x = d.Unit
	local up = (Vector3.yAxis - x * x:Dot(Vector3.yAxis)).Unit
	part:PivotTo(CFrame.fromMatrix((a + b) / 2, x, up))
	part.CastShadow = false
	part.Parent = parent
end

export type Line = { points: { Vector2 }, spacing: number, snapped: { number }?, missing: { number }? }

local function buildLine(line: Line, poles: Instance, wires: Instance, rng: Random): number
	local pole, snapped, top = template("ConflictDressing", "Pole"), template("ConflictDressing", "Pole_Snapped"), template("ConflictDressing", "Pole_Top")
	if not pole then
		return 0
	end
	-- stations along the polyline every `spacing`
	local stations: { { p: Vector2, dir: Vector2 } } = {}
	for i = 1, #line.points - 1 do
		local a, b = line.points[i], line.points[i + 1]
		local n = math.max(1, math.floor((b - a).Magnitude / line.spacing + 0.5))
		for k = 0, n - 1 do
			table.insert(stations, { p = a:Lerp(b, k / n), dir = (b - a).Unit })
		end
	end
	table.insert(stations, { p = line.points[#line.points], dir = (line.points[#line.points] - line.points[#line.points - 1]).Unit })
	local snap: { [number]: boolean } = {}
	for _, i in line.snapped or {} do
		snap[i] = true
	end
	local gone: { [number]: boolean } = {}
	for _, i in line.missing or {} do
		gone[i] = true
	end
	local placedPoles: { [number]: BasePart } = {}
	local count = 0
	for i, st in stations do
		if not gone[i] then
			-- crossarm (mesh X) across the line: yaw so local X is perpendicular to dir
			local yaw = math.deg(math.atan2(-st.dir.Y, st.dir.X)) + 90 + rng:NextNumber(-3, 3)
			local lean = rng:NextNumber(-1.2, 1.2)
			if snap[i] and snapped then
				placePart(snapped, poles, { at = st.p, yaw = yaw, sink = 0.4, roll = lean })
				if top then
					local fall = st.p + Vector2.new(st.dir.Y, -st.dir.X) * 9
					placePart(top, poles, { at = fall, yaw = yaw + rng:NextNumber(-40, 40), lean = 1, sink = 0.2 })
				end
			else
				placedPoles[i] = placePart(pole, poles, { at = st.p, yaw = yaw, sink = 0.5, roll = lean, pitch = rng:NextNumber(-1, 1) })
			end
			count += 1
		end
	end
	local span = template("ConflictDressing", "Wire_Span")
	for i = 1, #stations - 1 do
		local a, b = placedPoles[i], placedPoles[i + 1]
		if span and a and b then
			wireSpan(span, a:GetPivot():PointToWorldSpace(WIRE_TOP), b:GetPivot():PointToWorldSpace(WIRE_TOP), wires)
		elseif span and a and not b and snap[i + 1] then
			-- the wires dragged down to the snapped pole's stump
			local stump = stations[i + 1].p
			local y = ground(stump)
			wireSpan(span, a:GetPivot():PointToWorldSpace(WIRE_TOP), Vector3.new(stump.X, y + 10.5, stump.Y), wires)
		end
	end
	return count
end

---------------------------------------------------------------------------

function ConflictDressing.build(parent: Instance): boolean
	local a = assets()
	if not (a and a:FindFirstChild("ConflictDressing")) then
		return false
	end
	local started = os.clock()
	local rng = Random.new(Layout.SEED)
	local folder = Instance.new("Folder")
	folder.Name = "ConflictDressing"
	local function sub(name: string): Folder
		local f = Instance.new("Folder")
		f.Name = name
		f.Parent = folder
		return f
	end
	local hulks, checkpoint, compound, props, poles, wires = sub("Hulks"), sub("Checkpoint"), sub("Compound"), sub("Props"), sub("Poles"), sub("Wires")
	wires:SetAttribute("Flutter", 1.5)
	local n = 0
	for _, h in Layout.HULKS do
		if buildHulk(h, hulks) then
			n += 1
		end
	end
	for _, row in Layout.ROWS do
		n += buildRow(row, checkpoint, rng)
	end
	for _, coil in checkpoint:GetChildren() do
		if coil.Name == "Wire_Coil" then
			coil:SetAttribute("Sway", 0.02)
		end
	end
	n += buildPieces(Layout.PIECES, props)
	for _, group in Layout.GROUPS do
		n += buildGroup(group, compound)
	end
	for _, line in Layout.LINES do
		n += buildLine(line, poles, wires, rng)
	end
	folder:SetAttribute("Count", n)
	folder:SetAttribute("Seconds", math.floor((os.clock() - started) * 100) / 100)
	folder.Parent = parent
	return true
end

return ConflictDressing
