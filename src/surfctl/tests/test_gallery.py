"""Still-wallpaper gallery: discovery, names, `surfctl wallpaper set NAME`; every shipped set is complete."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from surfd import cli, config, dynwall, gallery, paths

REPO = Path(__file__).resolve().parents[3]


def run(*argv: str) -> int:
    return cli.main(list(argv))


@pytest.fixture()
def pictures(env: Path) -> Path:
    """A small gallery laid out as the packages install it, plus one picture of your own."""
    system = paths.system_dir() / "wallpapers"
    tide = system / "surfd" / "tide"
    tide.mkdir(parents=True)
    for name in ("tide-dark-3840x2160.jpg", "tide-light-3840x2160.jpg"):
        shutil.copy(REPO / "wallpapers" / "generated" / "tide" / name, tide / name)
    (system / "static").mkdir(parents=True)
    shutil.copy(REPO / "wallpapers" / "third-party" / "static" / "wallpaper-01.jpg", system / "static")
    (system / "static" / ".hidden.jpg").write_bytes(b"x")
    (system / "static" / "notes.txt").write_text("not a picture")
    mine = paths.data_home() / "surfd" / "wallpapers" / "static" / "holiday"
    mine.mkdir(parents=True)
    shutil.copy(REPO / "wallpapers" / "third-party" / "static" / "wallpaper-02.jpg", mine / "beach_day.jpg")
    return system


@pytest.mark.parametrize("name,group,title", [
    ("tide-dark-3840x2160.jpg", "surfd", "Tide, dark (3840×2160)"),
    ("dusk-light-5120x1440.jpg", "surfd", "Dusk, light (5120×1440)"),
    ("mklgustafsson-small-memory.png", "more", "Mklgustafsson small memory"),
    ("wallpaper-07.jpg", "more", "Wallpaper 07"),
    ("beach_day.jpg", "yours", "Beach day"),
])
def test_titles(name: str, group: str, title: str) -> None:
    assert gallery.title_for(Path(name), group) == title


def test_discover_orders_groups_and_skips_non_images(pictures: Path) -> None:
    pics = gallery.discover()
    assert [p.group for p in pics] == ["yours", "surfd", "surfd", "more"]
    assert [p.name for p in pics] == ["beach_day", "tide-dark-3840x2160", "tide-light-3840x2160", "wallpaper-01"]
    assert gallery.find("WALLPAPER-01.jpg") is not None and gallery.find("nope") is None


def test_set_by_name_and_list(pictures: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("wallpaper", "set", "tide-dark-3840x2160", "--no-reload") == 0
    assert config.load()["wallpaper"]["path"] == str(pictures / "surfd" / "tide" / "tide-dark-3840x2160.jpg")
    assert run("wallpaper", "set", "ghost", "--no-reload") == 1
    assert "wallpaper list" in capsys.readouterr().err
    assert run("wallpaper", "list") == 0
    out = capsys.readouterr().out
    assert "More wallpapers" in out and "wallpaper-01" in out and "Beach day" in out


def test_no_gallery_is_fine(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gallery.discover() == []
    assert run("wallpaper", "list") == 0


@pytest.mark.parametrize("folder", sorted(p.name for p in (REPO / "wallpapers" / "third-party" / "dynamic").iterdir()))
def test_every_shipped_dynamic_set_is_complete(folder: str) -> None:
    """All dynamic sets are packaged now, so each must load with every frame present."""
    dset = dynwall.load(REPO / "wallpapers" / "third-party" / "dynamic" / folder)
    assert dset.frames and all(f.file.is_file() for f in dset.frames)
    assert dset.light.is_file() and dset.dark.is_file()
