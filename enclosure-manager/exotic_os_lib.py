"""Exotic OS enclosure-manager core (plain CPython module, imported by the pyscript wrapper)."""
import os
import re
import yaml
import logging

_LOG = logging.getLogger('exotic_os')

"""
Exotic OS — enclosure manager (pyscript).

Registry-driven generator: reads /config/exotic_os/enclosures.yaml and (re)writes a
single consolidated yaml-mode Lovelace dashboard (home + screensaver + per-enclosure
views) plus per-enclosure PID helpers/automations. Add/Edit/Delete mutate the registry
then regenerate; the kiosk picks up dashboard changes on browser_mod.refresh (no restart).

Services:
  pyscript.enclosure_generate                  - rebuild dashboard from the registry
  pyscript.enclosure_save (slug?, **fields)    - upsert one enclosure, apply/remove PID, regenerate
  pyscript.enclosure_delete (slug)             - remove enclosure + its PID, regenerate
  pyscript.enclosure_form_init (mode, slug?)   - populate form dropdowns / prefill (Phase 2)
"""




REG_PATH = "/config/exotic_os/enclosures.yaml"
DASH_PATH = "/config/dashboards/exotic-os.yaml"          # generated consolidated dashboard
HELPERS_DIR = "/config/exotic_os/helpers"                # generated PID helper yaml (per slug)
AUTOM_DIR = "/config/exotic_os/automations"
PKG_PATH = "/config/packages/%s_pid.yaml"              # generated PID automation yaml (per slug)

ACCENT_DEFAULT = "#00E5FF"
BG0 = "#050505"
BG1 = "#0f0f0f"
CARD_BG = "#080808"

BREATHING = (
    "@keyframes breathing {\n"
    "  0% { transform: scale(0.9); opacity: 0.7; filter: drop-shadow(0px 0px 2px #00E5FF); }\n"
    "  50% { transform: scale(1.1); opacity: 1; filter: drop-shadow(0px 0px 8px #00E5FF); }\n"
    "  100% { transform: scale(0.9); opacity: 0.7; filter: drop-shadow(0px 0px 2px #00E5FF); }\n}\n"
)
PULSE = (
    "@keyframes pulse {\n"
    "  0% { filter: drop-shadow(0px 0px 2px {C}); }\n"
    "  50% { filter: drop-shadow(0px 0px 10px {C}); }\n"
    "  100% { filter: drop-shadow(0px 0px 2px {C}); }\n}\n"
)
CURSOR_NONE = "      :host {\n        cursor: none !important;\n      }\n"

SPECIES_ICON = {
    "Ball Python": "mdi:snake",
    "Corn Snake": "mdi:snake",
    "King Snake": "mdi:snake",
    "Rosy Boa": "mdi:snake",
    "Crested Gecko": "mdi:leaf",
    "Leopard Gecko": "mdi:gecko",
    "Mourning Gecko": "mdi:gecko",
    "Giant Day Gecko": "mdi:gecko",
    "Bearded Dragon": "mdi:lizard",
    "Pacman Frog": "mdi:frog",
}

# species -> (accent, setpoint, hot[min,max], cool[min,max], hum[min,max]) ; mirrors the cloud app SPECIES_PRESETS
SPECIES_PRESETS = {
    "Ball Python":    {"color": "#B026FF", "setpoint": 90, "hot": [88, 92], "cool": [76, 80], "hum": [50, 60]},
    "Crested Gecko":  {"color": "#39FF14", "setpoint": 75, "hot": [72, 78], "cool": [68, 72], "hum": [60, 80]},
    "Corn Snake":     {"color": "#FF6B00", "setpoint": 85, "hot": [85, 88], "cool": [72, 78], "hum": [40, 60]},
    "Leopard Gecko":  {"color": "#FFD400", "setpoint": 90, "hot": [88, 92], "cool": [72, 76], "hum": [30, 40]},
    "Bearded Dragon": {"color": "#FF3366", "setpoint": 100, "hot": [95, 105], "cool": [75, 85], "hum": [30, 40]},
}


# --------------------------------------------------------------------------- #
# blocking helpers (run via task.executor)
# --------------------------------------------------------------------------- #
def _read_yaml(path, default):
    if not os.path.exists(path):
        return default
    f = open(path, "r", encoding="utf-8")
    text = f.read()
    f.close()
    data = yaml.safe_load(text)
    if not data:
        return default
    return data


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _dump_yaml(obj):
    class _D(yaml.Dumper):
        pass
    _D.ignore_aliases = lambda self, data: True   # no &anchors / *aliases
    return yaml.dump(obj, Dumper=_D, default_flow_style=False, sort_keys=False, allow_unicode=True, width=100000)


def _slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "enclosure"


# --------------------------------------------------------------------------- #
# card builders
# --------------------------------------------------------------------------- #
def _orbit():
    return {
        "type": "custom:button-card", "icon": "mdi:orbit", "tap_action": {"action": "none"},
        "styles": {"card": [{"background": BG0}, {"border": "1px solid"}, {"border-radius": "12px"}, {"width": "85px"}],
                   "icon": [{"color": ACCENT_DEFAULT}, {"width": "40px"},
                            {"animation": "breathing 3s ease-in-out infinite"}, {"will-change": "transform, filter"}]},
        "extra_styles": BREATHING,
    }


def _back(path):
    return {
        "type": "custom:button-card", "icon": "mdi:chevron-left", "name": "Back",
        "tap_action": {"action": "navigate", "navigation_path": path},
        "styles": {"card": [{"background": BG0}, {"border": "1px solid"}, {"border-radius": "12px"}, {"width": "85px"}],
                   "icon": [{"color": "#a0b0b5"}, {"width": "35px"}],
                   "name": [{"color": "#a0b0b5"}, {"font-weight": "bold"}, {"font-size": "14px"}]},
    }


