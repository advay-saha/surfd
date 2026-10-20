# Wallpapers

- `generated/`: surfd's own gradient + grain + wordmark wallpapers (Tide, Driftwood, Kelp, Dusk; dark and
  light; 3840x2160, 3840x2400, 3440x1440, 5120x1440). Rebuild with
  `python3 -I tools/wallpapers/make_wallpapers.py render .` (CC BY-SA 4.0).
  Installed by `surfd-theme` in `/usr/share/surfd/wallpapers/surfd/` (the Picture gallery).
- `third-party/`: other people's artwork, **licence unverified**, see `third-party/CREDITS.md`.
  All of it is installed by the `surfd-wallpapers` package.
  - `dynamic/`: time-of-day sets, see [docs/dynamic-wallpapers.md](../docs/dynamic-wallpapers.md). `low-poly-mountain` is the default.
  - `static/`: single images, in the Picture gallery.

The icons, marks and banners are in `brand/` (`python3 -I tools/wallpapers/make_s_brand.py .`).
