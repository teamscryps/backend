# 🔔 Notification System Documentation

## Overview
A comprehensive notification system for the trading backend that supports multiple notification types, priorities, and management features.

## 🏗️ Architecture

### Database Schema
```sql
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR NOT NULL,
    message TEXT NOT NULL,
    notification_type VARCHAR NOT NULL,
    priority VARCHAR DEFAULT 'medium',
    data JSONB,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    read_at TIMESTAMP
);
```

### Notification Types
- **TRADE_EXECUTED**: Trade execution notifications
- **ORDER_PLACED**: Order placement confirmations
- **PRICE_ALERT**: Price target alerts
- **PORTFOLIO_UPDATE**: Portfolio change notifications
- **SYSTEM_ALERT**: System maintenance alerts
- **SECURITY_ALERT**: Security event notifications
- **BROKERAGE_UPDATE**: Brokerage status updates

### Priority Levels
- **LOW**: Informational notifications
- **MEDIUM**: Standard notifications
- **HIGH**: Important notifications
- **URGENT**: Critical notifications

## 📡 API Endpoints

### 🔐 Authentication Required
All notification endpoints require Bearer token authentication.

### 📝 Basic Operations

#### Create Notification
```http
POST /api/v1/notifications/notifications
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Trade Executed",
  "message": "Your buy order for RELIANCE has been executed",
  "notification_type": "trade_executed",
  "priority": "high",
  "data": {
    "order_type": "buy",
    "stock_ticker": "RELIANCE",
    "quantity": 10,
    "price": 2500.0
  }
}
```

#### Get Notifications
```http
GET /api/v1/notifications/notifications
Authorization: Bearer <token>

# Optional Query Parameters:
# notification_type: Filter by notification type
# priority: Filter by priority level
# is_read: Filter by read status (true/false)
# limit: Number of notifications to return (default: 50)
# offset: Number of notifications to skip (default: 0)
```

#### Get Unread Notifications
```http
GET /api/v1/notifications/notifications/unread
Authorization: Bearer <token>
```

#### Get Notification by ID
```http
GET /api/v1/notifications/notifications/{notification_id}
Authorization: Bearer <token>
```

### ⚙️ Management Operations

#### Mark Notification as Read
```http
PUT /api/v1/notifications/notifications/{notification_id}/read
Authorization: Bearer <token>
```

#### Mark All Notifications as Read
```http
PUT /api/v1/notifications/notifications/read-all
Authorization: Bearer <token>
```

#### Delete Notification
```http
DELETE /api/v1/notifications/notifications/{notification_id}
Authorization: Bearer <token>
```

#### Get Notification Statistics
```http
GET /api/v1/notifications/notifications/stats
Authorization: Bearer <token>

# Response:
{
  "total": 15,
  "unread": 3,
  "read": 12,
  "by_type": {
    "trade_executed": 8,
    "price_alert": 4,
    "system_alert": 3
  },
  "by_priority": {
    "high": 5,
    "medium": 8,
    "low": 2
  }
}
```

### 🤖 System Notifications

#### Trade Executed Notification
```http
POST /api/v1/notifications/system/trade-executed?user_id={user_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "trade_data": {
    "order_type": "buy",
    "stock_ticker": "RELIANCE",
    "quantity": 10,
    "price": 2500.0
  }
}
```

#### Price Alert Notification
```http
POST /api/v1/notifications/system/price-alert?user_id={user_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "alert_data": {
    "stock_ticker": "TCS",
    "target_price": 3500.0,
    "current_price": 3500.0
  }
}
```

#### Security Alert Notification
```http
POST /api/v1/notifications/system/security-alert?user_id={user_id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "alert_data": {
    "message": "Unusual login activity detected",
    "ip_address": "192.168.1.100",
    "location": "Mumbai, India"
  }
}
```

### 👑 Admin Operations

#### Broadcast Notification to All Users
```http
POST /api/v1/notifications/admin/notifications/broadcast
Authorization: Bearer <admin_token>
Content-Type: application/json

{
  "title": "System Maintenance",
  "message": "Scheduled maintenance on Sunday 2-4 AM",
  "notification_type": "system_alert",
  "priority": "medium"
}
```

## 🔧 Integration Examples

### Frontend Integration