def _title_card(name, label, color, edit_slug=None):
    c = {
        "type": "custom:button-card", "name": name, "label": label, "show_label": True,
        "tap_action": {"action": "none"},
        "styles": {"card": [{"background": f"linear-gradient(135deg, {BG0} 0%, #121212 100%)"},
                            {"border": "none"}, {"border-radius": "12px"}],
                   "name": [{"color": "#e8f4f8"}, {"font-family": '"Segoe UI", sans-serif'},
                            {"font-size": "24px"}, {"font-weight": 900}],
                   "label": [{"color": color}, {"font-family": '"Segoe UI", sans-serif'}, {"font-size": "14px"}]},
    }
    return c


def _header(name, label, color, back_path="/exotic-os/home"):
    return {"type": "horizontal-stack", "cards": [_back(back_path), _title_card(name, label, color), _orbit()]}


def _sensor_card(entity, label, color, icon, big=True):
    if not entity:
        entity = "sensor.none"
    return {
        "type": "custom:button-card", "entity": entity, "name": label, "icon": icon, "show_state": True,
        "tap_action": {"action": "more-info"},
        "styles": {"card": [{"background": CARD_BG}, {"border-radius": "12px"}, {"padding": "15px"}, {"border": "1px solid"}],
                   "name": [{"color": "#a0b0b5"}, {"font-size": "14px"}, {"margin-bottom": "5px"}],
                   "state": [{"color": "#e8f4f8"}, {"font-size": "26px" if big else "22px"}, {"font-weight": "bold"}],
                   "icon": [{"color": color}, {"width": "35px"}]},
    }


def _relay_card(enc):
    relay = enc.get("relay")
    name = enc.get("heater_type") or "Heat Relay"
    if not relay:
        return {
            "type": "custom:button-card", "name": "No relay configured", "icon": "mdi:power-plug-off",
            "tap_action": {"action": "none"},
            "styles": {"card": [{"background": CARD_BG}, {"border": "1px solid"}, {"border-radius": "12px"},
                                {"padding": "15px"}, {"height": "90px"}],
                       "name": [{"color": "#555"}, {"font-size": "16px"}], "icon": [{"color": "#444"}, {"width": "40px"}]},
        }
    color = enc["color"]
    return {
        "type": "custom:button-card", "entity": relay, "name": name,
        "label": f'[[[ var s = states["{relay}"]; return s && s.state === "on" ? "ACTIVE" : "STANDBY" ]]]',
        "show_label": True, "icon": "mdi:radiator", "tap_action": {"action": "toggle"},
        "styles": {"card": [{"border-radius": "12px"}, {"padding": "15px"}, {"height": "90px"}, {"transition": "all 0.3s ease"}],
                   "grid": [{"grid-template-columns": "60px auto"}, {"grid-template-rows": "auto auto"},
                            {"grid-template-areas": '"i n" "i l"'}, {"justify-content": "start"}],
                   "name": [{"color": "#e8f4f8"}, {"font-size": "18px"}, {"font-weight": "bold"}, {"justify-self": "start"}],
                   "label": [{"font-size": "14px"}, {"justify-self": "start"}, {"font-weight": "bold"}],
                   "icon": [{"width": "45px"}]},
        "state": [
            {"value": "on", "styles": {"card": [{"background": "#13051A"}, {"border": "1px solid"},
                                                {"box-shadow": f"0px 0px 18px {_rgba(color,0.4)}"}],
                                       "icon": [{"color": color}, {"animation": "pulse 2s infinite"}, {"will-change": "filter, transform"}],
                                       "label": [{"color": color}]}},
            {"value": "off", "styles": {"card": [{"background": CARD_BG}, {"border": "1px solid"}],
                                        "icon": [{"color": "#444444"}], "label": [{"color": "#444444"}]}},
        ],
        "extra_styles": PULSE.replace("{C}", color),
    }


def _history(entities, color):
    ents = [{"entity": e, "name": n} for e, n in entities if e]
    return {
        "type": "history-graph", "hours_to_show": 24, "entities": ents,
        "card_mod": {"style": "ha-card {\n  background: #080808 !important;\n  border-radius: 12px !important;\n  border: 1px solid #1a1a1a !important;\n}\n"},
    }


def _nav_tile(icon, name, label, path, color):
    return {
        "type": "custom:button-card", "icon": icon, "name": name, "label": label, "show_label": True,
        "tap_action": {"action": "navigate", "navigation_path": path},
        "styles": {"card": [{"background": CARD_BG}, {"border": "1px solid"}, {"border-radius": "12px"},
                            {"padding": "15px"}, {"height": "75px"}],
                   "grid": [{"grid-template-columns": "45px auto"}, {"grid-template-areas": '"i n" "i l"'}, {"justify-content": "start"}],
                   "icon": [{"color": color}, {"width": "35px"}],
                   "name": [{"color": "#e8f4f8"}, {"font-size": "16px"}, {"font-weight": "bold"}, {"justify-self": "start"}],
                   "label": [{"color": "#a0b0b5"}, {"font-size": "12px"}, {"justify-self": "start"}]},
    }


COLOR_MAP = {"Purple": "#B026FF", "Green": "#39FF14", "Orange": "#FF6B00", "Blue": "#00BFFF",
             "Yellow": "#FFD400", "Red": "#FF3366", "Teal": "#00CED1", "Pink": "#FF69B4", "Cyan": "#00E5FF"}


def color_hex(name):
    return COLOR_MAP.get(name, name if (name or "").startswith("#") else "#00E5FF")


def color_name(hex_color):
    for k, v in COLOR_MAP.items():
        if v.lower() == (hex_color or "").lower():
            return k
    return "Cyan"


def get_enclosure(slug):
    reg = _read_yaml(REG_PATH, {"enclosures": []})
    return next((e for e in reg.get("enclosures", []) if e["slug"] == slug), None)


