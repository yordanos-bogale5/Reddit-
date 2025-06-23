"""
Centralized error handling and logging for Reddit Dashboard
"""

import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import praw.exceptions

from database import SessionLocal
from models import ActivityLog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('reddit_dashboard.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class ErrorHandler:
    """Centralized error handling and logging"""
    
    @staticmethod
    def log_error(error: Exception, context: Dict[str, Any] = None, account_id: int = None):
        """Log error with context information"""
        error_details = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.error(f"Error occurred: {error_details}")
        
        # Log to database if account_id is provided
        if account_id:
            try:
                db = SessionLocal()
                activity_log = ActivityLog(
                    account_id=account_id,
                    action="error_occurred",
                    details=error_details
                )
                db.add(activity_log)
                db.commit()
                db.close()
            except Exception as db_error:
                logger.error(f"Failed to log error to database: {db_error}")
    
    @staticmethod
    def handle_reddit_api_error(error: Exception) -> Dict[str, Any]:
        """Handle Reddit API specific errors"""
        if isinstance(error, praw.exceptions.RedditAPIException):
            # Handle specific Reddit API errors
            error_type = error.error_type if hasattr(error, 'error_type') else 'UNKNOWN'
            
            error_responses = {
                'RATELIMIT': {
                    "error": "Rate limit exceeded",
                    "message": "Please wait before making more requests",
                    "retry_after": getattr(error, 'retry_after', 60)
                },
                'INVALID_USER': {
                    "error": "Invalid user",
                    "message": "The specified user does not exist"
                },
                'SUBREDDIT_NOEXIST': {
                    "error": "Subreddit does not exist",
                    "message": "The specified subreddit was not found"
                },
                'NO_TEXT': {
                    "error": "No text provided",
                    "message": "Text content is required for this action"
                },
                'TOO_LONG': {
                    "error": "Content too long",
                    "message": "The provided content exceeds the maximum length"
                }
            }
            
            return error_responses.get(error_type, {
                "error": "Reddit API error",
                "message": str(error)
            })
        
        elif isinstance(error, praw.exceptions.ResponseException):
            return {
                "error": "Reddit response error",
                "message": f"Reddit API returned status code {error.response.status_code}"
            }
        
        elif isinstance(error, praw.exceptions.ClientException):
            return {
                "error": "Reddit client error",
                "message": "Invalid request to Reddit API"
            }
        
        else:
            return {
                "error": "Unknown Reddit error",
                "message": str(error)
            }
    
    @staticmethod
    def handle_database_error(error: Exception) -> Dict[str, Any]:
        """Handle database specific errors"""
        if isinstance(error, SQLAlchemyError):
            return {
                "error": "Database error",
                "message": "A database operation failed",
                "details": str(error)
            }
        else:
            return {
                "error": "Unknown database error",
                "message": str(error)
            }
    
    @staticmethod
    def create_error_response(
        status_code: int,
        error_type: str,
        message: str,
        details: Dict[str, Any] = None
    ) -> HTTPException:
        """Create standardized error response"""
        error_detail = {
            "error": error_type,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if details:
            error_detail["details"] = details
        
        return HTTPException(status_code=status_code, detail=error_detail)

class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message: str, field: str = None):
        self.message = message
        self.field = field
        super().__init__(self.message)

class RateLimitError(Exception):
    """Custom rate limit error"""
    def __init__(self, message: str, retry_after: int = 60):
        self.message = message
        self.retry_after = retry_after
        super().__init__(self.message)

class AuthenticationError(Exception):
    """Custom authentication error"""
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)

def validate_account_id(account_id: int) -> None:
    """Validate account ID"""
    if not isinstance(account_id, int) or account_id <= 0:
        raise ValidationError("Invalid account ID", "account_id")

def validate_subreddit_name(subreddit: str) -> None:
    """Validate subreddit name"""
    if not subreddit or not isinstance(subreddit, str):
        raise ValidationError("Invalid subreddit name", "subreddit")
    
    if len(subreddit) > 21:  # Reddit subreddit name limit
        raise ValidationError("Subreddit name too long", "subreddit")
    
    # Basic validation for subreddit name format
    import re
    if not re.match(r'^[A-Za-z0-9_]+$', subreddit):
        raise ValidationError("Invalid subreddit name format", "subreddit")

def validate_content_length(content: str, max_length: int, field_name: str) -> None:
    """Validate content length"""
    if content and len(content) > max_length:
        raise ValidationError(f"{field_name} exceeds maximum length of {max_length}", field_name)

def validate_required_field(value: Any, field_name: str) -> None:
    """Validate required field"""
    if value is None:
        raise ValidationError(f"{field_name} is required", field_name)

    # For strings, check if empty or whitespace only
    if isinstance(value, str) and not value.strip():
        raise ValidationError(f"{field_name} is required", field_name)

# Global exception handler for FastAPI
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for FastAPI"""
    
    # Log the error
    ErrorHandler.log_error(exc, {
        "url": str(request.url),
        "method": request.method,
        "headers": dict(request.headers)
    })
    
    # Handle specific error types
    if isinstance(exc, ValidationError):
        return JSONResponse(
            status_code=400,
            content={
                "error": "Validation error",
                "message": exc.message,
                "field": exc.field,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    elif isinstance(exc, RateLimitError):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": exc.message,
                "retry_after": exc.retry_after,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    elif isinstance(exc, AuthenticationError):
        return JSONResponse(
            status_code=401,
            content={
                "error": "Authentication error",
                "message": exc.message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    elif isinstance(exc, praw.exceptions.RedditAPIException):
        error_info = ErrorHandler.handle_reddit_api_error(exc)
        return JSONResponse(
            status_code=400,
            content={
                **error_info,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    elif isinstance(exc, SQLAlchemyError):
        error_info = ErrorHandler.handle_database_error(exc)
        return JSONResponse(
            status_code=500,
            content={
                **error_info,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    else:
        # Generic error handler
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "message": "An unexpected error occurred",
                "timestamp": datetime.utcnow().isoformat()
            }
        )

# Decorator for endpoint error handling
def handle_errors(func):
    """Decorator to add error handling to endpoint functions"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ValidationError as e:
            raise ErrorHandler.create_error_response(400, "Validation error", e.message)
        except RateLimitError as e:
            raise ErrorHandler.create_error_response(429, "Rate limit exceeded", e.message)
        except AuthenticationError as e:
            raise ErrorHandler.create_error_response(401, "Authentication error", e.message)
        except Exception as e:
            ErrorHandler.log_error(e, {"function": func.__name__})
            raise ErrorHandler.create_error_response(500, "Internal server error", "An unexpected error occurred")
    
    return wrapper
