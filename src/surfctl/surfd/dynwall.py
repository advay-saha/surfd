"""Dynamic wallpapers: a set of frames that follows the time of day, the theme's light/dark style, or stays on one frame.

A set is a folder (in ~/.local/share/surfd/wallpapers/dynamic or /usr/share/surfd/wallpapers/dynamic) with
frames and a wallpaper.toml (see docs/dynamic-wallpapers.md; tools/wallpapers/heic2surfd.py makes one from an
Apple dynamic HEIC):

    [wallpaper]
    name  = "Low-poly mountain"
    kind  = "time"              # "time" (clock) or "solar" (sun position)
    light = "02-noon.jpg"       # brightest frame
    dark  = "00-night.jpg"      # darkest frame

    [[frame]]
    at = "06:00"                # kind = "time"; "solar" uses altitude = -10.0 and azimuth = 109.0 (degrees)
    file = "01-morning.jpg"

The three ways to follow a set are `[wallpaper] sync` in surfd.toml:
    auto   follow the time of day (the clock, or the sun for "solar" sets)
    theme  the lightest frame in the light style, the darkest in the dark style
    frame  one fixed frame, named by `[wallpaper] frame`
"""

from __future__ import annotations

import math
import re
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import paths

DEFAULT_SET = "low-poly-mountain"
SYNC_MODES = ("auto", "theme", "frame")
DEFAULT_LOCATION_LATITUDE = 30.0  # used only until the user sets `[wallpaper] location`
_TIME = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class DynError(ValueError):
    """A dynamic wallpaper set or setting that cannot be used."""


@dataclass(frozen=True)
class Frame:
    file: Path
    at: int | None = None  # minutes after midnight (kind "time")
    altitude: float | None = None  # degrees (kind "solar")
    azimuth: float | None = None


@dataclass
class DynSet:
    name: str  # folder name
    path: Path
    title: str
    kind: str  # "time" | "solar"
    light: Path
    dark: Path
    frames: list[Frame] = field(default_factory=list)


# ------------------------------------------------------------------- sets ---

def set_dirs() -> list[Path]:
    """Search path, highest priority first (a user set overrides a system set of the same name)."""
    return [paths.user_wallpapers_dir(), paths.system_wallpapers_dir()]


