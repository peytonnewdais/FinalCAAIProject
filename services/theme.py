"""Theme tokens shared by the CSS in assets/style.css and every Plotly figure.

The page toggles ``data-theme`` on <html>; callbacks receive the same value from
the ``theme`` store and pass it here so figures repaint in the matching palette.

AI usage: see docs/AI_USAGE.md.
"""
from __future__ import annotations

import plotly.graph_objects as go

from .a11y import CVD_DASHES, CVD_MARKERS, PALETTE_CVD, resolve_cvd
from .config import BENCHMARK, INDUSTRIES, PALETTE

FONT = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

# These mirror the CSS custom properties in assets/style.css; the two must move together.
# "muted" paints axis tick labels, which are real text and so are held to 4.5:1 - that is
# why light mode uses #74726c rather than the #898781 the design started with.
THEMES = {
    "light": dict(
        template="plotly_white", surface="#fcfcfb", page="#f9f9f7",
        ink="#0b0b0b", ink2="#52514e", muted="#74726c", grid="#e1e0d9", axis="#c3c2b7",
        event="#8a8f9c", good="#006300", bad="#d03b3b",
    ),
    "dark": dict(
        template="plotly_dark", surface="#1a1a19", page="#0d0d0d",
        ink="#ffffff", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a", axis="#383835",
        event="#7b8397", good="#0ca30c", bad="#e66767",
    ),
}


def resolve(theme) -> str:
    """Normalise whatever the store holds ("dark", "light", None) to a theme key."""
    return "dark" if theme == "dark" else "light"


def tokens(theme) -> dict:
    return THEMES[resolve(theme)]


def palette(theme, cvd=False) -> list[str]:
    """The active categorical palette for this theme and colorblind setting."""
    source = PALETTE_CVD if resolve_cvd(cvd) else PALETTE
    return source[resolve(theme)]


def industry_colors(theme, cvd=False) -> dict:
    """Industry -> hex. The benchmark is a reference line and wears the ink color."""
    colors = dict(zip(INDUSTRIES, palette(theme, cvd)))
    colors[BENCHMARK] = tokens(theme)["ink"]
    return colors


def slot(theme, index: int, cvd=False) -> str:
    """Categorical slot color (0-based) for series that are not industries."""
    return palette(theme, cvd)[index]


def line_dash(name, cvd=False) -> str:
    """Dash pattern for a series.

    In colorblind mode every industry gets its own pattern, so a line stays identifiable
    without relying on hue at all (WCAG 1.4.1). Off, everything is solid as designed.
    """
    if not resolve_cvd(cvd):
        return "solid"
    order = list(INDUSTRIES)
    return CVD_DASHES[order.index(name) % len(CVD_DASHES)] if name in order else "solid"


def marker_symbol(name, cvd=False) -> str:
    """Marker shape for a series, used alongside line_dash in colorblind mode."""
    order = list(INDUSTRIES)
    if not resolve_cvd(cvd) or name not in order:
        return "circle"
    return CVD_MARKERS[order.index(name) % len(CVD_MARKERS)]


def rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


def apply(fig: go.Figure, theme, **layout) -> go.Figure:
    """Paint a figure for the given theme: surfaces, ink, hairline grid, legend."""
    t = tokens(theme)
    fig.update_layout(
        template=t["template"],
        paper_bgcolor=t["surface"],
        plot_bgcolor=t["surface"],
        font=dict(family=FONT, color=t["ink2"], size=13),
        title=dict(font=dict(color=t["ink"], size=16), x=0.01, xanchor="left"),
        hoverlabel=dict(bgcolor=t["surface"], bordercolor=t["axis"],
                        font=dict(family=FONT, color=t["ink"], size=12)),
        legend=dict(font=dict(color=t["ink2"]), bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=56, r=24, t=56, b=48),
    )
    axis_style = dict(
        gridcolor=t["grid"], gridwidth=1, zerolinecolor=t["axis"], linecolor=t["axis"],
        tickcolor=t["axis"], tickfont=dict(color=t["muted"]), title_font=dict(color=t["ink2"]),
        showline=False,
    )
    fig.update_xaxes(**axis_style)
    fig.update_yaxes(**axis_style)
    if layout:
        fig.update_layout(**layout)
    return fig


def add_event_lines(fig: go.Figure, start, end, theme) -> None:
    """Dotted vertical markers for the key AI-boom events inside [start, end].

    Labels alternate left/right of the line so neighbouring events don't collide.
    """
    import pandas as pd

    from .config import EVENTS

    t = tokens(theme)
    positions = ("top left", "top right")
    shown = 0
    for day, label in EVENTS:
        stamp = pd.Timestamp(day)
        if pd.Timestamp(start) <= stamp <= pd.Timestamp(end):
            fig.add_vline(x=stamp, line_width=1, line_dash="dot", line_color=t["event"],
                          annotation_text=label,
                          annotation_position=positions[shown % 2],
                          annotation_font=dict(size=10, color=t["muted"]))
            shown += 1


def empty(theme, message: str, height: int = 320) -> go.Figure:
    t = tokens(theme)
    fig = go.Figure()
    fig.add_annotation(text=message, showarrow=False, font=dict(color=t["muted"], size=14),
                       xref="paper", yref="paper", x=0.5, y=0.5)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return apply(fig, theme, height=height, margin=dict(l=20, r=20, t=20, b=20))
