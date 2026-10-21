"""Key bindings: friendly names in surfd.toml -> Sway bindsym lines.

In surfd.toml:

    [keys.bindings]
    "Mod+Return" = "terminal"
    "Mod+Shift+3" = "move-to-workspace 3"
    "Mod+F1" = "exec foot -e htop"
    "Ctrl+Alt+t" = "sway layout toggle tabbed split"
    "Mod+p" = "none"            # removes a default binding

"Mod" is the modifier chosen with keys.modifier (Super by default).
"""

from __future__ import annotations

import os
import shlex
from dataclasses import dataclass
from typing import Any

MODIFIERS = {
    "super": "Mod4",
    "mod4": "Mod4",
    "win": "Mod4",
    "alt": "Mod1",
    "mod1": "Mod1",
    "ctrl": "Control",
    "control": "Control",
    "shift": "Shift",
}

DIRECTIONS = ("left", "right", "up", "down")


class BindingError(ValueError):
    pass


@dataclass(frozen=True)
class Action:
    category: str
    description: str
    command: str  # sway command; {apps.*} and {surfctl} are substituted
    locked: bool = False  # also works on the lock screen / when inhibited


SURFCTL = "surfctl"

# Order here is the order of the cheat sheet.
ACTIONS: dict[str, Action] = {
    # apps
    "terminal": Action("Apps", "Open a terminal", "exec {apps.terminal}"),
    "launcher": Action("Apps", "Search and launch apps", "exec {apps.launcher}"),
    "browser": Action("Apps", "Open the web browser", "exec {apps.browser}"),
    "files": Action("Apps", "Open the file manager", "exec {apps.files}"),
    "editor": Action("Apps", "Open the text editor", "exec {apps.editor}"),
    "settings": Action("Apps", "Open Surf Settings", "exec surf-settings"),
    "cheatsheet": Action("Apps", "Show this cheat sheet", "exec {surfctl} cheatsheet"),
    "control-menu": Action("Apps", "surfd menu: capture, toggles, theme, setup, system", "exec {surfctl} menu"),
    "dropdown-terminal": Action("Apps", "Drop-down terminal (show / hide)", "exec {surfctl} dropdown"),
    "system-monitor": Action("Apps", "System monitor", "exec {surfctl} monitor"),
    "calculator": Action("Apps", "Calculator (result is copied)", "exec {surfctl} calc"),
    "emoji": Action("Apps", "Emoji picker (copies and types it)", "exec {surfctl} emoji"),
    "clipboard": Action("Apps", "Clipboard history", "exec {surfctl} clipboard"),
    # windows
    "close": Action("Windows", "Close the window", "kill"),
    "fullscreen": Action("Windows", "Toggle fullscreen", "fullscreen toggle"),
    "toggle-floating": Action("Windows", "Float / tile the window", "floating toggle"),
    "focus-mode-toggle": Action("Windows", "Switch focus between tiled and floating", "focus mode_toggle"),
    "layout-toggle": Action("Windows", "Cycle layout: split, tabbed, stacked", "layout toggle split tabbed stacking"),
    "split-horizontal": Action("Windows", "Next window opens to the right", "splith"),
    "split-vertical": Action("Windows", "Next window opens below", "splitv"),
    "focus-parent": Action("Windows", "Focus the parent container", "focus parent"),
    "resize-mode": Action("Windows", "Resize with arrow keys (Esc to finish)", 'mode "resize"'),
    "scratchpad": Action("Windows", "Show / hide the scratchpad", "scratchpad show"),
    "move-to-scratchpad": Action("Windows", "Send the window to the scratchpad", "move scratchpad"),
    "window-switcher": Action("Windows", "Switch to any open window", "exec {surfctl} windows"),
    "sticky": Action("Windows", "Pin the floating window to every workspace", "sticky toggle"),
    "opacity": Action("Windows", "Make the window see-through / solid", "exec {surfctl} window opacity"),
    "center": Action("Windows", "Centre the floating window", "move position center"),
    "grow-width": Action("Windows", "Make the window wider", "resize grow width 40px"),
    "shrink-width": Action("Windows", "Make the window narrower", "resize shrink width 40px"),
    "grow-height": Action("Windows", "Make the window taller", "resize grow height 40px"),
    "shrink-height": Action("Windows", "Make the window shorter", "resize shrink height 40px"),
    "kill-all": Action("Windows", "Close every window on this workspace", "[workspace=__focused__] kill"),
    # workspaces
    "workspace-next": Action("Workspaces", "Next workspace", "workspace next_on_output"),
    "workspace-prev": Action("Workspaces", "Previous workspace", "workspace prev_on_output"),
    "workspace-last": Action("Workspaces", "Back to the last workspace", "workspace back_and_forth"),
    "workspace-empty": Action("Workspaces", "Go to an empty workspace", "exec {surfctl} window empty-workspace"),
    "workspace-to-output-left": Action("Workspaces", "Move this workspace to the display on the left",
                                       "move workspace to output left"),
    "workspace-to-output-right": Action("Workspaces", "Move this workspace to the display on the right",
                                        "move workspace to output right"),
    "focus-output-next": Action("Workspaces", "Focus the next display", "focus output right"),
    # capture
    "screenshot": Action("Capture", "Screenshot the whole screen", "exec {surfctl} screenshot full"),
    "screenshot-area": Action("Capture", "Screenshot a selected area", "exec {surfctl} screenshot area"),
    "screenshot-window": Action("Capture", "Screenshot the focused window", "exec {surfctl} screenshot window"),
    "screenshot-output": Action("Capture", "Screenshot the current display", "exec {surfctl} screenshot output"),
    "screenshot-edit": Action("Capture", "Screenshot an area and annotate it", "exec {surfctl} screenshot area --edit"),
    "record-area": Action("Capture", "Record an area (press again to stop)", "exec {surfctl} record area"),
    "record-screen": Action("Capture", "Record the display (press again to stop)", "exec {surfctl} record output"),
    "color-picker": Action("Capture", "Pick a colour from the screen (hex is copied)", "exec {surfctl} colorpick"),
    # system
    "lock": Action("System", "Lock the screen", "exec {surfctl} lock"),
    "power-menu": Action("System", "Log out, suspend, restart, shut down", "exec {surfctl} power-menu"),
    "reload": Action("System", "Reload the desktop configuration", "exec {surfctl} reload"),
    "notifications-dismiss": Action("System", "Dismiss notifications", "exec makoctl dismiss --all"),
    "notifications-restore": Action("System", "Show the last notification again", "exec makoctl restore"),
    "notification-history": Action("System", "Notification history", "exec {surfctl} notifications"),
    "dnd-toggle": Action("System", "Do not disturb on / off", "exec {surfctl} dnd toggle"),
    "nightlight-toggle": Action("System", "Night light on / off", "exec {surfctl} nightlight toggle"),
    "idle-toggle": Action("System", "Keep awake on / off (no lock or sleep)", "exec {surfctl} awake toggle"),
    "bar-toggle": Action("System", "Hide / show the bar", "exec pkill -x -USR1 waybar"),
    "theme-menu": Action("System", "Pick a theme", "exec {surfctl} menu theme"),
    "wallpaper-next": Action("System", "Next wallpaper", "exec {surfctl} wallpaper next"),
    "style-toggle": Action("System", "Switch between dark and light style", "exec {surfctl} theme variant toggle"),
    "wifi-menu": Action("System", "Wi-Fi networks", "exec {surfctl} network-menu"),
    "bluetooth-menu": Action("System", "Bluetooth devices", "exec {surfctl} bluetooth-menu"),
    "audio-menu": Action("System", "Choose the sound output", "exec {surfctl} audio-menu"),
    "power-profile": Action("System", "Next power profile (saver, balanced, performance)", "exec {surfctl} power-profile next"),
    "keyboard-layout-next": Action("System", "Next keyboard layout", "exec {osd} layout next"),
    # hardware keys (they also show a flyout)
    "volume-up": Action("Media", "Volume up", "exec {osd} volume up", True),
    "volume-down": Action("Media", "Volume down", "exec {osd} volume down", True),
    "volume-mute": Action("Media", "Mute / unmute", "exec {osd} volume mute", True),
    "mic-mute": Action("Media", "Mute / unmute microphone", "exec {osd} mic mute", True),
    "brightness-up": Action("Media", "Brightness up", "exec {osd} brightness up", True),
    "brightness-down": Action("Media", "Brightness down", "exec {osd} brightness down", True),
    "kbd-brightness-up": Action("Media", "Keyboard backlight up", "exec {osd} kbd-brightness up", True),
    "kbd-brightness-down": Action("Media", "Keyboard backlight down", "exec {osd} kbd-brightness down", True),
    "media-play": Action("Media", "Play / pause", "exec {osd} media play-pause", True),
    "media-next": Action("Media", "Next track", "exec {osd} media next", True),
    "media-prev": Action("Media", "Previous track", "exec {osd} media previous", True),
    "media-stop": Action("Media", "Stop playback", "exec playerctl stop", True),
}

