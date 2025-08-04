from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
from security import get_current_user
from models.user import User as UserModel
from datetime import datetime, timedelta
from pydantic import BaseModel
from enum import Enum
import uuid

router = APIRouter()

# Notification Types
class NotificationType(str, Enum):
    TRADE_EXECUTED = "trade_executed"
    ORDER_PLACED = "order_placed"
    PRICE_ALERT = "price_alert"
    PORTFOLIO_UPDATE = "portfolio_update"
    SYSTEM_ALERT = "system_alert"
    SECURITY_ALERT = "security_alert"
    BROKERAGE_UPDATE = "brokerage_update"

# Notification Priority
class NotificationPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

# Pydantic Models
class NotificationBase(BaseModel):
    title: str
    message: str
    notification_type: NotificationType
    priority: NotificationPriority = NotificationPriority.MEDIUM
    data: Optional[dict] = None

class NotificationCreate(NotificationBase):
    user_id: Optional[int] = None  # If None, send to all users

class NotificationOut(NotificationBase):
    id: int
    user_id: int
    is_read: bool
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class NotificationUpdate(BaseModel):
    is_read: bool

class NotificationFilter(BaseModel):
    notification_type: Optional[NotificationType] = None
    priority: Optional[NotificationPriority] = None
    is_read: Optional[bool] = None
    limit: Optional[int] = 50
    offset: Optional[int] = 0

# Database Model (you'll need to create this)
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
from database import Base

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(String, nullable=False)
    priority = Column(String, default="medium")
    data = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime, nullable=True)

# Notification Service Functions
async def create_notification(
    db: Session, 
    user_id: int, 
    title: str, 
    message: str, 
    notification_type: NotificationType,
    priority: NotificationPriority = NotificationPriority.MEDIUM,
    data: Optional[dict] = None
):
    """Create a new notification"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type.value,
        priority=priority.value,
        data=data,
        is_read=False
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return notification

async def get_user_notifications(
    db: Session, 
    user_id: int, 
    notification_type: Optional[NotificationType] = None,
    priority: Optional[NotificationPriority] = None,
    is_read: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get notifications for a user with filters"""
    query = db.query(Notification).filter(Notification.user_id == user_id)
    
    if notification_type:
        query = query.filter(Notification.notification_type == notification_type.value)
    
    if priority:
        query = query.filter(Notification.priority == priority.value)
    
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)
    
    return query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()

async def mark_notification_read(db: Session, notification_id: int, user_id: int):
    """Mark a notification as read"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    notification.is_read = True
    notification.read_at = datetime.utcnow()
    db.commit()
    db.refresh(notification)
    return notification

async def mark_all_notifications_read(db: Session, user_id: int):
    """Mark all notifications as read for a user"""
    notifications = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).all()
    
    for notification in notifications:
        notification.is_read = True
        notification.read_at = datetime.utcnow()
    
    db.commit()
    return {"message": f"Marked {len(notifications)} notifications as read"}

async def delete_notification(db: Session, notification_id: int, user_id: int):
    """Delete a notification"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == user_id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notification)
    db.commit()
    return {"message": "Notification deleted successfully"}

async def get_notification_stats(db: Session, user_id: int):
    """Get notification statistics for a user"""
    from sqlalchemy import func
    
    total = db.query(Notification).filter(Notification.user_id == user_id).count()
    unread = db.query(Notification).filter(
        Notification.user_id == user_id,
        Notification.is_read == False
    ).count()
    
    # Count by type
    type_counts = db.query(Notification.notification_type, func.count(Notification.id)).filter(
        Notification.user_id == user_id
    ).group_by(Notification.notification_type).all()
    
    # Count by priority
    priority_counts = db.query(Notification.priority, func.count(Notification.id)).filter(
        Notification.user_id == user_id
    ).group_by(Notification.priority).all()
    
    return {
        "total": total,
        "unread": unread,
        "read": total - unread,
        "by_type": dict(type_counts),
        "by_priority": dict(priority_counts)
    }

# API Endpoints

