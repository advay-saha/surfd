"""The surfd look for surfd's own GTK 4 / libadwaita apps (Settings, Welcome, Installer).

Stock libadwaita looks like GNOME; next to Sway, Waybar and fuzzel it stood out. This
stylesheet makes the apps match the rest of the desktop: the theme's colours, the
monospace font for titles, labels, buttons and inputs (help text stays in the
interface font, so it reads easily), small corners, thin borders instead of shadows,
an accent underline for the current tab, and arrow-prefixed section headings like the menus.

It only needs a palette, so the installer can use it before any user exists.
"""

from __future__ import annotations

from typing import Any

from . import color
from .themes import Palette


def section_title(text: str) -> str:
    """'Accent colour' -> an arrow and 'accent colour', like the fuzzel menus."""
    return f"› {text.lower()}" if text and not text.startswith("›") else text


def app_css(p: Palette, *, ui_font: str = "Inter", mono_font: str = "JetBrains Mono", radius: int = 12) -> str:
    r = max(0, min(radius // 3, 6))  # terminal-like: small corners whatever the bar uses
    border = color.mix(p.surface, p.text, 0.16)
    hover = color.mix(p.surface, p.text, 0.06)
    field = color.mix(p.background, p.surface, 0.5)
    mono = f'"{mono_font}", monospace'
    ui = f'"{ui_font}", sans-serif'
    defines = {
        "accent_color": p.accent if p.is_dark else color.mix(p.accent, "#000000", 0.15),
        "accent_bg_color": p.accent, "accent_fg_color": p.accent_text,
        "window_bg_color": p.background, "window_fg_color": p.text,
        "view_bg_color": field, "view_fg_color": p.text,
        "headerbar_bg_color": p.surface, "headerbar_fg_color": p.text,
        "headerbar_backdrop_color": p.surface, "headerbar_border_color": border,
        "card_bg_color": p.surface, "card_fg_color": p.text,
        "popover_bg_color": p.surface, "popover_fg_color": p.text,
        "dialog_bg_color": p.surface, "dialog_fg_color": p.text,
        "sidebar_bg_color": p.surface, "sidebar_fg_color": p.text,
        "destructive_bg_color": p.urgent, "destructive_fg_color": color.readable_on(p.urgent),
        "destructive_color": p.urgent, "error_color": p.urgent, "warning_color": p.warning,
        "success_color": p.success,
    }
    return "\n".join(f"@define-color {k} {v};" for k, v in defines.items()) + f"""

window, .background {{ background-color: {p.background}; color: {p.text}; }}

/* header bar: flat, a hairline underneath, monospace title */
headerbar {{ background: {p.surface}; box-shadow: inset 0 -1px {border}; min-height: 44px; }}
headerbar .title, windowtitle .title, .title-1, .title-2, .title-3, .title-4, .step-title,
.welcome-title, statuspage .title {{ font-family: {mono}; letter-spacing: -0.01em; }}

/* tabs: monospace, the current one underlined in the accent colour */
viewswitcher button.toggle, viewswitcherbar button.toggle {{
  border-radius: {r}px; background: transparent; box-shadow: none; }}
viewswitcher button.toggle label, viewswitcherbar button.toggle label {{ font-family: {mono}; }}
viewswitcher button.toggle:hover {{ background: {hover}; }}
viewswitcher button.toggle:checked, viewswitcherbar button.toggle:checked {{
  background: transparent; color: @accent_color; box-shadow: inset 0 -2px @accent_color; }}

/* section headings: "› theme" in the accent colour */
preferencesgroup > box > box.header .heading, preferencesgroup .header > .title > label.heading {{
  font-family: {mono}; color: @accent_color; font-weight: 700; }}
preferencesgroup .header .dim-label, preferencesgroup .header .description {{ font-family: {ui}; }}

/* lists: bordered blocks, no shadows */
list.boxed-list, .boxed-list, list.content {{
  background: {p.surface}; border: 1px solid {border}; border-radius: {r}px; box-shadow: none; }}
list.boxed-list > row, .boxed-list > row {{ border-radius: 0; }}
list.boxed-list > row:first-child {{ border-top-left-radius: {r}px; border-top-right-radius: {r}px; }}
list.boxed-list > row:last-child {{ border-bottom-left-radius: {r}px; border-bottom-right-radius: {r}px; }}
row .title {{ font-family: {mono}; }}
row .subtitle {{ font-family: {ui}; }}
row:hover {{ background-color: {hover}; }}
row:focus-visible {{ box-shadow: inset 2px 0 @accent_color; }}
row.expander list {{ background: transparent; }}

/* buttons: thin outline; the main action is a solid accent block */
button {{ border-radius: {r}px; font-family: {mono}; }}
button:not(.flat):not(.suggested-action):not(.destructive-action):not(.toggle):not(.image-button) {{
  background: transparent; box-shadow: inset 0 0 0 1px {border}; }}
button:not(.flat):not(.suggested-action):not(.destructive-action):hover {{ background: {hover}; }}
button.pill {{ border-radius: {r}px; padding: 8px 26px; }}
button.suggested-action {{ background: @accent_bg_color; color: @accent_fg_color; box-shadow: none; }}
button.suggested-action:hover {{ background: {color.mix(p.accent, p.text, 0.12)}; }}
button.destructive-action {{ background: {p.urgent}; color: {color.readable_on(p.urgent)}; box-shadow: none; }}
button.circular {{ border-radius: {r}px; }}

/* inputs */
entry, spinbutton, row.entry text, row.spin spinbutton text, dropdown > button {{ font-family: {mono}; }}
entry, spinbutton {{ border-radius: {r}px; background: {field}; box-shadow: inset 0 0 0 1px {border}; }}
entry:focus-within, spinbutton:focus-within {{ box-shadow: inset 0 0 0 1px @accent_color; outline: none; }}
row spinbutton, row.spin spinbutton {{ background: transparent; box-shadow: none; }}
row spinbutton:focus-within {{ box-shadow: inset 0 -2px @accent_color; }}
switch {{ border-radius: {r}px; }}
switch > slider {{ border-radius: {max(r - 2, 1)}px; }}
switch:checked {{ background: @accent_bg_color; }}
checkbutton check, radiobutton radio {{ border-radius: {max(r - 2, 2)}px; }}
scale trough {{ border-radius: 0; min-height: 4px; }}
scale highlight, progressbar progress {{ background: @accent_bg_color; border-radius: 0; }}
progressbar trough {{ border-radius: 0; }}
.big-progress progress, .big-progress trough {{ min-height: 8px; border-radius: 0; }}

/* pop-ups, menus, toasts, dialogs */
popover > contents, popover.menu > contents {{
  background: {p.surface}; border: 1px solid {border}; border-radius: {r}px; box-shadow: none; }}
popover modelbutton, popover label {{ font-family: {mono}; }}
toast {{ border-radius: {r}px; font-family: {mono}; background: {p.surface};
  border: 1px solid @accent_color; color: {p.text}; }}
dialog-host > dialog.floating sheet, window.dialog, messagedialog {{ border-radius: {r}px; }}
scrollbar slider {{ border-radius: 0; min-width: 4px; min-height: 4px; }}

/* surfd's own widgets */
.theme-card {{ padding: 6px; border-radius: {r}px; background: transparent; box-shadow: inset 0 0 0 1px {border}; }}
.theme-card:hover {{ background: {hover}; }}
.theme-card.selected {{ box-shadow: inset 0 0 0 2px @accent_color; }}
.theme-card label.heading {{ font-family: {mono}; font-weight: 600; }}
.theme-thumb {{ border-radius: {max(r - 2, 0)}px; }}
.swatch {{ min-width: 28px; min-height: 28px; border-radius: {r}px; padding: 0; }}
.swatch.selected {{ box-shadow: 0 0 0 2px {p.background}, 0 0 0 4px currentColor; }}
.palette-dot {{ min-width: 12px; min-height: 12px; border-radius: 2px; }}
.keycap {{ font-family: {mono}; font-size: 0.9em; padding: 2px 8px; border-radius: {r}px;
  background: transparent; box-shadow: inset 0 0 0 1px {border}; color: @accent_color; }}
.welcome-title {{ font-size: 26pt; font-weight: 700; }}
.prompt {{ font-family: {mono}; color: @accent_color; }}
.terminal-note {{ font-family: {mono}; color: {p.text_muted}; }}
.problem {{ color: {p.urgent}; font-family: {mono}; }}
"""


def current() -> tuple[Palette, dict[str, Any]]:
    """The palette and fonts of the user's settings; Tide (the default) when they can't be read."""
    from . import config, themes
    try:
        cfg = config.load()
        _, pal = themes.resolve(cfg)
    except Exception:
        cfg = config.load_defaults()
        pal = themes.resolve(cfg)[1]
    fonts = {"ui_font": config.get(cfg, "fonts.ui") or "Inter", "mono_font": config.get(cfg, "fonts.mono") or "JetBrains Mono",
             "radius": int(config.get(cfg, "layout.radius") or 12)}
    return pal, fonts


def current_css() -> str:
    pal, fonts = current()
    return app_css(pal, **fonts)
