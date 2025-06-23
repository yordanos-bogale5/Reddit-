"""
Safety tasks for Reddit automation engine
Includes rate limiting, account safety checks, shadowban detection, and health monitoring
"""
import redis
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from celery import current_task
from celery_worker import celery_app
from database import SessionLocal
from models import (
    RedditAccount, EngagementLog, ActivityLog, AccountHealth, 
    AutomationSettings, KarmaLog
)
from reddit_service import reddit_service

logger = logging.getLogger(__name__)

# Redis connection for rate limiting
redis_client = redis.Redis(
    host='localhost', 
    port=6379, 
    db=1,  # Use different DB for rate limiting
    decode_responses=True
)

@dataclass
class RateLimit:
    """Rate limit configuration"""
    action_type: str
    max_per_hour: int
    max_per_day: int
    cooldown_seconds: int
    burst_limit: int = 0  # Allow burst actions

# Default rate limits (conservative for safety)
DEFAULT_RATE_LIMITS = {
    'upvote': RateLimit('upvote', 60, 500, 30, 5),
    'comment': RateLimit('comment', 10, 50, 120, 2),
    'post': RateLimit('post', 3, 10, 300, 1),
    'follow': RateLimit('follow', 5, 20, 180, 1),
    'message': RateLimit('message', 5, 25, 240, 1),
}

@dataclass
class SafetyThresholds:
    """Safety thresholds for account health"""
    min_account_age_days: int = 7
    min_karma_threshold: int = 10
    max_daily_actions: int = 100
    max_hourly_actions: int = 20
    max_consecutive_failures: int = 5
    min_success_rate: float = 0.8
    shadowban_check_interval_hours: int = 6

SAFETY_THRESHOLDS = SafetyThresholds()

def get_rate_limit_key(account_id: int, action_type: str, time_window: str) -> str:
    """Generate Redis key for rate limiting"""
    timestamp = datetime.utcnow()
    if time_window == 'hour':
        time_key = timestamp.strftime('%Y%m%d%H')
    elif time_window == 'day':
        time_key = timestamp.strftime('%Y%m%d')
    elif time_window == 'minute':
        time_key = timestamp.strftime('%Y%m%d%H%M')
    else:
        time_key = timestamp.strftime('%Y%m%d')
    
    return f"rate_limit:{account_id}:{action_type}:{time_window}:{time_key}"

def get_cooldown_key(account_id: int, action_type: str) -> str:
    """Generate Redis key for action cooldowns"""
    return f"cooldown:{account_id}:{action_type}"

def check_rate_limits(account_id: int, action_type: str) -> bool:
    """Check if action is within rate limits"""
    try:
        rate_limit = DEFAULT_RATE_LIMITS.get(action_type)
        if not rate_limit:
            logger.warning(f"No rate limit defined for action type: {action_type}")
            return True
        
        # Check cooldown
        cooldown_key = get_cooldown_key(account_id, action_type)
        last_action_time = redis_client.get(cooldown_key)
        if last_action_time:
            time_since_last = time.time() - float(last_action_time)
            if time_since_last < rate_limit.cooldown_seconds:
                logger.info(f"Action {action_type} for account {account_id} in cooldown. "
                           f"Wait {rate_limit.cooldown_seconds - time_since_last:.1f} more seconds")
                return False
        
        # Check hourly limit
        hourly_key = get_rate_limit_key(account_id, action_type, 'hour')
        hourly_count = int(redis_client.get(hourly_key) or 0)
        if hourly_count >= rate_limit.max_per_hour:
            logger.warning(f"Hourly rate limit exceeded for {action_type} on account {account_id}")
            return False
        
        # Check daily limit
        daily_key = get_rate_limit_key(account_id, action_type, 'day')
        daily_count = int(redis_client.get(daily_key) or 0)
        if daily_count >= rate_limit.max_per_day:
            logger.warning(f"Daily rate limit exceeded for {action_type} on account {account_id}")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking rate limits: {e}")
        return False  # Fail safe - deny action if rate limit check fails

def record_action(account_id: int, action_type: str, success: bool = True) -> None:
    """Record an action for rate limiting purposes"""
    try:
        rate_limit = DEFAULT_RATE_LIMITS.get(action_type)
        if not rate_limit:
            return
        
        current_time = time.time()
        
        # Set cooldown
        cooldown_key = get_cooldown_key(account_id, action_type)
        redis_client.setex(cooldown_key, rate_limit.cooldown_seconds, current_time)
        
        # Increment counters
        hourly_key = get_rate_limit_key(account_id, action_type, 'hour')
        daily_key = get_rate_limit_key(account_id, action_type, 'day')
        
        # Use pipeline for atomic operations
        pipe = redis_client.pipeline()
        pipe.incr(hourly_key)
        pipe.expire(hourly_key, 3600)  # 1 hour TTL
        pipe.incr(daily_key)
        pipe.expire(daily_key, 86400)  # 24 hour TTL
        pipe.execute()
        
        # Record failure for safety monitoring
        if not success:
            failure_key = f"failures:{account_id}:{action_type}"
            redis_client.incr(failure_key)
            redis_client.expire(failure_key, 3600)  # Track failures for 1 hour
        
        logger.debug(f"Recorded {action_type} action for account {account_id}, success: {success}")
        
    except Exception as e:
        logger.error(f"Error recording action: {e}")

def get_action_counts(account_id: int, action_type: str) -> Dict[str, int]:
    """Get current action counts for an account"""
    try:
        hourly_key = get_rate_limit_key(account_id, action_type, 'hour')
        daily_key = get_rate_limit_key(account_id, action_type, 'day')
        failure_key = f"failures:{account_id}:{action_type}"

        return {
            'hourly_count': int(redis_client.get(hourly_key) or 0),
            'daily_count': int(redis_client.get(daily_key) or 0),
            'recent_failures': int(redis_client.get(failure_key) or 0)
        }
    except Exception as e:
        logger.error(f"Error getting action counts: {e}")
        return {'hourly_count': 0, 'daily_count': 0, 'recent_failures': 0}

