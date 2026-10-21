"""surfd 0.2 desktop features: flyouts, menus, pickers, capture, helpers and the configs behind them."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

from surfd import capture, cli, config, daemons, desktop, generate, keys, schema

REPO = Path(__file__).resolve().parents[3]
LIBEXEC = REPO / "src" / "session" / "libexec"


def run(*argv: str) -> int:
    return cli.main(list(argv))


def _ctx() -> generate.Context:
    return generate.build_context()


# --------------------------------------------------------------- calculator --

@pytest.mark.parametrize("expr,result", [
    ("2+2", 4), ("2^10", 1024), ("7/2", 3.5), ("(1+2)*3", 9), ("15% * 200", 30), ("sqrt(16)", 4),
    ("1,000 * 3", 3000), ("-3 + 1", -2), ("2 ** 0.5 * 2 ** 0.5", 2), ("10 // 3", 3), ("pi > 3", None),
])
def test_calculator(expr: str, result: float | None) -> None:
    if result is None:
        with pytest.raises(desktop.CalcError):
            desktop.calculate(expr)
        return
    assert desktop.calculate(expr) == pytest.approx(result)


@pytest.mark.parametrize("expr", ["__import__('os')", "open('x')", "2**99999", "1/0", "a+b", "[1,2]"])
def test_calculator_refuses_anything_but_arithmetic(expr: str) -> None:
    with pytest.raises(desktop.CalcError):
        desktop.calculate(expr)


def test_calc_command_prints(capsys: pytest.CaptureFixture[str], env: Path) -> None:
    assert run("calc", "2^10", "/", "4") == 0
    assert capsys.readouterr().out.strip() == "256"
    assert desktop.format_number(0.1 + 0.2) == "0.3"


# -------------------------------------------------------------- emoji, clip --

def test_emoji_list_has_names() -> None:
    items = dict(desktop.emoji_list())
    assert "🌊" in items and items["🌊"] == "water wave"
    assert len(items) > 1000


def test_clipboard_history(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for text in ("one", "two", "one", "   ", "three"):
        desktop.clipboard_store(text, limit=3)
    assert desktop.clipboard_load() == ["three", "one", "two"]
    desktop.clipboard_store("four", limit=3)
    assert desktop.clipboard_load() == ["four", "three", "one"]  # oldest dropped
    monkeypatch.setenv("CLIPBOARD_STATE", "sensitive")  # a password manager copied this
    assert desktop.clipboard_store("hunter2", limit=3) is False
    assert "hunter2" not in desktop.clipboard_load()
    assert oct(desktop.clipboard_file().stat().st_mode & 0o777) == "0o600"


def test_clipboard_store_command_reads_stdin(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import sys
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"copied from a terminal\n")))
    assert run("clipboard", "store") == 0
    assert desktop.clipboard_load() == ["copied from a terminal\n"]
    assert desktop.clipboard_label(1, "a\n  b\tc") == "  1  a b c"


# ----------------------------------------------------------------- autotile --

def _tree(layout: str, rect: dict[str, int]) -> dict:
    win = {"id": 7, "type": "con", "rect": rect, "nodes": []}
    return {"id": 1, "type": "root", "nodes": [{"id": 2, "type": "workspace", "layout": layout, "nodes": [win]}]}, win


@pytest.mark.parametrize("layout,rect,expected", [
    ("splith", {"width": 1600, "height": 900}, None),        # wide window in a row: next goes right, already so
    ("splith", {"width": 600, "height": 900}, "splitv"),     # tall window: next goes below
    ("splitv", {"width": 1600, "height": 400}, "splith"),
    ("tabbed", {"width": 600, "height": 900}, None),         # tabs and stacks are left alone
])
def test_autotile_splits_along_the_longer_side(layout: str, rect: dict[str, int], expected: str | None) -> None:
    tree, win = _tree(layout, rect)
    assert daemons.autotile_command({"change": "focus", "container": win}, tree) == expected


def test_autotile_ignores_floating_and_fullscreen() -> None:
    tree, win = _tree("splith", {"width": 600, "height": 900})
    assert daemons.autotile_command({"change": "focus", "container": {**win, "floating": "user_on"}}, tree) is None
    assert daemons.autotile_command({"change": "focus", "container": {**win, "fullscreen_mode": 1}}, tree) is None
    assert daemons.autotile_command({"change": "title", "container": win}, tree) is None


# -------------------------------------------------------------------- power --

def _supply(root: Path, name: str, **files: str) -> None:
    d = root / name
    d.mkdir(parents=True)
    for k, v in files.items():
        (d / k).write_text(v + "\n")


def test_read_power(tmp_path: Path) -> None:
    _supply(tmp_path, "AC", type="Mains", online="0")
    _supply(tmp_path, "BAT0", type="Battery", capacity="18", status="Discharging", energy_now="9000000",
            energy_full="50000000", power_now="9000000")
    _supply(tmp_path, "hidpp_battery_0", type="Battery", scope="Device", capacity="5")  # a mouse: ignored
    state = daemons.read_power(tmp_path)
    assert (state.percent, state.charging, state.on_ac, state.minutes_left) == (18, False, False, 60)
    assert daemons.read_power(tmp_path / "none").percent is None


def test_battery_alerts_once_per_drop() -> None:
    warned: set[str] = set()
    s = daemons.PowerState(19, False, False, None)
    assert daemons.battery_alert(s, 20, 8, warned) == "warning"
    assert daemons.battery_alert(s, 20, 8, warned) is None
    assert daemons.battery_alert(daemons.PowerState(7, False, False, None), 20, 8, warned) == "critical"
    assert daemons.battery_alert(daemons.PowerState(7, True, True, None), 20, 8, warned) is None  # plugged in
    assert daemons.battery_alert(s, 20, 8, warned) == "warning"  # unplugged again: warn again
    assert daemons.battery_alert(s, 0, 0, set()) is None


def test_nightlight_args() -> None:
    auto = daemons.nightlight_args("auto", 4000, "35.2, 33.4")
    assert auto[:5] == ["wlsunset", "-l", "35.20", "-L", "33.40"] and auto[-4:] == ["-t", "4000", "-T", "6500"]
    always = daemons.nightlight_args("on", 3500, "35.2, 33.4")
    assert always[-4:] == ["-t", "3500", "-T", "3501"]


# ------------------------------------------------------------------ capture --

def test_parse_ppm_pixel() -> None:
    assert capture.parse_ppm_pixel(b"P6\n1 1\n255\n\x5e\xcf\xc2") == "#5ecfc2"
    assert capture.parse_ppm_pixel(b"P6 # grim\n1 1 255\n\x00\x10\xff") == "#0010ff"
    with pytest.raises(ValueError):
        capture.parse_ppm_pixel(b"P3\n1 1\n255\n0 0 0")


def test_unique_names(tmp_path: Path) -> None:
    (tmp_path / "Shot.png").write_text("")
    (tmp_path / "Shot-2.png").write_text("")
    assert capture._unique(tmp_path, "Shot", ".png").name == "Shot-3.png"


# ------------------------------------------------------------ menus, audio --

def test_control_menu_tree_is_well_formed(env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(desktop.shutil, "which", lambda _x: None)  # no foot: falls back to apps.terminal
    def check(entries: list) -> int:
        n = 0
        for label, value in entries:
            assert isinstance(label, str) and label
            assert isinstance(value, list) and value
            n += check(value) if not isinstance(value[0], str) else 1
        return n
    assert check(desktop.control_menu_tree()) >= 35
    assert {"capture", "toggles", "connections", "setup", "system"} <= set(desktop.menu_names())
    monkeypatch.setenv("SURFD_SYSTEM_DIR", "/nonexistent")  # no settings at all (an RPM build): still works
    assert desktop.terminal_cmd("x", "btop")[-1] == "btop"


def test_audio_devices_from_wpctl(monkeypatch: pytest.MonkeyPatch) -> None:
    status = """PipeWire 'pipewire-0' [1.2.7, user@host, cookie:1]
 └─ Clients:
        33. WirePlumber                         [1.2.7, user@host, pid:1]

