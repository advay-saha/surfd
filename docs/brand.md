# surfd brand

## Colours

The default look (the **Tide** theme) uses the colours of the surfd banner.

| Role | Dark | On light | Where |
|---|---|---|---|
| Navy (background) | `#0c1b23` | | desktop, boot splash, installer, login |
| Mist (text) | `#dee9ef` | `#15262f` | text, wordmark |
| **Teal** (accent) | `#5ecfc2` | `#0f8f85` | the logo, focus, selection, active workspace |
| **Blue** (accent2) | `#4a90c8` | `#2f6fb0` | the far end of gradients: app icons, active workspace pill, wallpaper swells |

Teal to blue, left to right, is the signature gradient. It belongs on big
surfaces (the banner, app icon tiles, the wallpaper). The logo itself is a
single colour.

## Logo

| File (`theme/logos/`) | Use |
|---|---|
| `surfd-mark.svg` | the S in teal, transparent background: dark backgrounds, system logo (`os-release` `LOGO=`), installer sidebar |
| `surfd-mark-dark.svg` | the S in deep teal, for light backgrounds |
| `surfd-wordmark.svg`, `-dark` | "surfd" lettering on its own |
| `surfd-logo.svg`, `-dark` | S + lettering side by side: Welcome app, boot splash |

Keep clear space around the S of at least half its height, do not recolour it
outside the two teals above, and do not stretch it. The app icons
(`org.surfd.Settings`, `Welcome`, `Installer`) are a teal-to-blue tile with a
navy glyph. `docs/images/banner.png` is the banner for the README and for the
GitHub social preview (repository *Settings → Social preview*).

## Where the shapes come from

* The **S** was traced from the banner, smoothed and fitted with Bézier curves.
* The **lettering** in the banner is Outfit ExtraBold, so the logo uses that
  font's glyph outlines (SIL Open Font License 1.1, © The Outfit Project
  Authors; text in `LICENSES/OFL-1.1.txt`). The logos are outlines, so nothing
  needs the font installed. The interface itself keeps using the system fonts.

`theme/tools/brand_paths.py` holds the resulting paths and is generated; the
SVG logos, icons and wallpapers are generated from it by
`theme/tools/make_art.py` (`make art`). To change the shapes, replace the
banner and run `theme/tools/build_brand_paths.py banner.png outfit-latin-800-normal.woff`
(the font file is in npm's `@fontsource/outfit`), then `make art`.

The artwork contains nothing from Fedora, as the Fedora Remix guidelines require;
see the licensing notes in the README.
