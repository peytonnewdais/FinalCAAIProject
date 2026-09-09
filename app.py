"""AI Boom Scorecard - multi-page Dash app.

Pages live in ./pages (home, industries, compare, forecast). Shared data and API
clients live in ./services. Run with:  python app.py

Accessibility: see docs/ACCESSIBILITY.md. Two user-controlled display modes live here -
light/dark theme and colorblind mode - each stored in localStorage and stamped onto <html>
so both CSS and every Plotly figure can respond to them.

Application architecture
------------------------
# ``app.py`` contains the application shell and shared layout.
# ``pages/`` contains the user-facing pages:
  home, industries, compare, and forecast.
# ``services/`` contains shared configuration, data loading, API clients,
  calculations, and caching logic.
# ``assets/`` contains global CSS and JavaScript files.

AI usage: see docs/AI_USAGE.md.
"""
from __future__ import annotations

from dash import Dash, Input, Output, State, clientside_callback, dcc, html, page_container

from services import config
from services.market_data import load_prices
# Navigation routes used to build the shared header.
# Each tuple countains: (URL path, visible link label).
# The order here controls the order of the navigation links.
NAV = [
    ("/", "Home"),
    ("/industries", "Industries"),
    ("/compare", "Compare stocks"),
    ("/forecast", "Forecast"),
]

#----------------------------------------------------------------------------------------------------------------
# Create the main Dash application object. This object connects the shared 
# layout, page modules, callbacks, metadata, and underlying Flask server.
#
# The application uses Dash Pages for multi-page navigation. Individual page layouts are stored in the ./pages 
# directory and rendered through the shared page_container in the main layout.
app = Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title=config.APP_TITLE,
    update_title=None,
    meta_tags=[
        # No maximum-scale / user-scalable=no: blocking pinch zoom fails WCAG 1.4.4.
        {"name": "viewport", "content": "width=device-width, initial-scale=1"},
        {"name": "description",
         "content": "Which industries did the AI boom actually reward? Stock performance, "
                    "SEC filing analysis, and forecasts for 40 companies across 8 industries."},
    ],
    # Font Awesome supplies the glyphs on the home page cards.
    external_stylesheets=[
        "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.2/css/all.min.css",
    ],
)
server = app.server

# Two fixes to Dash's default template:
#   1. It ships an <html> with no lang attribute; WCAG 3.1.1 (Level A) requires one so
#      screen readers pick the right pronunciation rules.
#   2. It parks its own config/scripts inside a <footer>, which makes a second contentinfo
#      landmark alongside the real page footer. A plain <div> carries no landmark role.
app.index_string = """<!DOCTYPE html>
<html lang="en">
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <div>
            {%config%}
            {%scripts%}
            {%renderer%}
        </div>
    </body>
</html>"""

# Create the app's navigation links and mark the current page as active. The function creates one clickable link 
# for each page in 'NAV'. The link matching 'pathname' recieves the active CSS class.
def nav_links(pathname: str = "/") -> list:
    """Nav links, with the current page marked in text rather than by color alone."""
    links = []
    for path, label in NAV:
        current = pathname == path
        children = [label]
        if current:
            # dcc.Link rejects aria-current, so the state is carried as visually hidden
            # text instead - announced by screen readers, invisible on screen.
            children.append(html.Span(" (current page)", className="sr-only"))
        links.append(dcc.Link(children, href=path,
                              className="nav-link active" if current else "nav-link"))
    return links

# Adds the App layout like a theme store, URL tracker, header (brand + nav + theme toggle), page container, footer.

app.layout = html.Div(className="app", children=[
    # "light" | "dark"; seeded before first paint by assets/theme-init.js
    dcc.Store(id="theme", storage_type="local"),
    # True | False; colorblind-safe palette plus dash/marker shape encoding
    dcc.Store(id="cvd", storage_type="local"),
    dcc.Location(id="url", refresh=False),

    # WCAG 2.4.1 Bypass Blocks: first thing in the tab order, visible only on focus.
    html.A("Skip to main content", href="#main-content", className="skip-link"),

    html.Header(className="topbar", children=html.Div(className="topbar-inner", children=[
        dcc.Link(href="/", className="brand", children=[
            html.Span("AI", className="brand-mark", **{"aria-hidden": "true"}),
            html.Span("Boom Scorecard"),
        ]),
        html.Nav(id="nav-links", className="nav", children=nav_links(),
                 **{"aria-label": "Main"}),
        html.Div(className="topbar-actions", children=[
            # Both toggles carry their state in the visible label, so the accessible name
            # and the on-screen text always agree (WCAG 2.5.3 Label in Name).
            html.Button(id="cvd-toggle", className="theme-toggle", n_clicks=0,
                        title="Use a colorblind-safe palette with dashes and markers",
                        children="Colorblind: off"),
            html.Button(id="theme-toggle", className="theme-toggle", n_clicks=0,
                        title="Switch between light and dark mode", children="Theme"),
        ]),
    ])),

    html.Main(id="main-content", className="page", tabIndex="-1", children=page_container),

    # Mode changes are visual; this announces them to screen reader users (WCAG 4.1.3).
    html.Div(id="a11y-announcer", className="sr-only", role="status",
             **{"aria-live": "polite", "aria-atomic": "true"}),

    html.Footer(className="footer", children=[
        html.Span(config.TEAM),
        html.Span(config.SOURCE),
        html.Span("Educational project, not investment advice."),
        dcc.Link("Accessibility", href="/accessibility", className="footer-link"),
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

# Flip colorblind mode when its button is pressed.
clientside_callback(
    """
    function (n_clicks, current) {
        return !(current === true);
    }
    """,
    Output("cvd", "data"),
    Input("cvd-toggle", "n_clicks"),
    State("cvd", "data"),
    prevent_initial_call=True,
)

# Stamp colorblind mode on <html> so CSS can respond, and label the button with its state.
clientside_callback(
    """
    function (cvd) {
        const on = cvd === true;
        document.documentElement.setAttribute('data-cvd', on ? 'on' : 'off');
        return on ? 'Colorblind: on' : 'Colorblind: off';
    }
    """,
    Output("cvd-toggle", "children"),
    Input("cvd", "data"),
)

# Announce display-mode changes for users who cannot see them happen.
clientside_callback(
    """
    function (theme, cvd) {
        const t = theme === 'dark' ? 'Dark' : 'Light';
        const c = cvd === true ? 'on' : 'off';
        return t + ' theme, colorblind mode ' + c + '.';
    }
    """,
    Output("a11y-announcer", "children"),
    Input("theme", "data"),
    Input("cvd", "data"),
    prevent_initial_call=True,
)


# Highlight the active navigation link based on the current URL.
@app.callback(Output("nav-links", "children"), Input("url", "pathname"))
def highlight_nav(pathname):
    return nav_links(pathname or "/")

#It basically loads the prices when the app is run, and runs the app in debug mode.
if __name__ == "__main__":
    load_prices()  
    app.run(debug=True)
