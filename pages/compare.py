"""Compare page: two companies, their AI language on SEC EDGAR, and their stock returns."""
from __future__ import annotations

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

from services import ai_summary, config, edgar, theme
from services.market_data import period_start, price_stats, rebase, ticker_series
from services.ui import GRAPH_CONFIG, control, notice, num, page_head, pct, summary_block, table, tile, tone

dash.register_page(__name__, path="/compare", name="Compare stocks",
                   title=f"Compare stocks | {config.APP_TITLE}")

OPTIONS = [
    {"label": f"{t}  ·  {config.COMPANY_NAMES[t]}  ({industry})", "value": t}
    for industry, tickers in config.INDUSTRIES.items() for t in tickers
]
DEFAULT_A, DEFAULT_B = "NVDA", "ACN"


def layout():
    return html.Div([
        page_head(
            "Compare two stocks: AI adoption versus the share price",
            "We download each company's last five annual reports (10-K or 20-F) from SEC EDGAR, "
            "count how often they discuss artificial intelligence, pull R&D spending from XBRL, "
            "and set that against total return over the chosen period. Claude then writes the "
            "comparison from those numbers and the filing excerpts.",
            eyebrow="Company deep dive",
        ),

        html.Div(className="card", children=[
            html.Div(className="controls", children=[
                control("Stock A", dcc.Dropdown(id="cmp-a", options=OPTIONS, value=DEFAULT_A,
                                                clearable=False), grow=True),
                control("Stock B", dcc.Dropdown(id="cmp-b", options=OPTIONS, value=DEFAULT_B,
                                                clearable=False), grow=True),
                control("Price period", dcc.RadioItems(
                    id="cmp-period", value="boom",
                    options=[{"label": label, "value": key} for key, label in config.PERIODS.items()],
                )),
                html.Button("Analyze", id="cmp-run", n_clicks=0, className="btn btn-primary"),
            ]),
            html.P("The first analysis of a company downloads its filings from EDGAR "
                   "(roughly 10-20 seconds). Everything is cached afterwards.",
                   className="muted small", style={"marginTop": "12px"}),
        ]),

        dcc.Store(id="cmp-data"),
        html.Div(id="cmp-error"),

        dcc.Loading(type="circle", color="#2a78d6", delay_show=300, children=[
            html.Div(id="cmp-tiles", className="tiles"),
            html.Div(className="grid-2", children=[
                html.Div(className="card", children=dcc.Graph(
                    id="cmp-price", config=GRAPH_CONFIG, style={"height": "420px"})),
                html.Div(className="card", children=dcc.Graph(
                    id="cmp-mentions", config=GRAPH_CONFIG, style={"height": "420px"})),
            ]),
            html.Div(id="cmp-rd-card", className="card", children=dcc.Graph(
                id="cmp-rd", config=GRAPH_CONFIG, style={"height": "340px"})),
        ]),

        html.Div(className="card", children=[
            html.H3("Claude's read"),
            dcc.Loading(type="dot", color="#2a78d6", delay_show=300,
                        children=html.Div(id="cmp-summary")),
        ]),

        html.Div(className="card", children=[
            html.H3("Filings analyzed"),
            html.P("Mentions count every occurrence of: artificial intelligence, AI, machine "
                   "learning, generative AI, large language model / LLM, deep learning, neural "
                   "network. Density normalises for document length.", className="muted small"),
            html.Div(id="cmp-filings", className="table-wrap"),
        ]),
    ])


# ----------------------------------------------------------------- data


