#!/usr/bin/env bash
# Cooperative mutex for the single Roblox Studio instance shared by agents.
#   tools/studio-lock.sh acquire <owner>   # blocks until acquired (max 20 min wait)
#   tools/studio-lock.sh release <owner>
#   tools/studio-lock.sh refresh <owner>   # restart the stale clock while still holding it
#   tools/studio-lock.sh status
# Hold the lock for any start_stop_play / playtest / screen_capture session
# and release it (after stopping play) as soon as you are done. Locks older
# than 15 minutes are considered stale and may be broken.
set -u
cd "$(dirname "$0")/.."
LOCK=.studio-lock
cmd=${1:-status}
owner=${2:-unknown}
case "$cmd" in
acquire)
	for _ in $(seq 1 240); do
		if mkdir "$LOCK" 2>/dev/null; then
			echo "$owner $(date +%s)" > "$LOCK/owner"
			echo "acquired by $owner"
			exit 0
		fi
		if [ -f "$LOCK/owner" ]; then
			read -r holder since < "$LOCK/owner"
			age=$(( $(date +%s) - since ))
			if [ "$age" -gt 900 ]; then
				echo "breaking stale lock held by $holder (${age}s)"
				rm -rf "$LOCK"
				continue
			fi
		fi
		sleep 5
	done
	echo "timed out waiting for studio lock: $(cat "$LOCK/owner" 2>/dev/null)"
	exit 1
	;;
release)
	if [ -f "$LOCK/owner" ] && [ "$(cut -d' ' -f1 "$LOCK/owner")" = "$owner" ]; then
		rm -rf "$LOCK"
		echo "released by $owner"
	else
		echo "not held by $owner: $(cat "$LOCK/owner" 2>/dev/null || echo free)"
	fi
	;;
refresh)
	# Restart the 15-minute stale clock during a long session you still hold.
	if [ -f "$LOCK/owner" ] && [ "$(cut -d' ' -f1 "$LOCK/owner")" = "$owner" ]; then
		echo "$owner $(date +%s)" > "$LOCK/owner"
		echo "refreshed by $owner"
	else
		echo "not held by $owner: $(cat "$LOCK/owner" 2>/dev/null || echo free)"
		exit 1
	fi
	;;
status)
	cat "$LOCK/owner" 2>/dev/null || echo free
	;;
esac
