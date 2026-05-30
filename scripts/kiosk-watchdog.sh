#!/usr/bin/env bash
# Kiosk watchdog (cron every 2 min):
#  1) relaunch if Chromium fully exited
#  2) detect a renderer crash ("Aw, Snap!") via a fresh Chromium crash dump and
#     restart within ~2 min (the sad-tab can't be detected by title/process).
#   */2 * * * * /home/exoticos/kiosk-watchdog.sh >/dev/null 2>&1
export DISPLAY=:0
export XAUTHORITY=/home/exoticos/.Xauthority
CR="/home/exoticos/.config/chromium/Crash Reports"
relaunch() {
  pkill chromium 2>/dev/null
  sleep 4
  rm -f /home/exoticos/.config/chromium/Singleton* 2>/dev/null
  setsid bash /home/exoticos/kiosk.sh </dev/null >/home/exoticos/kiosk.log 2>&1 &
}
if ! pgrep -x chromium >/dev/null; then
  setsid bash /home/exoticos/kiosk.sh </dev/null >/home/exoticos/kiosk.log 2>&1 &
  exit 0
fi
if find "$CR" -name '*.dmp' -mmin -3 2>/dev/null | grep -q .; then
  relaunch
fi
