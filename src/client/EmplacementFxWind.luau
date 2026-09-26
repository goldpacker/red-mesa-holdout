--!strict
-- Wind on the emplacement (HS-2, driven by EmplacementFx): the radio whip
-- (Static/Antenna: base `Whip` + links Whip2..Whip4) bends as a damped
-- chain under a gusting wind, and the camo net (Static/CamoNet/Net)
-- ripples: its mesh is copied into an EditableMesh, its free-hanging
-- vertices are displaced by travelling waves and the normals of the moved
-- faces follow, so the shading ripples too. Client-only and visual.
--
-- Both pause (hold a fixed pose) while a beauty shot is staged
-- (Workspace attribute BeautyShot, tools/qa/BEAUTY.md §6). If an
-- EditableMesh can't be made (API disabled or over its memory budget) the
-- net simply stays still.

local AssetService = game:GetService("AssetService")
local Workspace = game:GetService("Workspace")

local Wind = {}

-- Wind: a steady breeze from the basin (world -Z toward +Z, a little from
-- the left) with slow gusts.
local WIND_DIR = Vector3.new(0.35, 0, 1).Unit
local WIND_BASE = 0.55
local GUST = 0.45

-- Antenna chain: joint bend weights (base spring flexes most), spring and
-- damping of the tip deflection (rad), natural frequency ~1.3 Hz.
local JOINT_WEIGHTS = { 0.42, 0.33, 0.25 }
local LEAN = math.rad(5) -- mean lean at WIND_BASE
local SWAY_K = 68
local SWAY_C = 2.2
local SWAY_NOISE = math.rad(7)

-- Net ripple.
local NET_AMP = 0.1 -- studs at full freedom and base wind
local NET_RATE = 1 / 15 -- seconds between mesh updates (the waves are slow)
local NET_FLOOR_CLEAR = 0.45 -- studs above the bunker floor before a vertex may move
local NET_PIN_CLEAR = 1.4 -- studs from a picket top before a vertex may move
local NET_MAX_DIST = 260 -- camera distance beyond which the ripple stops
local NET_RADIUS = 6.5 -- bounding sphere of the net (10.3 x 3.4 x 10.5 studs)
-- Picket tops holding the net, relative to the emplacement pivot
-- (emplacement.py: polar(POLE_R, NET_POLES, POLE_TOP) in Roblox axes).
local NET_PINS = { Vector3.new(8.51, -2.65, 2.93), Vector3.new(5.42, -2.65, 7.19) }

type Link = { part: BasePart, rest: CFrame, joint: Vector3 }

local links: { Link } = {}
local tip = Vector2.zero -- tip deflection angles (about world X and Z)
local tipVel = Vector2.zero
local clock = 0
local wasPaused = false

local net: MeshPart? = nil
local netMesh: EditableMesh? = nil
local netTimer = 0
local netCenter = Vector3.zero
local netUp = Vector3.yAxis -- world up and wind direction in net mesh space
local netAlong = Vector3.zAxis
-- Dense per-update state. Vertex slots: ids and current positions.
local netIds: { number } = {}
local netPos: { Vector3 } = {}
-- Moving vertices: slot, rest position, freedom weight, wave phase.
local mvSlot: { number } = {}
local mvRest: { Vector3 } = {}
local mvWeight: { number } = {}
local mvPhase: { number } = {}
-- Faces touching a moving vertex: vertex slots, normal slots, rest
-- (area-weighted) face normal.
local fA: { number }, fB: { number }, fC: { number } = {}, {}, {}
local fNA: { number }, fNB: { number }, fNC: { number } = {}, {}, {}
local fRest: { Vector3 } = {}
-- Normals those faces use: id, rest normal x rest area of all its faces.
local nIds: { number } = {}
local nRest: { Vector3 } = {}
local nSum: { Vector3 } = {}

local function paused(): boolean
	return Workspace:GetAttribute("BeautyShot") ~= nil
