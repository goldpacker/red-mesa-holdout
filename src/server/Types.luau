--!strict
-- Shared server-side types. See docs/ARCHITECTURE.md for the contracts.

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
	-- Damage multipliers per weapon id ("MG", "Rocket", "Missile"); missing = 1.
	resist: { [string]: number }?,
	update: (dt: number) -> (),
	die: () -> (),
	distanceToOutpost: () -> number,
	-- Optional: true while the enemy is in its attack range (drives the
	-- off-screen threat arrows). Defaults to false.
	isThreatening: (() -> boolean)?,
	-- Optional: intercepts damage (e.g. boss weak points). Receives the
	-- post-resist amount and the part that was hit (nil for splash);
	-- returns the damage to apply to `health`.
	onDamage: ((amount: number, weapon: string, part: BasePart?) -> number)?,
}

-- Callbacks enemies use to affect the game; provided by GameController.
export type Context = {
	damageOutpost: (amount: number, from: Vector3, heavy: boolean) -> (),
	enemyFired: (enemy: Enemy, attack: string, from: Vector3, to: Vector3) -> (),
	-- Broadcasts a GameEvent to clients (e.g. "JetWarning", "BossUpdate").
	emit: (kind: string, payload: any) -> (),
	-- Spawns another enemy mid-wave (boss escorts). Counts toward the wave.
	spawn: (kind: string, lane: string) -> Enemy?,
	-- Requests a supply crate drop; bias is "Rockets", "Missiles", "Repair" or nil.
	dropCrate: (bias: string?) -> (),
	-- Awards points outside of a normal kill (boss weak points).
	awardPoints: (points: number, position: Vector3, label: string) -> (),
}

-- Module contract for files in server/EnemyTypes/.
export type EnemyType = {
	kind: string,
	spawn: (ctx: Context, lane: string, rng: Random) -> Enemy,
}

return nil
