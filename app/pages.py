from html import escape
from pathlib import Path
from typing import Any

STYLE = (Path(__file__).parent / "style.css").read_text()


def _page(body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>Data dashboard</title><style>{STYLE}</style></head><body><main>{body}</main></body></html>"
    )


def _dashboard(content: str) -> str:
    logout = '<form method="post" action="/api/logout"><button type="submit">Log out</button></form>'
    return _page(f"<header><h1>Data dashboard</h1>{logout}</header>{content}")


def _freshness(status: dict[str, Any]) -> str:
    failure = status["last_failure"]
    fields = {
        "Last refresh": status["refreshed_at"] or "Not recorded yet",
        "Build": status["build_mode"] or "Not recorded yet",
        "Stale sources": ", ".join(status["stale_sources"]) or "None",
        "Last failure": failure["failed_at"] if failure else "None",
    }
    return "<dl>" + "".join(f"<dt>{name}</dt><dd>{escape(str(value))}</dd>" for name, value in fields.items()) + "</dl>"


def _table_row(table: dict[str, Any]) -> str:
    rows = table.get("row_count")
    start, end = table.get("date_from"), table.get("date_to")
    dates = f"{start or '?'} to {end or '?'}" if start or end else "No dates"
    return (
        f"<tr><td>{escape(table['name'])}</td>"
        f'<td class="number">{"Unknown" if rows is None else f"{rows:,}"}</td>'
        f'<td class="nowrap">{escape(dates)}</td>'
        f"<td>{escape(table.get('description') or '')}</td></tr>"
    )


def _tables(tables: list[dict[str, Any]]) -> str:
    if not tables:
        return "<p>No tables are published yet.</p>"
    head = '<tr><th>Table</th><th class="number">Rows</th><th>Dates</th><th>Description</th></tr>'
    return f"<table><thead>{head}</thead><tbody>{''.join(map(_table_row, tables))}</tbody></table>"


def render_dashboard(status: dict[str, Any], tables: list[dict[str, Any]]) -> str:
    return _dashboard(f"<h2>Freshness</h2>{_freshness(status)}<h2>Tables</h2>{_tables(tables)}")


def render_error(code: str, message: str) -> str:
    return _dashboard(f'<p class="error">{escape(message)} <span class="muted">({escape(code)})</span></p>')


def render_login(failed: bool) -> str:
    error = '<p class="error">That password is not right.</p>' if failed else ""
    return _page(
        f"<h1>Log in</h1>{error}"
        '<form method="post" action="/api/login">'
        '<label for="password">Dashboard password</label>'
        '<input id="password" name="password" type="password" autocomplete="current-password" required autofocus>'
        '<button type="submit">Log in</button></form>'
    )
