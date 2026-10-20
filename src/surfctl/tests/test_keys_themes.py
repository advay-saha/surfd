from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path

import pytest

from surfd import color, config, keys, paths, themes

# ------------------------------------------------------------------- keys --

@pytest.mark.parametrize("combo,expected", [
    ("Mod+Return", "Mod4+Return"),
    ("Shift+Mod+q", "Mod4+Shift+q"),
    ("ctrl+alt+Delete", "Mod1+Control+Delete"),
    ("Super+Shift+3", "Mod4+Shift+3"),
    ("Print", "Print"),
])
def test_normalize_combo(combo: str, expected: str) -> None:
    assert keys.normalize_combo(combo, "Super") == expected


def test_alt_as_main_modifier() -> None:
    assert keys.normalize_combo("Mod+Return", "Alt") == "Mod1+Return"


@pytest.mark.parametrize("combo", ["", "Mod+", "Hyper+x", "Mod+Shift", "Mod+Mod+x", "Mod+page down"])
def test_bad_combos(combo: str) -> None:
    with pytest.raises(keys.BindingError):
        keys.normalize_combo(combo, "Super")


def test_duplicate_combos_detected() -> None:
    cfg = {"keys": {"modifier": "Super", "bindings": {"Mod+Shift+x": "close", "Shift+Super+x": "fullscreen"}},
           "apps": {}}
    with pytest.raises(keys.BindingError, match="same key combination"):
        keys.compile_bindings(cfg)


@pytest.mark.parametrize("action", ["exec foo; swaymsg exit", "exec a, b", "teleport", "focus sideways",
                                    "workspace abc", "exec"])
def test_bad_actions(action: str) -> None:
    with pytest.raises(keys.BindingError):
        keys.resolve_action(action, {"terminal": "foot"})


def test_default_bindings_compile_and_cover_cheatsheet(env: Path) -> None:
    cfg = config.load_defaults()
    binds = keys.compile_bindings(cfg)
    assert len(binds) > 60
    assert any(b.action == "cheatsheet" and b.sway_combo == "Mod4+slash" for b in binds)
    media = [b for b in binds if b.category == "Media"]
    assert media and all(b.locked for b in media)
    rows = keys.cheatsheet_lines(cfg)
    assert ("Apps", "Super + Enter", "Open a terminal") in rows


# ----------------------------------------------------------------- themes --

REPO = Path(__file__).resolve().parents[3]
OWN_THEMES = sorted(p.name for p in (REPO / "theme" / "themes").iterdir())
PICTURE_THEMES = sorted(p.name for p in (REPO / "wallpapers" / "third-party" / "themes").iterdir())


def _toml(name: str) -> str:
    own = REPO / "theme" / "themes" / name / "theme.toml"
    return (own if own.exists() else REPO / "wallpapers" / "third-party" / "themes" / name / "theme.toml").read_text()


SHIPPED = [(n, v) for n in OWN_THEMES + PICTURE_THEMES for v in ("dark", "light") if f"[{v}]" in _toml(n)]


def test_shipped_themes_load(env: Path) -> None:
    found, broken = themes.discover()
    assert broken == []
    assert {t.name for t in found} == set(OWN_THEMES + PICTURE_THEMES)
    assert set(OWN_THEMES) == {"tide", "driftwood", "kelp", "dusk"} and len(PICTURE_THEMES) == 26
    for t in found:
        assert t.variants, t.name
        assert t.meta.get("license")
        if t.name in OWN_THEMES or t.dynamic:  # surfd's own and the dynamic ones come in both styles
            assert set(t.variants) == {"dark", "light"}, t.name


@pytest.mark.parametrize("name,variant", SHIPPED)
def test_theme_contrast_meets_wcag(env: Path, name: str, variant: str) -> None:
    """Text must stay readable: WCAG AA for body text, 3:1 for UI accents."""
    pal = themes.find(name).palette(variant)
    assert color.contrast(pal.text, pal.background) >= 7.0  # AAA body text
    assert color.contrast(pal.text, pal.surface) >= 7.0
    assert color.contrast(pal.text_muted, pal.surface) >= 4.5  # AA
    assert color.contrast(pal.accent, pal.background) >= 3.0  # UI component
    assert color.contrast(pal.accent_text, pal.accent) >= 4.5
    assert color.contrast(pal.accent2, pal.background) >= 3.0  # second accent (== accent when unset)
    for c in (pal.urgent, pal.warning, pal.success):
        assert color.contrast(c, pal.background) >= 3.0, c
    # terminal: normal colours 1-6 readable on the terminal background
    for c in pal.terminal[1:7]:
        assert color.contrast(c, pal.background) >= 3.0, c


