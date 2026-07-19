from datetime import datetime
from zoneinfo import ZoneInfo

from app.market_data.sync import is_trading_time

SHANGHAI = ZoneInfo("Asia/Shanghai")


def moment(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(2026, 7, 20, hour, minute, second, tzinfo=SHANGHAI)


def test_weekday_market_time_boundaries() -> None:
    assert is_trading_time(moment(9, 14, 59)) is False
    assert is_trading_time(moment(9, 15)) is True
    assert is_trading_time(moment(11, 30)) is True
    assert is_trading_time(moment(11, 30, 1)) is False
    assert is_trading_time(moment(13, 0)) is True
    assert is_trading_time(moment(15, 0)) is True
    assert is_trading_time(moment(15, 0, 1)) is False


def test_weekend_is_closed() -> None:
    saturday = datetime(2026, 7, 25, 10, 0, tzinfo=SHANGHAI)
    assert is_trading_time(saturday) is False
