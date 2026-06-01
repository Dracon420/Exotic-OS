# Exotic OS — Enclosure Manager

No-code **Add / Edit / Delete enclosure** for the Home Assistant kiosk. Tap
**Add Enclosure** on the home screen → a dropdown form (browser_mod popup) →
a fully styled enclosure dashboard is generated, with **PID heat control as a
toggle**. Everything is driven from a single registry file; nothing requires the
HA admin UI.

## How it works

```
registry  (exotic_os/enclosures.yaml)   <-- single source of truth
   │
   ▼  generate
exotic_os_lib.py  (plain CPython: dict-builders + file I/O + PID package gen)
   │
   ▼  imported by
pyscript/exotic_os.py  (thin wrapper: @service + HA service calls)
   │
   ├─ writes  dashboards/exotic-os.yaml   (one yaml-mode dashboard, all views)
   ├─ writes  packages/<slug>_pid.yaml    (PID helpers + 5 automations, per enclosure)
   └─ calls   *.reload + browser_mod.refresh   (no HA restart needed)
```

- **Add/Edit/Delete** mutate the registry, then **regenerate** the dashboard +
  PID and refresh the kiosk live (no restart).
- **pyscript** restricts builtins like `open()` inside script functions, so all
  file I/O lives in the imported plain module `exotic_os_lib.py`; the wrapper
  only does HA service calls.
- Dashboard is a **single yaml-mode dashboard** (`/exotic-os`) with one view per
  enclosure (`/exotic-os/<slug>`, `+ -cam`, `+ -heat`) — yaml-mode files are
  re-read on browser refresh, so edits apply with zero restarts.
- The **form** is a browser_mod popup backed by `input_*` helper entities
  (`packages_eos_form.yaml`). `enclosure_form_init` repopulates the sensor/relay
  dropdowns from live entities and prefills (edit) or applies species presets
  (add). Picking a species auto-fills accent color + setpoint.

## Services

| Service | Purpose |
|---|---|
| `pyscript.enclosure_generate` | Rebuild the dashboard from the registry |
| `pyscript.enclosure_save(slug?, **fields)` | Upsert one enclosure (+/- PID) |
| `pyscript.enclosure_delete(slug)` | Remove an enclosure (+ its PID) |
| `pyscript.enclosure_form_init(mode, slug?)` | Populate/prefill the form (called by the buttons) |
| `pyscript.enclosure_submit_form()` | Read the form helpers and save (Save button) |

## Install (on a fresh HA)

1. Install **pyscript** (HACS, or drop into `custom_components/pyscript/`).
2. `configuration.yaml`:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   pyscript:
     allow_all_imports: true
     hass_is_global: true
   lovelace:
     mode: storage
     dashboards:
       exotic-os:
         mode: yaml
         title: Exotic OS
         icon: mdi:orbit
         show_in_sidebar: true
         filename: dashboards/exotic-os.yaml
   ```
3. Deploy files:
   - `exotic_os_lib.py`            → `/config/exotic_os_lib.py`
   - `pyscript_exotic_os.py`       → `/config/pyscript/exotic_os.py`
   - `enclosures.yaml`             → `/config/exotic_os/enclosures.yaml`
   - `packages_eos_form.yaml`      → `/config/packages/eos_form.yaml`
4. Restart HA. The dashboard regenerates on boot (`@time_trigger("startup")`).

`generated-exotic-os.yaml` is a snapshot of the produced dashboard (derived — do
not hand-edit; it is overwritten on every regenerate).

## Notes
- Per `CLAUDE.md`: 780×460 canvas, `type: panel`, failsafe `'--'` JS, per-animal colors.
- PID gains are seeded per heater type so PID outputs immediately (no separate
  "apply heater defaults" automation).
- pyscript gotchas handled: no `open()`/`return`-in-`with`/genexprs in script
  funcs (moved to the imported module); `state.get()` returns a `StateVal` —
  coerced to `str()` before writing to the registry.
