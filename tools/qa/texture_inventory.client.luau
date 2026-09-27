-- Texture inventory (QA-B, docs/PERF_BUDGET.md §5). Paste into execute_luau
-- (Client datamodel) during a Studio playtest. Lists every texture id that
-- an instance in a rendered root references, one line per id:
--   <id>|<refs>|<live refs>|<properties>|<roots>
-- <live refs> counts references that can draw right now (part in the
-- Workspace and not fully transparent, emitter/beam/trail enabled, GUI
-- enabled and visible, the active Sky, MaterialVariants). Templates in
-- ReplicatedStorage are listed with the root "RS" (not rendered). Join the
-- output with tools/qa/texture_budget.py.
local Players = game:GetService("Players")

local PROPS: { [string]: { string } } = {
	SurfaceAppearance = { "ColorMap", "NormalMap", "RoughnessMap", "MetalnessMap" },
	MaterialVariant = { "ColorMap", "NormalMap", "RoughnessMap", "MetalnessMap" },
	Decal = { "Texture" },
	Texture = { "Texture" },
	ParticleEmitter = { "Texture" },
	Beam = { "Texture" },
	Trail = { "Texture" },
	ImageLabel = { "Image" },
	ImageButton = { "Image", "HoverImage", "PressedImage" },
	Sky = { "SkyboxBk", "SkyboxDn", "SkyboxFt", "SkyboxLf", "SkyboxRt", "SkyboxUp", "SunTextureId", "MoonTextureId" },
	MeshPart = { "TextureID" },
	SpecialMesh = { "TextureId" },
}
local SHORT = {
	ColorMap = "C", NormalMap = "N", RoughnessMap = "R", MetalnessMap = "M", Texture = "T", Image = "I",
	HoverImage = "Ih", PressedImage = "Ip", TextureID = "Tm", TextureId = "Tm",
	SkyboxBk = "S", SkyboxDn = "S", SkyboxFt = "S", SkyboxLf = "S", SkyboxRt = "S", SkyboxUp = "S",
	SunTextureId = "Sun", MoonTextureId = "Moon",
}

local function idOf(value: any): string?
	if typeof(value) ~= "string" or value == "" then
		return nil
	end
	local num = string.match(value, "^rbxassetid://(%d+)") or string.match(value, "[?&]id=(%d+)")
	return num or value
end

local function partLive(part: Instance?): boolean
	while part and not part:IsA("BasePart") do
		part = part.Parent
	end
	if not part then
		return true -- attachments under non-parts (e.g. Terrain) render
	end
	local p = part :: BasePart
	return p.Transparency < 1 and p.LocalTransparencyModifier < 1
end

local function guiLive(gui: Instance): boolean
	local node: Instance? = gui
	while node do
		if node:IsA("GuiObject") and not node.Visible then
			return false
		elseif node:IsA("LayerCollector") then
			return node.Enabled
		end
		node = node.Parent
	end
	return false
end

local function live(inst: Instance, root: string): boolean
	if root == "RS" then
		return false
	elseif inst:IsA("ParticleEmitter") or inst:IsA("Beam") or inst:IsA("Trail") then
		return (inst :: any).Enabled and partLive(inst.Parent)
	elseif inst:IsA("GuiObject") then
		return guiLive(inst)
	elseif inst:IsA("Decal") or inst:IsA("SurfaceAppearance") or inst:IsA("SpecialMesh") then
		return partLive(inst.Parent)
	elseif inst:IsA("MeshPart") then
		return partLive(inst)
	end
	return true
end

local byId: { [string]: { n: number, live: number, props: { [string]: boolean }, roots: { [string]: number } } } = {}
local function scan(rootInst: Instance, rootName: string)
	for _, inst in rootInst:GetDescendants() do
		local props = PROPS[inst.ClassName]
		if props then
			-- Sub-root: the top-level child the instance sits under (Workspace.X, PlayerGui.X).
			local node = inst
			while node.Parent and node.Parent ~= rootInst do
				node = node.Parent
			end
			local where = rootName .. "." .. node.Name
			for _, prop in props do
				local ok, value = pcall(function()
					return (inst :: any)[prop]
				end)
				local id = ok and idOf(value)
				if id then
					local rec = byId[id]
					if not rec then
						rec = { n = 0, live = 0, props = {}, roots = {} }
						byId[id] = rec
					end
					rec.n += 1
					if live(inst, rootName) then
						rec.live += 1
					end
					rec.props[inst.ClassName .. ":" .. SHORT[prop]] = true
					rec.roots[where] = (rec.roots[where] or 0) + 1
				end
			end
		end
	end
end

scan(workspace, "WS")
scan(game:GetService("Lighting"), "Lighting")
scan(game:GetService("MaterialService"), "MS")
scan(Players.LocalPlayer:WaitForChild("PlayerGui"), "PG")
scan(game:GetService("ReplicatedStorage"), "RS")

local lines = {}
for id, rec in byId do
	local props, roots = {}, {}
	for p in rec.props do
		table.insert(props, p)
	end
	for r, n in rec.roots do
		table.insert(roots, r .. "*" .. n)
	end
	table.sort(props)
	table.sort(roots)
	table.insert(lines, string.format("%s|%d|%d|%s|%s", id, rec.n, rec.live, table.concat(props, ","), table.concat(roots, ",")))
end
table.sort(lines)
return string.format("# %d ids, %s, ToD %s, phase %s\n", #lines, os.date("%H:%M:%S"),
	tostring(workspace:GetAttribute("TimeOfDay")), tostring(game.ReplicatedStorage.GameState:GetAttribute("Phase")))
	.. table.concat(lines, "\n")
