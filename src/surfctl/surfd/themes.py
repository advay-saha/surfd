"""Theme packs: a folder with a theme.toml and optional wallpapers/extras.

    mytheme/
      theme.toml          palette for [dark] and [light], metadata
      wallpapers/         images referenced from theme.toml (optional)
      waybar.css          appended to the generated bar style (optional)
      gtk.css             appended to the generated GTK 3/4 style (optional)
      LICENSE             licence for the artwork (recommended)

Drop the folder in ~/.local/share/surfd/themes/ (or use
`surfctl theme install`) and select it with `surfctl theme set mytheme`.
See docs/theme-making.md.
"""

from __future__ import annotations

import os
import re
import shutil
import tarfile
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import color, paths

COLOR_KEYS = (
    "background",  # desktop / window background
    "surface",  # bar, panels, notifications
    "surface_alt",  # hovered / selected surfaces
    "text",
    "text_muted",
    "accent",
    "urgent",
    "warning",
    "success",
)
VARIANTS = ("dark", "light")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")


class ThemeError(Exception):
    pass


@dataclass(frozen=True)
class Palette:
    variant: str
    background: str
    surface: str
    surface_alt: str
    text: str
    text_muted: str
    accent: str
    urgent: str
    warning: str
    success: str
    terminal: tuple[str, ...]
    accent_text: str = ""  # text drawn on top of accent
    border: str = ""  # inactive window border
    icon_theme: str = "Papirus"

    @property
    def is_dark(self) -> bool:
        return self.variant == "dark"


@dataclass
class Theme:
    name: str
    path: Path
    meta: dict[str, Any]
    variants: dict[str, dict[str, Any]]
    cursor_theme: str = "breeze_cursors"
    cursor_size: int = 24
    problems: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return str(self.meta.get("name", self.name))

    @property
    def is_system(self) -> bool:
        try:
            self.path.relative_to(paths.system_themes_dir())
            return True
        except ValueError:
            return False

    def wallpaper(self, variant: str) -> Path | None:
        rel = self.variants.get(variant, {}).get("wallpaper")
        if not rel:
            return None
        p = (self.path / rel).resolve()
        # PNG renders are produced at package build time from the SVG
        # sources; fall back to the other format if only one exists.
        if not p.exists():
            for alt in (p.with_suffix(".jpg"), p.with_suffix(".png"), p.with_suffix(".svg")):
                if alt.exists():
                    return alt
            return None
        return p

    def extra(self, filename: str) -> str:
        f = self.path / filename
        return f.read_text(encoding="utf-8") if f.is_file() else ""

    def palette(self, variant: str, accent_override: str = "") -> Palette:
        if variant not in self.variants:
            variant = next(iter(self.variants))
        v = self.variants[variant]
        cols = {k: color.normalize(v[k]) for k in COLOR_KEYS}
        if accent_override:
            cols["accent"] = color.normalize(accent_override)
        term = tuple(color.normalize(c) for c in v["terminal"])
        return Palette(
            variant=variant,
            terminal=term,
            accent_text=color.readable_on(cols["accent"], dark="#111111", light="#ffffff"),
            border=color.mix(cols["surface"], cols["text"], 0.18),
            icon_theme=str(v.get("icon_theme", "Papirus-Dark" if variant == "dark" else "Papirus")),
            **cols,
        )


def _validate_variant(name: str, data: Any) -> list[str]:
    errs: list[str] = []
    if not isinstance(data, dict):
        return [f"[{name}] must be a table"]
    for k in COLOR_KEYS:
        if k not in data:
            errs.append(f"[{name}] missing colour '{k}'")
        elif not color.is_color(data[k]):
            errs.append(f"[{name}] {k} = {data[k]!r} is not a colour")
    term = data.get("terminal")
    if not isinstance(term, list) or len(term) != 16 or not all(color.is_color(c) for c in term):
        errs.append(f"[{name}] terminal must be a list of 16 colours (ANSI 0-15)")
    return errs


def load(path: Path) -> Theme:
    """Load and validate a theme folder. Raises ThemeError if unusable."""
    toml = path / "theme.toml"
    if not toml.is_file():
        raise ThemeError(f"{path}: no theme.toml")
    try:
        with toml.open("rb") as fh:
            data = tomllib.load(fh)
    except tomllib.TOMLDecodeError as e:
        raise ThemeError(f"{toml}: {e}") from None

    name = path.name
    if not NAME_RE.match(name):
        raise ThemeError(f"{path}: folder name must be lowercase letters, digits, '.', '_' or '-'")

    variants = {v: data[v] for v in VARIANTS if v in data}
    if not variants:
        raise ThemeError(f"{toml}: needs a [dark] and/or [light] table")
    errs: list[str] = []
    for v, d in variants.items():
        errs += _validate_variant(v, d)
    if errs:
        raise ThemeError(f"{toml}: " + "; ".join(errs))

    cursor = data.get("cursor", {})
    theme = Theme(
        name=name,
        path=path,
        meta=data.get("meta", {}),
        variants=variants,
        cursor_theme=str(cursor.get("theme", "breeze_cursors")),
        cursor_size=int(cursor.get("size", 24)),
    )
    for v, data in variants.items():
        if data.get("wallpaper") and theme.wallpaper(v) is None:
            theme.problems.append(f"[{v}] wallpaper '{data['wallpaper']}' not found")
    if "license" not in theme.meta:
        theme.problems.append("[meta] has no license; add one so others can share it")
    return theme


