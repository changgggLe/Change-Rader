from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Response, status

from app.models.api import WatchlistResponse
from app.repositories.mock_market import repository

router = APIRouter(prefix="/watchlist", tags=["自选"])
StockSymbol = Annotated[str, Path(description="六位股票代码", pattern=r"^\d{6}$", examples=["603018"])]


@router.get(
    "",
    response_model=WatchlistResponse,
    summary="查询我的自选股票",
    description="返回当前用户已经加入自选的股票。阶段 1 尚未登录，所有本地请求共享同一份内存数据。",
    response_description="自选股票列表",
)
def get_watchlist() -> WatchlistResponse:
    return repository.watchlist()


@router.post(
    "/{symbol}",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="加入自选股票",
    description="把指定六位股票代码加入当前用户自选，并返回更新后的完整自选列表。重复添加不会产生重复记录。",
    response_description="更新后的自选股票列表",
    responses={404: {"description": "股票代码不存在"}},
)
def add_to_watchlist(symbol: StockSymbol) -> WatchlistResponse:
    if not repository.set_watched(symbol, True):
        raise HTTPException(status_code=404, detail="证券不存在")
    return repository.watchlist()


@router.delete(
    "/{symbol}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="移除自选股票",
    description="从当前用户自选中移除指定股票。成功时返回 HTTP 204，不包含响应正文。",
    responses={404: {"description": "股票代码不存在"}},
)
def remove_from_watchlist(symbol: StockSymbol) -> Response:
    if not repository.set_watched(symbol, False):
        raise HTTPException(status_code=404, detail="证券不存在")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
