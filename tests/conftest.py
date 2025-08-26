"""Test configuration and fixtures.

Provides an isolated in‑memory SQLite database so tests don't depend on the
developer's local Postgres (which may have an out-of-date schema). This ensures
new columns (e.g. cash_available, cash_blocked) exist for every test run.
"""

import os
from typing import Generator

# Set env flags BEFORE importing application modules
os.environ.setdefault("DEBUG", "1")
os.environ.setdefault("TESTING", "1")
os.environ.setdefault("TEST_DATABASE_URL", "sqlite:///./test_db.sqlite")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database  # original module with Base & SessionLocal placeholder
from database import Base, get_db
from main import app  # imports routers & models

# Use file-based SQLite to persist across multiple connections (in-memory would be per-connection)
TEST_DATABASE_URL = os.environ["TEST_DATABASE_URL"]

engine = create_engine(
    TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session", autouse=True)
def create_test_db() -> Generator[None, None, None]:
    """Create all tables once for the in-memory DB (persists per connection)."""
    Base.metadata.create_all(bind=engine)
    yield
    # (No drop_all for in-memory; database disappears after process ends)


@pytest.fixture()
def db_session() -> Generator:  # type: ignore
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def override_db_dependency(db_session):  # type: ignore
    """Override FastAPI dependency to use the SQLite session."""
    def _get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = _get_db

    # Also redirect direct imports of SessionLocal within tests/modules
    database.SessionLocal = TestingSessionLocal  # type: ignore
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture(scope="session")
def client() -> TestClient:  # type: ignore
    return TestClient(app)
