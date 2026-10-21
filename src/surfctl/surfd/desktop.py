"""Everyday desktop tools: the surfd menu, pickers, switchers and quick toggles.

Each function is what one `surfctl` command does; the commands are bound to keys
(see keys.ACTIONS) and reachable from the surfd menu (Super+Alt+Space). Menus use
fuzzel in dmenu mode; flyouts go through libexec/surfd-osd so they look the same
as the volume and brightness ones.
"""

from __future__ import annotations

import ast
import json
import math
import operator
import os
import re
import shutil
import subprocess
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import config, gallery, generate, paths, themes
from .session import _run, dmenu, notify

LIBEXEC = generate.LIBEXEC


# ------------------------------------------------------------------ basics --

def flyout(label: str, text: str, *, markup: bool = False) -> None:
    """A short flyout like the volume one (libexec/surfd-osd message)."""
    osd = LIBEXEC / "surfd-osd"
    if osd.exists():
        subprocess.run([str(osd), "markup" if markup else "message", label, text], check=False)
    else:
        notify(label, text, timeout_ms=1500)


def refresh_bar() -> None:
    """Ask Waybar to re-read surfd's status modules now (they also poll)."""
    if shutil.which("pkill"):
        subprocess.run(["pkill", "-RTMIN+8", "-x", "waybar"], check=False)


