from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SecurityMaster(TimestampMixin, Base):
    __tablename__ = "security_master"

    symbol: Mapped[str] = mapped_column(String(6), primary_key=True)
    exchange: Mapped[str] = mapped_column(String(8), index=True)
    board: Mapped[str] = mapped_column(String(16), index=True)
    board_label: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(64))
    list_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    benchmark_code: Mapped[str] = mapped_column(String(16))
    benchmark_name: Mapped[str] = mapped_column(String(64))
    price_limit_type: Mapped[str] = mapped_column(String(32), default="NORMAL_10")

    events: Mapped[list["AnomalyEvent"]] = relationship(back_populates="security")


class DailyQuote(TimestampMixin, Base):
    __tablename__ = "daily_quote"
    __table_args__ = (UniqueConstraint("symbol", "trade_date", "source", name="uq_daily_quote_symbol_date_source"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("security_master.symbol", ondelete="CASCADE"), index=True)
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    open_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    high_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    low_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    close_price: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    previous_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    change_percent: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    volume: Mapped[Decimal | None] = mapped_column(Numeric(24, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(32))
    source_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_status: Mapped[str] = mapped_column(String(16), default="VALID")


class IndexDailyQuote(TimestampMixin, Base):
    __tablename__ = "index_daily_quote"
    __table_args__ = (UniqueConstraint("index_code", "trade_date", "source", name="uq_index_quote_code_date_source"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    index_code: Mapped[str] = mapped_column(String(16), index=True)
    index_name: Mapped[str] = mapped_column(String(64))
    trade_date: Mapped[date] = mapped_column(Date, index=True)
    close_value: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    previous_close: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    change_percent: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    source: Mapped[str] = mapped_column(String(32))


class RuleVersion(TimestampMixin, Base):
    __tablename__ = "rule_version"
    __table_args__ = (UniqueConstraint("code", "effective_from", name="uq_rule_code_effective_from"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    exchange: Mapped[str] = mapped_column(String(8))
    board: Mapped[str] = mapped_column(String(16))
    window_days: Mapped[int]
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(18, 8), nullable=True)
    event_count_threshold: Mapped[int | None] = mapped_column(nullable=True)
    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AnomalyEvent(TimestampMixin, Base):
    __tablename__ = "anomaly_event"
    __table_args__ = (
        UniqueConstraint("symbol", "mode", "window_start", "window_end", "status", name="uq_anomaly_event_window"),
        Index("ix_anomaly_event_mode_quote_time", "mode", "quote_time"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("security_master.symbol", ondelete="CASCADE"), index=True)
    rule_version_id: Mapped[int | None] = mapped_column(ForeignKey("rule_version.id"), nullable=True)
    mode: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32))
    status_label: Mapped[str] = mapped_column(String(32))
    status_type: Mapped[str] = mapped_column(String(16))
    rule_note: Mapped[str] = mapped_column(String(256))
    quote_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    data_health: Mapped[str] = mapped_column(String(16), default="HEALTHY")
    last_price: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    day_change: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    display_change: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    window_start: Mapped[date] = mapped_column(Date)
    window_end: Mapped[date] = mapped_column(Date)
    stock_return: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    benchmark_return: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    deviation: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    threshold: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    metrics: Mapped[list[dict]] = mapped_column(JSON)

    security: Mapped[SecurityMaster] = relationship(back_populates="events")


class Watchlist(TimestampMixin, Base):
    __tablename__ = "watchlist"
    __table_args__ = (UniqueConstraint("user_key", "symbol", name="uq_watchlist_user_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_key: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("security_master.symbol", ondelete="CASCADE"), index=True)


class AlertSetting(TimestampMixin, Base):
    __tablename__ = "alert_setting"
    __table_args__ = (UniqueConstraint("user_key", "symbol", name="uq_alert_user_symbol"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_key: Mapped[str] = mapped_column(String(64), index=True)
    symbol: Mapped[str] = mapped_column(ForeignKey("security_master.symbol", ondelete="CASCADE"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
