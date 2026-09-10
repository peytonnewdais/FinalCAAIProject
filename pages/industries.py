"""Industries page: the main chart of industry indices, plus a scorecard bar chart.

This is essentially a copy of the main page of our previous dash app project, we were able to use AI to
move it over into this project and refactor it with the other code.

Used AI for colorblind mode
"""
import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from services import config
from services.market_data import industry_index, rebase, scorecard, years

dash.register_page(__name__, path="/industries", name="Industries")

YEARS = years()


def scorecard_figure(colorblind=False):
    """The bar chart of total returns. Its only "control" is the colorblind toggle."""
    scores = scorecard()
    colors = config.industry_colors(colorblind)

    fig = go.Figure(go.Bar(
        x=scores.values, y=scores.index, orientation="h",
        marker_color=[colors[name] for name in scores.index],
        text=[f"{v:+,.0f}%" for v in scores.values], textposition="outside",
        cliponaxis=False,
    ))
    fig.update_layout(
        title="Total return since ChatGPT launched",
        plot_bgcolor="white", paper_bgcolor="white", showlegend=False, bargap=0.3,
        margin=dict(l=10, r=60, t=60, b=40),
    )
    # Extra room on both sides so the "+950%" labels are not cut off.
    span = scores.max() - scores.min()
    fig.update_xaxes(range=[scores.min() - span * 0.2, scores.max() + span * 0.15],
                     title="Total return since Nov 30, 2022 (%)", gridcolor="#e1e0d9")
    return fig


def layout():
    return html.Div([
        html.H1("How the AI boom affected different industries"),
        html.P("Each line is an equal-weight basket of the five largest companies in an "
               "industry, rebased to 100 at the start of the window you pick. The black "
               "dashed line is the S&P 500."),

        html.Div(className="card", children=[
            html.Div(className="control", children=[
                html.Label("Industries"),
                dcc.Dropdown(
                    id="industry-picker",
                    options=[{"label": name, "value": name} for name in config.INDUSTRIES],
                    value=["Semiconductors & AI Hardware", "IT Services & Consulting"],
                    multi=True,
                    placeholder="Pick industries to compare against the S&P 500",
                ),
            ]),
            html.Label("Time window", style={"display": "block", "marginTop": "20px"}),
            dcc.RangeSlider(
                id="year-slider",
                min=YEARS[0], max=YEARS[-1], value=[YEARS[0], YEARS[-1]], step=None,
                marks={y: str(y) for y in YEARS},
            ),
            dcc.Graph(id="industry-chart", style={"height": "550px"}),
        ]),

        html.Div(className="card", children=[
            html.H3("The whole boom in one chart"),
            html.P("Total return of each industry index from ChatGPT's launch to the latest "
                   "close.", className="muted"),
            dcc.Graph(id="scorecard-chart", style={"height": "460px"}),
            html.P("Semiconductors climbed to roughly ten times its starting value while the "
                   "S&P 500 roughly doubled. IT services and content businesses lost a large "
                   "share of their value. The gains were concentrated, not shared."),
        ]),

        html.Div(className="card", children=[
            html.H3("Events marked on the chart"),
            html.Ul([html.Li(f"{pd.Timestamp(day):%b %d, %Y} - {label}")
                     for day, label in config.EVENTS]),
        ]),
    ])


@callback(
    Output("scorecard-chart", "figure"),
    Input("colorblind-mode", "data"),
)
def render_scorecard(colorblind):
    return scorecard_figure(bool(colorblind))


@callback(
    Output("industry-chart", "figure"),
    Input("industry-picker", "value"),
    Input("year-slider", "value"),
    Input("colorblind-mode", "data"),
)
def update_chart(industries, year_range, colorblind):
    # The S&P 500 is always shown, so the picked industries have something to beat.
    columns = list(industries or []) + [config.BENCHMARK]
    window = industry_index().loc[str(year_range[0]):str(year_range[1])]
    data = rebase(window[columns])               # restart every line at 100
    colors = config.industry_colors(colorblind)

    fig = go.Figure()
    for name in columns:
        fig.add_trace(go.Scatter(
            x=data.index, y=data[name], name=name, mode="lines",
            line=dict(color=colors[name], width=2,
                      dash="dash" if name == config.BENCHMARK else "solid"),
        ))

    # Dotted vertical lines for the AI events that fall inside the chosen window.
    # The labels alternate left and right so neighbouring events do not overlap.
    shown = 0
    for day, label in config.EVENTS:
        date = pd.Timestamp(day)
        if data.index.min() <= date <= data.index.max():
            side = "top left" if shown % 2 == 0 else "top right"
            fig.add_vline(x=date, line_width=1, line_dash="dot", line_color="#8a8f9c",
                          annotation_text=label, annotation_position=side,
                          annotation_font=dict(size=10, color="#6b6a65"))
            shown += 1

    fig.add_hline(y=100, line_width=1, line_color="#c3c2b7")   # the starting level
    fig.update_layout(
        title="Rebased index (start of window = 100)",
        hovermode="x unified", plot_bgcolor="white", paper_bgcolor="white",
        legend=dict(orientation="h", y=-0.15),
        margin=dict(l=50, r=25, t=60, b=40),
    )
    fig.update_yaxes(gridcolor="#e1e0d9")
    fig.update_xaxes(gridcolor="#e1e0d9")
    return fig