def load(folder: Path) -> DynSet:
    try:
        data = tomllib.loads((folder / "wallpaper.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise DynError(f"{folder.name}: cannot read wallpaper.toml ({e})") from e
    meta: dict[str, Any] = data.get("wallpaper", {})
    kind = meta.get("kind", "time")
    if kind not in ("time", "solar"):
        raise DynError(f"{folder.name}: kind must be \"time\" or \"solar\", not {kind!r}")
    frames: list[Frame] = []
    for i, raw in enumerate(data.get("frame", [])):
        where = f"{folder.name}: frame {i + 1}"
        f = folder / str(raw.get("file", ""))
        if not raw.get("file") or not f.is_file():
            raise DynError(f"{where}: file {raw.get('file')!r} not found")
        if kind == "time":
            m = _TIME.match(str(raw.get("at", "")))
            if not m:
                raise DynError(f"{where}: `at` must look like \"06:30\"")
            frames.append(Frame(f, at=int(m[1]) * 60 + int(m[2])))
        else:
            try:
                frames.append(Frame(f, altitude=float(raw["altitude"]), azimuth=float(raw["azimuth"])))
            except (KeyError, TypeError, ValueError):
                raise DynError(f"{where}: needs numeric altitude and azimuth") from None
    if len(frames) < 1:
        raise DynError(f"{folder.name}: no [[frame]] entries")
    by_name = {f.file.name: f.file for f in frames}
    ends = {}
    for key in ("light", "dark"):
        if meta.get(key) not in by_name:
            raise DynError(f"{folder.name}: `{key}` must name one of the frames")
        ends[key] = by_name[meta[key]]
    return DynSet(name=folder.name, path=folder, title=str(meta.get("name", folder.name)), kind=kind,
                  light=ends["light"], dark=ends["dark"], frames=frames)


def discover(problems: list[str] | None = None) -> dict[str, DynSet]:
    """All usable sets by folder name. Broken sets are skipped and described in `problems`."""
    found: dict[str, DynSet] = {}
    for base in set_dirs():
        if not base.is_dir():
            continue
        for d in sorted(base.iterdir()):
            if d.name in found or not (d / "wallpaper.toml").is_file():
                continue
            try:
                found[d.name] = load(d)
            except DynError as e:
                if problems is not None:
                    problems.append(str(e))
    return found


def find(name: str) -> DynSet | None:
    return discover().get(name) if name else None


# -------------------------------------------------------------- sun / clock ---

def now() -> datetime:
    """The current local time (a function so tests can replace it)."""
    return datetime.now().astimezone()


def parse_location(text: str) -> tuple[float, float] | None:
    """"" -> None (guess from the time zone); "35.2, 33.4" -> (35.2, 33.4)."""
    text = (text or "").strip()
    if not text or text == "auto":
        return None
    try:
        lat_s, lon_s = (p.strip() for p in text.split(","))
        lat, lon = float(lat_s), float(lon_s)
    except ValueError:
        raise DynError("location must be empty or \"latitude, longitude\", e.g. \"35.2, 33.4\"") from None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise DynError("location out of range: latitude -90..90, longitude -180..180")
    return lat, lon


def sun_position(when: datetime, lat: float, lon: float) -> tuple[float, float]:
    """Approximate solar altitude and azimuth in degrees (NOAA formulas); `when` must be timezone-aware."""
    jd = when.timestamp() / 86400.0 + 2440587.5
    n = jd - 2451545.0
    mean_lon = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(mean_lon + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    dec = math.asin(math.sin(eps) * math.sin(lam))
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    gmst = (280.46061837 + 360.98564736629 * n) % 360
    ha = math.radians((gmst + lon) % 360) - ra
    la = math.radians(lat)
    alt = math.asin(math.sin(la) * math.sin(dec) + math.cos(la) * math.cos(dec) * math.cos(ha))
    az = math.atan2(-math.sin(ha) * math.cos(dec), math.cos(la) * math.sin(dec) - math.sin(la) * math.cos(dec) * math.cos(ha))
    return math.degrees(alt), math.degrees(az) % 360


def _location(text: str, when: datetime) -> tuple[float, float]:
    """The configured place, else a rough guess: longitude from the UTC offset, a mid latitude."""
    loc = parse_location(text)
    if loc:
        return loc
    return DEFAULT_LOCATION_LATITUDE, (when.utcoffset() or timedelta(0)).total_seconds() / 3600 * 15.0


# ---------------------------------------------------------------- choosing ---

def _by_time(dset: DynSet, when: datetime) -> Frame:
    minute = when.hour * 60 + when.minute
    ordered = sorted(dset.frames, key=lambda f: f.at or 0)
    current = ordered[-1]  # before the first frame of the day: still the last one of yesterday
    for f in ordered:
        if (f.at or 0) <= minute:
            current = f
    return current


def _by_sun(dset: DynSet, when: datetime, location: str) -> Frame:
    alt, az = sun_position(when, *_location(location, when))
    if az > 180:  # the frames usually cover one half of the sky; fold the afternoon onto the morning
        az = 360 - az
    return min(dset.frames, key=lambda f: ((f.altitude or 0) - alt) ** 2 + (0.25 * ((f.azimuth or 0) - az)) ** 2)


def named_frame(dset: DynSet, key: str) -> Path | None:
    """A frame picked by position ("2") or by part of its file name ("noon"); None if not exactly one."""
    key = (key or "").strip()
    files = [f.file for f in dset.frames]
    if key.isdigit() and int(key) < len(files):
        return files[int(key)]
    hits = [f for f in files if key and key in f.name]
    return hits[0] if len(hits) == 1 else None


def choose(dset: DynSet, sync: str, variant: str, when: datetime | None = None, *,
           frame: str = "", location: str = "") -> Path:
    """The image to show for this set, sync mode and moment."""
    when = when or now()
    if sync == "theme":
        return dset.light if variant == "light" else dset.dark
    if sync == "frame":
        return named_frame(dset, frame) or (dset.light if variant == "light" else dset.dark)
    pick = _by_sun(dset, when, location) if dset.kind == "solar" else _by_time(dset, when)
    return pick.file


def seconds_to_next_change(dset: DynSet, when: datetime | None = None) -> int:
    """How long the clock-based frame stays valid (capped at 5 minutes; sun sets re-check at that pace)."""
    when = when or now()
    cap = 300
    if dset.kind != "time":
        return cap
    minute = when.hour * 60 + when.minute
    later = [f.at for f in dset.frames if f.at is not None and f.at > minute]
    nxt = min(later) if later else min(f.at or 0 for f in dset.frames) + 1440
    return max(1, min(cap, (nxt - minute) * 60 - when.second))


def link_path() -> Path:
    """A symlink that always points at the frame on screen (read by the lock screen)."""
    return paths.generated_dir() / "wallpaper-current"


def update_link(target: Path) -> None:
    """Point link_path() at `target` (atomically, so the lock screen never sees a missing file)."""
    link = link_path()
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = link.with_name(link.name + ".new")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(target)
    tmp.replace(link)


def current(cfg_get: Any, variant: str, when: datetime | None = None) -> tuple[DynSet, Path] | None:
    """The dynamic set and frame that the configuration selects right now, or None when it selects none.

    `cfg_get` is a function taking a dotted key such as "wallpaper.dynamic".
    """
    name = cfg_get("wallpaper.dynamic") or ""
    dset = find(name)
    if dset is None:
        return None
    path = choose(dset, cfg_get("wallpaper.sync") or "auto", variant, when,
                  frame=cfg_get("wallpaper.frame") or "", location=cfg_get("wallpaper.location") or "")
    return dset, path
