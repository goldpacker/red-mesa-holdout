#!/usr/bin/env python3
"""Offline test of src/shared/Wind.luau (VFX-4) with the `luau` CLI.

    python3 tools/vfx/qa/wind_test.py

Runs the real module source under a small Vector3/Workspace stub and checks
the contract other workstreams rely on (docs/FACELIFT_TEAM.md, "Wind"):
  * Wind.at(t) returns (Vector3 velocity, strength, gust), flat (Y = 0);
  * deterministic: the same t gives the same wind (a second, fresh copy of
    the module agrees to the last bit);
  * strength stays in ~0.75..2.3, gust in 0..1, mean strength ~1.1;
  * smooth: strength never changes faster than 1.5 per second;
  * the direction stays within 15 degrees of DIRECTION;
  * gusts are present 15..40 % of the time (gust > 0.3);
  * the client storm overlay: setStorm(1, dir, 2.6) turns the wind to `dir`
    and multiplies strength by 2.6; setStorm(0) restores Wind.base exactly.
Exit status 0 = all pass.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = (ROOT / "src/shared/Wind.luau").read_text().replace("--!strict", "")

HARNESS = r'''
local V = {}
V.__index = function(self, k)
	if k == "Unit" then
		local m = math.sqrt(self.X ^ 2 + self.Y ^ 2 + self.Z ^ 2)
		return setmetatable({ X = self.X / m, Y = self.Y / m, Z = self.Z / m }, V)
	elseif k == "Magnitude" then
		return math.sqrt(self.X ^ 2 + self.Y ^ 2 + self.Z ^ 2)
	elseif k == "Lerp" then
		return function(a, b, t)
			return setmetatable({ X = a.X + (b.X - a.X) * t, Y = a.Y + (b.Y - a.Y) * t, Z = a.Z + (b.Z - a.Z) * t }, V)
		end
	end
	return nil
end
V.__mul = function(a, k)
	return setmetatable({ X = a.X * k, Y = a.Y * k, Z = a.Z * k }, V)
end
local Vector3 = { new = function(x, y, z) return setmetatable({ X = x, Y = y, Z = z }, V) end }
local game = { GetService = function() return { GetServerTimeNow = function() return 0 end } end }
local function load()
	local fn = assert(loadstring(SOURCE))
	setfenv(fn, setmetatable({ Vector3 = Vector3, game = game }, { __index = getfenv(1) }))
	return fn()
end

local W, W2 = load(), load()
local fails = 0
local function check(ok, msg)
	if not ok then
		fails += 1
		print("FAIL " .. msg)
	end
end

local n, sum, lo, hi, gusty, maxRate = 0, 0, math.huge, -math.huge, 0, 0
local maxYaw, prev = 0, nil
local baseYaw = math.deg(math.atan2(W.DIRECTION.Z, W.DIRECTION.X))
local T0 = 1790500000
for i = 0, 36000 do -- one hour at 10 Hz
	local t = T0 + i * 0.1
	local v, s, g = W.at(t)
	local v2, s2, g2 = W2.at(t)
	check(v.X == v2.X and v.Z == v2.Z and s == s2 and g == g2, "deterministic at t=" .. t)
	check(v.Y == 0, "flat velocity")
	check(g >= 0 and g <= 1, "gust in 0..1")
	check(math.abs(v.Magnitude - W.SPEED * s) < 1e-6, "|velocity| = SPEED x strength")
	n += 1
	sum += s
	lo = math.min(lo, s)
	hi = math.max(hi, s)
	if g > 0.3 then
		gusty += 1
	end
	if prev then
		maxRate = math.max(maxRate, math.abs(s - prev) / 0.1)
	end
	prev = s
	local yaw = math.deg(math.atan2(v.Z, v.X))
	maxYaw = math.max(maxYaw, math.abs(yaw - baseYaw))
end
local mean = sum / n
check(lo >= 0.75 and hi <= 2.3, string.format("strength range %.2f..%.2f", lo, hi))
check(mean > 1.0 and mean < 1.25, string.format("mean strength %.2f", mean))
check(maxRate < 1.5, string.format("max strength change %.2f/s", maxRate))
check(maxYaw <= 15, string.format("max veer %.1f deg", maxYaw))
local share = gusty / n
check(share > 0.15 and share < 0.4, string.format("gusty share %.2f", share))

-- storm overlay
local t = T0 + 123.4
local vb, sb = W.base(t)
local dir = Vector3.new(0.3, 0, 0.95).Unit
W.setStorm(1, dir, 2.6)
local vs, ss = W.at(t)
check(math.abs(ss - sb * 2.6) < 1e-9, "storm strength x2.6")
check(math.abs(vs.Unit.X - dir.X) < 1e-9 and math.abs(vs.Unit.Z - dir.Z) < 1e-9, "storm direction")
W.setStorm(0)
local v0, s0 = W.at(t)
check(v0.X == vb.X and v0.Z == vb.Z and s0 == sb, "storm cleared = base")

print(string.format("wind: %d samples, strength %.2f..%.2f mean %.2f, gusty %.0f%%, max change %.2f/s, max veer %.1f deg", n, lo, hi, mean, share * 100, maxRate, maxYaw))
print(if fails == 0 then "PASS" else ("FAILED " .. fails))
'''


def main():
    body = "local SOURCE = [==[" + SRC + "]==]\n" + HARNESS
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False) as f:
        f.write(body)
        path = f.name
    out = subprocess.run(["luau", path], capture_output=True, text=True)
    sys.stdout.write(out.stdout + out.stderr)
    ok = out.returncode == 0 and out.stdout.strip().endswith("PASS")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
