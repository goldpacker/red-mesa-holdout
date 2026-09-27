--!strict
-- Where ConflictDressing puts things (ENV-4). Hand-placed on the layout
-- board (tools/env/dressing/survey.py --layout, which also flags any piece
-- near a simulated airdrop landing, a walk to a lane, or a lane).
--
-- Zones:
--   * the mesa foot (130-190 studs from the gun, between the lanes): the
--     outpost's checkpoint on the road; only lane followers pass here
--     (within 14 studs of their lane), no landings (< 300);
--   * the far basin (beyond 800): the old front line: a power line across
--     the basin, a ruined compound on the left flank with a dirt track to
--     the road, a destroyed convoy by the road's far end. Nothing lands or
--     walks there (landings are 300-800 out and walk inward);
--   * between (300-800, the airdrop band): only flat things (craters,
--     scorch, tracks: GroundDressing) and small props against rocks.
-- Far-end pieces stay >= 30 studs off the Road's first segment: the Siege
-- Crawler (44 x 91 studs) starts at its first waypoint.
-- Coordinates: studs on the XZ plane (Vector2 x, z); the gun is at (0, 0)
-- facing -Z; +X is right in the turret view. Yaw in degrees (0: the
-- mesh's front faces -Z; a row's pieces face across it).

local ConflictLayout = {}

ConflictLayout.SEED = 40426

local V = Vector2.new

-- Burnt-out hulks (enemy vehicle assets, burnt): kind, ground point, yaw,
-- extra roll/pitch, sink, turret swing, parts dropped.
ConflictLayout.HULKS = {
	-- destroyed convoy by the road's far end (beyond the drop band)
	{ kind = "Tank", at = V(34, -866), yaw = 152, roll = -3, pitch = 2, sink = 0.9, turret = 38, lean = 0.7, smoke = "light", drop = { "TrackL" } },
	{ kind = "Buggy", at = V(-88, -938), yaw = 70, roll = 168, sink = 0.4, lean = 0.4, drop = { "WheelFL", "GunBody" } },
	-- the old enemy position on the right flank
	{ kind = "Tank", at = V(468, -912), yaw = 214, roll = 4, pitch = -3, sink = 1.1, turret = -64, lean = 0.7, drop = { "Barrel" } },
	-- a buggy that reached the wire and burned (mesa foot, off the lanes)
	{ kind = "Buggy", at = V(-115, -135), yaw = -24, roll = 8, pitch = -4, sink = 0.5, lean = 0.8, drop = { "WheelRR", "BuggyKit" }, smoke = "light" },
}

-- Rows: hesco walls, barrier lines and concertina wire at the checkpoint,
-- and the remains of older positions in the far basin.
ConflictLayout.ROWS = {
	-- far basin: an old enemy hesco line on the right flank, gaps blown in it
	{ kit = "ConflictDressing", piece = "Hesco_3", from = V(392, -858), to = V(456, -884), step = 12.9, jitter = 0.6, yawJitter = 5, skip = { 3 } },
	{ kit = "ConflictDressing", piece = "Hesco_3", from = V(462, -890), to = V(488, -930), step = 12.9, jitter = 0.6, yawJitter = 6 },
	-- the road's far end: barriers pushed off the road, a strand of wire
	{ kit = "ConflictDressing", piece = "Jersey", from = V(-94, -930), to = V(-80, -902), step = 12.6, jitter = 1.5, yawJitter = 24 },
	{ kit = "ConflictDressing", piece = "Jersey", from = V(-10, -940), to = V(4, -914), step = 12.6, jitter = 1.5, yawJitter = 30 },
	{ kit = "GroundPatches", piece = "Wire_Coil", from = V(-108, -952), to = V(-80, -962), step = 16, jitter = 1, yawJitter = 10, lean = 0.9 },
	-- right of the road: hesco wall facing the basin, jersey barriers, wire
	{ kit = "ConflictDressing", piece = "Hesco_3", from = V(22, -138), to = V(48, -141), step = 12.9, jitter = 0.3, yawJitter = 2 },
	{ kit = "ConflictDressing", piece = "Jersey", from = V(22, -165), to = V(48, -172), step = 12.6, jitter = 0.8, yawJitter = 9 },
	{ kit = "GroundPatches", piece = "Wire_Coil", from = V(20, -182), to = V(52, -188), step = 16, jitter = 0.4, yawJitter = 4, lean = 0.8, extra = "Picket", extraStep = 8 },
	-- left of the road
	{ kit = "ConflictDressing", piece = "Hesco_3", from = V(-46, -132), to = V(-20, -135), step = 12.9, jitter = 0.3, yawJitter = 2 },
	{ kit = "ConflictDressing", piece = "Jersey", from = V(-48, -160), to = V(-22, -157), step = 12.6, jitter = 0.8, yawJitter = 12 },
	{ kit = "GroundPatches", piece = "Wire_Coil", from = V(-53, -180), to = V(-20, -181), step = 16, jitter = 0.4, yawJitter = 4, lean = 0.8, extra = "Picket", extraStep = 8 },
}

