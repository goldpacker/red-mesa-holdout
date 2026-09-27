--!strict
-- Airdrop timeline maths (AD-1): where a transport and each of its loads
-- are at server time t, from the AirdropSortie payload (docs/ARCHITECTURE.md).
-- Pure functions, shared by the client visuals and server checks, so AD-2
-- can restyle the motion without touching the timing contract: a load is
-- at `openPos` at `openT` and at `landPos` exactly at `landT`.

local AirdropPath = {}

export type Load = {
	loadId: number,
	kind: string,
	lane: string,
	releaseT: number,
	openT: number,
	landT: number,
	openPos: Vector3,
	landPos: Vector3,
	-- Flat unit direction the landed enemy faces (toward its lane).
	face: Vector3,
}

export type Sortie = {
	id: number,
	kind: string,
	lane: string,
	from: Vector3,
	to: Vector3,
	speed: number,
	t0: number,
	loads: { Load },
}

-- "Stowed" (still in the transport), "FreeFall", "Canopy" or "Landed".
export type Phase = string

function AirdropPath.heading(s: Sortie): Vector3
	local d = s.to - s.from
	return if d.Magnitude > 1e-3 then d.Unit else Vector3.new(1, 0, 0)
end

function AirdropPath.duration(s: Sortie): number
	return (s.to - s.from).Magnitude / s.speed
end

-- Server time the transport reaches the end of its path.
function AirdropPath.endTime(s: Sortie): number
	return s.t0 + AirdropPath.duration(s)
end

function AirdropPath.transportAt(s: Sortie, t: number): Vector3
	return s.from + AirdropPath.heading(s) * (s.speed * (t - s.t0))
end

-- The transport's frame at t: facing along its path, level.
function AirdropPath.transportFrame(s: Sortie, t: number): CFrame
	local p = AirdropPath.transportAt(s, t)
	return CFrame.lookAt(p, p + AirdropPath.heading(s))
end

-- Where the load leaves the ramp.
function AirdropPath.releasePos(s: Sortie, load: Load): Vector3
	return AirdropPath.transportAt(s, load.releaseT)
end

local function smooth(u: number): number
	return u * u * (3 - 2 * u)
end

-- Position of a load's lowest point (feet, wheels, tracks) at time t, its
-- phase and the phase progress 0..1.
function AirdropPath.loadAt(s: Sortie, load: Load, t: number): (Vector3, Phase, number)
	if t < load.releaseT then
		return AirdropPath.releasePos(s, load), "Stowed", 0
	elseif t < load.openT then
		-- Free fall: forward momentum bleeds off while it drops (u^2).
		local release = AirdropPath.releasePos(s, load)
		local u = (t - load.releaseT) / math.max(load.openT - load.releaseT, 1e-3)
		local flatStart = Vector3.new(release.X, 0, release.Z)
		local flatEnd = Vector3.new(load.openPos.X, 0, load.openPos.Z)
		local flat = flatStart:Lerp(flatEnd, 1 - (1 - u) * (1 - u))
		local y = release.Y + (load.openPos.Y - release.Y) * u * u
		return Vector3.new(flat.X, y, flat.Z), "FreeFall", u
	elseif t < load.landT then
		-- Under canopy: constant sink rate, sideways drift eased in and out.
		local u = (t - load.openT) / math.max(load.landT - load.openT, 1e-3)
		local flat = Vector3.new(load.openPos.X, 0, load.openPos.Z):Lerp(Vector3.new(load.landPos.X, 0, load.landPos.Z), smooth(u))
		local y = load.openPos.Y + (load.landPos.Y - load.openPos.Y) * u
		return Vector3.new(flat.X, y, flat.Z), "Canopy", u
	end
	return load.landPos, "Landed", 1
end

-- Horizontal distance between two points.
function AirdropPath.flat(a: Vector3, b: Vector3): number
	return Vector2.new(a.X - b.X, a.Z - b.Z).Magnitude
end

-- Closest horizontal approach of the (infinite) flight line to `point`.
function AirdropPath.clearance(s: Sortie, point: Vector3): number
	local h = AirdropPath.heading(s)
	local flatH = Vector2.new(h.X, h.Z)
	if flatH.Magnitude < 1e-6 then
		return AirdropPath.flat(s.from, point)
	end
	flatH = flatH.Unit
	local rel = Vector2.new(point.X - s.from.X, point.Z - s.from.Z)
	return math.abs(rel.X * flatH.Y - rel.Y * flatH.X)
end

return AirdropPath
