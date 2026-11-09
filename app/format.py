import math
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}
COMPACT_FROM = 10_000
COMPACT_SUFFIXES = ("", "k", "M", "B")
AGO_UNITS = (("day", 86_400), ("hour", 3_600), ("minute", 60))


def num(value: Any) -> float:
    """A number from the API, which sends BIGNUMERIC and INT64 as strings."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if math.isfinite(number) else 0.0


def _compact(value: float) -> str:
    """12345 to "12.3k"."""
    scaled, index = abs(value), 0
    while scaled >= 999.95 and index < len(COMPACT_SUFFIXES) - 1:
        scaled /= 1000
        index += 1
    text = f"{scaled:.1f}".removesuffix(".0")
    return f"{'-' if value < 0 else ''}{text}{COMPACT_SUFFIXES[index]}"


def _number(value: float, compact: bool, digits: int) -> str:
    if compact and abs(value) >= COMPACT_FROM:
        return _compact(value)
    return f"{value:,.{digits}f}"


def money(value: float, currency: str, *, compact: bool = False) -> str:
    symbol = CURRENCY_SYMBOLS.get(currency, f"{currency} ")
    amount = abs(value)
    digits = 0 if amount >= 100 or amount == 0 or (compact and amount == int(amount)) else 2
    return f"{'-' if value < 0 else ''}{symbol}{_number(amount, compact, digits)}"


def count(value: float, *, compact: bool = False) -> str:
    return _number(value, compact, 0)


def percent(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value * 100:.{1 if value < 0.1 else 0}f}".removesuffix(".0") + "%"


def ratio(part: float, whole: float) -> float | None:
    return part / whole if whole else None


def days_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def short_day(day: date) -> str:
    """Like "Nov 8"."""
    return f"{day:%b} {day.day}"


def day_range(start: date, end: date) -> str:
    """Like "Oct 10 to Nov 8, 2026"."""
    first = short_day(start) if start.year == end.year else f"{short_day(start)}, {start.year}"
    return f"{first} to {short_day(end)}, {end.year}"


def parse_time(timestamp: str) -> datetime:
    parsed = datetime.fromisoformat(timestamp)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def time_ago(timestamp: str, now: datetime | None = None) -> str:
    """Like "2 hours ago"."""
    seconds = ((now or datetime.now(UTC)) - parse_time(timestamp)).total_seconds()
    for unit, size in AGO_UNITS:
        if seconds >= size:
            amount = int(seconds / size + 0.5)
            if unit == "day" and amount == 1:
                return "yesterday"
            return f"{amount} {unit}{'' if amount == 1 else 's'} ago"
    return "just now"


def full_time(timestamp: str, timezone: str) -> str:
    """Like "Nov 9, 2026, 9:32 AM EST", for a tooltip."""
    local = parse_time(timestamp).astimezone(ZoneInfo(timezone))
    return f"{short_day(local.date())}, {local.year}, {local.hour % 12 or 12}:{local:%M %p} {local:%Z}"


def humanize(key: str) -> str:
    """Turns "paid_social_meta" into "Paid social meta"."""
    text = key.replace("_", " ").strip()
    return text[:1].upper() + text[1:]
