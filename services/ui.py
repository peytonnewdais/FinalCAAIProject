"""Small Dash layout helpers shared by the pages (tiles, controls, tables, notices)."""
from __future__ import annotations

import base64

from dash import dcc, html

GRAPH_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
}


def pct(value, digits: int = 1, sign: bool = True) -> str:
    if value is None:
        return "n/a"
    text = f"{value:+,.{digits}f}%" if sign else f"{value:,.{digits}f}%"
    return text


def num(value, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


def tone(value) -> str:
    if value is None:
        return ""
    return "up" if value > 0 else "down" if value < 0 else ""


def _spark_points(values: list[float], w: float, h: float, pad: float) -> str:
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    n = len(values)
    step = (w - 2 * pad) / (n - 1) if n > 1 else 0.0
    return " ".join(
        f"{pad + i * step:.1f},{h - pad - (v - lo) / span * (h - 2 * pad):.1f}"
        for i, v in enumerate(values)
    )


def sparkline_uri(values, color: str, width: float = 72, height: float = 28,
                  stroke: float = 2.2) -> str:
    """A tiny label-free trend line as a base64 data URI, ready for ``html.Img``."""
    values = [float(v) for v in values]
    points = _spark_points(values, width, height, pad=stroke)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" '
        f'preserveAspectRatio="none">'
        f'<polyline fill="none" stroke="{color}" stroke-width="{stroke:g}" '
        f'stroke-linecap="round" stroke-linejoin="round" points="{points}"/>'
        f'</svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def multi_sparkline_uri(series, width: float = 620, height: float = 200) -> str:
    """Several trend lines on one label-free canvas (decorative hero accent).

    ``series`` is a list of ``(values, color, dash)`` tuples; ``dash`` is ``None``
    for a solid line or an SVG dash-array string.
    """
    all_values = [float(v) for values, _, _ in series for v in values]
    lo, hi = min(all_values), max(all_values)
    span = (hi - lo) or 1.0
    pad = 6.0
    lines = []
    for values, color, dash in series:
        values = [float(v) for v in values]
        n = len(values)
        step = (width - 2 * pad) / (n - 1) if n > 1 else 0.0
        points = " ".join(
            f"{pad + i * step:.1f},{height - pad - (v - lo) / span * (height - 2 * pad):.1f}"
            for i, v in enumerate(values)
        )
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        lines.append(
            f'<polyline fill="none" stroke="{color}" stroke-width="3" '
            f'stroke-linecap="round" stroke-linejoin="round"{dash_attr} points="{points}"/>'
        )
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:g} {height:g}" '
        f'preserveAspectRatio="none">{"".join(lines)}</svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def tile(label: str, value: str, sub: str | None = None, value_tone: str = "",
         variant: str = "", spark: str | None = None, emphasis: bool = False) -> html.Div:
    value_cls = f"value {value_tone}".strip()
    if emphasis:
        value_cls += " value-xl"
    value_el = html.Div(value, className=value_cls)
    if spark:
        value_el = html.Div(className="value-row", children=[
            value_el, html.Img(src=spark, className="tile-spark", alt=""),
        ])
    children = [html.Div(label, className="label"), value_el]
    if sub:
        children.append(html.Div(sub, className="sub"))
    return html.Div(className=f"tile {variant}".strip(), children=children)


def control(label: str, component, grow: bool = False) -> html.Div:
    return html.Div(className="control grow" if grow else "control",
                    children=[html.Label(label), component])


def notice(text: str, kind: str = "info") -> html.Div:
    return html.Div(text, className=f"notice {kind}")


def page_head(title: str, subtitle: str, eyebrow: str | None = None) -> html.Div:
    children = []
    if eyebrow:
        children.append(html.P(eyebrow, className="eyebrow"))
    children += [html.H1(title), html.P(subtitle, className="subtitle")]
    return html.Div(className="page-head", children=children)


def table(headers: list[str], rows: list[list], numeric_from: int = 1) -> html.Table:
    """A plain themed table. Cells from ``numeric_from`` onward are right-aligned."""
    def cell(value, i):
        cls = "num" if i >= numeric_from else ""
        return html.Td(value, className=cls)

    return html.Table(className="data", children=[
        html.Thead(html.Tr([html.Th(h, className="num" if i >= numeric_from else "")
                            for i, h in enumerate(headers)])),
        html.Tbody([html.Tr([cell(v, i) for i, v in enumerate(row)]) for row in rows]),
    ])


def summary_block(result: dict) -> html.Div:
    meta = f"Written by {result.get('model', 'Claude')}"
    if result.get("cached"):
        meta += " (cached)"
    return html.Div(className="summary", children=[
        dcc.Markdown(result["text"], link_target="_blank"),
        html.P(meta, className="muted small"),
    ])
