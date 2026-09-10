"""Forecast page: a cone of possible futures for each industry index."""
import dash
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html
from plotly.subplots import make_subplots

from services import ai_summary, config
from services.forecast import LOOKBACKS, forecast_all
from services.market_data import industry_index, scorecard

dash.register_page(__name__, path="/forecast", name="Forecast")

HISTORY_DAYS = 252        # one year of real history drawn before the cone starts

# The chart's y-axis: every index is rebased to 100 on its October 2022 baseline, so a
# reading of 1200 means the industry basket is worth 12x what it was worth then - not a
# real price. Spelled out on the axis itself since that is easy to misread at a glance.
#
# Two lengths: the single-index chart has the full chart height for one axis title and
# can afford the long version, but the "all industries" grid splits that same height
# three ways - the long version doesn't fit a subplot row and spills into the next one,
# so the grid gets the short version instead.
Y_AXIS_TITLE = "Index level (100 = Oct 2022 baseline value)"
Y_AXIS_TITLE_SHORT = "Index level (100 = Oct 2022)"

VIEW_OPTIONS = [{"label": "All industries", "value": "all"}] + [
    {"label": name, "value": name} for name in list(config.INDUSTRIES) + [config.BENCHMARK]]


def layout():
    return html.Div([
        html.H1("Where could each industry go next?"),
        html.P("Each index is projected forward with geometric Brownian motion: future value = "
               "today's value × e^(trend + randomness). The shaded bands show a range of likely "
               "outcomes, not one prediction."),

        html.Div(className="card", children=[
            html.Div(className="controls", children=[
                html.Div(className="control", children=[
                    html.Label("View"),
                    dcc.Dropdown(id="view", options=VIEW_OPTIONS, value="all", clearable=False),
                ]),
                html.Div(className="control", children=[
                    html.Label("Lookback window"),
                    dcc.RadioItems(id="lookback", value="2y",
                                   options=[{"label": v, "value": k}
                                            for k, v in LOOKBACKS.items()]),
                ]),
            ]),
            html.Label("How far ahead", style={"display": "block", "marginTop": "20px"}),
            dcc.Slider(id="horizon", min=3, max=24, step=3, value=12,
                       marks={m: f"{m} mo" for m in range(3, 25, 3)}),
        ]),

        html.Div(className="card", children=dcc.Graph(id="forecast-chart",
                                                      style={"height": "650px"})),

        html.Div(className="card", children=[
            html.H3("Forecast table"),
            html.Div(id="forecast-table", className="table-wrap"),
        ]),

        html.Div(className="card", children=[
            html.H3("Claude's outlook"),
            html.P("Claude reads the forecast numbers for every industry and explains what the "
                   "model assumes and where it is most likely to be wrong.", className="muted"),
            html.Button("Generate outlook", id="outlook-button", n_clicks=0, className="button"),
            dcc.Loading(html.Div(id="outlook", style={"marginTop": "15px"})),
        ]),

        html.Div(className="card", children=[
            html.H3("How the forecast works"),
            html.Ul([
                html.Li("Daily log returns over the lookback window give an average (the trend) "
                        "and a standard deviation (the volatility)."),
                html.Li("This is not a regression - no line is fit against time. It is a "
                        "closed-form lognormal model (geometric Brownian motion, the same math "
                        "behind Black-Scholes): the average and standard deviation are plugged "
                        "straight into a formula for each percentile, not simulated."),
                html.Li("The future is projected from those two numbers, with uncertainty "
                        "growing over time. That is what makes the cone widen."),
                html.Li("The trend is always damped to half of its historical value, not the "
                        "full run and not zero. It is the shakiest input - a page that let "
                        "visitors dial it up or down would just move the guesswork onto them - "
                        "so the model picks the one defensible middle ground instead."),
                html.Li("Volatility is assumed to stay constant, so real markets will have "
                        "bigger surprises than the cone shows."),
                html.Li("This is a class project, not investment advice."),
            ]),
        ]),
    ])


def add_cone(fig, history, paths, color, name, row=None, col=None, legend=False):
    """Draw one index: its recent history, then the shaded forecast cone."""
    where = dict(row=row, col=col) if row else {}

    fig.add_trace(go.Scatter(x=history.index, y=history.values, mode="lines", name=name,
                             line=dict(color=color, width=2), showlegend=legend), **where)

    # Two shaded bands. Each is drawn as an invisible upper line, then a lower
    # line filled up to it.
    for low, high, shade, label in [("p10", "p90", 0.14, "80% range"),
                                    ("p25", "p75", 0.22, "50% range")]:
        fig.add_trace(go.Scatter(x=paths.index, y=paths[high], mode="lines",
                                 line=dict(width=0), hoverinfo="skip", showlegend=False), **where)
        fig.add_trace(go.Scatter(x=paths.index, y=paths[low], mode="lines", line=dict(width=0),
                                 fill="tonexty", fillcolor=fade(color, shade), name=label,
                                 hoverinfo="skip", showlegend=legend), **where)

    fig.add_trace(go.Scatter(x=paths.index, y=paths["p50"], mode="lines", name="Middle path",
                             line=dict(color=color, width=2, dash="dash"),
                             showlegend=legend), **where)


