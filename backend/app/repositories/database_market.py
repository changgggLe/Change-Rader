from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.cache.service import CacheService
from app.db.models import AlertSetting, AnomalyEvent, DailyQuote, IndexDailyQuote, SecurityMaster, Watchlist
from app.market_data.engine import ReturnPoint, calculate_three_day, calculate_window
from app.market_data.sync import is_trading_time, sync_watch_symbol
from app.models.api import AnomalyItem, AnomalyListResponse, MarketStatusResponse, SecurityDetailResponse, WatchlistResponse
from app.settings.config import Settings

SHANGHAI = ZoneInfo("Asia/Shanghai")


def percent(value: Decimal) -> str:
    return f"{value:+.2f}%"


class DatabaseMarketRepository:
    def __init__(self, session: Session, cache: CacheService, settings: Settings, user_key: str) -> None:
        self.session = session
        self.cache = cache
        self.settings = settings
        self.user_key = user_key

    def _real_data_ready(self) -> bool:
        return bool(self.session.scalar(select(func.count()).select_from(DailyQuote).where(DailyQuote.source == "SINA_PUBLIC")))

    def market_status(self) -> MarketStatusResponse:
        cache_key = "market:status"
        cached = self.cache.get_json(cache_key)
        if cached:
            return MarketStatusResponse.model_validate(cached)
        real_mode = self.settings.market_data_provider != "database_demo"
        ready = self._real_data_ready() if real_mode else False
        quote_time = (
            self.session.scalar(select(func.max(DailyQuote.source_time)).where(DailyQuote.source == "SINA_PUBLIC"))
            if ready
            else self.session.scalar(select(func.max(AnomalyEvent.quote_time)))
        ) or datetime.now(SHANGHAI)
        now = datetime.now(SHANGHAI)
        trading = is_trading_time(now)
        response = MarketStatusResponse(
            market_status="TRADING" if trading else "CLOSED",
            quote_time=quote_time,
            data_health="DEGRADED" if real_mode else "HEALTHY",
            source=("SINA_PUBLIC_PARTIAL" if ready else "PUBLIC_DATA_SYNCING") if real_mode else "DATABASE_DEMO",
        )
        self.cache.set_json(cache_key, response.model_dump(mode="json", by_alias=True), 1)
        return response

    def anomalies(self, mode: str) -> AnomalyListResponse:
        cache_key = f"anomaly:ranking:{mode.lower()}:{self.user_key}"
        cached = self.cache.get_json(cache_key)
        if cached:
            return AnomalyListResponse.model_validate(cached)

        real_mode = self.settings.market_data_provider != "database_demo"
        if real_mode and not self._real_data_ready():
            return AnomalyListResponse(
                market_status="CLOSED" if mode == "AFTER_HOURS" else "TRADING",
                quote_time=datetime.now(SHANGHAI),
                data_health="DEGRADED",
                mode=mode,
                items=[],
            )
        query = select(AnomalyEvent).options(joinedload(AnomalyEvent.security)).order_by(AnomalyEvent.quote_time.desc(), AnomalyEvent.id)
        if real_mode:
            query = query.where(AnomalyEvent.data_health == "DEGRADED")
        if mode != "HISTORY":
            query = query.where(AnomalyEvent.mode == mode)
        events = self.session.scalars(query).unique().all()
        watched, alerted = self._user_states()
        items = [self._to_item(event, event.symbol in watched, event.symbol in alerted) for event in events]
        response = AnomalyListResponse(
            market_status="CLOSED" if mode == "AFTER_HOURS" else "TRADING",
            quote_time=events[0].quote_time if events else datetime.now(SHANGHAI),
            data_health="DEGRADED" if real_mode else "HEALTHY",
            mode=mode,
            items=items,
        )
        self.cache.set_json(cache_key, response.model_dump(mode="json", by_alias=True), 30)
        return response

    def security(self, symbol: str) -> SecurityDetailResponse | None:
        event = self.session.scalar(
            select(AnomalyEvent)
            .options(joinedload(AnomalyEvent.security))
            .where(AnomalyEvent.symbol == symbol)
            .order_by(AnomalyEvent.quote_time.desc(), AnomalyEvent.mode.desc())
        )
        watched, alerted = self._user_states(symbol)
        if event is None:
            security = self.session.get(SecurityMaster, symbol)
            if security is None:
                return None
            item = self._normal_item(security, symbol in watched, symbol in alerted)
            return SecurityDetailResponse(**item.model_dump()) if item else None
        item = self._to_item(event, symbol in watched, symbol in alerted)
        return SecurityDetailResponse(**item.model_dump())

    def watchlist(self) -> WatchlistResponse:
        symbols = self.session.scalars(select(Watchlist.symbol).where(Watchlist.user_key == self.user_key)).all()
        items: list[AnomalyItem] = []
        for symbol in symbols:
            detail = self.security(symbol)
            if detail:
                items.append(AnomalyItem(**detail.model_dump(exclude={"disclaimer"})))
        return WatchlistResponse(items=items)

    def set_watched(self, symbol: str, enabled: bool) -> bool:
        security = self.session.get(SecurityMaster, symbol)
        has_real_quote = bool(
            self.session.scalar(
                select(func.count()).select_from(DailyQuote).where(
                    DailyQuote.symbol == symbol,
                    DailyQuote.source == "SINA_PUBLIC",
                )
            )
        )
        needs_real_sync = enabled and self.settings.market_data_provider != "database_demo" and not has_real_quote
        if security is None or needs_real_sync:
            if not enabled or self.settings.market_data_provider == "database_demo":
                return False
            try:
                if not sync_watch_symbol(self.session, self.cache, self.settings, symbol):
                    return False
            except Exception:
                self.session.rollback()
                return False
        existing = self.session.scalar(select(Watchlist).where(Watchlist.user_key == self.user_key, Watchlist.symbol == symbol))
        if enabled and existing is None:
            self.session.add(Watchlist(user_key=self.user_key, symbol=symbol))
        if not enabled and existing is not None:
            self.session.delete(existing)
        self.session.commit()
        self.cache.delete_prefix("anomaly:ranking:")
        return True

    def set_alerted(self, symbol: str, enabled: bool) -> bool:
        if self.session.get(SecurityMaster, symbol) is None:
            return False
        setting = self.session.scalar(select(AlertSetting).where(AlertSetting.user_key == self.user_key, AlertSetting.symbol == symbol))
        if setting is None:
            setting = AlertSetting(user_key=self.user_key, symbol=symbol, enabled=enabled)
            self.session.add(setting)
        else:
            setting.enabled = enabled
        self.session.commit()
        self.cache.delete_prefix("anomaly:ranking:")
        return True

    def _user_states(self, symbol: str | None = None) -> tuple[set[str], set[str]]:
        watch_query = select(Watchlist.symbol).where(Watchlist.user_key == self.user_key)
        alert_query = select(AlertSetting.symbol).where(AlertSetting.user_key == self.user_key, AlertSetting.enabled.is_(True))
        if symbol:
            watch_query = watch_query.where(Watchlist.symbol == symbol)
            alert_query = alert_query.where(AlertSetting.symbol == symbol)
        return set(self.session.scalars(watch_query)), set(self.session.scalars(alert_query))

    @staticmethod
    def _to_item(event: AnomalyEvent, watched: bool, alerted: bool) -> AnomalyItem:
        security = event.security
        return AnomalyItem(
            symbol=security.symbol,
            name=security.name,
            exchange=security.exchange,
            board=security.board,
            board_label=security.board_label,
            last_price=f"{event.last_price:.2f}",
            day_change=percent(event.day_change),
            display_change=percent(event.display_change),
            benchmark_code=security.benchmark_code,
            benchmark_name=security.benchmark_name,
            window_start=event.window_start,
            window_end=event.window_end,
            stock_return=percent(event.stock_return),
            benchmark_return=percent(event.benchmark_return),
            deviation=percent(event.deviation),
            threshold=f"{event.threshold:.2f}%",
            status=event.status,
            status_label=event.status_label,
            status_type=event.status_type,
            rule_note=event.rule_note,
            metrics=event.metrics,
            watched=watched,
            alerted=alerted,
        )

    def _normal_item(self, security: SecurityMaster, watched: bool, alerted: bool) -> AnomalyItem | None:
        stock_rows = self.session.execute(
            select(DailyQuote.trade_date, DailyQuote.close_price, DailyQuote.change_percent)
            .where(DailyQuote.symbol == security.symbol, DailyQuote.source == "SINA_PUBLIC")
            .order_by(DailyQuote.trade_date)
        ).all()
        index_rows = dict(
            self.session.execute(
                select(IndexDailyQuote.trade_date, IndexDailyQuote.change_percent).where(
                    IndexDailyQuote.index_code == security.benchmark_code,
                    IndexDailyQuote.source == "SINA_PUBLIC",
                )
            ).all()
        )
        if not stock_rows:
            return None
        points = [ReturnPoint(day, change, index_rows[day]) for day, _, change in stock_rows if day in index_rows]
        if not points:
            return None
        threshold3 = Decimal("20") if security.board == "MAIN" else Decimal("30")
        three = calculate_three_day(points, threshold3, security.board)
        ten = calculate_window(points, 10, Decimal("100"), security.board)
        thirty = calculate_window(points, 30, Decimal("200"), security.board)
        primary = three or calculate_window(points, 1, threshold3, security.board)
        if primary is None:
            return None

        def metric(key: str, label: str, result, threshold: Decimal) -> dict:
            deviation = result.deviation if result else Decimal("0")
            return {
                "key": key,
                "label": label,
                "current": percent(deviation) if result else "--",
                "threshold": f"{threshold:.0f}%",
                "progress": max(0, min(100, int(deviation / threshold * 100))),
                "triggered": bool(result and result.triggered),
            }

        latest = stock_rows[-1]
        return AnomalyItem(
            symbol=security.symbol,
            name=security.name,
            exchange=security.exchange,
            board=security.board,
            board_label=security.board_label,
            last_price=f"{latest.close_price:.2f}",
            day_change=percent(latest.change_percent),
            display_change=percent(latest.change_percent),
            benchmark_code=security.benchmark_code,
            benchmark_name=security.benchmark_name,
            window_start=primary.start,
            window_end=primary.end,
            stock_return=percent(primary.stock_return),
            benchmark_return=percent(primary.benchmark_return),
            deviation=percent(primary.deviation),
            threshold=f"{primary.threshold:.2f}%",
            status="NORMAL",
            status_label="未触发",
            status_type="normal",
            rule_note="当前未触发价格异动规则",
            metrics=[
                metric("THREE_DAY", "3 日偏离值", three, threshold3),
                metric("TEN_DAY", "10 日严重异动", ten, Decimal("100")),
                metric("THIRTY_DAY", "30 日严重异动", thirty, Decimal("200")),
            ],
            watched=watched,
            alerted=alerted,
        )