def _form_card(mode, slug=None):
    rows = [
        {"entity": "input_text.eos_form_name", "name": "Name"},
        {"entity": "input_select.eos_form_species", "name": "Species"},
        {"entity": "input_select.eos_form_hot_temp", "name": "Hot / main temp sensor"},
        {"entity": "input_select.eos_form_hot_hum", "name": "Hot / main humidity"},
        {"entity": "input_select.eos_form_cool_temp", "name": "Cool temp (optional)"},
        {"entity": "input_select.eos_form_cool_hum", "name": "Cool humidity (optional)"},
        {"entity": "input_select.eos_form_relay", "name": "Heat relay (optional)"},
        {"entity": "input_select.eos_form_heater_type", "name": "Heater type"},
        {"entity": "input_select.eos_form_camera", "name": "Camera (optional)"},
        {"entity": "input_select.eos_form_color", "name": "Accent color"},
        {"entity": "input_number.eos_form_setpoint", "name": "PID setpoint (°F)"},
        {"entity": "input_boolean.eos_form_pid", "name": "Enable PID heat control"},
    ]
    card = {"type": "entities", "entities": rows, "state_color": True,
            "card_mod": {"style": "ha-card { background: #0c0c0c !important; border: 1px solid #1a1a1a !important; }\n"}}
    cards = [card]
    if mode == "edit" and slug:
        cards.append({
            "type": "custom:button-card", "icon": "mdi:trash-can-outline", "name": "Delete this enclosure",
            "tap_action": {"action": "fire-dom-event", "browser_mod": {"service": "browser_mod.sequence", "data": {"sequence": [
                {"service": "pyscript.enclosure_delete", "data": {"slug": slug}},
                {"service": "browser_mod.close_popup"}]}}},
            "styles": {"card": [{"background": "#1A0000"}, {"border": "1px solid #FF3366"}, {"border-radius": "12px"},
                                {"height": "56px"}, {"margin-top": "8px"}],
                       "icon": [{"color": "#FF3366"}, {"width": "26px"}], "name": [{"color": "#FF3366"}, {"font-size": "14px"}]}})
    return {"type": "vertical-stack", "cards": cards}


def _open_form_action(mode, slug, title):
    init = {"service": "pyscript.enclosure_form_init", "data": {"mode": mode}}
    if slug:
        init["data"]["slug"] = slug
    popup = {"service": "browser_mod.popup", "data": {
        "title": title, "content": _form_card(mode, slug), "size": "wide", "dismissable": True,
        "right_button": "Save",
        "right_button_action": {"action": "fire-dom-event", "browser_mod": {"service": "browser_mod.sequence",
            "data": {"sequence": [{"service": "pyscript.enclosure_submit_form"}, {"service": "browser_mod.close_popup"}]}}},
        "left_button": "Cancel",
        "left_button_action": {"action": "fire-dom-event", "browser_mod": {"service": "browser_mod.close_popup"}}}}
    return {"action": "fire-dom-event", "browser_mod": {"service": "browser_mod.sequence",
            "data": {"sequence": [init, popup]}}}


def _edit_tile(slug, color):
    return {
        "type": "custom:button-card", "icon": "mdi:cog", "name": "Edit", "label": "Settings", "show_label": True,
        "tap_action": _open_form_action("edit", slug, "Edit Enclosure"),
        "styles": {"card": [{"background": CARD_BG}, {"border": "1px solid"}, {"border-radius": "12px"},
                            {"padding": "15px"}, {"height": "75px"}],
                   "grid": [{"grid-template-columns": "45px auto"}, {"grid-template-areas": '"i n" "i l"'}, {"justify-content": "start"}],
                   "icon": [{"color": "#a0b0b5"}, {"width": "32px"}],
                   "name": [{"color": "#e8f4f8"}, {"font-size": "16px"}, {"font-weight": "bold"}, {"justify-self": "start"}],
                   "label": [{"color": "#a0b0b5"}, {"font-size": "12px"}, {"justify-self": "start"}]},
    }


def _rgba(hex_color, a):
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r}, {g}, {b}, {a})"


# ---- views --------------------------------------------------------------- #
def _panel(path, title, cards):
    return {"title": title, "path": path, "type": "panel",
            "card_mod": {"style": ":host {\n  cursor: none !important;\n}\n"},
            "cards": [{"type": "vertical-stack", "cards": cards}]}


def _home_tile(enc):
    e = enc
    icon = SPECIES_ICON.get(e.get("species"), "mdi:home")
    ht, hh = e.get("hot_temp"), e.get("hot_hum")
    label = (f'[[[ var t=states["{ht}"]; var h=states["{hh}"]; '
             f'return (t?parseFloat(t.state).toFixed(1):"--")+"°F | "+(h?parseFloat(h.state).toFixed(0):"--")+"%" ]]]')
    color = e["color"]
    glow_on = _rgba(color, 0.4)
    return {
        "type": "custom:button-card", "entity": ht or "sensor.none", "name": e["name"], "icon": icon,
        "show_label": True, "label": label,
        "tap_action": {"action": "navigate", "navigation_path": f'/exotic-os/{e["slug"]}'},
        "styles": {"card": [{"background": CARD_BG}, {"border-radius": "12px"}, {"padding": "15px"}, {"height": "200px"}],
                   "name": [{"color": "#e8f4f8"}, {"font-size": "20px"}, {"font-weight": "bold"}],
                   "label": [{"color": "#a0b0b5"}, {"font-size": "16px"}, {"margin-top": "12px"}],
                   "icon": [{"color": color}, {"width": "50px"}]},
        "card_mod": {"style": (f"ha-card {{\n  border: none;\n"
                               f"  box-shadow: 0px 0px 18px {glow_on} !important;\n}}\n")},
    }


def _add_tile():
    return {
        "type": "custom:button-card", "name": "Add Enclosure", "label": "Tap to set up", "icon": "mdi:plus-circle-outline",
        "show_label": True, "show_name": True,
        "tap_action": _open_form_action("add", None, "Add Enclosure"),
        "styles": {"card": [{"background": "#121212"}, {"border": "2px dashed #333333"}, {"border-radius": "12px"},
                            {"padding": "15px"}, {"height": "200px"}],
                   "name": [{"color": "#888"}, {"font-size": "18px"}, {"font-weight": "bold"}],
                   "label": [{"color": "#555"}, {"font-size": "14px"}, {"margin-top": "12px"}],
                   "icon": [{"color": "#555"}, {"width": "50px"}]},
    }


