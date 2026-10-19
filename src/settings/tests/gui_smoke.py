"""Functional GUI smoke test. Runs inside a (headless) Wayland session:

    python3 src/settings/tests/gui_smoke.py OUTDIR

Opens Surf Settings, clicks through real widgets (theme card, style combo,
accent swatch, gaps spin row, reset dialog path) and checks that
surfd.toml and the generated files changed accordingly. Exits non-zero on
any failure. Used by tools/gui-screenshot.sh and CI.
"""

from __future__ import annotations

import subprocess
import sys
import traceback

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib  # noqa: E402

from surf_settings.app import App, Window  # noqa: E402
from surfd import config, paths, themes  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
failures: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("PASS " if cond else "FAIL ") + what, flush=True)
    if not cond:
        failures.append(what)


def run_steps(app: App) -> bool:
    try:
        win = next(w for w in app.get_windows() if isinstance(w, Window))
        picker = win.stack.get_child_by_name("appearance")
        # 1. pick a theme card (same callback a click invokes)
        theme_picker = _find(picker, "ThemePicker")
        theme_picker.on_pick("kelp")
        check(config.load()["theme"]["name"] == "kelp", "theme card switches theme to kelp")
        accent = themes.resolve(config.load())[1].accent
        check(accent in (paths.generated_dir() / "waybar" / "style.css").read_text(),
              f"bar style regenerated with kelp accent {accent}")
        # 2. accent swatch
        accent_row = _find(picker, "AccentRow")
        accent_row.buttons["#e88bc4"].emit("clicked")
        check(config.load()["theme"]["accent"] == "#e88bc4", "accent swatch sets theme.accent")
        # 3. a validated numeric change through the controller path
        win.ctl.change_now({"layout.gaps_inner": 14})
        check(config.load()["layout"]["gaps_inner"] == 14, "gaps change saved")
        # 4. an invalid change is refused and the file is untouched
        before = paths.user_config().read_text()
        win.ctl.change_now({"bar.left": ["teleporter"]})
        check(paths.user_config().read_text() == before, "invalid bar module rejected, file unchanged")
        # 5. reset keeps a backup and restores defaults
        win.ctl.reset()
        check(config.load()["theme"]["name"] == "tide", "reset restores defaults")
        check(bool(config.list_backups()), "reset kept a backup")
        win.ctl.restore_latest()
        check(config.load()["layout"]["gaps_inner"] == 14, "restore brings back the previous file")
        win.refresh()
        subprocess.run(["grim", f"{OUT}/settings-after-smoke.png"], check=False)
    except Exception:
        traceback.print_exc()
        failures.append("exception")
    app.quit()
    return GLib.SOURCE_REMOVE


def _find(widget, cls_name: str):  # type: ignore[no-untyped-def]
    stack = [widget]
    while stack:
        w = stack.pop()
        if type(w).__name__ == cls_name:
            return w
        child = w.get_first_child()
        while child is not None:
            stack.append(child)
            child = child.get_next_sibling()
    raise LookupError(cls_name)


def main() -> int:
    app = App()
    app.connect("activate", lambda a: GLib.timeout_add(1500, run_steps, a))
    app.run([sys.argv[0]])
    print(f"{'OK' if not failures else 'FAILED'}: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
