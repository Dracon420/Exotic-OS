# Exotic OS

A smart reptile enclosure monitoring and control system built on [Home Assistant](https://www.home-assistant.io/) and [ESPHome](https://esphome.io/). Designed for reptile keepers who want real peace of mind about their animals' wellbeing — not just a dashboard, but a system that watches, alerts, and acts.

## What it does

Exotic OS ties together temperature, humidity, UVB, and power-state sensors across multiple enclosures into a single, always-on display. Each animal gets its own card with live readings, status indicators, and alert thresholds. The system runs 24/7 on a Raspberry Pi backed by a PiSugar UPS so a power cut doesn't mean a missed alarm.

## Animals

| Name | Species | Accent color |
|---|---|---|
| Cora | Crested gecko | `#B026FF` |
| Sonic | Crested gecko | `#39FF14` |
| Motley | Corn snake | `#FF6B00` |
| Confused Spider | Ball python | `#00BFFF` |

## Repository layout

```
dashboard/          # Home Assistant Lovelace YAML (button-card, layout-card)
esphome/            # ESP32 node configs (.yaml per device)
ha-config/
  automations/      # HA automation snippets
  scripts/          # HA script snippets
scripts/            # Shell scripts (pisugar MQTT bridge, helpers)
docs/               # Project documentation and guides
hardware/           # Bill of materials, wiring diagrams, enclosure specs
```

## Stack

- **Home Assistant** — core platform, automations, alerting
- **ESPHome** — firmware for ESP32 sensor nodes
- **button-card** — custom Lovelace cards for per-animal panels
- **layout-card** — fixed 780×460 px canvas dashboard
- **PiSugar** — UPS HAT for Raspberry Pi; battery state exposed via MQTT bridge

## Design philosophy

- Hard numbers over trends: every card shows the live value, always.
- Failsafe first: sensors that stop reporting surface `--`, never a stale value.
- One glance: the dashboard is designed to be read across the room.

## Getting started

1. Flash your ESP32 nodes with the configs in `esphome/`.
2. Copy `ha-config/` snippets into your HA configuration and reload.
3. Import `dashboard/` YAML into a new Lovelace view (raw config editor).
4. Run `scripts/pisugar-mqtt.sh` as a service on the Pi for battery telemetry.

See `docs/` for wiring guides and a full hardware BOM.
