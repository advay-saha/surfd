#!/usr/bin/env python3
"""Render surfd's SVG artwork into the PNG files packages install.

    python3 theme/tools/render.py OUTDIR

Needs rsvg-convert (librsvg2-tools) and Pillow (python3-pillow). Run by surfd-theme.spec at build time,
so the git repository only contains SVG sources.

OUTDIR layout (mirrors where surfd-theme.spec installs things):
  themes/<name>/...                theme packs with rendered wallpapers
  plymouth/surfd/                  boot splash theme
  anaconda/                        installer sidebar/topbar art
  logos/                           PNG logos at common sizes
  greeter/background               default login background (JPEG)
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_art import MIST, NAVY, TEAL, logo_svg, mark_svg, mix, svg, wordmark_svg  # noqa: E402

BG, ACCENT, TEXT = NAVY, TEAL, MIST


def rsvg(src: str | Path, out: Path, *, width: int | None = None, height: int | None = None) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["rsvg-convert", "--format", "png", "-o", str(out)]
    if width:
        cmd += ["--width", str(width)]
    if height:
        cmd += ["--height", str(height)]
    if isinstance(src, Path):
        subprocess.run([*cmd, str(src)], check=True)
    else:
        subprocess.run(cmd, input=src.encode(), check=True)


def themes(out: Path) -> None:
    for theme in sorted((ROOT / "themes").iterdir()):
        dest = out / "themes" / theme.name
        shutil.copytree(theme, dest, dirs_exist_ok=True)
        for src in sorted((theme / "wallpapers").glob("*.svg")):
            png = dest / "wallpapers" / (src.stem + ".png")
            rsvg(src, png, width=3840, height=2160)
            # JPEG keeps the anti-banding grain at ~1 MB instead of ~7 MB.
            with Image.open(png) as im:
                im.convert("RGB").save(png.with_suffix(".jpg"), quality=90, subsampling=0, optimize=True)
            png.unlink()


def plymouth(out: Path) -> None:
    d = out / "plymouth" / "surfd"
    d.mkdir(parents=True, exist_ok=True)
    # Watermark: the logo, white-ish wordmark on the dark splash.
    rsvg(logo_svg(TEXT), d / "watermark.png", height=72)
    # Spinner: a 270° arc, 36 frames for one full turn.
    frames = 36
    for i in range(frames):
        a = i / frames * math.tau
        r, c = 13, 18
        start = (c + r * math.cos(a), c + r * math.sin(a))
        end = (c + r * math.cos(a + math.tau * 0.72), c + r * math.sin(a + math.tau * 0.72))
        body = (f'<circle cx="{c}" cy="{c}" r="{r}" fill="none" stroke="{TEXT}" stroke-opacity="0.12" stroke-width="3.2"/>'
                f'<path d="M{start[0]:.2f},{start[1]:.2f} A{r},{r} 0 1 1 {end[0]:.2f},{end[1]:.2f}" fill="none" '
                f'stroke="{ACCENT}" stroke-width="3.2" stroke-linecap="round"/>')
        rsvg(svg(36, 36, body), d / f"throbber-{i + 1:04d}.png", width=36, height=36)
    # Password prompt (disk encryption): entry field, bullets, lock icon.
    rsvg(svg(320, 44, f'<rect x="1" y="1" width="318" height="42" rx="12" fill="{mix(BG, TEXT, 0.08)}" '
                      f'stroke="{ACCENT}" stroke-opacity="0.7" stroke-width="2"/>'), d / "entry.png")
    rsvg(svg(14, 14, f'<circle cx="7" cy="7" r="5" fill="{TEXT}"/>'), d / "bullet.png")
    lock = (f'<rect x="5" y="13" width="22" height="16" rx="4" fill="{ACCENT}"/>'
            f'<path d="M10,13 V9 a6,6 0 0 1 12,0 V13" fill="none" stroke="{ACCENT}" stroke-width="3"/>')
    rsvg(svg(32, 32, lock), d / "lock.png")
    rsvg(svg(32, 32, f'<path d="M16,4 L28,18 H21 V28 H11 V18 H4 Z" fill="{TEXT}" fill-opacity="0.8"/>'), d / "capslock.png")
    (d / "surfd.plymouth").write_text((ROOT / "plymouth" / "surfd.plymouth").read_text())


def anaconda(out: Path) -> None:
    d = out / "anaconda"
    side = f"""<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="{mix(BG, ACCENT, 0.15)}"/><stop offset="1" stop-color="{BG}"/></linearGradient></defs>
<rect width="300" height="1200" fill="url(#g)"/>
<path d="M0,980 C80,950 160,1010 300,970 V1200 H0 Z" fill="{ACCENT}" fill-opacity="0.12"/>
<path d="M0,1040 C90,1010 190,1070 300,1030 V1200 H0 Z" fill="{ACCENT}" fill-opacity="0.18"/>"""
    rsvg(svg(300, 1200, side), d / "sidebar-bg.png")
    rsvg(svg(1200, 72, f'<rect width="1200" height="72" fill="{BG}"/>'
                      f'<rect y="70" width="1200" height="2" fill="{ACCENT}" fill-opacity="0.6"/>'), d / "topbar-bg.png")
    rsvg(mark_svg(), d / "sidebar-logo.png", width=96, height=96)
    rsvg(wordmark_svg(TEXT), d / "anaconda_header.png", height=36)


def logos(out: Path) -> None:
    d = out / "logos"
    for size in (64, 128, 256, 512):
        rsvg(ROOT / "logos" / "surfd-mark.svg", d / f"surfd-mark-{size}.png", width=size, height=size)
    rsvg(ROOT / "logos" / "surfd-logo.svg", d / "surfd-logo.png", height=128)
    rsvg(ROOT / "logos" / "surfd-logo-dark.svg", d / "surfd-logo-dark.png", height=128)


def greeter(out: Path) -> None:
    src = out / "themes" / "tide" / "wallpapers" / "tide-dark.jpg"
    (out / "greeter").mkdir(parents=True, exist_ok=True)
    shutil.copy(src, out / "greeter" / "background")


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    if shutil.which("rsvg-convert") is None:
        print("rsvg-convert not found (dnf install librsvg2-tools)", file=sys.stderr)
        return 1
    out = Path(sys.argv[1])
    themes(out)
    plymouth(out)
    anaconda(out)
    logos(out)
    greeter(out)
    print(f"rendered artwork into {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
