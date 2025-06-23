"""
Human Behavior Simulation API endpoints for Reddit automation dashboard
Provides sophisticated behavior patterns, scheduling, and activity simulation
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from database import get_db
from models import RedditAccount, AutomationSettings
from behavior_simulation import (
    behavior_simulator, ActivityType, UserPersonality, 
    ActivitySession, BehaviorPattern
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class ActivitySessionResponse(BaseModel):
    start_time: str
    duration_minutes: int
    activity_types: List[str]
    intensity: float
    break_probability: float
    personality_type: str

class BehaviorPatternResponse(BaseModel):
    personality: str
    daily_sessions: int
    session_duration_range: List[int]
    preferred_hours: List[int]
    activity_distribution: Dict[str, float]
    break_frequency: float
    weekend_modifier: float

class DelayCalculationRequest(BaseModel):
    action_type: str
    previous_action: Optional[str] = None
    account_id: Optional[int] = None

class ActivityProbabilityRequest(BaseModel):
    account_id: int
    action_type: str
    target_time: Optional[str] = None

class PersonalityUpdateRequest(BaseModel):
    account_id: int
    personality_type: str

class BehaviorAdaptationRequest(BaseModel):
    account_id: int
    recent_performance: Dict[str, Any]

@router.get("/personality-types")
async def get_personality_types():
    """
    Get available personality types and their characteristics
    
    Returns:
        List of personality types with descriptions
    """
    personalities = {
        "casual": {
            "name": "Casual User",
            "description": "Sporadic activity with longer breaks between sessions",
            "characteristics": [
                "2 sessions per day on average",
                "5-20 minute sessions",
                "Prefers lunch and evening hours",
                "More active on weekends",
                "Mostly browsing and upvoting"
            ]
        },
        "active": {
            "name": "Active User",
            "description": "Regular, consistent activity patterns",
            "characteristics": [
                "4 sessions per day on average",
                "10-45 minute sessions",
                "Active during work breaks and evenings",
                "Balanced activity distribution",
                "Good engagement rates"
            ]
        },
        "power_user": {
            "name": "Power User",
            "description": "High activity with multiple daily sessions",
            "characteristics": [
                "6+ sessions per day",
                "20-90 minute sessions",
                "Active throughout the day",
                "High comment and post frequency",
                "Sophisticated engagement patterns"
            ]
        },
        "lurker": {
            "name": "Lurker",
            "description": "Mostly browsing with minimal posting",
            "characteristics": [
                "3 sessions per day on average",
                "15-60 minute sessions",
                "Prefers evening hours",
                "Mostly browsing and occasional upvotes",
                "Rare comments and posts"
            ]
        }
    }
    
    return {
        "personality_types": personalities,
        "total_types": len(personalities)
    }

@router.get("/behavior-pattern/{account_id}")
async def get_account_behavior_pattern(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Get the current behavior pattern for an account
    
    Args:
        account_id: Account to analyze
        
    Returns:
        Current behavior pattern configuration
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get personality type
        personality = behavior_simulator._get_account_personality(account_id)
        pattern = behavior_simulator.behavior_patterns[personality]
        
        return BehaviorPatternResponse(
            personality=pattern.personality.value,
            daily_sessions=pattern.daily_sessions,
            session_duration_range=[pattern.session_duration_range[0], pattern.session_duration_range[1]],
            preferred_hours=pattern.preferred_hours,
            activity_distribution={k.value: v for k, v in pattern.activity_distribution.items()},
            break_frequency=pattern.break_frequency,
            weekend_modifier=pattern.weekend_modifier
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting behavior pattern: {e}")
        raise HTTPException(status_code=500, detail="Failed to get behavior pattern")

@router.post("/calculate-delay")
async def calculate_realistic_delay(request: DelayCalculationRequest):
    """
    Calculate realistic delay for an action based on human behavior
    
    Args:
        request: Delay calculation parameters
        
    Returns:
        Calculated delay in seconds with explanation
    """
    try:
        # Convert string action types to enum
        action_type = ActivityType(request.action_type)
        previous_action = ActivityType(request.previous_action) if request.previous_action else None
        
        # Calculate delay
        delay = behavior_simulator.generate_realistic_delay(action_type, previous_action)
        
        # Provide explanation
        explanation = f"Calculated delay for {action_type.value}"
        if previous_action:
            explanation += f" after {previous_action.value}"
        
        return {
            "delay_seconds": delay,
            "delay_minutes": round(delay / 60, 2),
            "action_type": request.action_type,
            "previous_action": request.previous_action,
            "explanation": explanation
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid action type: {e}")
    except Exception as e:
        logger.error(f"Error calculating delay: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate delay")

@router.post("/activity-probability")
async def calculate_activity_probability(
    request: ActivityProbabilityRequest,
    db: Session = Depends(get_db)
):
    """
    Calculate probability of performing an action at a specific time
    
    Args:
        request: Activity probability parameters
        
    Returns:
        Probability score and influencing factors
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Parse target time
        target_time = datetime.fromisoformat(request.target_time) if request.target_time else datetime.utcnow()
        
        # Convert action type
        action_type = ActivityType(request.action_type)
        
        # Calculate probability
        probability = behavior_simulator.calculate_activity_probability(
            request.account_id, action_type, target_time
        )
        
        # Get personality for context
        personality = behavior_simulator._get_account_personality(request.account_id)
        
        return {
            "account_id": request.account_id,
            "action_type": request.action_type,
            "target_time": target_time.isoformat(),
            "probability": probability,
            "probability_percentage": f"{probability * 100:.1f}%",
            "recommendation": "High" if probability > 0.7 else "Medium" if probability > 0.4 else "Low",
            "personality_type": personality.value,
            "factors": {
                "time_of_day": target_time.hour,
                "is_weekend": target_time.weekday() >= 5,
                "personality_influence": personality.value
            }
        }
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameters: {e}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating activity probability: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate activity probability")

