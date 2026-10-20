"""Surf Settings — a small GTK4/libadwaita front end for surfd.toml."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from surfd import __version__, config, dynwall, keys, paths, schema, themes  # noqa: E402

from .controller import Controller  # noqa: E402
from .widgets import APP_CSS, AccentRow, ThemePicker, css, keycap_row  # noqa: E402

APP_ID = "org.surfd.Settings"
PAGES = ("appearance", "layout", "bar", "input", "apps", "system")
SYNC_LABELS = {"auto": "Time of day", "theme": "Light / dark style", "frame": "One frame"}


def _choices(dotted: str) -> list[str]:
    return list(schema.SCHEMA[dotted].choices)


class Window(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, page: str = "appearance") -> None:
        super().__init__(application=app, title="Surf Settings", default_width=920, default_height=720)
        self.set_size_request(360, 420)
        self.toasts = Adw.ToastOverlay()
        self.ctl = Controller(self.error, self.applied)
        self.updating = False  # true while we push config values into widgets
        self.refreshers: list[Any] = []

        self.stack = Adw.ViewStack()
        switcher = Adw.ViewSwitcher(stack=self.stack, policy=Adw.ViewSwitcherPolicy.WIDE)
        header = Adw.HeaderBar(title_widget=switcher)
        menu = Gio.Menu()
        menu.append("Open surfd.toml", "win.open-config")
        menu.append("Keyboard shortcuts", "win.cheatsheet")
        menu.append("About Surf Settings", "win.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu))
        bottom = Adw.ViewSwitcherBar(stack=self.stack)

        view = Adw.ToolbarView()
        view.add_top_bar(header)
        view.add_bottom_bar(bottom)
        view.set_content(self.stack)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 640sp"))
        bp.add_setter(bottom, "reveal", True)
        self.add_breakpoint(bp)

        self.stack.add_titled_with_icon(self.page_appearance(), "appearance", "Appearance", "applications-graphics-symbolic")
        self.stack.add_titled_with_icon(self.page_layout(), "layout", "Windows", "view-grid-symbolic")
        self.stack.add_titled_with_icon(self.page_bar(), "bar", "Bar", "view-continuous-symbolic")
        self.stack.add_titled_with_icon(self.page_input(), "input", "Keyboard", "input-keyboard-symbolic")
        self.stack.add_titled_with_icon(self.page_apps(), "apps", "Apps", "applications-system-symbolic")
        self.stack.add_titled_with_icon(self.page_system(), "system", "System", "emblem-system-symbolic")
        if page in PAGES:
            self.stack.set_visible_child_name(page)

        for name, cb in (("open-config", self.open_config), ("cheatsheet", self.show_cheatsheet),
                         ("about", self.show_about)):
            act = Gio.SimpleAction.new(name, None)
            act.connect("activate", lambda *_a, f=cb: f())
            self.add_action(act)

        self.ctl.subscribe(lambda _cfg: self.refresh())
        self.refresh()

    # --------------------------------------------------------------- feedback --
    def error(self, msg: str) -> None:
        toast = Adw.Toast(title=GLib.markup_escape_text(msg.splitlines()[0][:200]), timeout=6)
        self.toasts.add_toast(toast)
        print(f"surf-settings: {msg}", file=sys.stderr)

    def applied(self, msg: str) -> None:
        self.toasts.add_toast(Adw.Toast(title=msg, timeout=1))

    def refresh(self) -> None:
        self.updating = True
        try:
            for fn in self.refreshers:
                fn()
        finally:
            self.updating = False

    # ------------------------------------------------------- row factories --
    def _set(self, dotted: str, value: Any, now: bool = False) -> None:
        if self.updating:
            return
        if now:
            self.ctl.change_now({dotted: value})
        else:
            self.ctl.change(dotted, value)

    def combo(self, dotted: str, labels: dict[str, str] | None = None) -> Adw.ComboRow:
        fld = schema.SCHEMA[dotted]
        values = _choices(dotted)
        model = Gtk.StringList.new([(labels or {}).get(v, v.replace("-", " ").capitalize()) for v in values])
        row = Adw.ComboRow(title=fld.label, subtitle=fld.help, model=model)
        row.connect("notify::selected", lambda r, _p: self._set(dotted, values[r.get_selected()], now=True))
        self.refreshers.append(lambda: row.set_selected(values.index(self.ctl.get(dotted))
                                                          if self.ctl.get(dotted) in values else 0))
        return row

    def switch(self, dotted: str) -> Adw.SwitchRow:
        fld = schema.SCHEMA[dotted]
        row = Adw.SwitchRow(title=fld.label, subtitle=fld.help)
        row.connect("notify::active", lambda r, _p: self._set(dotted, r.get_active(), now=True))
        self.refreshers.append(lambda: row.set_active(bool(self.ctl.get(dotted))))
        return row

    def spin(self, dotted: str, step: float = 1, digits: int = 0) -> Adw.SpinRow:
        fld = schema.SCHEMA[dotted]
        adj = Gtk.Adjustment(lower=fld.minimum or 0, upper=fld.maximum or 100, step_increment=step,
                             page_increment=step * 5)
        row = Adw.SpinRow(title=fld.label, subtitle=fld.help, adjustment=adj, digits=digits)
        kind = int if fld.kind == "int" else float
        row.connect("notify::value", lambda r, _p: self._set(dotted, kind(round(r.get_value(), digits or 0))
                                                            if kind is int else round(r.get_value(), digits)))
        self.refreshers.append(lambda: row.set_value(float(self.ctl.get(dotted))))
        return row

    def entry(self, dotted: str) -> Adw.EntryRow:
        fld = schema.SCHEMA[dotted]
        row = Adw.EntryRow(title=fld.label, show_apply_button=True)
        row.set_tooltip_text(fld.help)
        row.connect("apply", lambda r: self._set(dotted, r.get_text(), now=True))
        self.refreshers.append(lambda: row.set_text(str(self.ctl.get(dotted) or "")))
        return row

    @staticmethod
    def page(*groups: Adw.PreferencesGroup) -> Adw.PreferencesPage:
        p = Adw.PreferencesPage()
        for g in groups:
            p.add(g)
        return p

    # ------------------------------------------------------------- pages ----
    def page_appearance(self) -> Adw.PreferencesPage:
        g_theme = Adw.PreferencesGroup(title="Theme", description="Theme packs set colours, wallpaper and icons. "
                                       "Drop your own into ~/.local/share/surfd/themes.")
        style = self.combo("theme.variant", {"dark": "Dark", "light": "Light"})
        picker = ThemePicker(lambda name: self._set("theme.name", name, now=True))
        picker.set_margin_top(12)
        self.refreshers.append(lambda: picker.populate(self.ctl.get("theme.name"), self.ctl.get("theme.variant")))
        g_theme.add(style)
        g_theme.add(picker)

        g_accent = Adw.PreferencesGroup(title="Accent colour",
                                        description="Buttons, focus, selection and the active workspace.")
        reset = Gtk.Button(label="Theme default", valign=Gtk.Align.CENTER)
        reset.add_css_class("flat")
        reset.connect("clicked", lambda _b: self._set("theme.accent", "", now=True))
        g_accent.set_header_suffix(reset)
        accent = AccentRow(lambda c: self._set("theme.accent", c, now=True))
        accent.set_halign(Gtk.Align.START)
        accent.set_margin_top(4)
        self.refreshers.append(lambda: accent.show_value(self.ctl.get("theme.accent") or
                                                         themes.resolve(self.ctl.cfg)[1].accent))
        g_accent.add(accent)

        g_wp = self.group_wallpaper()

        g_fonts = Adw.PreferencesGroup(title="Fonts")
        for which in ("ui", "mono"):
            dotted = f"fonts.{which}"
            frow = Adw.ActionRow(title=schema.SCHEMA[dotted].label)
            fbtn = Gtk.FontDialogButton(dialog=Gtk.FontDialog(), level=Gtk.FontLevel.FAMILY, valign=Gtk.Align.CENTER)

            def on_font(b: Gtk.FontDialogButton, _p: object, key: str = dotted) -> None:
                desc = b.get_font_desc()
                if desc and desc.get_family():
                    self._set(key, desc.get_family(), now=True)

            fbtn.connect("notify::font-desc", on_font)

            def show_font(b: Gtk.FontDialogButton = fbtn, key: str = dotted) -> None:
                from gi.repository import Pango
                b.set_font_desc(Pango.FontDescription.from_string(str(self.ctl.get(key))))

            self.refreshers.append(show_font)
            frow.add_suffix(fbtn)
            g_fonts.add(frow)
        g_fonts.add(self.spin("fonts.size"))
        g_fonts.add(self.spin("fonts.mono_size"))
        return self.page(g_theme, g_accent, g_wp, g_fonts)

    def page_layout(self) -> Adw.PreferencesPage:
        g = Adw.PreferencesGroup(title="Windows",
                                 description="Tiling arranges windows for you. Floating behaves like a classic "
                                             "desktop: drag windows by their title bar.")
        g.add(self.combo("layout.mode", {"tiling": "Tiling", "floating": "Floating (mouse-friendly)"}))
        g.add(self.switch("layout.titlebars"))
        g.add(self.switch("layout.focus_follows_mouse"))
        g2 = Adw.PreferencesGroup(title="Spacing and shape")
        for k in ("layout.gaps_inner", "layout.gaps_outer", "layout.border_width", "layout.radius"):
            g2.add(self.spin(k))
        g3 = Adw.PreferencesGroup(title="Display")
        g3.add(self.spin("display.scale", step=0.25, digits=2))
        g4 = Adw.PreferencesGroup(title="Screen lock and power",
                                  description="Seconds of inactivity; 0 turns a step off.")
        for k in ("idle.lock_after", "idle.screen_off_after", "idle.suspend_after"):
            g4.add(self.spin(k, step=60))
        return self.page(g, g2, g3, g4)

    def page_bar(self) -> Adw.PreferencesPage:
        g = Adw.PreferencesGroup(title="Bar")
        g.add(self.combo("bar.position"))
        g.add(self.combo("bar.style"))
        g.add(self.spin("bar.height"))
        presets = Adw.ActionRow(title="Presets", subtitle="Start from a ready-made layout")
        from surfd.cli import BAR_PRESETS
        for name, sides in BAR_PRESETS.items():
            b = Gtk.Button(label=name.capitalize(), valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda _b, s=sides: self.ctl.change_now({f"bar.{k}": v for k, v in s.items()}))
            presets.add_suffix(b)
        g.add(presets)
        g2 = Adw.PreferencesGroup(title="Modules", description="Comma-separated, in order. Available: "
                                  + ", ".join(schema.BAR_MODULES))
        for side in ("left", "center", "right"):
            dotted = f"bar.{side}"
            row = Adw.EntryRow(title=schema.SCHEMA[dotted].label, show_apply_button=True)
            row.connect("apply", lambda r, d=dotted: self._set(d, r.get_text(), now=True))
            self.refreshers.append(lambda r=row, d=dotted: r.set_text(", ".join(self.ctl.get(d))))
            g2.add(row)
        g3 = Adw.PreferencesGroup(title="Notifications")
        g3.add(self.combo("notifications.position"))
        g3.add(self.spin("notifications.timeout", step=1000))
        return self.page(g, g2, g3)

    def page_input(self) -> Adw.PreferencesPage:
        g = Adw.PreferencesGroup(title="Keyboard")
        for k in ("input.keyboard_layout", "input.keyboard_variant", "input.keyboard_options"):
            g.add(self.entry(k))
        g.add(self.combo("keys.modifier", {"Super": "Super (Windows key)", "Alt": "Alt"}))
        g2 = Adw.PreferencesGroup(title="Mouse and touchpad")
        g2.add(self.switch("input.touchpad_tap"))
        g2.add(self.switch("input.natural_scroll"))
        g2.add(self.switch("input.gestures"))
        g2.add(self.spin("input.pointer_accel", step=0.1, digits=1))

        self.g_keys = Adw.PreferencesGroup(title="Key bindings",
                                           description="Super + / shows these anywhere. Actions: "
                                                       "see `surfctl keys actions`.")
        add = Adw.ExpanderRow(title="Add a binding", subtitle="e.g. Mod+F1 → exec foot -e htop")
        combo_e = Adw.EntryRow(title="Keys (Mod+Shift+x)")
        action_e = Adw.EntryRow(title="Action", show_apply_button=True)
        action_e.connect("apply", lambda r: self.add_binding(combo_e, r))
        add.add_row(combo_e)
        add.add_row(action_e)
        self.g_keys.add(add)
        self.key_rows: list[Gtk.Widget] = []
        self.refreshers.append(self.fill_bindings)
        return self.page(g, g2, self.g_keys)

    def fill_bindings(self) -> None:
        for r in self.key_rows:
            self.g_keys.remove(r)
        self.key_rows.clear()
        mod = self.ctl.get("keys.modifier")
        try:
            binds = keys.compile_bindings(self.ctl.cfg)
        except keys.BindingError as e:
            self.error(str(e))
            return
        for b in binds:
            row = Adw.ActionRow(title=GLib.markup_escape_text(b.description),
                                subtitle=GLib.markup_escape_text(b.action))
            row.add_prefix(keycap_row(keys.pretty_combo(b.combo, mod)))
            rm = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER, tooltip_text="Remove")
            rm.add_css_class("flat")
            rm.connect("clicked", lambda _b, c=b.combo: self.ctl.change_now({f"keys.bindings.{c}": "none"}))
            row.add_suffix(rm)
            self.g_keys.add(row)
            self.key_rows.append(row)

    def add_binding(self, combo_e: Adw.EntryRow, action_e: Adw.EntryRow) -> None:
        combo, action = combo_e.get_text().strip(), action_e.get_text().strip()
        try:
            keys.normalize_combo(combo, self.ctl.get("keys.modifier"))
            keys.resolve_action(action, self.ctl.get("apps"))
        except keys.BindingError as e:
            self.error(str(e))
            return
        if self.ctl.change_now({f"keys.bindings.{combo}": action}):
            combo_e.set_text("")
            action_e.set_text("")

    def page_apps(self) -> Adw.PreferencesPage:
        g = Adw.PreferencesGroup(title="Default apps", description="Commands used by key bindings and the bar.")
        for k in ("apps.terminal", "apps.launcher", "apps.browser", "apps.files", "apps.editor"):
            g.add(self.entry(k))
        g2 = Adw.PreferencesGroup(title="Autostart", description="Extra commands to run at login, comma-separated. "
                                  "Apps with their own autostart entry start anyway.")
        row = Adw.EntryRow(title="Commands", show_apply_button=True)
        row.connect("apply", lambda r: self._set("autostart.commands", r.get_text(), now=True))
        self.refreshers.append(lambda: row.set_text(", ".join(self.ctl.get("autostart.commands"))))
        g2.add(row)
        return self.page(g, g2)

    def page_system(self) -> Adw.PreferencesPage:
        g = Adw.PreferencesGroup(title="Configuration",
                                 description=f"Everything here lives in {paths.user_config()} — plain text, "
                                             "easy to back up or keep in git.")
        for title, subtitle, label, cb in (
            ("Edit surfd.toml", "Open the file in your text editor", "Open", self.open_config),
            ("Reload the desktop", "Regenerate and apply everything", "Reload", self.reload),
            ("Undo the last reset", "Restore the most recent backup", "Restore", self.restore),
        ):
            r = Adw.ActionRow(title=title, subtitle=subtitle)
            b = Gtk.Button(label=label, valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda _b, f=cb: f())
            r.add_suffix(b)
            g.add(r)
        reset = Adw.ActionRow(title="Reset to defaults", subtitle="A backup of your current file is kept")
        rb = Gtk.Button(label="Reset…", valign=Gtk.Align.CENTER)
        rb.add_css_class("destructive-action")
        rb.connect("clicked", lambda _b: self.confirm_reset())
        reset.add_suffix(rb)
        g.add(reset)

        g2 = Adw.PreferencesGroup(title="Themes")
        inst = Adw.ActionRow(title="Install a theme pack", subtitle="A folder, .tar.gz or .zip with a theme.toml")
        ib = Gtk.Button(label="Install…", valign=Gtk.Align.CENTER)
        ib.connect("clicked", lambda _b: self.install_theme())
        inst.add_suffix(ib)
        g2.add(inst)
        greeter = Adw.ActionRow(title="Use this theme on the login screen", subtitle="Asks for your password")
        gb = Gtk.Button(label="Apply", valign=Gtk.Align.CENTER)
        gb.connect("clicked", lambda _b: self.sync_greeter())
        greeter.add_suffix(gb)
        g2.add(greeter)

        g3 = Adw.PreferencesGroup(title="Hardware")
        hw = Adw.ActionRow(title="Check drivers and firmware",
                           subtitle="Suggests extra drivers (NVIDIA, Wi-Fi, audio) — installs nothing")
        hb = Gtk.Button(label="Check", valign=Gtk.Align.CENTER)
        hb.connect("clicked", lambda _b: self.hwprobe())
        hw.add_suffix(hb)
        g3.add(hw)
        return self.page(g, g2, g3)

    def group_wallpaper(self) -> Adw.PreferencesGroup:
        """Wallpaper: a dynamic (time-of-day) set, what it follows, your own image, scaling."""
        g = Adw.PreferencesGroup(title="Wallpaper", description="A dynamic wallpaper changes through the day. "
                                 "Your own image, when set, is shown instead.")
        default = Gtk.Button(label="Default", valign=Gtk.Align.CENTER)
        default.add_css_class("flat")
        default.set_tooltip_text("Back to the default wallpaper, following the time of day")
        default.connect("clicked", lambda _b: None if self.updating else self.ctl.change_now(
            {"wallpaper.path": "", "wallpaper.dynamic": dynwall.DEFAULT_SET, "wallpaper.sync": "auto",
             "wallpaper.frame": ""}))
        g.set_header_suffix(default)

        set_names: list[str] = [""]
        dyn = Adw.ComboRow(title=schema.SCHEMA["wallpaper.dynamic"].label, subtitle="Changes with the time of day",
                           model=Gtk.StringList())

        def fill(row: Adw.ComboRow, labels: list[str], index: int) -> None:
            """Update a combo only where it differs: rebuilding the list or re-selecting inside a change
            handler makes Adwaita send another "selected" notification after our guard is released."""
            model = row.get_model()
            if [model.get_string(i) for i in range(model.get_n_items())] != labels:
                row.set_model(Gtk.StringList.new(labels))
            if row.get_selected() != index:
                row.set_selected(index)

        def on_dynamic(r: Adw.ComboRow, _p: object) -> None:
            i = r.get_selected()
            if self.updating or i >= len(set_names) or set_names[i] == (self.ctl.get("wallpaper.dynamic") or ""):
                return
            changes: dict[str, Any] = {"wallpaper.dynamic": set_names[i]}
            if set_names[i]:
                changes["wallpaper.path"] = ""  # picking a dynamic wallpaper means you want to see it
            self.ctl.change_now(changes)

        dyn.connect("notify::selected", on_dynamic)

        sync = self.combo("wallpaper.sync", SYNC_LABELS)
        sync.set_subtitle("What decides which picture is shown")
        frame_names: list[str] = []
        frame = Adw.ComboRow(title=schema.SCHEMA["wallpaper.frame"].label, subtitle="The picture to keep showing",
                             model=Gtk.StringList())

        def on_frame(r: Adw.ComboRow, _p: object) -> None:
            i = r.get_selected()
            if self.updating or i >= len(frame_names) or frame_names[i] == self.ctl.get("wallpaper.frame"):
                return
            self._set("wallpaper.frame", frame_names[i], now=True)

        frame.connect("notify::selected", on_frame)
        location = self.entry("wallpaper.location")
        location.set_title("Location (latitude, longitude)")

        def refresh_dynamic() -> None:
            sets = dynwall.discover()
            set_names[:] = ["", *sets]
            name = self.ctl.get("wallpaper.dynamic") or ""
            fill(dyn, ["None (use the theme's wallpaper)", *(d.title for d in sets.values())],
                 set_names.index(name) if name in set_names else 0)
            dset = sets.get(name)
            mode = self.ctl.get("wallpaper.sync") or "auto"
            sync.set_visible(dset is not None)
            frame_names[:] = [f.file.name for f in dset.frames] if dset else []
            wanted = dynwall.named_frame(dset, self.ctl.get("wallpaper.frame") or "") if dset else None
            fill(frame, [self._frame_label(dset, f) for f in dset.frames] if dset else [],
                 frame_names.index(wanted.name) if wanted and wanted.name in frame_names else 0)
            frame.set_visible(dset is not None and mode == "frame")
            location.set_visible(dset is not None and dset.kind == "solar" and mode == "auto")

        self.refreshers.append(refresh_dynamic)

        own = Adw.ActionRow(title="Your own image")
        choose = Gtk.Button(label="Choose…", valign=Gtk.Align.CENTER)
        choose.connect("clicked", lambda _b: self.choose_wallpaper())
        clear = Gtk.Button(label="Remove", valign=Gtk.Align.CENTER)
        clear.add_css_class("flat")
        clear.connect("clicked", lambda _b: self._set("wallpaper.path", "", now=True))
        own.add_suffix(clear)
        own.add_suffix(choose)

        def refresh_own() -> None:
            path = self.ctl.get("wallpaper.path") or ""
            own.set_subtitle(path or "None; the wallpaper above (or the theme's) is shown")
            clear.set_visible(bool(path))

        self.refreshers.append(refresh_own)

        for row in (dyn, sync, frame, location, own, self.combo("wallpaper.mode")):
            g.add(row)
        return g

    @staticmethod
    def _frame_label(dset: dynwall.DynSet, f: dynwall.Frame) -> str:
        if f.at is not None:
            return f"{f.file.stem.split('-', 1)[-1].capitalize()}  ({f.at // 60:02d}:{f.at % 60:02d})"
        return f"{f.file.stem.split('-', 1)[-1]}  (sun {f.altitude:+.0f}°)"

    # ------------------------------------------------------------ actions ----
    def choose_wallpaper(self) -> None:
        dlg = Gtk.FileDialog(title="Choose a wallpaper")
        filt = Gtk.FileFilter(name="Images")
        for mime in ("image/png", "image/jpeg", "image/webp", "image/svg+xml"):
            filt.add_mime_type(mime)
        store = Gio.ListStore.new(Gtk.FileFilter)
        store.append(filt)
        dlg.set_filters(store)

        def done(d: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            if f and f.get_path():
                self._set("wallpaper.path", f.get_path(), now=True)

        dlg.open(self, None, done)

    def install_theme(self) -> None:
        dlg = Gtk.FileDialog(title="Install a theme pack")

        def done(d: Gtk.FileDialog, res: Gio.AsyncResult) -> None:
            try:
                f = d.open_finish(res)
            except GLib.Error:
                return
            try:
                t = themes.install(Path(f.get_path()), force=True)
            except themes.ThemeError as e:
                self.error(str(e))
                return
            self.applied(f"Installed {t.title}")
            self.refresh()

        dlg.open(self, None, done)

    def open_config(self) -> None:
        config.ensure_user_config()
        Gio.AppInfo.launch_default_for_uri(paths.user_config().as_uri(), None)

    def reload(self) -> None:
        self.ctl.change_now({})
        from surfd import generate, session
        try:
            session.regenerate_and_reload(generate.build_context())
            self.applied("Desktop reloaded")
        except Exception as e:
            self.error(str(e))

    def restore(self) -> None:
        if self.ctl.restore_latest():
            self.applied("Restored the latest backup")

    def confirm_reset(self) -> None:
        dlg = Adw.AlertDialog(heading="Reset everything to defaults?",
                              body="Your current surfd.toml is backed up first, and you can restore it "
                                   "from this page.")
        dlg.add_response("cancel", "Cancel")
        dlg.add_response("reset", "Reset")
        dlg.set_response_appearance("reset", Adw.ResponseAppearance.DESTRUCTIVE)

        def on_response(_d: Adw.AlertDialog, response: str) -> None:
            if response == "reset" and self.ctl.reset() is not None:
                self.applied("Reset to defaults (backup kept)")

        dlg.connect("response", on_response)
        dlg.present(self)

    def sync_greeter(self) -> None:
        if not shutil.which("pkexec"):
            self.error("pkexec is not installed; run: sudo surfctl greeter sync")
            return
        proc = subprocess.run(["pkexec", "surfctl", "greeter", "sync"], capture_output=True, text=True, check=False)
        (self.applied if proc.returncode == 0 else self.error)(
            "Login screen updated" if proc.returncode == 0 else (proc.stderr or proc.stdout).strip() or "Cancelled")

    def hwprobe(self) -> None:
        if not shutil.which("surfd-hwprobe"):
            self.error("surfd-hwprobe is not installed (sudo dnf install surfd-hwprobe)")
            return
        out = subprocess.run(["surfd-hwprobe"], capture_output=True, text=True, check=False).stdout
        view = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR,
                            top_margin=12, bottom_margin=12, left_margin=12, right_margin=12)
        view.get_buffer().set_text(out)
        dlg = Adw.Dialog(title="Hardware check", content_width=720, content_height=520)
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())
        tv.set_content(Gtk.ScrolledWindow(child=view))
        dlg.set_child(tv)
        dlg.present(self)

    def show_cheatsheet(self) -> None:
        dlg = Adw.Dialog(title="Keyboard shortcuts", content_width=640, content_height=640)
        page = Adw.PreferencesPage()
        groups: dict[str, Adw.PreferencesGroup] = {}
        for cat, combo, desc in keys.cheatsheet_lines(self.ctl.cfg):
            if cat not in groups:
                groups[cat] = Adw.PreferencesGroup(title=cat)
                page.add(groups[cat])
            row = Adw.ActionRow(title=GLib.markup_escape_text(desc))
            row.add_suffix(keycap_row(combo))
            groups[cat].add(row)
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())
        tv.set_content(page)
        dlg.set_child(tv)
        dlg.present(self)

    def show_about(self) -> None:
        about = Adw.AboutDialog(application_name="Surf Settings", application_icon=APP_ID, version=__version__,
                                developer_name="surfd contributors", license_type=Gtk.License.MIT_X11,
                                comments="Settings for the surfd desktop. surfd is based on Fedora Linux but is "
                                         "not an official Fedora project.",
                                website="https://github.com/advay-saha/surfd")
        about.present(self)


class App(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.page = "appearance"

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        args = command_line.get_arguments()[1:]
        if args and args[0] in ("-h", "--help"):
            command_line.print_literal("usage: surf-settings [" + "|".join(PAGES) + "]\n")
            return 0
        if args and args[0] in PAGES:
            self.page = args[0]
        self.activate()
        return 0

    def do_activate(self) -> None:
        css(APP_CSS)
        win = self.props.active_window or Window(self, self.page)
        if isinstance(win, Window) and self.page in PAGES:
            win.stack.set_visible_child_name(self.page)
        win.present()


def main() -> int:
    return App().run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
