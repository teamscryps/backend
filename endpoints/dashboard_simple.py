from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session, selectinload
from typing import List, Dict, Any
from database import get_db
from schemas.trades import TradeOut
from schemas.user import User
from schemas.order import OrderOut
from models.trade import Trade
from models.order import Order
from models.user import User as UserModel
from auth_service import get_user_by_email
from security import get_current_user
from datetime import datetime, timedelta

router = APIRouter()

# Dashboard Data Endpoint
@router.get(
    "/dashboard",
    response_model=dict
)
async def get_dashboard_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Fetch all data required for the dashboard, including trades, portfolio, and funds.
    """
    try:
        # Fetch user with eager loading
        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        unused_funds = 0  # Default to 0 instead of placeholder
        allocated_funds = 0
        holdings = []

        # Fetch ongoing trades
        ongoing_trades = db.query(Trade).options(
            selectinload(Trade.order)
        ).filter(
            Trade.status == 'open',
            Trade.order_executed_at >= datetime.utcnow() - timedelta(days=30)
        ).all()

        # Fetch recent trades
        recent_trades = db.query(Trade).options(
            selectinload(Trade.order)
        ).filter(
            Trade.order_executed_at >= datetime.utcnow() - timedelta(days=30)
        ).order_by(Trade.order_executed_at.desc()).limit(10).all()

        # Fetch upcoming trades
        upcoming_trades = db.query(Order).filter(
            Order.user_id == user.id,
            Order.order_type == "buy"
        ).all()

        # Calculate portfolio overview
        total_invested = sum(trade.capital_used for trade in ongoing_trades)
        total_profit = sum(
            (trade.sell_price * trade.quantity - trade.capital_used - (trade.brokerage_charge or 0) - (trade.mtf_charge or 0))
            for trade in recent_trades if trade.sell_price
        )
        portfolio_value = total_invested + total_profit
        portfolio_change = (total_profit / total_invested * 100) if total_invested > 0 else 0

        dashboard_data = {
            "activity_status": {
                "is_active": bool(user.session_id),
                "last_active": user.session_updated_at.strftime("%Y %H:%M:%S") if user.session_updated_at else None
            },
            "portfolio_overview": {
                "value": round(portfolio_value, 2),
                "change_percentage": round(portfolio_change, 2)
            },
            "ongoing_trades": [
                {
                    "stock": trade.stock_ticker,
                    "bought": trade.buy_price,
                    "quantity": trade.quantity,
                    "capital_used": trade.capital_used,
                    "profit": (trade.sell_price * trade.quantity - trade.capital_used - (trade.brokerage_charge or 0) - (trade.mtf_charge or 0))
                              if trade.sell_price else 0
                } for trade in ongoing_trades
            ],
            "recent_trades": [
                {
                    "date": trade.order_executed_at.strftime("%Y %H:%M:%S"),
                    "stock": trade.stock_ticker,
                    "bought": trade.buy_price,
                    "sold": trade.sell_price or 0,
                    "quantity": trade.quantity,
                    "capital_used": trade.capital_used,
                    "profit": (trade.sell_price * trade.quantity - trade.capital_used - (trade.brokerage_charge or 0) - (trade.mtf_charge or 0))
                              if trade.sell_price else 0
                } for trade in recent_trades
            ],
            "overall_profit": {
                "value": round(total_profit, 2),
                "percentage": round(portfolio_change, 2),
                "last_7_days": [
                    sum(
                        (trade.sell_price * trade.quantity - trade.capital_used - (trade.brokerage_charge or 0) - (trade.mtf_charge or 0))
                        for trade in db.query(Trade).filter(
                            Trade.order_executed_at >= datetime.utcnow() - timedelta(days=7-i),
                            Trade.order_executed_at < datetime.utcnow() - timedelta(days=6-i),
                            Trade.sell_price.isnot(None)
                        ).all()
                    )
                    for i in range(7)
                ]
            },
            "unused_funds": unused_funds,
            "allocated_funds": allocated_funds,
            "upcoming_trades": {
                "count": len(upcoming_trades),
                "holding_period": "N/A"  # No placeholder - calculate based on actual order data
            }
        }
        
        return dashboard_data
    except Exception as e:
        print(f"Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard data: {str(e)}") 