def is_account_safe(account_id: int) -> bool:
    """Comprehensive safety check for an account"""
    try:
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            logger.error(f"Account {account_id} not found")
            return False

        # Check account health
        health = account.account_health
        if not health:
            logger.warning(f"No health data for account {account_id}")
            return False

        # Check if shadowbanned
        if health.shadowbanned:
            logger.warning(f"Account {account_id} is shadowbanned")
            return False

        # Check account age
        if health.account_age_days < SAFETY_THRESHOLDS.min_account_age_days:
            logger.warning(f"Account {account_id} too young: {health.account_age_days} days")
            return False

        # Check trust score
        if health.trust_score < SAFETY_THRESHOLDS.min_success_rate:
            logger.warning(f"Account {account_id} trust score too low: {health.trust_score}")
            return False

        # Check recent failures
        total_failures = 0
        for action_type in DEFAULT_RATE_LIMITS.keys():
            counts = get_action_counts(account_id, action_type)
            total_failures += counts['recent_failures']

        if total_failures >= SAFETY_THRESHOLDS.max_consecutive_failures:
            logger.warning(f"Account {account_id} has too many recent failures: {total_failures}")
            return False

        # Check if account has login issues
        if health.login_issues:
            logger.warning(f"Account {account_id} has login issues")
            return False

        # Check if captcha is being triggered frequently
        if health.captcha_triggered:
            logger.warning(f"Account {account_id} is triggering captchas")
            return False

        db.close()
        return True

    except Exception as e:
        logger.error(f"Error checking account safety: {e}")
        if 'db' in locals():
            db.close()
        return False

def calculate_trust_score(account_id: int) -> float:
    """Calculate trust score based on account activity and success rate"""
    try:
        db = SessionLocal()

        # Get recent engagement logs (last 7 days)
        week_ago = datetime.utcnow() - timedelta(days=7)
        recent_logs = db.query(EngagementLog).filter(
            EngagementLog.account_id == account_id,
            EngagementLog.timestamp >= week_ago
        ).all()

        if not recent_logs:
            return 0.5  # Neutral score for new accounts

        # Calculate success rate
        successful_actions = sum(1 for log in recent_logs if log.status == 'success')
        total_actions = len(recent_logs)
        success_rate = successful_actions / total_actions if total_actions > 0 else 0

        # Get account health metrics
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        health = account.account_health if account else None

        # Base score from success rate
        trust_score = success_rate

        # Adjust based on account age (older accounts get bonus)
        if health and health.account_age_days:
            age_bonus = min(health.account_age_days / 365, 0.2)  # Max 20% bonus for 1+ year old accounts
            trust_score += age_bonus

        # Penalty for bans, deletions, removals
        if health:
            penalty = (health.bans * 0.3 + health.deletions * 0.1 + health.removals * 0.05)
            trust_score -= penalty

        # Ensure score is between 0 and 1
        trust_score = max(0.0, min(1.0, trust_score))

        db.close()
        return trust_score

    except Exception as e:
        logger.error(f"Error calculating trust score: {e}")
        if 'db' in locals():
            db.close()
        return 0.0

def update_account_health(account_id: int) -> Dict[str, Any]:
    """Update account health metrics"""
    try:
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            return {'success': False, 'error': 'Account not found'}

        # Get or create account health record
        health = account.account_health
        if not health:
            health = AccountHealth(account_id=account_id)
            db.add(health)

        # Update account age
        account_age = reddit_service.get_account_age(account.refresh_token)
        health.account_age_days = account_age

        # Update trust score
        health.trust_score = calculate_trust_score(account_id)

        # Check for recent issues
        recent_logs = db.query(EngagementLog).filter(
            EngagementLog.account_id == account_id,
            EngagementLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).all()

        # Count recent failures
        recent_failures = sum(1 for log in recent_logs if log.status == 'failed')

        # Update health flags based on recent activity
        health.login_issues = recent_failures > 5
        health.captcha_triggered = any('captcha' in str(log.details).lower() for log in recent_logs if log.details)

        db.commit()
        db.close()

        logger.info(f"Updated health for account {account_id}: trust_score={health.trust_score:.2f}")
        return {
            'success': True,
            'account_id': account_id,
            'trust_score': health.trust_score,
            'account_age_days': health.account_age_days
        }

    except Exception as e:
        logger.error(f"Error updating account health: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return {'success': False, 'error': str(e)}

# Celery Tasks for Safety Monitoring

@celery_app.task(bind=True, max_retries=3)
def detect_shadowbans(self) -> Dict[str, Any]:
    """Detect shadowbans across all accounts"""
    try:
        logger.info("Starting shadowban detection for all accounts")

        db = SessionLocal()
        accounts = db.query(RedditAccount).all()
        results = []

        for account in accounts:
            try:
                # Check if we should test this account (not too frequently)
                last_check_key = f"shadowban_check:{account.id}"
                last_check = redis_client.get(last_check_key)

                if last_check:
                    hours_since_check = (time.time() - float(last_check)) / 3600
                    if hours_since_check < SAFETY_THRESHOLDS.shadowban_check_interval_hours:
                        continue

                # Perform shadowban check
                is_shadowbanned = check_account_shadowban(account.id)

                # Update last check time
                redis_client.setex(last_check_key, 86400, time.time())  # 24 hour TTL

                results.append({
                    'account_id': account.id,
                    'username': account.reddit_username,
                    'shadowbanned': is_shadowbanned,
                    'checked_at': datetime.utcnow().isoformat()
                })

                # Small delay between checks to avoid rate limiting
                time.sleep(2)

            except Exception as e:
                logger.error(f"Error checking shadowban for account {account.id}: {e}")
                results.append({
                    'account_id': account.id,
                    'username': account.reddit_username,
                    'error': str(e)
                })

        db.close()

        shadowbanned_count = sum(1 for r in results if r.get('shadowbanned'))
        logger.info(f"Shadowban detection completed. {shadowbanned_count} shadowbanned accounts found")

        return {
            'success': True,
            'accounts_checked': len(results),
            'shadowbanned_count': shadowbanned_count,
            'results': results
        }

    except Exception as e:
        logger.error(f"Error in shadowban detection: {e}")
        if 'db' in locals():
            db.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)  # Retry in 5 minutes

        return {'success': False, 'error': str(e)}

