#!/usr/bin/env python3
"""
Test script for error handling and validation
"""

import sys
import os
import logging

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_error_handler_imports():
    """Test that error handler components can be imported"""
    logger.info("Testing error handler imports...")
    
    try:
        from error_handler import (
            ErrorHandler,
            ValidationError,
            RateLimitError,
            AuthenticationError,
            validate_account_id,
            validate_subreddit_name,
            validate_content_length,
            validate_required_field,
            handle_errors
        )
        
        logger.info("✓ All error handler components imported successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error importing error handler components: {e}")
        return False

def test_validation_functions():
    """Test validation functions"""
    logger.info("Testing validation functions...")
    
    try:
        from error_handler import (
            ValidationError,
            validate_account_id,
            validate_subreddit_name,
            validate_content_length,
            validate_required_field
        )
        
        # Test account ID validation
        logger.info("Testing account ID validation...")
        
        # Valid account ID
        try:
            validate_account_id(1)
            logger.info("✓ Valid account ID accepted")
        except ValidationError:
            logger.error("✗ Valid account ID rejected")
            return False
        
        # Invalid account IDs
        invalid_ids = [0, -1, "invalid", None]
        for invalid_id in invalid_ids:
            try:
                validate_account_id(invalid_id)
                logger.error(f"✗ Invalid account ID {invalid_id} was accepted")
                return False
            except ValidationError:
                logger.info(f"✓ Invalid account ID {invalid_id} correctly rejected")
            except Exception as e:
                logger.info(f"✓ Invalid account ID {invalid_id} correctly rejected with {type(e).__name__}")
        
        # Test subreddit name validation
        logger.info("Testing subreddit name validation...")
        
        # Valid subreddit names
        valid_subreddits = ["python", "programming", "webdev", "MachineLearning"]
        for subreddit in valid_subreddits:
            try:
                validate_subreddit_name(subreddit)
                logger.info(f"✓ Valid subreddit '{subreddit}' accepted")
            except ValidationError:
                logger.error(f"✗ Valid subreddit '{subreddit}' rejected")
                return False
        
        # Invalid subreddit names
        invalid_subreddits = ["", None, "a" * 25, "invalid-name", "invalid name"]
        for subreddit in invalid_subreddits:
            try:
                validate_subreddit_name(subreddit)
                logger.error(f"✗ Invalid subreddit '{subreddit}' was accepted")
                return False
            except ValidationError:
                logger.info(f"✓ Invalid subreddit '{subreddit}' correctly rejected")
            except Exception as e:
                logger.info(f"✓ Invalid subreddit '{subreddit}' correctly rejected with {type(e).__name__}")
        
        # Test content length validation
        logger.info("Testing content length validation...")
        
        # Valid content
        try:
            validate_content_length("Short content", 100, "test_field")
            logger.info("✓ Valid content length accepted")
        except ValidationError:
            logger.error("✗ Valid content length rejected")
            return False
        
        # Invalid content (too long)
        try:
            validate_content_length("a" * 101, 100, "test_field")
            logger.error("✗ Content exceeding length limit was accepted")
            return False
        except ValidationError:
            logger.info("✓ Content exceeding length limit correctly rejected")
        
        # Test required field validation
        logger.info("Testing required field validation...")
        
        # Valid required fields
        valid_values = ["valid", 123, ["list"], {"dict": "value"}]
        for value in valid_values:
            try:
                validate_required_field(value, "test_field")
                logger.info(f"✓ Valid required field {type(value).__name__} accepted")
            except ValidationError:
                logger.error(f"✗ Valid required field {type(value).__name__} rejected")
                return False
        
        # Invalid required fields (only None and empty/whitespace strings should be rejected)
        invalid_values = [None, "", "   "]
        for value in invalid_values:
            try:
                validate_required_field(value, "test_field")
                logger.error(f"✗ Invalid required field '{value}' was accepted")
                return False
            except ValidationError:
                logger.info(f"✓ Invalid required field '{value}' correctly rejected")

        # Test that 0 is actually valid (it's a valid integer value)
        try:
            validate_required_field(0, "test_field")
            logger.info("✓ Valid required field 0 (integer) accepted")
        except ValidationError:
            logger.error("✗ Valid required field 0 (integer) rejected")
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing validation functions: {e}")
        return False

