"""Filesystem locations. Everything is overridable for tests and packaging.

System data (read-only, shipped by RPMs):
    $SURFD_SYSTEM_DIR            default /usr/share/surfd
        defaults/surfd.toml      the default configuration
        themes/<name>/           system theme packs
        wallpapers/dynamic/<name>/   system dynamic (time-of-day) wallpaper sets
User data (XDG):
    ~/.config/surfd/surfd.toml   the user's configuration
    ~/.local/share/surfd/themes  user theme packs (drop a folder here)
    ~/.local/share/surfd/wallpapers/dynamic  user dynamic wallpaper sets
    ~/.local/state/surfd/        generated configs, backups
"""

from __future__ import annotations

import os
from pathlib import Path


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var, "")
    if value and os.path.isabs(value):
        return Path(value)
    return Path.home() / fallback


def system_dir() -> Path:
    return Path(os.environ.get("SURFD_SYSTEM_DIR", "/usr/share/surfd"))


def system_defaults() -> Path:
    return system_dir() / "defaults" / "surfd.toml"


def system_themes_dir() -> Path:
    return system_dir() / "themes"


def system_wallpapers_dir() -> Path:
    return system_dir() / "wallpapers" / "dynamic"


def config_home() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config")


def data_home() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share")


def state_home() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state")


def user_config() -> Path:
    return config_home() / "surfd" / "surfd.toml"


def user_config_dir() -> Path:
    return config_home() / "surfd"


def user_themes_dir() -> Path:
    return data_home() / "surfd" / "themes"


def user_wallpapers_dir() -> Path:
    return data_home() / "surfd" / "wallpapers" / "dynamic"


def generated_dir() -> Path:
    return state_home() / "surfd" / "generated"


def backups_dir() -> Path:
    return state_home() / "surfd" / "backups"


def theme_dirs() -> list[Path]:
    """Theme search path, highest priority first (user overrides system)."""
    return [user_themes_dir(), system_themes_dir()]
