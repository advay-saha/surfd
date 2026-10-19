# Making a surfd theme

A theme pack is a folder. Copy one, change some colours, and you have a
theme you can share as a `.tar.gz`.

```sh
surfctl theme new reef --from tide       # copies Tide to ~/.local/share/surfd/themes/reef
$EDITOR ~/.local/share/surfd/themes/reef/theme.toml
surfctl theme set reef                   # try it (applies live)
surfctl doctor                           # checks the pack
surfctl theme export reef ~/             # → ~/surfd-theme-reef.tar.gz
```

Someone else installs it with `surfctl theme install surfd-theme-reef.tar.gz`
or **System → Install a theme pack** in Surf Settings.

## Layout

```
reef/
  theme.toml        required: palette for [dark] and/or [light]
  wallpapers/       images referenced by theme.toml (optional)
  waybar.css        appended to the generated bar style (optional)
  gtk.css           appended to the generated GTK 3/4 style (optional)
  LICENSE           licence for your artwork (strongly recommended)
```

The folder name is the theme's id: lowercase letters, digits, `.`, `_`, `-`.
A user theme with the same name as a built-in one replaces it.

## theme.toml

```toml
[meta]
name = "Reef"
description = "Coral pinks over warm turquoise."
author = "You"
license = "CC-BY-SA-4.0"
version = "1.0"

[cursor]
theme = "breeze_cursors"     # any installed Xcursor theme
size = 24

[dark]
background  = "#0e1a1f"      # desktop and window background
surface     = "#152730"      # bar, notifications, panels, cards
surface_alt = "#1f3540"      # hover / selected surfaces
text        = "#e4eff2"
text_muted  = "#8fa7b0"      # secondary text
accent      = "#ff8a80"      # focus, selection, active workspace
# accent2   = "#ffb27a"      # optional: far end of accent gradients (see below)
urgent      = "#ff6b6b"
warning     = "#f6c56b"
success     = "#7fd6a0"
icon_theme  = "Papirus-Dark"
wallpaper   = "wallpapers/reef-dark.jpg"
terminal = [                 # ANSI 0-7 then bright 8-15
  "#1b2d36", "#ff6b6b", "#7fd6a0", "#f6c56b", "#6fb3e8", "#c59de8", "#5ecfc2", "#c5d4dc",
  "#3a5363", "#ff8f8f", "#a1e8bd", "#ffd98f", "#93cbf5", "#dbbdf5", "#8ce8dc", "#f2f7f9",
]

[light]
# same keys
```

All nine colour keys and the 16 terminal colours are required for each
variant you provide. A theme may provide only `[dark]` or only `[light]`.

### Where each colour shows up

| Key | Used by |
|---|---|
| `background` | wallpaper fallback, window and terminal background, Sway placeholder |
| `surface` | bar, notifications, launcher, GTK header bars, cards and dialogs |
| `surface_alt` | hovered/selected items, inactive focused window border |
| `text` / `text_muted` | everything readable / secondary labels |
| `accent` | focused window border, active workspace, launcher match, selection, GTK accent |
| `urgent` / `warning` / `success` | urgent windows, low battery, errors / resize mode / success states |
| `terminal` | foot's 16 colours |

surfd works out the text colour that sits on top of the accent, the inactive
border colour and the Qt palette for you.

**`accent2` (optional)** is a second accent. Where a surface is filled with the
accent (the active workspace pill in the bar, the login button) surfd draws a
left-to-right gradient from `accent` to `accent2`; Tide uses its teal and blue
this way, like the logo banner. Without `accent2` those surfaces are the plain
accent, and setting your own accent with `surfctl accent` also turns the
gradient off. Everything else (window borders, selection, GTK accent) keeps
using `accent`, so choose an `accent2` that sits well next to it and also meets
3:1 contrast on `background`.

### Readability

Built-in themes must pass these contrast checks (WCAG); please aim for them too:

- `text` on `background` and on `surface`: at least 7:1
- `text_muted` on `surface`: at least 4.5:1
- `accent`, `urgent`, `warning`, `success` on `background`: at least 3:1

`src/surfctl/tests/test_keys_themes.py::test_theme_contrast_meets_wcag` shows
how to check them.

## Wallpapers

Any image `swaybg` can read (JPEG, PNG). The built-in wallpapers are generated
from code by `theme/tools/make_art.py` as SVG and rendered to 3840×2160 JPEG
by `theme/tools/render.py`; reading `make_art.py` is a good start if you want
generative art for your theme. Only ship images you have the right to share.

## Extra CSS

`waybar.css` can restyle bar modules; the generated rules use the module ids
(`#clock`, `#workspaces button.focused`, …). `gtk.css` is appended to the
GTK 3 and GTK 4 user stylesheets; use libadwaita's named colours
(`@accent_bg_color`, …).

## Licensing

Built-in surfd themes are CC BY-SA 4.0. Put your licence in `[meta]` and a
`LICENSE` file so people know what they may do with your pack.