@callback(
    Output("cmp-data", "data"),
    Output("cmp-error", "children"),
    Input("cmp-run", "n_clicks"),
    State("cmp-a", "value"),
    State("cmp-b", "value"),
    State("cmp-period", "value"),
)
def run_analysis(_clicks, ticker_a, ticker_b, period):
    if not ticker_a or not ticker_b:
        return None, notice("Pick two companies to compare.", "error")
    if ticker_a == ticker_b:
        return None, notice("Pick two different companies.", "error")

    start = period_start(period)
    try:
        profile_a = edgar.company_ai_profile(ticker_a)
        profile_b = edgar.company_ai_profile(ticker_b)
    except edgar.EdgarError as exc:
        return None, notice(f"SEC EDGAR problem: {exc}", "error")
    except Exception as exc:  # network hiccups, malformed filings
        return None, notice(f"Could not analyze filings: {exc}", "error")

    data = {
        "a": ticker_a,
        "b": ticker_b,
        "period": period,
        "period_label": config.PERIODS[period],
        "start": start.date().isoformat(),
        "profiles": {ticker_a: profile_a, ticker_b: profile_b},
        "stats": {
            ticker_a: price_stats(ticker_a, start),
            ticker_b: price_stats(ticker_b, start),
            config.BENCHMARK_TICKER: price_stats(config.BENCHMARK_TICKER, start),
        },
    }
    return data, None


# ----------------------------------------------------------------- figures


def _latest_and_first(profile: dict):
    filings = profile["filings"]
    return filings[-1], filings[0]


