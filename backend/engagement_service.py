"""
Engagement logging and tracking service for Reddit Dashboard
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import SessionLocal
from models import RedditAccount, EngagementLog, ActivityLog
from reddit_service import reddit_service

logger = logging.getLogger(__name__)

class EngagementService:
    def __init__(self):
        pass
    
    def log_engagement(self, account_id: int, action_type: str, target_id: str, 
                      subreddit: str, status: str = "success", details: Dict[str, Any] = None) -> bool:
        """Log an engagement action (upvote, comment, post)"""
        try:
            db = SessionLocal()
            
            # Verify account exists
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if not account:
                logger.error(f"Account {account_id} not found")
                return False
            
            # Create engagement log entry
            engagement_log = EngagementLog(
                account_id=account_id,
                timestamp=datetime.utcnow(),
                action_type=action_type,
                target_id=target_id,
                subreddit=subreddit,
                status=status,
                details=details or {}
            )
            
            db.add(engagement_log)
            db.commit()
            
            logger.info(f"Engagement logged: {action_type} on {target_id} in r/{subreddit} - {status}")
            
            # Also log as activity
            self._log_activity(db, account_id, f"{action_type}_{status}", {
                "target_id": target_id,
                "subreddit": subreddit,
                "details": details
            })
            
            db.close()
            return True
            
        except Exception as e:
            logger.error(f"Error logging engagement: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return False
    
    def log_upvote(self, account_id: int, post_or_comment_id: str, subreddit: str, 
                   success: bool = True, error_message: str = None) -> bool:
        """Log an upvote action"""
        status = "success" if success else "failed"
        details = {"error_message": error_message} if error_message else {}
        
        return self.log_engagement(
            account_id=account_id,
            action_type="upvote",
            target_id=post_or_comment_id,
            subreddit=subreddit,
            status=status,
            details=details
        )
    
    def log_comment(self, account_id: int, parent_id: str, subreddit: str, 
                   comment_text: str, success: bool = True, error_message: str = None) -> bool:
        """Log a comment action"""
        status = "success" if success else "failed"
        details = {
            "comment_text": comment_text[:100] + "..." if len(comment_text) > 100 else comment_text,
            "comment_length": len(comment_text)
        }
        
        if error_message:
            details["error_message"] = error_message
        
        return self.log_engagement(
            account_id=account_id,
            action_type="comment",
            target_id=parent_id,
            subreddit=subreddit,
            status=status,
            details=details
        )
    
    def log_post(self, account_id: int, post_id: str, subreddit: str, 
                title: str, post_type: str = "text", success: bool = True, 
                error_message: str = None) -> bool:
        """Log a post action"""
        status = "success" if success else "failed"
        details = {
            "title": title[:100] + "..." if len(title) > 100 else title,
            "post_type": post_type
        }
        
        if error_message:
            details["error_message"] = error_message
        
        return self.log_engagement(
            account_id=account_id,
            action_type="post",
            target_id=post_id,
            subreddit=subreddit,
            status=status,
            details=details
        )
    
    def get_engagement_history(self, account_id: int, days: int = 30, 
                              action_type: str = None) -> List[Dict[str, Any]]:
        """Get engagement history for an account"""
        try:
            db = SessionLocal()
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Build query
            query = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= start_date,
                EngagementLog.timestamp <= end_date
            )
            
            # Filter by action type if specified
            if action_type:
                query = query.filter(EngagementLog.action_type == action_type)
            
            engagement_logs = query.order_by(desc(EngagementLog.timestamp)).all()
            
            # Convert to list of dictionaries
            history = []
            for log in engagement_logs:
                history.append({
                    "id": log.id,
                    "timestamp": log.timestamp.isoformat(),
                    "action_type": log.action_type,
                    "target_id": log.target_id,
                    "subreddit": log.subreddit,
                    "status": log.status,
                    "details": log.details
                })
            
            db.close()
            return history
            
        except Exception as e:
            logger.error(f"Error getting engagement history for account {account_id}: {e}")
            if 'db' in locals():
                db.close()
            return []
    
    def get_engagement_stats(self, account_id: int, days: int = 30) -> Dict[str, Any]:
        """Get engagement statistics for an account"""
        try:
            db = SessionLocal()
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get engagement logs
            engagement_logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= start_date
            ).all()
            
            # Initialize stats
            stats = {
                "total_actions": len(engagement_logs),
                "by_action_type": {"upvote": 0, "comment": 0, "post": 0},
                "by_status": {"success": 0, "failed": 0, "removed": 0},
                "by_subreddit": {},
                "success_rate": 0,
                "daily_average": 0,
                "most_active_subreddit": None,
                "period_days": days
            }
            
            # Analyze logs
            for log in engagement_logs:
                # Count by action type
                if log.action_type in stats["by_action_type"]:
                    stats["by_action_type"][log.action_type] += 1
                
                # Count by status
                if log.status in stats["by_status"]:
                    stats["by_status"][log.status] += 1
                
                # Count by subreddit
                if log.subreddit:
                    if log.subreddit not in stats["by_subreddit"]:
                        stats["by_subreddit"][log.subreddit] = 0
                    stats["by_subreddit"][log.subreddit] += 1
            
            # Calculate success rate
            if stats["total_actions"] > 0:
                success_count = stats["by_status"]["success"]
                stats["success_rate"] = round((success_count / stats["total_actions"]) * 100, 2)
                stats["daily_average"] = round(stats["total_actions"] / days, 2)
            
            # Find most active subreddit
            if stats["by_subreddit"]:
                stats["most_active_subreddit"] = max(stats["by_subreddit"], key=stats["by_subreddit"].get)
            
            db.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting engagement stats for account {account_id}: {e}")
            if 'db' in locals():
                db.close()
            return {}
    
    def get_subreddit_engagement_summary(self, account_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get engagement summary by subreddit"""
        try:
            db = SessionLocal()
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Get engagement logs
            engagement_logs = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= start_date
            ).all()
            
            # Group by subreddit
            subreddit_data = {}
            
            for log in engagement_logs:
                if not log.subreddit:
                    continue
                
                if log.subreddit not in subreddit_data:
                    subreddit_data[log.subreddit] = {
                        "subreddit": log.subreddit,
                        "total_actions": 0,
                        "upvotes": 0,
                        "comments": 0,
                        "posts": 0,
                        "success_count": 0,
                        "failed_count": 0,
                        "success_rate": 0
                    }
                
                data = subreddit_data[log.subreddit]
                data["total_actions"] += 1
                
                if log.action_type == "upvote":
                    data["upvotes"] += 1
                elif log.action_type == "comment":
                    data["comments"] += 1
                elif log.action_type == "post":
                    data["posts"] += 1
                
                if log.status == "success":
                    data["success_count"] += 1
                elif log.status == "failed":
                    data["failed_count"] += 1
            
            # Calculate success rates
            for data in subreddit_data.values():
                if data["total_actions"] > 0:
                    data["success_rate"] = round((data["success_count"] / data["total_actions"]) * 100, 2)
            
            # Convert to list and sort by total actions
            result = list(subreddit_data.values())
            result.sort(key=lambda x: x["total_actions"], reverse=True)
            
            db.close()
            return result
            
        except Exception as e:
            logger.error(f"Error getting subreddit engagement summary for account {account_id}: {e}")
            if 'db' in locals():
                db.close()
            return []
    
    def _log_activity(self, db: Session, account_id: int, action: str, details: Dict[str, Any]):
        """Log activity to activity log"""
        try:
            activity_log = ActivityLog(
                account_id=account_id,
                timestamp=datetime.utcnow(),
                action=action,
                details=details
            )
            
            db.add(activity_log)
            db.commit()
            
        except Exception as e:
            logger.error(f"Error logging activity: {e}")
            db.rollback()

engagement_service = EngagementService()
