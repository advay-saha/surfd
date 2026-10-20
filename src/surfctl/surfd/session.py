"""Talking to the running desktop: reload, gsettings, menus, screenshots."""

from __future__ import annotations

import datetime as _dt
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path

from . import config, dynwall, generate, keys, themes
from .generate import Context


def in_sway() -> bool:
    return bool(os.environ.get("SWAYSOCK")) and shutil.which("swaymsg") is not None


def _run(cmd: Sequence[str], *, input_text: str | None = None, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(cmd), input=input_text, text=True, capture_output=True, check=check)


def notify(summary: str, body: str = "", *, urgency_critical: bool = False, timeout_ms: int = 5000) -> None:
    """Send a desktop notification over D-Bus using gdbus (always present)."""
    if not shutil.which("gdbus") or not os.environ.get("DBUS_SESSION_BUS_ADDRESS", os.environ.get("WAYLAND_DISPLAY")):
        return
    hints = "{'urgency': <byte 2>}" if urgency_critical else "{}"
    _run(["gdbus", "call", "--session", "--dest", "org.freedesktop.Notifications",
          "--object-path", "/org/freedesktop/Notifications",
          "--method", "org.freedesktop.Notifications.Notify",
          "surfd", "0", "preferences-desktop", summary, body, "[]", hints, str(timeout_ms)])


# ------------------------------------------------------------ validation --

def validate_sway_config(text: str) -> tuple[bool, str]:
    """Check generated Sway config with `sway --validate` when sway exists."""
    sway = shutil.which("sway")
    if sway is None:
        return True, "sway not installed; skipped validation"
    with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as fh:
        fh.write(text)
        tmp = fh.name
    # Headless backend + software renderer: validation needs no GPU or seat
    # (sway 1.9+ creates its backend before parsing the config).
    env = dict(os.environ, WLR_BACKENDS="headless", WLR_RENDERER="pixman", WLR_LIBINPUT_NO_DEVICES="1")
    env.pop("WAYLAND_DISPLAY", None)
    runtime = None
    if not env.get("XDG_RUNTIME_DIR"):
        # sway refuses to start (even to validate) without a runtime dir,
        # e.g. inside an RPM build or a kickstart %post.
        runtime = tempfile.mkdtemp(prefix="surfd-validate-")
        env["XDG_RUNTIME_DIR"] = runtime
    try:
        r = subprocess.run([sway, "--validate", "--config", tmp], text=True, capture_output=True, env=env, check=False)
        out = (r.stdout + r.stderr).strip()
        # sway --validate exits 0 even for some recoverable errors; look for them.
        bad = r.returncode != 0 or re.search(r"\[(ERROR|error)\]|Error on line", out)
        return (not bad), out
    finally:
        os.unlink(tmp)
        if runtime:
            shutil.rmtree(runtime, ignore_errors=True)


# ---------------------------------------------------------------- apply --

def desktop_settings(ctx: Context) -> list[str]:
    """Push theme choices to gsettings (GTK4/libadwaita, portals) and Sway."""
    p, c = ctx.pal, ctx.c
    done: list[str] = []
    if shutil.which("gsettings"):
        schema = "org.gnome.desktop.interface"
        values = {
            "color-scheme": "prefer-dark" if p.is_dark else "default",
            "gtk-theme": "adw-gtk3-dark" if p.is_dark else "adw-gtk3",
            "icon-theme": p.icon_theme,
            "cursor-theme": ctx.theme.cursor_theme,
            "cursor-size": str(ctx.theme.cursor_size),
            "font-name": f"{c('fonts.ui')} {c('fonts.size')}",
            "monospace-font-name": f"{c('fonts.mono')} {c('fonts.mono_size')}",
        }
        for key, value in values.items():
            r = _run(["gsettings", "set", schema, key, value])
            if r.returncode == 0:
                done.append(f"gsettings {key}")
    if in_sway():
        _run(["swaymsg", "seat", "seat0", "xcursor_theme", ctx.theme.cursor_theme, str(ctx.theme.cursor_size)])
        done.append("sway cursor")
    return done


def reload_session(ctx: Context) -> list[str]:
    """Ask the running session to pick up freshly written config files."""
    done: list[str] = []
    if in_sway():
        r = _run(["swaymsg", "reload"])
        if r.returncode == 0:
            done.append("sway (bar, idle, notifications restarted)")
        else:
            done.append(f"sway reload FAILED: {(r.stdout + r.stderr).strip()}")
    done += desktop_settings(ctx)
    return done


# ------------------------------------------------------------- menus -----

def dmenu(options: list[str], prompt: str, *, width: int = 40, lines: int | None = None) -> str | None:
    if not shutil.which("fuzzel"):
        return None
    cmd = ["fuzzel", "--dmenu", "--prompt", prompt, "--width", str(width)]
    if lines:
        cmd += ["--lines", str(lines)]
    r = _run(cmd, input_text="\n".join(options) + "\n")
    choice = r.stdout.strip()
    return choice or None


POWER_ACTIONS = {
    "Lock": ["surfctl", "lock"],
    "Log out": ["swaymsg", "exit"],
    "Suspend": ["systemctl", "suspend"],
    "Restart": ["systemctl", "reboot"],
    "Shut down": ["systemctl", "poweroff"],
}


def power_menu() -> None:
    choice = dmenu(list(POWER_ACTIONS), "power > ", width=22, lines=len(POWER_ACTIONS))
    if choice in POWER_ACTIONS:
        subprocess.Popen(POWER_ACTIONS[choice], start_new_session=True)