end

-- 0..1.4 wind strength at time t (base + two octaves of gusts).
local function windStrength(t: number): number
	local g = math.noise(t * 0.23, 3.1) + 0.5 * math.noise(t * 0.61, 7.7)
	return math.max(0.1, WIND_BASE + GUST * g)
end

-- ---------------------------------------------------------------- antenna
local function attachAntenna(static: Instance)
	table.clear(links)
	tip, tipVel = Vector2.zero, Vector2.zero
	local antenna = static:FindFirstChild("Antenna")
	if not antenna then
		return
	end
	for k = 2, 4 do
		local part = antenna:FindFirstChild("Whip" .. k)
		if not part or not part:IsA("BasePart") then
			table.clear(links)
			return
		end
		local cf = part.CFrame
		table.insert(links, { part = part, rest = cf, joint = cf:PointToWorldSpace(Vector3.new(0, -part.Size.Y / 2, 0)) })
	end
end

local function stepAntenna(dt: number)
	if #links == 0 then
		return
	end
	local strength = windStrength(clock)
	-- Target deflection: lean with the wind plus a flutter; the spring
	-- makes the tip overshoot and swing back.
	local flutter = Vector2.new(math.noise(clock * 2.6, 11.3), math.noise(clock * 2.1, 17.9)) * SWAY_NOISE * strength
	local lean = Vector2.new(WIND_DIR.Z, -WIND_DIR.X) * LEAN * strength / WIND_BASE
	local target = lean + flutter
	local accel = (target - tip) * SWAY_K - tipVel * SWAY_C
	tipVel += accel * dt
	tip += tipVel * dt
	-- Chain: each joint bends by its share of the tip angle, about the rest
	-- joint, on top of the links below it.
	local acc = CFrame.identity
	local parts, frames = {}, {}
	for k, link in links do
		local w = JOINT_WEIGHTS[k]
		local bend = CFrame.new(link.joint) * CFrame.Angles(tip.X * w, 0, tip.Y * w) * CFrame.new(-link.joint)
		acc = acc * bend
		table.insert(parts, link.part)
		table.insert(frames, acc * link.rest)
	end
	Workspace:BulkMoveTo(parts, frames, Enum.BulkMoveMode.FireCFrameChanged)
end

-- -------------------------------------------------------------------- net
local function makeNetMesh(part: MeshPart): EditableMesh?
	local ok, mesh = pcall(function()
		return AssetService:CreateEditableMeshAsync(Content.fromUri(part.MeshId), { FixedSize = true })
	end)
	if not ok or not mesh then
		return nil
	end
	local ok2, live = pcall(function()
		return AssetService:CreateMeshPartAsync(Content.fromObject(mesh))
	end)
	if not ok2 or not live then
		mesh:Destroy()
		return nil
	end
	part:ApplyMesh(live)
	live:Destroy()
	return mesh
end

local function clearNet()
	netMesh = nil
	for _, list in { netIds, netPos, mvSlot, mvRest, mvWeight, mvPhase, fA, fB, fC, fNA, fNB, fNC, fRest, nIds, nRest, nSum } do
		table.clear(list :: { any })
	end
end

