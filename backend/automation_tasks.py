"""
Celery tasks for Reddit automation engine with human behavior simulation
"""
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

from celery import current_task
from celery_worker import celery_app
from database import SessionLocal
from models import (
    RedditAccount, EngagementLog, KarmaLog, AutomationSettings, 
    ActivityLog, AccountHealth
)
from reddit_service import reddit_service
from karma_service import karma_service
from safety_tasks import check_rate_limits, is_account_safe, get_action_counts
from behavior_simulation import behavior_simulator, ActivityType

logger = logging.getLogger(__name__)

# Human behavior simulation constants
HUMAN_DELAYS = {
    'min_action_delay': 30,      # 30 seconds minimum between actions
    'max_action_delay': 300,     # 5 minutes maximum between actions
    'reading_time': (10, 60),    # 10-60 seconds reading time
    'typing_speed': (20, 40),    # 20-40 characters per second
    'break_probability': 0.15,   # 15% chance of taking a break
    'break_duration': (300, 1800) # 5-30 minute breaks
}

ACTIVITY_PATTERNS = {
    'morning': {'start': 6, 'end': 12, 'activity_multiplier': 1.2},
    'afternoon': {'start': 12, 'end': 18, 'activity_multiplier': 1.0},
    'evening': {'start': 18, 'end': 23, 'activity_multiplier': 1.5},
    'night': {'start': 23, 'end': 6, 'activity_multiplier': 0.3}
}

def simulate_human_delay(action_type: str = 'default') -> float:
    """Simulate realistic human delays between actions"""
    base_delay = random.uniform(
        HUMAN_DELAYS['min_action_delay'], 
        HUMAN_DELAYS['max_action_delay']
    )
    
    # Add reading time for content-based actions
    if action_type in ['comment', 'post']:
        reading_time = random.uniform(*HUMAN_DELAYS['reading_time'])
        base_delay += reading_time
    
    # Add typing time for text-based actions
    if action_type == 'comment':
        # Simulate typing time (assuming average comment length)
        avg_comment_length = 100
        typing_speed = random.uniform(*HUMAN_DELAYS['typing_speed'])
        typing_time = avg_comment_length / typing_speed
        base_delay += typing_time
    
    # Random break chance
    if random.random() < HUMAN_DELAYS['break_probability']:
        break_time = random.uniform(*HUMAN_DELAYS['break_duration'])
        base_delay += break_time
        logger.info(f"Taking human-like break: {break_time:.1f} seconds")
    
    return base_delay

def get_activity_multiplier() -> float:
    """Get activity multiplier based on current time of day"""
    current_hour = datetime.now().hour
    
    for period, config in ACTIVITY_PATTERNS.items():
        start, end = config['start'], config['end']
        if start <= end:  # Normal period (not crossing midnight)
            if start <= current_hour < end:
                return config['activity_multiplier']
        else:  # Period crossing midnight
            if current_hour >= start or current_hour < end:
                return config['activity_multiplier']
    
    return 1.0  # Default multiplier

def should_perform_action() -> bool:
    """Determine if an action should be performed based on activity patterns"""
    multiplier = get_activity_multiplier()
    base_probability = 0.7  # 70% base chance
    adjusted_probability = min(base_probability * multiplier, 0.95)
    
    return random.random() < adjusted_probability

