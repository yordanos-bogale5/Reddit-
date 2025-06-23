"""
Subreddit & Keyword Targeting API endpoints for Reddit automation dashboard
Provides intelligent targeting, performance analysis, and optimization features
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from database import get_db
from models import RedditAccount, AutomationSettings
from targeting_service import targeting_service, SubredditMetrics, KeywordAnalysis, TargetingRecommendation

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class SubredditMetricsResponse(BaseModel):
    subreddit: str
    total_actions: int
    successful_actions: int
    success_rate: float
    avg_karma_gain: float
    avg_response_time: float
    engagement_rate: float
    risk_score: float
    recommendation: str

class KeywordAnalysisResponse(BaseModel):
    keyword: str
    frequency: int
    success_rate: float
    avg_karma: float
    sentiment_score: float
    relevance_score: float
    recommendation: str

class TargetingRecommendationResponse(BaseModel):
    subreddit: str
    confidence: float
    reasons: List[str]
    optimal_times: List[int]
    suggested_keywords: List[str]
    risk_level: str

class TargetingUpdateRequest(BaseModel):
    account_id: int
    selected_subreddits: List[str]
    active_keywords: List[str]
    engagement_schedule: Dict[str, List[int]]

class BlocklistRequest(BaseModel):
    account_id: int
    subreddits_to_block: List[str]
    reason: str

@router.get("/subreddit-performance/{account_id}")
async def get_subreddit_performance(
    account_id: int,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get subreddit performance analysis for an account
    
    Args:
        account_id: Account to analyze
        days: Number of days to analyze
        
    Returns:
        List of subreddit performance metrics
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get subreddit performance
        metrics = targeting_service.analyze_subreddit_performance(account_id, days)
        
        # Convert to response format
        response_metrics = []
        for metric in metrics:
            response_metrics.append(SubredditMetricsResponse(
                subreddit=metric.subreddit,
                total_actions=metric.total_actions,
                successful_actions=metric.successful_actions,
                success_rate=metric.success_rate,
                avg_karma_gain=metric.avg_karma_gain,
                avg_response_time=metric.avg_response_time,
                engagement_rate=metric.engagement_rate,
                risk_score=metric.risk_score,
                recommendation=metric.recommendation
            ))
        
        return {
            "account_id": account_id,
            "analysis_period_days": days,
            "total_subreddits": len(response_metrics),
            "metrics": response_metrics
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting subreddit performance: {e}")
        raise HTTPException(status_code=500, detail="Failed to get subreddit performance")

@router.get("/keyword-analysis/{account_id}")
async def get_keyword_analysis(
    account_id: int,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get keyword performance analysis for an account
    
    Args:
        account_id: Account to analyze
        days: Number of days to analyze
        
    Returns:
        List of keyword performance analysis
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get keyword analysis
        analyses = targeting_service.analyze_keyword_performance(account_id, days)
        
        # Convert to response format
        response_analyses = []
        for analysis in analyses:
            response_analyses.append(KeywordAnalysisResponse(
                keyword=analysis.keyword,
                frequency=analysis.frequency,
                success_rate=analysis.success_rate,
                avg_karma=analysis.avg_karma,
                sentiment_score=analysis.sentiment_score,
                relevance_score=analysis.relevance_score,
                recommendation=analysis.recommendation
            ))
        
        return {
            "account_id": account_id,
            "analysis_period_days": days,
            "total_keywords": len(response_analyses),
            "analyses": response_analyses
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting keyword analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to get keyword analysis")

@router.get("/recommendations/{account_id}")
async def get_targeting_recommendations(
    account_id: int,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get intelligent targeting recommendations for an account
    
    Args:
        account_id: Account to analyze
        days: Number of days to analyze
        
    Returns:
        List of targeting recommendations
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get targeting recommendations
        recommendations = targeting_service.get_targeting_recommendations(account_id, days)
        
        # Convert to response format
        response_recommendations = []
        for rec in recommendations:
            response_recommendations.append(TargetingRecommendationResponse(
                subreddit=rec.subreddit,
                confidence=rec.confidence,
                reasons=rec.reasons,
                optimal_times=rec.optimal_times,
                suggested_keywords=rec.suggested_keywords,
                risk_level=rec.risk_level
            ))
        
        return {
            "account_id": account_id,
            "analysis_period_days": days,
            "total_recommendations": len(response_recommendations),
            "recommendations": response_recommendations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting targeting recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get targeting recommendations")

@router.get("/blocklist-recommendations/{account_id}")
async def get_blocklist_recommendations(
    account_id: int,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get blocklist recommendations for an account
    
    Args:
        account_id: Account to analyze
        days: Number of days to analyze
        
    Returns:
        Blocklist recommendations with reasons
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get blocklist recommendations
        recommendations = targeting_service.create_blocklist_recommendations(account_id, days)
        
        if 'error' in recommendations:
            raise HTTPException(status_code=500, detail=recommendations['error'])
        
        return {
            "account_id": account_id,
            "analysis_period_days": days,
            **recommendations
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting blocklist recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get blocklist recommendations")

@router.post("/apply-recommendations")
async def apply_targeting_recommendations(
    account_id: int,
    auto_apply: bool = Query(False, description="Automatically apply recommendations"),
    db: Session = Depends(get_db)
):
    """
    Apply targeting recommendations to account automation settings
    
    Args:
        account_id: Account to update
        auto_apply: Whether to automatically apply recommendations
        
    Returns:
        Application results
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        if not auto_apply:
            return {
                "message": "Set auto_apply=true to apply recommendations",
                "account_id": account_id
            }
        
        # Get recommendations
        recommendations = targeting_service.get_targeting_recommendations(account_id, 30)
        
        if not recommendations:
            return {
                "message": "No recommendations available",
                "account_id": account_id
            }
        
        # Apply recommendations
        result = targeting_service.update_automation_targeting(account_id, recommendations)
        
        if not result.get('success'):
            raise HTTPException(status_code=500, detail=result.get('error', 'Failed to apply recommendations'))
        
        return {
            "success": True,
            "message": "Targeting recommendations applied successfully",
            "account_id": account_id,
            "application_results": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying targeting recommendations: {e}")
        raise HTTPException(status_code=500, detail="Failed to apply targeting recommendations")

@router.post("/update-targeting")
async def update_targeting_settings(
    request: TargetingUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Manually update targeting settings for an account
    
    Args:
        request: Targeting update request
        
    Returns:
        Update results
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get or create automation settings
        settings = account.automation_settings
        if not settings:
            settings = AutomationSettings(account_id=request.account_id)
            db.add(settings)
        
        # Update settings
        settings.selected_subreddits = request.selected_subreddits
        settings.active_keywords = request.active_keywords
        settings.engagement_schedule = request.engagement_schedule
        
        db.commit()
        
        return {
            "success": True,
            "message": "Targeting settings updated successfully",
            "account_id": request.account_id,
            "updated_subreddits": len(request.selected_subreddits),
            "updated_keywords": len(request.active_keywords),
            "schedule_entries": len(request.engagement_schedule)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating targeting settings: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update targeting settings")

@router.get("/current-settings/{account_id}")
async def get_current_targeting_settings(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current targeting settings for an account
    
    Args:
        account_id: Account to check
        
    Returns:
        Current targeting settings
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get automation settings
        settings = account.automation_settings
        
        if not settings:
            return {
                "account_id": account_id,
                "username": account.reddit_username,
                "has_settings": False,
                "message": "No targeting settings configured"
            }
        
        return {
            "account_id": account_id,
            "username": account.reddit_username,
            "has_settings": True,
            "settings": {
                "selected_subreddits": settings.selected_subreddits or [],
                "active_keywords": settings.active_keywords or [],
                "engagement_schedule": settings.engagement_schedule or {},
                "max_daily_comments": settings.max_daily_comments,
                "max_daily_upvotes": settings.max_daily_upvotes,
                "automation_enabled": {
                    "upvote": settings.auto_upvote_enabled,
                    "comment": settings.auto_comment_enabled,
                    "post": settings.auto_post_enabled
                }
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting targeting settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get targeting settings")
