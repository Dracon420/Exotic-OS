#!/usr/bin/env bash
# Exotic OS kiosk watchdog (cron every 2 min). Hardened 2026-07-16.
#   */2 * * * * /home/exoticos/kiosk-watchdog.sh >/dev/null 2>&1
# Recovers from three failure modes:
#   1) Chromium fully exited
#   2) Chromium WEDGED but alive -- an orphaned browser proc (state S) holding
#      the Singleton profile lock with a zombie child, seen as an abnormally
#      low process count. SIGTERM won't clear it, so relaunch uses SIGKILL.
#   3) Renderer crash ("Aw, Snap!") -> fresh crash dump.
export DISPLAY=:0
export XAUTHORITY=/home/exoticos/.Xauthority
CR="/home/exoticos/.config/chromium/Crash Reports"

# Single-writer: never let two watchdog runs act at once (that race spawned the
# duplicate Chromium instances that used to peg CPU and freeze the Pi).
exec 9>/tmp/kiosk-wd.lock
flock -n 9 || exit 0

relaunch() {
  killall -9 chromium chromium-browser chrome_crashpad_handler 2>/dev/null
  sleep 4
  for p in $(pgrep -x chromium); do kill -9 "$p" 2>/dev/null; done   # kill stragglers
  rm -f /home/exoticos/.config/chromium/Singleton* 2>/dev/null       # release lock
  : > /home/exoticos/kiosk.log
  setsid bash /home/exoticos/kiosk.sh </dev/null >/home/exoticos/kiosk.log 2>&1 &
}

n=$(pgrep -x chromium | wc -l)

# 1) fully exited
if [ "$n" -eq 0 ]; then relaunch; exit 0; fi

# 2) wedged: zombie chromium child, or half-dead low proc count (healthy ~9-11).
#    Re-check after 6s so a normal startup transient isn't mistaken for a wedge.
zomb=$(ps -eo stat,comm | awk '$2=="chromium" && $1 ~ /Z/{c++} END{print c+0}')
if [ "$zomb" -gt 0 ]; then relaunch; exit 0; fi
if [ "$n" -lt 4 ]; then
  sleep 6
  n2=$(pgrep -x chromium | wc -l)
  if [ "$n2" -lt 4 ]; then relaunch; exit 0; fi
fi

# 3) renderer crash dump in the last 3 min
if find "$CR" -name '*.dmp' -mmin -3 2>/dev/null | grep -q .; then relaunch; fi
