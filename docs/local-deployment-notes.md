# Local deployment notes — this-PC HA stack (May 2026)

The whole stack now runs as Docker containers on the Windows PC `192.168.68.63`
(Docker Desktop): `homeassistant` (`/config` → `C:\homeassistant`), `mosquitto`
(`1883`), `esphome` (`6052`). The **BTT Pi v2** (`192.168.68.59`, user `exoticos`)
is the wall kiosk (Chromium `--kiosk`) and runs Theengs Gateway (BLE→MQTT,
`-H 192.168.68.63 -P 1883`).

## Dashboards (the five screens)

Deployed as **YAML-mode Lovelace dashboards**, not via the raw-config editor.
Files live at `C:\homeassistant\dashboards\` (copies of `dashboard/*.yaml` here).
Registered in `C:\homeassistant\configuration.yaml`:

```yaml
lovelace:
  mode: storage
  dashboards:
    exotic-os:               { mode: yaml, filename: dashboards/exotic-os-home.yaml,  title: Exotic OS, show_in_sidebar: true }
    coras-enclosure:         { mode: yaml, filename: dashboards/coras-enclosure.yaml }
    sonics-enclosure:        { mode: yaml, filename: dashboards/sonics-enclosure.yaml }
    motley-corns-enclosure:  { mode: yaml, filename: dashboards/motley-corn.yaml }
    confused-spider-bp:      { mode: yaml, filename: dashboards/confused-spider.yaml }
```

The `url_path` keys must stay exactly as above — the in-dashboard
`navigation_path:` values (`/coras-enclosure/0`, `/confused-spider-bp`, …) resolve
to them. Editing a dashboard file only needs a browser refresh; adding/removing a
dashboard needs an HA restart.

## browser_mod — was broken (mis-nested), now fixed

HACS had installed it one level too deep:
`custom_components/browser_mod/browser_mod/` — so HA never found
`custom_components/browser_mod/manifest.json` and **silently never loaded the
integration** (no "custom integration browser_mod" warning in the log — that
absence is the tell). Fixed by flattening to `custom_components/browser_mod/`.
After that, the integration needs a config entry (it's UI-flow only, no YAML
import); created via the `+ Add Integration → Browser Mod` flow.

## Kiosk registration (for the screensaver automations)

browser_mod 2.x does **not** auto-persist a browser until registered. Enabled the
global **Auto Register** setting (`.storage/browser_mod.storage` →
`settings.autoRegister: true`); the kiosk then self-registers on load. Current
kiosk display browserID: **`browser_mod_b2dfa711_40e39ce3`** — this is the
`browser_id` used by `browser_mod.navigate` and the prefix of the idle/path
entities (`binary_sensor.browser_mod_b2dfa711_40e39ce3`,
`sensor.browser_mod_b2dfa711_40e39ce3_browser_path`). `screensaver.yaml` is wired
to these.

If the kiosk display is ever re-registered, the browserID changes — update
`screensaver.yaml` accordingly.

## Kiosk autostart + stability

`~/.config/openbox/autostart` launches **`/home/exoticos/kiosk.sh`** (in
`scripts/`), which sets `xset s off / -dpms` (no screen blanking → branded
screensaver shows instead of black) and launches Chromium at
`/exotic-os/home`. The kiosk authenticates with a normal user login typed once on
the Pi (token persists in the Chromium profile) — no `trusted_networks` /
passwordless auth is used.

### Hidden mouse cursor
The pointer is hidden at the X-server level via `-nocursor`, set in
`~/.xserverrc` (see `scripts/xserverrc`). This is the real fix — CSS
`cursor: none` (still present on the dashboard views via card_mod) only covers
the dashboard view, not the app root where the pointer parks at (0,0). `xinit`
prefers `~/.xserverrc`, so it applies on every X start. To apply without a reboot:
end the tty1 login shell so getty respawns the session
(`pkill -HUP -t tty1 -u exoticos bash`) — killing only Xorg does NOT restart it,
because `startx` runs once from `~/.bash_profile` at login.

### Overnight "Aw, Snap!" (Error code 11) — fixed
The renderer was OOM-killed / segfaulted after a few hours (~876MB RSS on a 2GB
Pi) and stuck on the error page with no recovery. Layered fix, all as the
`exoticos` user (no sudo):
- **Root cause:** removed `--memory-pressure-off` from the Chromium flags (it
  blocked memory reclaim). See `scripts/kiosk.sh`.
- **Prevention (keeps memory bounded):** HA automation *"Exotic OS: Kiosk hourly
  refresh"* (`ha-config/automations/kiosk-refresh.yaml`) calls `browser_mod.refresh`
  every hour — a soft page reload that sheds accumulated DOM/heap so memory never
  reaches the crash point.
- **Recovery (cron):**
  - `*/2 * * * * /home/exoticos/kiosk-watchdog.sh` — relaunch if Chromium exited,
    AND restart within ~2 min on a renderer crash, detected via a fresh Chromium
    crash dump (`Crash Reports/*.dmp` newer than 3 min) since the sad-tab can't be
    detected by title or process state.
  - `0 4 * * * /home/exoticos/kiosk-restart.sh` — full nightly restart for any
    process-level leak the soft refresh can't reclaim.

`scripts/kiosk*.sh` are deployed to `/home/exoticos/` on the Pi; the two cron
lines above are in the `exoticos` user crontab.

### fail2ban note
Repeated/failed SSH from a workstation can get that IP blanket-DROP banned on the
Pi (blocks all ports + ICMP, while the Pi keeps publishing to MQTT). Clear with
`sudo fail2ban-client unban --all`; optionally whitelist the LAN via `ignoreip`.