def spawn(cmd: list[str]) -> None:
    subprocess.Popen(cmd, start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def copy_text(text: str) -> bool:
    if not shutil.which("wl-copy"):
        return False
    subprocess.run(["wl-copy", "--", text], check=False)
    return True


def sway_json(kind: str) -> Any:
    r = _run(["swaymsg", "-r", "-t", kind])
    if r.returncode != 0:
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def walk(node: dict[str, Any]) -> list[dict[str, Any]]:
    out = [node]
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        out += walk(child)
    return out


def windows(tree: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(workspace name, window) for every real window, scratchpad included."""
    found: list[tuple[str, dict[str, Any]]] = []

    def visit(node: dict[str, Any], ws: str) -> None:
        if node.get("type") == "workspace":
            ws = node.get("name", "")
        if node.get("type") in ("con", "floating_con") and (node.get("app_id") or node.get("window")):
            found.append((ws, node))
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            visit(child, ws)

    visit(tree, "")
    return found


def focused(tree: dict[str, Any]) -> dict[str, Any] | None:
    return next((n for n in walk(tree) if n.get("focused")), None)


def app_name(win: dict[str, Any]) -> str:
    return win.get("app_id") or (win.get("window_properties") or {}).get("class") or "app"


def terminal_cmd(app_id: str, *argv: str) -> list[str]:
    """A terminal with its own app id (foot), running argv."""
    if shutil.which("foot"):
        return ["foot", "--app-id", app_id, *argv]
    try:
        term = config.get(config.load(), "apps.terminal") or "foot"
    except config.ConfigError:
        term = "foot"
    return [*term.split(), "-e", *argv]


# --------------------------------------------------------------- windows --

def window_switcher() -> None:
    tree = sway_json("get_tree")
    if not tree:
        return
    rows: dict[str, int] = {}
    for ws, win in windows(tree):
        where = "scratch" if ws == "__i3_scratch" else ws
        label = f"{where:>3}  {app_name(win)[:18]:<18}  {(win.get('name') or '')[:60]}"
        while any(k.split("\0")[0] == label for k in rows):
            label += " "
        icon = app_name(win).lower()
        rows[label + "\0icon\x1f" + icon] = int(win["id"])
    labels = list(rows)
    choice = dmenu(labels, "window > ", width=70, lines=min(max(len(labels), 1), 14))
    if not choice:
        return
    con = next((cid for label, cid in rows.items() if label.split("\0")[0] == choice), None)
    if con is not None:
        _run(["swaymsg", f"[con_id={con}] focus"])


def window_opacity() -> None:
    tree = sway_json("get_tree")
    win = focused(tree) if tree else None
    if not win:
        return
    see_through = float(win.get("opacity", 1.0)) < 0.99
    _run(["swaymsg", f"[con_id={win['id']}] opacity {'1' if see_through else '0.88'}"])


def empty_workspace() -> None:
    used = {int(w["num"]) for w in sway_json("get_workspaces") or [] if int(w.get("num", -1)) > 0}
    n = next(i for i in range(1, 100) if i not in used)
    _run(["swaymsg", f"workspace number {n}"])


def dropdown() -> None:
    """Show or hide the drop-down terminal; start it the first time."""
    tree = sway_json("get_tree")
    exists = bool(tree) and any(w.get("app_id") == "surfd-dropdown" for _, w in windows(tree))
    if exists:
        _run(["swaymsg", '[app_id="^surfd-dropdown$"] scratchpad show'])
    else:
        spawn(terminal_cmd("surfd-dropdown"))


def system_monitor() -> None:
    for tool in ("btop", "htop", "top"):
        if shutil.which(tool):
            spawn(terminal_cmd("surfd-monitor", tool))
            return


# ----------------------------------------------------------- calculator --

_OPS: dict[type, Callable[..., Any]] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
_NAMES: dict[str, Any] = {
    "pi": math.pi, "e": math.e, "tau": math.tau, "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
    "tan": math.tan, "asin": math.asin, "acos": math.acos, "atan": math.atan, "log": math.log10,
    "ln": math.log, "log2": math.log2, "exp": math.exp, "abs": abs, "round": round, "floor": math.floor,
    "ceil": math.ceil, "deg": math.degrees, "rad": math.radians, "fact": math.factorial,
}


class CalcError(ValueError):
    pass


def calculate(expr: str) -> float | int:
    """Evaluate arithmetic safely: numbers, + - * / // % ^ **, brackets and a few functions."""
    text = expr.strip().replace("^", "**").replace("×", "*").replace("÷", "/").replace(",", "")
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%(?!\s*[\d(])", r"(\1/100)", text)  # 15% -> 0.15
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        raise CalcError(f"can't read '{expr}'") from None

    def ev(node: ast.AST) -> Any:
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                raise CalcError("that power is too large")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        if isinstance(node, ast.Name) and node.id in _NAMES and not callable(_NAMES[node.id]):
            return _NAMES[node.id]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _NAMES
                and callable(_NAMES[node.func.id]) and not node.keywords):
            return _NAMES[node.func.id](*[ev(a) for a in node.args])
        raise CalcError(f"'{expr}' uses something the calculator doesn't know")

    try:
        value = ev(tree)
    except (ZeroDivisionError, OverflowError, ValueError, TypeError) as e:
        raise CalcError(str(e)) from None
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        return int(value)
    return value


def format_number(value: float | int) -> str:
    if isinstance(value, int):
        return str(value)
    return f"{value:.10g}"


def calculator() -> None:
    expr = dmenu([], "calc > ", width=40, lines=0)
    while expr:
        try:
            result = format_number(calculate(expr))
        except CalcError as e:
            expr = dmenu([], f"{e} > ", width=50, lines=0)
            continue
        copy_text(result)
        flyout("calc", f"{expr} = {result}   (copied)")
        # Keep going: the next prompt starts from the result.
        expr = dmenu([], f"= {result} > ", width=40, lines=0)


# ----------------------------------------------------------------- emoji --

_EMOJI_RANGES = [(0x1F300, 0x1F5FF), (0x1F600, 0x1F64F), (0x1F680, 0x1F6FF), (0x1F900, 0x1F9FF),
                 (0x1FA70, 0x1FAFF), (0x2600, 0x26FF), (0x2700, 0x27BF), (0x2190, 0x21FF), (0x2300, 0x23FF)]


def emoji_list() -> list[tuple[str, str]]:
    """(character, lowercase name) for every emoji and common symbol Python knows."""
    out: list[tuple[str, str]] = []
    for lo, hi in _EMOJI_RANGES:
        for cp in range(lo, hi + 1):
            ch = chr(cp)
            name = unicodedata.name(ch, "")
            if name and unicodedata.category(ch) == "So":
                out.append((ch, name.lower()))
    return out


def emoji_picker() -> None:
    items = emoji_list()
    labels = [f"{ch}  {name}" for ch, name in items]
    choice = dmenu(labels, "emoji > ", width=48, lines=14)
    if not choice:
        return
    ch = choice.split("  ", 1)[0]
    copy_text(ch)
    if shutil.which("wtype"):
        subprocess.run(["wtype", ch], check=False)


# ------------------------------------------------------------- clipboard --

def clipboard_file() -> Path:
    return paths.state_dir() / "clipboard.json"


def clipboard_load() -> list[str]:
    try:
        data = json.loads(clipboard_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return [x for x in data if isinstance(x, str)] if isinstance(data, list) else []


def clipboard_save(items: list[str]) -> None:
    f = clipboard_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(f)


def clipboard_store(text: str, limit: int) -> bool:
    """Remember one copied text (newest first). Skips blanks, huge blobs and password managers."""
    if os.environ.get("CLIPBOARD_STATE") == "sensitive" or not text.strip() or len(text) > 100_000:
        return False
    items = [x for x in clipboard_load() if x != text]
    clipboard_save([text, *items][:limit])
    return True


def clipboard_label(i: int, text: str) -> str:
    one = " ".join(text.split())
    return f"{i:>3}  {one[:90]}{'…' if len(one) > 90 else ''}"


def clipboard_menu() -> None:
    items = clipboard_load()
    if not items:
        flyout("clip", "nothing copied yet")
        return
    labels = [clipboard_label(i + 1, t) for i, t in enumerate(items)]
    choice = dmenu([*labels, "  ×  clear history"], "clipboard > ", width=80, lines=14)
    if not choice:
        return
    if choice.endswith("clear history"):
        clipboard_save([])
        flyout("clip", "history cleared")
        return
    index = labels.index(choice) if choice in labels else -1
    if index >= 0:
        copy_text(items[index])
        clipboard_save([items[index], *items[:index], *items[index + 1:]])


# ---------------------------------------------------------- notifications --

def dnd(mode: str) -> bool:
    """Do not disturb on/off/toggle; returns the new state."""
    current = bool(config.get(config.load(), "notifications.do_not_disturb"))
    new = {"on": True, "off": False}.get(mode, not current)
    config.set_values({"notifications.do_not_disturb": new})
    if shutil.which("makoctl"):
        subprocess.run(["makoctl", "mode", "-s", "do-not-disturb" if new else "default"], check=False)
    flyout("dnd", "on" if new else "off")
    refresh_bar()
    return new


def notification_history() -> list[dict[str, str]]:
    """Mako's notification history over D-Bus (newest first)."""
    if not shutil.which("busctl"):
        return []
    r = _run(["busctl", "--user", "--json=short", "call", "org.freedesktop.Notifications",
              "/fr/emersion/Mako", "fr.emersion.Mako", "ListHistory"])
    if r.returncode != 0:
        return []
    try:
        data = json.loads(r.stdout)["data"][0]
    except (json.JSONDecodeError, KeyError, IndexError):
        return []
    out = []
    for n in data:
        out.append({k: str((n.get(k) or {}).get("data", "")) for k in ("app-name", "summary", "body")})
    return out


def notifications_menu() -> None:
    history = notification_history()
    if not history:
        flyout("ntf", "no notifications yet")
        return
    labels = []
    for i, n in enumerate(history):
        body = re.sub(r"<[^>]+>", "", n["body"]).replace("\n", " ")
        labels.append(f"{i + 1:>3}  {n['app-name'][:12]:<12}  {n['summary'][:40]}  {body[:50]}")
    choice = dmenu(labels, "notifications > ", width=90, lines=14)
    if choice in labels:
        n = history[labels.index(choice)]
        notify(n["summary"], re.sub(r"<[^>]+>", "", n["body"]))


# ---------------------------------------------------------- quick toggles --

def awake(mode: str) -> bool:
    """Keep awake: stop locking, screen-off and sleep until switched off (or logout)."""
    flag = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "surfd-awake"
    new = {"on": True, "off": False}.get(mode, not flag.exists())
    if new:
        flag.touch()
        subprocess.run(["pkill", "-x", "-u", str(os.getuid()), "swayidle"], check=False)
    else:
        flag.unlink(missing_ok=True)
        cfg = config.load()
        spawn([str(LIBEXEC / "surfd-idle"), str(config.get(cfg, "idle.lock_after")),
               str(config.get(cfg, "idle.screen_off_after")), str(config.get(cfg, "idle.suspend_after"))])
    flyout("awake", "on" if new else "off")
    refresh_bar()
    return new


def nightlight_toggle(apply: Callable[[dict[str, Any], str], int]) -> int:
    current = config.get(config.load(), "display.night_light")
    new = "off" if current != "off" else "auto"
    rc = apply({"display.night_light": new}, f"night light {new}")
    flyout("night", "sunset to sunrise" if new == "auto" else "off")
    refresh_bar()
    return rc


def power_profiles() -> tuple[str, list[str]]:
    if not shutil.which("powerprofilesctl"):
        return "", []
    current = _run(["powerprofilesctl", "get"]).stdout.strip()
    listed = re.findall(r"^[ *]+([a-z-]+):", _run(["powerprofilesctl", "list"]).stdout, re.M)
    order = [p for p in ("power-saver", "balanced", "performance") if p in listed] or listed
    return current, order


def power_profile(choice: str) -> None:
    current, order = power_profiles()
    if not order:
        flyout("power", "power profiles are not available")
        return
    if choice == "next":
        target = order[(order.index(current) + 1) % len(order)] if current in order else order[0]
    elif choice == "menu":
        picked = dmenu([f"{'●' if p == current else ' '} {p}" for p in order], "profile > ", width=28,
                       lines=len(order))
        if not picked:
            return
        target = picked[2:]
    else:
        target = choice
    if target not in order:
        flyout("power", f"unknown profile {target}")
        return
    _run(["powerprofilesctl", "set", target])
    flyout("power", target.replace("-", " "))
    refresh_bar()


# ----------------------------------------------------------- sound output --

def audio_devices() -> dict[str, list[tuple[str, str, bool]]]:
    """{'sinks': [(id, name, is_default)], 'sources': [...]} parsed from `wpctl status`."""
    out: dict[str, list[tuple[str, str, bool]]] = {"sinks": [], "sources": []}
    if not shutil.which("wpctl"):
        return out
    section = ""
    in_audio = False
    for line in _run(["wpctl", "status"]).stdout.splitlines():
        if line.startswith("Audio"):
            in_audio = True
            continue
        if line and not line[0].isspace() and not line.startswith("├") and not line.startswith("└"):
            in_audio = line.startswith("Audio")
        if not in_audio:
            continue
        head = re.sub(r"[│├└─\s]+", " ", line).strip()
        if head.startswith(("Sinks:", "Sources:")):
            section = "sinks" if head.startswith("Sinks") else "sources"
            continue
        if head.endswith(":"):
            section = ""
            continue
        m = re.match(r"(\*)?\s*(\d+)\.\s+(.+?)(\s+\[vol:.*\])?$", head)
        if section and m:
            out[section].append((m.group(2), m.group(3).strip(), bool(m.group(1))))
    return out


def audio_menu() -> None:
    devs = audio_devices()
    rows: dict[str, str] = {}
    for kind, label in (("sinks", "out"), ("sources", "in ")):
        for dev_id, name, default in devs[kind]:
            rows[f"{label}  {'●' if default else ' '} {name}"] = dev_id
    if not rows:
        flyout("audio", "no sound devices found")
        return
    rows["     mixer…"] = ""
    choice = dmenu(list(rows), "sound > ", width=60, lines=min(len(rows), 12))
    if not choice:
        return
    if not rows[choice]:
        spawn(["pavucontrol"])
        return
    _run(["wpctl", "set-default", rows[choice]])
    flyout("out" if choice.startswith("out") else "in", choice[7:])


# -------------------------------------------------------------- bluetooth --

def bluetooth_devices() -> list[tuple[str, str, bool]]:
    """(address, name, connected) of paired devices."""
    if not shutil.which("bluetoothctl"):
        return []
    out = _run(["bluetoothctl", "devices", "Paired"]).stdout
    if "Device" not in out:
        out = _run(["bluetoothctl", "paired-devices"]).stdout
    devices = []
    for addr, name in re.findall(r"^Device ([0-9A-F:]{17}) (.+)$", out, re.M):
        info = _run(["bluetoothctl", "info", addr]).stdout
        devices.append((addr, name, "Connected: yes" in info))
    return devices


def bluetooth_menu() -> None:
    if not shutil.which("bluetoothctl"):
        flyout("bt", "Bluetooth is not available")
        return
    powered = "Powered: yes" in _run(["bluetoothctl", "show"]).stdout
    rows: dict[str, tuple[str, str]] = {}
    if powered:
        for addr, name, connected in bluetooth_devices():
            rows[f"{'●' if connected else ' '} {name}"] = ("disconnect" if connected else "connect", addr)
    rows["  Bluetooth " + ("off" if powered else "on")] = ("power", "off" if powered else "on")
    rows["  pair a new device…"] = ("manager", "")
    choice = dmenu(list(rows), "bluetooth > ", width=44, lines=min(len(rows), 12))
    if not choice:
        return
    verb, arg = rows[choice]
    if verb == "manager":
        spawn(["blueman-manager"])
        return
    r = _run(["bluetoothctl", verb, arg])
    name = choice[2:]
    flyout("bt", f"{name}: {verb}{'ed' if r.returncode == 0 else ' failed'}" if verb != "power"
           else f"Bluetooth {arg}")


# ------------------------------------------------------- theme and wallpaper --

def theme_menu(apply: Callable[[dict[str, Any], str], int]) -> int:
    cfg = config.load()
    current = config.get(cfg, "theme.name")
    found, _ = themes.discover()
    rows = {f"{'●' if t.name == current else ' '} {t.title:<20} {'/'.join(t.variants):<10}": t.name for t in found}
    rows["  dark / light"] = ""
    choice = dmenu(list(rows), "theme > ", width=44, lines=14)
    if not choice:
        return 0
    if not rows[choice]:
        variant = "light" if config.get(cfg, "theme.variant") == "dark" else "dark"
        return apply({"theme.variant": variant}, f"style set to {variant}")
    return apply(themes.selection(rows[choice]), f"theme set to {rows[choice]}")


def next_wallpaper(apply: Callable[[dict[str, Any], str], int], step: int = 1) -> int:
    pics = gallery.discover()
    if not pics:
        flyout("wall", "no wallpapers installed")
        return 1
    current = os.path.expanduser(config.get(config.load(), "wallpaper.path") or "")
    paths_ = [str(p.path) for p in pics]
    i = (paths_.index(current) + step) % len(pics) if current in paths_ else 0
    pic = pics[i]
    rc = apply({"wallpaper.path": str(pic.path)}, f"wallpaper: {pic.title}")
    flyout("wall", pic.title)
    return rc


# ----------------------------------------------------------- the surfd menu --

MenuEntry = tuple[str, Any]  # (label, list of entries | argv to run)


def _s(*args: str) -> list[str]:
    return ["surfctl", *args]


def control_menu_tree() -> list[MenuEntry]:
    """The surfd menu (Super+Alt+Space). Leaves are commands; branches are sub-menus."""
    return [
        ("apps", ["fuzzel"]),
        ("capture", [
            ("screenshot: area", _s("screenshot", "area")),
            ("screenshot: window", _s("screenshot", "window")),
            ("screenshot: display", _s("screenshot", "output")),
            ("screenshot: area, then annotate", _s("screenshot", "area", "--edit")),
            ("screenshot: display in 5 s", _s("screenshot", "output", "--delay", "5")),
            ("record: area (again to stop)", _s("record", "area")),
            ("record: display (again to stop)", _s("record", "output")),
            ("pick a colour", _s("colorpick")),
            ("open the screenshots folder", _s("screenshot", "--open-folder")),
        ]),
        ("toggles", [
            ("do not disturb", _s("dnd", "toggle")),
            ("night light", _s("nightlight", "toggle")),
            ("keep awake", _s("awake", "toggle")),
            ("dark / light style", _s("theme", "variant", "toggle")),
            ("tiling / floating mode", _s("mode", "toggle")),
            ("hide / show the bar", ["pkill", "-x", "-USR1", "waybar"]),
        ]),
        ("theme", _s("menu", "theme")),
        ("wallpaper", [
            ("next", _s("wallpaper", "next")),
            ("previous", _s("wallpaper", "previous")),
            ("follow the time of day (default)", _s("wallpaper", "reset")),
        ]),
        ("clipboard", _s("clipboard")),
        ("emoji", _s("emoji")),
        ("calculator", _s("calc")),
        ("notifications", _s("notifications")),
        ("windows", _s("windows")),
        ("connections", [
            ("wi-fi", _s("network-menu")),
            ("bluetooth", _s("bluetooth-menu")),
            ("sound output", _s("audio-menu")),
            ("power profile", _s("power-profile", "menu")),
        ]),
        ("setup", [
            ("surf settings", ["surf-settings"]),
            ("keyboard shortcuts", _s("cheatsheet")),
            ("displays", ["wdisplays"]),
            ("printers", ["system-config-printer"]),
            ("edit surfd.toml", ["xdg-open", str(paths.user_config())]),
            ("check the setup (doctor)", terminal_cmd("surfd-monitor", "sh", "-c", "surfctl doctor; read -r _")),
        ]),
        ("update", terminal_cmd("surfd-monitor", "sh", "-c", "surfctl update; read -r _")),
        ("system", [
            ("lock", _s("lock")),
            ("log out", ["swaymsg", "exit"]),
            ("suspend", ["systemctl", "suspend"]),
            ("restart", ["systemctl", "reboot"]),
            ("shut down", ["systemctl", "poweroff"]),
            ("reload the desktop", _s("reload")),
        ]),
    ]


def control_menu(path: str = "") -> None:
    entries = control_menu_tree()
    trail = ["surfd"]
    for part in [p for p in path.split("/") if p]:
        branch = dict(entries).get(part)
        if not isinstance(branch, list) or not branch or isinstance(branch[0], str):
            break
        entries, trail = branch, [*trail, part]
    while True:
        labels = [f"{'›' if isinstance(v, list) and v and not isinstance(v[0], str) else ' '} {k}" for k, v in entries]
        choice = dmenu(labels, " / ".join(trail) + " > ", width=40, lines=min(len(labels), 15))
        if not choice:
            return
        key = choice[2:]
        value = dict(entries)[key]
        if isinstance(value, list) and value and not isinstance(value[0], str):
            entries, trail = value, [*trail, key]
            continue
        spawn(list(value))
        return


def menu_names() -> list[str]:
    return [k for k, v in control_menu_tree() if isinstance(v, list) and v and not isinstance(v[0], str)]


