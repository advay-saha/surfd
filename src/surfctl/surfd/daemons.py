"""Background helpers started by the session (through libexec/surfd-daemon).

    surfctl daemon autotile      split new windows along the longer side (dwindle-like)
    surfctl daemon power         low battery warnings and charger flyouts
    surfctl daemon nightlight M  run wlsunset for night light mode M (auto | on)
    surfctl daemon updates       count available updates every few hours (for the bar)

Each runs until the session ends or surfd-daemon replaces it after a reload.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import config, dynwall, paths
from .desktop import flyout, refresh_bar, walk
from .session import _run, notify


def session_alive() -> bool:
    """False once the Sway session that started us is gone (logout): helpers then exit."""
    sock = os.environ.get("SWAYSOCK", "")
    return not sock or os.path.exists(sock)


def sleep_while_alive(seconds: float) -> bool:
    """Sleep up to `seconds`, waking every 30 s to check the session; False if it ended."""
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if not session_alive():
            return False
        time.sleep(min(30.0, max(end - time.monotonic(), 0.0)))
    return session_alive()


# ---------------------------------------------------------------- autotile --


def split_for(rect: dict[str, int]) -> str:
    """The split that puts the next window along the window's longer side."""
    return "splitv" if rect.get("height", 0) > rect.get("width", 0) else "splith"


def parent_of(tree: dict[str, Any], con_id: int) -> dict[str, Any] | None:
    for node in walk(tree):
        if any(child.get("id") == con_id for child in node.get("nodes", [])):
            return node
    return None


def autotile_command(event: dict[str, Any], tree: dict[str, Any] | None) -> str | None:
    """The split command for a window event, or None when the layout should be left alone."""
    if event.get("change") not in ("focus", "new", "move", "floating"):
        return None
    con = event.get("container") or {}
    if con.get("type") != "con" or con.get("fullscreen_mode") or con.get("floating") in ("auto_on", "user_on"):
        return None
    if tree is None:
        return None
    parent = parent_of(tree, int(con.get("id", -1)))
    if parent is None or parent.get("layout") in ("tabbed", "stacked"):
        return None
    want = split_for(con.get("rect") or {})
    return None if parent.get("layout") == want else want


def autotile() -> int:
    proc = subprocess.Popen(["swaymsg", "-m", "-r", "-t", "subscribe", '["window"]'],
                            stdout=subprocess.PIPE, text=True)
    assert proc.stdout is not None
    for line in proc.stdout:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("change") not in ("focus", "new", "move", "floating"):
            continue
        r = _run(["swaymsg", "-r", "-t", "get_tree"])
        try:
            tree = json.loads(r.stdout)
        except json.JSONDecodeError:
            continue
        cmd = autotile_command(event, tree)
        if cmd:
            _run(["swaymsg", cmd])
    return proc.wait()


# ------------------------------------------------------------------- power --

@dataclass
class PowerState:
    percent: int | None  # None: no battery
    charging: bool
    on_ac: bool
    minutes_left: int | None


def read_power(root: Path = Path("/sys/class/power_supply")) -> PowerState:
    batteries, on_ac, charging = [], False, False
    energy_now = energy_full = power_now = 0.0
    for supply in sorted(root.glob("*")) if root.exists() else []:
        kind = _read(supply / "type")
        if kind == "Mains" and _read(supply / "online") == "1":
            on_ac = True
        if kind == "Battery" and _read(supply / "scope") != "Device":
            cap = _read(supply / "capacity")
            if cap.isdigit():
                batteries.append(int(cap))
            charging = charging or _read(supply / "status") in ("Charging", "Full")
            for now_name, full_name, rate_name in (("energy_now", "energy_full", "power_now"),
                                                   ("charge_now", "charge_full", "current_now")):
                if (supply / now_name).exists():
                    energy_now += _num(supply / now_name)
                    energy_full += _num(supply / full_name)
                    power_now += _num(supply / rate_name)
                    break
    if not batteries:
        return PowerState(None, False, on_ac, None)
    percent = round(energy_now / energy_full * 100) if energy_full else round(sum(batteries) / len(batteries))
    minutes = int(energy_now / power_now * 60) if power_now > 0 and not charging else None
    return PowerState(percent, charging or on_ac, on_ac, minutes)


