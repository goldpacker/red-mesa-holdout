--!strict
-- Access to imported art assets (ReplicatedStorage.Assets, synced from
-- assets/roblox/). Every caller must handle nil and fall back to its
-- primitive placeholder, so gameplay never depends on an asset existing.
-- Asset names and required part/attachment names: docs/ASSET_CONTRACTS.md.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local AssetLibrary = {}

local function folder(): Instance?
	return ReplicatedStorage:FindFirstChild("Assets")
end

function AssetLibrary.has(name: string): boolean
	local f = folder()
	return f ~= nil and f:FindFirstChild(name) ~= nil
end

-- Returns a fresh clone of the named asset, or nil if it isn't available.
function AssetLibrary.clone(name: string): Instance?
	local f = folder()
	local source = f and f:FindFirstChild(name)
	if not source then
		return nil
	end
	local ok, copy = pcall(function()
		return source:Clone()
	end)
	return if ok then copy else nil
end

return AssetLibrary
