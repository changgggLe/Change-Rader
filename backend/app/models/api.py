from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MarketStatusResponse(ApiModel):
    market_status: Literal["TRADING", "CLOSED"] = Field(description="市场状态：TRADING 盘中，CLOSED 休市或盘后")
    quote_time: datetime = Field(description="最近一批行情的北京时间")
    data_health: Literal["HEALTHY", "DEGRADED"] = Field(description="数据健康状态：HEALTHY 正常，DEGRADED 降级")
    refresh_interval_seconds: int = Field(default=15, description="建议小程序轮询间隔，单位为秒")
    source: str = Field(default="MOCK", description="当前行情数据源标识；MOCK 表示阶段 1 模拟数据")


class RuleMetric(ApiModel):
    key: Literal["THREE_DAY", "TEN_DAY", "THIRTY_DAY"] = Field(description="规则窗口类型")
    label: str = Field(description="页面展示的规则名称")
    current: str = Field(description="当前偏离值或同向异动次数")
    threshold: str = Field(description="该规则的触发阈值")
    progress: int = Field(ge=0, le=100)
    triggered: bool = Field(description="该条规则当前是否已经触发")


class AnomalyItem(ApiModel):
    symbol: str = Field(description="六位股票代码")
    name: str = Field(description="股票简称")
    exchange: Literal["SSE", "SZSE"] = Field(description="交易所：SSE 上交所，SZSE 深交所")
    board: Literal["MAIN", "CHINEXT", "STAR"] = Field(description="板块：主板、创业板或科创板")
    board_label: str = Field(description="板块中文名称")
    last_price: str = Field(description="最新价；使用字符串避免金融数值精度损失")
    day_change: str = Field(description="当日涨跌幅")
    display_change: str = Field(description="榜单主区域优先展示的涨幅或偏离值")
    benchmark_code: str = Field(description="计算偏离值使用的基准指数代码")
    benchmark_name: str = Field(description="基准指数中文名称")
    window_start: date = Field(description="本次计算窗口起始交易日")
    window_end: date = Field(description="本次计算窗口结束交易日")
    stock_return: str = Field(description="窗口内股票累计涨幅")
    benchmark_return: str = Field(description="窗口内基准指数累计涨幅")
    deviation: str = Field(description="累计偏离值：股票累计涨幅减去指数累计涨幅")
    threshold: str = Field(description="当前命中或接近规则的阈值")
    status: Literal["SYSTEM_TRIGGERED", "SEVERE", "NEAR"] = Field(description="机器可读的系统计算状态")
    status_label: str = Field(description="页面展示的中文状态")
    status_type: Literal["triggered", "severe", "near"] = Field(description="前端样式类型")
    rule_note: str = Field(description="本次状态对应的规则摘要")
    metrics: list[RuleMetric] = Field(description="3 日、10 日和 30 日规则的详细进度")
    watched: bool = Field(default=False, description="当前用户是否已加入自选")
    alerted: bool = Field(default=False, description="当前用户是否开启提醒")


class AnomalyListResponse(ApiModel):
    market_status: Literal["TRADING", "CLOSED"] = Field(description="返回榜单时的市场状态")
    quote_time: datetime = Field(description="榜单所使用行情的北京时间")
    data_health: Literal["HEALTHY", "DEGRADED"] = Field(description="本次榜单的数据健康状态")
    mode: Literal["INTRADAY", "AFTER_HOURS", "HISTORY"] = Field(description="榜单类型：盘中、盘后或历史")
    items: list[AnomalyItem] = Field(description="按业务优先级排序的异动股票")


class SecurityDetailResponse(AnomalyItem):
    disclaimer: str = Field(default="系统按公开规则计算，不代表交易所最终认定，也不构成投资建议。", description="页面必须展示的风险提示")


class WatchlistResponse(ApiModel):
    items: list[AnomalyItem] = Field(description="当前用户的自选股票")


class AlertSettingRequest(ApiModel):
    enabled: bool = Field(description="true 开启提醒，false 关闭提醒")


class AlertSettingResponse(ApiModel):
    symbol: str = Field(description="六位股票代码")
    enabled: bool = Field(description="保存后的提醒开关状态")
