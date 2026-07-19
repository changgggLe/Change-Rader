from fastapi import APIRouter

from app.models.api import MarketStatusResponse
from app.repositories.mock_market import repository

router = APIRouter(prefix="/market", tags=["市场"])


@router.get(
    "/status",
    response_model=MarketStatusResponse,
    summary="查询当前市场和数据状态",
    description=(
        "返回当前是盘中还是盘后、最近行情时间、建议刷新间隔及数据源健康状态。"
        "小程序首页使用该接口决定展示“盘中监测中”或“盘后快照”。"
    ),
    response_description="市场运行状态",
)
def get_market_status() -> MarketStatusResponse:
    return repository.market_status()
