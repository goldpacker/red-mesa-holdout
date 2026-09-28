-- PERF-1 aim latency probe (Client datamodel, Studio play during a Wave,
-- Studio focused). Studio can't inject a real mouse delta (synthetic moves
-- arrive with InputObject.Delta = 0), so the step enters one stage later:
-- DebugYaw, which AimController.readInput applies right after
-- GetMouseDelta. A value set at Last+100 of frame k is first read by frame
-- k+1's camera step, the frame a mouse delta would arrive in.
-- Per frame (after every camera, turret and sight writer): camera yaw, the
-- drawn gun's yaw, the gunsight model's rotation change vs the camera, and
-- the screen-x offset of every own tracer at the frame it spawns.
-- Plan: turret view 10 deg step, 60 deg/s ramp; gunsight 5 deg step, 30 deg/s
-- ramp, MG bursts in the ramps. Returns a text summary (~10 s).
local RunService = game:GetService("RunService")
local plr = game.Players.LocalPlayer
local cam = workspace.CurrentCamera

local PITCH = -6
local plan = {}
local function hold(n: number, y: number, aim: boolean, fire: boolean?)
	for _ = 1, n do
		table.insert(plan, { y = y, aim = aim, tag = "hold", fire = fire })
	end
end
local function ramp(n: number, y0: number, rate: number, aim: boolean)
	for i = 1, n do
		table.insert(plan, { y = y0 + rate * i, aim = aim, tag = "ramp", fire = (i % 60) < 24 })
	end
end
hold(40, 0, false)
table.insert(plan, { y = 10, aim = false, tag = "STEP_T" })
hold(50, 10, false)
ramp(60, 10, -1, false)
hold(50, -50, false)
hold(70, -50, true)
table.insert(plan, { y = -45, aim = true, tag = "STEP_G" })
hold(50, -45, true)
ramp(120, -45, 0.5, true)
hold(30, 15, true)

local function yawOf(look: Vector3): number
	return math.deg(math.atan2(-look.X, -look.Z))
end

local rows = {}
local tracers: { [number]: { number } } = {} -- frame -> screen-x offsets of tracers spawned that frame
local wasOn: { [Instance]: boolean } = {}
local i, current = 0, nil :: any
local prevSight: CFrame? = nil
local done = false
plr:SetAttribute("DebugPitch", PITCH)
plr:SetAttribute("DebugWeapon", 1)
RunService:BindToRenderStep("P1AimLatency", Enum.RenderPriority.Last.Value + 100, function(dt)
	if current then
		local gun = workspace.Battlefield.Emplacement:FindFirstChild("TurretGun") :: Model
		local sightDelta = -1
		for _, c in cam:GetChildren() do
			if c:IsA("Model") and string.sub(c.Name, 1, 8) == "Gunsight" then
				local part = c:FindFirstChildWhichIsA("BasePart", true)
				if part and part.LocalTransparencyModifier < 0.9 then
					local rel = cam.CFrame:ToObjectSpace(part.CFrame)
					if prevSight then
						local _, angle = prevSight:ToObjectSpace(rel):ToAxisAngle()
						sightDelta = math.deg(angle)
					end
					prevSight = rel
				end
			end
		end
		local spawned = {}
		for _, a in workspace.Terrain:GetChildren() do
			if a.Name == "TracerTail" and a:IsA("Attachment") then
				local core = a:FindFirstChild("TracerCore") :: Beam?
				local on = core ~= nil and core.Enabled
				if on and not wasOn[a] and (a.WorldPosition - cam.CFrame.Position).Magnitude < 40 then
					local p, visible = cam:WorldToViewportPoint(a.WorldPosition)
					if visible then
						table.insert(spawned, p.X - cam.ViewportSize.X / 2)
					end
				end
				wasOn[a] = on
			end
		end
		table.insert(rows, { tag = current.tag, input = current.y, aim = current.aim, cam = yawOf(cam.CFrame.LookVector), gun = yawOf(gun:GetPivot().LookVector), sight = sightDelta, tracers = spawned, dt = dt })
	end
	i += 1
	current = plan[i]
	if not current then
		RunService:UnbindFromRenderStep("P1AimLatency")
		for _, a in { "DebugYaw", "DebugPitch", "DebugAiming", "DebugFire" } do
			plr:SetAttribute(a, nil)
		end
		done = true
		return
	end
	plr:SetAttribute("DebugYaw", current.y)
	plr:SetAttribute("DebugAiming", current.aim or nil)
	plr:SetAttribute("DebugFire", current.fire or nil)
end)
while not done do
	task.wait(0.2)
end

local out = {}
local slow = 0
for _, r in rows do
	if r.dt > 0.025 then
		slow += 1
	end
end
table.insert(out, string.format("%d frames, %d over 25 ms (throttled or hitching Studio invalidates the frame counts)", #rows, slow))
for _, tag in { "STEP_T", "STEP_G" } do
	local k
	for j, r in rows do
		if r.tag == tag then
			k = j
			break
		end
	end
	local r = rows[k]
	local settled
	for j = k, math.min(#rows - 5, k + 60) do
		local ok = true
		for q = j, j + 4 do
			if math.abs(rows[q].gun - rows[q].input) > 0.05 then
				ok = false
			end
		end
		if ok then
			settled = j - k
			break
		end
	end
	local over = 0
	for j = k, math.min(#rows, k + 30) do
		over = math.max(over, (rows[j].gun - rows[j].input) * (if r.input > rows[k - 1].input then 1 else -1))
	end
	table.insert(out, string.format("%s: camera reaches the input in the first frame: %s (cam %.3f vs input %.3f); sight model moved vs camera: %.3f deg; drawn gun settles (<0.05 deg) after %s frames, overshoot %.3f deg",
		tag, tostring(math.abs(r.cam - r.input) < 1e-3), r.cam, r.input, r.sight, tostring(settled), over))
end
local function rampStats(aim: boolean): string
	local lag, n, tr = 0, 0, {}
	for _, r in rows do
		if r.tag == "ramp" and r.aim == aim then
			lag += r.input - r.gun
			n += 1
			for _, x in r.tracers do
				table.insert(tr, math.abs(x))
			end
		end
	end
	local s, mx = 0, 0
	for _, x in tr do
		s += x
		mx = math.max(mx, x)
	end
	return string.format("drawn gun trails by %.2f deg (mean); tracer spawn |screen x| mean %.1f px, max %.1f px over %d tracers", math.abs(lag / math.max(n, 1)), s / math.max(#tr, 1), mx, #tr)
end
table.insert(out, "turret ramp 60 deg/s: " .. rampStats(false))
table.insert(out, "gunsight ramp 30 deg/s: " .. rampStats(true))
table.insert(out, string.format("viewport %s", tostring(cam.ViewportSize)))
return table.concat(out, "\n")
