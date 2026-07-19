from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path

from app.models.api import AlertSettingRequest, AlertSettingResponse
from app.repositories.database_market import DatabaseMarketRepository
from app.repositories.dependencies import get_market_repository

router = APIRouter(prefix="/alerts", tags=["提醒"])
StockSymbol = Annotated[str, Path(description="六位股票代码", pattern=r"^\d{6}$", examples=["603018"])]


@router.put(
    "/{symbol}",
    response_model=AlertSettingResponse,
    summary="更新股票异动提醒",
    description=(
        "开启或关闭指定股票的异动提醒设置。阶段 1 仅保存开关状态；"
        "接入微信订阅消息后，仍需用户主动完成微信授权。"
    ),
    response_description="保存后的提醒状态",
    responses={404: {"description": "股票代码不存在"}},
)
def update_alert(
    symbol: StockSymbol,
    payload: AlertSettingRequest,
    repository: DatabaseMarketRepository = Depends(get_market_repository),
) -> AlertSettingResponse:
    if not repository.set_alerted(symbol, payload.enabled):
        raise HTTPException(status_code=404, detail="证券不存在")
    return AlertSettingResponse(symbol=symbol, enabled=payload.enabled)
