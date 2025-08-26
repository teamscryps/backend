from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from database import Base
from models.user import User
from models.holding import Holding
from services.snapshot import run_daily_snapshots
from models.portfolio_snapshot import PortfolioSnapshot
from datetime import date

def setup_db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False})
    Base.metadata.create_all(bind=engine)
    return engine

def test_snapshot_generation():
    engine = setup_db()
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = SessionLocal()
    # Create clients with holdings
    u1 = User(name='Alice', email='alice@example.com', password='x', mobile='1', api_key='k', api_secret='s', broker='zerodha', role='client', cash_available=Decimal('500000'), cash_blocked=Decimal('8000'))
    u2 = User(name='Bob', email='bob@example.com', password='x', mobile='2', api_key='k', api_secret='s', broker='zerodha', role='client', cash_available=Decimal('200000'), cash_blocked=0)
    db.add_all([u1,u2]); db.commit(); db.refresh(u1); db.refresh(u2)
    db.add(Holding(user_id=u1.id, symbol='AAPL', quantity=100, avg_price=150))
    db.add(Holding(user_id=u1.id, symbol='TSLA', quantity=50, avg_price=700))
    db.add(Holding(user_id=u2.id, symbol='MSFT', quantity=20, avg_price=300))
    db.add(Holding(user_id=u2.id, symbol='GOOG', quantity=30, avg_price=2700))
    db.commit()
    count = run_daily_snapshots(db, date.today())
    assert count == 2
    snaps = db.query(PortfolioSnapshot).all()
    assert len(snaps) == 2
    for s in snaps:
        assert s.holdings and isinstance(s.holdings, list)
        # Unrealized PnL possibly positive or negative; ensure field exists
        assert s.unrealized_pnl is not None
