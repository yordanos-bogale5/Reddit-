import os
from celery import Celery
from dotenv import load_dotenv
import logging

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    'reddit_automation',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
    include=['tasks', 'automation_tasks', 'safety_tasks', 'automation_scheduler', 'safety_monitor', 'error_recovery']
)

# Configure Celery
celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # Rate limiting configuration
    task_default_rate_limit='100/m',  # 100 tasks per minute default
    # Task routing
    task_routes={
        'automation_tasks.*': {'queue': 'automation'},
        'automation_scheduler.*': {'queue': 'scheduler'},
        'safety_tasks.*': {'queue': 'safety'},
        'safety_monitor.*': {'queue': 'monitoring'},
        'error_recovery.*': {'queue': 'recovery'},
        'tasks.*': {'queue': 'default'},
    },
    # Worker configuration for safety
    worker_disable_rate_limits=False,
    worker_send_task_events=True,
)

# Configure periodic tasks for automation engine
celery_app.conf.beat_schedule = {
    # Core automation scheduling
    'process-scheduled-automation': {
        'task': 'automation_tasks.process_scheduled_automation',
        'schedule': 60.0,  # Check every minute for scheduled tasks
    },
    # Safety monitoring
    'monitor-account-health': {
        'task': 'safety_tasks.monitor_account_health',
        'schedule': 300.0,  # Check every 5 minutes
    },
    'detect-shadowbans': {
        'task': 'safety_tasks.detect_shadowbans',
        'schedule': 3600.0,  # Check hourly
    },
    # Karma tracking
    'update-karma-snapshots': {
        'task': 'automation_tasks.update_karma_snapshots',
        'schedule': 1800.0,  # Every 30 minutes
    },
    # Cleanup and maintenance
    'cleanup-old-logs': {
        'task': 'tasks.cleanup_old_logs',
        'schedule': 86400.0,  # Run daily
        'kwargs': {'days_to_keep': 30}
    },
    # Rate limit reset
    'reset-daily-limits': {
        'task': 'safety_tasks.reset_daily_limits',
        'schedule': 86400.0,  # Reset daily at midnight
    },
    # Automation scheduling
    'schedule-daily-automation': {
        'task': 'automation_scheduler.schedule_daily_automation',
        'schedule': 21600.0,  # Every 6 hours
    },
    'optimize-schedules': {
        'task': 'automation_scheduler.optimize_schedules',
        'schedule': 604800.0,  # Weekly optimization
    },
    # Safety monitoring
    'monitor-all-accounts': {
        'task': 'safety_monitor.monitor_all_accounts',
        'schedule': 1800.0,  # Every 30 minutes
    },
    'generate-safety-report': {
        'task': 'safety_monitor.generate_safety_report',
        'schedule': 86400.0,  # Daily safety report
    },
    'cleanup-resolved-alerts': {
        'task': 'safety_monitor.cleanup_resolved_alerts',
        'schedule': 604800.0,  # Weekly cleanup
    },
    # Error recovery
    'analyze-error-patterns': {
        'task': 'error_recovery.analyze_error_patterns',
        'schedule': 86400.0,  # Daily error analysis
    },
    'reset-circuit-breakers': {
        'task': 'error_recovery.reset_circuit_breakers',
        'schedule': 43200.0,  # Reset circuit breakers every 12 hours
    },
    'cleanup-error-logs': {
        'task': 'error_recovery.cleanup_error_logs',
        'schedule': 604800.0,  # Weekly error log cleanup
    },
}

if __name__ == '__main__':
    celery_app.start()