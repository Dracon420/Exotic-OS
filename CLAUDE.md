# Exotic OS — Claude architectural rules

These rules apply to every file in this repository. Do not deviate without an explicit instruction in the session.

## Dashboard canvas

The Lovelace dashboard is hard-coded to **780×460 px**. Never use viewport units (`vw`, `vh`, `dvw`, `dvh`, `%` of viewport). All sizing must use absolute `px` values or card-internal relative units.

## button-card JS templates

Every JavaScript template that reads sensor state must use a failsafe ternary so a missing or unavailable entity returns `'--'` rather than throwing or rendering `undefined`/`null`:

```js
var t = states['sensor.my_sensor'];
return t ? t.state : '--';
```

Do not chain optional access (`?.`) alone — always provide the `'--'` fallback explicitly.

## button-card name field

Never inject raw HTML into a button-card `name:` field. Use `label:` + a custom `card_mod` style if rich markup is needed. Injecting HTML into `name:` breaks card rendering in certain HA versions and is a template-injection risk.

## View type

All top-level Lovelace views use `type: panel`. Never use the default grid view.

## Color palette

### Per-animal accent colors

| Animal | Color |
|---|---|
| Cora | `#B026FF` |
| Sonic | `#39FF14` |
| Motley | `#FF6B00` |
| Confused Spider | `#00BFFF` |

Use each animal's accent color for: card borders, icon color when active, and any highlight element specific to that animal's card.

### System colors

| Role | Value |
|---|---|
| System cyan (alerts, headings) | `#00E5FF` |
| Primary background | `#050505` |
| Card / secondary background | `#0f0f0f` |

Do not introduce additional colors without updating this table.

## ESPHome configs

- One `.yaml` file per physical device, named after the node (e.g. `cora-node.yaml`).
- Keep `substitutions:` at the top of every config for device name and IP.
- All sensors must publish to MQTT with a stable topic path: `exotic-os/<node>/<sensor>`.

## HA configuration snippets

- Automations and scripts live in `ha-config/automations/` and `ha-config/scripts/` as standalone YAML files, one logical unit per file.
- Use `!include` in the main HA config; do not paste inline into `configuration.yaml`.

## Shell scripts

- Target `bash`, not `sh`. First line: `#!/usr/bin/env bash`.
- `set -euo pipefail` at the top of every script.
- Scripts must be idempotent where possible.
