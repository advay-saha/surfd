"""Dynamic (time-of-day) wallpapers: sets, frame choice, settings, generated config and the updater."""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from PIL import Image

from surfd import cli, config, dynwall, generate, paths, session

SETS = Path(__file__).resolve().parents[3] / "wallpapers" / "third-party" / "dynamic"


def run(*argv: str) -> int:
    return cli.main(list(argv))


def at(hour: int, minute: int = 0, second: int = 0, *, month: int = 10, offset_hours: float = 0.0) -> datetime:
    tz = timezone(timedelta(hours=offset_hours))
    return datetime(2026, month, 20, hour, minute, second, tzinfo=tz)


@pytest.fixture()
def mountain(env: Path) -> dynwall.DynSet:
    found = dynwall.find("low-poly-mountain")
    assert found is not None
    return found


def freeze(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    monkeypatch.setattr(dynwall, "now", lambda: when)


def bg_line(text: str) -> str:
    m = re.search(r"^output \* bg .*$", text, re.M)
    assert m, "no wallpaper line in the Sway config"
    return m.group(0)


# --------------------------------------------------------------- the sets ---

@pytest.mark.parametrize("folder", sorted(p.name for p in SETS.iterdir() if p.is_dir()))
def test_shipped_sets_are_valid(folder: str) -> None:
    dset = dynwall.load(SETS / folder)
    assert dset.kind in ("time", "solar")
    assert len(dset.frames) >= 3
    assert dset.light != dset.dark
    for f in dset.frames:
        assert f.file.is_file()
        with Image.open(f.file) as im:
            assert im.size[0] >= 1600 and im.size[0] / im.size[1] > 1.4  # a wide, usable wallpaper


@pytest.mark.parametrize("folder", sorted(p.name for p in SETS.iterdir() if p.is_dir()))
def test_light_is_brighter_than_dark(folder: str) -> None:
    dset = dynwall.load(SETS / folder)

    def luma(p: Path) -> float:
        with Image.open(p) as im:
            px = im.convert("L").resize((64, 36)).tobytes()
        return sum(px) / len(px)

    assert luma(dset.light) > luma(dset.dark)


def test_user_set_overrides_system_set(env: Path) -> None:
    mine = paths.user_wallpapers_dir() / "low-poly-mountain"
    shutil.copytree(SETS / "low-poly-mountain", mine)
    found = dynwall.find("low-poly-mountain")
    assert found is not None and found.path == mine


def test_broken_set_is_skipped_and_reported(env: Path) -> None:
    bad = paths.user_wallpapers_dir() / "broken"
    bad.mkdir(parents=True)
    (bad / "wallpaper.toml").write_text('[wallpaper]\nkind = "time"\nlight = "a.jpg"\ndark = "b.jpg"\n[[frame]]\nat = "25:00"\nfile = "a.jpg"\n')
    problems: list[str] = []
    sets = dynwall.discover(problems)
    assert "broken" not in sets and "low-poly-mountain" in sets
    assert any("broken" in p for p in problems)


# -------------------------------------------------------- choosing a frame ---

@pytest.mark.parametrize(("hour", "minute", "expected"), [
    (0, 0, "00-night.jpg"), (3, 30, "00-night.jpg"), (5, 59, "00-night.jpg"),
    (6, 0, "01-dawn.jpg"), (11, 59, "01-dawn.jpg"),
    (12, 0, "02-noon.jpg"), (17, 59, "02-noon.jpg"),
    (18, 0, "03-evening.jpg"), (19, 59, "03-evening.jpg"),
    (20, 0, "04-dusk.jpg"), (23, 59, "04-dusk.jpg"),
])
def test_auto_follows_the_clock(mountain: dynwall.DynSet, hour: int, minute: int, expected: str) -> None:
    assert dynwall.choose(mountain, "auto", "dark", at(hour, minute)).name == expected


def test_auto_ignores_the_style(mountain: dynwall.DynSet) -> None:
    assert dynwall.choose(mountain, "auto", "light", at(21)) == dynwall.choose(mountain, "auto", "dark", at(21))


def test_theme_sync_uses_lightest_and_darkest(mountain: dynwall.DynSet) -> None:
    for when in (at(1), at(13), at(21)):  # the clock does not matter
        assert dynwall.choose(mountain, "theme", "light", when) == mountain.light
        assert dynwall.choose(mountain, "theme", "dark", when) == mountain.dark


def test_frame_sync_by_name_by_number_and_fallback(mountain: dynwall.DynSet) -> None:
    assert dynwall.choose(mountain, "frame", "dark", at(1), frame="evening").name == "03-evening.jpg"
    assert dynwall.choose(mountain, "frame", "dark", at(1), frame="1").name == "01-dawn.jpg"
    # an unknown or ambiguous frame falls back to the style's frame instead of failing
    assert dynwall.choose(mountain, "frame", "light", at(1), frame="nope") == mountain.light
    assert dynwall.choose(mountain, "frame", "dark", at(1), frame="0") == mountain.dark
    assert dynwall.named_frame(mountain, "0") is not None and dynwall.named_frame(mountain, "-") is None


def test_seconds_to_next_change(mountain: dynwall.DynSet) -> None:
    assert dynwall.seconds_to_next_change(mountain, at(5, 59, 30)) == 30
    assert dynwall.seconds_to_next_change(mountain, at(19, 59, 50)) == 10
    assert dynwall.seconds_to_next_change(mountain, at(23, 59, 59)) == 1  # wraps to midnight
    assert dynwall.seconds_to_next_change(mountain, at(8)) == 300  # never sleeps longer than 5 minutes


# -------------------------------------------------------------------- sun ---

def test_sun_position_is_sane() -> None:
    alt, _ = dynwall.sun_position(at(12), 0.0, 0.0)  # equator, 12:00 UTC on 20 October: close to overhead
    assert 60 < alt <= 90
    alt, _ = dynwall.sun_position(at(0), 0.0, 0.0)
    assert alt < -50
    alt, az = dynwall.sun_position(at(9, offset_hours=0), 0.0, 0.0)  # morning: sun in the east
    assert 0 < alt < 60 and 45 < az < 135
    _, az = dynwall.sun_position(at(15), 0.0, 0.0)  # afternoon: sun in the west
    assert 225 < az < 315


def test_solar_set_picks_by_altitude() -> None:
    cyprus = dynwall.load(SETS / "cyprus")
    night = dynwall.choose(cyprus, "auto", "dark", at(23, 30, offset_hours=3), location="35.2, 33.4")
    noon = dynwall.choose(cyprus, "auto", "dark", at(12, 30, offset_hours=3), location="35.2, 33.4")
    by_file = {f.file: f for f in cyprus.frames}
    assert (by_file[night].altitude or 0) < -30  # deep night frame
    assert (by_file[noon].altitude or 0) > 10  # a daylight frame


def test_location_is_guessed_from_the_time_zone_when_unset() -> None:
    cyprus = dynwall.load(SETS / "cyprus")
    # no location: longitude comes from the UTC offset, so noon local time is still daylight
    assert (next(f for f in cyprus.frames if f.file == dynwall.choose(cyprus, "auto", "dark", at(12, offset_hours=5.5))).altitude or 0) > 0


@pytest.mark.parametrize(("text", "expected"), [("", None), ("auto", None), ("35.2, 33.4", (35.2, 33.4)), ("-33.9,151.2", (-33.9, 151.2))])
def test_parse_location(text: str, expected: tuple[float, float] | None) -> None:
    assert dynwall.parse_location(text) == expected


@pytest.mark.parametrize("text", ["nowhere", "1,2,3", "91, 0", "0, 181", "a, b"])
def test_parse_location_rejects(text: str) -> None:
    with pytest.raises(dynwall.DynError):
        dynwall.parse_location(text)


# ----------------------------------------------------------- the settings ---

def test_defaults_use_the_mountain_following_the_clock(env: Path) -> None:
    cfg = config.load()["wallpaper"]
    assert cfg["dynamic"] == dynwall.DEFAULT_SET == "low-poly-mountain"
    assert cfg["sync"] == "auto" and cfg["path"] == ""
    assert not [p for p in config.validate(config.load()) if p.level == "error"]


def test_validation_messages(env: Path) -> None:
    cfg = config.load()
    cfg["wallpaper"].update({"location": "nowhere", "dynamic": "ghost"})
    found = {p.key: p for p in config.validate(cfg)}
    assert found["wallpaper.location"].level == "error"
    assert found["wallpaper.dynamic"].level == "warning" and "ghost" in found["wallpaper.dynamic"].message
    cfg["wallpaper"].update({"location": "", "dynamic": "low-poly-mountain", "sync": "frame", "frame": "nope"})
    found = {p.key: p for p in config.validate(cfg)}
    assert found["wallpaper.frame"].level == "warning"


def test_sync_must_be_a_known_mode(env: Path) -> None:
    with pytest.raises(config.ConfigError):
        config.set_values({"wallpaper.sync": "sometimes"})


# --------------------------------------------------------- generated files ---

def test_sway_config_shows_the_current_frame(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, at(13))
    text = generate.sway(generate.build_context())
    assert "low-poly-mountain/02-noon.jpg" in bg_line(text)
    assert re.search(r"^exec_always \S+/surfd-dynwall on$", text, re.M)


def test_theme_style_decides_in_theme_sync(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, at(13))
    config.set_values({"wallpaper.sync": "theme", "theme.variant": "dark"})
    dark = generate.sway(generate.build_context())
    assert "00-night.jpg" in bg_line(dark) and re.search(r"surfd-dynwall off$", dark, re.M)
    config.set_values({"theme.variant": "light"})
    assert "02-noon.jpg" in bg_line(generate.sway(generate.build_context()))


def test_fixed_frame(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, at(2))
    config.set_values({"wallpaper.sync": "frame", "wallpaper.frame": "evening"})
    text = generate.sway(generate.build_context())
    assert "03-evening.jpg" in bg_line(text) and re.search(r"surfd-dynwall off$", text, re.M)


def test_own_image_wins_and_stops_the_updater(env: Path, tmp_path: Path) -> None:
    img = tmp_path / "mine.png"
    Image.new("RGB", (8, 8)).save(img)
    config.set_values({"wallpaper.path": str(img)})
    text = generate.sway(generate.build_context())
    assert str(img) in bg_line(text) and re.search(r"surfd-dynwall off$", text, re.M)


def test_no_dynamic_set_means_the_theme_wallpaper(env: Path) -> None:
    config.set_values({"wallpaper.dynamic": ""})
    ctx = generate.build_context()
    assert ctx.dynamic is None and ctx.wallpaper == ctx.theme.wallpaper(ctx.pal.variant)
    assert re.search(r"surfd-dynwall off$", generate.sway(ctx), re.M)


def test_missing_set_falls_back_to_the_theme(env: Path) -> None:
    config.set_values({"wallpaper.dynamic": "ghost"})
    ctx = generate.build_context()
    assert ctx.dynamic is None and ctx.wallpaper == ctx.theme.wallpaper(ctx.pal.variant)


def test_lock_screen_uses_the_link_only_while_following_the_clock(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    freeze(monkeypatch, at(13))
    ctx = generate.build_context()
    assert f"image={dynwall.link_path()}" in generate.swaylock(ctx)
    generate.write_all(ctx)
    assert dynwall.link_path().is_symlink() and dynwall.link_path().resolve().name == "02-noon.jpg"
    config.set_values({"wallpaper.sync": "theme"})
    assert f"image={dynwall.link_path()}" not in generate.swaylock(generate.build_context())


def test_update_link_replaces_atomically(env: Path, mountain: dynwall.DynSet) -> None:
    for frame in mountain.frames:
        dynwall.update_link(frame.file)
        assert dynwall.link_path().resolve() == frame.file.resolve()
    assert not list(dynwall.link_path().parent.glob("*.new"))


# ------------------------------------------------------------ the commands ---

def test_cli_dynamic_and_sync(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("wallpaper", "dynamic", "ghost") == 1 and "ghost" in capsys.readouterr().err
    assert run("wallpaper", "dynamic", "off") == 0 and config.load()["wallpaper"]["dynamic"] == ""
    assert run("wallpaper", "dynamic", "low-poly-mountain") == 0
    assert run("wallpaper", "sync", "theme") == 0 and config.load()["wallpaper"]["sync"] == "theme"
    assert run("wallpaper", "sync", "frame") == 1  # which frame?
    assert run("wallpaper", "sync", "frame", "nope") == 1
    assert run("wallpaper", "sync", "frame", "noon") == 0
    assert config.load()["wallpaper"]["frame"] == "noon"
    assert run("wallpaper", "sync", "auto") == 0 and config.load()["wallpaper"]["sync"] == "auto"


def test_cli_choosing_a_dynamic_set_replaces_an_own_image(env: Path, tmp_path: Path) -> None:
    img = tmp_path / "mine.png"
    Image.new("RGB", (8, 8)).save(img)
    assert run("wallpaper", "set", str(img)) == 0
    assert run("wallpaper", "dynamic", "low-poly-mountain") == 0
    assert config.load()["wallpaper"]["path"] == ""


def test_cli_reset_returns_to_the_default(env: Path, tmp_path: Path) -> None:
    config.set_values({"wallpaper.dynamic": "", "wallpaper.sync": "theme", "wallpaper.path": ""})
    assert run("wallpaper", "reset") == 0
    w = config.load()["wallpaper"]
    assert (w["dynamic"], w["sync"], w["path"], w["frame"]) == ("low-poly-mountain", "auto", "", "")


def test_cli_location(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("wallpaper", "location", "35.2", "33.4") == 0 and config.load()["wallpaper"]["location"] == "35.2, 33.4"
    assert run("wallpaper", "location", "99", "0") == 1 and "out of range" in capsys.readouterr().err
    assert run("wallpaper", "location", "auto") == 0 and config.load()["wallpaper"]["location"] == ""


def test_cli_status_and_list(env: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    freeze(monkeypatch, at(13))
    assert run("wallpaper", "status") == 0
    out = capsys.readouterr().out
    assert "Low-poly mountain" in out and "follows: auto" in out
    assert re.search(r"02-noon\.jpg\s+12:00 lightest\s+<-- showing", out)
    assert "00-night.jpg" in out and "darkest" in out
    assert run("wallpaper", "list") == 0
    assert "dynamic low-poly-mountain: Low-poly mountain, 5 frames, time based" in capsys.readouterr().out


def test_theme_style_switch_changes_the_wallpaper(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`surfctl theme variant` is what a light/dark toggle runs; in theme sync it must change the frame."""
    freeze(monkeypatch, at(13))
    assert run("wallpaper", "sync", "theme") == 0
    assert run("theme", "variant", "dark") == 0
    assert "00-night.jpg" in bg_line((paths.generated_dir() / "sway" / "config").read_text())
    assert run("theme", "variant", "light") == 0
    assert "02-noon.jpg" in bg_line((paths.generated_dir() / "sway" / "config").read_text())


# ------------------------------------------------------------- the updater ---

class FakeSway:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd: list[str], **_kw: object) -> object:
        self.calls.append(list(cmd))
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()


def test_updater_applies_the_current_frame(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sway = FakeSway()
    monkeypatch.setattr(session, "_run", sway)
    monkeypatch.setattr(session, "in_sway", lambda: True)
    freeze(monkeypatch, at(19))
    assert session.wallpaper_daemon(once=True) == 0
    assert len(sway.calls) == 1 and sway.calls[0][0] == "swaymsg"
    assert "03-evening.jpg" in sway.calls[0][1] and sway.calls[0][1].startswith("output * bg ")
    assert dynwall.link_path().resolve().name == "03-evening.jpg"


def test_updater_follows_the_day_and_stops_when_not_wanted(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sway = FakeSway()
    monkeypatch.setattr(session, "_run", sway)
    monkeypatch.setattr(session, "in_sway", lambda: True)
    clock = [at(5, 59, 40)]
    monkeypatch.setattr(dynwall, "now", lambda: clock[0])
    naps: list[float] = []

    def sleep(seconds: float) -> None:
        naps.append(seconds)
        clock[0] += timedelta(seconds=seconds)
        if len(naps) == 3:  # the user switches to theme sync while the updater runs
            config.set_values({"wallpaper.sync": "theme"})

    monkeypatch.setattr(session.time, "sleep", sleep)
    assert session.wallpaper_daemon() == 0
    shown = [re.search(r"/(\d\d-\w+)\.jpg", c[1]).group(1) for c in sway.calls]  # type: ignore[union-attr]
    assert shown[:2] == ["00-night", "01-dawn"]
    assert naps[0] == 20  # woke exactly when the morning frame starts
    assert all(n <= 300 for n in naps)


def test_updater_without_sway_still_keeps_the_link(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(session, "in_sway", lambda: False)
    freeze(monkeypatch, at(7))
    assert session.wallpaper_daemon(once=True) == 0
    assert dynwall.link_path().resolve().name == "01-dawn.jpg"


def test_updater_exits_at_once_when_nothing_follows_the_clock(env: Path) -> None:
    config.set_values({"wallpaper.dynamic": ""})
    assert session.wallpaper_daemon() == 0
