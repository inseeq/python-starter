import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date

from app.format import short_day
from app.pages import Html, swatch, text

# Series color classes in a fixed order, checked for color blindness. Give each entity one and keep it.
COLORS = ("s1", "s2", "s3", "s4")
MUTED = "muted"
X_LABELS = 6
Y_TICKS = 4

Format = Callable[[float], str]


@dataclass(frozen=True)
class Series:
    key: str
    label: str
    color: str
    values: list[float]


def nice_step(maximum: float, ticks: int) -> float:
    raw = maximum / ticks
    power = 10 ** math.floor(math.log10(raw))
    return next((step for step in (1, 2, 2.5, 5, 10) if step * power >= raw), 10) * power


def y_ticks(maximum: float) -> list[float]:
    if maximum <= 0:
        return [0]
    step = nice_step(maximum, Y_TICKS)
    return [index * step for index in range(math.ceil(round(maximum / step, 9)) + 1)]


def x_label_indexes(length: int) -> dict[int, bool]:
    """The days that get a label, counted back from the last, each with whether a phone hides it."""
    every = max(1, math.ceil(length / X_LABELS))
    return {index: rank % 2 == 1 for rank, index in enumerate(range(length - 1, -1, -every))}


def _pct(value: float, top: float) -> str:
    return f"{value / top * 100 if top > 0 else 0:.2f}%"


def legend(series: Sequence[Series]) -> str:
    if len(series) < 2:
        return ""
    items = "".join(f"<li>{swatch(s.color)}{text(s.label)}</li>" for s in series)
    return f'<ul class="legend">{items}</ul>'


def _tooltip(day: date, series: Sequence[Series], index: int, fmt: Format) -> str:
    rows = "".join(f'<span class="tip-row">{swatch(s.color)}{text(s.label)}<b>{text(fmt(s.values[index]))}</b></span>' for s in series)
    if len(series) > 1:
        total = sum(s.values[index] for s in series)
        rows += f'<span class="tip-row tip-total">Total<b>{text(fmt(total))}</b></span>'
    return f'<div class="tip" role="tooltip"><strong>{text(short_day(day))}</strong>{rows}</div>'


def column_chart(days: Sequence[date], series: Sequence[Series], fmt: Format, axis_fmt: Format, label: str) -> Html:
    """Columns per day, stacked when there is more than one series. Hover a day for its numbers, with no script."""
    totals = [sum(s.values[i] for s in series) for i in range(len(days))]
    ticks = y_ticks(max(totals, default=0))
    top = ticks[-1] or 1
    labelled = x_label_indexes(len(days))
    grid = "".join(f'<div class="gridline" style="bottom:{_pct(tick, top)}"><span>{text(axis_fmt(tick))}</span></div>' for tick in ticks)
    columns = []
    for i, day in enumerate(days):
        segments = "".join(
            f'<div class="seg {s.color}" style="flex-grow:{s.values[i] / totals[i]:.4f}"></div>' for s in series if s.values[i] > 0
        )
        xlabel = f'<span class="xlabel{" alt" if labelled[i] else ""}">{text(short_day(day))}</span>' if i in labelled else ""
        columns.append(
            f'<div class="col{" flip" if i >= len(days) / 2 else ""}">'
            f'<div class="stack" style="height:{_pct(totals[i], top)}">{segments}</div>'
            f"{xlabel}{_tooltip(day, series, i, fmt)}</div>"
        )
    return Html(
        f'<figure class="chart" aria-label="{text(label)}">{legend(series)}<div class="plot">'
        f'<div class="grid" aria-hidden="true">{grid}</div>'
        f'<div class="cols" style="--n:{len(days)}">{"".join(columns)}</div></div></figure>'
    )
