"""The surfd.toml schema: every supported key, its type, limits and help.

This is the single source of truth used by validation, `surfctl set`,
`surfctl explain` and the Surf Settings GUI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import color

BAR_MODULES = {
    "workspaces": "Workspace buttons",
    "mode": "Current Sway mode (e.g. resize)",
    "window": "Focused window title",
    "taskbar": "Open windows (good for floating mode)",
    "clock": "Date and time",
    "tray": "System tray (network, Bluetooth applets)",
    "network": "Wi-Fi / Ethernet status",
    "audio": "Volume (click: mixer)",
    "battery": "Battery level",
    "backlight": "Screen brightness",
    "bluetooth": "Bluetooth status",
    "cpu": "CPU usage",
    "memory": "Memory usage",
    "temperature": "CPU temperature",
    "keyboard": "Keyboard layout",
    "media": "Now playing (MPRIS)",
    "idle": "Keep-awake toggle",
    "power": "Power menu button",
}


class SchemaError(ValueError):
    pass


@dataclass(frozen=True)
class Field:
    kind: str  # str | int | float | bool | enum | color? | list | modules
    help: str
    choices: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    label: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def coerce(self, raw: Any) -> Any:
        """Convert a CLI string (or native value) to this field's type."""
        k = self.kind
        if k == "bool":
            if isinstance(raw, bool):
                return raw
            s = str(raw).strip().lower()
            if s in ("1", "true", "yes", "on"):
                return True
            if s in ("0", "false", "no", "off"):
                return False
            raise SchemaError(f"expected true/false, got '{raw}'")
        if k in ("int", "float"):
            try:
                v = int(raw) if k == "int" else float(raw)
            except (TypeError, ValueError):
                raise SchemaError(f"expected a {'whole ' if k == 'int' else ''}number, got '{raw}'") from None
            if isinstance(raw, bool):
                raise SchemaError(f"expected a number, got '{raw}'")
            return v
        if k in ("list", "modules"):
            if isinstance(raw, list):
                return [str(x) for x in raw]
            s = str(raw).strip()
            return [x.strip() for x in s.split(",") if x.strip()] if s else []
        if k == "color?":
            s = str(raw).strip()
            if s in ("", "default", "none"):
                return ""
            return color.normalize(s)
        return str(raw)

    def check(self, value: Any) -> str | None:
        """Return an error message, or None when value is valid."""
        k = self.kind
        if k == "bool" and not isinstance(value, bool):
            return "must be true or false"
        if k == "int" and (isinstance(value, bool) or not isinstance(value, int)):
            return "must be a whole number"
        if k == "float" and (isinstance(value, bool) or not isinstance(value, (int, float))):
            return "must be a number"
        if k in ("int", "float"):
            if self.minimum is not None and value < self.minimum:
                return f"must be at least {self.minimum:g}"
            if self.maximum is not None and value > self.maximum:
                return f"must be at most {self.maximum:g}"
        if k in ("str", "enum", "color?") and not isinstance(value, str):
            return "must be text in quotes"
        if k == "enum" and value not in self.choices:
            return f"must be one of: {', '.join(self.choices)}"
        if k == "color?" and value and not color.is_color(value):
            return "must be \"\" or a colour like \"#88c0d0\""
        if k in ("list", "modules"):
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                return "must be a list of strings, e.g. [\"a\", \"b\"]"
            if k == "modules":
                unknown = [m for m in value if m not in BAR_MODULES]
                if unknown:
                    return f"unknown bar module(s): {', '.join(unknown)} (see `surfctl bar modules`)"
        return None


def _f(kind: str, help: str, label: str = "", **kw: Any) -> Field:
    return Field(kind=kind, help=help, label=label, **kw)


NOTIFY_POSITIONS = ("top-right", "top-center", "top-left", "bottom-right", "bottom-center", "bottom-left")