def check_account_shadowban(account_id: int) -> bool:
    """Advanced shadowban detection for a specific account"""
    try:
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            return False

        # Method 1: Basic API check
        basic_check = reddit_service.check_shadowban(account.refresh_token)

        # Method 2: Post visibility check
        visibility_check = check_post_visibility(account.refresh_token)

        # Method 3: Profile access check
        profile_check = check_profile_access(account.refresh_token)

        # Combine results (if any method indicates shadowban, consider it shadowbanned)
        is_shadowbanned = basic_check or not visibility_check or not profile_check

        # Update account health
        health = account.account_health
        if health:
            health.shadowbanned = is_shadowbanned
            db.commit()

        # Log the check
        activity_log = ActivityLog(
            account_id=account_id,
            action='shadowban_check',
            details={
                'shadowbanned': is_shadowbanned,
                'basic_check': basic_check,
                'visibility_check': visibility_check,
                'profile_check': profile_check,
                'timestamp': datetime.utcnow().isoformat()
            }
        )
        db.add(activity_log)
        db.commit()

        db.close()

        if is_shadowbanned:
            logger.warning(f"Account {account_id} ({account.reddit_username}) appears to be shadowbanned")

        return is_shadowbanned

    except Exception as e:
        logger.error(f"Error checking shadowban for account {account_id}: {e}")
        if 'db' in locals():
            db.close()
        return False

def check_post_visibility(refresh_token: str) -> bool:
    """Check if recent posts are visible to others"""
    try:
        reddit = reddit_service.get_reddit_instance(refresh_token)
        user = reddit.user.me()

        # Get recent submissions
        recent_posts = list(user.submissions.new(limit=5))
        if not recent_posts:
            return True  # No posts to check

        # Check if posts have any engagement (upvotes, comments)
        for post in recent_posts:
            # If post has score > 1 or comments, it's likely visible
            if post.score > 1 or post.num_comments > 0:
                return True

        # If no posts have engagement, might be shadowbanned
        return False

    except Exception as e:
        logger.warning(f"Error checking post visibility: {e}")
        return True  # Assume visible if check fails

def check_profile_access(refresh_token: str) -> bool:
    """Check if profile is accessible"""
    try:
        reddit = reddit_service.get_reddit_instance(refresh_token)
        user = reddit.user.me()

        # Try to access profile information
        _ = user.name
        _ = user.created_utc
        _ = user.link_karma
        _ = user.comment_karma

        return True

    except Exception as e:
        logger.warning(f"Error accessing profile: {e}")
        return False

@celery_app.task(bind=True, max_retries=3)
def monitor_account_health(self) -> Dict[str, Any]:
    """Monitor health of all accounts and update metrics"""
    try:
        logger.info("Starting account health monitoring")

        db = SessionLocal()
        accounts = db.query(RedditAccount).all()
        results = []

        for account in accounts:
            try:
                # Update account health
                health_result = update_account_health(account.id)
                results.append(health_result)

                # Check if account needs attention
                if health_result.get('success') and health_result.get('trust_score', 0) < 0.5:
                    logger.warning(f"Account {account.id} has low trust score: {health_result['trust_score']}")

                # Small delay between updates
                time.sleep(1)

            except Exception as e:
                logger.error(f"Error monitoring health for account {account.id}: {e}")
                results.append({
                    'success': False,
                    'account_id': account.id,
                    'error': str(e)
                })

        db.close()

        successful_updates = sum(1 for r in results if r.get('success'))
        logger.info(f"Account health monitoring completed. {successful_updates}/{len(results)} accounts updated")

        return {
            'success': True,
            'accounts_monitored': len(results),
            'successful_updates': successful_updates,
            'results': results
        }

    except Exception as e:
        logger.error(f"Error in account health monitoring: {e}")
        if 'db' in locals():
            db.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

        return {'success': False, 'error': str(e)}

@celery_app.task
def reset_daily_limits() -> Dict[str, Any]:
    """Reset daily rate limits (called at midnight)"""
    try:
        logger.info("Resetting daily rate limits")

        # Get all daily rate limit keys
        pattern = "rate_limit:*:*:day:*"
        keys = redis_client.keys(pattern)

        if keys:
            redis_client.delete(*keys)
            logger.info(f"Reset {len(keys)} daily rate limit counters")

        # Also reset daily failure counters
        failure_pattern = "failures:*:*"
        failure_keys = redis_client.keys(failure_pattern)

        if failure_keys:
            redis_client.delete(*failure_keys)
            logger.info(f"Reset {len(failure_keys)} failure counters")

        return {
            'success': True,
            'daily_limits_reset': len(keys),
            'failure_counters_reset': len(failure_keys)
        }

    except Exception as e:
        logger.error(f"Error resetting daily limits: {e}")
        return {'success': False, 'error': str(e)}

