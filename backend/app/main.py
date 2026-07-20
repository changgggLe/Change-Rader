import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.router import api_router
from app.cache.service import build_cache
from app.db.seed import seed_database
from app.db.session import Database
from app.market_data.runner import market_sync_loop
from app.settings.config import Settings, get_settings

OPENAPI_TAGS = [
    {"name": "系统", "description": "服务健康检查与运行状态。"},
    {"name": "市场", "description": "交易时段、行情更新时间及数据源健康状态。"},
    {"name": "异动", "description": "盘中预测、盘后系统计算和历史异动榜单。所有结果均不代表交易所确认。"},
    {"name": "证券", "description": "单只股票的基础信息、基准指数及偏离值计算明细。"},
    {"name": "自选", "description": "当前用户的自选股票查询、添加和移除。数据持久化在数据库中。"},
    {"name": "提醒", "description": "单只股票的异动提醒开关。阶段 1 只保存设置，不发送微信消息。"},
]


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database = Database(settings.database_url)
        application.state.database = database
        application.state.cache = build_cache(settings)
        application.state.settings = settings
        application.state.market_sync = {"status": "idle", "result": None, "error": None}
        if settings.auto_create_tables:
            database.create_all()
        if settings.seed_demo_data:
            with database.session_factory() as session:
                seed_database(session, settings.internal_user_key)
        sync_task = None
        if settings.market_data_provider != "database_demo":
            sync_task = asyncio.create_task(market_sync_loop(application))
        yield
        if sync_task is not None:
            sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await sync_task
        application.state.cache.close()
        database.dispose()

    application = FastAPI(
        title="异动偏离预警器后端接口文档",
        version="0.1.0",
        description=(
            "异动偏离预警器内部 MVP 的前后端接口契约。\n\n"
            "当前默认接入新浪财经公开网页候选行情；本地使用 SQLite，CloudBase 部署使用关系型数据库。首次真实行情同步期间会明确标注降级状态。\n\n"
            "**重要说明：所有异动状态均为系统按公开规则计算，不代表交易所最终认定，也不构成投资建议。**"
        ),
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost", "http://127.0.0.1"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)

    @application.get(
        "/health",
        tags=["系统"],
        summary="检查后端服务是否正常",
        description="用于本地联调、部署健康检查和故障排查。返回 `ok` 表示 API 进程可以正常响应。",
        response_description="服务健康状态",
    )
    def health(request: Request) -> dict[str, str]:
        database_status = "ok"
        try:
            with request.app.state.database.session_factory() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            database_status = "error"
        cache_status = "ok" if request.app.state.cache.health() else "error"
        market_sync_status = request.app.state.market_sync["status"]
        overall = "ok" if database_status == "ok" and market_sync_status != "error" else "degraded"
        return {
            "status": overall,
            "service": "deviation-alert-api",
            "database": database_status,
            "cache": cache_status,
            "market_sync": market_sync_status,
        }

    return application


app = create_app()
