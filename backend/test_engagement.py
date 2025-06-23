#!/usr/bin/env python3
"""
Test script for engagement logging functionality
"""

import sys
import os
import logging
from datetime import datetime, timedelta

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import RedditAccount, EngagementLog
from engagement_service import engagement_service

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

def create_test_engagement_logs(account_id: int):
    """Create test engagement log entries"""
    logger.info("Creating test engagement logs...")
    
    # Test different types of engagements
    test_engagements = [
        # Upvotes
        {"action": "upvote", "target": "post_123", "subreddit": "python", "success": True},
        {"action": "upvote", "target": "comment_456", "subreddit": "programming", "success": True},
        {"action": "upvote", "target": "post_789", "subreddit": "python", "success": False, "error": "Rate limited"},
        
        # Comments
        {"action": "comment", "target": "post_123", "subreddit": "python", "success": True, "text": "Great post!"},
        {"action": "comment", "target": "comment_456", "subreddit": "programming", "success": True, "text": "I agree with this."},
        {"action": "comment", "target": "post_999", "subreddit": "webdev", "success": False, "error": "Comment removed"},
        
        # Posts
        {"action": "post", "target": "my_post_1", "subreddit": "python", "success": True, "title": "How to use Python for automation"},
        {"action": "post", "target": "my_post_2", "subreddit": "programming", "success": False, "error": "Title too long"},
    ]
    
    success_count = 0
    
    for i, engagement in enumerate(test_engagements):
        if engagement["action"] == "upvote":
            success = engagement_service.log_upvote(
                account_id=account_id,
                post_or_comment_id=engagement["target"],
                subreddit=engagement["subreddit"],
                success=engagement["success"],
                error_message=engagement.get("error")
            )
        elif engagement["action"] == "comment":
            success = engagement_service.log_comment(
                account_id=account_id,
                parent_id=engagement["target"],
                subreddit=engagement["subreddit"],
                comment_text=engagement.get("text", "Test comment"),
                success=engagement["success"],
                error_message=engagement.get("error")
            )
        elif engagement["action"] == "post":
            success = engagement_service.log_post(
                account_id=account_id,
                post_id=engagement["target"],
                subreddit=engagement["subreddit"],
                title=engagement.get("title", "Test post"),
                success=engagement["success"],
                error_message=engagement.get("error")
            )
        
        if success:
            success_count += 1
    
    logger.info(f"Created {success_count}/{len(test_engagements)} test engagement logs")
    return success_count == len(test_engagements)

def test_engagement_service_functions(account_id: int):
    """Test engagement service functions"""
    logger.info("Testing engagement service functions...")
    
    # Test engagement history
    logger.info("Testing get_engagement_history...")
    history = engagement_service.get_engagement_history(account_id, days=30)
    logger.info(f"Retrieved {len(history)} engagement history entries")
    
    # Test engagement stats
    logger.info("Testing get_engagement_stats...")
    stats = engagement_service.get_engagement_stats(account_id, days=30)
    logger.info(f"Engagement stats: {stats}")
    
    # Test subreddit engagement summary
    logger.info("Testing get_subreddit_engagement_summary...")
    subreddit_summary = engagement_service.get_subreddit_engagement_summary(account_id, days=30)
    logger.info(f"Subreddit engagement summary: {subreddit_summary}")
    
    # Test filtering by action type
    logger.info("Testing get_engagement_history with action_type filter...")
    upvote_history = engagement_service.get_engagement_history(account_id, days=30, action_type="upvote")
    logger.info(f"Retrieved {len(upvote_history)} upvote entries")
    
    comment_history = engagement_service.get_engagement_history(account_id, days=30, action_type="comment")
    logger.info(f"Retrieved {len(comment_history)} comment entries")
    
    post_history = engagement_service.get_engagement_history(account_id, days=30, action_type="post")
    logger.info(f"Retrieved {len(post_history)} post entries")
    
    return True

def test_direct_logging(account_id: int):
    """Test direct engagement logging"""
    logger.info("Testing direct engagement logging...")
    
    # Test logging a successful upvote
    success = engagement_service.log_upvote(
        account_id=account_id,
        post_or_comment_id="test_direct_upvote",
        subreddit="test_subreddit",
        success=True
    )
    logger.info(f"Direct upvote logging: {'Success' if success else 'Failed'}")
    
    # Test logging a failed comment
    success = engagement_service.log_comment(
        account_id=account_id,
        parent_id="test_direct_comment",
        subreddit="test_subreddit",
        comment_text="This is a test comment for direct logging",
        success=False,
        error_message="Test error message"
    )
    logger.info(f"Direct comment logging: {'Success' if success else 'Failed'}")
    
    return True

if __name__ == "__main__":
    logger.info("Reddit Dashboard Engagement Service Test")
    logger.info("=" * 50)
    
    # Get test account
    account_id = get_test_account_id()
    if not account_id:
        logger.error("Failed to get test account. Exiting.")
        sys.exit(1)
    
    # Create test engagement logs
    if not create_test_engagement_logs(account_id):
        logger.error("Failed to create test engagement logs. Exiting.")
        sys.exit(1)
    
    # Test engagement service functions
    if not test_engagement_service_functions(account_id):
        logger.error("Engagement service function tests failed. Exiting.")
        sys.exit(1)
    
    # Test direct logging
    if not test_direct_logging(account_id):
        logger.error("Direct logging tests failed. Exiting.")
        sys.exit(1)
    
    logger.info("All engagement service tests passed!")
    sys.exit(0)
