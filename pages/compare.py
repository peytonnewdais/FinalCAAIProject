"""Compare page: two companies, how much their SEC filings talk about AI, and how
their share prices did.

Pressing Analyze downloads the filings (slow the first time, cached afterwards),
stores the results in a dcc.Store, and the charts below read from that store.
"""
import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

from services import ai_summary, config, edgar
from services.market_data import period_start, price_stats, rebase, ticker_series

dash.register_page(__name__, path="/compare", name="Compare Stocks")

OPTIONS = [{"label": f"{t} - {config.COMPANY_NAMES[t]} ({industry})", "value": t}
           for industry, tickers in config.INDUSTRIES.items() for t in tickers]

COLOR_A = "#1f73d0"
COLOR_B = "#eb6834"

# initialize tiles for comparison
def tile(label, value, sub, color=""):
    """One small box showing a single number."""
    return html.Div(className="tile", children=[
        html.Div(label, className="label"),
        html.Div(value, className=f"value {color}"),
        html.Div(sub, className="sub"),
    ])

#Compute numbers as a percentage 
def percent(value):
    """Format a number as a percentage, or 'n/a' when it is missing."""
    return "n/a" if value is None else f"{value:+,.1f}%"

# create page layout
def layout():
    return html.Div([
        html.H1("Compare two stocks: AI adoption versus the share price"),
        html.P("We download each company's last five annual reports (10-K or 20-F) from SEC "
               "EDGAR, count how often they discuss artificial intelligence, and set that "
               "against the total return over the period you choose. Claude then writes the "
               "comparison from those numbers."),

        html.Div(className="card", children=[
            html.Div(className="controls", children=[
                html.Div(className="control", children=[
                    html.Label("Stock A"),
                    dcc.Dropdown(id="stock-a", options=OPTIONS, value="NVDA", clearable=False),
                ]),
                html.Div(className="control", children=[
                    html.Label("Stock B"),
                    dcc.Dropdown(id="stock-b", options=OPTIONS, value="ACN", clearable=False),
                ]),
                html.Div(className="control", children=[
                    html.Label("Price period"),
                    dcc.RadioItems(
                        id="period", value="boom",
                        options=[{"label": label, "value": key}
                                 for key, label in config.PERIODS.items()]),
                ]),
                html.Button("Analyze", id="analyze", n_clicks=0, className="button"),
            ]),
            html.P("The first analysis of a company downloads its filings from EDGAR, which "
                   "takes about 10-20 seconds. After that everything is cached.",
                   className="muted small"),
        ]),

        # Pressing Analyze downloads filings from EDGAR, which is the slow part.
        # This dcc.Loading wraps that callback's own outputs, so the spinner shows
        # up the moment the button is pressed and stays until the data is back.
        # The charts further down have their own spinner, but they only redraw
        # from the store, which is fast.
        # custom_spinner replaces the default dot with the spinning ring from
        # styles.css plus a line saying what is actually happening, because the
        # EDGAR download is long enough that a bare dot looks like a hang.
        dcc.Loading(
            delay_show=200,
            custom_spinner=html.Div(className="loading-note", children=[
                html.Span(className="spinner"),
                "Reading annual reports from SEC EDGAR...",
            ]),
            children=[
                dcc.Store(id="analysis"),   # holds the results between callbacks
                html.Div(id="analyze-status", className="muted small"),
            ],
        ),
        html.Div(id="error-message"),

        dcc.Loading(children=[
            html.Div(id="compare-tiles", className="tiles"),
            html.Div(className="card", children=dcc.Graph(id="price-chart")),
            html.Div(className="card", children=[
                dcc.Graph(id="mentions-chart"),
                html.P("How this is counted: every occurrence of artificial intelligence, AI, "
                       "machine learning, generative AI, large language model / LLM, deep "
                       "learning and neural network, divided by the number of words in the "
                       "report and scaled to a rate per 10,000 words, so reports of different "
                       "lengths can be compared.", className="muted small"),
            ]),
        ]),

        html.Div(className="card", children=[
            html.H3("Claude's read"),
            dcc.Loading(html.Div(id="claude-summary")),
        ]),

        html.Div(className="card", children=[
            html.H3("Filings analyzed"),
            html.Div(id="filings-table", className="table-wrap"),
        ]),
    ])