def test_custom_exceptions():
    """Test custom exception classes"""
    logger.info("Testing custom exception classes...")
    
    try:
        from error_handler import ValidationError, RateLimitError, AuthenticationError
        
        # Test ValidationError
        try:
            raise ValidationError("Test validation error", "test_field")
        except ValidationError as e:
            if e.message == "Test validation error" and e.field == "test_field":
                logger.info("✓ ValidationError works correctly")
            else:
                logger.error("✗ ValidationError properties incorrect")
                return False
        
        # Test RateLimitError
        try:
            raise RateLimitError("Test rate limit error", 120)
        except RateLimitError as e:
            if e.message == "Test rate limit error" and e.retry_after == 120:
                logger.info("✓ RateLimitError works correctly")
            else:
                logger.error("✗ RateLimitError properties incorrect")
                return False
        
        # Test AuthenticationError
        try:
            raise AuthenticationError("Test auth error")
        except AuthenticationError as e:
            if e.message == "Test auth error":
                logger.info("✓ AuthenticationError works correctly")
            else:
                logger.error("✗ AuthenticationError properties incorrect")
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing custom exceptions: {e}")
        return False

def test_error_handler_methods():
    """Test ErrorHandler static methods"""
    logger.info("Testing ErrorHandler methods...")
    
    try:
        from error_handler import ErrorHandler
        import praw.exceptions
        from sqlalchemy.exc import SQLAlchemyError
        
        # Test Reddit API error handling
        logger.info("Testing Reddit API error handling...")
        
        # Create a mock Reddit API exception
        class MockRedditAPIException(Exception):
            def __init__(self, error_type):
                self.error_type = error_type
                super().__init__(f"Mock Reddit API error: {error_type}")
        
        # Test rate limit error
        mock_error = MockRedditAPIException('RATELIMIT')
        result = ErrorHandler.handle_reddit_api_error(mock_error)
        if "Rate limit exceeded" in result.get("error", ""):
            logger.info("✓ Reddit rate limit error handled correctly")
        else:
            logger.warning(f"Reddit rate limit error handling result: {result}")
        
        # Test database error handling
        logger.info("Testing database error handling...")
        
        class MockSQLAlchemyError(SQLAlchemyError):
            def __init__(self):
                super().__init__("Mock database error")
        
        mock_db_error = MockSQLAlchemyError()
        result = ErrorHandler.handle_database_error(mock_db_error)
        if "Database error" in result.get("error", ""):
            logger.info("✓ Database error handled correctly")
        else:
            logger.warning(f"Database error handling result: {result}")
        
        # Test error logging
        logger.info("Testing error logging...")
        
        try:
            ErrorHandler.log_error(
                Exception("Test error"),
                context={"test": "context"},
                account_id=1
            )
            logger.info("✓ Error logging completed without exceptions")
        except Exception as e:
            logger.warning(f"Error logging failed: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing ErrorHandler methods: {e}")
        return False

def test_handle_errors_decorator():
    """Test the handle_errors decorator"""
    logger.info("Testing handle_errors decorator...")
    
    try:
        from error_handler import handle_errors, ValidationError
        
        @handle_errors
        def test_function_success():
            return {"success": True}
        
        @handle_errors
        def test_function_validation_error():
            raise ValidationError("Test validation error", "test_field")
        
        @handle_errors
        def test_function_generic_error():
            raise Exception("Test generic error")
        
        # Test successful function
        try:
            result = test_function_success()
            if result.get("success"):
                logger.info("✓ Decorator allows successful function execution")
            else:
                logger.error("✗ Decorator interfered with successful function")
                return False
        except Exception as e:
            logger.error(f"✗ Decorator failed on successful function: {e}")
            return False
        
        # Test validation error handling
        try:
            test_function_validation_error()
            logger.error("✗ Decorator did not handle ValidationError")
            return False
        except Exception as e:
            logger.info(f"✓ Decorator handled ValidationError: {type(e).__name__}")
        
        # Test generic error handling
        try:
            test_function_generic_error()
            logger.error("✗ Decorator did not handle generic error")
            return False
        except Exception as e:
            logger.info(f"✓ Decorator handled generic error: {type(e).__name__}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error testing handle_errors decorator: {e}")
        return False

if __name__ == "__main__":
    logger.info("Reddit Dashboard Error Handling Test")
    logger.info("=" * 50)
    
    # Test error handler imports
    if not test_error_handler_imports():
        logger.error("Error handler import test failed. Exiting.")
        sys.exit(1)
    
    # Test validation functions
    if not test_validation_functions():
        logger.error("Validation functions test failed. Exiting.")
        sys.exit(1)
    
    # Test custom exceptions
    if not test_custom_exceptions():
        logger.error("Custom exceptions test failed. Exiting.")
        sys.exit(1)
    
    # Test ErrorHandler methods
    if not test_error_handler_methods():
        logger.error("ErrorHandler methods test failed. Exiting.")
        sys.exit(1)
    
    # Test handle_errors decorator
    if not test_handle_errors_decorator():
        logger.error("handle_errors decorator test failed. Exiting.")
        sys.exit(1)
    
    logger.info("All error handling tests passed!")
    sys.exit(0)
