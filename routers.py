from fastapi import APIRouter
from endpoints.auth import router as auth_router
from endpoints.dashboard import router as dashboard_router
from execution_engine.endpoint import router as execution_router
from endpoints.trade import router as trade_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(execution_router, prefix="/execution", tags=["execution"]) 
api_router.include_router(trade_router, prefix="/trade", tags=["trade"]) 
