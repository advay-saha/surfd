"""Surf Installer — install surfd on a whole disk in five screens.

Welcome → Language & keyboard → Disk → Account → Review → (installing) → Done

For dual boot, existing partitions, RAID or LVM the Welcome screen offers
Fedora's full installer (Anaconda) instead.

SURF_INSTALLER_DRY_RUN=1 runs the whole flow without touching any disk
(used for tests and screenshots); SURF_INSTALLER_FAKE_DISKS=file.json
replaces the disk list with `lsblk -J` output.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import disks  # noqa: E402
from .plan import Plan, suggest_username  # noqa: E402

APP_ID = "org.surfd.Installer"
ENGINE = os.environ.get("SURF_INSTALLER_ENGINE", "/usr/libexec/surfd/surf-installer-engine")
DRY_RUN = os.environ.get("SURF_INSTALLER_DRY_RUN") == "1"

LOCALES = [
    ("en_US.UTF-8", "English (United States)"), ("en_GB.UTF-8", "English (United Kingdom)"),
    ("en_IN.UTF-8", "English (India)"), ("en_AU.UTF-8", "English (Australia)"), ("hi_IN.UTF-8", "हिन्दी (भारत)"),
    ("bn_IN.UTF-8", "বাংলা (ভারত)"), ("de_DE.UTF-8", "Deutsch"), ("fr_FR.UTF-8", "Français"),
    ("es_ES.UTF-8", "Español (España)"), ("es_MX.UTF-8", "Español (México)"), ("it_IT.UTF-8", "Italiano"),
    ("pt_BR.UTF-8", "Português (Brasil)"), ("pt_PT.UTF-8", "Português (Portugal)"), ("nl_NL.UTF-8", "Nederlands"),
    ("sv_SE.UTF-8", "Svenska"), ("pl_PL.UTF-8", "Polski"), ("cs_CZ.UTF-8", "Čeština"), ("tr_TR.UTF-8", "Türkçe"),
    ("ru_RU.UTF-8", "Русский"), ("uk_UA.UTF-8", "Українська"), ("ja_JP.UTF-8", "日本語"), ("ko_KR.UTF-8", "한국어"),
    ("zh_CN.UTF-8", "中文 (简体)"), ("zh_TW.UTF-8", "中文 (繁體)"),
]
FALLBACK_LAYOUTS = ["us", "gb", "in", "de", "fr", "es", "it", "pt", "br", "latam", "ca", "nl", "be", "ch", "se",
                    "no", "dk", "fi", "pl", "cz", "tr", "ru", "ua", "jp", "kr", "cn"]

CSS = """
.step-title { font-size: 20pt; font-weight: 300; }
.big-progress progress, .big-progress trough { min-height: 10px; border-radius: 99px; }
.problem { color: @error_color; }
"""


def _lines(cmd: list[str]) -> list[str]:
    if shutil.which(cmd[0]) is None:
        return []
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return [line.strip() for line in r.stdout.splitlines() if line.strip()] if r.returncode == 0 else []


def keyboard_layouts() -> list[str]:
    return _lines(["localectl", "list-x11-keymap-layouts"]) or FALLBACK_LAYOUTS


def timezones() -> list[str]:
    zones = _lines(["timedatectl", "list-timezones"])
    if zones:
        return zones
    tab = Path("/usr/share/zoneinfo/tzdata.zi")
    if Path("/usr/share/zoneinfo/zone1970.tab").is_file():
        tab = Path("/usr/share/zoneinfo/zone1970.tab")
        return sorted({line.split("\t")[2] for line in tab.read_text().splitlines()
                       if line and not line.startswith("#")} | {"UTC"})
    return ["UTC"]


def current_timezone() -> str:
    try:
        target = os.readlink("/etc/localtime")
        return target.split("zoneinfo/", 1)[1]
    except (OSError, IndexError):
        return "UTC"


def current_keyboard() -> tuple[str, str]:
    try:
        from surfd import config, system
        kb = system.system_keyboard()
        if kb.get("layout"):
            return kb["layout"], kb.get("variant", "")
        cfg = config.load()
        return cfg["input"]["keyboard_layout"], cfg["input"]["keyboard_variant"]
    except Exception:
        return "us", ""


def string_combo(title: str, items: list[str], labels: list[str] | None = None, searchable: bool = False) -> Adw.ComboRow:
    model = Gtk.StringList.new(labels or items)
    row = Adw.ComboRow(title=title, model=model, use_subtitle=False)
    if searchable:
        row.set_enable_search(True)
        row.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
    return row


class Installer(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="Install surfd", default_width=840, default_height=660)
        self.set_size_request(360, 520)
        self.plan = Plan()
        self.nav = Adw.NavigationView()
        self.toasts = Adw.ToastOverlay(child=self.nav)
        self.set_content(self.toasts)
        self.engine_proc: Gio.Subprocess | None = None
        self.log_path = Path(tempfile.gettempdir()) / "surf-installer.log"
        self.nav.add(self.page_welcome())

    # ------------------------------------------------------------ helpers --
    def page(self, title: str, tag: str, body: Gtk.Widget, *, next_label: str = "Next",
             on_next=None, destructive: bool = False, show_back: bool = True) -> tuple[Adw.NavigationPage, Gtk.Button]:  # type: ignore[no-untyped-def]
        header = Adw.HeaderBar(show_back_button=show_back)
        scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        scroller.set_child(Adw.Clamp(maximum_size=620, child=body, margin_top=12, margin_bottom=24,
                                     margin_start=18, margin_end=18))
        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.set_content(scroller)
        next_btn = Gtk.Button(label=next_label)
        next_btn.add_css_class("pill")
        next_btn.add_css_class("destructive-action" if destructive else "suggested-action")
        if on_next is not None:
            next_btn.connect("clicked", lambda _b: on_next())
            bar = Gtk.Box(halign=Gtk.Align.END, margin_top=10, margin_bottom=14, margin_start=18, margin_end=18)
            bar.append(next_btn)
            view.add_bottom_bar(bar)
        return Adw.NavigationPage(title=title, tag=tag, child=view), next_btn

    @staticmethod
    def vbox(*children: Gtk.Widget, spacing: int = 18) -> Gtk.Box:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=spacing)
        for c in children:
            box.append(c)
        return box

    def toast(self, msg: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=GLib.markup_escape_text(msg), timeout=5))

    # -------------------------------------------------------------- pages --
    def page_welcome(self) -> Adw.NavigationPage:
        status = Adw.StatusPage(title="Install surfd", icon_name=APP_ID,
                                description="This puts surfd on one disk of this computer. It takes about "
                                            "10 minutes and erases everything on the disk you choose.")
        start = Gtk.Button(label="Install surfd", halign=Gtk.Align.CENTER)
        start.add_css_class("pill")
        start.add_css_class("suggested-action")
        start.connect("clicked", lambda _b: self.nav.push(self.page_region()))
        advanced = Gtk.Button(label="Dual boot or custom partitions…", halign=Gtk.Align.CENTER)
        advanced.add_css_class("flat")
        advanced.set_tooltip_text("Opens Fedora's full installer (Anaconda)")
        advanced.connect("clicked", lambda _b: self.open_advanced())
        note = Gtk.Label(label="surfd is based on Fedora Linux but is not an official Fedora project.",
                         wrap=True, justify=Gtk.Justification.CENTER)
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        status.set_child(self.vbox(start, advanced, note, spacing=12))
        if DRY_RUN:
            status.set_description(status.get_description() + "\n\nDEMO MODE — no disk will be changed.")
        page, _ = self.page("Welcome", "welcome", status, show_back=False)
        return page

    def page_region(self) -> Adw.NavigationPage:
        group = Adw.PreferencesGroup(title="Language and region",
                                     description="Your choices are used for the installed system.")
        lang_codes = [c for c, _ in LOCALES]
        lang = string_combo("Language", lang_codes, [n for _, n in LOCALES])
        cur = os.environ.get("LANG", "en_US.UTF-8")
        lang.set_selected(lang_codes.index(cur) if cur in lang_codes else 0)

        layouts = keyboard_layouts()
        cur_layout, cur_variant = current_keyboard()
        kb = string_combo("Keyboard layout", layouts, searchable=True)
        first = cur_layout.split(",")[0]
        kb.set_selected(layouts.index(first) if first in layouts else 0)
        variant = Adw.EntryRow(title="Keyboard variant (optional, e.g. intl)", text=cur_variant)

        zones = timezones()
        tz = string_combo("Time zone", zones, searchable=True)
        cur_tz = current_timezone()
        tz.set_selected(zones.index(cur_tz) if cur_tz in zones else (zones.index("UTC") if "UTC" in zones else 0))

        def apply_keyboard(*_a: object) -> None:
            # Use the new layout right away in the live session, so passwords are typed correctly.
            if os.environ.get("SWAYSOCK") and shutil.which("swaymsg"):
                subprocess.run(["swaymsg", "input", "type:keyboard", "xkb_layout", layouts[kb.get_selected()]],
                               capture_output=True, check=False)

        kb.connect("notify::selected", apply_keyboard)
        for row in (lang, kb, variant, tz):
            group.add(row)

        def next_() -> None:
            self.plan.locale = lang_codes[lang.get_selected()]
            self.plan.keyboard_layout = layouts[kb.get_selected()]
            self.plan.keyboard_variant = variant.get_text().strip()
            self.plan.timezone = zones[tz.get_selected()]
            self.nav.push(self.page_disk())

        page, _ = self.page("Language and keyboard", "region", group, on_next=next_)
        return page

    def page_disk(self) -> Adw.NavigationPage:
        try:
            found = disks.list_disks()
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as e:
            found = []
            self.toast(f"Could not list disks: {e}")
        if not found:
            status = Adw.StatusPage(title="No disk to install on", icon_name="drive-harddisk-symbolic",
                                    description="surfd needs an internal disk of at least 20 GB that is not the "
                                                "USB stick you started from.")
            page, _ = self.page("Disk", "disk", status)
            return page

        group = Adw.PreferencesGroup(title="Where should surfd go?",
                                     description="Everything on the chosen disk will be erased.")
        first_radio: Gtk.CheckButton | None = None
        chosen: dict[str, disks.Disk] = {}
        for d in found:
            radio = Gtk.CheckButton(valign=Gtk.Align.CENTER)
            if first_radio is None:
                first_radio = radio
                chosen["disk"] = d
            else:
                radio.set_group(first_radio)
            row = Adw.ActionRow(title=GLib.markup_escape_text(d.title), subtitle=GLib.markup_escape_text(d.subtitle),
                                activatable_widget=radio)
            row.add_prefix(radio)
            row.add_suffix(Gtk.Image(icon_name="media-removable-symbolic" if d.removable else "drive-harddisk-symbolic"))
            if d.size < 20 * 1024**3:
                row.set_sensitive(False)
                row.set_subtitle(GLib.markup_escape_text(d.subtitle + " · too small"))
            radio.connect("toggled", lambda r, disk=d: r.get_active() and chosen.__setitem__("disk", disk))
            group.add(row)
        if first_radio is not None:
            first_radio.set_active(True)

        enc_group = Adw.PreferencesGroup(title="Encryption",
                                         description="Protects your files if the computer is lost or stolen. "
                                                     "You will type the passphrase at every start.")
        enc = Adw.SwitchRow(title="Encrypt the disk")
        p1 = Adw.PasswordEntryRow(title="Passphrase")
        p2 = Adw.PasswordEntryRow(title="Repeat the passphrase")
        for r in (p1, p2):
            r.set_visible(False)
        enc.connect("notify::active", lambda s, _p: [r.set_visible(s.get_active()) for r in (p1, p2)])
        for r in (enc, p1, p2):
            enc_group.add(r)
        problem = Gtk.Label(xalign=0, wrap=True)
        problem.add_css_class("problem")
        for r in (p1, p2):
            r.connect("changed", lambda _r: problem.set_text(""))
        enc.connect("notify::active", lambda *_a: problem.set_text(""))

        def next_() -> None:
            d = chosen.get("disk")
            if d is None:
                return
            self.plan.disk, self.plan.disk_size = d.path, d.size
            self.plan.extras["disk_label"] = f"{d.title} ({d.size_label})"
            self.plan.encrypt = enc.get_active()
            self.plan.passphrase = p1.get_text() if self.plan.encrypt else ""
            issues = self.plan.problems()
            msg = issues.get("disk") or issues.get("passphrase")
            if self.plan.encrypt and p1.get_text() != p2.get_text():
                msg = "The passphrases do not match."
            problem.set_text(msg or "")
            if not msg:
                self.nav.push(self.page_account())

        page, _ = self.page("Disk", "disk", self.vbox(group, enc_group, problem), on_next=next_)
        return page

    def page_account(self) -> Adw.NavigationPage:
        group = Adw.PreferencesGroup(title="Your account",
                                     description="You will be the administrator of this computer.")
        name = Adw.EntryRow(title="Your name")
        user = Adw.EntryRow(title="Username")
        pw1 = Adw.PasswordEntryRow(title="Password")
        pw2 = Adw.PasswordEntryRow(title="Repeat the password")
        host = Adw.EntryRow(title="Computer name", text=self.plan.hostname)
        edited = {"user": False}

        def on_name(row: Adw.EntryRow) -> None:
            if not edited["user"]:
                user.set_text(suggest_username(row.get_text()))

        name.connect("changed", on_name)
        user.connect("changed", lambda r: edited.__setitem__("user", r.has_focus() or edited["user"]))
        problem = Gtk.Label(xalign=0, wrap=True)
        problem.add_css_class("problem")
        for r in (name, user, pw1, pw2, host):
            group.add(r)
            r.connect("changed", lambda _r: problem.set_text(""))

        def next_() -> None:
            self.plan.fullname = name.get_text().strip()
            self.plan.username = user.get_text().strip()
            self.plan.password = pw1.get_text()
            self.plan.hostname = host.get_text().strip()
            issues = self.plan.problems()
            for key in ("fullname", "username", "password", "hostname"):
                if key in issues:
                    problem.set_text(issues[key])
                    return
            if pw1.get_text() != pw2.get_text():
                problem.set_text("The passwords do not match.")
                return
            problem.set_text("")
            self.nav.push(self.page_review())

        page, _ = self.page("Account", "account", self.vbox(group, problem), on_next=next_)
        return page

    def page_review(self) -> Adw.NavigationPage:
        p = self.plan
        group = Adw.PreferencesGroup(title="Ready to install")
        rows = [
            ("Disk (will be erased)", p.extras.get("disk_label", p.disk)),
            ("Encryption", "On" if p.encrypt else "Off"),
            ("Account", f"{p.fullname} ({p.username}), administrator"),
            ("Computer name", p.hostname),
            ("Language", dict(LOCALES).get(p.locale, p.locale)),
            ("Keyboard", p.keyboard_layout + (f" ({p.keyboard_variant})" if p.keyboard_variant else "")),
            ("Time zone", p.timezone),
        ]
        for title, value in rows:
            row = Adw.ActionRow(title=title, subtitle=GLib.markup_escape_text(value), subtitle_selectable=True)
            row.add_css_class("property")
            group.add(row)
        warn = Gtk.Label(wrap=True, xalign=0,
                         label=f"Installing erases everything on {p.extras.get('disk_label', p.disk)}. "
                               "Make sure you have a copy of anything important.")
        warn.add_css_class("dim-label")
        page, _ = self.page("Review", "review", self.vbox(group, warn), next_label="Erase disk and install",
                            on_next=self.confirm, destructive=True)
        return page

    def confirm(self) -> None:
        label = self.plan.extras.get("disk_label", self.plan.disk)
        dlg = Adw.AlertDialog(heading="Erase this disk?",
                              body=f"All data on {label} will be permanently deleted.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("install", "Erase and install")
        dlg.set_response_appearance("install", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancel")
        dlg.connect("response", lambda _d, r: r == "install" and self.start_install())
        dlg.present(self)

    # ----------------------------------------------------------- install --
    def page_progress(self) -> Adw.NavigationPage:
        self.bar = Gtk.ProgressBar(show_text=False)
        self.bar.add_css_class("big-progress")
        self.step_label = Gtk.Label(label="Starting…", xalign=0)
        self.step_label.add_css_class("title-3")
        hint = Gtk.Label(label="Please keep the computer plugged in. You can keep using it meanwhile.",
                         xalign=0, wrap=True)
        hint.add_css_class("dim-label")
        self.logview = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.CHAR,
                                    top_margin=8, bottom_margin=8, left_margin=8, right_margin=8)
        logscroll = Gtk.ScrolledWindow(child=self.logview, min_content_height=220)
        expander = Gtk.Expander(label="Details", child=logscroll)
        title = Gtk.Label(label="Installing surfd", xalign=0)
        title.add_css_class("step-title")
        page, _ = self.page("Installing", "progress", self.vbox(title, self.step_label, self.bar, hint, expander),
                            show_back=False)
        page.set_can_pop(False)
        return page

    def engine_command(self, plan_path: Path) -> list[str]:
        if DRY_RUN:
            target = Path(tempfile.mkdtemp(prefix="surf-installer-demo-"))
            return [sys.executable, "-m", "surf_installer", "--plan", str(plan_path), "--dry-run",
                    "--pace", os.environ.get("SURF_INSTALLER_PACE", "0.4"), "--log", str(self.log_path),
                    "--source", "/", "--target", str(target)]
        cmd = [ENGINE, "--plan", str(plan_path), "--log", str(self.log_path)]
        if shutil.which("sudo") and subprocess.run(["sudo", "-n", "true"], capture_output=True,
                                                    check=False).returncode == 0:
            return ["sudo", "-n", *cmd]  # live user: password-less sudo
        return ["pkexec", *cmd]

    def start_install(self) -> None:
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()) / "surf-installer"
        plan_path = runtime / "plan.json"
        self.plan.write(plan_path)
        self.nav.push(self.page_progress())
        if DRY_RUN:
            self.log_path.unlink(missing_ok=True)
        try:
            self.engine_proc = Gio.Subprocess.new(self.engine_command(plan_path),
                                                  Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        except GLib.Error as e:
            self.finish_error(f"Could not start the installer engine: {e.message}")
            return
        self.stream = Gio.DataInputStream.new(self.engine_proc.get_stdout_pipe())
        self.stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self.on_line)
        self.log_timer = GLib.timeout_add(1000, self.refresh_log)

    def on_line(self, stream: Gio.DataInputStream, res: Gio.AsyncResult) -> None:
        try:
            line, _ = stream.read_line_finish_utf8(res)
        except GLib.Error:
            line = None
        if line is None:
            self.engine_finished()
            return
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            ev = {"type": "text", "message": line}
        if ev.get("type") == "progress":
            self.bar.set_fraction(float(ev.get("fraction", 0)))
            self.step_label.set_text(str(ev.get("label", "")))
        elif ev.get("type") == "done":
            self.result = "done"
        elif ev.get("type") == "error":
            self.result = "error"
            self.error_message = str(ev.get("message", "unknown error"))
        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, self.on_line)

    def refresh_log(self) -> bool:
        try:
            text = self.log_path.read_text(encoding="utf-8", errors="replace")[-20000:]
        except OSError:
            return True
        buf = self.logview.get_buffer()
        if buf.get_char_count() != len(text):
            buf.set_text(text)
        return True

    def engine_finished(self) -> None:
        GLib.source_remove(self.log_timer)
        self.refresh_log()
        if getattr(self, "result", "") == "done":
            self.bar.set_fraction(1.0)
            self.nav.push(self.page_done())
        else:
            self.finish_error(getattr(self, "error_message", "The installer stopped unexpectedly."))

    def page_done(self) -> Adw.NavigationPage:
        status = Adw.StatusPage(title="surfd is installed", icon_name="emblem-ok-symbolic",
                                description="Remove the USB stick when the screen goes dark, then start "
                                            f"surfd and log in as {self.plan.username}.")
        restart = Gtk.Button(label="Restart now", halign=Gtk.Align.CENTER)
        restart.add_css_class("pill")
        restart.add_css_class("suggested-action")
        restart.connect("clicked", lambda _b: DRY_RUN or subprocess.Popen(["systemctl", "reboot"]))
        later = Gtk.Button(label="Keep using the live system", halign=Gtk.Align.CENTER)
        later.add_css_class("flat")
        later.connect("clicked", lambda _b: self.close())
        status.set_child(self.vbox(restart, later, spacing=8))
        page, _ = self.page("Done", "done", status, show_back=False)
        page.set_can_pop(False)
        return page

    def finish_error(self, message: str) -> None:
        status = Adw.StatusPage(title="The installation did not finish", icon_name="dialog-error-symbolic",
                                description=GLib.markup_escape_text(message))
        save = Gtk.Button(label="Save the log to your home folder", halign=Gtk.Align.CENTER)
        save.connect("clicked", lambda _b: self.save_log())
        advanced = Gtk.Button(label="Try Fedora's full installer", halign=Gtk.Align.CENTER)
        advanced.add_css_class("pill")
        advanced.connect("clicked", lambda _b: self.open_advanced())
        status.set_child(self.vbox(advanced, save, spacing=8))
        page, _ = self.page("Problem", "error", status, show_back=False)
        page.set_can_pop(False)
        self.nav.push(page)

    def save_log(self) -> None:
        dest = Path.home() / "surf-installer.log"
        try:
            shutil.copyfile(self.log_path, dest)
            self.toast(f"Saved {dest}")
        except OSError as e:
            self.toast(f"Could not save the log: {e}")

    def open_advanced(self) -> None:
        for cmd in (["liveinst"], ["anaconda", "--liveinst"]):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd, start_new_session=True)
                return
        self.toast("Fedora's full installer (anaconda-live) is not on this image")


class App(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(CSS.encode())
        from gi.repository import Gdk
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        (self.props.active_window or Installer(self)).present()


def main() -> int:
    return App().run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
