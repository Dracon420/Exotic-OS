#!/usr/bin/env bash
# Exotic OS nightly clean restart (cron: 0 4 * * *). Hardened 2026-07-16.
# Clears memory creep and any wedged renderer. Uses SIGKILL + Singleton-lock
# removal so a stuck browser proc can't survive and block the relaunch.
# Crash recovery between restarts is handled by kiosk-watchdog.sh.
#   0 4 * * * /home/exoticos/kiosk-restart.sh >/dev/null 2>&1
export DISPLAY=:0
export XAUTHORITY=/home/exoticos/.Xauthority
killall -9 chromium chromium-browser chrome_crashpad_handler 2>/dev/null
sleep 4
for p in $(pgrep -x chromium); do kill -9 "$p" 2>/dev/null; done
rm -f /home/exoticos/.config/chromium/Singleton* 2>/dev/null
: > /home/exoticos/kiosk.log
setsid bash /home/exoticos/kiosk.sh </dev/null >/home/exoticos/kiosk.log 2>&1 &
