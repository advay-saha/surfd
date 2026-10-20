#!/usr/bin/env python3
"""Write a theme pack for every wallpaper that ships with surfd.

    python3 theme/tools/make_wallpaper_themes.py

Each theme takes its colours from one picture. The seeds below (background hue and
saturation, accent, second accent) were picked by eye from the picture; everything else
(surfaces, text, status and terminal colours) is derived here, with lightness nudged until
the WCAG contrast rules in src/surfctl/tests/test_keys_themes.py hold.

* Still pictures get the one style that suits them (a dark picture, a dark theme).
* Dynamic (time-of-day) sets get both: light from the daytime frame, dark from the night one.
  The theme brings the dynamic set with it ([wallpaper] dynamic = ...).
* Dusk uses the "dusk" colourway; Tide, Driftwood and Kelp are kept by hand.

Output: <name>/theme.toml and LICENSE, in wallpapers/third-party/themes/ for themes made from
other artists' pictures (packaged with those pictures, in surfd-wallpapers) and in theme/themes/
for Dusk. Re-run after changing a seed.
"""

from __future__ import annotations

import colorsys
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / "src" / "surfctl"))
from surfd import color  # noqa: E402


@dataclass(frozen=True)
class Seed:
    hue: float  # background hue, degrees
    sat: float  # background saturation, 0-1 (capped per style)
    accent: str
    accent2: str


@dataclass(frozen=True)
class Spec:
    name: str
    title: str
    about: str  # "picked from ..." sentence for the description
    dark: Seed | None = None
    light: Seed | None = None
    picture: dict[str, str] | None = None  # variant -> gallery picture name
    dynamic: str = ""


def still(name: str, title: str, picture: str, credit: str, **seed: Seed) -> Spec:
    """A theme for one still picture, in the one style (dark= or light=) that suits it."""
    (variant,) = seed
    return Spec(name, title, f"Colours from {credit}.", picture={variant: picture}, **seed)


def dynamic(name: str, title: str, light: Seed, dark: Seed) -> Spec:
    return Spec(name, title, f"The {title} dynamic wallpaper: light by day, dark by night.",
                dark=dark, light=light, dynamic=name)


