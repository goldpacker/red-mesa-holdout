--!strict
-- Shared server-side types.

export type Enemy = {
	id: number,
	kind: string,
	model: Model,
	root: BasePart,
	health: number,
	maxHealth: number,
	dead: boolean,
	points: number,
	isAir: boolean,
	update: (dt: number) -> (),
	die: () -> (),
	distanceToOutpost: () -> number,
}

-- Callbacks enemies use to affect the game; provided by GameController.
export type Context = {
	damageOutpost: (amount: number, from: Vector3, heavy: boolean) -> (),
	enemyFired: (enemy: Enemy, attack: string, from: Vector3, to: Vector3) -> (),
}

return nil