# This callback does all the slow network work once - EDGAR filings and
# price history for both picks plus the S&P 500 - and stashes a plain dict in the "analysis"
# store. show_results and write_summary redraw from that store and never re-fetch.
#
# Everything in the returned dict must be JSON-serializable because it lives in a dcc.Store,
# hence str(start.date()) rather than a Timestamp. On any failure we write None to the store
# (downstream reads that as "nothing to show") and put a message in "error-message";
# on success we clear the error. n_clicks is only the trigger.
@callback(
    Output("analysis", "data"),
    Output("error-message", "children"),
    Output("analyze-status", "children"),
    Input("analyze", "n_clicks"),
    State("stock-a", "value"),
    State("stock-b", "value"),
    State("period", "value"),
)

# Takes the calls the edgar api to compare AI usage between both functions and 
def run_analysis(n_clicks, ticker_a, ticker_b, period):
    """Fetch the filings and the price statistics for both companies."""
    if ticker_a == ticker_b:
        return None, html.Div("Pick two different companies.", className="notice error"), ""

    start = period_start(period)
    try:
        profile_a = edgar.company_ai_profile(ticker_a)
        profile_b = edgar.company_ai_profile(ticker_b)
    except edgar.EdgarError as error:
        return None, html.Div(f"SEC EDGAR problem: {error}", className="notice error"), ""
    except Exception as error:                     # a dropped connection, a broken filing
        return None, html.Div(f"Could not analyze filings: {error}", className="notice error"), ""

    return {
        "a": ticker_a,
        "b": ticker_b,
        "period_label": config.PERIODS[period],
        "start": str(start.date()),
        "profiles": {ticker_a: profile_a, ticker_b: profile_b},
        "stats": {
            ticker_a: price_stats(ticker_a, start),
            ticker_b: price_stats(ticker_b, start),
            config.BENCHMARK_TICKER: price_stats(config.BENCHMARK_TICKER, start),
        },
    }, None, f"Analyzed {ticker_a} and {ticker_b} - {config.PERIODS[period]}."


@callback(
    Output("compare-tiles", "children"),
    Output("price-chart", "figure"),
    Output("mentions-chart", "figure"),
    Output("filings-table", "children"),
    Input("analysis", "data"),
)

