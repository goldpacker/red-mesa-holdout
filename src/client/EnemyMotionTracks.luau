--!strict
-- Running gear for EnemyMotion (LOOK-3): tank treads; planted tracks on the
-- tank and the Siege Crawler.
--
-- Moving tracks. The track meshes (`TrackL`/`TrackR`,
-- docs/ASSET_CONTRACTS.md) are single welded MeshParts on a shared trim
-- sheet, so their own texture can't scroll. Each track gets client-side
-- Textures (projected onto the mesh faces) carrying a tread-link strip that
-- scrolls with the distance the vehicle covers:
--   - the outer side face: the ground run of links along the bottom band
--     slides backward past the hull at road speed;
--   - the front and back faces: the tread rolling over the idler/sprocket.
-- Distance comes from the smoothed velocity, so the links stop with the
-- vehicle.
--
-- Planted tracks. Body motion moves the hull (Root) on its suspension; the
-- tracks are welded to Root, so their welds get the inverse of the body
-- offset (client-only C0) and stay on the ground while the hull pitches,
-- rolls and bobs.
--
-- Everything is undone when the vehicle dies (the wreck is charred).

local Assets = require(script.Parent.EnemyMotionAssets)

local Tracks = {}

-- Studs per tile: one period of TrimEnemy's `track` strip (trim.json), the
-- strip the track meshes are textured with (tools/ui/motion_textures.py).
local PERIOD = 15.644
-- Tread scale per kind (x PERIOD studs per tile). The Siege Crawler keeps
-- its planted tracks but no tread strip: HS-5 built it with two 4.3-stud
-- belts per track box, which one projected strip can't line up with.
local TREAD: { [string]: number } = { Tank = 1 }
local PLANTED: { [string]: boolean } = { Tank = true, SiegeCrawler = true }

type Face = { tex: Texture, axis: string, sign: number }
type Planted = { weld: Weld, c0: CFrame }

export type State = {
	faces: { Face },
	planted: { Planted },
	travel: number,
}

local function addFace(part: BasePart, face: Enum.NormalId, image: string, axis: string, sign: number, tileU: number, tileV: number, faces: { Face })
	local tex = Instance.new("Texture")
	tex.Name = "LookTread"
	tex.Texture = image
	tex.Face = face
	tex.StudsPerTileU = tileU
	tex.StudsPerTileV = tileV
	tex.ZIndex = 2
	tex.Parent = part
	table.insert(faces, { tex = tex, axis = axis, sign = sign })
end

-- The Root->track welds made by EnemyTypes/Common/Rig (parented to the
-- welded part, Part0 = Root).
local function plantedWelds(part: BasePart, root: BasePart, out: { Planted })
	for _, d in part:GetChildren() do
		if d:IsA("Weld") and d.Part0 == root and d.Part1 == part then
			table.insert(out, { weld = d, c0 = d.C0 })
		end
	end
end

function Tracks.new(model: Model, kind: string, root: BasePart): State?
	if not PLANTED[kind] then
		return nil
	end
	local scale = TREAD[kind]
	local side, roll = Assets.TreadSide, Assets.TreadRoll
	local faces: { Face } = {}
	local planted: { Planted } = {}
	local tile = PERIOD * (scale or 1)
	for _, name in { "TrackL", "TrackR" } do
		local part = model:FindFirstChild(name, true)
		if part and part:IsA("BasePart") then
			plantedWelds(part, root, planted)
			if scale and side and roll then
				local outer = if name == "TrackL" then Enum.NormalId.Left else Enum.NormalId.Right
				-- Signs measured in Studio (LOOK-3 report): a larger OffsetStudsU
				-- slides a side texture toward the viewer's left, a larger
				-- OffsetStudsV slides it up. Driving forward, the ground run
				-- slides rearward, the tread rolls down over the front idler
				-- and up over the rear sprocket.
				-- Side: U runs along the hull; the strip spans the face height.
				addFace(part, outer, side, "U", if name == "TrackL" then -1 else 1, tile, part.Size.Y, faces)
				-- Ends: V runs up the face; the links roll over the wheel.
				addFace(part, Enum.NormalId.Front, roll, "V", -1, part.Size.X, tile, faces)
				addFace(part, Enum.NormalId.Back, roll, "V", 1, part.Size.X, tile, faces)
			end
		end
	end
	if #faces == 0 and #planted == 0 then
		return nil
	end
	return { faces = faces, planted = planted, travel = 0 }
end

-- `offset` is the body offset applied to Root this frame (Root space).
function Tracks.update(s: State, dt: number, rot: CFrame, vel: Vector3, offset: CFrame)
	-- Signed ground speed along the hull (forward = -Z).
	local speed = vel:Dot(rot.LookVector)
	s.travel = (s.travel + speed * dt) % 1e4
	for _, f in s.faces do
		local o = f.sign * s.travel
		if f.axis == "U" then
			f.tex.OffsetStudsU = o
		else
			f.tex.OffsetStudsV = o
		end
	end
	local inverse = offset:Inverse()
	for _, p in s.planted do
		p.weld.C0 = inverse * p.c0
	end
end

function Tracks.destroy(s: State?)
	if not s then
		return
	end
	for _, f in s.faces do
		f.tex:Destroy()
	end
	for _, p in s.planted do
		if p.weld.Parent then
			p.weld.C0 = p.c0
		end
	end
	table.clear(s.faces)
	table.clear(s.planted)
end

return Tracks
