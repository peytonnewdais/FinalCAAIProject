"""Accessibility statement: what this app does for access, and where it still falls short.

AI usage: see docs/AI_USAGE.md.
"""
from __future__ import annotations

import dash
from dash import html

from services import config
from services.a11y import PALETTE_CVD
from services.ui import page_head

dash.register_page(__name__, path="/accessibility", name="Accessibility",
                   title=f"Accessibility | {config.APP_TITLE}")

DONE = [
    ("Keyboard", "Every control - navigation, dropdowns, sliders, radio groups, buttons - is "
                 "reachable and operable by keyboard. A 'Skip to main content' link is the first "
                 "tab stop, and focus is always shown with a 3:1 outline rather than being "
                 "silently removed."),
    ("Colour contrast", "Body text, tile labels, table headers and chart tick labels all meet the "
                        "WCAG AA 4.5:1 minimum; chart series and control outlines meet the 3:1 "
                        "minimum for non-text. The thresholds are re-checked by an automated test, "
                        "so a future colour change that breaks them fails the build."),
    ("Colour is never the only cue", "Gains and losses carry a + or - sign as well as a colour. "
                                     "The current page is marked with a pill, an underline and "
                                     "hidden text, not colour alone. In colourblind mode each "
                                     "chart series also gets its own dash pattern."),
    ("Charts have text alternatives", "Plotly draws to SVG with no built-in description, so every "
                                      "figure carries a written summary of what it currently "
                                      "shows - the series, the date range and the ranked ending "
                                      "values - updated whenever the chart updates."),
    ("Structure", "One <h1> per page, landmarks for header, navigation, main and footer, real "
                  "table headers with scope, labelled control groups, and a page <title> that "
                  "names the section."),
    ("Motion and zoom", "Animation is dropped entirely for anyone whose system asks to reduce "
                        "motion. Text reflows to 320px and honours the browser's own font size, "
                        "and pinch zoom is never blocked."),
    ("Status messages", "Errors and finished analyses are announced to screen readers without "
                        "moving focus."),
]

LIMITS = [
    "The charts are Plotly figures. They can be focused and their toolbar is reachable, but "
    "reading individual data points by keyboard is limited by Plotly itself. The written summary "
    "under each chart, and the data tables on the Compare and Forecast pages, are the reliable "
    "route to the same numbers.",
    "The default palette is tuned for contrast and for the project's visual identity, not for "
    "colour blindness - eight hues cannot be told apart under dichromacy however they are chosen. "
    "Colourblind mode is the supported path, and it changes both the palette and the line shapes.",
    "Claude-written summaries are generated text. They are labelled as such, but their reading "
    "level is not controlled and they may be longer than the rest of the page.",
]


def layout():
    return html.Div([
        page_head(
            "Accessibility",
            "This project targets WCAG 2.1 Level AA. Below is what that means in practice, "
            "what has been verified, and what is still imperfect.",
            eyebrow="Statement",
        ),

        html.Div(className="card", children=[
            html.H2("Two display modes"),
            html.P("Both are in the header on every page, and both are remembered in your "
                   "browser between visits."),
            html.Ul([
                html.Li([html.Strong("Theme"), " - light or dark. If you have never chosen, "
                         "the app follows your operating system setting."]),
                html.Li([html.Strong("Colourblind"), " - swaps in a palette optimised so the "
                         f"{len(PALETTE_CVD['light'])} industry colours stay as far apart as "
                         "possible under protanopia, deuteranopia and tritanopia, and gives "
                         "every line its own dash pattern so hue stops mattering at all."]),
            ]),
        ]),

        html.Div(className="card", children=[
            html.H2("What has been done"),
            html.Dl(className="a11y-list", children=[
                item for label, text in DONE
                for item in (html.Dt(label), html.Dd(text))
            ]),
        ]),

        html.Div(className="card", children=[
            html.H2("Known limitations"),
            html.Ul([html.Li(text) for text in LIMITS]),
        ]),

        html.Div(className="card", children=[
            html.H2("How this was checked"),
            html.P("Contrast ratios and colour-blindness separation are computed from the actual "
                   "palette values by an automated test (tests/test_a11y.py), which fails if any "
                   "colour drops below its threshold. Keyboard order, focus visibility and screen "
                   "reader output were checked by hand."),
            html.P([
                "Found something we missed? Tell us at ",
                html.A("the project repository", href="https://github.com", target="_blank",
                       rel="noopener"),
                " and we will fix it.",
            ]),
        ]),
    ])