@celery_app.task(bind=True, max_retries=3)
def process_scheduled_automation(self) -> Dict[str, Any]:
    """Process scheduled automation tasks based on account settings"""
    try:
        logger.info("Processing scheduled automation tasks")

        db = SessionLocal()

        # Get accounts with automation enabled
        accounts = db.query(RedditAccount).join(AutomationSettings).filter(
            (AutomationSettings.auto_upvote_enabled == True) |
            (AutomationSettings.auto_comment_enabled == True) |
            (AutomationSettings.auto_post_enabled == True)
        ).all()

        scheduled_tasks = []

        for account in accounts:
            try:
                # Safety check before scheduling
                if not is_account_safe(account.id):
                    logger.warning(f"Skipping automation for unsafe account {account.id}")
                    continue

                settings = account.automation_settings
                if not settings:
                    continue

                # Check engagement schedule
                current_hour = datetime.utcnow().hour
                schedule = settings.engagement_schedule or {}

                # Simple schedule check (can be enhanced)
                if str(current_hour) in schedule.get('active_hours', []):
                    # Schedule karma snapshot
                    from automation_tasks import update_karma_snapshots
                    task_result = update_karma_snapshots.delay(account.id)
                    scheduled_tasks.append({
                        'account_id': account.id,
                        'task_type': 'karma_snapshot',
                        'task_id': task_result.id
                    })

            except Exception as e:
                logger.error(f"Error scheduling automation for account {account.id}: {e}")

        db.close()

        logger.info(f"Scheduled {len(scheduled_tasks)} automation tasks")
        return {
            'success': True,
            'tasks_scheduled': len(scheduled_tasks),
            'scheduled_tasks': scheduled_tasks
        }

    except Exception as e:
        logger.error(f"Error processing scheduled automation: {e}")
        if 'db' in locals():
            db.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60)

        return {'success': False, 'error': str(e)}

def get_safety_status(account_id: int) -> Dict[str, Any]:
    """Get comprehensive safety status for an account"""
    try:
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            return {'error': 'Account not found'}

        health = account.account_health
        safety_status = {
            'account_id': account_id,
            'username': account.reddit_username,
            'is_safe': is_account_safe(account_id),
            'health_metrics': {
                'trust_score': health.trust_score if health else 0,
                'account_age_days': health.account_age_days if health else 0,
                'shadowbanned': health.shadowbanned if health else False,
                'login_issues': health.login_issues if health else False,
                'captcha_triggered': health.captcha_triggered if health else False,
                'bans': health.bans if health else 0,
                'deletions': health.deletions if health else 0,
                'removals': health.removals if health else 0
            },
            'rate_limits': {}
        }

        # Get rate limit status for each action type
        for action_type in DEFAULT_RATE_LIMITS.keys():
            counts = get_action_counts(account_id, action_type)
            rate_limit = DEFAULT_RATE_LIMITS[action_type]

            safety_status['rate_limits'][action_type] = {
                'hourly_count': counts['hourly_count'],
                'hourly_limit': rate_limit.max_per_hour,
                'daily_count': counts['daily_count'],
                'daily_limit': rate_limit.max_per_day,
                'recent_failures': counts['recent_failures'],
                'can_perform': check_rate_limits(account_id, action_type)
            }

        db.close()
        return safety_status

    except Exception as e:
        logger.error(f"Error getting safety status: {e}")
        if 'db' in locals():
            db.close()
        return {'error': str(e)}

# Advanced Rate Limiting Features

def check_burst_limits(account_id: int, action_type: str) -> bool:
    """Check if action is within burst limits (short-term rapid actions)"""
    try:
        rate_limit = DEFAULT_RATE_LIMITS.get(action_type)
        if not rate_limit or rate_limit.burst_limit == 0:
            return True

        # Check actions in last 5 minutes
        minute_key = get_rate_limit_key(account_id, action_type, 'minute')
        current_minute = datetime.utcnow().strftime('%Y%m%d%H%M')

        # Check last 5 minutes
        burst_count = 0
        for i in range(5):
            minute_timestamp = (datetime.utcnow() - timedelta(minutes=i)).strftime('%Y%m%d%H%M')
            key = f"rate_limit:{account_id}:{action_type}:minute:{minute_timestamp}"
            count = int(redis_client.get(key) or 0)
            burst_count += count

        if burst_count >= rate_limit.burst_limit:
            logger.warning(f"Burst limit exceeded for {action_type} on account {account_id}: {burst_count}/{rate_limit.burst_limit}")
            return False

        return True

    except Exception as e:
        logger.error(f"Error checking burst limits: {e}")
        return True  # Allow action if check fails

def get_adaptive_rate_limit(account_id: int, action_type: str) -> RateLimit:
    """Get adaptive rate limit based on account performance"""
    try:
        base_limit = DEFAULT_RATE_LIMITS.get(action_type)
        if not base_limit:
            return base_limit

        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account or not account.account_health:
            db.close()
            return base_limit

        health = account.account_health
        trust_score = health.trust_score
        account_age_days = health.account_age_days

        # Calculate adjustment factors
        trust_factor = trust_score  # 0.0 to 1.0
        age_factor = min(account_age_days / 365, 1.0)  # 0.0 to 1.0 (capped at 1 year)

        # Combine factors (higher trust and age = higher limits)
        adjustment_factor = (trust_factor * 0.7 + age_factor * 0.3)

        # Apply adjustments (can increase limits by up to 50% for trusted accounts)
        max_multiplier = 1.5
        min_multiplier = 0.5
        multiplier = min_multiplier + (adjustment_factor * (max_multiplier - min_multiplier))

        # Create adaptive rate limit
        adaptive_limit = RateLimit(
            action_type=base_limit.action_type,
            max_per_hour=int(base_limit.max_per_hour * multiplier),
            max_per_day=int(base_limit.max_per_day * multiplier),
            cooldown_seconds=int(base_limit.cooldown_seconds / multiplier),
            burst_limit=int(base_limit.burst_limit * multiplier) if base_limit.burst_limit > 0 else 0
        )

        db.close()

        logger.debug(f"Adaptive rate limit for account {account_id} {action_type}: "
                    f"multiplier={multiplier:.2f}, trust={trust_score:.2f}, age={account_age_days}")

        return adaptive_limit

    except Exception as e:
        logger.error(f"Error getting adaptive rate limit: {e}")
        if 'db' in locals():
            db.close()
        return base_limit

