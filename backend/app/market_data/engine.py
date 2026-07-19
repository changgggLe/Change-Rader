from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import reduce
from operator import mul


@dataclass(frozen=True)
class ReturnPoint:
    trade_date: date
    stock_change: Decimal
    benchmark_change: Decimal


@dataclass(frozen=True)
class WindowResult:
    days: int
    start: date
    end: date
    stock_return: Decimal
    benchmark_return: Decimal
    deviation: Decimal
    threshold: Decimal

    @property
    def triggered(self) -> bool:
        return self.deviation >= self.threshold


def compounded(changes: list[Decimal]) -> Decimal:
    factor = reduce(mul, (Decimal("1") + value / Decimal("100") for value in changes), Decimal("1"))
    return (factor - Decimal("1")) * Decimal("100")


def calculate_window(points: list[ReturnPoint], days: int, threshold: Decimal, board: str) -> WindowResult | None:
    if len(points) < days:
        return None
    window = points[-days:]
    stock_return = compounded([point.stock_change for point in window])
    benchmark_return = compounded([point.benchmark_change for point in window])
    if board == "STAR":
        deviation = sum((point.stock_change - point.benchmark_change for point in window), Decimal("0"))
    else:
        deviation = stock_return - benchmark_return
    return WindowResult(days, window[0].trade_date, window[-1].trade_date, stock_return, benchmark_return, deviation, threshold)


def calculate_three_day(points: list[ReturnPoint], threshold: Decimal, board: str) -> WindowResult | None:
    candidates = [result for days in (1, 2, 3) if (result := calculate_window(points, days, threshold, board))]
    return max(candidates, key=lambda item: item.deviation, default=None)
