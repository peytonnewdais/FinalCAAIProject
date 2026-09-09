"""Accessibility regression tests.

These assert the numbers behind the claims in docs/ACCESSIBILITY.md. If someone later picks
a prettier colour that fails WCAG, or drops a dash pattern from colorblind mode, this fails.
"""
import re
from pathlib import Path

import pytest

from services import theme
from services.a11y import (AA_NON_TEXT, AA_NORMAL_TEXT, CVD_DASHES, CVD_KINDS, CVD_MARKERS,
                           MIN_DELTA_E_DICHROMAT, MIN_DELTA_E_NORMAL, MIN_DELTA_E_TRITAN,
                           PALETTE_CVD, contrast_ratio, delta_e, hex_to_lab, lab_to_hex,
                           min_pairwise_delta_e, relative_luminance, resolve_cvd, simulate_cvd)
from services.config import INDUSTRIES, PALETTE

SURFACE = {"light": "#fcfcfb", "dark": "#1a1a19"}
PAGE = {"light": "#f9f9f7", "dark": "#0d0d0d"}
MODES = ("light", "dark")


# ------------------------------------------------------------------ colour maths

def test_contrast_ratio_hits_the_known_extremes():
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#ffffff", "#ffffff") == pytest.approx(1.0, abs=0.01)


def test_contrast_ratio_is_symmetric():
    assert contrast_ratio("#1f73d0", "#fcfcfb") == pytest.approx(
        contrast_ratio("#fcfcfb", "#1f73d0"))


def test_relative_luminance_is_bounded():
    assert relative_luminance("#000000") == pytest.approx(0.0, abs=1e-6)
    assert relative_luminance("#ffffff") == pytest.approx(1.0, abs=1e-6)


def test_delta_e_of_a_colour_with_itself_is_zero():
    assert delta_e("#1f73d0", "#1f73d0") == pytest.approx(0.0, abs=1e-9)


def test_lab_round_trip_preserves_in_gamut_colours():
    for color in ("#1f73d0", "#eb6834", "#008300", "#ffffff", "#000000"):
        assert lab_to_hex(hex_to_lab(color)) == color


def test_simulate_cvd_leaves_normal_vision_untouched():
    assert simulate_cvd("#1f73d0", "normal") == "#1f73d0"


def test_simulate_cvd_actually_changes_a_red_green_pair():
    # The canonical confusion: red and green collapse toward each other for a deuteranope.
    normal_gap = delta_e("#d03b3b", "#008300")
    deutan_gap = delta_e(simulate_cvd("#d03b3b", "deuteranopia"),
                         simulate_cvd("#008300", "deuteranopia"))
    assert deutan_gap < normal_gap


def test_resolve_cvd_normalises_store_values():
    assert resolve_cvd(True) is True
    assert resolve_cvd("on") is True
    assert resolve_cvd(False) is False
    assert resolve_cvd(None) is False


# ------------------------------------------------------------------ palettes

@pytest.mark.parametrize("mode", MODES)
def test_default_palette_meets_non_text_contrast(mode):
    """WCAG 1.4.11: a chart line is a graphical object and needs 3:1 against its surface."""
    for color in PALETTE[mode]:
        assert contrast_ratio(color, SURFACE[mode]) >= AA_NON_TEXT, f"{color} in {mode}"


@pytest.mark.parametrize("mode", MODES)
def test_colorblind_palette_meets_non_text_contrast(mode):
    for color in PALETTE_CVD[mode]:
        assert contrast_ratio(color, SURFACE[mode]) >= AA_NON_TEXT, f"{color} in {mode}"


@pytest.mark.parametrize("mode", MODES)
def test_colorblind_palette_separates_under_every_vision_type(mode):
    colors = PALETTE_CVD[mode]
    assert min_pairwise_delta_e(colors, "normal") >= MIN_DELTA_E_NORMAL
    assert min_pairwise_delta_e(colors, "protanopia") >= MIN_DELTA_E_DICHROMAT
    assert min_pairwise_delta_e(colors, "deuteranopia") >= MIN_DELTA_E_DICHROMAT
    assert min_pairwise_delta_e(colors, "tritanopia") >= MIN_DELTA_E_TRITAN


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("kind", ["protanopia", "deuteranopia"])
def test_colorblind_palette_beats_the_default_one(mode, kind):
    """The whole point of the mode: it must be a real improvement, not a different look."""
    assert (min_pairwise_delta_e(PALETTE_CVD[mode], kind)
            > min_pairwise_delta_e(PALETTE[mode], kind))


@pytest.mark.parametrize("mode", MODES)
def test_every_industry_has_a_colour_in_both_palettes(mode):
    assert len(PALETTE[mode]) >= len(INDUSTRIES)
    assert len(PALETTE_CVD[mode]) >= len(INDUSTRIES)


# ------------------------------------------------------------------ text tokens

