from fastapi import APIRouter
from endpoints.auth import router as auth_router
from endpoints.dashboard import router as dashboard_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"]) 