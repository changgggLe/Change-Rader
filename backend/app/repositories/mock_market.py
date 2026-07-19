from copy import deepcopy
from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.models.api import (
    AnomalyItem,
    AnomalyListResponse,
    MarketStatusResponse,
    RuleMetric,
    SecurityDetailResponse,
    WatchlistResponse,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


def metric(key: str, label: str, current: str, threshold: str, progress: int, triggered: bool) -> dict:
    return {
        "key": key,
        "label": label,
        "current": current,
        "threshold": threshold,
        "progress": progress,
        "triggered": triggered,
    }


SEED_ITEMS = [
    {
        "symbol": "603018", "name": "华星科技", "exchange": "SSE", "board": "MAIN", "board_label": "沪市主板",
        "last_price": "18.46", "day_change": "+9.98%", "display_change": "+22.31%", "benchmark_code": "000002",
        "benchmark_name": "上证A指", "window_start": date(2026, 7, 15), "window_end": date(2026, 7, 17),
        "stock_return": "+24.08%", "benchmark_return": "+1.77%", "deviation": "+22.31%", "threshold": "20.00%",
        "status": "SYSTEM_TRIGGERED", "status_label": "系统触发", "status_type": "triggered", "rule_note": "3 日偏离值超过 20%",
        "metrics": [metric("THREE_DAY", "3 日偏离值", "22.31%", "20%", 100, True), metric("TEN_DAY", "10 日严重异动", "48.20%", "100%", 48, False), metric("THIRTY_DAY", "30 日严重异动", "76.44%", "200%", 38, False)],
        "watched": False, "alerted": False,
    },
    {
        "symbol": "301219", "name": "腾越新材", "exchange": "SZSE", "board": "CHINEXT", "board_label": "创业板",
        "last_price": "42.80", "day_change": "+15.36%", "display_change": "+103.42%", "benchmark_code": "399106",
        "benchmark_name": "深证综指", "window_start": date(2026, 7, 6), "window_end": date(2026, 7, 17),
        "stock_return": "+108.31%", "benchmark_return": "+4.89%", "deviation": "+103.42%", "threshold": "100.00%",
        "status": "SEVERE", "status_label": "严重异动", "status_type": "severe", "rule_note": "10 日偏离值超过 100%",
        "metrics": [metric("THREE_DAY", "3 日偏离值", "31.20%", "30%", 100, True), metric("TEN_DAY", "10 日严重异动", "103.42%", "100%", 100, True), metric("THIRTY_DAY", "30 日严重异动", "164.50%", "200%", 82, False)],
        "watched": False, "alerted": False,
    },
    {
        "symbol": "688256", "name": "云帆芯片", "exchange": "SSE", "board": "STAR", "board_label": "科创板",
        "last_price": "67.12", "day_change": "+18.66%", "display_change": "+18.66%", "benchmark_code": "000002",
        "benchmark_name": "上证A指", "window_start": date(2026, 7, 15), "window_end": date(2026, 7, 17),
        "stock_return": "+37.16%", "benchmark_return": "+2.44%", "deviation": "+34.72%", "threshold": "30.00%",
        "status": "SEVERE", "status_label": "严重异动", "status_type": "severe", "rule_note": "10 日内第 3 次同向异动",
        "metrics": [metric("THREE_DAY", "3 日偏离值", "34.72%", "30%", 100, True), metric("TEN_DAY", "10 日内同向异动", "第 3 次", "3 次", 100, True), metric("THIRTY_DAY", "30 日严重异动", "128.30%", "200%", 64, False)],
        "watched": True, "alerted": True,
    },
    {
        "symbol": "002517", "name": "东方智能", "exchange": "SZSE", "board": "MAIN", "board_label": "深市主板",
        "last_price": "12.86", "day_change": "+9.21%", "display_change": "+9.21%", "benchmark_code": "399106",
        "benchmark_name": "深证综指", "window_start": date(2026, 7, 15), "window_end": date(2026, 7, 17),
        "stock_return": "+21.63%", "benchmark_return": "+2.42%", "deviation": "+19.21%", "threshold": "20.00%",
        "status": "NEAR", "status_label": "接近异动", "status_type": "near", "rule_note": "今日涨停即可触发 3 日规则",
        "metrics": [metric("THREE_DAY", "3 日偏离值", "19.21%", "20%", 96, False), metric("TEN_DAY", "10 日严重异动", "61.80%", "100%", 62, False), metric("THIRTY_DAY", "30 日严重异动", "96.40%", "200%", 48, False)],
        "watched": True, "alerted": False,
    },
]


class MockMarketRepository:
    def __init__(self) -> None:
        self._items = deepcopy(SEED_ITEMS)

    @staticmethod
    def now() -> datetime:
        return datetime.now(SHANGHAI)

    def market_status(self) -> MarketStatusResponse:
        return MarketStatusResponse(market_status="TRADING", quote_time=self.now(), data_health="HEALTHY")

    def anomalies(self, mode: str) -> AnomalyListResponse:
        status = "CLOSED" if mode == "AFTER_HOURS" else "TRADING"
        return AnomalyListResponse(market_status=status, quote_time=self.now(), data_health="HEALTHY", mode=mode, items=self._items)

    def security(self, symbol: str) -> SecurityDetailResponse | None:
        item = next((value for value in self._items if value["symbol"] == symbol), None)
        return SecurityDetailResponse(**item) if item else None

    def watchlist(self) -> WatchlistResponse:
        return WatchlistResponse(items=[AnomalyItem(**item) for item in self._items if item["watched"]])

    def set_watched(self, symbol: str, enabled: bool) -> bool:
        item = next((value for value in self._items if value["symbol"] == symbol), None)
        if item is None:
            return False
        item["watched"] = enabled
        return True

    def set_alerted(self, symbol: str, enabled: bool) -> bool:
        item = next((value for value in self._items if value["symbol"] == symbol), None)
        if item is None:
            return False
        item["alerted"] = enabled
        return True


repository = MockMarketRepository()
