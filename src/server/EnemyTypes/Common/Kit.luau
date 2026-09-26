--!strict
-- Shared helpers for enemy behaviour modules: terrain queries, primitive
-- fallback-model builders, lane lookup, outpost targeting and wrecks.
-- Lives in a Folder under EnemyTypes so Enemies.luau does not try to
-- register it as an enemy kind.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Workspace = game:GetService("Workspace")

local Aim = require(ReplicatedStorage.Shared.Aim)
local Config = require(ReplicatedStorage.Shared.Config)

local Kit = {}

-- Enemy force palette: dark gunmetal/charcoal with red markings (GAME_SPEC §13).
Kit.GUNMETAL = Color3.fromRGB(62, 66, 71)
Kit.CHARCOAL = Color3.fromRGB(42, 44, 48)
Kit.DARK = Color3.fromRGB(26, 27, 30)
Kit.RUBBER = Color3.fromRGB(24, 23, 22)
Kit.RED = Color3.fromRGB(186, 28, 24)
Kit.GLASS = Color3.fromRGB(28, 40, 52)
Kit.LAMP = Color3.fromRGB(255, 226, 170)

local groundParams = RaycastParams.new()
groundParams.FilterType = Enum.RaycastFilterType.Include
groundParams.FilterDescendantsInstances = { Workspace.Terrain }

function Kit.groundY(x: number, z: number): number
	local result = Workspace:Raycast(Vector3.new(x, 400, z), Vector3.new(0, -520, 0), groundParams)
	return if result then result.Position.Y else 0
end

-- First terrain hit along a segment (for crashing aircraft).
function Kit.terrainHit(from: Vector3, to: Vector3): Vector3?
	local result = Workspace:Raycast(from, to - from, groundParams)
	return if result then result.Position else nil
end

function Kit.flatDistance(a: Vector3, b: Vector3): number
	return Vector2.new(a.X - b.X, a.Z - b.Z).Magnitude
end

function Kit.outpostDistance(p: Vector3): number
	return Kit.flatDistance(p, Config.TURRET_PIVOT)
end

function Kit.inArc(p: Vector3): boolean
	return Aim.isInArc(p)
end