@router.get("/schedule/{account_id}")
async def generate_activity_schedule(
    account_id: int,
    days: int = Query(7, description="Number of days to schedule"),
    db: Session = Depends(get_db)
):
    """
    Generate realistic activity schedule for an account
    
    Args:
        account_id: Account to schedule for
        days: Number of days to generate schedule for
        
    Returns:
        Generated activity schedule
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Generate schedule
        schedule = behavior_simulator.generate_activity_schedule(account_id, days)
        
        # Convert to response format
        schedule_response = []
        for session in schedule:
            schedule_response.append(ActivitySessionResponse(
                start_time=session.start_time.isoformat(),
                duration_minutes=session.duration_minutes,
                activity_types=[at.value for at in session.activity_types],
                intensity=session.intensity,
                break_probability=session.break_probability,
                personality_type=session.personality_type.value
            ))
        
        # Calculate summary statistics
        total_sessions = len(schedule)
        total_duration = sum(s.duration_minutes for s in schedule)
        avg_session_duration = total_duration / total_sessions if total_sessions > 0 else 0
        
        return {
            "account_id": account_id,
            "schedule_days": days,
            "total_sessions": total_sessions,
            "total_duration_minutes": total_duration,
            "average_session_duration": round(avg_session_duration, 1),
            "sessions_per_day": round(total_sessions / days, 1),
            "schedule": schedule_response
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating activity schedule: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate activity schedule")

@router.post("/update-personality")
async def update_account_personality(
    request: PersonalityUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update personality type for an account
    
    Args:
        request: Personality update request
        
    Returns:
        Update confirmation and new behavior pattern
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Validate personality type
        try:
            personality = UserPersonality(request.personality_type)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid personality type")
        
        # Get or create automation settings
        settings = account.automation_settings
        if not settings:
            settings = AutomationSettings(account_id=request.account_id)
            db.add(settings)
        
        # Update personality type (add field if not exists)
        if not hasattr(settings, 'personality_type'):
            # This would require a database migration in production
            pass
        
        # For now, we'll store it in a JSON field or handle it differently
        # settings.personality_type = request.personality_type
        
        db.commit()
        
        # Get new behavior pattern
        pattern = behavior_simulator.behavior_patterns[personality]
        
        return {
            "success": True,
            "account_id": request.account_id,
            "old_personality": "unknown",  # Would need to track previous
            "new_personality": request.personality_type,
            "new_pattern": {
                "daily_sessions": pattern.daily_sessions,
                "session_duration_range": pattern.session_duration_range,
                "preferred_hours": pattern.preferred_hours,
                "weekend_modifier": pattern.weekend_modifier
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating personality: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update personality")

@router.get("/momentum/{account_id}")
async def get_engagement_momentum(
    account_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current engagement momentum for an account
    
    Args:
        account_id: Account to analyze
        
    Returns:
        Engagement momentum score and analysis
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Calculate momentum
        momentum = behavior_simulator.calculate_engagement_momentum(account_id)
        
        # Interpret momentum
        if momentum > 1.5:
            interpretation = "Very High - Account is in active engagement flow"
        elif momentum > 1.0:
            interpretation = "High - Good engagement momentum"
        elif momentum > 0.7:
            interpretation = "Medium - Moderate engagement level"
        elif momentum > 0.4:
            interpretation = "Low - Limited recent engagement"
        else:
            interpretation = "Very Low - Account appears inactive"
        
        return {
            "account_id": account_id,
            "momentum_score": momentum,
            "momentum_level": interpretation,
            "recommendations": [
                "Continue current activity pattern" if momentum > 1.0 else "Consider increasing engagement",
                "Monitor for fatigue signs" if momentum > 1.5 else "Good opportunity for activity",
                "Maintain natural breaks" if momentum > 1.0 else "Focus on quality over quantity"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting engagement momentum: {e}")
        raise HTTPException(status_code=500, detail="Failed to get engagement momentum")

@router.post("/adapt-behavior")
async def adapt_behavior_pattern(
    request: BehaviorAdaptationRequest,
    db: Session = Depends(get_db)
):
    """
    Adapt behavior pattern based on recent performance feedback
    
    Args:
        request: Behavior adaptation request with performance data
        
    Returns:
        Behavior adaptation recommendations
    """
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == request.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")
        
        # Get adaptation recommendations
        adaptations = behavior_simulator.adapt_behavior_based_on_feedback(
            request.account_id, request.recent_performance
        )
        
        return {
            "account_id": request.account_id,
            "adaptation_confidence": adaptations["confidence"],
            "recommendations": {
                "timing": adaptations["timing_adjustments"],
                "activity": adaptations["activity_adjustments"],
                "risk_management": adaptations["risk_adjustments"]
            },
            "performance_summary": request.recent_performance,
            "next_steps": [
                "Implement timing adjustments gradually",
                "Monitor performance for 24-48 hours",
                "Adjust based on results"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adapting behavior: {e}")
        raise HTTPException(status_code=500, detail="Failed to adapt behavior pattern")