@router.post("/notifications", response_model=NotificationOut)
async def create_user_notification(
    notification: NotificationCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new notification for the current user"""
    try:
        new_notification = await create_notification(
            db=db,
            user_id=current_user.id,
            title=notification.title,
            message=notification.message,
            notification_type=notification.notification_type,
            priority=notification.priority,
            data=notification.data
        )
        return new_notification
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create notification: {str(e)}")

@router.get("/notifications", response_model=List[NotificationOut])
async def get_notifications(
    notification_type: Optional[NotificationType] = None,
    priority: Optional[NotificationPriority] = None,
    is_read: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notifications for the current user with optional filters"""
    try:
        notifications = await get_user_notifications(
            db=db,
            user_id=current_user.id,
            notification_type=notification_type,
            priority=priority,
            is_read=is_read,
            limit=limit,
            offset=offset
        )
        return notifications
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch notifications: {str(e)}")

@router.get("/notifications/unread", response_model=List[NotificationOut])
async def get_unread_notifications(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get unread notifications for the current user"""
    try:
        notifications = await get_user_notifications(
            db=db,
            user_id=current_user.id,
            is_read=False
        )
        return notifications
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch unread notifications: {str(e)}")

@router.get("/notifications/stats")
async def get_notification_stats_endpoint(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get notification statistics for the current user"""
    try:
        stats = await get_notification_stats(db, current_user.id)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch notification stats: {str(e)}")

@router.get("/notifications/{notification_id}", response_model=NotificationOut)
async def get_notification(
    notification_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific notification by ID"""
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()
    
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    return notification

@router.put("/notifications/{notification_id}/read", response_model=NotificationOut)
async def mark_notification_as_read(
    notification_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark a notification as read"""
    try:
        notification = await mark_notification_read(db, notification_id, current_user.id)
        return notification
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark notification as read: {str(e)}")

@router.put("/notifications/read-all")
async def mark_all_notifications_as_read(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Mark all notifications as read for the current user"""
    try:
        result = await mark_all_notifications_read(db, current_user.id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark notifications as read: {str(e)}")

@router.delete("/notifications/{notification_id}")
async def delete_notification_endpoint(
    notification_id: int,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a notification"""
    try:
        result = await delete_notification(db, notification_id, current_user.id)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete notification: {str(e)}")

# Admin endpoints for sending notifications to all users
@router.post("/admin/notifications/broadcast")
async def broadcast_notification(
    notification: NotificationCreate,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Broadcast a notification to all users (admin only)"""
    # Check if user is admin (you can implement your own admin check)
    if not hasattr(current_user, 'is_admin') or not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        # Get all users
        users = db.query(UserModel).all()
        
        notifications_created = 0
        for user in users:
            await create_notification(
                db=db,
                user_id=user.id,
                title=notification.title,
                message=notification.message,
                notification_type=notification.notification_type,
                priority=notification.priority,
                data=notification.data
            )
            notifications_created += 1
        
        return {
            "message": f"Notification broadcasted to {notifications_created} users",
            "notifications_created": notifications_created
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to broadcast notification: {str(e)}")

# System notification endpoints for automated notifications
@router.post("/system/trade-executed")
async def create_trade_executed_notification(
    user_id: int,
    trade_data: dict,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a trade executed notification"""
    try:
        notification = await create_notification(
            db=db,
            user_id=user_id,
            title="Trade Executed",
            message=f"Your {trade_data.get('order_type', 'order')} order for {trade_data.get('stock_ticker', 'stock')} has been executed.",
            notification_type=NotificationType.TRADE_EXECUTED,
            priority=NotificationPriority.HIGH,
            data=trade_data
        )
        return notification
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create trade notification: {str(e)}")

@router.post("/system/price-alert")
async def create_price_alert_notification(
    user_id: int,
    alert_data: dict,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a price alert notification"""
    try:
        notification = await create_notification(
            db=db,
            user_id=user_id,
            title="Price Alert",
            message=f"{alert_data.get('stock_ticker', 'Stock')} has reached your target price of ₹{alert_data.get('target_price', '0')}",
            notification_type=NotificationType.PRICE_ALERT,
            priority=NotificationPriority.MEDIUM,
            data=alert_data
        )
        return notification
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create price alert: {str(e)}")

@router.post("/system/security-alert")
async def create_security_alert_notification(
    user_id: int,
    alert_data: dict,
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a security alert notification"""
    try:
        notification = await create_notification(
            db=db,
            user_id=user_id,
            title="Security Alert",
            message=alert_data.get('message', 'A security event has been detected on your account.'),
            notification_type=NotificationType.SECURITY_ALERT,
            priority=NotificationPriority.URGENT,
            data=alert_data
        )
        return notification
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create security alert: {str(e)}") 