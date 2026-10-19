"""surfd Welcome — first-login tour: pick a look, learn five keys, get apps."""

from __future__ import annotations

import shutil
import subprocess
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, Gtk  # noqa: E402

from surfd import paths, system  # noqa: E402

from .controller import Controller  # noqa: E402
from .widgets import APP_CSS, AccentRow, ThemePicker, css, keycap_row, logo_path  # noqa: E402

APP_ID = "org.surfd.Welcome"

ESSENTIAL_KEYS = [
    ("Super + Enter", "Open a terminal"),
    ("Super + Space", "Search and launch apps"),
    ("Super + Q", "Close the window"),
    ("Super + 1 … 9", "Switch workspace"),
    ("Super + Shift + Space", "Float / tile a window"),
    ("Super + /", "Every shortcut, searchable"),
    ("Super + ,", "Surf Settings"),
    ("Super + Shift + E", "Log out, restart, shut down"),
]


def is_live() -> bool:
    return system.is_live_session() or (paths.user_config_dir() / ".live-session").exists()


class Welcome(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app, title="Welcome to surfd", default_width=860, default_height=640)
        self.set_size_request(360, 480)
        self.toasts = Adw.ToastOverlay()
        self.ctl = Controller(lambda m: self.toasts.add_toast(Adw.Toast(title=m[:180], timeout=5)),
                              lambda _m: None)
        self.carousel = Adw.Carousel(allow_scroll_wheel=False, vexpand=True)
        dots = Adw.CarouselIndicatorDots(carousel=self.carousel)

        self.back = Gtk.Button(label="Back")
        self.back.connect("clicked", lambda _b: self.go(-1))
        self.next = Gtk.Button(label="Next")
        self.next.add_css_class("suggested-action")
        self.next.connect("clicked", lambda _b: self.go(+1))
        nav = Gtk.CenterBox(margin_start=18, margin_end=18, margin_bottom=18, margin_top=6)
        nav.set_start_widget(self.back)
        nav.set_center_widget(dots)
        nav.set_end_widget(self.next)

        self.pages = [self.page_hello(), self.page_look(), self.page_keys(), self.page_apps()]
        if is_live():
            self.pages.insert(1, self.page_install())
        for p in self.pages:
            self.carousel.append(p)
        self.carousel.connect("page-changed", lambda *_a: self.update_nav())

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        header = Adw.HeaderBar(show_title=False)
        header.add_css_class("flat")
        box.append(header)
        box.append(self.carousel)
        box.append(nav)
        self.toasts.set_child(box)
        self.set_content(self.toasts)
        self.update_nav()

    # ---------------------------------------------------------- navigation --
    def go(self, delta: int) -> None:
        idx = round(self.carousel.get_position()) + delta
        if idx >= len(self.pages):
            self.finish()
            return
        idx = max(0, idx)
        self.carousel.scroll_to(self.pages[idx], True)

    def update_nav(self) -> None:
        idx = round(self.carousel.get_position())
        self.back.set_sensitive(idx > 0)
        self.next.set_label("Start using surfd" if idx == len(self.pages) - 1 else "Next")

    def finish(self) -> None:
        marker = paths.user_config_dir() / ".welcome-done"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
        self.close()

    # --------------------------------------------------------------- pages --
    @staticmethod
    def status(title: str, description: str, child: Gtk.Widget | None = None) -> Adw.StatusPage:
        page = Adw.StatusPage(title=title, description=description, hexpand=True, vexpand=True)
        if child is not None:
            clamp = Adw.Clamp(maximum_size=760, child=child)
            page.set_child(clamp)
        return page

    def page_hello(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24, valign=Gtk.Align.CENTER)
        logo = logo_path()
        if logo is not None:
            pic = Gtk.Picture.new_for_filename(str(logo))
            pic.set_size_request(-1, 110)
            pic.set_can_shrink(True)
            box.append(pic)
        title = Gtk.Label(label="Welcome")
        title.add_css_class("welcome-title")
        box.append(title)
        text = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=60,
                         label="A light, calm desktop built on Fedora Linux. This short tour sets your look "
                               "and shows the few keys worth knowing. Everything can be changed later in "
                               "Surf Settings (Super + ,).")
        text.add_css_class("dim-label")
        box.append(text)
        note = Gtk.Label(label="surfd is based on Fedora Linux but is not an official Fedora project.")
        note.add_css_class("caption")
        note.add_css_class("dim-label")
        box.append(note)
        return Adw.Clamp(maximum_size=640, child=box, margin_start=24, margin_end=24)

    def page_install(self) -> Gtk.Widget:
        btn = Gtk.Button(label="Install surfd…", halign=Gtk.Align.CENTER)
        btn.add_css_class("pill")
        btn.add_css_class("suggested-action")
        btn.connect("clicked", lambda _b: self.launch_installer())
        page = self.status("You are running the live system",
                           "Try everything first — nothing is saved. When you are ready, install surfd to your "
                           "disk. The installer is also in the app launcher (Super + Space, type “install”).",
                           btn)
        page.set_icon_name("drive-harddisk-symbolic")
        return page

    def page_look(self) -> Gtk.Widget:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        style = Gtk.Box(spacing=0, halign=Gtk.Align.CENTER, css_classes=["linked"])
        dark = Gtk.ToggleButton(label="Dark")
        light = Gtk.ToggleButton(label="Light", group=dark)
        (dark if self.ctl.get("theme.variant") == "dark" else light).set_active(True)
        style.append(dark)
        style.append(light)
        picker = ThemePicker(lambda n: (self.ctl.change_now({"theme.name": n}), picker.select(n)))
        picker.set_max_children_per_line(3)
        accent = AccentRow(lambda c: (self.ctl.change_now({"theme.accent": c}), accent.show_value(c)))
        accent.set_halign(Gtk.Align.CENTER)

        def set_variant(btn: Gtk.ToggleButton, variant: str) -> None:
            if btn.get_active() and self.ctl.get("theme.variant") != variant:
                self.ctl.change_now({"theme.variant": variant})
                picker.populate(self.ctl.get("theme.name"), variant)

        dark.connect("toggled", set_variant, "dark")
        light.connect("toggled", set_variant, "light")
        picker.populate(self.ctl.get("theme.name"), self.ctl.get("theme.variant"))
        accent.show_value(self.ctl.get("theme.accent"))
        box.append(style)
        box.append(picker)
        box.append(accent)
        return self.status("Pick your look", "Changes apply instantly.", box)

    def page_keys(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup()
        for combo, desc in ESSENTIAL_KEYS:
            row = Adw.ActionRow(title=desc)
            row.add_suffix(keycap_row(combo))
            group.add(row)
        mode = Adw.SwitchRow(title="Prefer the mouse?",
                             subtitle="Windows float with title bars instead of tiling. Change any time.")
        mode.set_active(self.ctl.get("layout.mode") == "floating")
        mode.connect("notify::active",
                     lambda r, _p: self.ctl.change_now({"layout.mode": "floating" if r.get_active() else "tiling"}))
        group2 = Adw.PreferencesGroup()
        group2.add(mode)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        box.append(group)
        box.append(group2)
        return self.status("Eight keys to know", "Super is the Windows key. Touchpad: swipe three fingers "
                           "sideways to switch workspaces, up to open the launcher.", box)

    def page_apps(self) -> Gtk.Widget:
        group = Adw.PreferencesGroup()
        flathub = Adw.ActionRow(title="Apps from Flathub", use_markup=False,
                                subtitle="Flatpak is set up with Flathub. Example: "
                                         "flatpak install flathub org.libreoffice.LibreOffice")
        flathub.add_prefix(Gtk.Image(icon_name="system-software-install-symbolic"))
        group.add(flathub)
        dnf = Adw.ActionRow(title="Fedora packages", subtitle="sudo dnf install NAME — everything in Fedora works",
                            use_markup=False)
        dnf.add_prefix(Gtk.Image(icon_name="utilities-terminal-symbolic"))
        group.add(dnf)
        hw = Adw.ActionRow(title="Check your hardware", subtitle="Suggests NVIDIA, Wi-Fi or audio drivers if needed")
        hw.add_prefix(Gtk.Image(icon_name="computer-symbolic"))
        hb = Gtk.Button(label="Check", valign=Gtk.Align.CENTER)
        hb.connect("clicked", lambda _b: self.run_in_terminal("surfd-hwprobe; echo; read -p 'Press Enter to close'"))
        hw.add_suffix(hb)
        group.add(hw)
        return self.status("Getting apps", "surfd stays small; add what you need.", group)

    # ------------------------------------------------------------- helpers --
    def run_in_terminal(self, command: str) -> None:
        term = self.ctl.get("apps.terminal") or "foot"
        try:
            subprocess.Popen([*term.split(), "-e", "sh", "-c", command], start_new_session=True)
        except OSError as e:
            self.toasts.add_toast(Adw.Toast(title=f"Could not start {term}: {e}"))

    def launch_installer(self) -> None:
        for cmd in (["liveinst"], ["anaconda", "--liveinst"]):
            if shutil.which(cmd[0]):
                subprocess.Popen(cmd, start_new_session=True)
                return
        self.toasts.add_toast(Adw.Toast(title="The installer (anaconda-live) is not available on this image"))


class App(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self) -> None:
        css(APP_CSS)
        (self.props.active_window or Welcome(self)).present()


def main() -> int:
    return App().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
