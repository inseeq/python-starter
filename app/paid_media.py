from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any

from app.charts import COLORS, MUTED, Series, column_chart
from app.data import Period, date_params, get_period, get_settings, get_status, run_query
from app.format import count, humanize, money, num, percent, ratio, short_day
from app.inseeq import InseeqError
from app.pages import Html, Kpi, card, data_table, empty_state, error_state, frame, keyed, kpi_row, numbers, page_header

TITLE = "Paid media"
# One color per platform, wherever it appears.
PLATFORMS = {
    "google_ads": ("Google Ads", COLORS[0]),
    "meta_ads": ("Meta Ads", COLORS[1]),
    "linkedin_ads": ("LinkedIn Ads", COLORS[2]),
}


def platform(key: str) -> tuple[str, str]:
    return PLATFORMS.get(key, (humanize(key), MUTED))


@dataclass
class Totals:
    spend: float = 0.0
    clicks: float = 0.0
    impressions: float = 0.0

    def add(self, row: dict[str, Any]) -> None:
        self.spend += num(row.get("spend"))
        self.clicks += num(row.get("clicks"))
        self.impressions += num(row.get("impressions"))

    @property
    def cost_per_click(self) -> float | None:
        return ratio(self.spend, self.clicks)

    @property
    def click_rate(self) -> float | None:
        return ratio(self.clicks, self.impressions)


def _platform_order(key: str) -> tuple[int, str]:
    known = list(PLATFORMS)
    return (known.index(key), "") if key in known else (len(known), key)


def overview(period: Period, rows: list[dict[str, Any]]) -> Html:
    current, previous = Totals(), Totals()
    by_platform: dict[str, Totals] = defaultdict(Totals)
    spend_by_day: dict[tuple[date, str], float] = defaultdict(float)
    for row in rows:
        day, key = date.fromisoformat(str(row["day"])[:10]), str(row.get("platform") or "unknown")
        if day < period.start:
            previous.add(row)
            continue
        current.add(row)
        by_platform[key].add(row)
        spend_by_day[day, key] += num(row.get("spend"))

    if not by_platform:
        if rows:
            return empty_state("No ad data in these days", "Try a longer range.")
        return empty_state("No ad data yet", "Connect Google, Meta or LinkedIn Ads and this page fills in after the next refresh.")

    keys = sorted(by_platform, key=_platform_order)
    series = [Series(key, *platform(key), [spend_by_day[day, key] for day in period.days]) for key in keys]

    def cash(value: float | None) -> str:
        return "n/a" if value is None else money(value, period.currency)

    def axis(value: float) -> str:
        return money(value, period.currency, compact=True)

    compare = f"vs previous {len(period.days)} days"
    kpis = kpi_row(
        [
            Kpi("Spend", axis(current.spend), current.spend, previous.spend, compare, up_is_good=None),
            Kpi("Clicks", count(current.clicks, compact=True), current.clicks, previous.clicks, compare),
            Kpi("Cost per click", cash(current.cost_per_click), current.cost_per_click, previous.cost_per_click, compare, up_is_good=False),
            Kpi("Click rate", percent(current.click_rate), current.click_rate, previous.click_rate, compare),
        ]
    )

    day_columns = [("Day", False), *((s.label, True) for s in series)] + ([("Total", True)] if len(series) > 1 else [])
    day_rows = []
    for i, day in enumerate(period.days):
        values = [s.values[i] for s in series]
        day_rows.append([short_day(day), *map(cash, values), *([cash(sum(values))] if len(series) > 1 else [])])
    chart = column_chart(period.days, series, cash, axis, "Spend per day by platform")
    spend_card = card("Spend per day", period.label, Html(chart + numbers(data_table(day_columns, day_rows))))

    def platform_row(name: str | Html, totals: Totals) -> list[Any]:
        return [name, cash(totals.spend), count(totals.clicks), cash(totals.cost_per_click), percent(totals.click_rate)]

    platform_rows = [platform_row(keyed(*platform(key)), by_platform[key]) for key in keys]
    platform_columns = [("Platform", False), ("Spend", True), ("Clicks", True), ("Cost per click", True), ("Click rate", True)]
    platform_card = card("By platform", period.label, data_table(platform_columns, platform_rows, platform_row("Total", current)))
    return Html(f'{kpis}<div class="cards">{spend_card}{platform_card}</div>')


def render(range_key: str) -> str:
    status, settings = get_status(), get_settings()
    period = get_period(range_key, settings)
    try:
        rows = run_query("paid_media_daily", date_params(period.previous_start, period.end))["rows"]
        content = overview(period, rows)
    except InseeqError as error:
        content = error_state(error)
    return frame(TITLE, page_header(TITLE, period), content, status, period.timezone)
