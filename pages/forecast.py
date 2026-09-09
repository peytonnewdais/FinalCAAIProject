"""Forecast page: a drift-and-volatility cone for every industry index.

AI usage: see docs/AI_USAGE.md.
"""
from __future__ import annotations

import dash
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html
from plotly.subplots import make_subplots

from services import ai_summary, config, theme
from services.forecast import DRIFT_MODES, LOOKBACKS, forecast_all
from services.market_data import industry_index, scorecard
from services.ui import (GRAPH_CONFIG, chart, control, describe_ranked, notice, num, page_head,
                         pct, summary_block, table)

dash.register_page(__name__, path="/forecast", name="Forecast",
                   title=f"Forecast | {config.APP_TITLE}")

HISTORY_DAYS = 252  # one year of history shown before the cone
VIEW_OPTIONS = [{"label": "All industries (small multiples)", "value": "all"}] + [
    {"label": name, "value": name} for name in list(config.INDUSTRIES) + [config.BENCHMARK]
]


def layout():
    return html.Div([
        page_head(
            "Where could each industry go next?",
            "For every industry index we estimate a trend (drift) and a volatility from recent "
            "daily returns, then project a lognormal cone forward. The shaded bands are the "
            "50% and 80% ranges; the dashed line is the median path. Change the assumptions to "
            "see how fragile the picture is.",
            eyebrow="Statistical forecast",
        ),

        html.Div(className="card", children=[
            html.Div(className="controls", children=[
                control("View", dcc.Dropdown(id="fc-view", options=VIEW_OPTIONS, value="all",
                                             clearable=False), grow=True),
                control("Lookback for drift and volatility", dcc.RadioItems(
                    id="fc-lookback", value="2y",
                    options=[{"label": v, "value": k} for k, v in LOOKBACKS.items()])),
                control("Drift assumption", dcc.RadioItems(
                    id="fc-drift", value="half",
                    options=[{"label": v, "value": k} for k, v in DRIFT_MODES.items()])),
            ]),
            html.Div(className="slider-wrap", role="group",
                     **{"aria-labelledby": "fc-horizon-label"}, children=[
                         html.Label("Horizon", id="fc-horizon-label"),
                         dcc.Slider(id="fc-horizon", min=3, max=24, step=3, value=12,
                                    marks={m: f"{m} mo" for m in (3, 6, 9, 12, 15, 18, 21, 24)}),
                     ]),
        ]),

        html.Div(className="card", children=chart(dcc.Graph(
            id="fc-chart", config=GRAPH_CONFIG, style={"height": "72vh", "minHeight": "560px"}),
            "fc-chart-desc")),

        html.Div(className="card", children=[
            html.H3("Forecast table"),
            html.Div(id="fc-table", className="table-wrap"),
        ]),

        html.Div(className="card", children=[
            html.H3("Claude's outlook"),
            html.P("Claude reads the forecast statistics for every industry and explains what the "
                   "model is assuming, where it is most likely to be wrong, and what the ranges "
                   "mean. Generated on demand and cached for the current settings.",
                   className="muted"),
            html.Button("Generate outlook", id="fc-run", n_clicks=0, className="btn btn-primary"),
            dcc.Loading(type="dot", color="#2a78d6", delay_show=300,
                        children=html.Div(id="fc-summary", style={"marginTop": "16px"})),
        ]),

        html.Div(className="card", children=[
            html.H3("How the forecast works"),
            html.Ul([
                html.Li("Daily log returns over the lookback window give a mean (drift) and a "
                        "standard deviation (volatility)."),
                html.Li("Future log-price is treated as normal: mean = drift x days, variance = "
                        "volatility squared x days. That gives closed-form percentile paths, the "
                        "classic lognormal cone."),
                html.Li("The drift is the fragile input. 'Historical trend' extrapolates the "
                        "recent run; 'Half' shrinks it toward zero, a common hedge against "
                        "over-fitting a hot streak; 'No trend' is a pure random walk."),
                html.Li("Volatility is assumed constant and returns independent, so real markets "
                        "will see fatter tails and clustered moves than the cone suggests."),
                html.Li("This is a teaching tool, not investment advice."),
            ]),
        ]),
    ])


def _band(fig, paths, color, name, low, high, alpha, row=None, col=None, showlegend=False):
    kwargs = dict(row=row, col=col) if row else {}
    fig.add_trace(go.Scatter(x=paths.index, y=paths[high], mode="lines", line=dict(width=0),
                             hoverinfo="skip", showlegend=False, name=name), **kwargs)
    fig.add_trace(go.Scatter(x=paths.index, y=paths[low], mode="lines", line=dict(width=0),
                             fill="tonexty", fillcolor=theme.rgba(color, alpha),
                             hoverinfo="skip", showlegend=showlegend, name=name), **kwargs)


