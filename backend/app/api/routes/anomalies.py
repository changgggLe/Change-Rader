from fastapi import APIRouter, Depends

from app.models.api import AnomalyListResponse
from app.repositories.database_market import DatabaseMarketRepository
from app.repositories.dependencies import get_market_repository

router = APIRouter(prefix="/anomalies", tags=["异动"])


@router.get(
    "/intraday",
    response_model=AnomalyListResponse,
    summary="查询盘中预计异动榜单",
    description=(
        "按最新盘中价格计算正向异动、严重异动和接近异动。结果会随价格变化，"
        "只表示系统预测，不是收盘结果。小程序盘中页面每 10～15 秒调用一次。"
    ),
    response_description="盘中异动股票及计算摘要",
)
def list_intraday_anomalies(repository: DatabaseMarketRepository = Depends(get_market_repository)) -> AnomalyListResponse:
    return repository.anomalies("INTRADAY")


@router.get(
    "/confirmed",
    response_model=AnomalyListResponse,
    summary="查询盘后系统计算榜单",
    description=(
        "使用收盘行情计算当日异动结果。接口名称中的 confirmed 仅表示系统盘后结果已经固化，"
        "不代表交易所公告确认。"
    ),
    response_description="盘后系统计算的异动股票列表",
)
def list_confirmed_anomalies(repository: DatabaseMarketRepository = Depends(get_market_repository)) -> AnomalyListResponse:
    return repository.anomalies("AFTER_HOURS")


@router.get(
    "/history",
    response_model=AnomalyListResponse,
    summary="查询历史异动事件",
    description="返回新规生效日之后保存的历史系统计算事件。阶段 1 暂时返回模拟数据。",
    response_description="历史异动事件列表",
)
def list_anomaly_history(repository: DatabaseMarketRepository = Depends(get_market_repository)) -> AnomalyListResponse:
    return repository.anomalies("HISTORY")