SCHEMA: dict[str, Field] = {
    "theme.name": _f("str", "Theme pack name (a folder in ~/.local/share/surfd/themes or /usr/share/surfd/themes).", "Theme"),
    "theme.variant": _f("enum", "Dark or light colours.", "Style", choices=("dark", "light")),
    "theme.accent": _f("color?", "Accent colour like \"#88c0d0\"; empty uses the theme's accent.", "Accent colour"),
    "fonts.ui": _f("str", "Interface font family.", "Interface font"),
    "fonts.mono": _f("str", "Monospace font family (terminal, code).", "Monospace font"),
    "fonts.size": _f("int", "Interface font size in points.", "Interface size", minimum=6, maximum=32),
    "fonts.mono_size": _f("int", "Monospace font size in points.", "Monospace size", minimum=6, maximum=32),
    "wallpaper.path": _f("str", "Image file; empty uses the theme's wallpaper for the current style.", "Wallpaper"),
    "wallpaper.mode": _f("enum", "How the image is scaled.", "Scaling", choices=("fill", "fit", "center", "tile", "stretch")),
    "layout.mode": _f("enum", "tiling: windows tile automatically. floating: windows float with title bars (mouse-friendly).",
                      "Window mode", choices=("tiling", "floating")),
    "layout.gaps_inner": _f("int", "Space between windows in pixels.", "Inner gaps", minimum=0, maximum=64),
    "layout.gaps_outer": _f("int", "Space around the screen edge in pixels.", "Outer gaps", minimum=0, maximum=64),
    "layout.border_width": _f("int", "Window border width in pixels.", "Border width", minimum=0, maximum=10),
    "layout.radius": _f("int", "Corner rounding for the bar, notifications, launcher and lock screen. "
                        "(Sway draws square window borders.)", "Corner radius", minimum=0, maximum=32),
    "layout.titlebars": _f("bool", "Show window title bars in tiling mode (always on in floating mode).", "Title bars"),
    "layout.focus_follows_mouse": _f("bool", "Focus windows by hovering.", "Focus follows mouse"),
    "bar.position": _f("enum", "Bar at the top or bottom of the screen.", "Position", choices=("top", "bottom")),
    "bar.style": _f("enum", "floating: a detached rounded bar. docked: full-width, edge to edge.", "Bar style",
                    choices=("floating", "docked")),
    "bar.height": _f("int", "Bar height in pixels.", "Height", minimum=20, maximum=64),
    "bar.left": _f("modules", "Modules on the left.", "Left"),
    "bar.center": _f("modules", "Modules in the centre.", "Centre"),
    "bar.right": _f("modules", "Modules on the right.", "Right"),
    "input.keyboard_layout": _f("str", "XKB layout(s), e.g. \"us\" or \"us,de\".", "Keyboard layout"),
    "input.keyboard_variant": _f("str", "XKB variant, e.g. \"intl\" or \"\".", "Variant"),
    "input.keyboard_options": _f("str", "XKB options, e.g. \"caps:escape,grp:alt_shift_toggle\".", "Options"),
    "input.touchpad_tap": _f("bool", "Tap to click on touchpads.", "Tap to click"),
    "input.natural_scroll": _f("bool", "Content follows your fingers on touchpads.", "Natural scrolling"),
    "input.gestures": _f("bool", "Three-finger swipes switch workspaces; swipe up opens the launcher.", "Touchpad gestures"),
    "input.pointer_accel": _f("float", "Pointer speed from -1 (slow) to 1 (fast).", "Pointer speed", minimum=-1, maximum=1),
    "display.scale": _f("float", "Output scale for all displays; 0 lets Sway decide.", "Scale", minimum=0, maximum=4),
    "apps.terminal": _f("str", "Terminal command.", "Terminal"),
    "apps.launcher": _f("str", "App launcher command (fuzzel by default).", "Launcher"),
    "apps.browser": _f("str", "Web browser command.", "Browser"),
    "apps.files": _f("str", "File manager command.", "Files"),
    "apps.editor": _f("str", "Text editor command.", "Editor"),
    "idle.lock_after": _f("int", "Lock the screen after this many idle seconds (0 = never).", "Lock after", minimum=0, maximum=86400),
    "idle.screen_off_after": _f("int", "Turn displays off after this many idle seconds (0 = never).", "Screen off after",
                                minimum=0, maximum=86400),
    "idle.suspend_after": _f("int", "Suspend after this many idle seconds (0 = never).", "Suspend after", minimum=0, maximum=86400),
    "notifications.position": _f("enum", "Where notifications appear.", "Position", choices=NOTIFY_POSITIONS),
    "notifications.timeout": _f("int", "Milliseconds before a notification hides (0 = until dismissed).", "Timeout",
                                minimum=0, maximum=120000),
    "keys.modifier": _f("enum", "The main modifier used as \"Mod\" in key bindings.", "Main modifier", choices=("Super", "Alt")),
    "autostart.commands": _f("list", "Commands started with the session.", "Autostart"),
}

# Tables whose contents are free-form (validated elsewhere).
FREEFORM_TABLES = {"keys.bindings"}


def field_for(dotted: str) -> Field:
    try:
        return SCHEMA[dotted]
    except KeyError:
        close = [k for k in SCHEMA if k.split(".")[-1] == dotted.rsplit(".", maxsplit=1)[-1]]
        hint = f" Did you mean {close[0]}?" if close else " Run `surfctl explain` for all keys."
        raise SchemaError(f"unknown setting '{dotted}'.{hint}") from None


def sections() -> list[str]:
    seen: list[str] = []
    for key in SCHEMA:
        sec = key.split(".")[0]
        if sec not in seen:
            seen.append(sec)
    return seen
