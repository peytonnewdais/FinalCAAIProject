"""Home page: the question we asked, the headline numbers, and links to the other pages.

The small trend lines on the tiles and the big one behind the heading are drawn
as SVG by hand (see sparkline below) rather than with Plotly, because they carry
no axes or labels and only need to be a shape.
"""
import base64

import dash
from dash import dcc, html

from services import config
from services.market_data import industry_index, last_updated, rebase, scorecard

dash.register_page(__name__, path="/", name="Home")

# The three pages the home page links to, each with a Font Awesome icon name.
CARDS = [
    ("/industries", "fa-chart-line", "Industries",
     "Eight industry baskets rebased to 100 and compared against the S&P 500, with the "
     "key AI moments marked on the chart."),
    ("/compare", "fa-scale-balanced", "Compare Stocks",
     "Pick any two companies. We read their last five annual reports from SEC EDGAR, count "
     "how much they talk about AI, and ask Claude to weigh that against the share price."),
    ("/forecast", "fa-arrow-trend-up", "Forecast",
     "A drift-and-volatility cone for every industry index, plus a Claude outlook on what "
     "the numbers do and do not say."),
]

WIN_GREEN = "#0a7a2f"
LOSE_RED = "#c4302b"


def thin_out(series, count=44):
    """Keep about `count` evenly spaced points. A sparkline needs a shape, not every day."""
    step = max(len(series) // count, 1)
    return [float(v) for v in series.iloc[::step]]


def sparkline(lines, width=72, height=28, stroke=2.2):
    """Draw trend lines as an SVG image, returned as a data: URI for html.Img.

    `lines` is a list of (values, color, dash), where dash is None for a solid line
    or an SVG dash pattern like "7 6". All the lines share one scale so they can be
    compared against each other.
    """
    everything = [v for values, _, _ in lines for v in values]
    low, high = min(everything), max(everything)
    span = (high - low) or 1.0        # a perfectly flat line would divide by zero
    pad = stroke

    shapes = []
    for values, color, dash in lines:
        # x spreads the points evenly; y is flipped because SVG counts down from the top.
        step = (width - 2 * pad) / (len(values) - 1) if len(values) > 1 else 0
        points = " ".join(
            f"{pad + i * step:.1f},{height - pad - (v - low) / span * (height - 2 * pad):.1f}"
            for i, v in enumerate(values)
        )
        pattern = f' stroke-dasharray="{dash}"' if dash else ""
        shapes.append(f'<polyline fill="none" stroke="{color}" stroke-width="{stroke:g}" '
                      f'stroke-linecap="round" stroke-linejoin="round"{pattern} '
                      f'points="{points}"/>')

    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" '
           f'preserveAspectRatio="none">{"".join(shapes)}</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def banner_chart():
    """The big decorative line behind the heading: the AI industries against the S&P 500."""
    window = rebase(industry_index().loc[config.BOOM_START:])
    ai_average = window.drop(columns=[config.BENCHMARK]).mean(axis=1)
    return sparkline(
        [(thin_out(window[config.BENCHMARK]), "#94a3b8", "7 6"),
         (thin_out(ai_average), "#1f73d0", None)],
        width=620, height=200, stroke=3,
    )


def tile(label, value, sub, color="", spark=None):
    """One small box showing a single number, optionally with a trend line beside it."""
    number = html.Div(value, className=f"value {color}")
    if spark:
        number = html.Div(className="value-row", children=[
            number,
            html.Img(src=spark, className="tile-spark", alt=""),   # decorative only
        ])
    return html.Div(className="tile", children=[
        html.Div(label, className="label"),
        number,
        html.Div(sub, className="sub"),
    ])


def layout():
    scores = scorecard()
    industries = scores.drop(config.BENCHMARK)      # the S&P 500 is not an industry
    best = industries.idxmax()
    worst = industries.idxmin()
    benchmark = scores[config.BENCHMARK]

    index = industry_index()
    best_spark = sparkline([(thin_out(rebase(index[best]), 30), WIN_GREEN, None)], stroke=2.4)
    worst_spark = sparkline([(thin_out(rebase(index[worst]), 30), LOSE_RED, None)], stroke=2.4)

    return html.Div([
        html.Div(className="banner", children=[
            html.Img(src=banner_chart(), className="banner-chart", alt=""),
            html.Div(className="banner-text", children=[
                html.H1("Did the AI boom reward the companies that embraced it?"),
                html.P([
                    "ChatGPT launched on ", html.Strong("November 30, 2022"),
                    ". Since then, ", html.Strong("forty large companies"), " across ",
                    html.Strong("eight industries"), " have taken very different paths. This "
                    "dashboard compares their stock performance, reads what they tell the SEC "
                    "about artificial intelligence, and projects where each industry could "
                    "go next.",
                ]),
            ]),
        ]),

        html.Div(className="tiles", children=[
            tile("Biggest winner since the boom", f"{industries[best]:+,.0f}%", best,
                 "up", best_spark),
            tile("Biggest loser since the boom", f"{industries[worst]:+,.0f}%", worst,
                 "down", worst_spark),
            tile("S&P 500 over the same stretch", f"{benchmark:+,.0f}%", "SPY",
                 "up" if benchmark > 0 else "down"),
            tile("Companies tracked", str(len(config.COMPANY_TICKERS)),
                 f"{len(config.INDUSTRIES)} industries, 5 each"),
            tile("Prices as of", last_updated(), "Yahoo Finance"),
        ]),

        html.H2("Where to go next"),
        html.Div([
            dcc.Link(className="link-card", href=path, children=[
                # The heading right below says the same thing, so the icon is hidden
                # from screen readers instead of being read out twice.
                html.Span(className="icon", **{"aria-hidden": "true"},
                          children=html.I(className=f"fa-solid {icon}")),
                html.H3(title),
                html.P(text, className="muted"),
            ])
            for path, icon, title, text in CARDS
        ]),

        html.Div(className="card", children=[
            html.H3("The story"),
            html.P("We took the five largest companies in each of eight industries the AI boom "
                   "touched, from chip makers to the outsourcing and content businesses that AI "
                   "threatens. Each industry becomes an equal-weight index starting at 100 in "
                   "October 2022, one month before ChatGPT, so every line shares the same "
                   "starting point."),
            html.P("This was not a rising tide that lifted every industry equally. Semiconductors "
                   "climbed to many times their starting value while IT services and content "
                   "businesses lost most of theirs."),
        ]),

        html.Div(className="card", children=[
            html.H3("How the analysis works"),
            html.Ol([
                html.Li("Daily prices come from Yahoo Finance and are cached once a day."),
                html.Li("Each industry index is the average of its five rebased stocks."),
                html.Li("For any two companies we pull their last five annual reports from SEC "
                        "EDGAR and count the AI words."),
                html.Li("Claude reads those counts, the filing excerpts and the returns, and "
                        "writes the comparison."),
                html.Li("Forecasts measure a trend and a volatility, then project a cone forward."),
            ]),
        ]),
    ])