def _home_view(enclosures):
    header = {
        "type": "custom:button-card", "name": "Exotic OS", "label": "Smart husbandry, simplified",
        "show_label": True, "show_name": True, "show_icon": True, "icon": "mdi:orbit",
        "styles": {"card": [{"background": f"linear-gradient(135deg, {BG0} 0%, #121212 100%)"}, {"border": "none"},
                            {"padding": "25px 35px"}, {"border-radius": "12px"}, {"margin-bottom": "12px"}],
                   "grid": [{"grid-template-columns": "auto 85px"}, {"grid-template-areas": '"n i" "l i"'}],
                   "name": [{"color": "#e8f4f8"}, {"font-family": '"Segoe UI", sans-serif'}, {"font-size": "36px"},
                            {"font-weight": "900"}, {"justify-self": "center"}],
                   "label": [{"color": "#a0b0b5"}, {"font-size": "18px"}, {"justify-self": "center"}],
                   "icon": [{"color": ACCENT_DEFAULT}, {"width": "75px"}, {"justify-self": "end"},
                            {"animation": "breathing 3s ease-in-out infinite"}, {"will-change": "transform, filter"}]},
        "extra_styles": BREATHING.replace("0px 0px 2px", "0px 0px 4px").replace("0px 0px 8px", "0px 0px 15px"),
    }
    tiles = [_home_tile(e) for e in enclosures] + [_add_tile()]
    swipe = {"type": "custom:swipe-card",
             "parameters": {"centeredSlides": False, "slidesPerView": 4, "spaceBetween": 8, "freeMode": True},
             "cards": tiles}
    return _panel("home", "Home", [header, swipe])


def _enclosure_main_view(enc):
    e = enc
    color = e["color"]
    label = f'{e.get("species","")} · {e.get("dimensions","")}'.strip(" ·")
    cards = [_header(e["name"], label, color)]
    # sensor grid (2 cols): hot temp, cool temp, hot hum, cool hum (only those present)
    grid_cards = []
    if e.get("hot_temp"):
        grid_cards.append(_sensor_card(e["hot_temp"], "Hot Temp", color, "mdi:thermometer"))
    if e.get("cool_temp"):
        grid_cards.append(_sensor_card(e["cool_temp"], "Cool Temp", "#7A4B8F", "mdi:thermometer"))
    if e.get("hot_hum"):
        grid_cards.append(_sensor_card(e["hot_hum"], "Hot Hum", color, "mdi:water-percent"))
    if e.get("cool_hum"):
        grid_cards.append(_sensor_card(e["cool_hum"], "Cool Hum", "#7A4B8F", "mdi:water-percent"))
    left = {"type": "vertical-stack", "cards": [
        {"type": "grid", "columns": 2, "square": False, "cards": grid_cards},
        _relay_card(e),
    ]}
    hist = [(e.get("hot_temp"), "Hot Side"), (e.get("cool_temp"), "Cool Side")]
    histh = [(e.get("hot_hum"), "Hot Side"), (e.get("cool_hum"), "Cool Side")]
    right = {"type": "vertical-stack", "cards": [_history(hist, color), _history(histh, color)]}
    cards.append({"type": "horizontal-stack", "cards": [left, right]})
    # nav row: camera (if any) / heat-control (if pid) / edit
    nav = []
    if e.get("camera"):
        nav.append(_nav_tile("mdi:video", "Camera", "Live", f'/exotic-os/{e["slug"]}-cam', color))
    if e.get("pid"):
        nav.append(_nav_tile("mdi:thermometer-auto", "Heat Control", "PID Status", f'/exotic-os/{e["slug"]}-heat', color))
    nav.append(_edit_tile(e["slug"], color))
    cards.append({"type": "horizontal-stack", "cards": nav})
    return _panel(e["slug"], e["name"], cards)


def _enclosure_camera_view(enc):
    e = enc
    color = e["color"]
    pic = {"type": "picture-entity", "entity": e["camera"], "show_state": False, "show_name": False, "camera_view": "live",
           "card_mod": {"style": "ha-card {\n  background: #080808 !important;\n  border-radius: 12px !important;\n  border: 1px solid #1a1a1a !important;\n  overflow: hidden !important;\n}\n"}}
    strip = {"type": "horizontal-stack", "cards": [
        _sensor_card(e.get("hot_temp"), "Hot Temp", color, "mdi:thermometer", big=False),
        _sensor_card(e.get("cool_temp") or e.get("hot_temp"), "Cool Temp", "#7A4B8F", "mdi:thermometer", big=False),
        _sensor_card(e.get("hot_hum"), "Humidity", color, "mdi:water-percent", big=False),
    ]}
    cards = [_header(f'{e["name"]} Cam', "Live Feed", color, back_path=f'/exotic-os/{e["slug"]}'), pic, strip]
    return _panel(f'{e["slug"]}-cam', f'{e["name"]} Cam', cards)


SCREENSAVER_KEYFRAMES = (
    "@keyframes scroll-top {\n  0%   { transform: translateX(780px); }\n  100% { transform: translateX(-1500px); }\n}\n"
    "@keyframes scroll-bottom {\n  0%   { transform: translateX(780px); }\n  100% { transform: translateX(-800px); }\n}\n"
    "@keyframes pulse {\n  0%, 100% { transform: scale(0.85); opacity: 0.1; }\n  50%      { transform: scale(1.1); opacity: 0.6; }\n}\n"
    "@keyframes patrol-mid {\n  0%   { top: 160px; left: 100px; }\n  50%  { top: 160px; left: 530px; }\n  100% { top: 160px; left: 100px; }\n}\n"
)


