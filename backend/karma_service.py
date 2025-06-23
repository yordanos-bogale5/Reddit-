"""
Karma tracking and logging service for Reddit Dashboard
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc

from database import SessionLocal
from models import RedditAccount, KarmaLog, SubredditPerformance
from reddit_service import reddit_service

logger = logging.getLogger(__name__)

class KarmaService:
    def __init__(self):
        pass
    
    def log_karma_snapshot(self, account_id: int) -> bool:
        """Take a karma snapshot for an account and store it in the database"""
        try:
            db = SessionLocal()
            
            # Get the Reddit account
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if not account:
                logger.error(f"Account {account_id} not found")
                return False
            
            # Get detailed karma from Reddit
            karma_data = reddit_service.get_detailed_karma(account.refresh_token)
            
            # Create karma log entry
            karma_log = KarmaLog(
                account_id=account_id,
                timestamp=datetime.utcnow(),
                total_karma=karma_data["total_karma"],
                post_karma=karma_data["post_karma"],
                comment_karma=karma_data["comment_karma"],
                by_subreddit=karma_data["by_subreddit"],
                by_content_type=karma_data["by_content_type"]
            )
            
            db.add(karma_log)
            db.commit()
            
            logger.info(f"Karma snapshot logged for account {account_id}: {karma_data['total_karma']} total karma")
            
            # Update subreddit performance data
            self._update_subreddit_performance(db, account_id, karma_data["by_subreddit"])
            
            db.close()
            return True
            
        except Exception as e:
            logger.error(f"Error logging karma snapshot for account {account_id}: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return False
    
    def get_karma_history(self, account_id: int, days: int = 30) -> List[Dict[str, Any]]:
        """Get karma history for an account over the specified number of days"""
        try:
            db = SessionLocal()
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            # Query karma logs
            karma_logs = db.query(KarmaLog).filter(
                KarmaLog.account_id == account_id,
                KarmaLog.timestamp >= start_date,
                KarmaLog.timestamp <= end_date
            ).order_by(KarmaLog.timestamp).all()
            
            # Convert to list of dictionaries
            history = []
            for log in karma_logs:
                history.append({
                    "timestamp": log.timestamp.isoformat(),
                    "total_karma": log.total_karma,
                    "post_karma": log.post_karma,
                    "comment_karma": log.comment_karma,
                    "by_subreddit": log.by_subreddit,
                    "by_content_type": log.by_content_type
                })
            
            db.close()
            return history
            
        except Exception as e:
            logger.error(f"Error getting karma history for account {account_id}: {e}")
            if 'db' in locals():
                db.close()
            return []
    
    def get_karma_growth_stats(self, account_id: int, days: int = 30) -> Dict[str, Any]:
        """Calculate karma growth statistics for an account"""
        try:
            db = SessionLocal()
            
            # Get recent karma logs
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            karma_logs = db.query(KarmaLog).filter(
                KarmaLog.account_id == account_id,
                KarmaLog.timestamp >= start_date
            ).order_by(KarmaLog.timestamp).all()
            
            if len(karma_logs) < 2:
                db.close()
                return {
                    "total_growth": 0,
                    "post_growth": 0,
                    "comment_growth": 0,
                    "daily_average": 0,
                    "growth_rate": 0,
                    "period_days": days
                }
            
            # Calculate growth
            first_log = karma_logs[0]
            last_log = karma_logs[-1]
            
            total_growth = last_log.total_karma - first_log.total_karma
            post_growth = last_log.post_karma - first_log.post_karma
            comment_growth = last_log.comment_karma - first_log.comment_karma
            
            # Calculate daily average
            actual_days = (last_log.timestamp - first_log.timestamp).days
            if actual_days == 0:
                actual_days = 1
            
            daily_average = total_growth / actual_days
            
            # Calculate growth rate (percentage)
            growth_rate = 0
            if first_log.total_karma > 0:
                growth_rate = (total_growth / first_log.total_karma) * 100
            
            db.close()
            
            return {
                "total_growth": total_growth,
                "post_growth": post_growth,
                "comment_growth": comment_growth,
                "daily_average": round(daily_average, 2),
                "growth_rate": round(growth_rate, 2),
                "period_days": actual_days,
                "start_karma": first_log.total_karma,
                "end_karma": last_log.total_karma
            }
            
        except Exception as e:
            logger.error(f"Error calculating karma growth stats for account {account_id}: {e}")
            if 'db' in locals():
                db.close()
            return {}
    
    def get_top_subreddits_by_karma(self, account_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top subreddits by karma for an account"""
        try:
            db = SessionLocal()
            
            # Get the most recent karma log
            latest_log = db.query(KarmaLog).filter(
                KarmaLog.account_id == account_id
            ).order_by(desc(KarmaLog.timestamp)).first()
            
            if not latest_log or not latest_log.by_subreddit:
                db.close()
                return []
            
            # Sort subreddits by total karma
            subreddit_data = []
            for subreddit, karma_data in latest_log.by_subreddit.items():
                total_karma = karma_data.get("post_karma", 0) + karma_data.get("comment_karma", 0)
                subreddit_data.append({
                    "subreddit": subreddit,
                    "total_karma": total_karma,
                    "post_karma": karma_data.get("post_karma", 0),
                    "comment_karma": karma_data.get("comment_karma", 0)
                })
            
            # Sort by total karma and limit results
            subreddit_data.sort(key=lambda x: x["total_karma"], reverse=True)
            
            db.close()
            return subreddit_data[:limit]
            
        except Exception as e:
            logger.error(f"Error getting top subreddits for account {account_id}: {e}")
            if 'db' in locals():
                db.close()
            return []
    
    def _update_subreddit_performance(self, db: Session, account_id: int, subreddit_karma: Dict[str, Any]):
        """Update subreddit performance data"""
        try:
            for subreddit, karma_data in subreddit_karma.items():
                total_karma = karma_data.get("post_karma", 0) + karma_data.get("comment_karma", 0)
                
                # Check if performance record exists
                performance = db.query(SubredditPerformance).filter(
                    SubredditPerformance.account_id == account_id,
                    SubredditPerformance.subreddit == subreddit
                ).first()
                
                if performance:
                    # Update existing record
                    performance.karma_gain = total_karma
                    performance.engagement_score = self._calculate_engagement_score(karma_data)
                else:
                    # Create new record
                    performance = SubredditPerformance(
                        account_id=account_id,
                        subreddit=subreddit,
                        karma_gain=total_karma,
                        engagement_score=self._calculate_engagement_score(karma_data),
                        removed_count=0,
                        ignored_count=0
                    )
                    db.add(performance)
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error updating subreddit performance: {e}")
            db.rollback()
    
    def _calculate_engagement_score(self, karma_data: Dict[str, Any]) -> float:
        """Calculate engagement score based on karma data"""
        post_karma = karma_data.get("post_karma", 0)
        comment_karma = karma_data.get("comment_karma", 0)
        
        # Simple engagement score calculation
        # Could be enhanced with more sophisticated metrics
        total_karma = post_karma + comment_karma
        
        if total_karma <= 0:
            return 0.0
        
        # Weight comments slightly higher as they indicate more engagement
        score = (post_karma * 1.0 + comment_karma * 1.2) / total_karma
        return round(score, 2)

karma_service = KarmaService()
