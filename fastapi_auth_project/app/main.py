from fastapi import FastAPI
from app.api.v1.routers import api_router
from app.core.config import settings
from app.core.database import engine
from app.core import models

app = FastAPI(title=settings.PROJECT_NAME)

# Create database tables
models.Base.metadata.create_all(bind=engine)

# Include API routers
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI Auth App!"}