def _ss_stat(enc):
    e = enc
    color = e["color"]
    ht, hh = e.get("hot_temp") or "sensor.none", e.get("hot_hum") or "sensor.none"
    label = (f"[[[ var t=states['{ht}']; var h=states['{hh}']; "
             f"var tv=t?parseFloat(t.state).toFixed(1):'--'; var hv=h?parseFloat(h.state).toFixed(0):'--'; "
             f"return tv+'°F / '+hv+'%'; ]]]")
    return {
        "type": "custom:button-card", "name": e["name"].upper(), "label": label, "show_label": True,
        "styles": {"card": [{"background": "#0a0a0a"}, {"border": "1px solid #222"}, {"border-radius": "8px"},
                            {"padding": "10px"}, {"box-shadow": f"0px 0px 10px {_rgba(color, 0.2)}"}],
                   "name": [{"color": color}, {"font-weight": "bold"}, {"font-size": "16px"}, {"font-family": "monospace"}],
                   "label": [{"color": "#00E5FF"}, {"font-size": "18px"}, {"font-family": "monospace"},
                             {"text-shadow": "0px 0px 5px #00E5FF"}]},
    }


def _screensaver_view(enclosures):
    stats = {"type": "horizontal-stack", "cards": [_ss_stat(e) for e in enclosures]}
    inner = {
        "type": "custom:button-card",
        "styles": {"card": [{"width": "780px"}, {"height": "460px"}, {"background": "#000000"}, {"margin": 0},
                            {"padding": 0}, {"border": "none"}, {"overflow": "hidden"}],
                   "custom_fields": {
                       "top_text": [{"position": "absolute"}, {"top": "20px"}, {"left": "0px"}, {"width": "1500px"},
                                    {"animation": "scroll-top 30s linear infinite"}],
                       "stats": [{"position": "absolute"}, {"bottom": "30px"}, {"left": "0px"}, {"width": "700px"},
                                 {"animation": "scroll-bottom 25s linear infinite"}],
                       "albedo": [{"position": "absolute"}, {"width": "130px"},
                                  {"animation": "pulse 4s ease-in-out infinite, patrol-mid 50s linear infinite"}]}},
        "custom_fields": {
            "top_text": {"card": {"type": "custom:button-card", "name": "EXOTIC OS — SMART HUSBANDRY, SIMPLIFIED ",
                                  "styles": {"card": [{"background": "transparent"}, {"border": "none"}],
                                             "name": [{"color": "#546E7A"}, {"font-family": "monospace"},
                                                      {"font-size": "36px"}, {"letter-spacing": "4px"}]}}},
            "albedo": {"card": {"type": "custom:button-card", "icon": "mdi:orbit",
                                "styles": {"card": [{"background": "transparent"}, {"border": "none"}],
                                           "icon": [{"color": ACCENT_DEFAULT}, {"width": "100%"},
                                                    {"filter": "drop-shadow(0px 0px 15px #00E5FF)"}]}}},
            "stats": {"card": stats}},
        "extra_styles": SCREENSAVER_KEYFRAMES,
    }
    return _panel("screensaver", "Screensaver", [inner])


# --------------------------------------------------------------------------- #
# dashboard assembly
# --------------------------------------------------------------------------- #
def _build_dashboard(reg):
    enclosures = reg.get("enclosures", []) or []
    views = [_home_view(enclosures)]
    for e in enclosures:
        views.append(_enclosure_main_view(e))
        if e.get("camera"):
            views.append(_enclosure_camera_view(e))
        if e.get("pid"):
            views.append(_pid_view(e))
    views.append(_screensaver_view(enclosures))
    return {
        "kiosk_mode": {"hide_header": True, "hide_sidebar": True,
                       "admin_settings": {"hide_header": True, "hide_sidebar": True}},
        "title": "Exotic OS",
        "views": views,
    }


# --------------------------------------------------------------------------- #
# PID heat-control view (references <ep>_pid_* helper entities; ep = slug w/ _)
# --------------------------------------------------------------------------- #
def _ep(slug):
    return slug.replace("-", "_")


def _pid_step(entity, icon, op, color):
    act = {"action": "call-service", "service": f"input_number.{op}", "service_data": {"entity_id": entity}}
    return {"type": "custom:button-card", "icon": icon, "name": "", "tap_action": act, "hold_action": act,
            "styles": {"card": [{"background": "#0D0510"}, {"border": "2px solid"}, {"border-radius": "12px"},
                                {"height": "80px"}, {"width": "80px"}], "icon": [{"color": color}, {"width": "45px"}]}}


