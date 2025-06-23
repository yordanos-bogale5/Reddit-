"""
Analytics engine for Reddit automation dashboard
Provides comprehensive analytics calculations and aggregations
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from sqlalchemy import func, and_, or_
from sqlalchemy.orm import Session

from database import SessionLocal
from models import (
    RedditAccount, KarmaLog, EngagementLog, ActivityLog, 
    SubredditPerformance, AccountHealth, AutomationSettings
)

logger = logging.getLogger(__name__)

@dataclass
class KarmaGrowthMetrics:
    """Karma growth analytics data"""
    total_karma: int
    post_karma: int
    comment_karma: int
    growth_rate_daily: float
    growth_rate_weekly: float
    growth_rate_monthly: float
    peak_growth_day: Optional[str]
    trend_direction: str  # 'up', 'down', 'stable'

@dataclass
class EngagementMetrics:
    """Engagement analytics data"""
    total_actions: int
    successful_actions: int
    failed_actions: int
    success_rate: float
    actions_by_type: Dict[str, int]
    actions_by_subreddit: Dict[str, int]
    hourly_distribution: Dict[int, int]
    daily_average: float

@dataclass
class PerformanceMetrics:
    """Performance analytics data"""
    automation_efficiency: float
    average_response_time: float
    error_rate: float
    uptime_percentage: float
    most_active_hours: List[int]
    best_performing_subreddits: List[str]

class AnalyticsEngine:
    """Comprehensive analytics engine"""
    
    def __init__(self):
        self.db = SessionLocal()
    
    def __del__(self):
        if hasattr(self, 'db'):
            self.db.close()
    
    def get_karma_growth_analytics(self, account_id: int, days: int = 30) -> KarmaGrowthMetrics:
        """Calculate karma growth analytics for an account"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get karma logs for the period
            karma_logs = self.db.query(KarmaLog).filter(
                KarmaLog.account_id == account_id,
                KarmaLog.timestamp >= start_date
            ).order_by(KarmaLog.timestamp).all()
            
            if not karma_logs:
                return KarmaGrowthMetrics(
                    total_karma=0, post_karma=0, comment_karma=0,
                    growth_rate_daily=0, growth_rate_weekly=0, growth_rate_monthly=0,
                    peak_growth_day=None, trend_direction='stable'
                )
            
            # Current karma
            latest_log = karma_logs[-1]
            total_karma = latest_log.total_karma
            post_karma = latest_log.post_karma
            comment_karma = latest_log.comment_karma
            
            # Calculate growth rates
            if len(karma_logs) > 1:
                first_log = karma_logs[0]
                karma_change = total_karma - first_log.total_karma
                time_diff_days = (latest_log.timestamp - first_log.timestamp).days
                
                if time_diff_days > 0:
                    growth_rate_daily = karma_change / time_diff_days
                    growth_rate_weekly = growth_rate_daily * 7
                    growth_rate_monthly = growth_rate_daily * 30
                else:
                    growth_rate_daily = growth_rate_weekly = growth_rate_monthly = 0
            else:
                growth_rate_daily = growth_rate_weekly = growth_rate_monthly = 0
            
            # Find peak growth day
            peak_growth_day = None
            max_daily_growth = 0
            
            for i in range(1, len(karma_logs)):
                daily_growth = karma_logs[i].total_karma - karma_logs[i-1].total_karma
                if daily_growth > max_daily_growth:
                    max_daily_growth = daily_growth
                    peak_growth_day = karma_logs[i].timestamp.strftime('%Y-%m-%d')
            
            # Determine trend direction
            if len(karma_logs) >= 3:
                recent_trend = sum(karma_logs[i].total_karma - karma_logs[i-1].total_karma 
                                 for i in range(-3, 0) if i < len(karma_logs))
                if recent_trend > 5:
                    trend_direction = 'up'
                elif recent_trend < -5:
                    trend_direction = 'down'
                else:
                    trend_direction = 'stable'
            else:
                trend_direction = 'stable'
            
            return KarmaGrowthMetrics(
                total_karma=total_karma,
                post_karma=post_karma,
                comment_karma=comment_karma,
                growth_rate_daily=growth_rate_daily,
                growth_rate_weekly=growth_rate_weekly,
                growth_rate_monthly=growth_rate_monthly,
                peak_growth_day=peak_growth_day,
                trend_direction=trend_direction
            )
            
        except Exception as e:
            logger.error(f"Error calculating karma growth analytics: {e}")
            return KarmaGrowthMetrics(
                total_karma=0, post_karma=0, comment_karma=0,
                growth_rate_daily=0, growth_rate_weekly=0, growth_rate_monthly=0,
                peak_growth_day=None, trend_direction='stable'
            )
    
    def get_engagement_analytics(self, account_id: int, days: int = 30) -> EngagementMetrics:
        """Calculate engagement analytics for an account"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get engagement logs for the period
            engagement_logs = self.db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= start_date
            ).all()
            
            if not engagement_logs:
                return EngagementMetrics(
                    total_actions=0, successful_actions=0, failed_actions=0,
                    success_rate=0, actions_by_type={}, actions_by_subreddit={},
                    hourly_distribution={}, daily_average=0
                )
            
            # Basic metrics
            total_actions = len(engagement_logs)
            successful_actions = sum(1 for log in engagement_logs if log.status == 'success')
            failed_actions = total_actions - successful_actions
            success_rate = successful_actions / total_actions if total_actions > 0 else 0
            
            # Actions by type
            actions_by_type = {}
            for log in engagement_logs:
                action_type = log.action_type
                actions_by_type[action_type] = actions_by_type.get(action_type, 0) + 1
            
            # Actions by subreddit
            actions_by_subreddit = {}
            for log in engagement_logs:
                if log.subreddit:
                    subreddit = log.subreddit
                    actions_by_subreddit[subreddit] = actions_by_subreddit.get(subreddit, 0) + 1
            
            # Hourly distribution
            hourly_distribution = {}
            for log in engagement_logs:
                hour = log.timestamp.hour
                hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1
            
            # Daily average
            daily_average = total_actions / days if days > 0 else 0
            
            return EngagementMetrics(
                total_actions=total_actions,
                successful_actions=successful_actions,
                failed_actions=failed_actions,
                success_rate=success_rate,
                actions_by_type=actions_by_type,
                actions_by_subreddit=actions_by_subreddit,
                hourly_distribution=hourly_distribution,
                daily_average=daily_average
            )
            
        except Exception as e:
            logger.error(f"Error calculating engagement analytics: {e}")
            return EngagementMetrics(
                total_actions=0, successful_actions=0, failed_actions=0,
                success_rate=0, actions_by_type={}, actions_by_subreddit={},
                hourly_distribution={}, daily_average=0
            )
    
    def get_performance_analytics(self, account_id: int, days: int = 30) -> PerformanceMetrics:
        """Calculate performance analytics for an account"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get activity logs for the period
            activity_logs = self.db.query(ActivityLog).filter(
                ActivityLog.account_id == account_id,
                ActivityLog.timestamp >= start_date
            ).all()
            
            engagement_logs = self.db.query(EngagementLog).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= start_date
            ).all()
            
            # Calculate automation efficiency
            total_automated_actions = len([log for log in activity_logs 
                                         if 'automated' in log.action.lower()])
            successful_automated = len([log for log in engagement_logs 
                                      if log.status == 'success'])
            
            automation_efficiency = (successful_automated / total_automated_actions 
                                   if total_automated_actions > 0 else 0)
            
            # Calculate error rate
            total_actions = len(engagement_logs)
            failed_actions = len([log for log in engagement_logs if log.status == 'failed'])
            error_rate = failed_actions / total_actions if total_actions > 0 else 0
            
            # Most active hours
            hourly_activity = {}
            for log in engagement_logs:
                hour = log.timestamp.hour
                hourly_activity[hour] = hourly_activity.get(hour, 0) + 1
            
            most_active_hours = sorted(hourly_activity.keys(), 
                                     key=lambda h: hourly_activity[h], reverse=True)[:3]
            
            # Best performing subreddits
            subreddit_performance = {}
            for log in engagement_logs:
                if log.subreddit and log.status == 'success':
                    subreddit = log.subreddit
                    subreddit_performance[subreddit] = subreddit_performance.get(subreddit, 0) + 1
            
            best_performing_subreddits = sorted(subreddit_performance.keys(),
                                              key=lambda s: subreddit_performance[s], 
                                              reverse=True)[:5]
            
            return PerformanceMetrics(
                automation_efficiency=automation_efficiency,
                average_response_time=2.5,  # Placeholder - would need timing data
                error_rate=error_rate,
                uptime_percentage=0.95,  # Placeholder - would need uptime monitoring
                most_active_hours=most_active_hours,
                best_performing_subreddits=best_performing_subreddits
            )
            
        except Exception as e:
            logger.error(f"Error calculating performance analytics: {e}")
            return PerformanceMetrics(
                automation_efficiency=0, average_response_time=0, error_rate=0,
                uptime_percentage=0, most_active_hours=[], best_performing_subreddits=[]
            )
    
    def get_subreddit_analytics(self, account_id: int, days: int = 30) -> Dict[str, Any]:
        """Get detailed subreddit performance analytics"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            # Get engagement data by subreddit
            engagement_data = self.db.query(
                EngagementLog.subreddit,
                func.count(EngagementLog.id).label('total_actions'),
                func.sum(func.case([(EngagementLog.status == 'success', 1)], else_=0)).label('successful_actions'),
                func.avg(func.case([(EngagementLog.status == 'success', 1)], else_=0)).label('success_rate')
            ).filter(
                EngagementLog.account_id == account_id,
                EngagementLog.timestamp >= start_date,
                EngagementLog.subreddit.isnot(None)
            ).group_by(EngagementLog.subreddit).all()
            
            subreddit_stats = {}
            for row in engagement_data:
                subreddit_stats[row.subreddit] = {
                    'total_actions': row.total_actions,
                    'successful_actions': row.successful_actions or 0,
                    'success_rate': float(row.success_rate or 0),
                    'engagement_score': (row.successful_actions or 0) * float(row.success_rate or 0)
                }
            
            return {
                'subreddit_performance': subreddit_stats,
                'top_subreddits': sorted(subreddit_stats.keys(), 
                                       key=lambda s: subreddit_stats[s]['engagement_score'], 
                                       reverse=True)[:10],
                'total_subreddits': len(subreddit_stats)
            }
            
        except Exception as e:
            logger.error(f"Error calculating subreddit analytics: {e}")
            return {'subreddit_performance': {}, 'top_subreddits': [], 'total_subreddits': 0}

    def get_time_series_data(self, account_id: int, metric: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get time series data for charts"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)

            if metric == 'karma':
                # Get karma over time
                karma_logs = self.db.query(KarmaLog).filter(
                    KarmaLog.account_id == account_id,
                    KarmaLog.timestamp >= start_date
                ).order_by(KarmaLog.timestamp).all()

                return [
                    {
                        'date': log.timestamp.strftime('%Y-%m-%d'),
                        'total_karma': log.total_karma,
                        'post_karma': log.post_karma,
                        'comment_karma': log.comment_karma
                    }
                    for log in karma_logs
                ]

            elif metric == 'engagement':
                # Get daily engagement counts
                daily_engagement = self.db.query(
                    func.date(EngagementLog.timestamp).label('date'),
                    func.count(EngagementLog.id).label('total_actions'),
                    func.sum(func.case([(EngagementLog.status == 'success', 1)], else_=0)).label('successful_actions')
                ).filter(
                    EngagementLog.account_id == account_id,
                    EngagementLog.timestamp >= start_date
                ).group_by(func.date(EngagementLog.timestamp)).all()

                return [
                    {
                        'date': row.date.strftime('%Y-%m-%d'),
                        'total_actions': row.total_actions,
                        'successful_actions': row.successful_actions or 0,
                        'success_rate': (row.successful_actions or 0) / row.total_actions if row.total_actions > 0 else 0
                    }
                    for row in daily_engagement
                ]

            elif metric == 'activity':
                # Get daily activity counts
                daily_activity = self.db.query(
                    func.date(ActivityLog.timestamp).label('date'),
                    func.count(ActivityLog.id).label('activity_count')
                ).filter(
                    ActivityLog.account_id == account_id,
                    ActivityLog.timestamp >= start_date
                ).group_by(func.date(ActivityLog.timestamp)).all()

                return [
                    {
                        'date': row.date.strftime('%Y-%m-%d'),
                        'activity_count': row.activity_count
                    }
                    for row in daily_activity
                ]

            return []

        except Exception as e:
            logger.error(f"Error getting time series data for {metric}: {e}")
            return []

    def get_dashboard_summary(self, account_id: int = None) -> Dict[str, Any]:
        """Get dashboard summary statistics"""
        try:
            if account_id:
                accounts = [self.db.query(RedditAccount).filter(RedditAccount.id == account_id).first()]
                accounts = [acc for acc in accounts if acc]
            else:
                accounts = self.db.query(RedditAccount).all()

            summary = {
                'total_accounts': len(accounts),
                'total_karma': 0,
                'total_actions_today': 0,
                'success_rate_today': 0,
                'active_automations': 0,
                'alerts_count': 0,
                'top_performing_account': None,
                'recent_activity': []
            }

            today = datetime.utcnow().date()

            for account in accounts:
                # Get latest karma
                latest_karma = self.db.query(KarmaLog).filter(
                    KarmaLog.account_id == account.id
                ).order_by(KarmaLog.timestamp.desc()).first()

                if latest_karma:
                    summary['total_karma'] += latest_karma.total_karma

                # Get today's actions
                today_actions = self.db.query(EngagementLog).filter(
                    EngagementLog.account_id == account.id,
                    func.date(EngagementLog.timestamp) == today
                ).all()

                summary['total_actions_today'] += len(today_actions)

                # Check if automation is active
                if account.automation_settings and (
                    account.automation_settings.auto_upvote_enabled or
                    account.automation_settings.auto_comment_enabled or
                    account.automation_settings.auto_post_enabled
                ):
                    summary['active_automations'] += 1

            # Calculate overall success rate for today
            if summary['total_actions_today'] > 0:
                successful_today = self.db.query(EngagementLog).filter(
                    func.date(EngagementLog.timestamp) == today,
                    EngagementLog.status == 'success'
                ).count()
                summary['success_rate_today'] = successful_today / summary['total_actions_today']

            # Get recent activity
            recent_activities = self.db.query(ActivityLog).filter(
                ActivityLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
            ).order_by(ActivityLog.timestamp.desc()).limit(10).all()

            summary['recent_activity'] = [
                {
                    'account_id': activity.account_id,
                    'action': activity.action,
                    'timestamp': activity.timestamp.isoformat(),
                    'details': activity.details
                }
                for activity in recent_activities
            ]

            return summary

        except Exception as e:
            logger.error(f"Error getting dashboard summary: {e}")
            return {
                'total_accounts': 0, 'total_karma': 0, 'total_actions_today': 0,
                'success_rate_today': 0, 'active_automations': 0, 'alerts_count': 0,
                'top_performing_account': None, 'recent_activity': []
            }

    def get_comparative_analytics(self, account_ids: List[int], days: int = 30) -> Dict[str, Any]:
        """Get comparative analytics between multiple accounts"""
        try:
            comparison_data = {}

            for account_id in account_ids:
                account = self.db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
                if not account:
                    continue

                karma_metrics = self.get_karma_growth_analytics(account_id, days)
                engagement_metrics = self.get_engagement_analytics(account_id, days)
                performance_metrics = self.get_performance_analytics(account_id, days)

                comparison_data[account_id] = {
                    'username': account.reddit_username,
                    'karma_growth_rate': karma_metrics.growth_rate_daily,
                    'total_karma': karma_metrics.total_karma,
                    'success_rate': engagement_metrics.success_rate,
                    'total_actions': engagement_metrics.total_actions,
                    'automation_efficiency': performance_metrics.automation_efficiency,
                    'error_rate': performance_metrics.error_rate
                }

            # Calculate rankings
            rankings = {
                'karma_growth': sorted(comparison_data.items(),
                                     key=lambda x: x[1]['karma_growth_rate'], reverse=True),
                'success_rate': sorted(comparison_data.items(),
                                     key=lambda x: x[1]['success_rate'], reverse=True),
                'total_actions': sorted(comparison_data.items(),
                                      key=lambda x: x[1]['total_actions'], reverse=True),
                'automation_efficiency': sorted(comparison_data.items(),
                                              key=lambda x: x[1]['automation_efficiency'], reverse=True)
            }

            return {
                'accounts_data': comparison_data,
                'rankings': rankings,
                'summary': {
                    'best_karma_growth': rankings['karma_growth'][0] if rankings['karma_growth'] else None,
                    'best_success_rate': rankings['success_rate'][0] if rankings['success_rate'] else None,
                    'most_active': rankings['total_actions'][0] if rankings['total_actions'] else None,
                    'most_efficient': rankings['automation_efficiency'][0] if rankings['automation_efficiency'] else None
                }
            }

        except Exception as e:
            logger.error(f"Error getting comparative analytics: {e}")
            return {'accounts_data': {}, 'rankings': {}, 'summary': {}}

analytics_engine = AnalyticsEngine()