def check_adaptive_rate_limits(account_id: int, action_type: str) -> bool:
    """Enhanced rate limit check with adaptive limits"""
    try:
        # Get adaptive rate limit for this account
        rate_limit = get_adaptive_rate_limit(account_id, action_type)
        if not rate_limit:
            logger.warning(f"No rate limit defined for action type: {action_type}")
            return True

        # Check burst limits first
        if not check_burst_limits(account_id, action_type):
            return False

        # Check cooldown
        cooldown_key = get_cooldown_key(account_id, action_type)
        last_action_time = redis_client.get(cooldown_key)
        if last_action_time:
            time_since_last = time.time() - float(last_action_time)
            if time_since_last < rate_limit.cooldown_seconds:
                logger.info(f"Action {action_type} for account {account_id} in cooldown. "
                           f"Wait {rate_limit.cooldown_seconds - time_since_last:.1f} more seconds")
                return False

        # Check hourly limit
        hourly_key = get_rate_limit_key(account_id, action_type, 'hour')
        hourly_count = int(redis_client.get(hourly_key) or 0)
        if hourly_count >= rate_limit.max_per_hour:
            logger.warning(f"Hourly rate limit exceeded for {action_type} on account {account_id}: "
                          f"{hourly_count}/{rate_limit.max_per_hour}")
            return False

        # Check daily limit
        daily_key = get_rate_limit_key(account_id, action_type, 'day')
        daily_count = int(redis_client.get(daily_key) or 0)
        if daily_count >= rate_limit.max_per_day:
            logger.warning(f"Daily rate limit exceeded for {action_type} on account {account_id}: "
                          f"{daily_count}/{rate_limit.max_per_day}")
            return False

        return True

    except Exception as e:
        logger.error(f"Error checking adaptive rate limits: {e}")
        return False

def record_action_with_burst(account_id: int, action_type: str, success: bool = True) -> None:
    """Enhanced action recording with burst tracking"""
    try:
        rate_limit = DEFAULT_RATE_LIMITS.get(action_type)
        if not rate_limit:
            return

        current_time = time.time()

        # Set cooldown
        cooldown_key = get_cooldown_key(account_id, action_type)
        redis_client.setex(cooldown_key, rate_limit.cooldown_seconds, current_time)

        # Increment counters including minute-level for burst detection
        hourly_key = get_rate_limit_key(account_id, action_type, 'hour')
        daily_key = get_rate_limit_key(account_id, action_type, 'day')
        minute_key = get_rate_limit_key(account_id, action_type, 'minute')

        # Use pipeline for atomic operations
        pipe = redis_client.pipeline()
        pipe.incr(hourly_key)
        pipe.expire(hourly_key, 3600)  # 1 hour TTL
        pipe.incr(daily_key)
        pipe.expire(daily_key, 86400)  # 24 hour TTL
        pipe.incr(minute_key)
        pipe.expire(minute_key, 300)  # 5 minute TTL for burst detection
        pipe.execute()

        # Record failure for safety monitoring
        if not success:
            failure_key = f"failures:{account_id}:{action_type}"
            redis_client.incr(failure_key)
            redis_client.expire(failure_key, 3600)  # Track failures for 1 hour

            # Increase failure streak counter
            streak_key = f"failure_streak:{account_id}:{action_type}"
            redis_client.incr(streak_key)
            redis_client.expire(streak_key, 1800)  # 30 minute TTL
        else:
            # Reset failure streak on success
            streak_key = f"failure_streak:{account_id}:{action_type}"
            redis_client.delete(streak_key)

        logger.debug(f"Recorded {action_type} action for account {account_id}, success: {success}")

    except Exception as e:
        logger.error(f"Error recording action with burst tracking: {e}")

