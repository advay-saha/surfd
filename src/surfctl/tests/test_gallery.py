"""Still-wallpaper gallery: discovery, names, `surfctl wallpaper set NAME`; every shipped set is complete."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from surfd import cli, config, dynwall, gallery, paths, themes

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
    shutil.copy(REPO / "wallpapers" / "third-party" / "static" / "ogarart-red-cave.jpg", system / "static")
    (system / "static" / ".hidden.jpg").write_bytes(b"x")
    (system / "static" / "notes.txt").write_text("not a picture")
    mine = paths.data_home() / "surfd" / "wallpapers" / "static" / "holiday"
    mine.mkdir(parents=True)
    shutil.copy(REPO / "wallpapers" / "third-party" / "static" / "wheazzy-blue-mountains.jpg", mine / "beach_day.jpg")
    return system


@pytest.mark.parametrize("name,group,title", [
    ("tide-dark-3840x2160.jpg", "surfd", "Tide, dark (3840×2160)"),
    ("dusk-light-5120x1440.jpg", "surfd", "Dusk, light (5120×1440)"),
    ("mklgustafsson-small-memory.png", "more", "Small memory (mklgustafsson)"),
    ("lee_zudarts-study.jpg", "more", "Study (lee_zudarts)"),
    ("pixabay-wave-and-surfer.jpg", "more", "Wave and surfer (pixabay)"),
    ("wallpaper.jpg", "more", "Wallpaper"),
    ("beach_day.jpg", "yours", "Beach day"),
])
def test_titles(name: str, group: str, title: str) -> None:
    assert gallery.title_for(Path(name), group) == title


def test_discover_orders_groups_and_skips_non_images(pictures: Path) -> None:
    pics = gallery.discover()
    assert [p.group for p in pics] == ["yours", "surfd", "surfd", "more"]
    assert [p.name for p in pics] == ["beach_day", "tide-dark-3840x2160", "tide-light-3840x2160", "ogarart-red-cave"]
    assert gallery.find("OGARART-red-cave.jpg") is not None and gallery.find("nope") is None


def test_set_by_name_and_list(pictures: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("wallpaper", "set", "tide-dark-3840x2160", "--no-reload") == 0
    assert config.load()["wallpaper"]["path"] == str(pictures / "surfd" / "tide" / "tide-dark-3840x2160.jpg")
    assert run("wallpaper", "set", "ghost", "--no-reload") == 1
    assert "wallpaper list" in capsys.readouterr().err
    assert run("wallpaper", "list") == 0
    out = capsys.readouterr().out
    assert "More wallpapers" in out and "ogarart-red-cave" in out and "Beach day" in out


def test_no_gallery_is_fine(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert gallery.discover() == []
    assert run("wallpaper", "list") == 0


@pytest.mark.parametrize("folder", sorted(p.name for p in (REPO / "wallpapers" / "third-party" / "dynamic").iterdir()))
def test_every_shipped_dynamic_set_is_complete(folder: str) -> None:
    """All dynamic sets are packaged now, so each must load with every frame present."""
    dset = dynwall.load(REPO / "wallpapers" / "third-party" / "dynamic" / folder)
    assert dset.frames and all(f.file.is_file() for f in dset.frames)
    assert dset.light.is_file() and dset.dark.is_file()


# --------------------------------------------------- themes and their wallpapers --

@pytest.fixture()
def full(env: Path) -> Path:
    """Every wallpaper installed, as surfd-theme and surfd-wallpapers lay them out."""
    system = paths.system_dir() / "wallpapers"
    for c in ("tide", "driftwood", "kelp", "dusk"):
        shutil.copytree(REPO / "wallpapers" / "generated" / c, system / "surfd" / c)
    shutil.copytree(REPO / "wallpapers" / "third-party" / "static", system / "static")
    shutil.copytree(REPO / "wallpapers" / "third-party" / "dynamic", system / "dynamic", dirs_exist_ok=True)
    return system


def test_every_theme_finds_its_wallpaper(full: Path) -> None:
    found, broken = themes.discover()
    assert broken == []
    for t in found:
        assert not t.problems, (t.name, t.problems)
        for v in t.variants:
            wp = t.wallpaper(v)
            assert wp is not None and wp.is_file(), (t.name, v)
            assert wp.is_relative_to(full), (t.name, v)  # the gallery's pictures, not files in the theme


def test_picture_theme_brings_its_picture(full: Path) -> None:
    assert run("theme", "set", "red-cave", "--no-reload") == 0
    cfg = config.load()
    assert cfg["theme"]["name"] == "red-cave" and cfg["wallpaper"]["dynamic"] == "" and cfg["wallpaper"]["path"] == ""
    assert themes.find("red-cave").wallpaper("dark") == full / "static" / "ogarart-red-cave.jpg"
    # a picture theme in the other style keeps the picture, with the one palette it has
    assert themes.find("red-cave").palette("light").variant == "dark"


def test_dynamic_theme_turns_on_its_set(full: Path) -> None:
    assert run("wallpaper", "set", "ogarart-fortress", "--no-reload") == 0
    assert run("theme", "set", "tokyo-street", "--variant", "light", "--no-reload") == 0
    cfg = config.load()
    assert cfg["wallpaper"]["dynamic"] == "tokyo-street" and cfg["wallpaper"]["path"] == ""
    t = themes.find("tokyo-street")
    assert set(t.variants) == {"dark", "light"}
    assert t.wallpaper("light") == dynwall.find("tokyo-street").light
    assert t.wallpaper("dark") == dynwall.find("tokyo-street").dark


def test_keep_wallpaper(full: Path) -> None:
    assert run("wallpaper", "set", "ogarart-fortress", "--no-reload") == 0
    assert run("theme", "set", "plants", "--keep-wallpaper", "--no-reload") == 0
    cfg = config.load()
    assert cfg["theme"]["name"] == "plants" and cfg["wallpaper"]["path"].endswith("ogarart-fortress.jpg")
    assert themes.selection("tide") == {"theme.name": "tide", "wallpaper.path": "", "wallpaper.dynamic": ""}


def test_theme_with_missing_picture_or_set_is_flagged(env: Path) -> None:
    d = paths.user_themes_dir() / "lost"
    d.mkdir(parents=True)
    text = (REPO / "theme" / "themes" / "dusk" / "theme.toml").read_text()
    (d / "theme.toml").write_text(text.replace("dusk-dark-3840x2160", "no-such-picture") +
                                  '\n[wallpaper]\ndynamic = "no-such-set"\n')
    t = themes.find("lost")
    assert any("no-such-picture" in p for p in t.problems) and any("no-such-set" in p for p in t.problems)
