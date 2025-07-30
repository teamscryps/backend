from sqlalchemy.orm import Session
from models.audit import Audit
from database import get_db
from datetime import datetime
from typing import Optional, Dict, Any
import json
import traceback


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def log_action(
        self,
        action: str,
        level: str = "INFO",
        user_id: str = "anonymous",
        user_email: str = "anonymous",
        correlation_id: str = "",
        context: Optional[Dict[str, Any]] = None,
        method: Optional[str] = None,
        url: Optional[str] = None,
        client_ip: Optional[str] = None,
        error_message: Optional[str] = None,
        stack_trace: Optional[str] = None,
        request_data: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
        status_code: Optional[int] = None
    ):
        """
        Store audit log in PostgreSQL database
        """
        audit_entry = Audit(
            timestamp=datetime.utcnow(),
            level=level,
            action=action,
            user_id=str(user_id),
            user_email=user_email,
            correlation_id=correlation_id,
            context=context or {},
            method=method,
            url=url,
            client_ip=client_ip,
            error_message=error_message,
            stack_trace=stack_trace,
            request_data=request_data,
            response_data=response_data,
            duration_ms=duration_ms,
            status_code=status_code
        )
        
        self.db.add(audit_entry)
        self.db.commit()
        self.db.refresh(audit_entry)
        return audit_entry

    def log_request(
        self,
        action: str,
        method: str,
        url: str,
        client_ip: str,
        user_id: str = "anonymous",
        user_email: str = "anonymous",
        correlation_id: str = "",
        context: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict] = None,
        response_data: Optional[Dict] = None,
        duration_ms: Optional[int] = None,
        status_code: Optional[int] = None
    ):
        """
        Log HTTP request details
        """
        return self.log_action(
            action=action,
            level="INFO",
            user_id=user_id,
            user_email=user_email,
            correlation_id=correlation_id,
            context=context,
            method=method,
            url=url,
            client_ip=client_ip,
            request_data=request_data,
            response_data=response_data,
            duration_ms=duration_ms,
            status_code=status_code
        )

    def log_error(
        self,
        action: str,
        error: Exception,
        user_id: str = "anonymous",
        user_email: str = "anonymous",
        correlation_id: str = "",
        context: Optional[Dict[str, Any]] = None,
        method: Optional[str] = None,
        url: Optional[str] = None,
        client_ip: Optional[str] = None
    ):
        """
        Log error details
        """
        return self.log_action(
            action=action,
            level="ERROR",
            user_id=user_id,
            user_email=user_email,
            correlation_id=correlation_id,
            context=context,
            method=method,
            url=url,
            client_ip=client_ip,
            error_message=str(error),
            stack_trace="".join(traceback.format_tb(error.__traceback__)) if hasattr(error, "__traceback__") else "N/A"
        )


# Convenience functions for use in other modules
def log_action_to_db(
    db: Session,
    action: str,
    level: str = "INFO",
    user_id: str = "anonymous",
    user_email: str = "anonymous",
    correlation_id: str = "",
    context: Optional[Dict[str, Any]] = None,
    **kwargs
):
    """
    Log action to database
    """
    audit_service = AuditService(db)
    return audit_service.log_action(
        action=action,
        level=level,
        user_id=user_id,
        user_email=user_email,
        correlation_id=correlation_id,
        context=context,
        **kwargs
    )


def log_request_to_db(
    db: Session,
    action: str,
    method: str,
    url: str,
    client_ip: str,
    user_id: str = "anonymous",
    user_email: str = "anonymous",
    correlation_id: str = "",
    context: Optional[Dict[str, Any]] = None,
    **kwargs
):
    """
    Log request to database
    """
    audit_service = AuditService(db)
    return audit_service.log_request(
        action=action,
        method=method,
        url=url,
        client_ip=client_ip,
        user_id=user_id,
        user_email=user_email,
        correlation_id=correlation_id,
        context=context,
        **kwargs
    )


def log_error_to_db(
    db: Session,
    action: str,
    error: Exception,
    user_id: str = "anonymous",
    user_email: str = "anonymous",
    correlation_id: str = "",
    context: Optional[Dict[str, Any]] = None,
    **kwargs
):
    """
    Log error to database
    """
    audit_service = AuditService(db)
    return audit_service.log_error(
        action=action,
        error=error,
        user_id=user_id,
        user_email=user_email,
        correlation_id=correlation_id,
        context=context,
        **kwargs
    ) 