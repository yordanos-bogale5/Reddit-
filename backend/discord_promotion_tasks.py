"""
Celery tasks for Discord server promotion automation
Handles scheduled posting, subreddit rotation, and human behavior simulation
"""
import time
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from celery import Celery
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from models import (
    PromotionCampaign, CampaignPost, SubredditTarget, RedditAccount,
    EngagementLog, ActivityLog, AccountHealth
)
from reddit_service import reddit_service
from database import DATABASE_URL
from behavior_simulation import behavior_simulator, ActivityType

# Create database session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize Celery
celery_app = Celery('discord_promotion_tasks')
celery_app.config_from_object('celery_config')

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def automated_discord_promotion(self, campaign_id: int, account_id: int) -> Dict[str, Any]:
    """
    Perform automated Discord promotion posting with human behavior simulation
    
    Args:
        campaign_id: Campaign to post for
        account_id: Account to use for posting
        
    Returns:
        Task execution result
    """
    db = SessionLocal()
    try:
        # Get campaign and account
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()
        
        if not campaign or not campaign.is_active:
            return {'status': 'skipped', 'reason': 'campaign_inactive'}
        
        account = db.query(RedditAccount).filter(
            RedditAccount.id == account_id
        ).first()
        
        if not account or not account.refresh_token:
            return {'status': 'skipped', 'reason': 'account_invalid'}
        
        # Safety checks
        if not _is_account_safe_for_promotion(account_id, db):
            logger.warning(f"Account {account_id} not safe for Discord promotion")
            return {'status': 'skipped', 'reason': 'account_not_safe'}
        
        # Check rate limits
        if not _check_promotion_rate_limits(campaign_id, account_id, db):
            logger.warning(f"Rate limit exceeded for campaign {campaign_id}, account {account_id}")
            return {'status': 'skipped', 'reason': 'rate_limit_exceeded'}
        
        # Human behavior simulation
        activity_probability = behavior_simulator.calculate_activity_probability(
            account_id, ActivityType.POST
        )
        
        if random.random() > activity_probability:
            logger.info(f"Skipping Discord promotion due to behavior simulation")
            return {'status': 'skipped', 'reason': 'behavior_simulation'}
        
        # Select optimal subreddit
        target_subreddit = _select_optimal_subreddit_for_campaign(campaign_id, db)
        if not target_subreddit:
            return {'status': 'skipped', 'reason': 'no_available_subreddits'}
        
        # Simulate human delay before posting
        delay = _simulate_human_delay_for_promotion()
        logger.info(f"Simulating human delay for Discord promotion: {delay:.1f} seconds")
        time.sleep(delay)
        
        # Determine URL to post
        post_url = campaign.short_url if campaign.short_url else campaign.discord_url
        
        # Submit the promotion post
        try:
            result = reddit_service.submit_post(
                refresh_token=account.refresh_token,
                subreddit_name=target_subreddit,
                title=campaign.post_title,
                url=post_url
            )
            
            # Create campaign post record
            campaign_post = CampaignPost(
                campaign_id=campaign_id,
                account_id=account_id,
                subreddit=target_subreddit,
                status='success' if result.get('success') else 'failed',
                error_message=result.get('error') if not result.get('success') else None,
                details=result
            )
            
            if result.get('success'):
                campaign_post.post_id = result.get('post_id')
                campaign_post.permalink = result.get('permalink')
            
            db.add(campaign_post)
            
            # Log engagement
            engagement_log = EngagementLog(
                account_id=account_id,
                action_type='automated_discord_promotion',
                target_id=result.get('post_id'),
                subreddit=target_subreddit,
                status='success' if result.get('success') else 'failed',
                details={
                    'campaign_id': campaign_id,
                    'campaign_name': campaign.name,
                    'discord_url': post_url,
                    'automated': True,
                    'result': result
                }
            )
            db.add(engagement_log)
            
            # Update subreddit statistics
            _update_subreddit_promotion_stats(campaign_id, target_subreddit, result.get('success', False), db)
            
            db.commit()
            
            if result.get('success'):
                logger.info(f"Automated Discord promotion successful: r/{target_subreddit} - {result.get('post_id')}")
                return {
                    'status': 'success',
                    'post_id': result.get('post_id'),
                    'subreddit': target_subreddit,
                    'permalink': result.get('permalink'),
                    'campaign_id': campaign_id,
                    'account_id': account_id
                }
            else:
                logger.error(f"Automated Discord promotion failed: {result.get('error')}")
                return {
                    'status': 'failed',
                    'error': result.get('error'),
                    'subreddit': target_subreddit,
                    'campaign_id': campaign_id,
                    'account_id': account_id
                }
                
        except Exception as reddit_error:
            logger.error(f"Reddit API error during automated Discord promotion: {reddit_error}")
            
            # Create failed campaign post record
            campaign_post = CampaignPost(
                campaign_id=campaign_id,
                account_id=account_id,
                subreddit=target_subreddit,
                status='failed',
                error_message=str(reddit_error),
                details={'error': str(reddit_error), 'automated': True}
            )
            db.add(campaign_post)
            
            _update_subreddit_promotion_stats(campaign_id, target_subreddit, False, db)
            db.commit()
            
            return {
                'status': 'failed',
                'error': str(reddit_error),
                'subreddit': target_subreddit,
                'campaign_id': campaign_id,
                'account_id': account_id
            }
        
    except Exception as e:
        logger.error(f"Error in automated Discord promotion task: {e}")
        db.rollback()
        
        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying automated Discord promotion task (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return {
            'status': 'error',
            'error': str(e),
            'campaign_id': campaign_id,
            'account_id': account_id
        }
    
    finally:
        db.close()

@celery_app.task
def schedule_campaign_posts(campaign_id: int) -> Dict[str, Any]:
    """
    Schedule Discord promotion posts for a campaign based on its schedule configuration
    
    Args:
        campaign_id: Campaign to schedule posts for
        
    Returns:
        Scheduling result
    """
    db = SessionLocal()
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()
        
        if not campaign or not campaign.is_active:
            return {'status': 'skipped', 'reason': 'campaign_inactive'}
        
        schedule_config = campaign.posting_schedule
        if not schedule_config:
            return {'status': 'skipped', 'reason': 'no_schedule_config'}
        
        # Get available accounts for this campaign
        available_accounts = db.query(RedditAccount).filter(
            RedditAccount.refresh_token.isnot(None)
        ).all()
        
        if not available_accounts:
            return {'status': 'skipped', 'reason': 'no_available_accounts'}
        
        # Schedule posts based on configuration
        scheduled_tasks = []
        
        # Example schedule: post every X hours with Y randomization
        interval_hours = schedule_config.get('interval_hours', 6)
        randomization_minutes = schedule_config.get('randomization_minutes', 60)
        max_posts_per_day = schedule_config.get('max_posts_per_day', 4)
        
        # Check how many posts were made today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id,
            CampaignPost.posted_at >= today_start
        ).count()
        
        if today_posts >= max_posts_per_day:
            return {'status': 'skipped', 'reason': 'daily_limit_reached'}
        
        # Schedule next post
        base_delay = interval_hours * 3600  # Convert to seconds
        randomization = random.randint(-randomization_minutes * 60, randomization_minutes * 60)
        delay = max(300, base_delay + randomization)  # Minimum 5 minutes
        
        # Select account (rotate or random)
        account = random.choice(available_accounts)
        
        # Schedule the task
        task = automated_discord_promotion.apply_async(
            args=[campaign_id, account.id],
            countdown=delay
        )
        
        scheduled_tasks.append({
            'task_id': task.id,
            'campaign_id': campaign_id,
            'account_id': account.id,
            'scheduled_for': datetime.utcnow() + timedelta(seconds=delay),
            'delay_seconds': delay
        })
        
        logger.info(f"Scheduled Discord promotion for campaign {campaign_id} in {delay} seconds")
        
        return {
            'status': 'success',
            'scheduled_tasks': scheduled_tasks,
            'campaign_id': campaign_id
        }
        
    except Exception as e:
        logger.error(f"Error scheduling campaign posts: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'campaign_id': campaign_id
        }
    
    finally:
        db.close()

