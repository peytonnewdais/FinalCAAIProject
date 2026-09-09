"""Accessibility support: WCAG contrast math, color-vision-deficiency simulation, palettes.

Two jobs:

* **Runtime.** Holds the colorblind-mode palettes and the redundant (non-color) encodings -
  dash patterns and marker symbols - that ``services/theme.py`` hands to Plotly when a user
  turns colorblind mode on. WCAG 1.4.1 asks that color never be the *only* channel carrying
  information; in colorblind mode every series gets a shape as well as a hue.
* **Validation.** The contrast and CVD-simulation functions are pure and exercised by
  ``tests/test_a11y.py``, which fails if a palette or a CSS token pair drifts below the WCAG
  thresholds. That makes "this site is accessible" a claim the test suite re-checks, not a
  comment that rots.

Color science: sRGB/Lab conversions per IEC 61966-2-1 and CIE; CIEDE2000 per Sharma, Wu &
Dalal (2005); dichromacy simulation per Vienot, Brettel & Mollon (1999).

AI usage: see docs/AI_USAGE.md.
"""
from __future__ import annotations

import math

# WCAG 2.1 thresholds.
AA_NORMAL_TEXT = 4.5   # 1.4.3 Contrast (Minimum), text below ~18.7px
AA_LARGE_TEXT = 3.0    # 1.4.3, large text
AA_NON_TEXT = 3.0      # 1.4.11 Non-text Contrast: UI components and graphical objects

# Working thresholds for "two chart series still read as different colors", as CIEDE2000
# distance after CVD simulation. These are calibrated against the Okabe-Ito palette, the
# standard CVD-safe categorical set, which across eight colors scores min dE00 = 21.7 for
# normal vision, 10.2 protanopia, 13.5 deuteranopia and just 1.1 tritanopia.
#
# That calibration is the important finding: eight categories CANNOT be made mutually
# distinguishable by hue alone under dichromacy - not even by the reference palette. So
# colorblind mode pairs its palette with dash patterns and marker symbols below, and these
# thresholds are set to what is genuinely achievable rather than to a flattering round number.
MIN_DELTA_E_NORMAL = 20.0
MIN_DELTA_E_DICHROMAT = 11.0   # protanopia / deuteranopia, ~6% of men between them
MIN_DELTA_E_TRITAN = 9.0       # tritanopia, ~0.01% and the hardest to satisfy

CVD_KINDS = ("protanopia", "deuteranopia", "tritanopia")


# ------------------------------------------------------------------ sRGB basics

def hex_to_rgb(color: str) -> tuple[float, float, float]:
    """'#rrggbb' -> three 0-1 floats."""
    h = color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb_to_hex(rgb) -> str:
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02x}" for c in rgb)


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(c: float) -> float:
    c = max(0.0, min(1.0, c))
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


# ------------------------------------------------------------------ WCAG contrast