def _pid_view(enc):
    e = enc
    s = _ep(e["slug"])
    color = e["color"]
    hot = e.get("hot_temp") or "sensor.none"
    en = f"input_boolean.{s}_pid_enabled"
    header = _header("Heat Control",
                     f'[[[ var b=states["{en}"]; return b && b.state==="on" ? "PID ACTIVE" : "PID DISABLED" ]]]',
                     color, back_path=f'/exotic-os/{e["slug"]}')
    hot_now = {
        "type": "custom:button-card", "entity": hot, "name": "Hot Side Now", "show_state": True,
        "icon": "mdi:thermometer-high", "tap_action": {"action": "none"},
        "styles": {"card": [{"border-radius": "12px"}, {"padding": "15px"}, {"background": CARD_BG}, {"border": "1px solid"}],
                   "name": [{"color": "#a0b0b5"}, {"font-size": "13px"}],
                   "state": [{"color": "#e8f4f8"}, {"font-size": "38px"}, {"font-weight": "bold"}], "icon": [{"width": "32px"}]},
    }
    out = {
        "type": "custom:button-card", "entity": f"input_number.{s}_pid_output", "name": "Output %", "show_state": True,
        "icon": "mdi:gauge", "tap_action": {"action": "none"},
        "styles": {"card": [{"background": CARD_BG}, {"border": "1px solid"}, {"border-radius": "12px"}, {"padding": "15px"}],
                   "name": [{"color": "#a0b0b5"}, {"font-size": "13px"}],
                   "state": [{"color": ACCENT_DEFAULT}, {"font-size": "38px"}, {"font-weight": "bold"}],
                   "icon": [{"color": ACCENT_DEFAULT}, {"width": "32px"}]},
    }
    relay = e.get("relay") or "switch.none"
    relay_card = {
        "type": "custom:button-card", "entity": relay, "name": "Relay", "show_state": False, "icon": "mdi:radiator",
        "tap_action": {"action": "none"},
        "styles": {"card": [{"border-radius": "12px"}, {"padding": "15px"}], "name": [{"font-size": "13px"}], "icon": [{"width": "32px"}]},
        "state": [{"value": "on", "styles": {"card": [{"background": "#13051A"}, {"border": "1px solid"}],
                                             "icon": [{"color": color}], "name": [{"color": color}]}},
                  {"value": "off", "styles": {"card": [{"background": CARD_BG}, {"border": "1px solid"}],
                                              "icon": [{"color": "#333"}], "name": [{"color": "#444"}]}}],
    }
    setpoint_row = {"type": "horizontal-stack", "cards": [
        _pid_step(f"input_number.{s}_pid_setpoint", "mdi:minus", "decrement", color),
        {"type": "custom:button-card", "entity": f"input_number.{s}_pid_setpoint", "name": "Setpoint", "show_state": True,
         "tap_action": {"action": "more-info"},
         "styles": {"card": [{"background": CARD_BG}, {"border": "1px solid"}, {"border-radius": "12px"}, {"height": "80px"}],
                    "name": [{"color": "#a0b0b5"}, {"font-size": "13px"}, {"font-family": "monospace"}],
                    "state": [{"color": ACCENT_DEFAULT}, {"font-size": "36px"}, {"font-weight": "bold"}]}},
        _pid_step(f"input_number.{s}_pid_setpoint", "mdi:plus", "increment", color),
    ]}
    toggle_row = {"type": "horizontal-stack", "cards": [
        {"type": "custom:button-card", "entity": en,
         "name": '[[[ return entity.state === "on" ? "PID  ON" : "PID  OFF" ]]]', "icon": "mdi:thermostat",
         "tap_action": {"action": "toggle"},
         "styles": {"card": [{"border-radius": "12px"}, {"height": "70px"}, {"transition": "all 0.3s ease"}],
                    "name": [{"font-size": "18px"}, {"font-weight": "bold"}, {"font-family": "monospace"}], "icon": [{"width": "36px"}]},
         "state": [{"value": "on", "styles": {"card": [{"background": "#0D1A0D"}, {"border": "2px solid"},
                                                       {"box-shadow": "0px 0px 16px rgba(57,255,20,0.3)"}],
                                              "icon": [{"color": "#39FF14"}], "name": [{"color": "#39FF14"}]}},
                   {"value": "off", "styles": {"card": [{"background": CARD_BG}, {"border": "1px solid"}],
                                               "icon": [{"color": "#555"}], "name": [{"color": "#555"}]}}]},
        {"type": "custom:button-card", "icon": "mdi:restore", "name": "Reset Integral",
         "tap_action": {"action": "call-service", "service": "input_number.set_value",
                        "service_data": {"entity_id": f"input_number.{s}_pid_integral", "value": 0}},
         "styles": {"card": [{"background": CARD_BG}, {"border": "1px solid"}, {"border-radius": "12px"}, {"height": "70px"}],
                    "icon": [{"color": "#a0b0b5"}, {"width": "32px"}], "name": [{"color": "#a0b0b5"}, {"font-size": "14px"}]}},
    ]}
    selectors = {"type": "entities", "entities": [
        {"entity": f"input_select.{s}_heater_type", "name": "Heater type", "icon": "mdi:heat-wave"},
        {"entity": f"input_select.{s}_temp_sensor", "name": "Control sensor", "icon": "mdi:thermometer"},
        {"entity": f"input_select.{s}_relay", "name": "Heat relay", "icon": "mdi:power-socket-us"}],
        "card_mod": {"style": "ha-card {\n  background: #080808 !important;\n  border: 1px solid #1a1a1a !important;\n  border-radius: 12px !important;\n}\n.card-header { display: none !important; }\n"}}
    gains = {"type": "entities", "entities": [
        {"entity": f"input_number.{s}_pid_kp", "name": "Kp — Proportional", "icon": "mdi:alpha-p-circle"},
        {"entity": f"input_number.{s}_pid_ki", "name": "Ki — Integral", "icon": "mdi:alpha-i-circle"},
        {"entity": f"input_number.{s}_pid_kd", "name": "Kd — Derivative", "icon": "mdi:alpha-d-circle"},
        {"entity": f"input_number.{s}_pid_cycle_time", "name": "Cycle time (min)", "icon": "mdi:clock-outline"}],
        "card_mod": {"style": "ha-card {\n  background: #080808 !important;\n  border: 1px solid #1a1a1a !important;\n  border-radius: 12px !important;\n}\n.card-header { display: none !important; }\n"}}
    cards = [header,
             {"type": "horizontal-stack", "cards": [hot_now, out, relay_card]},
             setpoint_row, toggle_row, selectors, gains]
    return _panel(f'{e["slug"]}-heat', f'{e["name"]} Heat', cards)


# --------------------------------------------------------------------------- #
# PID package (helpers + timers + 5 automations) per enclosure, via /config/packages
# --------------------------------------------------------------------------- #
HEATER_OPTIONS = ["CHE (Ceramic Heat Emitter)", "Radiant Heat Panel", "Heat Mat",
                  "Deep Heat Projector", "Halogen Basking Bulb", "Mercury Vapor Bulb", "Radiant Heat Cable"]

# heater type -> initial (Kp, Ki, Kd, cycle_time_min); seeds working gains so PID
# produces output immediately (no separate "apply heater defaults" automation needed)
HEATER_GAINS = {
    "CHE (Ceramic Heat Emitter)": (10, 0.05, 50, 5),
    "Radiant Heat Panel": (10, 0.05, 50, 5),
    "Radiant Heat Cable": (12, 0.06, 40, 4),
    "Deep Heat Projector": (8, 0.03, 80, 10),
    "Heat Mat": (15, 0.08, 25, 3),
    "Halogen Basking Bulb": (20, 0.1, 15, 2),
    "Mercury Vapor Bulb": (20, 0.1, 15, 2),
}


def _num(name, nm, mn, mx, st, unit=None, icon="mdi:knob"):
    d = {"name": f"{name} {nm}", "min": mn, "max": mx, "step": st, "icon": icon}
    if unit:
        d["unit_of_measurement"] = unit
    return d


