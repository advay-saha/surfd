"""Walk through the whole installer wizard in demo mode, like a user would.

    SURF_INSTALLER_DRY_RUN=1 SURF_INSTALLER_FAKE_DISKS=disks.json \
        python3 src/installer/tests/gui_walkthrough.py OUTDIR

Fills in every screen through the real widgets, confirms the erase dialog,
waits for the (dry-run) engine and screenshots each step with grim.
Prints PASS/FAIL lines and exits non-zero on failure.
"""

from __future__ import annotations

import subprocess
import sys
import time
import traceback

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

from surf_installer.app import App, Installer  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
failures: list[str] = []


def check(cond: bool, what: str) -> None:
    print(("PASS " if cond else "FAIL ") + what, flush=True)
    if not cond:
        failures.append(what)


def walk(widget: Gtk.Widget):  # type: ignore[no-untyped-def]
    stack = [widget]
    while stack:
        w = stack.pop()
        yield w
        c = w.get_first_child()
        while c is not None:
            stack.append(c)
            c = c.get_next_sibling()


def find(root: Gtk.Widget, pred) -> Gtk.Widget:  # type: ignore[no-untyped-def]
    for w in walk(root):
        if pred(w):
            return w
    raise LookupError("widget not found")


def button(root: Gtk.Widget, label: str) -> Gtk.Button:
    return find(root, lambda w: isinstance(w, Gtk.Button) and w.get_label() == label and w.get_mapped())


def entry(root: Gtk.Widget, title: str) -> Adw.EntryRow:
    return find(root, lambda w: isinstance(w, Adw.EntryRow) and w.get_title() == title)


def shot(name: str) -> None:
    # let GTK draw the latest state before capturing
    ctx = GLib.MainContext.default()
    for _ in range(40):
        while ctx.iteration(False):
            pass
        time.sleep(0.01)
    subprocess.run(["grim", f"{OUT}/installer-{name}.png"], check=False)


def main() -> int:
    app = App()
    steps: list = []

    def visible(win: Installer) -> Gtk.Widget:
        return win.nav.get_visible_page()

    def run_steps(_app: App) -> None:
        win = next(w for w in _app.get_windows() if isinstance(w, Installer))

        def s_welcome() -> None:
            shot("1-welcome")
            button(visible(win), "Install surfd").emit("clicked")

        def s_region() -> None:
            check(visible(win).get_tag() == "region", "welcome -> language and keyboard")
            shot("2-region")
            button(visible(win), "Next").emit("clicked")

        def s_disk() -> None:
            check(visible(win).get_tag() == "disk", "region -> disk")
            shot("3-disk")
            page = visible(win)
            sw = find(page, lambda w: isinstance(w, Adw.SwitchRow))
            sw.set_active(True)
            find(page, lambda w: isinstance(w, Adw.PasswordEntryRow) and w.get_title() == "Passphrase").set_text("short")
            find(page, lambda w: isinstance(w, Adw.PasswordEntryRow) and w.get_title() == "Repeat the passphrase").set_text("short")
            button(page, "Next").emit("clicked")
            check(visible(win).get_tag() == "disk", "short passphrase is refused")
            for title in ("Passphrase", "Repeat the passphrase"):
                find(page, lambda w, t=title: isinstance(w, Adw.PasswordEntryRow) and w.get_title() == t).set_text("ocean waves at dawn")
            shot("3b-disk-encrypted")
            button(page, "Next").emit("clicked")

        def s_account() -> None:
            check(visible(win).get_tag() == "account", "disk -> account")
            page = visible(win)
            entry(page, "Your name").set_text("Advay Saha")
            check(entry(page, "Username").get_text() == "advay", "username suggested from the name")
            find(page, lambda w: isinstance(w, Adw.PasswordEntryRow) and w.get_title() == "Password").set_text("pw-one")
            find(page, lambda w: isinstance(w, Adw.PasswordEntryRow) and w.get_title() == "Repeat the password").set_text("pw-two")
            button(page, "Next").emit("clicked")
            check(visible(win).get_tag() == "account", "mismatched passwords are refused")
            find(page, lambda w: isinstance(w, Adw.PasswordEntryRow) and w.get_title() == "Repeat the password").set_text("pw-one")
            shot("4-account")
            button(page, "Next").emit("clicked")

        def s_review() -> None:
            check(visible(win).get_tag() == "review", "account -> review")
            check(win.plan.encrypt and win.plan.username == "advay" and win.plan.disk == "/dev/nvme0n1",
                  "plan collected from the screens")
            shot("5-review")
            button(visible(win), "Erase disk and install").emit("clicked")

        def s_confirm() -> None:
            dlg = win.get_visible_dialog() if hasattr(win, "get_visible_dialog") else None
            check(isinstance(dlg, Adw.AlertDialog), "erase confirmation dialog shown")
            shot("6-confirm")
            dlg.emit("response", "install")  # type: ignore[union-attr]

        def s_progress() -> None:
            check(visible(win).get_tag() == "progress", "installation started")
            shot("7-progress")

        def s_wait() -> bool:
            tag = visible(win).get_tag()
            if tag in ("done", "error"):
                check(tag == "done", "installation finished successfully (dry run)")
                shot("8-done")
                _app.quit()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        steps.extend([s_welcome, s_region, s_disk, s_account, s_review, s_confirm, s_progress])

        def tick() -> bool:
            if not steps:
                GLib.timeout_add(500, s_wait)
                return GLib.SOURCE_REMOVE
            try:
                steps.pop(0)()
            except Exception:
                traceback.print_exc()
                failures.append("exception")
                _app.quit()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        GLib.timeout_add(1200, tick)
        GLib.timeout_add(60000, lambda: (failures.append("timeout"), _app.quit()))

    app.connect("activate", lambda a: GLib.idle_add(run_steps, a))
    app.run(sys.argv[:1])
    print(f"{'OK' if not failures else 'FAILED'}: {len(failures)} failure(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
