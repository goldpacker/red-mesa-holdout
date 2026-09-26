#!/usr/bin/env bash
# Syntax-checks every Luau file under src/ (Roblox globals aren't modelled,
# so only SyntaxError lines are reported). Exit 1 on any syntax error.
set -u
cd "$(dirname "$0")/.."
out=$(find src -name '*.luau' -print0 | xargs -0 luau-analyze 2>&1 | grep 'SyntaxError' || true)
if [ -n "$out" ]; then
	echo "$out"
	exit 1
fi
echo "check: no syntax errors in $(find src -name '*.luau' | wc -l | tr -d ' ') files"