Audio
 ├─ Devices:
 │      42. Built-in Audio                      [alsa]
 ├─ Sinks:
 │  *   47. Built-in Audio Analog Stereo        [vol: 0.45]
 │      52. USB Headset                         [vol: 0.80 MUTED]
 ├─ Sources:
 │  *   48. Built-in Audio Analog Stereo        [vol: 1.00]
 ├─ Filters:
 └─ Streams:

Video
 ├─ Devices:
 │      60. Integrated Camera                   [v4l2]
"""
    monkeypatch.setattr(desktop.shutil, "which", lambda _x: "/usr/bin/wpctl")
    monkeypatch.setattr(desktop, "_run", lambda *_a, **_k: subprocess.CompletedProcess([], 0, status, ""))
    devs = desktop.audio_devices()
    assert devs["sinks"] == [("47", "Built-in Audio Analog Stereo", True), ("52", "USB Headset", False)]
    assert devs["sources"] == [("48", "Built-in Audio Analog Stereo", True)]


# ----------------------------------------------------------- settings, keys --

def test_new_settings_have_defaults_and_validate(env: Path) -> None:
    cfg = config.load()
    for key in ("osd.enabled", "osd.step", "notifications.do_not_disturb", "power.battery_warning",
                "capture.screenshots", "clipboard.size", "display.night_light", "layout.autotile",
                "input.repeat_rate", "updates.check"):
        assert key in schema.SCHEMA
        assert config.get(cfg, key) is not None, key
    assert not config.errors(config.validate(cfg))


def test_every_default_binding_compiles_and_every_action_has_a_key(env: Path) -> None:
    bindings = keys.compile_bindings(config.load())
    used = {b.action for b in bindings}
    unbound = set(keys.ACTIONS) - used - {"editor", "focus-mode-toggle", "split-horizontal", "split-vertical",
                                          "screenshot-output", "kill-all"}
    assert not unbound - {"kill-all", "screenshot-output"}, unbound
    assert len(bindings) > 110


def test_osd_command_follows_settings(env: Path) -> None:
    assert keys.osd_command({"step": 10}).endswith("surfd-osd --step 10")
    assert keys.osd_command({"step": 5, "enabled": False}).endswith("--quiet")
    assert run("set", "osd.step", "2", "--no-reload") == 0
    text = generate.sway(_ctx())
    assert "surfd-osd --step 2 brightness up" in text


def test_dnd_toggle_saves_and_reports(env: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert run("dnd", "on") == 0
    assert config.load()["notifications"]["do_not_disturb"] is True
    assert run("dnd", "status") == 0 and capsys.readouterr().out.strip().endswith("on")
    assert run("dnd", "toggle") == 0 and config.load()["notifications"]["do_not_disturb"] is False


# ------------------------------------------------------------ generated files --

def test_sway_config_has_the_new_behaviour(env: Path) -> None:
    text = generate.sway(_ctx())
    for needle in ("smart_gaps off", "hide_edge_borders smart", "workspace_auto_back_and_forth yes",
                   "xkb_numlock enabled", "repeat_rate 40", "seat * hide_cursor when-typing enable",
                   "bindsym --release --locked Caps_Lock exec", "bindswitch --reload --locked lid:on exec",
                   "surfd-daemon autotile on", "surfd-daemon clipboard on", "surfd-daemon nightlight off",
                   'app_id="^surfd-dropdown$"', "makoctl mode -s default", "udiskie"):
        assert needle in text, needle
    assert run("set", "layout.mode", "floating", "--no-reload") == 0
    assert "surfd-daemon autotile off" in generate.sway(_ctx())  # nothing to tile in floating mode


def test_mako_osd_and_dnd(env: Path) -> None:
    text = generate.mako(_ctx())
    assert "[app-name=surfd-osd]" in text and "history=0" in text and "anchor=bottom-center" in text
    assert re.search(r"\[mode=do-not-disturb\]\ninvisible=1", text)
    assert re.search(r"\[mode=do-not-disturb urgency=critical\]\ninvisible=0", text)
    env_text = generate.osd_env(_ctx())
    assert 'ACCENT="#' in env_text and "MONO=" in env_text


def test_waybar_status_modules(env: Path) -> None:
    assert run("bar", "preset", "full", "--no-reload") == 0
    conf = json.loads(generate.waybar_config(_ctx()).split("\n", 1)[1])
    for name in ("custom/notifications", "custom/recording", "custom/updates", "custom/profile",
                 "custom/nightlight", "pulseaudio#mic", "disk"):
        assert name in conf["modules-right"], name
    assert conf["custom/recording"]["signal"] == 8 and conf["custom/recording"]["exec"].endswith("surfd-status recording")


def test_portal_and_swappy_configs(env: Path) -> None:
    outs = {f"{o.path.parent.name}/{o.path.name}": o.content for o in generate.outputs(_ctx())}
    assert "ScreenCast=wlr" in outs["xdg-desktop-portal/sway-portals.conf"]
    assert "chooser_type=dmenu" in outs["xdg-desktop-portal-wlr/config"]
    assert "save_dir=" in outs["swappy/config"] and "Pictures/Screenshots" in outs["swappy/config"]


# -------------------------------------------------------------- shell helpers --

@pytest.mark.parametrize("script", ["surfd-osd", "surfd-daemon", "surfd-lid", "surfd-status", "surfd-notify-file"])
def test_helpers_are_valid_bash(script: str) -> None:
    path = LIBEXEC / script
    assert path.stat().st_mode & 0o111, f"{script} is not executable"
    assert subprocess.run(["bash", "-n", str(path)], check=False).returncode == 0


def test_osd_quiet_changes_nothing_visible(tmp_path: Path) -> None:
    r = subprocess.run([str(LIBEXEC / "surfd-osd"), "--quiet", "message", "x", "y"], capture_output=True,
                       text=True, check=False, env={"PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": str(tmp_path)})
    assert r.returncode == 0 and not (tmp_path / "surfd-osd.id").exists()
    usage = subprocess.run([str(LIBEXEC / "surfd-osd"), "bogus"], capture_output=True, text=True, check=False)
    assert usage.returncode == 2 and "surfd-osd" in usage.stderr


def test_status_without_state_is_empty(tmp_path: Path) -> None:
    env = {"PATH": "/usr/bin:/bin", "XDG_RUNTIME_DIR": str(tmp_path), "XDG_CACHE_HOME": str(tmp_path)}
    for module in ("recording", "updates"):
        r = subprocess.run([str(LIBEXEC / "surfd-status"), module], capture_output=True, text=True, env=env,
                           check=False)
        assert json.loads(r.stdout)["text"] == ""
    (tmp_path / "surfd").mkdir()
    (tmp_path / "surfd" / "updates.json").write_text('{"dnf": 3, "flatpak": 2, "checked": 1}')
    r = subprocess.run([str(LIBEXEC / "surfd-status"), "updates"], capture_output=True, text=True, env=env, check=False)
    assert json.loads(r.stdout)["class"] == "available" and "5" in json.loads(r.stdout)["text"]
