#!/usr/bin/env bash
# Exotic OS kiosk launcher (BTT Pi v2 -> /exotic-os/home).
#
# NOTE: --memory-pressure-off is deliberately OMITTED. That flag stops Chromium
# reclaiming memory; on the 2GB Pi the dashboard renderer grew to ~876MB over
# ~4.5h and was OOM-killed overnight ("Aw, Snap!" Error code 11). Leaving it out
# lets Chromium self-manage memory.
set -euo pipefail
export DISPLAY=:0
export XAUTHORITY=/home/exoticos/.Xauthority
# Disable X screen-blanking / DPMS so the branded screensaver view shows instead
# of a black screen on idle.
xset s off; xset s noblank; xset -dpms
exec chromium \
  --noerrdialogs --disable-infobars --disable-session-crashed-bubble \
  --kiosk --force-dark-mode --disable-dev-shm-usage \
  --renderer-process-limit=1 --disable-gpu \
  http://192.168.68.63:8123/exotic-os/home