-- Faces that touch a moving vertex, and for each normal they use the rest
-- normal scaled by the rest area of all faces sharing it, so a moved face
-- tilts a vertex normal in proportion to its share.
local function collectFaces(mesh: EditableMesh, slotOf: { [number]: number }, moving: { [number]: boolean })
	local area: { [number]: number } = {}
	local nSlot: { [number]: number } = {}
	local function normalSlot(id: number): number
		local s = nSlot[id]
		if not s then
			table.insert(nIds, id)
			s = #nIds
			nSlot[id] = s
		end
		return s
	end
	for _, f in mesh:GetFaces() do
		local vs = mesh:GetFaceVertices(f)
		local ns = mesh:GetFaceNormals(f)
		if #vs == 3 and #ns == 3 then
			local a, b, c = slotOf[vs[1]], slotOf[vs[2]], slotOf[vs[3]]
			local rest = (netPos[b] - netPos[a]):Cross(netPos[c] - netPos[a])
			for _, n in ns do
				area[n] = (area[n] or 0) + rest.Magnitude
			end
			if moving[a] or moving[b] or moving[c] then
				table.insert(fA, a)
				table.insert(fB, b)
				table.insert(fC, c)
				table.insert(fNA, normalSlot(ns[1]))
				table.insert(fNB, normalSlot(ns[2]))
				table.insert(fNC, normalSlot(ns[3]))
				table.insert(fRest, rest)
			end
		end
	end
	for j, id in nIds do
		nRest[j] = mesh:GetNormal(id) * (area[id] or 0)
		nSum[j] = nRest[j]
	end
end

local function attachNet(static: Instance)
	clearNet()
	local model = static:FindFirstChild("CamoNet")
	local part = model and model:FindFirstChild("Net")
	if not part or not part:IsA("MeshPart") or part.MeshId == "" then
		return
	end
	net = part
	task.spawn(function()
		local mesh = makeNetMesh(part)
		if not mesh or net ~= part then
			return
		end
		-- Mesh space -> world: the mesh is centred on the part, scaled to its Size.
		local slotOf: { [number]: number } = {}
		local lo, hi = Vector3.one * math.huge, -Vector3.one * math.huge
		for i, id in mesh:GetVertices() do
			local p = mesh:GetPosition(id)
			netIds[i], netPos[i], slotOf[id] = id, p, i
			lo, hi = lo:Min(p), hi:Max(p)
		end
		local extent = hi - lo
		local scale = Vector3.new(
			if extent.X > 1e-4 then part.Size.X / extent.X else 1,
			if extent.Y > 1e-4 then part.Size.Y / extent.Y else 1,
			if extent.Z > 1e-4 then part.Size.Z / extent.Z else 1
		)
		local mid = (lo + hi) / 2
		local origin = (static.Parent :: Model):GetPivot()
		local floorY = origin.Y - 6
		local pins = {}
		for _, pin in NET_PINS do
			table.insert(pins, origin:PointToWorldSpace(pin))
		end
		netCenter = part.Position
		local moving: { [number]: boolean } = {}
		local across = Vector3.new(-WIND_DIR.Z, 0, WIND_DIR.X)
		for i, rest in netPos do
			local world = part.CFrame:PointToWorldSpace((rest - mid) * scale)
			local lift = math.clamp((world.Y - floorY - NET_FLOOR_CLEAR) / 0.8, 0, 1)
			local pinDist = math.huge
			for _, pin in pins do
				pinDist = math.min(pinDist, (world - pin).Magnitude)
			end
			local free = math.clamp((pinDist - 0.3) / NET_PIN_CLEAR, 0, 1)
			local weight = lift * free * free
			if weight > 0.01 then
				moving[i] = true
				table.insert(mvSlot, i)
				table.insert(mvRest, rest)
				table.insert(mvWeight, weight)
				table.insert(mvPhase, world:Dot(WIND_DIR) * 1.9 + world:Dot(across) * 0.7)
			end
		end
		-- Displacements are applied in mesh space: world up / wind there.
		netUp = part.CFrame:VectorToObjectSpace(Vector3.yAxis) / scale
		netAlong = part.CFrame:VectorToObjectSpace(WIND_DIR) / scale
		if not pcall(collectFaces, mesh, slotOf, moving) then
			for _, list in { fA, fB, fC, fNA, fNB, fNC, fRest, nIds, nRest, nSum } do
				table.clear(list :: { any }) -- no normals API: positions only
			end
		end
		netMesh = mesh
	end)
end

