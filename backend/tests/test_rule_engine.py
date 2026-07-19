from datetime import date, timedelta
from decimal import Decimal

from app.market_data.engine import ReturnPoint, calculate_three_day, calculate_window


def points(stock: list[str], benchmark: list[str]) -> list[ReturnPoint]:
    start = date(2026, 7, 1)
    return [
        ReturnPoint(start + timedelta(days=index), Decimal(stock_change), Decimal(index_change))
        for index, (stock_change, index_change) in enumerate(zip(stock, benchmark, strict=True))
    ]


def test_main_board_uses_compounded_return_difference() -> None:
    result = calculate_window(points(["10", "10"], ["0", "0"]), 2, Decimal("20"), "MAIN")
    assert result is not None
    assert result.deviation == Decimal("21.00")
    assert result.triggered is True


def test_star_board_uses_sum_of_daily_deviations() -> None:
    result = calculate_window(points(["10", "10", "10"], ["1", "1", "1"]), 3, Decimal("30"), "STAR")
    assert result is not None
    assert result.deviation == Decimal("27")
    assert result.triggered is False


def test_three_day_rule_selects_best_window_within_three_days() -> None:
    result = calculate_three_day(points(["12", "-5", "15"], ["0", "0", "0"]), Decimal("20"), "MAIN")
    assert result is not None
    assert result.days == 3
    assert result.deviation > Decimal("20")
