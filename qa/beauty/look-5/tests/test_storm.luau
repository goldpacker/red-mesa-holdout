local H = require("./harness")
local Storm = require("./PostFxStorm")
local L, A, R = H.Lighting, H.Atmosphere, H.SunRays
local pass, fail = 0, 0
local function check(name, ok) if ok then pass += 1 else fail += 1; print("FAIL " .. name) end end
local function near(a, b) if type(a) == "number" then return math.abs(a - b) < 1e-4 end return math.abs(a.R-b.R)<1e-3 and math.abs(a.G-b.G)<1e-3 and math.abs(a.B-b.B)<1e-3 end
local snapshot = function()
	return { B = L.Brightness, E = L.ExposureCompensation, S = L.ShadowSoftness, OA = L.OutdoorAmbient, D = A.Density, O = A.Offset, Hz = A.Haze, G = A.Glare, C = A.Color, RI = R.Intensity }
end
Storm.start()
local base = snapshot()
-- 0 does nothing
Storm.update(0, "Sunset")
check("zero leaves values", near(L.Brightness, base.B) and near(A.Density, base.D))
-- full storm
Storm.update(1, "Sunset")
check("storm dims sun x0.6", near(L.Brightness, base.B * 0.6))
check("storm density 0.32", near(A.Density, 0.32))
check("storm offset 0.24", near(A.Offset, 0.24))
check("storm haze +1.2", near(A.Haze, base.Hz + 1.2))
check("storm glare 0", near(A.Glare, 0))
check("storm rays 0", near(R.Intensity, 0))
check("storm shadows soft", near(L.ShadowSoftness, 0.75))
-- half storm
Storm.update(0.5, "Sunset")
check("half density", near(A.Density, (base.D + 0.32) / 2))
check("half brightness", near(L.Brightness, base.B * (1 + (0.6 - 1) * 0.5)))
-- the server moves a property mid-storm (retry snap): base follows, blend re-applies
A.Density = 0.3 -- replicated server value (write not from the module)
Storm.update(0.5, "Sunset") -- same amount; dirty flag forces re-blend
check("server change re-blended", near(A.Density, (0.3 + 0.32) / 2))
L.Brightness = 3.0
Storm.update(0.5, "Sunset")
check("server brightness re-blended", near(L.Brightness, 3.0 * (1 + (0.6 - 1) * 0.5)))
-- clear: exact server values come back
Storm.update(0, "Sunset")
check("restore density = server's new 0.3", near(A.Density, 0.3))
check("restore brightness = server's new 3.0", near(L.Brightness, 3.0))
check("restore haze", near(A.Haze, base.Hz))
check("restore glare", near(A.Glare, base.G))
check("restore rays", near(R.Intensity, base.RI))
check("restore offset", near(A.Offset, base.O))
check("restore ambient", near(L.OutdoorAmbient, base.OA))
-- after clearing, server changes simply stick (nothing written)
A.Haze = 2.2
Storm.update(0, "Sunset")
check("no override after clear", near(A.Haze, 2.2))
-- an unknown preset name falls back to the afternoon storm look
L.Brightness = 1.5
Storm.update(1, "NoSuchPreset")
check("fallback storm sun x0.55", near(L.Brightness, 1.5 * 0.55))
Storm.update(0, "NoSuchPreset")
check("fallback restore", near(L.Brightness, 1.5))
-- ambient brightness preserved (hue shift, same luminance x gain)
Storm.update(1, "Afternoon")
local function lum(c) return 0.2126*c.R+0.7152*c.G+0.0722*c.B end
check("ambient luminance kept x1.12", math.abs(lum(L.OutdoorAmbient) - lum(base.OA) * 1.12) < 0.01)
Storm.update(0, "Afternoon")
print(string.format("PostFxStorm offline: %d pass, %d fail", pass, fail))
