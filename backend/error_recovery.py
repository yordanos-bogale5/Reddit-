"""
Error recovery system for Reddit automation engine
Provides robust error handling, retry mechanisms, and automatic fallback strategies
"""
import logging
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import traceback

from celery import current_task
from celery_worker import celery_app
from database import SessionLocal
from models import (
    RedditAccount, ActivityLog, EngagementLog, AutomationSettings
)
from safety_tasks import record_action, is_account_safe

logger = logging.getLogger(__name__)

class ErrorType(Enum):
    """Types of errors that can occur"""
    NETWORK_ERROR = "network_error"
    API_ERROR = "api_error"
    RATE_LIMIT_ERROR = "rate_limit_error"
    AUTHENTICATION_ERROR = "authentication_error"
    PERMISSION_ERROR = "permission_error"
    CONTENT_ERROR = "content_error"
    SHADOWBAN_ERROR = "shadowban_error"
    UNKNOWN_ERROR = "unknown_error"

class RecoveryStrategy(Enum):
    """Recovery strategies for different error types"""
    IMMEDIATE_RETRY = "immediate_retry"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    CIRCUIT_BREAKER = "circuit_breaker"
    FALLBACK_ACTION = "fallback_action"
    PAUSE_AUTOMATION = "pause_automation"
    NO_RETRY = "no_retry"

@dataclass
class ErrorPattern:
    """Error pattern configuration"""
    error_type: ErrorType
    keywords: List[str]
    strategy: RecoveryStrategy
    max_retries: int
    base_delay: int  # seconds
    max_delay: int  # seconds
    circuit_breaker_threshold: int = 5