def test_user_theme_shadows_system_theme(env: Path) -> None:
    dest = themes.new("tide-mine", "tide")
    assert dest.parent == paths.user_themes_dir()
    assert themes.find("tide-mine").title == "tide-mine"


def test_broken_theme_reported_not_fatal(env: Path) -> None:
    bad = paths.user_themes_dir() / "broken"
    bad.mkdir(parents=True)
    (bad / "theme.toml").write_text('[dark]\nbackground = "#000"\n')
    found, broken = themes.discover()
    assert "broken" not in {t.name for t in found}
    assert any("broken" in b for b in broken)


def _make_theme_dir(tmp: Path, name: str) -> Path:
    src = themes.find("kelp").path
    d = tmp / name
    d.mkdir()
    (d / "theme.toml").write_text((src / "theme.toml").read_text())
    return d


def test_install_folder_tar_and_zip(env: Path, tmp_path: Path) -> None:
    d = _make_theme_dir(tmp_path, "sunset")
    assert themes.install(d).name == "sunset"
    with pytest.raises(themes.ThemeError, match="already exists"):
        themes.install(d)
    assert themes.install(d, force=True).name == "sunset"

    tgz = tmp_path / "surfd-theme-reef.tar.gz"
    d2 = _make_theme_dir(tmp_path, "reef")
    with tarfile.open(tgz, "w:gz") as tf:
        tf.add(d2, arcname="reef")
    assert themes.install(tgz).name == "reef"

    zp = tmp_path / "lagoon.zip"
    with zipfile.ZipFile(zp, "w") as zf:  # flat archive: named after the file
        zf.write(d2 / "theme.toml", "theme.toml")
    assert themes.install(zp).name == "lagoon"


def test_install_rejects_path_traversal(env: Path, tmp_path: Path) -> None:
    evil = tmp_path / "evil.tar.gz"
    payload = tmp_path / "payload"
    payload.write_text("x")
    with tarfile.open(evil, "w:gz") as tf:
        tf.add(payload, arcname="../../escape.txt")
    with pytest.raises(themes.ThemeError):
        themes.install(evil)
    assert not (paths.user_themes_dir().parent / "escape.txt").exists()


def test_export_roundtrip(env: Path, tmp_path: Path) -> None:
    out = themes.export("driftwood", tmp_path)
    assert out.name == "surfd-theme-driftwood.tar.gz"
    with tarfile.open(out) as tf:
        assert "driftwood/theme.toml" in tf.getnames()


def test_accent_override(env: Path) -> None:
    pal = themes.find("tide").palette("dark", "#ff8800")
    assert pal.accent == "#ff8800"
    assert pal.accent_text in ("#111111", "#ffffff")


def test_second_accent(env: Path) -> None:
    tide, kelp = themes.find("tide").palette("dark"), themes.find("kelp").palette("dark")
    assert tide.accent == "#5ecfc2" and tide.accent2 == "#4a90c8"   # the logo's teal and blue
    assert kelp.accent2 == kelp.accent                                # themes without accent2 stay solid
    assert themes.find("tide").palette("dark", "#ff8800").accent2 == "#ff8800"  # a custom accent wins outright


def test_bad_second_accent_rejected() -> None:
    assert any("accent2" in e for e in themes._validate_variant("dark", {"accent2": "blue"}))


@pytest.mark.parametrize("value,expected", [("#ABC", "#aabbcc"), ("88c0d0", "#88c0d0"), (" #88C0D0 ", "#88c0d0")])
def test_color_normalize(value: str, expected: str) -> None:
    assert color.normalize(value) == expected


def test_color_helpers() -> None:
    assert color.mix("#000000", "#ffffff", 0.5) == "#808080"
    assert round(color.contrast("#000000", "#ffffff"), 1) == 21.0
    assert color.hex_alpha("#112233", 1.0) == "112233ff"
    with pytest.raises(color.ColorError):
        color.normalize("red")
