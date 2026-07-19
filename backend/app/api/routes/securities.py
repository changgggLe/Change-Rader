from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from app.models.api import SecurityDetailResponse
from app.repositories.mock_market import repository

router = APIRouter(prefix="/securities", tags=["证券"])


StockSymbol = Annotated[str, Path(description="六位股票代码", pattern=r"^\d{6}$", examples=["603018"])]


def load_security(symbol: str) -> SecurityDetailResponse:
    security = repository.security(symbol)
    if security is None:
        raise HTTPException(status_code=404, detail="证券不存在")
    return security


@router.get(
    "/{symbol}",
    response_model=SecurityDetailResponse,
    summary="查询单只股票详情",
    description="根据六位股票代码返回股票、所属板块、最新价格、对应基准指数和当前异动状态。",
    response_description="股票详情和异动状态",
    responses={404: {"description": "股票代码不存在"}},
)
def get_security(symbol: StockSymbol) -> SecurityDetailResponse:
    return load_security(symbol)


@router.get(
    "/{symbol}/deviation",
    response_model=SecurityDetailResponse,
    summary="查询偏离值计算明细",
    description=(
        "返回该股票 3 日、10 日、30 日规则进度，以及股票累计涨幅、对应指数累计涨幅和偏离值。"
        "页面可用这些字段解释系统为何触发或接近阈值。"
    ),
    response_description="偏离值计算过程与规则进度",
    responses={404: {"description": "股票代码不存在"}},
)
def get_security_deviation(symbol: StockSymbol) -> SecurityDetailResponse:
    return load_security(symbol)
