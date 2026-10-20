"""Test fixtures: an isolated HOME and a fake /usr/share/surfd built from the repo."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src" / "surfctl"))


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    system = tmp_path / "usr-share-surfd"
    (system / "defaults").mkdir(parents=True)
    shutil.copy(REPO / "config" / "defaults" / "surfd.toml", system / "defaults" / "surfd.toml")
    shutil.copytree(REPO / "theme" / "themes", system / "themes")
    # the default dynamic wallpaper, as the packages install it
    shutil.copytree(REPO / "wallpapers" / "third-party" / "dynamic" / "low-poly-mountain",
                    system / "wallpapers" / "dynamic" / "low-poly-mountain")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("SURFD_SYSTEM_DIR", str(system))
    monkeypatch.setenv("SURFD_LIBEXEC", str(REPO / "src" / "session" / "libexec"))
    monkeypatch.setenv("HOME", str(home))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "SWAYSOCK", "WAYLAND_DISPLAY",
                "DBUS_SESSION_BUS_ADDRESS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")
    return home


@pytest.fixture()
def repo() -> Path:
    return REPO
