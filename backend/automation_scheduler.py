"""
Intelligent automation scheduler for Reddit automation engine
Handles scheduling automation tasks based on human activity patterns and account-specific settings
"""
import random
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import json

from celery import current_task
from celery_worker import celery_app
from database import SessionLocal
from models import (
    RedditAccount, AutomationSettings, ActivityLog, EngagementLog
)
from safety_tasks import is_account_safe, check_adaptive_rate_limits
from automation_tasks import (
    automated_upvote, automated_comment, automated_post,
    intelligent_engagement_session, get_optimal_posting_time
)

logger = logging.getLogger(__name__)

@dataclass
class ScheduleSlot:
    """Represents a scheduled automation slot"""
    start_time: datetime
    end_time: datetime
    action_type: str
    priority: int
    account_id: int
    target_subreddit: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

@dataclass
class ActivityPattern:
    """Represents user activity patterns"""
    peak_hours: List[int]
    low_activity_hours: List[int]
    preferred_subreddits: List[str]
    avg_session_duration: int  # minutes
    break_frequency: float  # probability of taking breaks
    weekend_behavior: Dict[str, Any]

class AutomationScheduler:
    """Intelligent automation scheduler"""
    
    def __init__(self):
        self.default_patterns = {
            'casual_user': ActivityPattern(
                peak_hours=[9, 12, 18, 21],
                low_activity_hours=[1, 2, 3, 4, 5, 6],
                preferred_subreddits=['AskReddit', 'funny', 'todayilearned'],
                avg_session_duration=30,
                break_frequency=0.3,
                weekend_behavior={'more_active': True, 'later_start': True}
            ),
            'power_user': ActivityPattern(
                peak_hours=[8, 11, 14, 16, 19, 22],
                low_activity_hours=[2, 3, 4, 5],
                preferred_subreddits=['news', 'technology', 'science', 'politics'],
                avg_session_duration=60,
                break_frequency=0.2,
                weekend_behavior={'consistent': True}
            ),
            'night_owl': ActivityPattern(
                peak_hours=[22, 23, 0, 1, 2],
                low_activity_hours=[6, 7, 8, 9, 10, 11],
                preferred_subreddits=['gaming', 'movies', 'music'],
                avg_session_duration=45,
                break_frequency=0.25,
                weekend_behavior={'very_active': True}
            )
        }
    
    def analyze_account_pattern(self, account_id: int, days: int = 30) -> ActivityPattern:
        """Analyze account's historical activity to determine pattern"""
        try:
            db = SessionLocal()
            
            # Get historical activity
            start_date = datetime.utcnow() - timedelta(days=days)
            activities = db.query(ActivityLog).filter(
                ActivityLog.account_id == account_id,
                ActivityLog.timestamp >= start_date
            ).all()
            
            engagements = db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= start_date
            ).all()
            
            if not activities and not engagements:
                # No data, return casual user pattern
                db.close()
                return self.default_patterns['casual_user']
            
            # Analyze activity by hour
            hourly_activity = {}
            subreddit_frequency = {}
            session_durations = []
            
            all_activities = activities + engagements
            
            for activity in all_activities:
                hour = activity.timestamp.hour
                hourly_activity[hour] = hourly_activity.get(hour, 0) + 1
                
                # Track subreddit activity
                if hasattr(activity, 'subreddit') and activity.subreddit:
                    subreddit_frequency[activity.subreddit] = subreddit_frequency.get(activity.subreddit, 0) + 1
            
            # Determine peak hours (top 25% of activity)
            if hourly_activity:
                sorted_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)
                peak_count = max(1, len(sorted_hours) // 4)
                peak_hours = [hour for hour, _ in sorted_hours[:peak_count]]
                
                # Low activity hours (bottom 25%)
                low_count = max(1, len(sorted_hours) // 4)
                low_activity_hours = [hour for hour, _ in sorted_hours[-low_count:]]
            else:
                peak_hours = [9, 18, 21]
                low_activity_hours = [2, 3, 4, 5]
            
            # Get preferred subreddits
            preferred_subreddits = [
                subreddit for subreddit, _ in 
                sorted(subreddit_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
            ] if subreddit_frequency else ['AskReddit', 'funny']
            
            # Estimate session duration and break frequency
            avg_session_duration = random.randint(20, 60)  # Default range
            break_frequency = 0.25  # Default
            
            db.close()
            
            return ActivityPattern(
                peak_hours=peak_hours,
                low_activity_hours=low_activity_hours,
                preferred_subreddits=preferred_subreddits,
                avg_session_duration=avg_session_duration,
                break_frequency=break_frequency,
                weekend_behavior={'adaptive': True}
            )
            
        except Exception as e:
            logger.error(f"Error analyzing account pattern: {e}")
            if 'db' in locals():
                db.close()
            return self.default_patterns['casual_user']
    
    def generate_daily_schedule(self, account_id: int, target_date: datetime = None) -> List[ScheduleSlot]:
        """Generate daily automation schedule for an account"""
        try:
            if target_date is None:
                target_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            
            db = SessionLocal()
            account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
            if not account or not account.automation_settings:
                db.close()
                return []
            
            settings = account.automation_settings
            pattern = self.analyze_account_pattern(account_id)
            
            schedule_slots = []
            
            # Generate engagement sessions during peak hours
            for peak_hour in pattern.peak_hours:
                if random.random() < 0.7:  # 70% chance of activity during peak hours
                    session_start = target_date.replace(hour=peak_hour) + timedelta(
                        minutes=random.randint(0, 59)
                    )
                    
                    # Determine session duration
                    duration = random.randint(
                        pattern.avg_session_duration // 2,
                        pattern.avg_session_duration * 2
                    )
                    
                    session_end = session_start + timedelta(minutes=duration)
                    
                    # Choose target subreddit
                    target_subreddit = random.choice(
                        settings.selected_subreddits or pattern.preferred_subreddits
                    )
                    
                    schedule_slots.append(ScheduleSlot(
                        start_time=session_start,
                        end_time=session_end,
                        action_type='engagement_session',
                        priority=1,
                        account_id=account_id,
                        target_subreddit=target_subreddit,
                        parameters={'duration': duration}
                    ))
            
            # Add specific action slots based on settings
            if settings.auto_upvote_enabled:
                upvote_slots = self._generate_action_slots(
                    target_date, 'upvote', pattern, settings.max_daily_upvotes or 100
                )
                schedule_slots.extend(upvote_slots)
            
            if settings.auto_comment_enabled:
                comment_slots = self._generate_action_slots(
                    target_date, 'comment', pattern, settings.max_daily_comments or 20
                )
                schedule_slots.extend(comment_slots)
            
            if settings.auto_post_enabled:
                post_slots = self._generate_action_slots(
                    target_date, 'post', pattern, 5  # Max 5 posts per day
                )
                schedule_slots.extend(post_slots)
            
            # Sort by start time
            schedule_slots.sort(key=lambda x: x.start_time)
            
            db.close()
            return schedule_slots
            
        except Exception as e:
            logger.error(f"Error generating daily schedule: {e}")
            if 'db' in locals():
                db.close()
            return []
    
    def _generate_action_slots(self, target_date: datetime, action_type: str, 
                              pattern: ActivityPattern, max_count: int) -> List[ScheduleSlot]:
        """Generate specific action slots for a day"""
        slots = []
        
        # Distribute actions throughout the day, favoring peak hours
        action_count = random.randint(max_count // 4, max_count)
        
        for i in range(action_count):
            # Choose time based on pattern
            if random.random() < 0.6:  # 60% chance during peak hours
                hour = random.choice(pattern.peak_hours)
            else:
                # Avoid low activity hours
                available_hours = [h for h in range(24) if h not in pattern.low_activity_hours]
                hour = random.choice(available_hours)
            
            slot_time = target_date.replace(hour=hour) + timedelta(
                minutes=random.randint(0, 59),
                seconds=random.randint(0, 59)
            )
            
            # Add some randomness to avoid patterns
            slot_time += timedelta(minutes=random.randint(-15, 15))
            
            # Ensure slot is in the future
            if slot_time <= datetime.utcnow():
                slot_time += timedelta(days=1)
            
            slots.append(ScheduleSlot(
                start_time=slot_time,
                end_time=slot_time + timedelta(minutes=5),  # Short duration for individual actions
                action_type=action_type,
                priority=2,
                account_id=pattern.account_id if hasattr(pattern, 'account_id') else 0,
                target_subreddit=random.choice(pattern.preferred_subreddits)
            ))
        
        return slots

scheduler = AutomationScheduler()

# Celery Tasks for Automation Scheduling

@celery_app.task(bind=True, max_retries=3)
def schedule_daily_automation(self, account_id: int = None) -> Dict[str, Any]:
    """Schedule automation tasks for the day"""
    try:
        logger.info(f"Scheduling daily automation for account {account_id or 'all accounts'}")

        db = SessionLocal()

        if account_id:
            accounts = [db.query(RedditAccount).filter(RedditAccount.id == account_id).first()]
            accounts = [acc for acc in accounts if acc]
        else:
            # Get all accounts with automation enabled
            accounts = db.query(RedditAccount).join(AutomationSettings).filter(
                (AutomationSettings.auto_upvote_enabled == True) |
                (AutomationSettings.auto_comment_enabled == True) |
                (AutomationSettings.auto_post_enabled == True)
            ).all()

        scheduled_results = []

        for account in accounts:
            try:
                # Safety check
                if not is_account_safe(account.id):
                    logger.warning(f"Skipping scheduling for unsafe account {account.id}")
                    continue

                # Generate schedule for today and tomorrow
                today_schedule = scheduler.generate_daily_schedule(account.id)
                tomorrow = datetime.utcnow() + timedelta(days=1)
                tomorrow_schedule = scheduler.generate_daily_schedule(account.id, tomorrow)

                all_slots = today_schedule + tomorrow_schedule

                # Schedule tasks
                scheduled_tasks = []
                for slot in all_slots:
                    if slot.start_time <= datetime.utcnow():
                        continue  # Skip past slots

                    task_result = schedule_automation_slot.apply_async(
                        args=[slot.account_id, slot.action_type, slot.target_subreddit],
                        kwargs=slot.parameters or {},
                        eta=slot.start_time
                    )

                    scheduled_tasks.append({
                        'task_id': task_result.id,
                        'action_type': slot.action_type,
                        'scheduled_time': slot.start_time.isoformat(),
                        'target_subreddit': slot.target_subreddit
                    })

                # Log the scheduling
                activity_log = ActivityLog(
                    account_id=account.id,
                    action='daily_automation_scheduled',
                    details={
                        'slots_generated': len(all_slots),
                        'tasks_scheduled': len(scheduled_tasks),
                        'schedule_date': datetime.utcnow().isoformat(),
                        'scheduled_tasks': scheduled_tasks[:10]  # Store first 10 for reference
                    }
                )
                db.add(activity_log)

                scheduled_results.append({
                    'account_id': account.id,
                    'username': account.reddit_username,
                    'slots_generated': len(all_slots),
                    'tasks_scheduled': len(scheduled_tasks),
                    'status': 'success'
                })

            except Exception as e:
                logger.error(f"Error scheduling automation for account {account.id}: {e}")
                scheduled_results.append({
                    'account_id': account.id,
                    'username': account.reddit_username if account else 'unknown',
                    'status': 'error',
                    'error': str(e)
                })

        db.commit()
        db.close()

        successful_schedules = sum(1 for r in scheduled_results if r['status'] == 'success')
        logger.info(f"Daily automation scheduling completed: {successful_schedules}/{len(scheduled_results)} successful")

        return {
            'status': 'success',
            'accounts_processed': len(scheduled_results),
            'successful_schedules': successful_schedules,
            'results': scheduled_results
        }

    except Exception as e:
        logger.error(f"Error in daily automation scheduling: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

        return {'status': 'error', 'message': str(e)}

@celery_app.task(bind=True, max_retries=3)
def schedule_automation_slot(self, account_id: int, action_type: str, target_subreddit: str = None, **kwargs) -> Dict[str, Any]:
    """Execute a scheduled automation slot"""
    try:
        logger.info(f"Executing scheduled {action_type} for account {account_id}")

        # Final safety check before execution
        if not is_account_safe(account_id):
            logger.warning(f"Account {account_id} not safe for automation at execution time")
            return {'status': 'skipped', 'reason': 'account_not_safe'}

        # Check rate limits
        if not check_adaptive_rate_limits(account_id, action_type):
            logger.warning(f"Rate limits exceeded for {action_type} on account {account_id}")
            return {'status': 'skipped', 'reason': 'rate_limit_exceeded'}

        # Execute the appropriate action
        if action_type == 'engagement_session':
            duration = kwargs.get('duration', 30)
            result = intelligent_engagement_session.delay(account_id, target_subreddit, duration)

        elif action_type == 'upvote':
            # For demo purposes, generate a fake post ID
            fake_post_id = f"scheduled_upvote_{random.randint(1000, 9999)}"
            result = automated_upvote.delay(account_id, fake_post_id, target_subreddit or 'AskReddit')

        elif action_type == 'comment':
            # Generate a simple comment
            comments = [
                "Great post!", "Thanks for sharing!", "Interesting perspective.",
                "I agree with this.", "This is helpful.", "Good point!"
            ]
            comment_text = random.choice(comments)
            fake_post_id = f"scheduled_comment_{random.randint(1000, 9999)}"
            result = automated_comment.delay(account_id, fake_post_id, comment_text, target_subreddit or 'AskReddit')

        elif action_type == 'post':
            # Generate a simple post
            titles = [
                "What's your opinion on this?",
                "Thought you might find this interesting",
                "Quick question for the community"
            ]
            title = random.choice(titles)
            content = "This is a scheduled post. In a real implementation, this would be generated based on the subreddit and user preferences."
            result = automated_post.delay(account_id, target_subreddit or 'test', title, content)

        else:
            return {'status': 'error', 'message': f'Unknown action type: {action_type}'}

        logger.info(f"Scheduled {action_type} task queued for account {account_id}: {result.id}")
        return {
            'status': 'queued',
            'account_id': account_id,
            'action_type': action_type,
            'task_id': result.id,
            'target_subreddit': target_subreddit
        }

    except Exception as e:
        logger.error(f"Error executing scheduled automation slot: {e}")

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))

        return {'status': 'error', 'message': str(e)}

@celery_app.task
def optimize_schedules() -> Dict[str, Any]:
    """Optimize automation schedules based on performance data"""
    try:
        logger.info("Optimizing automation schedules")

        db = SessionLocal()
        accounts = db.query(RedditAccount).join(AutomationSettings).all()

        optimization_results = []

        for account in accounts:
            try:
                # Analyze recent performance
                from automation_tasks import analyze_engagement_patterns
                analysis = analyze_engagement_patterns(account.id, days=7)

                if analysis['status'] == 'success':
                    # Update automation settings based on analysis
                    settings = account.automation_settings
                    recommendations = analysis['recommendations']

                    # Update engagement schedule
                    if recommendations['optimal_hours']:
                        new_schedule = {
                            'active_hours': [str(hour) for hour in recommendations['optimal_hours']],
                            'avoid_hours': [str(hour) for hour in recommendations['avoid_hours']],
                            'last_optimized': datetime.utcnow().isoformat()
                        }
                        settings.engagement_schedule = new_schedule

                    optimization_results.append({
                        'account_id': account.id,
                        'optimizations_applied': True,
                        'optimal_hours': recommendations['optimal_hours'],
                        'recommended_subreddits': recommendations['recommended_subreddits'][:5]
                    })
                else:
                    optimization_results.append({
                        'account_id': account.id,
                        'optimizations_applied': False,
                        'reason': 'insufficient_data'
                    })

            except Exception as e:
                logger.error(f"Error optimizing schedule for account {account.id}: {e}")
                optimization_results.append({
                    'account_id': account.id,
                    'optimizations_applied': False,
                    'error': str(e)
                })

        db.commit()
        db.close()

        optimized_count = sum(1 for r in optimization_results if r.get('optimizations_applied'))
        logger.info(f"Schedule optimization completed: {optimized_count}/{len(optimization_results)} accounts optimized")

        return {
            'status': 'success',
            'accounts_processed': len(optimization_results),
            'optimized_count': optimized_count,
            'results': optimization_results
        }

    except Exception as e:
        logger.error(f"Error optimizing schedules: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return {'status': 'error', 'message': str(e)}
