"""Screenshots, screen recording and the colour picker.

    surfctl screenshot full|area|window|output [--edit] [--delay N]
    surfctl record area|output|stop|status
    surfctl colorpick

Screenshots go to capture.screenshots (and the clipboard); recordings to
capture.recordings. A notification offers to open (click) or annotate the result.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path
from typing import Any

from . import config, paths
from .desktop import LIBEXEC, copy_text, flyout, focused, refresh_bar, sway_json
from .session import _run, notify


def _folder(key: str) -> Path:
    raw = config.get(config.load(), key) or ""
    folder = Path(os.path.expanduser(raw)) if raw else Path.home()
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _stamp() -> str:
    return f"{_dt.datetime.now():%Y-%m-%d_%H-%M-%S}"


def _unique(folder: Path, stem: str, suffix: str) -> Path:
    """folder/stem.suffix, or stem-2, stem-3… when two captures land in the same second."""
    target, n = folder / f"{stem}{suffix}", 2
    while target.exists():
        target, n = folder / f"{stem}-{n}{suffix}", n + 1
    return target


def _announce(path: Path, title: str, *, image: bool) -> None:
    """Notification with actions: click opens the file; 'annotate' opens swappy (screenshots)."""
    helper = LIBEXEC / "surfd-notify-file"
    if helper.exists():
        subprocess.Popen([str(helper), title, str(path), "image" if image else "video"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        notify(title, str(path))


def geometry(mode: str) -> tuple[list[str], str] | None:
    """grim/wf-recorder arguments for the region: (['-g', 'x,y wxh'] or ['-o', name], label). None: cancelled."""
    if mode == "area":
        sel = _run(["slurp", "-d"])
        if sel.returncode != 0 or not sel.stdout.strip():
            return None
        return ["-g", sel.stdout.strip()], "area"
    if mode == "window":
        tree = sway_json("get_tree")
        win = focused(tree) if tree else None
        if win and win.get("type") in ("con", "floating_con"):
            r = win["rect"]
            # include the title bar when there is one
            deco = win.get("deco_rect") or {}
            y, h = r["y"] - int(deco.get("height", 0)), r["height"] + int(deco.get("height", 0))
            return ["-g", f"{r['x']},{y} {r['width']}x{h}"], "window"
        mode = "output"
    if mode == "output":
        outs = sway_json("get_outputs") or []
        name = next((o["name"] for o in outs if o.get("focused")), None)
        if name:
            return ["-o", name], "display"
    return [], "screen"


def screenshot(mode: str = "full", *, edit: bool = False, delay: int = 0) -> Path | None:
    if not shutil.which("grim"):
        notify("Screenshot", "grim is not installed", urgency_critical=True)
        return None
    region = geometry("full" if mode == "full" else mode)
    if region is None:
        return None
    for left in range(delay, 0, -1):
        flyout("shot", f"in {left}…")
        time.sleep(1)
    target = _unique(_folder("capture.screenshots"), f"Screenshot_{_stamp()}", ".png")
    if delay:
        time.sleep(0.4)  # let the countdown flyout fade
    if _run(["grim", *region[0], str(target)]).returncode != 0:
        notify("Screenshot failed", "grim could not capture the screen", urgency_critical=True)
        return None
    if shutil.which("wl-copy"):
        with target.open("rb") as fh:
            subprocess.run(["wl-copy", "--type", "image/png"], stdin=fh, check=False)
    if edit and shutil.which("swappy"):
        subprocess.Popen(["swappy", "-f", str(target), "-o", str(target)], start_new_session=True)
    else:
        _announce(target, f"Screenshot of the {region[1]} saved and copied", image=True)
    return target


def open_screenshots() -> None:
    subprocess.Popen(["xdg-open", str(_folder("capture.screenshots"))], start_new_session=True)


# --------------------------------------------------------------- recording --

def _record_state() -> Path:
    return Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "surfd-recording.json"


def recording() -> dict[str, Any] | None:
    """The recording in progress, if any."""
    try:
        state = json.loads(_record_state().read_text())
        os.kill(int(state["pid"]), 0)
        return state
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        _record_state().unlink(missing_ok=True)
        return None


def _monitor_source() -> str:
    """The pulse name of what the computer is playing (the default output's monitor)."""
    out = _run(["wpctl", "inspect", "@DEFAULT_AUDIO_SINK@"]).stdout if shutil.which("wpctl") else ""
    for line in out.splitlines():
        if "node.name" in line and "=" in line:
            return line.split("=", 1)[1].strip().strip('"') + ".monitor"
    return ""


def record(mode: str) -> int:
    """Start recording, or stop the one in progress (any mode stops it)."""
    current = recording()
    if current or mode == "stop":
        if not current:
            flyout("rec", "nothing is being recorded")
            return 0
        os.kill(int(current["pid"]), signal.SIGINT)
        for _ in range(50):
            if recording() is None:
                break
            time.sleep(0.1)
        _record_state().unlink(missing_ok=True)
        refresh_bar()
        _announce(Path(current["file"]), "Recording saved", image=False)
        return 0
    if not shutil.which("wf-recorder"):
        notify("Screen recording", "wf-recorder is not installed", urgency_critical=True)
        return 1
    region = geometry(mode)
    if region is None:
        return 0
    target = _unique(_folder("capture.recordings"), f"Recording_{_stamp()}", ".webm")
    # Fedora's FFmpeg has no H.264 encoder; VP8 in realtime mode is light enough for any CPU.
    cmd = ["wf-recorder", *region[0], "-f", str(target), "-c", "libvpx",
           "-p", "deadline=realtime", "-p", "cpu-used=8", "-p", "b=6M", "-r", "30"]
    if config.get(config.load(), "capture.record_audio"):
        source = _monitor_source()
        cmd.append(f"--audio={source}" if source else "--audio")
    log = paths.state_dir() / "recording.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as fh:
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=fh, stderr=fh, start_new_session=True)
    time.sleep(0.5)
    if proc.poll() is not None:
        notify("Recording failed", f"wf-recorder stopped; see {log}", urgency_critical=True)
        return 1
    _record_state().write_text(json.dumps({"pid": proc.pid, "file": str(target), "started": time.time(),
                                           "what": region[1]}))
    flyout("rec", f"recording the {region[1]}: press the same keys again to stop")
    refresh_bar()
    return 0


