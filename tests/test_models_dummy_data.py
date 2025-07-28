from database import SessionLocal, Base, engine
from models.user import User
from models.order import Order
from models.trade import Trade, TradeType
from sqlalchemy.exc import IntegrityError



# Create tables if they don't exist
Base.metadata.create_all(bind=engine)

def add_dummy_data():
    session = SessionLocal()
    try:
        # Add a dummy user
        user = User(
            email="dummy@example.com",
            password="password123",
            mobile="1234567890",
            api_key="apikey123",
            api_secret="apisecret123",
            broker="zerodha",
            session_id="sess_001"
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        # Add a dummy order
        order = Order(
            user_id=user.id,
            stock_symbol="TCS",
            quantity=10,
            price=3500.0,
            order_type="buy",
            mtf_enabled=True
        )
        session.add(order)
        session.commit()
        session.refresh(order)

        # Add a dummy trade
        trade = Trade(
            stock_ticker="TCS",
            buy_price=3500.0,
            quantity=10,
            capital_used=35000.0,
            order_executed_at=None,
            status="open",
            sell_price=None,
            brokerage_charge=50.0,
            mtf_charge=10.0,
            type=TradeType.EQ
        )
        session.add(trade)
        session.commit()
        print("Dummy data inserted successfully.")
    except IntegrityError as e:
        session.rollback()
        print(f"Integrity error: {e}")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    add_dummy_data() 