#!/usr/bin/env bash
# Clean periodic restart: clears Chromium memory creep and recovers a crashed
# renderer ("Aw, Snap!"), which cannot be detected by window title (it persists)
# or process state (the sad-tab keeps a renderer). Cron: every 2 hours.
#   0 */2 * * * /home/exoticos/kiosk-restart.sh >/dev/null 2>&1
export DISPLAY=:0
export XAUTHORITY=/home/exoticos/.Xauthority
pkill chromium 2>/dev/null || true
sleep 4
setsid bash /home/exoticos/kiosk.sh </dev/null >/tmp/kiosk.log 2>&1 &
