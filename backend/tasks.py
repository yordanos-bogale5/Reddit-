import logging
import time
import random
from datetime import datetime
from typing import Dict, Any

from celery_worker import celery_app
from database import SessionLocal
from models import RedditAccount, AutomationSettings
from reddit_service import reddit_service
from engagement_service import engagement_service
from karma_service import karma_service

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def automate_upvote(self, account_id: int, target_id: str, subreddit: str):
    """Automate Reddit upvote with human-like behavior"""
    try:
        logger.info(f"Starting upvote automation for account {account_id}, target {target_id}")

        # Get account and settings
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            logger.error(f"Account {account_id} not found")
            return {"success": False, "error": "Account not found"}

        settings = account.automation_settings
        if not settings or not settings.auto_upvote_enabled:
            logger.warning(f"Upvote automation disabled for account {account_id}")
            return {"success": False, "error": "Upvote automation disabled"}

        # Add human-like delay
        delay = random.uniform(1, 5)  # 1-5 seconds
        time.sleep(delay)

        # Perform upvote using Reddit API
        result = reddit_service.upvote_content(account.refresh_token, target_id)

        # Log the engagement
        success = engagement_service.log_upvote(
            account_id=account_id,
            post_or_comment_id=target_id,
            subreddit=subreddit,
            success=result["success"],
            error_message=result.get("error")
        )

        db.close()

        if result["success"]:
            logger.info(f"Upvote automation successful for account {account_id}")
            return {"success": True, "target_id": target_id, "subreddit": subreddit}
        else:
            logger.error(f"Upvote automation failed for account {account_id}: {result.get('error')}")
            return {"success": False, "error": result.get("error")}

    except Exception as e:
        logger.error(f"Error in upvote automation: {e}")
        if 'db' in locals():
            db.close()

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries
            logger.info(f"Retrying upvote automation in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)

        return {"success": False, "error": str(e)}

@celery_app.task(bind=True, max_retries=3)
def automate_comment(self, account_id: int, parent_id: str, comment_text: str, subreddit: str):
    """Automate Reddit comment with human-like behavior"""
    try:
        logger.info(f"Starting comment automation for account {account_id}, parent {parent_id}")

        # Get account and settings
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            logger.error(f"Account {account_id} not found")
            return {"success": False, "error": "Account not found"}

        settings = account.automation_settings
        if not settings or not settings.auto_comment_enabled:
            logger.warning(f"Comment automation disabled for account {account_id}")
            return {"success": False, "error": "Comment automation disabled"}

        # Check daily limits
        today_stats = engagement_service.get_engagement_stats(account_id, days=1)
        comments_today = today_stats.get("by_action_type", {}).get("comment", 0)

        if comments_today >= settings.max_daily_comments:
            logger.warning(f"Daily comment limit reached for account {account_id}")
            return {"success": False, "error": "Daily comment limit reached"}

        # Add human-like delay (comments take longer to write)
        delay = random.uniform(10, 30)  # 10-30 seconds
        time.sleep(delay)

        # Perform comment using Reddit API
        result = reddit_service.submit_comment(account.refresh_token, parent_id, comment_text)

        # Log the engagement
        success = engagement_service.log_comment(
            account_id=account_id,
            parent_id=parent_id,
            subreddit=subreddit,
            comment_text=comment_text,
            success=result["success"],
            error_message=result.get("error")
        )

        db.close()

        if result["success"]:
            logger.info(f"Comment automation successful for account {account_id}")
            return {
                "success": True,
                "comment_id": result.get("comment_id"),
                "parent_id": parent_id,
                "subreddit": subreddit
            }
        else:
            logger.error(f"Comment automation failed for account {account_id}: {result.get('error')}")
            return {"success": False, "error": result.get("error")}

    except Exception as e:
        logger.error(f"Error in comment automation: {e}")
        if 'db' in locals():
            db.close()

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries
            logger.info(f"Retrying comment automation in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)

        return {"success": False, "error": str(e)}

@celery_app.task(bind=True, max_retries=3)
def automate_post(self, account_id: int, subreddit: str, title: str, content: str = None, url: str = None):
    """Automate Reddit post with human-like behavior"""
    try:
        logger.info(f"Starting post automation for account {account_id}, subreddit {subreddit}")

        # Get account and settings
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            logger.error(f"Account {account_id} not found")
            return {"success": False, "error": "Account not found"}

        settings = account.automation_settings
        if not settings or not settings.auto_post_enabled:
            logger.warning(f"Post automation disabled for account {account_id}")
            return {"success": False, "error": "Post automation disabled"}

        # Add human-like delay (posts take time to create)
        delay = random.uniform(30, 60)  # 30-60 seconds
        time.sleep(delay)

        # Perform post using Reddit API
        result = reddit_service.submit_post(
            refresh_token=account.refresh_token,
            subreddit_name=subreddit,
            title=title,
            content=content,
            url=url
        )

        # Log the engagement
        success = engagement_service.log_post(
            account_id=account_id,
            post_id=result.get("post_id", "unknown"),
            subreddit=subreddit,
            title=title,
            post_type=result.get("post_type", "text"),
            success=result["success"],
            error_message=result.get("error")
        )

        db.close()

        if result["success"]:
            logger.info(f"Post automation successful for account {account_id}")
            return {
                "success": True,
                "post_id": result.get("post_id"),
                "title": title,
                "subreddit": subreddit,
                "url": result.get("url")
            }
        else:
            logger.error(f"Post automation failed for account {account_id}: {result.get('error')}")
            return {"success": False, "error": result.get("error")}

    except Exception as e:
        logger.error(f"Error in post automation: {e}")
        if 'db' in locals():
            db.close()

        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            retry_delay = 2 ** self.request.retries
            logger.info(f"Retrying post automation in {retry_delay} seconds")
            raise self.retry(countdown=retry_delay)

        return {"success": False, "error": str(e)}

@celery_app.task
def check_shadowban(account_id: int):
    """Check if account is shadowbanned"""
    try:
        logger.info(f"Checking shadowban status for account {account_id}")

        # Get account
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            logger.error(f"Account {account_id} not found")
            return {"success": False, "error": "Account not found"}

        # Check shadowban using Reddit API
        is_shadowbanned = reddit_service.check_shadowban(account.refresh_token)

        # Update account health
        if account.account_health:
            account.account_health.shadowbanned = is_shadowbanned
            db.commit()

        # Log the check
        from models import ActivityLog
        activity_log = ActivityLog(
            account_id=account_id,
            action="shadowban_check",
            details={
                "shadowbanned": is_shadowbanned,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        db.add(activity_log)
        db.commit()

        db.close()

        logger.info(f"Shadowban check completed for account {account_id}: {'SHADOWBANNED' if is_shadowbanned else 'OK'}")
        return {
            "success": True,
            "account_id": account_id,
            "shadowbanned": is_shadowbanned
        }

    except Exception as e:
        logger.error(f"Error checking shadowban for account {account_id}: {e}")
        if 'db' in locals():
            db.close()
        return {"success": False, "error": str(e)}

@celery_app.task
def log_karma_snapshot(account_id: int):
    """Take and log a karma snapshot for an account"""
    try:
        logger.info(f"Taking karma snapshot for account {account_id}")

        # Use karma service to log snapshot
        success = karma_service.log_karma_snapshot(account_id)

        if success:
            logger.info(f"Karma snapshot completed for account {account_id}")
            return {"success": True, "account_id": account_id}
        else:
            logger.error(f"Karma snapshot failed for account {account_id}")
            return {"success": False, "error": "Failed to log karma snapshot"}

    except Exception as e:
        logger.error(f"Error taking karma snapshot for account {account_id}: {e}")
        return {"success": False, "error": str(e)}

@celery_app.task
def scheduled_automation_check():
    """Check and execute scheduled automation tasks"""
    try:
        logger.info("Running scheduled automation check")

        db = SessionLocal()

        # Get all accounts with automation enabled
        accounts = db.query(RedditAccount).join(AutomationSettings).filter(
            (AutomationSettings.auto_upvote_enabled == True) |
            (AutomationSettings.auto_comment_enabled == True) |
            (AutomationSettings.auto_post_enabled == True)
        ).all()

        results = []

        for account in accounts:
            try:
                # Take karma snapshot
                karma_result = log_karma_snapshot.delay(account.id)

                # Check shadowban (less frequently)
                if random.random() < 0.1:  # 10% chance
                    shadowban_result = check_shadowban.delay(account.id)

                results.append({
                    "account_id": account.id,
                    "username": account.reddit_username,
                    "tasks_scheduled": True
                })

            except Exception as e:
                logger.error(f"Error scheduling tasks for account {account.id}: {e}")
                results.append({
                    "account_id": account.id,
                    "username": account.reddit_username,
                    "tasks_scheduled": False,
                    "error": str(e)
                })

        db.close()

        logger.info(f"Scheduled automation check completed for {len(results)} accounts")
        return {
            "success": True,
            "accounts_processed": len(results),
            "results": results
        }

    except Exception as e:
        logger.error(f"Error in scheduled automation check: {e}")
        if 'db' in locals():
            db.close()
        return {"success": False, "error": str(e)}

@celery_app.task
def cleanup_old_logs(days_to_keep: int = 30):
    """Clean up old log entries to prevent database bloat"""
    try:
        logger.info(f"Cleaning up logs older than {days_to_keep} days")

        from datetime import timedelta
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        db = SessionLocal()

        # Clean up old karma logs
        from models import KarmaLog, EngagementLog, ActivityLog

        karma_deleted = db.query(KarmaLog).filter(KarmaLog.timestamp < cutoff_date).count()
        db.query(KarmaLog).filter(KarmaLog.timestamp < cutoff_date).delete()

        engagement_deleted = db.query(EngagementLog).filter(EngagementLog.timestamp < cutoff_date).count()
        db.query(EngagementLog).filter(EngagementLog.timestamp < cutoff_date).delete()

        activity_deleted = db.query(ActivityLog).filter(ActivityLog.timestamp < cutoff_date).count()
        db.query(ActivityLog).filter(ActivityLog.timestamp < cutoff_date).delete()

        db.commit()
        db.close()

        logger.info(f"Cleanup completed: {karma_deleted} karma logs, {engagement_deleted} engagement logs, {activity_deleted} activity logs deleted")
        return {
            "success": True,
            "karma_logs_deleted": karma_deleted,
            "engagement_logs_deleted": engagement_deleted,
            "activity_logs_deleted": activity_deleted
        }

    except Exception as e:
        logger.error(f"Error in log cleanup: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return {"success": False, "error": str(e)}