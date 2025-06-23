"""
Comprehensive tests for safety monitor module
Tests safety alerts, automated responses, and monitoring dashboard functionality
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from safety_monitor import (
    SafetyMonitor, SafetyAlert, AlertLevel, safety_monitor
)
from models import RedditAccount, AccountHealth, ActivityLog

class TestSafetyAlerts:
    """Test safety alert generation and classification"""
    
    @pytest.fixture
    def mock_safety_status(self):
        """Mock safety status data"""
        return {
            'account_id': 1,
            'username': 'test_user',
            'is_safe': True,
            'health_metrics': {
                'trust_score': 0.8,
                'account_age_days': 30,
                'shadowbanned': False,
                'login_issues': False,
                'captcha_triggered': False,
                'bans': 0,
                'deletions': 0,
                'removals': 0
            },
            'rate_limits': {
                'upvote': {
                    'current_usage': {'recent_failures': 0},
                    'can_perform': True
                },
                'comment': {
                    'current_usage': {'recent_failures': 0},
                    'can_perform': True
                }
            }
        }
    
    def test_check_account_alerts_healthy_account(self, mock_safety_status):
        """Test alert checking for healthy account"""
        with patch('safety_monitor.get_safety_status') as mock_get_status:
            mock_get_status.return_value = mock_safety_status
            
            alerts = safety_monitor.check_account_alerts(1)
            
            assert len(alerts) == 0  # No alerts for healthy account
    
    def test_check_account_alerts_shadowbanned(self, mock_safety_status):
        """Test alert generation for shadowbanned account"""
        mock_safety_status['health_metrics']['shadowbanned'] = True
        
        with patch('safety_monitor.get_safety_status') as mock_get_status:
            mock_get_status.return_value = mock_safety_status
            
            alerts = safety_monitor.check_account_alerts(1)
            
            assert len(alerts) == 1
            assert alerts[0].alert_type == 'shadowban_detected'
            assert alerts[0].level == AlertLevel.EMERGENCY
    
    def test_check_account_alerts_low_trust_score(self, mock_safety_status):
        """Test alert generation for low trust score"""
        mock_safety_status['health_metrics']['trust_score'] = 0.2  # Critical level
        
        with patch('safety_monitor.get_safety_status') as mock_get_status:
            mock_get_status.return_value = mock_safety_status
            
            alerts = safety_monitor.check_account_alerts(1)
            
            assert len(alerts) == 1
            assert alerts[0].alert_type == 'trust_score_critical'
            assert alerts[0].level == AlertLevel.CRITICAL
    
    def test_check_account_alerts_warning_trust_score(self, mock_safety_status):
        """Test alert generation for warning-level trust score"""
        mock_safety_status['health_metrics']['trust_score'] = 0.4  # Warning level
        
        with patch('safety_monitor.get_safety_status') as mock_get_status:
            mock_get_status.return_value = mock_safety_status
            
            alerts = safety_monitor.check_account_alerts(1)
            
            assert len(alerts) == 1
            assert alerts[0].alert_type == 'trust_score_warning'
            assert alerts[0].level == AlertLevel.WARNING
    
    def test_check_account_alerts_login_issues(self, mock_safety_status):
        """Test alert generation for login issues"""
        mock_safety_status['health_metrics']['login_issues'] = True
        
        with patch('safety_monitor.get_safety_status') as mock_get_status:
            mock_get_status.return_value = mock_safety_status
            
            alerts = safety_monitor.check_account_alerts(1)
            
            assert len(alerts) == 1
            assert alerts[0].alert_type == 'login_issues'
            assert alerts[0].level == AlertLevel.CRITICAL
    
    def test_check_account_alerts_captcha_triggered(self, mock_safety_status):
        """Test alert generation for captcha triggers"""
        mock_safety_status['health_metrics']['captcha_triggered'] = True
        
        with patch('safety_monitor.get_safety_status') as mock_get_status:
            mock_get_status.return_value = mock_safety_status
            
            alerts = safety_monitor.check_account_alerts(1)
            
            assert len(alerts) == 1
            assert alerts[0].alert_type == 'captcha_triggered'
            assert alerts[0].level == AlertLevel.WARNING
    
    def test_check_account_alerts_rate_limit_violations(self, mock_safety_status):
        """Test alert generation for rate limit violations"""
        # Set up multiple rate limit violations
        for action in ['upvote', 'comment', 'post']:
            mock_safety_status['rate_limits'][action] = {
                'current_usage': {'recent_failures': 2},
                'can_perform': False
            }
        
        with patch('safety_monitor.get_safety_status') as mock_get_status:
            mock_get_status.return_value = mock_safety_status
            
            alerts = safety_monitor.check_account_alerts(1)
            
            # Should generate rate limit violation alert
            rate_limit_alerts = [a for a in alerts if a.alert_type == 'rate_limit_violations']
            assert len(rate_limit_alerts) == 1
            assert rate_limit_alerts[0].level == AlertLevel.WARNING
    
    def test_check_account_alerts_multiple_issues(self, mock_safety_status):
        """Test alert generation for account with multiple issues"""
        mock_safety_status['health_metrics']['trust_score'] = 0.2
        mock_safety_status['health_metrics']['captcha_triggered'] = True
        mock_safety_status['health_metrics']['login_issues'] = True
        
        with patch('safety_monitor.get_safety_status') as mock_get_status:
            mock_get_status.return_value = mock_safety_status
            
            alerts = safety_monitor.check_account_alerts(1)
            
            assert len(alerts) >= 3  # Should have multiple alerts
            alert_types = [alert.alert_type for alert in alerts]
            assert 'trust_score_critical' in alert_types
            assert 'captcha_triggered' in alert_types
            assert 'login_issues' in alert_types

class TestAutomatedResponses:
    """Test automated response system"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        with patch('safety_monitor.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            yield mock_session
    
    @pytest.fixture
    def mock_account_with_settings(self):
        """Mock account with automation settings"""
        account = Mock(spec=RedditAccount)
        account.id = 1
        account.reddit_username = 'test_user'
        
        settings = Mock()
        settings.auto_upvote_enabled = True
        settings.auto_comment_enabled = True
        settings.auto_post_enabled = True
        settings.max_daily_comments = 20
        settings.max_daily_upvotes = 100
        settings.engagement_schedule = {}
        
        account.automation_settings = settings
        return account
    
    def test_take_auto_action_pause_automation(self, mock_db_session, mock_account_with_settings):
        """Test automated response to pause automation"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account_with_settings
        
        alert = SafetyAlert(
            account_id=1,
            alert_type='shadowban_detected',
            level=AlertLevel.EMERGENCY,
            message='Account appears to be shadowbanned',
            details={'shadowban_status': True},
            timestamp=datetime.utcnow()
        )
        
        result = safety_monitor.take_auto_action(alert)
        
        assert result['action_taken'] is True
        assert result['action'] == 'pause_automation'
        
        # Verify automation was disabled
        settings = mock_account_with_settings.automation_settings
        assert settings.auto_upvote_enabled is False
        assert settings.auto_comment_enabled is False
        assert settings.auto_post_enabled is False
    
    def test_take_auto_action_reduce_activity(self, mock_db_session, mock_account_with_settings):
        """Test automated response to reduce activity"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account_with_settings
        
        alert = SafetyAlert(
            account_id=1,
            alert_type='trust_score_critical',
            level=AlertLevel.CRITICAL,
            message='Trust score critically low',
            details={'trust_score': 0.2},
            timestamp=datetime.utcnow()
        )
        
        original_comments = mock_account_with_settings.automation_settings.max_daily_comments
        original_upvotes = mock_account_with_settings.automation_settings.max_daily_upvotes
        
        result = safety_monitor.take_auto_action(alert)
        
        assert result['action_taken'] is True
        assert result['action'] == 'reduce_activity'
        
        # Verify limits were reduced
        settings = mock_account_with_settings.automation_settings
        assert settings.max_daily_comments == max(1, original_comments // 2)
        assert settings.max_daily_upvotes == max(10, original_upvotes // 2)
    
    def test_take_auto_action_increase_delays(self, mock_db_session, mock_account_with_settings):
        """Test automated response to increase delays"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account_with_settings
        
        alert = SafetyAlert(
            account_id=1,
            alert_type='high_failure_rate',
            level=AlertLevel.CRITICAL,
            message='High failure rate detected',
            details={'failure_rate': 0.8},
            timestamp=datetime.utcnow()
        )
        
        result = safety_monitor.take_auto_action(alert)
        
        assert result['action_taken'] is True
        assert result['action'] == 'increase_delays'
        
        # Verify delays were increased
        settings = mock_account_with_settings.automation_settings
        schedule = settings.engagement_schedule
        assert schedule['increased_delays'] is True
        assert schedule['delay_multiplier'] == 2.0
    
    def test_take_auto_action_no_action_defined(self, mock_db_session, mock_account_with_settings):
        """Test automated response when no action is defined"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account_with_settings
        
        alert = SafetyAlert(
            account_id=1,
            alert_type='unknown_alert_type',
            level=AlertLevel.WARNING,
            message='Unknown alert',
            details={},
            timestamp=datetime.utcnow()
        )
        
        result = safety_monitor.take_auto_action(alert)
        
        assert result['action_taken'] is False
        assert result['reason'] == 'no_auto_action_defined'
    
    def test_take_auto_action_account_not_found(self, mock_db_session):
        """Test automated response when account is not found"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        alert = SafetyAlert(
            account_id=999,
            alert_type='shadowban_detected',
            level=AlertLevel.EMERGENCY,
            message='Account appears to be shadowbanned',
            details={'shadowban_status': True},
            timestamp=datetime.utcnow()
        )
        
        result = safety_monitor.take_auto_action(alert)
        
        assert result['action_taken'] is False
        assert result['reason'] == 'account_or_settings_not_found'

class TestMonitoringTasks:
    """Test monitoring Celery tasks"""
    
    @patch('safety_monitor.safety_monitor.check_account_alerts')
    @patch('safety_monitor.safety_monitor.take_auto_action')
    def test_monitor_all_accounts_task(self, mock_take_action, mock_check_alerts):
        """Test the monitor all accounts Celery task"""
        from safety_monitor import monitor_all_accounts
        
        # Mock alerts
        alert = SafetyAlert(
            account_id=1,
            alert_type='trust_score_critical',
            level=AlertLevel.CRITICAL,
            message='Trust score critically low',
            details={'trust_score': 0.2},
            timestamp=datetime.utcnow()
        )
        mock_check_alerts.return_value = [alert]
        
        # Mock auto action
        mock_take_action.return_value = {
            'action_taken': True,
            'action': 'reduce_activity'
        }
        
        with patch('safety_monitor.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            # Mock accounts
            account = Mock(spec=RedditAccount)
            account.id = 1
            account.reddit_username = 'test_user'
            mock_session.query.return_value.all.return_value = [account]
            
            # Create mock task instance
            mock_task = Mock()
            mock_task.request = Mock()
            mock_task.request.retries = 0
            mock_task.max_retries = 3
            
            result = monitor_all_accounts(mock_task)
            
            assert result['status'] == 'success'
            monitoring_results = result['monitoring_results']
            assert monitoring_results['accounts_monitored'] == 1
            assert monitoring_results['total_alerts'] == 1
            assert monitoring_results['critical_alerts'] == 1
            assert monitoring_results['auto_actions_taken'] == 1
    
    def test_generate_safety_report_task(self):
        """Test the generate safety report Celery task"""
        from safety_monitor import generate_safety_report
        
        with patch('safety_monitor.get_safety_status') as mock_get_status:
            with patch('safety_monitor.SessionLocal') as mock_session_class:
                mock_session = Mock()
                mock_session_class.return_value = mock_session
                
                # Mock account
                account = Mock(spec=RedditAccount)
                account.id = 1
                account.reddit_username = 'test_user'
                mock_session.query.return_value.all.return_value = [account]
                mock_session.query.return_value.filter.return_value.all.return_value = []
                
                # Mock safety status
                mock_get_status.return_value = {
                    'health_metrics': {
                        'shadowbanned': False,
                        'trust_score': 0.8,
                        'login_issues': False,
                        'captcha_triggered': False
                    },
                    'rate_limits': {}
                }
                
                # Create mock task instance
                mock_task = Mock()
                mock_task.request = Mock()
                mock_task.request.retries = 0
                mock_task.max_retries = 3
                
                result = generate_safety_report(mock_task, days=7)
                
                assert result['status'] == 'success'
                report = result['report']
                assert 'report_date' in report
                assert report['period_days'] == 7
                assert report['accounts_analyzed'] == 1
                assert 'summary' in report
                assert 'account_details' in report

class TestSafetyMonitorConfiguration:
    """Test safety monitor configuration and thresholds"""
    
    def test_alert_thresholds_validity(self):
        """Test that alert thresholds are valid"""
        thresholds = safety_monitor.alert_thresholds
        
        assert 0 < thresholds['shadowban_probability'] <= 1
        assert 0 < thresholds['trust_score_critical'] < thresholds['trust_score_warning'] <= 1
        assert 0 < thresholds['failure_rate_critical'] < thresholds['failure_rate_warning'] <= 1
        assert thresholds['consecutive_failures'] > 0
        assert thresholds['rate_limit_violations'] > 0
    
    def test_auto_responses_mapping(self):
        """Test that auto responses are properly mapped"""
        responses = safety_monitor.auto_responses
        
        expected_actions = ['pause_automation', 'reduce_activity', 'increase_delays']
        
        for action in responses.values():
            assert action in expected_actions
        
        # Critical alerts should have appropriate responses
        assert responses.get('shadowban_detected') == 'pause_automation'
        assert responses.get('login_issues') == 'pause_automation'
        assert responses.get('trust_score_critical') == 'reduce_activity'

if __name__ == '__main__':
    pytest.main([__file__])
