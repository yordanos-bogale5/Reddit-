"""
Safety monitoring API endpoints for Reddit automation dashboard
Provides safety alerts, monitoring, and compliance features
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from database import get_db
from models import RedditAccount, AccountHealth, ActivityLog
from safety_tasks import (
    get_safety_status, comprehensive_shadowban_check, detect_captcha_patterns,
    auto_pause_automation, create_safety_alert, get_safety_alerts,
    get_rate_limit_status, check_adaptive_rate_limits
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class SafetyStatusResponse(BaseModel):
    account_id: int
    username: str
    is_safe: bool
    health_metrics: Dict[str, Any]
    rate_limits: Dict[str, Any]

class ShadowbanCheckResponse(BaseModel):
    account_id: int
    username: str
    timestamp: str
    tests: Dict[str, Any]
    overall_result: str
    confidence: float
    recommendations: List[str]

class SafetyAlertRequest(BaseModel):
    account_id: int
    alert_type: str
    severity: str
    message: str
    details: Optional[Dict[str, Any]] = None

class AutoPauseRequest(BaseModel):
    account_id: int
    reason: str

@router.get("/status/{account_id}", response_model=SafetyStatusResponse)
async def get_account_safety_status(account_id: int, db: Session = Depends(get_db)):
    """
    Get comprehensive safety status for an account
    
    Args:
        account_id: Account to check
        
    Returns:
        Detailed safety status including health metrics and rate limits
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get safety status
        status = get_safety_status(account_id)
        if 'error' in status:
            raise HTTPException(status_code=500, detail=status['error'])
        
        return SafetyStatusResponse(
            account_id=status['account_id'],
            username=status['username'],
            is_safe=status['is_safe'],
            health_metrics=status['health_metrics'],
            rate_limits=status['rate_limits']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting safety status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get safety status")

@router.post("/shadowban-check/{account_id}", response_model=ShadowbanCheckResponse)
async def perform_shadowban_check(account_id: int, db: Session = Depends(get_db)):
    """
    Perform comprehensive shadowban detection for an account
    
    Args:
        account_id: Account to check
        
    Returns:
        Detailed shadowban analysis with multiple test results
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Perform comprehensive shadowban check
        result = comprehensive_shadowban_check(account_id)
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        return ShadowbanCheckResponse(
            account_id=result['account_id'],
            username=result['username'],
            timestamp=result['timestamp'],
            tests=result['tests'],
            overall_result=result['overall_result'],
            confidence=result['confidence'],
            recommendations=result['recommendations']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing shadowban check: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform shadowban check")

@router.get("/captcha-detection/{account_id}")
async def detect_account_captcha_patterns(account_id: int, db: Session = Depends(get_db)):
    """
    Detect captcha patterns for an account
    
    Args:
        account_id: Account to analyze
        
    Returns:
        Captcha detection analysis
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Detect captcha patterns
        result = detect_captcha_patterns(account_id)
        if 'error' in result:
            raise HTTPException(status_code=500, detail=result['error'])
        
        return {
            "account_id": account_id,
            "captcha_analysis": result,
            "recommendations": [
                "Reduce automation frequency" if result.get('frequent_captchas') else "Captcha frequency appears normal",
                "Monitor for 24-48 hours" if result.get('captcha_mentions', 0) > 0 else "No recent captcha issues detected"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error detecting captcha patterns: {e}")
        raise HTTPException(status_code=500, detail="Failed to detect captcha patterns")

@router.post("/auto-pause")
async def auto_pause_account_automation(request: AutoPauseRequest, db: Session = Depends(get_db)):
    """
    Automatically pause automation for an account
    
    Args:
        request: Auto-pause request with account ID and reason
        
    Returns:
        Result of auto-pause operation
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Auto-pause automation
        result = auto_pause_automation(request.account_id, request.reason)
        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to pause automation'))
        
        return {
            "success": True,
            "message": f"Automation paused for account {request.account_id}",
            "details": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error auto-pausing automation: {e}")
        raise HTTPException(status_code=500, detail="Failed to auto-pause automation")

@router.post("/alerts")
async def create_safety_alert_endpoint(request: SafetyAlertRequest, db: Session = Depends(get_db)):
    """
    Create a safety alert for an account
    
    Args:
        request: Safety alert request
        
    Returns:
        Created alert details
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Create safety alert
        alert = create_safety_alert(
            request.account_id,
            request.alert_type,
            request.severity,
            request.message,
            request.details
        )
        
        if 'error' in alert:
            raise HTTPException(status_code=500, detail=alert['error'])
        
        return {
            "success": True,
            "message": "Safety alert created successfully",
            "alert": alert
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating safety alert: {e}")
        raise HTTPException(status_code=500, detail="Failed to create safety alert")

@router.get("/alerts")
async def get_safety_alerts_endpoint(
    account_id: Optional[int] = Query(None, description="Filter by account ID"),
    hours: int = Query(24, description="Hours to look back"),
    severity: Optional[str] = Query(None, description="Filter by severity")
):
    """
    Get recent safety alerts
    
    Args:
        account_id: Optional account ID filter
        hours: Hours to look back
        severity: Optional severity filter
        
    Returns:
        List of safety alerts
    """
    try:
        # Get alerts
        alerts = get_safety_alerts(account_id, hours)
        
        # Filter by severity if specified
        if severity:
            alerts = [alert for alert in alerts if alert.get('severity') == severity]
        
        return {
            "total_alerts": len(alerts),
            "filters": {
                "account_id": account_id,
                "hours": hours,
                "severity": severity
            },
            "alerts": alerts
        }
        
    except Exception as e:
        logger.error(f"Error getting safety alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get safety alerts")

@router.get("/rate-limits/{account_id}")
async def get_account_rate_limits(account_id: int, db: Session = Depends(get_db)):
    """
    Get detailed rate limit status for an account
    
    Args:
        account_id: Account to check
        
    Returns:
        Comprehensive rate limit information
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get rate limit status
        status = get_rate_limit_status(account_id)
        if 'error' in status:
            raise HTTPException(status_code=500, detail=status['error'])
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get rate limit status")

@router.get("/check-action/{account_id}")
async def check_action_allowed(
    account_id: int,
    action_type: str = Query(..., description="Action type: upvote, comment, post"),
    db: Session = Depends(get_db)
):
    """
    Check if an action is allowed for an account based on rate limits and safety
    
    Args:
        account_id: Account to check
        action_type: Type of action to check
        
    Returns:
        Whether action is allowed and reasons
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Check if action is allowed
        rate_limit_ok = check_adaptive_rate_limits(account_id, action_type)
        
        # Get detailed status
        safety_status = get_safety_status(account_id)
        is_safe = safety_status.get('is_safe', False)
        
        # Check for automation pause
        import redis
        import json
        redis_client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
        pause_key = f"automation_paused:{account_id}"
        pause_data = redis_client.get(pause_key)
        is_paused = bool(pause_data)
        
        allowed = rate_limit_ok and is_safe and not is_paused
        
        reasons = []
        if not rate_limit_ok:
            reasons.append("Rate limit exceeded")
        if not is_safe:
            reasons.append("Account safety check failed")
        if is_paused:
            pause_info = json.loads(pause_data) if pause_data else {}
            reasons.append(f"Automation paused: {pause_info.get('reason', 'Unknown reason')}")
        
        return {
            "account_id": account_id,
            "action_type": action_type,
            "allowed": allowed,
            "reasons": reasons if not allowed else ["Action allowed"],
            "checks": {
                "rate_limit_ok": rate_limit_ok,
                "is_safe": is_safe,
                "is_paused": is_paused
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking action allowance: {e}")
        raise HTTPException(status_code=500, detail="Failed to check action allowance")

@router.get("/health-summary")
async def get_overall_health_summary(db: Session = Depends(get_db)):
    """
    Get overall health summary across all accounts
    
    Returns:
        Summary of account health across the system
    """
    try:
        accounts = db.query(RedditAccount).all()
        
        summary = {
            "total_accounts": len(accounts),
            "safe_accounts": 0,
            "unsafe_accounts": 0,
            "paused_accounts": 0,
            "shadowbanned_accounts": 0,
            "accounts_with_alerts": 0,
            "recent_alerts": []
        }
        
        # Get recent alerts for all accounts
        all_alerts = get_safety_alerts(None, 24)
        summary["recent_alerts"] = all_alerts[:10]  # Last 10 alerts
        summary["accounts_with_alerts"] = len(set(alert['account_id'] for alert in all_alerts))
        
        # Check each account
        import redis
        redis_client = redis.Redis(host='localhost', port=6379, db=1, decode_responses=True)
        
        for account in accounts:
            try:
                # Check safety status
                safety_status = get_safety_status(account.id)
                if safety_status.get('is_safe'):
                    summary["safe_accounts"] += 1
                else:
                    summary["unsafe_accounts"] += 1
                
                # Check shadowban status
                health = account.account_health
                if health and health.shadowbanned:
                    summary["shadowbanned_accounts"] += 1
                
                # Check pause status
                pause_key = f"automation_paused:{account.id}"
                if redis_client.get(pause_key):
                    summary["paused_accounts"] += 1
                    
            except Exception as e:
                logger.warning(f"Error checking account {account.id} in summary: {e}")
                summary["unsafe_accounts"] += 1
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting health summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health summary")
