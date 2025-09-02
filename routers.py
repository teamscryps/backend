from fastapi import APIRouter
from endpoints.auth import router as auth_router
from endpoints.dashboard import router as dashboard_router
from endpoints.trade import router as trade_router
from endpoints.notifications import router as notifications_router
from endpoints.accounts import router as accounts_router
from endpoints.trader import router as trader_router
from endpoints.audit import router as audit_router
from endpoints.broker_webhook import router as broker_webhook_router
from endpoints.client import router as client_router
from endpoints.realtime_ws import router as realtime_ws_router
from endpoints.snapshot import router as snapshot_router
from endpoints.stocks import router as stocks_router
from endpoints.watchlist import router as watchlist_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
# Optional heavy routers (celery / external services) disabled in TEST mode
import os
if not os.getenv("TEST_MODE"):
	from execution_engine.endpoint import router as execution_router  # type: ignore
	api_router.include_router(execution_router, prefix="/execution", tags=["execution"]) 
api_router.include_router(trade_router, prefix="/trade", tags=["trade"]) 
api_router.include_router(notifications_router, prefix="/notifications", tags=["notifications"])
api_router.include_router(accounts_router, prefix="/accounts", tags=["accounts"]) 
api_router.include_router(trader_router, prefix="/trader", tags=["trader"])
api_router.include_router(audit_router)
api_router.include_router(broker_webhook_router)
api_router.include_router(client_router)
api_router.include_router(realtime_ws_router, tags=["realtime"])
api_router.include_router(snapshot_router)
api_router.include_router(stocks_router, prefix="/trader", tags=["stocks"])
api_router.include_router(watchlist_router, tags=["watchlist"])
