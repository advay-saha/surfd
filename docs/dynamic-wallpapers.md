# Dynamic wallpapers

macOS-style wallpapers for surfd: a set of frames that follows the time of day, can be pinned to
its lightest or darkest frame for light/dark mode, or fixed to one single frame.

> **Status:** the tool (`tools/wallpapers/surfd-dynwall`) and the wallpaper sets work on their own and are
> tested with dry runs. They are **not yet wired into** the session, `surfd.toml`, `surfctl` or Surf
> Settings. See [Wiring plan](#wiring-plan).

## Wallpaper sets

Eight sets live in `wallpapers/third-party/dynamic/` (artwork by other people, licence unverified: see
`wallpapers/third-party/CREDITS.md`). Each folder holds JPEG frames and a `wallpaper.toml`.

| folder | follows | frames | source size |
|---|---|---|---|
| `low-poly-mountain` | clock | 5 | 1920x1080 |
| `village` | clock | 5 | 3840x2160 |
| `exodus` | clock | 4 | 5120x2880 |
| `plants` | clock | 3 | 3840x2160 |
| `tokyo-street` | clock | 4 | 3200x1800 |
| `japanese-garden` | clock | 5 | 1713x965 |
| `desert-sands` | clock | 6 | 5120x2880 |
| `cyprus` | sun position | 9 | 3000x2000 |

`wallpaper.toml`:

```toml
[wallpaper]
name = "Low-poly mountain"
kind = "time"            # "time" (clock) or "solar" (sun position)
light = "02-noon.jpg"    # brightest frame, used by light mode
dark  = "00-night.jpg"   # darkest frame, used by dark mode
mode  = "fill"

[[frame]]
at = "06:00"             # kind = "time": used from this time until the next frame
file = "01-morning.jpg"
# kind = "solar" uses `altitude` and `azimuth` (degrees) instead of `at`
```

## Using it

```sh
surfd-dynwall daemon          # apply now and keep it in sync (put `exec surfd-dynwall daemon` in the Sway config)
surfd-dynwall list            # installed sets
surfd-dynwall use desert-sands
surfd-dynwall auto            # follow the time of day (default)
surfd-dynwall light           # pin the lightest frame
surfd-dynwall dark            # pin the darkest frame
surfd-dynwall toggle          # flip light <-> dark
surfd-dynwall frame 3         # pin one frame (number from `status`, or part of its file name)
surfd-dynwall status          # what is showing and why
surfd-dynwall location 35.2 33.4   # latitude longitude, for solar sets ("location auto" clears it)
```

Test options: `--at HH:MM`, `--date YYYY-MM-DD`, `--dry` (print instead of calling `swaymsg`).
State is kept in `~/.local/state/surfd/dynwall.json`; the daemon re-reads it every 30 s. It needs
Python 3.11+ and `swaymsg`; no `swaybg` process is used.

- "light" and "dark" are the **brightest and darkest frame** of each set. Exodus and Plants only differ a
  little between them because the artists made the frames that way.
- Sway cannot crossfade backgrounds, so frames switch instantly.
- Solar sets pick the frame whose sun height matches the sun at your location (without `location` the
  longitude comes from your time-zone offset). Cyprus only has morning-side frames, so the afternoon re-uses them.

## Adding a wallpaper from an Apple dynamic HEIC

```sh
pip install pillow-heif numpy
python3 -I tools/wallpapers/heic2surfd.py my.heic wallpapers/third-party/dynamic/my-name "My name" [jpeg_quality]
```

Both Apple formats (`h24` clock, `solar` sun position) are supported. Only add artwork you may redistribute.

## Default wallpaper

The intended default is **Low-poly mountain**: `surfd-dynwall use low-poly-mountain` in `auto` mode on first boot
(live session, installer and installed system), `light` / `dark` following the theme switch, and
`surfctl wallpaper reset` returning to it. If the set is missing, fall back to the generated Tide wallpaper.
Its source is only 1080p, so it is soft on 4K and ultrawide screens.

## Wiring plan

Not done yet:

1. Ship the chosen sets and `surfd-dynwall` in a package (and keep the ISO small: one or two sets, the rest optional).
2. `[wallpaper]` in `surfd.toml`: `dynamic = "low-poly-mountain"`, `sync = "auto" | "light" | "dark" | "frame"`; start
   `surfd-dynwall daemon` from the generated Sway config.
3. `surfctl theme variant light|dark` calls `surfd-dynwall light|dark` while the sync mode is not `auto`.
4. A "Dynamic" tab in Surf Settings, and tests in `src/surfctl/tests/`.
5. Replace the third-party art with wallpapers whose licence is clear before a public release.