def get_rate_limit_status(account_id: int) -> Dict[str, Any]:
    """Get comprehensive rate limit status for an account"""
    try:
        status = {
            'account_id': account_id,
            'limits': {},
            'global_status': 'healthy'
        }

        total_recent_failures = 0

        for action_type in DEFAULT_RATE_LIMITS.keys():
            base_limit = DEFAULT_RATE_LIMITS[action_type]
            adaptive_limit = get_adaptive_rate_limit(account_id, action_type)
            counts = get_action_counts(account_id, action_type)

            # Get failure streak
            streak_key = f"failure_streak:{account_id}:{action_type}"
            failure_streak = int(redis_client.get(streak_key) or 0)

            # Check burst count
            burst_count = 0
            for i in range(5):
                minute_timestamp = (datetime.utcnow() - timedelta(minutes=i)).strftime('%Y%m%d%H%M')
                key = f"rate_limit:{account_id}:{action_type}:minute:{minute_timestamp}"
                burst_count += int(redis_client.get(key) or 0)

            # Calculate remaining limits
            hourly_remaining = max(0, adaptive_limit.max_per_hour - counts['hourly_count'])
            daily_remaining = max(0, adaptive_limit.max_per_day - counts['daily_count'])

            # Check cooldown status
            cooldown_key = get_cooldown_key(account_id, action_type)
            last_action_time = redis_client.get(cooldown_key)
            cooldown_remaining = 0
            if last_action_time:
                cooldown_remaining = max(0, adaptive_limit.cooldown_seconds - (time.time() - float(last_action_time)))

            status['limits'][action_type] = {
                'base_limits': {
                    'hourly': base_limit.max_per_hour,
                    'daily': base_limit.max_per_day,
                    'cooldown': base_limit.cooldown_seconds,
                    'burst': base_limit.burst_limit
                },
                'adaptive_limits': {
                    'hourly': adaptive_limit.max_per_hour,
                    'daily': adaptive_limit.max_per_day,
                    'cooldown': adaptive_limit.cooldown_seconds,
                    'burst': adaptive_limit.burst_limit
                },
                'current_usage': {
                    'hourly_count': counts['hourly_count'],
                    'daily_count': counts['daily_count'],
                    'burst_count': burst_count,
                    'recent_failures': counts['recent_failures'],
                    'failure_streak': failure_streak
                },
                'remaining': {
                    'hourly': hourly_remaining,
                    'daily': daily_remaining,
                    'cooldown_seconds': cooldown_remaining
                },
                'can_perform': check_adaptive_rate_limits(account_id, action_type),
                'status': 'healthy' if counts['recent_failures'] < 3 else 'degraded'
            }

            total_recent_failures += counts['recent_failures']

        # Determine global status
        if total_recent_failures >= 10:
            status['global_status'] = 'critical'
        elif total_recent_failures >= 5:
            status['global_status'] = 'degraded'

        return status

    except Exception as e:
        logger.error(f"Error getting rate limit status: {e}")
        return {'error': str(e)}

# Enhanced Shadowban Detection Methods

def check_comment_visibility(refresh_token: str) -> Tuple[bool, Dict[str, Any]]:
    """Check if recent comments are visible to others"""
    try:
        reddit = reddit_service.get_reddit_instance(refresh_token)
        user = reddit.user.me()

        # Get recent comments
        recent_comments = list(user.comments.new(limit=10))
        if not recent_comments:
            return True, {'reason': 'no_comments', 'comments_checked': 0}

        visibility_indicators = {
            'total_comments': len(recent_comments),
            'comments_with_replies': 0,
            'comments_with_upvotes': 0,
            'avg_score': 0,
            'suspicious_patterns': []
        }

        total_score = 0
        for comment in recent_comments:
            total_score += comment.score

            # Check for replies (indicates visibility)
            if hasattr(comment, 'replies') and len(comment.replies) > 0:
                visibility_indicators['comments_with_replies'] += 1

            # Check for upvotes (score > 1 indicates others saw it)
            if comment.score > 1:
                visibility_indicators['comments_with_upvotes'] += 1

        visibility_indicators['avg_score'] = total_score / len(recent_comments) if recent_comments else 0

        # Analyze patterns that might indicate shadowban
        if visibility_indicators['comments_with_replies'] == 0 and len(recent_comments) >= 5:
            visibility_indicators['suspicious_patterns'].append('no_replies_to_recent_comments')

        if visibility_indicators['comments_with_upvotes'] == 0 and len(recent_comments) >= 5:
            visibility_indicators['suspicious_patterns'].append('no_upvotes_on_recent_comments')

        if visibility_indicators['avg_score'] <= 1.0 and len(recent_comments) >= 5:
            visibility_indicators['suspicious_patterns'].append('consistently_low_scores')

        # Determine if comments appear visible
        is_visible = (
            visibility_indicators['comments_with_replies'] > 0 or
            visibility_indicators['comments_with_upvotes'] > 0 or
            visibility_indicators['avg_score'] > 1.2
        )

        return is_visible, visibility_indicators

    except Exception as e:
        logger.warning(f"Error checking comment visibility: {e}")
        return True, {'error': str(e)}

def check_submission_visibility(refresh_token: str) -> Tuple[bool, Dict[str, Any]]:
    """Check if recent submissions are visible and getting engagement"""
    try:
        reddit = reddit_service.get_reddit_instance(refresh_token)
        user = reddit.user.me()

        # Get recent submissions
        recent_submissions = list(user.submissions.new(limit=10))
        if not recent_submissions:
            return True, {'reason': 'no_submissions', 'submissions_checked': 0}

        visibility_indicators = {
            'total_submissions': len(recent_submissions),
            'submissions_with_comments': 0,
            'submissions_with_upvotes': 0,
            'avg_score': 0,
            'avg_comments': 0,
            'suspicious_patterns': []
        }

        total_score = 0
        total_comments = 0

        for submission in recent_submissions:
            total_score += submission.score
            total_comments += submission.num_comments

            # Check for comments (indicates visibility)
            if submission.num_comments > 0:
                visibility_indicators['submissions_with_comments'] += 1

            # Check for upvotes (score > 1 indicates others saw it)
            if submission.score > 1:
                visibility_indicators['submissions_with_upvotes'] += 1

        visibility_indicators['avg_score'] = total_score / len(recent_submissions) if recent_submissions else 0
        visibility_indicators['avg_comments'] = total_comments / len(recent_submissions) if recent_submissions else 0

        # Analyze patterns that might indicate shadowban
        if visibility_indicators['submissions_with_comments'] == 0 and len(recent_submissions) >= 3:
            visibility_indicators['suspicious_patterns'].append('no_comments_on_recent_posts')

        if visibility_indicators['submissions_with_upvotes'] == 0 and len(recent_submissions) >= 3:
            visibility_indicators['suspicious_patterns'].append('no_upvotes_on_recent_posts')

        if visibility_indicators['avg_score'] <= 1.0 and len(recent_submissions) >= 3:
            visibility_indicators['suspicious_patterns'].append('consistently_low_post_scores')

        # Determine if submissions appear visible
        is_visible = (
            visibility_indicators['submissions_with_comments'] > 0 or
            visibility_indicators['submissions_with_upvotes'] > 0 or
            visibility_indicators['avg_score'] > 1.5
        )

        return is_visible, visibility_indicators

    except Exception as e:
        logger.warning(f"Error checking submission visibility: {e}")
        return True, {'error': str(e)}

