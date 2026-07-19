from fastapi import APIRouter, Depends

from app.models.api import MarketStatusResponse
from app.repositories.database_market import DatabaseMarketRepository
from app.repositories.dependencies import get_market_repository

router = APIRouter(prefix="/market", tags=["市场"])


@router.get(
    "/status",
    response_model=MarketStatusResponse,
    summary="查询当前市场和数据状态",
    description=(
        "按北京时间自动返回盘中或非交易状态、最近行情时间、建议刷新间隔及数据源健康状态。"
        "工作日 09:15～11:30、13:00～15:00 为盘中，其余时间为非交易状态；用户不能手动切换。"
    ),
    response_description="市场运行状态",
)
def get_market_status(repository: DatabaseMarketRepository = Depends(get_market_repository)) -> MarketStatusResponse:
    return repository.market_status()
