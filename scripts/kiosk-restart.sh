#!/usr/bin/env bash
# Full nightly restart of the kiosk: kills Chromium and relaunches it, resetting
# any process-level memory the hourly soft-refresh can't reclaim. Intra-day
# memory is handled by the HA "Kiosk hourly refresh" automation; crash recovery
# is handled by kiosk-watchdog.sh. Cron: once nightly at 04:00.
#   0 4 * * * /home/exoticos/kiosk-restart.sh >/dev/null 2>&1
export DISPLAY=:0
export XAUTHORITY=/home/exoticos/.Xauthority
pkill chromium 2>/dev/null || true
sleep 4
setsid bash /home/exoticos/kiosk.sh </dev/null >/home/exoticos/kiosk.log 2>&1 &
