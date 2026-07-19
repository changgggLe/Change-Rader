from fastapi import Request

from app.cache.service import CacheService
from app.settings.config import Settings


def get_cache(request: Request) -> CacheService:
    return request.app.state.cache


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings
