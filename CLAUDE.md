# Autonomous Roblox Game Development

You are working autonomously on a Roblox game. The full product specification is in `GAME_SPEC.md`.

## Primary objective

Keep working until the game satisfies `GAME_SPEC.md` **and** a complete end-to-end playthrough succeeds.

Do not stop just because individual features are implemented.

## Project layout

| Path                   | Purpose                                         |
| ---------------------- | ----------------------------------------------- |
| `GAME_SPEC.md`         | Product specification (source of truth)        |
| `PROGRESS.md`          | Running progress log (see below)                |
| `DONE.md`              | Final summary, created only on completion       |
| `src/`                 | Game source code                                |
| `assets/blender/`      | Blender source files                            |
| `assets/exported/`     | Exported game-ready assets                      |
| `assets/previews/`     | Rendered asset previews                         |
| `qa/screenshots/`      | Playtest screenshots                            |
| `logs/`                | Console output and playtest logs                |

## Development loop

Repeat until done:

1. Review `GAME_SPEC.md` and `PROGRESS.md`.
2. Pick the highest-priority unfinished requirement.
3. Implement it.
4. Playtest in Roblox Studio.
5. Inspect the console output.
6. Exercise the feature in play.
7. Capture screenshots when visual inspection is useful.
8. Diagnose and fix any problems, then test again.
9. Update `PROGRESS.md`.
10. Commit the working milestone.
11. Move on to the next requirement.

Do not wait for human approval between milestones.

## Progress tracking

Keep `PROGRESS.md` current at all times with:

- completed requirements
- current work
- known bugs
- last successful playtest
- next planned task

## Completion

Create `DONE.md` only when **all** of the following are true:

- every required gameplay feature is present
- the full gameplay loop succeeds from a fresh spawn
- there are no known critical runtime errors
- all major screens and environment areas have been visually inspected
- a final end-to-end playthrough succeeds

`DONE.md` must summarize:

- what was built
- the final playtest result
- known remaining issues
- the final Git commit hash

## If blocked

Do not stop at the first failure. Work through:

1. Diagnose the problem.
2. Inspect logs and game state.
3. Try a different implementation.
4. Simplify the feature while still satisfying `GAME_SPEC.md`.

If you are genuinely blocked by credentials, permissions, or anything else that requires human action, document it clearly in `PROGRESS.md` and continue with other independent work.

## Roblox

- Use the Roblox Studio MCP for inspection and playtesting.
- Keep gameplay logic server-authoritative where appropriate.
- Never publish the game publicly.
- Never spend Robux.
- Never modify unrelated cloud assets.
- Never interact with production experiences.

## Blender

- Drive Blender via Python/CLI where practical.
- Save source files under `assets/blender/`.
- Export game assets to `assets/exported/`.
- Save visual previews to `assets/previews/`.
- Avoid destructive edits to existing manually authored assets.

## Git

- Work only on the current branch.
- Commit after each meaningful working milestone.
- Never force-push.
- Never push to a remote unless explicitly instructed.