@celery_app.task(bind=True, max_retries=3)
def automated_upvote(self, account_id: int, post_id: str, subreddit: str) -> Dict[str, Any]:
    """Perform automated upvoting with human behavior simulation"""
    try:
        # Safety checks
        if not is_account_safe(account_id):
            logger.warning(f"Account {account_id} not safe for automation")
            return {'status': 'skipped', 'reason': 'account_not_safe'}
        
        if not check_rate_limits(account_id, 'upvote'):
            logger.warning(f"Rate limit exceeded for account {account_id}")
            return {'status': 'skipped', 'reason': 'rate_limit_exceeded'}
        
        # Enhanced human behavior simulation
        activity_probability = behavior_simulator.calculate_activity_probability(
            account_id, ActivityType.UPVOTE
        )

        if activity_probability < 0.3:
            logger.info(f"Skipping upvote due to low activity probability: {activity_probability:.2f}")
            return {'status': 'skipped', 'reason': 'low_activity_probability'}

        # Generate realistic delay using enhanced behavior simulation
        delay = behavior_simulator.generate_realistic_delay(ActivityType.UPVOTE)
        logger.info(f"Enhanced behavior simulation delay: {delay:.1f} seconds")
        time.sleep(delay)
        
        # Perform the upvote
        db = SessionLocal()
        try:
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if not account:
                return {'status': 'error', 'message': 'Account not found'}
            
            # Execute upvote via Reddit API
            result = reddit_service.upvote_post(account.refresh_token, post_id)
            
            # Log the engagement
            engagement_log = EngagementLog(
                account_id=account_id,
                action_type='upvote',
                target_id=post_id,
                subreddit=subreddit,
                status='success' if result['success'] else 'failed',
                details=result
            )
            db.add(engagement_log)
            
            # Log activity
            activity_log = ActivityLog(
                account_id=account_id,
                action='automated_upvote',
                details={
                    'post_id': post_id,
                    'subreddit': subreddit,
                    'delay_simulated': delay,
                    'result': result
                }
            )
            db.add(activity_log)
            
            db.commit()
            
            logger.info(f"Automated upvote completed for account {account_id}")
            return {
                'status': 'success',
                'account_id': account_id,
                'post_id': post_id,
                'subreddit': subreddit,
                'delay_simulated': delay
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in automated upvote: {e}")
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying automated upvote (attempt {self.request.retries + 1})")
            raise self.retry(countdown=60 * (self.request.retries + 1))
        return {'status': 'error', 'message': str(e)}

@celery_app.task(bind=True, max_retries=3)
def automated_comment(self, account_id: int, post_id: str, comment_text: str, subreddit: str) -> Dict[str, Any]:
    """Perform automated commenting with human behavior simulation"""
    try:
        # Safety checks
        if not is_account_safe(account_id):
            return {'status': 'skipped', 'reason': 'account_not_safe'}
        
        if not check_rate_limits(account_id, 'comment'):
            return {'status': 'skipped', 'reason': 'rate_limit_exceeded'}
        
        # Enhanced human behavior simulation for comments
        activity_probability = behavior_simulator.calculate_activity_probability(
            account_id, ActivityType.COMMENT
        )

        if activity_probability < 0.4:  # Higher threshold for comments
            logger.info(f"Skipping comment due to low activity probability: {activity_probability:.2f}")
            return {'status': 'skipped', 'reason': 'low_activity_probability'}

        # Generate realistic delay including typing simulation
        base_delay = behavior_simulator.generate_realistic_delay(ActivityType.COMMENT)
        typing_delay = behavior_simulator.simulate_typing_speed(len(comment_text))
        total_delay = base_delay + typing_delay

        logger.info(f"Enhanced comment delay: {total_delay:.1f}s (base: {base_delay:.1f}s, typing: {typing_delay:.1f}s)")
        time.sleep(total_delay)
        
        # Perform the comment
        db = SessionLocal()
        try:
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if not account:
                return {'status': 'error', 'message': 'Account not found'}
            
            # Execute comment via Reddit API
            result = reddit_service.comment_on_post(account.refresh_token, post_id, comment_text)
            
            # Log the engagement
            engagement_log = EngagementLog(
                account_id=account_id,
                action_type='comment',
                target_id=post_id,
                subreddit=subreddit,
                status='success' if result['success'] else 'failed',
                details=result
            )
            db.add(engagement_log)
            
            # Log activity
            activity_log = ActivityLog(
                account_id=account_id,
                action='automated_comment',
                details={
                    'post_id': post_id,
                    'subreddit': subreddit,
                    'comment_text': comment_text[:100] + '...' if len(comment_text) > 100 else comment_text,
                    'delay_simulated': total_delay,
                    'result': result
                }
            )
            db.add(activity_log)
            
            db.commit()
            
            logger.info(f"Automated comment completed for account {account_id}")
            return {
                'status': 'success',
                'account_id': account_id,
                'post_id': post_id,
                'comment_id': result.get('comment_id'),
                'subreddit': subreddit,
                'delay_simulated': total_delay
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in automated comment: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        return {'status': 'error', 'message': str(e)}

@celery_app.task(bind=True, max_retries=3)
def automated_post(self, account_id: int, subreddit: str, title: str, content: str = None, url: str = None) -> Dict[str, Any]:
    """Perform automated posting with human behavior simulation"""
    try:
        # Safety checks
        if not is_account_safe(account_id):
            return {'status': 'skipped', 'reason': 'account_not_safe'}
        
        if not check_rate_limits(account_id, 'post'):
            return {'status': 'skipped', 'reason': 'rate_limit_exceeded'}
        
        # Human behavior simulation
        if not should_perform_action():
            return {'status': 'skipped', 'reason': 'activity_pattern'}
        
        # Simulate human delay (longest for posts)
        delay = simulate_human_delay('post')
        logger.info(f"Simulating human delay for post: {delay:.1f} seconds")
        time.sleep(delay)
        
        # Perform the post
        db = SessionLocal()
        try:
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if not account:
                return {'status': 'error', 'message': 'Account not found'}
            
            # Execute post via Reddit API
            result = reddit_service.submit_post(
                account.refresh_token, subreddit, title, content, url
            )
            
            # Log the engagement
            engagement_log = EngagementLog(
                account_id=account_id,
                action_type='post',
                target_id=result.get('post_id'),
                subreddit=subreddit,
                status='success' if result['success'] else 'failed',
                details=result
            )
            db.add(engagement_log)
            
            # Log activity
            activity_log = ActivityLog(
                account_id=account_id,
                action='automated_post',
                details={
                    'subreddit': subreddit,
                    'title': title,
                    'post_type': 'link' if url else 'text',
                    'delay_simulated': delay,
                    'result': result
                }
            )
            db.add(activity_log)
            
            db.commit()
            
            logger.info(f"Automated post completed for account {account_id}")
            return {
                'status': 'success',
                'account_id': account_id,
                'post_id': result.get('post_id'),
                'subreddit': subreddit,
                'title': title,
                'delay_simulated': delay
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in automated post: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        return {'status': 'error', 'message': str(e)}

@celery_app.task(bind=True, max_retries=3)
def update_karma_snapshots(self, account_id: int = None) -> Dict[str, Any]:
    """Update karma snapshots for accounts"""
    try:
        db = SessionLocal()

        if account_id:
            accounts = [db.query(RedditAccount).filter(RedditAccount.id == account_id).first()]
            accounts = [acc for acc in accounts if acc]  # Filter out None
        else:
            accounts = db.query(RedditAccount).all()

        results = []

        for account in accounts:
            try:
                # Get detailed karma information
                karma_data = reddit_service.get_detailed_karma(account.refresh_token)

                # Create karma log entry
                karma_log = KarmaLog(
                    account_id=account.id,
                    total_karma=karma_data['total_karma'],
                    post_karma=karma_data['post_karma'],
                    comment_karma=karma_data['comment_karma'],
                    by_subreddit=karma_data.get('by_subreddit', {}),
                    by_content_type=karma_data.get('by_content_type', {})
                )
                db.add(karma_log)

                results.append({
                    'account_id': account.id,
                    'username': account.reddit_username,
                    'total_karma': karma_data['total_karma'],
                    'status': 'success'
                })

            except Exception as e:
                logger.error(f"Error updating karma for account {account.id}: {e}")
                results.append({
                    'account_id': account.id,
                    'username': account.reddit_username if account else 'unknown',
                    'status': 'error',
                    'error': str(e)
                })

        db.commit()
        db.close()

        successful_updates = sum(1 for r in results if r['status'] == 'success')
        logger.info(f"Karma snapshots updated: {successful_updates}/{len(results)} successful")

        return {
            'status': 'success',
            'accounts_processed': len(results),
            'successful_updates': successful_updates,
            'results': results
        }

    except Exception as e:
        logger.error(f"Error in karma snapshot update: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

        return {'status': 'error', 'message': str(e)}

def get_optimal_posting_time(account_id: int, subreddit: str) -> datetime:
    """Calculate optimal posting time based on historical data and patterns"""
    try:
        db = SessionLocal()

        # Get historical engagement data for this subreddit
        week_ago = datetime.utcnow() - timedelta(days=7)
        historical_data = db.query(EngagementLog).filter(
            EngagementLog.account_id == account_id,
            EngagementLog.subreddit == subreddit,
            EngagementLog.timestamp >= week_ago,
            EngagementLog.status == 'success'
        ).all()

        # Analyze engagement patterns by hour
        hourly_engagement = {}
        for log in historical_data:
            hour = log.timestamp.hour
            if hour not in hourly_engagement:
                hourly_engagement[hour] = []

            # Extract engagement metrics from details if available
            if log.details and isinstance(log.details, dict):
                score = log.details.get('score', 1)
                hourly_engagement[hour].append(score)

        # Find best performing hours
        best_hours = []
        for hour, scores in hourly_engagement.items():
            if scores:
                avg_score = sum(scores) / len(scores)
                best_hours.append((hour, avg_score))

        # Sort by average score
        best_hours.sort(key=lambda x: x[1], reverse=True)

        # Get current time and find next optimal slot
        current_time = datetime.utcnow()

        if best_hours:
            # Use top 3 best performing hours
            optimal_hours = [h[0] for h in best_hours[:3]]
        else:
            # Default to general best times for Reddit
            optimal_hours = [9, 14, 19, 21]  # 9 AM, 2 PM, 7 PM, 9 PM UTC

        # Find next optimal time
        for hour in optimal_hours:
            next_time = current_time.replace(hour=hour, minute=random.randint(0, 59), second=0, microsecond=0)
            if next_time <= current_time:
                next_time += timedelta(days=1)

            # Add some randomization (±30 minutes)
            random_offset = timedelta(minutes=random.randint(-30, 30))
            next_time += random_offset

            db.close()
            return next_time

        # Fallback: random time in next 24 hours
        random_hours = random.randint(1, 24)
        random_minutes = random.randint(0, 59)
        next_time = current_time + timedelta(hours=random_hours, minutes=random_minutes)

        db.close()
        return next_time

    except Exception as e:
        logger.error(f"Error calculating optimal posting time: {e}")
        if 'db' in locals():
            db.close()
        # Fallback to random time in next few hours
        return datetime.utcnow() + timedelta(hours=random.randint(1, 6))

def simulate_browsing_behavior(account_id: int, duration_minutes: int = 30) -> Dict[str, Any]:
    """Simulate realistic browsing behavior before performing actions"""
    try:
        logger.info(f"Simulating browsing behavior for account {account_id} for {duration_minutes} minutes")

        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            return {'status': 'error', 'message': 'Account not found'}

        browsing_actions = []
        start_time = time.time()
        end_time = start_time + (duration_minutes * 60)

        while time.time() < end_time:
            # Simulate different browsing activities
            action_type = random.choices(
                ['view_post', 'scroll', 'read_comments', 'switch_subreddit', 'pause'],
                weights=[30, 25, 20, 15, 10]
            )[0]

            if action_type == 'view_post':
                # Simulate viewing a post (reading time)
                reading_time = random.uniform(5, 45)  # 5-45 seconds
                time.sleep(reading_time)
                browsing_actions.append({'action': 'view_post', 'duration': reading_time})

            elif action_type == 'scroll':
                # Simulate scrolling through feed
                scroll_time = random.uniform(2, 10)  # 2-10 seconds
                time.sleep(scroll_time)
                browsing_actions.append({'action': 'scroll', 'duration': scroll_time})

            elif action_type == 'read_comments':
                # Simulate reading comments
                comment_reading_time = random.uniform(10, 60)  # 10-60 seconds
                time.sleep(comment_reading_time)
                browsing_actions.append({'action': 'read_comments', 'duration': comment_reading_time})

            elif action_type == 'switch_subreddit':
                # Simulate switching to different subreddit
                switch_time = random.uniform(1, 5)  # 1-5 seconds
                time.sleep(switch_time)
                browsing_actions.append({'action': 'switch_subreddit', 'duration': switch_time})

            elif action_type == 'pause':
                # Simulate natural pauses
                pause_time = random.uniform(3, 15)  # 3-15 seconds
                time.sleep(pause_time)
                browsing_actions.append({'action': 'pause', 'duration': pause_time})

        # Log the browsing session
        activity_log = ActivityLog(
            account_id=account_id,
            action='browsing_simulation',
            details={
                'duration_minutes': duration_minutes,
                'actions_performed': len(browsing_actions),
                'total_time': time.time() - start_time,
                'actions': browsing_actions[:10]  # Store first 10 actions to avoid large logs
            }
        )
        db.add(activity_log)
        db.commit()
        db.close()

        logger.info(f"Browsing simulation completed for account {account_id}")
        return {
            'status': 'success',
            'duration_minutes': duration_minutes,
            'actions_performed': len(browsing_actions),
            'total_time': time.time() - start_time
        }

    except Exception as e:
        logger.error(f"Error in browsing simulation: {e}")
        if 'db' in locals():
            db.close()
        return {'status': 'error', 'message': str(e)}

@celery_app.task(bind=True, max_retries=3)
def intelligent_engagement_session(self, account_id: int, target_subreddit: str = None, session_duration: int = 60) -> Dict[str, Any]:
    """Perform an intelligent engagement session with realistic human behavior"""
    try:
        logger.info(f"Starting intelligent engagement session for account {account_id}")

        # Safety checks
        if not is_account_safe(account_id):
            return {'status': 'skipped', 'reason': 'account_not_safe'}

        # Start with browsing simulation
        browsing_result = simulate_browsing_behavior(account_id, duration_minutes=random.randint(5, 15))
        if browsing_result['status'] != 'success':
            return browsing_result

        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            return {'status': 'error', 'message': 'Account not found'}

        settings = account.automation_settings
        if not settings:
            return {'status': 'error', 'message': 'No automation settings found'}

        session_actions = []
        session_start = time.time()
        session_end = session_start + (session_duration * 60)

        # Determine target subreddits
        if target_subreddit:
            target_subreddits = [target_subreddit]
        else:
            target_subreddits = settings.selected_subreddits or ['AskReddit', 'funny', 'todayilearned']

        while time.time() < session_end:
            # Choose random action based on settings and probabilities
            possible_actions = []

            if settings.auto_upvote_enabled and check_rate_limits(account_id, 'upvote'):
                possible_actions.extend(['upvote'] * 40)  # Higher probability

            if settings.auto_comment_enabled and check_rate_limits(account_id, 'comment'):
                possible_actions.extend(['comment'] * 20)  # Medium probability

            if settings.auto_post_enabled and check_rate_limits(account_id, 'post'):
                possible_actions.extend(['post'] * 5)  # Lower probability

            # Add browsing actions to make it more realistic
            possible_actions.extend(['browse'] * 35)

            if not possible_actions:
                logger.info("No actions available, ending session")
                break

            action = random.choice(possible_actions)
            subreddit = random.choice(target_subreddits)

            try:
                if action == 'upvote':
                    # Simulate finding a post to upvote
                    delay = simulate_human_delay('upvote')
                    time.sleep(delay)

                    # For demo purposes, we'll simulate the upvote action
                    # In real implementation, you'd get actual posts from Reddit
                    fake_post_id = f"demo_post_{random.randint(1000, 9999)}"
                    result = automated_upvote.delay(account_id, fake_post_id, subreddit)

                    session_actions.append({
                        'action': 'upvote',
                        'subreddit': subreddit,
                        'delay': delay,
                        'task_id': result.id
                    })

                elif action == 'comment':
                    # Simulate finding a post to comment on
                    delay = simulate_human_delay('comment')
                    time.sleep(delay)

                    # Generate a simple comment (in real implementation, use AI/templates)
                    comments = [
                        "Great post!", "Thanks for sharing!", "Interesting perspective.",
                        "I agree with this.", "This is helpful.", "Good point!"
                    ]
                    comment_text = random.choice(comments)
                    fake_post_id = f"demo_post_{random.randint(1000, 9999)}"

                    result = automated_comment.delay(account_id, fake_post_id, comment_text, subreddit)

                    session_actions.append({
                        'action': 'comment',
                        'subreddit': subreddit,
                        'comment_text': comment_text,
                        'delay': delay,
                        'task_id': result.id
                    })

                elif action == 'post':
                    # Simulate creating a post
                    delay = simulate_human_delay('post')
                    time.sleep(delay)

                    # Generate a simple post (in real implementation, use AI/templates)
                    titles = [
                        "What's your opinion on this?",
                        "Thought you might find this interesting",
                        "Quick question for the community",
                        "Sharing my experience with..."
                    ]
                    title = random.choice(titles)
                    content = "This is a demo post content. In a real implementation, this would be generated based on the subreddit and user preferences."

                    result = automated_post.delay(account_id, subreddit, title, content)

                    session_actions.append({
                        'action': 'post',
                        'subreddit': subreddit,
                        'title': title,
                        'delay': delay,
                        'task_id': result.id
                    })

                elif action == 'browse':
                    # Simulate browsing without taking action
                    browse_time = random.uniform(10, 60)
                    time.sleep(browse_time)

                    session_actions.append({
                        'action': 'browse',
                        'subreddit': subreddit,
                        'duration': browse_time
                    })

                # Random break chance
                if random.random() < 0.1:  # 10% chance of taking a break
                    break_duration = random.uniform(60, 300)  # 1-5 minute break
                    logger.info(f"Taking break for {break_duration:.1f} seconds")
                    time.sleep(break_duration)

                    session_actions.append({
                        'action': 'break',
                        'duration': break_duration
                    })

            except Exception as e:
                logger.error(f"Error during session action {action}: {e}")
                session_actions.append({
                    'action': action,
                    'error': str(e)
                })

        # Log the session
        activity_log = ActivityLog(
            account_id=account_id,
            action='intelligent_engagement_session',
            details={
                'session_duration_minutes': session_duration,
                'actual_duration': (time.time() - session_start) / 60,
                'actions_performed': len(session_actions),
                'target_subreddits': target_subreddits,
                'actions': session_actions[:20]  # Store first 20 actions
            }
        )
        db.add(activity_log)
        db.commit()
        db.close()

        logger.info(f"Intelligent engagement session completed for account {account_id}")
        return {
            'status': 'success',
            'account_id': account_id,
            'session_duration_minutes': session_duration,
            'actions_performed': len(session_actions),
            'target_subreddits': target_subreddits
        }

    except Exception as e:
        logger.error(f"Error in intelligent engagement session: {e}")
        if 'db' in locals():
            db.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

        return {'status': 'error', 'message': str(e)}

def get_adaptive_delay(account_id: int, action_type: str, base_delay: float) -> float:
    """Calculate adaptive delay based on account history and current conditions"""
    try:
        # Get recent activity for this account
        recent_failures = get_action_counts(account_id, action_type)['recent_failures']

        # Increase delay if there have been recent failures
        failure_multiplier = 1 + (recent_failures * 0.5)  # 50% increase per failure

        # Get current activity multiplier
        activity_multiplier = get_activity_multiplier()

        # Combine factors
        adaptive_delay = base_delay * failure_multiplier * activity_multiplier

        # Add random variation (±20%)
        variation = random.uniform(0.8, 1.2)
        adaptive_delay *= variation

        # Ensure minimum delay
        min_delay = HUMAN_DELAYS['min_action_delay']
        adaptive_delay = max(adaptive_delay, min_delay)

        logger.debug(f"Adaptive delay for {action_type}: {adaptive_delay:.1f}s "
                    f"(base: {base_delay:.1f}s, failures: {recent_failures}, "
                    f"activity: {activity_multiplier:.2f})")

        return adaptive_delay

    except Exception as e:
        logger.error(f"Error calculating adaptive delay: {e}")
        return base_delay

def analyze_engagement_patterns(account_id: int, days: int = 30) -> Dict[str, Any]:
    """Analyze engagement patterns to optimize future automation"""
    try:
        db = SessionLocal()

        # Get engagement data for analysis period
        start_date = datetime.utcnow() - timedelta(days=days)
        engagement_logs = db.query(EngagementLog).filter(
            EngagementLog.account_id == account_id,
            EngagementLog.timestamp >= start_date
        ).all()

        if not engagement_logs:
            return {'status': 'no_data', 'message': 'No engagement data found'}

        # Analyze by hour of day
        hourly_stats = {}
        for hour in range(24):
            hourly_stats[hour] = {'total': 0, 'successful': 0, 'failed': 0}

        # Analyze by subreddit
        subreddit_stats = {}

        # Analyze by action type
        action_stats = {}

        for log in engagement_logs:
            hour = log.timestamp.hour
            subreddit = log.subreddit
            action = log.action_type

            # Update hourly stats
            hourly_stats[hour]['total'] += 1
            if log.status == 'success':
                hourly_stats[hour]['successful'] += 1
            else:
                hourly_stats[hour]['failed'] += 1

            # Update subreddit stats
            if subreddit not in subreddit_stats:
                subreddit_stats[subreddit] = {'total': 0, 'successful': 0, 'failed': 0}
            subreddit_stats[subreddit]['total'] += 1
            if log.status == 'success':
                subreddit_stats[subreddit]['successful'] += 1
            else:
                subreddit_stats[subreddit]['failed'] += 1

            # Update action stats
            if action not in action_stats:
                action_stats[action] = {'total': 0, 'successful': 0, 'failed': 0}
            action_stats[action]['total'] += 1
            if log.status == 'success':
                action_stats[action]['successful'] += 1
            else:
                action_stats[action]['failed'] += 1

        # Calculate success rates
        for hour_data in hourly_stats.values():
            if hour_data['total'] > 0:
                hour_data['success_rate'] = hour_data['successful'] / hour_data['total']
            else:
                hour_data['success_rate'] = 0

        for subreddit_data in subreddit_stats.values():
            if subreddit_data['total'] > 0:
                subreddit_data['success_rate'] = subreddit_data['successful'] / subreddit_data['total']
            else:
                subreddit_data['success_rate'] = 0

        for action_data in action_stats.values():
            if action_data['total'] > 0:
                action_data['success_rate'] = action_data['successful'] / action_data['total']
            else:
                action_data['success_rate'] = 0

        # Find best performing times and subreddits
        best_hours = sorted(
            [(hour, data['success_rate']) for hour, data in hourly_stats.items() if data['total'] >= 3],
            key=lambda x: x[1],
            reverse=True
        )[:5]

        best_subreddits = sorted(
            [(subreddit, data['success_rate']) for subreddit, data in subreddit_stats.items() if data['total'] >= 3],
            key=lambda x: x[1],
            reverse=True
        )[:10]

        db.close()

        return {
            'status': 'success',
            'analysis_period_days': days,
            'total_engagements': len(engagement_logs),
            'hourly_stats': hourly_stats,
            'subreddit_stats': subreddit_stats,
            'action_stats': action_stats,
            'best_hours': best_hours,
            'best_subreddits': best_subreddits,
            'recommendations': {
                'optimal_hours': [hour for hour, _ in best_hours],
                'recommended_subreddits': [subreddit for subreddit, _ in best_subreddits],
                'avoid_hours': [hour for hour, data in hourly_stats.items()
                              if data['total'] >= 3 and data['success_rate'] < 0.5]
            }
        }

    except Exception as e:
        logger.error(f"Error analyzing engagement patterns: {e}")
        if 'db' in locals():
            db.close()
        return {'status': 'error', 'message': str(e)}

@celery_app.task
def optimize_automation_settings(account_id: int) -> Dict[str, Any]:
    """Optimize automation settings based on performance analysis"""
    try:
        logger.info(f"Optimizing automation settings for account {account_id}")

        # Analyze recent performance
        analysis = analyze_engagement_patterns(account_id, days=14)
        if analysis['status'] != 'success':
            return analysis

        db = SessionLocal()
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account or not account.automation_settings:
            return {'status': 'error', 'message': 'Account or settings not found'}

        settings = account.automation_settings
        recommendations = analysis['recommendations']

        # Update engagement schedule based on optimal hours
        if recommendations['optimal_hours']:
            new_schedule = {
                'active_hours': [str(hour) for hour in recommendations['optimal_hours']],
                'avoid_hours': [str(hour) for hour in recommendations['avoid_hours']],
                'last_optimized': datetime.utcnow().isoformat()
            }
            settings.engagement_schedule = new_schedule

        # Update selected subreddits if we have good data
        if recommendations['recommended_subreddits'] and len(recommendations['recommended_subreddits']) >= 3:
            # Keep existing subreddits but prioritize high-performing ones
            current_subreddits = settings.selected_subreddits or []
            recommended = recommendations['recommended_subreddits'][:5]  # Top 5

            # Merge lists, prioritizing recommended ones
            new_subreddits = recommended + [s for s in current_subreddits if s not in recommended]
            settings.selected_subreddits = new_subreddits[:10]  # Limit to 10

        # Adjust daily limits based on success rates
        overall_success_rate = sum(
            data['successful'] for data in analysis['action_stats'].values()
        ) / max(sum(data['total'] for data in analysis['action_stats'].values()), 1)

        if overall_success_rate > 0.8:
            # High success rate, can be slightly more aggressive
            settings.max_daily_comments = min(settings.max_daily_comments + 5, 100)
            settings.max_daily_upvotes = min(settings.max_daily_upvotes + 50, 1000)
        elif overall_success_rate < 0.6:
            # Low success rate, be more conservative
            settings.max_daily_comments = max(settings.max_daily_comments - 5, 10)
            settings.max_daily_upvotes = max(settings.max_daily_upvotes - 50, 100)

        db.commit()
        db.close()

        logger.info(f"Automation settings optimized for account {account_id}")
        return {
            'status': 'success',
            'account_id': account_id,
            'overall_success_rate': overall_success_rate,
            'optimizations_applied': {
                'schedule_updated': bool(recommendations['optimal_hours']),
                'subreddits_updated': bool(recommendations['recommended_subreddits']),
                'limits_adjusted': True
            },
            'new_settings': {
                'max_daily_comments': settings.max_daily_comments,
                'max_daily_upvotes': settings.max_daily_upvotes,
                'selected_subreddits': settings.selected_subreddits,
                'engagement_schedule': settings.engagement_schedule
            }
        }

    except Exception as e:
        logger.error(f"Error optimizing automation settings: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return {'status': 'error', 'message': str(e)}
