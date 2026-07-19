from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router

OPENAPI_TAGS = [
    {"name": "系统", "description": "服务健康检查与运行状态。"},
    {"name": "市场", "description": "交易时段、行情更新时间及数据源健康状态。"},
    {"name": "异动", "description": "盘中预测、盘后系统计算和历史异动榜单。所有结果均不代表交易所确认。"},
    {"name": "证券", "description": "单只股票的基础信息、基准指数及偏离值计算明细。"},
    {"name": "自选", "description": "当前用户的自选股票查询、添加和移除。阶段 1 暂存于进程内存。"},
    {"name": "提醒", "description": "单只股票的异动提醒开关。阶段 1 只保存设置，不发送微信消息。"},
]


def create_app() -> FastAPI:
    application = FastAPI(
        title="异动雷达后端接口文档",
        version="0.1.0",
        description=(
            "异动雷达内部 MVP 的前后端接口契约。\n\n"
            "当前阶段使用内存模拟行情，用于完成小程序联调；后续会替换为 PostgreSQL、Redis 和真实行情适配器。\n\n"
            "**重要说明：所有异动状态均为系统按公开规则计算，不代表交易所最终认定，也不构成投资建议。**"
        ),
        openapi_tags=OPENAPI_TAGS,
        docs_url="/docs",
        redoc_url="/redoc",
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
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "change-radar-api"}

    return application


app = create_app()
