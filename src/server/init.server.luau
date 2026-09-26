-- Server entry point for Red Mesa Holdout.
local WorldBuilder = require(script.WorldBuilder)
local GameController = require(script.GameController)

WorldBuilder.build()
GameController.start()
print("[RedMesa] server ready")