@callback(
    Output("cmp-tiles", "children"),
    Output("cmp-price", "figure"),
    Output("cmp-mentions", "figure"),
    Output("cmp-rd", "figure"),
    Output("cmp-rd-card", "style"),
    Output("cmp-filings", "children"),
    Input("cmp-data", "data"),
    Input("theme", "data"),
)
def render(data, theme_key):
    if not data:
        empty = theme.empty(theme_key, "Run an analysis to see results")
        return [], empty, empty, empty, {"display": "none"}, None

    a, b = data["a"], data["b"]
    pa, pb = data["profiles"][a], data["profiles"][b]
    stats = data["stats"]
    color_a, color_b = theme.slot(theme_key, 0), theme.slot(theme_key, 1)
    t = theme.tokens(theme_key)

    # --- tiles
    la, fa = _latest_and_first(pa)
    lb, fb = _latest_and_first(pb)
    tiles = [
        tile(f"{a} total return", pct(stats[a].get("total_return_pct")),
             data["period_label"], tone(stats[a].get("total_return_pct"))),
        tile(f"{b} total return", pct(stats[b].get("total_return_pct")),
             data["period_label"], tone(stats[b].get("total_return_pct"))),
        tile("S&P 500 total return", pct(stats["SPY"].get("total_return_pct")),
             data["period_label"], tone(stats["SPY"].get("total_return_pct"))),
        tile(f"{a} AI mentions / 10k words", num(la["mentions_per_10k_words"]),
             f"FY{la['fiscal_year']}, was {num(fa['mentions_per_10k_words'])} in FY{fa['fiscal_year']}"),
        tile(f"{b} AI mentions / 10k words", num(lb["mentions_per_10k_words"]),
             f"FY{lb['fiscal_year']}, was {num(fb['mentions_per_10k_words'])} in FY{fb['fiscal_year']}"),
    ]

    # --- price chart (one axis, everything indexed to 100 at the period start)
    start = pd.Timestamp(data["start"])
    fig_price = go.Figure()
    for ticker, color, dash_style in ((a, color_a, "solid"), (b, color_b, "solid"),
                                      (config.BENCHMARK_TICKER, t["ink"], "dash")):
        series = rebase(ticker_series(ticker, start))
        label = config.BENCHMARK if ticker == config.BENCHMARK_TICKER else f"{ticker} · {config.COMPANY_NAMES[ticker]}"
        fig_price.add_trace(go.Scatter(
            x=series.index, y=series.values, name=label, mode="lines",
            line=dict(color=color, width=2, dash=dash_style),
            hovertemplate="%{y:,.0f}<extra>" + ticker + "</extra>",
        ))
    theme.add_event_lines(fig_price, start, stats["SPY"]["end_date"], theme_key)
    fig_price.add_hline(y=100, line_width=1, line_color=t["axis"])
    theme.apply(fig_price, theme_key, title="Share price, rebased to 100 at period start",
                hovermode="x unified", legend=dict(orientation="h", y=-0.2, title=""))

    # --- AI mentions per 10k words by fiscal year
    fig_mentions = go.Figure()
    for profile, color in ((pa, color_a), (pb, color_b)):
        fig_mentions.add_trace(go.Bar(
            x=[f"FY{f['fiscal_year']}" for f in profile["filings"]],
            y=[f["mentions_per_10k_words"] for f in profile["filings"]],
            name=f"{profile['ticker']} · {profile['name']}",
            marker=dict(color=color, line=dict(width=0)),
            text=[f"{f['mentions_per_10k_words']:.1f}" for f in profile["filings"]],
            textposition="outside", textfont=dict(color=t["ink"], size=11), cliponaxis=False,
            customdata=[f["ai_mentions"] for f in profile["filings"]],
            hovertemplate="%{x}: %{y:.1f} per 10k words (%{customdata} mentions)<extra>"
                          + profile["ticker"] + "</extra>",
        ))
    fig_mentions.update_xaxes(categoryorder="category ascending", title="")
    fig_mentions.update_yaxes(title="Mentions per 10,000 words", rangemode="tozero")
    theme.apply(fig_mentions, theme_key, title="How much each annual report talks about AI",
                barmode="group", bargap=0.3, bargroupgap=0.08,
                legend=dict(orientation="h", y=-0.2, title=""))

    # --- R&D intensity (only when at least one company reports it)
    fig_rd = go.Figure()
    has_rd = False
    for profile, color in ((pa, color_a), (pb, color_b)):
        points = [(f["fiscal_year"], f["financials"]["rd_pct_of_revenue"]) for f in profile["filings"]
                  if f.get("financials") and f["financials"].get("rd_pct_of_revenue") is not None]
        if not points:
            continue
        has_rd = True
        fig_rd.add_trace(go.Scatter(
            x=[f"FY{y}" for y, _ in points], y=[v for _, v in points],
            name=f"{profile['ticker']} · {profile['name']}", mode="lines+markers",
            line=dict(color=color, width=2), marker=dict(size=9),
            hovertemplate="%{x}: %{y:.1f}% of revenue<extra>" + profile["ticker"] + "</extra>",
        ))
    fig_rd.update_yaxes(title="R&D as % of revenue", rangemode="tozero")
    fig_rd.update_xaxes(title="", categoryorder="category ascending")
    theme.apply(fig_rd, theme_key, title="R&D spending as a share of revenue (XBRL company facts)",
                hovermode="x unified", legend=dict(orientation="h", y=-0.25, title=""))
    rd_style = {} if has_rd else {"display": "none"}

    # --- filings table
    rows = []
    for profile in (pa, pb):
        for f in profile["filings"]:
            money = f.get("financials") or {}
            rows.append([
                f"{profile['ticker']} · {profile['name']}",
                f"FY{f['fiscal_year']}", f["form"], f["filing_date"],
                f"{f['word_count']:,}", f"{f['ai_mentions']:,}",
                num(f["mentions_per_10k_words"]),
                pct(money.get("rd_pct_of_revenue"), sign=False) if money.get("rd_pct_of_revenue") is not None else "n/a",
                html.A("Open on EDGAR", href=f["url"], target="_blank", rel="noopener"),
            ])
    filings_table = table(
        ["Company", "Fiscal year", "Form", "Filed", "Words", "AI mentions", "Per 10k words",
         "R&D % of revenue", "Source"],
        rows, numeric_from=4,
    )

    return tiles, fig_price, fig_mentions, fig_rd, rd_style, filings_table


# ----------------------------------------------------------------- Claude summary


@callback(Output("cmp-summary", "children"), Input("cmp-data", "data"))
def render_summary(data):
    if not data:
        return html.P("Run an analysis to get Claude's comparison.", className="muted")
    a, b = data["a"], data["b"]
    try:
        result = ai_summary.compare_companies(
            data["profiles"][a], data["profiles"][b],
            data["stats"][a], data["stats"][b], data["stats"]["SPY"], data["period_label"],
        )
    except ai_summary.SummaryUnavailable as exc:
        return notice(str(exc))
    return summary_block(result)
