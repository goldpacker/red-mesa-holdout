#!/usr/bin/env bash
# Counting semaphore for heavy headless Blender jobs (Cycles bakes/renders,
# fluid sims) shared by agents; see docs/FACELIFT_TEAM.md.
#   tools/blender-lock.sh acquire <owner>   # blocks until a slot is free (max 30 min wait)
#   tools/blender-lock.sh release <owner>
#   tools/blender-lock.sh status
# Hold a slot only while a heavy job runs. Slots older than
# BLENDER_LOCK_STALE seconds (default 60 min) are considered stale.
set -u
cd "$(dirname "$0")/.."
DIR=.blender-lock
SLOTS=${BLENDER_LOCK_SLOTS:-2}
STALE=${BLENDER_LOCK_STALE:-3600}
cmd=${1:-status}
owner=${2:-unknown}
mkdir -p "$DIR"
case "$cmd" in
acquire)
	for _ in $(seq 1 360); do
		for i in $(seq 1 "$SLOTS"); do
			slot="$DIR/slot-$i"
			if mkdir "$slot" 2>/dev/null; then
				echo "$owner $(date +%s)" > "$slot/owner"
				echo "acquired slot $i by $owner"
				exit 0
			fi
			if [ -f "$slot/owner" ]; then
				read -r holder since < "$slot/owner"
				age=$(( $(date +%s) - since ))
				if [ "$age" -gt "$STALE" ]; then
					echo "breaking stale slot $i held by $holder (${age}s)"
					rm -rf "$slot"
				fi
			fi
		done
		sleep 5
	done
	echo "timed out waiting for a blender slot"
	exit 1
	;;
release)
	for i in $(seq 1 "$SLOTS"); do
		slot="$DIR/slot-$i"
		if [ -f "$slot/owner" ] && [ "$(cut -d' ' -f1 "$slot/owner")" = "$owner" ]; then
			rm -rf "$slot"
			echo "released slot $i by $owner"
			exit 0
		fi
	done
	echo "no slot held by $owner"
	;;
status)
	for i in $(seq 1 "$SLOTS"); do
		echo "slot $i: $(cat "$DIR/slot-$i/owner" 2>/dev/null || echo free)"
	done
	;;
esac
