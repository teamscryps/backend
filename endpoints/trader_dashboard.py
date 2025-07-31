
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models.user import User
from models.trade import Trade
from models.order import Order
from datetime import datetime, timedelta
from fastapi.responses import JSONResponse

router = APIRouter()

@router.get("/dashboard", response_class=JSONResponse)
def get_trader_dashboard(db: Session = Depends(get_db)):
    # Total portfolio value (sum of all users' capital)
    total_portfolio = db.query(User).with_entities(User.capital).all()
    total_portfolio_value = sum([u.capital for u in total_portfolio])

    # Active trades (all users, status='open')
    active_trades = db.query(Trade).filter(Trade.status == 'open').all()
    active_trades_count = len(active_trades)

    # Active clients (users with at least one open trade)
    active_client_ids = set([t.user_id for t in active_trades])
    active_clients_count = len(active_client_ids)

    # Today's P&L (sum of all trades closed today)
    today = datetime.utcnow().date()
    todays_trades = db.query(Trade).filter(
        Trade.status == 'closed',
        Trade.order_executed_at >= datetime.combine(today, datetime.min.time()),
        Trade.order_executed_at <= datetime.combine(today, datetime.max.time()),
        Trade.sell_price.isnot(None)
    ).all()
    todays_pnl = sum(
        (t.sell_price * t.quantity - t.capital_used - (t.brokerage_charge or 0) - (t.mtf_charge or 0))
        for t in todays_trades
    )

    # Portfolio change % (last 7 days vs previous 7 days)
    week_ago = today - timedelta(days=7)
    prev_week_ago = today - timedelta(days=14)
    last_week_trades = db.query(Trade).filter(
        Trade.status == 'closed',
        Trade.order_executed_at >= week_ago,
        Trade.order_executed_at < today,
        Trade.sell_price.isnot(None)
    ).all()
    prev_week_trades = db.query(Trade).filter(
        Trade.status == 'closed',
        Trade.order_executed_at >= prev_week_ago,
        Trade.order_executed_at < week_ago,
        Trade.sell_price.isnot(None)
    ).all()
    last_week_pnl = sum((t.sell_price * t.quantity - t.capital_used - (t.brokerage_charge or 0) - (t.mtf_charge or 0)) for t in last_week_trades)
    prev_week_pnl = sum((t.sell_price * t.quantity - t.capital_used - (t.brokerage_charge or 0) - (t.mtf_charge or 0)) for t in prev_week_trades)
    portfolio_change_pct = ((last_week_pnl - prev_week_pnl) / prev_week_pnl * 100) if prev_week_pnl else 0

    # Active trades list (summary)
    active_trades_list = [
        {
            "stock": t.stock_ticker,
            "quantity": t.quantity,
            "buy_price": t.buy_price,
            "current_price": t.sell_price or t.buy_price,  # fallback if not sold
            "pnl": (t.sell_price * t.quantity - t.capital_used - (t.brokerage_charge or 0) - (t.mtf_charge or 0)) if t.sell_price else 0,
            "pnl_pct": ((t.sell_price - t.buy_price) / t.buy_price * 100) if t.sell_price else 0,
            "mtf": t.type.value if hasattr(t.type, 'value') else str(t.type)
        }
        for t in active_trades
    ]

    # Watchlist: Placeholder (implement if you have a model/table)
    watchlist = []

    dashboard_data = {
        "total_portfolio": total_portfolio_value,
        "portfolio_change_pct": round(portfolio_change_pct, 2),
        "active_trades": active_trades_count,
        "todays_pnl": round(todays_pnl, 2),
        "active_clients": active_clients_count,
        "active_trades_list": active_trades_list,
        "watchlist": watchlist
    }
    return dashboard_data
