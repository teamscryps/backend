from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import api_router
from config import settings
from database import engine, Base
from models import User  # ensure model registration
import os
import logging
from sqlalchemy import inspect

app = FastAPI(title=settings.PROJECT_NAME)
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "https://localhost:5173", "https://localhost:5174", "http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:5173"],  # Your frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# IMPORTANT:
# Avoid calling create_all() unconditionally in production because it can cause
# schema drift when Alembic migrations add new columns (e.g. cash_available,
# cash_blocked). Rely on Alembic instead. We only auto-create in explicit test/dev
# scenarios (SQLite or env flag).
if os.environ.get("TESTING") or engine.url.get_backend_name() == "sqlite" or os.environ.get("DEV_AUTO_CREATE") == "1":
    Base.metadata.create_all(bind=engine)
else:
    # Lightweight runtime check: warn if critical new columns are missing so an admin
    # knows to run `alembic upgrade head`.
    try:
        insp = inspect(engine)
        if 'users' in insp.get_table_names():
            user_cols = {c['name'] for c in insp.get_columns('users')}
            missing = {c for c in ("cash_available", "cash_blocked") if c not in user_cols}
            if missing:
                logging.getLogger(__name__).warning(
                    "Database schema missing columns %s on users table. Run Alembic migrations: `alembic upgrade head`.",
                    ", ".join(sorted(missing))
                )
    except Exception as e:
        logging.getLogger(__name__).warning("Schema inspection failed: %s", e)

# Include API routers
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    return {"message": "Welcome to the FastAPI Auth App!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 