"""
Safety monitoring dashboard for Reddit automation engine
Provides monitoring tasks, safety alerts, and automated responses to detected issues
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from celery import current_task
from celery_worker import celery_app
from database import SessionLocal
from models import (
    RedditAccount, AccountHealth, EngagementLog, ActivityLog, AutomationSettings
)
from safety_tasks import (
    is_account_safe, get_safety_status, comprehensive_shadowban_check,
    get_rate_limit_status, update_account_health
)

logger = logging.getLogger(__name__)

class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

@dataclass
class SafetyAlert:
    """Safety alert data structure"""
    account_id: int
    alert_type: str
    level: AlertLevel
    message: str
    details: Dict[str, Any]
    timestamp: datetime
    resolved: bool = False
    auto_action_taken: Optional[str] = None

class SafetyMonitor:
    """Safety monitoring and alerting system"""
    
    def __init__(self):
        self.alert_thresholds = {
            'shadowban_probability': 0.7,
            'trust_score_critical': 0.3,
            'trust_score_warning': 0.5,
            'failure_rate_critical': 0.8,
            'failure_rate_warning': 0.6,
            'consecutive_failures': 5,
            'rate_limit_violations': 3
        }
        
        self.auto_responses = {
            'shadowban_detected': 'pause_automation',
            'trust_score_critical': 'reduce_activity',
            'high_failure_rate': 'increase_delays',
            'rate_limit_violations': 'pause_automation',
            'login_issues': 'pause_automation'
        }
    
    def check_account_alerts(self, account_id: int) -> List[SafetyAlert]:
        """Check for safety alerts for a specific account"""
        alerts = []
        
        try:
            # Get comprehensive safety status
            safety_status = get_safety_status(account_id)
            if 'error' in safety_status:
                return alerts
            
            health_metrics = safety_status['health_metrics']
            rate_limits = safety_status['rate_limits']
            
            # Check shadowban status
            if health_metrics.get('shadowbanned'):
                alerts.append(SafetyAlert(
                    account_id=account_id,
                    alert_type='shadowban_detected',
                    level=AlertLevel.EMERGENCY,
                    message='Account appears to be shadowbanned',
                    details={'shadowban_status': True},
                    timestamp=datetime.utcnow()
                ))
            
            # Check trust score
            trust_score = health_metrics.get('trust_score', 0)
            if trust_score < self.alert_thresholds['trust_score_critical']:
                alerts.append(SafetyAlert(
                    account_id=account_id,
                    alert_type='trust_score_critical',
                    level=AlertLevel.CRITICAL,
                    message=f'Trust score critically low: {trust_score:.2f}',
                    details={'trust_score': trust_score},
                    timestamp=datetime.utcnow()
                ))
            elif trust_score < self.alert_thresholds['trust_score_warning']:
                alerts.append(SafetyAlert(
                    account_id=account_id,
                    alert_type='trust_score_warning',
                    level=AlertLevel.WARNING,
                    message=f'Trust score low: {trust_score:.2f}',
                    details={'trust_score': trust_score},
                    timestamp=datetime.utcnow()
                ))
            
            # Check login issues
            if health_metrics.get('login_issues'):
                alerts.append(SafetyAlert(
                    account_id=account_id,
                    alert_type='login_issues',
                    level=AlertLevel.CRITICAL,
                    message='Account experiencing login issues',
                    details={'login_issues': True},
                    timestamp=datetime.utcnow()
                ))
            
            # Check captcha triggers
            if health_metrics.get('captcha_triggered'):
                alerts.append(SafetyAlert(
                    account_id=account_id,
                    alert_type='captcha_triggered',
                    level=AlertLevel.WARNING,
                    message='Account triggering captchas frequently',
                    details={'captcha_triggered': True},
                    timestamp=datetime.utcnow()
                ))
            
            # Check rate limit violations
            rate_limit_violations = 0
            for action_type, limits in rate_limits.items():
                if not limits.get('can_perform') and limits.get('current_usage', {}).get('recent_failures', 0) > 0:
                    rate_limit_violations += 1
            
            if rate_limit_violations >= self.alert_thresholds['rate_limit_violations']:
                alerts.append(SafetyAlert(
                    account_id=account_id,
                    alert_type='rate_limit_violations',
                    level=AlertLevel.WARNING,
                    message=f'Multiple rate limit violations: {rate_limit_violations}',
                    details={'violations': rate_limit_violations, 'rate_limits': rate_limits},
                    timestamp=datetime.utcnow()
                ))
            
            # Check failure rates
            total_failures = sum(
                limits.get('current_usage', {}).get('recent_failures', 0)
                for limits in rate_limits.values()
            )
            total_actions = sum(
                limits.get('current_usage', {}).get('hourly_count', 0)
                for limits in rate_limits.values()
            )
            
            if total_actions > 0:
                failure_rate = total_failures / total_actions
                if failure_rate >= self.alert_thresholds['failure_rate_critical']:
                    alerts.append(SafetyAlert(
                        account_id=account_id,
                        alert_type='high_failure_rate',
                        level=AlertLevel.CRITICAL,
                        message=f'High failure rate: {failure_rate:.2%}',
                        details={'failure_rate': failure_rate, 'total_failures': total_failures, 'total_actions': total_actions},
                        timestamp=datetime.utcnow()
                    ))
                elif failure_rate >= self.alert_thresholds['failure_rate_warning']:
                    alerts.append(SafetyAlert(
                        account_id=account_id,
                        alert_type='moderate_failure_rate',
                        level=AlertLevel.WARNING,
                        message=f'Moderate failure rate: {failure_rate:.2%}',
                        details={'failure_rate': failure_rate, 'total_failures': total_failures, 'total_actions': total_actions},
                        timestamp=datetime.utcnow()
                    ))
            
            return alerts
            
        except Exception as e:
            logger.error(f"Error checking alerts for account {account_id}: {e}")
            return alerts
    
    def take_auto_action(self, alert: SafetyAlert) -> Dict[str, Any]:
        """Take automated action based on alert"""
        try:
            action = self.auto_responses.get(alert.alert_type)
            if not action:
                return {'action_taken': False, 'reason': 'no_auto_action_defined'}
            
            db = SessionLocal()
            account = db.query(RedditAccount).filter(RedditAccount.id == alert.account_id).first()
            if not account or not account.automation_settings:
                db.close()
                return {'action_taken': False, 'reason': 'account_or_settings_not_found'}
            
            settings = account.automation_settings
            
            if action == 'pause_automation':
                # Temporarily disable all automation
                settings.auto_upvote_enabled = False
                settings.auto_comment_enabled = False
                settings.auto_post_enabled = False
                
                action_details = {
                    'action': 'pause_automation',
                    'reason': alert.alert_type,
                    'timestamp': datetime.utcnow().isoformat(),
                    'alert_level': alert.level.value
                }
                
            elif action == 'reduce_activity':
                # Reduce daily limits by 50%
                settings.max_daily_comments = max(1, settings.max_daily_comments // 2)
                settings.max_daily_upvotes = max(10, settings.max_daily_upvotes // 2)
                
                action_details = {
                    'action': 'reduce_activity',
                    'new_comment_limit': settings.max_daily_comments,
                    'new_upvote_limit': settings.max_daily_upvotes,
                    'reason': alert.alert_type,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
            elif action == 'increase_delays':
                # Increase delays in engagement schedule
                schedule = settings.engagement_schedule or {}
                schedule['increased_delays'] = True
                schedule['delay_multiplier'] = 2.0
                schedule['modified_at'] = datetime.utcnow().isoformat()
                settings.engagement_schedule = schedule
                
                action_details = {
                    'action': 'increase_delays',
                    'delay_multiplier': 2.0,
                    'reason': alert.alert_type,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
            else:
                db.close()
                return {'action_taken': False, 'reason': 'unknown_action'}
            
            # Log the auto action
            activity_log = ActivityLog(
                account_id=alert.account_id,
                action='safety_auto_response',
                details=action_details
            )
            db.add(activity_log)
            
            db.commit()
            db.close()
            
            logger.warning(f"Auto action taken for account {alert.account_id}: {action} due to {alert.alert_type}")
            
            return {
                'action_taken': True,
                'action': action,
                'details': action_details,
                'alert_type': alert.alert_type,
                'alert_level': alert.level.value
            }
            
        except Exception as e:
            logger.error(f"Error taking auto action for alert: {e}")
            if 'db' in locals():
                db.rollback()
                db.close()
            return {'action_taken': False, 'error': str(e)}

safety_monitor = SafetyMonitor()

# Celery Tasks for Safety Monitoring

@celery_app.task(bind=True, max_retries=3)
def monitor_all_accounts(self) -> Dict[str, Any]:
    """Monitor all accounts for safety issues and generate alerts"""
    try:
        logger.info("Starting comprehensive safety monitoring for all accounts")

        db = SessionLocal()
        accounts = db.query(RedditAccount).all()

        monitoring_results = {
            'accounts_monitored': 0,
            'total_alerts': 0,
            'critical_alerts': 0,
            'auto_actions_taken': 0,
            'account_results': []
        }

        for account in accounts:
            try:
                # Check for alerts
                alerts = safety_monitor.check_account_alerts(account.id)

                # Take auto actions for critical alerts
                auto_actions = []
                for alert in alerts:
                    if alert.level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]:
                        action_result = safety_monitor.take_auto_action(alert)
                        if action_result.get('action_taken'):
                            auto_actions.append(action_result)
                            monitoring_results['auto_actions_taken'] += 1

                # Count alerts by severity
                critical_count = sum(1 for alert in alerts if alert.level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY])

                account_result = {
                    'account_id': account.id,
                    'username': account.reddit_username,
                    'alerts_count': len(alerts),
                    'critical_alerts': critical_count,
                    'auto_actions': len(auto_actions),
                    'status': 'critical' if critical_count > 0 else ('warning' if alerts else 'healthy')
                }

                monitoring_results['account_results'].append(account_result)
                monitoring_results['accounts_monitored'] += 1
                monitoring_results['total_alerts'] += len(alerts)
                monitoring_results['critical_alerts'] += critical_count

                # Log alerts to database
                if alerts:
                    alert_log = ActivityLog(
                        account_id=account.id,
                        action='safety_alerts_generated',
                        details={
                            'alerts_count': len(alerts),
                            'critical_alerts': critical_count,
                            'alert_types': [alert.alert_type for alert in alerts],
                            'auto_actions': auto_actions,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                    )
                    db.add(alert_log)

            except Exception as e:
                logger.error(f"Error monitoring account {account.id}: {e}")
                monitoring_results['account_results'].append({
                    'account_id': account.id,
                    'username': account.reddit_username,
                    'status': 'error',
                    'error': str(e)
                })

        db.commit()
        db.close()

        logger.info(f"Safety monitoring completed: {monitoring_results['accounts_monitored']} accounts, "
                   f"{monitoring_results['total_alerts']} alerts, {monitoring_results['auto_actions_taken']} auto actions")

        return {
            'status': 'success',
            'monitoring_results': monitoring_results
        }

    except Exception as e:
        logger.error(f"Error in comprehensive safety monitoring: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

        return {'status': 'error', 'message': str(e)}

@celery_app.task(bind=True, max_retries=3)
def generate_safety_report(self, account_id: int = None, days: int = 7) -> Dict[str, Any]:
    """Generate comprehensive safety report"""
    try:
        logger.info(f"Generating safety report for {'all accounts' if not account_id else f'account {account_id}'}")

        db = SessionLocal()

        if account_id:
            accounts = [db.query(RedditAccount).filter(RedditAccount.id == account_id).first()]
            accounts = [acc for acc in accounts if acc]
        else:
            accounts = db.query(RedditAccount).all()

        report = {
            'report_date': datetime.utcnow().isoformat(),
            'period_days': days,
            'accounts_analyzed': len(accounts),
            'summary': {
                'healthy_accounts': 0,
                'warning_accounts': 0,
                'critical_accounts': 0,
                'shadowbanned_accounts': 0,
                'total_alerts': 0
            },
            'account_details': []
        }

        for account in accounts:
            try:
                # Get safety status
                safety_status = get_safety_status(account.id)

                # Get recent alerts
                start_date = datetime.utcnow() - timedelta(days=days)
                recent_alerts = db.query(ActivityLog).filter(
                    ActivityLog.account_id == account.id,
                    ActivityLog.action == 'safety_alerts_generated',
                    ActivityLog.timestamp >= start_date
                ).all()

                # Analyze account health
                health_metrics = safety_status.get('health_metrics', {})
                is_shadowbanned = health_metrics.get('shadowbanned', False)
                trust_score = health_metrics.get('trust_score', 0)

                # Determine account status
                if is_shadowbanned:
                    account_status = 'critical'
                    report['summary']['shadowbanned_accounts'] += 1
                elif trust_score < 0.3:
                    account_status = 'critical'
                elif trust_score < 0.6:
                    account_status = 'warning'
                else:
                    account_status = 'healthy'

                # Count alerts
                total_alerts = sum(
                    len(log.details.get('alert_types', [])) for log in recent_alerts
                    if log.details and isinstance(log.details, dict)
                )

                account_detail = {
                    'account_id': account.id,
                    'username': account.reddit_username,
                    'status': account_status,
                    'health_metrics': health_metrics,
                    'recent_alerts': total_alerts,
                    'rate_limit_status': safety_status.get('rate_limits', {}),
                    'recommendations': []
                }

                # Generate recommendations
                if is_shadowbanned:
                    account_detail['recommendations'].append('Account appears shadowbanned - pause all automation')
                elif trust_score < 0.3:
                    account_detail['recommendations'].append('Trust score critical - reduce activity significantly')
                elif trust_score < 0.6:
                    account_detail['recommendations'].append('Trust score low - monitor closely and reduce activity')

                if health_metrics.get('login_issues'):
                    account_detail['recommendations'].append('Login issues detected - check credentials')

                if health_metrics.get('captcha_triggered'):
                    account_detail['recommendations'].append('Captcha triggers detected - slow down automation')

                report['account_details'].append(account_detail)
                report['summary']['total_alerts'] += total_alerts

                # Update summary counts
                if account_status == 'healthy':
                    report['summary']['healthy_accounts'] += 1
                elif account_status == 'warning':
                    report['summary']['warning_accounts'] += 1
                elif account_status == 'critical':
                    report['summary']['critical_accounts'] += 1

            except Exception as e:
                logger.error(f"Error analyzing account {account.id} for report: {e}")
                report['account_details'].append({
                    'account_id': account.id,
                    'username': account.reddit_username if account else 'unknown',
                    'status': 'error',
                    'error': str(e)
                })

        db.close()

        logger.info(f"Safety report generated: {report['summary']}")

        return {
            'status': 'success',
            'report': report
        }

    except Exception as e:
        logger.error(f"Error generating safety report: {e}")
        if 'db' in locals():
            db.close()

        if self.request.retries < self.max_retries:
            raise self.retry(countdown=300)

        return {'status': 'error', 'message': str(e)}

@celery_app.task
def cleanup_resolved_alerts(days_to_keep: int = 30) -> Dict[str, Any]:
    """Clean up old resolved alerts and logs"""
    try:
        logger.info(f"Cleaning up alerts and logs older than {days_to_keep} days")

        db = SessionLocal()
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)

        # Clean up old safety alert logs
        deleted_count = db.query(ActivityLog).filter(
            ActivityLog.action.in_(['safety_alerts_generated', 'safety_auto_response']),
            ActivityLog.timestamp < cutoff_date
        ).count()

        db.query(ActivityLog).filter(
            ActivityLog.action.in_(['safety_alerts_generated', 'safety_auto_response']),
            ActivityLog.timestamp < cutoff_date
        ).delete()

        db.commit()
        db.close()

        logger.info(f"Cleaned up {deleted_count} old safety logs")

        return {
            'status': 'success',
            'deleted_logs': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }

    except Exception as e:
        logger.error(f"Error cleaning up alerts: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return {'status': 'error', 'message': str(e)}
