import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Allow tests to switch to an isolated SQLite database by setting TESTING=1
if os.environ.get("TESTING"):
    DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_db.sqlite")
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    )
else:
    DATABASE_URL = "postgresql://postgres:1234@localhost:5432/scryps_db"
    engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()