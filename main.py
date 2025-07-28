from fastapi import FastAPI
from routers import api_router
from config import settings
from database import engine, Base
from models import User

app = FastAPI(title=settings.PROJECT_NAME)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include API routers
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI Auth App!"} 