def check_user_page_accessibility(refresh_token: str) -> Tuple[bool, Dict[str, Any]]:
    """Check if user page is accessible from different perspectives"""
    try:
        reddit = reddit_service.get_reddit_instance(refresh_token)
        user = reddit.user.me()
        username = user.name

        accessibility_info = {
            'username': username,
            'profile_accessible': False,
            'recent_activity_visible': False,
            'karma_visible': False,
            'account_age_visible': False,
            'error_details': []
        }

        try:
            # Try to access basic profile info
            _ = user.name
            _ = user.id
            accessibility_info['profile_accessible'] = True
        except Exception as e:
            accessibility_info['error_details'].append(f"Profile access error: {str(e)}")

        try:
            # Try to access karma information
            _ = user.link_karma
            _ = user.comment_karma
            accessibility_info['karma_visible'] = True
        except Exception as e:
            accessibility_info['error_details'].append(f"Karma access error: {str(e)}")

        try:
            # Try to access account creation date
            _ = user.created_utc
            accessibility_info['account_age_visible'] = True
        except Exception as e:
            accessibility_info['error_details'].append(f"Account age access error: {str(e)}")

        try:
            # Try to access recent activity
            list(user.submissions.new(limit=1))
            list(user.comments.new(limit=1))
            accessibility_info['recent_activity_visible'] = True
        except Exception as e:
            accessibility_info['error_details'].append(f"Recent activity access error: {str(e)}")

        # Determine overall accessibility
        is_accessible = (
            accessibility_info['profile_accessible'] and
            accessibility_info['karma_visible'] and
            accessibility_info['account_age_visible'] and
            accessibility_info['recent_activity_visible']
        )

        return is_accessible, accessibility_info

    except Exception as e:
        logger.warning(f"Error checking user page accessibility: {e}")
        return False, {'error': str(e)}

def comprehensive_shadowban_check(account_id: int) -> Dict[str, Any]:
    """Perform comprehensive shadowban detection using multiple methods"""
    try:
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            return {'error': 'Account not found'}

        logger.info(f"Performing comprehensive shadowban check for account {account_id}")

        # Method 1: Basic API check
        basic_check = reddit_service.check_shadowban(account.refresh_token)

        # Method 2: Post visibility check
        post_visible, post_details = check_post_visibility(account.refresh_token)

        # Method 3: Comment visibility check
        comment_visible, comment_details = check_comment_visibility(account.refresh_token)

        # Method 4: Submission visibility check
        submission_visible, submission_details = check_submission_visibility(account.refresh_token)

        # Method 5: Profile accessibility check
        profile_accessible, profile_details = check_profile_access(account.refresh_token)

        # Method 6: User page accessibility check
        user_page_accessible, user_page_details = check_user_page_accessibility(account.refresh_token)

        # Compile all results
        detection_results = {
            'account_id': account_id,
            'username': account.reddit_username,
            'timestamp': datetime.utcnow().isoformat(),
            'methods': {
                'basic_api_check': {
                    'shadowbanned': basic_check,
                    'weight': 0.3
                },
                'post_visibility': {
                    'visible': post_visible,
                    'details': post_details,
                    'weight': 0.2
                },
                'comment_visibility': {
                    'visible': comment_visible,
                    'details': comment_details,
                    'weight': 0.2
                },
                'submission_visibility': {
                    'visible': submission_visible,
                    'details': submission_details,
                    'weight': 0.15
                },
                'profile_accessibility': {
                    'accessible': profile_accessible,
                    'weight': 0.1
                },
                'user_page_accessibility': {
                    'accessible': user_page_accessible,
                    'details': user_page_details,
                    'weight': 0.05
                }
            }
        }

        # Calculate weighted shadowban probability
        shadowban_score = 0.0
        total_weight = 0.0

        methods = detection_results['methods']

        # Basic API check (higher weight if positive)
        if methods['basic_api_check']['shadowbanned']:
            shadowban_score += methods['basic_api_check']['weight']
        total_weight += methods['basic_api_check']['weight']

        # Visibility checks (higher score if NOT visible)
        if not methods['post_visibility']['visible']:
            shadowban_score += methods['post_visibility']['weight']
        total_weight += methods['post_visibility']['weight']

        if not methods['comment_visibility']['visible']:
            shadowban_score += methods['comment_visibility']['weight']
        total_weight += methods['comment_visibility']['weight']

        if not methods['submission_visibility']['visible']:
            shadowban_score += methods['submission_visibility']['weight']
        total_weight += methods['submission_visibility']['weight']

        # Accessibility checks (higher score if NOT accessible)
        if not methods['profile_accessibility']['accessible']:
            shadowban_score += methods['profile_accessibility']['weight']
        total_weight += methods['profile_accessibility']['weight']

        if not methods['user_page_accessibility']['accessible']:
            shadowban_score += methods['user_page_accessibility']['weight']
        total_weight += methods['user_page_accessibility']['weight']

        # Normalize score
        shadowban_probability = shadowban_score / total_weight if total_weight > 0 else 0

        # Determine final result
        is_shadowbanned = shadowban_probability > 0.5
        confidence_level = 'high' if shadowban_probability > 0.7 or shadowban_probability < 0.3 else 'medium'

        detection_results.update({
            'shadowban_probability': shadowban_probability,
            'is_shadowbanned': is_shadowbanned,
            'confidence_level': confidence_level,
            'recommendation': 'investigate' if 0.3 <= shadowban_probability <= 0.7 else ('shadowbanned' if is_shadowbanned else 'not_shadowbanned')
        })

        # Update account health
        health = account.account_health
        if health:
            health.shadowbanned = is_shadowbanned
            db.commit()

        # Log the comprehensive check
        activity_log = ActivityLog(
            account_id=account_id,
            action='comprehensive_shadowban_check',
            details=detection_results
        )
        db.add(activity_log)
        db.commit()

        db.close()

        if is_shadowbanned:
            logger.warning(f"Account {account_id} appears to be shadowbanned (probability: {shadowban_probability:.2f})")
        else:
            logger.info(f"Account {account_id} appears to be safe (shadowban probability: {shadowban_probability:.2f})")

        return detection_results

    except Exception as e:
        logger.error(f"Error in comprehensive shadowban check: {e}")
        if 'db' in locals():
            db.close()
        return {'error': str(e)}

