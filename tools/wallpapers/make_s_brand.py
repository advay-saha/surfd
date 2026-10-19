#!/usr/bin/env python3
"""surfd brand assets, v2: the wide gradient "S" mark.

Generates, for both dark and light:
  icon-<v>.svg/.png   rounded-square app icon with the S (desktop / favicon / avatar)
  mark-<v>.svg        bare S on transparent background
  banner-<v>.svg/.png 1280x640 GitHub banner: S over the "surfd" wordmark
  small-sizes.png     legibility check of the icon at 16-128 px

The S is the outline of Syne ExtraBold (OFL, see brand/fonts/syne/LICENSE) converted to a
path; the wordmark is Poppins Bold converted to paths, so nothing depends on
installed fonts at view time.

Usage: python3 -I tools/wallpapers/make_s_brand.py <repo_dir>   (writes <repo_dir>/brand/)
"""
import io
import sys
from pathlib import Path

import cairosvg
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image

SYNE = Path(__file__).resolve().parents[2] / "brand/fonts/syne/syne-latin-800-normal.woff"
POPPINS = Path("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf")
POPPINS_REG = Path("/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf")

PALETTES = {
    "dark": dict(
        page="#0d1b24", tile="#0d1b24", tile_edge="#1f3a4a",
        g0="#5fd3c4", g1="#4a8cc4",
        text="#dfeaef", muted="#8ca3b0", glow="#5fd3c4", glow_op=0.16,
        band_a="#112431", band_b="#16303f",
    ),
    "light": dict(
        page="#eef4f6", tile="#e9f2f5", tile_edge="#b9d0da",
        g0="#0f8f85", g1="#2d6fa8",
        text="#15262f", muted="#526873", glow="#2d6fa8", glow_op=0.12,
        band_a="#e3edf1", band_b="#d6e5eb",
    ),
}


# ------------------------------------------------------------------ glyphs --
def _outline(font_path, ch):
    f = TTFont(font_path)
    gs = f.getGlyphSet()
    name = f.getBestCmap()[ord(ch)]
    bp = BoundsPen(gs)
    gs[name].draw(bp)
    return gs, name, bp.bounds


def s_mark():
    """Syne ExtraBold 'S' as a path normalised to the origin (y down).

    Returns (path_d, width, height) in font units.
    """
    gs, name, (x0, y0, x1, y1) = _outline(SYNE, "S")
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}")
    gs[name].draw(TransformPen(pen, (1, 0, 0, -1, -x0, y1)))
    return pen.getCommands(), x1 - x0, y1 - y0


class Face:
    def __init__(self, path):
        self.font = TTFont(path)
        self.gs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.upm = self.font["head"].unitsPerEm
        self.hmtx = self.font["hmtx"]

    def advance(self, text, size, tracking=0.0):
        k = size / self.upm
        return sum(self.hmtx[self.cmap[ord(c)]][0] * k + tracking for c in text) - tracking

    def path(self, text, size, x, y, tracking=0.0):
        k = size / self.upm
        pen = SVGPathPen(self.gs, ntos=lambda v: f"{v:.2f}")
        cx = x
        for c in text:
            n = self.cmap[ord(c)]
            self.gs[n].draw(TransformPen(pen, (k, 0, 0, -k, cx, y)))
            cx += self.hmtx[n][0] * k + tracking
        return pen.getCommands()


# -------------------------------------------------------------------- icon --
def grad(uid, c):
    return (f'<linearGradient id="{uid}" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0" stop-color="{c["g0"]}"/><stop offset="1" stop-color="{c["g1"]}"/></linearGradient>')


def icon_body(c, uid, s_frac=0.70):
    """512x512 app icon: rounded tile + centred gradient S."""
    d, w, h = s_mark()
    k = 512 * s_frac / w
    x, y = (512 - w * k) / 2, (512 - h * k) / 2
    return (f'<defs>{grad("g-" + uid, c)}</defs>'
            f'<rect x="16" y="16" width="480" height="480" rx="112" fill="{c["tile"]}"/>'
            f'<rect x="17" y="17" width="478" height="478" rx="111" fill="none" stroke="{c["tile_edge"]}" stroke-width="2"/>'
            f'<path transform="translate({x:.2f} {y:.2f}) scale({k:.5f})" d="{d}" fill="url(#g-{uid})"/>')


def icon_svg(v):
    c = PALETTES[v]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" '
            f'role="img" aria-label="surfd icon"><title>surfd</title>{icon_body(c, "i" + v)}</svg>\n')


