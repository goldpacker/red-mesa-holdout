#!/usr/bin/env bash
# Runs a script on Blender's bundled Python (numpy + OpenImageIO available).
#   tools/env/py.sh tools/env/terrain_textures.py [args]
set -eu
BLENDER_PY=${BLENDER_PY:-$(ls -d /Applications/Blender.app/Contents/Resources/*/python/bin/python3* 2>/dev/null | head -1)}
exec "$BLENDER_PY" "$@"
