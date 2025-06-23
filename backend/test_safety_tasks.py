"""
Comprehensive tests for safety tasks module
Tests rate limiting, account safety checks, shadowban detection, and health monitoring
"""
import pytest
import redis
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from safety_tasks import (
    check_rate_limits, record_action, get_action_counts, is_account_safe,
    calculate_trust_score, update_account_health, check_adaptive_rate_limits,
    get_rate_limit_status, comprehensive_shadowban_check, DEFAULT_RATE_LIMITS
)
from models import RedditAccount, AccountHealth, EngagementLog, ActivityLog
from database import SessionLocal

class TestRateLimiting:
    """Test rate limiting functionality"""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client"""
        with patch('safety_tasks.redis_client') as mock_redis:
            mock_redis.get.return_value = None
            mock_redis.setex.return_value = True
            mock_redis.incr.return_value = 1
            mock_redis.expire.return_value = True
            mock_redis.pipeline.return_value = mock_redis
            mock_redis.execute.return_value = [1, True, 1, True]
            yield mock_redis
    
    def test_check_rate_limits_no_limits(self, mock_redis):
        """Test rate limit check when no limits are set"""
        mock_redis.get.return_value = None
        
        result = check_rate_limits(1, 'upvote')
        assert result is True
    
    def test_check_rate_limits_within_limits(self, mock_redis):
        """Test rate limit check when within limits"""
        mock_redis.get.side_effect = [None, '5', '50']  # cooldown, hourly, daily
        
        result = check_rate_limits(1, 'upvote')
        assert result is True
    
    def test_check_rate_limits_cooldown_active(self, mock_redis):
        """Test rate limit check when cooldown is active"""
        import time
        current_time = time.time()
        mock_redis.get.side_effect = [str(current_time), '5', '50']
        
        result = check_rate_limits(1, 'upvote')
        assert result is False
    
    def test_check_rate_limits_hourly_exceeded(self, mock_redis):
        """Test rate limit check when hourly limit exceeded"""
        mock_redis.get.side_effect = [None, '100', '200']  # Over hourly limit
        
        result = check_rate_limits(1, 'upvote')
        assert result is False
    
    def test_check_rate_limits_daily_exceeded(self, mock_redis):
        """Test rate limit check when daily limit exceeded"""
        mock_redis.get.side_effect = [None, '30', '600']  # Over daily limit
        
        result = check_rate_limits(1, 'upvote')
        assert result is False
    
    def test_record_action_success(self, mock_redis):
        """Test recording successful action"""
        record_action(1, 'upvote', success=True)
        
        # Verify Redis calls
        assert mock_redis.setex.called
        assert mock_redis.pipeline.called
        assert mock_redis.incr.call_count >= 2  # hourly and daily counters
    
    def test_record_action_failure(self, mock_redis):
        """Test recording failed action"""
        record_action(1, 'upvote', success=False)
        
        # Verify failure tracking
        assert mock_redis.setex.called
        assert mock_redis.incr.call_count >= 3  # hourly, daily, and failure counters
    
    def test_get_action_counts(self, mock_redis):
        """Test getting action counts"""
        mock_redis.get.side_effect = ['10', '100', '2']  # hourly, daily, failures
        
        counts = get_action_counts(1, 'upvote')
        
        assert counts['hourly_count'] == 10
        assert counts['daily_count'] == 100
        assert counts['recent_failures'] == 2

class TestAccountSafety:
    """Test account safety checks"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        with patch('safety_tasks.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            yield mock_session
    
    @pytest.fixture
    def mock_account(self):
        """Mock Reddit account with health data"""
        account = Mock(spec=RedditAccount)
        account.id = 1
        account.reddit_username = 'test_user'
        
        health = Mock(spec=AccountHealth)
        health.shadowbanned = False
        health.account_age_days = 30
        health.trust_score = 0.8
        health.login_issues = False
        health.captcha_triggered = False
        health.bans = 0
        health.deletions = 0
        health.removals = 0
        
        account.account_health = health
        return account
    
    def test_is_account_safe_healthy_account(self, mock_db_session, mock_account):
        """Test safety check for healthy account"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account
        
        with patch('safety_tasks.get_action_counts') as mock_counts:
            mock_counts.return_value = {'recent_failures': 0}
            
            result = is_account_safe(1)
            assert result is True
    
    def test_is_account_safe_shadowbanned(self, mock_db_session, mock_account):
        """Test safety check for shadowbanned account"""
        mock_account.account_health.shadowbanned = True
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account
        
        result = is_account_safe(1)
        assert result is False
    
    def test_is_account_safe_too_young(self, mock_db_session, mock_account):
        """Test safety check for account that's too young"""
        mock_account.account_health.account_age_days = 3  # Below threshold
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account
        
        result = is_account_safe(1)
        assert result is False
    
    def test_is_account_safe_low_trust_score(self, mock_db_session, mock_account):
        """Test safety check for account with low trust score"""
        mock_account.account_health.trust_score = 0.3  # Below threshold
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account
        
        with patch('safety_tasks.get_action_counts') as mock_counts:
            mock_counts.return_value = {'recent_failures': 0}
            
            result = is_account_safe(1)
            assert result is False
    
    def test_is_account_safe_too_many_failures(self, mock_db_session, mock_account):
        """Test safety check for account with too many recent failures"""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account
        
        with patch('safety_tasks.get_action_counts') as mock_counts:
            mock_counts.return_value = {'recent_failures': 10}  # High failure count
            
            result = is_account_safe(1)
            assert result is False
    
    def test_calculate_trust_score_no_data(self, mock_db_session):
        """Test trust score calculation with no engagement data"""
        mock_db_session.query.return_value.filter.return_value.all.return_value = []
        
        score = calculate_trust_score(1)
        assert score == 0.5  # Neutral score for new accounts
    
    def test_calculate_trust_score_high_success_rate(self, mock_db_session, mock_account):
        """Test trust score calculation with high success rate"""
        # Mock engagement logs with high success rate
        mock_logs = []
        for i in range(10):
            log = Mock(spec=EngagementLog)
            log.status = 'success'
            mock_logs.append(log)
        
        mock_db_session.query.return_value.filter.return_value.all.return_value = mock_logs
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_account
        
        score = calculate_trust_score(1)
        assert score > 0.8  # Should be high due to 100% success rate and age bonus