def cheatsheet(ctx: Context) -> None:
    rows = keys.cheatsheet_lines(ctx.cfg)
    binds = {b.description: b.command for b in keys.compile_bindings(ctx.cfg)}
    width = max(len(k) for _, k, _ in rows) + 2
    lines, commands = [], {}
    for category, combo, desc in rows:
        line = f"{combo.ljust(width)}{desc}   · {category.lower()}"
        lines.append(line)
        if desc in binds:
            commands[line] = binds[desc]
    choice = dmenu(lines, "keys > ", width=78, lines=18)
    if choice and choice in commands and in_sway():
        _run(["swaymsg", commands[choice]])


def network_menu() -> None:
    """Pick a Wi-Fi network with fuzzel; asks for the password if needed."""
    if not shutil.which("nmcli"):
        notify("Network", "nmcli is not installed")
        return
    r = _run(["nmcli", "-t", "-f", "IN-USE,SIGNAL,SECURITY,SSID", "device", "wifi", "list", "--rescan", "auto"])
    networks: dict[str, tuple[str, bool]] = {}
    for line in r.stdout.splitlines():
        # nmcli -t escapes ':' inside fields as '\:'
        parts = re.split(r"(?<!\\):", line)
        if len(parts) < 4 or not parts[3]:
            continue
        in_use, signal, security, ssid = parts[0], parts[1], parts[2], parts[3].replace("\\:", ":")
        if ssid in networks:
            continue
        lock_mark = "🔒" if security and security != "--" else "  "
        label = f"{'● ' if in_use == '*' else '  '}{ssid}   {signal}% {lock_mark}"
        networks[label] = (ssid, bool(security and security != "--"))
    options = [*list(networks), "Wi-Fi on/off", "Advanced settings…"]
    choice = dmenu(options, "wifi > ", width=44, lines=min(len(options), 12))
    if not choice:
        return
    if choice == "Wi-Fi on/off":
        state = _run(["nmcli", "radio", "wifi"]).stdout.strip()
        _run(["nmcli", "radio", "wifi", "off" if state == "enabled" else "on"])
        return
    if choice == "Advanced settings…":
        subprocess.Popen(["nm-connection-editor"], start_new_session=True)
        return
    ssid, secured = networks[choice]
    known = ssid in _run(["nmcli", "-t", "-f", "NAME", "connection", "show"]).stdout.splitlines()
    cmd = ["nmcli", "device", "wifi", "connect", ssid]
    if secured and not known:
        pw = _run(["fuzzel", "--dmenu", "--password", "--prompt", f"password for {ssid} > ", "--lines", "0"],
                  input_text="").stdout.strip()
        if not pw:
            return
        cmd += ["password", pw]
    result = _run(cmd)
    if result.returncode == 0:
        notify("Connected", ssid)
    else:
        notify("Could not connect", f"{ssid}: {(result.stderr or result.stdout).strip()}", urgency_critical=True)


def lock() -> None:
    subprocess.Popen(["swaylock", "-f"], start_new_session=True)


def screenshot(mode: str) -> Path | None:
    pictures = Path(os.environ.get("XDG_PICTURES_DIR", "")) if os.environ.get("XDG_PICTURES_DIR") else None
    if pictures is None and shutil.which("xdg-user-dir"):
        out = _run(["xdg-user-dir", "PICTURES"]).stdout.strip()
        pictures = Path(out) if out else None
    folder = (pictures or Path.home() / "Pictures") / "Screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"Screenshot_{_dt.datetime.now():%Y-%m-%d_%H-%M-%S}.png"
    cmd = ["grim"]
    if mode == "area":
        sel = _run(["slurp", "-d"])
        if sel.returncode != 0 or not sel.stdout.strip():
            return None  # cancelled
        cmd += ["-g", sel.stdout.strip()]
    cmd.append(str(target))
    if _run(cmd).returncode != 0:
        notify("Screenshot failed", "grim could not capture the screen", urgency_critical=True)
        return None
    if shutil.which("wl-copy"):
        with target.open("rb") as fh:
            subprocess.run(["wl-copy", "--type", "image/png"], stdin=fh, check=False)
    notify("Screenshot saved", f"{target}\nAlso copied to the clipboard.")
    return target


def regenerate_and_reload(ctx: Context, *, reload: bool = True) -> tuple[generate.WriteReport, list[str]]:
    """Write config files (refusing a Sway config that fails validation)."""
    ok, msg = validate_sway_config(generate.sway(ctx))
    if not ok:
        raise RuntimeError("generated Sway config failed validation; nothing was changed:\n" + msg)
    report = generate.write_all(ctx)
    actions = reload_session(ctx) if reload else []
    return report, actions


# ------------------------------------------------------ dynamic wallpaper --

def apply_wallpaper(ctx: Context) -> Path | None:
    """Show the dynamic wallpaper frame for this moment on every output; returns it (None: no dynamic wallpaper)."""
    if ctx.dynamic is None:
        return None
    frame = ctx.dynamic[1]
    dynwall.update_link(frame)
    if in_sway():
        _run(["swaymsg", f'output * bg "{frame}" {ctx.c("wallpaper.mode")} {ctx.pal.background}'])
    return frame


def wallpaper_daemon(*, once: bool = False) -> int:
    """Keep the wallpaper on the right frame while it follows the clock. Stops when the settings no longer ask for that.

    Started by the Sway config through libexec/surfd-dynwall (restarted on every reload).
    """
    last: Path | None = None
    while True:
        try:
            ctx = generate.build_context()
        except (config.ConfigError, themes.ThemeError, OSError):
            if once:
                return 1
            time.sleep(60)  # a half-edited config: try again shortly
            continue
        if not ctx.dynamic_follows_clock:
            return 0
        assert ctx.dynamic is not None
        if ctx.dynamic[1] != last:
            last = apply_wallpaper(ctx)
        if once:
            return 0
        time.sleep(dynwall.seconds_to_next_change(ctx.dynamic[0], dynwall.now()))
