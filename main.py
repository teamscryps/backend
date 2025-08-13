from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import api_router
from config import settings
from database import engine, Base
from models import User

app = FastAPI(title=settings.PROJECT_NAME)
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://localhost:5173", "https://localhost:5174"],  # Your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Create database tables
Base.metadata.create_all(bind=engine)

# Include API routers
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI Auth App!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 