class TestAdaptiveRateLimiting:
    """Test adaptive rate limiting functionality"""
    
    @pytest.fixture
    def mock_account_with_health(self):
        """Mock account with specific health metrics"""
        account = Mock(spec=RedditAccount)
        account.id = 1
        
        health = Mock(spec=AccountHealth)
        health.trust_score = 0.8
        health.account_age_days = 365  # 1 year old
        
        account.account_health = health
        return account
    
    def test_get_adaptive_rate_limit_trusted_account(self, mock_account_with_health):
        """Test adaptive rate limits for trusted account"""
        with patch('safety_tasks.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            mock_session.query.return_value.filter.return_value.first.return_value = mock_account_with_health
            
            from safety_tasks import get_adaptive_rate_limit
            adaptive_limit = get_adaptive_rate_limit(1, 'upvote')
            
            base_limit = DEFAULT_RATE_LIMITS['upvote']
            
            # Trusted account should have higher limits
            assert adaptive_limit.max_per_hour > base_limit.max_per_hour
            assert adaptive_limit.max_per_day > base_limit.max_per_day
            assert adaptive_limit.cooldown_seconds < base_limit.cooldown_seconds
    
    def test_check_adaptive_rate_limits_with_burst(self):
        """Test adaptive rate limits with burst detection"""
        with patch('safety_tasks.get_adaptive_rate_limit') as mock_get_limit:
            with patch('safety_tasks.check_burst_limits') as mock_burst:
                with patch('safety_tasks.redis_client') as mock_redis:
                    # Setup mocks
                    mock_limit = Mock()
                    mock_limit.cooldown_seconds = 30
                    mock_limit.max_per_hour = 60
                    mock_limit.max_per_day = 500
                    mock_get_limit.return_value = mock_limit
                    
                    mock_burst.return_value = True
                    mock_redis.get.side_effect = [None, '10', '100']  # cooldown, hourly, daily
                    
                    result = check_adaptive_rate_limits(1, 'upvote')
                    assert result is True
                    
                    # Verify burst check was called
                    mock_burst.assert_called_once_with(1, 'upvote')

class TestShadowbanDetection:
    """Test shadowban detection functionality"""
    
    @pytest.fixture
    def mock_reddit_service(self):
        """Mock Reddit service"""
        with patch('safety_tasks.reddit_service') as mock_service:
            yield mock_service
    
    def test_comprehensive_shadowban_check_not_shadowbanned(self, mock_reddit_service):
        """Test comprehensive shadowban check for non-shadowbanned account"""
        with patch('safety_tasks.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            # Mock account
            account = Mock(spec=RedditAccount)
            account.id = 1
            account.reddit_username = 'test_user'
            account.account_health = Mock()
            mock_session.query.return_value.filter.return_value.first.return_value = account
            
            # Mock all detection methods returning "not shadowbanned"
            mock_reddit_service.check_shadowban.return_value = False
            
            with patch('safety_tasks.check_post_visibility') as mock_post_vis:
                with patch('safety_tasks.check_comment_visibility') as mock_comment_vis:
                    with patch('safety_tasks.check_submission_visibility') as mock_sub_vis:
                        with patch('safety_tasks.check_profile_access') as mock_profile:
                            with patch('safety_tasks.check_user_page_accessibility') as mock_user_page:
                                # All checks return positive results
                                mock_post_vis.return_value = True
                                mock_comment_vis.return_value = (True, {})
                                mock_sub_vis.return_value = (True, {})
                                mock_profile.return_value = True
                                mock_user_page.return_value = (True, {})
                                
                                result = comprehensive_shadowban_check(1)
                                
                                assert result['is_shadowbanned'] is False
                                assert result['shadowban_probability'] < 0.5
                                assert result['confidence_level'] in ['high', 'medium']
    
    def test_comprehensive_shadowban_check_shadowbanned(self, mock_reddit_service):
        """Test comprehensive shadowban check for shadowbanned account"""
        with patch('safety_tasks.SessionLocal') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session
            
            # Mock account
            account = Mock(spec=RedditAccount)
            account.id = 1
            account.reddit_username = 'test_user'
            account.account_health = Mock()
            mock_session.query.return_value.filter.return_value.first.return_value = account
            
            # Mock detection methods indicating shadowban
            mock_reddit_service.check_shadowban.return_value = True
            
            with patch('safety_tasks.check_post_visibility') as mock_post_vis:
                with patch('safety_tasks.check_comment_visibility') as mock_comment_vis:
                    with patch('safety_tasks.check_submission_visibility') as mock_sub_vis:
                        with patch('safety_tasks.check_profile_access') as mock_profile:
                            with patch('safety_tasks.check_user_page_accessibility') as mock_user_page:
                                # All checks return negative results
                                mock_post_vis.return_value = False
                                mock_comment_vis.return_value = (False, {})
                                mock_sub_vis.return_value = (False, {})
                                mock_profile.return_value = False
                                mock_user_page.return_value = (False, {})
                                
                                result = comprehensive_shadowban_check(1)
                                
                                assert result['is_shadowbanned'] is True
                                assert result['shadowban_probability'] > 0.5
                                assert result['recommendation'] == 'shadowbanned'

if __name__ == '__main__':
    pytest.main([__file__])
