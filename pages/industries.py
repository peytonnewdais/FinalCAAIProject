"""Industries page: the original rebased-index chart plus the scorecard, theme-aware.

AI usage: see docs/AI_USAGE.md.
"""
from __future__ import annotations

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from services import config, theme
from services.market_data import industry_index, rebase, scorecard, years
from services.ui import GRAPH_CONFIG, chart, control, describe_ranked, page_head

dash.register_page(__name__, path="/industries", name="Industries",
                   title=f"Industries | {config.APP_TITLE}")

METRIC_LABEL = "Rebased index (start of window = 100)"


def layout():
    yrs = years()
    return html.Div([
        page_head(
            "How the AI boom affected different industries",
            "Each line is an equal-weight basket of the five largest companies in an industry, "
            "rebased to 100 at the start of the selected window. The dashed line is the S&P 500.",
            eyebrow="Industry scorecard",
        ),

        html.Div(className="card", children=[
            html.Div(className="controls", children=[
                control("Industries", dcc.Dropdown(
                    id="ind-industries",
                    options=[{"label": i, "value": i} for i in config.INDUSTRIES],
                    value=[], multi=True, clearable=True,
                    placeholder="Pick industries to compare against the S&P 500",
                ), grow=True),
            ]),
            html.Div(className="slider-wrap", role="group",
                     **{"aria-labelledby": "ind-years-label"}, children=[
                         html.Label("Time window", id="ind-years-label"),
                         dcc.RangeSlider(id="ind-years", min=yrs[0], max=yrs[-1],
                                         value=[yrs[0], yrs[-1]], step=None,
                                         marks={int(y): str(y) for y in yrs}),
                     ]),
            chart(dcc.Graph(id="ind-chart", config=GRAPH_CONFIG,
                            style={"height": "60vh", "minHeight": "460px"}),
                  "ind-chart-desc"),
        ]),

        html.Div(className="card", children=[
            html.H3("The whole boom in one chart"),
            html.P("Total return of each industry index from ChatGPT's launch to the latest close.",
                   className="muted"),
            chart(dcc.Graph(id="ind-scorecard", config=GRAPH_CONFIG,
                            style={"height": "460px"}),
                  "ind-scorecard-desc"),
            html.P(
                "Since the boom began, Semiconductors & AI Hardware climbed to roughly ten times its "
                "starting value while the S&P 500 roughly doubled. IT Services & Consulting and "
                "Content & Support Services lost a large share of their value. The gains were "
                "concentrated, not shared.",
            ),
        ]),

        html.Div(className="card", children=[
            html.H3("Events marked on the chart"),
            html.Ul([html.Li([html.Strong(pd.Timestamp(day).strftime("%b %d, %Y")), f" - {label}"])
                     for day, label in config.EVENTS]),
        ]),
    ])


@callback(
    Output("ind-chart", "figure"),
    Output("ind-chart-desc", "children"),
    Input("ind-industries", "value"),
    Input("ind-years", "value"),
    Input("theme", "data"),
    Input("cvd", "data"),
)
def update_chart(industries, year_range, theme_key, cvd):
    window = industry_index().loc[str(year_range[0]):str(year_range[1])]
    columns = list(industries or []) + [config.BENCHMARK]
    data = rebase(window[columns])
    colors = theme.industry_colors(theme_key, cvd)

    fig = go.Figure()
    for name in columns:
        is_benchmark = name == config.BENCHMARK
        # In colorblind mode each industry also gets its own dash pattern, so the lines stay
        # separable without relying on hue.
        dash_style = "dash" if is_benchmark else theme.line_dash(name, cvd)
        fig.add_trace(go.Scatter(
            x=data.index, y=data[name], name=name, mode="lines",
            line=dict(color=colors[name], width=2, dash=dash_style),
            hovertemplate="%{y:,.0f}<extra>" + name + "</extra>",
        ))

    theme.add_event_lines(fig, data.index.min(), data.index.max(), theme_key)
    fig.add_hline(y=100, line_width=1, line_color=theme.tokens(theme_key)["axis"])
    theme.apply(
        fig, theme_key,
        title=METRIC_LABEL, hovermode="x unified",
        legend=dict(orientation="h", y=-0.16, title=""),
        yaxis=dict(title=""), xaxis=dict(title=""),
    )

    finals = sorted(((name, float(data[name].iloc[-1])) for name in columns),
                    key=lambda pair: pair[1], reverse=True)
    description = describe_ranked(
        f"Line chart. {len(columns)} series from {data.index.min():%B %Y} to "
        f"{data.index.max():%B %Y}, each starting at 100. Ending values, highest first:",
        finals,
    )
    return fig, description


@callback(
    Output("ind-scorecard", "figure"),
    Output("ind-scorecard-desc", "children"),
    Input("theme", "data"),
    Input("cvd", "data"),
)
def update_scorecard(theme_key, cvd):
    scores = scorecard()
    colors = theme.industry_colors(theme_key, cvd)
    t = theme.tokens(theme_key)

    fig = go.Figure(go.Bar(
        x=scores.values, y=scores.index, orientation="h",
        marker=dict(color=[colors[i] for i in scores.index], line=dict(width=0)),
        text=[f"{v:+,.0f}%" for v in scores.values], textposition="outside",
        cliponaxis=False, textfont=dict(color=t["ink"], size=12),
        hovertemplate="%{y}: %{x:+,.0f}%<extra></extra>",
    ))
    span = float(scores.max() - scores.min())
    fig.update_xaxes(range=[scores.min() - span * 0.18, scores.max() + span * 0.14],
                     title="Total return since Nov 30, 2022 (%)")
    fig.update_yaxes(title="")
    theme.apply(fig, theme_key, title="Total return since Fall 2022", showlegend=False,
                bargap=0.3, margin=dict(l=10, r=40, t=56, b=48))

    ranked = sorted(((name, float(v)) for name, v in scores.items()),
                    key=lambda pair: pair[1], reverse=True)
    description = describe_ranked(
        "Bar chart. Total return since November 30, 2022, best first:", ranked, unit="%",
    )
    return fig, description
