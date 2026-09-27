-- Offline harness for client/PostFxStorm: mocks Color3, signals, instances, services.
local Color3 = {}
Color3.__index = Color3
local function c3(r, g, b) return setmetatable({ R = r, G = g, B = b }, Color3) end
function Color3.new(r, g, b) return c3(r, g, b) end
function Color3.fromRGB(r, g, b) return c3(r / 255, g / 255, b / 255) end
function Color3:Lerp(o, t) return c3(self.R + (o.R - self.R) * t, self.G + (o.G - self.G) * t, self.B + (o.B - self.B) * t) end
Color3.__eq = function(a, b) return a.R == b.R and a.G == b.G and a.B == b.B end
Color3.__tostring = function(c) return string.format("(%.3f,%.3f,%.3f)", c.R, c.G, c.B) end
_G.Color3 = Color3
local realTypeof = typeof
_G.typeof = function(v) if type(v) == "table" and getmetatable(v) == Color3 then return "Color3" end return realTypeof(v) end

local function f32(x) -- property storage rounds like a float
	if type(x) ~= "number" then return x end
	return string.unpack("f", string.pack("f", x))
end

local function signal()
	local s = { fns = {} }
	function s:Connect(fn) table.insert(self.fns, fn) return { Disconnect = function() end } end
	function s:Fire(...) for _, fn in self.fns do fn(...) end end
	return s
end

local function inst(className, props)
	local o = { __props = {}, __attrs = {}, ClassName = className, Changed = signal(), __children = {} }
	for k, v in props or {} do o.__props[k] = f32(v) end
	return setmetatable(o, {
		__index = function(t, k)
			local v = rawget(t, "__props")[k]
			if v ~= nil then return v end
			if k == "GetAttribute" then return function(self, n) return self.__attrs[n] end end
			if k == "SetAttribute" then return function(self, n, v) self.__attrs[n] = v end end
			if k == "WaitForChild" then return function(self, n) return self.__children[n] end end
			return nil
		end,
		__newindex = function(t, k, v)
			local p = rawget(t, "__props")
			v = f32(v)
			if p[k] ~= v then
				p[k] = v
				t.Changed:Fire(k)
			end
		end,
	})
end

local Lighting = inst("Lighting", {
	Brightness = 3.9, ExposureCompensation = 0, ShadowSoftness = 0.14,
	Ambient = Color3.fromRGB(64, 60, 88), OutdoorAmbient = Color3.fromRGB(78, 78, 130),
	ColorShift_Top = Color3.fromRGB(255, 170, 110), EnvironmentSpecularScale = 1,
})
local Atmosphere = inst("Atmosphere", { Density = 0.25, Offset = 0.32, Haze = 1.3, Glare = 0.7,
	Color = Color3.fromRGB(232, 182, 156), Decay = Color3.fromRGB(118, 88, 112) })
local SunRays = inst("SunRaysEffect", { Intensity = 0.2 })
Lighting.__children.Atmosphere = Atmosphere
Lighting.__children.SunRays = SunRays
local Camera = inst("Camera", {})
local Workspace = inst("Workspace", { CurrentCamera = Camera })
_G.game = { GetService = function(_, n) if n == "Lighting" then return Lighting end return Workspace end }
_G.Instance = { new = function(cn) local o = inst(cn, { Enabled = true, TintColor = Color3.new(1, 1, 1), Saturation = 0, Contrast = 0 }) return o end }
_G.task = { spawn = function(fn) fn() end }
return { Lighting = Lighting, Atmosphere = Atmosphere, SunRays = SunRays, Color3 = Color3 }