def _pid_package(enc):
    e = enc
    s = _ep(e["slug"])
    name = e["name"]
    setp = e.get("setpoint", 88)
    heater = e.get("heater_type") or "CHE (Ceramic Heat Emitter)"
    if heater not in HEATER_OPTIONS:
        heater = "CHE (Ceramic Heat Emitter)"
    sensors = [x for x in [e.get("hot_temp"), e.get("cool_temp")] if x] or ["sensor.none"]
    relay = e.get("relay") or "switch.none"
    spn = _num(name, "PID Setpoint", 60, 110, 0.5, "°F", "mdi:target")
    spn["initial"] = setp
    pkg = {
        "input_boolean": {f"{s}_pid_enabled": {"name": f"{name} PID Enabled", "icon": "mdi:thermostat"}},
        "input_select": {
            f"{s}_heater_type": {"name": f"{name} Heater Type", "options": HEATER_OPTIONS, "initial": heater, "icon": "mdi:radiator"},
            f"{s}_temp_sensor": {"name": f"{name} Temp Sensor", "options": sensors, "initial": sensors[0], "icon": "mdi:thermometer"},
            f"{s}_relay": {"name": f"{name} Relay", "options": [relay], "initial": relay, "icon": "mdi:power-socket-us"},
        },
        "input_number": {
            f"{s}_pid_setpoint": spn,
            f"{s}_pid_kp": _num(name, "Kp", 0, 100, 0.1),
            f"{s}_pid_ki": _num(name, "Ki", 0, 10, 0.01),
            f"{s}_pid_kd": _num(name, "Kd", 0, 100, 0.1),
            f"{s}_pid_cycle_time": _num(name, "Cycle Time", 1, 30, 1, "min", "mdi:timer"),
            f"{s}_pid_output": _num(name, "PID Output", 0, 100, 0.1, "%", "mdi:gauge"),
            f"{s}_pid_integral": _num(name, "PID Integral", -1000, 1000, 0.01, None, "mdi:math-integral"),
            f"{s}_pid_prev_error": _num(name, "PID Prev Error", -100, 100, 0.01, None, "mdi:delta"),
        },
        "timer": {
            f"{s}_pid_cycle_timer": {"name": f"{name} PID Cycle Timer", "duration": "00:05:00"},
            f"{s}_pid_on_timer": {"name": f"{name} PID On Timer", "duration": "00:01:00"},
        },
        "automation": _pid_automations(s, name),
    }
    # seed working initial gains so PID outputs immediately
    kp, ki, kd, ct = HEATER_GAINS.get(heater, (10, 0.05, 50, 5))
    inn = pkg["input_number"]
    inn[f"{s}_pid_kp"]["initial"] = kp
    inn[f"{s}_pid_ki"]["initial"] = ki
    inn[f"{s}_pid_kd"]["initial"] = kd
    inn[f"{s}_pid_cycle_time"]["initial"] = ct
    inn[f"{s}_pid_output"]["initial"] = 0
    inn[f"{s}_pid_integral"]["initial"] = 0
    inn[f"{s}_pid_prev_error"]["initial"] = 0
    return pkg


