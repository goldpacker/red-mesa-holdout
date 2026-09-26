#!/usr/bin/env bash
# Build one or more assets in headless Blender.  tools/assets/build.sh SupplyCrate [Tank ...]
set -euo pipefail
cd "$(dirname "$0")/../.."
BLENDER=${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}
mkdir -p logs/assets
for name in "$@"; do
	echo "== building $name"
	"$BLENDER" -b --factory-startup -P tools/assets/build.py -- "$name" ${BUILD_ARGS:-} > "logs/assets/$name.log" 2>&1 || { tail -30 "logs/assets/$name.log"; exit 1; }
	grep '\[rmh' "logs/assets/$name.log" | tail -40
done