PARAM_ACTIONS = {
    "focus": ("Windows", "Move focus {arg}", "focus {arg}"),
    "move": ("Windows", "Move the window {arg}", "move {arg}"),
    "workspace": ("Workspaces", "Go to workspace {arg}", "workspace number {arg}"),
    "move-to-workspace": ("Workspaces", "Send window to workspace {arg}", "move container to workspace number {arg}"),
}


@dataclass(frozen=True)
class Binding:
    combo: str  # as written by the user
    sway_combo: str  # e.g. "Mod4+Shift+q"
    action: str
    command: str  # resolved sway command
    description: str
    category: str
    locked: bool


def normalize_combo(combo: str, modifier: str) -> str:
    """'Mod+Shift+q' -> 'Mod4+Shift+q'. Raises BindingError."""
    if not combo or not combo.strip():
        raise BindingError("empty key combination")
    parts = [p.strip() for p in combo.split("+")]
    if any(not p for p in parts):
        raise BindingError(f"'{combo}': stray '+' (use 'plus' for the + key)")
    *mods, key = parts
    out: list[str] = []
    for m in mods:
        low = m.lower()
        if low == "mod":
            low = modifier.lower()
        if low not in MODIFIERS:
            raise BindingError(f"'{combo}': unknown modifier '{m}' (use Mod, Super, Alt, Ctrl, Shift)")
        sway_mod = MODIFIERS[low]
        if sway_mod in out:
            raise BindingError(f"'{combo}': modifier '{m}' repeated")
        out.append(sway_mod)
    if key.lower() in MODIFIERS or key.lower() == "mod":
        raise BindingError(f"'{combo}': ends with a modifier; add a key, e.g. '{combo}+Return'")
    if any(c.isspace() for c in key):
        raise BindingError(f"'{combo}': key names cannot contain spaces")
    # Canonical modifier order keeps duplicate detection reliable.
    order = ["Mod4", "Mod1", "Control", "Shift"]
    out.sort(key=order.index)
    return "+".join([*out, key])