def _add_series(fig, history, paths, color, name, t, row=None, col=None, legend=False):
    kwargs = dict(row=row, col=col) if row else {}
    fig.add_trace(go.Scatter(
        x=history.index, y=history.values, mode="lines", name=name,
        line=dict(color=color, width=2), showlegend=legend,
        hovertemplate="%{y:,.0f}<extra>" + name + "</extra>",
    ), **kwargs)
    _band(fig, paths, color, "80% range", "p10", "p90", 0.14, row, col, showlegend=legend)
    _band(fig, paths, color, "50% range", "p25", "p75", 0.22, row, col, showlegend=legend)
    fig.add_trace(go.Scatter(
        x=paths.index, y=paths["p50"], mode="lines", name="Median path",
        line=dict(color=color, width=2, dash="dash"), showlegend=legend,
        hovertemplate="median %{y:,.0f}<extra>" + name + "</extra>",
    ), **kwargs)
    fig.add_trace(go.Scatter(
        x=[history.index[-1]], y=[history.values[-1]], mode="markers", showlegend=False,
        marker=dict(color=color, size=8, line=dict(color=t["surface"], width=2)),
        hovertemplate="today %{y:,.0f}<extra>" + name + "</extra>",
    ), **kwargs)


@callback(
    Output("fc-chart", "figure"),
    Output("fc-table", "children"),
    Output("fc-chart-desc", "children"),
    Input("fc-view", "value"),
    Input("fc-horizon", "value"),
    Input("fc-lookback", "value"),
    Input("fc-drift", "value"),
    Input("theme", "data"),
    Input("cvd", "data"),
)
def update_forecast(view, horizon, lookback, drift, theme_key, cvd):
    index = industry_index()
    results = forecast_all(index, int(horizon), lookback, drift)
    colors = theme.industry_colors(theme_key, cvd)
    t = theme.tokens(theme_key)
    names = list(index.columns)

    if view == "all":
        fig = make_subplots(rows=3, cols=3, subplot_titles=names,
                            vertical_spacing=0.09, horizontal_spacing=0.06)
        for i, name in enumerate(names):
            row, col = i // 3 + 1, i % 3 + 1
            paths, _ = results[name]
            history = index[name].iloc[-HISTORY_DAYS:]
            _add_series(fig, history, paths, colors[name], name, t, row, col)
        fig.update_annotations(font=dict(size=12, color=t["ink"]))
        theme.apply(fig, theme_key, title=f"{horizon}-month cone for every index (last 12 months of history shown)",
                    showlegend=False, hovermode="x", margin=dict(l=40, r=20, t=70, b=30))
        fig.update_xaxes(tickfont=dict(size=10), nticks=5)
        fig.update_yaxes(tickfont=dict(size=10))
    else:
        paths, _ = results[view]
        history = index[view].iloc[-2 * HISTORY_DAYS:]
        fig = go.Figure()
        _add_series(fig, history, paths, colors[view], view, t, legend=True)
        theme.apply(fig, theme_key, title=f"{view}: {horizon}-month cone",
                    hovermode="x unified", legend=dict(orientation="h", y=-0.12, title=""),
                    yaxis=dict(title="Index (Oct 2022 = 100)"))

    since_boom = scorecard()
    rows = []
    for name in names:
        _, s = results[name]
        rows.append([
            html.Span([html.Span(className="swatch", style={"background": colors[name]}), name]),
            num(s["last_value"], 0), pct(float(since_boom[name]), 0),
            pct(s["ann_drift_pct"]), pct(s["ann_vol_pct"], sign=False),
            html.Span(pct(s["median_change_pct"]), className="up" if s["median_change_pct"] > 0 else "down"),
            pct(s["p10_change_pct"]), pct(s["p90_change_pct"]), f"{s['prob_gain_pct']:.0f}%",
        ])
    forecast_table = table(
        ["Index", "Today", "Since boom", "Ann. drift used", "Ann. volatility",
         f"Median in {horizon} mo", "10th pct", "90th pct", "P(higher)"],
        rows,
        caption=f"Forecast statistics for every industry index over {horizon} months, "
                f"using {LOOKBACKS[lookback].lower()} and {DRIFT_MODES[drift].lower()}",
    )

    shown = names if view == "all" else [view]
    description = describe_ranked(
        f"Forecast cone chart. {'All ' + str(len(names)) + ' indices' if view == 'all' else view}, "
        f"projected {horizon} months using {LOOKBACKS[lookback].lower()} and "
        f"{DRIFT_MODES[drift].lower()}. Median projected change:",
        [(name, results[name][1]["median_change_pct"]) for name in shown],
        unit="%", digits=1,
    )
    description += " " + describe_ranked(
        "Probability each index ends higher than today:",
        [(name, results[name][1]["prob_gain_pct"]) for name in shown], unit="%",
    )
    return fig, forecast_table, description


@callback(
    Output("fc-summary", "children"),
    Input("fc-run", "n_clicks"),
    State("fc-horizon", "value"),
    State("fc-lookback", "value"),
    State("fc-drift", "value"),
    prevent_initial_call=True,
)
def outlook(_clicks, horizon, lookback, drift):
    index = industry_index()
    results = forecast_all(index, int(horizon), lookback, drift)
    since_boom = scorecard()
    rows = []
    for name in index.columns:
        _, s = results[name]
        rows.append({
            "industry": name,
            "members": config.INDUSTRIES.get(name, [config.BENCHMARK_TICKER]),
            "total_return_since_chatgpt_pct": round(float(since_boom[name]), 1),
            **s,
        })
    settings = {
        "horizon_months": int(horizon),
        "lookback": LOOKBACKS[lookback],
        "drift_assumption": DRIFT_MODES[drift],
        "index_base": "Equal-weight basket of five stocks, 100 = Oct 3, 2022",
    }
    try:
        result = ai_summary.industry_outlook(rows, settings)
    except ai_summary.SummaryUnavailable as exc:
        return notice(str(exc))
    return summary_block(result)
