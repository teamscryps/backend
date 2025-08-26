from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import date
from database import get_db
from security import get_current_user
from models.user import User as UserModel
from models.portfolio_snapshot import PortfolioSnapshot
from services.snapshot import run_daily_snapshots

router = APIRouter(prefix="/snapshot", tags=["snapshot"])

@router.post("/run")
def run_snapshot(snap_date: str | None = None, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != 'trader':
        raise HTTPException(status_code=403, detail="Only traders can trigger snapshots")
    d = date.fromisoformat(snap_date) if snap_date else date.today()
    count = run_daily_snapshots(db, d)
    return {"snapshots_created": count, "date": d.isoformat()}

@router.get("/latest/{user_id}")
def latest_snapshot(user_id: int, current_user: UserModel = Depends(get_current_user), db: Session = Depends(get_db)):
    # Authorization: trader can view; client can view own
    if current_user.role != 'trader' and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Not allowed")
    snap = db.query(PortfolioSnapshot).filter(PortfolioSnapshot.user_id==user_id).order_by(PortfolioSnapshot.snapshot_date.desc(), PortfolioSnapshot.id.desc()).first()
    if not snap:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return {
        'user_id': snap.user_id,
        'date': snap.snapshot_date.isoformat(),
        'cash_available': float(snap.cash_available or 0),
        'cash_blocked': float(snap.cash_blocked or 0),
        'realized_pnl': float(snap.realized_pnl or 0),
        'unrealized_pnl': float(snap.unrealized_pnl or 0),
        'holdings': snap.holdings,
        'created_at': snap.created_at.isoformat() if snap.created_at else None
    }