def osd_command(osd: dict[str, Any]) -> str:
    """The flyout helper with the user's step; --quiet changes values without showing a flyout."""
    libexec = os.environ.get("SURFD_LIBEXEC", "/usr/libexec/surfd")
    cmd = f"{libexec}/surfd-osd --step {int(osd.get('step', 5))}"
    return cmd if osd.get("enabled", True) else cmd + " --quiet"


def resolve_action(action: str, apps: dict[str, Any], osd: dict[str, Any] | None = None) -> tuple[str, str, str, bool]:
    """Return (sway_command, description, category, locked)."""
    action = action.strip()
    if not action:
        raise BindingError("empty action")
    head, _, rest = action.partition(" ")
    rest = rest.strip()
    if head == "exec":
        if not rest:
            raise BindingError("'exec' needs a command, e.g. 'exec foot'")
        _check_exec(rest)
        return f"exec {rest}", f"Run: {rest}", "Custom", False
    if head == "sway":
        if not rest:
            raise BindingError("'sway' needs a Sway command, e.g. 'sway layout tabbed'")
        if "\n" in rest:
            raise BindingError("'sway' commands must fit on one line")
        return rest, f"Sway: {rest}", "Custom", False
    if head in PARAM_ACTIONS:
        if not rest:
            raise BindingError(f"'{head}' needs an argument")
        category, desc, cmd = PARAM_ACTIONS[head]
        if head in ("focus", "move") and rest not in DIRECTIONS:
            raise BindingError(f"'{head} {rest}': direction must be left, right, up or down")
        if head in ("workspace", "move-to-workspace") and not rest.isdigit():
            raise BindingError(f"'{head} {rest}': workspace must be a number")
        return cmd.format(arg=rest), desc.format(arg=rest), category, False
    if action not in ACTIONS:
        raise BindingError(f"unknown action '{action}' (see `surfctl keys actions`)")
    a = ACTIONS[action]
    cmd = a.command.replace("{surfctl}", SURFCTL).replace("{osd}", osd_command(osd or {}))
    for name, value in apps.items():
        cmd = cmd.replace("{apps." + name + "}", str(value))
    if a.command.startswith("exec {apps."):
        _check_exec(cmd[len("exec "):])
    if "{apps." in cmd:
        raise BindingError(f"action '{action}' needs an app that is not configured in [apps]")
    return cmd, a.description, a.category, a.locked


