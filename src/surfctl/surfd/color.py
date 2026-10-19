"""Small colour helpers. Colours are "#rrggbb" strings throughout."""

from __future__ import annotations

import re

_HEX = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


class ColorError(ValueError):
    pass


def normalize(value: str) -> str:
    """Return a canonical lowercase "#rrggbb" or raise ColorError."""
    if not isinstance(value, str):
        raise ColorError(f"colour must be a string like '#88c0d0', got {value!r}")
    m = _HEX.match(value.strip())
    if not m:
        raise ColorError(f"'{value}' is not a colour; use '#rgb' or '#rrggbb'")
    digits = m.group(1)
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return "#" + digits.lower()


def is_color(value: object) -> bool:
    try:
        normalize(value)  # type: ignore[arg-type]
    except ColorError:
        return False
    return True


def to_rgb(value: str) -> tuple[int, int, int]:
    h = normalize(value)[1:]
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def from_rgb(r: float, g: float, b: float) -> str:
    def clamp(x: float) -> int:
        return max(0, min(255, round(x)))

    return f"#{clamp(r):02x}{clamp(g):02x}{clamp(b):02x}"


def mix(a: str, b: str, amount: float) -> str:
    """Blend a toward b by amount (0 = a, 1 = b)."""
    ra, ga, ba = to_rgb(a)
    rb, gb, bb = to_rgb(b)
    return from_rgb(ra + (rb - ra) * amount, ga + (gb - ga) * amount, ba + (bb - ba) * amount)


def luminance(value: str) -> float:
    """WCAG relative luminance."""

    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = to_rgb(value)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def readable_on(background: str, dark: str = "#000000", light: str = "#ffffff") -> str:
    """Pick whichever of dark/light text contrasts more with background."""
    return dark if contrast(background, dark) >= contrast(background, light) else light


def hex_no_hash(value: str) -> str:
    return normalize(value)[1:]


def rgba(value: str, alpha: float) -> str:
    """CSS rgba() string."""
    r, g, b = to_rgb(value)
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def hex_alpha(value: str, alpha: float) -> str:
    """"rrggbbaa" without '#', as fuzzel and swaylock expect."""
    return hex_no_hash(value) + f"{round(max(0.0, min(1.0, alpha)) * 255):02x}"
