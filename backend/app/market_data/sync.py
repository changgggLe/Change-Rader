from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.cache.service import CacheService
from app.db.models import AnomalyEvent, DailyQuote, IndexDailyQuote, RuleVersion, SecurityMaster
from app.market_data.eastmoney import BOARDS, SOURCE as EASTMONEY_SOURCE, BoardDefinition, DailyBar, EastmoneyClient, SpotQuote
from app.market_data.engine import ReturnPoint, WindowResult, calculate_three_day, calculate_window
from app.market_data.sina import SOURCE as SINA_SOURCE, SinaSpotClient
from app.settings.config import Settings

SHANGHAI = ZoneInfo("Asia/Shanghai")
REAL_DATA_HEALTH = "DEGRADED"  # 候选池模式，真实数据但尚非全市场历史覆盖


def active_market_source(settings: Settings) -> str:
    return EASTMONEY_SOURCE if settings.market_data_provider == "eastmoney" else SINA_SOURCE


def build_market_client(settings: Settings) -> SinaSpotClient | EastmoneyClient:
    client_class = EastmoneyClient if settings.market_data_provider == "eastmoney" else SinaSpotClient
    return client_class(settings.market_http_timeout_seconds, settings.market_http_use_environment_proxy)


def is_trading_time(now: datetime) -> bool:
    current = now.astimezone(SHANGHAI)
    if current.weekday() >= 5:
        return False
    return time(9, 15) <= current.time() <= time(11, 30) or time(13, 0) <= current.time() <= time(15, 0)


def _upsert_security(session: Session, quote: SpotQuote) -> SecurityMaster:
    security = session.get(SecurityMaster, quote.symbol)
    board = quote.board
    if security is None:
        security = SecurityMaster(symbol=quote.symbol)
        session.add(security)
    security.exchange = board.exchange
    security.board = board.board
    security.board_label = board.board_label
    security.name = quote.name
    security.status = "ACTIVE"
    security.benchmark_code = board.benchmark_code
    security.benchmark_name = board.benchmark_name
    security.price_limit_type = board.price_limit_type
    return security


def _upsert_stock_bar(session: Session, symbol: str, bar: DailyBar, source_time: datetime, source: str) -> None:
    row = session.scalar(
        select(DailyQuote).where(
            DailyQuote.symbol == symbol,
            DailyQuote.trade_date == bar.trade_date,
            DailyQuote.source == source,
        )
    )
    if row is None:
        row = DailyQuote(symbol=symbol, trade_date=bar.trade_date, source=source)
        session.add(row)
    row.open_price = bar.open_price
    row.high_price = bar.high_price
    row.low_price = bar.low_price
    row.close_price = bar.close_price
    row.change_percent = bar.change_percent
    row.volume = bar.volume
    row.source_time = source_time
    row.quality_status = "VALID"


def _upsert_spot(session: Session, quote: SpotQuote, trade_date, source_time: datetime, source: str) -> None:
    row = session.scalar(
        select(DailyQuote).where(
            DailyQuote.symbol == quote.symbol,
            DailyQuote.trade_date == trade_date,
            DailyQuote.source == source,
        )
    )
    if row is None:
        row = DailyQuote(symbol=quote.symbol, trade_date=trade_date, source=source)
        session.add(row)
    row.open_price = quote.open_price
    row.high_price = quote.high_price
    row.low_price = quote.low_price
    row.close_price = quote.last_price
    row.previous_close = quote.previous_close
    row.change_percent = quote.change_percent
    row.volume = quote.volume
    row.source_time = source_time
    row.quality_status = "VALID"


def _upsert_index_bar(session: Session, board: BoardDefinition, bar: DailyBar, source: str) -> None:
    row = session.scalar(
        select(IndexDailyQuote).where(
            IndexDailyQuote.index_code == board.benchmark_code,
            IndexDailyQuote.trade_date == bar.trade_date,
            IndexDailyQuote.source == source,
        )
    )
    if row is None:
        row = IndexDailyQuote(index_code=board.benchmark_code, trade_date=bar.trade_date, source=source)
        session.add(row)
    row.index_name = board.benchmark_name
    row.close_value = bar.close_price
    row.change_percent = bar.change_percent


