from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import logging

from database import get_db
from models import RedditAccount, AutomationSettings, ActivityLog
from engagement_service import engagement_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Pydantic models for request/response
class AutomationSettingsUpdate(BaseModel):
    selected_subreddits: Optional[List[str]] = None
    active_keywords: Optional[List[str]] = None
    engagement_schedule: Optional[Dict[str, Any]] = None
    max_daily_comments: Optional[int] = None
    max_daily_upvotes: Optional[int] = None
    auto_upvote_enabled: Optional[bool] = None
    auto_comment_enabled: Optional[bool] = None
    auto_post_enabled: Optional[bool] = None

class AutomationTaskCreate(BaseModel):
    account_id: int
    task_type: str  # "upvote", "comment", "post"
    target_id: Optional[str] = None
    subreddit: str
    content: Optional[str] = None
    schedule_time: Optional[str] = None

@router.get("/settings/{account_id}", summary="Get automation settings")
def get_automation_settings(account_id: int, db: Session = Depends(get_db)):
    """Get automation settings for an account"""
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Get automation settings
        settings = account.automation_settings
        if not settings:
            # Create default settings if none exist
            settings = AutomationSettings(
                account_id=account_id,
                selected_subreddits=[],
                active_keywords=[],
                engagement_schedule={},
                max_daily_comments=10,
                max_daily_upvotes=50,
                auto_upvote_enabled=False,
                auto_comment_enabled=False,
                auto_post_enabled=False
            )
            db.add(settings)
            db.commit()
            db.refresh(settings)

        return {
            "account_id": account_id,
            "selected_subreddits": settings.selected_subreddits,
            "active_keywords": settings.active_keywords,
            "engagement_schedule": settings.engagement_schedule,
            "max_daily_comments": settings.max_daily_comments,
            "max_daily_upvotes": settings.max_daily_upvotes,
            "auto_upvote_enabled": getattr(settings, 'auto_upvote_enabled', False),
            "auto_comment_enabled": getattr(settings, 'auto_comment_enabled', False),
            "auto_post_enabled": getattr(settings, 'auto_post_enabled', False)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting automation settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get automation settings")

@router.put("/settings/{account_id}", summary="Update automation settings")
def update_automation_settings(
    account_id: int,
    settings_update: AutomationSettingsUpdate,
    db: Session = Depends(get_db)
):
    """Update automation settings for an account"""
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Get or create automation settings
        settings = account.automation_settings
        if not settings:
            settings = AutomationSettings(account_id=account_id)
            db.add(settings)

        # Update settings with provided values
        update_data = settings_update.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(settings, field, value)

        db.commit()

        # Log the settings update
        activity_log = ActivityLog(
            account_id=account_id,
            action="automation_settings_updated",
            details=update_data
        )
        db.add(activity_log)
        db.commit()

        return {
            "message": "Automation settings updated successfully",
            "account_id": account_id,
            "updated_fields": list(update_data.keys())
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating automation settings: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to update automation settings")

@router.get("/status/{account_id}", summary="Get automation status")
def get_automation_status(account_id: int, db: Session = Depends(get_db)):
    """Get current automation status and recent activity for an account"""
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Get automation settings
        settings = account.automation_settings

        # Get recent engagement stats (last 24 hours)
        from datetime import datetime, timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)

        recent_engagements = db.query(ActivityLog).filter(
            ActivityLog.account_id == account_id,
            ActivityLog.timestamp >= yesterday
        ).count()

        # Get engagement stats for today
        today_stats = engagement_service.get_engagement_stats(account_id, days=1)

        # Calculate automation status
        automation_active = False
        if settings:
            automation_active = (
                getattr(settings, 'auto_upvote_enabled', False) or
                getattr(settings, 'auto_comment_enabled', False) or
                getattr(settings, 'auto_post_enabled', False)
            )

        return {
            "account_id": account_id,
            "automation_active": automation_active,
            "settings_configured": settings is not None,
            "recent_activity": {
                "total_actions_24h": recent_engagements,
                "today_stats": today_stats
            },
            "limits": {
                "max_daily_comments": settings.max_daily_comments if settings else 0,
                "max_daily_upvotes": settings.max_daily_upvotes if settings else 0,
                "comments_used_today": today_stats.get("by_action_type", {}).get("comment", 0),
                "upvotes_used_today": today_stats.get("by_action_type", {}).get("upvote", 0)
            } if settings else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting automation status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get automation status")

@router.post("/task/manual", summary="Execute manual automation task")
def execute_manual_task(task: AutomationTaskCreate, db: Session = Depends(get_db)):
    """Execute a manual automation task (upvote, comment, post)"""
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == task.account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Execute the task based on type
        if task.task_type == "upvote":
            if not task.target_id:
                raise HTTPException(status_code=400, detail="target_id required for upvote task")

            success = engagement_service.log_upvote(
                account_id=task.account_id,
                post_or_comment_id=task.target_id,
                subreddit=task.subreddit,
                success=True  # For manual tasks, assume success for demo
            )

            return {
                "message": f"Manual upvote task executed",
                "task_type": task.task_type,
                "target_id": task.target_id,
                "subreddit": task.subreddit,
                "success": success
            }

        elif task.task_type == "comment":
            if not task.target_id or not task.content:
                raise HTTPException(status_code=400, detail="target_id and content required for comment task")

            success = engagement_service.log_comment(
                account_id=task.account_id,
                parent_id=task.target_id,
                subreddit=task.subreddit,
                comment_text=task.content,
                success=True  # For manual tasks, assume success for demo
            )

            return {
                "message": f"Manual comment task executed",
                "task_type": task.task_type,
                "target_id": task.target_id,
                "subreddit": task.subreddit,
                "content": task.content[:50] + "..." if len(task.content) > 50 else task.content,
                "success": success
            }

        elif task.task_type == "post":
            if not task.content:
                raise HTTPException(status_code=400, detail="content required for post task")

            # Generate a dummy post ID for demo
            import uuid
            post_id = str(uuid.uuid4())[:8]

            success = engagement_service.log_post(
                account_id=task.account_id,
                post_id=post_id,
                subreddit=task.subreddit,
                title=task.content,
                success=True  # For manual tasks, assume success for demo
            )

            return {
                "message": f"Manual post task executed",
                "task_type": task.task_type,
                "post_id": post_id,
                "subreddit": task.subreddit,
                "title": task.content[:50] + "..." if len(task.content) > 50 else task.content,
                "success": success
            }

        else:
            raise HTTPException(status_code=400, detail="Invalid task_type. Must be 'upvote', 'comment', or 'post'")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing manual task: {e}")
        raise HTTPException(status_code=500, detail="Failed to execute manual task")

@router.get("/activity/{account_id}", summary="Get recent automation activity")
def get_automation_activity(
    account_id: int,
    days: int = Query(7, description="Number of days to look back"),
    db: Session = Depends(get_db)
):
    """Get recent automation activity for an account"""
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Get recent activity logs
        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        activity_logs = db.query(ActivityLog).filter(
            ActivityLog.account_id == account_id,
            ActivityLog.timestamp >= start_date
        ).order_by(ActivityLog.timestamp.desc()).limit(100).all()

        # Get engagement history
        engagement_history = engagement_service.get_engagement_history(account_id, days=days)

        # Format activity logs
        formatted_logs = []
        for log in activity_logs:
            formatted_logs.append({
                "id": log.id,
                "timestamp": log.timestamp.isoformat(),
                "action": log.action,
                "details": log.details
            })

        return {
            "account_id": account_id,
            "period_days": days,
            "activity_logs": formatted_logs,
            "engagement_history": engagement_history,
            "total_activities": len(formatted_logs),
            "total_engagements": len(engagement_history)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting automation activity: {e}")
        raise HTTPException(status_code=500, detail="Failed to get automation activity")

@router.post("/toggle/{account_id}", summary="Toggle automation on/off")
def toggle_automation(
    account_id: int,
    automation_type: str = Query(..., description="Type of automation: 'upvote', 'comment', 'post', or 'all'"),
    enabled: bool = Query(..., description="Enable or disable automation"),
    db: Session = Depends(get_db)
):
    """Toggle automation on or off for an account"""
    try:
        # Verify account exists
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        # Get or create automation settings
        settings = account.automation_settings
        if not settings:
            settings = AutomationSettings(account_id=account_id)
            db.add(settings)

        # Update the appropriate automation setting
        if automation_type == "upvote":
            settings.auto_upvote_enabled = enabled
        elif automation_type == "comment":
            settings.auto_comment_enabled = enabled
        elif automation_type == "post":
            settings.auto_post_enabled = enabled
        elif automation_type == "all":
            settings.auto_upvote_enabled = enabled
            settings.auto_comment_enabled = enabled
            settings.auto_post_enabled = enabled
        else:
            raise HTTPException(status_code=400, detail="Invalid automation_type")

        db.commit()

        # Log the toggle action
        activity_log = ActivityLog(
            account_id=account_id,
            action=f"automation_toggled",
            details={
                "automation_type": automation_type,
                "enabled": enabled,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        db.add(activity_log)
        db.commit()

        return {
            "message": f"Automation {automation_type} {'enabled' if enabled else 'disabled'}",
            "account_id": account_id,
            "automation_type": automation_type,
            "enabled": enabled
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling automation: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to toggle automation")