from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


SOURCE = "EASTMONEY_PUBLIC"
TOKEN = "fa5fd1943c7b386f172d6893dbfba10b"


@dataclass(frozen=True)
class BoardDefinition:
    exchange: str
    board: str
    board_label: str
    filter_expression: str
    benchmark_code: str
    benchmark_name: str
    price_limit_type: str


BOARDS = (
    BoardDefinition("SSE", "MAIN", "沪市主板", "m:1+t:2", "000002", "上证A股指数", "NORMAL_10"),
    BoardDefinition("SZSE", "MAIN", "深市主板", "m:0+t:6", "399107", "深证A股指数", "NORMAL_10"),
    BoardDefinition("SZSE", "CHINEXT", "创业板", "m:0+t:80", "399102", "创业板综合指数", "GROWTH_20"),
    BoardDefinition("SSE", "STAR", "科创板", "m:1+t:23", "000688", "科创50指数", "GROWTH_20"),
)


def board_for_symbol(symbol: str) -> BoardDefinition | None:
    if symbol.startswith(("688", "689")):
        return BOARDS[3]
    if symbol.startswith(("300", "301")):
        return BOARDS[2]
    if symbol.startswith(("600", "601", "603", "605")):
        return BOARDS[0]
    if symbol.startswith(("000", "001", "002", "003")):
        return BOARDS[1]
    return None


@dataclass(frozen=True)
class SpotQuote:
    symbol: str
    name: str
    board: BoardDefinition
    last_price: Decimal
    change_percent: Decimal
    open_price: Decimal | None
    high_price: Decimal | None
    low_price: Decimal | None
    previous_close: Decimal | None
    volume: Decimal | None


@dataclass(frozen=True)
class DailyBar:
    trade_date: date
    open_price: Decimal
    close_price: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: Decimal
    change_percent: Decimal


def _decimal(value: Any) -> Decimal | None:
    if value in (None, "", "-"):
        return None
    return Decimal(str(value))


class EastmoneyClient:
    """东方财富公开网页接口适配器；仅用于内部 MVP，不代表数据授权。"""

    spot_url = "https://82.push2.eastmoney.com/api/qt/clist/get"
    quote_url = "https://push2.eastmoney.com/api/qt/stock/get"
    history_url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"

    def __init__(self, timeout_seconds: int = 12, use_environment_proxy: bool = False) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.trust_env = use_environment_proxy
        retry = Retry(total=2, connect=2, read=2, backoff_factor=0.3, status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def top_movers(self, board: BoardDefinition, limit: int) -> list[SpotQuote]:
        params = {
            "pn": 1,
            "pz": limit,
            "po": 1,
            "np": 1,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": 2,
            "invt": 2,
            "fid": "f3",
            "fs": board.filter_expression,
            "fields": "f2,f3,f5,f12,f14,f15,f16,f17,f18",
        }
        payload = self._get_json(self.spot_url, params)
        rows = (payload.get("data") or {}).get("diff") or {}
        values = rows.values() if isinstance(rows, dict) else rows
        result: list[SpotQuote] = []
        for row in values:
            last_price = _decimal(row.get("f2"))
            change_percent = _decimal(row.get("f3"))
            symbol = str(row.get("f12") or "")
            if len(symbol) != 6 or last_price is None or change_percent is None:
                continue
            result.append(
                SpotQuote(
                    symbol=symbol,
                    name=str(row.get("f14") or symbol),
                    board=board,
                    last_price=last_price,
                    change_percent=change_percent,
                    open_price=_decimal(row.get("f17")),
                    high_price=_decimal(row.get("f15")),
                    low_price=_decimal(row.get("f16")),
                    previous_close=_decimal(row.get("f18")),
                    volume=_decimal(row.get("f5")),
                )
            )
        return result

    def history(self, code: str, limit: int = 45, *, is_index: bool = False) -> list[DailyBar]:
        shanghai = code.startswith(("5", "6", "9")) or (is_index and code.startswith("000"))
        secid = f"{1 if shanghai else 0}.{code}"
        params = {
            "secid": secid,
            "klt": 101,
            "fqt": 0,
            "lmt": limit,
            "end": "20500101",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
            "ut": TOKEN,
        }
        payload = self._get_json(self.history_url, params)
        data = payload.get("data") or {}
        bars: list[DailyBar] = []
        for line in data.get("klines") or []:
            values = line.split(",")
            if len(values) < 9:
                continue
            bars.append(
                DailyBar(
                    trade_date=date.fromisoformat(values[0]),
                    open_price=Decimal(values[1]),
                    close_price=Decimal(values[2]),
                    high_price=Decimal(values[3]),
                    low_price=Decimal(values[4]),
                    volume=Decimal(values[5]),
                    change_percent=Decimal(values[8]),
                )
            )
        return bars

    def quote(self, symbol: str) -> SpotQuote | None:
        board = board_for_symbol(symbol)
        if board is None:
            return None
        secid = f"{1 if board.exchange == 'SSE' else 0}.{symbol}"
        params = {
            "secid": secid,
            "ut": TOKEN,
            "fltt": 2,
            "invt": 2,
            "fields": "f43,f44,f45,f46,f47,f57,f58,f60,f170",
        }
        data = self._get_json(self.quote_url, params).get("data") or {}
        last_price = _decimal(data.get("f43"))
        previous_close = _decimal(data.get("f60"))
        change_percent = _decimal(data.get("f170"))
        if last_price is None or previous_close is None or change_percent is None:
            return None
        return SpotQuote(
            symbol=symbol,
            name=str(data.get("f58") or symbol),
            board=board,
            last_price=last_price,
            change_percent=change_percent,
            open_price=_decimal(data.get("f46")),
            high_price=_decimal(data.get("f44")),
            low_price=_decimal(data.get("f45")),
            previous_close=previous_close,
            volume=_decimal(data.get("f47")),
        )

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self.session.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        if payload.get("rc") not in (None, 0):
            raise RuntimeError(f"东方财富接口返回错误 rc={payload.get('rc')}")
        return payload
