"""Widgets shared by Surf Settings and the Welcome app."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from surfd import color, themes

ACCENT_PRESETS = ["#5ecfc2", "#4a90c8", "#9a8cf0", "#e88bc4", "#f2777a", "#e8956b", "#f4c76c", "#9ccf6e"]


def css(text: str) -> None:
    provider = Gtk.CssProvider()
    provider.load_from_string(text) if hasattr(provider, "load_from_string") else provider.load_from_data(text.encode())
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)


APP_CSS = """
.theme-card { padding: 6px; border-radius: 14px; background: alpha(currentColor, 0.04); }
.theme-card:hover { background: alpha(currentColor, 0.08); }
.theme-card.selected { box-shadow: inset 0 0 0 3px @accent_bg_color; }
.theme-thumb { border-radius: 10px; }
.swatch { min-width: 30px; min-height: 30px; border-radius: 999px; padding: 0; }
.swatch.selected { box-shadow: 0 0 0 3px @window_bg_color, 0 0 0 5px currentColor; }
.palette-dot { min-width: 14px; min-height: 14px; border-radius: 999px; }
.keycap { font-family: monospace; font-size: 0.9em; padding: 2px 8px; border-radius: 6px;
          background: alpha(currentColor, 0.1); }
.welcome-title { font-size: 28pt; font-weight: 300; }
"""


_THUMBS: dict[tuple[str, int, int], Gdk.Texture] = {}  # decoding big wallpapers is slow: once per picture


def _thumb(theme: themes.Theme, variant: str, width: int = 220, height: int = 124) -> Gtk.Widget:
    pal = theme.palette(variant)  # a theme with one style shows it whatever the style chosen
    wp = theme.wallpaper(pal.variant)
    if wp is not None and wp.suffix.lower() in (".jpg", ".jpeg", ".png"):
        try:
            key = (str(wp), width, height)
            if key not in _THUMBS:
                pix = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(wp), width, height, False)
                _THUMBS[key] = Gdk.Texture.new_for_pixbuf(pix)
            tex = _THUMBS[key]
            pic = Gtk.Picture.new_for_paintable(tex)
            pic.set_size_request(width, height)
            pic.set_content_fit(Gtk.ContentFit.COVER) if hasattr(pic, "set_content_fit") else None
            pic.add_css_class("theme-thumb")
            return pic
        except GLib.Error:
            pass
    box = Gtk.Box()
    box.set_size_request(width, height)
    box.add_css_class("theme-thumb")
    name = f"thumb-{theme.name}-{variant}"
    box.set_name(name)
    css(f"#{name} {{ background: linear-gradient(135deg, {pal.background}, {pal.surface_alt} 60%, {pal.accent}); }}")
    return box


class ThemePicker(Gtk.FlowBox):
    """Cards with a wallpaper preview and palette dots for every theme."""

    def __init__(self, on_pick: Callable[[str], None]) -> None:
        super().__init__(selection_mode=Gtk.SelectionMode.NONE, column_spacing=12, row_spacing=12,
                         homogeneous=True, max_children_per_line=4, min_children_per_line=1)
        self.on_pick = on_pick
        self.cards: dict[str, Gtk.Widget] = {}
        self.variant = "dark"

    def populate(self, current: str, variant: str) -> None:
        self.variant = variant
        while (child := self.get_first_child()) is not None:
            self.remove(child)
        self.cards.clear()
        found, _ = themes.discover()
        rules: list[str] = []
        for t in found:
            pal = t.palette(variant)
            card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            card.add_css_class("theme-card")
            card.append(_thumb(t, variant))
            row = Gtk.Box(spacing=6, margin_start=4, margin_end=4, margin_bottom=2)
            label = Gtk.Label(label=t.title, xalign=0, hexpand=True)
            label.add_css_class("heading")
            row.append(label)
            for i, col in enumerate((pal.background, pal.surface_alt, pal.text, pal.accent)):
                dot = Gtk.Box()
                dot.add_css_class("palette-dot")
                dot.set_name(f"dot-{t.name}-{variant}-{i}")
                rules.append(f"#dot-{t.name}-{variant}-{i} {{ background: {col}; "
                             "box-shadow: 0 0 0 1px alpha(currentColor, 0.2); }")
                dot.set_valign(Gtk.Align.CENTER)
                row.append(dot)
            card.append(row)
            button = Gtk.Button(child=card)
            button.add_css_class("flat")
            button.set_tooltip_text(str(t.meta.get("description", "")))
            button.connect("clicked", lambda _b, name=t.name: self.on_pick(name))
            self.append(button)
            self.cards[t.name] = card
        if rules:
            css("\n".join(rules))
        self.select(current)

    def select(self, name: str) -> None:
        for n, card in self.cards.items():
            (card.add_css_class if n == name else card.remove_css_class)("selected")


class AccentRow(Gtk.Box):
    """Preset accent swatches plus a free colour chooser."""

    def __init__(self, on_pick: Callable[[str], None]) -> None:
        super().__init__(spacing=10, valign=Gtk.Align.CENTER)
        self.on_pick = on_pick
        self.buttons: dict[str, Gtk.Button] = {}
        for i, col in enumerate(ACCENT_PRESETS):
            b = Gtk.Button()
            b.add_css_class("swatch")
            b.set_name(f"swatch-{i}")
            css(f"#swatch-{i} {{ background: {col}; color: {col}; }}")
            b.set_tooltip_text(col)
            b.connect("clicked", lambda _b, c=col: self.on_pick(c))
            self.append(b)
            self.buttons[col] = b
        self.chooser = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog(with_alpha=False), valign=Gtk.Align.CENTER)
        self.chooser.set_tooltip_text("Any colour…")
        self._signal = self.chooser.connect("notify::rgba", self._custom)
        self.append(self.chooser)

    def _custom(self, button: Gtk.ColorDialogButton, _pspec: object) -> None:
        rgba = button.get_rgba()
        self.on_pick(color.from_rgb(rgba.red * 255, rgba.green * 255, rgba.blue * 255))

    def show_value(self, value: str) -> None:
        for col, b in self.buttons.items():
            (b.add_css_class if col == value else b.remove_css_class)("selected")
        if value:
            rgba = Gdk.RGBA()
            rgba.parse(value)
            self.chooser.handler_block(self._signal)
            self.chooser.set_rgba(rgba)
            self.chooser.handler_unblock(self._signal)


def keycap_row(combo: str) -> Gtk.Box:
    box = Gtk.Box(spacing=4, valign=Gtk.Align.CENTER)
    for part in combo.split(" + "):
        lab = Gtk.Label(label=part)
        lab.add_css_class("keycap")
        box.append(lab)
    return box


def logo_path() -> Path | None:
    for p in (Path("/usr/share/surfd/logos/surfd-logo.svg"),
              Path(__file__).resolve().parents[3] / "theme" / "logos" / "surfd-logo.svg"):
        if p.is_file():
            return p
    return None