-- Tilts every affected normal by the change of the moved faces' normals.
local function updateNormals(mesh: EditableMesh)
	for j = 1, #nIds do
		nSum[j] = nRest[j]
	end
	for f = 1, #fA do
		local a = netPos[fA[f]]
		local delta = (netPos[fB[f]] - a):Cross(netPos[fC[f]] - a) - fRest[f]
		nSum[fNA[f]] += delta
		nSum[fNB[f]] += delta
		nSum[fNC[f]] += delta
	end
	for j = 1, #nIds do
		local s = nSum[j]
		if s.Magnitude > 1e-9 then
			mesh:SetNormal(nIds[j], s.Unit)
		end
	end
end

local normalTick = 0

-- Moves the free vertices; normals follow on every other call (`force`
-- updates them now), which halves the cost and can't be seen.
local function placeNet(mesh: EditableMesh, t: number, amp: number, force: boolean?)
	for k = 1, #mvSlot do
		local phase = mvPhase[k]
		local wave = math.sin(phase - t * 3.1) * 0.65 + math.sin(phase * 2.3 - t * 5.3 + 1.7) * 0.35
		local d = mvWeight[k] * amp * wave
		local p = mvRest[k] + netUp * d + netAlong * (d * 0.35)
		local slot = mvSlot[k]
		netPos[slot] = p
		mesh:SetPosition(netIds[slot], p)
	end
	normalTick += 1
	if #nIds > 0 and (force or normalTick % 2 == 0) and not pcall(updateNormals, mesh) then
		table.clear(nIds) -- normals API failed: positions only from now on
	end
end

-- True when the net's bounding sphere may be inside the camera's view.
local function netInView(camera: Camera, offset: Vector3, dist: number): boolean
	if dist < NET_RADIUS then
		return true
	end
	local halfV = math.rad(camera.FieldOfView) / 2
	local viewport = camera.ViewportSize
	local aspect = viewport.X / math.max(1, viewport.Y)
	local halfDiag = math.atan(math.tan(halfV) * math.sqrt(1 + aspect * aspect))
	local angle = math.acos(math.clamp(offset.Unit:Dot(camera.CFrame.LookVector), -1, 1))
	return angle < halfDiag + math.asin(NET_RADIUS / dist)
end

local function stepNet(dt: number, camera: Camera)
	local mesh = netMesh
	if not mesh then
		return
	end
	netTimer -= dt
	if netTimer > 0 then
		return
	end
	local offset = netCenter - camera.CFrame.Position
	local dist = offset.Magnitude
	-- Fewer updates the smaller the net is on screen (the title camera
	-- sees it from ~170 studs).
	netTimer = if dist < 40 then NET_RATE elseif dist < 110 then NET_RATE * 2 else NET_RATE * 4
	if dist > NET_MAX_DIST or not netInView(camera, offset, dist) then
		return -- too far, or outside the view
	end
	placeNet(mesh, clock, NET_AMP * windStrength(clock) / WIND_BASE)
end

-- ------------------------------------------------------------------- API
function Wind.attach(emplacement: Instance)
	local static = emplacement:FindFirstChild("Static")
	if not static then
		return
	end
	attachAntenna(static)
	attachNet(static)
end

-- Rest pose (beauty shots are captured with everything at rest).
local function rest()
	tip, tipVel = Vector2.zero, Vector2.zero
	for _, link in links do
		link.part.CFrame = link.rest
	end
	local mesh = netMesh
	if mesh then
		placeNet(mesh, 0, 0, true)
	end
end

-- `hidden`: the emplacement is hidden (gunsight view), skip the work.
function Wind.step(dt: number, hidden: boolean)
	if paused() then
		if not wasPaused then
			rest()
		end
		wasPaused = true
		return
	end
	wasPaused = false
	clock += dt
	if hidden then
		return
	end
	stepAntenna(dt)
	stepNet(dt, Workspace.CurrentCamera)
end

return Wind
