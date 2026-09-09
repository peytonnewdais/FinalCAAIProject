"""Home page: the question, headline numbers, and where to go next.

AI usage: see docs/AI_USAGE.md.
"""
from __future__ import annotations

import dash
from dash import dcc, html

from services import config
from services.market_data import industry_index, last_updated, rebase, scorecard
from services.ui import multi_sparkline_uri, pct, sparkline_uri, tile, tone

dash.register_page(__name__, path="/", name="Home", title=f"{config.APP_TITLE}")

CARDS = [
    ("/industries", "fa-chart-line", "Industries",
     "The original chart: eight industry baskets rebased to 100 against the S&P 500, "
     "with the key AI-boom moments marked."),
    ("/compare", "fa-scale-balanced", "Compare stocks",
     "Pick any two companies. We read their last five annual reports from SEC EDGAR, "
     "measure how much they talk about AI, and let Claude weigh that against the share price."),
    ("/forecast", "fa-arrow-trend-up", "Forecast",
     "A drift-and-volatility cone for every industry index, with an optional Claude outlook "
     "on what the numbers do and do not say."),
]

# Vivid green/red for the winner and loser stats, matched to the CSS --good/--bad tokens.
WIN_GREEN = "#059669"
LOSE_RED = "#dc2626"


def _downsample(series, count: int = 44) -> list[float]:
    step = max(len(series) // count, 1)
    return [float(v) for v in series.iloc[::step]]


def _hero_accent_chart() -> str:
    """Decorative background sparkline: a stylized AI-50 basket climbing past the S&P 500."""
    idx = industry_index()
    window = rebase(idx.loc[config.BOOM_START:])
    ai50 = window.drop(columns=[config.BENCHMARK]).mean(axis=1)
    return multi_sparkline_uri([
        (_downsample(window[config.BENCHMARK]), "#94a3b8", "7 6"),
        (_downsample(ai50), "#2a78d6", None),
    ])


def layout():
    scores = scorecard()
    industries = scores.drop(config.BENCHMARK)
    best, worst = industries.idxmax(), industries.idxmin()
    benchmark = float(scores[config.BENCHMARK])

    idx = industry_index()
    win_spark = sparkline_uri(_downsample(rebase(idx[best]), 30), WIN_GREEN, stroke=2.4)
    lose_spark = sparkline_uri(_downsample(rebase(idx[worst]), 30), LOSE_RED, stroke=2.4)

    return html.Div([
        html.Section(className="hero", children=[
            html.Img(src=_hero_accent_chart(), className="hero-accent-chart", alt=""),
            html.Div(className="hero-content", children=[
                html.P("Team 8 final project", className="eyebrow"),
                html.H1("Did the AI boom reward the companies that embraced it?"),
                html.P(className="lead", children=[
                    "ChatGPT launched on ", html.Strong("November 30, 2022"),
                    ". Since then, ", html.Strong("forty large companies"), " across ",
                    html.Strong("eight industries"), " have taken very different paths. This "
                    "dashboard compares their stock performance, reads what they tell the SEC "
                    "about artificial intelligence, and projects where each industry could go next.",
                ]),
                html.Div(className="hero-actions", children=[
                    dcc.Link("Explore industries", href="/industries", className="btn btn-primary"),
                    dcc.Link("Compare two stocks", href="/compare", className="btn"),
                    dcc.Link("See forecasts", href="/forecast", className="btn"),
                ]),
            ]),
        ]),

        html.Section(className="tiles", children=[
            tile("Biggest winner since the boom", pct(float(industries[best]), 0), best,
                 tone(industries[best]), variant="tile--up", spark=win_spark, emphasis=True),
            tile("Biggest loser since the boom", pct(float(industries[worst]), 0), worst,
                 tone(industries[worst]), variant="tile--down", spark=lose_spark, emphasis=True),
            tile("S&P 500 over the same stretch", pct(benchmark, 0), "SPY, adjusted close",
                 tone(benchmark), variant="tile--accent"),
            tile("Companies tracked", str(len(config.COMPANY_TICKERS)),
                 f"{len(config.INDUSTRIES)} industries, 5 each", variant="tile--neutral"),
            tile("Prices as of", last_updated(), "Yahoo Finance via yfinance",
                 variant="tile--neutral"),
        ]),

        html.Section(className="card-grid", children=[
            dcc.Link(href=path, className="link-card", children=[
                # Font Awesome glyph; the heading below says the same thing, so the
                # icon is hidden from screen readers.
                html.Span(className="icon", **{"aria-hidden": "true"},
                          children=html.I(className=f"fa-solid {icon}")),
                html.H3(title),
                html.P(text, className="muted"),
                html.Span("Open →", className="go"),
            ])
            for path, icon, title, text in CARDS
        ]),

        html.Section(className="grid-2", children=[
            html.Div(className="card", children=[
                html.H3("The story"),
                html.P(
                    "We took the five largest companies in each of eight industries that the AI "
                    "boom touched most, from chip makers to the outsourcing and content businesses "
                    "that AI threatens. Each industry becomes an equal-weight index starting at 100 "
                    "in October 2022, one month before ChatGPT, so every line shares the same "
                    "pre-boom baseline."
                ),
                html.P(
                    "This was not a rising tide that lifted every industry equally. It was a transfer "
                    "of wealth: semiconductors climbed to many times their starting value while IT "
                    "services and content businesses lost most of theirs."
                ),
            ]),
            html.Div(className="card", children=[
                html.H3("How the analysis works"),
                html.Ol(className="steps", children=[
                    html.Li("Daily adjusted closes come from Yahoo Finance and are cached once a day."),
                    html.Li("Industry indices are the equal-weight mean of five rebased tickers."),
                    html.Li("For any two companies, the last five annual reports (10-K or 20-F) are "
                            "pulled from SEC EDGAR and scanned for AI terms; XBRL facts add R&D spend."),
                    html.Li("Claude reads the counts, the filing excerpts, and the returns, and writes "
                            "a grounded comparison."),
                    html.Li("Forecasts fit a drift and volatility to each index and project a "
                            "lognormal cone forward."),
                ]),
            ]),
        ]),
    ])
