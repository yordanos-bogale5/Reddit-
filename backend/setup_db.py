#!/usr/bin/env python3
"""
Database setup and testing script for Reddit Dashboard
"""

import sys
import os
import logging
from datetime import datetime

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import create_tables, test_connection, SessionLocal
from models import User, RedditAccount, KarmaLog, EngagementLog, ActivityLog

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_database():
    """Set up the database with tables and test data"""
    logger.info("Starting database setup...")
    
    # Test connection
    if not test_connection():
        logger.error("Database connection failed. Exiting.")
        return False
    
    # Create tables
    try:
        create_tables()
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        return False
    
    # Create test user
    try:
        db = SessionLocal()
        
        # Check if test user already exists
        existing_user = db.query(User).filter(User.username == "testuser").first()
        if not existing_user:
            test_user = User(
                username="testuser",
                password_hash="dummy_hash"
            )
            db.add(test_user)
            db.commit()
            logger.info("Test user created successfully")
        else:
            logger.info("Test user already exists")
        
        db.close()
        
    except Exception as e:
        logger.error(f"Failed to create test user: {e}")
        return False
    
    logger.info("Database setup completed successfully!")
    return True

def test_database_operations():
    """Test basic database operations"""
    logger.info("Testing database operations...")
    
    try:
        db = SessionLocal()
        
        # Test user query
        users = db.query(User).all()
        logger.info(f"Found {len(users)} users in database")
        
        # Test account query
        accounts = db.query(RedditAccount).all()
        logger.info(f"Found {len(accounts)} Reddit accounts in database")
        
        # Test karma logs
        karma_logs = db.query(KarmaLog).all()
        logger.info(f"Found {len(karma_logs)} karma log entries")
        
        # Test engagement logs
        engagement_logs = db.query(EngagementLog).all()
        logger.info(f"Found {len(engagement_logs)} engagement log entries")
        
        # Test activity logs
        activity_logs = db.query(ActivityLog).all()
        logger.info(f"Found {len(activity_logs)} activity log entries")
        
        db.close()
        logger.info("Database operations test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"Database operations test failed: {e}")
        return False

if __name__ == "__main__":
    logger.info("Reddit Dashboard Database Setup")
    logger.info("=" * 50)
    
    # Setup database
    if setup_database():
        # Test operations
        if test_database_operations():
            logger.info("All tests passed! Database is ready.")
            sys.exit(0)
        else:
            logger.error("Database operations test failed.")
            sys.exit(1)
    else:
        logger.error("Database setup failed.")
        sys.exit(1)
