"""Reading system-wide facts (no side effects)."""

from __future__ import annotations

import re
from pathlib import Path

X11_KEYBOARD = Path("/etc/X11/xorg.conf.d/00-keyboard.conf")
VCONSOLE = Path("/etc/vconsole.conf")


def system_keyboard(x11: Path = X11_KEYBOARD, vconsole: Path = VCONSOLE) -> dict[str, str]:
    """Keyboard layout chosen in the installer (localectl), if any.

    Anaconda/localectl write the X11 layout to 00-keyboard.conf; fall back
    to the console keymap in vconsole.conf.
    """
    result: dict[str, str] = {}
    if x11.is_file():
        text = x11.read_text(encoding="utf-8", errors="replace")
        for opt, key in (("XkbLayout", "layout"), ("XkbVariant", "variant"), ("XkbOptions", "options")):
            m = re.search(rf'Option\s+"{opt}"\s+"([^"]*)"', text)
            if m and m.group(1):
                result[key] = m.group(1)
    if "layout" not in result and vconsole.is_file():
        m = re.search(r'^KEYMAP="?([A-Za-z0-9_-]+)"?', vconsole.read_text(encoding="utf-8", errors="replace"), re.M)
        if m:
            # Console keymaps like "de-nodeadkeys" map to layout "de".
            result["layout"] = m.group(1).split("-")[0]
    return result


def is_live_session(cmdline: Path = Path("/proc/cmdline")) -> bool:
    try:
        return "rd.live.image" in cmdline.read_text(encoding="utf-8").split()
    except OSError:
        return False
