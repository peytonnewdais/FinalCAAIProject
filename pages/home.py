"""Home page: the question, headline numbers, and where to go next.

AI usage: see docs/AI_USAGE.md.
"""
from __future__ import annotations

import dash
from dash import dcc, html

from services import config
from services.market_data import last_updated, scorecard
from services.ui import pct, tile, tone

dash.register_page(__name__, path="/", name="Home", title=f"{config.APP_TITLE}")

CARDS = [
    ("/industries", "📈", "Industries",
     "The original chart: eight industry baskets rebased to 100 against the S&P 500, "
     "with the key AI-boom moments marked."),
    ("/compare", "🔍", "Compare stocks",
     "Pick any two companies. We read their last five annual reports from SEC EDGAR, "
     "measure how much they talk about AI, and let Claude weigh that against the share price."),
    ("/forecast", "🔮", "Forecast",
     "A drift-and-volatility cone for every industry index, with an optional Claude outlook "
     "on what the numbers do and do not say."),
]


def layout():
    scores = scorecard()
    industries = scores.drop(config.BENCHMARK)
    best, worst = industries.idxmax(), industries.idxmin()
    benchmark = float(scores[config.BENCHMARK])

    return html.Div([
        html.Section(className="hero", children=[
            html.P("Team 8 final project", className="eyebrow"),
            html.H1("Did the AI boom reward the companies that embraced it?"),
            html.P(className="lead", children=(
                "ChatGPT launched on November 30, 2022. Since then, forty large companies across "
                "eight industries have taken very different paths. This dashboard compares their "
                "stock performance, reads what they tell the SEC about artificial intelligence, "
                "and projects where each industry could go next."
            )),
            html.Div(className="hero-actions", children=[
                dcc.Link("Explore industries", href="/industries", className="btn btn-primary"),
                dcc.Link("Compare two stocks", href="/compare", className="btn"),
                dcc.Link("See forecasts", href="/forecast", className="btn"),
            ]),
        ]),

        html.Section(className="tiles", children=[
            tile("Biggest winner since the boom", pct(float(industries[best]), 0), best, tone(industries[best])),
            tile("Biggest loser since the boom", pct(float(industries[worst]), 0), worst, tone(industries[worst])),
            tile("S&P 500 over the same stretch", pct(benchmark, 0), "SPY, adjusted close", tone(benchmark)),
            tile("Companies tracked", str(len(config.COMPANY_TICKERS)),
                 f"{len(config.INDUSTRIES)} industries, 5 each"),
            tile("Prices as of", last_updated(), "Yahoo Finance via yfinance"),
        ]),

        html.Section(className="card-grid", children=[
            dcc.Link(href=path, className="link-card", children=[
                # The heading right below says the same thing; without this a screen reader
                # reads "chart increasing, Industries".
                html.Div(icon, className="icon", **{"aria-hidden": "true"}),
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