def _percent(value: Decimal) -> str:
    return f"{value:+.2f}%"


def _metric(key: str, label: str, result: WindowResult | None, threshold: Decimal) -> dict:
    deviation = result.deviation if result else Decimal("0")
    progress = max(0, min(100, int(deviation / threshold * 100)))
    return {
        "key": key,
        "label": label,
        "current": _percent(deviation) if result else "--",
        "threshold": f"{threshold:.0f}%",
        "progress": progress,
        "triggered": bool(result and result.triggered),
    }


def _build_event(
    quote: SpotQuote,
    points: list[ReturnPoint],
    quote_time: datetime,
    mode: str,
    rule_version_id: int | None,
) -> AnomalyEvent | None:
    three_threshold = Decimal("20") if quote.board.board == "MAIN" else Decimal("30")
    three = calculate_three_day(points, three_threshold, quote.board.board)
    ten = calculate_window(points, 10, Decimal("100"), quote.board.board)
    thirty = calculate_window(points, 30, Decimal("200"), quote.board.board)

    severe = [result for result in (ten, thirty) if result and result.triggered]
    if severe:
        primary = max(severe, key=lambda item: item.deviation / item.threshold)
        status, status_label, status_type = "SEVERE", "严重异动", "severe"
        rule_note = f"{primary.days} 日累计偏离值达到 {primary.threshold:.0f}%"
    elif three and three.triggered:
        primary = three
        status, status_label, status_type = "SYSTEM_TRIGGERED", "系统触发", "triggered"
        rule_note = f"{primary.days} 个交易日累计偏离值达到 {three_threshold:.0f}%"
    else:
        price_limit = Decimal("10") if quote.board.price_limit_type == "NORMAL_10" else Decimal("20")
        potential_points = list(points)
        if potential_points:
            last = potential_points[-1]
            potential_points[-1] = ReturnPoint(last.trade_date, max(last.stock_change, price_limit), last.benchmark_change)
        potential = calculate_three_day(potential_points, three_threshold, quote.board.board)
        if not (three and potential and potential.triggered):
            return None
        primary = three
        status, status_label, status_type = "NEAR", "接近异动", "near"
        rule_note = "按当日涨停价测算可触发 3 日异动阈值"

    return AnomalyEvent(
        symbol=quote.symbol,
        rule_version_id=rule_version_id,
        mode=mode,
        status=status,
        status_label=status_label,
        status_type=status_type,
        rule_note=rule_note,
        quote_time=quote_time,
        data_health=REAL_DATA_HEALTH,
        last_price=quote.last_price,
        day_change=quote.change_percent,
        display_change=primary.deviation,
        window_start=primary.start,
        window_end=primary.end,
        stock_return=primary.stock_return,
        benchmark_return=primary.benchmark_return,
        deviation=primary.deviation,
        threshold=primary.threshold,
        metrics=[
            _metric("THREE_DAY", "3 日偏离值", three, three_threshold),
            _metric("TEN_DAY", "10 日严重异动", ten, Decimal("100")),
            _metric("THIRTY_DAY", "30 日严重异动", thirty, Decimal("200")),
        ],
    )


