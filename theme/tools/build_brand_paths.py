#!/usr/bin/env python3
"""One-off dev tool: build theme/tools/brand_paths.py (the vector brand shapes) from the brand banner.

    pip install pillow numpy scipy scikit-image fonttools
    python3 theme/tools/build_brand_paths.py banner.png outfit-latin-800-normal.woff

* The big "S" is traced from the banner: its outline is extracted at sub-pixel
  precision (marching squares), split at the sharp terminal corners, smoothed
  along each arc (the banner is a soft raster) and fitted with cubic Béziers
  (Schneider's algorithm).
* The lowercase "surfd" lettering in the banner is Outfit ExtraBold (SIL OFL 1.1,
  the glyph overlap with the banner is 0.90 IoU, the next-best of nine fonts 0.76),
  so its crisp glyph outlines are taken from the font file instead of tracing pixels.

The generated file is committed: building surfd never needs this script.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from PIL import Image
from scipy.ndimage import gaussian_filter, gaussian_filter1d
from skimage.measure import find_contours

TOL = 0.45          # max distance (banner pixels) between smoothed outline and fitted curve
CORNER_DEG = 48     # turning angle over ~4 px that counts as a corner
ARC_SIGMA = 7.0     # smoothing along each arc, in outline samples (~pixels)


# ------------------------------------------------------------ coverage maps --

def coverage_s(im: np.ndarray, box: tuple[int, int, int, int]) -> np.ndarray:
    """0..1 coverage of the gradient S, normalised against its colour gradient along x."""
    x0, y0, x1, y1 = box
    g = im[y0:y1, x0:x1, 1]
    xs = np.arange(x0, x1)
    fg = 201 + (144 - 201) * np.clip((xs - 404) / (725 - 404), 0, 1)   # green channel of the gradient
    return np.clip((g - 28.0) / (fg[None, :] - 28.0), 0, 1)


# ------------------------------------------------- Bézier fitting (Schneider) --

def _bez(ctrl: np.ndarray, t: np.ndarray) -> np.ndarray:
    t = t[:, None]
    return ((1 - t) ** 3) * ctrl[0] + 3 * ((1 - t) ** 2) * t * ctrl[1] + 3 * (1 - t) * t ** 2 * ctrl[2] + t ** 3 * ctrl[3]


def _dbez(ctrl: np.ndarray, t: np.ndarray, order: int) -> np.ndarray:
    t = t[:, None]
    if order == 1:
        return 3 * ((1 - t) ** 2 * (ctrl[1] - ctrl[0]) + 2 * (1 - t) * t * (ctrl[2] - ctrl[1]) + t ** 2 * (ctrl[3] - ctrl[2]))
    return 6 * ((1 - t) * (ctrl[2] - 2 * ctrl[1] + ctrl[0]) + t * (ctrl[3] - 2 * ctrl[2] + ctrl[1]))


def _chord_params(pts: np.ndarray) -> np.ndarray:
    d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
    return d / d[-1]


def _fit_once(pts: np.ndarray, u: np.ndarray, t1: np.ndarray, t2: np.ndarray) -> np.ndarray:
    p0, p3 = pts[0], pts[-1]
    b0, b1, b2, b3 = ((1 - u) ** 3)[:, None], (3 * (1 - u) ** 2 * u)[:, None], (3 * (1 - u) * u ** 2)[:, None], (u ** 3)[:, None]
    a1, a2 = b1 * t1, b2 * t2
    c = np.array([[np.sum(a1 * a1), np.sum(a1 * a2)], [np.sum(a1 * a2), np.sum(a2 * a2)]])
    tmp = pts - (b0 + b1) * p0 - (b2 + b3) * p3
    x = np.array([np.sum(a1 * tmp), np.sum(a2 * tmp)])
    det = c[0, 0] * c[1, 1] - c[0, 1] ** 2
    seg = np.linalg.norm(p3 - p0)
    if abs(det) > 1e-9:
        al1, al2 = (x[0] * c[1, 1] - x[1] * c[0, 1]) / det, (c[0, 0] * x[1] - c[0, 1] * x[0]) / det
    else:
        al1 = al2 = 0.0
    eps = 1e-6 * seg
    if al1 < eps or al2 < eps:
        al1 = al2 = seg / 3
    return np.array([p0, p0 + t1 * al1, p3 + t2 * al2, p3])


def _reparam(ctrl: np.ndarray, pts: np.ndarray, u: np.ndarray) -> np.ndarray:
    d = _bez(ctrl, u) - pts
    d1, d2 = _dbez(ctrl, u, 1), _dbez(ctrl, u, 2)
    num = np.sum(d * d1, axis=1)
    den = np.sum(d1 * d1, axis=1) + np.sum(d * d2, axis=1)
    den[np.abs(den) < 1e-12] = 1e-12
    return np.clip(u - num / den, 0, 1)


def fit_curve(pts: np.ndarray, t1: np.ndarray, t2: np.ndarray, tol: float) -> list[np.ndarray]:
    if len(pts) == 2:
        d = np.linalg.norm(pts[1] - pts[0]) / 3
        return [np.array([pts[0], pts[0] + t1 * d, pts[1] + t2 * d, pts[1]])]
    u = _chord_params(pts)
    ctrl = _fit_once(pts, u, t1, t2)
    err = np.sum((_bez(ctrl, u) - pts) ** 2, axis=1)
    if err.max() < tol ** 2:
        return [ctrl]
    if err.max() < (tol * 4) ** 2:
        for _ in range(12):
            u = _reparam(ctrl, pts, u)
            ctrl = _fit_once(pts, u, t1, t2)
            err = np.sum((_bez(ctrl, u) - pts) ** 2, axis=1)
            if err.max() < tol ** 2:
                return [ctrl]
    split = int(np.argmax(err))
    split = min(max(split, 1), len(pts) - 2)
    centre = pts[split + 1] - pts[split - 1]
    centre = centre / (np.linalg.norm(centre) or 1)
    return fit_curve(pts[: split + 1], t1, -centre, tol) + fit_curve(pts[split:], centre, t2, tol)


def _tangent(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    v = b - a
    return v / (np.linalg.norm(v) or 1)


def split_corners(pts: np.ndarray) -> list[int]:
    """Indices (into a closed polyline) where the outline turns sharply."""
    n, k = len(pts), 4
    idx = []
    for i in range(n):
        a, b = pts[i] - pts[(i - k) % n], pts[(i + k) % n] - pts[i]
        cosang = np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) or 1)
        ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
        if ang > CORNER_DEG:
            idx.append((i, ang))
    # keep only the sharpest point of each cluster
    out: list[int] = []
    for i, _ang in sorted(idx, key=lambda t: -t[1]):
        if all(min((i - j) % n, (j - i) % n) > 2 * k for j in out):
            out.append(i)
    return sorted(out)


def smooth_arc(seg: np.ndarray, closed: bool) -> np.ndarray:
    """Low-pass an open arc along its length, keeping both end points (odd reflection at the ends)."""
    if len(seg) < 12:
        return seg
    k = min(int(ARC_SIGMA * 4), len(seg) - 1)
    if closed:
        ext = np.vstack([seg[-k - 1:-1], seg, seg[1:k + 1]])
        return gaussian_filter1d(ext, ARC_SIGMA, axis=0)[k:-k]
    head = 2 * seg[0] - seg[1:k + 1][::-1]
    tail = 2 * seg[-1] - seg[-k - 1:-1][::-1]
    out = gaussian_filter1d(np.vstack([head, seg, tail]), ARC_SIGMA, axis=0)[k:-k]
    out[0], out[-1] = seg[0], seg[-1]
    return out


def outline_to_path(pts: np.ndarray, ox: float, oy: float) -> tuple[str, int]:
    """Closed polyline (x, y) -> SVG path data of cubic Béziers (corners preserved)."""
    corners = split_corners(pts)
    if not corners:                       # smooth closed curve: start anywhere, tangent continuous
        corners = [0]
        smooth_closed = True
    else:
        smooth_closed = False
    d, count = "", 0
    for ci, start in enumerate(corners):
        end = corners[(ci + 1) % len(corners)]
        seg = np.vstack([pts[start:end + 1]]) if end > start else np.vstack([pts[start:], pts[:end + 1]])
        if smooth_closed:
            seg = np.vstack([pts, pts[:1]])
        if len(seg) < 3:
            continue
        seg = smooth_arc(seg, closed=smooth_closed)
        t1 = _tangent(seg[0], seg[min(3, len(seg) - 1)])
        t2 = _tangent(seg[-1], seg[max(-4, -len(seg))])
        curves = fit_curve(seg, t1, t2, TOL)
        if ci == 0:
            d += f"M{curves[0][0][0] - ox:.2f},{curves[0][0][1] - oy:.2f}"
        for c in curves:
            d += (f"C{c[1][0] - ox:.2f},{c[1][1] - oy:.2f} {c[2][0] - ox:.2f},{c[2][1] - oy:.2f} "
                  f"{c[3][0] - ox:.2f},{c[3][1] - oy:.2f}")
            count += 1
    return d + "Z", count


def trace(cov: np.ndarray, min_area: float = 30) -> tuple[str, tuple[float, float, float, float], int]:
    cov = gaussian_filter(cov, 0.6)
    padded = np.pad(cov, 2)
    contours = [c for c in find_contours(padded, 0.5) if np.allclose(c[0], c[-1])]
    shapes = []
    for c in contours:
        xy = np.c_[c[:-1, 1], c[:-1, 0]] - 2          # (x, y), un-padded
        area = 0.5 * abs(np.dot(xy[:, 0], np.roll(xy[:, 1], 1)) - np.dot(xy[:, 1], np.roll(xy[:, 0], 1)))
        if area >= min_area:
            shapes.append(xy)
    allpts = np.vstack(shapes)
    x0, y0 = allpts.min(0)
    x1, y1 = allpts.max(0)
    paths, count = [], 0
    for xy in sorted(shapes, key=lambda p: p[:, 0].min()):
        p, n = outline_to_path(xy, x0, y0)
        paths.append(p)
        count += n
    return "".join(paths), (float(x0), float(y0), float(x1), float(y1)), count


def wordmark(font_file: str, text: str = "surfd") -> tuple[str, tuple[float, float, float, float]]:
    """Glyph outlines of `text` as one SVG path, y-down, origin at the top-left of its ink box."""
    font = TTFont(font_file)
    gs, cmap, hmtx = font.getGlyphSet(), font.getBestCmap(), font["hmtx"]
    parts, x = [], 0.0
    xmin = ymin = 1e9
    xmax = ymax = -1e9
    for ch in text:
        name = cmap[ord(ch)]
        bp = BoundsPen(gs)
        gs[name].draw(bp)
        b = bp.bounds
        xmin, xmax = min(xmin, x + b[0]), max(xmax, x + b[2])
        ymin, ymax = min(ymin, -b[3]), max(ymax, -b[1])
        pen = SVGPathPen(gs, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        gs[name].draw(TransformPen(pen, (1, 0, 0, -1, x, 0)))
        parts.append(pen.getCommands())
        x += hmtx[name][0]
    return "".join(parts), (xmin, ymin, xmax, ymax)


def main(banner: str, font_file: str) -> None:
    im = np.asarray(Image.open(banner).convert("RGB")).astype(float)
    s_path, s_box, ns = trace(coverage_s(im, (390, 66, 740, 284)))
    w_path, w_box = wordmark(font_file)
    out = Path(__file__).with_name("brand_paths.py")
    out.write_text(
        '"""Brand vector shapes. Generated by build_brand_paths.py; do not edit by hand.\n\n'
        "S_PATH: the big S, traced from the brand banner (CC-BY-SA-4.0, surfd contributors).\n"
        "WORD_PATH: the lowercase 'surfd' set in Outfit ExtraBold, glyph outlines used as artwork\n"
        "(Outfit is (c) The Outfit Project Authors, SIL Open Font License 1.1; see LICENSES/OFL-1.1.txt).\n"
        'Coordinates are y-down; *_BOX is (xmin, ymin, xmax, ymax) of the ink; S_PATH starts at its box origin."""\n\n'
        f"S_SIZE = ({s_box[2] - s_box[0]:.2f}, {s_box[3] - s_box[1]:.2f})\n"
        f'S_PATH = "{s_path}"\n\n'
        f"WORD_BOX = ({w_box[0]:.1f}, {w_box[1]:.1f}, {w_box[2]:.1f}, {w_box[3]:.1f})\n"
        f'WORD_PATH = "{w_path}"\n')
    print(f"S: {ns} curves, size {s_box[2] - s_box[0]:.1f}x{s_box[3] - s_box[1]:.1f}; wordmark box {w_box}; wrote {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
