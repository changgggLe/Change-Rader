from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AlertSetting, AnomalyEvent, DailyQuote, IndexDailyQuote, RuleVersion, SecurityMaster, Watchlist
from app.repositories.mock_market import SEED_ITEMS

SHANGHAI = ZoneInfo("Asia/Shanghai")


def decimal_value(value: str) -> Decimal:
    cleaned = value.replace("%", "").replace("+", "").strip()
    return Decimal(cleaned)


def seed_database(session: Session, user_key: str) -> None:
    if session.scalar(select(func.count()).select_from(SecurityMaster)):
        return

    rule = RuleVersion(
        code="POSITIVE_DEVIATION_20260706",
        name="正向价格异常波动规则",
        exchange="ALL",
        board="ALL",
        window_days=3,
        threshold=Decimal("20"),
        effective_from=date(2026, 7, 6),
    )
    session.add(rule)
    session.flush()

    quote_time = datetime.now(SHANGHAI)
    index_seen: set[str] = set()
    for item in SEED_ITEMS:
        session.add(
            SecurityMaster(
                symbol=item["symbol"],
                exchange=item["exchange"],
                board=item["board"],
                board_label=item["board_label"],
                name=item["name"],
                status="ACTIVE",
                benchmark_code=item["benchmark_code"],
                benchmark_name=item["benchmark_name"],
                price_limit_type="NORMAL_10" if item["board"] == "MAIN" else "GROWTH_20",
            )
        )
        session.add(
            DailyQuote(
                symbol=item["symbol"],
                trade_date=item["window_end"],
                close_price=decimal_value(item["last_price"]),
                change_percent=decimal_value(item["day_change"]),
                source="DATABASE_DEMO",
                source_time=quote_time,
                quality_status="VALID",
            )
        )
        if item["benchmark_code"] not in index_seen:
            session.add(
                IndexDailyQuote(
                    index_code=item["benchmark_code"],
                    index_name=item["benchmark_name"],
                    trade_date=item["window_end"],
                    close_value=Decimal("1000"),
                    change_percent=decimal_value(item["benchmark_return"]),
                    source="DATABASE_DEMO",
                )
            )
            index_seen.add(item["benchmark_code"])

        for mode in ("INTRADAY", "AFTER_HOURS"):
            session.add(
                AnomalyEvent(
                    symbol=item["symbol"],
                    rule_version_id=rule.id,
                    mode=mode,
                    status=item["status"],
                    status_label=item["status_label"],
                    status_type=item["status_type"],
                    rule_note=item["rule_note"],
                    quote_time=quote_time,
                    data_health="HEALTHY",
                    last_price=decimal_value(item["last_price"]),
                    day_change=decimal_value(item["day_change"]),
                    display_change=decimal_value(item["display_change"]),
                    window_start=item["window_start"],
                    window_end=item["window_end"],
                    stock_return=decimal_value(item["stock_return"]),
                    benchmark_return=decimal_value(item["benchmark_return"]),
                    deviation=decimal_value(item["deviation"]),
                    threshold=decimal_value(item["threshold"]),
                    metrics=item["metrics"],
                )
            )
        if item["watched"]:
            session.add(Watchlist(user_key=user_key, symbol=item["symbol"]))
        if item["alerted"]:
            session.add(AlertSetting(user_key=user_key, symbol=item["symbol"], enabled=True))

    session.commit()