def sync_market_data(session: Session, cache: CacheService, settings: Settings) -> dict[str, int | str]:
    spot_client = build_market_client(settings)
    source = active_market_source(settings)
    now = datetime.now(SHANGHAI)

    # 免费站点对同一 IP 的并发较敏感，实时排行按板块顺序获取更稳定。
    quotes = [quote for board in BOARDS for quote in spot_client.top_movers(board, settings.market_candidate_limit_per_board)]
    index_histories = {board.benchmark_code: spot_client.history(board.benchmark_code, 45, is_index=True) for board in BOARDS}

    if not quotes or not any(index_histories.values()):
        raise RuntimeError("真实行情返回空数据")

    existing_counts = dict(
        session.execute(
            select(DailyQuote.symbol, func.count(DailyQuote.id))
            .where(DailyQuote.symbol.in_([quote.symbol for quote in quotes]), DailyQuote.source == source)
            .group_by(DailyQuote.symbol)
        ).all()
    )
    needs_history = [quote for quote in quotes if existing_counts.get(quote.symbol, 0) < 35]
    histories: dict[str, list[DailyBar]] = {}
    for quote in needs_history:
        try:
            histories[quote.symbol] = spot_client.history(quote.symbol, 45)
        except Exception:
            histories[quote.symbol] = []

    latest_trade_date = max(bar.trade_date for bars in index_histories.values() for bar in bars)
    for quote in quotes:
        _upsert_security(session, quote)
        for bar in histories.get(quote.symbol, []):
            _upsert_stock_bar(session, quote.symbol, bar, now, source)
        # 历史日线通常已经包含当天；先落库，再用实时快照覆盖同一行。
        session.flush()
        _upsert_spot(session, quote, latest_trade_date, now, source)
    for board in BOARDS:
        for bar in index_histories[board.benchmark_code]:
            _upsert_index_bar(session, board, bar, source)
    session.flush()

    mode = "INTRADAY" if is_trading_time(now) else "AFTER_HOURS"
    if mode == "INTRADAY":
        session.execute(delete(AnomalyEvent).where(AnomalyEvent.mode == mode))
    else:
        session.execute(delete(AnomalyEvent).where(AnomalyEvent.mode == mode, AnomalyEvent.window_end == latest_trade_date))
    session.execute(delete(AnomalyEvent).where(AnomalyEvent.data_health == "HEALTHY"))

    rule_version_id = session.scalar(select(RuleVersion.id).order_by(RuleVersion.effective_from.desc()))
    events = 0
    for quote in quotes:
        stock_rows = session.execute(
            select(DailyQuote.trade_date, DailyQuote.change_percent)
            .where(DailyQuote.symbol == quote.symbol, DailyQuote.source == source)
            .order_by(DailyQuote.trade_date)
        ).all()
        index_rows = dict(
            session.execute(
                select(IndexDailyQuote.trade_date, IndexDailyQuote.change_percent).where(
                    IndexDailyQuote.index_code == quote.board.benchmark_code,
                    IndexDailyQuote.source == source,
                )
            ).all()
        )
        points = [ReturnPoint(day, change, index_rows[day]) for day, change in stock_rows if day in index_rows]
        event = _build_event(quote, points, now, mode, rule_version_id)
        if event is not None:
            session.add(event)
            events += 1

    session.commit()
    cache.delete_prefix("market:")
    cache.delete_prefix("anomaly:")
    return {"source": source, "quotes": len(quotes), "backfilled": len(needs_history), "events": events, "mode": mode}


def sync_watch_symbol(session: Session, cache: CacheService, settings: Settings, symbol: str) -> bool:
    """按代码补齐一只自选股及其基准指数，不要求它已进入异动候选池。"""
    client = build_market_client(settings)
    source = active_market_source(settings)
    quote = client.quote(symbol)
    if quote is None:
        return False
    stock_history = client.history(symbol, 45)
    index_history = client.history(quote.board.benchmark_code, 45, is_index=True)
    if not stock_history or not index_history:
        return False
    now = datetime.now(SHANGHAI)
    _upsert_security(session, quote)
    for bar in stock_history:
        _upsert_stock_bar(session, symbol, bar, now, source)
    session.flush()
    latest_trade_date = index_history[-1].trade_date
    _upsert_spot(session, quote, latest_trade_date, now, source)
    for bar in index_history:
        _upsert_index_bar(session, quote.board, bar, source)
    session.commit()
    cache.delete_prefix("market:")
    cache.delete_prefix("anomaly:")
    return True
