import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.format import day_range, days_between
from app.inseeq import InseeqError, get_client

RANGES = {"7d": 7, "30d": 30, "90d": 90}
DEFAULT_RANGE = "30d"
DEFAULT_SETTINGS = ("UTC", "USD")


@dataclass(frozen=True)
class Period:
    range: str
    start: date
    end: date
    previous_start: date
    previous_end: date
    days: list[date]
    label: str
    timezone: str
    currency: str


def run_query(name: str, params: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Runs a file in queries/ and refuses a cut-off answer, so no total is ever silently short."""
    result = get_client().run_saved(name, params=params)
    if result["truncated"]:
        raise InseeqError("truncated", f"The {name} query returned more rows than the page reads, so its totals would be wrong.")
    return result


def date_params(start: date, end: date) -> list[dict[str, str]]:
    return [
        {"name": "start_date", "type": "DATE", "value": start.isoformat()},
        {"name": "end_date", "type": "DATE", "value": end.isoformat()},
    ]


def get_status() -> dict[str, Any] | None:
    try:
        return get_client().status()
    except InseeqError:
        return None


def get_settings() -> tuple[str, str]:
    """The client's time zone and currency from cfg_client, or UTC and USD."""
    try:
        rows = run_query("client_settings")["rows"]
    except InseeqError:
        return DEFAULT_SETTINGS
    row = rows[0] if rows else {}
    timezone, currency = str(row.get("timezone") or "UTC"), str(row.get("currency") or "USD").upper()
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        timezone = "UTC"
    return timezone, currency if re.fullmatch(r"[A-Z]{3}", currency) else "USD"


def parse_range(value: str | None) -> str:
    return value if value in RANGES else DEFAULT_RANGE


def get_period(range_key: str, settings: tuple[str, str] | None = None) -> Period:
    """Days are the client's days: "yesterday" on a server in UTC is often the wrong day."""
    timezone, currency = settings or get_settings()
    length = RANGES[range_key]
    end = datetime.now(ZoneInfo(timezone)).date() - timedelta(days=1)
    start = end - timedelta(days=length - 1)
    return Period(
        range=range_key,
        start=start,
        end=end,
        previous_start=start - timedelta(days=length),
        previous_end=start - timedelta(days=1),
        days=days_between(start, end),
        label=day_range(start, end),
        timezone=timezone,
        currency=currency,
    )
