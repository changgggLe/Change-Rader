from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_app_settings, get_cache
from app.cache.service import CacheService
from app.db.session import get_db
from app.repositories.database_market import DatabaseMarketRepository
from app.settings.config import Settings


def get_market_repository(
    session: Session = Depends(get_db),
    cache: CacheService = Depends(get_cache),
    settings: Settings = Depends(get_app_settings),
    user_key: Annotated[
        str | None,
        Header(alias="X-User-Key", min_length=8, max_length=64, pattern=r"^[A-Za-z0-9_-]+$"),
    ] = None,
    wechat_openid: Annotated[
        str | None,
        Header(alias="X-WX-OPENID", min_length=8, max_length=64),
    ] = None,
    wechat_appid: Annotated[
        str | None,
        Header(alias="X-WX-APPID", min_length=8, max_length=64),
    ] = None,
) -> DatabaseMarketRepository:
    if wechat_openid:
        if settings.wechat_appid and wechat_appid != settings.wechat_appid:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="微信小程序身份不匹配")
        resolved_user_key = wechat_openid
    elif settings.require_wechat_identity:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少微信用户身份")
    else:
        resolved_user_key = user_key or settings.internal_user_key
    return DatabaseMarketRepository(session, cache, settings, resolved_user_key)