# ------------------------------------------------------------ colour picker --

def parse_ppm_pixel(data: bytes) -> str:
    """'#rrggbb' of the first pixel of a binary PPM (P6) image."""
    if not data.startswith(b"P6"):
        raise ValueError("not a PPM image")
    fields: list[bytes] = []
    i = 2
    while len(fields) < 3:
        while data[i:i + 1].isspace():
            i += 1
        if data[i:i + 1] == b"#":
            i = data.index(b"\n", i) + 1
            continue
        j = i
        while not data[j:j + 1].isspace():
            j += 1
        fields.append(data[i:j])
        i = j
    i += 1  # the single whitespace byte before the pixels
    r, g, b = data[i], data[i + 1], data[i + 2]
    return f"#{r:02x}{g:02x}{b:02x}"


def colorpick() -> str | None:
    if not (shutil.which("grim") and shutil.which("slurp")):
        notify("Colour picker", "grim and slurp are needed", urgency_critical=True)
        return None
    point = _run(["slurp", "-p", "-b", "00000000"])
    if point.returncode != 0 or not point.stdout.strip():
        return None
    shot = subprocess.run(["grim", "-g", point.stdout.strip(), "-t", "ppm", "-"], capture_output=True, check=False)
    try:
        hexcol = parse_ppm_pixel(shot.stdout)
    except (ValueError, IndexError):
        notify("Colour picker", "could not read the colour", urgency_critical=True)
        return None
    copy_text(hexcol)
    rgb = ", ".join(str(int(hexcol[k:k + 2], 16)) for k in (1, 3, 5))
    flyout("colour", f"<span foreground='{hexcol}'>████</span>  <b>{hexcol}</b>   rgb({rgb})   copied", markup=True)
    return hexcol
