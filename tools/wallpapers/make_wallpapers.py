#!/usr/bin/env python3
"""surfd wallpapers: horizontal gradient + monochrome film grain + traced 'surfd' wordmark.

Everything is measured from the original 3840x2160 'Tide' dark wallpaper:
  * gradient: linear in sRGB from the left colour to the right colour
  * grain: white, monochrome (same value added to R, G and B), std fades linearly from ~10 levels
    at the left edge to ~0 at the far right
  * wordmark: ink box 1164x368 px, vertically centred, right edge 340 px (0.1574 H) from the right,
    height 0.1704 H; vector traced from the original (wordmark_path.json next to this file)

Usage:
  python3 -I tools/wallpapers/make_wallpapers.py render <repo_dir> [jpeg_quality]   (writes <repo_dir>/wallpapers/generated/)
  python3 -I tools/wallpapers/make_wallpapers.py verify <repo_dir> <original.png>
"""
import colorsys
import io
import json
import sys
from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageDraw, ImageFont


# ------------------------------------------------------------------ design --
# (left, right) gradient ends, wordmark colour, grain strength at the left edge (levels)
def hls(h, lightness, s):
    r, g, b = colorsys.hls_to_rgb(h / 360.0, lightness, s)
    return (r * 255, g * 255, b * 255)


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(float(int(h[i:i + 2], 16)) for i in (0, 2, 4))


SCHEMES = {
    "tide": dict(
        title="Tide (default)",
        dark=dict(left=(21.8, 79.8, 80.8), right=(12.5, 26.5, 35.5), text=(222, 233, 238), grain=10.15),
        light=dict(left=hls(181, 0.80, 0.45), right=hexrgb("#eef4f6"), text=hexrgb("#15262f"), grain=8.0),
    ),
    "driftwood": dict(
        title="Driftwood",
        dark=dict(left=hls(20, 0.21, 0.50), right=hexrgb("#1b1714"), text=hexrgb("#ece3d8"), grain=10.15),
        light=dict(left=hls(20, 0.82, 0.55), right=hexrgb("#f6f0e8"), text=hexrgb("#2d241d"), grain=8.0),
    ),
    "kelp": dict(
        title="Kelp",
        dark=dict(left=hls(105, 0.20, 0.50), right=hexrgb("#10160f"), text=hexrgb("#e1ead9"), grain=10.15),
        light=dict(left=hls(100, 0.82, 0.50), right=hexrgb("#f1f5ec"), text=hexrgb("#1c2619"), grain=8.0),
    ),
    "dusk": dict(
        title="Dusk",
        dark=dict(left=hls(258, 0.25, 0.42), right=hexrgb("#0f0c1a"), text=hexrgb("#e6e1f3"), grain=10.15),
        light=dict(left=hls(255, 0.84, 0.55), right=hexrgb("#f4f1fa"), text=hexrgb("#1f1a33"), grain=8.0),
    ),
}

SIZES = [  # (label, width, height)
    ("16x9", 3840, 2160),
    ("16x10", 3840, 2400),
    ("21x9", 3440, 1440),
    ("32x9", 5120, 1440),
]

# wordmark geometry as fractions of the image height (from the original: H=2160)
INK_W, INK_H = 1164, 368
H_FRAC = INK_H / 2160          # wordmark height / image height
MARGIN_FRAC = 340 / 2160       # gap between wordmark and right edge / image height
GRAIN_ZERO_AT = 0.986          # grain reaches 0 at this fraction of the width
GRAIN_FLOOR = 0.5              # tiny dither so the dark right edge cannot band


def load_wordmark(root):
    return json.loads(Path(__file__).with_name("wordmark_path.json").read_text())


def wordmark_alpha(wm, W, H):
    s = H_FRAC * H / INK_H
    w_t, h_t = INK_W * s, INK_H * s
    x0 = W - MARGIN_FRAC * H - w_t
    y0 = (H - h_t) / 2
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}">'
           f'<path transform="translate({x0:.3f} {y0:.3f}) scale({s:.6f})" d="{wm["path"]}" '
           f'fill="#fff" fill-rule="evenodd"/></svg>')
    png = cairosvg.svg2png(bytestring=svg.encode(), output_width=W, output_height=H)
    return np.asarray(Image.open(io.BytesIO(png)).convert("RGBA"))[..., 3].astype(np.float32) / 255.0