#creates the chart comparing the usage between the two 
def show_results(data):
    """Draw everything from the stored analysis."""
    if not data:
        blank = go.Figure()
        blank.add_annotation(text="Press Analyze to see results", showarrow=False,
                             xref="paper", yref="paper", x=0.5, y=0.5)
        blank.update_xaxes(visible=False)
        blank.update_yaxes(visible=False)
        blank.update_layout(plot_bgcolor="white", paper_bgcolor="white", height=320)
        return [], blank, blank, None

    a, b = data["a"], data["b"]
    profile_a, profile_b = data["profiles"][a], data["profiles"][b]
    stats = data["stats"]
    label = data["period_label"]

    # --- the five tiles at the top
    latest_a, first_a = profile_a["filings"][-1], profile_a["filings"][0]
    latest_b, first_b = profile_b["filings"][-1], profile_b["filings"][0]
    tiles = [
        tile(f"{a} total return", percent(stats[a].get("total_return_pct")), label,
             "up" if stats[a].get("total_return_pct", 0) > 0 else "down"),
        tile(f"{b} total return", percent(stats[b].get("total_return_pct")), label,
             "up" if stats[b].get("total_return_pct", 0) > 0 else "down"),
        tile("S&P 500 total return", percent(stats["SPY"].get("total_return_pct")), label,
             "up" if stats["SPY"].get("total_return_pct", 0) > 0 else "down"),
        tile(f"{a} AI mentions / 10k words", f"{latest_a['mentions_per_10k_words']:,.1f}",
             f"FY{latest_a['fiscal_year']}, was {first_a['mentions_per_10k_words']:,.1f} "
             f"in FY{first_a['fiscal_year']}"),
        tile(f"{b} AI mentions / 10k words", f"{latest_b['mentions_per_10k_words']:,.1f}",
             f"FY{latest_b['fiscal_year']}, was {first_b['mentions_per_10k_words']:,.1f} "
             f"in FY{first_b['fiscal_year']}"),
    ]

    # --- share prices, all three rebased to 100 so they can share one axis 
    price_fig = go.Figure()
    for ticker, color in [(a, COLOR_A), (b, COLOR_B), (config.BENCHMARK_TICKER, "#33322f")]:
        series = rebase(ticker_series(ticker, pd.Timestamp(data["start"])))
        price_fig.add_trace(go.Scatter(
            x=series.index, y=series.values, mode="lines",
            name=f"{ticker} - {config.COMPANY_NAMES.get(ticker, 'S&P 500')}",
            line=dict(color=color, width=2,
                      dash="dash" if ticker == config.BENCHMARK_TICKER else "solid"),
        ))
    price_fig.add_hline(y=100, line_width=1, line_color="#c3c2b7")
    price_fig.update_layout(title="Share price, rebased to 100 at the start of the period",
                            hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white",
                            height=420, legend=dict(orientation="h", y=-0.18))
    price_fig.update_yaxes(gridcolor="#e1e0d9")

    # --- AI mentions per fiscal year, one pair of bars per year
    mentions_fig = go.Figure()
    for profile, color in [(profile_a, COLOR_A), (profile_b, COLOR_B)]:
        mentions_fig.add_trace(go.Bar(
            x=[f"FY{f['fiscal_year']}" for f in profile["filings"]],
            y=[f["mentions_per_10k_words"] for f in profile["filings"]],
            name=f"{profile['ticker']} - {profile['name']}",
            marker_color=color,
            text=[f"{f['mentions_per_10k_words']:.1f}" for f in profile["filings"]],
            textposition="outside", cliponaxis=False,
        ))
    mentions_fig.update_layout(title="How much each annual report talks about AI",
                               barmode="group", plot_bgcolor="white", paper_bgcolor="white",
                               height=420, legend=dict(orientation="h", y=-0.18))
    mentions_fig.update_yaxes(title="Mentions per 10,000 words", rangemode="tozero",
                              gridcolor="#e1e0d9")

    # --- one row per filing we read, all of company A's years then all of company B's
    # (not paired by year - the two companies can have different filing histories). The
    # "num" class right-aligns numeric cells; the header loop below tags columns 4+ with
    # it to match.
    header = ["Company", "Fiscal year", "Form", "Filed", "Words", "AI mentions",
              "Per 10k words", "Source"]
    rows = []
    for profile in [profile_a, profile_b]:
        for f in profile["filings"]:
            rows.append(html.Tr([
                html.Td(f"{profile['ticker']} - {profile['name']}"),
                html.Td(f"FY{f['fiscal_year']}"),
                html.Td(f["form"]),
                html.Td(f["filing_date"]),
                html.Td(f"{f['word_count']:,}", className="num"),
                html.Td(f"{f['ai_mentions']:,}", className="num"),
                html.Td(f"{f['mentions_per_10k_words']:,.1f}", className="num"),
                html.Td(html.A("Open on EDGAR", href=f["url"], target="_blank")),
            ]))

    table = html.Table(className="data", children=[
        # Columns 4 onward hold numbers, so their headers are right-aligned too.
        html.Thead(html.Tr([html.Th(name, className="num" if i >= 4 else "")
                            for i, name in enumerate(header)])),
        html.Tbody(rows),
    ])

    return tiles, price_fig, mentions_fig, table


# The only network call on this page after run_analysis. It re-runs whenever
# the "analysis" store changes and reads straight from it - no re-fetch. Every way the Claude
# call can fail (package missing, no API key, rate limit, API error) arrives as
# SummaryUnavailable and is shown as a plain notice rather than crashing the callback.
# ai_summary caches answers on disk keyed by a hash of model + effort + prompt, so a repeated
# comparison is free and gets tagged "(cached)"; answer["model"] is what the API actually ran.
@callback(Output("claude-summary", "children"), Input("analysis", "data"))
def write_summary(data):
    """Ask Claude to compare the two companies once the data is ready."""
    if not data:
        return html.P("Press Analyze to get Claude's comparison.", className="muted")

    a, b = data["a"], data["b"]
    try:
        answer = ai_summary.compare_companies(
            data["profiles"][a], data["profiles"][b],
            data["stats"][a], data["stats"][b], data["stats"]["SPY"], data["period_label"],
        )
    except ai_summary.SummaryUnavailable as error:
        return html.Div(str(error), className="notice")

    note = f"Written by {answer['model']}"
    if answer.get("cached"):
        note += " (cached)"
    return html.Div([
        dcc.Markdown(answer["text"]),
        html.P(note, className="muted small"),
    ])