def find(name: str) -> Theme | None:
    for d in paths.theme_dirs():
        candidate = d / name
        if (candidate / "theme.toml").is_file():
            try:
                return load(candidate)
            except ThemeError:
                return None
    return None


def discover() -> tuple[list[Theme], list[str]]:
    """All usable themes (user ones shadow system ones) and load errors."""
    found: dict[str, Theme] = {}
    problems: list[str] = []
    for d in paths.theme_dirs():
        if not d.is_dir():
            continue
        for sub in sorted(d.iterdir()):
            if sub.name in found or not (sub / "theme.toml").is_file():
                continue
            try:
                found[sub.name] = load(sub)
            except ThemeError as e:
                problems.append(str(e))
    return sorted(found.values(), key=lambda t: t.name), problems


def names() -> list[str]:
    return [t.name for t in discover()[0]]


def resolve(cfg: dict[str, Any]) -> tuple[Theme, Palette]:
    """The theme and palette selected by the configuration."""
    name = cfg["theme"]["name"]
    theme = find(name)
    if theme is None:
        raise ThemeError(f"theme '{name}' is not installed or is broken (try `surfctl theme list`)")
    return theme, theme.palette(cfg["theme"]["variant"], cfg["theme"].get("accent", ""))


# --------------------------------------------------------- install / export --

def _safe_members_tar(tf: tarfile.TarFile, dest: Path) -> list[tarfile.TarInfo]:
    out = []
    for m in tf.getmembers():
        target = (dest / m.name).resolve()
        if not str(target).startswith(str(dest.resolve()) + os.sep) and target != dest.resolve():
            raise ThemeError(f"archive entry escapes the theme folder: {m.name}")
        if m.issym() or m.islnk() or m.isdev():
            raise ThemeError(f"archive contains links or devices, refusing: {m.name}")
        out.append(m)
    return out


def _extract(archive: Path, dest: Path) -> None:
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            members = _safe_members_tar(tf, dest)
            tf.extractall(dest, members=members, filter="data")
    elif zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            for n in zf.namelist():
                target = (dest / n).resolve()
                if not str(target).startswith(str(dest.resolve()) + os.sep):
                    raise ThemeError(f"archive entry escapes the theme folder: {n}")
            zf.extractall(dest)
    else:
        raise ThemeError(f"{archive}: not a folder, .tar.* or .zip")


def install(source: Path, *, force: bool = False) -> Theme:
    """Install a theme folder or archive into the user theme directory."""
    source = source.expanduser()
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        if source.is_dir():
            root = source
        else:
            extracted = tmpd / "extracted"
            extracted.mkdir()
            _extract(source, extracted)
            roots = [p for p in extracted.iterdir() if p.is_dir()]
            if (extracted / "theme.toml").is_file():
                # Flat archive: name the theme after the archive file.
                stem = source.name.split(".")[0].removeprefix("surfd-theme-").lower()
                root = tmpd / stem
                extracted.rename(root)
            elif len(roots) == 1 and (roots[0] / "theme.toml").is_file():
                root = roots[0]
            else:
                raise ThemeError(f"{source}: expected theme.toml at the top or in a single folder")
        theme = load(root)  # validate before copying anything
        dest = paths.user_themes_dir() / theme.name
        if dest.exists():
            if not force:
                raise ThemeError(f"theme '{theme.name}' already exists in {dest.parent} (use --force to replace)")
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root, dest)
    return load(dest)


def export(name: str, output: Path) -> Path:
    theme = find(name)
    if theme is None:
        raise ThemeError(f"theme '{name}' not found")
    output = output.expanduser()
    if output.is_dir():
        output = output / f"surfd-theme-{theme.name}.tar.gz"
    with tarfile.open(output, "w:gz") as tf:
        tf.add(theme.path, arcname=theme.name)
    return output


def new(name: str, base: str) -> Path:
    """Copy an existing theme as a starting point for a new one."""
    if not NAME_RE.match(name):
        raise ThemeError("theme names use lowercase letters, digits, '.', '_' or '-'")
    src = find(base)
    if src is None:
        raise ThemeError(f"base theme '{base}' not found")
    dest = paths.user_themes_dir() / name
    if dest.exists():
        raise ThemeError(f"{dest} already exists")
    shutil.copytree(src.path, dest)
    toml = dest / "theme.toml"
    text = toml.read_text(encoding="utf-8")
    text = re.sub(r'(?m)^name = ".*"$', f'name = "{name}"', text, count=1)
    toml.write_text(text, encoding="utf-8")
    return dest
