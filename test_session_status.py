#!/usr/bin/env python3
"""
Test script to verify client session status functionality
"""
import sys
import os
sys.path.append('/Users/apple/Desktop/backend')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.user import User
from endpoints.trader import check_client_session_active

def test_session_status():
    """Test the session status check function"""

    # Database connection
    DATABASE_URL = "postgresql://postgres:1234@localhost:5432/scryps_db"
    engine = create_engine(DATABASE_URL, echo=False)

    # Create session
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        print("🔍 Testing client session status functionality...")
        print("=" * 60)

        # Get all clients
        clients = db.query(User).filter(User.role == "client").all()

        print(f"Found {len(clients)} clients:")
        print()

        for client in clients:
            session_active = check_client_session_active(client)
            status_icon = "✅" if session_active else "❌"

            print(f"{status_icon} Client: {client.name} ({client.email})")
            print(f"   Broker: {client.broker or 'Not Set'}")
            print(f"   API Key: {'Set' if client.api_key else 'Not Set'}")
            print(f"   Session ID: {'Set' if client.session_id else 'Not Set'}")

            if client.session_updated_at:
                from datetime import datetime, timedelta
                session_age = datetime.utcnow() - client.session_updated_at
                days_old = session_age.days
                print(f"   Session Age: {days_old} days old")
                if days_old > 7:
                    print(f"   Status: Session expired (older than 7 days)")
                else:
                    print(f"   Status: Session valid")
            else:
                print(f"   Session Age: Never updated")

            print(f"   Session Active: {session_active}")
            print()

        # Test the trader as well
        trader = db.query(User).filter(User.role == "trader").first()
        if trader:
            trader_session_active = check_client_session_active(trader)
            print(f"👤 Trader: {trader.name} ({trader.email})")
            print(f"   Session Active: {trader_session_active}")
            print()

    except Exception as e:
        print(f"❌ Error: {str(e)}")

    finally:
        db.close()

if __name__ == "__main__":
    test_session_status()
