"""
Account Health Dashboard API endpoints for Reddit automation dashboard
Provides comprehensive health metrics, trend analysis, and monitoring features
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from database import get_db
from models import RedditAccount, AccountHealth
from health_dashboard import health_dashboard, HealthMetrics, TrendAnalysis, HealthAlert

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class HealthMetricsResponse(BaseModel):
    trust_score: float
    activity_score: float
    engagement_score: float
    safety_score: float
    consistency_score: float
    growth_score: float
    overall_health: float
    health_grade: str
    risk_level: str

class TrendAnalysisResponse(BaseModel):
    metric_name: str
    current_value: float
    previous_value: float
    change_percentage: float
    trend_direction: str
    confidence: float

class HealthAlertResponse(BaseModel):
    alert_type: str
    severity: str
    message: str
    metric_affected: str
    current_value: float
    threshold: float
    recommendations: List[str]

class HealthDashboardResponse(BaseModel):
    account_id: int
    username: str
    metrics: HealthMetricsResponse
    trends: List[TrendAnalysisResponse]
    alerts: List[HealthAlertResponse]
    recommendations: List[str]
    last_updated: str

@router.get("/metrics/{account_id}")
async def get_health_metrics(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive health metrics for an account
    
    Args:
        account_id: Account to analyze
        
    Returns:
        Detailed health metrics
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Calculate health metrics
        metrics = health_dashboard.calculate_comprehensive_health(account_id)
        
        return HealthMetricsResponse(
            trust_score=metrics.trust_score,
            activity_score=metrics.activity_score,
            engagement_score=metrics.engagement_score,
            safety_score=metrics.safety_score,
            consistency_score=metrics.consistency_score,
            growth_score=metrics.growth_score,
            overall_health=metrics.overall_health,
            health_grade=metrics.health_grade,
            risk_level=metrics.risk_level
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health metrics")

@router.get("/trends/{account_id}")
async def get_health_trends(
    account_id: int,
    days: int = Query(30, description="Number of days for trend analysis"),
    db: Session = Depends(get_db)
):
    """
    Get health trend analysis for an account
    
    Args:
        account_id: Account to analyze
        days: Number of days for trend analysis
        
    Returns:
        Health trend analysis
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Analyze trends
        trends = health_dashboard.analyze_health_trends(account_id, days)
        
        # Convert to response format
        trend_responses = []
        for trend in trends:
            trend_responses.append(TrendAnalysisResponse(
                metric_name=trend.metric_name,
                current_value=trend.current_value,
                previous_value=trend.previous_value,
                change_percentage=trend.change_percentage,
                trend_direction=trend.trend_direction,
                confidence=trend.confidence
            ))
        
        return {
            "account_id": account_id,
            "analysis_period_days": days,
            "trends": trend_responses
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health trends")

@router.get("/alerts/{account_id}")
async def get_health_alerts(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Get health alerts for an account
    
    Args:
        account_id: Account to analyze
        
    Returns:
        List of health alerts
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Generate alerts
        alerts = health_dashboard.generate_health_alerts(account_id)
        
        # Convert to response format
        alert_responses = []
        for alert in alerts:
            alert_responses.append(HealthAlertResponse(
                alert_type=alert.alert_type,
                severity=alert.severity,
                message=alert.message,
                metric_affected=alert.metric_affected,
                current_value=alert.current_value,
                threshold=alert.threshold,
                recommendations=alert.recommendations
            ))
        
        return {
            "account_id": account_id,
            "total_alerts": len(alert_responses),
            "alerts_by_severity": {
                "critical": len([a for a in alerts if a.severity == "critical"]),
                "high": len([a for a in alerts if a.severity == "high"]),
                "medium": len([a for a in alerts if a.severity == "medium"]),
                "low": len([a for a in alerts if a.severity == "low"])
            },
            "alerts": alert_responses
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health alerts: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health alerts")

@router.get("/recommendations/{account_id}")
async def get_health_recommendations(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Get personalized health improvement recommendations
    
    Args:
        account_id: Account to analyze
        
    Returns:
        List of actionable recommendations
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get recommendations
        recommendations = health_dashboard.get_health_recommendations(account_id)
        
        return {
            "account_id": account_id,
            "username": account.reddit_username,
            "total_recommendations": len(recommendations),
            "recommendations": recommendations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting health recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health recommendations")

@router.get("/dashboard/{account_id}")
async def get_complete_health_dashboard(
    account_id: int,
    trend_days: int = Query(30, description="Days for trend analysis"),
    db: Session = Depends(get_db)
):
    """
    Get complete health dashboard for an account
    
    Args:
        account_id: Account to analyze
        trend_days: Days for trend analysis
        
    Returns:
        Complete health dashboard data
    """
    try:
        from datetime import datetime
        
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get all health data
        metrics = health_dashboard.calculate_comprehensive_health(account_id)
        trends = health_dashboard.analyze_health_trends(account_id, trend_days)
        alerts = health_dashboard.generate_health_alerts(account_id)
        recommendations = health_dashboard.get_health_recommendations(account_id)
        
        # Convert to response format
        metrics_response = HealthMetricsResponse(
            trust_score=metrics.trust_score,
            activity_score=metrics.activity_score,
            engagement_score=metrics.engagement_score,
            safety_score=metrics.safety_score,
            consistency_score=metrics.consistency_score,
            growth_score=metrics.growth_score,
            overall_health=metrics.overall_health,
            health_grade=metrics.health_grade,
            risk_level=metrics.risk_level
        )
        
        trend_responses = [
            TrendAnalysisResponse(
                metric_name=trend.metric_name,
                current_value=trend.current_value,
                previous_value=trend.previous_value,
                change_percentage=trend.change_percentage,
                trend_direction=trend.trend_direction,
                confidence=trend.confidence
            ) for trend in trends
        ]
        
        alert_responses = [
            HealthAlertResponse(
                alert_type=alert.alert_type,
                severity=alert.severity,
                message=alert.message,
                metric_affected=alert.metric_affected,
                current_value=alert.current_value,
                threshold=alert.threshold,
                recommendations=alert.recommendations
            ) for alert in alerts
        ]
        
        return HealthDashboardResponse(
            account_id=account_id,
            username=account.reddit_username,
            metrics=metrics_response,
            trends=trend_responses,
            alerts=alert_responses,
            recommendations=recommendations,
            last_updated=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting complete health dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to get complete health dashboard")

@router.get("/summary")
async def get_all_accounts_health_summary(
    db: Session = Depends(get_db)
):
    """
    Get health summary for all accounts
    
    Returns:
        Summary of health across all accounts
    """
    try:
        accounts = db.query(RedditAccount).all()
        
        summary = {
            "total_accounts": len(accounts),
            "health_distribution": {
                "A": 0, "B": 0, "C": 0, "D": 0, "F": 0
            },
            "risk_distribution": {
                "Low": 0, "Medium": 0, "High": 0
            },
            "average_scores": {
                "overall_health": 0,
                "trust_score": 0,
                "safety_score": 0
            },
            "accounts_with_alerts": 0,
            "total_critical_alerts": 0
        }
        
        total_health = 0
        total_trust = 0
        total_safety = 0
        accounts_with_alerts = 0
        total_critical_alerts = 0
        
        for account in accounts:
            try:
                metrics = health_dashboard.calculate_comprehensive_health(account.id)
                alerts = health_dashboard.generate_health_alerts(account.id)
                
                # Update distributions
                summary["health_distribution"][metrics.health_grade] += 1
                summary["risk_distribution"][metrics.risk_level] += 1
                
                # Update totals for averages
                total_health += metrics.overall_health
                total_trust += metrics.trust_score
                total_safety += metrics.safety_score
                
                # Count alerts
                if alerts:
                    accounts_with_alerts += 1
                    critical_alerts = len([a for a in alerts if a.severity == "critical"])
                    total_critical_alerts += critical_alerts
                    
            except Exception as e:
                logger.warning(f"Error analyzing account {account.id}: {e}")
        
        # Calculate averages
        if len(accounts) > 0:
            summary["average_scores"]["overall_health"] = total_health / len(accounts)
            summary["average_scores"]["trust_score"] = total_trust / len(accounts)
            summary["average_scores"]["safety_score"] = total_safety / len(accounts)
        
        summary["accounts_with_alerts"] = accounts_with_alerts
        summary["total_critical_alerts"] = total_critical_alerts
        
        return summary
        
    except Exception as e:
        logger.error(f"Error getting health summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to get health summary")