SPECS = [
    # --- still pictures ("More wallpapers" in the gallery) ---
    still("study", "Study", "lee_zudarts-study", "'Study' by lee_zudarts", dark=
          Seed(333, 0.25, "#8f9fe0", "#e8a3b0")),
    still("small-memory", "Small Memory", "mklgustafsson-small-memory", "'Small memory' by Mikael Gustafsson", dark=
          Seed(215, 0.70, "#f2be96", "#5db3bf")),
    still("scenery-sunset", "Scenery Sunset", "muriLLu-anime-scenery-sunset", "'Anime scenery sunset' by muriLLu", dark=
          Seed(257, 0.50, "#f2a97b", "#e1827f")),
    still("bitter-coast", "Bitter Coast", "ogarart-bitter-coast", "'Bitter coast' by ogarart", light=
          Seed(23, 0.60, "#ab192f", "#78345c")),
    still("fortress", "Fortress", "ogarart-fortress", "'Fortress' by ogarart", dark=
          Seed(222, 0.70, "#70c7e1", "#639cc5")),
    still("red-cave", "Red Cave", "ogarart-red-cave", "'Red cave' by ogarart", dark=
          Seed(320, 0.27, "#f65c52", "#e0607a")),
    still("breaking-wave", "Breaking Wave", "pixabay-breaking-wave-coast", "a breaking-wave photo from Pixabay", light=
          Seed(214, 0.25, "#134d5b", "#2c6877")),
    still("curling-wave", "Curling Wave", "pixabay-curling-wave", "a curling-wave photo from Pixabay", light=
          Seed(178, 0.18, "#046469", "#1d7f89")),
    still("tropical-beach", "Tropical Beach", "pixabay-tropical-beach-aerial", "an aerial beach photo from Pixabay",
          light= Seed(186, 0.45, "#047f88", "#2f7d3a")),
    still("morning-surf", "Morning Surf", "pixabay-wave-and-surfer", "a wave-and-surfer photo from Pixabay", light=
          Seed(200, 0.10, "#3d6670", "#8a6f60")),
    still("starfall", "Starfall", "totalcoconut-midjourney-landscape", "'Midjourney landscape' by totalcoconut", dark=
          Seed(232, 0.45, "#ec9ba8", "#b88fc0")),
    still("golden-hour", "Golden Hour", "unknown-anime-sunset", "'Anime sunset' (artist unknown)", dark=
          Seed(216, 0.45, "#e7a07f", "#c98a6c")),
    still("crimson-sunset", "Crimson Sunset", "unreal-midjourney-a-stunning-sunset", "'A stunning sunset' by unreal",
          dark= Seed(272, 0.55, "#f95e3f", "#e0459a")),
    still("temple", "Temple", "vorgbardo-ancient-oriental-temple", "'Ancient oriental temple' by VorgBardo", dark=
          Seed(196, 0.50, "#a4d8cd", "#e0675a")),
    still("retro-planet", "Retro Planet", "vorgbardo-midjourney-1960s-sci-fi-planet", "'1960s sci-fi planet' by VorgBardo",
          light= Seed(40, 0.70, "#a6600f", "#566579")),
    still("camino-de-kazul", "Camino de Kazul", "voyager-camino-de-kazul", "'Camino de Kazul' by voyager", light=
          Seed(190, 0.50, "#2b6f7f", "#a0506a")),
    still("moonrise", "Moonrise", "wallpapersden-landscape-moon-digital-evening", "'Landscape moon digital evening' "
          "(wallpapersden)", dark= Seed(205, 0.75, "#4cbeab", "#7fd6e0")),
    still("blue-mountains", "Blue Mountains", "wheazzy-blue-mountains", "'Blue mountains' by wheazzy", dark=
          Seed(206, 0.65, "#5fa2dc", "#8ec5f0")),
    # --- dynamic (time-of-day) sets: light from the day frame, dark from the night frame ---
    dynamic("cyprus", "Cyprus", light=Seed(50, 0.12, "#3f6e85", "#5f6b2f"), dark=Seed(205, 0.25, "#93b4cc", "#e8c07a")),
    dynamic("desert-sands", "Desert Sands", light=Seed(30, 0.40, "#3e759e", "#9c6a3f"),
            dark=Seed(214, 0.45, "#5fd3a0", "#4fb3c9")),
    dynamic("exodus", "Exodus", light=Seed(37, 0.14, "#1f5a70", "#3f7f7f"), dark=Seed(234, 0.20, "#d4807c", "#c57d5f")),
    dynamic("japanese-garden", "Japanese Garden", light=Seed(270, 0.40, "#b03a2e", "#6a5ab0"),
            dark=Seed(205, 0.70, "#e86a5a", "#f0b86a")),
    dynamic("low-poly-mountain", "Low-poly Mountain", light=Seed(80, 0.50, "#3d5f97", "#2f8f88"),
            dark=Seed(252, 0.23, "#63bcb6", "#479ac2")),
    dynamic("plants", "Plants", light=Seed(190, 0.40, "#a33566", "#0c6c8a"), dark=Seed(205, 0.50, "#ef6f8e", "#a98bd8")),
    dynamic("tokyo-street", "Tokyo Street", light=Seed(25, 0.50, "#8a4a26", "#9a5a68"),
            dark=Seed(216, 0.65, "#6f9fe0", "#c8a6c0")),
    dynamic("village", "Village", light=Seed(45, 0.35, "#5b6b1c", "#8a5a20"), dark=Seed(195, 0.40, "#a8d86a", "#5fb0e0")),
    # --- surfd's own colourway (the other three, Tide, Driftwood and Kelp, are written by hand) ---
    Spec("dusk", "Dusk", "Violet dusk; uses the Dusk colourway wallpapers.",
         dark=Seed(255, 0.45, "#b9a3f0", "#8a9cf0"), light=Seed(260, 0.40, "#5a3fa8", "#3f4fb0"),
         picture={"dark": "dusk-dark-3840x2160", "light": "dusk-light-3840x2160"}),
]


def hls(h: float, s: float, light: float) -> str:
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, max(0.0, min(1.0, light)), max(0.0, min(1.0, s)))
    return color.from_rgb(r * 255, g * 255, b * 255)


def parts(c: str) -> tuple[float, float, float]:
    r, g, b = color.to_rgb(c)
    h, light, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return h * 360, s, light


def nudge(c: str, ok, dark: bool) -> str:
    """Lighten (dark style) or darken (light style) c in small steps until ok(c)."""
    h, s, light = parts(c)
    step = 0.01 if dark else -0.01
    while not ok(c) and 0.0 < light < 1.0:
        light += step
        c = hls(h, s, light)
    return c


def readable_text(c: str) -> float:
    return color.contrast(color.readable_on(c, dark="#111111", light="#ffffff"), c)


