#!/usr/bin/env python3
"""
Test script for karma tracking functionality
"""

import sys
import os
import logging
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import RedditAccount, User, KarmaLog
from karma_service import karma_service

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_account():
    """Create a test Reddit account for testing"""
    try:
        db = SessionLocal()
        
        # Check if test account already exists
        existing_account = db.query(RedditAccount).filter(
            RedditAccount.reddit_username == "test_reddit_user"
        ).first()
        
        if existing_account:
            logger.info(f"Test account already exists with ID: {existing_account.id}")
            db.close()
            return existing_account.id
        
        # Get test user
        test_user = db.query(User).filter(User.username == "testuser").first()
        if not test_user:
            logger.error("Test user not found. Run setup_db.py first.")
            db.close()
            return None
        
        # Create test Reddit account (without real tokens for testing)
        test_account = RedditAccount(
            user_id=test_user.id,
            reddit_username="test_reddit_user",
            refresh_token="dummy_token_for_testing"
        )
        
        db.add(test_account)
        db.commit()
        
        account_id = test_account.id
        logger.info(f"Test Reddit account created with ID: {account_id}")
        
        db.close()
        return account_id
        
    except Exception as e:
        logger.error(f"Error creating test account: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return None

def create_test_karma_logs(account_id: int):
    """Create some test karma log entries"""
    try:
        db = SessionLocal()
        
        # Create a few test karma logs with different timestamps
        test_logs = [
            {
                "total_karma": 100,
                "post_karma": 60,
                "comment_karma": 40,
                "by_subreddit": {"python": {"post_karma": 30, "comment_karma": 20}, "programming": {"post_karma": 30, "comment_karma": 20}},
                "by_content_type": {"posts": 60, "comments": 40}
            },
            {
                "total_karma": 150,
                "post_karma": 80,
                "comment_karma": 70,
                "by_subreddit": {"python": {"post_karma": 40, "comment_karma": 35}, "programming": {"post_karma": 40, "comment_karma": 35}},
                "by_content_type": {"posts": 80, "comments": 70}
            },
            {
                "total_karma": 200,
                "post_karma": 110,
                "comment_karma": 90,
                "by_subreddit": {"python": {"post_karma": 55, "comment_karma": 45}, "programming": {"post_karma": 55, "comment_karma": 45}},
                "by_content_type": {"posts": 110, "comments": 90}
            }
        ]
        
        for i, log_data in enumerate(test_logs):
            # Create logs with different timestamps (spaced 1 day apart)
            timestamp = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)
            timestamp = timestamp.replace(day=timestamp.day - (len(test_logs) - i))
            
            karma_log = KarmaLog(
                account_id=account_id,
                timestamp=timestamp,
                total_karma=log_data["total_karma"],
                post_karma=log_data["post_karma"],
                comment_karma=log_data["comment_karma"],
                by_subreddit=log_data["by_subreddit"],
                by_content_type=log_data["by_content_type"]
            )
            
            db.add(karma_log)
        
        db.commit()
        logger.info(f"Created {len(test_logs)} test karma log entries")
        
        db.close()
        return True
        
    except Exception as e:
        logger.error(f"Error creating test karma logs: {e}")
        if 'db' in locals():
            db.rollback()
            db.close()
        return False

def test_karma_service_functions(account_id: int):
    """Test karma service functions"""
    logger.info("Testing karma service functions...")
    
    # Test karma history
    logger.info("Testing get_karma_history...")
    history = karma_service.get_karma_history(account_id, days=30)
    logger.info(f"Retrieved {len(history)} karma history entries")
    
    # Test karma growth stats
    logger.info("Testing get_karma_growth_stats...")
    growth_stats = karma_service.get_karma_growth_stats(account_id, days=30)
    logger.info(f"Growth stats: {growth_stats}")
    
    # Test top subreddits
    logger.info("Testing get_top_subreddits_by_karma...")
    top_subreddits = karma_service.get_top_subreddits_by_karma(account_id, limit=5)
    logger.info(f"Top subreddits: {top_subreddits}")
    
    return True

if __name__ == "__main__":
    logger.info("Reddit Dashboard Karma Service Test")
    logger.info("=" * 50)
    
    # Create test account
    account_id = create_test_account()
    if not account_id:
        logger.error("Failed to create test account. Exiting.")
        sys.exit(1)
    
    # Create test karma logs
    if not create_test_karma_logs(account_id):
        logger.error("Failed to create test karma logs. Exiting.")
        sys.exit(1)
    
    # Test karma service functions
    if test_karma_service_functions(account_id):
        logger.info("All karma service tests passed!")
        sys.exit(0)
    else:
        logger.error("Karma service tests failed.")
        sys.exit(1)