def fade(hex_color, alpha):
    """Turn '#1f73d0' into a see-through rgba() color for the shaded bands."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


@callback(
    Output("forecast-chart", "figure"),
    Output("forecast-table", "children"),
    Input("view", "value"),
    Input("horizon", "value"),
    Input("lookback", "value"),
)
def update_forecast(view, horizon, lookback):
    index = industry_index()
    results = forecast_all(index, horizon, lookback)
    names = list(index.columns)

    if view == "all":
        # Nine small charts in a 3x3 grid, one per index.
        fig = make_subplots(rows=3, cols=3, subplot_titles=names,
                            vertical_spacing=0.09, horizontal_spacing=0.06)
        for i, name in enumerate(names):
            paths, _ = results[name]
            history = index[name].iloc[-HISTORY_DAYS:]
            add_cone(fig, history, paths, config.INDUSTRY_COLORS[name], name,
                     row=i // 3 + 1, col=i % 3 + 1)
        fig.update_layout(title=f"{horizon}-month forecast for every index", showlegend=False)
        fig.update_annotations(font_size=12)
        # One label is enough for a 3x3 grid; every subplot shares the same scale.
        for row in (1, 2, 3):
            fig.update_yaxes(title_text=Y_AXIS_TITLE_SHORT, row=row, col=1,
                             title_font=dict(size=10))
    else:
        paths, _ = results[view]
        history = index[view].iloc[-2 * HISTORY_DAYS:]
        fig = go.Figure()
        add_cone(fig, history, paths, config.INDUSTRY_COLORS[view], view, legend=True)
        fig.update_layout(title=f"{view}: {horizon}-month forecast", hovermode="x unified",
                          legend=dict(orientation="h", y=-0.12),
                          yaxis_title=Y_AXIS_TITLE)

    fig.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                      margin=dict(l=45, r=25, t=70, b=40))
    fig.update_xaxes(gridcolor="#e1e0d9")
    fig.update_yaxes(gridcolor="#e1e0d9")

    # --- the table under the chart
    since_boom = scorecard()
    header = ["Index", "Today", "Since boom", "Trend used", "Volatility",
              f"Middle in {horizon} mo", "10th pct", "90th pct", "Chance of a gain"]
    rows = []
    for name in names:
        _, s = results[name]
        rows.append(html.Tr([
            html.Td(name),
            html.Td(f"{s['last_value']:,.0f}", className="num"),
            html.Td(f"{since_boom[name]:+,.0f}%", className="num"),
            html.Td(f"{s['ann_drift_pct']:+,.1f}%", className="num"),
            html.Td(f"{s['ann_vol_pct']:,.1f}%", className="num"),
            html.Td(f"{s['median_change_pct']:+,.1f}%", className="num",
                    style={"color": "#0a7a2f" if s["median_change_pct"] > 0 else "#c4302b"}),
            html.Td(f"{s['p10_change_pct']:+,.1f}%", className="num"),
            html.Td(f"{s['p90_change_pct']:+,.1f}%", className="num"),
            html.Td(f"{s['prob_gain_pct']}%", className="num"),
        ]))

    table = html.Table(className="data", children=[
        html.Thead(html.Tr([html.Th(name, className="num" if i else "")
                            for i, name in enumerate(header)])),
        html.Tbody(rows),
    ])
    return fig, table


@callback(
    Output("outlook", "children"),
    Input("outlook-button", "n_clicks"),
    State("horizon", "value"),
    State("lookback", "value"),
    prevent_initial_call=True,
)
def write_outlook(n_clicks, horizon, lookback):
    """Send the forecast numbers for every industry to Claude."""
    index = industry_index()
    results = forecast_all(index, horizon, lookback)
    since_boom = scorecard()

    rows = []
    for name in index.columns:
        _, stats = results[name]
        rows.append({
            "industry": name,
            "members": config.INDUSTRIES.get(name, [config.BENCHMARK_TICKER]),
            "total_return_since_chatgpt_pct": round(float(since_boom[name]), 1),
            **stats,
        })

    settings = {
        "horizon_months": horizon,
        "lookback": LOOKBACKS[lookback],
        "drift_assumption": "Half of the historical trend, fixed (not user-adjustable)",
        "index_base": "Equal-weight basket of five stocks, 100 = Oct 3, 2022",
    }

    try:
        answer = ai_summary.industry_outlook(rows, settings)
    except ai_summary.SummaryUnavailable as error:
        return html.Div(str(error), className="notice")

    note = f"Written by {answer['model']}"
    if answer.get("cached"):
        note += " (cached)"
    return html.Div([
        dcc.Markdown(answer["text"]),
        html.P(note, className="muted small"),
    ])
