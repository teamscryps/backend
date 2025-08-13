from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from database import get_db
from schemas.user import User
from models.user import User as UserModel
from security import get_current_user
from datetime import datetime

router = APIRouter()

@router.get(
    "/accounts",
    response_model=List[Dict[str, Any]]
)
async def get_user_accounts(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Fetch brokerage connection information for the current user.
    Returns a list of connected brokerage accounts with connection details.
    """
    try:
        # Debug: Print current user info
        print(f"Current user email: {current_user.email}")
        print(f"Current user type: {type(current_user)}")
        
        # Fetch user with brokerage information
        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Debug: Print user info from database
        print(f"Database user broker: {user.broker}")
        print(f"Database user api_credentials_set: {user.api_credentials_set}")
        print(f"Database user session_id: {user.session_id}")
        print(f"Database user session_updated_at: {user.session_updated_at}")

        accounts = []
        
        # Check if user has API credentials set and broker information
        if user.api_credentials_set and user.broker:
            # Determine connection status based on session_id and session_updated_at
            is_connected = bool(user.session_id and user.session_updated_at)
            
            # Calculate connection date (use session_updated_at if available, otherwise created_at)
            connected_date = user.session_updated_at if user.session_updated_at else user.created_at
            
            account_info = {
                "id": user.id,
                "brokerage": user.broker.title(),  # Capitalize first letter
                "broker_code": user.broker.lower(),
                "connected_date": connected_date.strftime("%Y-%m-%d %H:%M:%S") if connected_date else None,
                "connection_status": "Connected" if is_connected else "Disconnected",
                "last_active": user.session_updated_at.strftime("%Y-%m-%d %H:%M:%S") if user.session_updated_at else None,
                "api_credentials_set": user.api_credentials_set,
                "has_refresh_token": bool(user.broker_refresh_token),
                "capital": user.capital
            }
            
            print(f"Adding account info: {account_info}")
            accounts.append(account_info)
        else:
            print(f"User does not meet criteria: api_credentials_set={user.api_credentials_set}, broker={user.broker}")
        
        # If no brokerage accounts are connected, return empty list
        # This will show the "No connected brokerage accounts" message in the frontend
        print(f"Returning {len(accounts)} accounts")
        
        return accounts
        
    except Exception as e:
        print(f"Accounts endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching accounts: {str(e)}")

@router.get(
    "/accounts/{brokerage_name}",
    response_model=Dict[str, Any]
)
async def get_specific_brokerage_account(
    brokerage_name: str,
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Fetch specific brokerage account details for the current user.
    """
    try:
        # Fetch user with brokerage information
        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if the requested brokerage matches user's broker
        if not user.broker or user.broker.lower() != brokerage_name.lower():
            raise HTTPException(status_code=404, detail=f"Brokerage '{brokerage_name}' not found for this user")
        
        if not user.api_credentials_set:
            raise HTTPException(status_code=400, detail="API credentials not set for this brokerage")
        
        # Determine connection status
        is_connected = bool(user.session_id and user.session_updated_at)
        connected_date = user.session_updated_at if user.session_updated_at else user.created_at
        
        account_details = {
            "id": user.id,
            "brokerage": user.broker.title(),
            "broker_code": user.broker.lower(),
            "connected_date": connected_date.strftime("%Y-%m-%d %H:%M:%S") if connected_date else None,
            "connection_status": "Connected" if is_connected else "Disconnected",
            "last_active": user.session_updated_at.strftime("%Y-%m-%d %H:%M:%S") if user.session_updated_at else None,
            "api_credentials_set": user.api_credentials_set,
            "has_refresh_token": bool(user.broker_refresh_token),
            "capital": user.capital,
            "session_id": user.session_id if is_connected else None,
            "created_at": user.created_at.strftime("%Y-%m-%d %H:%M:%S") if user.created_at else None
        }
        
        return account_details
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Specific account endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching account details: {str(e)}")

@router.delete(
    "/accounts/{brokerage_name}",
    response_model=Dict[str, str]
)
async def disconnect_brokerage_account(
    brokerage_name: str,
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Disconnect a brokerage account by clearing session and refresh tokens.
    """
    try:
        # Fetch user with brokerage information
        user = db.query(UserModel).filter(UserModel.email == current_user.email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if the requested brokerage matches user's broker
        if not user.broker or user.broker.lower() != brokerage_name.lower():
            raise HTTPException(status_code=404, detail=f"Brokerage '{brokerage_name}' not found for this user")
        
        # Clear session and refresh tokens
        user.session_id = None
        user.session_updated_at = None
        user.broker_refresh_token = None
        
        # Commit changes
        db.commit()
        
        return {
            "message": f"Successfully disconnected from {user.broker.title()}",
            "brokerage": user.broker.title()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Disconnect account error: {e}")
        raise HTTPException(status_code=500, detail=f"Error disconnecting account: {str(e)}")
