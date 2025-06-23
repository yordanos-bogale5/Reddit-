#!/usr/bin/env python3
"""
Test script for analytics endpoints
"""

import sys
import os
import logging
import requests
import time
import subprocess
import signal
from threading import Thread

# Add the backend directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal
from models import RedditAccount

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FastAPITestServer:
    def __init__(self):
        self.process = None
        self.base_url = "http://localhost:8000"
    
    def start(self):
        """Start the FastAPI server"""
        try:
            logger.info("Starting FastAPI server...")
            self.process = subprocess.Popen(
                ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for server to start
            time.sleep(3)
            
            # Test if server is running
            try:
                response = requests.get(f"{self.base_url}/", timeout=5)
                if response.status_code == 200:
                    logger.info("FastAPI server started successfully")
                    return True
            except:
                pass
            
            logger.error("Failed to start FastAPI server")
            return False
            
        except Exception as e:
            logger.error(f"Error starting FastAPI server: {e}")
            return False
    
    def stop(self):
        """Stop the FastAPI server"""
        if self.process:
            logger.info("Stopping FastAPI server...")
            self.process.terminate()
            self.process.wait()
            logger.info("FastAPI server stopped")

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

def test_analytics_endpoints(account_id: int, base_url: str):
    """Test all analytics endpoints"""
    logger.info("Testing analytics endpoints...")
    
    endpoints_to_test = [
        {
            "name": "Analytics Overview",
            "url": f"{base_url}/analytics/?account_id={account_id}",
            "expected_keys": ["account_id", "username", "current_karma", "karma_growth", "activity"]
        },
        {
            "name": "Karma Analytics",
            "url": f"{base_url}/analytics/karma?account_id={account_id}&days=30",
            "expected_keys": ["account_id", "period_days", "karma_history", "growth_stats", "top_subreddits"]
        },
        {
            "name": "Engagement Analytics",
            "url": f"{base_url}/analytics/engagement?account_id={account_id}&days=30",
            "expected_keys": ["account_id", "period_days", "engagement_stats"]
        }
    ]
    
    results = []
    
    for endpoint in endpoints_to_test:
        try:
            logger.info(f"Testing {endpoint['name']}...")
            response = requests.get(endpoint["url"], timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if expected keys are present
                missing_keys = []
                for key in endpoint["expected_keys"]:
                    if key not in data:
                        missing_keys.append(key)
                
                if missing_keys:
                    logger.warning(f"{endpoint['name']}: Missing keys: {missing_keys}")
                    results.append({"endpoint": endpoint["name"], "status": "partial", "data": data})
                else:
                    logger.info(f"{endpoint['name']}: ✓ Success")
                    results.append({"endpoint": endpoint["name"], "status": "success", "data": data})
            
            else:
                logger.error(f"{endpoint['name']}: HTTP {response.status_code} - {response.text}")
                results.append({"endpoint": endpoint["name"], "status": "failed", "error": response.text})
        
        except Exception as e:
            logger.error(f"{endpoint['name']}: Exception - {e}")
            results.append({"endpoint": endpoint["name"], "status": "error", "error": str(e)})
    
    return results

def test_karma_snapshot_endpoint(account_id: int, base_url: str):
    """Test the karma snapshot endpoint"""
    logger.info("Testing karma snapshot endpoint...")
    
    try:
        response = requests.post(f"{base_url}/analytics/karma/snapshot?account_id={account_id}", timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            logger.info(f"Karma snapshot: ✓ Success - {data}")
            return True
        else:
            logger.error(f"Karma snapshot: HTTP {response.status_code} - {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Karma snapshot: Exception - {e}")
        return False

def print_test_results(results):
    """Print test results summary"""
    logger.info("\n" + "=" * 50)
    logger.info("ANALYTICS ENDPOINTS TEST RESULTS")
    logger.info("=" * 50)
    
    success_count = 0
    total_count = len(results)
    
    for result in results:
        status_symbol = "✓" if result["status"] == "success" else "✗"
        logger.info(f"{status_symbol} {result['endpoint']}: {result['status'].upper()}")
        
        if result["status"] == "success":
            success_count += 1
            # Print some sample data
            if "data" in result:
                data = result["data"]
                if "account_id" in data:
                    logger.info(f"   Account ID: {data['account_id']}")
                if "karma_growth" in data:
                    logger.info(f"   Karma Growth: {data['karma_growth']}")
                if "engagement_stats" in data:
                    stats = data["engagement_stats"]
                    logger.info(f"   Total Actions: {stats.get('total_actions', 0)}")
                    logger.info(f"   Success Rate: {stats.get('success_rate', 0)}%")
    
    logger.info(f"\nSUMMARY: {success_count}/{total_count} endpoints working correctly")
    return success_count == total_count

if __name__ == "__main__":
    logger.info("Reddit Dashboard Analytics Endpoints Test")
    logger.info("=" * 50)
    
    # Get test account
    account_id = get_test_account_id()
    if not account_id:
        logger.error("Failed to get test account. Exiting.")
        sys.exit(1)
    
    # Start FastAPI server
    server = FastAPITestServer()
    if not server.start():
        logger.error("Failed to start FastAPI server. Exiting.")
        sys.exit(1)
    
    try:
        # Test analytics endpoints
        results = test_analytics_endpoints(account_id, server.base_url)
        
        # Test karma snapshot endpoint
        snapshot_success = test_karma_snapshot_endpoint(account_id, server.base_url)
        
        # Print results
        all_success = print_test_results(results) and snapshot_success
        
        if all_success:
            logger.info("All analytics endpoint tests passed!")
            exit_code = 0
        else:
            logger.error("Some analytics endpoint tests failed.")
            exit_code = 1
    
    finally:
        # Stop server
        server.stop()
    
    sys.exit(exit_code)