#### React Hook Example
```javascript
import { useState, useEffect } from 'react';

const useNotifications = (token) => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const fetchNotifications = async () => {
    try {
      const response = await fetch('/api/v1/notifications/notifications', {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      const data = await response.json();
      setNotifications(data);
    } catch (error) {
      console.error('Failed to fetch notifications:', error);
    }
  };

  const markAsRead = async (notificationId) => {
    try {
      await fetch(`/api/v1/notifications/notifications/${notificationId}/read`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`
        }
      });
      fetchNotifications(); // Refresh list
    } catch (error) {
      console.error('Failed to mark notification as read:', error);
    }
  };

  useEffect(() => {
    fetchNotifications();
    // Poll for new notifications every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, [token]);

  return { notifications, unreadCount, markAsRead };
};
```

#### Real-time Updates with WebSocket
```javascript
const useNotificationWebSocket = (token) => {
  const [notifications, setNotifications] = useState([]);
  
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/notifications?token=${token}`);
    
    ws.onmessage = (event) => {
      const notification = JSON.parse(event.data);
      setNotifications(prev => [notification, ...prev]);
    };
    
    return () => ws.close();
  }, [token]);
  
  return notifications;
};
```

### Backend Integration

#### Trade Execution Hook
```python
from endpoints.notifications import create_notification, NotificationType, NotificationPriority

async def on_trade_executed(user_id: int, trade_data: dict, db: Session):
    """Create notification when trade is executed"""
    await create_notification(
        db=db,
        user_id=user_id,
        title="Trade Executed",
        message=f"Your {trade_data['order_type']} order for {trade_data['stock_ticker']} has been executed.",
        notification_type=NotificationType.TRADE_EXECUTED,
        priority=NotificationPriority.HIGH,
        data=trade_data
    )
```

#### Price Alert System
```python
async def check_price_alerts(db: Session):
    """Check for price alerts and create notifications"""
    alerts = db.query(PriceAlert).filter(PriceAlert.is_active == True).all()
    
    for alert in alerts:
        current_price = get_current_price(alert.stock_ticker)
        
        if current_price >= alert.target_price:
            await create_notification(
                db=db,
                user_id=alert.user_id,
                title="Price Alert",
                message=f"{alert.stock_ticker} has reached your target price of ₹{alert.target_price}",
                notification_type=NotificationType.PRICE_ALERT,
                priority=NotificationPriority.MEDIUM,
                data={
                    "stock_ticker": alert.stock_ticker,
                    "target_price": alert.target_price,
                    "current_price": current_price
                }
            )
```

## 🧪 Testing

### Manual Testing
```bash
# Test notification creation
curl -X POST "http://localhost:8000/api/v1/notifications/notifications" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Test Notification",
    "message": "This is a test notification",
    "notification_type": "system_alert",
    "priority": "medium"
  }'

# Test getting notifications
curl -X GET "http://localhost:8000/api/v1/notifications/notifications" \
  -H "Authorization: Bearer <token>"

# Test notification stats
curl -X GET "http://localhost:8000/api/v1/notifications/notifications/stats" \
  -H "Authorization: Bearer <token>"
```

### Automated Testing
```bash
# Run the comprehensive test suite
python3 test_notifications.py
```

## 📊 Performance Considerations

### Database Indexing
```sql
-- Recommended indexes for optimal performance
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_created_at ON notifications(created_at DESC);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_type ON notifications(notification_type);
CREATE INDEX idx_notifications_priority ON notifications(priority);
```

### Caching Strategy
```python
# Redis caching for frequently accessed data
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

async def get_cached_notifications(user_id: int):
    cache_key = f"notifications:{user_id}"
    cached = redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    # Fetch from database and cache
    notifications = await get_user_notifications(user_id)
    redis_client.setex(cache_key, 300, json.dumps(notifications))  # 5 min cache
    return notifications
```

## 🔒 Security Features

### Data Validation
- All input data is validated using Pydantic models
- SQL injection protection through SQLAlchemy ORM
- XSS protection through proper content encoding

### Access Control
- User can only access their own notifications
- Admin endpoints require admin privileges
- Token-based authentication for all endpoints

### Audit Logging
```python
# Log all notification operations
import logging

logger = logging.getLogger(__name__)

async def create_notification_with_logging(user_id: int, **kwargs):
    notification = await create_notification(user_id, **kwargs)
    logger.info(f"Notification created: {notification.id} for user {user_id}")
    return notification
```

## 🚀 Future Enhancements

### Planned Features
1. **Push Notifications**: Mobile push notification support
2. **Email Notifications**: Email integration for critical alerts
3. **SMS Notifications**: SMS alerts for urgent notifications
4. **Notification Templates**: Reusable notification templates
5. **Bulk Operations**: Bulk mark as read/delete operations
6. **Notification Preferences**: User-configurable notification settings
7. **Real-time Updates**: WebSocket support for live notifications
8. **Notification Analytics**: Advanced analytics and reporting

### Scalability Considerations
- Horizontal scaling with load balancers
- Database sharding for large user bases
- Message queues for high-volume notifications
- CDN integration for global delivery

## 📝 Changelog

### v1.0.0 (Current)
- ✅ Basic notification CRUD operations
- ✅ Multiple notification types and priorities
- ✅ System notification endpoints
- ✅ Notification statistics and analytics
- ✅ Comprehensive error handling
- ✅ Full test coverage
- ✅ Database migration support

---

**Last Updated**: August 4, 2025  
**Version**: 1.0.0  
**Status**: ✅ Production Ready 