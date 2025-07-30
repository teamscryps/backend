
import logging
import logging.handlers
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
from fastapi import Request
from schemas.user import User
from config import settings
import uuid
import traceback

class Logger:
    def __init__(self, log_file: str = "logs/app.log", max_log_days: int = 7):
        """
        Initialize the logger with file rotation, JSON formatting, and dynamic log level.
        """
        # Ensure log directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

        # Configure logger
        self.logger = logging.getLogger("DashboardLogger")
        self.logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

        # Remove existing handlers to avoid duplication
        self.logger.handlers.clear()

        # File handler with daily rotation
        file_handler = logging.handlers.TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",
            interval=1,
            backupCount=max_log_days,
            encoding="utf-8"
        )

        # Stream handler for stdout
        stream_handler = logging.StreamHandler()

        # JSON formatter
        formatter = logging.Formatter(
            json.dumps({
                "timestamp": "%(asctime)s",
                "level": "%(levelname)s",
                "action": "%(message)s",
                "user_id": "%(user_id)s",
                "user_email": "%(user_email)s",
                "correlation_id": "%(correlation_id)s",
                "context": "%(context)s"
            }, ensure_ascii=False)
        )
        file_handler.setFormatter(formatter)
        stream_handler.setFormatter(formatter)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(stream_handler)

    def log_action(
        self,
        action: str,
        level: str = "INFO",
        user: Optional[User] = None,
        correlation_id: str = "",
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Log a user action with context and correlation ID.
        """
        user_id = user.id if user else "anonymous"
        user_email = user.email if user else "anonymous"
        if not user:
            context = context or {}
            context["warning"] = "No authenticated user provided"
        context_str = json.dumps(context or {}, ensure_ascii=False)

        self.logger.log(
            level=getattr(logging, level.upper(), logging.INFO),
            msg=action,
            extra={
                "user_id": user_id,
                "user_email": user_email,
                "correlation_id": correlation_id,
                "context": context_str
            }
        )

    async def log_request(
        self,
        request: Request,
        action: str,
        user: Optional[User] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Log an HTTP request with user action details and correlation ID.
        """
        correlation_id = str(uuid.uuid4())
        context = context or {}
        context.update({
            "method": request.method,
            "url": str(request.url),
            "client_ip": request.client.host if request.client else "unknown"
        })
        self.log_action(action, "INFO", user, correlation_id, context)
        return correlation_id

    def log_error(
        self,
        action: str,
        error: Exception,
        user: Optional[User] = None,
        correlation_id: str = "",
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Log an error with stack trace and correlation ID.
        """
        context = context or {}
        context["error"] = str(error)
        context["stack_trace"] = "".join(traceback.format_tb(error.__traceback__)) if hasattr(error, "__traceback__") else "N/A"
        self.log_action(action, "ERROR", user, correlation_id, context)

# Singleton logger instance
logger_instance = Logger()

# Convenience functions for use in other modules
def log_action(action: str, user: Optional[User] = None, correlation_id: str = "", context: Optional[Dict[str, Any]] = None):
    logger_instance.log_action(action, "INFO", user, correlation_id, context)

async def log_request(request: Request, action: str, user: Optional[User] = None, context: Optional[Dict[str, Any]] = None):
    return await logger_instance.log_request(request, action, user, context)

def log_error(action: str, error: Exception, user: Optional[User] = None, correlation_id: str = "", context: Optional[Dict[str, Any]] = None):
    logger_instance.log_error(action, error, user, correlation_id, context)
