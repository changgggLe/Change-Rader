from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.market_data.eastmoney import BoardDefinition, DailyBar, SpotQuote, board_for_symbol

SOURCE = "SINA_PUBLIC"


class SinaSpotClient:
    """新浪财经公开排行接口，作为实时快照源。"""

    url = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"
    history_url = "https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketData.getKLineData"
    quote_url = "https://hq.sinajs.cn/list="
    nodes = {"SSE:MAIN": "sh_a", "SZSE:MAIN": "sz_a", "SZSE:CHINEXT": "cyb", "SSE:STAR": "kcb"}

    def __init__(self, timeout_seconds: int = 12, use_environment_proxy: bool = False) -> None:
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.trust_env = use_environment_proxy
        retry = Retry(total=3, connect=3, read=3, backoff_factor=0.4, status_forcelist=(429, 500, 502, 503, 504))
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def top_movers(self, board: BoardDefinition, limit: int) -> list[SpotQuote]:
        node = self.nodes[f"{board.exchange}:{board.board}"]
        params = {"page": 1, "num": min(100, max(limit * 3, 30)), "sort": "changepercent", "asc": 0, "node": node}
        response = self.session.get(self.url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        result: list[SpotQuote] = []
        for row in response.json():
            symbol = str(row.get("code") or "")
            if not self._belongs_to_board(symbol, board):
                continue
            trade = self._decimal(row.get("trade"))
            change = self._decimal(row.get("changepercent"))
            if trade is None or change is None:
                continue
            result.append(
                SpotQuote(
                    symbol=symbol,
                    name=str(row.get("name") or symbol),
                    board=board,
                    last_price=trade,
                    change_percent=change,
                    open_price=self._decimal(row.get("open")),
                    high_price=self._decimal(row.get("high")),
                    low_price=self._decimal(row.get("low")),
                    previous_close=self._decimal(row.get("settlement")),
                    volume=self._decimal(row.get("volume")),
                )
            )
            if len(result) >= limit:
                break
        return result

    def history(self, code: str, limit: int = 45, *, is_index: bool = False) -> list[DailyBar]:
        shanghai = code.startswith(("5", "6", "9")) or (is_index and code.startswith("000"))
        params = {"symbol": f"{'sh' if shanghai else 'sz'}{code}", "scale": 240, "ma": "no", "datalen": limit + 1}
        response = self.session.get(self.history_url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()
        rows = response.json()
        bars: list[DailyBar] = []
        previous_close: Decimal | None = None
        for row in rows:
            close_price = Decimal(str(row["close"]))
            if previous_close not in (None, Decimal("0")):
                change_percent = (close_price / previous_close - Decimal("1")) * Decimal("100")
                bars.append(
                    DailyBar(
                        trade_date=date.fromisoformat(row["day"]),
                        open_price=Decimal(str(row["open"])),
                        close_price=close_price,
                        high_price=Decimal(str(row["high"])),
                        low_price=Decimal(str(row["low"])),
                        volume=Decimal(str(row.get("volume") or 0)),
                        change_percent=change_percent,
                    )
                )
            previous_close = close_price
        return bars[-limit:]

    def quote(self, symbol: str) -> SpotQuote | None:
        board = board_for_symbol(symbol)
        if board is None:
            return None
        market = "sh" if board.exchange == "SSE" else "sz"
        response = self.session.get(
            f"{self.quote_url}{market}{symbol}",
            headers={"Referer": "https://finance.sina.com.cn/"},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        text = response.content.decode("gbk", errors="replace")
        if '=""' in text or '="' not in text:
            return None
        values = text.split('="', 1)[1].rsplit('"', 1)[0].split(",")
        if len(values) < 10 or not values[0]:
            return None
        previous_close = Decimal(values[2])
        last_price = Decimal(values[3])
        if previous_close <= 0 or last_price <= 0:
            return None
        return SpotQuote(
            symbol=symbol,
            name=values[0],
            board=board,
            last_price=last_price,
            change_percent=(last_price / previous_close - Decimal("1")) * Decimal("100"),
            open_price=Decimal(values[1]),
            high_price=Decimal(values[4]),
            low_price=Decimal(values[5]),
            previous_close=previous_close,
            volume=Decimal(values[8]),
        )

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        if value in (None, "", "-"):
            return None
        return Decimal(str(value))

    @staticmethod
    def _belongs_to_board(symbol: str, board: BoardDefinition) -> bool:
        if board.board == "STAR":
            return symbol.startswith(("688", "689"))
        if board.board == "CHINEXT":
            return symbol.startswith(("300", "301"))
        if board.exchange == "SSE":
            return symbol.startswith(("600", "601", "603", "605"))
        return symbol.startswith(("000", "001", "002", "003"))
