"""
NLP API endpoints for Reddit automation dashboard
Provides comment quality analysis, sentiment analysis, and content moderation
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import logging

from database import get_db
from models import RedditAccount, EngagementLog, ActivityLog
from nlp_service import nlp_service, CommentQualityScore, SentimentAnalysis

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class CommentAnalysisRequest(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None

class CommentQualityResponse(BaseModel):
    overall_score: float
    sentiment_score: float
    spam_probability: float
    readability_score: float
    relevance_score: float
    toxicity_score: float
    language: str
    word_count: int
    issues: List[str]
    recommendations: List[str]

class SentimentResponse(BaseModel):
    compound: float
    positive: float
    negative: float
    neutral: float
    confidence: float

class BatchAnalysisRequest(BaseModel):
    comments: List[Dict[str, Any]]  # Each dict should have 'text' and optional 'context'

class BatchAnalysisResponse(BaseModel):
    results: List[CommentQualityResponse]
    summary: Dict[str, Any]

class QualityFilterRequest(BaseModel):
    account_id: int
    min_quality_score: float = 70.0
    max_spam_probability: float = 0.3
    max_toxicity_score: float = 0.2

@router.post("/analyze/comment", response_model=CommentQualityResponse)
async def analyze_comment_quality(request: CommentAnalysisRequest):
    """
    Analyze the quality of a single comment
    
    Args:
        request: Comment text and optional context
        
    Returns:
        Detailed quality analysis including scores and recommendations
    """
    try:
        result = nlp_service.analyze_comment_quality(request.text, request.context)
        
        return CommentQualityResponse(
            overall_score=result.overall_score,
            sentiment_score=result.sentiment_score,
            spam_probability=result.spam_probability,
            readability_score=result.readability_score,
            relevance_score=result.relevance_score,
            toxicity_score=result.toxicity_score,
            language=result.language,
            word_count=result.word_count,
            issues=result.issues,
            recommendations=result.recommendations
        )
        
    except Exception as e:
        logger.error(f"Error analyzing comment quality: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze comment quality")

@router.post("/analyze/sentiment", response_model=SentimentResponse)
async def analyze_sentiment(request: CommentAnalysisRequest):
    """
    Analyze sentiment of text
    
    Args:
        request: Text to analyze
        
    Returns:
        Detailed sentiment analysis
    """
    try:
        result = nlp_service.analyze_sentiment(request.text)
        
        return SentimentResponse(
            compound=result.compound,
            positive=result.positive,
            negative=result.negative,
            neutral=result.neutral,
            confidence=result.confidence
        )
        
    except Exception as e:
        logger.error(f"Error analyzing sentiment: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze sentiment")

@router.post("/analyze/spam")
async def detect_spam(request: CommentAnalysisRequest):
    """
    Detect spam probability in text
    
    Args:
        request: Text to analyze
        
    Returns:
        Spam probability and classification
    """
    try:
        spam_prob = nlp_service.detect_spam(request.text)
        
        return {
            "spam_probability": spam_prob,
            "is_spam": spam_prob > 0.7,
            "confidence": "high" if spam_prob > 0.8 or spam_prob < 0.2 else "medium",
            "text_length": len(request.text),
            "word_count": len(request.text.split())
        }
        
    except Exception as e:
        logger.error(f"Error detecting spam: {e}")
        raise HTTPException(status_code=500, detail="Failed to detect spam")

@router.post("/analyze/batch", response_model=BatchAnalysisResponse)
async def analyze_batch_comments(request: BatchAnalysisRequest):
    """
    Analyze multiple comments in batch
    
    Args:
        request: List of comments to analyze
        
    Returns:
        Analysis results for all comments plus summary statistics
    """
    try:
        results = []
        total_score = 0
        spam_count = 0
        toxic_count = 0
        
        for comment_data in request.comments:
            text = comment_data.get('text', '')
            context = comment_data.get('context')
            
            analysis = nlp_service.analyze_comment_quality(text, context)
            
            result = CommentQualityResponse(
                overall_score=analysis.overall_score,
                sentiment_score=analysis.sentiment_score,
                spam_probability=analysis.spam_probability,
                readability_score=analysis.readability_score,
                relevance_score=analysis.relevance_score,
                toxicity_score=analysis.toxicity_score,
                language=analysis.language,
                word_count=analysis.word_count,
                issues=analysis.issues,
                recommendations=analysis.recommendations
            )
            
            results.append(result)
            total_score += analysis.overall_score
            
            if analysis.spam_probability > 0.7:
                spam_count += 1
            if analysis.toxicity_score > 0.5:
                toxic_count += 1
        
        # Calculate summary statistics
        avg_score = total_score / len(results) if results else 0
        summary = {
            "total_comments": len(results),
            "average_quality_score": avg_score,
            "spam_detected": spam_count,
            "toxic_content_detected": toxic_count,
            "quality_distribution": {
                "high_quality": len([r for r in results if r.overall_score >= 80]),
                "medium_quality": len([r for r in results if 50 <= r.overall_score < 80]),
                "low_quality": len([r for r in results if r.overall_score < 50])
            }
        }
        
        return BatchAnalysisResponse(results=results, summary=summary)
        
    except Exception as e:
        logger.error(f"Error in batch analysis: {e}")
        raise HTTPException(status_code=500, detail="Failed to analyze comments in batch")

@router.get("/quality/filter/{account_id}")
async def filter_comments_by_quality(
    account_id: int,
    min_quality_score: float = Query(70.0, description="Minimum quality score"),
    max_spam_probability: float = Query(0.3, description="Maximum spam probability"),
    max_toxicity_score: float = Query(0.2, description="Maximum toxicity score"),
    days: int = Query(7, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """
    Filter account's recent comments by quality criteria
    
    Args:
        account_id: Account to analyze
        min_quality_score: Minimum overall quality score
        max_spam_probability: Maximum allowed spam probability
        max_toxicity_score: Maximum allowed toxicity score
        days: Number of days to analyze
        
    Returns:
        Filtered comments with quality analysis
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get recent engagement logs with comments
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        engagement_logs = db.query(EngagementLog).filter(
            EngagementLog.account_id == account_id,
            EngagementLog.timestamp >= cutoff_date,
            EngagementLog.action_type == 'comment',
            EngagementLog.content.isnot(None)
        ).all()
        
        filtered_comments = []
        quality_stats = {
            "total_analyzed": 0,
            "passed_filter": 0,
            "failed_quality": 0,
            "failed_spam": 0,
            "failed_toxicity": 0
        }
        
        for log in engagement_logs:
            if not log.content:
                continue
                
            # Analyze comment quality
            context = {
                "subreddit": log.subreddit,
                "post_id": log.target_id
            }
            
            analysis = nlp_service.analyze_comment_quality(log.content, context)
            quality_stats["total_analyzed"] += 1
            
            # Apply filters
            passes_filter = True
            failure_reasons = []
            
            if analysis.overall_score < min_quality_score:
                passes_filter = False
                failure_reasons.append("low_quality")
                quality_stats["failed_quality"] += 1
            
            if analysis.spam_probability > max_spam_probability:
                passes_filter = False
                failure_reasons.append("spam")
                quality_stats["failed_spam"] += 1
            
            if analysis.toxicity_score > max_toxicity_score:
                passes_filter = False
                failure_reasons.append("toxicity")
                quality_stats["failed_toxicity"] += 1
            
            if passes_filter:
                quality_stats["passed_filter"] += 1
            
            filtered_comments.append({
                "log_id": log.id,
                "timestamp": log.timestamp,
                "subreddit": log.subreddit,
                "content": log.content[:200] + "..." if len(log.content) > 200 else log.content,
                "passes_filter": passes_filter,
                "failure_reasons": failure_reasons,
                "quality_analysis": {
                    "overall_score": analysis.overall_score,
                    "sentiment_score": analysis.sentiment_score,
                    "spam_probability": analysis.spam_probability,
                    "toxicity_score": analysis.toxicity_score,
                    "issues": analysis.issues,
                    "recommendations": analysis.recommendations[:3]  # Limit recommendations
                }
            })
        
        return {
            "account_id": account_id,
            "filter_criteria": {
                "min_quality_score": min_quality_score,
                "max_spam_probability": max_spam_probability,
                "max_toxicity_score": max_toxicity_score
            },
            "statistics": quality_stats,
            "comments": filtered_comments
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error filtering comments by quality: {e}")
        raise HTTPException(status_code=500, detail="Failed to filter comments")

@router.get("/quality/trends/{account_id}")
async def get_quality_trends(
    account_id: int,
    days: int = Query(30, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """
    Get quality trends for an account's comments over time
    
    Args:
        account_id: Account to analyze
        days: Number of days to analyze
        
    Returns:
        Quality trends and statistics
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get recent comments
        from datetime import datetime, timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        engagement_logs = db.query(EngagementLog).filter(
            EngagementLog.account_id == account_id,
            EngagementLog.timestamp >= cutoff_date,
            EngagementLog.action_type == 'comment',
            EngagementLog.content.isnot(None)
        ).order_by(EngagementLog.timestamp).all()
        
        # Analyze trends
        daily_stats = {}
        overall_stats = {
            "total_comments": 0,
            "avg_quality_score": 0,
            "avg_sentiment": 0,
            "spam_rate": 0,
            "toxicity_rate": 0
        }
        
        total_quality = 0
        total_sentiment = 0
        spam_count = 0
        toxic_count = 0
        
        for log in engagement_logs:
            if not log.content:
                continue
            
            date_key = log.timestamp.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    "date": date_key,
                    "comment_count": 0,
                    "avg_quality": 0,
                    "avg_sentiment": 0,
                    "spam_count": 0,
                    "toxic_count": 0
                }
            
            # Analyze comment
            analysis = nlp_service.analyze_comment_quality(log.content)
            
            # Update daily stats
            daily_stats[date_key]["comment_count"] += 1
            daily_stats[date_key]["avg_quality"] += analysis.overall_score
            daily_stats[date_key]["avg_sentiment"] += analysis.sentiment_score
            
            if analysis.spam_probability > 0.7:
                daily_stats[date_key]["spam_count"] += 1
                spam_count += 1
            
            if analysis.toxicity_score > 0.5:
                daily_stats[date_key]["toxic_count"] += 1
                toxic_count += 1
            
            # Update overall stats
            overall_stats["total_comments"] += 1
            total_quality += analysis.overall_score
            total_sentiment += analysis.sentiment_score
        
        # Calculate averages for daily stats
        for date_key in daily_stats:
            day_data = daily_stats[date_key]
            if day_data["comment_count"] > 0:
                day_data["avg_quality"] /= day_data["comment_count"]
                day_data["avg_sentiment"] /= day_data["comment_count"]
        
        # Calculate overall averages
        if overall_stats["total_comments"] > 0:
            overall_stats["avg_quality_score"] = total_quality / overall_stats["total_comments"]
            overall_stats["avg_sentiment"] = total_sentiment / overall_stats["total_comments"]
            overall_stats["spam_rate"] = spam_count / overall_stats["total_comments"]
            overall_stats["toxicity_rate"] = toxic_count / overall_stats["total_comments"]
        
        return {
            "account_id": account_id,
            "period_days": days,
            "overall_statistics": overall_stats,
            "daily_trends": list(daily_stats.values()),
            "recommendations": _generate_trend_recommendations(overall_stats)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quality trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to get quality trends")

def _generate_trend_recommendations(stats: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on quality trends"""
    recommendations = []
    
    if stats["avg_quality_score"] < 60:
        recommendations.append("Focus on improving overall comment quality")
    
    if stats["spam_rate"] > 0.2:
        recommendations.append("Reduce promotional or repetitive content")
    
    if stats["toxicity_rate"] > 0.1:
        recommendations.append("Use more respectful and constructive language")
    
    if stats["avg_sentiment"] < -0.3:
        recommendations.append("Consider more balanced or positive perspectives")
    
    if not recommendations:
        recommendations.append("Comment quality trends look good!")
    
    return recommendations
