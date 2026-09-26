--!strict
-- Landscape meshes over the gameplay terrain (FACELIFT_PLAN §4 Phase 1a):
-- the mesa and its ridge, the rear and flank canyon walls, the far wall and
-- the four buttes, built in Blender from the terrain TerrainBuilder makes
-- (tools/env/landscape/) and synced from assets/roblox/Landscape_*.rbxmx.
--
-- Visual only. The terrain stays the collision and height surface: every
-- mesh encloses it (0.35+ studs clear, ~1 stud on the mesa), so ground
-- snapping, projectiles and bullets still hit the terrain just under the
-- visible rock. Meshes don't collide and aren't queryable; `Material` says
-- what they look like (Sandstone) for anything that inspects them.
--
-- Mesa chunks get a precise collision shape at runtime, so the QA
-- line-of-sight check, which makes visible meshes queryable for its rays,
-- tests the rock and not a bounding box (Rojo-made MeshParts only have box
-- collision; a single convex hull would bridge the gun pit). Missing assets
-- leave the plain terrain.

local AssetService = game:GetService("AssetService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Landscape = {}

Landscape.PIECES = { "Mesa", "RearWall", "FlankLeft", "FlankRight", "FarWall", "Butte1", "Butte2", "Butte3", "Butte4" }

-- Pieces whose chunks sit near the turret's sight lines.
local COLLISION_PIECES = { Mesa = true }

local function source(name: string): Instance?
	local assets = ReplicatedStorage:FindFirstChild("Assets")
	return assets and assets:FindFirstChild("Landscape_" .. name)
end

local function prepare(part: BasePart)
	part.Anchored = true
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
	part.CastShadow = true
end

-- Replaces a chunk's box collision with a precise convex decomposition
-- (~0.8 s per chunk, off the main build).
local function applyCollision(part: MeshPart)
	local ok, err = pcall(function()
		local shaped = AssetService:CreateMeshPartAsync(Content.fromUri(part.MeshId), {
			CollisionFidelity = Enum.CollisionFidelity.PreciseConvexDecomposition,
			RenderFidelity = Enum.RenderFidelity.Precise,
		})
		part:ApplyMesh(shaped)
		shaped:Destroy()
	end)
	if not ok then
		warn(string.format("[RedMesa] landscape collision for %s unavailable: %s", part.Name, tostring(err)))
	end
end

-- Cliff kit (Blender rock kit: tools/assets/models/rock_kit.py) as fallen
-- blocks where the walls meet the floor. Each entry: kit piece, position
-- (base centre on the live floor, y 2), yaw in degrees (the piece's front
-- faces -Z at 0), scale, sink below the floor.
local KIT = {
	-- rear wall base (face at z ~146), fronts toward the basin (-Z)
	{ "Cliff_Wall_A", Vector3.new(-560, 2, 128), 4, 1.1, 2.0 },
	{ "Cliff_Wall_B", Vector3.new(-330, 2, 131), -6, 0.9, 1.5 },
	{ "Cliff_Corner", Vector3.new(260, 2, 128), 12, 1.0, 2.5 },
	{ "Cliff_Wall_A", Vector3.new(520, 2, 129), -3, 0.95, 2.0 },
	-- left flank shelf (face at x ~ -733), fronts toward +X
	{ "Cliff_Wall_B", Vector3.new(-712, 2, -640), -86, 1.0, 1.8 },
	{ "Cliff_Butte", Vector3.new(-705, 2, -330), -95, 0.9, 2.0 },
	{ "Cliff_Wall_A", Vector3.new(-712, 2, -60), -92, 1.05, 2.2 },
	-- right flank shelf (face at x ~ 733), fronts toward -X
	{ "Cliff_Corner", Vector3.new(708, 2, -560), 84, 1.0, 2.2 },
	{ "Cliff_Wall_B", Vector3.new(712, 2, -250), 92, 1.1, 1.8 },
	{ "Cliff_Butte", Vector3.new(705, 2, 40), 95, 0.85, 2.0 },
	-- flank main faces beyond the shelf (face at x ~ +-792)
	{ "Cliff_Wall_A", Vector3.new(-772, 2, -1000), -90, 1.2, 2.5 },
	{ "Cliff_Wall_B", Vector3.new(772, 2, -900), 88, 1.2, 2.5 },
	-- far wall base (face at z ~ -1333), fronts toward +Z
	{ "Cliff_Wall_B", Vector3.new(-780, 2, -1312), 178, 1.2, 2.5 },
	{ "Cliff_Corner", Vector3.new(-200, 2, -1310), 170, 1.1, 2.5 },
	{ "Cliff_Wall_A", Vector3.new(450, 2, -1313), 182, 1.25, 2.5 },
	{ "Cliff_Butte", Vector3.new(880, 2, -1300), 188, 1.0, 2.5 },
}

local function buildKit(folder: Instance)
	local assets = ReplicatedStorage:FindFirstChild("Assets")
	if not assets then
		return
	end
	local kit = Instance.new("Folder")
	kit.Name = "CliffKit"
	for i, e in KIT do
		local src = assets:FindFirstChild(e[1])
		if src and src:IsA("Model") then
			local rock = src:Clone()
			rock.Name = string.format("%s_%02d", e[1], i)
			rock:ScaleTo(e[4])
			rock:PivotTo(CFrame.new((e[2] :: Vector3) - Vector3.new(0, e[5], 0)) * CFrame.Angles(0, math.rad(e[3]), 0))
			for _, d in rock:GetDescendants() do
				if d:IsA("BasePart") then
					prepare(d)
				end
			end
			rock.Parent = kit
		end
	end
	kit.Parent = folder
end

function Landscape.build(parent: Instance): Folder
	local folder = Instance.new("Folder")
	folder.Name = "Landscape"
	local precise: { MeshPart } = {}
	local placed = 0
	for _, name in Landscape.PIECES do
		local src = source(name)
		if src then
			local ok, copy = pcall(function()
				return src:Clone()
			end)
			if ok and copy then
				for _, d in copy:GetDescendants() do
					if d:IsA("BasePart") then
						prepare(d)
						if COLLISION_PIECES[name] and d:IsA("MeshPart") then
							table.insert(precise, d)
						end
					end
				end
				copy.Parent = folder
				placed += 1
			end
		end
	end
	if placed > 0 then
		buildKit(folder)
	end
	folder.Parent = parent
	if #precise > 0 then
		task.spawn(function()
			for _, part in precise do
				applyCollision(part)
			end
		end)
	end
	if placed > 0 and placed < #Landscape.PIECES then
		print(string.format("[RedMesa] landscape: %d of %d pieces available; terrain shows for the rest", placed, #Landscape.PIECES))
	end
	return folder
end

return Landscape
