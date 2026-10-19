from __future__ import annotations

from pathlib import Path

import pytest

from surfd import config, paths, schema


def test_defaults_are_valid(env: Path) -> None:
    cfg = config.load_defaults()
    problems = config.validate(cfg)
    assert problems == [], problems


def test_every_schema_key_has_a_default(env: Path) -> None:
    cfg = config.load_defaults()
    missing = [k for k in schema.SCHEMA if config.get(cfg, k) is None]
    assert missing == []


def test_partial_user_file_falls_back_to_defaults(env: Path) -> None:
    paths.user_config().parent.mkdir(parents=True)
    paths.user_config().write_text('[layout]\ngaps_inner = 20\n')
    cfg = config.load()
    assert cfg["layout"]["gaps_inner"] == 20
    assert cfg["layout"]["gaps_outer"] == 6  # from defaults
    assert cfg["theme"]["name"] == "tide"
    assert config.errors(config.validate(cfg)) == []


def test_set_preserves_comments_and_order(env: Path) -> None:
    config.ensure_user_config()
    before = paths.user_config().read_text()
    config.set_value("theme.accent", "#88C0D0")
    after = paths.user_config().read_text()
    assert 'accent = "#88c0d0"' in after
    # every comment line survives
    comments = [line for line in before.splitlines() if line.strip().startswith("#")]
    for line in comments:
        assert line in after
    assert len(after.splitlines()) == len(before.splitlines())


@pytest.mark.parametrize("key,value,fragment", [
    ("layout.gaps_inner", "-3", "at least"),
    ("layout.gaps_inner", "lots", "whole number"),
    ("theme.variant", "purple", "one of"),
    ("theme.accent", "#12345", "not a colour"),
    ("bar.left", "workspaces,teleporter", "unknown bar module"),
    ("nonsense.key", "1", "unknown setting"),
])
def test_invalid_values_are_rejected_and_file_unchanged(env: Path, key: str, value: str, fragment: str) -> None:
    config.ensure_user_config()
    before = paths.user_config().read_text()
    with pytest.raises((config.ConfigError, schema.SchemaError), match=fragment):
        config.set_value(key, value)
    assert paths.user_config().read_text() == before


def test_unknown_theme_is_an_error(env: Path) -> None:
    config.ensure_user_config()
    with pytest.raises(config.ConfigError, match="not found"):
        config.set_value("theme.name", "does-not-exist")


def test_unknown_keys_are_warnings_not_errors(env: Path) -> None:
    paths.user_config().parent.mkdir(parents=True)
    paths.user_config().write_text('[layout]\ngapz = 3\n[weird]\nx = 1\n')
    problems = config.validate(config.load())
    assert config.errors(problems) == []
    assert {p.key for p in problems} == {"layout.gapz", "weird"}


def test_broken_toml_reports_line(env: Path) -> None:
    paths.user_config().parent.mkdir(parents=True)
    paths.user_config().write_text('[theme]\nname = "tide\n')
    with pytest.raises(config.ConfigError, match="line 2"):
        config.load()


def test_reset_whole_file_keeps_backup(env: Path) -> None:
    config.set_value("layout.gaps_inner", "30")
    saved = config.reset()
    assert saved is not None and "gaps_inner = 30" in saved.read_text()
    assert config.load()["layout"]["gaps_inner"] == 8
    assert paths.user_config().read_text() == paths.system_defaults().read_text()


def test_reset_one_section_only(env: Path) -> None:
    config.set_values({"layout.gaps_inner": "30", "theme.variant": "light"})
    config.reset("layout")
    cfg = config.load()
    assert cfg["layout"]["gaps_inner"] == 8
    assert cfg["theme"]["variant"] == "light"


def test_restore_backup(env: Path) -> None:
    config.set_value("layout.radius", "3")
    config.reset()
    latest = config.list_backups()[0]
    config.restore(latest)
    assert config.load()["layout"]["radius"] == 3


def test_disable_default_binding(env: Path) -> None:
    config.set_value("keys.bindings.Mod+q", "none")
    from surfd import keys
    combos = {b.combo for b in keys.compile_bindings(config.load())}
    assert "Mod+q" not in combos
