"""Still wallpapers that come with surfd, or that you collect, for `surfctl wallpaper list` and Surf Settings.

    ~/.local/share/surfd/wallpapers/static/          your own collection (any folder layout)
    /usr/share/surfd/wallpapers/surfd/<colourway>/   surfd's own gradient wallpapers (Tide, Driftwood, Kelp, Dusk)
    /usr/share/surfd/wallpapers/static/              more wallpapers by other artists (see their CREDITS.md)

Choosing one sets `wallpaper.path`, which wins over the dynamic wallpaper. Dynamic (time-of-day)
sets live next to these in wallpapers/dynamic and are handled by dynwall.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import paths

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
GROUPS = {"yours": "Yours", "surfd": "surfd", "more": "More wallpapers"}
_SIZE = re.compile(r"-(\d{3,5})x(\d{3,5})$")


@dataclass(frozen=True)
class Picture:
    title: str
    path: Path
    group: str  # a key of GROUPS

    @property
    def name(self) -> str:
        """What `surfctl wallpaper set NAME` accepts: the file name without its extension."""
        return self.path.stem


def gallery_dirs() -> list[tuple[str, Path]]:
    return [
        ("yours", paths.data_home() / "surfd" / "wallpapers" / "static"),
        ("surfd", paths.system_dir() / "wallpapers" / "surfd"),
        ("more", paths.system_dir() / "wallpapers" / "static"),
    ]


def title_for(path: Path, group: str) -> str:
    """'tide-dark-3840x2160' -> 'Tide, dark (3840 by 2160, with a multiplication sign)'; 'small-memory' -> 'Small memory'."""
    stem = path.stem
    size = ""
    m = _SIZE.search(stem)
    if m:
        size = f" ({m.group(1)}×{m.group(2)})"
        stem = stem[: m.start()]
    words = re.split(r"[-_ ]+", stem.strip("-_ "))
    if group == "surfd" and len(words) == 2 and words[1] in ("dark", "light"):
        return f"{words[0].capitalize()}, {words[1]}{size}"
    text = " ".join(w for w in words if w)
    return (text[:1].upper() + text[1:] if text else path.name) + size


def discover() -> list[Picture]:
    """Every still wallpaper, yours first, then surfd's own, then the rest; sorted by title within each."""
    found: list[Picture] = []
    for group, folder in gallery_dirs():
        if not folder.is_dir():
            continue
        pics = [p for p in folder.rglob("*")
                if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
                and not any(part.startswith(".") for part in p.relative_to(folder).parts)]
        found += sorted((Picture(title_for(p, group), p, group) for p in pics), key=lambda x: (x.title.lower(), str(x.path)))
    return found


def find(name: str) -> Picture | None:
    """A picture by file name (with or without extension), e.g. 'tide-dark-3840x2160'."""
    key = name.strip().lower()
    for pic in discover():
        if key in (pic.path.stem.lower(), pic.path.name.lower()):
            return pic
    return None
