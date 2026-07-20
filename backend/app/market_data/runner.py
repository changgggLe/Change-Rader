from __future__ import annotations

import asyncio
from datetime import datetime, time
from zoneinfo import ZoneInfo

from fastapi import FastAPI

from app.market_data.sync import is_trading_time, sync_market_data

SHANGHAI = ZoneInfo("Asia/Shanghai")


async def market_sync_loop(application: FastAPI) -> None:
    """盘中按配置轮询；盘后启动时固化一次，之后只检查是否开市。"""
    synced_closed_marker = None
    while True:
        now = datetime.now(SHANGHAI)
        trading = is_trading_time(now)
        if now.weekday() >= 5:
            closed_phase = "WEEKEND"
        elif now.time() < time(9, 15):
            closed_phase = "PRE_OPEN"
        elif now.time() > time(15, 0):
            closed_phase = "POST_CLOSE"
        else:
            closed_phase = None  # 午间休市不采集，也不生成盘后事件
        closed_marker = (now.date(), closed_phase)
        should_sync = trading or (closed_phase is not None and synced_closed_marker != closed_marker)
        if should_sync:
            try:
                application.state.market_sync = {"status": "syncing", "result": None, "error": None}

                def run_once():
                    with application.state.database.session_factory() as session:
                        return sync_market_data(session, application.state.cache, application.state.settings)

                result = await asyncio.to_thread(run_once)
                application.state.market_sync = {"status": "ok", "result": result, "error": None}
                if result["mode"] == "AFTER_HOURS":
                    synced_closed_marker = closed_marker
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                application.state.market_sync = {"status": "error", "result": None, "error": str(exc)}
        await asyncio.sleep(application.state.settings.market_sync_interval_seconds if trading else 60)