class ErrorRecoverySystem:
    """Comprehensive error recovery system"""
    
    def __init__(self):
        self.error_patterns = {
            ErrorType.NETWORK_ERROR: ErrorPattern(
                error_type=ErrorType.NETWORK_ERROR,
                keywords=['connection', 'timeout', 'network', 'unreachable', 'dns'],
                strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=5,
                base_delay=30,
                max_delay=300
            ),
            ErrorType.API_ERROR: ErrorPattern(
                error_type=ErrorType.API_ERROR,
                keywords=['api', 'server error', '500', '502', '503', '504'],
                strategy=RecoveryStrategy.EXPONENTIAL_BACKOFF,
                max_retries=3,
                base_delay=60,
                max_delay=600
            ),
            ErrorType.RATE_LIMIT_ERROR: ErrorPattern(
                error_type=ErrorType.RATE_LIMIT_ERROR,
                keywords=['rate limit', 'too many requests', '429', 'quota'],
                strategy=RecoveryStrategy.LINEAR_BACKOFF,
                max_retries=2,
                base_delay=300,
                max_delay=1800
            ),
            ErrorType.AUTHENTICATION_ERROR: ErrorPattern(
                error_type=ErrorType.AUTHENTICATION_ERROR,
                keywords=['unauthorized', '401', 'authentication', 'invalid token', 'expired'],
                strategy=RecoveryStrategy.PAUSE_AUTOMATION,
                max_retries=1,
                base_delay=3600,
                max_delay=3600
            ),
            ErrorType.PERMISSION_ERROR: ErrorPattern(
                error_type=ErrorType.PERMISSION_ERROR,
                keywords=['forbidden', '403', 'permission', 'banned', 'suspended'],
                strategy=RecoveryStrategy.PAUSE_AUTOMATION,
                max_retries=0,
                base_delay=0,
                max_delay=0
            ),
            ErrorType.SHADOWBAN_ERROR: ErrorPattern(
                error_type=ErrorType.SHADOWBAN_ERROR,
                keywords=['shadowban', 'shadow ban', 'invisible', 'not visible'],
                strategy=RecoveryStrategy.PAUSE_AUTOMATION,
                max_retries=0,
                base_delay=0,
                max_delay=0
            ),
            ErrorType.CONTENT_ERROR: ErrorPattern(
                error_type=ErrorType.CONTENT_ERROR,
                keywords=['content', 'spam', 'duplicate', 'removed', 'deleted'],
                strategy=RecoveryStrategy.FALLBACK_ACTION,
                max_retries=2,
                base_delay=60,
                max_delay=300
            )
        }
        
        self.circuit_breakers = {}  # Track circuit breaker states
        
    def classify_error(self, error_message: str, error_details: Dict[str, Any] = None) -> ErrorType:
        """Classify error based on message and details"""
        error_message_lower = error_message.lower()
        
        # Check each error pattern
        for error_type, pattern in self.error_patterns.items():
            if any(keyword in error_message_lower for keyword in pattern.keywords):
                return error_type
        
        # Check HTTP status codes if available
        if error_details:
            status_code = error_details.get('status_code')
            if status_code:
                if status_code == 429:
                    return ErrorType.RATE_LIMIT_ERROR
                elif status_code == 401:
                    return ErrorType.AUTHENTICATION_ERROR
                elif status_code == 403:
                    return ErrorType.PERMISSION_ERROR
                elif status_code >= 500:
                    return ErrorType.API_ERROR
        
        return ErrorType.UNKNOWN_ERROR
    
    def should_retry(self, account_id: int, error_type: ErrorType, attempt: int) -> bool:
        """Determine if operation should be retried"""
        pattern = self.error_patterns.get(error_type)
        if not pattern:
            return False
        
        # Check max retries
        if attempt >= pattern.max_retries:
            return False
        
        # Check circuit breaker
        if pattern.strategy == RecoveryStrategy.CIRCUIT_BREAKER:
            circuit_key = f"{account_id}:{error_type.value}"
            if self.circuit_breakers.get(circuit_key, 0) >= pattern.circuit_breaker_threshold:
                logger.warning(f"Circuit breaker open for {circuit_key}")
                return False
        
        # Check if account is still safe
        if not is_account_safe(account_id):
            logger.warning(f"Account {account_id} not safe, skipping retry")
            return False
        
        return True
    
    def calculate_delay(self, error_type: ErrorType, attempt: int) -> int:
        """Calculate delay before retry"""
        pattern = self.error_patterns.get(error_type)
        if not pattern:
            return 60  # Default 1 minute
        
        if pattern.strategy == RecoveryStrategy.IMMEDIATE_RETRY:
            return 0
        elif pattern.strategy == RecoveryStrategy.EXPONENTIAL_BACKOFF:
            delay = pattern.base_delay * (2 ** attempt)
        elif pattern.strategy == RecoveryStrategy.LINEAR_BACKOFF:
            delay = pattern.base_delay * (attempt + 1)
        else:
            delay = pattern.base_delay
        
        # Add jitter to avoid thundering herd
        jitter = random.uniform(0.8, 1.2)
        delay = int(delay * jitter)
        
        # Cap at max delay
        return min(delay, pattern.max_delay)
    
    def record_error(self, account_id: int, action_type: str, error_type: ErrorType, 
                    error_message: str, error_details: Dict[str, Any] = None) -> None:
        """Record error for analysis and circuit breaker logic"""
        try:
            # Update circuit breaker counter
            circuit_key = f"{account_id}:{error_type.value}"
            self.circuit_breakers[circuit_key] = self.circuit_breakers.get(circuit_key, 0) + 1
            
            # Record action as failed
            record_action(account_id, action_type, success=False)
            
            # Log error to database
            db = SessionLocal()
            error_log = ActivityLog(
                account_id=account_id,
                action='error_recorded',
                details={
                    'action_type': action_type,
                    'error_type': error_type.value,
                    'error_message': error_message,
                    'error_details': error_details or {},
                    'circuit_breaker_count': self.circuit_breakers[circuit_key],
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            db.add(error_log)
            db.commit()
            db.close()
            
            logger.error(f"Error recorded for account {account_id}: {error_type.value} - {error_message}")
            
        except Exception as e:
            logger.error(f"Error recording error: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
    
    def reset_circuit_breaker(self, account_id: int, error_type: ErrorType) -> None:
        """Reset circuit breaker after successful operation"""
        circuit_key = f"{account_id}:{error_type.value}"
        if circuit_key in self.circuit_breakers:
            del self.circuit_breakers[circuit_key]
            logger.info(f"Circuit breaker reset for {circuit_key}")
    
    def get_fallback_action(self, original_action: str, error_type: ErrorType) -> Optional[str]:
        """Get fallback action for failed operation"""
        fallback_map = {
            'post': 'comment',  # If posting fails, try commenting
            'comment': 'upvote',  # If commenting fails, try upvoting
            'upvote': None,  # No fallback for upvoting
        }
        
        if error_type == ErrorType.CONTENT_ERROR:
            return fallback_map.get(original_action)
        
        return None

error_recovery = ErrorRecoverySystem()

def with_error_recovery(action_type: str):
    """Decorator for adding error recovery to automation tasks"""
    def decorator(func: Callable) -> Callable:
        def wrapper(self, account_id: int, *args, **kwargs):
            attempt = getattr(self.request, 'retries', 0)
            
            try:
                # Execute the original function
                result = func(self, account_id, *args, **kwargs)
                
                # If successful, reset any circuit breakers
                for error_type in ErrorType:
                    error_recovery.reset_circuit_breaker(account_id, error_type)
                
                return result
                
            except Exception as e:
                error_message = str(e)
                error_details = {
                    'traceback': traceback.format_exc(),
                    'args': args,
                    'kwargs': kwargs
                }
                
                # Classify the error
                error_type = error_recovery.classify_error(error_message, error_details)
                
                # Record the error
                error_recovery.record_error(account_id, action_type, error_type, error_message, error_details)
                
                # Determine if we should retry
                if error_recovery.should_retry(account_id, error_type, attempt):
                    delay = error_recovery.calculate_delay(error_type, attempt)
                    logger.info(f"Retrying {action_type} for account {account_id} in {delay} seconds (attempt {attempt + 1})")
                    raise self.retry(countdown=delay)
                
                # Check for fallback action
                pattern = error_recovery.error_patterns.get(error_type)
                if pattern and pattern.strategy == RecoveryStrategy.FALLBACK_ACTION:
                    fallback_action = error_recovery.get_fallback_action(action_type, error_type)
                    if fallback_action:
                        logger.info(f"Attempting fallback action {fallback_action} for account {account_id}")
                        # Note: In a real implementation, you'd queue the fallback task here
                        return {
                            'status': 'fallback_attempted',
                            'original_action': action_type,
                            'fallback_action': fallback_action,
                            'error_type': error_type.value,
                            'error_message': error_message
                        }
                
                # If we can't retry or fallback, return error
                return {
                    'status': 'error',
                    'error_type': error_type.value,
                    'error_message': error_message,
                    'attempt': attempt,
                    'max_retries_reached': True
                }
        
        return wrapper
    return decorator

# Celery Tasks for Error Recovery Management

@celery_app.task(bind=True, max_retries=3)
def analyze_error_patterns(self, account_id: int = None, days: int = 7) -> Dict[str, Any]:
    """Analyze error patterns to improve recovery strategies"""
    try:
        logger.info(f"Analyzing error patterns for {'all accounts' if not account_id else f'account {account_id}'}")

        db = SessionLocal()

        # Get error logs
        start_date = datetime.utcnow() - timedelta(days=days)
        query = db.query(ActivityLog).filter(
            ActivityLog.action == 'error_recorded',
            ActivityLog.timestamp >= start_date
        )

        if account_id:
            query = query.filter(ActivityLog.account_id == account_id)

        error_logs = query.all()

        analysis = {
            'analysis_period_days': days,
            'total_errors': len(error_logs),
            'error_by_type': {},
            'error_by_account': {},
            'error_by_action': {},
            'recovery_effectiveness': {},
            'recommendations': []
        }

        for log in error_logs:
            if not log.details or not isinstance(log.details, dict):
                continue

            error_type = log.details.get('error_type', 'unknown')
            action_type = log.details.get('action_type', 'unknown')
            account_id_log = log.account_id

            # Count by error type
            analysis['error_by_type'][error_type] = analysis['error_by_type'].get(error_type, 0) + 1

            # Count by account
            analysis['error_by_account'][account_id_log] = analysis['error_by_account'].get(account_id_log, 0) + 1

            # Count by action
            analysis['error_by_action'][action_type] = analysis['error_by_action'].get(action_type, 0) + 1

        # Generate recommendations
        if analysis['error_by_type']:
            most_common_error = max(analysis['error_by_type'], key=analysis['error_by_type'].get)
            analysis['recommendations'].append(f"Most common error: {most_common_error}")

            if analysis['error_by_type'].get('rate_limit_error', 0) > 10:
                analysis['recommendations'].append("High rate limit errors - consider reducing automation frequency")

            if analysis['error_by_type'].get('authentication_error', 0) > 5:
                analysis['recommendations'].append("Authentication errors detected - check account credentials")

            if analysis['error_by_type'].get('permission_error', 0) > 0:
                analysis['recommendations'].append("Permission errors detected - accounts may be banned or restricted")

        # Identify problematic accounts
        if analysis['error_by_account']:
            avg_errors = sum(analysis['error_by_account'].values()) / len(analysis['error_by_account'])
            problematic_accounts = [
                acc_id for acc_id, count in analysis['error_by_account'].items()
                if count > avg_errors * 2
            ]

            if problematic_accounts:
                analysis['recommendations'].append(f"Accounts with high error rates: {problematic_accounts}")

        db.close()

        logger.info(f"Error pattern analysis completed: {analysis['total_errors']} errors analyzed")

        return {
            'status': 'success',
            'analysis': analysis
        }

    except Exception as e:
        logger.error(f"Error analyzing error patterns: {e}")
        if 'db' in locals():
            db.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

        return {'status': 'error', 'message': str(e)}

@celery_app.task
def reset_circuit_breakers(account_id: int = None) -> Dict[str, Any]:
    """Reset circuit breakers for accounts"""
    try:
        logger.info(f"Resetting circuit breakers for {'all accounts' if not account_id else f'account {account_id}'}")

        reset_count = 0

        if account_id:
            # Reset for specific account
            keys_to_remove = [key for key in error_recovery.circuit_breakers.keys() if key.startswith(f"{account_id}:")]
            for key in keys_to_remove:
                del error_recovery.circuit_breakers[key]
                reset_count += 1
        else:
            # Reset all circuit breakers
            reset_count = len(error_recovery.circuit_breakers)
            error_recovery.circuit_breakers.clear()

        logger.info(f"Reset {reset_count} circuit breakers")

        return {
            'status': 'success',
            'reset_count': reset_count,
            'account_id': account_id
        }

    except Exception as e:
        logger.error(f"Error resetting circuit breakers: {e}")
        return {'status': 'error', 'message': str(e)}

@celery_app.task
def cleanup_error_logs(days_to_keep: int = 30) -> Dict[str, Any]:
    """Clean up old error logs"""
    try:
        logger.info(f"Cleaning up error logs older than {days_to_keep} days")

        db = SessionLocal()
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        # Count and delete old error logs
        deleted_count = db.query(ActivityLog).filter(
            ActivityLog.action == 'error_recorded',
            ActivityLog.timestamp < cutoff_date
        ).count()

        db.query(ActivityLog).filter(
            ActivityLog.action == 'error_recorded',
            ActivityLog.timestamp < cutoff_date
        ).delete()

        db.commit()
        db.close()

        logger.info(f"Cleaned up {deleted_count} old error logs")

        return {
            'status': 'success',
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }

    except Exception as e:
        logger.error(f"Error cleaning up error logs: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return {'status': 'error', 'message': str(e)}

@celery_app.task
def generate_error_recovery_report(days: int = 7) -> Dict[str, Any]:
    """Generate comprehensive error recovery report"""
    try:
        logger.info(f"Generating error recovery report for last {days} days")

        # Get error analysis
        analysis_result = analyze_error_patterns.delay(days=days)
        analysis = analysis_result.get(timeout=60)

        if analysis['status'] != 'success':
            return analysis

        # Get current circuit breaker status
        circuit_breaker_status = {
            'total_circuit_breakers': len(error_recovery.circuit_breakers),
            'active_circuit_breakers': list(error_recovery.circuit_breakers.keys()),
            'circuit_breaker_counts': dict(error_recovery.circuit_breakers)
        }

        report = {
            'report_date': datetime.utcnow().isoformat(),
            'period_days': days,
            'error_analysis': analysis['analysis'],
            'circuit_breaker_status': circuit_breaker_status,
            'system_health': {
                'total_errors': analysis['analysis']['total_errors'],
                'error_rate': analysis['analysis']['total_errors'] / days if days > 0 else 0,
                'most_problematic_accounts': list(analysis['analysis']['error_by_account'].keys())[:5],
                'recovery_recommendations': analysis['analysis']['recommendations']
            }
        }

        logger.info(f"Error recovery report generated: {report['system_health']}")

        return {
            'status': 'success',
            'report': report
        }

    except Exception as e:
        logger.error(f"Error generating recovery report: {e}")
        return {'status': 'error', 'message': str(e)}
