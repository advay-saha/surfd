#!/usr/bin/env python3
"""Trace the 'surfd' wordmark out of the original 4K wallpaper into a vector path.

Writes tools/wallpapers/wordmark_path.json with an SVG path (origin = top-left of the ink box, units = pixels of
the 3840x2160 original) plus the measured text colour, and an overlay PNG to check the trace.

Usage: python3 -I trace_wordmark.py <original.png> <out.json> <overlay.png>
"""
import io
import json
import sys

import cairosvg
import numpy as np
import potrace
from PIL import Image

BG_LEFT = np.array([22, 80, 81.0])
BG_RIGHT = np.array([13, 27, 36.0])
UP = 4  # supersampling factor for sub-pixel accurate edges


def soft_alpha(a):
    _H, W, _ = a.shape
    t = np.linspace(0, 1, W)[None, :, None]
    bg = (1 - t) * BG_LEFT + t * BG_RIGHT
    bg = np.broadcast_to(bg, a.shape)
    text = np.array([223, 234, 239.0])
    d = text[None, None, :] - bg
    return np.clip(((a - bg) * d).sum(axis=2) / (d * d).sum(axis=2), 0, 1)


def main(orig, out_json, overlay):
    a = np.asarray(Image.open(orig).convert("RGB")).astype(float)
    H, W, _ = a.shape
    alpha = soft_alpha(a)
    ys, xs = np.where(alpha > 0.5)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    pad = 24
    cx0, cy0, cx1, cy1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
    crop = alpha[cy0:cy1, cx0:cx1]

    # measured solid text colour from fully covered pixels
    solid = alpha > 0.995
    colour = np.median(a[solid], axis=0)
    print("text colour", colour.round(1), "-> #{:02x}{:02x}{:02x}".format(*tuple(round(v) for v in colour)))

    img = Image.fromarray((crop * 255).astype(np.uint8)).resize(
        (crop.shape[1] * UP, crop.shape[0] * UP), Image.LANCZOS)
    big = np.asarray(img).astype(float) / 255.0
    # potracer wants a boolean array in which ink is False
    bm = potrace.Bitmap(~(big > 0.5))
    plist = bm.trace(turdsize=8, turnpolicy=potrace.POTRACE_TURNPOLICY_MINORITY,
                     alphamax=1.0, opticurve=True, opttolerance=0.25)

    def P(p):  # potrace point -> pixel coordinates of the ink box (origin at ink top-left)
        return (p.x / UP + cx0 - x0, p.y / UP + cy0 - y0)

    parts = []
    for curve in plist:
        sx, sy = P(curve.start_point)
        d = [f"M{sx:.2f} {sy:.2f}"]
        for seg in curve.segments:
            if seg.is_corner:
                cx, cy = P(seg.c)
                ex, ey = P(seg.end_point)
                d.append(f"L{cx:.2f} {cy:.2f}L{ex:.2f} {ey:.2f}")
            else:
                c1x, c1y = P(seg.c1)
                c2x, c2y = P(seg.c2)
                ex, ey = P(seg.end_point)
                d.append(f"C{c1x:.2f} {c1y:.2f} {c2x:.2f} {c2y:.2f} {ex:.2f} {ey:.2f}")
        d.append("Z")
        parts.append("".join(d))
    path = "".join(parts)
    print("curves:", len(plist), "path chars:", len(path), "ink box", x1 - x0, "x", y1 - y0)

    # verify: rasterise the trace at original scale and compare with the soft alpha
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{crop.shape[1]}" height="{crop.shape[0]}">'
           f'<rect width="100%" height="100%" fill="black"/>'
           f'<path transform="translate({x0 - cx0} {y0 - cy0})" d="{path}" fill="white" fill-rule="evenodd"/></svg>')
    png = cairosvg.svg2png(bytestring=svg.encode())
    fit = np.asarray(Image.open(io.BytesIO(png)).convert("L")).astype(float) / 255.0
    iou = np.minimum(fit, crop).sum() / np.maximum(fit, crop).sum()
    mae = np.abs(fit - crop).mean()
    print(f"IoU {iou:.4f}   mean abs alpha error {mae:.5f}   max err {np.abs(fit - crop).max():.2f}")

    rgb = np.zeros((*crop.shape, 3), np.uint8)
    rgb[..., 0] = (fit * 255).astype(np.uint8)
    rgb[..., 1] = (crop * 255).astype(np.uint8)
    Image.fromarray(rgb).save(overlay)

    json.dump(dict(
        source_size=[W, H], ink_box=[int(x0), int(y0), int(x1 - x0), int(y1 - y0)],
        text_colour="#{:02x}{:02x}{:02x}".format(*tuple(round(v) for v in colour)),
        path=path, iou=float(iou),
    ), open(out_json, "w"))


if __name__ == "__main__":
    main(*sys.argv[1:4])
