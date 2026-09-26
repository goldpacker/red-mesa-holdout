#!/usr/bin/env bash
# Build flipbook sheets and single textures (see tools/vfx/README.md).
#   tools/vfx/render.sh DustPuff Fireball     # named outputs
#   tools/vfx/render.sh all                   # everything in sheets/registry.py
#   NO_RENDER=1 tools/vfx/render.sh Fireball  # re-assemble cached frames only
# Volumetric sheets render under a tools/blender-lock.sh slot (released as
# soon as the render ends); assembling, painted sheets and singles need no lock.
set -euo pipefail
cd "$(dirname "$0")/../.."
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
OWNER=${VFX_LOCK_OWNER:-vfx}
mkdir -p logs/vfx

names=("$@")
if [ "${#names[@]}" -eq 0 ]; then
	echo "usage: tools/vfx/render.sh <Name...|all>"; exit 2
fi
if [ "${names[0]}" = all ]; then
	read -r -a names <<< "$(python3 tools/vfx/sheets/registry.py names)"
fi

holding=0
release() { if [ "$holding" = 1 ]; then tools/blender-lock.sh release "$OWNER"; holding=0; fi; }
trap release EXIT INT TERM

for name in "${names[@]}"; do
	method=$(python3 tools/vfx/sheets/registry.py method "$name")
	if [ "$method" = render ] && [ -z "${NO_RENDER:-}" ]; then
		echo "== render $name"
		tools/blender-lock.sh acquire "$OWNER"; holding=1
		if ! "$BLENDER" -b --factory-startup -P tools/vfx/vfx.py -- render "$name" > "logs/vfx/$name.render.log" 2>&1; then
			release; tail -30 "logs/vfx/$name.render.log"; exit 1
		fi
		release
		grep '\[vfx' "logs/vfx/$name.render.log" | tail -3
	fi
	echo "== assemble $name"
	if ! "$BLENDER" -b --factory-startup -P tools/vfx/vfx.py -- assemble "$name" > "logs/vfx/$name.log" 2>&1; then
		tail -30 "logs/vfx/$name.log"; exit 1
	fi
	grep '\[vfx' "logs/vfx/$name.log" | tail -3
done
