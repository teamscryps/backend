from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from execution_engine.tasks import bulk_trade_execution

router = APIRouter()

class BulkTradeRequest(BaseModel):
    broker_type: str
    stock_symbol: str
    percent_quantity: float
    user_ids: list[int]

@router.post('/bulk-execute')
def bulk_execute_trades(request: BulkTradeRequest):
    task = bulk_trade_execution.delay(
        request.broker_type,
        request.stock_symbol,
        request.percent_quantity,
        request.user_ids
    )
    return {"task_id": task.id, "status": "started"} 