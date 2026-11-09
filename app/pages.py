import os
from collections.abc import Sequence
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

from app.data import RANGES, Period
from app.format import full_time, parse_time, percent, time_ago
from app.inseeq import InseeqError

STYLE = (Path(__file__).parent / "style.css").read_text()
FLAT_BELOW = 0.005
ARROWS = {"up": "↑", "down": "↓", "flat": "→"}
CURRENT = ' aria-current="page"'
NUMERIC = ' class="num"'


class Html(str):
    """Markup built here and already escaped. Anything else passed to a builder is text and gets escaped."""


def text(value: Any) -> str:
    return value if isinstance(value, Html) else escape(str(value))


def title() -> str:
    return os.environ.get("DASHBOARD_TITLE") or "Dashboard"


def _document(page_title: str, body: str) -> str:
    return Html(
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{text(page_title)}</title><style>{STYLE}</style></head><body>{body}</body></html>"
    )


def _brand() -> str:
    return f'<span class="brand"><span class="brand-mark" aria-hidden="true"></span>{text(title())}</span>'


def freshness(status: dict[str, Any] | None, timezone: str) -> str:
    refreshed_at = (status or {}).get("refreshed_at")
    if not status or not refreshed_at:
        return '<p class="freshness">Waiting for the first refresh</p>'
    behind = len(status.get("stale_sources") or [])
    failed_at = (status.get("last_failure") or {}).get("failed_at")
    failed = bool(failed_at and parse_time(failed_at) > parse_time(refreshed_at))
    notes = "<small>The last refresh failed</small>" if failed else ""
    if behind:
        notes += f"<small>{'1 source is' if behind == 1 else f'{behind} sources are'} behind</small>"
    return (
        f'<p class="freshness{" warn" if notes else ""}" title="{text(full_time(refreshed_at, timezone))}">'
        f'<span class="dot" aria-hidden="true"></span><span>Updated {text(time_ago(refreshed_at))}</span>{notes}</p>'
    )


def frame(page_title: str, header: str, content: str, status: dict[str, Any] | None, timezone: str) -> str:
    """The frame around a page: the brand, the freshness line and the log-out button."""
    logout = '<form method="post" action="/api/logout"><button type="submit" class="quiet">Log out</button></form>'
    topbar = f'<header class="topbar">{_brand()}<div class="topbar-end">{freshness(status, timezone)}{logout}</div></header>'
    return _document(f"{page_title} | {title()}", f'{topbar}<main class="content">{header}{content}</main>')


def page_header(page_title: str, period: Period, path: str = "/") -> str:
    """The page title, the period it shows and the range picker."""
    links = "".join(
        f'<a href="{text(path)}?range={key}"{CURRENT if key == period.range else ""}>{days} days</a>'
        for key, days in RANGES.items()
    )
    return (
        f'<header class="page-header"><div><h1>{text(page_title)}</h1><p>{text(period.label)}</p></div>'
        f'<nav class="segmented" aria-label="Date range">{links}</nav></header>'
    )


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    current: float | None
    previous: float | None
    compare_label: str
    # Whether a rise is good news. Spend going up is neither, so pass None.
    up_is_good: bool | None = True


def _kpi(kpi: Kpi) -> str:
    change = (kpi.current - kpi.previous) / kpi.previous if kpi.current is not None and kpi.previous else None
    if change is None:
        delta = '<span class="kpi-delta neutral">No earlier data to compare</span>'
    else:
        direction = "flat" if abs(change) < FLAT_BELOW else "up" if change > 0 else "down"
        neutral = direction == "flat" or kpi.up_is_good is None
        tone = "neutral" if neutral else "good" if (direction == "up") == kpi.up_is_good else "bad"
        delta = (
            f'<span class="kpi-delta {tone}"><span aria-hidden="true">{ARROWS[direction]}</span> '
            f"{text(percent(abs(change)))} {text(kpi.compare_label)}</span>"
        )
    return (
        f'<div class="kpi"><span class="kpi-label">{text(kpi.label)}</span>'
        f'<span class="kpi-value">{text(kpi.value)}</span>{delta}</div>'
    )


def kpi_row(kpis: Sequence[Kpi]) -> Html:
    return Html(f'<div class="kpis">{"".join(map(_kpi, kpis))}</div>')


def card(card_title: str, subtitle: str, body: str) -> Html:
    return Html(f'<section class="card"><header><h3>{text(card_title)}</h3><p>{text(subtitle)}</p></header>{body}</section>')


def swatch(color: str) -> Html:
    """A color key. Pass a class from charts.COLORS, never data."""
    return Html(f'<span class="swatch {escape(color)}"></span>')


def keyed(label: str, color: str) -> Html:
    """A label with its color key in front, for a table cell."""
    return Html(swatch(color) + escape(label))


def data_table(columns: Sequence[tuple[str, bool]], rows: Sequence[Sequence[Any]], total: Sequence[Any] | None = None) -> Html:
    """Columns are (label, numeric). Cells are text, or Html from a builder here."""

    def row(cells: Sequence[Any]) -> str:
        tds = (f"<td{NUMERIC if numeric else ''}>{text(cell)}</td>" for cell, (_, numeric) in zip(cells, columns, strict=True))
        return f"<tr>{''.join(tds)}</tr>"

    head = "".join(f"<th{NUMERIC if numeric else ''}>{text(label)}</th>" for label, numeric in columns)
    foot = f"<tfoot>{row(total)}</tfoot>" if total else ""
    body = "".join(map(row, rows))
    return Html(f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody>{foot}</table></div>')


def numbers(body: str) -> Html:
    """The numbers behind a chart, folded away until asked for."""
    return Html(f'<details class="numbers"><summary>Show the numbers</summary>{body}</details>')


def empty_state(heading: str, message: str) -> Html:
    return Html(f'<div class="empty"><h3>{text(heading)}</h3><p>{text(message)}</p></div>')


def error_state(error: InseeqError) -> Html:
    """What a reader sees when a page cannot load. The code is for whoever fixes it."""
    message = error.message.lower()
    missing = "not found: table" in message or "was not found" in message
    heading = "This page needs data your organization does not have yet." if missing else "This page could not load."
    return Html(
        f'<div class="callout bad" role="alert"><strong>{heading}</strong>'
        f"<p>{text(error.message)}</p><code>{text(error.code)}</code></div>"
    )


def render_login(failed: bool) -> str:
    error = '<p class="callout bad" role="alert">That password is not right.</p>' if failed else ""
    return _document(
        f"Log in | {title()}",
        '<main class="login"><form method="post" action="/api/login" class="card login-card">'
        f"{_brand()}<h1>Log in</h1>{error}"
        '<label for="password">Dashboard password</label>'
        '<input id="password" name="password" type="password" autocomplete="current-password" required autofocus>'
        '<button type="submit" class="primary">Log in</button></form></main>',
    )
