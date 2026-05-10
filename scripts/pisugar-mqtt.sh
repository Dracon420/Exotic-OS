#!/usr/bin/env bash
set -euo pipefail

# Polls the PiSugar2 Pro UPS over its Unix socket and publishes battery
# state to MQTT so Home Assistant can track power status and SoC.
#
# Requires: mosquitto_pub, nc (netcat)
# Run as a systemd service on the Raspberry Pi host.

MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
MQTT_TOPIC_BASE="${MQTT_TOPIC_BASE:-exotic-os/pisugar}"
PISUGAR_SOCKET="${PISUGAR_SOCKET:-/tmp/pisugar_server}"
POLL_INTERVAL="${POLL_INTERVAL:-30}"

query() {
    echo "$1" | nc -q 1 -U "$PISUGAR_SOCKET" 2>/dev/null | sed "s/^$1: //"
}

publish() {
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$1" -m "$2" -r
}

echo "PiSugar MQTT bridge starting (topic base: $MQTT_TOPIC_BASE)"

while true; do
    battery=$(query "get battery")
    charging=$(query "get battery_charging")
    voltage=$(query "get battery_voltage")
    power_plugged=$(query "get battery_power_plugged")

    publish "${MQTT_TOPIC_BASE}/battery"      "${battery}"
    publish "${MQTT_TOPIC_BASE}/charging"     "${charging}"
    publish "${MQTT_TOPIC_BASE}/voltage"      "${voltage}"
    publish "${MQTT_TOPIC_BASE}/power_plugged" "${power_plugged}"

    sleep "$POLL_INTERVAL"
done
