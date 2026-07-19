from fastapi import APIRouter

from app.api.routes import alerts, anomalies, market, securities, watchlist

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(market.router)
api_router.include_router(anomalies.router)
api_router.include_router(securities.router)
api_router.include_router(watchlist.router)
api_router.include_router(alerts.router)
