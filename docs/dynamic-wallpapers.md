# Dynamic wallpapers

macOS-style wallpapers: a set of pictures that follows the **time of day**, follows the theme's **light/dark
style**, or stays on **one frame**. surfd's default wallpaper is one: **Low-poly mountain**.

## Using them

Everything is a normal surfd setting (`[wallpaper]` in `surfd.toml`), so `surfctl`, Surf Settings
(*Appearance -> Wallpaper*) and hand edits agree.

```sh
surfctl wallpaper status               # what is showing, and every frame of the set
surfctl wallpaper list                 # installed sets
surfctl wallpaper dynamic desert-sands # pick a set; "off" goes back to the theme's wallpaper
surfctl wallpaper sync auto            # follow the time of day (default)
surfctl wallpaper sync theme           # lightest frame in light style, darkest in dark style
surfctl wallpaper sync frame noon      # keep one frame: its number, or part of its file name
surfctl wallpaper location 35.2 33.4   # latitude longitude, for sets that follow the sun
surfctl wallpaper reset                # back to the default (Low-poly mountain, time of day)
surfctl wallpaper set ~/Pictures/x.jpg # your own image: it wins over a dynamic wallpaper
```

```toml
[wallpaper]
path = ""                       # your own image; wins over the dynamic wallpaper
dynamic = "low-poly-mountain"   # "" = the theme's wallpaper
sync = "auto"                   # "auto" | "theme" | "frame"
frame = ""                      # with sync = "frame"
location = ""                   # "35.2, 33.4" for sun-following sets; "" = guess from the time zone
mode = "fill"                   # scaling, as for any wallpaper
```

- **`auto`** follows the clock (or the sun, for sets made that way). A small helper (`surfd-dynwall`, started by
  the Sway config and restarted on every reload) changes the picture exactly when the next frame starts. It sleeps
  at most 5 minutes at a time, so suspend and resume are harmless. It stops by itself when nothing needs it.
- **`theme`** uses the set's lightest frame in the light style and the darkest in the dark style. Because the
  style is a normal setting, `surfctl theme variant toggle` (or the Style switch in Surf Settings) changes the
  wallpaper too.
- **`frame`** keeps one picture; `surfctl wallpaper status` numbers them.
- The **lock screen** shows the same picture as the desktop. `sudo surfctl greeter sync` copies the current
  frame to the login screen (a single picture; the login screen does not change through the day).
- Sway cannot crossfade backgrounds, so frames switch instantly.

## The sets

Sets live in `/usr/share/surfd/wallpapers/dynamic/` (system) and `~/.local/share/surfd/wallpapers/dynamic/`
(yours; same name = yours wins). The repository holds eight in `wallpapers/third-party/dynamic/`; only the
default is installed by the `surfd-wallpapers` package.

| set | follows | frames | source size |
|---|---|---|---|
| `low-poly-mountain` (default) | clock | 5 | 1920x1080 |
| `village` | clock | 5 | 3840x2160 |
| `exodus` | clock | 4 | 5120x2880 |
| `plants` | clock | 3 | 3840x2160 |
| `tokyo-street` | clock | 4 | 3200x1800 |
| `japanese-garden` | clock | 5 | 1713x965 |
| `desert-sands` | clock | 6 | 5120x2880 |
| `cyprus` | sun position | 9 | 3000x2000 |

"Lightest" and "darkest" are the brightest and darkest frame of each set, measured when it was converted.
Exodus and Plants only differ a little between them because the artists made the frames that way.
Low-poly mountain is only 1080p, so it is soft on 4K and ultrawide screens.

**Licences:** these are other people's artwork and their licences are **not verified** (see
`wallpapers/third-party/CREDITS.md` and `LICENSES/LicenseRef-third-party-unverified.txt`). That conflicts with the
"original artwork only" rule in CONTRIBUTING.md. Confirm them, or replace the default with wallpapers whose
licence is clear, before a release or an ISO you distribute.

## Making a set

A set is a folder with frames and a `wallpaper.toml`:

```toml
[wallpaper]
name  = "Low-poly mountain"
kind  = "time"              # "time" (clock) or "solar" (sun position)
light = "02-noon.jpg"       # lightest frame
dark  = "00-night.jpg"      # darkest frame

[[frame]]
at = "06:00"                # kind = "time": used from this time until the next frame
file = "01-dawn.jpg"
# kind = "solar": altitude = -10.0 and azimuth = 109.0 (degrees) instead of `at`
```

From an Apple dynamic HEIC (both its clock and its sun-position formats work):

```sh
pip install pillow-heif numpy
python3 tools/wallpapers/heic2surfd.py my.heic ~/.local/share/surfd/wallpapers/dynamic/my-set "My set"
surfctl wallpaper dynamic my-set
```

Only add artwork you may redistribute. A set that is broken (a missing frame, a bad time) is skipped and
`surfctl wallpaper list` does not show it.

## How it works (for contributors)

- `src/surfctl/surfd/dynwall.py` finds sets, picks the frame (clock or NOAA sun position) and is pure logic.
- `generate.Context.dynamic` evaluates it once per generated config, so the Sway config, the lock screen and
  the login-screen sync all show the same frame. The Sway config also runs `libexec/surfd-dynwall on|off` on
  every reload; `on` starts `surfctl wallpaper daemon` (`session.wallpaper_daemon`), `off` stops a leftover one.
- While following the clock, the lock screen reads `~/.local/state/surfd/generated/wallpaper-current`, a symlink
  the helper keeps on the current frame.
- Tests: `src/surfctl/tests/test_dynwall.py`; the GUI is covered by `src/settings/tests/gui_smoke.py`.