def render(wm, spec, W, H, seed=7):
    left, right, text = (np.array(spec[k], np.float32) for k in ("left", "right", "text"))
    t = np.linspace(0.0, 1.0, W, dtype=np.float32)[None, :, None]
    base = (1 - t) * left + t * right                                  # (1, W, 3)
    sigma = np.maximum(spec["grain"] * (1 - t[..., 0] / GRAIN_ZERO_AT), GRAIN_FLOOR)   # (1, W)
    rng = np.random.default_rng(seed)
    n = rng.standard_normal((H, W), dtype=np.float32) * sigma
    img = base + n[..., None]                                          # same noise on R, G, B
    a = wordmark_alpha(wm, W, H)[..., None]
    img = img * (1 - a) + text * a
    return np.clip(np.rint(img), 0, 255).astype(np.uint8)


# ------------------------------------------------------------------ verify --
def verify(root, original):
    from scipy.ndimage import binary_dilation, gaussian_filter
    wm = load_wordmark(root)
    ref = np.asarray(Image.open(original).convert("RGB")).astype(np.float32)
    H, W, _ = ref.shape
    mine = render(wm, SCHEMES["tide"]["dark"], W, H).astype(np.float32)
    a_mine = wordmark_alpha(wm, W, H)
    keep = ~binary_dilation(a_mine > 0.01, iterations=30)
    # 1) low-frequency agreement (gradient colours) away from the text
    def sm(x):
        return np.stack([gaussian_filter(x[..., c], 8) for c in range(3)], -1)
    d = np.abs(sm(mine) - sm(ref))[keep]
    print(f"smoothed colour difference vs original: mean {d.mean():.3f}  p99 {np.percentile(d, 99):.3f}  max {d.max():.2f} (levels, 0-255)")
    # 2) grain strength along x
    print("grain std by x   (original / mine):")
    for x0 in (0, 400, 1000, 1600, 2200, 2800, 3300, 3700):
        pr, pm = ref[100:900, x0:x0 + 100], mine[100:900, x0:x0 + 100]
        sr = (pr - pr.mean(axis=0, keepdims=True)).std()
        sm_ = (pm - pm.mean(axis=0, keepdims=True)).std()
        print(f"  x={x0 + 50:5d}   {sr:5.2f} / {sm_:5.2f}")
    # 3) wordmark coverage
    lum_ref = ref.mean(axis=2)
    mask_ref = (lum_ref > 150)
    mask_mine = (mine.mean(axis=2) > 150)
    iou = (mask_ref & mask_mine).sum() / (mask_ref | mask_mine).sum()
    print(f"wordmark mask IoU (luma>150): {iou:.4f}; pixels differing in text box: {(mask_ref ^ mask_mine).sum()}")
    scratch = Path(root) / "scratch"
    scratch.mkdir(exist_ok=True)
    Image.fromarray(mine.astype(np.uint8)).save(scratch / "tide-dark-recreated.png")


# ----------------------------------------------------------------- render ---
def contact_sheet(root, thumbs, out):
    cell_w, cell_h, pad, label_h = 480, 270, 16, 30
    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (cell_w + pad) + pad, rows * (cell_h + label_h + pad) + pad), (40, 40, 44))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)
    except OSError:
        font = ImageFont.load_default()
    for i, (label, im) in enumerate(thumbs):
        x = pad + (i % cols) * (cell_w + pad)
        y = pad + (i // cols) * (cell_h + label_h + pad)
        sheet.paste(im.resize((cell_w, cell_h), Image.LANCZOS), (x, y))
        d.text((x, y + cell_h + 6), label, fill=(225, 228, 232), font=font)
    sheet.save(out)


def render_all(root, quality):
    root = Path(root)
    wm = load_wordmark(root)
    out = root / "wallpapers" / "generated"
    thumbs, ultra = [], []
    for key, sch in SCHEMES.items():
        (out / key).mkdir(parents=True, exist_ok=True)
        for variant in ("dark", "light"):
            for label, W, H in SIZES:
                arr = render(wm, sch[variant], W, H)
                im = Image.fromarray(arr)
                name = f"{key}-{variant}-{W}x{H}.jpg"
                im.save(out / key / name, quality=quality, subsampling=2, optimize=True)
                if label == "16x9":
                    thumbs.append((f"{sch['title']} - {variant}", im))
                if label == "32x9" and key == "tide":
                    ultra.append((variant, im))
            print("rendered", key, variant)
    contact_sheet(root, thumbs, out / "overview.png")
    # ultrawide preview: both Tide variants stacked
    w = 1600
    prev = Image.new("RGB", (w, 2 * int(w * 1440 / 5120) + 12), (40, 40, 44))
    for i, (_, im) in enumerate(ultra):
        prev.paste(im.resize((w, int(w * 1440 / 5120)), Image.LANCZOS), (0, i * (int(w * 1440 / 5120) + 12)))
    prev.save(out / "overview-ultrawide.png")


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "render":
        render_all(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 90)
    elif mode == "verify":
        verify(sys.argv[2], sys.argv[3])
    else:
        raise SystemExit(__doc__)
