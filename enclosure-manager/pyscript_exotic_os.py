"""
Exotic OS — enclosure manager (pyscript WRAPPER).

Thin layer: imports the plain-Python engine /config/exotic_os_lib.py (which does all
file I/O + dashboard/PID generation as full CPython), and performs the HA-side service
calls (helper/automation reloads + browser_mod.refresh). pyscript restricts builtins
like open() inside script functions, so all I/O lives in the imported module.

Services:
  pyscript.enclosure_generate                 - rebuild dashboard from the registry
  pyscript.enclosure_save (slug?, **fields)   - upsert an enclosure (+/- PID), regenerate
  pyscript.enclosure_delete (slug)            - remove an enclosure (+ PID), regenerate
  pyscript.enclosure_form_init (mode, slug?)  - open the Add/Edit form (Phase 2)
"""

import sys
import importlib

if "/config" not in sys.path:
    sys.path.insert(0, "/config")
import exotic_os_lib as lib

PID_DOMAINS = ("input_boolean", "input_select", "input_number", "timer", "automation")


def _reload(domains):
    for dom in domains:
        try:
            service.call(dom, "reload")
        except Exception as e:
            log.warning(f"EOS: reload {dom} failed: {e}")


def _refresh(browser_id):
    if browser_id:
        try:
            service.call("browser_mod", "refresh", browser_id=[browser_id])
        except Exception as e:
            log.warning(f"EOS: refresh skipped: {e}")


@service
def enclosure_generate():
    """Rebuild the consolidated dashboard yaml from the registry, then refresh the kiosk."""
    try:
        importlib.reload(lib)
    except Exception as e:
        log.warning(f"EOS: lib reload skipped: {e}")
    info = task.executor(lib.generate_dashboard)
    _refresh(info.get("browser_id"))
    return f"generated {info.get('count')}"


@service
def enclosure_save(slug=None, **fields):
    """Upsert one enclosure, apply/remove its PID, regenerate, refresh."""
    importlib.reload(lib)
    res = task.executor(lib.save_enclosure, slug, dict(fields))
    if res.get("reload"):
        _reload(PID_DOMAINS)
    info = task.executor(lib.generate_dashboard)
    _refresh(info.get("browser_id"))
    return res.get("slug")


@service
def enclosure_delete(slug=None):
    if not slug:
        return "no slug"
    importlib.reload(lib)
    task.executor(lib.delete_enclosure, slug)
    _reload(PID_DOMAINS)
    info = task.executor(lib.generate_dashboard)
    _refresh(info.get("browser_id"))
    return slug


def _sel(entity, value, options=None):
    """Set an input_select's options (if given) then select `value`, safely."""
    if options:
        try:
            service.call("input_select", "set_options", entity_id=entity, options=options)
        except Exception as e:
            log.warning(f"EOS: set_options {entity} failed: {e}")
    if value is None:
        return
    try:
        service.call("input_select", "select_option", entity_id=entity, option=value)
    except Exception as e:
        log.warning(f"EOS: select_option {entity}={value!r} failed: {e}")


def _norm(v):
    return None if v in (None, "none", "—", "", "unknown", "unavailable") else v


