#!/usr/bin/env bash
# Cooperative mutex for the single Roblox Studio instance shared by agents.
#   tools/studio-lock.sh acquire <owner>   # waits its turn in a FIFO queue (max 40 min per call)
#   tools/studio-lock.sh release <owner>
#   tools/studio-lock.sh refresh <owner>   # restart the stale clock while still holding it
#   tools/studio-lock.sh status
# Hold the lock for any start_stop_play / playtest / screen_capture session
# and release it (after stopping play) as soon as you are done. Locks older
# than 15 minutes are considered stale and may be broken.
# Waiters are served in arrival order. If your acquire call is interrupted
# (e.g. a tool timeout), just run it again: your place in the queue is kept
# for 15 minutes, and you're only skipped while you aren't polling.
set -u
cd "$(dirname "$0")/.."
LOCK=.studio-lock
QUEUE=.studio-lock-queue
ACTIVE=20     # a waiter that polled within this many seconds is in line
ABANDON=900   # tickets untouched this long are dropped
cmd=${1:-status}
owner=${2:-unknown}

# True when $owner is the earliest active waiter.
my_turn() {
	local now best="" best_t="" t m since name
	now=$(date +%s)
	for t in "$QUEUE"/*; do
		[ -f "$t" ] || continue
		m=$(stat -f %m "$t")
		if [ $((now - m)) -gt "$ABANDON" ]; then rm -f "$t"; continue; fi
		[ $((now - m)) -gt "$ACTIVE" ] && continue
		read -r since < "$t" || true
		[ -n "${since:-}" ] || continue
		name=$(basename "$t")
		if [ -z "$best" ] || [ "$since" -lt "$best_t" ] || { [ "$since" -eq "$best_t" ] && [[ "$name" < "$best" ]]; }; then
			best=$name
			best_t=$since
		fi
	done
	[ "$best" = "$owner" ]
}

case "$cmd" in
acquire)
	if [ -f "$LOCK/owner" ] && [ "$(cut -d' ' -f1 "$LOCK/owner")" = "$owner" ]; then
		echo "already held by $owner"
		exit 0
	fi
	mkdir -p "$QUEUE"
	ticket="$QUEUE/$owner"
	[ -f "$ticket" ] || date +%s > "$ticket"
	for _ in $(seq 1 480); do
		touch "$ticket"
		if my_turn && mkdir "$LOCK" 2>/dev/null; then
			echo "$owner $(date +%s)" > "$LOCK/owner"
			rm -f "$ticket"
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
	echo "holder: $(cat "$LOCK/owner" 2>/dev/null || echo free)"
	for t in "$QUEUE"/*; do
		[ -f "$t" ] && echo "waiting: $(basename "$t") since $(cat "$t") (polled $(( $(date +%s) - $(stat -f %m "$t") ))s ago)"
	done
	true
	;;
esac
