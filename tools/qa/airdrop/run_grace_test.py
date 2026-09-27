"""Runs tools/qa/airdrop/handoff_grace_test.luau against the real
src/client/AirdropStyle.luau with minimal stubs (Luau CLI `luau` on PATH)."""
import pathlib
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[3]
STUBS = """
local services = { ReplicatedStorage = { FindFirstChild = function() return nil end }, Workspace = { GetAttribute = function() return nil end } }
game = { GetService = function(_, n) return services[n] or {} end }
local V = {}
V.__index = function(v, k)
	if k == "Magnitude" then return math.sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z) end
	if k == "Unit" then local m = math.sqrt(v.X * v.X + v.Y * v.Y + v.Z * v.Z); return Vector3.new(v.X / m, v.Y / m, v.Z / m) end
end
V.__mul = function(a, b) if type(b) == "number" then return Vector3.new(a.X * b, a.Y * b, a.Z * b) end return Vector3.new(b.X * a, b.Y * a, b.Z * a) end
Vector3 = { new = function(x, y, z) return setmetatable({ X = x or 0, Y = y or 0, Z = z or 0 }, V) end }
Color3 = { fromRGB = function() return {} end, new = function() return {} end }
local STYLE = [=====[%s]=====]
local style = assert(loadstring(STYLE, "AirdropStyle"))()
function require(_) return style end
"""


def main() -> int:
    style = (ROOT / "src/client/AirdropStyle.luau").read_text()
    test = (ROOT / "tools/qa/airdrop/handoff_grace_test.luau").read_text()
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False) as fh:
        fh.write(STUBS % style)
        fh.write(test)
        path = fh.name
    out = subprocess.run(["luau", path], capture_output=True, text=True)
    sys.stdout.write(out.stdout + out.stderr)
    return 0 if "ALL PASS" in out.stdout else 1


if __name__ == "__main__":
    sys.exit(main())
