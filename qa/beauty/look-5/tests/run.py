#!/usr/bin/env python3
"""LOOK-5 offline test of client/PostFxStorm (the StormAmount blend):
mocks Color3, float-rounded instance properties and Changed signals, then runs
test_storm.luau against the live module source twice, with immediate and
with deferred signal behaviour.   python3 qa/beauty/look-5/tests/run.py"""
import pathlib
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
h = (HERE / "harness.luau").read_text()
h = h.replace("_G.Color3 = Color3\n", "").replace("local realTypeof = typeof\n_G.typeof = function(v)", "local realTypeof = typeof\nlocal typeof = function(v)")
h = h.replace("_G.game = {", "local game = {").replace("_G.Instance = {", "local Instance = {").replace("_G.task = {", "local task = {")
h = h.replace("return { Lighting = Lighting, Atmosphere = Atmosphere, SunRays = SunRays, Color3 = Color3 }",
              "local H = { Lighting = Lighting, Atmosphere = Atmosphere, SunRays = SunRays, Color3 = Color3 }")
m = (ROOT / "src" / "client" / "PostFxStorm.luau").read_text().replace("--!strict", "")
m = "local Storm = (function()\n" + m + "\nend)()\n"
t = (HERE / "test_storm.luau").read_text().replace('local H = require("./harness")\nlocal Storm = require("./PostFxStorm")\n', "")
hd = h.replace("\tfunction s:Fire(...) for _, fn in self.fns do fn(...) end end",
               "\tfunction s:Fire(...) local args = table.pack(...) table.insert(QUEUE, function() for _, fn in self.fns do fn(table.unpack(args, 1, args.n)) end end) end")
hd = "local QUEUE = {}\nlocal function flush() local q = QUEUE QUEUE = {} for _, f in q do f() end end\n" + hd
td = "\n".join(("flush(); " + ln) if ln.startswith(("Storm.update(", "check(")) else ln for ln in t.split("\n"))
with tempfile.TemporaryDirectory() as tmp:
    for name, src in (("immediate", h + "\n" + m + "\n" + t), ("deferred", hd + "\n" + m + "\n" + td)):
        f = pathlib.Path(tmp) / f"{name}.luau"
        f.write_text(src)
        out = subprocess.run(["luau", str(f)], capture_output=True, text=True)
        print(f"{name} signals: {(out.stdout + out.stderr).strip()}")
