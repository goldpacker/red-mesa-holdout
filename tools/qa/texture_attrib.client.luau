-- Texture memory attribution by removal (QA-B, docs/PERF_BUDGET.md §5).
-- Client datamodel, Studio playtest, everything staged and resident first.
-- Don't paste this file directly: `tools/qa/py tools/qa/texture_budget.py
-- attrib-script` prints it with the GROUPS table filled in from the id maps.
-- The first call installs _G.QATex and returns the group count; then run
-- slices that fit in one MCP call (~6 s per group):
--   return _G.QATex.run(1, 8)
-- For each group it re-points every reference to one tiny texture that is
-- already resident (64² HUD tile) — maps of SurfaceAppearances and
-- MaterialVariants go empty — so nothing falls back to a stock texture, then
-- waits for GraphicsTexture to settle and records the drop. Destructive for
-- the play session only (client-side); stop Play afterwards.
-- LIMITATION (QA-B, 2026-09-26): Roblox frees only part of a texture's
-- memory when its last reference goes (0.33 MB steps, order-dependent; the
-- terrain MaterialVariants, UI and most of the Emplacement stayed cached),
-- so each drop is a lower bound. For per-asset costs use the additive
-- texture_calib.client.luau in a fresh session.
local Stats = game:GetService("Stats")
local Players = game:GetService("Players")

local GROUPS: { { name: string, ids: { string } } } = {} --@@GROUPS@@

local SMALL = "rbxassetid://93922214770132" -- UiKitAssets.hazard, 64x64
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
	Sky = { "SkyboxBk", "SkyboxDn", "SkyboxFt", "SkyboxLf", "SkyboxRt", "SkyboxUp" },
	MeshPart = { "TextureID" },
	SpecialMesh = { "TextureId" },
}
local EMPTY_OK = { NormalMap = true, RoughnessMap = true, MetalnessMap = true }
local TAGS = { "GraphicsTexture", "GraphicsParticles", "GraphicsTextureCharacter", "Gui" }

local function mem(): { number }
	local out = {}
	for i, tag in TAGS do
		out[i] = Stats:GetMemoryUsageMbForTag((Enum.DeveloperMemoryTag :: any)[tag])
	end
	return out
end

-- Polls every 0.5 s until four readings in a row agree within 0.05 MB
-- (GraphicsTexture and GraphicsParticles), or maxWait passes.
local function settle(maxWait: number): ({ number }, number)
	local started = os.clock()
	local last = mem()
	local stable = 0
	while os.clock() - started < maxWait do
		task.wait(0.5)
		local now = mem()
		if math.abs(now[1] - last[1]) < 0.05 and math.abs(now[2] - last[2]) < 0.05 then
			stable += 1
			if stable >= 4 then
				return now, os.clock() - started
			end
		else
			stable = 0
		end
		last = now
	end
	return last, os.clock() - started
end

local function idOf(value: any): string?
	if typeof(value) ~= "string" or value == "" then
		return nil
	end
	return string.match(value, "^rbxassetid://(%d+)") or string.match(value, "[?&]id=(%d+)")
end

local function roots(): { Instance }
	return {
		workspace,
		game:GetService("Lighting"),
		game:GetService("MaterialService"),
		Players.LocalPlayer:WaitForChild("PlayerGui"),
	}
end

local function strip(idset: { [string]: boolean }): (number, number)
	local changed, failed = 0, 0
	for _, root in roots() do
		for _, inst in root:GetDescendants() do
			local props = PROPS[inst.ClassName]
			if props then
				for _, prop in props do
					local ok, value = pcall(function()
						return (inst :: any)[prop]
					end)
					local id = ok and idOf(value)
					if id and idset[id] then
						local target = if EMPTY_OK[prop] then "" else SMALL
						local set = pcall(function()
							(inst :: any)[prop] = target
						end)
						if set then
							changed += 1
						elseif inst:IsA("SurfaceAppearance") and inst.Parent and inst.Parent:IsA("BasePart") then
							-- Maps not writable here: drop the appearance and use a
							-- texture-free material so no stock texture loads.
							(inst.Parent :: BasePart).Material = Enum.Material.SmoothPlastic
							inst:Destroy()
							changed += 1
							break
						else
							failed += 1
						end
					end
				end
			end
		end
	end
	return changed, failed
end

local QATex = { groups = GROUPS, log = {} :: { string } }

function QATex.run(first: number, last: number): string
	local lines = {}
	local before = settle(4)
	for i = first, math.min(last, #GROUPS) do
		local g = GROUPS[i]
		local set = {}
		for _, id in g.ids do
			set[id] = true
		end
		local changed, failed = strip(set)
		local after, waited = before, 0
		if changed > 0 then
			after, waited = settle(8)
		end
		local line = string.format("%02d %-34s refs %3d%s  tex %7.2f -> %7.2f  (-%5.2f)  particles -%5.2f  char -%4.2f  gui -%4.2f  %.1fs",
			i, g.name, changed, if failed > 0 then string.format(" (failed %d)", failed) else "",
			before[1], after[1], before[1] - after[1], before[2] - after[2], before[3] - after[3], before[4] - after[4], waited)
		table.insert(lines, line)
		table.insert(QATex.log, line)
		before = after
	end
	return table.concat(lines, "\n")
end

function QATex.mem(): string
	local m = mem()
	local parts = {}
	for i, tag in TAGS do
		table.insert(parts, string.format("%s %.2f", tag, m[i]))
	end
	return table.concat(parts, "  ")
end

_G.QATex = QATex
return string.format("installed %d groups; %s", #GROUPS, QATex.mem())