def _read(path: Path) -> str:
    try:
        return path.read_text().strip()
    except OSError:
        return ""


def _num(path: Path) -> float:
    try:
        return float(_read(path))
    except ValueError:
        return 0.0


def battery_alert(state: PowerState, warning: int, critical: int, warned: set[str]) -> str | None:
    """Which alert to show now ('critical' / 'warning' / None); `warned` remembers what was shown."""
    if state.percent is None or state.charging:
        warned.clear()
        return None
    if critical and state.percent <= critical and "critical" not in warned:
        warned.update({"critical", "warning"})
        return "critical"
    if warning and state.percent <= warning and "warning" not in warned:
        warned.add("warning")
        return "warning"
    return None


def power() -> int:
    warned: set[str] = set()
    last: PowerState | None = None
    while True:
        state = read_power()
        cfg = config.load()
        if last is not None and state.percent is not None and state.on_ac != last.on_ac:
            flyout("power", f"charging  {state.percent}%" if state.on_ac else f"on battery  {state.percent}%")
        alert = battery_alert(state, int(config.get(cfg, "power.battery_warning") or 0),
                              int(config.get(cfg, "power.battery_critical") or 0), warned)
        if alert:
            left = f" (about {state.minutes_left // 60} h {state.minutes_left % 60} min left)" \
                if state.minutes_left else ""
            if alert == "critical":
                notify(f"Battery critically low: {state.percent}%",
                       f"Plug in the charger now; the computer will soon switch off.{left}", urgency_critical=True)
            else:
                notify(f"Battery low: {state.percent}%", f"Plug in the charger soon.{left}")
        last = state
        if not sleep_while_alive(10 if state.percent is not None else 120):
            return 0


# ------------------------------------------------------------- night light --

def nightlight_args(mode: str, temperature: int, location: str) -> list[str]:
    """wlsunset arguments. 'on' keeps the evening colour all day (day and night 1 K apart)."""
    lat, lon = dynwall._location(location, dynwall.now())
    high = temperature + 1 if mode == "on" else 6500
    return ["wlsunset", "-l", f"{lat:.2f}", "-L", f"{lon:.2f}", "-t", str(temperature), "-T", str(high)]


def nightlight(mode: str) -> int:
    if mode not in ("auto", "on") or not shutil.which("wlsunset"):
        return 0
    cfg = config.load()
    args = nightlight_args(mode, int(config.get(cfg, "display.night_temperature")),
                           str(config.get(cfg, "wallpaper.location") or ""))
    os.execvp(args[0], args)
    return 0  # not reached


# ------------------------------------------------------------------ updates --

def updates_file() -> Path:
    return paths.cache_dir() / "updates.json"


def count_updates() -> dict[str, int]:
    counts = {"dnf": 0, "flatpak": 0}
    if shutil.which("dnf"):
        r = _run(["dnf", "check-upgrade", "--quiet", "--refresh"])
        if r.returncode == 100:
            counts["dnf"] = sum(1 for line in r.stdout.splitlines()
                                if line.strip() and not line.startswith((" ", "Obsoleting", "Last metadata")))
    if shutil.which("flatpak"):
        r = _run(["flatpak", "remote-ls", "--updates", "--columns=application"])
        if r.returncode == 0:
            counts["flatpak"] = sum(1 for line in r.stdout.splitlines() if line.strip())
    return counts


def write_updates(counts: dict[str, int]) -> None:
    f = updates_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({**counts, "checked": int(time.time())}))


def updates() -> int:
    if not sleep_while_alive(300):  # let the session settle and the network come up
        return 0
    while True:
        try:
            write_updates(count_updates())
            refresh_bar()
        except OSError:
            pass
        if not sleep_while_alive(6 * 3600):
            return 0


def update_system() -> int:
    """Install every update (dnf, then Flatpak), in the terminal it runs in."""
    rc = 0
    print("\033[1m$ sudo dnf upgrade --refresh\033[0m")
    rc |= subprocess.call(["sudo", "dnf", "upgrade", "--refresh"])
    if shutil.which("flatpak"):
        print("\n\033[1m$ flatpak update\033[0m")
        rc |= subprocess.call(["flatpak", "update"])
    write_updates({"dnf": 0, "flatpak": 0})
    refresh_bar()
    print("\nDone." if rc == 0 else "\nSomething went wrong; see above.")
    return rc
