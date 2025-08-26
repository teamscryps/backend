from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from services.fills import apply_fill, apply_cancel, FillAlreadyApplied
from webhook_security import verify_signature
from models.order import Order as OrderModel
from models.user import User as UserModel
from security import get_current_user

router = APIRouter(prefix="/broker", tags=["broker"])

class FillEvent(BaseModel):
    order_id: int
    quantity: int
    price: float
    broker_fill_id: str | None = None

class CancelEvent(BaseModel):
    order_id: int
    status: str  # CANCELLED or REJECTED

@router.post("/fill")
async def broker_fill(request: Request, event: FillEvent, db: Session = Depends(get_db)):
    # Verify HMAC signature using raw body
    raw_body = await request.body()
    verify_signature(raw_body, request.headers)
    try:
        order = apply_fill(db, event.order_id, event.quantity, event.price, event.broker_fill_id)
        db.commit()
        return {"status": order.status, "filled_qty": order.filled_qty, "avg_fill_price": float(order.avg_fill_price or 0)}
    except FillAlreadyApplied:
        return {"status": "IGNORED", "reason": "duplicate"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/cancel")
async def broker_cancel(request: Request, event: CancelEvent, db: Session = Depends(get_db)):
    raw_body = await request.body()
    verify_signature(raw_body, request.headers)
    try:
        # Idempotent handling: if already in a terminal state return stable response
        order = db.query(OrderModel).get(event.order_id)
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order.status in ("CANCELLED", "REJECTED", "FILLED"):
            return {"status": order.status, "idempotent": True}
        order = apply_cancel(db, event.order_id, event.status)
        db.commit()
        return {"status": order.status, "idempotent": False}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