def mark_svg(v):
    c = PALETTES[v]
    d, w, h = s_mark()
    pad = 8
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {w + 2 * pad:.0f} {h + 2 * pad:.0f}" '
            f'role="img" aria-label="surfd mark"><title>surfd</title><defs>{grad("g-m" + v, c)}</defs>'
            f'<path d="{d}" fill="url(#g-m{v})"/></svg>\n')


# ------------------------------------------------------------------ banner --
def banner_svg(v, W=1280, H=640):
    c = PALETTES[v]
    bold, reg = Face(POPPINS), Face(POPPINS_REG)
    d, sw, sh = s_mark()

    s_w = 250
    k = s_w / sw
    s_h = sh * k
    word, word_size, word_track = "surfd", 108, 2.0
    tag, tag_size, tag_track = "lightweight  ·  aesthetic  ·  endlessly customizable", 25, 1.2

    # vertical stack, centred as a block between y=60 and y=545
    asc = word_size * 0.74  # ascender height of f / d above the baseline
    gap1, gap2 = 44, 44
    block = s_h + gap1 + asc + gap2 + tag_size * 0.7
    top = 60 + (485 - block) / 2
    s_x, s_y = (W - s_w) / 2, top
    word_base = s_y + s_h + gap1 + asc
    tag_base = word_base + gap2 + tag_size * 0.7

    word_w, tag_w = bold.advance(word, word_size, word_track), reg.advance(tag, tag_size, tag_track)
    word_d = bold.path(word, word_size, (W - word_w) / 2, word_base, word_track)
    tag_d = reg.path(tag, tag_size, (W - tag_w) / 2, tag_base, tag_track)

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="surfd - lightweight, aesthetic Linux distro">
  <title>surfd</title>
  <defs>
    {grad("g-b" + v, c)}
    <radialGradient id="glow-{v}" cx="50%" cy="40%" r="55%">
      <stop offset="0" stop-color="{c['glow']}" stop-opacity="{c['glow_op']}"/>
      <stop offset="1" stop-color="{c['glow']}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="{W}" height="{H}" fill="{c['page']}"/>
  <rect width="{W}" height="{H}" fill="url(#glow-{v})"/>
  <path d="M0 566 C160 536 300 536 460 562 S760 596 920 566 S1160 540 1280 556 V640 H0 Z" fill="{c['band_a']}"/>
  <path d="M0 600 C180 574 320 576 480 598 S780 626 940 600 S1170 584 1280 594 V640 H0 Z" fill="{c['band_b']}"/>
  <path transform="translate({s_x:.2f} {s_y:.2f}) scale({k:.5f})" d="{d}" fill="url(#g-b{v})"/>
  <path d="{word_d}" fill="{c['text']}"/>
  <path d="{tag_d}" fill="{c['muted']}"/>
</svg>
"""


# ------------------------------------------------------- small-size check --
def small_sizes(out):
    sizes = [16, 24, 32, 48, 64, 128]
    scale = 4
    128 * scale // 2 + 24
    sheet = Image.new("RGB", (len(sizes) * 150 + 20, 2 * 170 + 20), "#808080")
    for row, v in enumerate(("dark", "light")):
        bg = PALETTES[v]["page"]
        for col, s in enumerate(sizes):
            png = cairosvg.svg2png(bytestring=icon_svg(v).encode(), output_width=s, output_height=s)
            im = Image.open(io.BytesIO(png)).convert("RGBA")
            big = im.resize((s * scale if s * scale <= 140 else 140,) * 2, Image.NEAREST)
            tile = Image.new("RGB", (140, 150), bg)
            tile.paste(big, ((140 - big.width) // 2, (150 - big.height) // 2), big)
            sheet.paste(tile, (20 + col * 150 - 10, 10 + row * 170))
    sheet.save(out)


# -------------------------------------------------------------------- main --
def main(root):
    out = Path(root) / "brand"
    out.mkdir(exist_ok=True)
    for v in ("dark", "light"):
        (out / f"icon-{v}.svg").write_text(icon_svg(v))
        (out / f"mark-{v}.svg").write_text(mark_svg(v))
        (out / f"banner-{v}.svg").write_text(banner_svg(v))
        cairosvg.svg2png(url=str(out / f"icon-{v}.svg"), write_to=str(out / f"icon-{v}.png"),
                         output_width=1024, output_height=1024)
        cairosvg.svg2png(url=str(out / f"banner-{v}.svg"), write_to=str(out / f"banner-{v}.png"),
                         output_width=1280, output_height=640)
    small_sizes(out / "small-sizes.png")
    print("wrote:", ", ".join(sorted(p.name for p in out.iterdir() if p.is_file())))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
