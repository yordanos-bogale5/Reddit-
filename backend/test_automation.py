#!/usr/bin/env python3
"""
Test script for automation endpoints
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

def test_automation_settings_crud(account_id: int):
    """Test automation settings CRUD operations"""
    logger.info("Testing automation settings CRUD operations...")
    
    try:
        db = SessionLocal()
        
        # Test creating automation settings
        logger.info("Creating automation settings...")
        settings = AutomationSettings(
            account_id=account_id,
            selected_subreddits=["python", "programming", "webdev"],
            active_keywords=["automation", "bot", "script"],
            engagement_schedule={"morning": "09:00", "evening": "18:00"},
            max_daily_comments=15,
            max_daily_upvotes=75,
            auto_upvote_enabled=True,
            auto_comment_enabled=False,
            auto_post_enabled=False
        )
        
        db.add(settings)
        db.commit()
        db.refresh(settings)
        
        logger.info(f"Created automation settings with ID: {settings.id}")
        
        # Test reading automation settings
        logger.info("Reading automation settings...")
        retrieved_settings = db.query(AutomationSettings).filter(
            AutomationSettings.account_id == account_id
        ).first()
        
        if retrieved_settings:
            logger.info(f"Retrieved settings: {retrieved_settings.selected_subreddits}")
            logger.info(f"Auto upvote enabled: {retrieved_settings.auto_upvote_enabled}")
            logger.info(f"Max daily comments: {retrieved_settings.max_daily_comments}")
        else:
            logger.error("Failed to retrieve automation settings")
            return False
        
        # Test updating automation settings
        logger.info("Updating automation settings...")
        retrieved_settings.auto_comment_enabled = True
        retrieved_settings.max_daily_comments = 20
        retrieved_settings.selected_subreddits = ["python", "programming", "webdev", "MachineLearning"]
        
        db.commit()
        logger.info("Updated automation settings successfully")
        
        # Test reading updated settings
        updated_settings = db.query(AutomationSettings).filter(
            AutomationSettings.account_id == account_id
        ).first()
        
        if updated_settings.auto_comment_enabled and updated_settings.max_daily_comments == 20:
            logger.info("Settings update verified successfully")
        else:
            logger.error("Settings update verification failed")
            return False
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Error testing automation settings CRUD: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return False

def test_automation_logic(account_id: int):
    """Test automation logic and calculations"""
    logger.info("Testing automation logic...")
    
    try:
        db = SessionLocal()
        
        # Get automation settings
        settings = db.query(AutomationSettings).filter(
            AutomationSettings.account_id == account_id
        ).first()
        
        if not settings:
            logger.error("No automation settings found")
            return False
        
        # Test automation status calculation
        automation_active = (
            settings.auto_upvote_enabled or
            settings.auto_comment_enabled or
            settings.auto_post_enabled
        )
        
        logger.info(f"Automation active: {automation_active}")
        logger.info(f"Upvote automation: {settings.auto_upvote_enabled}")
        logger.info(f"Comment automation: {settings.auto_comment_enabled}")
        logger.info(f"Post automation: {settings.auto_post_enabled}")
        
        # Test limits
        logger.info(f"Daily comment limit: {settings.max_daily_comments}")
        logger.info(f"Daily upvote limit: {settings.max_daily_upvotes}")
        
        # Test subreddit configuration
        logger.info(f"Selected subreddits: {settings.selected_subreddits}")
        logger.info(f"Active keywords: {settings.active_keywords}")
        logger.info(f"Engagement schedule: {settings.engagement_schedule}")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Error testing automation logic: {e}")
        if 'db' in locals():
            db.close()
        return False

def test_automation_toggles(account_id: int):
    """Test automation toggle functionality"""
    logger.info("Testing automation toggles...")
    
    try:
        db = SessionLocal()
        
        # Get current settings
        settings = db.query(AutomationSettings).filter(
            AutomationSettings.account_id == account_id
        ).first()
        
        if not settings:
            logger.error("No automation settings found")
            return False
        
        # Test toggling upvote automation
        original_upvote_state = settings.auto_upvote_enabled
        settings.auto_upvote_enabled = not original_upvote_state
        db.commit()
        
        # Verify toggle
        updated_settings = db.query(AutomationSettings).filter(
            AutomationSettings.account_id == account_id
        ).first()
        
        if updated_settings.auto_upvote_enabled != original_upvote_state:
            logger.info(f"Upvote automation toggled: {original_upvote_state} -> {updated_settings.auto_upvote_enabled}")
        else:
            logger.error("Failed to toggle upvote automation")
            return False
        
        # Test toggling comment automation
        original_comment_state = settings.auto_comment_enabled
        settings.auto_comment_enabled = not original_comment_state
        db.commit()
        
        # Verify toggle
        updated_settings = db.query(AutomationSettings).filter(
            AutomationSettings.account_id == account_id
        ).first()
        
        if updated_settings.auto_comment_enabled != original_comment_state:
            logger.info(f"Comment automation toggled: {original_comment_state} -> {updated_settings.auto_comment_enabled}")
        else:
            logger.error("Failed to toggle comment automation")
            return False
        
        # Reset to original states
        settings.auto_upvote_enabled = original_upvote_state
        settings.auto_comment_enabled = original_comment_state
        db.commit()
        
        logger.info("Automation toggles test completed successfully")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Error testing automation toggles: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return False

if __name__ == "__main__":
    logger.info("Reddit Dashboard Automation System Test")
    logger.info("=" * 50)
    
    # Get test account
    account_id = get_test_account_id()
    if not account_id:
        logger.error("Failed to get test account. Exiting.")
        sys.exit(1)
    
    # Test automation settings CRUD
    if not test_automation_settings_crud(account_id):
        logger.error("Automation settings CRUD test failed. Exiting.")
        sys.exit(1)
    
    # Test automation logic
    if not test_automation_logic(account_id):
        logger.error("Automation logic test failed. Exiting.")
        sys.exit(1)
    
    # Test automation toggles
    if not test_automation_toggles(account_id):
        logger.error("Automation toggles test failed. Exiting.")
        sys.exit(1)
    
    logger.info("All automation system tests passed!")
    sys.exit(0)
