--!strict
-- One HS-6 canopy (`Parachute` or `ParachuteCargo`, docs/ASSET_CONTRACTS.md)
-- hanging from a load (AD-2). Three states share the model pivot (the riser
-- confluence), one visible at a time: Deploying (the streamer), Open, and
-- Collapsed (lying on the ground toward +Z, pivot on the ground).
--
-- In the air every part hangs on a Weld from the load's anchor part, so
-- the whole load moves with one CFrame write; the canopy's own frame
-- (tilt, streamer direction) and the open "blossom" (scaling the canopy
-- and its lines about the pivot) are Weld C0 writes. On touchdown the
-- canopy is unwelded: the open canopy tips over downwind and deflates, then
-- the Collapsed mesh takes over on the ground, lingers and fades.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AssetLibrary = require(ReplicatedStorage.Shared.AssetLibrary)

local Canopy = {}

type Piece = { part: BasePart, size: Vector3, local0: CFrame, weld: Weld? }

export type C = {
	model: Model,
	anchor: BasePart,
	attach: CFrame, -- chute pivot in the anchor's frame
	states: { [string]: { Piece } },
	state: string,
	sx: number,
	sy: number,
	root: BasePart?, -- the chute's Root marker
	rootWeld: Weld?,
	lamp: BasePart?,
	lampLocal: CFrame,
	lampWeld: Weld?,
	height: number, -- apex above the pivot (Open)
	-- Ground phase.
	falling: Piece?,
	fall: { from: CFrame, to: CFrame, t0: number, time: number }?,
	ground: CFrame?,
	groundAt: number?, -- server time the collapsed mesh lay down
}

local FLYING = { "Open", "Deploying" }

local function quiet(p: BasePart)
	p.Anchored = false
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Massless = true
end

local function scaled(cf: CFrame, sx: number, sy: number): CFrame
	local p = cf.Position
	return CFrame.new(p.X * sx, p.Y * sy, p.Z * sx) * cf.Rotation
end

local function weldTo(anchor: BasePart, p: BasePart, c0: CFrame): Weld
	quiet(p)
	local w = Instance.new("Weld")
	w.Name = "AirdropWeld"
	w.Part0 = anchor
	w.Part1 = p
	w.C0 = c0
	w.Parent = p
	return w
end

-- A canopy on `anchor`, pivot at `attach` (anchor space). nil if the asset
-- is missing (the caller keeps its fallback).
function Canopy.new(assetName: string, parent: Instance, anchor: BasePart, attach: CFrame): C?
	local asset = AssetLibrary.clone(assetName)
	if not (asset and asset:IsA("Model")) then
		if asset then
			asset:Destroy()
		end
		return nil
	end
	local model = asset :: Model
	local marker = model:FindFirstChild("Root")
	if marker and marker:IsA("BasePart") then
		model.PrimaryPart = marker -- can read nil after a live sync (HS-6 note 6)
	end
	model:PivotTo(CFrame.identity)
	local states: { [string]: { Piece } } = {}
	for _, name in { "Open", "Deploying", "Collapsed" } do
		local list: { Piece } = {}
		local sub = model:FindFirstChild(name)
		if sub then
			for _, d in sub:GetChildren() do
				if d:IsA("BasePart") then
					quiet(d)
					table.insert(list, { part = d, size = d.Size, local0 = d.CFrame, weld = nil })
				end
			end
		end
		states[name] = list
	end
	local lamp = model:FindFirstChild("NightLamp")
	local apex = model:FindFirstChild("Apex", true)
	local c: C = {
		model = model,
		anchor = anchor,
		attach = attach,
		states = states,
		state = "",
		sx = 1,
		sy = 1,
		root = if marker and marker:IsA("BasePart") then marker else nil,
		rootWeld = nil,
		lamp = if lamp and lamp:IsA("BasePart") then lamp else nil,
		lampLocal = if lamp and lamp:IsA("BasePart") then lamp.CFrame else CFrame.identity,
		lampWeld = nil,
		height = if apex and apex:IsA("Attachment") then apex.WorldPosition.Y else 30,
		falling = nil,
		fall = nil,
		ground = nil,
		groundAt = nil,
	}
	for _, name in FLYING do
		for _, piece in states[name] do
			piece.weld = weldTo(anchor, piece.part, attach * piece.local0)
			piece.part.Transparency = 1
		end
	end
	for _, piece in states.Collapsed do
		piece.part.Transparency = 1
		piece.part.Anchored = true
	end
	if c.root then
		c.rootWeld = weldTo(anchor, c.root, attach)
	end
	if c.lamp then
		c.lampWeld = weldTo(anchor, c.lamp, attach * c.lampLocal)
	end
	model.Parent = parent
	return c
end

-- Shows one state (the others hidden).
function Canopy.show(c: C, state: string)
	if c.state == state then
		return
	end
	c.state = state
	for name, list in c.states do
		local visible = name == state
		for _, piece in list do
			piece.part.Transparency = if visible then 0 else 1
		end
	end
end