def _pid_automations(s, name):
    return [
        {"id": f"eos_{s}_pid_enabled", "alias": f"Exotic OS: {name} PID — Enabled",
         "triggers": [{"trigger": "state", "entity_id": f"input_boolean.{s}_pid_enabled", "to": "on"}],
         "actions": [{"action": "timer.start", "data": {"entity_id": f"timer.{s}_pid_cycle_timer",
                      "duration": {"minutes": f"{{{{ states('input_number.{s}_pid_cycle_time') | int(5) }}}}"}}}]},
        {"id": f"eos_{s}_pid_disabled", "alias": f"Exotic OS: {name} PID — Disabled",
         "triggers": [{"trigger": "state", "entity_id": f"input_boolean.{s}_pid_enabled", "to": "off"}],
         "actions": [
            {"action": "timer.cancel", "data": {"entity_id": f"timer.{s}_pid_cycle_timer"}},
            {"action": "timer.cancel", "data": {"entity_id": f"timer.{s}_pid_on_timer"}},
            {"action": "switch.turn_off", "target": {"entity_id": f"{{{{ states('input_select.{s}_relay') }}}}"}},
            {"action": "input_number.set_value", "data": {"entity_id": f"input_number.{s}_pid_integral", "value": 0}},
            {"action": "input_number.set_value", "data": {"entity_id": f"input_number.{s}_pid_prev_error", "value": 0}},
            {"action": "input_number.set_value", "data": {"entity_id": f"input_number.{s}_pid_output", "value": 0}}]},
        {"id": f"eos_{s}_pid_cycle", "alias": f"Exotic OS: {name} PID — Cycle",
         "triggers": [{"trigger": "event", "event_type": "timer.finished",
                       "event_data": {"entity_id": f"timer.{s}_pid_cycle_timer"}}],
         "conditions": [{"condition": "state", "entity_id": f"input_boolean.{s}_pid_enabled", "state": "on"}],
         "actions": [
            {"action": "timer.start", "data": {"entity_id": f"timer.{s}_pid_cycle_timer",
             "duration": {"minutes": f"{{{{ states('input_number.{s}_pid_cycle_time') | int(5) }}}}"}}},
            {"variables": {
                "setpoint": f"{{{{ states('input_number.{s}_pid_setpoint') | float(90) }}}}",
                "kp": f"{{{{ states('input_number.{s}_pid_kp') | float(10) }}}}",
                "ki": f"{{{{ states('input_number.{s}_pid_ki') | float(0.05) }}}}",
                "kd": f"{{{{ states('input_number.{s}_pid_kd') | float(50) }}}}",
                "dt": f"{{{{ states('input_number.{s}_pid_cycle_time') | float(5) }}}}",
                "integral": f"{{{{ states('input_number.{s}_pid_integral') | float(0) }}}}",
                "prev_error": f"{{{{ states('input_number.{s}_pid_prev_error') | float(0) }}}}",
                "current_temp": ("{% set t = states(states('input_select." + s + "_temp_sensor')) %}"
                                 " {{ t | float(-999) if t not in ['unknown','unavailable','none',''] else -999 }}")}},
            {"choose": [
                {"conditions": [{"condition": "template", "value_template": "{{ current_temp == -999 }}"}],
                 "sequence": [
                    {"action": "switch.turn_off", "target": {"entity_id": f"{{{{ states('input_select.{s}_relay') }}}}"}},
                    {"action": "timer.cancel", "data": {"entity_id": f"timer.{s}_pid_on_timer"}}]}],
             "default": [
                {"variables": {
                    "error": "{{ setpoint - current_temp }}",
                    "output": ("{% set e = setpoint - current_temp %}{% set ni = [[integral + e*dt,-500]|max,500]|min %}"
                               "{% set d = (e - prev_error)/dt %}{{ [[kp*e + ki*ni + kd*d,0]|max,100]|min|round(1) }}"),
                    "new_integral": ("{% set e = setpoint - current_temp %}{{ [[integral + e*dt,-500]|max,500]|min|round(4) }}"),
                    "on_seconds": ("{% set e = setpoint - current_temp %}{% set ni = [[integral + e*dt,-500]|max,500]|min %}"
                                   "{% set d = (e - prev_error)/dt %}{% set out = [[kp*e + ki*ni + kd*d,0]|max,100]|min %}"
                                   "{{ (out/100*dt*60)|int }}")}},
                {"action": "input_number.set_value", "data": {"entity_id": f"input_number.{s}_pid_integral", "value": "{{ new_integral }}"}},
                {"action": "input_number.set_value", "data": {"entity_id": f"input_number.{s}_pid_prev_error", "value": "{{ error | round(4) }}"}},
                {"action": "input_number.set_value", "data": {"entity_id": f"input_number.{s}_pid_output", "value": "{{ output }}"}},
                {"choose": [
                    {"conditions": [{"condition": "template", "value_template": "{{ on_seconds | int > 0 }}"}],
                     "sequence": [
                        {"action": "switch.turn_on", "target": {"entity_id": f"{{{{ states('input_select.{s}_relay') }}}}"}},
                        {"action": "timer.start", "data": {"entity_id": f"timer.{s}_pid_on_timer", "duration": "{{ on_seconds }}"}}]}],
                 "default": [
                    {"action": "switch.turn_off", "target": {"entity_id": f"{{{{ states('input_select.{s}_relay') }}}}"}},
                    {"action": "timer.cancel", "data": {"entity_id": f"timer.{s}_pid_on_timer"}}]}]}]},
        {"id": f"eos_{s}_pid_on_end", "alias": f"Exotic OS: {name} PID — On Timer End",
         "triggers": [{"trigger": "event", "event_type": "timer.finished", "event_data": {"entity_id": f"timer.{s}_pid_on_timer"}}],
         "actions": [{"action": "switch.turn_off", "target": {"entity_id": f"{{{{ states('input_select.{s}_relay') }}}}"}}]},
    ]


def _rm(path):
    if os.path.exists(path):
        os.remove(path)


# --------------------------------------------------------------------------- #
# public services: save / delete / form_init
# --------------------------------------------------------------------------- #

# ---- orchestration (no HA service calls; returns info for the wrapper) ----
def generate_dashboard():
    reg = _read_yaml(REG_PATH, {'enclosures': []})
    dash = _build_dashboard(reg)
    text = '# GENERATED by Exotic OS enclosure manager - edit the registry, not this file.' + chr(10) + _dump_yaml(dash)
    _write_text(DASH_PATH, text)
    n = len(reg.get('enclosures', []) or [])
    _LOG.warning('EOS: dashboard generated (%s enclosures)', n)
    return {'count': n, 'browser_id': (reg.get('system') or {}).get('browser_id')}

def write_pid_package(enc):
    pkg = _pid_package(enc)
    text = '# GENERATED PID package for ' + enc['slug'] + chr(10) + _dump_yaml(pkg)
    _write_text(PKG_PATH % _ep(enc['slug']), text)

def remove_pid_package(slug):
    _rm(PKG_PATH % _ep(slug))

def save_enclosure(slug, fields):
    reg = _read_yaml(REG_PATH, {'enclosures': []})
    encs = reg.setdefault('enclosures', [])
    if not slug:
        slug = _slugify(fields.get('name', 'enclosure'))
        base, i = slug, 2
        while any(e['slug'] == slug for e in encs):
            slug = base + '-' + str(i); i += 1
    cur = next((e for e in encs if e['slug'] == slug), None)
    if cur is None:
        cur = {'slug': slug}; encs.append(cur)
    prev_pid = bool(cur.get('pid'))
    for k in ('name','species','color','dimensions','hot_temp','hot_hum','cool_temp','cool_hum','relay','camera','heater_type','setpoint'):
        if k in fields and fields[k] not in (None, '', 'none'):
            cur[k] = fields[k]
    if 'pid' in fields:
        cur['pid'] = str(fields['pid']).lower() in ('true','1','on','yes')
    pre = SPECIES_PRESETS.get(cur.get('species'))
    if pre:
        cur.setdefault('color', pre['color']); cur.setdefault('setpoint', pre['setpoint'])
    _write_text(REG_PATH, _dump_yaml(reg))
    pid_now = bool(cur.get('pid'))
    if pid_now:
        write_pid_package(cur)
    elif prev_pid and not pid_now:
        remove_pid_package(slug)
    _LOG.warning('EOS: saved enclosure %s (pid=%s)', slug, pid_now)
    return {'slug': slug, 'pid': pid_now, 'prev_pid': prev_pid, 'reload': pid_now or prev_pid}

def delete_enclosure(slug):
    reg = _read_yaml(REG_PATH, {'enclosures': []})
    reg['enclosures'] = [e for e in reg.get('enclosures', []) if e['slug'] != slug]
    _write_text(REG_PATH, _dump_yaml(reg))
    remove_pid_package(slug)
    _LOG.warning('EOS: deleted enclosure %s', slug)
    return {'slug': slug, 'reload': True}