-- Where an enemy shot lands: the rock lip just below and in front of the
-- gun (on the shooter's side), so impacts read without blinding the camera.
function Kit.impactPoint(from: Vector3, rng: Random?): Vector3
	local pivot = Config.TURRET_PIVOT
	local flat = Vector3.new(from.X - pivot.X, 0, from.Z - pivot.Z)
	local dir = if flat.Magnitude > 0.1 then flat.Unit else Vector3.new(0, 0, -1)
	local r = rng or Random.new()
	return pivot + dir * r:NextNumber(10, 15) + Vector3.new(r:NextNumber(-3, 3), -9, r:NextNumber(-3, 3))
end

-- Ground lane waypoints, falling back to `default` for unknown names.
function Kit.groundLane(name: string, default: string): { Vector2 }
	return Config.Lanes[name] or Config.Lanes[default]
end

function Kit.pick<T>(list: { T }, rng: Random): T
	return list[rng:NextInteger(1, #list)]
end

---------------------------------------------------------------------------
-- Primitive builders. Parts are created anchored in model space (forward
-- -Z, ground at y = 0); Rig.prepare welds them to Root afterwards.
---------------------------------------------------------------------------

local function base(p: BasePart, parent: Instance, name: string, cf: CFrame, color: Color3, material: Enum.Material?)
	p.Name = name
	p.CFrame = cf
	p.Color = color
	p.Material = material or Enum.Material.Metal
	p.Anchored = true
	p.CanCollide = false
	p.CanTouch = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Parent = parent
end

function Kit.box(parent: Instance, name: string, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material?): Part
	local p = Instance.new("Part")
	p.Size = size
	base(p, parent, name, cf, color, material)
	return p
end

-- WedgePart: slope rises from the front (-Z, bottom) to the back (+Z, top).
function Kit.wedge(parent: Instance, name: string, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material?): WedgePart
	local p = Instance.new("WedgePart")
	p.Size = size
	base(p, parent, name, cf, color, material)
	return p
end

-- Cylinder whose axis runs along the X axis of `cf`.
function Kit.cyl(parent: Instance, name: string, length: number, diameter: number, cf: CFrame, color: Color3, material: Enum.Material?): Part
	local p = Instance.new("Part")
	p.Shape = Enum.PartType.Cylinder
	p.Size = Vector3.new(length, diameter, diameter)
	base(p, parent, name, cf, color, material)
	return p
end

-- Cylinder along Z (barrels, pods): axis points forward.
function Kit.barrel(parent: Instance, name: string, length: number, diameter: number, center: Vector3, color: Color3): Part
	return Kit.cyl(parent, name, length, diameter, CFrame.new(center) * CFrame.Angles(0, math.rad(90), 0), color)
end

-- Upright cylinder (hatches, hubs, stacks).
function Kit.post(parent: Instance, name: string, height: number, diameter: number, center: Vector3, color: Color3, material: Enum.Material?): Part
	return Kit.cyl(parent, name, height, diameter, CFrame.new(center) * CFrame.Angles(0, 0, math.rad(90)), color, material)
end

function Kit.ball(parent: Instance, name: string, diameter: number, center: Vector3, color: Color3, material: Enum.Material?): Part
	local p = Instance.new("Part")
	p.Shape = Enum.PartType.Ball
	p.Size = Vector3.one * diameter
	base(p, parent, name, CFrame.new(center), color, material)
	return p
end

-- Non-hittable glowing detail (lamps, lenses).
function Kit.lamp(parent: Instance, name: string, size: Vector3, cf: CFrame, color: Color3): Part
	local p = Kit.box(parent, name, size, cf, color, Enum.Material.Neon)
	p.CanQuery = false
	p.CastShadow = false
	return p
end

-- Decorative (non-hittable) detail.
function Kit.decor(p: BasePart): BasePart
	p.CanQuery = false
	return p
end

-- The enemy emblem: a red downward chevron, painted flat on a surface.
-- `cf` is centred on the surface with its -Z (LookVector) pointing out.
function Kit.chevron(parent: Instance, cf: CFrame, size: number)
	local arm = size * 0.62
	for _, side in { -1, 1 } do
		local bar = Kit.box(
			parent,
			"Emblem",
			Vector3.new(arm, size * 0.16, 0.08),
			cf * CFrame.new(side * size * 0.22, 0, -0.04) * CFrame.Angles(0, 0, math.rad(side * 38)),
			Kit.RED,
			Enum.Material.SmoothPlastic
		)
		Kit.decor(bar)
	end
	local bar = Kit.box(parent, "Emblem", Vector3.new(size * 0.9, size * 0.07, 0.08), cf * CFrame.new(0, size * 0.42, -0.04), Kit.RED, Enum.Material.SmoothPlastic)
	Kit.decor(bar)
end

function Kit.attachment(part: BasePart, name: string, worldPos: Vector3, lookDir: Vector3?): Attachment
	local a = Instance.new("Attachment")
	a.Name = name
	local cf = if lookDir then CFrame.lookAt(worldPos, worldPos + lookDir) else CFrame.new(worldPos)
	a.CFrame = part.CFrame:ToObjectSpace(cf)
	a.Parent = part
	return a
end

-- A forward-facing spotlight on a lamp part (headlights, searchlights).
function Kit.spotlight(part: BasePart, range: number, angle: number, brightness: number, color: Color3?): SpotLight
	local s = Instance.new("SpotLight")
	s.Face = Enum.NormalId.Front
	s.Range = range
	s.Angle = angle
	s.Brightness = brightness
	s.Color = color or Kit.LAMP
	s.Shadows = false
	s.Parent = part
	return s
end

function Kit.glow(part: BasePart, range: number, brightness: number, color: Color3): PointLight
	local l = Instance.new("PointLight")
	l.Range = range
	l.Brightness = brightness
	l.Color = color
	l.Shadows = false
	l.Parent = part
	return l
end

---------------------------------------------------------------------------
-- Assets
---------------------------------------------------------------------------

-- Clones ReplicatedStorage.Assets.<name> if it exists and has every
-- descendant listed in `required`; nil otherwise (callers fall back).
function Kit.loadAsset(name: string, required: { string }): Model?
	local ok, AssetLibrary = pcall(require, ReplicatedStorage.Shared.AssetLibrary)
	if not ok then
		return nil
	end
	local copy = (AssetLibrary :: any).clone(name)
	if not copy or not copy:IsA("Model") then
		if copy then
			copy:Destroy()
		end
		return nil
	end
	for _, childName in required do
		if not copy:FindFirstChild(childName, true) then
			warn(string.format("[RedMesa] asset %s lacks %s; using fallback", name, childName))
			copy:Destroy()
			return nil
		end
	end
	return copy
end

---------------------------------------------------------------------------
-- Terrain-following placement
---------------------------------------------------------------------------

-- CFrame for a ground vehicle at `pos2` heading along `heading2`, pitched
-- and rolled to the terrain under its footprint.
function Kit.groundFrame(pos2: Vector2, heading2: Vector2, halfLength: number, halfWidth: number, lift: number): CFrame
	local f = if heading2.Magnitude > 1e-3 then heading2.Unit else Vector2.new(0, -1)
	local r = Vector2.new(-f.Y, f.X)
	local front = pos2 + f * halfLength
	local back = pos2 - f * halfLength
	local left = pos2 + r * halfWidth
	local right = pos2 - r * halfWidth
	local yF, yB = Kit.groundY(front.X, front.Y), Kit.groundY(back.X, back.Y)
	local yL, yR = Kit.groundY(left.X, left.Y), Kit.groundY(right.X, right.Y)
	local centreY = math.max((yF + yB) / 2, (yL + yR) / 2, Kit.groundY(pos2.X, pos2.Y) - 0.5)
	local forward = Vector3.new(front.X - back.X, yF - yB, front.Y - back.Y).Unit
	local side = Vector3.new(left.X - right.X, yL - yR, left.Y - right.Y).Unit
	local up = side:Cross(forward)
	if up.Y < 0 then
		up = -up
	end
	local position = Vector3.new(pos2.X, centreY + lift, pos2.Y)
	return CFrame.lookAt(position, position + forward, up)
end

-- Rotates heading `current` toward `desired` by at most `maxAngle` radians.
function Kit.turnToward(current: Vector2, desired: Vector2, maxAngle: number): Vector2
	if desired.Magnitude < 1e-4 then
		return current
	end
	local a = math.atan2(current.Y, current.X)
	local b = math.atan2(desired.Y, desired.X)
	local delta = (b - a + math.pi) % (2 * math.pi) - math.pi
	delta = math.clamp(delta, -maxAngle, maxAngle)
	local n = a + delta
	return Vector2.new(math.cos(n), math.sin(n))
end

---------------------------------------------------------------------------
-- Turrets (server-side aim maths; the client animates the same yaw)
---------------------------------------------------------------------------

-- Yaw (radians about the pivot's Y) that points a turret's -Z at `target`.
function Kit.aimYaw(frame: CFrame, pivotLocal: CFrame, target: Vector3): number
	local rel = (frame * pivotLocal):PointToObjectSpace(target)
	return math.atan2(-rel.X, -rel.Z)
end

-- World muzzle position of a turret yawed by `yaw`.
function Kit.muzzleWorld(frame: CFrame, pivotLocal: CFrame, muzzleLocal: CFrame, yaw: number): Vector3
	local pivotWorld = frame * pivotLocal * CFrame.Angles(0, yaw, 0)
	return (pivotWorld * pivotLocal:ToObjectSpace(muzzleLocal)).Position
end

-- Local (model-pivot space) frames of a mover's pivot and of an attachment
-- inside it, measured right after the model is built.
function Kit.moverFrames(model: Model, moverName: string, attachmentName: string): (CFrame, CFrame)
	local ground = model:GetPivot()
	local mover = model:FindFirstChild(moverName, true)
	local pivot = if mover and mover:IsA("Model") then mover:GetPivot() elseif mover and mover:IsA("BasePart") then mover.CFrame else ground
	local att = (mover and mover:FindFirstChild(attachmentName, true)) or model:FindFirstChild(attachmentName, true)
	local muzzle = if att and att:IsA("Attachment") then att.WorldCFrame else pivot * CFrame.new(0, 0, -6)
	return ground:ToObjectSpace(pivot), ground:ToObjectSpace(muzzle)
end

---------------------------------------------------------------------------
-- Destruction
---------------------------------------------------------------------------

local function wrecksFolder(): Instance
	return Workspace:FindFirstChild("Wrecks") or Workspace
end

-- Burns the paint off a model: darkens every part, kills its lights and
-- makes it ignore weapon raycasts.
local CHARRED = Color3.fromRGB(22, 20, 19)

function Kit.char(model: Instance)
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.CanQuery = false
			local textured = d:FindFirstChildWhichIsA("SurfaceAppearance")
			if textured then
				-- An imported mesh's Color is untextured white: burn it outright.
				textured:Destroy()
				d.Color = CHARRED:Lerp(Color3.fromRGB(60, 52, 46), math.random() * 0.4)
				d.Material = Enum.Material.Slate
			else
				if d.Material == Enum.Material.Neon or d.Material == Enum.Material.Glass then
					d.Material = Enum.Material.Slate
				end
				d.Color = d.Color:Lerp(CHARRED, 0.6)
			end
			if d.Transparency > 0.5 and d.Name ~= "Root" then
				d.Transparency = 1
			end
		elseif d:IsA("Light") then
			d:Destroy()
		end
	end
end

-- Stops a model from catching weapon raycasts (dead but still moving).
function Kit.noQuery(model: Instance)
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.CanQuery = false
		end
	end
end

-- Moves a dead vehicle into Workspace.Wrecks (cleared at intermission).
-- `state` drives client effects: "Dead" = explode + burn now, "Crashing" =
-- smoke trail until the state becomes "Wreck", "Dying" = boss sequence.
function Kit.toWrecks(model: Model, state: string, fxScale: number)
	model:SetAttribute("FxScale", fxScale)
	model:SetAttribute("State", state)
	model.Parent = wrecksFolder()
end

-- Splits off a named sub-model (e.g. a turret) as its own anchored wreck
-- piece so it can be flung and left burning.
function Kit.detach(model: Model, name: string): Model?
	local sub = model:FindFirstChild(name, true)
	if not sub then
		return nil
	end
	local piece: Model
	if sub:IsA("Model") then
		piece = sub
		-- Without a PrimaryPart a Model's pivot stays where it was authored
		-- while its welded parts travel; anchor the pivot to a real part.
		if not piece.PrimaryPart then
			local best, volume = nil, -1
			for _, d in piece:GetDescendants() do
				if d:IsA("BasePart") and d.Size.X * d.Size.Y * d.Size.Z > volume then
					best, volume = d, d.Size.X * d.Size.Y * d.Size.Z
				end
			end
			piece.PrimaryPart = best
		end
	elseif sub:IsA("BasePart") then
		piece = Instance.new("Model")
		piece.Name = name
		sub.Parent = piece
		piece.PrimaryPart = sub
	else
		return nil
	end
	for _, d in piece:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = true
		elseif d:IsA("JointInstance") or d:IsA("WeldConstraint") then
			d:Destroy()
		end
	end
	-- Joints to the piece may live on the hull (Motor6D in Root).
	for _, d in model:GetDescendants() do
		if (d:IsA("JointInstance")) and (d.Part1 and d.Part1:IsDescendantOf(piece) or d.Part0 and d.Part0:IsDescendantOf(piece)) then
			d:Destroy()
		elseif d:IsA("WeldConstraint") and (d.Part1 and d.Part1:IsDescendantOf(piece) or d.Part0 and d.Part0:IsDescendantOf(piece)) then
			d:Destroy()
		end
	end
	piece.Parent = wrecksFolder()
	return piece
end

-- Throws a detached piece ballistically (anchored, moved by PivotTo) until
-- it hits terrain, then leaves it lying there. `state` is set on landing.
function Kit.fling(piece: Model, velocity: Vector3, spin: Vector3, state: string)
	local RunService = game:GetService("RunService")
	local cf = piece:GetPivot()
	local v = velocity
	local elapsed = 0
	local conn: RBXScriptConnection
	conn = RunService.Heartbeat:Connect(function(dt)
		if not piece.Parent then
			conn:Disconnect()
			return
		end
		elapsed += dt
		v += Vector3.new(0, -Workspace.Gravity * 0.6 * dt, 0)
		local nextPos = cf.Position + v * dt
		local hit = Kit.terrainHit(cf.Position, nextPos)
		local floor = Kit.groundY(nextPos.X, nextPos.Z)
		if not hit and v.Y < 0 and nextPos.Y < floor then
			hit = Vector3.new(nextPos.X, floor, nextPos.Z)
		end
		if hit or elapsed > 4 then
			local landing = hit or Vector3.new(nextPos.X, math.max(nextPos.Y, floor), nextPos.Z)
			piece:PivotTo(CFrame.new(landing + Vector3.new(0, 1, 0)) * cf.Rotation)
			piece:SetAttribute("State", state)
			conn:Disconnect()
			return
		end
		cf = CFrame.new(nextPos) * cf.Rotation * CFrame.Angles(spin.X * dt, spin.Y * dt, spin.Z * dt)
		piece:PivotTo(cf)
	end)
end

-- Anchors every part in place (so a wreck stops following its root).
function Kit.freeze(model: Instance)
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = true
		end
	end
end

return Kit