def _is_account_safe_for_promotion(account_id: int, db) -> bool:
    """Check if account is safe for Discord promotion"""
    account_health = db.query(AccountHealth).filter(
        AccountHealth.account_id == account_id
    ).first()
    
    if not account_health:
        return False
    
    # Safety criteria for Discord promotion
    if account_health.shadowbanned:
        return False
    
    if account_health.captcha_triggered:
        return False
    
    if account_health.trust_score < 0.5:
        return False
    
    if account_health.bans > 0:
        return False
    
    return True

def _check_promotion_rate_limits(campaign_id: int, account_id: int, db) -> bool:
    """Check if posting rate limits are respected"""
    # Check recent posts for this campaign and account
    recent_posts = db.query(CampaignPost).filter(
        CampaignPost.campaign_id == campaign_id,
        CampaignPost.account_id == account_id,
        CampaignPost.posted_at > datetime.utcnow() - timedelta(hours=2)
    ).count()
    
    # Limit to 1 post per 2 hours per account per campaign
    return recent_posts == 0

def _select_optimal_subreddit_for_campaign(campaign_id: int, db) -> Optional[str]:
    """Select optimal subreddit for automated posting"""
    targets = db.query(SubredditTarget).filter(
        SubredditTarget.campaign_id == campaign_id,
        SubredditTarget.is_active == True
    ).order_by(
        SubredditTarget.priority.asc(),
        SubredditTarget.success_rate.desc()
    ).all()
    
    if not targets:
        return None
    
    # Prefer subreddits not posted to in last 8 hours
    for target in targets:
        recent_post = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id,
            CampaignPost.subreddit == target.subreddit_name,
            CampaignPost.posted_at > datetime.utcnow() - timedelta(hours=8)
        ).first()
        
        if not recent_post:
            return target.subreddit_name
    
    # Fallback to preferred subreddits
    preferred = [t for t in targets if t.is_preferred]
    if preferred:
        return random.choice(preferred).subreddit_name
    
    return random.choice(targets).subreddit_name

def _simulate_human_delay_for_promotion() -> float:
    """Simulate human-like delay for Discord promotion posts"""
    # Longer delays for promotional content to appear more natural
    base_delay = random.uniform(30, 120)  # 30 seconds to 2 minutes
    variation = random.uniform(0.5, 2.0)
    return base_delay * variation

def _update_subreddit_promotion_stats(campaign_id: int, subreddit: str, success: bool, db):
    """Update subreddit target statistics for promotion"""
    target = db.query(SubredditTarget).filter(
        SubredditTarget.campaign_id == campaign_id,
        SubredditTarget.subreddit_name == subreddit
    ).first()
    
    if target:
        target.total_posts += 1
        if success:
            target.successful_posts += 1
        else:
            target.removed_posts += 1
        
        target.success_rate = (target.successful_posts / target.total_posts) * 100
        target.last_posted = datetime.utcnow()