@service
def enclosure_form_init(mode="add", slug=None):
    """Populate the form dropdowns from live entities and prefill (edit) or clear (add)."""
    importlib.reload(lib)
    temps = sorted([e for e in state.names(domain="sensor") if e.endswith("_tempc")]) or ["—"]
    hums = sorted([e for e in state.names(domain="sensor") if e.endswith("_hum")]) or ["—"]
    switches = ["none"] + sorted(state.names(domain="switch"))
    cams = ["none"] + sorted(state.names(domain="camera"))

    enc = {}
    if mode == "edit" and slug:
        enc = task.executor(lib.get_enclosure, slug) or {}

    species = enc.get("species") or "Ball Python"
    pre = lib.SPECIES_PRESETS.get(species, {})
    setp = enc.get("setpoint") or pre.get("setpoint", 88)
    col = enc.get("color") or pre.get("color")

    service.call("input_text", "set_value", entity_id="input_text.eos_form_slug", value=(slug or ""))
    service.call("input_text", "set_value", entity_id="input_text.eos_form_name", value=enc.get("name", ""))
    service.call("input_number", "set_value", entity_id="input_number.eos_form_setpoint", value=float(setp))
    if enc.get("pid"):
        service.call("input_boolean", "turn_on", entity_id="input_boolean.eos_form_pid")
    else:
        service.call("input_boolean", "turn_off", entity_id="input_boolean.eos_form_pid")

    _sel("input_select.eos_form_species", species)
    _sel("input_select.eos_form_heater_type", enc.get("heater_type") or "CHE (Ceramic Heat Emitter)")
    _sel("input_select.eos_form_color", lib.color_name(col) if col else "Cyan")
    _sel("input_select.eos_form_hot_temp", enc.get("hot_temp") or temps[0], options=temps)
    _sel("input_select.eos_form_hot_hum", enc.get("hot_hum") or hums[0], options=hums)
    _sel("input_select.eos_form_cool_temp", enc.get("cool_temp") or "none", options=["none"] + temps)
    _sel("input_select.eos_form_cool_hum", enc.get("cool_hum") or "none", options=["none"] + hums)
    _sel("input_select.eos_form_relay", enc.get("relay") or "none", options=switches)
    _sel("input_select.eos_form_camera", enc.get("camera") or "none", options=cams)
    log.warning(f"EOS: form_init mode={mode} slug={slug} (temps={len(temps)} switches={len(switches)-1})")


def _sv(entity):
    """Return a plain str for an entity state (pyscript state.get returns a StateVal object)."""
    v = state.get(entity)
    return None if v is None else str(v)


@service
def enclosure_submit_form():
    """Read the form helper entities and upsert the enclosure."""
    importlib.reload(lib)
    fields = {
        "name": _sv("input_text.eos_form_name"),
        "species": _sv("input_select.eos_form_species"),
        "color": lib.color_hex(_sv("input_select.eos_form_color")),
        "hot_temp": _norm(_sv("input_select.eos_form_hot_temp")),
        "hot_hum": _norm(_sv("input_select.eos_form_hot_hum")),
        "cool_temp": _norm(_sv("input_select.eos_form_cool_temp")),
        "cool_hum": _norm(_sv("input_select.eos_form_cool_hum")),
        "relay": _norm(_sv("input_select.eos_form_relay")),
        "camera": _norm(_sv("input_select.eos_form_camera")),
        "heater_type": _sv("input_select.eos_form_heater_type"),
        "setpoint": float(_sv("input_number.eos_form_setpoint")),
        "pid": "true" if _sv("input_boolean.eos_form_pid") == "on" else "false",
    }
    slug = _norm(_sv("input_text.eos_form_slug"))
    res = task.executor(lib.save_enclosure, slug, fields)
    if res.get("reload"):
        _reload(PID_DOMAINS)
    info = task.executor(lib.generate_dashboard)
    _refresh(info.get("browser_id"))
    return res.get("slug")


@state_trigger("input_select.eos_form_species")
def _eos_species_changed(value=None):
    """When the user picks a species in the open Add form, auto-fill color + setpoint."""
    if str(state.get("input_text.eos_form_slug") or ""):
        return  # edit mode: don't override the loaded values
    pre = lib.SPECIES_PRESETS.get(str(value))
    if not pre:
        return
    try:
        service.call("input_select", "select_option", entity_id="input_select.eos_form_color",
                     option=lib.color_name(pre["color"]))
        service.call("input_number", "set_value", entity_id="input_number.eos_form_setpoint",
                     value=float(pre["setpoint"]))
    except Exception as e:
        log.warning(f"EOS: species autofill failed: {e}")


@time_trigger("startup")
def _eos_on_startup():
    """Regenerate the dashboard from the registry on boot so it always matches."""
    try:
        importlib.reload(lib)
        info = task.executor(lib.generate_dashboard)
        _refresh(info.get("browser_id"))
    except Exception as e:
        log.error(f"EOS: startup generate failed: {e}")
