--!strict
-- Read-only client view of the server's GameState attributes plus the
-- GameEvent stream, re-exposed as simple listener lists.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local GameState = {}

local stateObject = ReplicatedStorage:WaitForChild("GameState") :: Configuration
local gameEvent = ReplicatedStorage:WaitForChild("Remotes"):WaitForChild("GameEvent") :: RemoteEvent

type Listener = (payload: any) -> ()
local eventListeners: { [string]: { Listener } } = {}
local changeListeners: { [string]: { Listener } } = {}

function GameState.get(name: string): any
	return stateObject:GetAttribute(name)
end

function GameState.phase(): string
	return (stateObject:GetAttribute("Phase") :: string?) or "Title"
end

function GameState.isCombat(): boolean
	local p = GameState.phase()
	return p == "Wave" or p == "WaveIntro" or p == "Intermission"
end

function GameState.onEvent(kind: string, fn: Listener)
	eventListeners[kind] = eventListeners[kind] or {}
	table.insert(eventListeners[kind], fn)
end

function GameState.onChanged(attribute: string, fn: Listener)
	if not changeListeners[attribute] then
		changeListeners[attribute] = {}
		stateObject:GetAttributeChangedSignal(attribute):Connect(function()
			local value = stateObject:GetAttribute(attribute)
			for _, listener in changeListeners[attribute] do
				task.spawn(listener, value)
			end
		end)
	end
	table.insert(changeListeners[attribute], fn)
end

gameEvent.OnClientEvent:Connect(function(kind: string, payload: any)
	local listeners = eventListeners[kind]
	if not listeners then
		return
	end
	for _, listener in listeners do
		task.spawn(listener, payload)
	end
end)

return GameState