def relative_luminance(color: str) -> float:
    """WCAG 2.1 relative luminance of an sRGB hex color."""
    r, g, b = (_srgb_to_linear(c) for c in hex_to_rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colors, 1.0 (identical) to 21.0 (black on white)."""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


# ------------------------------------------------------------------ CIE Lab + CIEDE2000

_D65 = (0.95047, 1.00000, 1.08883)


def _rgb_to_xyz(rgb):
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    return (0.4124564 * r + 0.3575761 * g + 0.1804375 * b,
            0.2126729 * r + 0.7151522 * g + 0.0721750 * b,
            0.0193339 * r + 0.1191920 * g + 0.9503041 * b)


def _xyz_to_rgb(xyz):
    x, y, z = xyz
    return (_linear_to_srgb(3.2404542 * x - 1.5371385 * y - 0.4985314 * z),
            _linear_to_srgb(-0.9692660 * x + 1.8760108 * y + 0.0415560 * z),
            _linear_to_srgb(0.0556434 * x - 0.2040259 * y + 1.0572252 * z))


def _f(t: float) -> float:
    return t ** (1 / 3) if t > 216 / 24389 else (841 / 108) * t + 4 / 29


def _f_inv(t: float) -> float:
    return t ** 3 if t > 6 / 29 else (t - 4 / 29) * (108 / 841)


def hex_to_lab(color: str) -> tuple[float, float, float]:
    x, y, z = _rgb_to_xyz(hex_to_rgb(color))
    fx, fy, fz = _f(x / _D65[0]), _f(y / _D65[1]), _f(z / _D65[2])
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def lab_to_hex(lab) -> str:
    L, a, b = lab
    fy = (L + 16) / 116
    xyz = (_D65[0] * _f_inv(fy + a / 500), _D65[1] * _f_inv(fy), _D65[2] * _f_inv(fy - b / 200))
    return rgb_to_hex(_xyz_to_rgb(xyz))


def delta_e(a: str, b: str) -> float:
    """CIEDE2000 perceptual distance between two hex colors."""
    l1, a1, b1 = hex_to_lab(a)
    l2, a2, b2 = hex_to_lab(b)

    c1, c2 = math.hypot(a1, b1), math.hypot(a2, b2)
    c_bar = (c1 + c2) / 2
    g = 0.5 * (1 - math.sqrt(c_bar ** 7 / (c_bar ** 7 + 25 ** 7))) if c_bar else 0.0
    a1p, a2p = (1 + g) * a1, (1 + g) * a2
    c1p, c2p = math.hypot(a1p, b1), math.hypot(a2p, b2)

    h1p = math.degrees(math.atan2(b1, a1p)) % 360 if (a1p or b1) else 0.0
    h2p = math.degrees(math.atan2(b2, a2p)) % 360 if (a2p or b2) else 0.0

    dLp = l2 - l1
    dCp = c2p - c1p
    if c1p * c2p == 0:
        dhp = 0.0
    elif abs(h2p - h1p) <= 180:
        dhp = h2p - h1p
    elif h2p - h1p > 180:
        dhp = h2p - h1p - 360
    else:
        dhp = h2p - h1p + 360
    dHp = 2 * math.sqrt(c1p * c2p) * math.sin(math.radians(dhp) / 2)

    Lp_bar = (l1 + l2) / 2
    Cp_bar = (c1p + c2p) / 2
    if c1p * c2p == 0:
        hp_bar = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hp_bar = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hp_bar = (h1p + h2p + 360) / 2
    else:
        hp_bar = (h1p + h2p - 360) / 2

    t = (1 - 0.17 * math.cos(math.radians(hp_bar - 30))
         + 0.24 * math.cos(math.radians(2 * hp_bar))
         + 0.32 * math.cos(math.radians(3 * hp_bar + 6))
         - 0.20 * math.cos(math.radians(4 * hp_bar - 63)))
    d_theta = 30 * math.exp(-(((hp_bar - 275) / 25) ** 2))
    Rc = 2 * math.sqrt(Cp_bar ** 7 / (Cp_bar ** 7 + 25 ** 7)) if Cp_bar else 0.0
    Sl = 1 + (0.015 * (Lp_bar - 50) ** 2) / math.sqrt(20 + (Lp_bar - 50) ** 2)
    Sc = 1 + 0.045 * Cp_bar
    Sh = 1 + 0.015 * Cp_bar * t
    Rt = -math.sin(math.radians(2 * d_theta)) * Rc

    return math.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                     + Rt * (dCp / Sc) * (dHp / Sh))


# ------------------------------------------------------------------ CVD simulation

# Vienot, Brettel & Mollon (1999): linear RGB -> LMS and back.
_RGB_TO_LMS = ((17.8824, 43.5161, 4.11935),
               (3.45565, 27.1554, 3.86714),
               (0.0299566, 0.184309, 1.46709))
_LMS_TO_RGB = ((0.0809444479, -0.130504409, 0.116721066),
               (-0.0102485335, 0.0540193266, -0.113614708),
               (-0.000365296938, -0.00412161469, 0.693511405))


def _matmul(matrix, vec):
    return tuple(sum(m * v for m, v in zip(row, vec)) for row in matrix)


def simulate_cvd(color: str, kind: str) -> str:
    """Approximate how a hex color looks to a dichromat.

    ``kind`` is one of CVD_KINDS. Anything else returns the color unchanged, so
    ``simulate_cvd(c, "normal")`` is a no-op and callers can loop uniformly.
    """
    if kind not in CVD_KINDS:
        return color

    linear = tuple(_srgb_to_linear(c) for c in hex_to_rgb(color))
    L, M, S = _matmul(_RGB_TO_LMS, linear)

    if kind == "protanopia":
        L = 2.02344 * M - 2.52581 * S
    elif kind == "deuteranopia":
        M = 0.494207 * L + 1.24827 * S
    else:  # tritanopia
        S = -0.395913 * L + 0.801109 * M

    return rgb_to_hex(_matmul(_LMS_TO_RGB, (L, M, S)))


def min_pairwise_delta_e(colors, kind: str = "normal") -> float:
    """Smallest CIEDE2000 gap between any two colors, as seen with ``kind`` vision."""
    seen = [simulate_cvd(c, kind) for c in colors]
    return min(delta_e(a, b)
               for i, a in enumerate(seen)
               for b in seen[i + 1:])


# ------------------------------------------------------------------ colorblind mode

# Hues sit near eight evenly spaced anchors so the palette still reads as designed; their
# lightness and chroma were then optimized to maximize the worst-case CIEDE2000 gap after
# CVD simulation, subject to every color clearing 3:1 against its chart surface.
#
# Lightness does most of the work here, because lightness is the one channel every form of
# color blindness preserves. Measured worst-case gaps (see tests/test_a11y.py):
#
#   light  normal 21.0  protan 12.6  deutan 12.3  tritan  9.4   contrast floor 3.21:1
#   dark   normal 21.9  protan 22.2  deutan 21.4  tritan 15.3   contrast floor 3.20:1
#
# For comparison, raw Okabe-Ito scores 10.2 / 13.5 / 1.1 and drops to 1.29:1 contrast on a
# near-white surface, so this beats the reference palette on tritanopia and on contrast.
PALETTE_CVD = {
    "light": ["#0033a0", "#95572f", "#719580", "#859600", "#c370be", "#007684", "#6786fb", "#61002b"],
    "dark":  ["#ccf3ff", "#9f5636", "#60fc59", "#b0a625", "#cba7ff", "#00dac3", "#8267b1", "#ffa3b6"],
}

# Redundant, non-color encodings applied in colorblind mode so a series stays identifiable in
# greyscale or to a monochromat. Index-aligned with the palettes above.
CVD_DASHES = ["solid", "dash", "dot", "dashdot", "longdash", "longdashdot", "solid", "dash"]
CVD_MARKERS = ["circle", "square", "diamond", "triangle-up", "cross", "x", "star", "hexagon"]


def resolve_cvd(value) -> bool:
    """Normalise whatever the ``cvd`` store holds (True, "on", None, ...) to a bool."""
    return value is True or value == "on"