-- Re-hangs the canopy: its pivot frame on the anchor, and the current
-- state's scale about the pivot (width sx, height sy).
function Canopy.set(c: C, attach: CFrame, sx: number, sy: number)
	local resize = math.abs(sx - c.sx) > 1e-4 or math.abs(sy - c.sy) > 1e-4
	c.attach = attach
	c.sx, c.sy = sx, sy
	for _, name in FLYING do
		local active = name == c.state
		for _, piece in c.states[name] do
			local w = piece.weld
			if w then
				if active then
					w.C0 = attach * scaled(piece.local0, sx, sy)
					if resize then
						piece.part.Size = Vector3.new(piece.size.X * sx, piece.size.Y * sy, piece.size.Z * sx)
					end
				else
					w.C0 = attach * piece.local0
					if piece.part.Size ~= piece.size then
						piece.part.Size = piece.size
					end
				end
			end
		end
	end
	if c.rootWeld then
		c.rootWeld.C0 = attach
	end
	if c.lampWeld then
		c.lampWeld.C0 = attach * c.lampLocal
	end
end

-- Parts the "no effect" test may hit (the visible flying canopy and lines).
function Canopy.hitParts(c: C, out: { BasePart })
	if c.state == "Collapsed" or c.fall then
		return
	end
	for _, piece in c.states[c.state] or {} do
		table.insert(out, piece.part)
	end
end

function Canopy.placeCollapsed(c: C, sink: number?)
	local g = c.ground
	if not g then
		return
	end
	local frame = if sink then g * CFrame.new(0, -sink, 0) else g
	for _, piece in c.states.Collapsed do
		piece.part.CFrame = frame * piece.local0
	end
end

-- Touchdown: the canopy unhooks from the load; the open canopy tips over
-- toward the ground frame's +Z and comes down over `time` seconds, then
-- the Collapsed mesh lies on `ground` (+Z downwind, +Y the ground normal,
-- origin where the risers end).
function Canopy.collapse(c: C, ground: CFrame, now: number, time: number)
	c.ground = ground
	local list = c.states[c.state] or {}
	local canopyPiece: Piece? = nil
	for _, name in FLYING do
		for _, piece in c.states[name] do
			if piece.weld then
				piece.weld:Destroy()
				piece.weld = nil
			end
			piece.part.Anchored = true
		end
	end
	for _, piece in list do
		if piece.part.Name:match("^Canopy") then
			canopyPiece = piece
		else
			-- The lines go slack at once.
			piece.part.Transparency = 1
		end
	end
	if c.rootWeld then
		c.rootWeld:Destroy()
		c.rootWeld = nil
	end
	if c.root then
		c.root.Anchored = true
	end
	if c.lamp then
		c.lamp.Transparency = 1
	end
	if canopyPiece and c.state ~= "Collapsed" then
		local lie = math.max(c.height * 0.55, 6)
		c.falling = canopyPiece
		c.fall = {
			from = canopyPiece.part.CFrame,
			to = ground * CFrame.new(0, c.height * 0.12, lie) * CFrame.Angles(math.rad(82), 0, 0),
			t0 = now,
			time = time,
		}
	else
		Canopy.show(c, "Collapsed")
		Canopy.placeCollapsed(c)
		c.groundAt = now
	end
end

-- Ground phase: returns true once the canopy has faded out completely.
function Canopy.stepGround(c: C, now: number, linger: number, fade: number, sink: number): boolean
	local f = c.fall
	local piece = c.falling
	if f then
		local k = math.clamp((now - f.t0) / f.time, 0, 1)
		local e = k * k * (2 - k)
		if piece then
			piece.part.CFrame = f.from:Lerp(f.to, e)
			-- Deflating: the dome flattens (Y, now along the ground) and the
			-- mouth sags (Z, now upright) as it goes over.
			piece.part.Size = Vector3.new(piece.size.X * c.sx * (1 + 0.08 * e), piece.size.Y * c.sy * (1 - 0.6 * e), piece.size.Z * c.sx * (1 - 0.65 * e))
		end
		if k >= 1 then
			c.fall = nil
			c.falling = nil
			if piece then
				piece.part.Transparency = 1
			end
			Canopy.show(c, "Collapsed")
			Canopy.placeCollapsed(c)
			c.groundAt = now
		end
		return false
	end
	local age = now - (c.groundAt or now)
	if age < linger then
		return false
	end
	local k = math.clamp((age - linger) / fade, 0, 1)
	for _, p in c.states.Collapsed do
		p.part.Transparency = k
	end
	Canopy.placeCollapsed(c, sink * k)
	return k >= 1
end

-- Lying on the ground (not falling, not yet fading)?
function Canopy.onGround(c: C): boolean
	return c.groundAt ~= nil
end

-- Starts the fade now (the cap on collapsed canopies was reached).
function Canopy.expire(c: C, now: number, linger: number)
	if c.groundAt then
		c.groundAt = math.min(c.groundAt, now - linger)
	end
end

function Canopy.destroy(c: C)
	c.model:Destroy()
end

return Canopy
