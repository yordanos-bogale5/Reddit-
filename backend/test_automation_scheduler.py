"""
Comprehensive tests for automation scheduler module
Tests intelligent scheduling, activity pattern analysis, and schedule optimization
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from automation_scheduler import (
    AutomationScheduler, ScheduleSlot, ActivityPattern, scheduler
)
from models import RedditAccount, AutomationSettings, ActivityLog, EngagementLog

class TestActivityPatternAnalysis:
    """Test activity pattern analysis functionality"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        with patch('automation_scheduler.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            yield mock_session
    
    @pytest.fixture
    def sample_activity_logs(self):
        """Create sample activity logs for testing"""
        logs = []
        base_time = datetime.utcnow() - timedelta(days=7)
        
        # Create logs with different hours to simulate patterns
        for day in range(7):
            for hour in [9, 14, 19, 21]:  # Peak hours
                log = Mock(spec=ActivityLog)
                log.timestamp = base_time + timedelta(days=day, hours=hour)
                log.subreddit = 'AskReddit'
                logs.append(log)
        
        return logs
    
    def test_analyze_account_pattern_with_data(self, mock_db_session, sample_activity_logs):
        """Test pattern analysis with sufficient data"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = sample_activity_logs
        
        pattern = scheduler.analyze_account_pattern(1, days=7)
        
        assert isinstance(pattern, ActivityPattern)
        assert len(pattern.peak_hours) > 0
        assert len(pattern.preferred_subreddits) > 0
        assert pattern.avg_session_duration > 0
    
    def test_analyze_account_pattern_no_data(self, mock_db_session):
        """Test pattern analysis with no historical data"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        pattern = scheduler.analyze_account_pattern(1, days=7)
        
        # Should return default casual user pattern
        assert isinstance(pattern, ActivityPattern)
        assert pattern.peak_hours == scheduler.default_patterns['casual_user'].peak_hours
    
    def test_analyze_account_pattern_subreddit_frequency(self, mock_db_session):
        """Test subreddit frequency analysis"""
        # Create logs with different subreddits
        logs = []
        subreddits = ['AskReddit', 'AskReddit', 'funny', 'todayilearned', 'AskReddit']
        
        for i, subreddit in enumerate(subreddits):
            log = Mock(spec=EngagementLog)
            log.timestamp = datetime.utcnow() - timedelta(hours=i)
            log.subreddit = subreddit
            logs.append(log)
        
        mock_db_session.query.return_value.filter.return_value.all.return_value = logs
        
        pattern = scheduler.analyze_account_pattern(1, days=7)
        
        # AskReddit should be the most frequent
        assert 'AskReddit' in pattern.preferred_subreddits
        assert pattern.preferred_subreddits[0] == 'AskReddit'

