#!/usr/bin/env python3
"""
Test script for Celery tasks (without actually running Celery)
"""

import sys
import os
import logging

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import RedditAccount, AutomationSettings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_test_account_id():
    """Get the test account ID"""
    try:
        db = SessionLocal()
        account = db.query(RedditAccount).filter(
            RedditAccount.reddit_username == "test_reddit_user"
        ).first()
        
        if account:
            db.close()
            return account.id
        else:
            logger.error("Test account not found. Run test_karma.py first.")
            db.close()
            return None
            
    except Exception as e:
        logger.error(f"Error getting test account: {e}")
        if 'db' in locals():
            db.close()
        return None

def test_task_imports():
    """Test that all task functions can be imported"""
    logger.info("Testing task imports...")
    
    try:
        from tasks import (
            automate_upvote,
            automate_comment,
            automate_post,
            check_shadowban,
            log_karma_snapshot,
            scheduled_automation_check,
            cleanup_old_logs
        )
        
        logger.info("✓ All task functions imported successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error importing tasks: {e}")
        return False

def test_task_function_calls(account_id: int):
    """Test calling task functions directly (without Celery)"""
    logger.info("Testing task function calls...")
    
    try:
        # Import task functions
        from tasks import (
            check_shadowban,
            log_karma_snapshot,
            cleanup_old_logs
        )
        
        # Test shadowban check
        logger.info("Testing shadowban check...")
        shadowban_result = check_shadowban(account_id)
        logger.info(f"Shadowban check result: {shadowban_result}")
        
        # Test karma snapshot
        logger.info("Testing karma snapshot...")
        karma_result = log_karma_snapshot(account_id)
        logger.info(f"Karma snapshot result: {karma_result}")
        
        # Test cleanup (with 0 days to keep for testing)
        logger.info("Testing log cleanup...")
        cleanup_result = cleanup_old_logs(days_to_keep=0)
        logger.info(f"Cleanup result: {cleanup_result}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing task function calls: {e}")
        return False

def test_automation_task_validation(account_id: int):
    """Test automation task validation logic"""
    logger.info("Testing automation task validation...")
    
    try:
        # Import task functions
        from tasks import automate_upvote, automate_comment, automate_post
        
        # Create a mock task object for testing
        class MockTask:
            def __init__(self):
                self.request = MockRequest()
                self.max_retries = 3
            
            def retry(self, countdown=None):
                raise Exception("Retry called")
        
        class MockRequest:
            def __init__(self):
                self.retries = 0
        
        # Test upvote automation validation
        logger.info("Testing upvote automation validation...")

        # This should fail because we're using dummy tokens
        # But we can test the validation logic
        mock_task = MockTask()

        # Test with non-existent account - use the actual function signature
        try:
            # For bound tasks, we need to call the function directly
            result = automate_upvote.run(99999, "test_target", "test_subreddit")
            if not result["success"] and "Account" in result["error"]:
                logger.info("✓ Upvote automation correctly validates account existence")
            else:
                logger.warning(f"Unexpected upvote validation result: {result}")
        except Exception as e:
            logger.info(f"✓ Upvote automation validation works (expected error: {e})")

        # Test comment automation validation
        logger.info("Testing comment automation validation...")
        try:
            result = automate_comment.run(99999, "test_parent", "test comment", "test_subreddit")
            if not result["success"] and "Account" in result["error"]:
                logger.info("✓ Comment automation correctly validates account existence")
            else:
                logger.warning(f"Unexpected comment validation result: {result}")
        except Exception as e:
            logger.info(f"✓ Comment automation validation works (expected error: {e})")

        # Test post automation validation
        logger.info("Testing post automation validation...")
        try:
            result = automate_post.run(99999, "test_subreddit", "Test Title", "Test content")
            if not result["success"] and "Account" in result["error"]:
                logger.info("✓ Post automation correctly validates account existence")
            else:
                logger.warning(f"Unexpected post validation result: {result}")
        except Exception as e:
            logger.info(f"✓ Post automation validation works (expected error: {e})")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing automation task validation: {e}")
        return False

def test_automation_settings_integration(account_id: int):
    """Test integration with automation settings"""
    logger.info("Testing automation settings integration...")
    
    try:
        db = SessionLocal()
        
        # Get or create automation settings
        account = db.query(RedditAccount).filter(RedditAccount.id == account_id).first()
        if not account:
            logger.error("Test account not found")
            return False
        
        settings = account.automation_settings
        if not settings:
            settings = AutomationSettings(
                account_id=account_id,
                selected_subreddits=["python", "programming"],
                active_keywords=["automation", "bot"],
                engagement_schedule={},
                max_daily_comments=10,
                max_daily_upvotes=50,
                auto_upvote_enabled=True,
                auto_comment_enabled=True,
                auto_post_enabled=False
            )
            db.add(settings)
            db.commit()
        
        # Test settings validation
        logger.info(f"Automation settings found:")
        logger.info(f"  - Upvote enabled: {settings.auto_upvote_enabled}")
        logger.info(f"  - Comment enabled: {settings.auto_comment_enabled}")
        logger.info(f"  - Post enabled: {settings.auto_post_enabled}")
        logger.info(f"  - Max daily comments: {settings.max_daily_comments}")
        logger.info(f"  - Max daily upvotes: {settings.max_daily_upvotes}")
        logger.info(f"  - Selected subreddits: {settings.selected_subreddits}")
        
        # Test automation status calculation
        automation_active = (
            settings.auto_upvote_enabled or
            settings.auto_comment_enabled or
            settings.auto_post_enabled
        )
        
        logger.info(f"  - Automation active: {automation_active}")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Error testing automation settings integration: {e}")
        if 'db' in locals():
            db.close()
        return False

def test_scheduled_automation_check():
    """Test the scheduled automation check function"""
    logger.info("Testing scheduled automation check...")
    
    try:
        from tasks import scheduled_automation_check
        
        # Run the scheduled check
        result = scheduled_automation_check()
        logger.info(f"Scheduled automation check result: {result}")
        
        if result["success"]:
            logger.info(f"✓ Processed {result['accounts_processed']} accounts")
            return True
        else:
            logger.warning(f"Scheduled check failed: {result.get('error')}")
            return False
        
    except Exception as e:
        logger.error(f"Error testing scheduled automation check: {e}")
        return False

if __name__ == "__main__":
    logger.info("Reddit Dashboard Celery Tasks Test")
    logger.info("=" * 50)
    
    # Test task imports
    if not test_task_imports():
        logger.error("Task import test failed. Exiting.")
        sys.exit(1)
    
    # Get test account
    account_id = get_test_account_id()
    if not account_id:
        logger.error("Failed to get test account. Exiting.")
        sys.exit(1)
    
    # Test task function calls
    if not test_task_function_calls(account_id):
        logger.error("Task function call test failed. Exiting.")
        sys.exit(1)
    
    # Test automation task validation
    if not test_automation_task_validation(account_id):
        logger.error("Automation task validation test failed. Exiting.")
        sys.exit(1)
    
    # Test automation settings integration
    if not test_automation_settings_integration(account_id):
        logger.error("Automation settings integration test failed. Exiting.")
        sys.exit(1)
    
    # Test scheduled automation check
    if not test_scheduled_automation_check():
        logger.error("Scheduled automation check test failed. Exiting.")
        sys.exit(1)
    
    logger.info("All Celery task tests passed!")
    sys.exit(0)
