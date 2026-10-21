"""Generated configs are checked with the real tools when they are installed."""

from __future__ import annotations

import configparser
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from surfd import config, generate, paths, session, system

needs_sway = pytest.mark.skipif(shutil.which("sway") is None, reason="sway not installed")
needs_foot = pytest.mark.skipif(shutil.which("foot") is None, reason="foot not installed")


def _ctx(**changes: str) -> generate.Context:
    if changes:
        config.set_values(changes)
    return generate.build_context()


@needs_sway
@pytest.mark.parametrize("theme", ["tide", "driftwood", "kelp"])
@pytest.mark.parametrize("variant", ["dark", "light"])
@pytest.mark.parametrize("mode", ["tiling", "floating"])
def test_sway_config_validates(env: Path, theme: str, variant: str, mode: str) -> None:
    ctx = _ctx(**{"theme.name": theme, "theme.variant": variant, "layout.mode": mode})
    ok, out = session.validate_sway_config(generate.sway(ctx))
    assert ok, out


@needs_sway
def test_sway_validation_catches_errors(env: Path) -> None:
    ok, out = session.validate_sway_config("gaps inner banana\n")
    assert not ok and "Error on line" in out


def test_floating_mode_rules(env: Path) -> None:
    tiling = generate.sway(_ctx())
    assert "for_window [all] floating enable" not in tiling
    assert "default_border pixel 2" in tiling
    floating = generate.sway(_ctx(**{"layout.mode": "floating"}))
    assert "for_window [all] floating enable" in floating
    assert "default_border normal 2" in floating


def test_gestures_toggle(env: Path) -> None:
    assert "bindgesture swipe:3:left" in generate.sway(_ctx())
    assert "bindgesture" not in generate.sway(_ctx(**{"input.gestures": "false"}))


def test_media_keys_work_when_locked(env: Path) -> None:
    text = generate.sway(_ctx())
    assert re.search(r"^bindsym --to-code --locked XF86AudioRaiseVolume exec \S*/surfd-osd --step 5 volume up$", text, re.M)
    assert re.search(r"^bindsym --to-code Mod4\+Return exec foot$", text, re.M)


def test_custom_wallpaper_used(env: Path, tmp_path: Path) -> None:
    img = tmp_path / "beach.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    text = generate.sway(_ctx(**{"wallpaper.path": str(img), "wallpaper.mode": "fit"}))
    assert f'output * bg "{img}" fit' in text


def test_waybar_config_is_json_and_maps_modules(env: Path) -> None:
    ctx = _ctx(**{"bar.right": "tray,audio,power", "bar.position": "bottom"})
    text = generate.waybar_config(ctx)
    data = json.loads(re.sub(r"(?m)^//.*$", "", text))
    assert data["modules-right"] == ["tray", "pulseaudio", "custom/power"]
    assert data["position"] == "bottom" and "margin-bottom" in data


def test_waybar_css_uses_palette(env: Path) -> None:
    css = generate.waybar_css(_ctx(**{"theme.accent": "#ff8800"}))
    assert "#ff8800" in css
    assert css.count("{") == css.count("}")


def test_accent_gradient_only_with_second_accent(env: Path) -> None:
    css = generate.waybar_css(_ctx())                                  # tide: teal to blue
    assert "linear-gradient(to right, #5ecfc2, #4a90c8)" in css
    assert "linear-gradient" not in generate.waybar_css(_ctx(**{"theme.accent": "#ff8800"}))
    assert "linear-gradient" not in generate.waybar_css(_ctx(**{"theme.name": "kelp"}))


def test_ini_outputs_parse(env: Path) -> None:
    ctx = _ctx()
    for text in (generate.fuzzel(ctx), generate.foot(ctx), generate.gtk_settings(ctx, 3), generate.qt6ct_conf(ctx)):
        cp = configparser.ConfigParser(interpolation=None, comment_prefixes=("#", ";"), strict=True)
        cp.read_string(text)
    # mako uses an INI-like format whose top section has no header
    cp = configparser.ConfigParser(interpolation=None, comment_prefixes=("#",), strict=True)
    cp.read_string("[global]\n" + generate.mako(ctx))
    assert cp["urgency=high"]["default-timeout"] == "0"


def test_qt_palette_has_21_roles(env: Path) -> None:
    text = generate.qt6ct_colors(_ctx())
    for line in text.splitlines()[1:]:
        assert len(line.split("=", 1)[1].split(", ")) == 21


def test_gtk4_css_has_named_colours_and_variables(env: Path) -> None:
    css = generate.gtk4_css(_ctx(**{"theme.accent": "#336699"}))
    assert "@define-color accent_bg_color #336699;" in css
    assert "--accent-bg-color: #336699;" in css
    assert ":root" not in generate.gtk3_css(_ctx())  # GTK 3 can't parse it


@needs_foot
def test_foot_accepts_generated_config(env: Path, tmp_path: Path) -> None:
    f = tmp_path / "foot.ini"
    for variant in ("dark", "light"):
        f.write_text(generate.foot(_ctx(**{"theme.variant": variant})))
        r = subprocess.run(["foot", "--check-config", "--config", str(f)], capture_output=True, text=True, check=False,
                           env=dict(os.environ, LC_ALL="C.UTF-8"))
        assert r.returncode == 0, r.stderr


def test_write_all_respects_takeover(env: Path) -> None:
    ctx = _ctx()
    report = generate.write_all(ctx)
    assert len(report.written) == len(generate.outputs(ctx))
    foot_ini = paths.config_home() / "foot" / "foot.ini"
    foot_ini.write_text("[main]\nfont=monospace:size=20\n")  # user removed the marker
    ctx = _ctx(**{"fonts.mono_size": "14"})
    report = generate.write_all(ctx)
    assert foot_ini in report.skipped
    assert foot_ini.read_text() == "[main]\nfont=monospace:size=20\n"
    report = generate.write_all(ctx)
    assert report.written == []  # idempotent


def test_greeter_css(env: Path) -> None:
    css = generate.greeter_css(_ctx(), "/etc/surfd/greetd/background")
    assert 'url("file:///etc/surfd/greetd/background")' in css
    assert "box#body" in css


def test_system_keyboard(tmp_path: Path) -> None:
    x11 = tmp_path / "00-keyboard.conf"
    x11.write_text('Section "InputClass"\n  Option "XkbLayout" "de,us"\n  Option "XkbVariant" "nodeadkeys,"\nEndSection\n')
    assert system.system_keyboard(x11, tmp_path / "none") == {"layout": "de,us", "variant": "nodeadkeys,"}
    vc = tmp_path / "vconsole.conf"
    vc.write_text('KEYMAP="fr-latin9"\nFONT="eurlatgr"\n')
    assert system.system_keyboard(tmp_path / "none", vc) == {"layout": "fr"}