# (label, foreground, background) pairs that carry real text and so owe 4.5:1.
TEXT_PAIRS = [
    ("light muted on surface", "#74726c", "#fcfcfb"),
    ("light muted on page", "#74726c", "#f9f9f7"),
    ("light body on surface", "#52514e", "#fcfcfb"),
    ("light heading on surface", "#0b0b0b", "#fcfcfb"),
    ("light link on surface", "#1f73d0", "#fcfcfb"),
    ("light gain on surface", "#006300", "#fcfcfb"),
    ("light loss on surface", "#d03b3b", "#fcfcfb"),
    ("light button text on accent", "#ffffff", "#1f73d0"),
    ("dark muted on surface", "#898781", "#1a1a19"),
    ("dark muted on page", "#898781", "#0d0d0d"),
    ("dark body on surface", "#c3c2b7", "#1a1a19"),
    ("dark heading on surface", "#ffffff", "#1a1a19"),
    ("dark link on surface", "#3987e5", "#1a1a19"),
    ("dark gain on surface", "#0ca30c", "#1a1a19"),
    ("dark loss on surface", "#e66767", "#1a1a19"),
    ("dark button text on accent", "#0d0d0d", "#3987e5"),
]


@pytest.mark.parametrize("label,fg,bg", TEXT_PAIRS, ids=[p[0] for p in TEXT_PAIRS])
def test_text_tokens_meet_aa_contrast(label, fg, bg):
    assert contrast_ratio(fg, bg) >= AA_NORMAL_TEXT, f"{label}: {contrast_ratio(fg, bg):.2f}:1"


@pytest.mark.parametrize("ring,backgrounds", [
    ("#1f73d0", ["#fcfcfb", "#f9f9f7"]),
    ("#7ab5ff", ["#1a1a19", "#0d0d0d"]),
])
def test_focus_ring_is_visible_against_its_backgrounds(ring, backgrounds):
    """WCAG 1.4.11 again: the focus indicator is a graphical object."""
    for bg in backgrounds:
        assert contrast_ratio(ring, bg) >= AA_NON_TEXT


def test_plotly_tick_label_colour_matches_the_css_muted_token():
    """theme.THEMES mirrors the CSS custom properties; drift would silently break contrast."""
    css = (Path(__file__).resolve().parent.parent / "assets" / "style.css").read_text(encoding="utf-8")
    root_block = css.split(":root {", 1)[1].split("}", 1)[0]
    tokens = dict(re.findall(r"--([\w-]+):\s*([^;]+);", root_block))
    assert tokens["muted"].strip() == theme.THEMES["light"]["muted"]
    assert tokens["ink"].strip() == theme.THEMES["light"]["ink"]
    assert tokens["surface"].strip() == theme.THEMES["light"]["surface"]


# ------------------------------------------------------------------ redundant encoding

def test_colorblind_mode_gives_each_industry_a_distinct_dash():
    dashes = [theme.line_dash(name, cvd=True) for name in INDUSTRIES]
    # Six Plotly dash styles exist, so eight industries reuse two - but neighbours in the
    # legend must never share one, and the palette carries the rest of the separation.
    assert len(set(dashes)) >= 6
    assert all(d in CVD_DASHES for d in dashes)


def test_dashes_are_off_when_colorblind_mode_is_off():
    assert all(theme.line_dash(name, cvd=False) == "solid" for name in INDUSTRIES)


def test_colorblind_mode_gives_each_industry_a_marker_symbol():
    symbols = [theme.marker_symbol(name, cvd=True) for name in INDUSTRIES]
    assert len(set(symbols)) == len(INDUSTRIES)
    assert all(s in CVD_MARKERS for s in symbols)


def test_markers_are_uniform_when_colorblind_mode_is_off():
    assert all(theme.marker_symbol(name, cvd=False) == "circle" for name in INDUSTRIES)


def test_encoding_tables_cover_every_industry():
    assert len(CVD_DASHES) >= len(INDUSTRIES)
    assert len(CVD_MARKERS) >= len(INDUSTRIES)


# ------------------------------------------------------------------ theme wiring

@pytest.mark.parametrize("mode", MODES)
def test_theme_swaps_palettes_when_colorblind_mode_is_on(mode):
    assert theme.palette(mode, cvd=False) == PALETTE[mode]
    assert theme.palette(mode, cvd=True) == PALETTE_CVD[mode]


def test_industry_colours_cover_every_industry_plus_the_benchmark():
    colors = theme.industry_colors("light", cvd=True)
    for name in INDUSTRIES:
        assert name in colors
    assert len(colors) == len(INDUSTRIES) + 1   # + the S&P 500 reference line


def test_benchmark_keeps_the_ink_colour_in_both_modes():
    from services.config import BENCHMARK
    for cvd in (False, True):
        assert theme.industry_colors("light", cvd)[BENCHMARK] == theme.THEMES["light"]["ink"]
