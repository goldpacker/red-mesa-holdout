-- PERF-1 view x quality probe (Client datamodel, Studio play, Studio focused:
-- click the Studio title bar first; unfocused Studio renders at ~15 fps).
-- For each QualityLevel x view it samples, inside RenderStepped:
--   * at the vsync-capped rate: frame time (mean, p95), Stats.RenderCPUFrameTime
--     and RenderGPUFrameTime ("gpu@60": at 60 fps the Apple GPU clock hunts,
--     so this reads 3-9 ms for the same work; use it as a trend only);
--   * the script time per system from client/FrameProfile (Workspace
--     FrameProfile = true is set here);
--   * GPU-bound: K near-transparent full-screen sheets in front of the camera
--     pin the GPU at its top clock (frames ~25-28 ms, not vsync-quantised);
--     frame time - K * U = the scene's GPU time at the top clock. Calibrate U
--     once per viewport (two K values in one view: U = dT / dK; 0.281-0.283
--     ms per sheet at 1670x1005 on the M4 Pro).
-- Views: "title" (whatever camera the phase has), "turret", "mg", "rocket",
-- "aa" (gunsight of that weapon). Aim is fixed at the turret beauty angle
-- (DebugYaw -2, DebugPitch -7.5) with the MG trigger held (tracers, flashes,
-- impacts; the MG overheats and cools like a player's).
-- Inputs (LocalPlayer attributes, optional): P1Label "scene", P1Levels
-- "15,8", P1Views "turret,mg,rocket,aa", P1K 80 (0 = skip GPU-bound), P1U
-- 0.281. Output: LocalPlayer P1ViewsText (poll it; ~5 s per block).
local HttpService = game:GetService("HttpService")
local RunService = game:GetService("RunService")
local Stats = game:GetService("Stats")
local Workspace = game:GetService("Workspace")
local plr = game.Players.LocalPlayer
local cam = Workspace.CurrentCamera

local function list(attr: string, default: string): { string }
	local out = {}
	for item in string.gmatch(tostring(plr:GetAttribute(attr) or default), "[^,%s]+") do
		table.insert(out, item)
	end
	return out
end
local LABEL = tostring(plr:GetAttribute("P1Label") or "scene")
local LEVELS = list("P1Levels", "15,8")
local VIEWS = list("P1Views", "turret,mg,rocket,aa")
local K = tonumber(plr:GetAttribute("P1K")) or 80
local U = tonumber(plr:GetAttribute("P1U")) or 0.281
local WEAPON = { turret = 1, mg = 1, rocket = 2, aa = 3 }

local function setLoad(count: number)
	local f = Workspace:FindFirstChild("P1Load")
	if not f then
		f = Instance.new("Folder")
		f.Name = "P1Load"
		f.Parent = Workspace
	end
	local parts = f:GetChildren()
	while #parts < count do
		local p = Instance.new("Part")
		p.Anchored, p.CanCollide, p.CanQuery, p.CanTouch, p.CastShadow = true, false, false, false, false
		p.Material = Enum.Material.SmoothPlastic
		p.Transparency = 0.985
		p.Color = Color3.new(0.5, 0.5, 0.5)
		p.Size = Vector3.new(3, 3, 0.01)
		p.Parent = f
		table.insert(parts, p)
	end
	while #parts > count do
		(table.remove(parts) :: Instance):Destroy()
	end
	pcall(function()
		RunService:UnbindFromRenderStep("P1LoadFollow")
	end)
	if count > 0 then
		RunService:BindToRenderStep("P1LoadFollow", Enum.RenderPriority.Last.Value + 300, function()
			local cf = cam.CFrame
			local items = f:GetChildren()
			local cfs = {}
			for i = 1, #items do
				cfs[i] = cf * CFrame.new(0, 0, -0.25 - i * 0.002)
			end
			Workspace:BulkMoveTo(items, cfs, Enum.BulkMoveMode.FireCFrameChanged)
		end)
	end
end

local function snapProfile(): { [string]: any }
	local raw = plr:GetAttribute("FrameProfileOut")
	return if type(raw) == "string" then HttpService:JSONDecode(raw) else {}
end
local function setView(view: string)
	if view == "title" then
		return
	end
	plr:SetAttribute("DebugWeapon", WEAPON[view] or 1)
	plr:SetAttribute("DebugAiming", if view ~= "turret" then true else nil)
	plr:SetAttribute("DebugYaw", -2)
	plr:SetAttribute("DebugPitch", -7.5)
	plr:SetAttribute("DebugFire", true)
end
local function mean(values: { number }): number
	local s = 0
	for _, v in values do
		s += v
	end
	return if #values > 0 then s / #values else 0
end
local function pct(values: { number }, p: number): number
	if #values == 0 then
		return 0
	end
	local s = table.clone(values)
	table.sort(s)
	return s[math.clamp(math.ceil(#s * p), 1, #s)]
end

local function block(level: string, view: string): string
	pcall(function()
		settings().Rendering.QualityLevel = (Enum.QualityLevel :: any)["Level" .. string.format("%02d", tonumber(level) :: number)]
	end)
	setView(view)
	setLoad(0)
	task.wait(1)
	local dts, cpus, gpus = {}, {}, {}
	local conn = RunService.RenderStepped:Connect(function(dt)
		table.insert(dts, dt * 1000)
		table.insert(gpus, Stats.RenderGPUFrameTime * 1000)
		table.insert(cpus, Stats.RenderCPUFrameTime * 1000)
	end)
	local p0 = snapProfile()
	task.wait(2)
	conn:Disconnect()
	task.wait(0.55) -- FrameProfile publishes every 0.5 s
	local p1 = snapProfile()
	local frames = (p1.frames or 0) - (p0.frames or 0)
	local top, total = {}, 0
	for name, e in p1 do
		if name ~= "frames" and frames > 0 then
			local ms = (e.s - (p0[name] or { s = 0 }).s) * 1000 / frames
			total += ms
			table.insert(top, { name, ms })
		end
	end
	table.sort(top, function(a, b)
		return a[2] > b[2]
	end)
	local topText = {}
	for i = 1, math.min(5, #top) do
		table.insert(topText, string.format("%s %.2f", top[i][1], top[i][2]))
	end
	local tris, dc, sdc = Stats.SceneTriangleCount, Stats.SceneDrawcallCount, Stats.ShadowsDrawcallCount
	local bound = ""
	if K > 0 then
		setLoad(K)
		task.wait(0.4)
		local bt = {}
		local c = RunService.RenderStepped:Connect(function(dt)
			table.insert(bt, dt * 1000)
		end)
		task.wait(1.6)
		c:Disconnect()
		setLoad(0)
		local b = mean(bt)
		bound = string.format(" | GPU-bound %5.2f -> scene %4.2f ms", b, b - K * U)
	end
	return string.format("L%02d %-6s fps %5.1f p95 %5.2f | cpu %4.2f gpu@60 %4.2f%s | script %.2f [%s] tris %d dc %d sdc %d",
		tonumber(level) :: number, view, 1000 / mean(dts), pct(dts, 0.95), mean(cpus), mean(gpus), bound, total, table.concat(topText, ", "), tris, dc, sdc)
end

Workspace:SetAttribute("FrameProfile", true)
plr:SetAttribute("P1ViewsText", nil)
task.spawn(function()
	local state = game.ReplicatedStorage.GameState
	local lines = { string.format("[%s] viewport %s ToD %s phase %s wave %s enemies %d K %d U %.3f", LABEL, tostring(cam.ViewportSize),
		tostring(Workspace:GetAttribute("TimeOfDay")), tostring(state:GetAttribute("Phase")), tostring(state:GetAttribute("Wave")),
		#Workspace.Enemies:GetChildren(), K, U) }
	for _, level in LEVELS do
		for _, view in VIEWS do
			table.insert(lines, block(level, view))
		end
	end
	for _, a in { "DebugFire", "DebugAiming" } do
		plr:SetAttribute(a, nil)
	end
	plr:SetAttribute("DebugWeapon", 1)
	plr:SetAttribute("P1ViewsText", table.concat(lines, "\n"))
end)
return string.format("started: %d levels x %d views, ~%.0f s", #LEVELS, #VIEWS, #LEVELS * #VIEWS * 5.6)
