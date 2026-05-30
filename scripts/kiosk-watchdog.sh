#!/usr/bin/env bash
# Relaunch the kiosk if Chromium has fully exited. Cron: every 2 minutes.
#   */2 * * * * /home/exoticos/kiosk-watchdog.sh >/dev/null 2>&1
export DISPLAY=:0
export XAUTHORITY=/home/exoticos/.Xauthority
pgrep -x chromium >/dev/null && exit 0
setsid bash /home/exoticos/kiosk.sh </dev/null >/tmp/kiosk.log 2>&1 &