# Enhanced Safety Features

def detect_captcha_patterns(account_id: int) -> Dict[str, Any]:
    """Detect patterns that indicate frequent captcha triggers"""
    try:
        db = SessionLocal()

        # Look for captcha-related activity in logs
        recent_logs = db.query(ActivityLog).filter(
            ActivityLog.account_id == account_id,
            ActivityLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
        ).all()

        captcha_indicators = {
            'captcha_mentions': 0,
            'failed_actions': 0,
            'suspicious_delays': 0,
            'frequent_captchas': False,
            'last_captcha_time': None,
            'captcha_frequency': 0.0
        }

        for log in recent_logs:
            details_str = str(log.details).lower() if log.details else ''

            # Check for captcha mentions
            if 'captcha' in details_str or 'challenge' in details_str:
                captcha_indicators['captcha_mentions'] += 1
                captcha_indicators['last_captcha_time'] = log.timestamp.isoformat()

            # Check for failed actions that might indicate captcha
            if log.action in ['upvote', 'comment', 'post'] and 'failed' in details_str:
                captcha_indicators['failed_actions'] += 1

        # Calculate captcha frequency
        if captcha_indicators['captcha_mentions'] > 0:
            captcha_indicators['captcha_frequency'] = captcha_indicators['captcha_mentions'] / 24  # per hour
            captcha_indicators['frequent_captchas'] = captcha_indicators['captcha_frequency'] > 0.5  # More than 1 every 2 hours

        db.close()
        return captcha_indicators

    except Exception as e:
        logger.error(f"Error detecting captcha patterns: {e}")
        if 'db' in locals():
            db.close()
        return {'error': str(e)}

def auto_pause_automation(account_id: int, reason: str) -> Dict[str, Any]:
    """Automatically pause automation for an account due to safety concerns"""
    try:
        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            return {'success': False, 'error': 'Account not found'}

        # Disable all automation
        settings = account.automation_settings
        if settings:
            settings.auto_upvote_enabled = False
            settings.auto_comment_enabled = False
            settings.auto_post_enabled = False
            db.commit()

        # Log the auto-pause
        activity_log = ActivityLog(
            account_id=account_id,
            action='auto_pause_automation',
            details={
                'reason': reason,
                'timestamp': datetime.utcnow().isoformat(),
                'previous_settings': {
                    'auto_upvote_enabled': True,
                    'auto_comment_enabled': True,
                    'auto_post_enabled': True
                } if settings else None
            }
        )
        db.add(activity_log)
        db.commit()

        # Set pause flag in Redis for immediate effect
        pause_key = f"automation_paused:{account_id}"
        redis_client.setex(pause_key, 86400, json.dumps({
            'paused': True,
            'reason': reason,
            'timestamp': datetime.utcnow().isoformat()
        }))

        db.close()

        logger.warning(f"Automation paused for account {account_id}: {reason}")
        return {
            'success': True,
            'account_id': account_id,
            'reason': reason,
            'paused_at': datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error auto-pausing automation: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return {'success': False, 'error': str(e)}

def get_safety_alerts(account_id: int = None, hours: int = 24) -> List[Dict[str, Any]]:
    """Get safety alerts for monitoring"""
    try:
        # For now, return empty list - this is a placeholder implementation
        # In a full implementation, this would query a database or cache
        return []
    except Exception as e:
        logger.error(f"Error getting safety alerts: {e}")
        return []

def create_safety_alert(account_id: int, alert_type: str, severity: str, message: str, details: Dict = None) -> Dict[str, Any]:
    """Create a safety alert for monitoring"""
    try:
        alert_data = {
            'account_id': account_id,
            'alert_type': alert_type,  # 'shadowban', 'captcha', 'rate_limit', 'suspicious_activity'
            'severity': severity,  # 'low', 'medium', 'high', 'critical'
            'message': message,
            'details': details or {},
            'timestamp': datetime.utcnow().isoformat(),
            'resolved': False
        }

        # Store alert in Redis for real-time monitoring
        alert_key = f"safety_alert:{account_id}:{int(time.time())}"
        redis_client.setex(alert_key, 86400 * 7, json.dumps(alert_data))  # Keep for 7 days

        # Also store in database for persistence
        db = SessionLocal()
        activity_log = ActivityLog(
            account_id=account_id,
            action='safety_alert',
            details=alert_data
        )
        db.add(activity_log)
        db.commit()
        db.close()

        logger.warning(f"Safety alert created for account {account_id}: {alert_type} - {message}")

        # Auto-pause if critical
        if severity == 'critical':
            auto_pause_result = auto_pause_automation(account_id, f"Critical safety alert: {message}")
            alert_data['auto_paused'] = auto_pause_result.get('success', False)

        return alert_data

    except Exception as e:
        logger.error(f"Error creating safety alert: {e}")
        if 'db' in locals():
            db.close()
        return {'error': str(e)}