def palette(seed: Seed, dark: bool) -> dict[str, object]:
    h = seed.hue
    if dark:
        bg = hls(h, min(seed.sat, 0.45), 0.085)
        surface = hls(h, min(seed.sat, 0.40), 0.12)
        surface_alt = hls(h, min(seed.sat, 0.35), 0.19)
        text = hls(h, 0.25, 0.91)
        muted = hls(h, 0.15, 0.66)
        status = {"urgent": hls(358, 0.75, 0.70), "warning": hls(40, 0.85, 0.70), "success": hls(110, 0.50, 0.68)}
        ansi = [(0, 0.70, 0.66), (110, 0.45, 0.62), (43, 0.75, 0.66), (210, 0.65, 0.68), (290, 0.50, 0.72),
                (178, 0.50, 0.62)]
        term0, term7, term8, term15 = hls(h, 0.30, 0.17), hls(h, 0.15, 0.80), hls(h, 0.20, 0.38), hls(h, 0.20, 0.96)
        bright = 0.10
    else:
        bg = hls(h, min(seed.sat, 0.35), 0.945)
        surface = hls(h, min(seed.sat, 0.30), 0.985)
        surface_alt = hls(h, min(seed.sat, 0.30), 0.89)
        text = hls(h, 0.35, 0.13)
        muted = hls(h, 0.18, 0.38)
        status = {"urgent": hls(0, 0.60, 0.42), "warning": hls(36, 0.85, 0.32), "success": hls(115, 0.50, 0.30)}
        ansi = [(0, 0.60, 0.42), (115, 0.50, 0.32), (40, 0.80, 0.33), (210, 0.60, 0.40), (290, 0.40, 0.45),
                (178, 0.60, 0.32)]
        term0, term7, term8, term15 = hls(h, 0.30, 0.15), hls(h, 0.12, 0.80), hls(h, 0.12, 0.42), hls(h, 0.30, 0.985)
        bright = 0.08

    def fits(min_bg: float):
        return lambda c: color.contrast(c, bg) >= min_bg

    muted = nudge(muted, lambda c: color.contrast(c, surface) >= 4.6, dark)
    accent = nudge(seed.accent, lambda c: color.contrast(c, bg) >= 3.2 and readable_text(c) >= 4.6, dark)
    accent2 = nudge(seed.accent2, fits(3.2), dark)
    status = {k: nudge(v, fits(3.2), dark) for k, v in status.items()}
    normal = [nudge(color.mix(hls(*a), accent, 0.12), fits(3.2), dark) for a in ansi]
    brights = [hls(hh, ss + 0.1, ll + (bright if dark else -bright)) for hh, ss, ll in (parts(c) for c in normal)]
    return {
        "background": bg, "surface": surface, "surface_alt": surface_alt, "text": text, "text_muted": muted,
        "accent": accent, "accent2": accent2, **status,
        "icon_theme": "Papirus-Dark" if dark else "Papirus-Light",
        "terminal": [term0, *normal, term7, term8, *brights, term15],
    }


def toml(spec: Spec) -> str:
    out = [f"# {spec.title} — a surfd theme pack, written by theme/tools/make_wallpaper_themes.py. "
           "Format: docs/theme-making.md", "",
           "[meta]", f'name = "{spec.title}"', f'description = "{spec.about}"',
           'author = "surfd contributors"', 'license = "CC-BY-SA-4.0"', 'version = "1.0"', "",
           "[cursor]", 'theme = "breeze_cursors"', "size = 24", ""]
    if spec.dynamic:
        out += ["[wallpaper]", f'dynamic = "{spec.dynamic}"   # choosing this theme turns on this dynamic wallpaper', ""]
    for variant in ("dark", "light"):
        seed = getattr(spec, variant)
        if seed is None:
            continue
        pal = palette(seed, variant == "dark")
        out.append(f"[{variant}]")
        for key in ("background", "surface", "surface_alt", "text", "text_muted", "accent", "accent2",
                    "urgent", "warning", "success"):
            out.append(f'{key:<11} = "{pal[key]}"')
        out.append(f'icon_theme  = "{pal["icon_theme"]}"')
        if spec.picture and variant in spec.picture:
            out.append(f'wallpaper   = "{spec.picture[variant]}"   # a picture from the wallpaper gallery')
        out.append("# ANSI colours 0-7, then bright 8-15")
        out.append("terminal = [")
        out += [f'  "{c}",' for c in pal["terminal"]]  # type: ignore[union-attr]
        out += ["]", ""]
    return "\n".join(out).rstrip() + "\n"


LICENSE = """{name} — a surfd theme pack
Palette © 2026 surfd contributors, CC BY-SA 4.0
https://creativecommons.org/licenses/by-sa/4.0/
The palette was picked from a wallpaper that ships with surfd; the picture itself is not part of
this theme pack. See wallpapers/third-party/CREDITS.md in the surfd repository for its artist and terms.
"""


def main() -> int:
    for spec in SPECS:
        home = ROOT / "themes" if spec.name == "dusk" else ROOT.parent / "wallpapers" / "third-party" / "themes"
        d = home / spec.name
        d.mkdir(parents=True, exist_ok=True)
        (d / "theme.toml").write_text(toml(spec), encoding="utf-8")
        (d / "LICENSE").write_text(LICENSE.format(name=spec.name), encoding="utf-8")
    print(f"wrote {len(SPECS)} themes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
