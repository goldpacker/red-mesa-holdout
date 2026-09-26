--!strict
-- Visible landscape surfaces for effects (VFX-3). The landscape meshes
-- (server/Landscape: mesa, canyon walls, buttes, cliff kit) are visual only
-- and CanQuery = false, so every ray, gameplay or effect, hits the terrain
-- underneath: measured in Studio, 30-125 studs *behind* the visible wall
-- face along a turret shot. Bullet impacts and rocket blasts put there are
-- hidden inside the rock.
--
-- `hit(from, to)` finds the first landscape surface on the segment for
-- effects only: it picks the meshes whose boxes the segment crosses, makes
-- just those queryable for one synchronous raycast and restores them before
-- returning (nothing else runs in between, so gameplay rays and aiming never
-- see the change). The walls use Box collision, so the hit lies on or in
-- front of the rock you see, on the line of sight from the gun.

local Workspace = game:GetService("Workspace")

local Surface = {}

local parts: { BasePart } = {}
local watched: Instance? = nil

local params = RaycastParams.new()
params.FilterType = Enum.RaycastFilterType.Include

local function track(folder: Instance)
	watched = folder
	parts = {}
	local function add(d: Instance)
		if d:IsA("BasePart") and d.Transparency < 1 then
			table.insert(parts, d)
		end
	end
	for _, d in folder:GetDescendants() do
		add(d)
	end
	folder.DescendantAdded:Connect(add)
end

local function refresh()
	if watched and watched.Parent then
		return
	end
	local battlefield = Workspace:FindFirstChild("Battlefield")
	local land = battlefield and battlefield:FindFirstChild("Landscape")
	if land then
		track(land)
	end
end

-- Does the segment o + u * t, t in [0, len], cross `part`'s box?
local function crosses(part: BasePart, o: Vector3, u: Vector3, len: number): boolean
	local cf = part.CFrame
	local lo = cf:PointToObjectSpace(o)
	local ld = cf:VectorToObjectSpace(u)
	local h = part.Size * 0.5
	local tmin, tmax = 0, len
	for _, axis in { "X", "Y", "Z" } do
		local p, d, e = (lo :: any)[axis] :: number, (ld :: any)[axis] :: number, (h :: any)[axis] :: number
		if math.abs(d) < 1e-6 then
			if math.abs(p) > e then
				return false
			end
		else
			local t1, t2 = (-e - p) / d, (e - p) / d
			if t1 > t2 then
				t1, t2 = t2, t1
			end
			tmin, tmax = math.max(tmin, t1), math.min(tmax, t2)
			if tmin > tmax then
				return false
			end
		end
	end
	return true
end

-- The first landscape surface between `from` and `to` (a little past it),
-- or nil. Effects only.
function Surface.hit(from: Vector3, to: Vector3): RaycastResult?
	refresh()
	if #parts == 0 then
		return nil
	end
	local d = to - from
	local len = d.Magnitude
	if len < 1 then
		return nil
	end
	local u = d / len
	local candidates: { Instance } = {}
	for _, part in parts do
		if part.Parent and crosses(part, from, u, len + 2) then
			table.insert(candidates, part)
		end
	end
	if #candidates == 0 then
		return nil
	end
	local was: { boolean } = table.create(#candidates)
	for i, part in candidates do
		was[i] = (part :: BasePart).CanQuery;
		(part :: BasePart).CanQuery = true
	end
	params.FilterDescendantsInstances = candidates
	local result = Workspace:Raycast(from, u * (len + 2), params)
	for i, part in candidates do
		(part :: BasePart).CanQuery = was[i]
	end
	return result
end

return Surface
