#!/usr/bin/env bash
# Runs a Look tool on Blender's bundled Python (numpy available).
#   tools/ui/py.sh tools/ui/look_textures.py
set -eu
BLENDER_PY=${BLENDER_PY:-$(ls -d /Applications/Blender.app/Contents/Resources/*/python/bin/python3* 2>/dev/null | head -1)}
exec "$BLENDER_PY" "$@"
