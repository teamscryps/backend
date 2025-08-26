from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
from database import get_db
from security import get_current_user
from models.audit_log import AuditLog
from models.user import User as UserModel

router = APIRouter(prefix="/audit", tags=["audit"])

@router.get("/logs")
def list_audit_logs(
    actor_user_id: Optional[int] = Query(None),
    target_user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    since: Optional[str] = Query(None, description="ISO8601 start time inclusive"),
    until: Optional[str] = Query(None, description="ISO8601 end time inclusive"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Query audit logs with optional filters.

    Requires authentication; traders can see their own and their clients' logs (simplified rule).
    Clients can only see their own logs.
    """
    q = db.query(AuditLog)
    # Basic authorization: clients restricted to own actor or target.
    if current_user.role != "trader":
        q = q.filter((AuditLog.actor_user_id == current_user.id) | (AuditLog.target_user_id == current_user.id))
    if actor_user_id is not None:
        q = q.filter(AuditLog.actor_user_id == actor_user_id)
    if target_user_id is not None:
        q = q.filter(AuditLog.target_user_id == target_user_id)
    if action is not None:
        q = q.filter(AuditLog.action == action)
    def parse_ts(val: Optional[str]):
        if not val:
            return None
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid datetime format: {val}")
    since_dt = parse_ts(since)
    until_dt = parse_ts(until)
    if since_dt:
        q = q.filter(AuditLog.created_at >= since_dt)
    if until_dt:
        q = q.filter(AuditLog.created_at <= until_dt)
    q = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    rows = q.all()
    return [
        {
            "id": r.id,
            "actor_user_id": r.actor_user_id,
            "target_user_id": r.target_user_id,
            "action": r.action,
            "description": r.description,
            "details": r.details,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
