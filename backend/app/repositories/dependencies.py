from typing import Annotated

from fastapi import Depends, Header
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
) -> DatabaseMarketRepository:
    return DatabaseMarketRepository(session, cache, settings, user_key or settings.internal_user_key)