class TestScheduleGeneration:
    """Test schedule generation functionality"""
    
    @pytest.fixture
    def mock_account_with_settings(self):
        """Mock account with automation settings"""
        account = Mock(spec=RedditAccount)
        account.id = 1
        account.reddit_username = 'test_user'
        
        settings = Mock(spec=AutomationSettings)
        settings.auto_upvote_enabled = True
        settings.auto_comment_enabled = True
        settings.auto_post_enabled = False
        settings.max_daily_upvotes = 100
        settings.max_daily_comments = 20
        settings.selected_subreddits = ['AskReddit', 'funny']
        
        account.automation_settings = settings
        return account
    
    def test_generate_daily_schedule_basic(self, mock_account_with_settings):
        """Test basic daily schedule generation"""
        with patch('automation_scheduler.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = mock_account_with_settings
            
            with patch.object(scheduler, 'analyze_account_pattern') as mock_analyze:
                # Mock pattern analysis
                pattern = ActivityPattern(
                    peak_hours=[9, 14, 19],
                    low_activity_hours=[2, 3, 4],
                    preferred_subreddits=['AskReddit', 'funny'],
                    avg_session_duration=30,
                    break_frequency=0.3,
                    weekend_behavior={'adaptive': True}
                )
                mock_analyze.return_value = pattern
                
                schedule = scheduler.generate_daily_schedule(1)
                
                assert isinstance(schedule, list)
                assert len(schedule) > 0
                
                # Check that slots are properly formed
                for slot in schedule:
                    assert isinstance(slot, ScheduleSlot)
                    assert slot.account_id == 1
                    assert slot.start_time <= slot.end_time
                    assert slot.action_type in ['engagement_session', 'upvote', 'comment']
    
    def test_generate_daily_schedule_no_settings(self):
        """Test schedule generation for account without settings"""
        with patch('automation_scheduler.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = None
            
            schedule = scheduler.generate_daily_schedule(1)
            
            assert schedule == []
    
    def test_generate_daily_schedule_disabled_automation(self):
        """Test schedule generation for account with disabled automation"""
        account = Mock(spec=RedditAccount)
        account.id = 1
        
        settings = Mock(spec=AutomationSettings)
        settings.auto_upvote_enabled = False
        settings.auto_comment_enabled = False
        settings.auto_post_enabled = False
        
        account.automation_settings = settings
        
        with patch('automation_scheduler.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = account
            
            with patch.object(scheduler, 'analyze_account_pattern') as mock_analyze:
                pattern = ActivityPattern(
                    peak_hours=[9, 14, 19],
                    low_activity_hours=[2, 3, 4],
                    preferred_subreddits=['AskReddit'],
                    avg_session_duration=30,
                    break_frequency=0.3,
                    weekend_behavior={'adaptive': True}
                )
                mock_analyze.return_value = pattern
                
                schedule = scheduler.generate_daily_schedule(1)
                
                # Should only have engagement sessions, no specific actions
                action_types = [slot.action_type for slot in schedule]
                assert 'upvote' not in action_types
                assert 'comment' not in action_types
                assert 'post' not in action_types
    
    def test_schedule_slots_timing(self, mock_account_with_settings):
        """Test that schedule slots are properly timed"""
        with patch('automation_scheduler.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = mock_account_with_settings
            
            with patch.object(scheduler, 'analyze_account_pattern') as mock_analyze:
                pattern = ActivityPattern(
                    peak_hours=[9, 14, 19],
                    low_activity_hours=[2, 3, 4],
                    preferred_subreddits=['AskReddit'],
                    avg_session_duration=30,
                    break_frequency=0.3,
                    weekend_behavior={'adaptive': True}
                )
                mock_analyze.return_value = pattern
                
                target_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
                schedule = scheduler.generate_daily_schedule(1, target_date)
                
                # Check that slots are within the target date
                for slot in schedule:
                    assert slot.start_time.date() >= target_date.date()
                    # Most slots should be within 24 hours of target date
                    time_diff = slot.start_time - target_date
                    assert time_diff.total_seconds() <= 48 * 3600  # Within 48 hours

class TestScheduleOptimization:
    """Test schedule optimization functionality"""
    
    def test_generate_action_slots_distribution(self):
        """Test that action slots are properly distributed"""
        pattern = ActivityPattern(
            peak_hours=[9, 14, 19],
            low_activity_hours=[2, 3, 4],
            preferred_subreddits=['AskReddit', 'funny'],
            avg_session_duration=30,
            break_frequency=0.3,
            weekend_behavior={'adaptive': True}
        )
        
        target_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        slots = scheduler._generate_action_slots(target_date, 'upvote', pattern, 50)
        
        assert len(slots) <= 50  # Should not exceed max count
        assert len(slots) >= 12  # Should have at least 25% of max count
        
        # Check that slots avoid low activity hours when possible
        slot_hours = [slot.start_time.hour for slot in slots]
        low_activity_count = sum(1 for hour in slot_hours if hour in pattern.low_activity_hours)
        total_slots = len(slots)
        
        # Most slots should not be in low activity hours
        assert low_activity_count < total_slots * 0.5
    
    def test_schedule_slot_properties(self):
        """Test that schedule slots have correct properties"""
        pattern = ActivityPattern(
            peak_hours=[9, 14, 19],
            low_activity_hours=[2, 3, 4],
            preferred_subreddits=['AskReddit', 'funny'],
            avg_session_duration=30,
            break_frequency=0.3,
            weekend_behavior={'adaptive': True}
        )
        
        target_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        slots = scheduler._generate_action_slots(target_date, 'comment', pattern, 20)
        
        for slot in slots:
            assert slot.action_type == 'comment'
            assert slot.priority == 2
            assert slot.target_subreddit in pattern.preferred_subreddits
            assert slot.start_time <= slot.end_time
            assert (slot.end_time - slot.start_time).total_seconds() <= 300  # 5 minutes max

class TestSchedulerIntegration:
    """Test scheduler integration with other components"""
    
    @patch('automation_scheduler.is_account_safe')
    @patch('automation_scheduler.schedule_automation_slot')
    def test_schedule_daily_automation_task(self, mock_schedule_slot, mock_is_safe):
        """Test the daily automation scheduling Celery task"""
        from automation_scheduler import schedule_daily_automation
        
        # Mock safety check
        mock_is_safe.return_value = True
        
        # Mock task scheduling
        mock_task_result = Mock()
        mock_task_result.id = 'test-task-id'
        mock_schedule_slot.apply_async.return_value = mock_task_result
        
        with patch('automation_scheduler.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            # Mock account with settings
            account = Mock(spec=RedditAccount)
            account.id = 1
            account.reddit_username = 'test_user'
            
            settings = Mock(spec=AutomationSettings)
            settings.auto_upvote_enabled = True
            settings.auto_comment_enabled = False
            settings.auto_post_enabled = False
            
            account.automation_settings = settings
            
            mock_session.query.return_value.join.return_value.filter.return_value.all.return_value = [account]
            mock_session.query.return_value.filter.return_value.first.return_value = account
            
            with patch.object(scheduler, 'generate_daily_schedule') as mock_generate:
                # Mock schedule generation
                slot = ScheduleSlot(
                    start_time=datetime.utcnow() + timedelta(hours=1),
                    end_time=datetime.utcnow() + timedelta(hours=1, minutes=30),
                    action_type='upvote',
                    priority=2,
                    account_id=1,
                    target_subreddit='AskReddit'
                )
                mock_generate.return_value = [slot]
                
                # Create a mock task instance
                mock_task = Mock()
                mock_task.request = Mock()
                mock_task.request.retries = 0
                mock_task.max_retries = 3
                
                result = schedule_daily_automation(mock_task, account_id=1)
                
                assert result['status'] == 'success'
                assert result['successful_schedules'] == 1
                assert len(result['results']) == 1
    
    def test_default_patterns_validity(self):
        """Test that default patterns are valid"""
        for pattern_name, pattern in scheduler.default_patterns.items():
            assert isinstance(pattern, ActivityPattern)
            assert len(pattern.peak_hours) > 0
            assert len(pattern.low_activity_hours) > 0
            assert len(pattern.preferred_subreddits) > 0
            assert pattern.avg_session_duration > 0
            assert 0 <= pattern.break_frequency <= 1
            assert isinstance(pattern.weekend_behavior, dict)
            
            # Check that hours are valid
            for hour in pattern.peak_hours:
                assert 0 <= hour <= 23
            for hour in pattern.low_activity_hours:
                assert 0 <= hour <= 23

if __name__ == '__main__':
    pytest.main([__file__])
