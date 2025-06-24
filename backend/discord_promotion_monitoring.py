"""
Discord Promotion Monitoring Service
Handles post monitoring, shadowban detection, and health checks for Discord promotion campaigns
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine

from models import (
    PromotionCampaign, CampaignPost, SubredditTarget, RedditAccount,
    AccountHealth, EngagementLog, ActivityLog
)
from reddit_service import reddit_service
from database import DATABASE_URL
from celery import Celery

# Create database session
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize Celery
celery_app = Celery('discord_promotion_monitoring')
celery_app.config_from_object('celery_config')

logger = logging.getLogger(__name__)

@celery_app.task
def monitor_campaign_posts(campaign_id: int) -> Dict[str, Any]:
    """
    Monitor all posts for a campaign to check for removals, shadowbans, and engagement
    
    Args:
        campaign_id: Campaign to monitor
        
    Returns:
        Monitoring results
    """
    db = SessionLocal()
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            return {'status': 'error', 'message': 'Campaign not found'}
        
        # Get recent posts that need monitoring (last 7 days)
        recent_posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id,
            CampaignPost.status == 'success',
            CampaignPost.posted_at > datetime.utcnow() - timedelta(days=7)
        ).all()
        
        monitoring_results = {
            'campaign_id': campaign_id,
            'posts_checked': 0,
            'posts_removed': 0,
            'posts_updated': 0,
            'shadowban_detected': False,
            'errors': []
        }
        
        for post in recent_posts:
            try:
                # Get account for this post
                account = post.account
                if not account or not account.refresh_token:
                    continue
                
                # Check if post still exists and get current stats
                post_data = _check_post_status(account.refresh_token, post.post_id)
                
                if post_data:
                    # Update post statistics
                    post.upvotes = post_data.get('upvotes', 0)
                    post.downvotes = post_data.get('downvotes', 0)
                    post.comments_count = post_data.get('num_comments', 0)
                    
                    # Check if post was removed
                    if post_data.get('removed', False):
                        post.status = 'removed'
                        post.removed_at = datetime.utcnow()
                        monitoring_results['posts_removed'] += 1
                        
                        # Update subreddit stats
                        _update_subreddit_removal_stats(campaign_id, post.subreddit, db)
                        
                        logger.warning(f"Post {post.post_id} in r/{post.subreddit} was removed")
                    
                    monitoring_results['posts_updated'] += 1
                else:
                    # Post not found - might be deleted or shadowbanned
                    post.status = 'removed'
                    post.removed_at = datetime.utcnow()
                    monitoring_results['posts_removed'] += 1
                    
                    # Check for potential shadowban
                    if _check_potential_shadowban(account.refresh_token, post.subreddit):
                        monitoring_results['shadowban_detected'] = True
                        _handle_shadowban_detection(account.id, post.subreddit, db)
                
                monitoring_results['posts_checked'] += 1
                
                # Add delay between checks to avoid rate limiting
                time.sleep(2)
                
            except Exception as e:
                error_msg = f"Error checking post {post.post_id}: {str(e)}"
                monitoring_results['errors'].append(error_msg)
                logger.error(error_msg)
        
        db.commit()
        
        logger.info(f"Campaign {campaign_id} monitoring complete: {monitoring_results}")
        return monitoring_results
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error monitoring campaign posts: {e}")
        return {'status': 'error', 'message': str(e)}
    
    finally:
        db.close()

@celery_app.task
def check_account_health_for_promotion(account_id: int) -> Dict[str, Any]:
    """
    Comprehensive health check for accounts used in Discord promotion
    
    Args:
        account_id: Account to check
        
    Returns:
        Health check results
    """
    db = SessionLocal()
    try:
        account = db.query(RedditAccount).filter(
            RedditAccount.id == account_id
        ).first()
        
        if not account or not account.refresh_token:
            return {'status': 'error', 'message': 'Account not found or not connected'}
        
        health_results = {
            'account_id': account_id,
            'username': account.reddit_username,
            'overall_health': 'good',
            'issues': [],
            'recommendations': [],
            'safe_for_promotion': True
        }
        
        try:
            # Check basic account access
            user_info = reddit_service.get_user_info(account.refresh_token)
            if not user_info.get('success'):
                health_results['issues'].append('Cannot access account information')
                health_results['overall_health'] = 'critical'
                health_results['safe_for_promotion'] = False
                return health_results
            
            # Check for shadowban
            is_shadowbanned = reddit_service.check_shadowban(account.refresh_token)
            if is_shadowbanned:
                health_results['issues'].append('Account appears to be shadowbanned')
                health_results['overall_health'] = 'critical'
                health_results['safe_for_promotion'] = False
            
            # Check recent promotion activity
            recent_promotions = db.query(CampaignPost).filter(
                CampaignPost.account_id == account_id,
                CampaignPost.posted_at > datetime.utcnow() - timedelta(days=7)
            ).count()
            
            if recent_promotions > 20:
                health_results['issues'].append(f'High promotion activity: {recent_promotions} posts in last 7 days')
                health_results['overall_health'] = 'warning'
                health_results['recommendations'].append('Consider reducing posting frequency')
            
            # Check removal rate
            total_posts = db.query(CampaignPost).filter(
                CampaignPost.account_id == account_id
            ).count()
            
            removed_posts = db.query(CampaignPost).filter(
                CampaignPost.account_id == account_id,
                CampaignPost.status == 'removed'
            ).count()
            
            if total_posts > 0:
                removal_rate = (removed_posts / total_posts) * 100
                if removal_rate > 50:
                    health_results['issues'].append(f'High removal rate: {removal_rate:.1f}%')
                    health_results['overall_health'] = 'warning'
                    health_results['safe_for_promotion'] = False
                elif removal_rate > 25:
                    health_results['recommendations'].append(f'Monitor removal rate: {removal_rate:.1f}%')
            
            # Update account health record
            account_health = db.query(AccountHealth).filter(
                AccountHealth.account_id == account_id
            ).first()
            
            if account_health:
                account_health.shadowbanned = is_shadowbanned
                account_health.trust_score = _calculate_trust_score(health_results)
                
                if health_results['overall_health'] == 'critical':
                    account_health.trust_score = 0.0
                elif health_results['overall_health'] == 'warning':
                    account_health.trust_score = max(0.3, account_health.trust_score * 0.7)
            
            db.commit()
            
        except Exception as reddit_error:
            health_results['issues'].append(f'Reddit API error: {str(reddit_error)}')
            health_results['overall_health'] = 'critical'
            health_results['safe_for_promotion'] = False
        
        return health_results
        
    except Exception as e:
        logger.error(f"Error checking account health: {e}")
        return {'status': 'error', 'message': str(e)}
    
    finally:
        db.close()

@celery_app.task
def generate_promotion_safety_report(campaign_id: int) -> Dict[str, Any]:
    """
    Generate comprehensive safety report for a Discord promotion campaign
    
    Args:
        campaign_id: Campaign to analyze
        
    Returns:
        Safety report
    """
    db = SessionLocal()
    try:
        campaign = db.query(PromotionCampaign).filter(
            PromotionCampaign.id == campaign_id
        ).first()
        
        if not campaign:
            return {'status': 'error', 'message': 'Campaign not found'}
        
        # Get all posts for this campaign
        all_posts = db.query(CampaignPost).filter(
            CampaignPost.campaign_id == campaign_id
        ).all()
        
        # Get unique accounts used
        account_ids = list(set(post.account_id for post in all_posts))
        
        safety_report = {
            'campaign_id': campaign_id,
            'campaign_name': campaign.name,
            'generated_at': datetime.utcnow().isoformat(),
            'overall_safety_score': 0,
            'risk_level': 'low',
            'total_posts': len(all_posts),
            'accounts_used': len(account_ids),
            'issues': [],
            'recommendations': [],
            'account_health': {},
            'subreddit_risks': {}
        }
        
        # Analyze account health
        for account_id in account_ids:
            health_check = check_account_health_for_promotion.delay(account_id)
            # Note: In production, you'd want to wait for results or use a different approach
            
        # Analyze subreddit performance and risks
        subreddit_stats = {}
        for post in all_posts:
            if post.subreddit not in subreddit_stats:
                subreddit_stats[post.subreddit] = {
                    'total': 0, 'removed': 0, 'successful': 0
                }
            
            subreddit_stats[post.subreddit]['total'] += 1
            if post.status == 'removed':
                subreddit_stats[post.subreddit]['removed'] += 1
            elif post.status == 'success':
                subreddit_stats[post.subreddit]['successful'] += 1
        
        # Calculate risk scores
        high_risk_subreddits = []
        for subreddit, stats in subreddit_stats.items():
            if stats['total'] > 0:
                removal_rate = (stats['removed'] / stats['total']) * 100
                if removal_rate > 60:
                    high_risk_subreddits.append(subreddit)
                    safety_report['subreddit_risks'][subreddit] = {
                        'risk_level': 'high',
                        'removal_rate': removal_rate,
                        'total_posts': stats['total']
                    }
        
        # Generate overall safety score and recommendations
        if high_risk_subreddits:
            safety_report['risk_level'] = 'high'
            safety_report['overall_safety_score'] = 30
            safety_report['issues'].append(f'High removal rates in: {", ".join(high_risk_subreddits)}')
            safety_report['recommendations'].append('Consider pausing posts to high-risk subreddits')
        else:
            safety_report['overall_safety_score'] = 80
            safety_report['recommendations'].append('Continue monitoring post performance')
        
        return safety_report
        
    except Exception as e:
        logger.error(f"Error generating safety report: {e}")
        return {'status': 'error', 'message': str(e)}
    
    finally:
        db.close()

def _check_post_status(refresh_token: str, post_id: str) -> Optional[Dict[str, Any]]:
    """Check if a Reddit post still exists and get its current stats"""
    try:
        reddit = reddit_service.get_reddit_instance(refresh_token)
        submission = reddit.submission(id=post_id)
        
        # Try to access post properties
        return {
            'upvotes': submission.score,
            'downvotes': 0,  # Reddit doesn't provide downvote count directly
            'num_comments': submission.num_comments,
            'removed': submission.removed_by_category is not None,
            'title': submission.title,
            'url': submission.url
        }
    except Exception as e:
        logger.warning(f"Could not check post {post_id}: {e}")
        return None

def _check_potential_shadowban(refresh_token: str, subreddit: str) -> bool:
    """Check if account might be shadowbanned in a specific subreddit"""
    try:
        # This is a simplified check - in practice, shadowban detection is complex
        return reddit_service.check_shadowban(refresh_token)
    except Exception:
        return False

def _handle_shadowban_detection(account_id: int, subreddit: str, db):
    """Handle detected shadowban by updating account health and logging"""
    account_health = db.query(AccountHealth).filter(
        AccountHealth.account_id == account_id
    ).first()
    
    if account_health:
        account_health.shadowbanned = True
        account_health.trust_score = 0.0
    
    # Log the detection
    activity_log = ActivityLog(
        account_id=account_id,
        action='shadowban_detected',
        details={
            'subreddit': subreddit,
            'detected_at': datetime.utcnow().isoformat(),
            'source': 'discord_promotion_monitoring'
        }
    )
    db.add(activity_log)

def _update_subreddit_removal_stats(campaign_id: int, subreddit: str, db):
    """Update subreddit target statistics when a post is removed"""
    target = db.query(SubredditTarget).filter(
        SubredditTarget.campaign_id == campaign_id,
        SubredditTarget.subreddit_name == subreddit
    ).first()
    
    if target:
        target.removed_posts += 1
        # Recalculate success rate
        if target.total_posts > 0:
            target.success_rate = (target.successful_posts / target.total_posts) * 100

def _calculate_trust_score(health_results: Dict[str, Any]) -> float:
    """Calculate trust score based on health check results"""
    base_score = 1.0
    
    if health_results['overall_health'] == 'critical':
        return 0.0
    elif health_results['overall_health'] == 'warning':
        base_score *= 0.6
    
    # Reduce score based on number of issues
    issue_penalty = len(health_results['issues']) * 0.1
    return max(0.0, base_score - issue_penalty)