def _check_exec(command: str) -> None:
    # Sway splits commands on ';' and ',' before running exec, so a binding
    # like "exec a; b" would run "b" as a Sway command. Refuse it.
    bad = [c for c in ";,\n" if c in command]
    if bad:
        raise BindingError(
            f"command '{command}' contains {' '.join(repr(c) for c in bad)}; "
            "put it in a script and bind 'exec /path/to/script' instead")


def compile_bindings(cfg: dict[str, Any]) -> list[Binding]:
    """All effective bindings, validated. Raises BindingError on the first problem."""
    keys = cfg.get("keys", {})
    modifier = keys.get("modifier", "Super")
    apps = cfg.get("apps", {})
    seen: dict[str, str] = {}
    result: list[Binding] = []
    for combo, action in keys.get("bindings", {}).items():
        if not isinstance(action, str):
            raise BindingError(f"'{combo}': action must be text, e.g. \"terminal\"")
        if action.strip().lower() in ("none", ""):
            continue
        sway_combo = normalize_combo(combo, modifier)
        if sway_combo in seen:
            raise BindingError(f"'{combo}' and '{seen[sway_combo]}' are the same key combination")
        seen[sway_combo] = combo
        command, desc, category, locked = resolve_action(action, apps, cfg.get("osd", {}))
        result.append(Binding(combo, sway_combo, action, command, desc, category, locked))
    return result


def binding_problems(cfg: dict[str, Any]) -> list[str]:
    try:
        compile_bindings(cfg)
    except BindingError as e:
        return [f"keys.bindings: {e}"]
    return []


def pretty_combo(combo: str, modifier: str) -> str:
    """Human label for the cheat sheet: 'Mod+Shift+q' -> 'Super + Shift + Q'."""
    parts = combo.split("+")
    labels = []
    for p in parts[:-1]:
        low = p.lower()
        labels.append({"mod": modifier, "super": "Super", "win": "Super", "mod4": "Super", "alt": "Alt",
                       "mod1": "Alt", "ctrl": "Ctrl", "control": "Ctrl", "shift": "Shift"}.get(low, p))
    key = parts[-1]
    nice = {"Return": "Enter", "space": "Space", "slash": "/", "comma": ",", "period": ".", "minus": "-",
            "equal": "=", "grave": "`", "backslash": "\\", "Escape": "Esc", "Print": "PrtSc",
            "Left": "←", "Right": "→", "Up": "↑", "Down": "↓"}
    key = nice.get(key, key.upper() if len(key) == 1 else key.replace("XF86", ""))
    return " + ".join([*labels, key])


def cheatsheet_lines(cfg: dict[str, Any]) -> list[tuple[str, str, str]]:
    """(category, keys, description) rows, grouped by category, for display."""
    modifier = cfg.get("keys", {}).get("modifier", "Super")
    rows = [(b.category, pretty_combo(b.combo, modifier), b.description, b.command) for b in compile_bindings(cfg)]
    categories = ["Apps", "Windows", "Workspaces", "System", "Media", "Custom"]
    rows.sort(key=lambda r: (categories.index(r[0]) if r[0] in categories else 99))
    mouse = [
        ("Mouse", f"{modifier} + left drag", "Move a window"),
        ("Mouse", f"{modifier} + right drag", "Resize a window"),
    ]
    return [(c, k, d) for c, k, d, _ in rows] + mouse


def quote_exec(command: str) -> str:
    """Quote a shell command for a sway `exec` line."""
    return shlex.quote(command)
