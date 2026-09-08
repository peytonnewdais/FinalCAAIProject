"""AI Boom Scorecard - multi-page Dash app.

Pages live in ./pages (home, industries, compare, forecast). Shared data and API
clients live in ./services. Run with:  python app.py
"""
from __future__ import annotations

from dash import Dash, Input, Output, State, clientside_callback, dcc, html, page_container

from services import config
from services.market_data import load_prices

NAV = [
    ("/", "Home"),
    ("/industries", "Industries"),
    ("/compare", "Compare stocks"),
    ("/forecast", "Forecast"),
]

app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title=config.APP_TITLE,
    update_title=None,
)
server = app.server


def nav_links(pathname: str = "/") -> list:
    return [
        dcc.Link(label, href=path,
                 className="nav-link active" if pathname == path else "nav-link")
        for path, label in NAV
    ]


app.layout = html.Div(className="app", children=[
    # "light" | "dark"; seeded before first paint by assets/theme-init.js
    dcc.Store(id="theme", storage_type="local"),
    dcc.Location(id="url", refresh=False),

    html.Header(className="topbar", children=html.Div(className="topbar-inner", children=[
        dcc.Link(href="/", className="brand", children=[
            html.Span("AI", className="brand-mark"),
            html.Span("Boom Scorecard"),
        ]),
        html.Nav(id="nav-links", className="nav", children=nav_links()),
        html.Button(id="theme-toggle", className="theme-toggle", n_clicks=0,
                    title="Switch between light and dark mode", children="Theme"),
    ])),

    html.Main(className="page", children=page_container),

    html.Footer(className="footer", children=[
        html.Span(config.TEAM),
        html.Span(config.SOURCE),
        html.Span("Educational project, not investment advice."),
    ]),
])


# Flip the stored theme when the button is pressed.
clientside_callback(
    """
    function (n_clicks, current) {
        return current === 'dark' ? 'light' : 'dark';
    }
    """,
    Output("theme", "data"),
    Input("theme-toggle", "n_clicks"),
    State("theme", "data"),
    prevent_initial_call=True,
)

# Apply the theme to <html> (CSS variables follow data-theme) and label the button.
clientside_callback(
    """
    function (theme) {
        const t = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', t);
        return t === 'dark' ? '\\u2600\\uFE0E  Light mode' : '\\u263E  Dark mode';
    }
    """,
    Output("theme-toggle", "children"),
    Input("theme", "data"),
)


@app.callback(Output("nav-links", "children"), Input("url", "pathname"))
def highlight_nav(pathname):
    return nav_links(pathname or "/")


if __name__ == "__main__":
    load_prices()  # warm the price cache before the first request
    app.run(debug=True)