-- Single props (supplies at the checkpoint, debris by the hulks).
local C = "ConflictDressing"
ConflictLayout.PIECES = {
	{ kit = C, piece = "Crates", at = V(33, -123), yaw = 12 },
	{ kit = C, piece = "Drums", at = V(-32, -119), yaw = -30 },
	{ kit = C, piece = "Tyres", at = V(-31, -148), yaw = 50 },
	{ kit = C, piece = "Drum_Red", at = V(44, -154), yaw = 0, roll = 90, sink = -1.1 },
	{ kit = C, piece = "Sheet", at = V(24, -896), yaw = 30, lean = 1 },
	{ kit = C, piece = "Drums", at = V(430, -900), yaw = 70 },
	{ kit = C, piece = "Crates", at = V(418, -842), yaw = -20 },
	{ kit = C, piece = "Tyres", at = V(-68, -872), yaw = 15 },
	{ kit = "GroundPatches", piece = "Patch_Scorch", at = V(468, -912), yaw = 10, lean = 1, scale = 1.5 },
	{ kit = C, piece = "Tyre", at = V(-70, -950), yaw = 10, lean = 1 },
	{ kit = C, piece = "Crate", at = V(52, -884), yaw = 40, lean = 1, roll = 8, sink = 0.5 },
	{ kit = "GroundPatches", piece = "Patch_Scorch", at = V(34, -866), yaw = 0, lean = 1, scale = 1.6 },
	{ kit = "GroundPatches", piece = "Patch_Scorch", at = V(-88, -938), yaw = 70, lean = 1, scale = 1.2 },
	{ kit = "GroundPatches", piece = "Patch_Scorch", at = V(-115, -135), yaw = 20, lean = 1, scale = 1.1 },
}

-- The ruined compound on the left flank (beyond the drop band): a walled
-- yard, a house with its roof fallen in, rubble, junk. Offsets from the
-- origin, rotated by yaw.
ConflictLayout.GROUPS = {
	{
		origin = V(-332, -800),
		yaw = 18,
		pieces = {
			-- yard walls (24 long, pivot at the wall's centre base, faces -Z/+Z at yaw 0)
			{ kit = C, piece = "Adobe_Wall", at = V(-12, -24), yaw = 0, sink = 0.4 },
			{ kit = C, piece = "Adobe_Gap", at = V(12, -24), yaw = 0, sink = 0.4 },
			{ kit = C, piece = "Adobe_Door", at = V(-24, -12), yaw = 90, sink = 0.4 },
			{ kit = C, piece = "Adobe_Wall", at = V(-24, 12), yaw = 90, sink = 0.4 },
			{ kit = C, piece = "Adobe_Gap", at = V(24, 0), yaw = 90, sink = 0.4 },
			-- the house in the back corner: two walls standing, the roof fallen in
			{ kit = C, piece = "Adobe_Wall", at = V(0, 24), yaw = 0, sink = 0.4 },
			{ kit = C, piece = "Adobe_Door", at = V(-12, 12), yaw = 0, sink = 0.4 },
			{ kit = C, piece = "Roof", at = V(-6, 18), yaw = 0, sink = 0.2 },
			{ kit = C, piece = "Rubble", at = V(16, 20), yaw = 40, sink = 0.3 },
			{ kit = C, piece = "Rubble", at = V(-34, -30), yaw = 10, sink = 0.5, scale = 0.8 },
			{ kit = C, piece = "Drums", at = V(8, -8), yaw = 30 },
			{ kit = C, piece = "Tyre", at = V(-8, -4), yaw = 0, lean = 1 },
			{ kit = C, piece = "Sheet", at = V(14, 6), yaw = 70, lean = 1 },
			{ kit = "GroundPatches", piece = "Patch_Stain", at = V(0, 0), yaw = 0, lean = 1, scale = 1.8 },
			{ kit = "GroundPatches", piece = "Patch_Stain", at = V(-10, 14), yaw = 50, lean = 1, scale = 1.2 },
		},
	},
}

-- The power line across the far basin, left wall to right wall, bending
-- round the buttes; poles every `spacing`; one snapped (station index).
ConflictLayout.LINES = {
	{ points = { V(-700, -972), V(-300, -994), V(140, -992), V(470, -962), V(700, -918) }, spacing = 74, snapped = { 7 } },
}

return ConflictLayout
