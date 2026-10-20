#!/usr/bin/env python3
"""Convert an Apple-style dynamic HEIC wallpaper into a surfd wallpaper folder.

Reads the apple_desktop XMP plist (h24 = clock based, solar = sun-position based), writes every
frame as a JPEG and a wallpaper.toml:

  [wallpaper]  name, kind ("time" | "solar"), light = <frame>, dark = <frame>
  [[frame]]    at = "HH:MM"                      (kind = time)
  [[frame]]    altitude = -17.0, azimuth = 105.0 (kind = solar)
               file = "NN-label.jpg"

The light / dark frames are the brightest and darkest frame of the set (measured on luma).

Usage: python3 -I heic2surfd.py <in.heic> <out_dir> <name> [jpeg_quality]
(out_dir: ~/.local/share/surfd/wallpapers/dynamic/<set> for a set of your own)
"""
import base64
import plistlib
import re
import sys
from pathlib import Path

import numpy as np
import pillow_heif


def luma(im):
    a = np.asarray(im.convert("L").resize((256, 144))).astype(np.float32)
    return float(a.mean())


def label(minutes):
    h = minutes // 60
    if h < 4:
        return "night"
    if h < 7:
        return "dawn"
    if h < 11:
        return "morning"
    if h < 14:
        return "noon"
    if h < 17:
        return "afternoon"
    if h < 19:
        return "evening"
    if h < 21:
        return "dusk"
    return "night"


def main(src, out, name, quality=90):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    hf = pillow_heif.open_heif(src)
    xmp = hf.info["xmp"].decode("utf8", "replace")
    kind_key, b64 = re.search(r'apple_desktop:(\w+)="([^"]+)"', xmp).groups()
    meta = plistlib.loads(base64.b64decode(b64))
    imgs = [im.to_pillow().convert("RGB") for im in hf]
    lum = [luma(im) for im in imgs]

    entries = []  # (sort_key, frame_index, toml_fields, label)
    if kind_key == "h24":
        kind = "time"
        for e in sorted(meta["ti"], key=lambda e: e["t"]):
            minutes = round(e["t"] * 24 * 60)
            entries.append((minutes, e["i"], f'at = "{minutes // 60:02d}:{minutes % 60:02d}"', label(minutes)))
    elif kind_key == "solar":
        kind = "solar"
        for e in sorted(meta["si"], key=lambda e: (e["a"], e["z"])):
            entries.append((e["a"], e["i"], f'altitude = {e["a"]:.1f}\nazimuth = {e["z"]:.1f}',
                            f'sun{round(e["a"]):+d}'.replace("+", "p").replace("-", "m")))
    else:
        raise SystemExit(f"unknown apple_desktop kind {kind_key}")

    names = {}
    for n, (_, idx, _, lab) in enumerate(entries):
        names[idx] = f"{n:02d}-{lab}.jpg"
        imgs[idx].save(out / names[idx], quality=quality, subsampling=2, optimize=True)

    # light / dark stills = the brightest and darkest frame. The file's own ap.l / ap.d hints are
    # ignored on purpose: in several files they point at frames that are almost equally bright.
    light, dark = int(np.argmax(lum)), int(np.argmin(lum))
    why = "brightest / darkest"

    lines = ["[wallpaper]", f'name = "{name}"', f'kind = "{kind}"', f'light = "{names[light]}"',
             f'dark = "{names[dark]}"', ""]
    for _, idx, fields, _ in entries:
        lines += ["[[frame]]", fields, f'file = "{names[idx]}"', ""]
    (out / "wallpaper.toml").write_text("\n".join(lines))
    print(f"{name}: {kind}, {len(imgs)} frames {imgs[0].size}, light={names[light]} ({lum[light]:.0f}) "
          f"dark={names[dark]} ({lum[dark]:.0f}) [{why}]")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 90)
