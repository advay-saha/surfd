"""Generated GTK 3/4 CSS (desktop and login screen) must parse cleanly.

Needs PyGObject with GTK 3 and 4 typelibs; skipped otherwise. GTK 3 and 4
cannot share a process, so each check runs in its own interpreter.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "surfctl"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "surfctl" / "tests"))

from conftest import env  # noqa: F401  (fixture re-export)

from surfd import generate

CHECK = textwrap.dedent("""
    import sys, gi
    gi.require_version("Gtk", sys.argv[1])
    from gi.repository import Gtk
    errors = []
    p = Gtk.CssProvider()
    p.connect("parsing-error", lambda _p, section, err: errors.append(err.message))
    css = open(sys.argv[2]).read()
    if sys.argv[1] == "4.0":
        p.load_from_string(css) if hasattr(p, "load_from_string") else p.load_from_data(css, -1)
    else:
        p.load_from_data(css.encode())
    print(Gtk.get_minor_version())
    print("\\n".join(errors))
    sys.exit(1 if errors else 0)
""")


def _gtk_available(version: str) -> bool:
    r = subprocess.run([sys.executable, "-c", f"import gi; gi.require_version('Gtk', '{version}')"],
                       capture_output=True, check=False)
    return r.returncode == 0


def _check(version: str, css: str, tmp_path: Path) -> None:
    f = tmp_path / "style.css"
    f.write_text(css)
    r = subprocess.run([sys.executable, "-c", CHECK, version, str(f)], capture_output=True, text=True, check=False)
    minor, *errors = r.stdout.strip().splitlines()
    if version == "4.0" and int(minor) < 16:
        # GTK < 4.16 does not know :root (used for libadwaita >= 1.6 variables);
        # it skips that block and still applies the named colours.
        errors = [e for e in errors if e and e != "Unknown name of pseudo-class"]
    errors = [e for e in errors if e]
    assert not errors, f"GTK {version}.{minor} CSS errors:\n" + "\n".join(errors) + r.stderr


@pytest.mark.parametrize("theme", ["tide", "driftwood", "kelp"])
def test_gtk3_css_parses(env, tmp_path, theme):  # noqa: F811
    if not _gtk_available("3.0"):
        pytest.skip("GTK 3 introspection not available")
    from surfd import config
    config.set_values({"theme.name": theme})
    ctx = generate.build_context()
    _check("3.0", generate.gtk3_css(ctx), tmp_path)
    _check("3.0", generate.greeter_css(ctx, "/usr/share/surfd/greeter/background"), tmp_path)


@pytest.mark.parametrize("variant", ["dark", "light"])
def test_gtk4_css_parses(env, tmp_path, variant):  # noqa: F811
    if not _gtk_available("4.0"):
        pytest.skip("GTK 4 introspection not available")
    from surfd import config
    config.set_values({"theme.variant": variant})
    _check("4.0", generate.gtk4_css(generate.build_context()), tmp_path)


@pytest.mark.parametrize("theme,variant", [("tide", "dark"), ("tide", "light"), ("dusk", "dark")])
def test_app_style_parses(env: Path, tmp_path: Path, theme: str, variant: str) -> None:  # noqa: F811
    """The surfd look for Settings, Welcome and the installer (surfd.gtkstyle) is valid GTK 4 CSS."""
    if not _gtk_available("4.0"):
        pytest.skip("GTK 4 not available")
    from surfd import gtkstyle, themes
    pal = themes.find(theme).palette(variant)
    _check("4.0", gtkstyle.app_css(pal, ui_font="Inter", mono_font="JetBrains Mono", radius=12), tmp_path)
